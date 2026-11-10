const cache = new Map();
const labels = {monthly: 'No mês (%)', ytd: 'No ano (%)', annual: 'Em 12 meses (%)', weight: 'Peso na cesta (%)'};
export const levelLabels = ['Índice geral', 'Grupos', 'Subgrupos', 'Itens', 'Subitens'];
export function locationLabel(location) {
  const suffix = {'6':'Município','7':'Região metropolitana'}[location.level];
  return location.name + (suffix ? ` · ${suffix}` : '');
}
export function detailRows(dataset) {
  return dataset.rows.map(([date, location, category, monthly, ytd, annual, weight]) => ({
    date, location, category, monthly, ytd, annual, weight,
    name: dataset.categories[category].name,
    level: dataset.categories[category].level,
    locality: locationLabel(dataset.locations[location]),
    index: dataset.name, table: dataset.table, unit: '%',
    source: 'IBGE/SIDRA', source_url: dataset.source_url, collected_at: dataset.created_at,
  }));
}
async function load(descriptor) {
  if (!cache.has(descriptor.file)) cache.set(descriptor.file, (async () => {
    if (!/^inflation-[a-f0-9]{16}\.json$/.test(descriptor.file)) throw new Error('Arquivo inválido');
    const response = await fetch(descriptor.file);
    if (!response.ok) throw new Error('Dados indisponíveis');
    const bytes = await response.arrayBuffer();
    const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2, '0')).join('');
    if (hash !== descriptor.sha256) throw new Error('Integridade dos dados inválida');
    return JSON.parse(new TextDecoder().decode(bytes));
  })().catch(error => { cache.delete(descriptor.file); throw error; }));
  return cache.get(descriptor.file);
}
export async function renderInflationDetail(host, ui, files) {
  const {el, select, state, note, message, table, number, month, download, charts} = ui;
  host.append(el('h3', {}, 'Regiões e subitens · IBGE'), note('Últimas 24 referências publicadas. Brasil: índice geral, grupos, subgrupos, itens e subitens. Localidades pesquisadas: índice geral e grupos. A cobertura regional não representa todos os municípios ou estados.'));
  if (!files || !Object.keys(files).length) { host.append(message('Detalhamento aguardando uma coleta validada do IBGE.')); return; }
  host.append(select('ibge-index', 'Índice detalhado', Object.entries(files).map(([id, f]) => [id, f.name]), '7060'));
  const target = el('section'); host.append(target);
  target.append(note('Carregando detalhamento oficial…'));
  let dataset;
  try { dataset = await load(files[state['ibge-index']]); }
  catch { if (target.isConnected) target.replaceChildren(message('Não foi possível carregar o detalhamento. Recarregue a página para tentar novamente.')); return; }
  if (!target.isConnected) return;
  target.replaceChildren();
  const rows = detailRows(dataset);
  target.append(note(`Fonte: IBGE/SIDRA · tabela ${dataset.table} · Coleta: ${new Date(dataset.created_at).toLocaleString('pt-BR', {timeZone:'America/Sao_Paulo'})}. Acumulados publicados pelo IBGE; podem diferir dos cálculos com taxas arredondadas da visão geral.`));
  const filters = el('div', {class:'filters'}); target.append(filters);
  filters.append(select('ibge-location', 'Localidade pesquisada', Object.entries(dataset.locations).map(([id,l]) => [id, locationLabel(l)]), '1'));
  const local = rows.filter(r => r.location === state['ibge-location']);
  const levels = [...new Set(local.map(r => r.level))].sort();
  filters.append(select('ibge-level', 'Nível de detalhe', levels.map(l => [String(l),levelLabels[l]]), '1'));
  const level = local.filter(r => r.level === Number(state['ibge-level']));
  const categories = [...new Map(level.map(r => [r.category, r.name])).entries()].sort((a,b) => a[1].localeCompare(b[1], 'pt-BR', {numeric:true}));
  filters.append(select('ibge-category', 'Categoria no histórico', categories, categories[0][0]));
  const months = [...new Set(level.map(r => r.date))].sort().reverse();
  filters.append(select('ibge-month', 'Referência do detalhamento', months.map(d => [d,month(d)]), months[0]));
  filters.append(select('ibge-metric', 'Medida do histórico', Object.entries(labels), 'monthly'));
  const columns = [['name','Categoria'], ['monthly',labels.monthly,number], ['ytd',labels.ytd,number], ['annual',labels.annual,number], ['weight',labels.weight,number]];
  const selected = level.filter(r => r.date === state['ibge-month']).sort((a,b) => a.name.localeCompare(b.name,'pt-BR',{numeric:true}));
  target.append(table(selected, columns), download('Baixar detalhamento · CSV',selected,'inflacao_detalhamento.csv'));
  target.append(note('Peso é a participação na cesta daquele índice e localidade, não contribuição em pontos percentuais. Não some níveis hierárquicos nem taxas de inflação. — significa valor não disponível, nunca zero.'));
  const history = local.filter(r => r.category === state['ibge-category']);
  const title = `${dataset.name} · ${history[0].name} · ${history[0].locality}`;
  target.append(el('h3', {}, title));
  const chart = el('div', {class:'chart'}); target.append(chart);
  const metric = state['ibge-metric'];
  charts().then(({drawLines}) => { if(chart.isConnected) drawLines(chart,[{name:history[0].name,unit:'%',metric,rows:history,color:"#285c50"}],['%'],{title,source:`IBGE/SIDRA ${dataset.table} · ${labels[metric]}`,period:`${month(history[0].date)}–${month(history.at(-1).date)}`,asOf:dataset.created_at}); });
  target.append(download('Baixar histórico detalhado · CSV',history,'inflacao_historico_detalhado.csv'));
  if (Number(state['ibge-level']) <= 1) {
    const comparison = rows.filter(r => r.category === state['ibge-category'] && r.date === state['ibge-month']);
    target.append(el('h3', {}, 'Comparação entre localidades'), table(comparison, [['locality','Localidade'],...columns.slice(1)]),download('Baixar comparação regional · CSV', comparison,'inflacao_regional.csv'));
  }
  target.append(note('IPCA, INPC e IPCA-15 têm populações, cestas e janelas de coleta distintas. Esta visão mantém as medidas oficiais de cada tabela, sem substituir um índice por outro.'),el('a',{href:dataset.source_url,target:'_blank',rel:'noopener noreferrer'},'Consultar tabela oficial no SIDRA'));
}
