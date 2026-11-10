import { renderInflationDetail } from "./inflation-detail.js";
import "./style.css";
import { panoramaRows, referenceLabel } from "./panorama.js";
import { laborPeriod, laborExport } from "./labor.js";
import { readShare, shareHash, pageKeys } from "./share.js";
import {
  compositionRows,
  monthNumber,
  monthDate,
  colors,
  eventLabels,
  finite,
  periodRows,
  rebase,
  compareBase100,
  unit,
  lagPairs,
  pearson,
  compareCollections,
  lastChanges,
  health,
  csv,
} from "./model.js";
const pages = [
  ["panorama", "Panorama Brasil"],
  ["overview", "Visão geral"],
  ["credit", "Juros e crédito"],
  ["composition", "Composição do crédito"],
  ["inflation", "Inflação detalhada"],
  ["labor", "Trabalho e renda"],
  ["external", "Setor externo e câmbio"],
  ["activity", "Crescimento e atividade"],
  ["comparison", "Comparação em base 100"],
  ["family", "Famílias e inadimplência"],
  ["explorer", "Explorador de indicadores"],
  ["relations", "Relações e defasagens"],
  ["revisions", "Histórico de revisões"],
  ["dictionary", "Dicionário e metodologia"],
  ["quality", "Fontes e qualidade"],
];
const pickerUI = {};
const state = readShare(location.hash).state,
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
const currentPage = () => readShare(location.hash).page;
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
    { type: "button", onclick: () => save(csv(rows, columns, state["csv-profile"] || "excel"), filename) },
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
function indicatorPicker(key, title, options, initial) {
  const available = new Set(options.map(([code]) => String(code)));
  state[key] ??= initial;
  state[key] = state[key].map(String).filter((code) => available.has(code));
  const ui = pickerUI[key] ??= { open: false, search: "" };
  const limit = ["comparison-codes", "inflation-groups"].includes(key) ? 6 : options.length;
  const selected = state[key];
  const wrapper = el("section", { class: "indicator-picker", "data-picker": key });
  const menu = el("details", { class: "picker-menu", ...(ui.open ? { open: true } : {}) });
  const summary = el("summary", { id: key + "-toggle" },
    el("span", {}, title),
    el("span", { class: "picker-count" }, `${selected.length} selecionados`),
    el("span", { class: "picker-chevron", "aria-hidden": true }, "⌄"));
  const search = el("input", { type: "search", id: key + "-search", placeholder: "Buscar indicador…", "aria-label": "Buscar indicadores", value: ui.search });
  const list = el("div", { class: "picker-options" });
  const normalize = (text) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const fill = () => {
    ui.search = search.value;
    list.replaceChildren();
    const matching = options.filter(([code, name]) => normalize(`${name} ${code}`).includes(normalize(ui.search)));
    const groups = new Map();
    for (const option of matching) {
      const group = byCode.get(Number(option[0]))?.classification || "Outros indicadores";
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(option);
    }
    for (const [group, items] of groups) {
      const field = el("fieldset", {}, el("legend", {}, group));
      for (const [code, name] of items) {
        const value = String(code), checked = selected.includes(value);
        const input = el("input", { type: "checkbox", id: `${key}-${value}`, value,
          disabled: !checked && selected.length >= limit,
          onchange: (e) => {
            state[key] = e.target.checked ? [...selected, value] : selected.filter((v) => v !== value);
            ui.open = true;
            render();
          } });
        input.checked = checked;
        field.append(el("label", { class: "picker-option", for: `${key}-${value}` }, input, el("span", {}, name)));
      }
      list.append(field);
    }
    if (!matching.length) list.append(note("Nenhum indicador encontrado."));
  };
  search.addEventListener("input", fill);
  fill();
  menu.append(summary, el("div", { class: "picker-panel" }, search, list,
    el("div", { class: "picker-footer" },
      el("small", {}, key === "comparison-codes" ? "Selecione de 2 a 6 indicadores" : "Selecione os indicadores do gráfico"),
      el("button", { type: "button", onclick: () => { menu.open = false; ui.open = false; summary.focus(); } }, "Concluir"))));
  menu.addEventListener("toggle", () => { if (menu.isConnected) ui.open = menu.open; });
  const tags = el("div", { class: "picker-tags", "aria-label": "Indicadores selecionados" });
  for (const value of selected) {
    const name = options.find(([code]) => String(code) === value)[1];
    tags.append(el("span", { class: "picker-tag" }, el("span", {}, name),
      el("button", { type: "button", "aria-label": "Remover " + name, onclick: () => { state[key] = selected.filter((v) => v !== value); render(); } }, "×")));
  }
  wrapper.append(menu, tags);
  return wrapper;
}
document.addEventListener("pointerdown", (event) => {
  for (const picker of document.querySelectorAll(".indicator-picker")) {
    if (!picker.contains(event.target)) {
      picker.querySelector("details").open = false;
      pickerUI[picker.dataset.picker].open = false;
    }
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  for (const picker of document.querySelectorAll(".indicator-picker")) {
    const menu = picker.querySelector("details");
    if (menu.open) { menu.open = false; pickerUI[picker.dataset.picker].open = false; menu.querySelector("summary").focus(); }
  }
});
function checks(
  key,
  title,
  options,
  initial = options.map((o) => String(o[0])),
) {
  if (key.startsWith("inflation-") || key === "comparison-codes" || /^credit-(Total|PF|PJ)$/.test(key))
    return indicatorPicker(key, title, options, initial);
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
  const numericColumns = new Set(
    columns
      .filter(([key, , format]) => format === number || rows.some((row) => finite(row[key])))
      .map(([key]) => key),
  );
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
            { class: numericColumns.has(key) ? "numeric" : "" },
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
        { scope: "col", class: numericColumns.has(key) ? "numeric" : "" },
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
    name: s.short_name || s.name,
    unit: unit(s, metricName, data.manifest),
    metric: metricName,
    rows: rows.filter((r) => r.code === s.code),
    color: customColors?.[s.code] || colors[index % colors.length],
  }));
  const chartDates = selected.flatMap((s) => s.rows.map((r) => r.date)).sort();
  box.append(
    note(
      `Fonte: BCB/SGS ${codes.join(", ")} · ${chartDates.length ? month(chartDates[0]) + "–" + month(chartDates.at(-1)) : "sem período"} · ${units.join(" / ")}`,
    ),
  );
  parent.append(box);
  charts()
    .then((c) => c.drawLines(plot, selected, units, {title:title || specs.map(s=>s.short_name||s.name).join(" · "), source:`Fonte: BCB/SGS ${codes.join(", ")} · ${data.labels[metricName]}`, period:chartDates.length ? month(chartDates[0])+"–"+month(chartDates.at(-1)) : "", asOf:data.manifest.as_of}))
    .catch((error) => {
      console.error(error);
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
function collectionBulletin() {
  const b = data.bulletin;
  if (!b) return;
  const box = details("Boletim da coleta");
  box.append(note(`Coleta validada: ${localTime(b.created_at)} · Brasília`));
  for (const text of b.paragraphs) box.append(el("p", {}, text));
  for (const [title, items] of [["Novas referências e variações mensais", b.highlights], ["Revisões históricas", b.revisions]]) {
    box.append(el("h3", {}, title));
    if (!items.length) box.append(note(b.counts === null ? "Comparação ainda indisponível." : "Nenhum registro desta categoria na última comparação."));
    else box.append(el("ul", {}, items.slice(0, 8).map(item => el("li", {}, item.text, " ", link("Fonte", item.source_url)))));
    if (items.length > 8) box.append(note(`Exibidos 8 de ${items.length} registros, em ordem SGS e referência. O JSON contém todos.`));
  }
  box.append(details("Como ler o boletim", b.notes.map(text => note(text))),
    el("div", {class: "actions"},
      el("button", {type: "button", id: "download-bulletin", onclick: () => save(b.markdown, `boletim-${b.snapshot_id}.md`, "text/markdown;charset=utf-8")}, "Baixar boletim · Markdown"),
      el("button", {type: "button", onclick: () => save(JSON.stringify(b, null, 2), `boletim-${b.snapshot_id}.json`, "application/json")}, "Baixar boletim completo · JSON")),
    note(`Coleta: ${b.snapshot_id} · Anterior: ${b.previous_snapshot_id || "não disponível"}`));
  main.append(box);
}
function panorama() {
  main.append(note("Um retrato da economia brasileira com a última referência de cada indicador. As datas diferem e os valores estão sujeitos a revisões."));
  const rows = panoramaRows(data.rows, data.catalog);
  const cards = el("div", {class:"kpis panorama-kpis"});
  for (const row of rows) {
    const card = metric(row.label, finite(row.value) ? `${number(row.value, row.code === 3698 ? 4 : 2)} ${row.unit}` : "Indisponível", referenceLabel(row.date,row.period));
    card.append(note(row.description), note(`${row.source} · SGS ${row.code}`));
    if (row.source_url) card.append(link("Consultar fonte",row.source_url));
    card.append(el("p",{},el("a",{href:`#${row.page}`},`Abrir ${row.module}`)));
    cards.append(card);
  }
  main.append(cards, note(`Data-base da coleta: ${data.manifest.as_of.slice(0,10).split("-").reverse().join("/")}. Data de coleta e período de referência são informações diferentes.`));
  main.append(el("h3",{},"Evolução dos indicadores"), select("panorama-code","Indicador do panorama",rows.map(r=>[r.code,r.label]),433));
  const selected = rows.find(r=>r.code === Number(state["panorama-code"]));
  const history = data.rows.filter(r=>r.code === selected.code);
  main.append(note(selected.description));
  chart(main,[selected.code],selected.metric,history,selected.label);
  main.append(download("Baixar resumo do Panorama Brasil · CSV",rows.map(r=>({code:r.code,indicator:r.label,reference:r.date,reference_period:referenceLabel(r.date,r.period),value:r.value,unit:r.unit,measure:r.metric,description:r.description,source:r.source,source_url:r.source_url,snapshot_id:data.manifest.snapshot_id})),"panorama-brasil.csv"));
  main.append(details("Como ler o panorama",note("Cada cartão usa a última observação original disponível da série. Se o cálculo dessa referência estiver indisponível, o cartão não recua silenciosamente para um valor antigo. Ausências não são zeros. As unidades e os períodos não devem ser somados ou comparados diretamente."), note("O histórico mantém a medida do cartão e inclui todas as referências da base. Para filtros, outras medidas e Excel, abra o módulo correspondente ou o Explorador de indicadores.")));
  collectionBulletin();
}
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
  collectionBulletin();
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
function composition() {
  main.append(note("Saldos de fim de mês por modalidade. As participações usam o total de crédito PF ou PJ, incluindo recursos livres e direcionados."));
  main.append(select("composition-segment", "Segmento", [["PF", "Pessoas físicas"], ["PJ", "Pessoas jurídicas"]], "PF"));
  const segment = state["composition-segment"], specs = data.catalog.filter(s => s.credit_composition && s.segment === segment);
  if (!specs.length) { main.append(message("Modalidades ainda indisponíveis nesta coleta. Aguarde a atualização dos dados.")); return; }
  const all = compositionRows(data.rows, data.catalog, segment);
  main.append(period("composition", all));
  const rows = filtered("composition", all);
  if (!rows.length) { main.append(message("Não há observações no intervalo selecionado.")); return; }
  const months = [...new Set(rows.map(r => r.date))].sort().reverse();
  const complete = months.find(d => rows.filter(r => r.date === d).every(r => finite(r.original) && finite(r.share)));
  main.append(el("div", {class:"filters"},
    select("composition-month", "Referência da composição", months.map(d => [d,month(d)]), complete || months[0]),
    select("composition-metric", "Medida do histórico", [["original","Saldo (R$ milhões)"],["share","Participação no total do segmento (%)"]], "original")));
  const current = rows.filter(r => r.date === state["composition-month"]);
  main.append(el("div",{class:"kpis"},metric("Saldo total " + segment, number(current[0]?.total) + " R$ milhões", month(state["composition-month"])),metric("Modalidades acompanhadas",specs.length,"Seleção parcial da carteira")));
  if (current.some(r => !finite(r.original) || !finite(r.share))) main.append(message("Há valores ou participações indisponíveis nesta referência. Ausências não são tratadas como zero; percentuais exigem total positivo e saldo compatível."));
  main.append(table(current, [["modality","Modalidade"],["resources","Recursos"],["original","Saldo (R$ milhões)",number],["share","% do total " + segment,number]]));
  const key = "composition-" + segment;
  main.append(checks(key,"Modalidades no histórico",specs.map((s,i)=>[s.code,s.modality,colors[i%colors.length]])));
  const selected = state[key].map(Number), measure = state["composition-metric"], units = [measure === "share" ? "% do total " + segment : "R$ milhões"];
  if (selected.length) {
    const box = el("section",{class:"chart-wrap"},el("h3",{},"Evolução das modalidades — " + segment)), plot = el("div",{class:"chart","aria-label":"Evolução das modalidades"});
    box.append(plot,note("Fonte: BCB/SGS · " + units[0])); main.append(box);
    charts().then(c=>c.drawLines(plot,specs.filter(s=>selected.includes(s.code)).map(s=>({name:s.modality,metric:measure,unit:units[0],rows:rows.filter(r=>r.code===s.code),color:colors[specs.indexOf(s)%colors.length]})),units,{title:"Evolução das modalidades — "+segment,source:"Fonte: BCB/SGS · "+specs.filter(s=>selected.includes(s.code)).map(s=>s.code).join(", "),period:month(rows[0].date)+"–"+month(rows.at(-1).date),asOf:data.manifest.as_of})).catch(()=>{if(plot.isConnected) plot.textContent="Não foi possível carregar o gráfico.";});
  } else main.append(message("Selecione uma modalidade para exibir o histórico."));
  const exported = rows.map(r=>({...r,unit:"R$ milhões",snapshot_id:data.manifest.snapshot_id}));
  main.append(download("Baixar modalidades · CSV",exported,"composicao-credito-"+segment+".csv"));
  main.append(note("As modalidades acompanhadas não esgotam a carteira e seus percentuais não precisam somar 100%. Cada participação usa o total do mesmo segmento e mês; não há interpolação nem combinação de referências diferentes. Valores nominais, sujeitos a revisões."));
  main.append(details("Fontes das modalidades",...specs.map(s=>el("p",{},el("a",{href:safeURL(s.source_url),target:"_blank",rel:"noopener noreferrer"},s.modality + " · SGS " + s.code)))));
}
const quarter = d => d ? `${Math.floor((Number(d.slice(5,7))-1)/3)+1}º tri/${d.slice(0,4)}` : "—";
function activity() {
  const specs = data.catalog.filter(s => s.activity_group), codes = specs.map(s => s.code);
  const all = data.rows.filter(r => codes.includes(r.code));
  main.append(note("Brasil · PIB trimestral do IBGE e indicadores mensais de atividade. IBC-Br é um indicador do Banco Central e não substitui o PIB. Índices medem volume, não valores em reais."));
  if (!all.length) { main.append(message("Crescimento e atividade ainda indisponível nesta coleta.")); return; }
  main.append(period("activity",all));
  const rows = filtered("activity",all);
  if (!rows.length) { main.append(message("Não há observações no intervalo selecionado.")); return; }
  const cards = el("div",{class:"kpis external-kpis"});
  for (const [code,m,label] of [[22109,"qoq_pct","PIB · trimestre anterior"],[22099,"yoy_pct","PIB · mesmo trimestre do ano anterior"],[24364,"mom_pct","IBC-Br · mês anterior"],[21859,"yoy_pct","Indústria · mesmo mês do ano anterior"],[1455,"yoy_pct","Varejo · mesmo mês do ano anterior"],[23982,"yoy_pct","Serviços · mesmo mês do ano anterior"]]) {
    const s=byCode.get(code), r=rows.filter(r=>r.code===code && finite(r.original)).at(-1);
    cards.append(metric(label,r && finite(r[m]) ? `${number(r[m])} %` : "—",r ? `${s.frequency === "Q" ? quarter(r.date) : month(r.date)} · ${s.seasonally_adjusted ? "Com ajuste sazonal" : "Sem ajuste sazonal"}` : "Sem referência no período"));
  }
  main.append(cards,note("Cada cartão informa sua própria referência. Comparação trimestral usa PIB ajustado; comparação anual usa PIB observado. Variações são calculadas antes do filtro, sem preencher períodos ausentes."));
  const controls=el("div",{class:"filters labor-filters"});
  controls.append(select("activity-code","Indicador do histórico",specs.map(s=>[s.code,s.short_name||s.name]),22109));
  const code=Number(state["activity-code"]), spec=byCode.get(code);
  controls.append(select("activity-metric","Medida do histórico",spec.allowed_transforms.filter(m=>m!=="base100").map(m=>[m,data.labels[m]]),spec.frequency==="Q" && spec.seasonally_adjusted ? "qoq_pct" : "yoy_pct"));
  main.append(controls);
  chart(main,[code],state["activity-metric"],rows,`${spec.short_name||spec.name} · ${spec.frequency==="Q" ? "Trimestral" : "Mensal"}`);
  main.append(note(spec.description));
  if (spec.frequency==="Q") main.append(note("Datas do gráfico representam o início de cada trimestre. Não há interpolação nem repetição mensal do PIB."));
  const componentSpecs=specs.filter(s=>s.activity_group==="Componentes do PIB");
  const quarters=[...new Set(rows.filter(r=>componentSpecs.some(s=>s.code===r.code)).map(r=>r.date))].sort().reverse();
  if (quarters.length) {
    main.append(el("h3",{},"Componentes do PIB"),select("activity-quarter","Trimestre dos componentes",quarters.map(d=>[d,quarter(d)]),quarters[0]));
    const summary=componentSpecs.map(s=>{const r=rows.find(r=>r.code===s.code && r.date===state["activity-quarter"]); return {name:s.short_name,value:r?.original??null,yoy:r?.yoy_pct??null};});
    main.append(table(summary,[["name","Componente"],["value","Índice de volume",number],["yoy","Mesmo trimestre do ano anterior (%)",number]]),note("Componentes sem ajuste sazonal. Índices encadeados não são participações nem contribuições ao crescimento; não devem ser somados. Exportações e importações do PIB incluem bens e serviços e diferem dos valores em dólares do módulo externo."));
  }
  const exported=rows.map(r=>{const s=byCode.get(r.code);return {date:r.date,reference_period:s.frequency==="Q"?quarter(r.date):month(r.date),code:r.code,indicator:s.short_name||s.name,frequency:s.frequency,seasonally_adjusted:!!s.seasonally_adjusted,original:r.original,unit:s.unit,qoq_pct:r.qoq_pct??null,mom_pct:r.mom_pct??null,yoy_pct:r.yoy_pct??null,source:s.source,source_url:s.source_url,snapshot_id:data.manifest.snapshot_id};});
  main.append(details("Ver histórico em tabela",table(exported.filter(r=>r.code===code),[["reference_period","Referência"],["original","Índice",number],[spec.frequency==="Q"&&spec.seasonally_adjusted?"qoq_pct":spec.seasonally_adjusted?"mom_pct":"yoy_pct","Variação (%)",number]])));
  main.append(download("Baixar crescimento e atividade · CSV",exported,"crescimento-atividade.csv"));
  main.append(note("Excel disponível no Explorador. Índices já medem volume; não aplicamos nova deflação pelo IPCA. Histórico reconsultado integralmente para incorporar revisões."));
  main.append(details("Fontes — crescimento e atividade",...specs.map(s=>el("p",{},link(`${s.short_name||s.name} · SGS ${s.code}`,s.source_url)))));
}

function external() {
  const specs = data.catalog.filter(s => s.classification === "Setor externo e câmbio");
  const codes = specs.map(s => s.code), all = data.rows.filter(r => codes.includes(r.code));
  main.append(note("Brasil · Dados mensais do Banco Central. Comércio de bens e transações correntes seguem o balanço de pagamentos (BPM6), com ajustes em relação ao Comex Stat/MDIC."));
  if (!all.length) { main.append(message("Setor externo e câmbio ainda indisponível nesta coleta. Aguarde a atualização dos dados.")); return; }
  main.append(period("external", all));
  const rows = filtered("external", all);
  if (!rows.length) { main.append(message("Não há observações no intervalo selecionado.")); return; }
  const months = [...new Set(rows.map(r => r.date))].sort().reverse();
  main.append(select("external-reference", "Referência do resumo", months.map(d => [d, month(d)]), months[0]));
  const ref = state["external-reference"], cards = el("div", {class:"kpis external-kpis"});
  for (const s of specs) {
    const r = rows.find(r => r.code === s.code && r.date === ref);
    cards.append(metric(s.short_name || s.name, finite(r?.original) ? `${number(r.original, s.code === 3698 ? 4 : 2)} ${s.unit}` : "—", `${month(ref)} · ${s.code === 3698 ? "Média do mês" : s.measure_type === "stock" ? "Fim do mês" : "Fluxo do mês"}${finite(r?.original) ? "" : " · Indisponível nesta referência"}`));
  }
  main.append(cards, note("Todos os cartões usam a referência escolhida. — indica dado indisponível, não zero. Os fluxos são mensais; reservas são estoque e dólar é cotação média."));
  const controls = el("div", {class:"filters labor-filters"});
  controls.append(select("external-code", "Indicador do histórico", specs.map(s => [s.code,s.short_name || s.name]), 3698));
  const code = Number(state["external-code"]), spec = byCode.get(code);
  controls.append(select("external-metric", "Medida do histórico", spec.allowed_transforms.filter(m => m !== "base100").map(m => [m, m === "original" ? `Valor (${spec.unit})` : data.labels[m]]), "original"));
  main.append(controls);
  const measure = state["external-metric"];
  chart(main, [code], measure, rows, `${spec.short_name || spec.name} · ${data.labels[measure]}`);
  main.append(note(spec.description), note("Acumulados somam apenas fluxos: exigem todos os meses desde janeiro ou os 12 meses consecutivos. São calculados antes do filtro. Saldos negativos indicam déficit. A alta do dólar em R$/US$ indica desvalorização do real."));
  const exported = rows.map(r => {
    const s = byCode.get(r.code);
    return {date:r.date, code:r.code, indicator:s.short_name || s.name, value:r.original, unit:s.unit, year_to_date:r.sum_ytd ?? null, trailing_12_months:r.sum12 ?? null, monthly_change_pct:r.mom_pct ?? null, annual_change_pct:r.yoy_pct ?? null, source:s.source, source_url:s.source_url, snapshot_id:data.manifest.snapshot_id};
  });
  main.append(details("Ver histórico em tabela", table(rows.filter(r => r.code === code), [["date","Referência",month],[measure,`${data.labels[measure]} (${unit(spec,measure)})`,number]])));
  main.append(download("Baixar setor externo e câmbio · CSV", exported, "setor-externo-cambio.csv"));
  main.append(note("CSV inclui valores originais, acumulados dos fluxos, variações permitidas, unidades e fontes. Excel e outras comparações estão no Explorador de indicadores."));
  main.append(details("Fontes e metodologia — setor externo", note("Valores em dólares correntes, sem deflação pelo IPCA. Reservas não medem apenas compras e vendas de moeda: seus valores também variam com preços dos ativos e taxas de câmbio. Câmbio mensal não representa cotação em tempo real. O histórico é atualizado integralmente para incorporar revisões."), ...specs.map(s => el("p", {}, link(`${s.short_name || s.name} · SGS ${s.code}`, s.source_url)))));
}

function labor() {
  const specs = data.catalog.filter(s => s.classification === "Trabalho e renda");
  const codes = specs.map(s => s.code), all = data.rows.filter(r => codes.includes(r.code));
  main.append(note("Brasil · IBGE / PNAD Contínua, distribuído pelo BCB/SGS. Cada referência é um trimestre móvel: os três meses terminados no mês indicado. Sem ajuste sazonal."));
  if (!all.length) {
    main.append(message("Trabalho e renda ainda indisponível nesta coleta. Aguarde a atualização dos dados."));
    return;
  }
  main.append(period("labor", all));
  const rows = filtered("labor", all);
  if (!rows.length) { main.append(message("Não há observações no intervalo selecionado.")); return; }
  const months = [...new Set(rows.map(r => r.date))].sort().reverse();
  main.append(select("labor-reference", "Trimestre móvel do resumo", months.map(d => [d, laborPeriod(d)]), months[0]));
  const ref = state["labor-reference"], cards = el("div", {class:"kpis labor-kpis"});
  for (const spec of specs) {
    const r = rows.find(r => r.code === spec.code && r.date === ref);
    cards.append(metric(spec.short_name || spec.name, finite(r?.original) ? `${number(r.original)} ${spec.unit}` : "—", `${laborPeriod(ref)}${finite(r?.original) ? "" : " · Indisponível nesta referência"}`));
  }
  main.append(cards);
  const lastIncome = all.filter(r => r.code === 24382 && finite(r.original)).map(r => r.date).sort().at(-1);
  const incomeBase = lastIncome ? monthDate(monthNumber(lastIncome) - 1).slice(0,7) : null;
  const exported = laborExport(rows, specs, data.manifest, incomeBase);
  const summary = specs.map(s => exported.find(r => r.code === s.code && r.reference_end === ref) || {indicator:s.short_name || s.name, value:null, unit:s.unit, change12:null, change_unit:s.measure_type === "rate" ? "p.p." : "%"});
  main.append(table(summary, [["indicator","Indicador"],["value","Valor",number],["unit","Unidade"],["change12","Variação em 12 meses",number],["change_unit","Unidade da variação"]]));
  main.append(note("Comparação com o mesmo trimestre móvel do ano anterior: pontos percentuais para a taxa de desocupação e variação percentual para pessoas e rendimento. Ausências permanecem indisponíveis; os cálculos usam o histórico anterior ao filtro."));
  const controls = el("div", {class:"filters labor-filters"});
  controls.append(select("labor-code", "Indicador do histórico", specs.map(s => [s.code,s.short_name || s.name]), 24369));
  const code = Number(state["labor-code"]), spec = byCode.get(code), annual = spec.measure_type === "rate" ? "diff12_pp" : "yoy_pct";
  controls.append(select("labor-metric", "Medida do histórico", [["original",`Valor (${spec.unit})`],[annual,`Mesmo trimestre do ano anterior (${annual === "diff12_pp" ? "p.p." : "%"})`]], "original"));
  main.append(controls);
  chart(main, [code], state["labor-metric"], rows, `${spec.short_name || spec.name} · trimestres móveis`);
  main.append(note("O eixo de datas indica o mês final de cada trimestre móvel. Referências consecutivas compartilham dois meses de pesquisa."));
  main.append(details("Ver histórico em tabela", table(exported.filter(r => r.code === code), [["reference_period","Trimestre móvel"],["indicator","Indicador"],["value","Valor",number],["unit","Unidade"],["change12","Variação em 12 meses",number],["change_unit","Unidade da variação"]])));
  main.append(download("Baixar trabalho e renda · CSV", exported, "trabalho-renda.csv"));
  main.append(note(`Rendimento já corrigido pela fonte; base de preços: ${incomeBase ? incomeBase.slice(5,7)+"/"+incomeBase.slice(0,4) : "indisponível"} (mês central do trimestre mais recente da série). A base não muda com o filtro. O histórico é reconsultado integralmente para incorporar revisões.`));
  main.append(details("Fontes e metodologia — trabalho e renda", note("Estimativas amostrais para pessoas de 14 anos ou mais. Diferenças numéricas não implicam significância estatística. Rendimento habitual do trabalho principal conforme metadados SGS; não é renda domiciliar per capita nem salário mínimo. Não aplicamos nova deflação ao rendimento real."), specs.map(s => el("p", {}, link(`${s.short_name || s.name} · SGS ${s.code}`, s.source_url)))));
}

function inflation() {
  main.append(select("inflation-view", "Visão da inflação", [["general", "Índices e grupos nacionais"], ["detail", "Regiões e subitens · IBGE"]], "general"));
  if (state["inflation-view"] === "detail") {
    renderInflationDetail(main, {el, select, state, note, message, table, number, month, download, charts}, data.inflation_files);
    return;
  }
  const specs = data.catalog.filter(s => s.classification === "Inflação"),
    general = specs.filter(s => s.inflation_group !== "Grupos do IPCA"),
    groups = specs.filter(s => s.inflation_group === "Grupos do IPCA"),
    allRows = data.rows.filter(r => specs.some(s => s.code === r.code));
  if (!allRows.length) { main.append(message("Inflação indisponível nesta coleta.")); return; }
  main.append(note("Compare índices e acompanhe os nove grupos do IPCA. Cada indicador mantém sua própria data de referência."));
  main.append(period("inflation", allRows));
  const rows = filtered("inflation", allRows);
  const metrics = ["original", "inflation_ytd", "inflation12"].filter(m => general.some(s => s.allowed_transforms.includes(m)));
  main.append(el("div", {class: "filters"}, select("inflation-metric", "Medida", metrics.map(m => [m, m === "original" ? "Variação mensal (%)" : data.labels[m]]), "original")));
  if (!rows.length) { main.append(message("Não há observações no intervalo selecionado.")); return; }
  const measure = state["inflation-metric"], cards = el("div", {class: "kpis inflation-kpis"});
  for (const spec of general) {
    const latest = rows.filter(r => r.code === spec.code && finite(r.original)).at(-1);
    cards.append(metric(spec.short_name || spec.name, latest ? `${number(latest[measure])} %` : "—", latest ? `${month(latest.date)} · ${measure === "original" ? "No mês" : measure === "inflation_ytd" ? "No ano" : "Em 12 meses"}` : "Sem referência no recorte"));
  }
  main.append(cards, note("Os cartões usam a última referência disponível de cada índice dentro do período. Ausência de acumulado aparece como —; não é zero."));
  main.append(checks("inflation-codes", "Índices para comparar", general.map(s => [s.code, s.short_name || s.name]), general.map(s => String(s.code))));
  const selected = state["inflation-codes"].map(Number);
  if (selected.length) chart(main, selected, measure, rows, "Evolução dos índices de inflação");
  else main.append(message("Selecione ao menos um índice."));
  const exported = rows.filter(r => selected.includes(r.code)).map(r => ({date:r.date, code:r.code, name:byCode.get(r.code).name, monthly_pct:r.original, year_to_date_pct:r.inflation_ytd ?? null, trailing_12_months_pct:r.inflation12 ?? null, source:byCode.get(r.code).source, source_url:byCode.get(r.code).source_url, snapshot_id:data.manifest.snapshot_id}));
  if (exported.length) main.append(download("Baixar índices · CSV", exported, "inflacao_indices.csv"), details("Ver dados dos índices", table(exported, [["date","Referência",month],["name","Índice"],["monthly_pct","No mês (%)",number],["year_to_date_pct","No ano (%)",number],["trailing_12_months_pct","Em 12 meses (%)",number]])));
  main.append(el("h3", {}, "Grupos do IPCA"), note("Variações dos grupos, não contribuições em pontos percentuais. Não some as taxas para reconstruir o IPCA."));
  if (groups.length) {
    const groupRows = rows.filter(r => groups.some(s => s.code === r.code));
    const months = [...new Set(groupRows.filter(r => finite(r.original)).map(r => r.date))].sort().reverse();
    if (months.length) {
      main.append(select("inflation-group-month", "Referência dos grupos", months.map(m => [m,month(m)]), months[0]));
      const monthRows = groups.map(s => {
        const row = groupRows.find(r => r.code === s.code && r.date === state["inflation-group-month"]);
        return {date:state["inflation-group-month"], code:s.code, group:s.modality, monthly_pct:row?.original ?? null, year_to_date_pct:row?.inflation_ytd ?? null, trailing_12_months_pct:row?.inflation12 ?? null, source:s.source, source_url:s.source_url, snapshot_id:data.manifest.snapshot_id};
      });
      main.append(table(monthRows, [["group","Grupo"],["monthly_pct","No mês (%)",number],["year_to_date_pct","No ano (%)",number],["trailing_12_months_pct","Em 12 meses (%)",number]]), download("Baixar grupos · CSV",monthRows,"inflacao_grupos.csv"));
      main.append(checks("inflation-groups", "Grupos no gráfico", groups.map(s => [s.code,s.modality]), ["1635","1636","1639"]));
      if (state["inflation-groups"].length) chart(main,state["inflation-groups"].map(Number),measure,groupRows,"Evolução dos grupos selecionados");
    } else main.append(message("Sem dados dos grupos neste período."));
  } else main.append(note("Os grupos serão exibidos após a primeira coleta validada do catálogo ampliado."));
  main.append(details("Fontes e como interpretar", note("IBGE: IPCA, IPCA-15, INPC e grupos do IPCA. FGV IBRE: IGP-M e INCC-M. Distribuição: BCB/SGS."), note("IPCA-15 tem janela de coleta e cobertura próprias. INCC-M mede custos de construção e não equivale ao INCC-DI ou INCC-10. Os índices medem cestas diferentes."), note("Acumulados calculados por composição das taxas mensais, antes do filtro de período. No ano: janeiro até a referência; em 12 meses: doze meses consecutivos completos. Lacunas não são preenchidas. Arredondamentos podem gerar pequenas diferenças frente aos acumulados oficiais."), el("ul", {}, specs.map(s => el("li", {}, link(s.short_name || s.name,s.source_url))))));
}

function comparison() {
  main.append(
    note(
      "Compare trajetórias relativas usando o mesmo mês-base. Até seis indicadores, com cores distintas.",
    ),
  );
  const available = data.catalog.filter((s) => s.measure_type !== "variation");
  main.append(
    checks(
      "comparison-codes",
      "Indicadores",
      available.map((s) => [s.code, s.name]),
      ["20539", "20631", "20714"],
    ),
    period("comparison"),
  );
  const codes = state["comparison-codes"].map(Number);
  if (codes.length < 2 || codes.length > 6) {
    main.append(message("Selecione de dois a seis indicadores."));
    return;
  }
  const result = compareBase100(filtered("comparison", data.rows), codes);
  if (!result.base) {
    main.append(
      message(
        "Não há mês comum com valores válidos e diferentes de zero. Ajuste o período ou os indicadores.",
      ),
    );
    return;
  }
  main.append(
    note(
      `Mês-base comum: ${month(result.base)} = 100. O gráfico começa no primeiro mês do recorte em que todas as séries têm valor válido e diferente de zero.`,
    ),
  );
  chart(main, codes, "base100", result.rows, "Evolução relativa · base 100");
  main.append(
    note(
      "Índice = valor original ÷ valor no mês-base × 100. 120 significa alta de 20% em relação à base, não 20 pontos percentuais. A normalização não corrige inflação, sazonalidade ou diferenças de conceito. Lacunas permanecem vazias; o fim do histórico pode variar por série.",
    ),
  );
  if (result.rows.some((r) => r.date === result.base && r.original < 0))
    main.append(
      message(
        "Há denominador negativo no mês-base: a direção do índice se inverte em relação ao valor original. Interprete com cautela.",
        "alert",
      ),
    );
  const exported = result.rows.map((r) => ({
    code: r.code,
    name: byCode.get(r.code).name,
    date: r.date,
    original: r.original,
    original_unit: byCode.get(r.code).unit,
    base100: r.base100,
    base_month: result.base,
    snapshot_id: data.manifest.snapshot_id,
  }));
  main.append(
    download("Baixar comparação · CSV", exported, "comparacao_base100.csv"),
    details("Ver valores comparados", table(exported)),
    note(
      "Taxas mensais de inflação não são indexadas nesta comparação; consulte seus acumulados no explorador.",
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
    reference_period: spec.frequency === "Q" ? quarter(r.date) : month(r.date),
    frequency: spec.frequency,
    name: spec.name,
    unit: spec.unit,
    original: r.original,
    ...(metricName === "original" ? {} : { [metricName]: r[metricName] }),
    transformed_unit: unit(spec, metricName, data.manifest),
    source: spec.source || "Banco Central do Brasil / SGS",
    source_url: spec.source_url,
    snapshot_id: data.manifest.snapshot_id,
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
      "Compare dois indicadores e explore a associação entre referências mensais. PIB trimestral fica fora desta análise de defasagens mensais.",
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
        data.catalog.filter(s => s.frequency !== "Q").map((s) => [s.code, s.name]),
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
          {title:"Relações e defasagens", source:`Fonte: BCB/SGS · X: ${state["relation-x"]} (${data.labels[state["relation-xm"]]}) · Y: ${state["relation-y"]} (${data.labels[state["relation-ym"]]}) · Defasagem de X: ${state.lag} meses`, period:month(pairs[0].date)+"–"+month(pairs.at(-1).date),asOf:data.manifest.as_of},
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
            spec.frequency === "Q" ? "Trimestral" : spec.frequency === "D" ? "Diária" : "Mensal",
          ],
          ["Periodicidade no painel", spec.frequency === "Q" ? "Trimestral" : "Mensal"],
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
        "Fonte: " + (spec.source || "Banco Central do Brasil / SGS"),
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
          ? Math.floor((today - (s.frequency === "Q" ? Date.parse(monthDate(monthNumber(last.date)+3))-86400000 : Date.parse(last.date))) / 86400000)
          : null;
      return {
        code: s.code,
        name: s.name,
        last: last ? (s.frequency === "Q" ? quarter(last.date) : month(last.date)) : "—",
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
      ["last", "Última referência"],
      ["lag", "Dias desde a referência"],
      ["limit", "Limite operacional (dias)"],
      ["status", "Situação"],
    ]),
    note(
      "Dias desde o início do mês ou encerramento do trimestre de referência. Limites do catálogo são critérios operacionais, não prazos oficiais. Coleta sem observação nova não comprova atraso do Bacen.",
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
    if (readShare(a.hash).page === page) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  main.append(
    el("h2", {}, pages.find(([key]) => key === page)[1]),
    note(
      "As referências variam por indicador. A Selic considera apenas meses concluídos.",
    ),
  );
  main.append(details("Opções de exportação",
    select("csv-profile", "Formato dos arquivos CSV", [["excel", "Excel em português"], ["analysis", "CSV para análise"]], "excel"),
    note("Excel em português: ponto e vírgula entre colunas, vírgula decimal e cabeçalhos em português. CSV para análise: vírgula entre colunas, ponto decimal e nomes de campos estáveis. Ambos preservam acentos, datas ISO e a precisão dos valores; células vazias indicam ausência."),
    note("CSV não guarda cores nem larguras de coluna. Para uma planilha formatada e identificadores como texto, baixe Excel no Explorador. Ao importar CSV, defina códigos e identificadores como texto para preservar zeros à esquerda.")));
  try {
    ({
      panorama,
      overview,
      inflation,
      labor,
      external,
      activity,
      comparison,
      credit,
      composition,
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
  const hash = shareHash(page, state);
  if (location.hash !== hash) history.replaceState(null, "", hash);
  for (const [key] of pages) {
    const anchor = document.querySelector(`nav a[data-page="${key}"]`);
    if (anchor) anchor.href = shareHash(key, state);
  }
  const sharedURL = location.href;
  const field = el("input", { id: "share-url", type: "text", readonly: true, value: sharedURL, onclick: (e) => e.target.select() });
  const status = el("p", { role: "status", id: "share-status" });
  main.append(details("Compartilhar análise",
    el("button", { type: "button", id: "copy-analysis", onclick: async () => {
      try {
        await navigator.clipboard.writeText(sharedURL);
        status.textContent = "Link copiado.";
      } catch {
        field.focus(); field.select();
        status.textContent = "Selecione e copie o link abaixo.";
      }
    } }, "Copiar link da análise"),
    el("label", { for: "share-url" }, "Link com os filtros selecionados", field), status,
    note("O link preserva os filtros e usa a base disponível ao abrir. Revisões futuras podem alterar os valores; exporte os dados para guardar esta coleta.")));
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
        `${data.manifest.series} séries · ${number(data.manifest.rows, 0)} observações`,
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
const themeButton = document.getElementById("theme-toggle");
function syncThemeButton() {
  const dark = document.documentElement.dataset.theme === "dark";
  const label = dark ? "Ativar modo claro" : "Ativar modo escuro";
  themeButton.setAttribute("aria-label", label);
  themeButton.setAttribute("title", label);
  themeButton.setAttribute("aria-pressed", String(dark));
  themeButton.replaceChildren(el("span", { "aria-hidden": true }, dark ? "☀" : "☾"));
}
syncThemeButton();
themeButton.addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("observatorio-theme", theme); } catch { /* The toggle still works without storage. */ }
  syncThemeButton();
  render();
});
for (const [key, label] of pages)
  document.getElementById("nav").append(el("a", { href: "#" + key, "data-page": key }, label));
window.addEventListener("hashchange", () => {
  const restored = readShare(location.hash);
  for (const key of pageKeys[restored.page]) delete state[key];
  Object.assign(state, restored.state);
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

