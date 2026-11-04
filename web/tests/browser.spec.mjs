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
    for (const route of ["overview", "credit", "explorer", "quality"]) {
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
  await page.locator("#comparison-codes-20539").uncheck();
  await page.locator("#comparison-codes-20631").uncheck();
  await expect(page.locator("main")).toContainText(
    "Selecione de dois a seis indicadores",
  );
});
