from datetime import date

import numpy as np
import pandas as pd
import pytest

from observatorio.config import catalog
from observatorio.labor import labor_period, labor_export
from observatorio.quality import validate_monthly
from observatorio.transform import indicators, monthly


def specs():
    return [s for s in catalog() if s['classification'] == 'Trabalho e renda']


def test_labor_catalog_preserves_concepts_and_no_double_deflation():
    entries = specs()
    assert {s['code'] for s in entries} == {24369, 24379, 24380, 24382}
    for s in entries:
        assert s['refresh_full_history'] and s['frequency'] == 'M'
        assert s['reference_period'] == 'trimestre móvel'
        assert not s['seasonally_adjusted']
        assert 'real' not in s['allowed_transforms']
        assert 'mom_pct' not in s['allowed_transforms']
        assert 'IBGE' in s['source']
    assert entries[0]['allowed_transforms'] == ['original', 'diff12_pp']


def test_calendar_annual_change_and_missing_months():
    rate = specs()[0]
    raw = pd.DataFrame({'date': pd.to_datetime(['2024-01-01','2024-03-01','2025-01-01','2025-02-01','2025-03-01']), 'value':[8, 0, 6, 5, 0]})
    x = monthly(raw, rate, date(2025,4,1))
    result = indicators(x, rate)
    assert result.loc['2025-01-01','diff12_pp'] == -2
    assert np.isnan(result.loc['2025-02-01','diff12_pp'])
    assert result.loc['2025-03-01','diff12_pp'] == 0
    levels = indicators(x, specs()[1])
    assert levels.loc['2025-01-01','yoy_pct'] == -25
    assert np.isnan(levels.loc['2025-03-01','yoy_pct'])


@pytest.mark.parametrize('code,value', [(24369,-1),(24369,101),(24379,-1),(24380,-1),(24382,-1)])
def test_invalid_labor_values_block_publication(code,value):
    spec = next(s for s in specs() if s['code']==code)
    x = pd.Series([value], index=pd.to_datetime(['2026-01-01']))
    assert any(level=='error' for _,level,_ in validate_monthly(x,spec,date(2026,2,1)))


def test_export_retains_units_missing_values_and_income_base():
    frame = pd.DataFrame([
        {'code':24369,'date':pd.Timestamp('2026-01-01'),'original':0,'diff12_pp':-2},
        {'code':24382,'date':pd.Timestamp('2026-01-01'),'original':np.nan,'yoy_pct':np.nan},
    ])
    result = labor_export(frame,specs(),{'snapshot_id':'test'},'2026-08')
    assert labor_period('2026-01-01') == '11/2025–01/2026'
    assert result.iloc[0]['value']==0 and result.iloc[0].change_unit=='p.p.'
    assert pd.isna(result.iloc[1]['value']) and result.iloc[1].change_unit=='%'
    assert result.iloc[1].income_price_base=='2026-08'
    assert result.snapshot_id.eq('test').all()


def test_incremental_refreshes_full_history_and_records_income_base(tmp_path, monkeypatch):
    from observatorio.client import SGSClient
    from observatorio.pipeline import run_pipeline
    from observatorio.snapshot import load_snapshot
    calls = []

    def fetch(self, code, start, end):
        calls.append((code, start))
        return [{'data':d.strftime('%d/%m/%Y'), 'valor':str(100+i)} for i,d in enumerate(pd.date_range('2020-01-01', '2023-01-01', freq='MS'))]

    monkeypatch.setattr(SGSClient, 'fetch', fetch)
    args = dict(start=date(2020,1,1), end=date(2023,1,31), codes=[24382], url='sqlite:///'+str(tmp_path/'labor.db'), output_root=tmp_path)
    assert run_pipeline(**args, full=True)['status'] == 'success'
    assert run_pipeline(**args, full=False, requery_months=3)['status'] == 'success'
    assert calls == [(24382,date(2020,1,1)),(24382,date(2020,1,1))]
    _, entries, _, _ = load_snapshot(tmp_path)
    assert entries[0]['income_price_base'] == '2022-12'


def test_dashboard_with_labor_data(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    import observatorio.snapshot
    from observatorio.config import ROOT
    original = observatorio.snapshot.load_snapshot
    frame, entries, quality, manifest = original(ROOT)
    extra = []
    for s in specs():
        for i, dt in enumerate(pd.date_range('2025-01-01',periods=14,freq='MS')):
            extra.append(dict(code=s['code'], date=dt, original=8 if s['code']==24369 else 100+i, diff12_pp=0 if i>=12 else np.nan, yoy_pct=12 if i>=12 else np.nan))
    labor = pd.DataFrame(extra)
    labor.loc[(labor.code==24382) & (labor.date==pd.Timestamp('2026-02-01')), 'original'] = np.nan
    monkeypatch.setattr(observatorio.snapshot, 'load_snapshot', lambda *a,**kw:(pd.concat([frame,labor],ignore_index=True),entries+specs(),quality,manifest))
    st.cache_data.clear()
    app=AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=30).run()
    app.sidebar.radio[0].set_value('Trabalho e renda').run()
    assert not app.exception
    assert len(app.metric)==4 and app.metric[-1].value=='—'
    app.selectbox[0].set_value(pd.Timestamp('2026-01-01')).run()
    assert app.metric[-1].value=='112,00 R$'
    app.selectbox[1].set_value(24382).run()
    app.selectbox[2].set_value('yoy_pct').run()
    assert not app.exception
    st.cache_data.clear()
