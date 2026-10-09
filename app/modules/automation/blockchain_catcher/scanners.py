from __future__ import annotations

from app.modules.automation.blockchain_catcher.base_catcher import BaseBlockchainCatcher
from app.modules.automation.blockchain_catcher.base_client import ScannerConfig


class _EtherscanCompatibleCatcher(BaseBlockchainCatcher):

    env_prefix: str = ""

    def __init__(self, session=None, **config_kwargs):
        config = ScannerConfig.from_env(
            env_prefix=self.env_prefix,
            default_api_url=self.default_api_url,
            default_api_key=self.default_api_key,
        )
        super().__init__(config=config, session=session)


class EtherscanCatcher(_EtherscanCompatibleCatcher):
    blockchain_name = "Ethereum"
    blockchain_symbol = "ETH"
    env_prefix = "ETHERSCAN"
    default_api_url = "https://api.etherscan.io/api"
    default_api_key = "YOUR_ETHERSCAN_API_KEY"


class PolygonscanCatcher(_EtherscanCompatibleCatcher):
    blockchain_name = "Polygon"
    blockchain_symbol = "POL"
    env_prefix = "POLYGONSCAN"
    default_api_url = "https://api.polygonscan.com/api"
    default_api_key = "YOUR_POLYGONSCAN_API_KEY"


class BscScanCatcher(_EtherscanCompatibleCatcher):
    blockchain_name = "BNB Smart Chain"
    blockchain_symbol = "BNB"
    env_prefix = "BSCSCAN"
    default_api_url = "https://api.bscscan.com/api"
    default_api_key = "YOUR_BSCSCAN_API_KEY"


class ArbiscanCatcher(_EtherscanCompatibleCatcher):
    blockchain_name = "Arbitrum"
    blockchain_symbol = "ARB"
    env_prefix = "ARBISCAN"
    default_api_url = "https://api.arbiscan.io/api"
    default_api_key = "YOUR_ARBISCAN_API_KEY"


class SnowtraceCatcher(_EtherscanCompatibleCatcher):
    blockchain_name = "Avalanche"
    blockchain_symbol = "AVAX"
    env_prefix = "SNOWTRACE"
    default_api_url = "https://api.snowtrace.io/api"
    default_api_key = "YOUR_SNOWTRACE_API_KEY"


etherscan_catcher = EtherscanCatcher()
polygonscan_catcher = PolygonscanCatcher()
bscscan_catcher = BscScanCatcher()
arbiscan_catcher = ArbiscanCatcher()
snowtrace_catcher = SnowtraceCatcher()


__all__ = [
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
