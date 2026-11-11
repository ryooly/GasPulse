from __future__ import annotations

from fastapi import APIRouter, Query

from app.modules.testing.service import (
    list_components,
    run_all,
    test_all_catchers,
    test_api_and_services,
    test_automation,
    test_catcher,
    test_database,
)

router = APIRouter(prefix="/testing", tags=["testing"])


@router.get("/", summary="Testing overview")
def testing_overview() -> dict:
    """List all built components, APIs/routes, automation engines, and scanners."""
    return list_components()


@router.get("/components", summary="List components")
def testing_components() -> dict:
    return list_components()


@router.get("/api", summary="Test API and service functions")
def testing_api() -> dict:
    """Run smoke checks against FastAPI routes and chart service/repository logic (SQLite in-memory)."""
    return test_api_and_services()


@router.get("/automation", summary="Test automation engine")
def testing_automation() -> dict:
    """Validate automation engine/scanner registration and instantiation."""
    return test_automation()


@router.get("/catchers", summary="Test all blockchain catchers")
def testing_catchers(
    live: bool = Query(False, description="If true, perform lightweight live network checks/fetches for each catcher."),
    sample_size: int = Query(2, ge=1, le=5, description="Sample size for live fetch where applicable."),
) -> dict:
    """Test all catcher APIs/functions. Default is config/instantiation checks only (no network)."""
    return test_all_catchers(live=live, sample_size=sample_size)


@router.get("/catchers/{scanner_id}", summary="Test one blockchain catcher")
def testing_catcher(
    scanner_id: str,
    live: bool = Query(False, description="If true, perform lightweight live network checks/fetches."),
    sample_size: int = Query(2, ge=1, le=5, description="Sample size for live fetch where applicable."),
) -> dict:
    """Test a single catcher by scanner id (e.g. etherscan, bitcoin, solana, polkadot, chainlink)."""
    return test_catcher(scanner_id=scanner_id, live=live, sample_size=sample_size)


@router.get("/database", summary="Test database connectivity")
def testing_database() -> dict:
    """Check connectivity to the configured DATABASE_URL."""
    return test_database()


@router.get("/run-all", summary="Run all tests")
def testing_run_all(
    live: bool = Query(False, description="If true, include lightweight live network checks for catchers."),
    include_db: bool = Query(True, description="Include configured database connectivity check."),
) -> dict:
    """Run all available checks across APIs, automation, catchers, and database."""
    return run_all(live=live, include_db=include_db)


__all__ = ["router"]
