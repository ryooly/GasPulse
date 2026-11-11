from __future__ import annotations

import time
import traceback
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.exception import Base as AppException
from app.models import Blockchain, FeeChartData, FeeSnapshot, TimeUnit, TimeUnitName
from app.modules.automation.automation_engine.core import SCANNER_CLASSES
from app.modules.automation.automation_engine import TIMEFRAME_ENGINES
from app.modules.automation.blockchain_catcher import (
    ArbiscanCatcher,
    BaseExternalCatcher,
    BitcoinMempoolCatcher,
    BscScanCatcher,
    ChainlinkCatcher,
    EtherscanCatcher,
    PolkadotCatcher,
    PolygonscanCatcher,
    SnowtraceCatcher,
    SolanaCatcher,
)
from db.base import Base
from db.session import DATABASE_URL, engine

CATCHER_CLASSES: dict[str, type] = {
    "etherscan": EtherscanCatcher,
    "polygonscan": PolygonscanCatcher,
    "bscscan": BscScanCatcher,
    "arbiscan": ArbiscanCatcher,
    "snowtrace": SnowtraceCatcher,
    "bitcoin": BitcoinMempoolCatcher,
    "solana": SolanaCatcher,
    "polkadot": PolkadotCatcher,
    "chainlink": ChainlinkCatcher,
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _sqlite_session() -> Session:
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(bind=test_engine)
    SessionTest = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
    db = SessionTest()
    try:
        yield db
    finally:
        db.close()
        test_engine.dispose()


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, (bytes, bytearray)):
        try:
            return value.value
        except Exception:
            pass
    if hasattr(value, "__dict__") and not is_dataclass(value):
        try:
            return {k: _serialize(v) for k, v in vars(value).items() if not k.startswith("_")}
        except Exception:
            return str(value)
    if is_dataclass(value):
        return {k: _serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(v) for v in value]
    return str(value)


def _result(name: str, ok: bool, duration_ms: float, detail: Any = None, error: str | None = None, skipped: bool = False) -> dict[str, Any]:
    payload = {
        "name": name,
        "status": "skipped" if skipped else ("pass" if ok else "fail"),
        "ok": ok and not skipped,
        "skipped": skipped,
        "duration_ms": round(duration_ms, 2),
        "detail": _serialize(detail),
    }
    if error:
        payload["error"] = error
    return payload


def run_check(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        detail = fn()
        if isinstance(detail, dict) and detail.get("skipped"):
            return _result(name, ok=True, duration_ms=(time.perf_counter() - start) * 1000, detail=detail, skipped=True)
        return _result(name, ok=True, duration_ms=(time.perf_counter() - start) * 1000, detail=detail)
    except AppException as exc:
        return _result(name, ok=False, duration_ms=(time.perf_counter() - start) * 1000, error=f"{exc.error_code}: {exc}")
    except Exception as exc:
        return _result(name, ok=False, duration_ms=(time.perf_counter() - start) * 1000, error=f"{type(exc).__name__}: {exc}")


def list_components() -> dict[str, Any]:
    catchers = []
    for scanner_id, cls in CATCHER_CLASSES.items():
        inst = cls()
        cfg = inst.config
        catchers.append({
            "scanner_id": scanner_id,
            "class": cls.__name__,
            "blockchain_name": getattr(inst, "blockchain_name", None),
            "blockchain_symbol": getattr(inst, "blockchain_symbol", None),
            "api_url": getattr(cfg, "api_url", None),
            "has_api_key": bool(getattr(cfg, "api_key", "")),
            "kind": "external" if isinstance(inst, BaseExternalCatcher) else "evm",
        })
    engines = []
    for e in TIMEFRAME_ENGINES:
        engines.append({
            "name": e.name,
            "timeframe": e.timeframe.value,
            "interval_seconds": e.interval_seconds,
            "running": e.running,
            "scanner_ids": list(e.scanner_ids),
        })
    routes = []
    try:
        from app.main import app
        for r in app.routes:
            routes.append({
                "path": getattr(r, "path", getattr(r, "path_format", None)),
                "methods": sorted(list(getattr(r, "methods", []) or [])),
                "name": getattr(r, "name", None),
            })
    except Exception as exc:
        routes = [{"error": f"{type(exc).__name__}: {exc}"}]
    return {
        "generated_at": _utcnow_iso(),
        "database_url_configured": DATABASE_URL,
        "registered_scanners": [s for s, _ in SCANNER_CLASSES],
        "catchers": catchers,
        "engines": engines,
        "routes": routes,
    }


def _db_check() -> dict[str, Any]:
    with engine.connect() as conn:
        value = conn.execute(text("SELECT 1")).scalar()
    return {"database_url": DATABASE_URL, "select_1": value}


def _seed_chart_data(db: Session) -> dict[str, Any]:
    chain = Blockchain(name="TestChain", symbol="TST", native_currency="TST", explorer_api_url="https://example.test", is_active=True)
    db.add(chain)
    db.flush()
    unit = TimeUnit(name=TimeUnitName.HOUR, interval_seconds=3600)
    db.add(unit)
    db.flush()
    now = datetime.now(timezone.utc)
    from decimal import Decimal
    point = FeeChartData(blockchain_id=chain.id, time_unit_id=unit.id, fee_value=Decimal("1.23"), recorded_at=now)
    snap = FeeSnapshot(blockchain_id=chain.id, time_unit_id=unit.id, raw_fee_value=Decimal("1.23"), sample_count=1, block_number=1, recorded_at=now)
    db.add(point)
    db.add(snap)
    db.commit()
    return {"blockchain": chain.name, "time_unit": unit.name.value}


def _chart_service_check() -> dict[str, Any]:
    from app.modules.repository.fee_chart_repository import FeeChartRepository
    from app.modules.service.fee_chart_service import FeeChartService
    with _sqlite_session() as db:
        seeded = _seed_chart_data(db)
        repo = FeeChartRepository(db)
        svc = FeeChartService(repo)
        points = svc.get_chart("TestChain", TimeUnitName.HOUR, 24)
        return {
            "seeded": seeded,
            "points_returned": len(points),
            "first_fee_value": str(points[0].fee_value) if points else None,
            "allowed_ranges": {k.value: v for k, v in svc.ALLOWED_RANGES.items()},
        }


def _api_smoke_check() -> dict[str, Any]:
    from app.main import app
    client = TestClient(app)
    results = {}
    r = client.get("/")
    results["health"] = {"status_code": r.status_code, "json": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text}
    # charts likely empty without seeded DB but endpoint should respond or return domain error cleanly
    r = client.get("/charts/hour", params={"blockchain": "__not_found__", "range": 24})
    results["chart_hour_not_found"] = {"status_code": r.status_code, "body": _safe_body(r)}
    return results


def _safe_body(response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text[:500]


def _catcher_dry_run(scanner_id: str, live: bool = False, sample_size: int = 2) -> dict[str, Any]:
    cls = CATCHER_CLASSES.get(scanner_id)
    if cls is None:
        raise ValueError(f"Unknown scanner_id {scanner_id!r}. Known: {sorted(CATCHER_CLASSES)}")
    inst = cls()
    info = {
        "scanner_id": scanner_id,
        "class": cls.__name__,
        "blockchain_name": getattr(inst, "blockchain_name", None),
        "blockchain_symbol": getattr(inst, "blockchain_symbol", None),
        "api_url": getattr(inst.config, "api_url", None),
        "has_api_key": bool(getattr(inst.config, "api_key", "")),
        "live": live,
    }
    if not live:
        info["note"] = "Instantiation/config validation only. Pass live=true to perform a lightweight network fetch/sample."
        return info

    if isinstance(inst, BaseExternalCatcher):
        samples = inst.fetch_fee_samples(seconds=3600, sample_size=max(1, min(sample_size, 5)))
        info["sample_count"] = len(samples)
        info["samples"] = [{"number": s.number, "timestamp": s.timestamp, "fee": str(s.fee_gwei)} for s in samples[:5]]
        metrics = inst.compute_snapshot_metrics(samples)
        info["metrics_status"] = getattr(metrics.get("status"), "value", metrics.get("status"))
        info["raw_fee_value"] = str(metrics.get("raw_fee_value"))
        return info

    # EVM/Etherscan-like: use lightweight calls
    try:
        oracle = inst.get_gas_oracle()
        info["gas_oracle_keys"] = sorted(list(oracle.keys())) if isinstance(oracle, dict) else str(type(oracle))
    except Exception as exc:
        info["gas_oracle_error"] = f"{type(exc).__name__}: {exc}"
    try:
        latest = inst.get_latest_block_number()
        info["latest_block_number"] = latest
    except Exception as exc:
        info["latest_block_error"] = f"{type(exc).__name__}: {exc}"
    if "gas_oracle_error" in info and "latest_block_error" in info:
        raise RuntimeError(f"EVM catcher live checks failed: gas_oracle={info['gas_oracle_error']}; latest_block={info['latest_block_error']}")
    return info


def test_catcher(scanner_id: str, live: bool = False, sample_size: int = 2) -> dict[str, Any]:
    return run_check(f"catcher:{scanner_id}", lambda: _catcher_dry_run(scanner_id, live=live, sample_size=sample_size))


def test_all_catchers(live: bool = False, sample_size: int = 2) -> dict[str, Any]:
    results = [test_catcher(sid, live=live, sample_size=sample_size) for sid in CATCHER_CLASSES]
    summary = {
        "total": len(results),
        "pass": sum(1 for r in results if r["status"] == "pass"),
        "fail": sum(1 for r in results if r["status"] == "fail"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
    }
    return {"generated_at": _utcnow_iso(), "live": live, "summary": summary, "results": results}


def test_automation() -> dict[str, Any]:
    checks = []
    checks.append(run_check("automation:registered_scanners", lambda: {
        "registered": [s for s, _ in SCANNER_CLASSES],
        "expected_present": sorted(CATCHER_CLASSES),
        "matches_catchers": sorted([s for s, _ in SCANNER_CLASSES]) == sorted(CATCHER_CLASSES),
    }))
    checks.append(run_check("automation:engines", lambda: {
        "engines": [{
            "name": e.name,
            "timeframe": e.timeframe.value,
            "interval_seconds": e.interval_seconds,
            "running": e.running,
            "scanner_count": len(e.scanner_ids),
        } for e in TIMEFRAME_ENGINES]
    }))
    checks.append(run_check("automation:engine_instantiation", lambda: {
        "instantiated": [cls().blockchain_name for _, cls in SCANNER_CLASSES],
    }))
    summary = {"total": len(checks), "pass": sum(1 for c in checks if c["status"] == "pass"), "fail": sum(1 for c in checks if c["status"] == "fail"), "skipped": sum(1 for c in checks if c["status"] == "skipped")}
    return {"generated_at": _utcnow_iso(), "summary": summary, "results": checks}


def test_api_and_services() -> dict[str, Any]:
    checks = []
    checks.append(run_check("api:app_routes", lambda: {
        "routes": [getattr(r, "path", getattr(r, "path_format", None)) for r in __import__("app.main", fromlist=["app"]).app.routes]
    }))
    checks.append(run_check("service:fee_chart_sqlite", _chart_service_check))
    checks.append(run_check("api:smoke", _api_smoke_check))
    summary = {"total": len(checks), "pass": sum(1 for c in checks if c["status"] == "pass"), "fail": sum(1 for c in checks if c["status"] == "fail"), "skipped": sum(1 for c in checks if c["status"] == "skipped")}
    return {"generated_at": _utcnow_iso(), "summary": summary, "results": checks}


def test_database() -> dict[str, Any]:
    checks = [run_check("database:connectivity", _db_check)]
    summary = {"total": len(checks), "pass": sum(1 for c in checks if c["status"] == "pass"), "fail": sum(1 for c in checks if c["status"] == "fail"), "skipped": sum(1 for c in checks if c["status"] == "skipped")}
    return {"generated_at": _utcnow_iso(), "summary": summary, "results": checks}


def run_all(live: bool = False, include_db: bool = True) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    sections["components"] = list_components()
    sections["api_and_services"] = test_api_and_services()
    sections["automation"] = test_automation()
    sections["catchers"] = test_all_catchers(live=live)
    if include_db:
        sections["database"] = test_database()
    else:
        sections["database"] = {"skipped": True, "reason": "include_db=false"}
    failures = []
    for name, sec in sections.items():
        if isinstance(sec, dict):
            for r in sec.get("results", []) or []:
                if r.get("status") == "fail":
                    failures.append({"section": name, "check": r.get("name"), "error": r.get("error")})
    ok = len(failures) == 0
    return {"generated_at": _utcnow_iso(), "ok": ok, "live": live, "include_db": include_db, "failure_count": len(failures), "failures": failures, "sections": sections}

