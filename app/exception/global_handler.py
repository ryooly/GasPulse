"""Global exception handler wiring for the FastAPI application.

:class:`Global` is the single place that knows how to translate the domain
exceptions defined in :mod:`app.exception.base` into HTTP responses. Registering
it on the app removes the need for scattered ``try/except ... raise HTTPException``
blocks in every router.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exception.base import Base


class Global:
    """App-wide translator from :class:`Base` exceptions to JSON responses.

    Each exception carries its own ``status_code`` and response model (via
    ``to_payload``), so this handler stays generic and simply forwards them. The
    payload keeps FastAPI's conventional ``detail`` key for backwards-compatible
    clients while adding a machine-readable ``error`` code.
    """

    @staticmethod
    def register(app: FastAPI) -> None:
        """Attach the handler to ``app`` for the whole ``Base`` hierarchy."""
        app.add_exception_handler(Base, Global.handle)

    @staticmethod
    async def handle(request: Request, exc: Base) -> JSONResponse:
        payload = exc.to_payload()
        status_code = payload.pop("status_code", exc.status_code)
        return JSONResponse(status_code=status_code, content=payload)


__all__ = ["Global"]
