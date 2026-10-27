# Observatório de Crédito do Brasil

[Abrir painel](https://observatorio-credito-brasil.streamlit.app/)

Dashboard de Lukas Monken com 24 séries oficiais BCB/SGS e seis páginas de análise. Python, Pandas, SQL e Streamlit.

## Atualização diária

O workflow **Atualizar dados do Bacen** roda todos os dias às **19h17 de Brasília** (22h17 UTC), além de permitir execução manual em Actions → Run workflow. O agendamento do GitHub pode atrasar em períodos de alta demanda.

A rotina coleta novamente o histórico desde 2010, incluindo revisões, em um banco SQLite temporário. Séries mensais usam o histórico completo do endpoint oficial; séries diárias usam janelas inferiores a dez anos. Todos os indicadores são recalculados com as regras documentadas em `docs/metodologia.md`.

Somente uma coleta bem-sucedida das 24 séries, sem perda de cobertura da base publicada, pode atualizar o snapshot. Se ocorrer falha, o workflow termina com erro e a última base válida permanece online. Evidências brutas e diagnóstico ficam nos artifacts do Actions por sete dias. O histórico de commits preserva as versões publicadas.

O bot publica em `data/processed/<id-da-execução>` e atualiza `latest.json` somente depois da verificação de integridade; o Streamlit acompanha os commits na branch main. A atualização é diária, mas a frequência e a defasagem das observações continuam sendo as do Bacen. A Selic é agregada apenas para meses concluídos neste painel mensal.

Em repositórios públicos, o GitHub pode desativar agendamentos após 60 dias sem atividade. Consulte a aba Actions se a data de coleta deixar de avançar. As notificações de falha dependem das preferências da sua conta GitHub.

## Execução

Interface: `pip install -r requirements.txt` e `streamlit run dashboard/app.py`.

Coleta: `pip install -r requirements-update.txt` e `python scripts/update_data.py`.

Entrypoint no Streamlit: `dashboard/app.py`; Python 3.14. Sem secrets ou banco externo. Não publique `.env`, credenciais ou o diretório temporário `work/`.

## Arquitetura e validação

`observatorio/client.py` coleta e preserva respostas; `transform.py` trata o calendário e calcula indicadores; `db.py` persiste com upsert; `pipeline.py` produz snapshots; `snapshot.py` valida a leitura; `dashboard/app.py` exibe os dados. O job diário usa uma pasta exclusiva dentro de `work/` e nunca sobrescreve o snapshot ativo.

Não há login, dados privados nem uploads de usuários. A aplicação é deliberadamente pública e somente de leitura. `DATABASE_URL` é configuração do pipeline completo; o job diário escolhe seu próprio SQLite isolado. `TEST_DATABASE_URL` é reservado ao banco descartável de testes.

```bash
python -m pip install -r requirements-update.txt -r requirements-dev.txt
python -m pytest -q
ruff check observatorio dashboard scripts tests
mypy observatorio scripts/update_data.py
python -m coverage run -m pytest -q
python -m coverage report
```

O workflow `Verificar aplicação` adiciona um PostgreSQL 17 descartável para a integração. Sem `TEST_DATABASE_URL`, esse teste é ignorado localmente. A coleta diária continua às 19h17 de Brasília.

As correções foram homologadas e publicadas; os links das execuções estão na [auditoria](docs/auditoria.md). A CI validou PostgreSQL e a coleta real, sem certificar disponibilidade contínua da hospedagem. Snapshots por execução crescem no repositório; retenção e arquivamento devem ser definidos antes de operação prolongada.
