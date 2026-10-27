import hashlib
import json
from datetime import date
import pandas as pd
from sqlalchemy import text
from observatorio.pipeline import run_pipeline
from observatorio.db import engine_for
from observatorio.client import ReplayClient, APIError
import pytest

def evidence(folder,code,rows):
    folder.mkdir(exist_ok=True)
    body=json.dumps(rows).encode();(folder/f'{code}.body').write_bytes(body)
    envelope=dict(code=code,status=200,start='2020-01-01',end='2021-12-31',extracted_at='2022-01-01T00:00:00Z',body_file=f'{code}.body',sha256=hashlib.sha256(body).hexdigest())
    (folder/f'{code}.json').write_text(json.dumps(envelope))

def test_replay_checksum_and_coverage(tmp_path):
    evidence(tmp_path,433,[{'data':'01/01/2020','valor':'1'}])
    replay=ReplayClient(tmp_path)
    assert len(replay.fetch(433,date(2020,1,1),date(2021,12,31)))==1
    with pytest.raises(APIError,match='fim solicitado'): replay.fetch(433,date(2020,1,1),date(2022,1,1))
    (tmp_path/'433.body').write_text('[]')
    with pytest.raises(APIError,match='Checksum'): replay.fetch(433,date(2020,1,1),date(2021,12,31))

def test_vertical_pipeline_partial_idempotence_sql_and_export(tmp_path):
    raw=tmp_path/'raw';url='sqlite:///'+str(tmp_path/'test.db')
    for code,value in [(433,1),(20539,100)]:
        rows=[{'data':d.strftime('%d/%m/%Y'),'valor':str(value+i)} for i,d in enumerate(pd.date_range('2020-01-01',periods=24,freq='MS'))]
        evidence(raw,code,rows)
    kw=dict(start=date(2020,1,1),end=date(2021,12,31),full=True,replay=raw,codes=[433,20539,432],url=url,output_root=tmp_path)
    first=run_pipeline(**kw)
    second=run_pipeline(**kw)
    assert first['status']=='partial' and second['failures']==1
    assert second['snapshot']['series']==2
    engine=engine_for(url)
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM observations')).scalar()==48
        assert c.execute(text('SELECT count(*) FROM revisions')).scalar()==0
        assert c.execute(text('SELECT count(*) FROM v_latest')).scalar()==2
        assert c.execute(text("SELECT yoy_pct FROM v_monthly_changes WHERE code=20539 AND date='2021-01-01'")).scalar()==pytest.approx(12)
    sid=second['run_id']
    assert (tmp_path/f'data/processed/{sid}/analytics.csv').read_bytes()==(tmp_path/f'exports/tableau/{sid}/analytics.csv').read_bytes()
    pointer=(tmp_path/'data/processed/latest.json').read_text()
    # Total collection failure must keep the previous known snapshot.
    failure=run_pipeline(**{**kw,'codes':[432]})
    assert failure['status']=='failed'
    assert (tmp_path/'data/processed/latest.json').read_text()==pointer
