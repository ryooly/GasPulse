from __future__ import annotations

from app.models.time_unit_models import TimeUnitName
from app.modules.automation.automation_engine.core import TimeframeEngine

week_engine = TimeframeEngine(TimeUnitName.WEEK, name="week-automation")

start = week_engine.start
shutdown = week_engine.shutdown
capture_now = week_engine.capture_now

__all__ = ["week_engine", "start", "shutdown", "capture_now"]
