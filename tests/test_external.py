from datetime import date

import numpy as np
import pandas as pd
import pytest

from observatorio.config import catalog
from observatorio.quality import validate_monthly
from observatorio.transform import indicators


def specs():
    return [s for s in catalog() if s['classification'] == 'Setor externo e câmbio']


def test_external_catalog_concepts():
    assert {s['code'] for s in specs()} == {3698, 3546, 22708, 22709, 22707, 22701}
    for s in specs():
        assert s['refresh_full_history'] and s['frequency'] == 'M'
        assert 'real' not in s['allowed_transforms']
        assert ('sum12' in s['allowed_transforms']) == (s['measure_type'] in ('flow','balance'))
        if s['measure_type'] == 'balance':
            assert not {'yoy_pct','base100','mom_pct'} & set(s['allowed_transforms'])


def test_flow_sums_require_complete_calendar_and_preserve_deficits():
    spec = next(s for s in specs() if s['code'] == 22701)
    x = pd.Series(-10.0, index=pd.date_range('2024-01-01',periods=25,freq='MS'))
    result = indicators(x,spec)
    assert result.loc['2024-12-01','sum12'] == -120
    assert result.loc['2025-01-01','sum_ytd'] == -10
    assert result.loc['2024-11-01','sum_ytd'] == -110
    assert pd.isna(result.loc['2024-11-01','sum12'])
    x = x.drop(pd.Timestamp('2024-05-01'))
    result = indicators(x,spec)
    assert pd.isna(result.loc['2024-12-01','sum_ytd'])
    assert pd.isna(result.loc['2025-04-01','sum12'])
    assert result.loc['2025-05-01','sum12'] == -120
    assert pd.isna(indicators(x.iloc[2:], spec).loc['2024-04-01','sum_ytd'])
    x.iloc[-1] = 0
    assert indicators(x,spec).iloc[-1].sum_ytd == 0


@pytest.mark.parametrize('code,value,error',[(22701,-100,False),(22707,-100,False),(22708,-1,True),(22709,0,False),(3546,-1,True),(3698,0,True),(3698,-1,True)])
def test_external_domains(code,value,error):
    spec = next(s for s in specs() if s['code']==code)
    result = validate_monthly(pd.Series([value],index=pd.to_datetime(['2026-01-01'])),spec,date(2026,2,1))
    assert any(level=='error' for _,level,_ in result) == error


def test_external_dashboard_populated(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    import observatorio.snapshot
    from observatorio.config import ROOT
    frame, entries, quality, manifest = observatorio.snapshot.load_snapshot(ROOT)
    extra = []
    for s in specs():
        for i, dt in enumerate(pd.date_range('2025-01-01',periods=14,freq='MS')):
            extra.append(dict(code=s['code'],date=dt,original=-10 if s['measure_type']=='balance' else 5, sum_ytd=-10*(i%12+1),sum12=-120 if i>=11 else np.nan,mom_pct=0,yoy_pct=0))
    external = pd.DataFrame(extra)
    external.loc[(external.code==22701)&(external.date==pd.Timestamp('2026-02-01')),'original'] = np.nan
    codes=[s['code'] for s in specs()]
    monkeypatch.setattr(observatorio.snapshot,'load_snapshot',lambda *a,**kw:(pd.concat([frame[~frame.code.isin(codes)],external],ignore_index=True),[s for s in entries if s['code'] not in codes]+specs(),quality,manifest))
    st.cache_data.clear()
    app=AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=30).run()
    app.sidebar.radio[0].set_value('Setor externo e câmbio').run()
    assert not app.exception
    assert len(app.metric)==6 and app.metric[-1].value=='—'
    app.selectbox[0].set_value(pd.Timestamp('2026-01-01')).run()
    assert app.metric[-1].value=='-10,00 US$ milhões'
    app.selectbox[1].set_value(22701).run()
    app.selectbox[2].set_value('sum12').run()
    assert not app.exception
    app.selectbox[1].set_value(3698).run()
    assert not app.exception
    assert app.selectbox[2].value=='original'
    st.cache_data.clear()
