from __future__ import annotations

from app.models.time_unit_models import TimeUnitName
from app.modules.automation.automation_engine.core import TimeframeEngine

day_engine = TimeframeEngine(TimeUnitName.DAY, name="day-automation")

start = day_engine.start
shutdown = day_engine.shutdown
capture_now = day_engine.capture_now

__all__ = ["day_engine", "start", "shutdown", "capture_now"]
