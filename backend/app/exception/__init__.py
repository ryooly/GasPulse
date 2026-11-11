"""Central exception package for GasPulse.

Replaces the previous ``app.errorHandler`` module and consolidates:

* the fundamental ``Base`` exception structure and every concrete domain error
  (``ScannerAPIError``, ``InvalidTimeframeError``, ``InvalidChartRangeError``),
* the ``Global`` handler that converts those errors into HTTP responses.
"""

from __future__ import annotations

from .base import (
    Base,
    BlockchainNotFoundError,
    InvalidChartRangeError,
    InvalidTimeframeError,
    InvalidToolInputError,
    ScannerAPIError,
    UnsupportedBlockchainError,
)
from .global_handler import Global

__all__ = [
    "Base",
    "ScannerAPIError",
    "InvalidTimeframeError",
    "InvalidChartRangeError",
    "InvalidToolInputError",
    "UnsupportedBlockchainError",
    "BlockchainNotFoundError",
    "Global",
]
