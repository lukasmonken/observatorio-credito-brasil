"""Exportação do recorte do explorador com metadados e metodologia."""

from datetime import datetime, timezone
from io import BytesIO
import math

import pandas as pd

METRIC_LABELS = {
    "qoq_pct": "Variação trimestral (%)",
    "sum12": "Acumulado em 12 meses",
    "sum_ytd": "Acumulado no ano",
    "original": "Valor original",
    "ma3": "Média móvel de 3 meses",
    "mom_pct": "Variação mensal (%)",
    "yoy_pct": "Variação em 12 meses (%)",
    "diff_pp": "Mudança mensal (p.p.)",
    "diff12_pp": "Mudança em 12 meses (p.p.)",
    "base100": "Índice base 100",
    "real": "Valor real (R$ milhões)",
    "real_yoy_pct": "Crescimento real em 12 meses (%)",
    "inflation_ytd": "Inflação acumulada no ano (%)",
    "inflation12": "Inflação acumulada em 12 meses (%)",
}

METRIC_FORMULAS = {
    "qoq_pct": "(xₜ / xₜ₋₁ trimestre − 1) × 100, com ajuste sazonal; denominador zero ou ausente gera ausência.",
    "sum12": "Soma dos 12 meses até a referência; exige todos os meses presentes.",
    "sum_ytd": "Soma de janeiro até a referência; exige todos os meses desde janeiro.",
            "original": "Valor da série após organização no calendário mensal.",
            "ma3": "(xₜ + xₜ₋₁ + xₜ₋₂) / 3; exige os três meses presentes.",
            "mom_pct": "(xₜ / xₜ₋₁ − 1) × 100; denominador zero ou ausente gera ausência.",
            "yoy_pct": "(xₜ / xₜ₋₁₂ − 1) × 100; compara com o mesmo mês ou trimestre do ano anterior, conforme a frequência.",
            "diff_pp": "xₜ − xₜ₋₁, em pontos percentuais.",
            "diff12_pp": "xₜ − xₜ₋₁₂, em pontos percentuais.",
            "base100": "100 × xₜ / primeiro valor válido. No explorador, a base é recalculada no intervalo selecionado; base zero gera ausência.",
            "real": "Nominalₜ × P_base / Pₜ, com índice de preços encadeado pelo IPCA.",
            "real_yoy_pct": "(realₜ / realₜ₋₁₂ − 1) × 100; crescimento descontada a inflação pelo IPCA.",
            "inflation_ytd": "[Produto dos fatores (1 + taxaₘ / 100), de janeiro ao mês de referência − 1] × 100; exige todos os meses desde janeiro.",
            "inflation12": "[Produto dos 12 fatores (1 + taxaₘ / 100) − 1] × 100; exige 12 meses presentes.",
        }


def build_excel(data, spec, manifest, metric, transformed_unit, period, methodology):
    if data.empty or len(data) > 1_048_575:
        raise ValueError("Quantidade de linhas inválida para exportação")
    if metric not in spec["allowed_transforms"] or metric not in METRIC_FORMULAS:
        raise ValueError("Transformação não permitida para o indicador")
    if not data.code.eq(spec["code"]).all() or not data.snapshot_id.eq(manifest["snapshot_id"]).all():
        raise ValueError("Dados não correspondem ao indicador e à coleta informados")
    if len(period) != 2 or period[0] > period[1]:
        raise ValueError("Período inválido")
    dates = pd.to_datetime(data.date)
    if dates.isna().any() or dates.duplicated().any() or not dates.dt.date.between(*period).all():
        raise ValueError("Referências inválidas ou fora do período selecionado")
    for column in {"original", metric}:
        if not data[column].map(lambda value: pd.isna(value) or math.isfinite(value)).all():
            raise ValueError("Valor infinito na exportação")
    values = pd.DataFrame({
        "SGS": data.code,
        "Referência": dates,
        "Indicador": data["name"] if "name" in data else spec["name"],
        "Valor original": data.original,
        "Unidade original": spec["unit"],
    })
    if metric != "original":
        values[METRIC_LABELS[metric]] = data[metric]
        values["Unidade da transformação"] = transformed_unit
    if spec["frequency"] == "Q":
        values["Trimestre"] = dates.map(lambda d: f"{d.quarter}º tri/{d.year}")
    values = values.sort_values("Referência")
    indicator = [
        ("Código SGS", spec["code"]), ("Nome", spec["name"]),
        ("Nome oficial", spec.get("official_name", "Não informado")),
        ("Conceito", spec.get("description", "Não informado")),
        ("Fonte primária", spec.get("source", "Banco Central do Brasil / SGS")),
        ("Fonte oficial e metadados", spec["source_url"]),
        ("Unidade original", spec["unit"]),
        ("Periodicidade de origem", {"D": "Diária", "M": "Mensal", "Q": "Trimestral"}.get(spec["frequency"], spec["frequency"])),
        ("Periodicidade exportada", "Mensal — trimestres móveis" if spec.get("reference_period") == "trimestre móvel" else "Trimestral" if spec["frequency"] == "Q" else "Mensal"),
        ("Tratamento temporal", "Última observação de cada mês concluído, sem média mensal." if spec["frequency"] == "D" else "Data representa o início do trimestre; não há mensalização." if spec["frequency"] == "Q" else "Referência mensal preservada."),
        ("Categoria", spec["classification"]), ("Segmento", spec["segment"]),
        ("Modalidade", spec.get("modality", "Não informada")),
        ("Recursos", spec.get("resources", "Não informado")),
        ("Limitações", "\n".join(spec.get("limitations", [])) or "Consulte a fonte oficial."),
        ("Metadados conferidos em", spec.get("metadata_verified_at", "Não informado")),
    ]
    first = data.loc[data.original.notna()].sort_values("date")
    base100 = first.iloc[0].date.strftime("%m/%Y") if metric == "base100" and not first.empty and first.iloc[0].original != 0 else "Não aplicável ou indisponível"
    methods = [
        ("Transformação selecionada", METRIC_LABELS[metric]),
        ("Unidade da transformação", transformed_unit),
        ("Cálculo", METRIC_FORMULAS[metric]),
        ("Mês-base do índice base 100 no recorte", base100),
        ("Mês-base dos valores reais", (spec.get("income_price_base") if spec.get("measure_type") == "income_real" else manifest.get("price_base_month")) or "Indisponível"),
        ("Valores ausentes", "Células vazias representam ausência; zero permanece zero. Nenhum dado foi imputado na exportação."),
        ("Percentuais", "Valores na escala indicada pela unidade: 15 significa 15%, não 0,15. Diferenças de taxas são pontos percentuais."),
        ("Cálculos no arquivo", "Valores calculados pelo painel. O arquivo não recalcula indicadores nem contém fórmulas executáveis."),
        ("Janela dos cálculos", "Variações e médias utilizam o histórico da base antes do filtro. Apenas base 100 é recalculada no período selecionado."),
    ]
    methods.extend(("Metodologia econômica", paragraph.strip().lstrip("# ")) for paragraph in methodology.split("\n\n") if paragraph.strip())
    collection = [
        ("Projeto", "Observatório de Crédito Brasil"),
        ("Aplicação", "https://observatorio-credito-brasil.streamlit.app/"),
        ("Snapshot", manifest["snapshot_id"]),
        ("Snapshot criado em (UTC)", manifest["created_at"]),
        ("Data de corte da coleta", manifest["as_of"]),
        ("Exportado em (UTC)", datetime.now(timezone.utc).isoformat()),
        ("Início solicitado", period[0].isoformat()), ("Fim solicitado", period[1].isoformat()),
        ("Primeira referência exportada", dates.min().strftime("%m/%Y")),
        ("Última referência exportada", dates.max().strftime("%m/%Y")),
        ("Observações exportadas", len(data)), ("Transformação", metric),
        ("Fonte", "Catálogo e dados do snapshot identificado acima."),
        ("Datas", "Referência não é data de divulgação. Coleta/exportação não identificam a publicação original do Bacen."),
    ]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="mm/yyyy",
                        engine_kwargs={"options": {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False}}) as writer:
        book = writer.book
        body = book.add_format({"font_name": "Times New Roman", "font_size": 11, "valign": "top"})
        numeric = book.add_format({"font_name": "Times New Roman", "font_size": 11, "num_format": "#,##0.00######", "align": "right"})
        text = book.add_format({"font_name": "Times New Roman", "font_size": 11, "text_wrap": True, "valign": "top"})
        header = book.add_format({"font_name": "Times New Roman", "font_size": 11, "bold": True, "bg_color": "#F4F5F5", "bottom": 1, "bottom_color": "#DDE1E1", "text_wrap": True})
        sheets = {"Dados": values, **{name: pd.DataFrame(rows, columns=["Campo", "Informação"]) for name, rows in (
            ("Indicador", indicator), ("Metodologia", methods), ("Coleta", collection),
        )}}
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False, startrow=1, header=False)
            sheet = writer.sheets[name]
            sheet.hide_gridlines(2)
            sheet.freeze_panes(1, 0)
            sheet.set_row(0, 32)
            sheet.write_row(0, 0, table.columns.tolist(), header)
            if name == "Dados":
                sheet.autofilter(0, 0, len(table), len(table.columns) - 1)
                for index, column in enumerate(table.columns):
                    width = 10 if column == "SGS" else 15 if column == "Referência" else 44 if column == "Indicador" else 27
                    style = numeric if column in ("Valor original", METRIC_LABELS[metric]) else body
                    sheet.set_column(index, index, width, style)
            else:
                sheet.set_column(0, 0, 42, text)
                sheet.set_column(1, 1, 105, text)
                for row, value in enumerate(table["Informação"], 1):
                    line_count = sum(max(1, (len(line) + 99) // 100) for line in str(value).split("\n"))
                    sheet.set_row(row, max(30, line_count * 16))
    return output.getvalue()
