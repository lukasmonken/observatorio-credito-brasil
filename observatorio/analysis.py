"""Relatório descritivo gerado exclusivamente do snapshot observado."""
import pandas as pd
from .config import ROOT
from .snapshot import load_snapshot
from .transform import correlations

def analyze(root=ROOT):
    df,specs,quality,manifest=load_snapshot(root)
    by_code={s['code']:s for s in specs}
    def series(code,metric='original'):
        return df[df.code==code].set_index('date')[metric].sort_index()
    lines=['# Achados observados',f"\nSnapshot: `{manifest['snapshot_id']}`. Extração/reprocessamento: {manifest['created_at']}. Corte: {manifest['as_of']}.",
           '\nAnálise exploratória de estatísticas agregadas. Não é modelo de risco individual nem evidência causal.',
           '\n## Últimas referências\n','| Indicador (SGS) | Referência | Valor | Mudança mensal |','|---|---|---:|---:|']
    for code in (432,20539,20631,20716,21084,21083,29037,29034,433,24364):
        d=df[(df.code==code)&df.original.notna()]
        if d.empty: continue
        r=d.iloc[-1]; s=by_code[code]
        metric='diff_pp' if s['measure_type']=='rate' else 'mom_pct'
        change=r.get(metric,float('nan'))
        delta=f'{change:+.2f} '+('p.p.' if metric=='diff_pp' else '%') if pd.notna(change) else 'não calculada'
        lines.append(f"| {s['name']} ({code}) | {r.date:%Y-%m} | {r.original:,.2f} {s['unit']} | {delta} |")
    lines+=['\n## Crédito nominal e real\n']
    for code in (20539,20540,20541,20631):
        d=df[(df.code==code)&df.yoy_pct.notna()&df.real_yoy_pct.notna()]
        if d.empty: continue
        r=d.iloc[-1]
        lines.append(f"- {by_code[code]['name']} (SGS {code}), {r.date:%Y-%m}: variação nominal de {r.yoy_pct:.2f}% em 12 meses e real de {r.real_yoy_pct:.2f}%, com deflator encadeado do IPCA. A diferença mostra o efeito dos preços sobre o crescimento observado; não mede capacidade individual de pagamento.")
    lines+=['\n## PF e PJ na mesma referência\n']
    pair=pd.concat([series(21084).rename('pf'),series(21083).rename('pj')],axis=1).dropna()
    if len(pair):
        r=pair.iloc[-1]
        lines.append(f'Em {pair.index[-1]:%Y-%m}, a inadimplência total era {r.pf:.2f}% em PF e {r.pj:.2f}% em PJ: diferença de {r.pf-r.pj:+.2f} p.p. (SGS 21084/21083). O indicador mede parcela da carteira com atraso superior a 90 dias, não percentual de clientes. A composição das carteiras limita a comparação de risco.')
    lines+=['\n## Juros por modalidade\n']
    modalities=pd.concat([series(20741).rename('cheque'),series(20742).rename('pessoal')],axis=1).dropna()
    if len(modalities):
        r=modalities.iloc[-1]
        lines.append(f'Em {modalities.index[-1]:%Y-%m}, os juros de novas operações PF com recursos livres eram {r.cheque:.2f}% a.a. no cheque especial (20741) e {r.pessoal:.2f}% a.a. no crédito pessoal não consignado (20742). São unidades e segmentos comparáveis, mas contratos, garantias e prazos distintos. A diferença não prova cobrança excessiva nem risco equivalente.')
    lines+=['\n## Associações e defasagens\n','Defasagem k significa X(t−k) associado a Y(t). Transformações são calculadas no calendário mensal antes do alinhamento; pares ausentes são removidos sem encurtar o calendário. Nenhum p-valor é apresentado, pois não foi modelada a dependência temporal.\n']
    studies=[('selic_inadimplencia',432,'diff_pp',21084,'diff_pp'),('concessoes_inadimplencia',20633,'real_yoy_pct',21084,'diff12_pp'),('atividade_credito',24364,'yoy_pct',20539,'real_yoy_pct')]
    corr_frames=[]
    for title,xcode,xmetric,ycode,ymetric in studies:
        if xcode not in by_code or ycode not in by_code:
            lines.append(f'- {title}: não calculada, série ausente no snapshot.'); continue
        c=correlations(series(xcode,xmetric),series(ycode,ymetric),12)
        c['study']=title;c['x_code']=xcode;c['y_code']=ycode;c['x_metric']=xmetric;c['y_metric']=ymetric
        corr_frames.append(c)
        for lag in (0,6,12):
            r=c[c.lag==lag].iloc[0]
            lines.append(f'- {title}, SGS {xcode} ({xmetric}) → {ycode} ({ymetric}), k={lag}: r={r.correlation:.3f}, n={r.n}, período {r.start} a {r.end}.')
    lines+=['\nAs associações ajudam a selecionar hipóteses para monitoramento. Não estimam o efeito de elevar juros: há causalidade reversa, variáveis omitidas, sazonalidade residual e autocorrelação. Variações em 12 meses têm janelas sobrepostas. Não selecionamos automaticamente a maior correlação como “melhor defasagem”.',
      '\n## Limitações e uso\n',f"- Valores reais em R$ milhões de {manifest['price_base_month']}; concessões são fluxos mensais sem ajuste sazonal.",
      '- A Selic representa a meta ao final do mês concluído, não a taxa média mensal nem retorno acumulado.',
      '- As referências diferem entre indicadores. O fim da tabela não representa uma data de divulgação comum.',
      '- Mudanças contábeis e revisões históricas exigem interpretação, especialmente a partir de 2025; consulte docs/metodologia.md.',
      '- Próxima aplicação: acompanhar concessões reais, inadimplência e renda conjuntamente, segmentando modalidades antes de decidir políticas de crédito.',
      '\n## Fontes\n']
    lines += [f"- SGS {s['code']}: [{s['official_name']}]({s['source_url']})" for s in specs]
    (root/'reports').mkdir(exist_ok=True)
    (root/'reports/achados.md').write_text('\n'.join(lines)+'\n')
    if corr_frames: pd.concat(corr_frames,ignore_index=True).to_csv(root/'reports/correlations.csv',index=False)
    return str(root/'reports/achados.md')
