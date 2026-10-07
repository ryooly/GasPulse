from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.models.fee_chart_models import FeeChartData
from app.modules.controllers.fee_chart_controller import FeeChartController
from app.modules.repository.fee_chart_repository import FeeChartRepository
from app.modules.service.fee_chart_service import FeeChartService
from app.schemas.fee_chart_schemas import FeeChartPointPublic
from db.session import get_db

router = APIRouter(prefix="/charts", tags=["charts"])


def get_chart_controller(db: Session = Depends(get_db)) -> FeeChartController:
    repository = FeeChartRepository(session=db)
    service = FeeChartService(repository=repository)
    return FeeChartController(service=service)


@router.get("/hour", response_model=list[FeeChartPointPublic])
def get_hour_chart(
    blockchain: str = Query(..., min_length=1),
    points: int = Query(
        24,
        alias="range",
        ge=1,
        description="Hourly points to plot: 24 (1 day), 48 (2 days) or 72 (3 days).",
    ),
    controller: FeeChartController = Depends(get_chart_controller),
) -> list[FeeChartData]:
    return controller.get_hourly_chart(blockchain, points)


@router.get("/day", response_model=list[FeeChartPointPublic])
def get_day_chart(
    blockchain: str = Query(..., min_length=1),
    points: int = Query(
        7,
        alias="range",
        ge=1,
        description="Daily points to plot: 7 (1 week), 14 (2 weeks) or 21 (3 weeks).",
    ),
    controller: FeeChartController = Depends(get_chart_controller),
) -> list[FeeChartData]:
    return controller.get_daily_chart(blockchain, points)


@router.get("/week", response_model=list[FeeChartPointPublic])
def get_week_chart(
    blockchain: str = Query(..., min_length=1),
    points: int = Query(
        3,
        alias="range",
        ge=1,
        description="Weekly points to plot: 3, 6 or 9.",
    ),
    controller: FeeChartController = Depends(get_chart_controller),
) -> list[FeeChartData]:
    return controller.get_weekly_chart(blockchain, points)


__all__ = ["router"]
