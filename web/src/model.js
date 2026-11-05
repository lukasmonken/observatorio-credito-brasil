export const eventLabels = {
  revision: "Revisão de valor",
  new_observation: "Nova referência",
  historical_fill: "Preenchimento histórico",
  new_series: "Série incluída",
};
export const colors = [
  "#285c50",
  "#526f9d",
  "#a16b36",
  "#805b83",
  "#637445",
  "#9b5555",
];
export const finite = (value) =>
  typeof value === "number" && Number.isFinite(value);
export const monthNumber = (date) =>
  Number(date.slice(0, 4)) * 12 + Number(date.slice(5, 7)) - 1;
export const monthDate = (month) =>
  `${Math.floor(month / 12)}-${String((month % 12) + 1).padStart(2, "0")}-01`;
export function periodRows(rows, start, end) {
  if (!start || !end || start > end)
    throw new Error("Selecione um período válido.");
  return rows.filter((r) => r.date >= start && r.date <= end);
}
export function rebase(rows) {
  const first = rows.find((r) => finite(r.original));
  return rows.map((r) => ({
    ...r,
    base100:
      first && first.original !== 0 && finite(r.original)
        ? (r.original / first.original) * 100
        : null,
  }));
}
export function unit(spec, metric, manifest) {
  if (["mom_pct", "yoy_pct", "real_yoy_pct", "inflation12", "inflation_ytd"].includes(metric))
    return "%";
  if (["diff_pp", "diff12_pp"].includes(metric)) return "p.p.";
  if (metric === "base100") return "índice base 100";
  if (metric === "real")
    return `R$ milhões de ${manifest.price_base_month?.slice(0, 7) || "base indisponível"}`;
  return spec.unit;
}
export function lagPairs(x, y, lag, start, end) {
  if (!Number.isInteger(lag) || lag < 0 || lag > 24)
    throw new Error("Defasagem inválida.");
  const byMonth = new Map(x.map((r) => [monthNumber(r.date), r.value]));
  return y
    .filter((r) => r.date >= start && r.date <= end)
    .flatMap((r) => {
      const value = byMonth.get(monthNumber(r.date) - lag);
      return finite(value) && finite(r.value)
        ? [{ date: r.date, x: value, y: r.value }]
        : [];
    });
}
export function pearson(pairs) {
  if (pairs.length < 12) return null;
  const n = pairs.length,
    ax = pairs.reduce((a, p) => a + p.x, 0) / n,
    ay = pairs.reduce((a, p) => a + p.y, 0) / n;
  let xx = 0,
    yy = 0,
    xy = 0;
  for (const p of pairs) {
    const x = p.x - ax,
      y = p.y - ay;
    xx += x * x;
    yy += y * y;
    xy += x * y;
  }
  return xx > 0 && yy > 0
    ? Math.max(-1, Math.min(1, xy / Math.sqrt(xx * yy)))
    : null;
}
function decimal(value) {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(value));
  if (!match) throw new Error("Valor decimal inválido.");
  return {
    n: BigInt((match[1] || "") + match[2] + (match[3] || "")),
    scale: (match[3] || "").length,
  };
}
export function subtract(a, b) {
  const x = decimal(a),
    y = decimal(b),
    s = Math.max(x.scale, y.scale);
  const diff =
    x.n * 10n ** BigInt(s - x.scale) - y.n * 10n ** BigInt(s - y.scale);
  const sign = diff < 0n ? "-" : "",
    digits = (diff < 0n ? -diff : diff).toString().padStart(s + 1, "0");
  return sign + (s ? digits.slice(0, -s) + "." + digits.slice(-s) : digits);
}
export const equalDecimal = (a, b) => decimal(subtract(a, b)).n === 0n;
export function compareCollections(history, meta, earlier, later) {
  if (!meta) throw new Error("Histórico indisponível.");
  const ids = [
      meta.baseline_snapshot_id,
      ...meta.comparisons.map((c) => c.snapshot_id),
    ],
    a = ids.indexOf(earlier),
    b = ids.indexOf(later);
  if (a < 0 || b < 0 || a >= b)
    throw new Error("Escolha uma coleta inicial anterior à coleta final.");
  const selected = new Map(
    ids.slice(a + 1, b + 1).map((id, index) => [id, index]),
  );
  const events = history
    .filter((e) => selected.has(e.snapshot_id))
    .sort((x, y) => selected.get(x.snapshot_id) - selected.get(y.snapshot_id));
  const groups = new Map();
  for (const event of events) {
    const key = `${event.code}/${event.reference_date}`;
    if (!groups.has(key)) groups.set(key, { first: event, last: event });
    else {
      const group = groups.get(key);
      if (
        !event.old_value ||
        !equalDecimal(event.old_value, group.last.new_value)
      )
        throw new Error("Valores intermediários inconsistentes no histórico.");
      group.last = event;
    }
  }
  const result = [];
  for (const { first, last } of groups.values()) {
    if (first.old_value !== "" && equalDecimal(first.old_value, last.new_value))
      continue;
    result.push({
      code: last.code,
      name: last.name,
      reference_date: last.reference_date,
      event_type: first.old_value === "" ? "added_observation" : "revision",
      old_value: first.old_value,
      new_value: last.new_value,
      difference:
        first.old_value === "" ? "" : subtract(last.new_value, first.old_value),
      unit: last.unit,
      difference_unit: last.difference_unit,
      previous_snapshot_id: earlier,
      snapshot_id: later,
    });
  }
  return result.sort(
    (x, y) =>
      Number(x.code) - Number(y.code) ||
      x.reference_date.localeCompare(y.reference_date),
  );
}
export function lastChanges(history, meta) {
  if (!meta) return null;
  const comparison = meta.comparisons.at(-1),
    events = history.filter((e) => e.snapshot_id === comparison.snapshot_id);
  return {
    ...comparison,
    events,
    series_count: new Set(events.map((e) => e.code)).size,
  };
}
export function health(monitor, manifest, now = Date.now()) {
  const success = monitor?.last_success_at || manifest.created_at,
    age = (now - Date.parse(success)) / 3600000;
  if (!Number.isFinite(age) || age < -1)
    return ["unknown", "Horário de atualização inconsistente."];
  if (age > 30)
    return [
      "stale",
      "Sem atualização validada há mais de 30 horas. A última base válida continua disponível.",
    ];
  if (["failed", "cancelled"].includes(monitor?.status))
    return [
      "failed",
      "A última tentativa de atualização falhou ou foi interrompida. A última base válida foi preservada.",
    ];
  if (monitor?.status === "running")
    return [
      "running",
      "Atualização em andamento. Os dados exibidos são da última base válida.",
    ];
  if (!monitor) return ["unknown", "Detalhes operacionais indisponíveis."];
  return ["ok", "Última coleta concluída com sucesso."];
}
export function csv(rows, columns) {
  const keys = columns || Object.keys(rows[0] || {});
  const value = (v) => {
    let s = v == null ? "" : String(v);
    if (/^[=+@\t\r]/.test(s) || /^-[^\d.]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"', '""') + '"';
  };
  return (
    "\ufeff" +
    [
      keys.map(value).join(","),
      ...rows.map((r) => keys.map((k) => value(r[k])).join(",")),
    ].join("\r\n")
  );
}

export function compareBase100(rows, codes) {
  codes = [...new Set(codes)];
  if (!codes.length) return { rows: [], base: null };
  const selected = rows.filter((r) => codes.includes(r.code));
  const months = new Map();
  for (const row of selected) {
    if (!months.has(row.date)) months.set(row.date, new Map());
    months.get(row.date).set(row.code, row.original);
  }
  const base = [...months.keys()]
    .sort()
    .find((date) =>
      codes.every(
        (code) =>
          finite(months.get(date).get(code)) &&
          months.get(date).get(code) !== 0,
      ),
    );
  if (!base) return { rows: [], base: null };
  return {
    base,
    rows: selected
      .filter((r) => r.date >= base)
      .map((r) => {
        const value = finite(r.original)
          ? (r.original / months.get(base).get(r.code)) * 100
          : null;
        return { ...r, base100: finite(value) ? value : null };
      })
      .sort((a, b) => a.date.localeCompare(b.date) || a.code - b.code),
  };
}
