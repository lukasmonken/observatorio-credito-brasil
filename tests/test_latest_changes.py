import pandas as pd
from streamlit.testing.v1 import AppTest

from observatorio.config import ROOT
from observatorio.revisions import COLUMNS, EVENT_LABELS, latest_changes, read_history
from observatorio.snapshot import load_snapshot


def history(events):
    return pd.DataFrame(events, columns=COLUMNS)


def metadata():
    return {"comparisons": [
        {"snapshot_id": "old", "previous_snapshot_id": "baseline", "detected_at": "2026-11-01T12:00:00+00:00"},
        {"snapshot_id": "current", "previous_snapshot_id": "old", "detected_at": "2026-11-02T12:00:00+00:00"},
    ]}


def event(kind, code="1", snapshot="current"):
    return {"snapshot_id": snapshot, "code": code, "name": f"Indicador {code}", "event_type": kind}


def test_summary_excludes_previous_collections_and_counts_distinct_series():
    events = history([
        event("revision", snapshot="old"), event("revision"),
        event("new_observation"), event("new_observation", "2"),
        event("historical_fill", "2"), event("new_series", "10"), event("new_series", "10"),
    ])
    before = events.copy(deep=True)
    summary = latest_changes(events, metadata())
    assert summary["counts"] == dict(revision=1, new_observation=2, historical_fill=1, new_series=2)
    assert summary["series_count"] == 3
    assert len(summary["events"]) == 6
    assert set(summary["events"].snapshot_id) == {"current"}
    assert summary["by_series"].code.tolist() == ["1", "2", "10"]
    assert summary["by_series"][list(EVENT_LABELS)].sum().to_dict() == summary["counts"]
    pd.testing.assert_frame_equal(events, before)


def test_latest_unchanged_does_not_reuse_older_changes():
    summary = latest_changes(history([event("revision", snapshot="old")]), metadata())
    assert summary["snapshot_id"] == "current"
    assert summary["events"].empty
    assert summary["by_series"].empty
    assert summary["series_count"] == 0
    assert not any(summary["counts"].values())


def test_missing_comparison_is_not_reported_as_zero_changes():
    assert latest_changes(history([]), None) is None


def test_overview_matches_published_comparison_and_preserves_charts():
    import json

    _, _, _, manifest = load_snapshot(ROOT)
    pointer = json.loads((ROOT / "data/processed/latest.json").read_text())
    events, meta = read_history(ROOT / pointer["path"], manifest)
    summary = latest_changes(events, meta)
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Visão geral").run()
    assert not app.exception
    assert any(expander.label == "O que mudou na última atualização" for expander in app.expander)
    assert len(app.get("plotly_chart")) == 2
    if summary is not None:
        metrics = {m.label: m.value for m in app.metric}
        assert metrics["Valores revisados"] == str(summary["counts"]["revision"])
        assert metrics["Novas referências"] == str(summary["counts"]["new_observation"])
        if summary["events"].empty:
            assert any("Nenhuma mudança nos valores originais" in message.value for message in app.info)
        else:
            assert len(app.dataframe[0].value) == summary["series_count"]
    app.sidebar.radio[0].set_value("Histórico de revisões").run()
    assert not app.exception
