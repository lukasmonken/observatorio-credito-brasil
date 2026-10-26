import hashlib
import json
import logging
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from .config import ROOT, catalog, database_url
from .client import SGSClient, ReplayClient
from .db import engine_for, initialize, register_catalog, persist_series, read_observations, check, numeric
from .transform import parse_rows, monthly, price_index, indicators
from .quality import validate_monthly

log=logging.getLogger(__name__)

def utcnow(): return datetime.now(timezone.utc).isoformat()

def build_snapshot(engine, specs, run_id, as_of, summary, output_root=ROOT):
    monthly_data={}
    for s in specs:
        df=read_observations(engine,s['code'])
        if not df.empty:
            df=df[df.date.dt.date<=as_of]
            if not df.empty: monthly_data[s['code']]=monthly(df,s,as_of)
    if not monthly_data:
        return None
    prices=price_index(monthly_data[433]) if 433 in monthly_data else None
    base=str(prices.dropna().index[-1].date()) if prices is not None and not prices.dropna().empty else None
    frames=[]
    catalog_rows=[]
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM derived_indicators'))
        conn.execute(text('DELETE FROM monthly_observations'))
        for s in specs:
            code=s['code']
            x=monthly_data.get(code)
            if x is None: continue
            checks=validate_monthly(x,s,as_of)
            for name,severity,message in checks:
                conn.execute(text('INSERT INTO quality VALUES(:id,:run,:code,:name,:severity,:message)'),dict(id=str(uuid.uuid4()),run=run_id,code=code,name=name,severity=severity,message=message))
            if any(c[1]=='error' for c in checks):
                raise ValueError(f'Qualidade impeditiva no snapshot: {code}')
            frame=indicators(x,s,prices)
            frame.index.name='date'
            frame=frame.reset_index()
            frame['code']=code
            frame['name']=s['name']
            frame['unit']=s['unit']
            frame['segment']=s['segment']
            frame['classification']=s['classification']
            frame['modality']=s['modality']
            frame['resources']=s['resources']
            frame['snapshot_id']=run_id
            frame['price_base_month']=base if 'real' in frame.columns else None
            valid=x.dropna()
            frame['index_base_month']=str(valid.index[0].date()) if 'base100' in frame.columns and len(valid) else None
            frames.append(frame)
            conn.execute(text('INSERT INTO monthly_observations VALUES(:code,:date,:value,:run)'),[dict(code=code,date=str(t.date()),value=numeric(v),run=run_id) for t,v in x.items()])
            records=[]
            for metric in [c for c in s['allowed_transforms'] if c!='original']:
                for t,v in zip(frame.date,frame[metric]):
                    records.append(dict(code=code,date=str(t.date()),metric=metric,value=numeric(v),base=base if metric.startswith('real') else str(valid.index[0].date()) if metric=='base100' and len(valid) else None,run=run_id))
            if records:
                conn.execute(text('INSERT INTO derived_indicators VALUES(:code,:date,:metric,:value,:base,:run)'),records)
            catalog_rows.append({**s,'coverage_observed':dict(start=str(x.index.min().date()),end=str(x.index.max().date())), 'months':int(x.notna().sum())})
    result=pd.concat(frames,ignore_index=True).sort_values(['code','date'])
    if result.duplicated(['code','date']).any(): raise ValueError('Duplicidade no snapshot')
    with engine.connect() as conn:
        quality=pd.read_sql(text('SELECT code,check_name,severity,message FROM quality WHERE run_id=:run'),conn,params={'run':run_id})
        latest=pd.read_sql(text('SELECT * FROM v_latest'),conn)
        coverage=pd.read_sql(text('SELECT * FROM v_coverage'),conn)
    target=output_root/'data/processed'/run_id
    target.mkdir(parents=True,exist_ok=False)
    result.to_csv(target/'analytics.csv',index=False,date_format='%Y-%m-%d')
    latest.to_csv(target/'latest.csv',index=False)
    quality.to_csv(target/'quality.csv',index=False)
    coverage.to_csv(target/'coverage.csv',index=False)
    flat=pd.DataFrame([{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in s.items()} for s in catalog_rows])
    flat.to_csv(target/'catalog.csv',index=False)
    (target/'catalog.json').write_text(json.dumps(catalog_rows,ensure_ascii=False,indent=2))
    manifest=dict(snapshot_id=run_id,created_at=utcnow(),as_of=str(as_of),price_base_month=base,
        rows=len(result),series=int(result.code.nunique()),summary=summary,files={})
    for name in ('analytics.csv','latest.csv','quality.csv','coverage.csv','catalog.csv'):
        manifest['files'][name]=hashlib.sha256((target/name).read_bytes()).hexdigest()
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    # Tableau consumes byte-identical files. Reconciliation is an actual SHA256 check.
    tableau=output_root/'exports/tableau'/run_id
    tableau.mkdir(parents=True,exist_ok=False)
    for name in manifest['files']:
        (tableau/name).write_bytes((target/name).read_bytes())
        assert hashlib.sha256((tableau/name).read_bytes()).hexdigest()==manifest['files'][name]
    (tableau/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    pointer=dict(snapshot_id=run_id,path=str(target.relative_to(output_root)))
    pointer_path=output_root/'data/processed/latest.json'
    tmp=pointer_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(pointer))
    os.replace(tmp,pointer_path)
    (output_root/'exports/tableau/latest.json').write_text(json.dumps(dict(snapshot_id=run_id,path=str(tableau.relative_to(output_root)))))
    return manifest

def run_pipeline(start=date(2010,1,1),end=None,full=False,requery_months=18,replay=None,codes=None,url=None,output_root=ROOT):
    end=end or date.today()
    if start>end or requery_months<1: raise ValueError('Datas ou janela inválidas')
    specs=catalog()
    if codes:
        unknown=set(codes)-{s['code'] for s in specs}
        if unknown: raise ValueError(f'Séries não verificadas: {unknown}')
    engine=engine_for(url or database_url())
    initialize(engine)
    register_catalog(engine,specs)
    run_id=str(uuid.uuid4())
    client=ReplayClient(replay) if replay else SGSClient(output_root/'data/raw',run_id, monthly_codes=[s['code'] for s in specs if s['frequency']=='M'])
    summary=dict(results=[],source_replay=str(Path(replay).resolve()) if replay else None,start=str(start),end=str(end),requery_months=requery_months)
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO runs VALUES(:id,:at,NULL,\'running\',:mode,:summary)'),dict(id=run_id,at=utcnow(),mode='replay' if replay else 'full' if full else 'incremental',summary=json.dumps(summary)))
    for spec in specs:
        code=spec['code']
        if codes and code not in codes: continue
        try:
            previous=read_observations(engine,code)
            begin=start
            if not full and not previous.empty:
                begin=max(start,(previous.date.max()-pd.DateOffset(months=requery_months)).replace(day=1).date())
            rows=client.fetch(code,begin,end)
            parsed=parse_rows(rows,as_of=end)
            if parsed.date.min().date()<begin: raise ValueError('Resposta fora do intervalo solicitado')
            if spec['frequency']=='D':
                expected=pd.date_range(parsed.date.min(),parsed.date.max(),freq='D')
                missing=len(expected.difference(pd.DatetimeIndex(parsed.date)))
                if missing: check(engine,run_id,code,'daily_gaps','warning',f'{missing} dias ausentes no intervalo observado da meta Selic; sem preenchimento automático')
            x=monthly(parsed,spec,end)
            checks=validate_monthly(x,spec,end)
            if any(c[1]=='error' for c in checks): raise ValueError(str(checks))
            revised=persist_series(engine,code,parsed,run_id)
            item=dict(code=code,status='success',rows=len(parsed),revisions=revised,start=str(begin))
            log.info('SGS %s: %s linhas; %s revisões',code,len(parsed),revised)
        except Exception as exc:
            item=dict(code=code,status='failed',error=str(exc))
            check(engine,run_id,code,'collection','error',str(exc))
            log.error('SGS %s falhou: %s',code,exc)
        summary['results'].append(item)
    success=sum(x['status']=='success' for x in summary['results'])
    failures=len(summary['results'])-success
    summary['status']='partial' if success and failures else 'failed' if failures else 'success'
    summary['successes'],summary['failures']=success,failures
    summary['requested_series']=len(summary['results'])
    summary['catalog_series']=len(specs)
    manifest=None
    try:
        if success:
            manifest=build_snapshot(engine,specs,run_id,end,summary,output_root)
    except Exception as exc:
        summary['status']='failed'
        summary['snapshot_error']=str(exc)
        log.exception('Não foi possível publicar snapshot')
    with engine.begin() as conn:
        conn.execute(text('UPDATE runs SET ended_at=:end,status=:status,summary_json=:summary WHERE run_id=:run'),dict(end=utcnow(),status=summary['status'],summary=json.dumps(summary),run=run_id))
    audit=output_root/'reports/runs'
    audit.mkdir(parents=True,exist_ok=True)
    (audit/f'{run_id}.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    state=output_root/'data/processed/last_attempt.json'
    state.parent.mkdir(parents=True,exist_ok=True)
    temp=state.with_suffix('.tmp')
    temp.write_text(json.dumps(dict(run_id=run_id,ended_at=utcnow(),**summary),ensure_ascii=False,indent=2))
    os.replace(temp,state)
    engine.dispose()
    return dict(run_id=run_id,**summary,snapshot=manifest)
