"""Shared building blocks for the per-timeframe automation engines.

Each timeframe lives in its own folder (``hour/``, ``day/``, ``week/``); those
modules only declare *which* timeframe and cadence they use and reuse the pieces
here:

* :data:`SCANNER_CLASSES` - the scanner APIs from ``blockchain_catcher.scanners``.
* :func:`capture_scanner` - runs ONE scanner API call and inserts a ``FeeSnapshot``.
* :class:`TimeframeEngine` - an APScheduler ``BackgroundScheduler`` that triggers
  every scanner API on that timeframe's interval.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.models.time_unit_models import TimeUnitName
from app.modules.automation.blockchain_catcher import (
    ArbiscanCatcher,
    BaseBlockchainCatcher,
    BscScanCatcher,
    EtherscanCatcher,
    PolygonscanCatcher,
    SnowtraceCatcher,
)
from db.session import SessionLocal

logger = logging.getLogger("gaspulse.automation.engine")

DEFAULT_SAMPLE_SIZE = 5

# Every scanner API exposed by blockchain_catcher.scanners, as (id, catcher class).
# Calling the class builds a fresh catcher so config is re-read from env each run.
SCANNER_CLASSES: tuple[tuple[str, Callable[[], BaseBlockchainCatcher]], ...] = (
    ("etherscan", EtherscanCatcher),
    ("polygonscan", PolygonscanCatcher),
    ("bscscan", BscScanCatcher),
    ("arbiscan", ArbiscanCatcher),
    ("snowtrace", SnowtraceCatcher),
)

# How often each timeframe's capture runs (cadence matches the timeframe period).
TIMEFRAME_INTERVAL_SECONDS: dict[TimeUnitName, int] = {
    TimeUnitName.HOUR: 3600,
    TimeUnitName.DAY: 86400,
    TimeUnitName.WEEK: 604800,
}


def _timeframe_value(timeframe: str | TimeUnitName) -> str:
    return timeframe.value if isinstance(timeframe, TimeUnitName) else str(timeframe)


def capture_scanner(
    catcher_factory: Callable[[], BaseBlockchainCatcher],
    scanner_id: str,
    timeframe: str | TimeUnitName,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> None:
    """Run one scanner API call for a timeframe and persist a ``FeeSnapshot``.

    Opens its own DB session; failures are rolled back and logged so a single
    scanner never crashes the scheduler or blocks the other jobs.
    """
    unit = _timeframe_value(timeframe)
    db = SessionLocal()
    try:
        catcher = catcher_factory()
        snapshot = catcher.capture_and_insert(db, timeframe, sample_size=sample_size)
        logger.info(
            "capture %s [%s]: fee=%s status=%s block=%s",
            scanner_id, unit, snapshot.raw_fee_value, snapshot.status.value, snapshot.block_number,
        )
    except Exception:  # keep the scheduler alive regardless of a job's failure
        db.rollback()
        logger.exception("capture %s [%s] failed", scanner_id, unit)
    finally:
        db.close()


class TimeframeEngine:
    """APScheduler engine that triggers every scanner API for one timeframe.

    A single instance is created per timeframe folder (hour / day / week); it
    schedules one recurring job per scanner API on that timeframe's interval.
    """

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
                "coalesce": True,        # collapse missed runs into a single one
                "max_instances": 1,      # never overlap two runs of the same job
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
        """Stop the scheduler if it is running."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("%s engine stopped", self.name)

    def capture_now(self, scanner_id: str | None = None) -> None:
        """Run one (or all) scanner API(s) for this timeframe immediately."""
        selected = [
            (sid, factory) for sid, factory in SCANNER_CLASSES
            if scanner_id is None or sid == scanner_id
        ]
        if not selected:
            raise ValueError(f"No scanner API {scanner_id!r} in {self.name} engine")
        for sid, factory in selected:
            capture_scanner(factory, sid, self.timeframe, self._sample_size)

    def _build_task(
        self, scanner_id: str, catcher_factory: Callable[[], BaseBlockchainCatcher]
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
