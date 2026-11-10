import pandas as pd
from observatorio.panorama import panorama_rows, reference_label


def test_latest_reference_preserves_missing_derived_zero_and_negative():
    df = pd.DataFrame([
        {'code':433,'date':pd.Timestamp('2026-08-01'),'original':0.2,'inflation12':4.5},
        {'code':433,'date':pd.Timestamp('2026-09-01'),'original':0.1,'inflation12':None},
        {'code':432,'date':pd.Timestamp('2026-09-01'),'original':0},
        {'code':22707,'date':pd.Timestamp('2026-08-01'),'original':-123},
    ])
    result = {r['code']:r for r in panorama_rows(df, [])}
    assert len(result) == 6
    assert result[433]['date'] == pd.Timestamp('2026-09-01')
    assert result[433]['value'] is None
    assert result[432]['value'] == 0
    assert result[22707]['value'] == -123
    assert result[22109]['date'] is None
    assert reference_label('2026-04-01', 'quarter') == '2º trimestre de 2026'
    assert reference_label('2026-01-01', 'rolling') == 'Trimestre móvel: 11/2025–01/2026'


def test_panorama_navigation():
    from streamlit.testing.v1 import AppTest
    from observatorio.config import ROOT
    app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30).run()
    assert not app.exception
    assert app.sidebar.radio[0].value == 'Panorama Brasil'
    assert len(app.metric) == 6
    app.button(key='panorama_module_24369').click().run()
    assert not app.exception
    assert app.sidebar.radio[0].value == 'Trabalho e renda'
