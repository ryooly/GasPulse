"""Blockchain scanner catchers package.

Public surface: the base engine, the concrete per-chain catchers, shared
exceptions, the ``CapturedBlock`` DTO, and ready-to-use singletons.
"""

from app.exception import (
    InvalidTimeframeError,
    ScannerAPIError,
)
from app.modules.automation.blockchain_catcher.base_client import (
    BaseScannerClient,
    ScannerConfig,
)
from app.modules.automation.blockchain_catcher.base_catcher import (
    BaseBlockchainCatcher,
    CapturedBlock,
)
from app.modules.automation.blockchain_catcher.scanners import (
    ArbiscanCatcher,
    BscScanCatcher,
    EtherscanCatcher,
    PolygonscanCatcher,
    SnowtraceCatcher,
    arbiscan_catcher,
    bscscan_catcher,
    etherscan_catcher,
    polygonscan_catcher,
    snowtrace_catcher,
)

__all__ = [
    "BaseScannerClient",
    "ScannerConfig",
    "BaseBlockchainCatcher",
    "CapturedBlock",
    "InvalidTimeframeError",
    "ScannerAPIError",
    "EtherscanCatcher",
    "PolygonscanCatcher",
    "BscScanCatcher",
    "ArbiscanCatcher",
    "SnowtraceCatcher",
    "etherscan_catcher",
    "polygonscan_catcher",
    "bscscan_catcher",
    "arbiscan_catcher",
    "snowtrace_catcher",
]
