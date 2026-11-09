# Crescimento e atividade

Módulo nacional nas versões web (`#activity`) e Streamlit. São 14 séries, incluindo o IBC-Br já existente: PIB total observado e ajustado, oito componentes do PIB e três pesquisas mensais de volume. Não utiliza valores monetários nominais como medida de crescimento real.

## Catálogo oficial verificado em 09/11/2026

| SGS | Indicador | Frequência | Ajuste sazonal |
| --- | --- | --- | --- |
| 24364 | IBC-Br | Mensal | Sim |
| 21859 | Produção industrial geral, PIM-PF | Mensal | Não |
| 1455 | Volume de vendas no varejo, total Brasil, PMC | Mensal | Não |
| 23982 | Volume de serviços, total Brasil, PMS | Mensal | Não |
| 22099 | PIB a preços de mercado, índice de volume observado | Trimestral | Não |
| 22109 | PIB a preços de mercado, índice dessazonalizado | Trimestral | Sim |
| 22083 | Agropecuária | Trimestral | Não |
| 22084 | Indústria | Trimestral | Não |
| 22089 | Serviços | Trimestral | Não |
| 22100 | Consumo das famílias | Trimestral | Não |
| 22101 | Consumo do governo | Trimestral | Não |
| 22102 | Formação bruta de capital fixo | Trimestral | Não |
| 22103 | Exportações | Trimestral | Não |
| 22104 | Importações | Trimestral | Não |

Produtor: IBGE, exceto IBC-Br (Banco Central). Distribuição: BCB/SGS. Cada entrada do catálogo liga diretamente à sua ficha oficial de metadados. Fontes verificadas na interface SGS: [PIB observado](https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=22099), [PIB ajustado](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarGraficoPorId&hdOidSeriesSelecionadas=22109), [indústria](https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=21859), [varejo](https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=1455), [serviços](https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=23982).

As fichas podem conter textos genéricos ou desatualizados: a de serviços abre com uma referência a receita nominal, mas o nome da série e o detalhamento identificam o índice de volume; a de varejo menciona uma base anterior. Por isso, exibimos a unidade índice sem presumir uma base numérica comum. As séries são usadas separadamente; nenhuma troca de variante é realizada para preencher lacunas.

## Tratamento temporal e cálculos

- Frequência `Q` é preservada. Datas são normalizadas ao início do trimestre, com rótulo `nº tri/ano`; nenhuma mensalização ou interpolação. Trimestres ainda não concluídos são excluídos. Um trimestre ausente gera lacuna no calendário trimestral.
- `qoq_pct`: variação contra o trimestre anterior, exclusiva do PIB com ajuste sazonal. Não anualizamos a taxa.
- `yoy_pct`: comparação contra quatro trimestres ou 12 meses anteriores, conforme a frequência. Séries observadas usam a comparação anual para evitar interpretar sazonalidade como tendência.
- Índices encadeados dos componentes não são aditivos: não somamos, não calculamos participações nem contribuições a partir deles. A abertura de serviços no PIB difere da cobertura da PMS. Comércio varejista não é o total do comércio da economia.
- Valores zero e ausências são preservados; denominador zero gera ausência. Índices não recebem nova deflação pelo IPCA. O IBC-Br não é o PIB oficial.
- Cada cartão informa sua própria referência e ajuste sazonal. O filtro é aplicado depois dos cálculos, preservando a base de comparação. Histórico integral reconsultado para captar revisões.
- Relações e defasagens continuam mensais; séries trimestrais são excluídas desse seletor. O Explorador oferece as transformações aprovadas e Excel com frequência e trimestre explícitos.
- O limite de defasagem das séries trimestrais conta dias desde o encerramento do trimestre, não desde a data normalizada de início.

## Compatibilidade

Migração idempotente expande a frequência permitida para `Q` em SQLite/PostgreSQL, preservando observações e referências. As tabelas históricas com nome `monthly_observations` passam a armazenar referências na frequência de cada série. A visão SQL de mudanças mensais exclui séries trimestrais. Snapshots anteriores continuam legíveis.
