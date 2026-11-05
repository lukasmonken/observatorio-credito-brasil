from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from html import escape
import streamlit as st
from observatorio.config import ROOT
from observatorio.bulletin import build_bulletin
from observatorio.excel import METRIC_FORMULAS as formulas, METRIC_LABELS as labels, build_excel
from observatorio.monitoring import collection_health, read_status, source_freshness
from observatorio.revisions import EVENT_LABELS, compare_collections, latest_changes, read_history
from observatorio.snapshot import load_snapshot
from observatorio.transform import lag_pairs, compare_base100

st.set_page_config(page_title="Observatório de Crédito | Brasil", layout="wide")
st.markdown(
    "<style>" + (Path(__file__).with_name("styles.css")).read_text() + "</style>",
    unsafe_allow_html=True,
)
st.title("Observatório de Crédito Brasil")
st.caption("Dados e indicadores do mercado de crédito brasileiro")

ACCENT = "#285c50"
SERIES_COLORS = [ACCENT, "#526f9d", "#a16b36", "#805b83", "#637445", "#9b5555"]


def number(value, decimals=2, signed=False):
    return (
        format(value, f"{'+' if signed else ''},.{decimals}f")
        .replace(",", "_")
        .replace(".", ",")
        .replace("_", ".")
    )


def style_chart(fig, height=340):
    fig.update_layout(
        template="plotly_white",
        height=height,
        font=dict(family="-apple-system, BlinkMacSystemFont, system-ui, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif", size=14, color="#24292e"),
        margin=dict(l=12, r=20, t=16, b=28),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        colorway=[ACCENT, "#66788a", "#8a7155"],
        separators=",.",
        legend=dict(orientation="h", y=-0.18, font=dict(size=11)),
        hoverlabel=dict(bgcolor="#ffffff", font_size=12, font_color="#202428"),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        showline=True,
        linecolor="#dfe3e6",
        tickfont=dict(size=11, color="#626970"),
        automargin=True,
    )
    fig.update_yaxes(
        gridcolor="#edf0f2",
        zerolinecolor="#dfe3e6",
        zerolinewidth=1,
        tickfont=dict(size=11, color="#626970"),
        automargin=True,
    )
    return fig


@st.cache_data(show_spinner=False)
def cached_snapshot(pointer, root):
    snapshot = load_snapshot(root, pointer=pointer)
    directory = root / json.loads(pointer)["path"]
    history, history_meta = read_history(directory, snapshot[3])
    return (*snapshot, history, history_meta)


try:
    with st.spinner("Carregando base tratada…"):
        pointer = (ROOT / "data/processed/latest.json").read_text()
        df, specs, quality, manifest, history, history_meta = cached_snapshot(pointer, ROOT)
except FileNotFoundError:
    st.info(
        "Ainda não há base coletada. Execute `python -m observatorio collect --full` na pasta do projeto."
    )
    st.stop()
except Exception:
    st.error(
        "Não foi possível carregar o snapshot. Reexecute o pipeline e confira o relatório de execução."
    )
    logging.getLogger(__name__).exception("Falha ao carregar snapshot")
    st.stop()

by_code = {s["code"]: s for s in specs}
names = {s["code"]: s["name"] for s in specs}
pages = [
    "Visão geral",
    "Juros e crédito",
    "Inflação detalhada",
    "Comparação em base 100",
    "Famílias e inadimplência",
    "Explorador de indicadores",
    "Relações e defasagens",
    "Histórico de revisões",
    "Dicionário e metodologia",
    "Fontes e qualidade",
]
st.sidebar.markdown("**OBSERVATÓRIO / BRASIL**")
page = st.sidebar.radio("Navegação", pages)
st.sidebar.divider()
st.sidebar.caption("FONTES OFICIAIS · BCB / SGS")
st.sidebar.write(
    f"{manifest['series']} séries · {number(manifest['rows'], 0)} registros mensais"
)
st.sidebar.caption(
    f"Coleta: {pd.Timestamp(manifest['as_of']):%d/%m/%Y}\n\nSnapshot: {manifest['snapshot_id'][:8]}"
)
if manifest["summary"]["status"] != "success":
    st.warning(
        "Atualização parcial: consulte Fontes e qualidade. Algumas séries podem conter dados de execuções anteriores."
    )
attempt_path = ROOT / "data/processed/last_attempt.json"
if attempt_path.exists():
    try:
        attempt = json.loads(attempt_path.read_text())
        if not isinstance(attempt, dict):
            raise ValueError("Estado de execução inválido")
    except (OSError, ValueError):
        logging.getLogger(__name__).exception("Falha ao ler estado da última coleta")
        st.warning(
            "O estado da última coleta está indisponível. Os dados abaixo pertencem ao snapshot validado."
        )
        attempt = {}
    if (
        attempt.get("status") == "failed"
        and attempt.get("run_id") != manifest["snapshot_id"]
    ):
        st.error(
            "A última tentativa de atualização falhou. Esta tela mantém o último snapshot válido; confira reports/runs."
        )
try:
    operational = read_status(ROOT)
    health, health_message = collection_health(operational, manifest)
except (OSError, ValueError, TypeError, KeyError):
    logging.getLogger(__name__).exception("Falha ao ler monitoramento operacional")
    operational = None
    health, health_message = (
        "unknown",
        "Monitoramento indisponível. Os dados exibidos pertencem ao snapshot validado.",
    )
if health in ("stale", "failed"):
    st.warning(health_message)
    st.caption(
        "Consulte Fontes e qualidade para separar falhas de coleta de defasagens da fonte."
    )

st.caption(
    f"Fonte: Banco Central do Brasil · Coleta: {pd.Timestamp(manifest['as_of']):%d/%m/%Y} · Histórico: {df.date.min():%m/%Y}–{df.date.max():%m/%Y}"
)
st.divider()
st.subheader(page)
st.caption(
    "As referências variam por indicador. A Selic considera apenas meses concluídos."
)



def unit_for(code, metric):
    if metric in ("mom_pct", "yoy_pct", "real_yoy_pct", "inflation12", "inflation_ytd"):
        return "%"
    if metric in ("diff_pp", "diff12_pp"):
        return "p.p."
    if metric == "base100":
        return "índice base 100"
    if metric == "real":
        return (
            f"R$ milhões de {manifest['price_base_month'][:7]}"
            if manifest.get("price_base_month")
            else "R$ milhões (base indisponível)"
        )
    return by_code[code]["unit"]


def chart(codes, metric="original", data=None, title=None, color=ACCENT):
    data = df if data is None else data
    for code in codes:
        if code not in by_code:
            st.info(f"SGS {code}: série indisponível nesta execução.")
            continue
        d = data[data.code == code].sort_values("date")
        if metric not in d or d[metric].dropna().empty:
            st.info(f"{names[code]}: sem valores disponíveis para essa transformação.")
            continue
        st.markdown("#### " + (title or names[code]))
        fig = px.line(
            d,
            x="date",
            y=metric,
            labels={"date": "Referência mensal", metric: unit_for(code, metric)},
            color_discrete_sequence=[color],
        )
        fig.update_traces(
            connectgaps=False,
            line_width=2,
            hovertemplate="%{x|%m/%Y}<br>%{y:,.2f} "
            + unit_for(code, metric)
            + "<extra></extra>",
        )
        style_chart(fig)
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(
            fig,
            width="stretch",
            theme=None,
            config={"displaylogo": False, "scrollZoom": False},
            key=f"{page}-{code}-{metric}-{title}",
        )
        st.caption(
            f"Fonte: BCB/SGS {code} · {d.date.min():%m/%Y}–{d.date.max():%m/%Y} · {unit_for(code, metric)}"
        )


def date_filter(data, key):
    a = data.date.min().date()
    b = data.date.max().date()
    selected = st.date_input(
        "Período de análise",
        value=(a, b),
        min_value=a,
        max_value=b,
        key=key,
        format="DD/MM/YYYY",
        width=280,
    )
    if len(selected) != 2:
        st.info("Selecione as duas datas do intervalo.")
        st.stop()
    filtered = data[
        (data.date.dt.date >= selected[0]) & (data.date.dt.date <= selected[1])
    ]
    if filtered.empty:
        st.info("Não há observações no intervalo selecionado. Amplie o período.")
        st.stop()
    return filtered


if page == "Visão geral":
    with st.expander("Boletim da coleta"):
        bulletin = build_bulletin(df, specs, manifest, history, history_meta)
        st.markdown(bulletin["markdown"])
        st.download_button("Baixar boletim · Markdown", bulletin["markdown"], f"boletim-{manifest['snapshot_id']}.md", "text/markdown", key="bulletin_md")
        st.download_button("Baixar boletim completo · JSON", json.dumps(bulletin, ensure_ascii=False, indent=2), f"boletim-{manifest['snapshot_id']}.json", "application/json", key="bulletin_json")
    cols = st.columns(4)
    for col, code, label in zip(
        cols,
        [432, 21084, 29037, 29034],
        ["Meta Selic", "Inadimplência PF", "Endividamento", "Comprometimento de renda"],
    ):
        d = df[(df.code == code) & df.original.notna()]
        if d.empty:
            continue
        r = d.iloc[-1]
        delta = r.get("diff_pp")
        with col:
            st.metric(
                label,
                f"{number(r.original)} {by_code[code]['unit']}",
                delta=f"{number(delta, signed=True)} p.p. no mês"
                if pd.notna(delta)
                else None,
                delta_color="off",
            )
            st.caption(f"Referência: {r.date:%m/%Y} · SGS {code}")
    changes = latest_changes(history, history_meta)
    with st.expander("O que mudou na última atualização", expanded=False):
        if changes is None:
            st.info("Resumo indisponível: esta base ainda não tem comparação com uma coleta anterior.")
        else:
            detected = pd.Timestamp(changes["detected_at"]).tz_convert("America/Sao_Paulo")
            st.caption(f"Comparação detectada em {detected:%d/%m/%Y %H:%M} · Brasília · {changes['series_count']} indicadores com mudanças")
            counts = changes["counts"]
            cols = st.columns(4)
            for col, kind, label in zip(cols, EVENT_LABELS, ["Valores revisados", "Novas referências", "Preenchimentos históricos", "Observações de séries incluídas"]):
                col.metric(label, counts[kind])
            if changes["events"].empty:
                st.info("Nenhuma mudança nos valores originais em relação à coleta anterior. A atualização foi verificada; não houve novos dados nem revisões detectadas.")
            else:
                st.dataframe(
                    changes["by_series"].rename(columns={
                        "code": "SGS", "name": "Indicador", "revision": "Valores revisados",
                        "new_observation": "Novas referências", "historical_fill": "Preenchimentos históricos",
                        "new_series": "Observações de séries incluídas",
                    }),
                    hide_index=True, width="stretch",
                )
                st.download_button(
                    "Baixar mudanças da última coleta · CSV",
                    changes["events"].to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"mudancas-{changes['snapshot_id']}.csv",
                    mime="text/csv", key="latest_changes_csv",
                )
            st.caption("Contagens de observações (série × mês), não de meses únicos. Novas referências avançam a série; preenchimentos completam lacunas antigas. Valores derivados não entram na comparação.")
            st.caption(f"Coleta anterior: {changes['previous_snapshot_id']} · Coleta atual: {changes['snapshot_id']}")
            st.caption("A data de detecção não é a data oficial de divulgação do Bacen. Consulte Histórico de revisões para filtrar eventos de todas as coletas.")
    st.divider()
    left, right = st.columns(2)
    with left:
        chart(
            [20539],
            "real_yoy_pct",
            title="Estoque de crédito · crescimento real em 12 meses",
        )
    with right:
        chart([21084], title="Inadimplência · pessoas físicas")
    st.caption(
        "Leitura conjunta: crescimento real do crédito, custo e atrasos. As séries mostram associações históricas; não estabelecem causalidade."
    )
elif page == "Inflação detalhada":
    inflation_specs = [s for s in specs if s['classification'] == 'Inflação']
    general = [s for s in inflation_specs if s.get('inflation_group') != 'Grupos do IPCA']
    groups = [s for s in inflation_specs if s.get('inflation_group') == 'Grupos do IPCA']
    st.caption('Compare índices e acompanhe os nove grupos do IPCA. Cada indicador mantém sua própria referência.')
    inflation_data = date_filter(df[df.code.isin([s['code'] for s in inflation_specs])], 'inflation_period')
    measures = [m for m in ['original', 'inflation_ytd', 'inflation12'] if any(m in s['allowed_transforms'] for s in general)]
    measure = st.selectbox('Medida', measures, format_func=lambda m: 'Variação mensal (%)' if m == 'original' else labels[m])
    for col, spec in zip(st.columns(len(general)), general):
        available = inflation_data[(inflation_data.code == spec['code']) & inflation_data.original.notna()]
        last = available.iloc[-1] if len(available) else None
        value = last.get(measure) if last is not None else None
        col.metric(spec.get('short_name', spec['name']), f'{number(value)} %' if pd.notna(value) else '—')
        col.caption(last.date.strftime('%m/%Y') if last is not None else 'Sem referência no recorte')
    st.caption('Última referência de cada índice no período. Acumulados ausentes aparecem como —, não como zero.')
    selected = st.multiselect('Índices para comparar', [s['code'] for s in general], default=[s['code'] for s in general], format_func=lambda c: by_code[c].get('short_name', names[c]))

    def inflation_plot(codes, title):
        rows = inflation_data[inflation_data.code.isin(codes)]
        if rows.empty:
            st.info('Selecione ao menos um indicador com dados no período.')
            return
        fig = px.line(rows, x='date', y=measure, color='name', labels={'date': 'Referência', measure: '%', 'name': 'Indicador'}, color_discrete_sequence=SERIES_COLORS)
        fig.update_traces(connectgaps=False)
        st.markdown('#### ' + title)
        st.plotly_chart(style_chart(fig), width='stretch', key=title)

    inflation_plot(selected, 'Evolução dos índices de inflação')
    exported = inflation_data[inflation_data.code.isin(selected)].copy()
    if not exported.empty:
        exported['source'] = exported.code.map(lambda c: by_code[c]['source'])
        exported['source_url'] = exported.code.map(lambda c: by_code[c]['source_url'])
        columns = ['date', 'code', 'name', 'original', *[m for m in ['inflation_ytd', 'inflation12'] if m in exported], 'unit', 'source', 'source_url', 'snapshot_id']
        st.download_button('Baixar índices · CSV', exported[columns].to_csv(index=False).encode('utf-8-sig'), 'inflacao_indices.csv', 'text/csv')
        with st.expander('Ver dados dos índices'):
            st.dataframe(exported[columns], hide_index=True)
    st.markdown('### Grupos do IPCA')
    st.caption('Variações dos grupos, não contribuições em pontos percentuais. Não some as taxas para reconstruir o IPCA.')
    group_data = inflation_data[inflation_data.code.isin([s['code'] for s in groups])]
    months = sorted(group_data.loc[group_data.original.notna(), 'date'].unique(), reverse=True)
    if len(months):
        reference = st.selectbox('Referência dos grupos', months, format_func=lambda d: pd.Timestamp(d).strftime('%m/%Y'))
        records = []
        for spec in groups:
            found = group_data[(group_data.code == spec['code']) & (group_data.date == reference)]
            row = found.iloc[0] if len(found) else {}
            records.append({'Referência': pd.Timestamp(reference).strftime('%Y-%m-%d'), 'Grupo': spec['modality'], 'No mês (%)': row.get('original'), 'No ano (%)': row.get('inflation_ytd'), 'Em 12 meses (%)': row.get('inflation12'), 'Fonte': spec['source'], 'URL': spec['source_url'], 'Coleta': manifest['snapshot_id']})
        group_table = pd.DataFrame(records)
        st.dataframe(group_table.iloc[:, :5], hide_index=True)
        st.download_button('Baixar grupos · CSV', group_table.to_csv(index=False).encode('utf-8-sig'), 'inflacao_grupos.csv', 'text/csv')
        selected_groups = st.multiselect('Grupos no gráfico', [s['code'] for s in groups], max_selections=6, default=[c for c in [1635, 1636, 1639] if c in by_code], format_func=lambda c: by_code[c]['modality'])
        inflation_plot(selected_groups, 'Evolução dos grupos selecionados')
    else:
        st.info('Sem dados dos grupos neste período ou catálogo ainda não atualizado.')
    with st.expander('Fontes e como interpretar'):
        st.write('IBGE: IPCA, IPCA-15, INPC e grupos. FGV IBRE: IGP-M e INCC-M. Distribuição: BCB/SGS.')
        st.write('IPCA-15 possui janela e cobertura próprias. INCC-M mede custos de construção e não equivale a INCC-DI ou INCC-10.')
        st.write('Acumulados compostos antes do filtro: janeiro até a referência, ou doze meses consecutivos. Exigem todos os meses; lacunas permanecem ausentes. Arredondamentos podem gerar diferenças frente ao acumulado oficial.')
        for spec in inflation_specs:
            st.markdown(f"[{spec.get('short_name', spec['name'])}]({spec['source_url']})")

elif page == "Juros e crédito":
    filter_segment, filter_indicators = st.columns([1, 3])
    with filter_segment:
        segment = st.selectbox("Segmento", ["Total", "PF", "PJ"])
    available = [
        s["code"]
        for s in specs
        if s["segment"] == segment
        and s["classification"] in ("Juros", "Spread", "Estoque", "Concessões")
    ]
    with filter_indicators:
        selection = st.multiselect(
            "Indicadores",
            available,
            default=available[:3],
            format_func=lambda x: names[x],
            key=f"credit_indicators_{segment}",
        )
    data = date_filter(df, "credit_dates")
    colors = {c: SERIES_COLORS[available.index(c) % len(SERIES_COLORS)] for c in available}
    if selection:
        st.markdown(
            " · ".join(
                f'<span style="color:{colors[c]};font-weight:600">━ {escape(names[c])}</span>'
                for c in selection
            ), unsafe_allow_html=True,
        )
    view = st.radio("Visualização", ["Gráficos separados", "Comparar no mesmo gráfico"], horizontal=True, key="credit_view")
    if not selection:
        st.info("Selecione ao menos um indicador para exibir os gráficos.")
    elif view == "Gráficos separados":
        for c in selection:
            chart([c], data=data, color=colors[c])
    else:
        units = list(dict.fromkeys(by_code[c]["unit"] for c in selection))
        if len(units) > 2:
            st.info("Para manter os eixos legíveis, selecione indicadores com até duas unidades diferentes ou use os gráficos separados.")
        else:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            for c in selection:
                values = data.loc[data.code == c].sort_values("date")
                unit = by_code[c]["unit"]
                fig.add_trace(go.Scatter(
                    x=values.date, y=values.original, name=names[c],
                    mode="lines", connectgaps=False,
                    line={"color": colors[c], "width": 2},
                    hovertemplate="%{x|%m/%Y}<br>%{y:,.2f} " + unit + "<extra>%{fullData.name}</extra>",
                ), secondary_y=unit != units[0])
            style_chart(fig, height=440)
            fig.update_yaxes(title_text=units[0], secondary_y=False)
            fig.update_yaxes(title_text=units[1] if len(units) == 2 else None,
                             visible=len(units) == 2, showgrid=False, secondary_y=True)
            fig.update_layout(hovermode="x unified", legend={"itemclick": "toggle", "itemdoubleclick": "toggleothers"})
            st.plotly_chart(fig, width="stretch", theme=None, key="credit_combined",
                            config={"displaylogo": False, "scrollZoom": False})
            st.caption("Valores originais, sem normalização. Eixos com escalas independentes: cruzamentos e inclinações entre unidades diferentes não indicam igualdade de valores. Clique na legenda para ocultar ou reexibir uma série.")
    st.caption(
        "Modalidades PF com recursos livres podem ser comparadas em % a.a.; garantias, prazos e composição diferem. Agregados não devem ser somados às modalidades."
    )
elif page == "Comparação em base 100":
    available = [s['code'] for s in specs if s['measure_type'] != 'variation']
    selection = st.multiselect("Indicadores", available, default=[20539, 20631, 20714],
                               format_func=lambda c: names[c], max_selections=6, key="comparison_codes")
    data = date_filter(df, "comparison_dates")
    if len(selection) < 2:
        st.info("Selecione de dois a seis indicadores.")
    else:
        compared, base = compare_base100(data, selection)
        if base is None:
            st.info("Não há mês comum com valores válidos e diferentes de zero. Ajuste o período ou os indicadores.")
        else:
            st.caption(f"Mês-base comum: {base:%m/%Y} = 100. Primeiro mês do recorte com valores válidos e diferentes de zero em todas as séries.")
            fig = go.Figure()
            for index, code in enumerate(selection):
                values = compared.loc[compared.code == code]
                fig.add_trace(go.Scatter(x=values.date, y=values.base100, name=names[code], mode="lines",
                                        connectgaps=False, line=dict(color=SERIES_COLORS[index], width=2),
                                        hovertemplate="%{x|%m/%Y}<br>%{y:,.2f} · base 100<extra>%{fullData.name}</extra>"))
            style_chart(fig, height=440)
            fig.update_yaxes(title_text="Índice base 100")
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, width="stretch", theme=None, key="comparison_base100")
            st.caption("Índice = valor original ÷ valor no mês-base × 100. 120 significa alta de 20%, não 20 p.p. A normalização não corrige inflação, sazonalidade ou diferenças de conceito. Lacunas permanecem vazias e as séries podem terminar em meses diferentes.")
            if compared.loc[compared.date == base, 'original'].lt(0).any():
                st.warning("Há denominador negativo no mês-base: a direção do índice se inverte em relação ao valor original.")
            exported = compared[['code', 'date', 'original', 'base100']].copy()
            exported['name'] = exported.code.map(names)
            exported['original_unit'] = exported.code.map(lambda c: by_code[c]['unit'])
            exported['base_month'] = base.strftime('%Y-%m-%d')
            exported['snapshot_id'] = manifest['snapshot_id']
            st.download_button("Baixar comparação · CSV", exported.to_csv(index=False).encode('utf-8-sig'),
                               'comparacao_base100.csv', 'text/csv', key="comparison_csv")
            with st.expander("Ver valores comparados"):
                st.dataframe(exported, hide_index=True, width="stretch")
    st.caption("Taxas mensais de inflação não são indexadas nesta comparação; consulte seus acumulados no explorador.")
elif page == "Famílias e inadimplência":
    data = date_filter(df, "family_dates")
    cols = st.columns(2)
    for i, c in enumerate([29037, 29034, 21084, 21083]):
        with cols[i % 2]:
            chart([c], data=data)
    st.warning(
        "Inadimplência mede percentual da carteira, não de pessoas. Mudanças contábeis e de composição limitam comparações históricas; veja a metodologia."
    )
elif page == "Explorador de indicadores":
    filter_code, filter_metric = st.columns([3, 2])
    with filter_code:
        code = st.selectbox(
            "Indicador",
            list(names),
            format_func=lambda x: names[x],
            key="explorer_code",
        )
    with filter_metric:
        metric = st.selectbox(
            "Transformação",
            by_code[code]["allowed_transforms"],
            format_func=lambda x: labels[x],
        )
    data = date_filter(df[df.code == code], "explorer_dates")
    if metric == "base100":
        first = data.original.dropna()
        data = data.copy()
        data["base100"] = (
            data.original / first.iloc[0] * 100
            if len(first) and first.iloc[0] != 0
            else float("nan")
        )
        if len(first):
            st.caption(
                f"Base 100 recalculada no primeiro valor válido do período selecionado: {data.loc[first.index[0], 'date']:%m/%Y}."
            )
    chart([code], metric, data)
    if metric == "real":
        st.caption(
            f"Deflação pelo IPCA encadeado; mês-base {manifest['price_base_month']}. Sem inflação disponível, o valor real permanece ausente."
        )
    download = (
        data[["code", "date", "name", "unit", "original", metric]]
        .loc[:, lambda d: ~d.columns.duplicated()]
        .copy()
    )
    download["transformed_unit"] = unit_for(code, metric)
    st.download_button(
        "Baixar dados filtrados · CSV",
        download.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"sgs_{code}_{metric}.csv",
        mime="text/csv",
    )
    excel_data = build_excel(
        data, by_code[code], manifest, metric, unit_for(code, metric),
        st.session_state["explorer_dates"], (ROOT / "docs/metodologia.md").read_text(),
    )
    st.download_button(
        "Baixar dados filtrados · Excel", excel_data,
        file_name=f"sgs_{code}_{metric}_{manifest['snapshot_id'][:8]}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="explorer_excel",
    )
    st.caption("O Excel inclui o recorte exibido, unidades, fonte, metodologia e identificação da coleta.")
    with st.expander("Ver tabela"):
        st.dataframe(download, width="stretch", hide_index=True)
elif page == "Relações e defasagens":
    st.caption(
        "Compare dois indicadores e explore a associação entre referências mensais."
    )
    c1, c2 = st.columns(2)
    with c1:
        xcode = st.selectbox(
            "X · indicador antecedente",
            list(names),
            format_func=lambda c: names[c],
            index=list(names).index(432) if 432 in names else 0,
        )
    with c2:
        ycode = st.selectbox(
            "Y · indicador posterior",
            list(names),
            format_func=lambda c: names[c],
            index=list(names).index(21084) if 21084 in names else 0,
        )

    def permitted(c):
        return [
            m
            for m in by_code[c]["allowed_transforms"]
            if m
            in (
                "original",
                "mom_pct",
                "yoy_pct",
                "diff_pp",
                "diff12_pp",
                "real_yoy_pct",
            )
        ]

    c1, c2 = st.columns(2)
    with c1:
        opts = permitted(xcode)
        xm = st.selectbox(
            "Transformação de X",
            opts,
            index=opts.index("diff_pp") if "diff_pp" in opts else len(opts) - 1,
            format_func=lambda x: labels[x],
        )
    with c2:
        opts = permitted(ycode)
        ym = st.selectbox(
            "Transformação de Y",
            opts,
            index=opts.index("diff_pp") if "diff_pp" in opts else len(opts) - 1,
            format_func=lambda x: labels[x],
        )
    lag = st.slider("Defasagem de X em meses", 0, 24, 6)
    data = date_filter(df, "relation_dates")
    x = df[df.code == xcode].set_index("date")[xm]
    y = df[df.code == ycode].set_index("date")[ym]
    pairs = lag_pairs(x, y, lag)
    pairs = pairs[(pairs.index >= data.date.min()) & (pairs.index <= data.date.max())]
    r = (
        pairs.x.corr(pairs.y)
        if len(pairs) >= 12 and pairs.x.std() > 0 and pairs.y.std() > 0
        else float("nan")
    )
    st.write(
        f"X(t−{lag}) × Y(t) · n = {len(pairs)} pares mensais · correlação de Pearson = {r:.3f}"
        if pd.notna(r)
        else f"n = {len(pairs)} · amostra insuficiente ou série constante."
    )
    if len(pairs):
        st.caption(
            f"Período de Y: {pairs.index.min():%m/%Y} a {pairs.index.max():%m/%Y}. X pode anteceder o início desse período."
        )
        fig = px.scatter(
            pairs,
            x="x",
            y="y",
            labels={
                "x": "X · " + unit_for(xcode, xm),
                "y": "Y · " + unit_for(ycode, ym),
            },
            color_discrete_sequence=[ACCENT],
        )
        style_chart(fig, height=400)
        fig.update_traces(
            marker=dict(size=6, opacity=0.75),
            hovertemplate="X: %{x:,.3f}<br>Y: %{y:,.3f}<extra></extra>",
        )
        st.caption(f"X: {names[xcode]} · Y: {names[ycode]}")
        st.plotly_chart(
            fig,
            width="stretch",
            theme=None,
            config={"displaylogo": False, "scrollZoom": False},
        )
    lagrows = []
    for k in range(13):
        p = lag_pairs(x, y, k)
        p = p[(p.index >= data.date.min()) & (p.index <= data.date.max())]
        lagrows.append(
            {
                "Defasagem (meses)": k,
                "n": len(p),
                "r": p.x.corr(p.y)
                if len(p) >= 12 and p.x.std() > 0 and p.y.std() > 0
                else float("nan"),
            }
        )
    st.dataframe(pd.DataFrame(lagrows), hide_index=True, width="stretch")
    st.warning(
        "Exploração, não causalidade. Tendência, sazonalidade, autocorrelação, janelas de 12 meses sobrepostas e quebras metodológicas afetam as correlações. Prefira mudanças ou crescimento real a níveis. Não há teste de significância ajustado para dependência temporal."
    )
elif page == "Histórico de revisões":
    st.caption(
        "Compara valores originais entre coletas publicadas. A data de detecção não é a data oficial de divulgação ou revisão pelo Bacen."
    )
    if history_meta is None:
        st.info(
            "O histórico entre coletas começa na próxima atualização validada. Esta base ainda não contém comparações registradas."
        )
    else:
        comparison = history_meta["comparisons"][-1]
        detected = pd.Timestamp(comparison["detected_at"]).tz_convert(
            "America/Sao_Paulo"
        )
        st.write(f"Última comparação: {detected:%d/%m/%Y %H:%M} · Brasília")
        metrics = st.columns(3)
        metrics[0].metric("Valores revisados", comparison["counts"]["revision"])
        metrics[1].metric("Novas referências", comparison["counts"]["new_observation"])
        metrics[2].metric(
            "Preenchimentos históricos", comparison["counts"]["historical_fill"]
        )
        if comparison["counts"]["new_series"]:
            st.info(
                f"{comparison['counts']['new_series']} observações de séries incluídas nesta comparação."
            )
        st.caption(
            f"Snapshots: {comparison['previous_snapshot_id']} → {comparison['snapshot_id']}"
        )
        st.caption(
            f"Histórico acompanhado desde a base {history_meta['baseline_snapshot_id']} ({pd.Timestamp(history_meta['baseline_created_at']):%d/%m/%Y}). Comparações registradas: {len(history_meta['comparisons'])}."
        )
        if sum(comparison["counts"].values()) == 0:
            st.info(
                "Nenhuma mudança nos valores originais na última comparação. Isso não apaga eventos de coletas anteriores."
            )
        if history.empty:
            st.info(
                "Ainda não foram detectadas revisões, novas referências ou preenchimentos históricos desde o início do acompanhamento."
            )
        else:
            st.subheader("Eventos registrados")
            left, right = st.columns(2)
            with left:
                codes = st.multiselect(
                    "Séries",
                    sorted(history.code.unique(), key=int),
                    default=sorted(history.code.unique(), key=int),
                    format_func=lambda code: (
                        f"SGS {code} · {names.get(int(code), code)}"
                    ),
                )
            with right:
                kinds = st.multiselect(
                    "Tipo de mudança",
                    list(EVENT_LABELS),
                    default=list(EVENT_LABELS),
                    format_func=lambda kind: EVENT_LABELS[kind],
                )
            detected_dates = (
                pd.to_datetime(history.detected_at, utc=True)
                .dt.tz_convert("America/Sao_Paulo")
                .dt.date
            )
            period = st.date_input(
                "Período de detecção",
                value=(detected_dates.min(), detected_dates.max()),
                min_value=detected_dates.min(),
                max_value=detected_dates.max(),
                format="DD/MM/YYYY",
            )
            if len(period) != 2:
                st.info("Selecione as duas datas do período de detecção.")
            else:
                filtered = history[
                    history.code.isin(codes)
                    & history.event_type.isin(kinds)
                    & detected_dates.between(period[0], period[1])
                ].sort_values(["detected_at", "reference_date"], ascending=False)
                if filtered.empty:
                    st.info("Nenhum evento corresponde aos filtros selecionados.")
                else:
                    view = filtered.copy()
                    view["event_type"] = view.event_type.map(EVENT_LABELS)
                    view["detected_at"] = (
                        pd.to_datetime(view.detected_at, utc=True)
                        .dt.tz_convert("America/Sao_Paulo")
                        .dt.strftime("%d/%m/%Y %H:%M")
                    )
                    view["reference_date"] = pd.to_datetime(
                        view.reference_date
                    ).dt.strftime("%m/%Y")
                    for column in ("old_value", "new_value", "difference"):
                        view[column] = pd.to_numeric(view[column], errors="coerce")
                    st.dataframe(
                        view.rename(
                            columns={
                                "code": "SGS",
                                "name": "Indicador",
                                "event_type": "Mudança",
                                "reference_date": "Referência",
                                "old_value": "Valor anterior",
                                "new_value": "Valor novo",
                                "difference": "Diferença",
                                "unit": "Unidade",
                                "difference_unit": "Unidade da diferença",
                                "detected_at": "Detectado em · Brasília",
                                "previous_snapshot_id": "Snapshot anterior",
                                "snapshot_id": "Snapshot novo",
                                "event_id": "ID do evento",
                            }
                        ),
                        hide_index=True,
                        width="stretch",
                        column_order=[
                            "Detectado em · Brasília",
                            "SGS",
                            "Indicador",
                            "Mudança",
                            "Referência",
                            "Valor anterior",
                            "Valor novo",
                            "Diferença",
                            "Unidade",
                            "Unidade da diferença",
                            "Snapshot anterior",
                            "Snapshot novo",
                        ],
                    )
                    st.download_button(
                        "Baixar histórico filtrado · CSV",
                        filtered.to_csv(index=False).encode("utf-8-sig"),
                        "historico_revisoes.csv",
                        "text/csv",
                    )
            st.caption(
                "Diferença = valor novo − valor anterior. Para taxas, a diferença é em pontos percentuais; nas demais séries, usa a unidade original. Novas observações não têm valor anterior nem diferença. O CSV preserva os valores decimais e os identificadores completos."
            )
        with st.expander("Comparações entre coletas, inclusive sem mudanças"):
            comparisons = pd.json_normalize(history_meta["comparisons"])
            st.dataframe(comparisons, hide_index=True, width="stretch")
            st.download_button(
                "Baixar registro de comparações · CSV",
                comparisons.to_csv(index=False).encode("utf-8-sig"),
                "comparacoes_coletas.csv",
                "text/csv",
            )
        with st.expander("Comparar duas coletas"):
            collection_dates = {
                history_meta["baseline_snapshot_id"]: history_meta["baseline_created_at"],
                **{item["snapshot_id"]: item["detected_at"] for item in history_meta["comparisons"]},
            }
            identifiers = list(collection_dates)
            def collection_label(identifier):
                moment = pd.Timestamp(collection_dates[identifier]).tz_convert("America/Sao_Paulo")
                return f"{moment:%d/%m/%Y %H:%M} · {identifier[:8]}"
            st.caption("Diferença líquida dos valores originais entre duas bases. Revisões intermediárias que se anulam não aparecem aqui. Horários de registro em Brasília.")
            with st.form("compare_collections_form"):
                left, right = st.columns(2)
                earlier = left.selectbox("Coleta inicial", identifiers[:-1], index=len(identifiers) - 2, format_func=collection_label, key="comparison_earlier")
                later = right.selectbox("Coleta final", identifiers[1:], index=len(identifiers) - 2, format_func=collection_label, key="comparison_later")
                compare_requested = st.form_submit_button("Comparar coletas", key="compare_collections_submit")
            if compare_requested:
                if identifiers.index(earlier) >= identifiers.index(later):
                    st.info("Escolha uma coleta inicial anterior à coleta final.")
                else:
                    try:
                        compared = compare_collections(history, history_meta, earlier, later)
                    except ValueError:
                        logging.getLogger(__name__).exception("Falha ao comparar coletas")
                        st.error("Não foi possível validar a comparação. Confira o histórico de revisões.")
                    else:
                        counts = st.columns(4)
                        counts[0].metric("Observações com diferença líquida", len(compared))
                        counts[1].metric("Indicadores afetados", compared.code.nunique())
                        counts[2].metric("Revisões líquidas", int(compared.event_type.eq("revision").sum()))
                        counts[3].metric("Observações adicionadas", int(compared.event_type.eq("added_observation").sum()))
                        if compared.empty:
                            st.info("Nenhuma diferença nos valores originais entre as duas coletas. Podem existir revisões intermediárias que se anularam.")
                        else:
                            view = compared.copy()
                            view["event_type"] = view.event_type.map({"revision": "Revisão líquida", "added_observation": "Observação adicionada"})
                            view["reference_date"] = pd.to_datetime(view.reference_date).dt.strftime("%m/%Y")
                            st.dataframe(view.rename(columns={
                                "code": "SGS", "name": "Indicador", "reference_date": "Referência",
                                "event_type": "Mudança", "old_value": "Valor inicial", "new_value": "Valor final",
                                "difference": "Diferença líquida", "unit": "Unidade", "difference_unit": "Unidade da diferença",
                                "previous_snapshot_id": "Coleta inicial", "snapshot_id": "Coleta final",
                            }), hide_index=True, width="stretch")
                        st.download_button("Baixar comparação · CSV", compared.to_csv(index=False).encode("utf-8-sig"),
                                           file_name=f"comparacao-{earlier}-{later}.csv", mime="text/csv", key="comparison_csv")
                        st.caption(f"Coleta inicial: {earlier} · Coleta final: {later}")
                        st.caption("Diferença = valor final − valor inicial. Taxas em p.p.; demais valores na unidade original. Novas observações não têm valor inicial. Adições incluem novos meses, lacunas preenchidas e séries incluídas. A comparação não altera a base publicada.")
elif page == "Dicionário e metodologia":
    st.caption("Fichas do catálogo associado à base publicada. Nenhum filtro altera os dados de origem.")
    query = st.text_input("Buscar por nome ou código SGS", key="dictionary_search").strip().casefold()
    matches = [s for s in specs if query in f"{s['code']} {s['name']} {s.get('official_name', '')}".casefold()]
    if not matches:
        st.info("Nenhum indicador encontrado. Tente outro nome ou código SGS.")
    else:
        code = st.selectbox(
            "Indicador", [s["code"] for s in matches],
            format_func=lambda c: f"{c} · {names[c]}", key="dictionary_code",
        )
        spec = by_code[code]
        st.markdown("#### " + spec.get("official_name", spec["name"]))
        st.write(spec.get("description") or "Conceito não informado no catálogo.")
        observed = df.loc[(df.code == code) & df.original.notna(), "date"]
        period = f"{observed.min():%m/%Y} – {observed.max():%m/%Y}" if not observed.empty else "Sem valores válidos"
        st.dataframe(pd.DataFrame([
            {"Campo": "Código SGS", "Informação": str(code)},
            {"Campo": "Unidade no painel", "Informação": spec["unit"]},
            {"Campo": "Unidade nos metadados oficiais", "Informação": spec.get("official_unit", "Não informada")},
            {"Campo": "Periodicidade de origem", "Informação": {"D": "Diária", "M": "Mensal"}.get(spec["frequency"], spec["frequency"])},
            {"Campo": "Periodicidade no painel", "Informação": "Mensal"},
            {"Campo": "Tratamento temporal", "Informação": "Última observação de cada mês concluído; não é média mensal." if spec["frequency"] == "D" else "Referência mensal preservada, sem somar ou reponderar."},
            {"Campo": "Categoria", "Informação": spec["classification"]},
            {"Campo": "Segmento", "Informação": spec["segment"]},
            {"Campo": "Modalidade", "Informação": spec.get("modality", "Não informada")},
            {"Campo": "Recursos", "Informação": spec.get("resources", "Não informado")},
            {"Campo": "Período com valores na base", "Informação": period},
            {"Campo": "Metadados conferidos em", "Informação": spec.get("metadata_verified_at", "Não informado")},
        ]), hide_index=True, width="stretch")
        st.markdown(f"[Consultar fonte oficial e metadados]({spec['source_url']})")
        st.caption("Fonte: " + by_code[code].get("source", "Banco Central do Brasil / SGS"))
        st.markdown("#### Como interpretar")
        interpretations = {
            "stock": "Mede o saldo da carteira em uma data. Aumento do saldo não equivale ao volume de novos empréstimos do mês.",
            "flow": "Mede novas operações contratadas no mês. Não representa o saldo em aberto. Dias úteis e sazonalidade afetam comparações mensais.",
            "rate": "Leia o nível na unidade indicada. Mudanças são expressas em pontos percentuais: de 10% para 12% significa +2 p.p.",
            "index": "Mede evolução relativa da atividade. Não representa PIB em reais. A série IBC-Br selecionada já tem ajuste sazonal.",
            "variation": "O IPCA original é a inflação do mês. O acumulado em 12 meses compõe os fatores mensais; não soma as taxas.",
        }
        st.write(interpretations.get(spec.get("measure_type"), "Consulte o conceito oficial e a unidade da série."))
        st.markdown("#### Transformações disponíveis")
        st.dataframe(pd.DataFrame([
            {"Transformação": labels[m], "Unidade": unit_for(code, m), "Cálculo e leitura": formulas[m]}
            for m in spec["allowed_transforms"]
        ]), hide_index=True, width="stretch")
        st.markdown("#### Limitações e comparabilidade")
        for limitation in spec.get("limitations", []):
            st.write("• " + limitation)
        st.caption("A observação do catálogo sobre reconsulta de 18 meses se refere ao modo incremental. O job diário atual faz coleta completa do período configurado. A data da coleta não é a data de publicação original do Bacen.")
        st.caption(f"Snapshot: {manifest['snapshot_id']} · Mês-base dos valores reais: {manifest.get('price_base_month') or 'Indisponível'}")
    with st.expander("Metodologia econômica completa", expanded=False):
        st.markdown((ROOT / "docs/metodologia.md").read_text())
    st.download_button(
        "Baixar catálogo da base publicada · JSON",
        json.dumps(specs, ensure_ascii=False, indent=2).encode("utf-8"),
        "dicionario_indicadores.json", "application/json",
    )
else:
    st.subheader("Monitoramento da atualização")
    st.write(health_message)

    def local_time(value):
        return (
            pd.Timestamp(value)
            .tz_convert("America/Sao_Paulo")
            .strftime("%d/%m/%Y %H:%M")
            if value
            else "Não registrado"
        )

    monitor = operational or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("Última tentativa · Brasília", local_time(monitor.get("started_at")))
    c2.metric(
        "Último sucesso · Brasília",
        local_time(monitor.get("last_success_at") or manifest["created_at"]),
    )
    duration = monitor.get("duration_seconds")
    c3.metric(
        "Duração da tentativa",
        f"{duration} s" if duration is not None else "Não registrada",
    )
    if monitor.get("failed_series"):
        st.warning(
            "Séries com falha na última tentativa: "
            + ", ".join(str(code) for code in monitor["failed_series"])
        )
    if monitor.get("stage"):
        st.caption("Etapa registrada: " + monitor["stage"])
    st.caption(
        "Coleta diária prevista às 19h17 de Brasília. Alerta operacional após 30 horas sem sucesso. A duração inclui preparação, testes e coleta, até a validação; não inclui o envio ao GitHub."
    )
    st.markdown(
        "[Consultar execuções e diagnóstico no GitHub Actions](https://github.com/lukasmonken/observatorio-credito-brasil/actions)"
    )
    st.subheader("Atualidade das séries")
    freshness = source_freshness(
        df, specs, datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    )
    st.dataframe(pd.DataFrame(freshness), hide_index=True, width="stretch")
    st.caption(
        "Dias desde o início do mês de referência. Limites específicos do catálogo são critérios operacionais, não prazos oficiais de divulgação. Uma coleta bem-sucedida pode retornar a mesma referência; isso não comprova falha nem atraso do Bacen."
    )
    st.subheader("Base publicada")
    st.write(
        f"Execução: {manifest['summary']['successes']} séries atualizadas; {manifest['summary']['failures']} falhas. Mês-base dos valores reais: {manifest['price_base_month']}."
    )
    st.dataframe(
        pd.DataFrame(
            [
                dict(
                    SGS=s["code"],
                    Indicador=s["name"],
                    Unidade=s["unit"],
                    Frequência=s["frequency"],
                    Início=s["coverage_observed"]["start"],
                    Fim=s["coverage_observed"]["end"],
                    Fonte=s["source_url"],
                )
                for s in specs
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    st.subheader("Validações da execução")
    st.dataframe(quality, width="stretch", hide_index=True)
    with st.expander("Metodologia econômica", expanded=True):
        st.markdown((ROOT / "docs/metodologia.md").read_text())
    with st.expander("Catálogo completo e limitações"):
        st.json(specs)
