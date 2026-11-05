# Próximas implementações

Este documento distingue funcionalidades planejadas de funcionalidades já disponíveis.

| Item | Entrega | Estado |
| --- | --- | --- |
| 1 | Inflação detalhada: IPCA, INPC e IGP-M; grupos e recortes conforme disponibilidade e licença das fontes | Planejado |
| 2 | Composição do crédito: PF/PJ, modalidades e outras aberturas do BCB | Planejado |
| 3 | Comparação em base 100 | Disponível |
| 4 | Compartilhamento dos filtros por URL | Disponível |
| 5 | Boletim automático da coleta, com novas referências, variações e revisões separadas | Implementado |
| 6 | Instituições financeiras: capital, Basileia e comparação entre instituições | Planejado; adicionado em 05/11/2026 |

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
