import csv
from datetime import date
from io import StringIO

import pandas as pd
import pytest

from observatorio.csv_export import build_csv


@pytest.mark.parametrize('profile,separator,header', [('excel', ';', 'Valor original'), ('analysis', ',', 'original')])
def test_csv_roundtrip_preserves_numbers_text_and_dates(profile, separator, header):
    frame = pd.DataFrame({'code': ['00123', '00123'], 'date': [date(2026, 1, 1), date(2026, 2, 1)],
                          'name': ['Ação; "teste",\nsegunda linha', 'Outro'], 'original': [-1234.567891234, 0],
                          'missing': [None, None]})
    before = frame.copy(deep=True)
    content = build_csv(frame, profile)
    assert content.startswith(b'\xef\xbb\xbf')
    rows = list(csv.DictReader(StringIO(content.decode('utf-8-sig')), delimiter=separator))
    assert float(rows[0][header].replace(',', '.')) == frame.original.iloc[0]
    assert float(rows[1][header].replace(",", ".")) == 0
    assert rows[0]['missing'] == ''
    assert list(rows[0].values())[:3] == ['00123', '2026-01-01', 'Ação; "teste",\nsegunda linha']
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize('profile,separator', [('excel', ';'), ('analysis', ',')])
def test_csv_blocks_formula_text_but_preserves_numeric_negatives(profile, separator):
    text = ['=1+1', '  +1+1', '\t@SUM(A1)', '-1+2', '\rtext', 'https://example.com']
    rows = list(csv.reader(StringIO(build_csv(pd.DataFrame({'text': text, 'number': [-1.25]*6}), profile).decode('utf-8-sig')), delimiter=separator))
    assert all(row[0].startswith("'") for row in rows[1:6])
    assert rows[6][0] == text[-1]
    assert all(not row[1].startswith("'") for row in rows[1:])


def test_invalid_profile_and_infinity_fail():
    with pytest.raises(ValueError):
        build_csv(pd.DataFrame({'value': [1]}), 'invalid')
    with pytest.raises(ValueError):
        build_csv(pd.DataFrame({'value': [float('inf')]}))


def test_streamlit_csv_profile_controls_export(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from observatorio.config import ROOT
    import observatorio.csv_export as exports
    captured = []
    original = exports.build_csv
    def capture(frame, profile):
        result = original(frame, profile)
        captured.append((profile, result))
        return result
    monkeypatch.setattr(exports, 'build_csv', capture)
    app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30).run()
    app.sidebar.radio[0].set_value('Explorador de indicadores').run()
    assert not app.exception
    assert captured[-1][0] == 'excel'
    assert 'Código SGS' in captured[-1][1].decode('utf-8-sig')
    app.segmented_control(key='csv_profile').set_value('analysis').run()
    assert not app.exception
    assert captured[-1][0] == 'analysis'
    assert '"code","date"' in captured[-1][1].decode('utf-8-sig')


def test_revision_decimal_strings_remain_exact():
    value = '-0.12345678901234567890123456789'
    frame = pd.DataFrame({'difference': [value], 'code': ['00123']})
    rows = list(csv.DictReader(StringIO(build_csv(frame, 'excel').decode('utf-8-sig')), delimiter=';'))
    assert rows[0]['Diferença'] == value.replace('.', ',')
    assert rows[0]['Código SGS'] == '00123'
