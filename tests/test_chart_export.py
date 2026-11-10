from copy import deepcopy

import plotly.graph_objects as go
import pytest

from observatorio.chart_export import prepare_figure


def example():
    return go.Figure(data=[go.Scatter(x=['2026-01-01','2026-02-01','2026-03-01'], y=[0,None,-1.25], name='Série A',mode='lines',yaxis='y2')],layout={'xaxis':{'title':'Referência'},'yaxis':{'title':'R$ milhões'},'yaxis2':{'title':'%','overlaying':'y','side':'right'}})


def test_export_preserves_data_and_secondary_axis_without_mutation():
    original = example()
    before = deepcopy(original.to_plotly_json())
    fig, notice = prepare_figure(original, 'Título', 'Fonte: BCB/SGS · Coleta: 2026-11-09', {'title':'Teste <script>', 'subtitle':'Ação & crédito','colors':{0:'#abcdef'},'labels':'Último valor'})
    assert original.to_plotly_json() == before
    assert list(fig.data[0].y) == [0,None,-1.25]
    assert fig.data[0].yaxis == 'y2'
    assert fig.layout.yaxis2.title.text == '%'
    assert fig.data[0].text == ('','','-1,25')
    assert not fig.data[0].connectgaps
    assert '&lt;script&gt;' in fig.layout.title.text
    assert 'Fonte: BCB/SGS' in fig.layout.annotations[0].text
    assert notice == ''


def test_many_labels_are_limited_and_bars_keep_values():
    original = go.Figure(go.Scatter(x=list(range(70)),y=list(range(70)),mode='lines'))
    fig, notice = prepare_figure(original,'Teste','Fonte',{'labels':'Todos','kind':'Barras'})
    assert notice
    assert fig.data[0].type == 'bar'
    assert list(fig.data[0].y) == list(range(70))
    assert sum(bool(t) for t in fig.data[0].text) == 1


def test_invalid_dimensions_rejected():
    with pytest.raises(ValueError): prepare_figure(example(),'Teste','Fonte',{'width':99999})


def test_streamlit_custom_export_configuration():
    from streamlit.testing.v1 import AppTest
    from observatorio.config import ROOT
    app = AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=30).run()
    app.sidebar.radio[0].set_value('Explorador de indicadores').run()
    app.toggle[0].set_value(True).run()
    assert not app.exception
    title = next(w for w in app.text_input if w.label == 'Título')
    title.set_value('Meu gráfico').run()
    assert not app.exception
    assert len(app.get('plotly_chart')) == 2
    assert any(w.label == 'Formato da imagem' for w in app.selectbox)
