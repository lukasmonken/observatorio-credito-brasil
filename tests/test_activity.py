from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from observatorio.config import ROOT, catalog
from observatorio.db import engine_for, initialize, register_catalog
from observatorio.transform import monthly, indicators


def specs():
    return [s for s in catalog() if s.get('activity_group')]


def test_activity_concepts():
    entries=specs()
    assert len(entries)==14
    for s in entries:
        assert s['refresh_full_history']
        assert 'real' not in s['allowed_transforms']
        assert 'sum12' not in s['allowed_transforms']
        if s['frequency']=='Q':
            assert 'mom_pct' not in s['allowed_transforms']
            assert ('qoq_pct' in s['allowed_transforms']) == s['seasonally_adjusted']


def test_quarter_calendar_no_monthly_repetition_and_annual_growth():
    s=next(s for s in specs() if s['code']==22099)
    raw=pd.DataFrame({'date':pd.to_datetime(['2024-01-01','2024-07-01','2024-10-01','2025-01-01','2025-04-01']),'value':[100,110,0,120,130]})
    x=monthly(raw,s,date(2025,5,1))
    assert len(x)==5 and x.index.month.tolist()==[1,4,7,10,1]
    assert np.isnan(x.iloc[1])
    result=indicators(x,s)
    assert result.iloc[-1].yoy_pct==pytest.approx(20)
    adjusted={**s,'allowed_transforms':['original','qoq_pct']}
    q=indicators(x,adjusted)
    assert np.isnan(q.iloc[2].qoq_pct) and np.isnan(q.iloc[-1].qoq_pct)
    assert q.iloc[3].qoq_pct==-100
    duplicate=pd.concat([raw,raw.iloc[[0]].assign(date=pd.Timestamp('2024-03-31'))])
    with pytest.raises(ValueError,match='mesmo trimestre'):
        monthly(duplicate,s,date(2025,5,1))


def test_sqlite_legacy_migration_preserves_data_and_foreign_keys(tmp_path):
    e=engine_for('sqlite:///'+str(tmp_path/'legacy.db'))
    with e.begin() as conn:
        for stmt in (ROOT/'sql/schema.sql').read_text().replace("'D','M','Q'","'D','M'").split(';'):
            if stmt.strip(): conn.execute(text(stmt))
    register_catalog(e,[next(s for s in specs() if s['code']==24364)])
    with e.begin() as conn:
        conn.execute(text("INSERT INTO runs VALUES('r','2026-01-01',NULL,'success','full','{}')"))
        conn.execute(text("INSERT INTO observations VALUES(24364,'2025-01-01',100,'r')"))
    initialize(e)
    initialize(e)
    register_catalog(e,[next(s for s in specs() if s['code']==22099)])
    with e.connect() as conn:
        assert conn.execute(text('SELECT value FROM observations')).scalar()==100
        assert conn.execute(text('PRAGMA foreign_keys')).scalar()==1
        assert not conn.execute(text('PRAGMA foreign_key_check')).all()
        assert conn.execute(text('SELECT count(*) FROM series')).scalar()==2


def test_quarterly_pipeline_and_excel(tmp_path,monkeypatch):
    from observatorio.client import SGSClient
    from observatorio.pipeline import run_pipeline
    from observatorio.snapshot import load_snapshot
    from observatorio.excel import build_excel
    from zipfile import ZipFile
    from io import BytesIO
    calls=[]
    def fetch(self,code,start,end):
        calls.append((code,code in self.monthly_codes))
        return [{'data':d.strftime('%d/%m/%Y'),'valor':str(100+i)} for i,d in enumerate(pd.date_range('2024-01-01',periods=8,freq='QS'))]
    monkeypatch.setattr(SGSClient,'fetch',fetch)
    entries=[s for s in specs() if s['code'] in (22099,22109)]
    run_pipeline(codes=[s['code'] for s in entries],url='sqlite:///'+str(tmp_path/'db.sqlite'),output_root=tmp_path,start=date(2024,1,1),end=date(2026,1,1),full=True)
    frame,_,quality,manifest=load_snapshot(tmp_path)
    assert len(frame)==16
    assert calls==[(22099,True),(22109,True)]
    assert not quality.check_name.eq('gaps').any()
    assert set(frame.reference_period)=={f'{q}º tri/{y}' for y in (2024,2025) for q in (1,2,3,4)}
    data=frame[frame.code==22099]
    book=ZipFile(BytesIO(build_excel(data,entries[0],manifest,'yoy_pct','%',(date(2024,1,1),date(2026,1,1)),'')))
    strings=book.read('xl/sharedStrings.xml').decode()
    assert 'Trimestral' in strings and 'Trimestre' in strings



def test_activity_dashboard(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    import observatorio.snapshot
    frame,entries,quality,manifest=observatorio.snapshot.load_snapshot(ROOT)
    extra=[]
    for s in specs():
        x=pd.Series(range(100,120),index=pd.date_range('2020-01-01',periods=20,freq='QS' if s['frequency']=='Q' else 'MS'),dtype=float)
        rows=indicators(x,s).reset_index(names='date');rows['code']=s['code'];extra.append(rows)
    codes=[s['code'] for s in specs()]
    monkeypatch.setattr(observatorio.snapshot,'load_snapshot',lambda *a,**kw:(pd.concat([frame[~frame.code.isin(codes)],*extra],ignore_index=True),[s for s in entries if s['code'] not in codes]+specs(),quality,manifest))
    st.cache_data.clear()
    app=AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=30).run()
    app.sidebar.radio[0].set_value('Crescimento e atividade').run()
    assert not app.exception and len(app.metric)==6
    app.selectbox[0].set_value(22109).run()
    app.selectbox[1].set_value('qoq_pct').run()
    assert not app.exception
    app.selectbox[0].set_value(23982).run()
    assert not app.exception
    assert 'Variação trimestral (%)' not in app.selectbox[1].options
    st.cache_data.clear()
