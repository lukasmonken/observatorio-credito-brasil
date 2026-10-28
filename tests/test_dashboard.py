"""AppTest offline com snapshot real local; sem chamadas à internet."""

import pytest
from streamlit.testing.v1 import AppTest
from observatorio.config import ROOT


@pytest.mark.parametrize(
    "page",
    [
        "Visão geral",
        "Juros e crédito",
        "Famílias e inadimplência",
        "Explorador de indicadores",
        "Relações e defasagens",
        "Fontes e qualidade",
    ],
)
def test_dashboard_pages(page):
    # Integration with frozen real local snapshot, no internet calls.
    if not (ROOT / "data/processed/latest.json").exists():
        pytest.skip(
            "Snapshot local ausente; executar coleta/replay para verificar interface"
        )
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    assert not app.exception
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception


def test_explorer_transforms():
    if not (ROOT / "data/processed/latest.json").exists():
        pytest.skip("Snapshot ausente")
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Explorador de indicadores").run()
    if "Saldo - Total" not in app.selectbox[0].options:
        pytest.skip("SGS 20539 ausente do snapshot parcial")
    app.selectbox[0].set_value(20539).run()
    for metric in ["original", "real", "base100", "yoy_pct"]:
        app.selectbox[1].set_value(metric).run()
        assert not app.exception


def test_no_snapshot_state(tmp_path, monkeypatch):
    import observatorio.config

    monkeypatch.setattr(observatorio.config, "ROOT", tmp_path)
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("Ainda não há base" in x.value for x in app.info)


def test_broken_snapshot_state(tmp_path, monkeypatch):
    import observatorio.config

    monkeypatch.setattr(observatorio.config, "ROOT", tmp_path)
    p = tmp_path / "data/processed"
    p.mkdir(parents=True)
    (p / "latest.json").write_text("{broken")
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("Não foi possível" in x.value for x in app.error)


def test_invalid_attempt_metadata_does_not_break_dashboard(tmp_path, monkeypatch):
    import shutil
    import observatorio.config

    shutil.copytree(ROOT / "data/processed", tmp_path / "data/processed")
    (tmp_path / "data/processed/last_attempt.json").write_text("{broken")
    monkeypatch.setattr(observatorio.config, "ROOT", tmp_path)
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("estado da última coleta" in x.value for x in app.warning)


def test_snapshot_error_does_not_expose_internal_details(tmp_path, monkeypatch):
    import observatorio.config
    import observatorio.snapshot

    monkeypatch.setattr(observatorio.config, "ROOT", tmp_path)
    p = tmp_path / "data/processed"
    p.mkdir(parents=True)
    (p / "latest.json").write_text('{"snapshot_id":"private-error"}')

    def fail(*args, **kwargs):
        raise ValueError("private-path-and-internal-details")

    monkeypatch.setattr(observatorio.snapshot, "load_snapshot", fail)
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    assert not app.exception and app.error
    assert not app.code


def test_filter_between_monthly_references_has_empty_state():
    from datetime import date

    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Juros e crédito").run()
    app.date_input[0].set_value((date(2020, 1, 2), date(2020, 1, 20))).run()
    assert not app.exception
    assert any("Não há observações" in x.value for x in app.info)


def test_credit_selection_changes_charts_and_preserves_colors():
    import json

    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Juros e crédito").run()
    selected = list(app.multiselect[0].value)
    charts = app.get("plotly_chart")
    assert len(charts) == len(selected) == 3
    colors = [
        json.loads(chart.proto.spec)["data"][0]["line"]["color"] for chart in charts
    ]
    assert len(set(colors)) == 3
    app.multiselect[0].set_value(selected[1:]).run()
    assert not app.exception
    assert len(app.get("plotly_chart")) == 2
    assert [
        json.loads(chart.proto.spec)["data"][0]["line"]["color"]
        for chart in app.get("plotly_chart")
    ] == colors[1:]
    app.multiselect[0].set_value([]).run()
    assert not app.get("plotly_chart")
    assert any("Selecione ao menos" in item.value for item in app.info)


def test_monitoring_failure_is_visible_without_hiding_snapshot(tmp_path, monkeypatch):
    import shutil
    from datetime import datetime, timezone
    import observatorio.config
    from observatorio.monitoring import write_status

    shutil.copytree(ROOT / "data/processed", tmp_path / "data/processed")
    (tmp_path / "docs").mkdir()
    shutil.copy2(ROOT / "docs/metodologia.md", tmp_path / "docs/metodologia.md")
    now = datetime.now(timezone.utc).isoformat()
    write_status(
        tmp_path,
        {
            "status": "failed",
            "last_success_at": now,
            "started_at": now,
            "duration_seconds": 25,
            "failed_series": [432],
        },
    )
    monkeypatch.setattr(observatorio.config, "ROOT", tmp_path)
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("última tentativa" in item.value for item in app.warning)
    assert len(app.get("plotly_chart")) == 2
    app.sidebar.radio[0].set_value("Fontes e qualidade").run()
    assert not app.exception
    assert any("432" in item.value for item in app.warning)
    assert any(
        item.label == "Duração da tentativa" and item.value == "25 s"
        for item in app.metric
    )
