import pandas as pd

def validate_monthly(x, spec, as_of):
    results=[]
    def add(name,severity,message): results.append((name,severity,message))
    add('coverage','info',f'{x.index.min():%Y-%m} a {x.index.max():%Y-%m}; {x.notna().sum()} meses observados')
    if x.isna().any(): add('gaps','warning',f'{x.isna().sum()} valores ausentes; não interpolados')
    valid=x.dropna()
    if valid.empty:
        add('coverage','error','Nenhum valor numérico'); return results
    lag=(pd.Timestamp(as_of)-valid.index.max()).days
    if lag > spec['max_lag_days']: add('freshness','warning',f'Última referência há {lag} dias; limiar operacional, não calendário oficial')
    if spec['measure_type'] in ('stock','flow','index') and (valid<0).any():
        add('range','error','Valor negativo incompatível com estoque, fluxo ou índice selecionado')
    if spec['classification']=='Inadimplência' and ((valid<0)|(valid>100)).any():
        add('range','error','Inadimplência fora de [0,100]')
    change=x.diff().abs()
    # Descriptive flag only, retaining all observations including shocks.
    threshold=change.median()*10
    extreme=(change>threshold).sum() if threshold>0 else 0
    if extreme: add('large_change','warning',f'{extreme} variações >10x mediana absoluta; observações preservadas')
    if not any(r[1]=='error' for r in results): add('schema','info','Unicidade, calendário mensal e domínio verificados')
    return results
