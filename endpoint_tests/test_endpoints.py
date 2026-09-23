"""Endpoint verification for GasPulse.

Covers every app-defined route:
  * health   -> GET /
  * fees     -> GET /hour, /day, /week
  * charts   -> GET /charts/hour, /charts/day, /charts/week
  * metadata -> GET /openapi.json, /docs

Run with:  python -m pytest endpoint_tests -v
      or:  python endpoint_tests/run_tests.py
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.models.fee_snapshot_models import FeeSnapshot, FeeStatus
from app.models.time_unit_models import TimeUnitName
from db.base import utcnow


# --------------------------------------------------------------------------- #
# metadata / health
# --------------------------------------------------------------------------- #
def test_health(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_lists_all_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    for expected in (
        "/", "/hour", "/day", "/week",
        "/charts/hour", "/charts/day", "/charts/week",
    ):
        assert expected in paths, f"missing route {expected}"


def test_docs_available(client):
    assert client.get("/docs").status_code == 200


# --------------------------------------------------------------------------- #
# fee endpoints (single latest *valid* snapshot, wrapped in a list)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path,unit", [
    ("/hour", "hour"), ("/day", "day"), ("/week", "week"),
])
def test_fee_returns_fresh_latest(client, seed_fees, path, unit):
    resp = client.get(path, params={"blockchain": seed_fees.blockchain_name})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    point = body[0]
    assert point["blockchain_name"] == "Ethereum"
    assert point["time_unit"] == unit
    assert point["status"] == FeeStatus.STABLE.value
    # internal-only fields must not leak to the public payload
    assert "created_at" not in point
    assert "blockchain_id" not in point
    assert "time_unit_id" not in point


def test_fee_stale_snapshot_is_excluded(client, seed_base):
    """A snapshot older than its interval is not 'valid' -> empty list."""
    stale_at = utcnow() - timedelta(hours=5)  # hour interval is 1h
    with seed_base.session_factory() as db:
        db.add(FeeSnapshot(
            blockchain_id=seed_base.blockchain_id,
            time_unit_id=seed_base.unit_ids[TimeUnitName.HOUR],
            raw_fee_value=2.0,
            status=FeeStatus.STABLE,
            recorded_at=stale_at,
        ))
        db.commit()
    resp = client.get("/hour", params={"blockchain": "Ethereum"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_fee_blockchain_lookup_is_case_insensitive(client, seed_fees):
    resp = client.get("/hour", params={"blockchain": "ethereum"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_fee_unknown_blockchain_returns_empty(client, seed_fees):
    resp = client.get("/hour", params={"blockchain": "Solana"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_fee_missing_blockchain_param_is_422(client, seed_fees):
    assert client.get("/hour").status_code == 422


# --------------------------------------------------------------------------- #
# chart endpoints (range == number of points retrieved)
# --------------------------------------------------------------------------- #
def test_chart_hour_range_returns_n_points_ascending(client, seed_charts):
    resp = client.get("/charts/hour", params={"blockchain": "Ethereum", "range": 24})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 24
    timestamps = [p["recorded_at"] for p in body]
    assert timestamps == sorted(timestamps), "series must be chronological"
    sample = body[0]
    assert sample["blockchain_name"] == "Ethereum"
    assert sample["time_unit"] == "hour"
    assert set(sample) == {"id", "blockchain_name", "time_unit", "fee_value", "recorded_at"}


def test_chart_hour_default_range_is_24(client, seed_charts):
    resp = client.get("/charts/hour", params={"blockchain": "Ethereum"})
    assert resp.status_code == 200
    assert len(resp.json()) == 24


def test_chart_hour_range_48_returns_available(client, seed_charts):
    """Only 30 hourly points seeded, so range=48 returns all 30."""
    resp = client.get("/charts/hour", params={"blockchain": "Ethereum", "range": 48})
    assert resp.status_code == 200
    assert len(resp.json()) == 30


@pytest.mark.parametrize("path,default_range", [
    ("/charts/day", 7), ("/charts/week", 3),
])
def test_chart_day_and_week(client, seed_charts, path, default_range):
    resp = client.get(path, params={"blockchain": "Ethereum"})
    assert resp.status_code == 200
    assert len(resp.json()) == default_range


@pytest.mark.parametrize("path,bad_range", [
    ("/charts/hour", 5), ("/charts/hour", 25),
    ("/charts/day", 10), ("/charts/week", 4),
])
def test_chart_invalid_range_is_422(client, seed_charts, path, bad_range):
    resp = client.get(path, params={"blockchain": "Ethereum", "range": bad_range})
    assert resp.status_code == 422
    assert "Allowed values" in resp.json()["detail"]


@pytest.mark.parametrize("path,valid_ranges", [
    ("/charts/hour", [24, 48, 72]),
    ("/charts/day", [7, 14, 21]),
    ("/charts/week", [3, 6, 9]),
])
def test_chart_all_valid_ranges_accepted(client, seed_charts, path, valid_ranges):
    for value in valid_ranges:
        resp = client.get(path, params={"blockchain": "Ethereum", "range": value})
        assert resp.status_code == 200, f"{path} range={value} should be valid"


def test_chart_range_below_minimum_is_422(client, seed_charts):
    resp = client.get("/charts/hour", params={"blockchain": "Ethereum", "range": 0})
    assert resp.status_code == 422  # FastAPI ge=1 validation


def test_chart_blockchain_lookup_is_case_insensitive(client, seed_charts):
    resp = client.get("/charts/hour", params={"blockchain": "ETHEREUM", "range": 24})
    assert resp.status_code == 200
    assert len(resp.json()) == 24


def test_chart_unknown_blockchain_returns_empty(client, seed_charts):
    resp = client.get("/charts/hour", params={"blockchain": "Solana", "range": 24})
    assert resp.status_code == 200
    assert resp.json() == []


def test_chart_missing_blockchain_param_is_422(client, seed_charts):
    assert client.get("/charts/hour").status_code == 422
