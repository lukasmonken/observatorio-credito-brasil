# Histórico de revisões entre coletas

## Escopo

A atualização diária compara o candidato validado com o último snapshot publicado. O histórico persistente está nos arquivos `revision_history.csv` e `revision_history.json` do novo snapshot. Ele não depende do banco SQLite temporário e permanece disponível entre execuções do GitHub Actions.

A página **Histórico de revisões** mostra o resumo da última comparação, eventos acumulados, filtros por série, tipo e data de detecção, além de download CSV. O registro de comparações também é exportável e inclui execuções sem mudanças.

## Classificação

| Evento | Critério |
|---|---|
| Revisão de valor | A mesma série e referência já tinham valor numérico e passaram a ter outro valor |
| Nova referência | Valor para um mês posterior à última referência numérica anterior daquela série |
| Preenchimento histórico | Valor para uma lacuna ou referência anteriormente ausente, dentro ou antes do histórico já observado |
| Série incluída | Primeiros valores de uma série que não tinha observações numéricas na base anterior |

A comparação usa apenas `original`, por código SGS e mês de referência. Mudanças em valores reais por atualização do mês-base do IPCA, médias móveis ou outros indicadores derivados não geram revisões por si só. Variações entre meses distintos não são revisões: uma revisão compara o **mesmo mês em duas coletas**.

A diferença é valor novo menos valor anterior, na unidade original; para taxas percentuais, é expressa em pontos percentuais. Não se calcula variação percentual da revisão, evitando ambiguidade e divisão por zero. Novas observações e preenchimentos não têm valor anterior nem diferença; ausências não são convertidas em zero.

Os valores são lidos como texto do CSV e comparados com `Decimal`. Formatações numericamente equivalentes, como `1.0` e `1.00`, não geram eventos. Não se aplica tolerância relativa que pudesse esconder pequenas revisões de valores grandes. O CSV preserva os decimais; a tabela pode formatá-los para exibição.

## Rastreabilidade

Cada evento registra:

- Código SGS, nome, referência e unidade.
- Tipo da mudança, valor anterior, valor novo e diferença.
- Data/hora de detecção, com fuso UTC no arquivo e Brasília no painel.
- IDs dos snapshots anterior e novo.
- ID determinístico do evento, baseado no par de snapshots, série e referência.

A data de detecção é o momento da comparação pelo projeto. Não é a data oficial em que o Bacen divulgou ou revisou o dado. A funcionalidade registra uma mudança observada na série; não atribui a causa da revisão.

## Início e cobertura

O acompanhamento começa com a primeira atualização validada após a implantação, usando como base o snapshot publicado imediatamente anterior. O painel informa esse snapshot inicial e sua data. Não foram reconstruídas comparações antigas nem inventadas datas retroativas de detecção.

Se uma série mudar várias vezes entre duas coletas, somente a diferença entre os valores observados será registrada. Se o valor mudar e voltar ao original antes da próxima coleta, a mudança não será detectada. O histórico descreve as versões observadas pelo projeto.

## Publicação e integridade

A comparação ocorre após as validações de completude e cobertura, dentro do bloqueio de publicação. Eventos anteriores são preservados, e uma nova entrada no registro de comparações é criada mesmo quando não há mudanças. Cada novo snapshot carrega o histórico acumulado, de modo que a leitura não depende de procurar todos os diretórios antigos.

Os dois arquivos entram no manifesto com hashes SHA256 e versão de esquema. A leitura verifica hashes, IDs, encadeamento das comparações, unicidade, contagens e diferenças. Histórico corrompido não é reiniciado silenciosamente.

Somente depois dessas verificações o ponteiro `latest.json` é substituído. Falhas de comparação, escrita ou integridade preservam o ponteiro anterior. No GitHub, o snapshot e o histórico são publicados no mesmo commit. Repetir a publicação do mesmo diretório imutável é recusado e não duplica eventos.

A proteção existente contra perda de cobertura continua ativa: retirar um valor numérico ou substituí-lo por ausência bloqueia a publicação e aparece como falha operacional. Esse tipo de candidato rejeitado não é incorporado ao histórico publicado. Mudanças de unidade, frequência ou tipo de medida também exigem migração explícita, para não produzir diferenças entre valores incompatíveis.

## Arquivos e testes

- `observatorio/revisions.py`: comparação, classificação, persistência e validação do histórico.
- `scripts/update_data.py`: integração antes da promoção do snapshot diário.
- `observatorio/snapshot.py`: validação do histórico ao carregar snapshots instrumentados; compatibilidade com snapshots antigos.
- `dashboard/app.py`: consulta e exportação.
- `tests/test_revisions.py`: regressões de precisão decimal, zeros, negativos, preenchimentos, séries novas, corrupção, recuperação e publicação atômica.

A CLI local `python -m observatorio collect` mantém seu mecanismo SQL de revisões quando reutiliza o banco. O histórico aqui documentado é o do publicador diário `scripts/update_data.py`; ambos têm escopos distintos.

Os arquivos acumulados crescem com o número de eventos e comparações. A política futura de retenção dos snapshots deve preservar o histórico contido na versão ativa; esta entrega não remove versões antigas.
