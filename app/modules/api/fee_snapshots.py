from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.models.fee_snapshot_models import FeeSnapshot
from app.modules.controllers.fee_snapshot_controller import FeeSnapshotController
from app.modules.repository.fee_snapshot_repository import FeeSnapshotRepository
from app.modules.service.fee_snapshot_service import FeeSnapshotService
from app.schemas.fee_snapshot_schemas import FeeSnapshotPublic
from db.session import get_db

router = APIRouter(tags=["fees"])


def get_fee_controller(db: Session = Depends(get_db)) -> FeeSnapshotController:
    repository = FeeSnapshotRepository(session=db)
    service = FeeSnapshotService(repository=repository)
    return FeeSnapshotController(service=service)


@router.get("/hour", response_model=list[FeeSnapshotPublic])
def get_hour_fees(
    blockchain: str = Query(..., min_length=1),
    controller: FeeSnapshotController = Depends(get_fee_controller),
) -> list[FeeSnapshot]:
    snapshot = controller.get_hourly_fees(blockchain)
    return [snapshot] if snapshot is not None else []


@router.get("/day", response_model=list[FeeSnapshotPublic])
def get_day_fees(
    blockchain: str = Query(..., min_length=1),
    controller: FeeSnapshotController = Depends(get_fee_controller),
) -> list[FeeSnapshot]:
    snapshot = controller.get_daily_fees(blockchain)
    return [snapshot] if snapshot is not None else []


@router.get("/week", response_model=list[FeeSnapshotPublic])
def get_week_fees(
    blockchain: str = Query(..., min_length=1),
    controller: FeeSnapshotController = Depends(get_fee_controller),
) -> list[FeeSnapshot]:
    snapshot = controller.get_weekly_fees(blockchain)
    return [snapshot] if snapshot is not None else []


__all__ = ["router"]
