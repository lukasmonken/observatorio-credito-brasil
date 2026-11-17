from unittest.mock import Mock

import pytest
import requests

from scripts.reconcile_indicators import REFERENCES, reconcile


def sample(code):
    _, unit, frequency = REFERENCES[code]
    label = "2º tri/2026" if frequency == "Q" else "04/2026"
    return {"catalog": [{"code": code, "unit": unit, "frequency": frequency}],
            "rows": [{"code": code, "date": "2026-04-01", "original": 5.1234, "reference_period": label}]}


def source(day="01/04/2026"):
    session = Mock()
    session.get.return_value.url = "https://api.bcb.gov.br/"
    session.get.return_value.json.return_value = [{"data": day, "valor": "5.1234"}]
    return session


@pytest.mark.parametrize("code", REFERENCES)
def test_value_unit_and_period(code):
    session = source("30/06/2026" if code == 22099 else "30/04/2026")
    assert reconcile(session, sample(code), code)["status"] == "confere"
    params = session.get.call_args.kwargs["params"]
    assert params["dataInicial"] == "01/04/2026"
    assert params["dataFinal"] == ("30/06/2026" if code == 22099 else "30/04/2026")


def test_divergence_records_both_sides():
    data = sample(20539)
    data["catalog"][0].update(unit="R$", frequency="Q")
    data["rows"][0].update(reference_period="05/2026", original=5123400)
    result = reconcile(source(), data, 20539)
    assert result["status"] == "divergência"
    assert result["detail"] == "valor, unidade, frequência, período"
    assert result["published_value"] == 5123400 and result["source_value"] == "5.1234"


def test_wrong_quarter_even_with_same_value():
    assert reconcile(source("01/07/2026"), sample(22099), 22099)["detail"] == "período"


def test_source_unavailable_is_distinct_from_divergence():
    session = source()
    session.get.side_effect = requests.Timeout
    assert reconcile(session, sample(3698), 3698)["status"] == "inconclusivo"


def test_missing_latest_value_is_not_skipped():
    data = sample(20631)
    data["rows"][0]["original"] = None
    assert reconcile(source(), data, 20631)["detail"] == "valor"
