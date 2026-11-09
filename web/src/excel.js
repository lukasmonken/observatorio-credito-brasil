import ExcelJS from "exceljs";
import { finite, unit } from "./model.js";
export async function excelFile(data, rows, spec, metric, period) {
  if (
    !rows.length ||
    rows.length > 1048575 ||
    !spec.allowed_transforms.includes(metric) ||
    period[0] > period[1]
  )
    throw new Error("Recorte inválido");
  if (
    rows.some(
      (r) => r.code !== spec.code || r.date < period[0] || r.date > period[1],
    ) ||
    new Set(rows.map((r) => r.date)).size !== rows.length
  )
    throw new Error("Referências inválidas");
  const book = new ExcelJS.Workbook();
  book.creator = "Observatório de Crédito Brasil";
  book.created = new Date();
  function sheet(name, headers, values) {
    const ws = book.addWorksheet(name, {
      views: [{ state: "frozen", ySplit: 1, showGridLines: false }],
    });
    ws.addRow(headers);
    ws.addRows(values);
    ws.eachRow((row, i) => {
      row.eachCell((cell) => {
        cell.font = { name: "Times New Roman", size: 11, bold: i === 1 };
        cell.alignment = { vertical: "top", wrapText: true };
        if (i === 1)
          cell.fill = {
            type: "pattern",
            pattern: "solid",
            fgColor: { argb: "FFF4F5F5" },
          };
      });
      if (i === 1) row.height = 30;
    });
    return ws;
  }
  const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date)),
    headers = [
      "SGS",
      "Referência",
      "Indicador",
      "Valor original",
      "Unidade original",
    ];
  if (metric !== "original")
    headers.push(data.labels[metric], "Unidade da transformação");
  if (spec.frequency === "Q") headers.push("Trimestre");
  const values = sorted.map((r) => {
    for (const key of new Set(["original", metric]))
      if (r[key] != null && !finite(r[key])) throw new Error("Valor inválido");
    const value = [
      spec.code,
      new Date(r.date + "T00:00:00Z"),
      spec.name,
      r.original ?? null,
      spec.unit,
    ];
    if (metric !== "original")
      value.push(r[metric] ?? null, unit(spec, metric, data.manifest));
    if (spec.frequency === "Q") value.push(`${Math.floor((Number(r.date.slice(5,7))-1)/3)+1}º tri/${r.date.slice(0,4)}`);
    return value;
  });
  const ws = sheet("Dados", headers, values);
  ws.columns.forEach((column, i) => {
    column.width = i === 0 ? 10 : i === 1 ? 15 : i === 2 ? 44 : 27;
  });
  ws.getColumn(2).numFmt = "mm/yyyy";
  ws.getColumn(4).numFmt = "#,##0.00######";
  if (metric !== "original") ws.getColumn(6).numFmt = "#,##0.00######";
  ws.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: rows.length + 1, column: headers.length },
  };
  const indicator = [
    ["Código SGS", spec.code],
    ["Nome", spec.name],
    ["Nome oficial", spec.official_name || "Não informado"],
    ["Conceito", spec.description || "Não informado"],
    [
      "Fonte primária",
      spec.source || "Banco Central do Brasil / SGS",
    ],
    ["Fonte oficial e metadados", spec.source_url],
    ["Unidade original", spec.unit],
    ["Periodicidade de origem", spec.frequency === "Q" ? "Trimestral" : spec.frequency === "D" ? "Diária" : "Mensal"],
    ["Periodicidade exportada", spec.reference_period === "trimestre móvel" ? "Mensal — trimestres móveis" : spec.frequency === "Q" ? "Trimestral" : "Mensal"],
    [
      "Tratamento temporal",
      spec.frequency === "D"
        ? "Última observação de cada mês concluído, sem média mensal."
        : spec.frequency === "Q" ? "Data representa o início do trimestre; não há mensalização." : "Referência mensal preservada.",
    ],
    ["Categoria", spec.classification],
    ["Segmento", spec.segment],
    ["Modalidade", spec.modality || "Não informada"],
    ["Recursos", spec.resources || "Não informado"],
    ["Limitações", (spec.limitations || []).join("\n")],
    ["Metadados conferidos em", spec.metadata_verified_at || "Não informado"],
  ];
  const first = sorted.find((r) => finite(r.original)),
    month = (d) => d.slice(5, 7) + "/" + d.slice(0, 4);
  const methods = [
    ["Transformação selecionada", data.labels[metric]],
    ["Unidade da transformação", unit(spec, metric, data.manifest)],
    ["Cálculo", data.formulas[metric]],
    [
      "Mês-base do índice base 100 no recorte",
      metric === "base100" && first?.original
        ? month(first.date)
        : "Não aplicável ou indisponível",
    ],
    [
      "Mês-base dos valores reais",
      (spec.measure_type === "income_real" ? spec.income_price_base : data.manifest.price_base_month) || "Indisponível",
    ],
    [
      "Valores ausentes",
      "Células vazias representam ausência; zero permanece zero. Nenhum dado foi imputado na exportação.",
    ],
    [
      "Percentuais",
      "15 significa 15%, não 0,15. Diferenças de taxas são pontos percentuais.",
    ],
    [
      "Cálculos no arquivo",
      "Valores calculados pelo painel. Não contém fórmulas executáveis.",
    ],
    [
      "Janela dos cálculos",
      "Variações e médias utilizam o histórico anterior ao filtro. Apenas base 100 é recalculada no período selecionado.",
    ],
    ...data.methodology
      .split("\n\n")
      .filter((p) => p.trim())
      .map((p) => ["Metodologia econômica", p.trim().replace(/^#+ /, "")]),
  ];
  const collection = [
    ["Projeto", "Observatório de Crédito Brasil"],
    ["Aplicação", "https://lukasmonken.github.io/observatorio-credito-brasil/"],
    ["Snapshot", data.manifest.snapshot_id],
    ["Snapshot criado em (UTC)", data.manifest.created_at],
    ["Data de corte da coleta", data.manifest.as_of],
    ["Exportado em (UTC)", new Date().toISOString()],
    ["Início solicitado", period[0]],
    ["Fim solicitado", period[1]],
    ["Primeira referência exportada", month(sorted[0].date)],
    ["Última referência exportada", month(sorted.at(-1).date)],
    ["Observações exportadas", rows.length],
    ["Transformação", metric],
    ["Fonte", "Catálogo e dados do snapshot identificado acima."],
    [
      "Datas",
      "Referência não é data de divulgação. Coleta/exportação não identificam a publicação original do Bacen.",
    ],
  ];
  for (const [name, values] of [
    ["Indicador", indicator],
    ["Metodologia", methods],
    ["Coleta", collection],
  ]) {
    const ws = sheet(name, ["Campo", "Informação"], values);
    ws.getColumn(1).width = 42;
    ws.getColumn(2).width = 105;
    ws.eachRow((row, i) => {
      if (i > 1)
        row.height = Math.min(
          409,
          Math.max(
            30,
            16 *
              String(row.getCell(2).value)
                .split("\n")
                .reduce(
                  (n, line) => n + Math.max(1, Math.ceil(line.length / 95)),
                  0,
                ),
          ),
        );
    });
  }
  return book.xlsx.writeBuffer();
}
