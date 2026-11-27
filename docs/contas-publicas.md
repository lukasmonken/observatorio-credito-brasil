# Contas públicas

Primeira entrega: cinco séries mensais oficiais do Banco Central, em percentual do PIB. Metadados conferidos em 26/11/2026.

| SGS | Indicador | Referência | Abrangência |
| --- | --- | --- | --- |
| 13762 | [Dívida bruta — DBGG](https://dadosabertos.bcb.gov.br/dataset/13762-divida-bruta-do-governo-geral--pib---metodologia-utilizada-a-partir-de-2008) | Estoque na referência | Governo geral |
| 4513 | [Dívida líquida — DLSP](https://dadosabertos.bcb.gov.br/dataset/4513-divida-liquida-do-setor-publico--pib---total---setor-publico-consolidado) | Estoque na referência | Setor público consolidado |
| 5793 | [Resultado primário — 12 meses](https://dadosabertos.bcb.gov.br/dataset/5793-nfsp-sem-desvalorizacao-cambial--pib---fluxo-acumulado-em-12-meses---resultado-primario---tota) | Fluxo acumulado em 12 meses | Setor público consolidado |
| 5727 | [Resultado nominal — 12 meses](https://dadosabertos.bcb.gov.br/dataset/5727-nfsp-sem-desvalorizacao-cambial--pib---fluxo-acumulado-em-12-meses---resultado-nominal---total) | Fluxo acumulado em 12 meses | Setor público consolidado |
| 5760 | [Juros nominais — 12 meses](https://dadosabertos.bcb.gov.br/dataset/5760-nfsp-sem-desvalorizacao-cambial--pib---fluxo-acumulado-em-12-meses---juros-nominais---total---) | Fluxo acumulado em 12 meses | Setor público consolidado |

## Leitura e transformações

Preservamos os valores oficiais e o sinal da necessidade de financiamento: nos resultados primário e nominal, positivo significa déficit, negativo significa superávit. Não inverter sinais nas exportações. Ver [Manual de Estatísticas Fiscais do BCB, cálculo dos fluxos](https://www.bcb.gov.br/content/estatisticas/Documents/notas_metodologicas/estatisticas-fiscais/estatisticasfiscais.pdf).

Dívidas são estoques; resultados e juros já são fluxos acumulados em 12 meses. As observações mensais destes últimos compartilham meses e não podem ser somadas novamente. O resultado primário usa caixa, os juros usam competência. Nominal inclui primário e juros.

DBGG e DLSP possuem abrangências diferentes; não interpretar a subtração como ativos públicos. Juros em % do PIB não são taxa de juros em % a.a. As relações com o PIB são fornecidas pelo BCB, sem recalcular denominadores no painel.

No catálogo, measure_type=rate representa a relação percentual publicada, não o caráter econômico do numerador. fiscal_basis distingue stock e flow12. Transformações autorizadas: original, diferença em p.p. ante o mês anterior e ante 12 meses. Sem soma, percentual de variação, deflação ou base 100.

O resumo usa uma referência escolhida, sem recuar silenciosamente para valores antigos. Ausência é exibida como travessão e exportada vazia, nunca como zero. Filtros, histórico, CSV com unidade/abrangência/fonte/coleta e links compartilháveis estão na seção Contas públicas. O histórico é reconsultado integralmente para incorporar revisões.

## Escopo posterior

Receitas e despesas do Governo Central pelo Tesouro Nacional ficam para outra entrega, com identificação própria de abrangência e metodologia. Não misturar com o setor público consolidado.
