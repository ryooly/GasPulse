from __future__ import annotations


class ScannerAPIError(Exception):
    """Raised when an HTTP request to a blockchain scanner API fails."""


class InvalidTimeframeError(ValueError):
    """Raised when a timeframe cannot be resolved to a known TimeUnitName."""


__all__ = ["ScannerAPIError", "InvalidTimeframeError"]


# ERROR HANDLER