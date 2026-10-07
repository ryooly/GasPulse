"""Day automation engine (APScheduler).

Triggers every scanner API (Etherscan, Polygonscan, BscScan, Arbiscan,
Snowtrace) once per day and runs the capture-and-insert flow for the ``DAY``
timeframe.
"""

from __future__ import annotations

from app.models.time_unit_models import TimeUnitName
from app.modules.automation.automation_engine.core import TimeframeEngine

day_engine = TimeframeEngine(TimeUnitName.DAY, name="day-automation")

start = day_engine.start
shutdown = day_engine.shutdown
capture_now = day_engine.capture_now

__all__ = ["day_engine", "start", "shutdown", "capture_now"]
