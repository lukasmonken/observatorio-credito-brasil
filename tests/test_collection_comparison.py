import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from observatorio.config import ROOT
from observatorio.revisions import COLUMNS, compare_collections, compare_snapshots

SPECS = [{"code": 1, "name": "Taxa", "unit": "%", "measure_type": "rate", "frequency": "M"}]
META = {"baseline_snapshot_id": "a", "comparisons": [{"snapshot_id": "b"}, {"snapshot_id": "c"}]}


def frame(values):
    return pd.DataFrame([{"code": 1, "date": date, "original": value} for date, value in values], columns=["code", "date", "original"])


def chain(a, b, c):
    return pd.DataFrame(
        compare_snapshots(frame(a), frame(b), SPECS, "a", "b", "2026-11-01T12:00:00+00:00")
        + compare_snapshots(frame(b), frame(c), SPECS, "b", "c", "2026-11-02T12:00:00+00:00"), columns=COLUMNS,
    )


def test_revisions_that_reverse_cancel_and_selection_still_exposes_intermediate():
    events = chain([("2026-01-01", "1")], [("2026-01-01", "2")], [("2026-01-01", "1.00")])
    assert compare_collections(events, META, "a", "c").empty
    assert compare_collections(events, META, "a", "b").iloc[0].difference == "1"
    assert compare_collections(events, META, "b", "c").iloc[0].difference == "-1.00"


def test_net_difference_preserves_decimal_precision_and_zero():
    events = chain([("2026-01-01", "0")], [("2026-01-01", "-0.1")], [("2026-01-01", "0.01")])
    result = compare_collections(events, META, "a", "c").iloc[0]
    assert result.old_value == "0" and result.new_value == "0.01"
    assert result.difference == "0.01" and result.difference_unit == "p.p."
    assert result.previous_snapshot_id == "a" and result.snapshot_id == "c"


def test_new_observation_then_revision_is_still_an_addition():
    events = chain([("2026-01-01", "1")], [("2026-01-01", "1"), ("2026-02-01", "2")], [("2026-01-01", "1"), ("2026-02-01", "3")])
    result = compare_collections(events, META, "a", "c").iloc[0]
    assert result.event_type == "added_observation"
    assert result.old_value == result.difference == ""
    assert result.new_value == "3"


def test_historical_fill_and_new_series_are_additions():
    events = chain([], [("2026-02-01", "2")], [("2026-01-01", "1"), ("2026-02-01", "2")])
    result = compare_collections(events, META, "a", "c")
    assert len(result) == 2 and result.event_type.eq("added_observation").all()


def test_unchanged_comparisons_have_empty_result_with_export_columns():
    result = compare_collections(pd.DataFrame(columns=COLUMNS), META, "a", "c")
    assert result.empty
    assert {"old_value", "new_value", "previous_snapshot_id", "snapshot_id"} <= set(result.columns)


@pytest.mark.parametrize("earlier,later", [("a", "a"), ("c", "b"), ("missing", "c")])
def test_invalid_selection_rejected(earlier, later):
    with pytest.raises(ValueError):
        compare_collections(pd.DataFrame(columns=COLUMNS), META, earlier, later)


def test_broken_intermediate_values_rejected():
    events = chain([("2026-01-01", "1")], [("2026-01-01", "2")], [("2026-01-01", "3")])
    events.loc[1, "old_value"] = "999"
    with pytest.raises(ValueError, match="intermediários"):
        compare_collections(events, META, "a", "c")


def test_input_row_order_is_not_comparison_order():
    events = chain([("2026-01-01", "1")], [("2026-01-01", "2")], [("2026-01-01", "4")])
    assert compare_collections(events.iloc[::-1], META, "a", "c").iloc[0].difference == "3"


def test_dashboard_compares_selected_endpoints_without_changing_active_data():
    pointer = (ROOT / "data/processed/latest.json").read_bytes()
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Histórico de revisões").run()
    assert not app.exception
    directory = ROOT / json.loads(pointer)["path"]
    meta = json.loads((directory / "revision_history.json").read_text())
    app.selectbox(key="comparison_earlier").set_value(meta["baseline_snapshot_id"])
    app.button(key="compare_collections_submit").click().run()
    assert not app.exception and not app.error
    assert any(m.label == "Revisões líquidas" for m in app.metric)
    assert app.get("download_button")
    assert (ROOT / "data/processed/latest.json").read_bytes() == pointer

    same = meta["comparisons"][0]["snapshot_id"]
    app.selectbox(key="comparison_earlier").set_value(same)
    app.selectbox(key="comparison_later").set_value(same)
    app.button(key="compare_collections_submit").click().run()
    assert not app.exception
    assert any("inicial anterior" in item.value for item in app.info)
