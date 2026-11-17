# Observatório Econômico do Brasil

Painel público de Lukas Monken para acompanhar a economia brasileira. O **Panorama Brasil** reúne os indicadores mais recentes com o período de referência de cada medida. O menu dá acesso às análises de juros e crédito, composição do crédito, inflação, trabalho e renda, setor externo e atividade econômica.

[Abrir o painel no GitHub Pages](https://lukasmonken.github.io/observatorio-credito-brasil/) · [Abrir a versão Streamlit](https://observatorio-credito-brasil.streamlit.app/)

## Explorar e baixar dados

- **Explorador de indicadores** permite escolher a série, o período e a transformação e baixar o recorte em CSV ou Excel.
- **Dicionário e metodologia** reúne fontes, unidades, fórmulas e limitações. A barra lateral do site mostra o total de séries e observações da versão publicada.
- **Fontes e qualidade** informa o resultado da última coleta e permite baixar o catálogo principal em Parquet. O manifesto público aponta para os arquivos da publicação. [Dados públicos e exemplo de leitura](docs/dados-publicos.md)
- **Histórico de revisões** mostra o que mudou entre coletas e permite exportar a comparação. [Regras e limites](docs/revisoes.md)

Os guias temáticos descrevem os recortes e cuidados de interpretação. [Composição do crédito](docs/composicao-credito.md) · [Inflação](docs/inflacao.md) · [Trabalho e renda](docs/trabalho-renda.md) · [Setor externo e câmbio](docs/setor-externo.md) · [Crescimento e atividade](docs/crescimento-atividade.md)

## Direitos de uso

Lukas Monken reserva os direitos sobre o código de sua autoria. Para reutilizá-lo em outro projeto, consulte o [aviso de direitos do código](LICENSE).

Para redistribuir séries ou arquivos exportados, consulte as condições de cada produtor e mantenha a atribuição da fonte. [Condições de reutilização dos dados](docs/dados-publicos.md#reutilização-e-redistribuição)

## Atualização e publicação

O GitHub Actions agenda **Atualizar dados do Bacen** para 19h17 e **Atualizar inflação do IBGE** para 19h43, no horário de Brasília. A execução pode começar depois do horário agendado. As séries mantêm a frequência e a defasagem da fonte. Por exemplo, a Selic diária entra no painel após a conclusão do mês, e o PIB conserva o trimestre de referência.

A coleta do catálogo principal usa SQLite temporário e valida todas as séries esperadas e sua cobertura antes de promover uma nova versão. As tabelas detalhadas de inflação do IBGE têm coleta própria. O aplicativo do Observatório abre uma proposta de atualização e a integra à `main` após os testes obrigatórios. Uma falha na coleta principal preserva a última base válida e gera um diagnóstico.

O Pages prepara os arquivos públicos a partir da versão validada. O Streamlit lê os arquivos do snapshot apontado por `data/processed/latest.json`. Em **Fontes e qualidade**, o visitante pode conferir a última tentativa, o último sucesso e as séries com falha. [Hospedagem e testes do site](docs/github-pages.md) · [Monitoramento e recuperação](docs/monitoramento.md) · [Backup dos dados](docs/backup.md) · [Retenção dos snapshots](docs/retencao-snapshots.md)

## Executar localmente

Para abrir o painel Streamlit com os dados do repositório, use Python 3.14 na raiz do projeto.

```bash
python -m pip install -r requirements.txt
streamlit run dashboard/app.py
```

Para executar a coleta principal em um ambiente preparado para atualização, use os comandos abaixo. Para trabalhar na interface estática, siga o [guia de execução local do Pages](docs/github-pages.md#executar-localmente).

```bash
python -m pip install -r requirements-update.txt
python scripts/update_data.py
```

## Arquitetura e validação

Python, Pandas e NumPy organizam as séries e calculam os indicadores. O pipeline usa SQLAlchemy com SQLite e tem integração testada com PostgreSQL. O site público usa JavaScript e Plotly para filtros e visualizações. A documentação detalha os arquivos, as consultas e as regras de cálculo. [Tecnologias e exemplos SQL](docs/tecnologias.md) · [Metodologia](docs/metodologia.md)

```bash
python -m pip install -r requirements-update.txt -r requirements-dev.txt
ruff check observatorio dashboard scripts tests
mypy observatorio scripts/update_data.py scripts/monitor_update.py scripts/monitor_backup.py scripts/monitor_pages.py
python -m coverage run -m pytest -q
python -m coverage report
```

O workflow **Verificar aplicação** usa um PostgreSQL descartável para o teste de integração. Em execução local, esse teste usa `TEST_DATABASE_URL`. O histórico de verificações anteriores está na [auditoria técnica](docs/auditoria.md).
