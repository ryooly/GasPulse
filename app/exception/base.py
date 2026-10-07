"""Fundamental exception structure for GasPulse.

``Base`` is the single root for every domain error raised by the backend. Concrete
errors subclass it and declare how they should surface (HTTP ``status_code`` and a
machine-readable ``error_code``); the :class:`app.exception.global_handler.Global`
handler then turns any subclass into a response, so routers/controllers no longer
need per-endpoint ``try/except`` blocks.
"""

from __future__ import annotations

from app.models.time_unit_models import TimeUnitName


class Base(Exception):
    """Root class for all GasPulse domain exceptions.

    Carries the HTTP status code and a stable ``error_code`` and knows how to
    serialize itself into the response payload used by the global handler.
    """

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)

    @property
    def default_message(self) -> str:
        return self.__doc__ or self.__class__.__name__

    def to_payload(self) -> dict[str, object]:
        """Response model consumed by :class:`Global`."""
        return {
            "detail": str(self),
            "error": self.error_code,
            "status_code": self.status_code,
        }


class ScannerAPIError(Base):
    """Raised when an HTTP request to a blockchain scanner API fails."""

    status_code = 502
    error_code = "scanner_api_error"


class InvalidTimeframeError(Base):
    """Raised when a timeframe cannot be resolved to a known TimeUnitName."""

    status_code = 400
    error_code = "invalid_timeframe"


class InvalidChartRangeError(Base):
    """Raised when a chart range is not allowed for the requested timeframe."""

    status_code = 422
    error_code = "invalid_chart_range"

    def __init__(
        self,
        time_unit: TimeUnitName,
        requested: int,
        allowed: tuple[int, ...],
    ) -> None:
        self.time_unit = time_unit
        self.requested = requested
        self.allowed = allowed
        super().__init__(
            f"Invalid range {requested} for timeframe '{time_unit.value}'. "
            f"Allowed values: {', '.join(str(value) for value in allowed)}."
        )


__all__ = [
    "Base",
    "ScannerAPIError",
    "InvalidTimeframeError",
    "InvalidChartRangeError",
]
