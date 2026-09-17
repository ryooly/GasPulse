from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models
from app.modules.api.fee_snapshots import router as fee_snapshots_router
from db.base import Base
from db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="GasPulse",
    description="Blockchain gas fee snapshots exposed for the frontend.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(fee_snapshots_router)


@app.get("/", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
