# Trabalho e renda

Primeira entrega nacional: quatro séries da PNAD Contínua do IBGE distribuídas pelo SGS do Banco Central. O módulo reutiliza a coleta validada, snapshots, histórico de revisões e monitoramento do Observatório. Não consulta terceiros durante a abertura da página.

| SGS | Indicador | Unidade | Comparação anual |
| --- | --- | --- | --- |
| 24369 | Taxa de desocupação | % da força de trabalho | Diferença em pontos percentuais |
| 24379 | Pessoas ocupadas | Mil pessoas | Variação percentual |
| 24380 | Pessoas desocupadas | Mil pessoas | Variação percentual |
| 24382 | Rendimento médio real habitual das pessoas ocupadas | R$ | Variação percentual |

## Referência e conceitos

As séries começam em março de 2012. A frequência de divulgação é mensal, mas cada referência representa os três meses terminados no mês registrado: 2026-01 corresponde a novembro/2025–janeiro/2026. Trimestres consecutivos compartilham dois meses. Não somar essas observações nem tratá-las como fluxos mensais independentes. O módulo usa séries sem ajuste sazonal e comparação com o mesmo trimestre móvel do ano anterior (12 meses no calendário).

Taxa de desocupação é a proporção de desocupados na força de trabalho, não na população total. Pessoas ocupadas e desocupadas são estimativas em milhares, para pessoas de 14 anos ou mais. Não equivalem ao saldo de empregos formais do Novo Caged.

Nos metadados do SGS 24382, o conceito específico é rendimento bruto real habitual do trabalho principal das pessoas ocupadas com rendimento. A unidade é reais, já corrigidos pela fonte pelo IPCA a preços do mês central do trimestre mais recente divulgado. Não aplicamos uma segunda deflação e não confundimos com renda domiciliar per capita, salário mínimo ou massa de rendimentos. A base de preços exibida acompanha a última referência válida da série no snapshot completo; filtros históricos não alteram essa base. Os metadados consultados também descrevem outros conceitos no sumário geral; a implementação segue o conceito específico da série.

A coleta diária existente é integral. Adicionalmente, as quatro séries têm `refresh_full_history` para que até a coleta incremental reconsulte todo o histórico solicitado: reponderações e atualização da base de preços podem modificar observações antigas. Não misturar vintages de rendimento para calcular variações.

Ausências permanecem ausentes, zeros são preservados, denominadores zero não geram percentuais. O resumo mostra a referência selecionada para todos os indicadores; nunca substitui uma ausência por valor de outro trimestre. Os cálculos anuais usam o histórico antes do filtro. Diferenças numéricas entre estimativas amostrais não constituem teste de significância estatística.

## Interface e exportação

Menu **Trabalho e renda** em ambas as interfaces; no site, rota `#labor`. Filtro de período, referência do resumo, quatro cartões, tabela de variações anuais, seleção de indicador e medida, histórico e CSV. O CSV inclui início/fim no rótulo do trimestre, valor, unidade, comparação anual e sua unidade, base de preços do rendimento, fonte, URL e snapshot. Os indicadores também ficam disponíveis no explorador e em sua exportação Excel.

Recortes regionais, informalidade, subutilização, distribuição de renda e Novo Caged não fazem parte desta entrega.

## Evidência de metadados — conferida em 05/11/2026

- [SGS 24369](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?hdOidSeriesSelecionadas=24369&method=consultarGraficoPorId): taxa de desocupação, %, frequência M, início 01/03/2012.
- [SGS 24379](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?hdOidSeriesSelecionadas=24379&method=consultarGraficoPorId): população ocupada, unidades (mil), frequência M, início 01/03/2012.
- [SGS 24380](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?hdOidSeriesSelecionadas=24380&method=consultarGraficoPorId): população desocupada, unidades (mil), frequência M, início 01/03/2012.
- [SGS 24382 — dados básicos e metadados](https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=24382): nome, fonte IBGE, reais, frequência mensal, início 01/03/2012; abas consultadas no navegador, incluindo conceito e base de preços (metadados atualizados em 28/06/2023).
- [IBGE — PNAD Contínua](https://www.ibge.gov.br/estatisticas/sociais/educacao/17270-pesquisa-nacional-por-amostra-de-domicilios-continua-pnadc.html): referências mensais como trimestres móveis, não medidas isoladas de cada mês.
