import indicators from "../../observatorio/panorama.json" with { type: "json" };
import { finite } from "./model.js";
import { laborPeriod } from "./labor.js";
export { indicators };
export function panoramaRows(rows, catalog) {
  return indicators.map(item => {
    const latest = rows.filter(r => r.code === item.code && finite(r.original))
      .sort((a,b) => a.date.localeCompare(b.date)).at(-1);
    return {...item, date:latest?.date ?? null,
      value:finite(latest?.[item.metric]) ? latest[item.metric] : null,
      source_url:catalog.find(s => s.code === item.code)?.source_url || ""};
  });
}
export function referenceLabel(date, kind) {
  if (!date) return "Sem referência disponível";
  if (kind === "quarter") return `${Math.ceil(Number(date.slice(5,7))/3)}º trimestre de ${date.slice(0,4)}`;
  if (kind === "rolling") return `Trimestre móvel: ${laborPeriod(date)}`;
  return `${date.slice(5,7)}/${date.slice(0,4)}`;
}
