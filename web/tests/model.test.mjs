import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  rebase,
  periodRows,
  lagPairs,
  pearson,
  subtract,
  compareCollections,
  health,
  csv,
} from "../src/model.js";
const config = JSON.parse(
  await readFile(new URL("../generated/site.json", import.meta.url)),
);
const data = JSON.parse(
  await readFile(new URL("../generated/" + config.data, import.meta.url)),
);
const parity = JSON.parse(
  await readFile(new URL("../generated/parity.json", import.meta.url)),
);
for (const c of parity.correlations)
  test(`Paridade Python: ${c.xc}/${c.yc}, lag ${c.lag}`, () => {
    const source = (code) =>
      data.rows
        .filter((r) => r.code === code)
        .map((r) => ({ date: r.date, value: r[c.metric] }));
    const pairs = lagPairs(source(c.xc), source(c.yc), c.lag, c.start, c.end);
    assert.deepEqual(pairs, c.pairs);
    const r = pearson(pairs);
    if (c.r === null) assert.equal(r, null);
    else assert.ok(Math.abs(r - c.r) < 1e-12);
  });
for (const [i, c] of parity.comparisons.entries())
  test("Revisões equivalentes ao Python " + i, () => {
    const sort = (rows) =>
      rows.sort(
        (a, b) =>
          String(a.code).localeCompare(String(b.code)) ||
          a.reference_date.localeCompare(b.reference_date),
      );
    assert.deepEqual(
      sort(
        compareCollections(data.history, data.history_meta, c.earlier, c.later),
      ),
      sort(c.expected),
    );
  });
test("Base 100 respeita recorte, ausência e zero", () => {
  const rows = [
    { date: "2020-01-01", original: 10 },
    { date: "2020-02-01", original: null },
    { date: "2020-03-01", original: 20 },
    { date: "2020-04-01", original: 40 },
  ];
  assert.deepEqual(
    rebase(periodRows(rows, "2020-02-01", "2020-04-01")).map((r) => r.base100),
    [null, 100, 200],
  );
  assert.deepEqual(
    rebase([{ original: 0 }, { original: 2 }]).map((r) => r.base100),
    [null, null],
  );
  assert.deepEqual(rebase([]), []);
  assert.throws(() => periodRows(rows, "2021", "2020"));
});
test("Defasagem usa mês calendário e não posição", () => {
  const x = [
      { date: "2020-01-01", value: 5 },
      { date: "2020-03-01", value: 8 },
    ],
    y = [
      { date: "2020-03-01", value: 2 },
      { date: "2020-04-01", value: 3 },
    ];
  assert.deepEqual(lagPairs(x, y, 1, "2020-01-01", "2020-12-01"), [
    { date: "2020-04-01", x: 8, y: 3 },
  ]);
  assert.throws(() => lagPairs(x, y, 25, "", ""));
  assert.equal(
    pearson(Array.from({ length: 12 }, () => ({ x: 1, y: 1 }))),
    null,
  );
  assert.equal(pearson([{ x: 1, y: 2 }]), null);
});
test("Decimais exatos, adições, revisões anuladas e continuidade", () => {
  assert.equal(subtract("9007199254740993.001", "9007199254740993"), "0.001");
  assert.equal(subtract("0.1", "0.3"), "-0.2");
  const meta = {
    baseline_snapshot_id: "a",
    comparisons: [{ snapshot_id: "b" }, { snapshot_id: "c" }],
  };
  const base = {
    code: "1",
    name: "Teste",
    reference_date: "2020-01-01",
    unit: "%",
    difference_unit: "p.p.",
  };
  const events = [
    { ...base, snapshot_id: "b", old_value: "1", new_value: "2" },
    { ...base, snapshot_id: "c", old_value: "2", new_value: "1" },
  ];
  assert.deepEqual(compareCollections(events, meta, "a", "c"), []);
  events[0].old_value = "";
  assert.equal(
    compareCollections(events, meta, "a", "c")[0].event_type,
    "added_observation",
  );
  events[1].old_value = "3";
  assert.throws(() => compareCollections(events, meta, "a", "c"));
  assert.throws(() => compareCollections([], meta, "c", "a"));
});
test("Monitoramento diferencia falha, execução ausente e estado desconhecido", () => {
  const now = Date.parse("2026-11-03T12:00:00Z"),
    manifest = { created_at: "2026-11-03T00:00:00Z" };
  assert.equal(health({ status: "failed" }, manifest, now)[0], "failed");
  assert.equal(health(null, manifest, now)[0], "unknown");
  assert.equal(
    health({ status: "success" }, manifest, now + 31 * 3600000)[0],
    "stale",
  );
  assert.equal(health({ status: "running" }, manifest, now)[0], "running");
});
test("CSV preserva decimais e protege fórmulas", () => {
  const result = csv([
    { value: '=HYPERLINK("x")', negative: -1.2, zero: 0, empty: null },
  ]);
  assert.match(result, /'=HYPERLINK/);
  assert.match(result, /"-1.2","0",""/);
});
