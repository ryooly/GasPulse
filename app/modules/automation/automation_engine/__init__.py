"""Automation engine package.

The automation is split by timeframe into three folders, each an APScheduler
engine that triggers every scanner API on that timeframe's interval and runs the
capture-and-insert flow:

* :mod:`.hour` -> ``hour_engine``  (every scanner, hourly)
* :mod:`.day`  -> ``day_engine``   (every scanner, daily)
* :mod:`.week` -> ``week_engine``  (every scanner, weekly)

Shared pieces (:class:`TimeframeEngine`, :func:`capture_scanner`, the scanner
list) live in :mod:`.core`. Start any subset with each engine's ``start()`` or
use ``start_all()`` / ``shutdown_all()``.
"""

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

# All timeframe engines, in capture-frequency order.
TIMEFRAME_ENGINES: tuple[TimeframeEngine, ...] = (hour_engine, day_engine, week_engine)


def start_all(run_now: bool = False) -> None:
    """Start the hour, day and week engines together."""
    for engine in TIMEFRAME_ENGINES:
        engine.start(run_now=run_now)


def shutdown_all() -> None:
    """Stop every timeframe engine that is currently running."""
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
