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

## Dicionário no painel

A página **Dicionário e metodologia** permite buscar as 24 séries por nome ou
código SGS. Cada ficha usa o catálogo do snapshot publicado, preservando o conceito
oficial, unidade, segmento, modalidade, periodicidade, fonte e limitações. O período
mostrado considera observações originais não ausentes, não a data da coleta. A data
de conferência dos metadados não representa a última atualização dos valores.
As fórmulas disponíveis respeitam `allowed_transforms`; não se oferecem variações
percentuais onde o projeto definiu mudanças em pontos percentuais.

O job diário executa coleta completa do período configurado. A limitação de
reconsulta de 18 meses presente nos catálogos se aplica ao modo incremental do
pipeline, não ao job diário atual. O histórico de revisões compara snapshots
publicados e registra a data de detecção, não a data em que a fonte realizou a
revisão. Valores anteriores ao início desse registro não são reconstruídos.

A média móvel adicional oferecida para o comprometimento de renda é uma nova
suavização de uma série que já é média móvel trimestral dessazonalizada na fonte.
Não deve ser interpretada como o valor original publicado. Para a inflação,
acumulado de 12 meses exige todos os meses da janela; para crescimento em 12 meses,
o cálculo exige os valores nos dois extremos, sem imputação dos meses intermediários.

## Exportação Excel do explorador

Em **Explorador de indicadores → Baixar dados filtrados · Excel**, o arquivo
respeita o indicador, o período e a transformação selecionados no painel.
A aba **Dados** contém os valores originais e, quando selecionada, a transformação.
A aba **Indicador** registra a fonte oficial, o conceito, unidades, periodicidade,
segmento e limitações do catálogo da base publicada. **Metodologia** inclui a
fórmula selecionada, o mês-base e esta documentação. **Coleta** identifica o
snapshot, datas de coleta/exportação, filtro solicitado e referências exportadas.

O Excel recebe os resultados calculados pelo painel, sem recalcular indicadores
nem inserir fórmulas executáveis. A base 100 acompanha a primeira observação
válida do recorte; médias e variações preservam os cálculos feitos sobre o
histórico antes do filtro. Datas de referência são células de data, formatadas
como mês/ano. Números permanecem numéricos; células vazias significam ausência e
zero permanece zero. Percentuais mantêm sua escala original: 15 representa 15%,
não 0,15. Valores seguem a precisão numérica do Excel (aproximadamente 15 dígitos
significativos), sem arredondamento prévio adicional pelo exportador.

Cabeçalhos congelados, filtros e unidades facilitam o uso fora do painel. Textos
e URLs são gravados como conteúdo, sem conversão automática em fórmulas ou links
ativos. O arquivo é gerado em memória, não grava dados no servidor e não realiza
chamadas externas. A exportação CSV existente continua disponível.


## Inflação detalhada

Cinco índices gerais (IPCA, IPCA-15, INPC, IGP-M e INCC-M) e nove grupos do IPCA. Acumulados por composição das taxas mensais, com calendário completo e sem preencher lacunas. Fontes primárias: IBGE e FGV IBRE; distribuição: BCB/SGS. Consulte [séries, cálculos e limites](inflacao.md).

## Trabalho e renda — PNAD Contínua

As séries nacionais SGS 24369, 24379, 24380 e 24382 têm divulgação mensal e referência em trimestres móveis, identificados pelo mês final. Referências consecutivas compartilham dois meses de pesquisa. A taxa de desocupação usa a força de trabalho como denominador e sua comparação anual é expressa em pontos percentuais. Ocupados e desocupados estão em milhares de pessoas; seu crescimento anual e o do rendimento usam variação percentual frente ao mesmo trimestre móvel do ano anterior. As séries não têm ajuste sazonal nesta entrega.

O rendimento habitual real é publicado já deflacionado, na base de preços do mês central do trimestre mais recente divulgado. Não aplicar novamente a deflação do crédito a essa série. O histórico é reconsultado integralmente para incorporar mudanças da base de preços e revisões. Estimativas amostrais não são registros do Caged; diferenças descritivas não representam testes de significância. Ver [Trabalho e renda](trabalho-renda.md) para conceitos, fontes, cobertura e limitações.
