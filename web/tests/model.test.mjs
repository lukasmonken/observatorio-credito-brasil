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

test("Excel mantém zero, ausência e texto sem fórmulas executáveis", async () => {
  const { excelFile } = await import("../src/excel.js"),
    { default: ExcelJS } = await import("exceljs");
  const spec = { ...data.catalog[0], name: "=1+1" },
    rows = [
      { code: spec.code, date: "2020-01-01", original: 0 },
      { code: spec.code, date: "2020-02-01", original: null },
    ];
  const buffer = await excelFile(data, rows, spec, "original", [
    "2020-01-01",
    "2020-02-01",
  ]);
  const book = new ExcelJS.Workbook();
  await book.xlsx.load(buffer);
  assert.equal(book.getWorksheet("Dados").getCell("D2").value, 0);
  assert.equal(book.getWorksheet("Dados").getCell("D3").value, null);
  assert.equal(book.getWorksheet("Dados").getCell("C2").value, "=1+1");
  for (const sheet of book.worksheets)
    sheet.eachRow((row) =>
      row.eachCell((cell) => assert.equal(cell.formula, undefined)),
    );
});

test("Comparação base 100 usa mês comum e equivale ao Python", async () => {
  const { compareBase100 } = await import("../src/model.js");
  const expected = JSON.parse(
    await readFile(
      new URL("../generated/base100-parity.json", import.meta.url),
    ),
  );
  const actual = compareBase100(
    periodRows(data.rows, "2018-01-01", "2025-06-01"),
    [20539, 20631, 20714],
  );
  assert.equal(actual.base, expected.base);
  assert.equal(actual.rows.length, expected.rows.length);
  actual.rows.forEach((r, i) => {
    const e = expected.rows[i];
    assert.equal(r.date, e.date);
    assert.equal(r.code, e.code);
    if (e.base100 === null) assert.equal(r.base100, null);
    else assert.ok(Math.abs(r.base100 - e.base100) < 1e-10);
  });
  const rows = [
    { code: 1, date: "2020-01-01", original: 10 },
    { code: 1, date: "2020-02-01", original: 20 },
    { code: 2, date: "2020-02-01", original: 4 },
    { code: 1, date: "2020-03-01", original: null },
    { code: 2, date: "2020-03-01", original: 8 },
  ];
  assert.deepEqual(
    compareBase100(rows, [1, 2]).rows.map((r) => r.base100),
    [100, 100, null, 200],
  );
  assert.equal(compareBase100(rows, [1, 9]).base, null);
  assert.equal(compareBase100(rows, []).base, null);
  rows[2].original = 0;
  assert.equal(compareBase100(rows, [1, 2]).base, null);
});

test("Links preservam filtros, listas vazias, Unicode e defasagem zero", async () => {
  const { readShare, shareHash, pageKeys } = await import("../src/share.js");
  const examples = {
    inflation: { "inflation-codes": ["433","7456"], "inflation-groups": ["1635"], "inflation-metric": "inflation_ytd", "inflation-group-month": "2025-02-01", inflationstart: "2025-01-01", inflationend: "2025-12-01" },
    credit: { segment: "PF", "credit-PF": ["20540", "20716"], "credit-view": "combined", creditstart: "2020-01-01" },
    comparison: { "comparison-codes": [], comparisonstart: "2020-01-01", comparisonend: "2021-02-01" },
    explorer: { "explorer-code": "20539", "explorer-metric": "base100" },
    relations: { lag: 0, "relation-x": "432", "relation-y": "21084" },
    revisions: { "revision-types": ["revision"], "compare-initial": "abc123" },
    dictionary: { "dictionary-search": "Inflação & crédito + juros? #Brasil", "dictionary-code": "433" },
  };
  for (const page of Object.keys(pageKeys)) {
    const state = examples[page] || {};
    assert.deepEqual(readShare(shareHash(page, state)), { page, state });
  }
  assert.deepEqual(readShare("#explorer"), { page: "explorer", state: {} });
});
test("Links inválidos ignoram chaves desconhecidas, tipos incorretos e datas impossíveis", async () => {
  const { readShare } = await import("../src/share.js");
  assert.deepEqual(readShare('#comparison?v=1&comparison-codes=%7B%7D&comparisonstart=2020-02-31&__proto__=x').state, {});
  assert.deepEqual(readShare('#relations?v=1&lag=99').state, {});
  assert.deepEqual(readShare('#relations?v=1&lag=%22hello%22').state, {});
  assert.deepEqual(readShare('#explorer?v=2&explorer-code=433').state, {});
  assert.equal(readShare('#constructor?v=1').page, 'overview');
  assert.equal(readShare('#not-a-page').page, 'overview');
});

test("Composição usa total do segmento no mesmo mês e preserva ausência e zero", async () => {
  const {compositionRows} = await import("../src/model.js");
  const specs = [{code:1,credit_composition:true,segment:"PF",modality:"A"},{code:2,credit_composition:true,segment:"PF",modality:"B"}];
  const rows=[{code:20541,date:"2025-01-01",original:100},{code:1,date:"2025-01-01",original:25},{code:20541,date:"2025-02-01",original:200},{code:2,date:"2025-02-01",original:0}];
  assert.deepEqual(compositionRows(rows,specs,"PF").map(r=>r.share),[25,null,null,0]);
  for (const total of [0,null,-1,20]) assert.equal(compositionRows([{code:20541,date:"2025-01-01",original:total},rows[1]],specs,"PF")[0].share,null);
  assert.throws(()=>compositionRows([...rows,rows[0]],specs,"PF"),/duplicadas/);
  assert.deepEqual(compositionRows(rows,specs,"PJ"),[]);
});

test("Trabalho e renda preserva trimestre móvel, ausências e unidades", async () => {
  const { laborPeriod, laborExport } = await import("../src/labor.js");
  assert.equal(laborPeriod("2026-01-01"), "11/2025–01/2026");
  const specs = [{code:24369, name:"Desocupação", unit:"%", measure_type:"rate"}, {code:24382,name:"Rendimento",unit:"R$",measure_type:"income_real"}];
  const rows = laborExport([{code:24369,date:"2026-01-01",original:0,diff12_pp:-2},{code:24382,date:"2026-01-01",original:null,yoy_pct:null}], specs, {snapshot_id:"test"}, "2026-08");
  assert.equal(rows[0].value,0);
  assert.equal(rows[0].change_unit,"p.p.");
  assert.equal(rows[0].change12,-2);
  assert.equal(rows[1].value,null);
  assert.equal(rows[1].income_price_base,"2026-08");
  assert.equal(rows[1].change_unit,"%");
  const { shareHash, readShare } = await import("../src/share.js");
  const state = {"labor-code":"24382","labor-metric":"yoy_pct","labor-reference":"2026-01-01",laborstart:"2025-01-01",laborend:"2026-01-01"};
  assert.deepEqual(readShare(shareHash("labor",state)),{page:"labor",state});
});

test("CSV em português preserva precisão, separadores e protege texto", () => {
  const rows = [{code:"00123", name:'Ação; "teste",\nlinha', original:-1234.567891234, zero:0, missing:null, text:"  =1+1"}];
  const localized = csv(rows, undefined, "excel");
  assert.ok(localized.startsWith('\ufeff"Código SGS";"Indicador";"Valor original"'));
  assert.ok(localized.includes('"00123";"Ação; ""teste"",\nlinha";"-1234,567891234";"0";""'));
  assert.ok(localized.includes("'  =1+1"));
  const analysis = csv(rows, undefined, "analysis");
  assert.ok(analysis.includes('"original"'));
  assert.ok(analysis.includes('"-1234.567891234"'));
  assert.throws(() => csv([{value:Infinity}]), /não finito/);
  assert.throws(() => csv(rows, undefined, "invalid"), /Perfil/);
});

test("Composição exportável preserva dados, unidades e lacunas", async () => {
  const {exportFigure} = await import("../src/chart-export.js");
  const traces=[{name:"Série A",type:"scatter",mode:"lines",x:["2026-01-01","2026-02-01","2026-03-01"],y:[0,null,-1.25],yaxis:"y2",line:{color:"#285c50"}}];
  const original=structuredClone(traces);
  const meta={title:"Teste",source:"Fonte: BCB/SGS 432",period:"01/2026–03/2026",asOf:"2026-11-09"};
  const result=exportFigure(traces,{xaxis:{},yaxis:{title:{text:"R$ milhões"}},yaxis2:{title:{text:"%"},overlaying:"y",side:"right"}},meta,{title:"Teste <script>",subtitle:"Ação & crédito",labels:"last",colors:["#abcdef"]});
  assert.deepEqual(traces,original);assert.deepEqual(result.data[0].y,[0,null,-1.25]);assert.equal(result.data[0].yaxis,"y2");
  assert.equal(result.layout.yaxis2.title.text,"%");assert.equal(result.data[0].connectgaps,false);
  assert.deepEqual(result.data[0].text,["","","-1,25"]);assert.match(result.layout.title.text,/&lt;script&gt;/);
  assert.match(result.layout.annotations[0].text,/Fonte: BCB/);
  const many=[{...traces[0],x:Array.from({length:70},(_,i)=>i),y:Array.from({length:70},(_,i)=>i)}];
  const bars=exportFigure(many,{xaxis:{},yaxis:{}},meta,{labels:"all",kind:"bar"});
  assert.equal(bars.data[0].type,"bar");assert.ok(bars.notice);assert.equal(bars.data[0].text.filter(Boolean).length,1);
});
