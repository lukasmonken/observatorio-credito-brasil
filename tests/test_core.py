import json
from datetime import date
from unittest.mock import Mock
import numpy as np
import pandas as pd
import pytest
import requests
from sqlalchemy import text
from observatorio.client import SGSClient, APIError, windows
from observatorio.transform import parse_rows, parse_value, monthly, indicators, price_index, lag_pairs
from observatorio.db import engine_for, initialize, register_catalog, persist_series
from observatorio.config import catalog
from observatorio.quality import validate_monthly

def spec(code): return next(s for s in catalog() if s['code']==code)
def values(v): return pd.Series(v,index=pd.date_range('2020-01-01',periods=len(v),freq='MS'),dtype=float)

@pytest.mark.parametrize('raw,expected',[('1.234,56',1234.56),('1234.56',1234.56),('-0,20',-.2),('0',0)])
def test_numbers(raw,expected): assert parse_value(raw)==expected

def test_null_is_not_zero():
    assert np.isnan(parse_value(''))
    with pytest.raises(ValueError): parse_value('NaN')
    with pytest.raises(ValueError): parse_value('inf')

def test_parsing_contract():
    row={'data':'01/01/2020','valor':'2,5'}
    assert len(parse_rows([row,row]))==1
    with pytest.raises(ValueError,match='conflitante'): parse_rows([row,{**row,'valor':'3'}])
    with pytest.raises(ValueError,match='futura'): parse_rows([row],as_of=date(2019,1,1))
    with pytest.raises(ValueError): parse_rows([{'data':'99/99/2020','valor':'2'}])
    with pytest.raises(ValueError): parse_rows([{'data':'01/01/2020'}])
    with pytest.raises(ValueError): parse_rows([])

def test_calendar_gap_does_not_compress_lag():
    df=parse_rows([{'data':'01/01/2020','valor':'100'},{'data':'01/03/2020','valor':'110'}])
    x=monthly(df,spec(20539),date(2020,4,1))
    assert len(x)==3 and np.isnan(x.iloc[1])
    out=indicators(x,spec(20539))
    assert np.isnan(out.mom_pct.iloc[2])
    assert np.isnan(out.ma3.iloc[2])

def test_daily_last_complete_month_no_mean():
    df=parse_rows([{'data':'01/01/2020','valor':'4'},{'data':'31/01/2020','valor':'5'},{'data':'01/02/2020','valor':'8'}])
    x=monthly(df,spec(432),date(2020,2,10))
    assert list(x)==[5]

def test_rate_change_is_pp():
    out=indicators(values([10,12]),spec(432))
    assert out.diff_pp.iloc[-1]==2
    assert 'mom_pct' not in out

def test_deflation_and_compound_inflation():
    prices=price_index(values([10,10]))
    out=indicators(values([100,110]),spec(20539),prices)
    assert out.real.iloc[0]==pytest.approx(110)
    assert out.real.iloc[1]==pytest.approx(110)
    out=indicators(values([1]*12),spec(433))
    assert out.inflation12.iloc[-1]==pytest.approx((1.01**12-1)*100)

def test_missing_inflation_breaks_chain():
    x=price_index(values([1,np.nan,2]))
    assert x.iloc[1:].isna().all()

def test_zero_base_not_infinite():
    x=indicators(values([0,1]),spec(20539))
    assert np.isnan(x.mom_pct.iloc[-1]) and x.base100.isna().all()

def test_lag_direction():
    pairs=lag_pairs(values([10,20,30]),values([1,2,3]),1)
    assert pairs.x.tolist()==[10,20] and pairs.y.tolist()==[2,3]

def test_windows_contiguous_under_ten_years():
    ws=list(windows(date(2010,1,1),date(2026,10,26)))
    assert len(ws)==4
    for a,b in ws: assert (b-a).days<3653
    for (_,b),(a,_) in zip(ws,ws[1:]): assert (a-b).days==1

def response(status=200,payload=None):
    r=Mock();r.status_code=status;r.ok=status==200;r.headers={};r.url='https://api.bcb.gov.br/test'
    r.content=json.dumps(payload if payload is not None else []).encode();r.json.return_value=payload if payload is not None else []
    return r

def test_retry_bounded_and_raw_preserved(tmp_path):
    session=Mock();session.get.side_effect=[response(503),response(200,[{'data':'01/01/2020','valor':'1'}])]
    sleep=Mock();client=SGSClient(tmp_path,'run',session=session,sleeper=sleep)
    rows=client.fetch(432,date(2020,1,1),date(2020,1,2))
    assert len(rows)==1 and session.get.call_count==2 and sleep.call_count==1
    assert len(list((tmp_path/'run').glob('*.body')))==2

def test_no_retry_permanent_error(tmp_path):
    session=Mock();session.get.return_value=response(400)
    with pytest.raises(APIError): SGSClient(tmp_path,'run',session=session).fetch(432,date(2020,1,1),date(2020,1,2))
    assert session.get.call_count==1

def test_timeout_and_invalid_json(tmp_path):
    session=Mock();session.get.side_effect=requests.Timeout('x')
    with pytest.raises(APIError): SGSClient(tmp_path,'timeout',session=session,sleeper=lambda _:None).fetch(432,date(2020,1,1),date(2020,1,2))
    assert session.get.call_count==3
    session=Mock();r=response();r.json.side_effect=ValueError('bad');session.get.return_value=r
    with pytest.raises(APIError,match='JSON inválido'): SGSClient(tmp_path,'json',session=session).fetch(432,date(2020,1,1),date(2020,1,2))

def test_idempotence_revision_and_unit_guard():
    e=engine_for('sqlite:///:memory:');initialize(e);register_catalog(e,[spec(432)])
    with e.begin() as c: c.execute(text("INSERT INTO runs VALUES('r','2020-01-01',NULL,'running','test','{}')"))
    df=parse_rows([{'data':'01/01/2020','valor':'4'}])
    assert persist_series(e,432,df,'r')==0
    assert persist_series(e,432,df,'r')==0
    df.loc[0,'value']=5
    assert persist_series(e,432,df,'r')==1
    assert persist_series(e,432,df,'r')==0
    with e.connect() as c:
        assert c.execute(text('SELECT count(*) FROM observations')).scalar()==1
        assert c.execute(text('SELECT old_value FROM revisions')).scalar()==4
    with pytest.raises(ValueError,match='unidade'): register_catalog(e,[{**spec(432),'unit':'wrong'}])

def test_quality_keeps_shock_and_rejects_impossible():
    checks=validate_monthly(values([1,2,3,90]),spec(21084),date(2020,5,1))
    assert any(c[1]=='warning' for c in checks) and not any(c[1]=='error' for c in checks)
    checks=validate_monthly(values([101]),spec(21084),date(2020,2,1))
    assert any(c[1]=='error' for c in checks)
