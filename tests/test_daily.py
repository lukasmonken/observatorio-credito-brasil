import json
import importlib.util
from pathlib import Path
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location('update_data', Path(__file__).parents[1] / 'scripts/update_data.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_publish_gate():
    old = pd.DataFrame({'code': [1, 2], 'date': ['2026-01-01'] * 2, 'original': [1., 2.]})
    ok = dict(status='success', failures=0, successes=2)
    revised = old.copy()
    revised.loc[0, 'original'] = 1.5
    module.validate_candidate(ok, old, revised, [1, 2])
    with pytest.raises(ValueError, match='incompleta'):
        module.validate_candidate({**ok, 'status': 'partial', 'failures': 1}, old, revised, [1, 2])
    with pytest.raises(ValueError, match='todas'):
        module.validate_candidate(ok, old, revised.iloc[:1], [1, 2])
    revised.loc[0, 'original'] = float('nan')
    with pytest.raises(ValueError, match='cobertura'):
        module.validate_candidate(ok, old, revised, [1, 2])


def test_monthly_request_filters_full_history_and_keeps_evidence(tmp_path):
    from datetime import date
    from observatorio.client import SGSClient
    class Response:
        status_code = 200
        ok = True
        url = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json'
        headers = {}
        content = json.dumps([{'data': '01/12/2025', 'valor': '1'}, {'data': '01/01/2026', 'valor': '2'}]).encode()
        def json(self):
            return json.loads(self.content)
    class Session:
        def get(self, url, params, timeout):
            assert params == {'formato': 'json'}
            return Response()
    client = SGSClient(tmp_path, 'test', session=Session(), monthly_codes=[433])
    assert client.fetch(433, date(2026, 1, 1), date(2026, 1, 31)) == [{'data': '01/01/2026', 'valor': '2'}]
    assert len(list((tmp_path / 'test').glob('*.body'))) == 1
