from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.exception import BlockchainNotFoundError, InvalidChartRangeError, ScannerAPIError
from app.models.fee_chart_models import FeeChartData
from app.models.time_unit_models import TimeUnitName
from app.modules.repository import FeeChartRepository
from app.modules.tools import (
    get_token_price_usdt,
    get_transactions_last_24h,
    get_validators_last_24h,
)


class FeeChartService:

    ALLOWED_RANGES: dict[TimeUnitName, tuple[int, ...]] = {
        TimeUnitName.HOUR: (24, 48, 72),
        TimeUnitName.DAY: (7, 14, 21),
        TimeUnitName.WEEK: (3, 6, 9),
    }

    # Native fee unit -> native token conversion factor.
    # EVM base fees are stored in gwei (1e-9 of native token).
    # Bitcoin mempool fees are sat/vB (1e-8 BTC). Solana samples use lamports (1e-9 SOL).
    # Polkadot Subscan total_fee is in planck (1e-10 DOT). Others default to 1 native token.
    _FEE_UNIT_FACTOR: dict[str, Decimal] = {
        "ETH": Decimal("1e-9"),
        "BNB": Decimal("1e-9"),
        "POL": Decimal("1e-9"),
        "AVAX": Decimal("1e-9"),
        "ARB": Decimal("1e-9"),
        "OP": Decimal("1e-9"),
        "BTC": Decimal("1e-8"),
        "SOL": Decimal("1e-9"),
        "DOT": Decimal("1e-10"),
    }

    _USDT_Q = Decimal("0.00000001")

    def __init__(self, repository: FeeChartRepository | None = None) -> None:
        self._repository = repository

    def allowed_ranges(self, time_unit: TimeUnitName) -> tuple[int, ...]:
        return self.ALLOWED_RANGES[time_unit]

    @staticmethod
    def _normalize_name(name: str) -> str:
        return name.strip().lower()

    def _resolve_price_token(self, blockchain_name: str, native_currency: str) -> str:
        # Chainlink chart samples on this project are not a native gas fee; treat as LINK-denominated.
        if self._normalize_name(blockchain_name) == "chainlink":
            return "LINK"
        return native_currency or blockchain_name

    def _convert_points_to_usdt(self, points: list[FeeChartData]) -> list[FeeChartData]:
        if not points:
            return points

        # Avoid double-conversion when the same ORM instances are reused in one session.
        if all(getattr(point, "fee_unit", None) == "USDT" for point in points):
            return points

        blockchain = points[0].blockchain
        native_currency = (getattr(blockchain, "native_currency", None) or getattr(blockchain, "symbol", "") or "").upper()
        token = self._resolve_price_token(getattr(blockchain, "name", ""), native_currency)
        try:
            price_info = get_token_price_usdt(token)
            price_usdt = Decimal(str(price_info["price_usdt"]))
        except Exception as exc:
            raise ScannerAPIError(f"Failed to convert fee values to USDT for {token!r}: {exc}") from exc

        factor = self._FEE_UNIT_FACTOR.get(native_currency, Decimal("1"))
        for point in points:
            if getattr(point, "fee_unit", None) == "USDT":
                continue
            converted = (Decimal(str(point.fee_value)) * factor * price_usdt).quantize(
                self._USDT_Q, rounding=ROUND_HALF_UP
            )
            point.fee_value = converted
            # Transient attribute for schema serialization and idempotent conversion.
            setattr(point, "fee_unit", "USDT")
        return points

    def get_chart(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
        range_: int,
    ) -> list[FeeChartData]:
        if self._repository is None:
            raise RuntimeError("FeeChartRepository is required for chart operations")
        normalized_name = blockchain_name.strip()
        if not normalized_name:
            raise BlockchainNotFoundError("blockchain must not be empty")
        allowed = self.ALLOWED_RANGES[time_unit]
        if range_ not in allowed:
            raise InvalidChartRangeError(time_unit, range_, allowed)
        if not self._repository.blockchain_exists(normalized_name):
            raise BlockchainNotFoundError(f"Blockchain {normalized_name!r} was not found")
        points = self._repository.list_latest_points(
            normalized_name, time_unit, limit=range_,
        )
        return self._convert_points_to_usdt(points)

    def get_token_price(self, token: str) -> dict:
        return get_token_price_usdt(token)

    def get_transactions_24h(self, blockchain_name: str) -> dict:
        return get_transactions_last_24h(blockchain_name)

    def get_validators_24h(self, blockchain_name: str) -> dict:
        return get_validators_last_24h(blockchain_name)


__all__ = ["FeeChartService", "InvalidChartRangeError"]

