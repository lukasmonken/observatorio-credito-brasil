import math
from datetime import date
import numpy as np
import pandas as pd

def parse_value(value):
    if value is None or str(value).strip() in ('', '-', '...', 'null'):
        return np.nan
    s = str(value).strip()
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    v = float(s)
    if not math.isfinite(v):
        raise ValueError(f'Número não finito: {value}')
    return v

def parse_rows(rows, as_of=None):
    if not rows:
        raise ValueError('Consulta sem observações')
    data = []
    for row in rows:
        if not isinstance(row, dict) or not {'data','valor'} <= row.keys():
            raise ValueError('Campos data/valor obrigatórios')
        dt = pd.to_datetime(row['data'], format='%d/%m/%Y', errors='raise')
        if dt.date() > (as_of or date.today()):
            raise ValueError('Data futura inesperada')
        data.append((dt, parse_value(row['valor'])))
    df = pd.DataFrame(data, columns=['date','value'])
    for _, group in df.groupby('date'):
        if group.value.nunique(dropna=False) > 1:
            raise ValueError('Duplicidade conflitante na mesma resposta')
    return df.drop_duplicates('date').sort_values('date').reset_index(drop=True)

def monthly(df, spec, as_of):
    x = df.set_index('date').value.sort_index()
    if spec['frequency'] == 'M':
        p = x.index.to_period('M')
        if p.duplicated().any():
            raise ValueError('Mais de uma observação no mesmo mês')
        x.index = p.to_timestamp()
    elif spec['frequency'] == 'D':
        # Last actual value (including explicit null) in each completed month.
        x = x.resample('MS').agg(lambda g: g.iloc[-1] if len(g) else np.nan)
        x = x[x.index < pd.Timestamp(as_of).to_period('M').to_timestamp()]
    else:
        raise ValueError('Frequência sem regra aprovada')
    if x.empty:
        raise ValueError('Sem meses concluídos')
    return x.reindex(pd.date_range(x.index.min(),x.index.max(),freq='MS')).rename('value')

def price_index(inflation):
    if (inflation.dropna() <= -100).any():
        raise ValueError('Inflação impossível para encadeamento')
    # A missing month invalidates the chain after it; never bridge unknown inflation.
    return (1 + inflation / 100).cumprod(skipna=False)

def indicators(x, spec, prices=None):
    out = pd.DataFrame({'original':x})
    allowed = spec['allowed_transforms']
    if 'ma3' in allowed: out['ma3'] = x.rolling(3,min_periods=3).mean()
    if 'mom_pct' in allowed: out['mom_pct'] = x.pct_change(fill_method=None).mul(100)
    if 'yoy_pct' in allowed: out['yoy_pct'] = x.pct_change(12,fill_method=None).mul(100)
    if 'diff_pp' in allowed: out['diff_pp'] = x.diff()
    if 'diff12_pp' in allowed: out['diff12_pp'] = x.diff(12)
    if 'base100' in allowed:
        valid = x.dropna()
        out['base100'] = x / valid.iloc[0] * 100 if len(valid) and valid.iloc[0] != 0 else np.nan
    if 'inflation12' in allowed:
        out['inflation12'] = ((1+x/100).rolling(12,min_periods=12).apply(np.prod,raw=True)-1)*100
    if 'real' in allowed:
        if prices is not None and len(prices.dropna()):
            out['real'] = x / prices.reindex(x.index) * prices.dropna().iloc[-1]
            out['real_yoy_pct'] = out['real'].pct_change(12,fill_method=None)*100
        else:
            out['real'] = np.nan
            out['real_yoy_pct'] = np.nan
    return out.replace([np.inf,-np.inf],np.nan)

def lag_pairs(x, y, lag):
    if not 0 <= lag <= 24:
        raise ValueError('Defasagem deve estar entre 0 e 24 meses')
    idx = pd.date_range(min(x.index.min(),y.index.min()),max(x.index.max(),y.index.max()),freq='MS')
    # Positive lag: X in month t-lag paired with Y in month t.
    return pd.concat([x.reindex(idx).shift(lag).rename('x'),y.reindex(idx).rename('y')],axis=1).dropna()

def correlations(x, y, max_lag=12):
    rows=[]
    for lag in range(max_lag+1):
        pairs=lag_pairs(x,y,lag)
        r = pairs.x.corr(pairs.y) if len(pairs)>=12 and pairs.x.std()>0 and pairs.y.std()>0 else np.nan
        rows.append(dict(lag=lag,n=len(pairs),correlation=r,start=str(pairs.index.min().date()) if len(pairs) else None,end=str(pairs.index.max().date()) if len(pairs) else None))
    return pd.DataFrame(rows)
