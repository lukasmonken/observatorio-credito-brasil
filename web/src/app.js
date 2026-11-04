import "./style.css";
import {
  colors,
  eventLabels,
  finite,
  periodRows,
  rebase,
  unit,
  lagPairs,
  pearson,
  compareCollections,
  lastChanges,
  health,
  csv,
} from "./model.js";
const pages = [
  ["overview", "Visão geral"],
  ["credit", "Juros e crédito"],
  ["family", "Famílias e inadimplência"],
  ["explorer", "Explorador de indicadores"],
  ["relations", "Relações e defasagens"],
  ["revisions", "Histórico de revisões"],
  ["dictionary", "Dicionário e metodologia"],
  ["quality", "Fontes e qualidade"],
];
const state = {},
  main = document.querySelector("main");
let data, byCode, series, dates, signature, chartsPromise;
const number = (value, digits = 2) =>
  finite(value)
    ? new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      }).format(value)
    : "—";
const month = (value) =>
  value ? value.slice(5, 7) + "/" + value.slice(0, 4) : "—";
const localTime = (value) =>
  value
    ? new Date(value).toLocaleString("pt-BR", {
        timeZone: "America/Sao_Paulo",
        dateStyle: "short",
        timeStyle: "short",
      })
    : "Não registrado";
const currentPage = () =>
  pages.some(([key]) => key === location.hash.slice(1))
    ? location.hash.slice(1)
    : "overview";
function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== false && value != null)
      node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child != null)
      node.append(
        child instanceof Node ? child : document.createTextNode(String(child)),
      );
  }
  return node;
}
const note = (text) => el("p", { class: "note" }, text);
const message = (text, kind = "") =>
  el(
    "div",
    { class: "message " + kind, role: kind === "error" ? "alert" : "status" },
    text,
  );
function safeURL(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" ? parsed.href : "#";
  } catch {
    return "#";
  }
}
const link = (text, url) =>
  el(
    "a",
    { href: safeURL(url), target: "_blank", rel: "noopener noreferrer" },
    text,
  );
function save(content, filename, type = "text/csv;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = el("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function download(label, rows, filename, columns) {
  return el(
    "button",
    { type: "button", onclick: () => save(csv(rows, columns), filename) },
    label,
  );
}
function details(title, ...children) {
  return el("details", {}, el("summary", {}, title), ...children);
}
function metric(label, value, extra = "") {
  return el(
    "div",
    { class: "kpi" },
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, value),
    el("small", {}, extra),
  );
}
function select(key, label, options, initial) {
  const values = options.map((o) => String(Array.isArray(o) ? o[0] : o));
  if (!values.includes(String(state[key])))
    state[key] = String(initial ?? values[0]);
  if (!values.includes(String(state[key]))) state[key] = values[0];
  const input = el("select", {
    id: key,
    onchange: (e) => {
      state[key] = e.target.value;
      render();
    },
  });
  for (const option of options) {
    const [value, text] = Array.isArray(option) ? option : [option, option];
    const item = el("option", { value }, text);
    item.selected = String(value) === String(state[key]);
    input.append(item);
  }
  return el("label", { for: key }, label, input);
}
function textInput(key, label, initial = "", type = "search") {
  state[key] ??= initial;
  return el(
    "label",
    { for: key },
    label,
    el("input", {
      id: key,
      type,
      value: state[key],
      oninput: (e) => {
        state[key] = e.target.value;
        render();
      },
    }),
  );
}
function period(key, rows = data.rows) {
  const sorted = rows.map((r) => r.date).sort();
  const min = sorted[0],
    max = sorted.at(-1);
  state[key + "start"] ??= min;
  state[key + "end"] ??= max;
  const box = el("div", { class: "filters" });
  for (const [suffix, label] of [
    ["start", "Início do período"],
    ["end", "Fim do período"],
  ]) {
    const id = key + suffix;
    box.append(
      el(
        "label",
        { for: id },
        label,
        el("input", {
          id,
          type: "date",
          min,
          max,
          value: state[id],
          onchange: (e) => {
            state[id] = e.target.value;
            render();
          },
        }),
      ),
    );
  }
  return box;
}
function filtered(key, rows) {
  return periodRows(rows, state[key + "start"], state[key + "end"]);
}
function checks(
  key,
  title,
  options,
  initial = options.map((o) => String(o[0])),
) {
  state[key] ??= initial;
  const available = new Set(options.map((o) => String(o[0])));
  state[key] = state[key].filter((v) => available.has(String(v)));
  const box = el("fieldset", {}, el("legend", {}, title)),
    items = el("div", { class: "checks" });
  for (const [value, text, color] of options) {
    const id = `${key}-${value}`,
      checkbox = el("input", {
        type: "checkbox",
        id,
        value,
        onchange: (e) => {
          state[key] = e.target.checked
            ? [...state[key], String(value)]
            : state[key].filter((v) => v !== String(value));
          render();
        },
      });
    checkbox.checked = state[key].includes(String(value));
    items.append(
      el(
        "label",
        { for: id },
        checkbox,
        el("span", color ? { style: `color:${color}` } : {}, text),
      ),
    );
  }
  box.append(items);
  return box;
}
function table(rows, columns) {
  columns ??= Object.keys(rows[0] || {}).map((key) => [key, key]);
  if (!rows.length) return message("Nenhum registro corresponde aos filtros.");
  let ordered = [...rows],
    offset = 0;
  const holder = el("div"),
    wrap = el("div", { class: "table-wrap", tabindex: 0 }),
    grid = el("table"),
    body = el("tbody"),
    head = el("tr");
  const foot = el("div", { class: "actions" }),
    count = el("small");
  let orderKey,
    ascending = true;
  function fill() {
    body.replaceChildren();
    for (const row of ordered.slice(offset, offset + 100)) {
      const tr = el("tr");
      for (const [key, , format] of columns) {
        const value = row[key];
        tr.append(
          el(
            "td",
            { class: finite(value) ? "numeric" : "" },
            format
              ? format(value)
              : value == null
                ? "—"
                : typeof value === "object"
                  ? JSON.stringify(value)
                  : String(value),
          ),
        );
      }
      body.append(tr);
    }
    count.textContent = `${offset + 1}–${Math.min(offset + 100, rows.length)} de ${rows.length} registros`;
    previous.disabled = offset === 0;
    next.disabled = offset + 100 >= rows.length;
    wrap.scrollTop = 0;
  }
  for (const [key, label] of columns) {
    head.append(
      el(
        "th",
        {},
        el(
          "button",
          {
            type: "button",
            "aria-label": "Ordenar por " + label,
            onclick: () => {
              ascending = orderKey === key ? !ascending : true;
              orderKey = key;
              ordered.sort((a, b) => {
                const x = a[key],
                  y = b[key];
                if (x == null) return 1;
                if (y == null) return -1;
                return (
                  (finite(x) && finite(y)
                    ? x - y
                    : String(x).localeCompare(String(y), "pt-BR", {
                        numeric: true,
                      })) * (ascending ? 1 : -1)
                );
              });
              offset = 0;
              fill();
            },
          },
          label,
        ),
      ),
    );
  }
  const previous = el(
      "button",
      {
        onclick: () => {
          offset = Math.max(0, offset - 100);
          fill();
        },
      },
      "Anterior",
    ),
    next = el(
      "button",
      {
        onclick: () => {
          offset += 100;
          fill();
        },
      },
      "Próxima",
    );
  grid.append(el("thead", {}, head), body);
  wrap.append(grid);
  foot.append(count);
  if (rows.length > 100) foot.append(previous, next);
  holder.append(wrap, foot);
  fill();
  return holder;
}
function charts() {
  return (chartsPromise ??= import("./charts.js"));
}
function chart(
  parent,
  codes,
  metricName = "original",
  rows = data.rows,
  title,
  customColors,
) {
  const specs = codes.map((c) => byCode.get(Number(c))).filter(Boolean);
  const units = [
    ...new Set(specs.map((s) => unit(s, metricName, data.manifest))),
  ];
  if (units.length > 2) {
    parent.append(
      message(
        "Selecione indicadores com até duas unidades diferentes ou use gráficos separados.",
      ),
    );
    return;
  }
  const box = el(
      "section",
      { class: "chart-wrap" },
      el("h3", {}, title || specs.map((s) => s.name).join(" · ")),
    ),
    plot = el(
      "div",
      { class: "chart", "aria-label": title || "Gráfico de séries" },
      "Carregando gráfico…",
    );
  box.append(plot);
  const selected = specs.map((s, index) => ({
    name: s.name,
    unit: unit(s, metricName, data.manifest),
    metric: metricName,
    rows: rows.filter((r) => r.code === s.code),
    color: customColors?.[s.code] || colors[index % colors.length],
  }));
  box.append(
    note(
      `Fonte: BCB/SGS ${codes.join(", ")} · ${rows.length ? month(rows.map(r => r.date).sort()[0]) + "–" + month(rows.map(r => r.date).sort().at(-1)) : "sem período"} · ${units.join(" / ")}`,
    ),
  );
  parent.append(box);
  charts()
    .then((c) => c.drawLines(plot, selected, units))
    .catch(() => {
      if (plot.isConnected)
        plot.replaceChildren(
          message(
            "Não foi possível carregar o gráfico. Recarregue a página.",
            "error",
          ),
        );
    });
}
const eventColumns = [
  ["code", "SGS"],
  ["name", "Indicador"],
  ["event_label", "Mudança"],
  ["reference_date", "Referência", month],
  ["old_value", "Valor anterior"],
  ["new_value", "Valor novo"],
  ["difference", "Diferença"],
  ["unit", "Unidade"],
  ["difference_unit", "Unidade da diferença"],
];
function overview() {
  const kpis = el("div", { class: "kpis" });
  for (const [code, label] of [
    [432, "Meta Selic"],
    [21084, "Inadimplência PF"],
    [29037, "Endividamento"],
    [29034, "Comprometimento de renda"],
  ]) {
    const row = series
      .get(code)
      ?.filter((r) => finite(r.original))
      .at(-1);
    if (row)
      kpis.append(
        metric(
          label,
          `${number(row.original)} ${byCode.get(code).unit}`,
          `Referência ${month(row.date)} · ${finite(row.diff_pp) ? number(row.diff_pp) + " p.p. no mês · " : ""}SGS ${code}`,
        ),
      );
  }
  main.append(kpis);
  const changed = lastChanges(data.history, data.history_meta),
    box = details("O que mudou na última atualização");
  if (!changed)
    box.append(
      message("Esta base ainda não tem comparação com uma coleta anterior."),
    );
  else {
    box.append(
      note(
        `${localTime(changed.detected_at)} · Brasília · ${changed.series_count} indicadores com mudanças`,
      ),
    );
    const metrics = el("div", { class: "kpis" });
    for (const [key, label] of Object.entries(eventLabels))
      metrics.append(metric(label, changed.counts[key]));
    box.append(metrics);
    if (changed.events.length) {
      box.append(
        table(
          changed.events.map((e) => ({
            ...e,
            event_label: eventLabels[e.event_type],
          })),
          eventColumns,
        ),
        download(
          "Baixar mudanças da última coleta · CSV",
          changed.events,
          `mudancas-${changed.snapshot_id}.csv`,
        ),
      );
    } else
      box.append(
        message(
          "Nenhuma mudança nos valores originais em relação à coleta anterior.",
        ),
      );
    box.append(
      note(
        `Contagens de observações (série × mês). Coletas: ${changed.previous_snapshot_id} → ${changed.snapshot_id}. A data de detecção não é a data oficial de divulgação.`,
      ),
    );
  }
  main.append(box);
  const grid = el("div", { class: "grid2" });
  main.append(grid);
  chart(
    grid,
    [20539],
    "real_yoy_pct",
    data.rows,
    "Estoque de crédito · crescimento real em 12 meses",
  );
  chart(
    grid,
    [21084],
    "original",
    data.rows,
    "Inadimplência · pessoas físicas",
  );
  main.append(
    note(
      "Leitura conjunta: crescimento real do crédito, custo e atrasos. As séries mostram associações históricas; não estabelecem causalidade.",
    ),
  );
}
function credit() {
  main.append(
    el(
      "div",
      { class: "filters" },
      select("segment", "Segmento", ["Total", "PF", "PJ"], "Total"),
      select(
        "credit-view",
        "Visualização",
        [
          ["separate", "Gráficos separados"],
          ["combined", "Comparar no mesmo gráfico"],
        ],
        "separate",
      ),
    ),
  );
  const available = data.catalog.filter(
    (s) =>
      s.segment === state.segment &&
      ["Juros", "Spread", "Estoque", "Concessões"].includes(s.classification),
  );
  const palette = Object.fromEntries(
      available.map((s, i) => [s.code, colors[i % colors.length]]),
    ),
    key = "credit-" + state.segment;
  main.append(
    checks(
      key,
      "Indicadores",
      available.map((s) => [s.code, s.name, palette[s.code]]),
      available.slice(0, 3).map((s) => String(s.code)),
    ),
    period("credit"),
  );
  const rows = filtered("credit", data.rows),
    selected = state[key].map(Number);
  if (!rows.length) {
    main.append(
      message("Não há observações no intervalo selecionado. Amplie o período."),
    );
    return;
  }
  if (!selected.length)
    main.append(
      message("Selecione ao menos um indicador para exibir os gráficos."),
    );
  else if (state["credit-view"] === "combined") {
    chart(main, selected, "original", rows, "Juros e crédito", palette);
    main.append(
      note(
        "Valores originais, sem normalização. Eixos com escalas independentes: cruzamentos e inclinações entre unidades diferentes não indicam igualdade. Clique na legenda para ocultar ou reexibir uma série.",
      ),
    );
  } else
    for (const code of selected)
      chart(main, [code], "original", rows, undefined, palette);
  main.append(
    note(
      "Modalidades PF com recursos livres podem ser comparadas em % a.a.; garantias, prazos e composição diferem. Agregados não devem ser somados às modalidades.",
    ),
  );
}
function family() {
  main.append(period("family"));
  const rows = filtered("family", data.rows);
  if (!rows.length) {
    main.append(message("Não há observações no intervalo selecionado."));
    return;
  }
  const grid = el("div", { class: "grid2" });
  main.append(grid);
  for (const code of [29037, 29034, 21084, 21083])
    chart(grid, [code], "original", rows);
  main.append(
    message(
      "Inadimplência mede percentual da carteira, não de pessoas. Mudanças contábeis e de composição limitam comparações históricas; veja a metodologia.",
      "alert",
    ),
  );
}
function explorer() {
  const controls = el(
    "div",
    { class: "filters" },
    select(
      "explorer-code",
      "Indicador",
      data.catalog.map((s) => [s.code, s.name]),
      432,
    ),
  );
  const code = Number(state["explorer-code"]),
    spec = byCode.get(code);
  controls.append(
    select(
      "explorer-metric",
      "Transformação",
      spec.allowed_transforms.map((m) => [m, data.labels[m]]),
      "original",
    ),
  );
  main.append(controls, period("explorer", series.get(code)));
  const metricName = state["explorer-metric"];
  let rows = filtered("explorer", series.get(code));
  if (!rows.length) {
    main.append(
      message("Não há observações no intervalo selecionado. Amplie o período."),
    );
    return;
  }
  if (metricName === "base100") {
    rows = rebase(rows);
    const first = rows.find((r) => finite(r.original));
    main.append(
      note(
        `Base 100 recalculada no primeiro valor válido do período selecionado: ${month(first?.date)}. Base zero gera ausência.`,
      ),
    );
  }
  if (metricName === "real")
    main.append(
      note(
        `Deflação pelo IPCA encadeado; mês-base ${data.manifest.price_base_month}. Sem inflação disponível, o valor real permanece ausente.`,
      ),
    );
  chart(main, [code], metricName, rows);
  const exported = rows.map((r) => ({
    code,
    date: r.date,
    name: spec.name,
    unit: spec.unit,
    original: r.original,
    ...(metricName === "original" ? {} : { [metricName]: r[metricName] }),
    transformed_unit: unit(spec, metricName, data.manifest),
  }));
  const actions = el(
    "div",
    { class: "actions" },
    download(
      "Baixar dados filtrados · CSV",
      exported,
      `sgs_${code}_${metricName}.csv`,
    ),
  );
  const excel = el(
    "button",
    {
      type: "button",
      id: "download-excel",
      onclick: async () => {
        excel.disabled = true;
        excel.textContent = "Preparando Excel…";
        try {
          const { excelFile } = await import("./excel.js");
          const content = await excelFile(data, rows, spec, metricName, [
            state.explorerstart,
            state.explorerend,
          ]);
          save(
            content,
            `sgs_${code}_${metricName}_${data.manifest.snapshot_id.slice(0, 8)}.xlsx`,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          );
        } catch {
          actions.after(
            message(
              "Não foi possível gerar o Excel. Tente novamente.",
              "error",
            ),
          );
        } finally {
          excel.disabled = false;
          excel.textContent = "Baixar dados filtrados · Excel";
        }
      },
    },
    "Baixar dados filtrados · Excel",
  );
  actions.append(excel);
  main.append(
    actions,
    note(
      "O Excel inclui o recorte exibido, unidades, fonte, metodologia e identificação da coleta.",
    ),
    details("Ver tabela", table(exported)),
  );
}
const permitted = (spec) =>
  spec.allowed_transforms.filter((m) =>
    [
      "original",
      "mom_pct",
      "yoy_pct",
      "diff_pp",
      "diff12_pp",
      "real_yoy_pct",
    ].includes(m),
  );
function relations() {
  main.append(
    note(
      "Compare dois indicadores e explore a associação entre referências mensais.",
    ),
  );
  const controls = el("div", { class: "filters" });
  for (const [axis, initial, label] of [
    ["x", 432, "X · indicador antecedente"],
    ["y", 21084, "Y · indicador posterior"],
  ])
    controls.append(
      select(
        "relation-" + axis,
        label,
        data.catalog.map((s) => [s.code, s.name]),
        initial,
      ),
    );
  for (const axis of ["x", "y"]) {
    const opts = permitted(byCode.get(Number(state["relation-" + axis])));
    controls.append(
      select(
        "relation-" + axis + "m",
        "Transformação de " + axis.toUpperCase(),
        opts.map((m) => [m, data.labels[m]]),
        opts.includes("diff_pp") ? "diff_pp" : opts.at(-1),
      ),
    );
  }
  state.lag ??= 6;
  controls.append(
    el(
      "label",
      { for: "lag" },
      `Defasagem de X em meses: ${state.lag}`,
      el("input", {
        type: "range",
        id: "lag",
        min: 0,
        max: 24,
        step: 1,
        value: state.lag,
        oninput: (e) => {
          state.lag = Number(e.target.value);
          render();
        },
      }),
    ),
  );
  main.append(controls, period("relations"));
  const included = filtered("relations", data.rows);
  if (!included.length) {
    main.append(message("Não há observações no intervalo selecionado."));
    return;
  }
  const x = series
      .get(Number(state["relation-x"]))
      .map((r) => ({ date: r.date, value: r[state["relation-xm"]] })),
    y = series
      .get(Number(state["relation-y"]))
      .map((r) => ({ date: r.date, value: r[state["relation-ym"]] }));
  const pairs = lagPairs(
      x,
      y,
      Number(state.lag),
      state.relationsstart,
      state.relationsend,
    ),
    r = pearson(pairs);
  main.append(
    el(
      "p",
      { class: "inline-stats", id: "correlation" },
      finite(r)
        ? `X(t−${state.lag}) × Y(t) · n = ${pairs.length} pares mensais · correlação de Pearson = ${number(r, 3)}`
        : `n = ${pairs.length} · amostra insuficiente ou série constante.`,
    ),
  );
  if (pairs.length) {
    main.append(
      note(
        `Período de Y: ${month(pairs[0].date)} a ${month(pairs.at(-1).date)}. X pode anteceder o início desse período.`,
      ),
    );
    const node = el("div", { class: "chart" }, "Carregando gráfico…");
    main.append(node);
    charts()
      .then((c) =>
        c.drawScatter(
          node,
          pairs,
          unit(
            byCode.get(Number(state["relation-x"])),
            state["relation-xm"],
            data.manifest,
          ),
          unit(
            byCode.get(Number(state["relation-y"])),
            state["relation-ym"],
            data.manifest,
          ),
        ),
      )
      .catch(() => {
        if (node.isConnected)
          node.textContent = "Não foi possível carregar o gráfico.";
      });
  }
  const lags = Array.from({ length: 13 }, (_, lag) => {
    const p = lagPairs(x, y, lag, state.relationsstart, state.relationsend);
    return { lag, n: p.length, r: pearson(p) };
  });
  main.append(
    table(lags, [
      ["lag", "Defasagem (meses)"],
      ["n", "n"],
      ["r", "r", (v) => number(v, 3)],
    ]),
    message(
      "Exploração, não causalidade. Tendência, sazonalidade, autocorrelação, janelas de 12 meses sobrepostas e quebras metodológicas afetam as correlações. Não há teste de significância ajustado para dependência temporal.",
      "alert",
    ),
  );
}
function revisions() {
  main.append(
    note(
      "Compara valores originais entre coletas publicadas. A data de detecção não é a data oficial de divulgação ou revisão pelo Bacen.",
    ),
  );
  const meta = data.history_meta;
  if (!meta) {
    main.append(message("Esta base ainda não contém comparações registradas."));
    return;
  }
  const comparison = meta.comparisons.at(-1);
  main.append(
    note(`Última comparação: ${localTime(comparison.detected_at)} · Brasília`),
  );
  const metrics = el("div", { class: "kpis" });
  for (const [key, label] of Object.entries(eventLabels))
    metrics.append(metric(label, comparison.counts[key]));
  main.append(
    metrics,
    note(
      `Coletas: ${comparison.previous_snapshot_id} → ${comparison.snapshot_id}`,
    ),
    note(
      `Histórico acompanhado desde ${localTime(meta.baseline_created_at)} · ${meta.comparisons.length} comparações registradas.`,
    ),
  );
  if (Object.values(comparison.counts).every((n) => n === 0))
    main.append(
      message(
        "Nenhuma mudança nos valores originais na última comparação. Isso não apaga eventos de coletas anteriores.",
      ),
    );
  if (!data.history.length)
    main.append(
      message(
        "Ainda não foram detectadas mudanças desde o início do acompanhamento.",
      ),
    );
  else {
    const codes = [...new Set(data.history.map((e) => e.code))].sort(
      (a, b) => Number(a) - Number(b),
    );
    main.append(
      details(
        "Filtrar séries",
        checks(
          "revision-codes",
          "Séries",
          codes.map((code) => [
            code,
            `SGS ${code} · ${byCode.get(Number(code))?.name || code}`,
          ]),
        ),
      ),
      checks("revision-types", "Tipo de mudança", Object.entries(eventLabels)),
    );
    const detectedDates = data.history
      .map((e) => brDate(new Date(e.detected_at)))
      .sort();
    state["revision-start"] ??= detectedDates[0];
    state["revision-end"] ??= detectedDates.at(-1);
    const filters = el("div", { class: "filters" });
    for (const [key, label] of [
      ["revision-start", "Detecção inicial"],
      ["revision-end", "Detecção final"],
    ]) {
      filters.append(
        el(
          "label",
          { for: key },
          label,
          el("input", {
            id: key,
            type: "date",
            value: state[key],
            min: detectedDates[0],
            max: detectedDates.at(-1),
            onchange: (e) => {
              state[key] = e.target.value;
              render();
            },
          }),
        ),
      );
    }
    main.append(filters);
    if (state["revision-start"] > state["revision-end"]) {
      main.append(message("Selecione um período de detecção válido."));
    } else {
      const filtered = data.history
        .filter(
          (e) =>
            state["revision-codes"].includes(e.code) &&
            state["revision-types"].includes(e.event_type) &&
            brDate(new Date(e.detected_at)) >= state["revision-start"] &&
            brDate(new Date(e.detected_at)) <= state["revision-end"],
        )
        .sort(
          (a, b) =>
            b.detected_at.localeCompare(a.detected_at) ||
            b.reference_date.localeCompare(a.reference_date),
        );
      main.append(
        table(
          filtered.map((e) => ({
            ...e,
            event_label: eventLabels[e.event_type],
          })),
          [
            ["detected_at", "Detectado em · Brasília", localTime],
            ...eventColumns,
            ["previous_snapshot_id", "Coleta anterior"],
            ["snapshot_id", "Coleta nova"],
          ],
        ),
        download(
          "Baixar histórico filtrado · CSV",
          filtered,
          "historico_revisoes.csv",
          Object.keys(data.history[0]),
        ),
      );
    }
  }
  main.append(
    note(
      "Diferença = valor novo − valor anterior. Para taxas, em pontos percentuais; demais séries na unidade original. Novas observações não têm valor anterior nem diferença.",
    ),
  );
  const comparisons = meta.comparisons.map((c) => ({
    previous_snapshot_id: c.previous_snapshot_id,
    snapshot_id: c.snapshot_id,
    detected_at: c.detected_at,
    ...c.counts,
  }));
  main.append(
    details(
      "Comparações entre coletas, inclusive sem mudanças",
      table(comparisons),
      download(
        "Baixar registro de comparações · CSV",
        comparisons,
        "comparacoes_coletas.csv",
      ),
    ),
  );
  const ids = [
      meta.baseline_snapshot_id,
      ...meta.comparisons.map((c) => c.snapshot_id),
    ],
    moments = [
      meta.baseline_created_at,
      ...meta.comparisons.map((c) => c.detected_at),
    ],
    opts = ids.map((id, i) => [
      id,
      `${localTime(moments[i])} · ${id.slice(0, 8)}`,
    ]);
  const box = details(
    "Comparar duas coletas",
    note(
      "Diferença líquida dos valores originais entre duas bases. Revisões intermediárias que se anulam não aparecem aqui. Horários de registro em Brasília.",
    ),
  );
  const controls = el(
    "div",
    { class: "filters" },
    select("compare-initial", "Coleta inicial", opts.slice(0, -1), ids.at(-2)),
    select("compare-final", "Coleta final", opts.slice(1), ids.at(-1)),
  );
  const results = el("div", { id: "comparison-result" });
  controls.append(
    el(
      "button",
      {
        id: "compare-button",
        onclick: () => {
          results.replaceChildren();
          try {
            const compared = compareCollections(
              data.history,
              meta,
              state["compare-initial"],
              state["compare-final"],
            );
            const counts = el(
              "div",
              { class: "kpis" },
              metric("Observações com diferença líquida", compared.length),
              metric(
                "Indicadores afetados",
                new Set(compared.map((e) => e.code)).size,
              ),
              metric(
                "Revisões líquidas",
                compared.filter((e) => e.event_type === "revision").length,
              ),
              metric(
                "Observações adicionadas",
                compared.filter((e) => e.event_type === "added_observation")
                  .length,
              ),
            );
            results.append(
              counts,
              compared.length
                ? table(
                    compared.map((e) => ({
                      ...e,
                      event_label:
                        e.event_type === "revision"
                          ? "Revisão líquida"
                          : "Observação adicionada",
                    })),
                    eventColumns,
                  )
                : message(
                    "Nenhuma diferença nos valores originais entre as duas coletas. Podem existir revisões intermediárias que se anularam.",
                  ),
              download(
                "Baixar comparação · CSV",
                compared,
                `comparacao-${state["compare-initial"]}-${state["compare-final"]}.csv`,
                [
                  "code",
                  "name",
                  "reference_date",
                  "event_type",
                  "old_value",
                  "new_value",
                  "difference",
                  "unit",
                  "difference_unit",
                  "previous_snapshot_id",
                  "snapshot_id",
                ],
              ),
              note(
                `Coleta inicial: ${state["compare-initial"]} · Coleta final: ${state["compare-final"]}`,
              ),
              note(
                "Adições incluem novos meses, lacunas preenchidas e séries incluídas. A comparação não altera a base publicada.",
              ),
            );
          } catch (error) {
            results.append(message(error.message, "alert"));
          }
        },
      },
      "Comparar coletas",
    ),
  );
  box.append(controls, results);
  if (state["compare-initial"] || state["compare-final"])
    box.open = Boolean(state.comparisonOpen);
  box.addEventListener("toggle", () => (state.comparisonOpen = box.open));
  main.append(box);
}
function methodology() {
  return details(
    "Metodologia econômica completa",
    el("div", { class: "methodology" }, data.methodology),
  );
}
const interpretations = {
  stock:
    "Mede o saldo da carteira em uma data. Aumento do saldo não equivale ao volume de novos empréstimos do mês.",
  flow: "Mede novas operações contratadas no mês. Dias úteis e sazonalidade afetam comparações mensais.",
  rate: "Leia o nível na unidade indicada. De 10% para 12% significa +2 p.p.",
  index:
    "Mede evolução relativa da atividade. Não representa PIB em reais. O IBC-Br selecionado já tem ajuste sazonal.",
  variation:
    "O IPCA original é a inflação do mês. O acumulado em 12 meses compõe os fatores mensais; não soma as taxas.",
};
function dictionary() {
  main.append(
    note("Fichas do catálogo associado à base publicada."),
    el(
      "div",
      { class: "filters" },
      textInput("dictionary-search", "Buscar por nome ou código SGS"),
    ),
  );
  const query = state["dictionary-search"].toLocaleLowerCase("pt-BR"),
    matches = data.catalog.filter((s) =>
      `${s.code} ${s.name} ${s.official_name || ""}`
        .toLocaleLowerCase("pt-BR")
        .includes(query),
    );
  if (!matches.length) main.append(message("Nenhum indicador encontrado."));
  else {
    main.append(
      el(
        "div",
        { class: "filters" },
        select(
          "dictionary-code",
          "Indicador",
          matches.map((s) => [s.code, `${s.code} · ${s.name}`]),
        ),
      ),
    );
    const spec = byCode.get(Number(state["dictionary-code"])),
      observed = series.get(spec.code).filter((r) => finite(r.original));
    main.append(
      el("h3", {}, spec.official_name || spec.name),
      el("p", {}, spec.description || "Conceito não informado."),
      table(
        [
          ["Código SGS", spec.code],
          ["Unidade no painel", spec.unit],
          [
            "Unidade nos metadados oficiais",
            spec.official_unit || "Não informada",
          ],
          [
            "Periodicidade de origem",
            spec.frequency === "D" ? "Diária" : "Mensal",
          ],
          ["Periodicidade no painel", "Mensal"],
          [
            "Tratamento temporal",
            spec.frequency === "D"
              ? "Última observação de cada mês concluído; não é média mensal."
              : "Referência mensal preservada, sem somar ou reponderar.",
          ],
          ["Categoria", spec.classification],
          ["Segmento", spec.segment],
          ["Modalidade", spec.modality],
          ["Recursos", spec.resources],
          [
            "Período com valores na base",
            observed.length
              ? month(observed[0].date) + " – " + month(observed.at(-1).date)
              : "Sem valores válidos",
          ],
          [
            "Metadados conferidos em",
            spec.metadata_verified_at || "Não informado",
          ],
        ].map(([field, value]) => ({ field, value })),
        [
          ["field", "Campo"],
          ["value", "Informação"],
        ],
      ),
      link("Consultar fonte oficial e metadados", spec.source_url),
      note(
        spec.code === 433
          ? "Fonte primária: IBGE; distribuição: BCB/SGS."
          : "Fonte: Banco Central do Brasil / SGS.",
      ),
      el("h3", {}, "Como interpretar"),
      el(
        "p",
        {},
        interpretations[spec.measure_type] || "Consulte o conceito oficial.",
      ),
      el("h3", {}, "Transformações disponíveis"),
      table(
        spec.allowed_transforms.map((m) => ({
          label: data.labels[m],
          unit: unit(spec, m, data.manifest),
          formula: data.formulas[m],
        })),
        [
          ["label", "Transformação"],
          ["unit", "Unidade"],
          ["formula", "Cálculo e leitura"],
        ],
      ),
      el("h3", {}, "Limitações e comparabilidade"),
      el(
        "ul",
        {},
        (spec.limitations || []).map((text) => el("li", {}, text)),
      ),
      note(
        `Snapshot: ${data.manifest.snapshot_id} · Mês-base dos valores reais: ${data.manifest.price_base_month || "Indisponível"}`,
      ),
    );
  }
  main.append(
    methodology(),
    note(
      "A reconsulta de 18 meses descrita no catálogo refere-se ao modo incremental. O job diário atual coleta o período completo.",
    ),
    el(
      "button",
      {
        onclick: () =>
          save(
            JSON.stringify(data.catalog, null, 2),
            "dicionario_indicadores.json",
            "application/json",
          ),
      },
      "Baixar catálogo · JSON",
    ),
  );
}
function brDate(date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (t) => parts.find((p) => p.type === t).value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}
function quality() {
  const m = data.monitoring || {},
    [status, text] = health(data.monitoring, data.manifest);
  main.append(
    el("h3", {}, "Monitoramento da atualização"),
    message(text, status === "ok" ? "" : "alert"),
    el(
      "div",
      { class: "kpis" },
      metric("Última tentativa · Brasília", localTime(m.started_at)),
      metric(
        "Último sucesso · Brasília",
        localTime(m.last_success_at || data.manifest.created_at),
      ),
      metric(
        "Duração da tentativa",
        m.duration_seconds == null
          ? "Não registrada"
          : m.duration_seconds + " s",
      ),
    ),
  );
  if (m.failed_series?.length)
    main.append(
      message("Séries com falha: " + m.failed_series.join(", "), "alert"),
    );
  if (m.stage) main.append(note("Etapa registrada: " + m.stage));
  main.append(
    note(
      "Coleta diária prevista às 19h17 de Brasília. Alerta após 30 horas sem sucesso. Duração até a validação, sem o envio ao GitHub.",
    ),
    link(
      "Consultar execuções e diagnóstico no GitHub Actions",
      "https://github.com/lukasmonken/observatorio-credito-brasil/actions",
    ),
    el("h3", {}, "Atualidade das séries"),
  );
  const today = Date.parse(brDate(new Date())),
    freshness = data.catalog.map((s) => {
      const last = series
          .get(s.code)
          .filter((r) => finite(r.original))
          .at(-1),
        lag = last
          ? Math.floor((today - Date.parse(last.date)) / 86400000)
          : null;
      return {
        code: s.code,
        name: s.name,
        last: last?.date,
        lag,
        limit: s.max_lag_days,
        status:
          lag == null
            ? "Sem dados"
            : lag > s.max_lag_days
              ? "Acima do limite"
              : "Dentro do limite",
      };
    });
  main.append(
    table(freshness, [
      ["code", "SGS"],
      ["name", "Indicador"],
      ["last", "Última referência", month],
      ["lag", "Dias desde a referência"],
      ["limit", "Limite operacional (dias)"],
      ["status", "Situação"],
    ]),
    note(
      "Dias desde o início do mês de referência. Limites do catálogo são critérios operacionais, não prazos oficiais. Coleta sem observação nova não comprova atraso do Bacen.",
    ),
    el("h3", {}, "Base publicada"),
    note(
      `Execução: ${data.manifest.summary.successes} séries atualizadas; ${data.manifest.summary.failures} falhas. Mês-base real: ${data.manifest.price_base_month}.`,
    ),
    table(
      data.catalog.map((s) => ({
        code: s.code,
        name: s.name,
        unit: s.unit,
        frequency: s.frequency,
        start: s.coverage_observed.start,
        end: s.coverage_observed.end,
        source: s.source_url,
      })),
    ),
    el("h3", {}, "Validações da execução"),
    table(data.quality),
    methodology(),
    details(
      "Catálogo completo e limitações",
      el("pre", {}, JSON.stringify(data.catalog, null, 2)),
    ),
  );
}
function render() {
  if (!data) return;
  const active = document.activeElement,
    focus = active?.id,
    position = active?.type === "search" ? active.selectionStart : null;
  for (const node of main.querySelectorAll(".chart"))
    if (chartsPromise) chartsPromise.then((c) => c.dispose(node));
  main.replaceChildren();
  const page = currentPage();
  for (const a of document.querySelectorAll("nav a")) {
    if (a.hash === "#" + page) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  main.append(
    el("h2", {}, pages.find(([key]) => key === page)[1]),
    note(
      "As referências variam por indicador. A Selic considera apenas meses concluídos.",
    ),
  );
  try {
    ({
      overview,
      credit,
      family,
      explorer,
      relations,
      revisions,
      dictionary,
      quality,
    })[page]();
  } catch (error) {
    main.append(
      message(
        error.message === "Selecione um período válido."
          ? error.message
          : "Não foi possível exibir esta seleção. Revise os filtros ou recarregue a página.",
        "error",
      ),
    );
    console.error(error);
  }
  if (focus) {
    const replacement = document.getElementById(focus);
    replacement?.focus({ preventScroll: true });
    if (position != null && replacement?.type === "search")
      replacement.setSelectionRange(position, position);
  }
  updateHealth();
}
function updateHealth() {
  if (!data) return;
  const [status, text] = health(data.monitoring, data.manifest),
    box = document.getElementById("health");
  box.replaceChildren();
  if (status !== "ok") box.append(message(text, "alert"));
  if (data.monitoring_error)
    box.append(message(data.monitoring_error, "alert"));
}
async function load() {
  const response = await fetch("./site.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Base indisponível");
  const config = await response.json();
  if (
    !/^data-[a-f0-9]{16}\.json$/.test(config.data) ||
    !/^[a-f0-9]{64}$/.test(config.sha256)
  )
    throw new Error("Configuração inválida");
  if (config.sha256 === signature) return false;
  const request = await fetch("./" + config.data);
  if (!request.ok) throw new Error("Base indisponível");
  const buffer = await request.arrayBuffer();
  const hash = Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", buffer)),
    (v) => v.toString(16).padStart(2, "0"),
  ).join("");
  if (hash !== config.sha256) throw new Error("Integridade inválida");
  const payload = JSON.parse(new TextDecoder().decode(buffer));
  if (
    payload.schema_version !== 1 ||
    !Array.isArray(payload.rows) ||
    !Array.isArray(payload.catalog) ||
    payload.manifest.snapshot_id !== config.snapshot_id ||
    payload.rows.length !== payload.manifest.rows
  )
    throw new Error("Formato inválido");
  data = payload;
  signature = hash;
  byCode = new Map(data.catalog.map((s) => [s.code, s]));
  series = new Map(
    data.catalog.map((s) => [
      s.code,
      data.rows
        .filter((r) => r.code === s.code)
        .sort((a, b) => a.date.localeCompare(b.date)),
    ]),
  );
  dates = data.rows.map((r) => r.date).sort();
  document.getElementById("metadata").textContent =
    `Fonte: Banco Central do Brasil · Coleta: ${data.manifest.as_of.split("-").reverse().join("/")} · Histórico: ${month(dates[0])}–${month(dates.at(-1))}`;
  document
    .getElementById("sidebar-meta")
    .replaceChildren(
      el(
        "div",
        {},
        `${data.manifest.series} séries · ${number(data.manifest.rows, 0)} registros mensais`,
      ),
      el("div", {}, "Snapshot: " + data.manifest.snapshot_id.slice(0, 8)),
      el(
        "button",
        { onclick: () => location.reload() },
        "Verificar atualização",
      ),
    );
  return true;
}
for (const [key, label] of pages)
  document.getElementById("nav").append(el("a", { href: "#" + key }, label));
window.addEventListener("hashchange", () => {
  render();
  main.focus({ preventScroll: true });
});
load()
  .then(() => render())
  .catch(() =>
    main.replaceChildren(
      message(
        "Não foi possível carregar a base validada. Verifique sua conexão e tente novamente.",
        "error",
      ),
      el("button", { onclick: () => location.reload() }, "Tentar novamente"),
    ),
  );
setInterval(updateHealth, 60000);
setInterval(async () => {
  try {
    if (await load()) render();
  } catch {
    document
      .getElementById("health")
      .append(
        message(
          "Não foi possível verificar uma nova versão. Esta página mantém a última base carregada.",
          "alert",
        ),
      );
  }
}, 300000);
