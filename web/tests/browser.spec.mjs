import { test, expect } from "@playwright/test";
import ExcelJS from "exceljs";
const pages = [
  "overview",
  "credit",
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
