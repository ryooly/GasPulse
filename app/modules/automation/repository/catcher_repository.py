from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.models.blockchains import Blockchain
from app.models.fee_snapshot_models import FeeSnapshot
from app.models.time_unit_models import TimeUnit, TimeUnitName


class CatcherRepository:
    """Encapsulates all DB operations needed by BaseBlockchainCatcher."""

    def __init__(self, db) -> None:
        self._db = db

    def get_or_create_blockchain(
        self, name: str, symbol: str, api_url: str
    ) -> Blockchain:
        blockchain = self._db.scalars(
            select(Blockchain).where(Blockchain.name == name)
        ).first()
        if blockchain is None:
            blockchain = Blockchain(
                name=name,
                symbol=symbol,
                native_currency=symbol,
                explorer_api_url=api_url,
                is_active=True,
            )
            self._db.add(blockchain)
            self._db.commit()
            self._db.refresh(blockchain)
        return blockchain

    def get_or_create_time_unit(self, unit: TimeUnitName, seconds: int) -> TimeUnit:
        time_unit = self._db.scalars(
            select(TimeUnit).where(TimeUnit.name == unit)
        ).first()
        if time_unit is None:
            time_unit = TimeUnit(name=unit, interval_seconds=seconds)
            self._db.add(time_unit)
            self._db.commit()
            self._db.refresh(time_unit)
        return time_unit

    def get_previous_fee(
        self, blockchain_id: int, time_unit_id: int
    ) -> Decimal | None:
        prior = self._db.scalars(
            select(FeeSnapshot)
            .where(
                FeeSnapshot.blockchain_id == blockchain_id,
                FeeSnapshot.time_unit_id == time_unit_id,
            )
            .order_by(FeeSnapshot.id.desc())
            .limit(1)
        ).first()
        return prior.raw_fee_value if prior is not None else None

    def insert_snapshot(self, snapshot: FeeSnapshot) -> FeeSnapshot:
        self._db.add(snapshot)
        self._db.commit()
        self._db.refresh(snapshot)
        return snapshot


__all__ = ["CatcherRepository"]
