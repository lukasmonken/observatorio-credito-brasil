# Metodologia econômica

As séries são estatísticas agregadas oficiais do BCB/SGS. O IPCA é produzido pelo IBGE e redistribuído pelo SGS. Não há dados de clientes nem estimativas de risco individual.

## Calendário e unidades

- Referência mensal representada pelo primeiro dia do mês; isso não significa publicação nesse dia. A data original é preservada em `observations` e nos brutos.
- Selic 432: meta anual diária, agregada pelo último valor observado de cada mês concluído. O mês corrente fica fora da base mensal, mesmo se houver dados diários.
- Séries originalmente mensais não são somadas nem reponderadas. Estoques são saldos de fim de período; concessões são fluxos do mês; taxas e spreads mantêm a ponderação oficial.
- Valores monetários em R$ milhões. A ficha genérica da série 20539 foi confrontada com a ficha detalhada SGS, que confirma a escala. Nenhuma conversão monetária implícita.
- Juros são % a.a.; inadimplência, endividamento e comprometimento são percentuais; spread é p.p. A diferença entre duas taxas percentuais é expressa em p.p., não em variação percentual.
- O comprometimento 29034 já é média móvel trimestral com ajuste sazonal. Endividamento 29037 usa renda acumulada em 12 meses (RNDBF). Não se compara diretamente o nível dos dois indicadores.
- IBC-Br 24364 é um índice com ajuste sazonal, não uma medida do PIB em reais. A base numérica original é mantida; a transformação base 100 explicita seu mês inicial.

## Transformações

Para estoques, fluxos e índices: variação mensal = `(x_t/x_(t−1)−1)*100`; variação em 12 meses = `(x_t/x_(t−12)−1)*100`. Não há preenchimento de ausências antes do cálculo. Denominador zero resulta em ausência.

Para taxas: diferença mensal ou em 12 meses, em p.p. A média móvel exige três meses presentes. Para o IPCA, acumulado em 12 meses = `(produto(1+IPCA_m/100)−1)*100`; percentuais não são somados.

Índice de preços `P_t = produto(1+IPCA_m/100)` a partir do início da coleta. Valor real = `valor nominal_t * P_base/P_t`. Mês-base é o último IPCA válido do snapshot, informado em cada exportação. Uma ausência intermediária invalida a cadeia a partir dela, evitando encadear sobre inflação desconhecida. Valores monetários depois do último IPCA não recebem estimativa de inflação. O deflator IPCA mede poder de compra do consumidor; não é índice específico de preços do crédito.

Base 100 no snapshot usa o primeiro valor válido de cada série; portanto bases iniciais podem diferir. No explorador, recalcula-se no primeiro valor válido do intervalo selecionado e informa-se a referência. Não se utiliza base 100 para comparar o nível de taxas.

## Comparabilidade e revisões

PF/PJ totais incluem recursos livres e direcionados. Juros PF de recursos livres 20740 não equivalem ao total PF 20716. Cheque especial, crédito pessoal não consignado e renegociação têm estruturas de prazo e risco distintas. A série 20743 é subconjunto de 20742; não somar ambas.

Inadimplência mede parcela da carteira com ao menos uma prestação em atraso superior a 90 dias, excluindo operações baixadas a prejuízo. Não equivale à porcentagem de pessoas negativadas.

As estatísticas sofrem revisões históricas. A ficha SGS da 20539 registra revisão em fevereiro de 2017. O BCB descreve revisão anual ordinária em junho e, em 2026, alterações em financiamentos imobiliários, prazos do cartão na apuração do comprometimento e captura de inadimplência de instituições não bancárias. Mudanças contábeis a partir de 2025 podem afetar reconhecimento e permanência de créditos nas carteiras; não atribuir toda variação posterior ao ciclo econômico. O projeto não estima tamanho desse efeito nem corrige as séries automaticamente.

Fontes de contexto: [estatísticas monetárias e de crédito](https://www.bcb.gov.br/estatisticas/estatisticasmonetariascredito) e metadados detalhados preservados em `data/metadata`. A extensão quantitativa das quebras permanece uma limitação, e exige documentação adicional para inferência econométrica.

## Correlações

Defasagem positiva k: X(t−k) pareado com Y(t). Primeiro se reindexa o calendário mensal, depois se defasa, por fim se descartam pares incompletos. O período apresentado é o de Y. Cada correlação mostra n e período; n<12 ou variância nula não produz coeficiente.

Análises principais usam diferenças em p.p. ou crescimento real. Séries em nível com tendência podem gerar associações espúrias. Diferenças não eliminam automaticamente autocorrelação; crescimento em 12 meses possui janelas sobrepostas. Concessões são sazonais e não foram dessazonalizadas pelo projeto. Não há testes causais, p-valores corrigidos, previsão, seleção automática da melhor defasagem ou inferência sobre indivíduos.
