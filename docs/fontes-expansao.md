# Fontes para expansão do Observatório Econômico do Brasil

Levantamento documental em 05/11/2026. Escopo: possibilidades futuras, sem ativar novos coletores ou alterar o nome do site. APIs documentadas não significam disponibilidade contínua; códigos, cobertura, limites e respostas devem ser homologados antes da integração.

## Catálogo inicial

| Fonte | Dados candidatos | Acesso identificado | Aplicação / condição |
| --- | --- | --- | --- |
| Banco Central — SGS | Selic, crédito, juros, inadimplência, IBC-Br; séries de índices de preços de terceiros | API de séries em JSON/CSV; mesmo mecanismo já utilizado no projeto | Crédito, atividade e inflação. Identificar o produtor original e validar cada série e unidade. |
| Banco Central — IFData | Cadastro, capital e Basileia, ativo/passivo, resultados, composição da carteira | API OData e relatórios oficiais | Instituições e conglomerados, com cobertura trimestral e perímetro explícito. |
| Banco Central — PTAX | Cotações de moedas, compra/venda e boletins por data | API OData documentada | Câmbio de referência; não apresentar como cotação de mercado em tempo real. |
| Banco Central — Expectativas de Mercado | Expectativas para inflação, PIB, Selic e câmbio, conforme catálogo | API própria documentada | Projeções do mercado, separadas de valores observados e de previsões institucionais do BCB. |
| IBGE — SIDRA / API de Agregados | PIB e componentes, IPCA/IPCA-15/INPC, produção industrial, comércio, serviços, PNAD Contínua, SINAPI | API com tabelas, metadados, períodos e localidades | Fonte principal para atividade, preços, trabalho e custos de construção; disponibilidade de recortes varia por pesquisa. |
| Ipea — Ipeadata | Séries macroeconômicas, regionais e sociais; históricos e indicadores complementares | API REST/OData v4, com metadados e valores em JSON | Complemento e consulta histórica; manter a fonte original e verificar atualização e séries descontinuadas. |
| MDIC — Comex Stat | Exportações, importações e saldo calculado; produtos, países e recortes territoriais | API documentada e bases completas em CSV | Comércio exterior de bens; não confundir com todo o balanço de pagamentos. |
| FGV IBRE | IGP-M, IGP-DI, INCC-M/DI/10; possíveis expansões para outros indicadores | Divulgações públicas e FGV Dados; parte dos históricos detalhados exige contrato | Validar variante, cobertura, licença e meio de acesso antes de prometer automação detalhada. |
| Fipe — FipeZap | Índices de preços anunciados de venda e locação residencial/comercial, por cidades cobertas | Planilhas Excel históricas e informes mensais no site oficial | Coleta por arquivo é viável; não foi identificada API pública documentada nas páginas consultadas. |
| Secovi-SP | Pesquisa de imóveis novos, vendas, lançamentos e oferta; pesquisas de locação e recortes regionais conforme publicação | Relatórios, apresentações e publicações; parte do conteúdo é exclusiva para associados | Planejar ingestão validada de arquivos abertos ou integração autorizada. Não foi identificada API pública documentada nas páginas consultadas. |
| Tesouro Nacional — Siconfi | RREO, RGF, contas anuais e matrizes contábeis, conforme endpoint | API pública em JSON, com paginação e limites | Expansão fiscal de estados e municípios; reconciliar conceitos antes de agregar entes. |

## Inflação: IGP-M e INCC

São candidatos viáveis, mas precisam de identificação precisa. O SGS confirma a série **189 — IGP-M**, em variação percentual mensal, e a série **192 — INCC**, também em variação mensal. A identificação genérica de INCC não autoriza rotulá-la automaticamente como INCC-M: validar os metadados, a versão e a continuidade histórica com a FGV antes de integrar. Não trocar versões silenciosamente para preencher lacunas.

A FGV produz INCC-M, INCC-DI e INCC-10, com janelas distintas de coleta. Seus resultados gerais têm divulgação gratuita, mas grande parte das séries históricas detalhadas depende de assinatura. A primeira entrega deve privilegiar séries agregadas com acesso e reutilização confirmados. O acesso por um distribuidor como SGS ou Ipeadata não dispensa identificar a fonte original nem verificar condições de uso.

Para custos de construção, acrescentar **SINAPI/IBGE** como indicador próprio. SINAPI e INCC não são séries equivalentes e não devem ser emendados. Acumulados de inflação devem usar composição das taxas mensais, com tratamento de lacunas, e não soma simples.

## Imobiliário: proposta de primeira versão

- **Preços e aluguéis:** FipeZap, por cidade e segmento disponível, com variação mensal, acumulada e comparação histórica. Confirmar unidade e disponibilidade de preço médio por m² nos arquivos antes de expor esse KPI.
- **Mercado primário:** Secovi-SP, com vendas, lançamentos e oferta segundo o perímetro de cada pesquisa. Explicitar que São Paulo ou uma amostra regional não representam o Brasil inteiro.
- **Custos:** INCC, com a variante identificada, e SINAPI; separar mão de obra e materiais apenas quando a fonte permitir.
- **Financiamento:** ampliar o catálogo BCB para crédito imobiliário, após validar séries de saldo, concessões, taxas e segmentação.

FipeZap mede preços de anúncios, não preços finais de transações. A base residencial cobre apartamentos prontos nas cidades acompanhadas; a comercial tem escopo próprio. Preservar as quebras de cobertura e metodologia. Os números de vendas de imóveis novos do Secovi medem outro universo e não devem ser tratados como confirmação direta dos preços do FipeZap.

Automatização por Excel/CSV oficial é uma opção legítima mesmo sem API. Guardar o arquivo original e sua origem, validar planilhas/colunas, período, unidades e totais e bloquear publicação se o formato mudar. Em PDF, usar extração com revisão e reconciliação; evitar uma coleta frágil dependente apenas da aparência da página. Não contornar login nem presumir que material publicamente legível permite redistribuição integral.

## Regras comuns para as próximas integrações

- Cada indicador terá produtor, distribuidor, identificador, unidade, frequência, região, ajuste sazonal, transformação permitida e URL de origem.
- Registrar período de referência, data de divulgação quando disponível e data de coleta separadamente. A home não deve dar a impressão de que indicadores diários, mensais e trimestrais medem o mesmo período.
- Distinguir PIB de IBC-Br, preços correntes de volume, observações de expectativas, estoque de fluxo e índices de taxas de variação.
- Para comércio exterior, preservar critérios de valoração, país, produto e território. Não misturar saldos comerciais do MDIC com conceitos do balanço de pagamentos sem reconciliação.
- Preferir o produtor original; usar Ipeadata e séries redistribuídas como complemento documentado, sem substituir fontes silenciosamente.
- Reaproveitar snapshots, revisões, monitoramento, validação de ausências e exportações do projeto. Homologar limites, paginação e revisões de cada provedor.

## Referências oficiais consultadas

1. [BCB — IBC-Br / SGS](https://dadosabertos.bcb.gov.br/pt_BR/dataset/24363-indice-de-atividade-economica-do-banco-central---ibc-br).
2. [BCB — IFData e recursos de API](https://dadosabertos.bcb.gov.br/dataset/ifdata---dados-selecionados-de-instituies-financeiras).
3. [BCB — documentação PTAX](https://www.bcb.gov.br/conteudo/dadosabertos/BCBDepin/gnastportal-dados-abertostaxas-de-cambio---todos-os-boletins-diarios.pdf).
4. [BCB — Expectativas de Mercado](https://dadosabertos.bcb.gov.br/dataset/expectativas-mercado).
5. [IBGE — API de Agregados](https://servicodados.ibge.gov.br/api/docs/agregados?versao=3) e [Painel de Indicadores](https://www.ibge.gov.br/indicadores.html).
6. [Ipeadata — documentação da API](https://www.ipeadata.gov.br/api/).
7. [Comex Stat — documentação da API](https://api-comexstat.mdic.gov.br/docs) e [MDIC — bases em dados abertos](https://www.gov.br/mdic/pt-br/assuntos/comercio-exterior/estatisticas/base-de-dados-bruta).
8. [FGV IBRE — INCC e condições de acesso](https://portalibre.fgv.br/estudos-e-pesquisas/indices-de-precos/incc) e [FGV — índices econômicos](https://portal.fgv.br/indices-economicos).
9. [BCB — SGS 189, IGP-M](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?hdOidSeriesSelecionadas=189&method=consultarGraficoPorId) e [SGS 192, INCC](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarSeries&series=192).
10. [Fipe — FipeZap, séries e metodologia](https://fipe.org.br/pt-br/indices/fipezap/).
11. [Secovi-SP — pesquisa mensal](https://secovi.com.br/pesquisa-mensal-do-mercado-imobiliario/), [pesquisas e condições de acesso](https://secovi.com.br/pesquisas-e-indices/) e [downloads públicos](https://secovi.com.br/baixar/).
12. [Tesouro — Siconfi API](https://apidatalake.tesouro.gov.br/docs/siconfi/).
