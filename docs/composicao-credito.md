# Composição do crédito por modalidade

Primeira entrega com sete séries mensais de saldo de fim de período, em R$ milhões, do BCB/SGS. A coleta validada, o histórico de revisões e o Explorador incorporam as novas séries.

| SGS | Segmento | Modalidade | Recursos | Fonte |
|---|---|---|---|---|
| 20579 | PF | Consignado | Livres | [BCB](https://dadosabertos.bcb.gov.br/dataset/20579-saldo-da-carteira-de-credito-com-recursos-livres---pessoas-fisicas---credito-pessoal-consigna) |
| 20581 | PF | Veículos | Livres | [BCB](https://dadosabertos.bcb.gov.br/dataset/20581-saldo-da-carteira-de-credito-com-recursos-livres---pessoas-fisicas---aquisicao-de-veiculos) |
| 20612 | PF | Imobiliário | Direcionados | [BCB](https://dadosabertos.bcb.gov.br/dataset/20612-saldo-da-carteira-de-credito-com-recursos-direcionados---pessoas-fisicas---financiamento-imob) |
| 20609 | PF | Rural | Direcionados | [BCB](https://dadosabertos.bcb.gov.br/dataset/20609-saldo-da-carteira-de-credito-com-recursos-direcionados---pessoas-fisicas---credito-rural-tota) |
| 20550 | PJ | Capital de giro | Livres | [BCB](https://dadosabertos.bcb.gov.br/dataset/20550-saldo-da-carteira-de-credito-com-recursos-livres---pessoas-juridicas---capital-de-giro-total) |
| 20553 | PJ | Veículos | Livres | [BCB](https://dadosabertos.bcb.gov.br/dataset/20553-saldo-da-carteira-de-credito-com-recursos-livres---pessoas-juridicas---aquisicao-de-veiculos) |
| 20544 | PJ | Duplicatas e recebíveis | Livres | [BCB](https://dadosabertos.bcb.gov.br/dataset/20544-saldo-da-carteira-de-credito-com-recursos-livres---pessoas-juridicas---desconto-de-duplicatas) |

## Cálculo e interpretação

Participação = 100 × saldo da modalidade / saldo total do segmento, sempre no mesmo mês. Denominadores: PF SGS 20541 e PJ SGS 20540, incluindo recursos livres e direcionados. Não é participação apenas no crédito livre. O saldo imobiliário desta entrega corresponde ao financiamento imobiliário com recursos direcionados; veículos corresponde à aquisição com recursos livres.

A seleção não cobre todas as modalidades e não deve ser normalizada para somar 100%. Não é um ranking de risco. Nenhum residual “outros” é calculado. O seletor oferece inicialmente a referência mais recente com todas as modalidades e participações disponíveis no recorte; datas incompletas continuam selecionáveis com aviso. Ausências não viram zero, não são interpoladas e não usam o último mês disponível de outra série. Total zero, ausente, negativo ou inferior ao saldo da modalidade torna a participação indisponível. Zeros de saldo com total positivo são preservados.

Valores são nominais. O histórico e o CSV respeitam o período selecionado; a referência mensal controla a tabela. Downloads incluem código SGS, segmento, recursos, denominador, fonte e URL. O site inclui o identificador da coleta. Snapshots anteriores à ampliação exibem mensagem de indisponibilidade.

Metadados de nomes, periodicidade e unidades conferidos em páginas oficiais em 05/11/2026. A publicação exige coleta e validação de todas as séries do catálogo; não publicar observações sintéticas usadas nos testes.
