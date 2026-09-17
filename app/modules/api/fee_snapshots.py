from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.blockchains import Blockchain
from app.models.fee_snapshot_models import FeeSnapshot
from app.models.time_unit_models import TimeUnit, TimeUnitName
from app.schemas.fee_snapshot_schemas import FeeSnapshotPublic
from db.session import get_db

router = APIRouter(tags=["fees"])


@router.get("/hour", response_model=list[FeeSnapshotPublic])
def get_hour_fees(
    blockchain: str = Query(
        ..., min_length=1,
    ),
    db: Session = Depends(get_db),
) -> list[FeeSnapshot]:
    return


@router.get("/day", response_model=list[FeeSnapshotPublic])
def get_day_fees(
    blockchain: str = Query(
        ..., min_length=1,
    ),
    db: Session = Depends(get_db),
) -> list[FeeSnapshot]:
    return


@router.get("/week", response_model=list[FeeSnapshotPublic])
def get_week_fees(
    blockchain: str = Query(
        ..., min_length=1,
    ),
    db: Session = Depends(get_db),
) -> list[FeeSnapshot]:
    return


__all__ = ["router"]
