# Inflação detalhada

Primeira entrega: cinco índices gerais e nove grupos nacionais do IPCA, em dados mensais distribuídos pelo Banco Central. Todos participam da mesma coleta validada, histórico de revisões, monitoramento, dicionário e exportações do Observatório.

| Série SGS | Indicador | Produtor |
| --- | --- | --- |
| 433 | IPCA | IBGE |
| 7478 | IPCA-15 | IBGE |
| 188 | INPC | IBGE |
| 189 | IGP-M | FGV IBRE |
| 7456 | INCC-M | FGV IBRE |
| 1635 | IPCA — Alimentação e bebidas | IBGE |
| 1636 | IPCA — Habitação | IBGE |
| 1637 | IPCA — Artigos de residência | IBGE |
| 1638 | IPCA — Vestuário | IBGE |
| 1639 | IPCA — Transportes | IBGE |
| 1640 | IPCA — Comunicação | IBGE |
| 1641 | IPCA — Saúde e cuidados pessoais | IBGE |
| 1642 | IPCA — Despesas pessoais | IBGE |
| 1643 | IPCA — Educação | IBGE |

## Uso e cálculo

Acesse **Inflação detalhada** no menu. Selecione o período, a medida (mensal, no ano ou em 12 meses) e os índices. Os cartões usam a última referência de cada índice dentro do recorte: não são necessariamente o mesmo mês. A tabela dos grupos usa um mês explícito e mantém ausências como ausências. É possível comparar até seis grupos no gráfico; a tabela contém os nove.

A taxa mensal é o valor original, em percentual. Acumulados são calculados no histórico completo antes de filtrar o período, por `100 × (produto(1 + taxa/100) − 1)`. Não usamos soma de percentuais nem variação percentual de uma taxa de inflação.

- **No ano:** exige todos os meses desde janeiro até a referência; reinicia a cada janeiro. Uma série que começa em março não ganha um falso acumulado anual.
- **Em 12 meses:** exige doze meses consecutivos, incluindo a referência. Lacunas impedem o cálculo até que a janela volte a estar completa.
- Deflação e taxa zero são preservadas. Taxas menores ou iguais a −100% bloqueiam publicação.
- Arredondamentos das taxas mensais publicadas podem causar pequenas diferenças frente aos acumulados divulgados diretamente pelo produtor.
- Cada grupo tem sua própria taxa. Ela não é contribuição em pontos percentuais ao IPCA. Não somar nem tirar média simples das taxas para reconstruir o índice geral.

Downloads dos índices e dos grupos incluem códigos, referências, taxas, fonte, URL e identificação da coleta. As mesmas séries ficam disponíveis no Explorador, inclusive com a exportação Excel existente. A expansão do catálogo preserva a leitura de snapshots antigos: a página mostra somente os indicadores já coletados, sem inventar valores.

## Metadados e evidências

Conferência em 05/11/2026:

- [BCB — correspondência entre códigos e os nove grupos do IPCA](https://www4.bcb.gov.br/pec/series/port/metadados/mg41Bp.htm). Documento histórico usado para identificar os códigos, não para afirmar cobertura geográfica ou ponderações atuais.
- [BCB — IPCA-15, SGS 7478](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?hdOidSeriesSelecionadas=7478&method=consultarGraficoPorId).
- [BCB — INPC, SGS 188](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarSeries&series=188).
- [BCB — IGP-M, SGS 189](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?hdOidSeriesSelecionadas=189&method=consultarGraficoPorId).
- [BCB — INCC-M, SGS 7456](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?hdOidSeriesSelecionadas=7456&method=consultarGraficoPorId): confirma variante M, periodicidade mensal e unidade de variação percentual mensal.
- [IBGE — IPCA](https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-ipca.html), [IPCA-15](https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9260-indice-nacional-de-precos-ao-consumidor-amplo-15.html) e [FGV — variantes do INCC](https://portalibre.fgv.br/estudos-e-pesquisas/indices-de-precos/incc).

As respostas JSON das 37 séries do catálogo ampliado foram coletadas em homologação; a execução validou todas. O coletor preserva respostas originais e checksums nos artefatos de cada execução. A série 192, nomeada genericamente INCC no SGS, não foi usada como substituta da 7456.

## Limites desta entrega

Cobertura nacional. Não inclui ainda subitens, pesos/contribuições, recortes regionais ou outras variantes do INCC. IPCA-15 tem janela e cobertura próprias; não equivale aos primeiros quinze dias do IPCA. INCC-M mede custos de construção, não preços de venda de imóveis. Mudanças de metodologia, cesta e ponderações exigem cuidado na leitura histórica.

A coleta diária consulta a fonte, mas a frequência das observações continua mensal. A inclusão de séries novas aparece no histórico como série incluída, sem ser confundida com nova referência mensal ou revisão.

## Regiões e subitens — IBGE

Na página **Inflação detalhada**, escolha **Visão da inflação → Regiões e subitens · IBGE**.

- IPCA: [SIDRA 7060](https://sidra.ibge.gov.br/tabela/7060).
- INPC: [SIDRA 7063](https://sidra.ibge.gov.br/tabela/7063).
- IPCA-15: [SIDRA 7062](https://sidra.ibge.gov.br/tabela/7062).

A ampliação conserva as últimas 24 referências mensais de cada tabela. Para Brasil,
abrange toda a hierarquia oficial; para as localidades pesquisadas, o índice geral
e os nove grupos. Municípios e regiões metropolitanas são recortes da pesquisa,
não séries para todas as UFs ou cidades. Subitens regionais e histórico anterior
à janela de 24 meses não fazem parte desta entrega.

Variação mensal, acumulado no ano, acumulado em 12 meses e peso vêm diretamente
do SIDRA. Não recalculamos os acumulados a partir das taxas arredondadas. Pesos
representam participação na cesta de cada índice/localidade, não contribuição em
pontos percentuais. Não se somam taxas, níveis hierárquicos ou pesos de regiões.
Os índices têm populações e janelas de coleta próprias.

As convenções do IBGE são preservadas: `-` significa zero absoluto; `..`, `...` e
`X`/`x` são ausências. Negativos e zero numérico permanecem valores válidos.
Os códigos de tabela, categoria e localidade são separados dos códigos SGS.

A coleta diária usa `scripts/update_inflation.py`, valida as três tabelas antes
da publicação e conserva a última coleta em caso de falha. A interface informa
a data de coleta específica, distinta do snapshot SGS. A publicação empacota
arquivos separados com hash SHA-256, carregados apenas ao abrir o detalhamento.
CSV inclui índice, localidade, categoria, unidade, tabela, fonte e data de coleta.

INCC-M continua na visão nacional. INCC-DI e INCC-10 não foram adicionados:
dependem de validação específica de acesso ao histórico e condições da FGV;
não devem ser substituídos por séries de janela diferente.
