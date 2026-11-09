"""Composição de gráficos exportáveis preservando dados e unidades."""
from html import escape
import math
import textwrap

import plotly.graph_objects as go
import streamlit as st


def wrapped(value, width):
    return '<br>'.join(escape(line) for line in textwrap.wrap(str(value), width=width))


def prepare_figure(figure, title, source, options=None):
    options = options or {}
    fig = go.Figure(figure)
    dark = options.get('theme') == 'Escuro'
    bg, fg = ('#151515', '#eeeeee') if dark else ('#ffffff', '#24292e')
    width, height = options.get('width', 1200), options.get('height', 900)
    size = options.get('size', 16)
    if width not in (1000, 1200, 1600) or height not in (700, 900, 1100) or size not in (12, 16, 20):
        raise ValueError('Dimensões inválidas')
    count = sum(sum(v is not None and math.isfinite(float(v)) for v in trace.y) for trace in fig.data)
    labels = options.get('labels', 'Último valor')
    notice = ''
    if labels == 'Todos' and count > 60:
        labels = 'Último valor'
        notice = 'Acima de 60 pontos, os rótulos aparecem apenas no último valor de cada série para evitar sobreposição.'
    for i, trace in enumerate(fig.data):
        trace.visible = True
        trace.name = wrapped(trace.name or title, 30)
        color = options.get('colors', {}).get(i, trace.line.color or trace.marker.color or '#285c50')
        trace.line.color = color
        trace.marker.color = color
        trace.connectgaps = False
        mode = options.get('kind') or ('Pontos' if trace.mode == 'markers' else 'Linhas')
        trace.mode = 'markers' if mode == 'Pontos' else 'lines'
        valid = [j for j,v in enumerate(trace.y) if v is not None and math.isfinite(float(v))]
        trace.text = [format(float(v), ',.2f').replace(',', '_').replace('.', ',').replace('_','.') if j in valid and (labels == 'Todos' or labels == 'Último valor' and j == valid[-1]) else '' for j,v in enumerate(trace.y)]
        if labels != 'Sem rótulos': trace.mode += '+text'
        trace.textposition = 'top center'
        trace.textfont = dict(size=size, color=fg)
        trace.cliponaxis = False
        trace.showlegend = True
    if options.get('kind') == 'Barras':
        bars = []
        for trace in fig.data:
            values = trace.to_plotly_json()
            for name in ('mode', 'line', 'connectgaps'): values.pop(name, None)
            values.update(type='bar',textposition='outside')
            bars.append(go.Bar(values))
        fig = go.Figure(data=bars, layout=fig.layout)
    subtitle = options.get('subtitle', '')
    fig.update_layout(template='none', width=width, height=height, autosize=False,
                      title=dict(text=wrapped(options.get('title') or title, 65)+(('<br><sup>'+wrapped(subtitle,80)+'</sup>') if subtitle else ''),x=0.04,y=0.97,xanchor='left',yanchor='top',font=dict(size=size+6)),
                      font=dict(family='Arial, sans-serif',size=size,color=fg),paper_bgcolor=bg,plot_bgcolor=bg,
                      margin=dict(l=90,r=380 if 'yaxis2' in fig.layout else 330,t=170,b=140),showlegend=True,separators=',.',
                      barmode='group',legend=dict(orientation='v',x=1.03,y=1,xanchor='left',yanchor='top',font=dict(size=12)),
                      annotations=[dict(text=wrapped(source,100),xref='paper',yref='paper',x=0,y=0,yshift=-95,xanchor='left',yanchor='top',showarrow=False,align='left',font=dict(size=11))])
    fig.update_xaxes(autorange=True,range=None,showticklabels=True,automargin=True,gridcolor='#333' if dark else '#e5e5e5')
    fig.update_yaxes(autorange=True,range=None,showticklabels=True,automargin=True,gridcolor='#333' if dark else '#e5e5e5')
    return fig, notice


def exportable_chart(figure, *, export_title, export_source, key, **kwargs):
    """Controles nativos e download Plotly no navegador, sem servidor de imagens."""
    config = dict(kwargs.pop('config', {}) or {})
    config.update(displaylogo=False, modeBarButtonsToRemove=['toImage'])
    kwargs.pop('theme',None)
    st.plotly_chart(figure,key=key,theme=None,config=config,**kwargs)
    options = {}
    with st.expander('Personalizar e baixar gráfico'):
        enabled = st.toggle('Personalizar imagem', key=key+'-customize')
        if not enabled:
            return
        if enabled:
            options['title'] = st.text_input('Título', export_title[:180], max_chars=180, key=key+'-title')
            options['subtitle'] = st.text_input('Subtítulo', max_chars=160, key=key+'-subtitle')
            options['kind'] = st.selectbox('Tipo de gráfico', ['Pontos'] if all(t.mode == 'markers' for t in figure.data) else ['Linhas','Barras','Pontos'], key=key+'-kind')
            options['labels'] = st.selectbox('Rótulos de valores', ['Último valor','Sem rótulos','Todos'], key=key+'-labels')
            options['theme'] = st.selectbox('Fundo',['Claro','Escuro'],key=key+'-theme')
            options['width'] = st.selectbox('Largura (px)',[1200,1000,1600],key=key+'-width')
            options['height'] = st.selectbox('Altura (px)',[900,700,1100],key=key+'-height')
            options['size'] = st.selectbox('Tamanho do texto',[16,12,20],key=key+'-size')
            options['colors'] = {i:st.color_picker('Cor · '+(trace.name or export_title),trace.line.color or trace.marker.color or '#285c50', key=key+f'-color-{i}') for i,trace in enumerate(figure.data)}
        image_format = st.selectbox('Formato da imagem',['png','svg'],key=key+'-format')
        scale = st.selectbox('Resolução PNG',[1,2],format_func=lambda n:'Normal (1×)' if n==1 else 'Alta (2×)',key=key+'-scale')
        st.caption('Use o botão de câmera do gráfico para baixar a composição com título, fonte e unidades. A prévia se ajusta à tela; o arquivo usa as dimensões escolhidas. PNG guarda pixels e SVG mantém elementos vetoriais.')
    formatted, notice = prepare_figure(figure, export_title, export_source, options)
    if notice: st.caption(notice)
    config = {}
    config.update(displaylogo=False,toImageButtonOptions=dict(format=image_format,filename='observatorio-grafico',width=formatted.layout.width,height=formatted.layout.height,scale=scale if image_format=='png' else 1))
    kwargs.pop('theme',None)
    return st.plotly_chart(formatted,key=key+'-preview',theme=None,config=config,**kwargs)
