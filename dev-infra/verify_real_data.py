"""Verify every endpoint serves REAL data from the Docker PostgreSQL database.

Unlike endpoint_tests/ (isolated in-memory SQLite + synthetic fixtures), this
script does NOT override get_db: it talks to the real migrated+seeded Postgres
through the app's actual dependency chain, proving the endpoints work end-to-end
against real persisted data.

Prereq: Postgres running (docker compose up -d) and `python dev-infra/seed.py`.
Run:    python dev-infra/verify_real_data.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://gaspulse:gaspulse@127.0.0.1:5433/gaspulse",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402

client = TestClient(main.app)  # no dependency override -> real DB

_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}  {detail}")


def main_checks() -> None:
    print("Health / metadata")
    r = client.get("/")
    check("GET / -> 200 {'status':'ok'}", r.status_code == 200 and r.json() == {"status": "ok"}, r.text)
    paths = client.get("/openapi.json").json()["paths"]
    check("all routes registered", all(p in paths for p in (
        "/hour", "/day", "/week", "/charts/hour", "/charts/day", "/charts/week")))

    print("\nFee endpoints (real latest snapshot per timeframe)")
    for path, unit in (("/hour", "hour"), ("/day", "day"), ("/week", "week")):
        r = client.get(path, params={"blockchain": "Ethereum"})
        ok = r.status_code == 200 and len(r.json()) == 1
        body = r.json()[0] if ok else {}
        check(
            f"GET {path}?blockchain=Ethereum -> 1 fresh row ({unit})",
            ok and body.get("time_unit") == unit and body.get("blockchain_name") == "Ethereum",
            r.text[:200],
        )
        if ok:
            print(f"        raw_fee_value={body.get('raw_fee_value')} status={body.get('status')}")

    print("\nChart endpoints (range == number of real points)")
    chart_cases = [
        ("/charts/hour", 24, 24), ("/charts/hour", 48, 48), ("/charts/hour", 72, 72),
        ("/charts/day", 7, 7), ("/charts/day", 21, 21),
        ("/charts/week", 3, 3), ("/charts/week", 9, 9),
    ]
    for path, rng, expected in chart_cases:
        r = client.get(path, params={"blockchain": "Ethereum", "range": rng})
        data = r.json() if r.status_code == 200 else []
        ascending = [p["recorded_at"] for p in data] == sorted(p["recorded_at"] for p in data)
        check(f"GET {path}?range={rng} -> {expected} pts, chronological",
              r.status_code == 200 and len(data) == expected and ascending,
              f"status={r.status_code} count={len(data)}")

    print("\nValidation / edge cases")
    r = client.get("/charts/hour", params={"blockchain": "Ethereum", "range": 5})
    check("invalid range -> 422", r.status_code == 422, str(r.status_code))
    r = client.get("/charts/hour", params={"blockchain": "Solana", "range": 24})
    check("unknown blockchain -> 200 []", r.status_code == 200 and r.json() == [], r.text[:120])
    r = client.get("/charts/hour", params={"blockchain": "ethereum", "range": 24})
    check("case-insensitive blockchain -> 24 pts", r.status_code == 200 and len(r.json()) == 24, str(r.status_code))
    r = client.get("/hour")
    check("missing blockchain param -> 422", r.status_code == 422, str(r.status_code))

    print("\nMulti-chain spot check (chart hour range=24)")
    for chain in ("Polygon", "Arbitrum", "Avalanche"):
        r = client.get("/charts/hour", params={"blockchain": chain, "range": 24})
        check(f"{chain} -> 24 pts", r.status_code == 200 and len(r.json()) == 24, str(r.status_code))


if __name__ == "__main__":
    main_checks()
    print(f"\nResult: {_passed} passed, {_failed} failed")
    raise SystemExit(1 if _failed else 0)
