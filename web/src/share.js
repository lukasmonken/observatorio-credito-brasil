// Only public, supported controls are serialized. No arbitrary application state.
const periods = (prefix) => [prefix + "start", prefix + "end"];
export const pageKeys = {
  overview: [],
  labor: ["labor-reference", "labor-code", "labor-metric", ...periods("labor")],
  composition: ["composition-segment", "composition-month", "composition-metric", "composition-PF", "composition-PJ", ...periods("composition")],
  inflation: ["inflation-codes", "inflation-groups", "inflation-metric", "inflation-group-month", ...periods("inflation")],
  credit: ["segment", "credit-view", "credit-Total", "credit-PF", "credit-PJ", ...periods("credit")],
  comparison: ["comparison-codes", ...periods("comparison")],
  family: periods("family"),
  explorer: ["explorer-code", "explorer-metric", ...periods("explorer")],
  relations: ["relation-x", "relation-y", "relation-xm", "relation-ym", "lag", ...periods("relations")],
  revisions: ["revision-codes", "revision-types", "revision-start", "revision-end", "compare-initial", "compare-final"],
  dictionary: ["dictionary-search", "dictionary-code"],
  quality: [],
};
const arrays = new Set(["composition-PF", "composition-PJ", "inflation-codes", "inflation-groups", "credit-Total", "credit-PF", "credit-PJ", "comparison-codes", "revision-codes", "revision-types"]);
function valid(key, value) {
  if (arrays.has(key)) {
    if (!Array.isArray(value) || value.length > 100) return undefined;
    if (!value.every((v) => typeof v === "string" && /^[a-z0-9_]{1,40}$/.test(v))) return undefined;
    return [...new Set(value)];
  }
  if (key === "lag") return Number.isInteger(value) && value >= 0 && value <= 24 ? value : undefined;
  if (typeof value !== "string" || value.length > 200) return undefined;
  if (key.endsWith("start") || key.endsWith("end")) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return undefined;
    const date = new Date(value);
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return undefined;
  }
  return value;
}
export function readShare(hash) {
  const [route, query = ""] = hash.replace(/^#/, "").split("?");
  const page = Object.hasOwn(pageKeys, route) ? route : "overview";
  const state = {};
  if (query.length > 16000) return { page, state };
  const params = new URLSearchParams(query);
  if (params.get("v") !== "1") return { page, state };
  for (const key of pageKeys[page]) {
    if (!params.has(key)) continue;
    try {
      const raw = params.get(key);
      const value = valid(key, arrays.has(key) || key === "lag" ? JSON.parse(raw) : raw);
      if (value !== undefined) state[key] = value;
    } catch { /* Invalid individual parameters fall back to the control default. */ }
  }
  return { page, state };
}
export function shareHash(page, state) {
  if (!Object.hasOwn(pageKeys, page)) page = "overview";
  const params = new URLSearchParams({ v: "1" });
  for (const key of pageKeys[page]) {
    const value = valid(key, state[key]);
    if (value !== undefined) params.set(key, arrays.has(key) ? JSON.stringify(value) : String(value));
  }
  return "#" + page + (params.size > 1 ? "?" + params.toString() : "");
}
