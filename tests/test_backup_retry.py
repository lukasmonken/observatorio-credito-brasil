import subprocess
from unittest.mock import Mock

import pytest

from scripts import retry_backup


@pytest.fixture
def execution(monkeypatch):
    monkeypatch.setattr(retry_backup.shutil, "which", lambda _: "/usr/bin/rclone")
    run = Mock()
    sleep = Mock()
    monkeypatch.setattr(retry_backup.subprocess, "run", run)
    monkeypatch.setattr(retry_backup.time, "sleep", sleep)
    monkeypatch.setattr(retry_backup.random, "uniform", lambda *_: 4)
    return run, sleep


def result(code=0, message=""):
    return subprocess.CompletedProcess([], code, stdout="", stderr=message)


@pytest.mark.parametrize("message", [
    "Failed to create file system: googleapi: Error 403: User rate limit exceeded, userRateLimitExceeded",
    "googleapi: Error 403: Quota exceeded for quota metric 'Queries' and limit 'Queries per minute'",
    "Error 429: Too Many Requests", "googleapi: Error 503: backendError",
    "connection reset by peer", "i/o timeout",
])
def test_transient_initialization_failure_recovers(execution, message, caplog):
    run, sleep = execution
    run.side_effect = [result(1, message + ' token=PRIVATE'), result()]
    retry_backup.run_rclone(["copy", "local", "backup:dest", "--immutable"])
    assert run.call_count == 2
    assert run.call_args_list[0] == run.call_args_list[1]
    assert "--immutable" in run.call_args.args[0]
    assert run.call_args.kwargs["timeout"] == 120
    sleep.assert_called_once_with(34)
    assert "PRIVATE" not in caplog.text


def test_exhausted_retries_fail_with_backoff(execution):
    run, sleep = execution
    run.return_value = result(1, "Error 503: unavailable")
    with pytest.raises(RuntimeError, match=r"após 3 tentativa"):
        retry_backup.run_rclone(["check", "local", "backup:dest", "--download"])
    assert run.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [34, 64]


def test_process_timeout_retries(execution):
    run, sleep = execution
    run.side_effect = [subprocess.TimeoutExpired("rclone", 120), result()]
    retry_backup.run_rclone(["copy", "backup:dest", "local"])
    assert run.call_count == 2
    sleep.assert_called_once()


@pytest.mark.parametrize("message", [
    "invalid_grant: Token has been expired or revoked",
    "Error 403: insufficientPermissions", "Error 403: Forbidden",
    "storageQuotaExceeded", "dailyLimitExceeded", "unknown flag: flag",
    "corrupted on transfer; Error 503: backendError",
    "Source and destination hashes differ", "files differ",
    "Source and destination exist but do not match: immutable file modified",
    "unexpected unrecognized failure",
])
def test_permanent_or_unknown_failure_is_not_repeated(execution, message):
    run, sleep = execution
    run.return_value = result(1, message)
    with pytest.raises(RuntimeError, match=r"após 1 tentativa"):
        retry_backup.run_rclone(["check", "local", "backup:dest"])
    run.assert_called_once()
    sleep.assert_not_called()


def test_success_does_not_wait(execution):
    run, sleep = execution
    run.return_value = result()
    retry_backup.run_rclone(["copy", "local", "backup:dest"])
    run.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize("command", ["deletefile", "purge", "rmdir", "sync"])
def test_destructive_operations_are_rejected(execution, command):
    run, sleep = execution
    with pytest.raises(ValueError, match="Somente copy e check"):
        retry_backup.run_rclone([command, "backup:dest"])
    run.assert_not_called()
    sleep.assert_not_called()
