# Auditoria técnica — Observatório de Crédito Brasil

Data: 27/10/2026. Escopo: projeto completo local e pacote Git em `deploy/streamlit`, cuja base anterior era o commit `ed1e114`. A auditoria combina leitura de código, testes offline, análise estática, inspeção de dependências e revisão do diff. Não é um pentest da infraestrutura do Streamlit ou do GitHub.

## Resumo executivo

A arquitetura é adequada ao volume atual: coleta independente da interface, dados originais preservados, persistência relacional, transformações econômicas centralizadas e dashboard que consome snapshots. Não houve reescrita da aplicação nem mudança nas fórmulas econômicas. O principal risco encontrado estava na publicação e no consumo de arquivos, seguido por concorrência e caminhos de erro pouco testados.

As correções estão implementadas no projeto local e sincronizadas com o pacote de deploy. Os 15 arquivos de dados já versionados nesse pacote foram comparados por SHA256 e permanecem idênticos. Nenhuma coleta real ou substituição da base publicada foi executada nesta auditoria. As alterações não foram enviadas ao GitHub nem aplicadas ao site online.

Situação: adequado para seguir à validação de CI e homologação do dashboard público. Não certificado para operação com SLA ou uso crítico. A integração PostgreSQL precisa executar de fato; a presença de um workflow não equivale a uma integração aprovada.

## Arquitetura e pontos de entrada

- `python -m observatorio`: inicialização do banco, coleta completa/incremental/replay e relatório analítico.
- `scripts/update_data.py`: atualização diária em SQLite isolado, com validação de cobertura e publicação do snapshot.
- `dashboard/app.py`: seis páginas Streamlit, filtros e exportação CSV; não consulta o Bacen durante a navegação.
- `scripts/prepare_streamlit_cloud.py`: empacotamento; agora recusa um destino que já é repositório Git.
- `scripts/build_catalog.py`: construção do catálogo a partir de evidências oficiais locais.
- `scripts/collect_bridge.mjs`: transporte Node alternativo, fora do caminho de produção diário.
- `.github/workflows/update-data.yml`: coleta diária às 19h17 de Brasília, timeout de 30 minutos, serialização do job e evidências por sete dias.
- `.github/workflows/ci.yml`: nova verificação com testes, Ruff, mypy, cobertura e PostgreSQL 17 descartável; ainda não executada remotamente.

Fluxo: API SGS → respostas brutas e checksum → parsing/validação → upsert e histórico de revisões → calendário mensal e indicadores → CSVs/manifesto → ponteiro do snapshot → interface e Tableau. SQL usa parâmetros; não existe concatenação de inputs de usuários em consultas. Chaves compostas impedem duplicação de observações. Transações por série e transação de reconstrução dos derivados são mantidas.

Não há autenticação, cadastro, uploads ou informação privada de clientes: a aplicação é pública e somente de leitura. `DATABASE_URL` configura o pipeline; `TEST_DATABASE_URL` aponta exclusivamente para um banco de testes autorizado. O job diário escolhe sua própria base temporária.

## Problemas críticos — P0

Nenhum P0 confirmado no escopo examinado. Isso não significa ausência garantida de vulnerabilidades desconhecidas.

## Problemas importantes — P1

| Local | Problema e risco | Correção implementada |
|---|---|---|
| `scripts/update_data.py` | Copiava os arquivos sobre `current` antes de trocar o ponteiro. Interrupção ou leitura concorrente poderia combinar versões. | Diretório novo por execução; validação completa; troca atômica do ponteiro. A versão anterior não é sobrescrita. Testes simulam falha de cópia e candidato inválido. |
| `observatorio/snapshot.py` | Manifesto continha hashes, mas o loader não os verificava nem reconciliava dados, catálogo e execução. | Verificação de hashes, IDs, contagens, calendário, duplicatas, finitude, cobertura e transformações declaradas antes da exibição. |
| `observatorio/pipeline.py`, `db.py` e job diário | Proteção de concorrência por série no PostgreSQL não cobria a reconstrução completa. O job local reutilizava e apagava um único banco temporário. | Bloqueio do diretório de saída e banco durante a coleta; advisory lock de sessão no PostgreSQL; lock de arquivo no SQLite; diretório temporário exclusivo por job. |
| `scripts/prepare_streamlit_cloud.py` | Reempacotar poderia repor dados antigos no checkout usado pelo dashboard online. | Recusa explícita de destino com `.git`, antes de copiar arquivos. Teste verifica essa proteção. |

O job diário também registra o ponteiro antes da coleta e recusa a publicação se ele mudar durante o processamento. Essa checagem evita que uma coleta atrasada substitua outra publicação. O gate aceita revisões numéricas legítimas, mas bloqueia perda de cobertura, série vazia, duplicatas e infinitos.

## Melhorias realizadas — P2/P3

- Datas nulas e `NaT` agora têm rejeição explícita; parsing continua aceitando o formato SGS.
- Correlações com séries vazias retornam uma tabela vazia de pares e resultados sem coeficiente, em vez de falhar ao criar o calendário.
- Metadados corrompidos da última tentativa não derrubam um snapshot válido; a interface mostra aviso.
- Filtros entre duas referências mensais exibem estado vazio compreensível.
- O cache recebe o conteúdo exato do ponteiro e o diretório; a leitura não troca silenciosamente de versão entre a chave do cache e o carregamento.
- Retry não reutiliza `Retry-After` de uma resposta anterior quando a tentativa seguinte termina em timeout.
- Respostas mensais validam campos e datas antes do filtro de período. HTTPs transitórios mantêm tentativas limitadas; erros permanentes não são repetidos.
- Conexões do banco e sessões HTTP são fechadas no encerramento do pipeline.
- SQLite cria o diretório pai quando necessário.
- `assert` usado como validação de integridade foi substituído por erro explícito, preservando o controle mesmo com Python em modo otimizado.
- O ponteiro de exportação Tableau também usa substituição atômica individual.
- `.gitignore` e `.dockerignore` passam a excluir secrets, locks, caches de ferramentas e diretórios temporários adicionais.
- Dez imports sem uso foram identificados na análise inicial; os imports desnecessários foram removidos, sem remover APIs públicas.
- Funções modificadas foram formatadas para eliminar trechos comprimidos e tornar fluxos de exceção e transação legíveis.

## Segurança

### Caminhos de replay e snapshot

**Severidade: baixa. Local:** `ReplayClient.fetch` e `load_snapshot`.

**Problema:** referências de arquivo não eram confinadas ao diretório esperado. **Risco:** um operador que executasse replay de um manifesto local não confiável poderia provocar leitura de arquivos externos ao conjunto, ou o ponteiro local poderia apontar para outra pasta. Não havia um endpoint público para fornecer esses manifestos. **Correção:** resolução e verificação de confinamento de caminhos; teste específico de `../` no replay e ponteiro externo no snapshot.

### Detalhes internos na interface

**Severidade: média. Local:** tratamento de falha em `dashboard/app.py` e configuração Streamlit.

**Problema:** o expansor público exibia `str(exc)`. **Risco:** exposição de caminhos ou detalhes internos de erros. Nenhuma credencial efetivamente exposta foi confirmada. **Correção:** mensagem pública genérica, diagnóstico no log e `client.showErrorDetails = "none"`. Teste confirma ausência do bloco de detalhes.

### Dependências e repositório

`pip-audit` analisou os 44 pacotes fixados do ambiente de execução e não encontrou vulnerabilidades conhecidas. `pip check` não encontrou incompatibilidades de requisitos. A consulta ocorreu em 27/10/2026; não é garantia contra falhas futuras, comprometimento do fornecedor ou vulnerabilidades sem aviso publicado.

A inspeção de arquivos rastreados não encontrou `.env`, secrets, bancos locais ou chaves privadas. A busca por padrões de tokens GitHub, AWS access key e cabeçalhos de chaves privadas no histórico Git disponível não encontrou correspondências. Essa busca não detecta todo segredo possível.

Não foram identificados `eval`, desserialização pickle, shell com input de usuários, uploads ou SQL dinâmico de usuários no caminho Python de produção. O HTML manual contém CSS local estático. XSS, CSRF e gerenciamento de sessão não foram tratados como vulnerabilidades existentes sem uma superfície concreta na aplicação. TLS/CORS/autenticação do provedor permanecem responsabilidade de configuração e infraestrutura externas a este escopo.

## Bugs e regras econômicas

Foram corrigidos os casos de publicação parcial, concorrência, leitura de snapshot inconsistente, retry com estado antigo, datas inválidas e séries vazias descritos acima.

Permanecem as regras de Selic no último mês concluído, IPCA composto, deflação encadeada, ausência de interpolação, variação percentual versus p.p., base 100 e alinhamento de defasagens. A comparação estrutural do módulo `transform.py` confirmou mudanças apenas em `parse_rows` e `lag_pairs`; as funções de cálculo `monthly`, `price_index`, `indicators` e `correlations` mantiveram sua lógica.

## Testes

Foram acrescentados 29 casos parametrizados/individuais à suíte completa: integridade e esquema do snapshot, datas inválidas, execução concorrente SQLite, falha de cópia, recusa de publicação inválida, publicação bem-sucedida, mudança concorrente do ponteiro, série nova vazia, infinito, retry, replay fora do diretório, metadados de execução inválidos, filtro vazio, erro sem detalhes internos, relatório analítico e proteção do empacotador.

O teste PostgreSQL existente foi ampliado para exercitar o bloqueio da execução completa. Ele continua pendente localmente porque não existe servidor/banco de teste configurado. A CI adicionada prepara esse ambiente, mas não foi executada nesta sessão.

| Verificação | Resultado |
|---|---|
| Suíte original | 32 aprovados, 0 falhos, 1 ignorado |
| Suíte completa após auditoria | 61 aprovados, 0 falhos, 1 ignorado |
| Pacote de deploy | 60 aprovados, 0 falhos, 1 ignorado; não inclui o teste local do empacotador |
| Cobertura do projeto completo | 84% de linhas, arredondado; 987 statements, 161 não executados |
| Dashboard | 95% de linhas |
| Transformações | 95% de linhas |
| Job diário | 92% de linhas |
| Ruff | Sem achados nas regras F, E9 e S configuradas |
| mypy | Sem erros com `check_untyped_defs`; imports sem stubs são ignorados |
| Dependências fixadas | 44 pacotes; nenhuma vulnerabilidade conhecida reportada |
| Compatibilidade de requisitos | `pip check` aprovado |
| Dados existentes no deploy | 15 arquivos idênticos por SHA256 |

Cobertura é de linhas, não de branches. CLI e construtor de catálogo têm baixa/nenhuma cobertura, e mypy não é estrito: funções sem tipos e bibliotecas sem stubs limitam a análise. Durante a criação de um teste houve falha por import ausente no próprio teste; foi corrigida antes dos resultados finais acima.

## Performance

Não foi identificado gargalo que justificasse reescrever cálculos ou adicionar cache adicional. A leitura validada de 4.590 registros levou mediana de aproximadamente 14 ms e máximo de 18 ms em dez medições locais; esse número não mede latência de rede nem capacidade multiusuário. A leitura continua protegida pelo cache do Streamlit.

A coleta diária completa foi mantida porque captura revisões históricas. Reduzir chamadas à API sem uma política de revisões poderia tornar a base incorreta. Não houve teste de carga, profiling de produção ou benchmark PostgreSQL, e não se reivindica ganho percentual de velocidade.

## Qualidade do código e aparência artificial

Não é possível atribuir autoria por IA apenas pela aparência do código. Os problemas concretos eram imports sem uso, lógica muito comprimida, caminhos de falha pouco verificados e validações de integridade que existiam no produtor mas não no consumidor.

Foram removidos imports mortos e formatados os módulos alterados. Mantiveram-se funções simples, sem criar repositórios genéricos, serviços abstratos ou classes sem necessidade. `publish_snapshot` concentra uma operação que precisa ser testada sob falha. `pipeline_lock` centraliza o ciclo do bloqueio e evita duplicar a lógica entre bancos.

A captura ampla de exceções por série foi mantida deliberadamente: a coleta deve registrar qual série falhou e continuar o diagnóstico das demais. Agora inclui traceback no log. O gate diário impede que uma falha parcial vire publicação. A captura ampla na interface delimita a apresentação de erro ao usuário; não transforma falha em sucesso.

## Itens não alterados e limites operacionais

1. **P2 — PostgreSQL:** schema, upsert e advisory lock foram revisados, mas a integração real não foi executada. CI preparada; confirmar seu resultado antes de adotar esse banco em produção.
2. **P2 — Retenção:** snapshots por execução e histórico Git crescem com o tempo. Não apaguei bases existentes nem defini uma política destrutiva de retenção sem requisito de negócio. Para operação prolongada, definir arquivamento e limites; o dataset atual é pequeno.
3. **P2 — Supply chain:** Actions continuam usando tags de versão, e o lock Python não tem hashes de distribuição. Fixar SHAs verificados e hashes é um endurecimento adicional; não inventei hashes nem atualizei major versions. Ferramentas de desenvolvimento ficam separadas em `requirements-dev.txt`.
4. **P2 — Publicação multissistema:** banco, filesystem do dashboard e ponteiro Tableau não constituem uma única transação distribuída. Os arquivos são completos antes da promoção e cada ponteiro é atômico, mas uma falha de disco entre as trocas pode deixar consumidores em versões diferentes. Os IDs permitem detectar essa condição. Não foi introduzida uma camada transacional distribuída para o tamanho atual do projeto.
5. **P2 — Transporte Node alternativo:** `collect_bridge.mjs` permanece legado, fora do job diário, usando filtros de data também para séries mensais. O cliente Python já usa a estratégia mensal sem filtros. Não foi possível validar o auxiliar com Node local; ele não deve ser considerado homologado para substituir o cliente principal. A tentativa de ajuste não validada foi revertida.
6. **P2 — Infraestrutura:** Docker/PostgreSQL e disponibilidade do Streamlit não foram testados de ponta a ponta. O Dockerfile local continua com usuário padrão; endurecer para usuário sem privilégios e validar permissões de volumes antes de hospedar esse container publicamente. A versão publicada usa Streamlit Cloud.
7. **P2 — Limites externos:** a API pode alterar schema, unidade ou revisão histórica. O catálogo exige revisão humana; a API de valores não prova que a unidade permaneceu igual. Não há SLA nem calendário oficial de divulgação integrado.
8. **P3 — Tipagem e estrutura:** não transformei toda a aplicação em código estritamente tipado nem dividi todas as páginas em módulos. A modularidade atual serve ao escopo; refatoração extensa aumentaria o diff sem corrigir um defeito demonstrado.
9. **P3 — Ferramentas auxiliares e testes:** o caminho feliz completo do empacotador, o construtor de catálogo e a CLI merecem maior cobertura. Não foi criada cobertura artificial apenas para elevar o percentual.

A recarga via CLI continua podendo publicar snapshot parcial com alerta, como já era documentado. O job público diário exige sucesso das 24 séries. Essa diferença é intencional e foi preservada.

## Avaliação final

Notas de julgamento técnico para o escopo atual, não métricas certificadas nem garantia de produção:

| Dimensão | Nota / 10 | Limitação principal |
|---|---:|---|
| Segurança | 8,0 | Infraestrutura e supply chain não integralmente verificadas |
| Confiabilidade | 8,0 | PostgreSQL e falhas distribuídas ainda exigem homologação |
| Qualidade | 8,0 | Alguns utilitários permanecem compactos e pouco tipados |
| Manutenibilidade | 8,0 | Duas árvores de código exigem sincronização cuidadosa |
| Performance | 8,0 | Medição local, sem teste de carga |
| Testes | 8,0 | 84% de linhas; lacunas em CLI, auxiliares e integração real |
| Documentação | 8,0 | Fluxos e limites documentados; execução de CI ainda pendente |
| Arquitetura | 8,0 | Simples e adequada; sem atomicidade entre banco e consumidores |
| Geral | **8,0** | **Pronto para homologação; não aprovado incondicionalmente para produção crítica** |

Aprovaria as correções como um PR com validação de CI obrigatória antes da promoção. O próximo passo operacional é executar a CI e uma coleta diária de homologação, conferir o novo snapshot e só então promover o código. Não houve publicação nesta auditoria.

## Fontes e reprodução

- Código e testes locais, comparados com a cópia anterior à auditoria e com o checkout Git de deploy.
- [Configuração oficial do Streamlit](https://docs.streamlit.io/develop/api-reference/configuration/config.toml); opção `client.showErrorDetails` também confirmada na versão instalada.
- [pip-audit, projeto PyPA](https://github.com/pypa/pip-audit): ferramenta usada para consultar vulnerabilidades conhecidas.
- Comandos de reprodução no README. Os testes de dados usam snapshots existentes e evidências simuladas em diretórios temporários; não consultam a API real.
