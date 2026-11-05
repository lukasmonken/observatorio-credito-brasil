from datetime import datetime, timedelta, timezone
import io
import json
from urllib.error import URLError

import pytest

from scripts import monitor_backup as monitor

NOW = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)


def record(hours=1, status="completed", conclusion="success", verified=True, run_id=1):
    start = NOW - timedelta(hours=hours)
    end = start + timedelta(minutes=5) if status == "completed" else None
    return dict(run_id=run_id, run_attempt=1, started_at=start.isoformat(),
                ended_at=end.isoformat() if end else None, duration_seconds=300 if end else None,
                status=status, conclusion=conclusion, verified=verified,
                skipped=conclusion == "skipped")


def test_recent_success_is_healthy():
    report = monitor.evaluate([record()], NOW)
    assert report["status"] == "ok"
    assert report["last_success"]["run_id"] == 1


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out"])
def test_failure_is_not_hidden_by_recent_success(conclusion):
    report = monitor.evaluate([record(2), record(1, conclusion=conclusion, verified=False, run_id=2)], NOW)
    assert report["status"] == "alert"
    assert report["last_attempt"]["run_id"] == 2
    assert report["last_success"]["run_id"] == 1


def test_skipped_does_not_become_attempt_or_success():
    report = monitor.evaluate([record(1, conclusion="skipped", verified=False, run_id=2), record(2)], NOW)
    assert report["latest_execution_skipped"]
    assert report["last_attempt"]["run_id"] == 1
    assert report["last_success"]["run_id"] == 1
    assert report["status"] == "alert"


def test_missing_runs_and_old_success_alert_separately():
    report = monitor.evaluate([record(32)], NOW)
    assert any("sem tentativa" in error for error in report["errors"])
    assert any("Sem backup validado" in error for error in report["errors"])


@pytest.mark.parametrize("hours,expected", [(0.5, "running"), (1, "running"), (1.1, "alert")])
def test_running_or_stuck(hours, expected):
    report = monitor.evaluate([record(hours, status="queued", conclusion=None, verified=False, run_id=2), record(2)], NOW)
    assert report["status"] == expected


def test_running_does_not_hide_old_success():
    report = monitor.evaluate([record(0.5, status="in_progress", conclusion=None, verified=False), record(32)], NOW)
    assert report["status"] == "alert"


def test_future_dates_are_not_healthy():
    assert monitor.evaluate([record(-1)], NOW)["status"] == "alert"


def test_no_runs_is_not_healthy():
    report = monitor.evaluate([], NOW)
    assert report["status"] == "alert"
    assert report["last_success"] is None


def run_and_job(conclusion="success", steps=None):
    run = {"id": 42, "run_attempt": 2, "run_started_at": (NOW - timedelta(minutes=10)).isoformat(), "status": "completed"}
    job = {"started_at": run["run_started_at"], "completed_at": NOW.isoformat(), "status": "completed",
           "conclusion": conclusion, "steps": steps if steps is not None else [{"name": monitor.VERIFICATION_STEP, "conclusion": "success"}]}
    return run, job


def test_requires_real_verification_step_not_only_workflow_success():
    run, job = run_and_job(steps=[])
    result = monitor.summarize_run(run, [job])
    assert not result["verified"]
    assert monitor.evaluate([result], NOW)["status"] == "alert"


def test_complete_success_has_attempt_and_duration():
    run, job = run_and_job()
    result = monitor.summarize_run(run, [job])
    assert result["verified"]
    assert result["duration_seconds"] == 600
    assert result["run_attempt"] == 2


def test_retry_uses_attempt_time_not_original_creation():
    run, job = run_and_job()
    run["created_at"] = (NOW - timedelta(days=10)).isoformat()
    result = monitor.summarize_run(run, [job])
    assert monitor.evaluate([result], NOW)["status"] == "ok"


def test_api_uses_specific_attempt_and_read_timeout(monkeypatch):
    run, job = run_and_job()
    calls = []
    def response(request, timeout):
        calls.append(request.full_url)
        assert timeout == 10
        payload = {"workflow_runs": [run]} if "workflows/" in request.full_url else {"jobs": [job]}
        return io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(monitor, "urlopen", response)
    report = monitor.check("owner/repo", "private-token", NOW)
    assert report["status"] == "ok"
    assert calls[-1].endswith("actions/runs/42/attempts/2/jobs?per_page=100")
    assert "private-token" not in json.dumps(report)


@pytest.mark.parametrize("payload", [{}, {"workflow_runs": None}, {"workflow_runs": [{"id": "invalid"}]}])
def test_bad_schema_fails(monkeypatch, payload):
    monkeypatch.setattr(monitor, "api_get", lambda *_: payload)
    with pytest.raises((ValueError, KeyError, TypeError)):
        monitor.check("owner/repo", "token", NOW)


def test_queued_without_job_is_pending(monkeypatch):
    run, _ = run_and_job()
    run["status"] = "queued"
    monkeypatch.setattr(monitor, "api_get", lambda *args: {"workflow_runs": [run]} if "workflows/" in args[-1] else {"jobs": []})
    report = monitor.check("owner/repo", "token", NOW)
    assert report["last_attempt"]["status"] == "queued"
    assert report["last_success"] is None


@pytest.mark.parametrize("error", [URLError("private-token"), TimeoutError("private-token"), ValueError("private-token")])
def test_query_failure_produces_unknown_report_and_failed_exit(monkeypatch, tmp_path, capsys, error):
    target = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", ["monitor_backup.py", "--report", str(target)])
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "private-token")
    def fail(*_):
        raise error
    monkeypatch.setattr(monitor, "check", fail)
    with pytest.raises(SystemExit) as exit_info:
        monitor.main()
    assert exit_info.value.code == 1
    assert json.loads(target.read_text())["status"] == "unknown"
    assert "private-token" not in target.read_text() + capsys.readouterr().out


def test_invalid_repo_never_makes_request(monkeypatch):
    def unexpected(*_):
        pytest.fail("Não deve acessar a rede")
    monkeypatch.setattr(monitor, "urlopen", unexpected)
    with pytest.raises(ValueError):
        monitor.api_get("owner/repo/../../other", "token", "actions/runs")


def test_skipped_inverted_timestamps_do_not_hide_newer_verified_backup(monkeypatch):
    skipped_run, skipped_job = run_and_job("skipped", steps=[])
    skipped_run.update(id=41, run_started_at="2026-11-05T12:03:59Z")
    skipped_job.update(started_at="2026-11-05T12:04:09Z",
                       completed_at="2026-11-05T12:03:59Z")
    good_run, good_job = run_and_job()
    good_run.update(run_started_at="2026-11-05T12:06:00Z")
    good_job.update(started_at="2026-11-05T12:06:03Z",
                    completed_at="2026-11-05T12:07:54Z")
    def response(repo, token, path):
        if "workflows/" in path:
            return {"workflow_runs": [good_run, skipped_run]}
        return {"jobs": [skipped_job if "/41/" in path else good_job]}
    monkeypatch.setattr(monitor, "api_get", response)
    report = monitor.check("owner/repo", "token",
                           datetime(2026, 11, 5, 12, 8, 5, tzinfo=timezone.utc))
    assert report["status"] == "ok"
    assert report["last_success"]["run_id"] == 42
    assert report["runs_checked"] == 2


def test_latest_skipped_with_inverted_times_still_alerts():
    run, job = run_and_job("skipped", steps=[])
    job["completed_at"] = (NOW - timedelta(minutes=11)).isoformat()
    result = monitor.summarize_run(run, [job])
    assert result["duration_seconds"] is None
    assert result["ended_at"] is None
    assert not result["verified"]
    report = monitor.evaluate([result, record(2)], NOW)
    assert report["status"] == "alert"
    assert report["latest_execution_skipped"]
    assert report["last_success"]["run_id"] == 1


@pytest.mark.parametrize("conclusion", ["success", "failure", "cancelled"])
def test_executed_jobs_with_negative_duration_remain_invalid(conclusion):
    run, job = run_and_job(conclusion)
    job["completed_at"] = (NOW - timedelta(minutes=11)).isoformat()
    with pytest.raises(ValueError, match="Duração negativa"):
        monitor.summarize_run(run, [job])
