import { test, expect } from "@playwright/test";
import ExcelJS from "exceljs";
const pages = [
  "overview",
  "inflation",
  "labor",
  "external",
  "activity",
  "credit",
  "composition",
  "comparison",
  "family",
  "explorer",
  "relations",
  "revisions",
  "dictionary",
  "quality",
];
for (const route of pages)
  test("Página " + route, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    await page.goto("#" + route);
    await expect(page.locator("main h2")).toBeVisible();
    await expect(page.locator("main")).not.toContainText("Não foi possível");
    if (
      ["overview", "credit", "family", "explorer", "relations"].includes(route)
    )
      await expect(page.locator(".js-plotly-plot").first()).toBeVisible();
    expect(errors).toEqual([]);
  });
test("Três séries com cores distintas e seleção interativa", async ({
  page,
}) => {
  await page.goto("#credit");
  await page.locator("#credit-view").selectOption("combined");
  await expect(page.locator(".js-plotly-plot")).toBeVisible();
  await expect
    .poll(() => page.locator(".js-plotly-plot").evaluate((n) => n.data.length))
    .toBe(3);
  const colors = await page
    .locator(".js-plotly-plot")
    .evaluate((n) => n.data.map((t) => t.line.color));
  expect(new Set(colors).size).toBe(3);
  await page.locator(".legendtoggle").first().click();
  await expect
    .poll(() =>
      page.locator(".js-plotly-plot").evaluate((n) => n.data[0].visible),
    )
    .toBe("legendonly");
  await page.locator("#credit-Total-toggle").click();
  await page.locator("fieldset input").first().uncheck();
  await expect
    .poll(() => page.locator(".js-plotly-plot").evaluate((n) => n.data.length))
    .toBe(2);
});
test("Excel exporta recorte com base 100 e quatro abas", async ({ page }) => {
  await page.goto("#explorer");
  await page.locator("#explorer-code").selectOption("20539");
  await page.locator("#explorer-metric").selectOption("base100");
  await page.locator("#explorerstart").fill("2020-01-01");
  await page.locator("#explorerend").fill("2020-06-01");
  const download = page.waitForEvent("download");
  await page.locator("#download-excel").click();
  const file = await download,
    book = new ExcelJS.Workbook();
  await book.xlsx.readFile(await file.path());
  expect(book.worksheets.map((s) => s.name)).toEqual([
    "Dados",
    "Indicador",
    "Metodologia",
    "Coleta",
  ]);
  const sheet = book.getWorksheet("Dados");
  expect(sheet.rowCount).toBe(7);
  expect(sheet.getCell("F2").value).toBe(100);
  expect(sheet.getCell("B2").value.toISOString().slice(0, 10)).toBe(
    "2020-01-01",
  );
  expect(book.getWorksheet("Coleta").getColumn(2).values.join(" ")).toContain(
    "2020-06-01",
  );
});
test("Revisões compara coletas e exporta CSV", async ({ page }) => {
  await page.goto("#revisions");
  await page.getByText("Comparar duas coletas", { exact: true }).click();
  await page.locator("#compare-button").click();
  await expect(page.locator("#comparison-result")).toContainText(
    "Observações com diferença líquida",
  );
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Baixar comparação · CSV", exact: true })
    .click();
  expect((await download).suggestedFilename()).toMatch(/comparacao-.*\.csv/);
});
test("Dicionário busca e estado vazio", async ({ page }) => {
  await page.goto("#dictionary");
  await page.locator("#dictionary-search").fill("433");
  await expect(page.locator("#dictionary-code")).toHaveValue("433");
  await expect(page.locator("main")).toContainText("IBGE");
  await page.locator("#dictionary-search").fill("zzzinexistente");
  await expect(page.locator("main")).toContainText(
    "Nenhum indicador encontrado",
  );
});
for (const width of [1920, 1440, 1366, 390])
  test("Layout sem transbordamento " + width, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ["overview", "credit", "comparison", "explorer", "quality"]) {
      await page.goto("#" + route);
      await expect(page.locator("main h2")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    if (width === 1440) {
      await page.goto("#overview");
      await expect(page.locator(".js-plotly-plot").first()).toBeVisible();
      await page.screenshot({
        path: "test-results/overview-1440.png",
        fullPage: true,
      });
    }
  });
test("Arquivo adulterado não é exibido", async ({ page }) => {
  await page.route("**/data-*.json", (route) =>
    route.fulfill({ status: 200, body: "{}", contentType: "application/json" }),
  );
  await page.goto("");
  await expect(page.getByRole("alert")).toContainText(
    "Não foi possível carregar a base validada",
  );
  await expect(page.locator("main h2")).toHaveCount(0);
});
test("Falha de rede tem mensagem e nova tentativa", async ({ page }) => {
  await page.route("**/site.json", (route) => route.abort());
  await page.goto("");
  await expect(
    page.getByRole("button", { name: "Tentar novamente" }),
  ).toBeVisible();
});

test("Comparação normalizada compartilha base e exporta recorte", async ({
  page,
}) => {
  await page.goto("#comparison");
  await page.locator("#comparisonstart").fill("2020-01-01");
  await page.locator("#comparisonend").fill("2022-01-01");
  await expect(page.locator("main")).toContainText(
    "Mês-base comum: 01/2020 = 100",
  );
  await expect
    .poll(() =>
      page
        .locator(".js-plotly-plot")
        .evaluateAll((nodes) => nodes[0]?.data?.map((t) => t.y[0]) || []),
    )
    .toEqual([100, 100, 100]);
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Baixar comparação · CSV", exact: true })
    .click();
  expect((await download).suggestedFilename()).toBe("comparacao_base100.csv");
  await page.locator("#comparison-codes-toggle").click();
  await page.locator("#comparison-codes-20539").uncheck();
  await page.locator("#comparison-codes-20631").uncheck();
  await expect(page.locator("main")).toContainText(
    "Selecione de dois a seis indicadores",
  );
});

test("Link restaura explorador em nova página e após recarregar", async ({ page, context }) => {
  await page.goto("#explorer");
  await page.locator("#explorer-code").selectOption("20539");
  await page.locator("#explorer-metric").selectOption("base100");
  await page.locator("#explorerstart").fill("2020-01-01");
  await page.locator("#explorerend").fill("2021-01-01");
  await page.getByText("Compartilhar análise", { exact: true }).click();
  const url = await page.locator("#share-url").inputValue();
  const other = await context.newPage();
  await other.goto(url);
  await expect(other.locator("#explorer-code")).toHaveValue("20539");
  await expect(other.locator("#explorer-metric")).toHaveValue("base100");
  await expect(other.locator("#explorerstart")).toHaveValue("2020-01-01");
  await expect(other.locator("#explorerend")).toHaveValue("2021-01-01");
  await other.reload();
  await expect(other.locator("#explorer-metric")).toHaveValue("base100");
  await expect(other.locator(".js-plotly-plot")).toBeVisible();
  const traces = await other.locator(".js-plotly-plot").evaluate(n => n.data);
  expect(traces[0].y[0]).toBe(100);
});
test("Link restaura comparação, navegação voltar e fallback de cópia", async ({ page }) => {
  await page.goto("#comparison");
  await page.locator("#comparisonstart").fill("2020-01-01");
  await page.locator("#comparison-codes-toggle").click();
  await page.locator("#comparison-codes-20714").uncheck();
  const url = page.url();
  await page.getByRole("link", { name: "Explorador de indicadores", exact: true }).click();
  await expect(page.locator("#explorer-code")).toBeVisible();
  await page.goBack();
  await expect(page.locator("#comparisonstart")).toHaveValue("2020-01-01");
  await expect(page.locator("#comparison-codes-20714")).not.toBeChecked();
  await page.goto(url);
  await expect(page.locator("#comparison-codes-20714")).not.toBeChecked();
  await page.getByText("Compartilhar análise", { exact: true }).click();
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async (text) => { window.copiedAnalysis = text; } } }));
  await page.locator("#copy-analysis").click();
  await expect(page.locator("#share-status")).toHaveText("Link copiado.");
  expect(await page.evaluate(() => window.copiedAnalysis)).toBe(page.url());
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: () => Promise.reject(new Error("blocked")) } }));
  await page.locator("#copy-analysis").click();
  await expect(page.locator("#share-status")).toContainText("Selecione e copie");
  await expect(page.locator("#share-url")).toHaveValue(page.url());
});
test("Parâmetros inválidos não quebram controles", async ({ page }) => {
  await page.goto("#comparison?v=1&comparison-codes=%7B%7D&comparisonstart=2020-02-31");
  await expect(page.locator(".js-plotly-plot")).toBeVisible();
  await expect(page.locator("#comparison-codes-20539")).toBeChecked();
  await page.goto("#relations?v=1&lag=999&relation-x=bad");
  await expect(page.locator("#lag")).toHaveValue("6");
  await expect(page.locator("main")).not.toContainText("Não foi possível");
});

for (const width of [1440, 390]) test("Menu de indicadores compacto " + width, async ({ page }) => {
  await page.setViewportSize({width, height: 900});
  await page.goto("#comparison");
  const menu = page.locator(".picker-menu");
  await expect(menu).not.toHaveAttribute("open");
  await expect(page.locator(".picker-tag")).toHaveCount(3);
  await page.locator("#comparison-codes-toggle").click();
  await page.locator("#comparison-codes-search").fill("selic");
  await expect(page.locator(".picker-option")).toHaveCount(1);
  await page.locator(".picker-option input").check();
  await expect(page.locator("#comparison-codes-search")).toHaveValue("selic");
  await expect(page.locator(".picker-tag")).toHaveCount(4);
  await page.locator("#comparison-codes-search").fill("");
  await page.locator("#comparison-codes-20540").check();
  await page.locator("#comparison-codes-20541").check();
  await expect(page.locator(".picker-tag")).toHaveCount(6);
  await expect(page.locator(".picker-option input:not(:checked):not(:disabled)")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: `test-results/picker-open-${width}.png`, fullPage: true});
  await page.keyboard.press("Escape");
  await expect(menu).not.toHaveAttribute("open");
  await expect(page.locator("#comparison-codes-toggle")).toBeFocused();
  await page.locator(".picker-tag button").last().click();
  await expect(page.locator(".picker-tag")).toHaveCount(5);
  await page.locator("#comparison-codes-toggle").click();
  await page.locator("#comparison-codes-search").fill("zzzinexistente");
  await expect(page.locator(".picker-options")).toContainText("Nenhum indicador encontrado");
  await page.locator("h2").click();
  await expect(menu).not.toHaveAttribute("open");
  await expect(page.locator(".js-plotly-plot")).toBeVisible();
  await page.screenshot({path: `test-results/picker-closed-${width}.png`, fullPage: true});
});

for (const width of [1440, 390]) test("Tema escuro preserva filtros e preferência " + width, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  await page.goto("#comparison");
  await page.locator("#comparisonstart").fill("2020-01-01");
  const url = page.url();
  await page.getByRole("button", { name: "Ativar modo escuro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("#theme-toggle")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#comparisonstart")).toHaveValue("2020-01-01");
  expect(page.url()).toBe(url);
  await expect.poll(() => page.locator(".js-plotly-plot").evaluateAll(nodes => nodes[0]?.layout?.paper_bgcolor)).toBe("#151515");
  await page.locator("#comparison-codes-toggle").click();
  await page.screenshot({ path: `test-results/dark-picker-${width}.png`, fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("link", {name: "Relações e defasagens", exact: true}).click();
  await expect.poll(() => page.locator(".js-plotly-plot").evaluateAll(nodes => nodes[0]?.layout?.paper_bgcolor)).toBe("#151515");
  await page.getByRole("button", { name: "Ativar modo claro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect.poll(() => page.locator(".js-plotly-plot").evaluateAll(nodes => nodes[0]?.layout?.paper_bgcolor)).toBe("#fff");
  expect(await page.evaluate(() => localStorage.getItem("observatorio-theme"))).toBe("light");
});
test("Tema funciona com armazenamento bloqueado", async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => { throw new Error("blocked"); };
    Storage.prototype.setItem = () => { throw new Error("blocked"); };
  });
  await page.goto("#overview");
  await page.getByRole("button", {name: "Ativar modo escuro"}).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
});

test("Boletim da coleta exibe identificação e exporta Markdown", async ({ page }) => {
  await page.goto("#overview");
  await page.getByText("Boletim da coleta", {exact: true}).click();
  await expect(page.locator("main")).toContainText("Novas referências e variações mensais");
  const download = page.waitForEvent("download");
  await page.locator("#download-bulletin").click();
  const file = await download;
  const {readFile} = await import("node:fs/promises");
  const text = await readFile(await file.path(), "utf8");
  expect(text).toContain("# Boletim da coleta");
  expect(text).toContain("Coleta anterior:");
  expect(file.suggestedFilename()).toMatch(/^boletim-.+\.md$/);
  await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
});

test("Inflação: catálogo ampliado, acumulados, grupos, exportação e tema", async ({ page }) => {
  // Deterministic test-only data; never published as observations.
  const {readFile} = await import("node:fs/promises");
  const {createHash} = await import("node:crypto");
  const config = JSON.parse(await readFile(new URL("../generated/site.json", import.meta.url), "utf8"));
  const payload = JSON.parse(await readFile(new URL("../generated/" + config.data, import.meta.url), "utf8"));
  payload.catalog = JSON.parse(await readFile(new URL("../../catalog.json", import.meta.url), "utf8"));
  const inflation = payload.catalog.filter(s => s.classification === "Inflação");
  payload.rows = payload.rows.filter(r => !inflation.some(s => s.code === r.code));
  for (const spec of inflation) for (let i=0; i<24; i++) {
    payload.rows.push({code:spec.code, date:`${2024+Math.floor(i/12)}-${String(i%12+1).padStart(2,"0")}-01`, original:1, inflation_ytd:(1.01**(i%12+1)-1)*100, inflation12:i<11?null:(1.01**12-1)*100});
  }
  payload.manifest.rows=payload.rows.length;
  payload.manifest.series=payload.catalog.length;
  const body=JSON.stringify(payload), hash=createHash("sha256").update(body).digest("hex");
  const fixtureName = `data-${hash.slice(0,16)}.json`;
  await page.route("**/site.json", route => route.fulfill({json:{...config,data:fixtureName,sha256:hash}}));
  await page.route("**/"+fixtureName, route => route.fulfill({body,contentType:"application/json"}));
  await page.goto("#inflation");
  await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
  await expect(page.locator(".inflation-kpis .kpi")).toHaveCount(5);
  await page.locator("#inflation-metric").selectOption("inflation_ytd");
  await expect(page.locator(".inflation-kpis")).toContainText("12,68");
  await page.locator("#inflation-group-month").selectOption("2025-01-01");
  await expect(page.locator("main")).toContainText("Alimentação e bebidas");
  const download=page.waitForEvent("download");
  await page.getByRole("button",{name:"Baixar grupos · CSV",exact:true}).click();
  const file=await download;
  const csv=await readFile(await file.path(),"utf8");
  expect(csv).toContain("2025-01-01");
  expect(csv).toContain("Acumulado em 12 meses (%)");
  expect(csv).toContain("IBGE");
  await page.screenshot({path:"test-results/inflation-desktop.png",fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.getByRole("button",{name:"Ativar modo escuro"}).click();
  await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await page.screenshot({path:"test-results/inflation-mobile-dark.png",fullPage:true});
  await page.locator("#inflation-codes-toggle").click();
  await page.locator("#inflation-codes-search").fill("INCC");
  await expect(page.locator("#inflation-codes-7456")).toBeVisible();
  await page.locator("#inflation-codes-7456").uncheck();
  await expect.poll(()=>page.locator(".js-plotly-plot").first().evaluate(n=>n.data.length)).toBe(4);
  await page.locator("#inflationstart").fill("2025-03-01");
  await page.locator("#inflationend").fill("2025-01-01");
  await expect(page.locator("main")).toContainText("Selecione um período válido.");
});

test("Composição: modalidades PF/PJ, participação, CSV e dispositivo móvel", async ({page}) => {
  const {readFile}=await import("node:fs/promises"), {createHash}=await import("node:crypto");
  const config=JSON.parse(await readFile(new URL("../generated/site.json",import.meta.url),"utf8"));
  const payload=JSON.parse(await readFile(new URL("../generated/"+config.data,import.meta.url),"utf8"));
  payload.catalog=JSON.parse(await readFile(new URL("../../catalog.json",import.meta.url),"utf8"));
  const modalities=payload.catalog.filter(s=>s.credit_composition);
  const codes=[20540,20541,...modalities.map(s=>s.code)];
  payload.rows=payload.rows.filter(r=>!codes.includes(r.code));
  for (const code of codes) for (const date of ["2025-01-01","2025-02-01"]) payload.rows.push({code,date,original:code===20540||code===20541?1000:100});
  payload.manifest.rows=payload.rows.length;payload.manifest.series=payload.catalog.length;
  const body=JSON.stringify(payload),hash=createHash("sha256").update(body).digest("hex"),filename=`data-${hash.slice(0,16)}.json`;
  await page.route("**/site.json",r=>r.fulfill({json:{...config,data:filename,sha256:hash}}));
  await page.route("**/"+filename,r=>r.fulfill({body,contentType:"application/json"}));
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("#composition");
  await expect(page.locator("main")).toContainText("Consignado");
  await expect(page.locator("main table")).toContainText("10,00");
  await page.locator("#composition-metric").selectOption("share");
  await expect(page.locator(".js-plotly-plot")).toHaveCount(1);
  await expect.poll(()=>page.locator(".js-plotly-plot").evaluate(n=>n.data[0].y[0])).toBe(10);
  await page.locator("#composition-segment").selectOption("PJ");
  await expect(page.locator("main table")).toContainText("Capital de giro");
  const pending=page.waitForEvent("download");
  await page.getByRole("button",{name:"Baixar modalidades · CSV",exact:true}).click();
  const downloaded=await pending, text=await readFile(await downloaded.path(),"utf8");
  expect(text).toContain("20540");expect(text).toContain("Identificador da coleta");expect(text).toContain("Banco Central");
  await page.screenshot({path:"test-results/composition-desktop.png",fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.getByRole("button",{name:"Ativar modo escuro"}).click();
  await expect(page.locator(".js-plotly-plot")).toHaveCount(1);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await page.screenshot({path:"test-results/composition-mobile-dark.png",fullPage:true});
  expect(errors).toEqual([]);
});

test("Trabalho e renda: trimestres, referência comum, gráfico, CSV e modo escuro", async ({ page }) => {
  const {readFile} = await import("node:fs/promises");
  const {createHash} = await import("node:crypto");
  const config = JSON.parse(await readFile(new URL("../generated/site.json", import.meta.url), "utf8"));
  const payload = JSON.parse(await readFile(new URL("../generated/" + config.data, import.meta.url), "utf8"));
  payload.catalog = JSON.parse(await readFile(new URL("../../catalog.json", import.meta.url), "utf8"));
  const specs = payload.catalog.filter(s => s.classification === "Trabalho e renda");
  payload.rows = payload.rows.filter(r => !specs.some(s => s.code === r.code));
  // Synthetic fixture is confined to this browser test.
  for (const s of specs) for (let i=0;i<14;i++) {
    payload.rows.push({code:s.code,date:`${2025+Math.floor(i/12)}-${String(i%12+1).padStart(2,"0")}-01`,original:s.code===24382 && i===13?null:s.code===24369?8:100+i,diff12_pp:i>=12?0:null,yoy_pct:i>=12?12:null});
  }
  payload.manifest.rows = payload.rows.length;
  payload.manifest.series = payload.catalog.length;
  const body=JSON.stringify(payload), hash=createHash("sha256").update(body).digest("hex"), name=`data-${hash.slice(0,16)}.json`;
  await page.route("**/site.json", route=>route.fulfill({json:{...config,data:name,sha256:hash}}));
  await page.route("**/"+name, route=>route.fulfill({body,contentType:"application/json"}));
  await page.goto("#labor");
  await expect(page.locator(".labor-kpis .kpi")).toHaveCount(4);
  await expect(page.locator(".labor-kpis .kpi").last()).toContainText("Indisponível nesta referência");
  await page.locator("#labor-reference").selectOption("2026-01-01");
  await expect(page.locator(".labor-kpis")).toContainText("11/2025–01/2026");
  await expect(page.locator(".labor-kpis .kpi").last()).toContainText("112,00 R$");
  await page.locator("#labor-code").selectOption("24382");
  await page.locator("#labor-metric").selectOption("yoy_pct");
  await expect(page.locator(".js-plotly-plot")).toBeVisible();
  await page.locator("#labor-code").selectOption("24369");
  await expect(page.locator("#labor-metric")).toHaveValue("original");
  await page.locator("#labor-metric").selectOption("diff12_pp");
  await expect.poll(()=>page.locator(".js-plotly-plot").evaluate(n=>n.layout.yaxis.title.text)).toBe("p.p.");
  const downloading = page.waitForEvent("download");
  await page.getByRole("button",{name:"Baixar trabalho e renda · CSV"}).click();
  const file = await downloading, csvText=await readFile(await file.path(),"utf8");
  expect(csvText).toContain("Período de referência");
  expect(csvText).toContain("11/2025–01/2026");
  expect(csvText).toContain("Base de preços do rendimento");
  expect(csvText).toContain(payload.manifest.snapshot_id);
  await page.screenshot({path:"test-results/labor-desktop.png",fullPage:true});
  await page.locator("#theme-toggle").click();
  await page.setViewportSize({width:390,height:844});
  await expect(page.locator(".labor-kpis")).toBeVisible();
  await page.screenshot({path:"test-results/labor-mobile-dark.png",fullPage:true});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.locator("#laborstart").fill("2026-02-01");
  await page.locator("#laborend").fill("2025-01-01");
  await expect(page.getByRole("alert")).toContainText("Selecione um período válido");
});

test("Setor externo: déficit, acumulados, referência, CSV e celular", async ({ page }) => {
  const {readFile} = await import("node:fs/promises");
  const {createHash} = await import("node:crypto");
  const config = JSON.parse(await readFile(new URL("../generated/site.json", import.meta.url), "utf8"));
  const payload = JSON.parse(await readFile(new URL("../generated/" + config.data, import.meta.url), "utf8"));
  payload.catalog = JSON.parse(await readFile(new URL("../../catalog.json", import.meta.url), "utf8"));
  payload.labels.sum12 = "Acumulado em 12 meses";
  payload.labels.sum_ytd = "Acumulado no ano";
  const specs = payload.catalog.filter(s => s.classification === "Setor externo e câmbio");
  payload.rows = payload.rows.filter(r => !specs.some(s => s.code === r.code));
  for (const s of specs) for (let i=0;i<14;i++) {
    payload.rows.push({code:s.code,date:`${2025+Math.floor(i/12)}-${String(i%12+1).padStart(2,"0")}-01`,original:s.code===22701 && i===13?null:s.measure_type==="balance"?-10:5,sum12:i>=11?-120:null,sum_ytd:-10*(i%12+1),yoy_pct:0,mom_pct:0});
  }
  payload.manifest.rows=payload.rows.length; payload.manifest.series=payload.catalog.length;
  const body=JSON.stringify(payload), hash=createHash("sha256").update(body).digest("hex"), name=`data-${hash.slice(0,16)}.json`;
  await page.route("**/site.json", route=>route.fulfill({json:{...config,data:name,sha256:hash}}));
  await page.route("**/"+name, route=>route.fulfill({body,contentType:"application/json"}));
  await page.goto("#external");
  await expect(page.locator(".external-kpis .kpi")).toHaveCount(6);
  await expect(page.locator(".external-kpis .kpi").last()).toContainText("Indisponível nesta referência");
  await page.locator("#external-reference").selectOption("2026-01-01");
  await expect(page.locator(".external-kpis .kpi").last()).toContainText("-10,00 US$ milhões");
  await page.locator("#external-code").selectOption("22701");
  await page.locator("#external-metric").selectOption("sum12");
  await expect.poll(()=>page.locator(".js-plotly-plot").evaluate(n=>n.layout.yaxis.title.text)).toBe("US$ milhões");
  await page.locator("#external-code").selectOption("3698");
  await expect(page.locator("#external-metric")).toHaveValue("original");
  await expect(page.locator("#external-metric option[value=sum12]")).toHaveCount(0);
  const downloading=page.waitForEvent("download");
  await page.getByRole("button",{name:"Baixar setor externo e câmbio · CSV"}).click();
  const csvText=await readFile(await (await downloading).path(),"utf8");
  expect(csvText).toContain("Acumulado em 12 meses");
  expect(csvText).toContain(payload.manifest.snapshot_id);
  expect(csvText).toContain("-10");
  await page.screenshot({path:"test-results/external-desktop.png",fullPage:true});
  await page.locator("#theme-toggle").click();
  await page.setViewportSize({width:390,height:844});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:"test-results/external-mobile-dark.png",fullPage:true});
  await page.locator("#externalstart").fill("2026-02-01");
  await page.locator("#externalend").fill("2025-01-01");
  await expect(page.getByRole("alert")).toContainText("Selecione um período válido");
});

test("Atividade: frequências, componentes, gráficos e CSV", async ({ page }) => {
  const {readFile}=await import("node:fs/promises"), {createHash}=await import("node:crypto");
  const config=JSON.parse(await readFile(new URL("../generated/site.json",import.meta.url),"utf8"));
  const payload=JSON.parse(await readFile(new URL("../generated/"+config.data,import.meta.url),"utf8"));
  payload.catalog=JSON.parse(await readFile(new URL("../../catalog.json",import.meta.url),"utf8"));
  payload.labels.qoq_pct="Variação trimestral (%)";
  const specs=payload.catalog.filter(s=>s.activity_group);
  payload.rows=payload.rows.filter(r=>!specs.some(s=>s.code===r.code));
  for(const s of specs) for(let i=0;i<(s.frequency==="Q"?10:28);i++) {
    const n=i*(s.frequency==="Q"?3:1), year=2024+Math.floor(n/12), month=String(n%12+1).padStart(2,"0");
    payload.rows.push({code:s.code,date:`${year}-${month}-01`,reference_period:s.frequency==="Q"?`${Math.floor((n%12)/3)+1}º tri/${year}`:`${month}/${year}`,original:100+i,qoq_pct:i?1:null,mom_pct:i?1:null,yoy_pct:i>=4?4:null});
  }
  payload.manifest.rows=payload.rows.length;payload.manifest.series=payload.catalog.length;
  const body=JSON.stringify(payload),hash=createHash("sha256").update(body).digest("hex"),name=`data-${hash.slice(0,16)}.json`;
  await page.route("**/site.json",r=>r.fulfill({json:{...config,data:name,sha256:hash}}));
  await page.route("**/"+name,r=>r.fulfill({body,contentType:"application/json"}));
  await page.goto("#activity");
  await expect(page.locator(".external-kpis .kpi")).toHaveCount(6);
  await expect(page.locator(".external-kpis")).toContainText("2º tri/2026");
  await expect(page.locator("#activity-code")).toHaveValue("22109");
  await expect(page.locator("#activity-metric")).toHaveValue("qoq_pct");
  await expect(page.locator(".js-plotly-plot")).toBeVisible();
  await expect.poll(()=>page.locator(".js-plotly-plot").evaluate(n=>n.data[0].x.length)).toBe(10);
  await page.locator("#activity-code").selectOption("21859");
  await expect(page.locator("#activity-metric option[value=qoq_pct]")).toHaveCount(0);
  await page.locator("#activity-metric").selectOption("yoy_pct");
  await page.locator("#activity-quarter").selectOption("2025-01-01");
  await expect(page.locator("main table").first()).toContainText("Consumo das famílias");
  const pending=page.waitForEvent("download");
  await page.getByRole("button",{name:"Baixar crescimento e atividade · CSV"}).click();
  const text=await readFile(await (await pending).path(),"utf8");
  expect(text).toContain("Periodicidade");expect(text).toContain("Ajuste sazonal");expect(text).toContain("2º tri/2026");
  await page.screenshot({path:"test-results/activity-desktop.png",fullPage:true});
  await page.locator("#theme-toggle").click();
  await page.setViewportSize({width:390,height:844});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:"test-results/activity-mobile.png",fullPage:true});
  await page.locator("#activitystart").fill("2026-04-01");
  await page.locator("#activityend").fill("2025-01-01");
  await expect(page.getByRole("alert")).toContainText("Selecione um período válido");
});

test("Perfis CSV: Excel português e análise preservam o recorte", async ({page}) => {
  const { readFile } = await import("node:fs/promises");
  await page.goto("#explorer");
  await page.locator("#explorer-code").selectOption("20539");
  await page.locator("#explorerstart").fill("2020-01-01");
  await page.locator("#explorerend").fill("2020-06-01");
  let pending = page.waitForEvent("download");
  await page.getByRole("button", {name:"Baixar dados filtrados · CSV",exact:true}).click();
  const localized = await readFile(await (await pending).path(), "utf8");
  expect(localized).toMatch(/^\ufeff"Código SGS";"Data de referência"/);
  expect(localized).toContain('"URL da fonte"');
  expect(localized).toContain('"Identificador da coleta"');
  expect(localized).toContain('"2020-01-01"');
  expect(localized).toContain('"2020-06-01"');
  expect(localized).not.toContain('"2020-07-01"');
  expect(localized.split("\r\n")).toHaveLength(7);
  await page.getByText("Opções de exportação", {exact:true}).click();
  await page.locator("#csv-profile").selectOption("analysis");
  pending = page.waitForEvent("download");
  await page.getByRole("button", {name:"Baixar dados filtrados · CSV",exact:true}).click();
  const analysis = await readFile(await (await pending).path(), "utf8");
  expect(analysis).toMatch(/^\ufeff"code","date"/);
  expect(analysis).toContain('"source_url"');
  expect(analysis.split("\r\n")).toHaveLength(7);
  // Dados numéricos mantêm a precisão; só mudam os separadores do perfil.
  const a = analysis.split("\r\n")[1].split('","');
  const b = localized.split("\r\n")[1].split('";"');
  expect(b[6].replace(",", ".")).toBe(a[6]);
  pending = page.waitForEvent("download");
  await page.locator("#download-excel").click();
  const book = new ExcelJS.Workbook();
  await book.xlsx.readFile(await (await pending).path());
  const sheet = book.getWorksheet("Dados");
  expect(sheet.getCell("A2").value).toBe("20539");
  expect(sheet.views[0].xSplit).toBe(2);
  expect(sheet.getCell("D1").alignment.horizontal).toBe("right");
  expect(sheet.getCell("D2").type).toBe(ExcelJS.ValueType.Number);
  expect(sheet.autoFilter).toBeTruthy();
});

test("Gráfico exporta PNG e SVG com título, fonte, unidades e prévia fiel", async ({page}) => {
  const {readFile} = await import('node:fs/promises');
  await page.goto('#explorer');
  await page.locator('#explorer-code').selectOption('432');
  const panel=page.locator('.chart-export').first();
  await panel.locator('summary').click();
  await panel.locator('[data-export-field=title]').fill('Selic — análise de teste');
  await panel.locator('[data-export-field=subtitle]').fill('Histórico selecionado');
  await panel.locator('[data-export-field=labels]').selectOption('last');
  await panel.locator('[data-export-field=color0]').fill('#123456');
  await panel.locator('[data-export-field=scale]').selectOption('2');
  await panel.getByRole('button',{name:'Atualizar prévia'}).click();
  const preview=panel.locator('.export-preview'), link=panel.locator('.export-download');
  await expect(preview).toBeVisible({timeout:30000});
  await expect(link).toBeVisible();
  expect(await preview.getAttribute('src')).toBe(await link.getAttribute('href'));
  let pending=page.waitForEvent('download');await link.click();
  const png=await readFile(await (await pending).path());
  expect(png.subarray(1,4).toString()).toBe('PNG');
  expect(png.readUInt32BE(16)).toBe(2400);expect(png.readUInt32BE(20)).toBe(1800);
  await panel.locator('[data-export-field=format]').selectOption('svg');
  await expect(link).toBeHidden();
  await panel.locator('[data-export-field=theme]').selectOption('dark');
  await panel.getByRole('button',{name:'Atualizar prévia'}).click();
  await expect(link).toBeVisible({timeout:30000});
  pending=page.waitForEvent('download');await link.click();
  const svg=await readFile(await (await pending).path(),'utf8');
  expect(svg).toContain('Selic — análise de teste');expect(svg).toContain('Histórico selecionado');
  expect(svg).toContain('Fonte: BCB/SGS 432');expect(svg).toContain('% a.a.');expect(svg).toContain('Coleta:');
  expect(svg).toContain('rgb(18, 52, 86)');expect(svg).toContain('width="1200"');
  await page.screenshot({path:'test-results/chart-export-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await page.screenshot({path:'test-results/chart-export-mobile.png',fullPage:true});
});
