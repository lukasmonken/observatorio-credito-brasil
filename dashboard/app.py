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

st.set_page_config(page_title='Observatório de Crédito | Brasil', layout='wide')
st.markdown('<style>' + (Path(__file__).with_name('styles.css')).read_text() + '</style>', unsafe_allow_html=True)
st.title('Observatório de Crédito Brasil')
st.caption('Dados e indicadores do mercado de crédito brasileiro')

ACCENT = '#285c50'

def number(value, decimals=2, signed=False):
    return format(value, f'{"+" if signed else ""},.{decimals}f').replace(',', '_').replace('.', ',').replace('_', '.')

def style_chart(fig, height=340):
    fig.update_layout(
        template='plotly_white', height=height,
        font=dict(family='Arial, Helvetica, sans-serif', size=12, color='#24292e'),
        margin=dict(l=12, r=20, t=16, b=28),
        paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
        colorway=[ACCENT, '#66788a', '#8a7155'],
        separators=',.',
        legend=dict(orientation='h', y=-0.18, font=dict(size=11)),
        hoverlabel=dict(bgcolor='#ffffff', font_size=12, font_color='#202428'),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showline=True, linecolor='#dfe3e6',
                     tickfont=dict(size=11, color='#626970'), automargin=True)
    fig.update_yaxes(gridcolor='#edf0f2', zerolinecolor='#dfe3e6', zerolinewidth=1,
                     tickfont=dict(size=11, color='#626970'), automargin=True)
    return fig

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
st.sidebar.markdown('**OBSERVATÓRIO / BRASIL**')
page=st.sidebar.radio('Navegação',pages)
st.sidebar.divider()
st.sidebar.caption('FONTES OFICIAIS · BCB / SGS')
st.sidebar.write(f"{manifest['series']} séries · {number(manifest['rows'], 0)} registros mensais")
st.sidebar.caption(f"Coleta: {pd.Timestamp(manifest['as_of']):%d/%m/%Y}\n\nSnapshot: {manifest['snapshot_id'][:8]}")
if manifest['summary']['status']!='success':
    st.warning('Atualização parcial: consulte Fontes e qualidade. Algumas séries podem conter dados de execuções anteriores.')
attempt_path=ROOT/'data/processed/last_attempt.json'
if attempt_path.exists():
    attempt=json.loads(attempt_path.read_text())
    if attempt['status']=='failed' and attempt['run_id']!=manifest['snapshot_id']:
        st.error('A última tentativa de atualização falhou. Esta tela mantém o último snapshot válido; confira reports/runs.')
st.caption(f"Fonte: Banco Central do Brasil · Coleta: {pd.Timestamp(manifest['as_of']):%d/%m/%Y} · Histórico: {df.date.min():%m/%Y}–{df.date.max():%m/%Y}")
st.divider()
st.subheader(page)
st.caption('As referências variam por indicador. A Selic considera apenas meses concluídos.')

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
        st.markdown('#### ' + (title or names[code]))
        fig=px.line(d,x='date',y=metric,labels={'date':'Referência mensal',metric:unit_for(code,metric)},color_discrete_sequence=[ACCENT])
        fig.update_traces(connectgaps=False, line_width=2, hovertemplate='%{x|%m/%Y}<br>%{y:,.2f} ' + unit_for(code,metric) + '<extra></extra>')
        style_chart(fig)
        fig.update_layout(hovermode='x unified')
        st.plotly_chart(fig,width='stretch',theme=None,config={'displaylogo':False,'scrollZoom':False},key=f'{page}-{code}-{metric}-{title}')
        st.caption(f"Fonte: BCB/SGS {code} · {d.date.min():%m/%Y}–{d.date.max():%m/%Y} · {unit_for(code,metric)}")

def date_filter(data,key):
    a=data.date.min().date();b=data.date.max().date()
    selected=st.date_input('Período de análise',value=(a,b),min_value=a,max_value=b,key=key,format='DD/MM/YYYY',width=280)
    if len(selected)!=2:
        st.info('Selecione as duas datas do intervalo.');st.stop()
    return data[(data.date.dt.date>=selected[0])&(data.date.dt.date<=selected[1])]

if page=='Visão geral':
    cols=st.columns(4)
    for col,code,label in zip(cols,[432,21084,29037,29034],['Meta Selic','Inadimplência PF','Endividamento','Comprometimento de renda']):
        d=df[(df.code==code)&df.original.notna()]
        if d.empty: continue
        r=d.iloc[-1]
        delta=r.get('diff_pp')
        with col:
            st.metric(label,f"{number(r.original)} {by_code[code]['unit']}",delta=f'{number(delta, signed=True)} p.p. no mês' if pd.notna(delta) else None,delta_color='off')
            st.caption(f'Referência: {r.date:%m/%Y} · SGS {code}')
    st.divider()
    left,right=st.columns(2)
    with left: chart([20539], 'real_yoy_pct',title='Estoque de crédito · crescimento real em 12 meses')
    with right: chart([21084],title='Inadimplência · pessoas físicas')
    st.caption('Leitura conjunta: crescimento real do crédito, custo e atrasos. As séries mostram associações históricas; não estabelecem causalidade.')
elif page=='Juros e crédito':
    filter_segment,filter_indicators=st.columns([1,3])
    with filter_segment:
        segment=st.selectbox('Segmento',['Total','PF','PJ'])
    available=[s['code'] for s in specs if s['segment']==segment and s['classification'] in ('Juros','Spread','Estoque','Concessões')]
    with filter_indicators:
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
    filter_code,filter_metric=st.columns([3,2])
    with filter_code:
        code=st.selectbox('Indicador',list(names),format_func=lambda x:names[x],key='explorer_code')
    with filter_metric:
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
    st.caption('Compare dois indicadores e explore a associação entre referências mensais.')
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
        fig=px.scatter(pairs,x='x',y='y',labels={'x':'X · '+unit_for(xcode,xm),'y':'Y · '+unit_for(ycode,ym)},color_discrete_sequence=[ACCENT])
        style_chart(fig, height=400)
        fig.update_traces(marker=dict(size=6, opacity=0.75), hovertemplate='X: %{x:,.3f}<br>Y: %{y:,.3f}<extra></extra>')
        st.caption(f'X: {names[xcode]} · Y: {names[ycode]}')
        st.plotly_chart(fig,width='stretch',theme=None,config={'displaylogo':False,'scrollZoom':False})
    lagrows=[]
    for k in range(13):
        p=lag_pairs(x,y,k);p=p[(p.index>=data.date.min())&(p.index<=data.date.max())]
        lagrows.append({'Defasagem (meses)':k,'n':len(p),'r':p.x.corr(p.y) if len(p)>=12 and p.x.std()>0 and p.y.std()>0 else float('nan')})
    st.dataframe(pd.DataFrame(lagrows),hide_index=True,width='stretch')
    st.warning('Exploração, não causalidade. Tendência, sazonalidade, autocorrelação, janelas de 12 meses sobrepostas e quebras metodológicas afetam as correlações. Prefira mudanças ou crescimento real a níveis. Não há teste de significância ajustado para dependência temporal.')
else:
    st.write(f"Execução: {manifest['summary']['successes']} séries atualizadas; {manifest['summary']['failures']} falhas. Mês-base dos valores reais: {manifest['price_base_month']}.")
    st.dataframe(pd.DataFrame([dict(SGS=s['code'],Indicador=s['name'],Unidade=s['unit'],Frequência=s['frequency'],Início=s['coverage_observed']['start'],Fim=s['coverage_observed']['end'],Fonte=s['source_url']) for s in specs]),width='stretch',hide_index=True)
    st.subheader('Validações da execução')
    st.dataframe(quality,width='stretch',hide_index=True)
    with st.expander('Metodologia econômica',expanded=True):
        st.markdown((ROOT/'docs/metodologia.md').read_text())
    with st.expander('Catálogo completo e limitações'): st.json(specs)
