from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.models.fee_chart_models import FeeChartData
from app.models.time_unit_models import TimeUnitName
from app.modules.automation.blockchain_catcher import (
    ArbiscanCatcher,
    BaseBlockchainCatcher,
    BitcoinMempoolCatcher,
    BscScanCatcher,
    ChainlinkCatcher,
    EtherscanCatcher,
    PolkadotCatcher,
    PolygonscanCatcher,
    SnowtraceCatcher,
    SolanaCatcher,
)
from app.modules.tools import get_token_price_usdt
from db.session import SessionLocal

logger = logging.getLogger("gaspulse.automation.engine")

DEFAULT_SAMPLE_SIZE = 5

SCANNER_CLASSES: tuple[tuple[str, Callable[[], object]], ...] = (
    ("etherscan", EtherscanCatcher),
    ("polygonscan", PolygonscanCatcher),
    ("bscscan", BscScanCatcher),
    ("arbiscan", ArbiscanCatcher),
    ("snowtrace", SnowtraceCatcher),
    ("bitcoin", BitcoinMempoolCatcher),
    ("solana", SolanaCatcher),
    ("polkadot", PolkadotCatcher),
    ("chainlink", ChainlinkCatcher),
)

# token symbol used for USD/USDT conversion per scanner id
SCANNER_PRICE_TOKEN: dict[str, str] = {
    "etherscan": "ETH",
    "polygonscan": "POL",
    "bscscan": "BNB",
    "arbiscan": "ETH",
    "snowtrace": "AVAX",
    "bitcoin": "BTC",
    "solana": "SOL",
    "polkadot": "DOT",
    "chainlink": "LINK",
}

# raw_fee_value unit -> native token factor (same semantics as catcher raw units)
SCANNER_FEE_UNIT_FACTOR: dict[str, Decimal] = {
    "etherscan": Decimal("1e-9"),
    "polygonscan": Decimal("1e-9"),
    "bscscan": Decimal("1e-9"),
    "arbiscan": Decimal("1e-9"),
    "snowtrace": Decimal("1e-9"),
    "bitcoin": Decimal("1e-8"),
    "solana": Decimal("1e-9"),
    "polkadot": Decimal("1e-10"),
    "chainlink": Decimal("1"),
}

_USDT_Q = Decimal("0.00000001")

TIMEFRAME_INTERVAL_SECONDS: dict[TimeUnitName, int] = {
    TimeUnitName.HOUR: 3600,
    TimeUnitName.DAY: 86400,
    TimeUnitName.WEEK: 604800,
}


def _timeframe_value(timeframe: str | TimeUnitName) -> str:
    return timeframe.value if isinstance(timeframe, TimeUnitName) else str(timeframe)


def _resolve_usd_price(scanner_id: str) -> Decimal | None:
    token = SCANNER_PRICE_TOKEN.get(scanner_id)
    if not token:
        return None
    try:
        info = get_token_price_usdt(token)
        return Decimal(str(info["price_usdt"]))
    except Exception:
        logger.warning("failed to resolve USDT price for %s (%s)", scanner_id, token, exc_info=True)
        return None


def _insert_chart_point_usdt(db, snapshot, scanner_id: str, usd_price: Decimal | None) -> None:
    factor = SCANNER_FEE_UNIT_FACTOR.get(scanner_id, Decimal("1"))
    if usd_price is not None:
        fee_usdt = (Decimal(str(snapshot.raw_fee_value)) * factor * usd_price).quantize(_USDT_Q)
    elif snapshot.usd_value is not None:
        fee_usdt = Decimal(str(snapshot.usd_value)).quantize(_USDT_Q)
    else:
        # Fallback: store raw value if conversion unavailable (keeps pipeline running).
        fee_usdt = Decimal(str(snapshot.raw_fee_value))
        logger.warning("storing raw fee_value for %s: no USDT conversion available", scanner_id)
    db.add(
        FeeChartData(
            blockchain_id=snapshot.blockchain_id,
            time_unit_id=snapshot.time_unit_id,
            fee_value=fee_usdt,
            recorded_at=snapshot.recorded_at,
        )
    )
    db.commit()


def capture_scanner(
    catcher_factory: Callable[[], object],
    scanner_id: str,
    timeframe: str | TimeUnitName,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> None:
    unit = _timeframe_value(timeframe)
    db = SessionLocal()
    try:
        catcher = catcher_factory()
        usd_price = _resolve_usd_price(scanner_id)
        snapshot = catcher.capture_and_insert(db, timeframe, sample_size=sample_size, usd_price=usd_price)
        try:
            _insert_chart_point_usdt(db, snapshot, scanner_id, usd_price)
        except Exception:
            db.rollback()
            logger.exception("failed to insert USDT chart point for %s [%s]", scanner_id, unit)
        logger.info(
            "capture %s [%s]: raw=%s usd=%s status=%s block=%s",
            scanner_id,
            unit,
            snapshot.raw_fee_value,
            snapshot.usd_value,
            snapshot.status.value,
            snapshot.block_number,
        )
    except Exception:
        db.rollback()
        logger.exception("capture %s [%s] failed", scanner_id, unit)
    finally:
        db.close()


class TimeframeEngine:

    def __init__(
        self,
        timeframe: TimeUnitName,
        name: str,
        interval_seconds: int | None = None,
        sample_size: int = DEFAULT_SAMPLE_SIZE,
    ) -> None:
        self.timeframe = timeframe
        self.name = name
        self._unit = _timeframe_value(timeframe)
        self.interval_seconds = int(interval_seconds or TIMEFRAME_INTERVAL_SECONDS[timeframe])
        self._sample_size = int(sample_size)
        self._scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 30,
            },
        )

    @property
    def scanner_ids(self) -> tuple[str, ...]:
        return tuple(scanner_id for scanner_id, _ in SCANNER_CLASSES)

    @property
    def running(self) -> bool:
        return self._scheduler.running

    def _job_id(self, scanner_id: str) -> str:
        return f"{self._unit}:{scanner_id}"

    def start(self, run_now: bool = False) -> None:
        if self._scheduler.running:
            logger.warning("%s engine already running; ignoring start()", self.name)
            return
        for scanner_id, catcher_factory in SCANNER_CLASSES:
            task = self._build_task(scanner_id, catcher_factory)
            if run_now:
                self._scheduler.add_job(
                    func=task,
                    trigger=DateTrigger(run_date=datetime.now(timezone.utc)),
                    id=f"{self._job_id(scanner_id)}:immediate",
                    name=f"capture {scanner_id} [{self._unit}] (immediate)",
                    replace_existing=True,
                )
            self._scheduler.add_job(
                func=task,
                trigger=IntervalTrigger(seconds=self.interval_seconds),
                id=self._job_id(scanner_id),
                name=f"capture {scanner_id} [{self._unit}]",
                replace_existing=True,
            )
        self._scheduler.start()
        logger.info(
            "%s engine started: %d scanner API(s) every %ds (run_now=%s)",
            self.name, len(SCANNER_CLASSES), self.interval_seconds, run_now,
        )

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("%s engine stopped", self.name)

    def capture_now(self, scanner_id: str | None = None) -> None:
        selected = [
            (sid, factory) for sid, factory in SCANNER_CLASSES
            if scanner_id is None or sid == scanner_id
        ]
        if not selected:
            raise ValueError(f"No scanner API {scanner_id!r} in {self.name} engine")
        for sid, factory in selected:
            capture_scanner(factory, sid, self.timeframe, self._sample_size)

    def _build_task(
        self, scanner_id: str, catcher_factory: Callable[[], object]
    ) -> Callable[[], None]:
        def task() -> None:
            capture_scanner(catcher_factory, scanner_id, self.timeframe, self._sample_size)

        task.__name__ = f"capture_{self._job_id(scanner_id).replace(':', '_')}"
        return task


__all__ = [
    "DEFAULT_SAMPLE_SIZE",
    "SCANNER_CLASSES",
    "TIMEFRAME_INTERVAL_SECONDS",
    "capture_scanner",
    "TimeframeEngine",
]


