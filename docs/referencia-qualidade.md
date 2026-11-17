# Referência de qualidade de 17/11/2026

A fase 2 fixa uma versão reproduzível para comparar futuras mudanças de dados e interface. A coleta principal registra **67 séries e 11.806 observações**. Os dados regionais e a inflação detalhada têm arquivos próprios.

## Dados de referência

- Código e dados: [commit 487adb11](https://github.com/lukasmonken/observatorio-credito-brasil/tree/487adb11eb1830c2aeb920961ee9f9014c86e10d).
- Identificação e hashes SHA-256 de todos os arquivos: [manifesto do snapshot](https://github.com/lukasmonken/observatorio-credito-brasil/blob/487adb11eb1830c2aeb920961ee9f9014c86e10d/data/processed/410070be-751a-4b59-b55b-e937a78d88e8/manifest.json).
- Referência individual das 67 séries, com código, data, unidade e último valor observado: [latest.csv](https://github.com/lukasmonken/observatorio-credito-brasil/blob/487adb11eb1830c2aeb920961ee9f9014c86e10d/data/processed/410070be-751a-4b59-b55b-e937a78d88e8/latest.csv). A data de coleta é 17/11/2026; cada série tem sua própria data econômica.
- Cobertura, observações ausentes e unidade de período: [coverage.csv](https://github.com/lukasmonken/observatorio-credito-brasil/blob/487adb11eb1830c2aeb920961ee9f9014c86e10d/data/processed/410070be-751a-4b59-b55b-e937a78d88e8/coverage.csv). O conjunto de testes de esquema, frequência, escala e transformações autorizadas é [test_catalog_contract.py](https://github.com/lukasmonken/observatorio-credito-brasil/blob/487adb11eb1830c2aeb920961ee9f9014c86e10d/tests/test_catalog_contract.py). A carga verifica o manifesto e a integridade do snapshot.
- Amostra externa consultada em 17/11/2026: [IPCA, SGS 433](https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01%2F10%2F2026&dataFinal=31%2F10%2F2026), 0,14% em outubro; [meta Selic, SGS 432](https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json&dataInicial=31%2F10%2F2026&dataFinal=31%2F10%2F2026), 13,75% a.a. no último dia de outubro. Na série agregada, a data representa o mês. São duas conciliações externas; a comparação das 67 séries com o próprio histórico publicado verifica consistência interna.

## Evidências antes da ampliação dos testes

| Verificação | Resultado observado |
|---|---|
| Aplicação Python, incluindo AppTest do Streamlit com dados reais locais, validação e PostgreSQL | [619 testes passaram, com dois avisos](https://github.com/lukasmonken/observatorio-credito-brasil/actions/runs/44070734720). Execução da proposta da coleta incorporada ao commit de referência. |
| Empacotamento para Pages, modelo JavaScript e navegador | [7 testes do pacote, 25 do modelo e 47 de navegador passaram](https://github.com/lukasmonken/observatorio-credito-brasil/actions/runs/44071275639). |
| Monitor do endereço público | [Verificação HTTP íntegra e um teste de navegador aprovado](https://github.com/lukasmonken/observatorio-credito-brasil/actions/runs/44071600354). |

## Roteiro de repetição

Para reproduzir a medição histórica, use o commit indicado acima. Para repetir os novos casos de caracterização, use a revisão que contém este documento e os testes da fase 2. Os fluxos **Verificar aplicação** e **Publicar dashboard no GitHub Pages** executam as suítes, com versões de ferramentas e sequência de comandos registradas no repositório. Em uma proposta de mudança, o Pages testa a versão candidata sem publicá-la em produção.

| Cenário | Como verificar e o que observar |
|---|---|
| Integridade dos dados | Rodar `python -m pytest -q tests/test_catalog_contract.py tests/test_core.py tests/test_pages_data.py`. Conferir código, tipo, frequência, unidade, data, nulos, zeros, falta de denominador, indicadores derivados e valores do Parquet contra o JSON. Na versão da fase 2, conferir também a data e o valor de cada linha de latest.csv contra a última observação válida. |
| Streamlit | Executar `python -m pytest -q tests/test_dashboard.py` e as suítes dos módulos. Abrir as seções, trocar a transformação no Explorador e conferir estados de snapshot ausente ou inválido. O AppTest exerce o aplicativo em Python com a coleta fixada; disponibilidade da hospedagem é uma verificação separada. |
| Navegação, filtros e downloads | No Pages, percorrer as 15 rotas, verificar console, selecionar período e série, reabrir um link em outra aba e conferir os arquivos CSV e Excel contra o recorte exibido. A suíte de navegador também exercita PNG, SVG e o boletim. |
| Celular | Repetir no navegador a 390 px e verificar que a página não ultrapassa a largura disponível. Os testes incluem filtros e tabelas de módulos selecionados. |
| Rede | Simular falha na requisição da base do Pages, verificar a mensagem, restaurar a rede e acionar a nova tentativa. Testar separadamente falha de API no coletor e preservação do último snapshot válido. |
| JavaScript desativado | Abrir o Pages com JavaScript desativado e conferir título, orientação e link para Streamlit. Nesta referência o HTML inicial não apresenta indicadores numéricos. O teste protege o acesso alternativo e permite uma futura melhoria do conteúdo estático. |

Os resultados automatizados não substituem uma revisão visual em aparelho físico nem uma conferência de todas as observações nas fontes oficiais. Ausência de resumo econômico sem JavaScript é uma limitação conhecida, já registrada na lista de implementações.

## Conferência das interfaces públicas

Em 17/11/2026, Pages e Streamlit exibiram o identificador 410070be, 67 séries e 11.806 observações. A hospedagem do Streamlit estava suspensa por inatividade; após a reativação, carregou o Panorama Brasil com os dados esperados. Essa espera inicial faz parte da referência operacional.

## Conferência diária de indicadores

O GitHub Actions executa **Conferir indicadores com o SGS** diariamente às 00h47 de Brasília e sob demanda. O monitor lê a base servida pelo Pages e consulta novamente o SGS para o último período publicado de cada série. Compara o valor original, a unidade, a frequência e o período exibido. A API de observações fornece data e valor. As unidades e frequências de referência estão registradas separadamente do catálogo publicado.

| Série SGS | Indicador | Unidade | Período |
|---|---|---|---|
| 20539 | Saldo total de crédito, estoque ao fim do mês | R$ milhões | Mês |
| 20631 | Concessões totais, novas operações no mês | R$ milhões | Mês |
| 3698 | Dólar de venda, média do mês | R$/US$ | Mês |
| 22099 | PIB observado, índice de volume do IBGE distribuído pelo SGS | Índice | Trimestre |

O resumo da execução apresenta os dois valores, seus períodos e a consulta oficial. O arquivo `reconciliation.json` fica disponível por 30 dias. Uma divergência pode indicar revisão oficial posterior à coleta. Uma consulta sem resposta válida aparece como inconclusiva. Ambos os casos sinalizam falha na conferência e preservam o site publicado. A amostra verifica o último ponto publicado de cada série. Os alertas de defasagem e a auditoria das observações históricas são controles separados.
