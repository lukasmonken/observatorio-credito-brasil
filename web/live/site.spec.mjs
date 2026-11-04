import {test,expect} from '@playwright/test';
test('Publicação carrega dados e renderiza gráficos no navegador',async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('',{waitUntil:'domcontentloaded'});
  await expect(page.locator('main h2')).toHaveText('Visão geral');
  await expect(page.locator('main > .kpis > .kpi')).toHaveCount(4);
  await expect(page.locator('.js-plotly-plot')).toHaveCount(2);
  await expect(page.locator('.scatterlayer .trace').first()).toBeVisible();
  await expect(page.locator('main .error')).toHaveCount(0);
  await page.getByRole('link',{name:'Juros e crédito',exact:true}).click();
  await page.locator('#credit-view').selectOption('combined');
  await expect.poll(()=>page.locator('.js-plotly-plot').evaluateAll(nodes=>nodes[0]?.data?.length||0)).toBe(3);
  await expect(page.locator('main .error')).toHaveCount(0);
  expect(errors).toEqual([]);
});
