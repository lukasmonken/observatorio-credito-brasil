"""Revisões persistentes, classificação dos eventos e publicação atômica."""

import hashlib
import json
import shutil
from decimal import Decimal

import pandas as pd
import pytest

from observatorio.config import ROOT
from observatorio.revisions import (
    HISTORY_FILES,
    attach_history,
    compare_snapshots,
    read_history,
)
from scripts.update_data import publish_snapshot
from observatorio.snapshot import load_snapshot

SPECS = [
    {"code": 1, "name": "Taxa", "unit": "%", "measure_type": "rate", "frequency": "M"}
]
DETECTED = "2026-10-28T16:00:00+00:00"


def frame(dates, values, code=1):
    return pd.DataFrame(
        {"code": [code] * len(dates), "date": dates, "original": values}
    )


def compare(old, new):
    return compare_snapshots(old, new, SPECS, "a", "b", DETECTED)


def test_original_values_only_and_equivalent_decimals():
    old = frame(["2026-01-01", "2026-02-01"], ["1.00", ""])
    new = frame(["2026-02-01", "2026-01-01"], ["", "1.0"])
    old["real"] = [20, 30]
    new["real"] = [10, 40]
    assert compare(old, new) == []


def test_revision_zero_negative_and_small_changes_are_exact():
    old = frame(["2026-01-01", "2026-02-01", "2026-03-01"], ["0", "-1.5", "100000000"])
    new = frame(old.date, ["0.01", "-1.75", "100000000.01"])
    events = compare(old, new)
    assert [e["difference"] for e in events] == ["0.01", "-0.25", "0.01"]
    assert all(
        e["event_type"] == "revision" and e["difference_unit"] == "p.p." for e in events
    )
    assert events == compare(old, new)


def test_new_month_and_historical_fill_are_not_revisions():
    old = frame(["2025-11-01", "2025-12-01"], ["", "2"])
    new = frame(
        ["2025-10-01", "2025-11-01", "2025-12-01", "2026-01-01"], ["1", "1.5", "2", "3"]
    )
    events = compare(old, new)
    assert [e["event_type"] for e in events] == [
        "historical_fill",
        "historical_fill",
        "new_observation",
    ]
    assert all(e["old_value"] == e["difference"] == "" for e in events)


def test_new_series_is_distinguished():
    events = compare(frame([], []), frame(["2026-01-01"], ["2"]))
    assert events[0]["event_type"] == "new_series"


@pytest.mark.parametrize("value", ["", None])
def test_value_removal_blocks_history(value):
    with pytest.raises(ValueError, match="Perda"):
        compare(frame(["2026-01-01"], ["1"]), frame(["2026-01-01"], [value]))


def test_deleted_observation_blocks_history():
    with pytest.raises(ValueError, match="Perda"):
        compare(frame(["2026-01-01"], ["1"]), frame([], []))


@pytest.mark.parametrize("value", ["inf", "NaN", "invalid"])
def test_invalid_numbers_rejected(value):
    with pytest.raises(ValueError):
        compare(frame(["2026-01-01"], ["1"]), frame(["2026-01-01"], [value]))


def test_duplicate_key_and_same_snapshot_rejected():
    old = frame(["2026-01-01"], ["1"])
    with pytest.raises(ValueError, match="duplicada"):
        compare(old, pd.concat([old, old]))
    with pytest.raises(ValueError, match="distintos"):
        compare_snapshots(old, old, SPECS, "a", "a", DETECTED)


def bundle(root, run_id, values):
    folder = root / run_id
    folder.mkdir()
    data = frame(["2026-01-01", "2026-02-01"], values)
    data.to_csv(folder / "analytics.csv", index=False)
    (folder / "catalog.json").write_text(json.dumps(SPECS))
    manifest = {"snapshot_id": run_id, "created_at": DETECTED, "files": {}}
    return folder, manifest


def test_history_accumulates_and_records_unchanged_comparison(tmp_path):
    a, ma = bundle(tmp_path, "a", ["1", "2"])
    b, mb = bundle(tmp_path, "b", ["1.5", "2"])
    attach_history(b, a, ma, mb)
    events, meta = read_history(b, mb)
    assert len(events) == 1 and meta["baseline_snapshot_id"] == "a"
    c, mc = bundle(tmp_path, "c", ["1.50", "2.0"])
    attach_history(c, b, mb, mc)
    events_c, meta_c = read_history(c, mc)
    assert events_c.to_dict("records") == events.to_dict("records")
    assert len(meta_c["comparisons"]) == 2
    assert sum(meta_c["comparisons"][-1]["counts"].values()) == 0
    assert read_history(b, mb)[1]["snapshot_id"] == "b"


def test_missing_history_or_corruption_never_silently_resets_it(tmp_path):
    a, ma = bundle(tmp_path, "a", ["1", "2"])
    b, mb = bundle(tmp_path, "b", ["2", "2"])
    attach_history(b, a, ma, mb)
    (b / "revision_history.csv").write_text("broken")
    c, mc = bundle(tmp_path, "c", ["3", "2"])
    with pytest.raises(ValueError, match="Checksum"):
        attach_history(c, b, mb, mc)
    mb["files"].pop("revision_history.csv")
    with pytest.raises(ValueError, match="incompleto"):
        read_history(b, mb)


def test_history_semantics_checked_even_if_checksum_is_updated(tmp_path):
    a, ma = bundle(tmp_path, "a", ["1", "2"])
    b, mb = bundle(tmp_path, "b", ["2", "2"])
    attach_history(b, a, ma, mb)
    events = pd.read_csv(b / "revision_history.csv", dtype=str)
    events.loc[0, "difference"] = "99"
    events.to_csv(b / "revision_history.csv", index=False)
    mb["files"]["revision_history.csv"] = hashlib.sha256(
        (b / "revision_history.csv").read_bytes()
    ).hexdigest()
    with pytest.raises(ValueError, match="Diferença"):
        read_history(b, mb)


def test_metadata_unit_change_blocks_comparison(tmp_path):
    a, ma = bundle(tmp_path, "a", ["1", "2"])
    b, mb = bundle(tmp_path, "b", ["2", "2"])
    (b / "catalog.json").write_text(json.dumps([{**SPECS[0], "unit": "R$"}]))
    with pytest.raises(ValueError, match="migração"):
        attach_history(b, a, ma, mb)


@pytest.fixture
def publication(tmp_path):
    pointer = json.loads((ROOT / "data/processed/latest.json").read_text())
    old = tmp_path / pointer["path"]
    shutil.copytree(ROOT / pointer["path"], old)
    (tmp_path / "data/processed/latest.json").write_text(json.dumps(pointer))
    baseline_manifest = json.loads((old / "manifest.json").read_text())
    baseline_manifest.pop("revision_history_version", None)
    for name in HISTORY_FILES:
        baseline_manifest["files"].pop(name, None)
        (old / name).unlink(missing_ok=True)
    (old / "manifest.json").write_text(json.dumps(baseline_manifest))
    candidate = tmp_path / "candidate"
    shutil.copytree(old, candidate)
    manifest = json.loads((candidate / "manifest.json").read_text())
    manifest["snapshot_id"] = "revision-test"
    manifest.pop("revision_history_version", None)
    for name in HISTORY_FILES:
        manifest["files"].pop(name, None)
        (candidate / name).unlink(missing_ok=True)
    data = pd.read_csv(candidate / "analytics.csv", dtype=str, keep_default_na=False)
    row = data.index[data.original != ""][0]
    data.loc[row, "original"] = str(
        Decimal(data.loc[row, "original"]) + Decimal("0.01")
    )
    data["snapshot_id"] = "revision-test"
    data.to_csv(candidate / "analytics.csv", index=False)
    manifest["files"]["analytics.csv"] = hashlib.sha256(
        (candidate / "analytics.csv").read_bytes()
    ).hexdigest()
    (candidate / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path, candidate


def test_publication_binds_history_and_snapshot_atomically(publication):
    root, candidate = publication
    publish_snapshot(candidate, root, "revision-test")
    manifest = load_snapshot(root)[3]
    events, meta = read_history(root / "data/processed/revision-test", manifest)
    assert meta["comparisons"][-1]["counts"]["revision"] == 1
    assert events.iloc[-1].difference == "0.01"
    with pytest.raises(FileExistsError):
        publish_snapshot(candidate, root, "revision-test")
    assert read_history(root / "data/processed/revision-test", manifest)[
        0
    ].event_id.is_unique


def test_history_failure_preserves_previous_pointer(publication, monkeypatch):
    import scripts.update_data as daily

    root, candidate = publication
    previous = (root / "data/processed/latest.json").read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(daily, "attach_history", fail)
    with pytest.raises(OSError):
        daily.publish_snapshot(candidate, root, "revision-test")
    assert (root / "data/processed/latest.json").read_bytes() == previous
    load_snapshot(root)


def test_history_page_filters_and_exports(publication, monkeypatch):
    import observatorio.config
    from streamlit.testing.v1 import AppTest

    root, candidate = publication
    publish_snapshot(candidate, root, "revision-test")
    monkeypatch.setattr(observatorio.config, "ROOT", root)
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Histórico de revisões").run()
    assert not app.exception
    assert app.metric[0].value == "1"
    assert app.get("download_button")
    app.multiselect[1].set_value(["new_observation"]).run()
    assert not app.exception
    assert any("Nenhum evento corresponde" in info.value for info in app.info)
