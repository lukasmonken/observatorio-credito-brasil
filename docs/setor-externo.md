# Setor externo e câmbio

Implementado nas versões web (`#external`) e Streamlit: seis séries mensais nacionais, referência comum para os cartões, filtros, histórico, acumulados dos fluxos, CSV e integração com o Explorador (inclusive Excel). Histórico a partir de janeiro de 2010, reconsultado integralmente em cada coleta para incorporar revisões.

## Fontes oficiais verificadas em 06/11/2026

| SGS | Indicador | Unidade | Natureza |
| --- | --- | --- | --- |
| 3698 | Dólar livre, venda, média de período | R$/US$ no histórico desde 2010 | Média mensal |
| 3546 | Reservas internacionais, total | US$ milhões | Estoque de fim de mês |
| 22708 | Exportação de bens, balanço de pagamentos | US$ milhões | Fluxo mensal |
| 22709 | Importação de bens, balanço de pagamentos | US$ milhões | Fluxo mensal |
| 22707 | Balança comercial, balanço de pagamentos, saldo | US$ milhões | Fluxo mensal, admite déficit |
| 22701 | Transações correntes, saldo | US$ milhões | Fluxo mensal, admite déficit |

[SGS 3698: nome, unidade e frequência](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarGraficoPorId&hdOidSeriesSelecionadas=3698).
[SGS 3546: nome, unidade e frequência](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarGraficoPorId&hdOidSeriesSelecionadas=3546).
[Exportações](https://dadosabertos.bcb.gov.br/dataset/22708-exportacao-de-bens---balanco-de-pagamentos---mensal), [importações](https://dadosabertos.bcb.gov.br/dataset/22709-importacao-de-bens---balanco-de-pagamentos---mensal), [saldo comercial](https://dadosabertos.bcb.gov.br/dataset/22707-balanca-comercial---balanco-de-pagamentos---mensal---saldo), [transações correntes](https://dadosabertos.bcb.gov.br/dataset/22701-transacoes-correntes---mensal---saldo).

## Leitura e cálculos

- Comércio segue BPM6/BCB, com ajustes de cobertura aos registros do MDIC. Não confundir com a balança aduaneira do Comex Stat. Transações correntes incluem bens, serviços e rendas; não equivalem ao saldo comercial.
- Valores monetários externos são dólares correntes, sem deflação pelo IPCA brasileiro. Saldos negativos são preservados e não recebem crescimento percentual ou base 100.
- Dólar é cotação média mensal de venda, não cotação em tempo real ou fechamento diário. Alta em R$/US$ significa depreciação do real.
- Reservas são estoque; sua variação inclui efeitos de preços e câmbio dos ativos, não apenas intervenções.
- `sum12` soma os últimos 12 meses completos. `sum_ytd` soma janeiro até a referência. Ambos são exclusivos de fluxos, exigem calendário completo e são calculados antes dos filtros de tela. Ausência não é zero; uma lacuna invalida a janela correspondente.
- Cartões usam uma única referência escolhida. Se uma série ainda não publicou aquele mês, aparece indisponível, sem substituição silenciosa por mês anterior.
- A cotação deve ser positiva; exportações, importações e reservas não podem ser negativas. Déficits comerciais e correntes são válidos.

## Escopo

Este módulo cobre a visão macroeconômica nacional. Desagregações do Comex Stat por país parceiro, produto, estado e município exigem o conector MDIC e permanecem uma expansão distinta; não são simuladas a partir das séries agregadas do BCB.
