from datetime import datetime, timezone

import pytest

from scripts.retain_backups import plan_retention

NOW = datetime(2026, 10, 29, 22, tzinfo=timezone.utc)


def backup(folder, date):
    return [{"Path": f"{folder}/{name}", "IsDir": False, "ModTime": date, "Size": 100}
            for name in [f"credito-{folder}.zip", "SHA256SUMS", "source-commit.txt"]]


def test_retains_recent_and_last_per_month_with_year_boundary():
    entries = (backup("1-1", "2026-10-29T21:00:00Z")
               + backup("2-1", "2026-10-01T12:00:00Z")
               + backup("3-1", "2026-09-10T12:00:00Z")
               + backup("4-1", "2026-09-20T12:00:00Z")
               + backup("5-1", "2025-11-01T12:00:00Z")
               + backup("6-1", "2025-10-31T12:00:00Z"))
    result = plan_retention(entries, NOW, "1-1")
    assert result["keep"] == ["1-1", "2-1", "4-1", "5-1"]
    assert result["delete"] == ["3-1", "6-1"]
    assert result == plan_retention(list(reversed(entries)), NOW, "1-1")


def test_missing_current_blocks_cleanup():
    with pytest.raises(ValueError, match="limpeza bloqueada"):
        plan_retention([], NOW, "1-1")


@pytest.mark.parametrize("bad", [
    backup("other", "2024-01-01T12:00:00Z"),
    backup("2-1", "2024-01-01T12:00:00Z")[:2],
    backup("2-1", "2027-01-01T12:00:00Z"),
    backup("2-1", "invalid"),
    backup("2-1", "2024-01-01T12:00:00Z") * 2,
    backup("2-1", "2024-01-01T12:00:00Z") + [{"Path": "2-1/personal.txt", "IsDir": False}],
])
def test_never_deletes_unknown_incomplete_future_or_duplicate_files(bad):
    result = plan_retention(backup("1-1", "2026-10-29T21:00:00Z") + bad, NOW, "1-1")
    assert not result["delete"]
    assert result["ignored"]


def test_keeps_latest_even_if_all_backups_are_old():
    result = plan_retention(backup("1-1", "2020-01-01T12:00:00Z"), NOW, "1-1")
    assert result["keep"] == ["1-1"]
    assert not result["delete"]


@pytest.mark.parametrize("apply", [False, True])
def test_command_simulates_by_default_and_only_removes_expired_known_files(tmp_path, monkeypatch, apply):
    import json
    import sys
    from types import SimpleNamespace
    from scripts import retain_backups

    current = "1-1"
    timestamp = datetime.now(timezone.utc).isoformat()
    entries = backup(current, timestamp) + backup("2-1", "2020-01-01T12:00:00Z")
    local = tmp_path / "backup"
    local.mkdir()
    for name in ["credito-1-1.zip", "SHA256SUMS", "source-commit.txt"]:
        (local / name).write_text("test")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1] == "lsjson":
            if command[2].endswith("/2-1"):
                items = [dict(e, Path=e["Path"].split("/", 1)[1]) for e in entries if e["Path"].startswith("2-1/")]
            else:
                items = entries
            return SimpleNamespace(stdout=json.dumps(items))
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(retain_backups.shutil, "which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr(retain_backups.subprocess, "run", run)
    report = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["retain_backups.py", "--config", "private.conf", "--current", current,
                                    "--verified-local", str(local), "--report", str(report)] + (["--apply"] if apply else []))
    retain_backups.main()
    deletes = [c for c in calls if c[1] == "deletefile"]
    assert len(deletes) == (3 if apply else 0)
    assert all(c[2].startswith(retain_backups.REMOTE + "/2-1/") and "--drive-use-trash=true" in c for c in deletes)
    assert calls[0][1] == "check"
    assert json.loads(report.read_text())["keep"] == [current]
