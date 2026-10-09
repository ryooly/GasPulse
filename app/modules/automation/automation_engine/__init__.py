from __future__ import annotations

from app.modules.automation.automation_engine.core import (
    SCANNER_CLASSES,
    TIMEFRAME_INTERVAL_SECONDS,
    TimeframeEngine,
    capture_scanner,
)
from app.modules.automation.automation_engine.day import day_engine
from app.modules.automation.automation_engine.hour import hour_engine
from app.modules.automation.automation_engine.week import week_engine

TIMEFRAME_ENGINES: tuple[TimeframeEngine, ...] = (hour_engine, day_engine, week_engine)


def start_all(run_now: bool = False) -> None:
    for engine in TIMEFRAME_ENGINES:
        engine.start(run_now=run_now)


def shutdown_all() -> None:
    for engine in TIMEFRAME_ENGINES:
        engine.shutdown()


__all__ = [
    "TimeframeEngine",
    "capture_scanner",
    "SCANNER_CLASSES",
    "TIMEFRAME_INTERVAL_SECONDS",
    "hour_engine",
    "day_engine",
    "week_engine",
    "TIMEFRAME_ENGINES",
    "start_all",
    "shutdown_all",
]
