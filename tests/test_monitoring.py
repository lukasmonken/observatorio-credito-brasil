"""Falhas, ausência de execução e defasagem da fonte são estados distintos."""

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from observatorio.monitoring import (
    collection_health,
    read_status,
    source_freshness,
    write_status,
)

spec = importlib.util.spec_from_file_location(
    "monitor_update", Path(__file__).parents[1] / "scripts/monitor_update.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)


def snapshot(root):
    folder = root / "data/processed/snapshot"
    folder.mkdir(parents=True)
    manifest = {
        "created_at": (NOW - timedelta(days=1)).isoformat(),
        "snapshot_id": "snapshot",
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    (folder.parent / "latest.json").write_text(
        json.dumps({"path": "data/processed/snapshot"})
    )
    return manifest


@pytest.mark.parametrize(
    "hours,expected", [(29.9, "ok"), (30, "ok"), (30.1, "stale"), (-2, "unknown")]
)
def test_collection_age_limits(hours, expected):
    state = {
        "status": "success",
        "last_success_at": (NOW - timedelta(hours=hours)).isoformat(),
    }
    assert collection_health(state, {}, NOW)[0] == expected


def test_failure_is_not_hidden_by_recent_snapshot():
    state = {
        "status": "failed",
        "last_success_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    assert collection_health(state, {}, NOW)[0] == "failed"


def test_no_metadata_uses_snapshot_but_does_not_invent_attempt():
    assert collection_health(None, {"created_at": NOW.isoformat()}, NOW)[0] == "unknown"
    assert (
        collection_health(
            None, {"created_at": (NOW - timedelta(hours=31)).isoformat()}, NOW
        )[0]
        == "stale"
    )


def test_failed_attempt_preserves_success_and_redacts_exception(tmp_path):
    manifest = snapshot(tmp_path)
    module.start(tmp_path, NOW)
    folder = tmp_path / "work/collection-a/data/processed"
    folder.mkdir(parents=True)
    (folder / "last_attempt.json").write_text(
        json.dumps(
            {"results": [{"code": 432, "status": "failed", "error": "SECRET-PATH"}]}
        )
    )
    state = module.finish(
        tmp_path, NOW + timedelta(seconds=45), "failed", "coleta_e_validacao"
    )
    assert state["last_success_at"] == manifest["created_at"]
    assert state["duration_seconds"] == 45
    assert state["failed_series"] == [432]
    assert "SECRET-PATH" not in json.dumps(state)
    assert (
        json.loads((tmp_path / "data/processed/latest.json").read_text())["path"]
        == "data/processed/snapshot"
    )


def test_recovery_clears_failure(tmp_path):
    snapshot(tmp_path)
    module.start(tmp_path, NOW)
    module.finish(tmp_path, NOW, "failed", "testes")
    module.start(tmp_path, NOW + timedelta(days=1))
    state = module.finish(
        tmp_path, NOW + timedelta(days=1, seconds=5), "success", "snapshot_validado"
    )
    assert state["failed_series"] == []
    assert state["snapshot_id"] == "snapshot"
    assert state["last_success_at"] == (NOW + timedelta(days=1, seconds=5)).isoformat()


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        "{broken",
        '{"status":"inventado"}',
        '{"status":"success","started_at":"2026-10-27"}',
    ],
)
def test_bad_operational_metadata(tmp_path, content):
    folder = tmp_path / "data/processed"
    folder.mkdir(parents=True)
    (folder / "monitoring.json").write_text(content)
    with pytest.raises(ValueError):
        read_status(tmp_path)


def test_source_delay_is_separate_from_collection_failure():
    df = pd.DataFrame(
        {
            "code": [1, 2],
            "date": pd.to_datetime(["2026-07-01", "2026-09-01"]),
            "original": [1.0, 2.0],
        }
    )
    specs = [
        {"code": code, "name": str(code), "max_lag_days": 90} for code in (1, 2, 3)
    ]
    rows = source_freshness(df, specs, NOW.date())
    assert [r["Situação"] for r in rows] == [
        "Acima do limite",
        "Dentro do limite",
        "Sem dados",
    ]
    assert (
        collection_health(
            {"status": "success", "last_success_at": NOW.isoformat()}, {}, NOW
        )[0]
        == "ok"
    )


@pytest.mark.parametrize(
    "status,conclusion,hours,fail",
    [
        ("completed", "success", 2, False),
        ("completed", "failure", 2, True),
        ("completed", "cancelled", 2, True),
        ("completed", "success", 31, True),
        ("queued", None, 2, True),
        ("in_progress", None, 0.25, False),
    ],
)
def test_watchdog_detects_missing_failed_or_stuck_run(status, conclusion, hours, fail):
    run = {
        "status": status,
        "conclusion": conclusion,
        "created_at": (NOW - timedelta(hours=hours)).isoformat(),
    }
    assert bool(module.check_runs([run], NOW)) == fail


def test_watchdog_no_runs():
    assert module.check_runs([], NOW)


def test_watchdog_checks_remote_publication_failure(tmp_path, monkeypatch):
    snapshot(tmp_path)
    write_status(tmp_path, {"status": "success", "last_success_at": NOW.isoformat()})
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    import io

    def response(request, timeout):
        assert timeout == 20
        return io.BytesIO(
            json.dumps(
                {
                    "workflow_runs": [
                        {
                            "status": "completed",
                            "conclusion": "failure",
                            "created_at": NOW.isoformat(),
                        }
                    ]
                }
            ).encode()
        )

    monkeypatch.setattr(module, "urlopen", response)
    assert module.check(tmp_path, NOW) == ["Último job terminou com estado: failure."]
