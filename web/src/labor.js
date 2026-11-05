import { finite, monthNumber, monthDate } from "./model.js";

export function laborPeriod(date) {
  if (!date) return "—";
  const start = monthDate(monthNumber(date) - 2);
  return `${start.slice(5, 7)}/${start.slice(0, 4)}–${date.slice(5, 7)}/${date.slice(0, 4)}`;
}

export function laborExport(rows, specs, manifest, incomeBase) {
  const byCode = new Map(specs.map(s => [s.code, s]));
  return rows.filter(r => byCode.has(r.code)).map(r => {
    const s = byCode.get(r.code), rate = s.measure_type === "rate";
    return {
      reference_end: r.date,
      reference_period: laborPeriod(r.date),
      code: r.code,
      indicator: s.short_name || s.name,
      value: finite(r.original) ? r.original : null,
      unit: s.unit,
      change12: (rate ? r.diff12_pp : r.yoy_pct) ?? null,
      change_unit: rate ? "p.p." : "%",
      income_price_base: s.measure_type === "income_real" ? incomeBase : null,
      region: "Brasil",
      source: s.source,
      source_url: s.source_url,
      snapshot_id: manifest.snapshot_id,
    };
  });
}
