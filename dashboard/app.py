from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from observatorio.config import ROOT
from observatorio.snapshot import load_snapshot
from observatorio.transform import lag_pairs, correlations

st.set_page_config(page_title='Observatório de Crédito | Brasil',page_icon='◈',layout='wide')
st.markdown('''<style>
.block-container{padding-top:2rem;max-width:1450px}
h1{letter-spacing:-1.5px;font-weight:650!important}
[data-testid="stMetric"]{background:#182332;border:1px solid #2b394a;border-radius:12px;padding:18px}
[data-testid="stMetricLabel"]{font-size:.85rem}
</style>''',unsafe_allow_html=True)
st.caption('BRASIL  /  ECONOMIA & DADOS PÚBLICOS')
st.title('Observatório de Crédito')
st.markdown('Juros, atividade econômica e condições financeiras das famílias brasileiras.')

@st.cache_data(show_spinner=False)
def cached_snapshot(pointer):
    return load_snapshot()

try:
    with st.spinner('Carregando base tratada…'):
        pointer=(ROOT/'data/processed/latest.json').read_text()
        df,specs,quality,manifest=cached_snapshot(pointer)
except FileNotFoundError:
    st.info('Ainda não há base coletada. Execute `python -m observatorio collect --full` na pasta do projeto.')
    st.stop()
except Exception as exc:
    st.error('Não foi possível carregar o snapshot. Reexecute o pipeline e confira o relatório de execução.')
    with st.expander('Detalhe técnico'): st.code(str(exc))
    st.stop()

by_code={s['code']:s for s in specs}
names={s['code']:s['name'] for s in specs}
pages=['Visão geral','Juros e crédito','Famílias e inadimplência','Explorador de indicadores','Relações e defasagens','Fontes e qualidade']
page=st.sidebar.radio('Navegação',pages)
st.sidebar.divider()
st.sidebar.caption('FONTES OFICIAIS · BCB / SGS')
st.sidebar.write(f"{manifest['series']} séries • {manifest['rows']:,} registros mensais")
st.sidebar.caption(f"Corte da coleta: {manifest['as_of']}\n\nSnapshot: {manifest['snapshot_id'][:8]}")
if manifest['summary']['status']!='success':
    st.warning('Atualização parcial: consulte Fontes e qualidade. Algumas séries podem conter dados de execuções anteriores.')
attempt_path=ROOT/'data/processed/last_attempt.json'
if attempt_path.exists():
    attempt=json.loads(attempt_path.read_text())
    if attempt['status']=='failed' and attempt['run_id']!=manifest['snapshot_id']:
        st.error('A última tentativa de atualização falhou. Esta tela mantém o último snapshot válido; confira reports/runs.')
st.caption(f"Base processada em {manifest['created_at'][:10]}. Últimas referências variam por indicador. Apenas meses concluídos para Selic.")

labels={'original':'Valor original','ma3':'Média móvel de 3 meses','mom_pct':'Variação mensal (%)','yoy_pct':'Variação em 12 meses (%)','diff_pp':'Mudança mensal (p.p.)','diff12_pp':'Mudança em 12 meses (p.p.)','base100':'Índice base 100','real':'Valor real (R$ milhões)','real_yoy_pct':'Crescimento real em 12 meses (%)','inflation12':'IPCA acumulado em 12 meses (%)'}

def unit_for(code,metric):
    if metric in ('mom_pct','yoy_pct','real_yoy_pct','inflation12'): return '%'
    if metric in ('diff_pp','diff12_pp'): return 'p.p.'
    if metric=='base100': return 'índice base 100'
    if metric=='real': return f"R$ milhões de {manifest['price_base_month'][:7]}"
    return by_code[code]['unit']

def chart(codes,metric='original',data=None,title=None):
    data=df if data is None else data
    for code in codes:
        if code not in by_code:
            st.info(f'SGS {code}: série indisponível nesta execução.'); continue
        d=data[data.code==code].sort_values('date')
        if metric not in d or d[metric].dropna().empty:
            st.info(f'{names[code]}: sem valores disponíveis para essa transformação.'); continue
        fig=px.line(d,x='date',y=metric,title=title or names[code],labels={'date':'Referência mensal',metric:unit_for(code,metric)},color_discrete_sequence=['#64c9b4'])
        fig.update_traces(connectgaps=False)
        fig.update_layout(height=310,margin=dict(l=10,r=15,t=50,b=20),hovermode='x unified',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig,width='stretch',key=f'{page}-{code}-{metric}-{title}')
        st.caption(f"Fonte: BCB/SGS {code} · {d.date.min():%m/%Y}–{d.date.max():%m/%Y} · {unit_for(code,metric)}")

def date_filter(data,key):
    a=data.date.min().date();b=data.date.max().date()
    selected=st.date_input('Período de análise',value=(a,b),min_value=a,max_value=b,key=key)
    if len(selected)!=2:
        st.info('Selecione as duas datas do intervalo.');st.stop()
    return data[(data.date.dt.date>=selected[0])&(data.date.dt.date<=selected[1])]

if page=='Visão geral':
    st.subheader('O pulso do crédito brasileiro')
    cols=st.columns(4)
    for col,code,label in zip(cols,[432,21084,29037,29034],['Meta Selic','Inadimplência PF','Endividamento','Comprometimento de renda']):
        d=df[(df.code==code)&df.original.notna()]
        if d.empty: continue
        r=d.iloc[-1]
        delta=r.get('diff_pp')
        with col:
            st.metric(label,f"{r.original:.2f} {by_code[code]['unit']}",delta=f'{delta:+.2f} p.p. no mês' if pd.notna(delta) else None,delta_color='off')
            st.caption(f'Referência: {r.date:%m/%Y} · SGS {code}')
    left,right=st.columns(2)
    with left: chart([20539], 'real_yoy_pct',title='Estoque de crédito · crescimento real em 12 meses')
    with right: chart([21084],title='Inadimplência · pessoas físicas')
    st.info('Leitura conjunta: crescimento real do crédito, custo e atrasos. As séries mostram associações históricas; não estabelecem causalidade.')
elif page=='Juros e crédito':
    segment=st.selectbox('Segmento',['Total','PF','PJ'])
    available=[s['code'] for s in specs if s['segment']==segment and s['classification'] in ('Juros','Spread','Estoque','Concessões')]
    selection=st.multiselect('Indicadores',available,default=available[:3],format_func=lambda x:names[x])
    data=date_filter(df,'credit_dates')
    for c in selection: chart([c],data=data)
    st.caption('Modalidades PF com recursos livres podem ser comparadas em % a.a.; garantias, prazos e composição diferem. Agregados não devem ser somados às modalidades.')
elif page=='Famílias e inadimplência':
    data=date_filter(df,'family_dates')
    cols=st.columns(2)
    for i,c in enumerate([29037,29034,21084,21083]):
        with cols[i%2]: chart([c],data=data)
    st.warning('Inadimplência mede percentual da carteira, não de pessoas. Mudanças contábeis e de composição limitam comparações históricas; veja a metodologia.')
elif page=='Explorador de indicadores':
    code=st.selectbox('Indicador',list(names),format_func=lambda x:names[x],key='explorer_code')
    metric=st.selectbox('Transformação',by_code[code]['allowed_transforms'],format_func=lambda x:labels[x])
    data=date_filter(df[df.code==code],'explorer_dates')
    if metric=='base100':
        first=data.original.dropna()
        data=data.copy()
        data['base100']=data.original/first.iloc[0]*100 if len(first) and first.iloc[0]!=0 else float('nan')
        if len(first): st.caption(f'Base 100 recalculada no primeiro valor válido do período selecionado: {data.loc[first.index[0],"date"]:%m/%Y}.')
    chart([code],metric,data)
    if metric=='real': st.caption(f"Deflação pelo IPCA encadeado; mês-base {manifest['price_base_month']}. Sem inflação disponível, o valor real permanece ausente.")
    download=data[['code','date','name','unit','original',metric]].loc[:,lambda d:~d.columns.duplicated()].copy()
    download['transformed_unit']=unit_for(code,metric)
    st.download_button('Baixar dados filtrados · CSV',download.to_csv(index=False).encode('utf-8-sig'),file_name=f'sgs_{code}_{metric}.csv',mime='text/csv')
    with st.expander('Ver tabela'): st.dataframe(download,width='stretch',hide_index=True)
elif page=='Relações e defasagens':
    st.subheader('Uma hipótese, dois indicadores')
    c1,c2=st.columns(2)
    with c1: xcode=st.selectbox('X · indicador antecedente',list(names),format_func=lambda c:names[c],index=list(names).index(432) if 432 in names else 0)
    with c2: ycode=st.selectbox('Y · indicador posterior',list(names),format_func=lambda c:names[c],index=list(names).index(21084) if 21084 in names else 0)
    def permitted(c): return [m for m in by_code[c]['allowed_transforms'] if m in ('original','mom_pct','yoy_pct','diff_pp','diff12_pp','real_yoy_pct')]
    c1,c2=st.columns(2)
    with c1:
        opts=permitted(xcode);xm=st.selectbox('Transformação de X',opts,index=opts.index('diff_pp') if 'diff_pp' in opts else len(opts)-1,format_func=lambda x:labels[x])
    with c2:
        opts=permitted(ycode);ym=st.selectbox('Transformação de Y',opts,index=opts.index('diff_pp') if 'diff_pp' in opts else len(opts)-1,format_func=lambda x:labels[x])
    lag=st.slider('Defasagem de X em meses',0,24,6)
    data=date_filter(df,'relation_dates')
    x=df[df.code==xcode].set_index('date')[xm];y=df[df.code==ycode].set_index('date')[ym]
    pairs=lag_pairs(x,y,lag)
    pairs=pairs[(pairs.index>=data.date.min())&(pairs.index<=data.date.max())]
    r=pairs.x.corr(pairs.y) if len(pairs)>=12 and pairs.x.std()>0 and pairs.y.std()>0 else float('nan')
    st.write(f'X(t−{lag}) × Y(t) · n = {len(pairs)} pares mensais · correlação de Pearson = {r:.3f}' if pd.notna(r) else f'n = {len(pairs)} · amostra insuficiente ou série constante.')
    if len(pairs):
        st.caption(f'Período de Y: {pairs.index.min():%m/%Y} a {pairs.index.max():%m/%Y}. X pode anteceder o início desse período.')
        fig=px.scatter(pairs,x='x',y='y',labels={'x':names[xcode]+' · '+unit_for(xcode,xm),'y':names[ycode]+' · '+unit_for(ycode,ym)},color_discrete_sequence=['#64c9b4'])
        st.plotly_chart(fig,width='stretch')
    lagrows=[]
    for k in range(13):
        p=lag_pairs(x,y,k);p=p[(p.index>=data.date.min())&(p.index<=data.date.max())]
        lagrows.append({'Defasagem (meses)':k,'n':len(p),'r':p.x.corr(p.y) if len(p)>=12 and p.x.std()>0 and p.y.std()>0 else float('nan')})
    st.dataframe(pd.DataFrame(lagrows),hide_index=True,width='stretch')
    st.warning('Exploração, não causalidade. Tendência, sazonalidade, autocorrelação, janelas de 12 meses sobrepostas e quebras metodológicas afetam as correlações. Prefira mudanças ou crescimento real a níveis. Não há teste de significância ajustado para dependência temporal.')
else:
    st.subheader('Rastreabilidade e qualidade')
    st.write(f"Execução: {manifest['summary']['successes']} séries atualizadas; {manifest['summary']['failures']} falhas. Mês-base dos valores reais: {manifest['price_base_month']}.")
    st.dataframe(pd.DataFrame([dict(SGS=s['code'],Indicador=s['name'],Unidade=s['unit'],Frequência=s['frequency'],Início=s['coverage_observed']['start'],Fim=s['coverage_observed']['end'],Fonte=s['source_url']) for s in specs]),width='stretch',hide_index=True)
    st.subheader('Validações da execução')
    st.dataframe(quality,width='stretch',hide_index=True)
    with st.expander('Metodologia econômica',expanded=True):
        st.markdown((ROOT/'docs/metodologia.md').read_text())
    with st.expander('Catálogo completo e limitações'): st.json(specs)
