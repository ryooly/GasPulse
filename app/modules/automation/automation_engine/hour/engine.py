from __future__ import annotations

from app.models.time_unit_models import TimeUnitName
from app.modules.automation.automation_engine.core import TimeframeEngine

hour_engine = TimeframeEngine(TimeUnitName.HOUR, name="hour-automation")

start = hour_engine.start
shutdown = hour_engine.shutdown
capture_now = hour_engine.capture_now

__all__ = ["hour_engine", "start", "shutdown", "capture_now"]
