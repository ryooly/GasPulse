from __future__ import annotations

"""Unit tests for the APScheduler automation engine (app/modules/automation/automation_engine).

These tests are fully mocked: no blockchain scanner API is ever called and no
real database session is opened, so they run anywhere without Docker or network.
The engine under test only wires *when* and *how* each scanner's
``capture_and_insert`` runs, so that is what we assert.

Run:
    python -m pytest test/test_automation_engine.py -v
Run a single case:
    python -m pytest test/test_automation_engine.py -v -k test_success
"""

from unittest.mock import MagicMock, patch

import pytest
from apscheduler.triggers.interval import IntervalTrigger

from app.models.time_unit_models import TimeUnitName
from app.modules.automation.automation_engine import (
    TIMEFRAME_ENGINES,
    core,
    day_engine,
    hour_engine,
    shutdown_all,
    start_all,
    week_engine,
)
from app.modules.automation.automation_engine.core import TimeframeEngine, capture_scanner

EXPECTED_SCANNERS = ("etherscan", "polygonscan", "bscscan", "arbiscan", "snowtrace")


def _make_engine(timeframe=TimeUnitName.HOUR, name="test-engine", **kwargs):
    """Build an isolated engine so tests never touch the shared module singletons."""
    return TimeframeEngine(timeframe, name=name, **kwargs)


def _stub_scheduler(engine):
    """Replace add_job/start on an engine's scheduler and record what was scheduled.

    Returns the engine and the list of (id, trigger_type) it scheduled, without
    spawning a real scheduler thread or firing any capture.
    """
    added = []

    def fake_add_job(func=None, trigger=None, id=None, name=None, **_kw):
        added.append((id, type(trigger).__name__))

    engine._scheduler.add_job = fake_add_job
    engine._scheduler.start = lambda *a, **k: None
    return added


# ─── Configuration ──────────────────────────────────────────────────────────

def test_scanner_classes_cover_all_scanners():
    assert tuple(scanner_id for scanner_id, _ in core.SCANNER_CLASSES) == EXPECTED_SCANNERS


def test_timeframe_intervals_match_expected_periods():
    assert core.TIMEFRAME_INTERVAL_SECONDS[TimeUnitName.HOUR] == 3600
    assert core.TIMEFRAME_INTERVAL_SECONDS[TimeUnitName.DAY] == 86400
    assert core.TIMEFRAME_INTERVAL_SECONDS[TimeUnitName.WEEK] == 604800


@pytest.mark.parametrize(
    "engine, timeframe, expected_interval",
    [
        (hour_engine, TimeUnitName.HOUR, 3600),
        (day_engine, TimeUnitName.DAY, 86400),
        (week_engine, TimeUnitName.WEEK, 604800),
    ],
)
def test_each_timeframe_engine_defaults_to_its_interval_and_all_scanners(engine, timeframe, expected_interval):
    # interval is derived from the timeframe via TIMEFRAME_INTERVAL_SECONDS
    assert engine.timeframe is timeframe
    assert engine.interval_seconds == expected_interval
    assert engine.scanner_ids == EXPECTED_SCANNERS


def test_module_not_running_until_started():
    # importing the package must not spin up any scheduler
    assert not hour_engine.running
    assert not day_engine.running
    assert not week_engine.running


def test_timeframe_engines_registry_order():
    assert TIMEFRAME_ENGINES == (hour_engine, day_engine, week_engine)


# ─── capture_scanner (core unit) ────────────────────────────────────────────

def _fake_db():
    """Patch core.SessionLocal so capture_scanner uses an in-memory mock session."""
    return patch.object(core, "SessionLocal")


def test_capture_scanner_success_calls_capture_and_insert_and_closes():
    db = MagicMock()
    catcher = MagicMock()
    snapshot = MagicMock()
    snapshot.raw_fee_value, snapshot.status.value, snapshot.block_number = 12, "stable", 100
    catcher.capture_and_insert.return_value = snapshot
    factory = MagicMock(return_value=catcher)

    with _fake_db() as session_local:
        session_local.return_value = db
        capture_scanner(factory, "etherscan", TimeUnitName.HOUR, sample_size=7)

    factory.assert_called_once()
    catcher.capture_and_insert.assert_called_once_with(db, TimeUnitName.HOUR, sample_size=7)
    db.commit.assert_not_called()  # catcher/repository owns the commit
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_capture_scanner_failure_rolls_back_closes_and_does_not_raise():
    db = MagicMock()
    catcher = MagicMock()
    catcher.capture_and_insert.side_effect = RuntimeError("boom")
    factory = MagicMock(return_value=catcher)

    with _fake_db() as session_local:
        session_local.return_value = db
        # must swallow the exception (logged) so the scheduler stays alive
        capture_scanner(factory, "bscscan", TimeUnitName.DAY, sample_size=5)

    db.rollback.assert_called_once()
    db.close.assert_called_once()


# ─── Job scheduling (start) ─────────────────────────────────────────────────

def test_start_schedules_one_interval_job_per_scanner():
    engine = _make_engine(TimeUnitName.DAY)
    added = _stub_scheduler(engine)

    engine.start()  # run_now defaults to False

    expected_ids = {f"day:{scanner}" for scanner in EXPECTED_SCANNERS}
    assert {job_id for job_id, _ in added} == expected_ids
    assert all(trigger == "IntervalTrigger" for _, trigger in added)
    assert len(added) == len(EXPECTED_SCANNERS)


def test_start_run_now_adds_immediate_and_interval_jobs():
    engine = _make_engine(TimeUnitName.HOUR)
    added = _stub_scheduler(engine)

    engine.start(run_now=True)

    triggers = {trigger for _, trigger in added}
    assert triggers == {"DateTrigger", "IntervalTrigger"}
    assert len(added) == 2 * len(EXPECTED_SCANNERS)
    immediate = [job_id for job_id, trigger in added if trigger == "DateTrigger"]
    assert all(job_id.endswith(":immediate") for job_id in immediate)


def test_start_is_ignored_when_already_running():
    engine = _make_engine(TimeUnitName.HOUR)
    with patch.object(core, "capture_scanner"):
        engine.start()  # really start -> scheduler.running becomes True
    try:
        added = _stub_scheduler(engine)  # stub add_job to detect any re-scheduling
        engine.start()  # already running -> returns early, adds nothing
        assert added == []
    finally:
        engine.shutdown()


def test_shutdown_is_noop_when_not_running():
    engine = _make_engine(TimeUnitName.HOUR)  # never started -> running is False
    called = MagicMock()
    engine._scheduler.shutdown = called

    engine.shutdown()

    called.assert_not_called()


def test_real_scheduler_lifecycle_and_resilience_defaults():
    # Uses a real (background) scheduler but run_now=False, so nothing fires:
    # the first interval run is 3600s away. Guards scheduler wiring + job_defaults.
    engine = _make_engine(TimeUnitName.HOUR)
    with patch.object(core, "capture_scanner"):
        engine.start()
        try:
            assert engine.running
            jobs = engine._scheduler.get_jobs()
            assert sorted(j.id for j in jobs) == sorted(f"hour:{s}" for s in EXPECTED_SCANNERS)
            for job in jobs:
                # the resilience settings declared on BackgroundScheduler apply
                assert job.coalesce is True
                assert job.max_instances == 1
                assert isinstance(job.trigger, IntervalTrigger)
        finally:
            engine.shutdown()
    assert not engine.running


# ─── Task closures & capture_now ────────────────────────────────────────────

def test_build_task_invokes_capture_scanner_for_its_scanner():
    engine = _make_engine(TimeUnitName.WEEK, sample_size=9)
    factory = MagicMock()

    with patch.object(core, "capture_scanner") as captured:
        engine._build_task("arbiscan", factory)()

    captured.assert_called_once_with(factory, "arbiscan", TimeUnitName.WEEK, 9)


def test_capture_now_all_runs_every_scanner_for_the_timeframe():
    engine = _make_engine(TimeUnitName.DAY)

    with patch.object(core, "capture_scanner") as captured:
        engine.capture_now()

    called_scanners = sorted(call.args[1] for call in captured.call_args_list)
    assert called_scanners == sorted(EXPECTED_SCANNERS)
    assert all(call.args[2] == TimeUnitName.DAY for call in captured.call_args_list)


def test_capture_now_single_scanner():
    engine = _make_engine(TimeUnitName.HOUR)

    with patch.object(core, "capture_scanner") as captured:
        engine.capture_now("etherscan")

    captured.assert_called_once()
    assert captured.call_args.args[1] == "etherscan"


def test_capture_now_unknown_scanner_raises():
    engine = _make_engine(TimeUnitName.HOUR)
    with pytest.raises(ValueError, match="No scanner API"):
        engine.capture_now("not-a-scanner")


# ─── start_all / shutdown_all (package facade) ──────────────────────────────

def test_start_all_and_shutdown_all_touch_every_engine():
    with (
        patch.object(TimeframeEngine, "start") as start,
        patch.object(TimeframeEngine, "shutdown") as stop,
    ):
        start_all(run_now=True)
        assert start.call_count == len(TIMEFRAME_ENGINES)
        assert all(call.kwargs == {"run_now": True} for call in start.call_args_list)

        shutdown_all()
        assert stop.call_count == len(TIMEFRAME_ENGINES)
