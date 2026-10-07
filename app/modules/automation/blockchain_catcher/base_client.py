from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import requests

from app.exception import ScannerAPIError


@dataclass
class ScannerConfig:
    api_url: str
    api_key: str = ""
    connect_timeout: float = 5.0
    read_timeout: float = 10.0
    max_retries: int = 3
    backoff_factor: float = 0.5
    extra_headers: dict[str, str] = field(default_factory=dict)

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.connect_timeout, self.read_timeout)

    @classmethod
    def from_env(
        cls,
        env_prefix: str,
        default_api_url: str,
        default_api_key: str = "",
    ) -> "ScannerConfig":
        api_url = os.getenv(f"{env_prefix}_API_URL", default_api_url)
        api_key = os.getenv(f"{env_prefix}_API_KEY", default_api_key)
        return cls(api_url=api_url, api_key=api_key)


class BaseScannerClient:

    def __init__(self, config: ScannerConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    @property
    def api_url(self) -> str:
        return self.config.api_url

    @property
    def api_key(self) -> str:
        return self.config.api_key

    def _build_params(self, params: dict | None) -> dict:
        merged = dict(params or {})
        if self.config.api_key:
            merged.setdefault("apikey", self.config.api_key)
        return merged

    def request(
        self,
        params: dict | None = None,
        timeout: tuple[float, float] | None = None,
    ) -> dict:
        url = self.config.api_url
        eff_timeout = timeout or self.config.timeout
        request_params = self._build_params(params)
        headers = {"Accept": "application/json", **self.config.extra_headers}

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.get(
                    url, params=request_params, headers=headers, timeout=eff_timeout,
                )
                status_code = getattr(response, "status_code", None)
                if isinstance(status_code, int) and status_code >= 500:
                    raise ScannerAPIError(
                        f"HTTP request to {url} failed with status {status_code}"
                    )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ScannerAPIError) as exc:
                last_error = exc
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.backoff_factor * (2 ** attempt))

        raise ScannerAPIError(f"HTTP request to {url} failed: {last_error}")


__all__ = ["ScannerConfig", "BaseScannerClient"]
