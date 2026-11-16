"""Contratos econômicos do catálogo e reconciliação offline do snapshot publicado."""

import json
from urllib.parse import urlparse

import pandas as pd
import pytest

from observatorio.config import ROOT, catalog
from observatorio.snapshot import load_snapshot


@pytest.fixture(params=catalog(), ids=lambda spec: str(spec["code"]))
def spec(request):
    return request.param


def test_origem_e_documentacao(spec):
    grupo = spec["classification"]
    if spec["code"] in {189, 7456}:
        produtor = "FGV IBRE"
    elif grupo in {"Inflação", "Trabalho e renda", "Crescimento e atividade"}:
        produtor = "IBGE"
    else:
        produtor = "Banco Central do Brasil"
    assert spec["producer"] == produtor
    assert spec["distributor"] == "BCB/SGS"
    assert spec["source_url"].startswith("https://")
    host = urlparse(spec["source_url"]).hostname
    assert host == "bcb.gov.br" or (host and host.endswith(".bcb.gov.br"))
    assert (ROOT / spec["metadata_evidence"]).is_file()
    limites = spec["limitations"]
    assert isinstance(limites, list) and limites
    assert all(isinstance(item, str) and item.strip() for item in limites)
    assert len(limites) == len(set(limites))


def test_unidade_e_transformacoes(spec):
    tipo = spec["measure_type"]
    unidade = spec["unit"]
    metricas = set(spec["allowed_transforms"])
    assert "original" in metricas
    assert len(metricas) == len(spec["allowed_transforms"])
    unidades = {
        "stock": {"R$ milhões", "US$ milhões", "mil pessoas"},
        "flow": {"R$ milhões", "US$ milhões"},
        "balance": {"US$ milhões"},
        "index": {"índice"},
        "rate": {"%", "% a.a.", "p.p."},
        "variation": {"% a.m."},
        "exchange_rate": {"R$/US$"},
        "income_real": {"R$"},
    }
    assert unidade in unidades[tipo]
    if spec["classification"] in {"Estoque", "Concessões"}:
        assert unidade == "R$ milhões"
    if spec["classification"] == "Spread":
        assert unidade == "p.p."
    if spec["classification"] == "Juros":
        assert unidade == "% a.a."
    if metricas & {"real", "real_yoy_pct"}:
        assert unidade == "R$ milhões" and tipo in {"stock", "flow"}
    if metricas & {"sum12", "sum_ytd"}:
        assert tipo in {"flow", "balance"} and spec["frequency"] == "M"
    if metricas & {"diff_pp", "diff12_pp"}:
        assert tipo == "rate"
    if tipo in {"rate", "variation"}:
        assert not metricas & {"mom_pct", "yoy_pct", "base100"}
    if metricas & {"inflation12", "inflation_ytd"}:
        assert tipo == "variation" and unidade == "% a.m."


def test_frequencia_e_sazonalidade(spec):
    freq = spec["frequency"]
    assert spec["aggregation"] == {
        "D": "last_complete_month", "M": "identity_month", "Q": "identity_quarter"
    }[freq]
    metricas = set(spec["allowed_transforms"])
    ajuste = spec.get("seasonally_adjusted")
    if spec.get("activity_group") or spec.get("external_group") or spec.get("reference_period") == "trimestre móvel":
        assert type(ajuste) is bool
    if "com ajuste sazonal" in spec["official_name"].lower():
        assert ajuste is True
    if "sem ajuste sazonal" in " ".join(spec["limitations"]).lower():
        assert ajuste is False
    if "qoq_pct" in metricas:
        assert freq == "Q" and ajuste is True
    if freq == "Q":
        assert not metricas & {"mom_pct", "ma3", "sum12", "inflation12"}


def test_configuracao_independe_da_coleta(spec):
    assert spec["coverage_observed"] == {"start": None, "end": None}
    assert "months" not in spec


def test_cobertura_publicada_reconcilia_com_as_observacoes():
    pointer = (ROOT / "data/processed/latest.json").read_text()
    frame, published, _, _ = load_snapshot(ROOT, pointer=pointer)
    directory = ROOT / json.loads(pointer)["path"]
    coverage = pd.read_csv(directory / "coverage.csv").set_index("code", verify_integrity=True)
    assert set(coverage.index) == {item["code"] for item in published}
    for item in published:
        code = item["code"]
        rows = frame.loc[frame.code == code].set_index("date").sort_index()
        summary = coverage.loc[code]
        first, last = rows.index.min(), rows.index.max()
        cadence = "QS-JAN" if item["frequency"] == "Q" else "MS"
        assert rows.index.equals(pd.date_range(first, last, freq=cadence)), code
        start, end = first.date().isoformat(), last.date().isoformat()
        assert (summary.first_date, summary.last_date) == (start, end), code
        assert item["coverage_observed"] == {"start": start, "end": end}, code
        assert item["months"] == summary.observed_months == rows.original.count(), code
        assert summary.missing_months == rows.original.isna().sum(), code
        assert summary.unit == item["unit"] and rows.unit.eq(item["unit"]).all(), code
