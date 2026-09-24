from __future__ import annotations

from app.modules.automation.blockchain_catcher.arbiscan_catcher import (
    ARBISCAN_API_KEY,
    ARBISCAN_API_URL,
    ArbiscanCatcher,
)
from app.modules.automation.blockchain_catcher.base_catcher import (
    BaseBlockchainCatcher,
    BlockchainCatcherError,
    CapturedBlock,
    InvalidTimeframeError,
    ScannerAPIError,
)
from app.modules.automation.blockchain_catcher.bscscan_catcher import (
    BSCSCAN_API_KEY,
    BSCSCAN_API_URL,
    BscScanCatcher,
)
from app.modules.automation.blockchain_catcher.etherscan_catcher import (
    ETHERSCAN_API_KEY,
    ETHERSCAN_API_URL,
    EtherscanCatcher,
)
from app.modules.automation.blockchain_catcher.polygonscan_catcher import (
    POLYGONSCAN_API_KEY,
    POLYGONSCAN_API_URL,
    PolygonscanCatcher,
)
from app.modules.automation.blockchain_catcher.snowtrace_catcher import (
    SNOWTRACE_API_KEY,
    SNOWTRACE_API_URL,
    SnowtraceCatcher,
)

__all__ = [
    "ARBISCAN_API_KEY",
    "ARBISCAN_API_URL",
    "BSCSCAN_API_KEY",
    "BSCSCAN_API_URL",
    "ETHERSCAN_API_KEY",
    "ETHERSCAN_API_URL",
    "POLYGONSCAN_API_KEY",
    "POLYGONSCAN_API_URL",
    "SNOWTRACE_API_KEY",
    "SNOWTRACE_API_URL",
    "ArbiscanCatcher",
    "BaseBlockchainCatcher",
    "BlockchainCatcherError",
    "BscScanCatcher",
    "CapturedBlock",
    "EtherscanCatcher",
    "InvalidTimeframeError",
    "PolygonscanCatcher",
    "ScannerAPIError",
    "SnowtraceCatcher",
]
