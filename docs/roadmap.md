# Próximas implementações

Este documento distingue funcionalidades planejadas de funcionalidades já disponíveis.

| Item | Entrega | Estado |
| --- | --- | --- |
| 1 | Inflação detalhada: IPCA, IPCA-15, INPC, IGP-M, INCC-M e nove grupos nacionais do IPCA | Primeira entrega implementada; regiões, subitens e outras variantes do INCC permanecem planejados |
| 2 | Composição do crédito: PF/PJ, modalidades e outras aberturas do BCB | Primeira entrega: sete modalidades PF/PJ, saldos e participações; outras aberturas permanecem planejadas |
| 3 | Comparação em base 100 | Disponível |
| 4 | Compartilhamento dos filtros por URL | Disponível |
| 5 | Boletim automático da coleta, com novas referências, variações e revisões separadas | Implementado |
| 6 | Instituições financeiras: capital, Basileia e comparação entre instituições | Planejado; adicionado em 05/11/2026 |
| 7 | Evolução para Observatório Econômico do Brasil, com navegação por módulos e panorama geral de KPIs | Planejado; adicionado em 05/11/2026 |
| 8 | Crescimento e atividade: PIB, IBC-Br, indústria, comércio e serviços | Planejado |
| 9 | Setor externo: balança comercial, câmbio, reservas e contas externas | Planejado |
| 10 | Mercado imobiliário e construção: FipeZap, Secovi-SP, INCC, SINAPI e crédito imobiliário | Planejado; acesso às fontes condicionado conforme catálogo |
| 11 | Expansões: trabalho e renda, contas públicas e recortes regionais | Possibilidades futuras |
| 12 | Exportações prontas para análise: CSV compatível com planilhas e melhoria do Excel existente | Planejado; relato de problema visual no CSV em 05/11/2026 |
| 13 | Personalização e exportação de gráficos com título, números, unidades e fonte | Planejado |

Os itens futuros são um backlog de possibilidades. O usuário esclareceu em 05/11/2026 que não deseja implementar todas essas expansões agora. O item 5 foi concluído separadamente, conforme combinado.

## 12. Exportações prontas para análise

Relato do usuário: o CSV foi baixado e os dados aparentavam estar corretos, mas a apresentação ficou desconfigurada ao abrir. A causa ainda não foi reproduzida nem diagnosticada; investigar separador, codificação, convenções numéricas e programa de abertura antes de alterar o exportador.

- Oferecer um formato CSV adequado ao Excel em português, com separador e decimal coerentes, acentos preservados e cabeçalhos claros; considerar um perfil interoperável separado para ferramentas analíticas.
- Manter uma linha por observação, datas consistentes, colunas estáveis, valores numéricos sem símbolos misturados, unidade e fonte identificadas. Preservar zeros e códigos de identificação e distinguir dados ausentes.
- Aprimorar a exportação Excel já existente para abertura imediata: tipos de célula, formatos de data/número, filtros, cabeçalho fixo, largura de colunas e uma aba de metadados.
- Explicar na escolha de formato que CSV não armazena cores, larguras ou formatação de células; essas propriedades pertencem ao arquivo Excel.
- Validar acentos, aspas, separadores, datas, decimais e proteção contra fórmulas; testar importação e reimportação sem perda ou mudança de valores.

## 13. Gráficos personalizáveis para download

Relato do usuário: o gráfico exportado saiu sem título e sem os números esperados. Reproduzir a exportação e distinguir números dos eixos de rótulos nos pontos antes da implementação.

- Criar uma prévia de exportação com título/subtítulo editáveis, período, unidade, legenda, fonte e data-base.
- Permitir escolher tipo de gráfico entre opções compatíveis com a análise, cores das séries, tema/fundo, dimensões, resolução e tamanho da fonte.
- Oferecer rótulos de valores nos pontos, somente no último ponto ou desativados; manter escalas e números dos eixos legíveis, com limites para evitar sobreposição.
- Exportar a composição completa em imagem; avaliar PNG e SVG conforme suporte do renderizador e validar equivalência entre prévia e arquivo.
- Avaliar primeiro os recursos da biblioteca de gráficos já utilizada, sem pressupor uma integração externa ou serviço pago.
- Respeitar as unidades e os dados: personalização visual não pode alterar valores, ocultar transformações ou produzir comparação enganosa.

Critérios de aceite: título, eixos, legenda, unidades e fonte presentes no arquivo final; cores e rótulos refletem a prévia; funcionamento nos temas claro/escuro e em dispositivos móveis. Nenhuma dessas mudanças de exportação foi implementada nesta atualização do roadmap.

## Direção do produto: Observatório Econômico do Brasil

Solicitação registrada em 05/11/2026. Ampliar o escopo do Observatório para a economia brasileira, preservando o crédito como módulo próprio. A mudança de nome, navegação e páginas ainda não foi implementada.

Menu proposto:

1. **Panorama Brasil**: visão geral com PIB, IPCA em 12 meses, Selic, desemprego, câmbio e saldo comercial. Cada cartão informa sua própria data-base, unidade e fonte.
2. **Crédito**: manter as análises atuais e ampliar modalidades e composição.
3. **Instituições financeiras**: módulo IFData descrito abaixo, com capital e Basileia.
4. **Inflação**: IPCA, IPCA-15, INPC, IGP-M e INCC, com seletor da variante e metodologia.
5. **Crescimento e atividade**: PIB trimestral e seus componentes; IBC-Br, produção industrial, comércio e serviços mensais.
6. **Setor externo e câmbio**: exportações, importações e saldo comercial, parceiros e produtos; PTAX, reservas e balanço de pagamentos em subseções próprias.
7. **Imobiliário e construção**: preços de venda/locação, vendas e lançamentos de imóveis novos, custos de construção e financiamento imobiliário.
8. **Trabalho e renda / Contas públicas / Regiões**: expansões posteriores, sem páginas vazias antes de haver dados validados.

Manter o menu selecionável, responsividade, tipografia de sistema e temas claro/escuro. Usar abas ou subseções dentro de cada módulo para evitar uma navegação com dezenas de itens.

### Sequência proposta, ainda sem cronograma

- Preparar catálogo de múltiplas fontes, com identificadores próprios: nem toda série será identificada por código SGS.
- Implementar Panorama Brasil, expansão da inflação e atividade usando APIs públicas documentadas.
- Acrescentar Comex Stat e PTAX; executar o módulo IFData como entrega própria.
- Integrar FipeZap por planilha oficial e SINAPI; INCC/FGV e Secovi avançam conforme disponibilidade e condições de reutilização.
- Ampliar trabalho/renda, fiscal e regiões após estabilizar os módulos anteriores.

O [catálogo de fontes e viabilidade](fontes-expansao.md) registra exemplos, formas de acesso e restrições. A ordem é uma proposta para implementação futura, não uma promessa de cobertura integral de cada fonte.

## 6. Instituições financeiras e capital

Objetivo: consultar uma instituição ou conglomerado, acompanhar seus indicadores ao longo do tempo e comparar entidades com o mesmo perímetro e data-base.

### Primeira entrega proposta

- Menu com busca por nome e identificação da entidade, trimestre e tipo de consolidação.
- Índice de Basileia e, conforme cobertura validada, índices de Capital Principal e Nível I, Patrimônio de Referência e ativos ponderados pelo risco (RWA).
- Histórico trimestral, comparação entre entidades e exportação CSV com fonte, unidade e data-base.
- Ativo total, patrimônio líquido, carteira de crédito e resultado, após validação do significado e periodicidade de cada campo.
- Manter os modos claro/escuro e a tipografia do painel.

### Expansões posteriores

- Composição da carteira por PF/PJ, modalidade, atividade econômica e região, conforme relatórios disponíveis.
- Indicadores de qualidade da carteira e rentabilidade, apenas após validar cobertura e fórmulas; distinguir dados publicados de cálculos do Observatório.
- Filtros por segmento e tipo de instituição quando disponíveis no cadastro.

### Fonte e critérios de implementação

Usar o [IFData do Banco Central](https://dadosabertos.bcb.gov.br/dataset/ifdata---dados-selecionados-de-instituies-financeiras), pela [API OData](https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/), com coletor separado do SGS. Validar o catálogo de relatórios, campos, unidades, paginação e disponibilidade histórica antes de fixar códigos no coletor.

A divulgação é trimestral: o BCB informa prazo de 60 dias após março, junho e setembro e 90 dias após dezembro. Mostrar data-base, data de coleta e eventual defasagem separadamente.

A [metodologia oficial](https://www.bcb.gov.br/conteudo/dadosabertos/BCBDesig/IFData%20-%20Esclarecimentos%20e%20Metodologia.pdf) distingue instituições individuais, conglomerados financeiros e conglomerados prudenciais. As informações de capital usam conglomerados prudenciais e instituições independentes a partir de março de 2015. Não atribuir automaticamente um indicador consolidado a cada CNPJ do grupo, somar entidades com seus conglomerados ou unir perímetros históricos incompatíveis.

Preservar valores ausentes como indisponíveis, nunca como zero. Não presumir cobertura de todas as instituições ou de todos os indicadores em todos os trimestres. Tratar mudanças cadastrais e revisões sem perder a identificação histórica.

Validar os requisitos regulatórios por entidade e período antes de oferecer qualquer comparação com mínimos exigidos. Basileia isoladamente não será convertida em selo de segurança ou ranking de solvência.

Critérios de aceite: reconciliar amostras com o IFData oficial; validar unidades, zeros, ausências e duplicidades; testar atualização e revisões; mostrar fonte e perímetro em cada visualização. Este módulo ainda não está implementado.
