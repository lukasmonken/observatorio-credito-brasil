# Dados públicos do Observatório Brasil

Em **Fontes e qualidade**, use **Baixar todas as séries · Parquet** para obter a base do catálogo principal. O arquivo cobre todos os indicadores e períodos do snapshot exibido, independentemente dos filtros da tela. As tabelas detalhadas de inflação do IBGE têm arquivos JSON próprios.

## Reutilização e redistribuição

CSV, Excel, JSON e Parquet podem reunir séries de produtores diferentes. Ao compartilhar um recorte, identifique o produtor, a pesquisa ou série, o distribuidor, a referência e a versão da coleta. Os campos `producer`, `distributor`, `code` e `source_url` estão no catálogo do JSON principal. Identifique também cálculos feitos pelo Observatório, como deflação ou médias móveis.

| Origem | Como verificar as condições |
| --- | --- |
| Banco Central do Brasil | Consulte a licença da ficha oficial de cada conjunto. Por exemplo, a ficha da meta Selic (SGS 432) indica ODbL. Para essa base, mantenha a atribuição e os avisos de licença e observe as condições de compartilhamento aplicáveis a bases derivadas. [Ficha da Selic](https://dadosabertos.bcb.gov.br/dataset/432-taxa-de-juros---meta-selic-definida-pelo-copom) · [Texto da ODbL](https://opendatacommons.org/licenses/odbl/1-0/) |
| IBGE | Identifique a pesquisa, a tabela SIDRA ou a série, o recorte e o período. Quando a distribuição ocorre pelo SGS, credite também esse canal. Consulte a documentação do produto para as condições de reutilização. Nas fontes consultadas, não identificamos uma licença única expressa para todas as tabelas e séries do IBGE usadas aqui. [SIDRA](https://sidra.ibge.gov.br/) · [Termos do portal do IBGE](https://www.ibge.gov.br/acesso-informacao/acoes-e-programas/politica-de-privacidade.html) |
| FGV IBRE | O IGP-M (SGS 189) e o INCC-M (SGS 7456) são produzidos pela FGV IBRE. A instituição distingue consulta gratuita e produtos licenciados e informa restrições contratuais à disseminação de dados licenciados. Não identificamos autorização geral para redistribuir as séries completas obtidas via SGS. Para republicar esses históricos, confirme a permissão aplicável com a FGV IBRE ou exclua essas séries do material redistribuído. [FGV Dados](https://portalibre.fgv.br/fgv-dados) · [Orientação oficial sobre as séries institucionais](https://portalibre.fgv.br/sites/default/files/users/user1816/tutorial-series-institucionais.pdf) |

Os direitos concedidos pelo titular do software abrangem o código de sua autoria. As séries econômicas e as bibliotecas incorporadas ou instaladas conservam os termos dos respectivos titulares.

## Onde encontrar os arquivos

O ponto de entrada estável é o [manifesto público site.json](https://lukasmonken.github.io/observatorio-credito-brasil/site.json). Resolva os nomes dos arquivos em relação ao endereço do manifesto.

| Campo de site.json | Conteúdo |
| --- | --- |
| `schema_version` | Versão inteira do contrato. A versão atual é 1. |
| `snapshot_id` | Identificador da coleta validada do catálogo principal. |
| `data`, `sha256` | Nome do JSON principal e SHA-256 dos bytes desse arquivo. |
| `parquet.file`, `parquet.sha256` | Nome e SHA-256 do Parquet de observações. |
| `inflation[]` | Arquivos de inflação detalhada disponíveis, com nome, descrição e SHA-256 próprios. As referências dessas tabelas podem divergir das do catálogo principal. |

O JSON principal contém `manifest` (coleta, data-base, contagens e mês-base dos valores reais), `catalog` (fichas das séries), `rows` (observações), `labels` e `formulas` (transformações). Inclui também metodologia, boletim, qualidade, revisões e monitoramento. `built_at` indica a geração do pacote. Consulte `manifest.as_of` para a data-base da coleta e a referência de cada linha para o período econômico.

## Dicionário das observações

Cada linha corresponde a uma série e uma referência. Use o par `code` e `date` para associar valores. O Parquet contém as mesmas linhas e valores de `rows` do JSON e inclui os campos descritivos da série.

| Campo no Parquet | Tipo | Interpretação |
| --- | --- | --- |
| `code` | int64 | Identificador do catálogo do Observatório. Consulte a ficha da série para o identificador e a origem oficiais. |
| `date`, `reference_period` | date32, texto | Data que identifica o período e rótulo mensal ou trimestral. No JSON, a data usa AAAA-MM-DD. |
| `name`, `frequency` | texto | Nome da série e frequência do catálogo. A agregação utilizada está em `catalog[].aggregation`. |
| `unit`, `source`, `source_url` | texto | Unidade de `original`, fonte e endereço de referência do catálogo. |
| `original` | float64 | Valor publicado para a referência, após a agregação da série. |
| Demais métricas | float64 anulável | Consulte `catalog[].allowed_transforms`, `labels` e `formulas`. Variações percentuais são expressas em %, diferenças de taxas em pontos percentuais e base 100 em índice. |

Um valor nulo representa uma medida ausente ou inaplicável. Zero é um valor observado. Preserve as lacunas temporais nas comparações. O arquivo traz `snapshot_id`, `schema_version`, `as_of` e `price_base_month` nos metadados do esquema Arrow.

## Ler com Python

O exemplo usa `requests` e `pyarrow`. Ele verifica o checksum e a identificação da coleta antes de selecionar os dados da Selic.

```python
import hashlib
from io import BytesIO
from urllib.parse import urljoin

import pyarrow.compute as pc
import pyarrow.parquet as pq
import requests

url = "https://lukasmonken.github.io/observatorio-credito-brasil/site.json"
response = requests.get(url, timeout=30)
response.raise_for_status()
manifesto = response.json()
if manifesto["schema_version"] != 1:
    raise ValueError("Versão de contrato desconhecida")

arquivo = manifesto["parquet"]
response = requests.get(urljoin(url, arquivo["file"]), timeout=60)
response.raise_for_status()
if hashlib.sha256(response.content).hexdigest() != arquivo["sha256"]:
    raise ValueError("Checksum divergente")

tabela = pq.read_table(BytesIO(response.content))
if tabela.schema.metadata[b"snapshot_id"].decode() != manifesto["snapshot_id"]:
    raise ValueError("Coleta divergente")
selic = tabela.filter(pc.equal(tabela["code"], 432))
print(selic.select(["date", "original", "unit"]).to_pandas().tail())
```

## Compatibilidade e disponibilidade

Na versão 1, leitores devem aceitar novos campos, métricas e séries. A remoção de campos obrigatórios ou mudanças incompatíveis de tipo ou significado exigem nova versão do contrato. O descritor Parquet é uma adição à versão 1 e pode estar ausente em cópias anteriores do manifesto.

Os arquivos são estáticos e acompanham as publicações do GitHub Pages, sem garantia de horário ou disponibilidade contínua. Se uma coleta falhar, o site pode continuar servindo o último snapshot validado. Consulte `monitoring` e as datas de referência antes de avaliar a atualidade dos números. Uma publicação pode substituir arquivos antigos. Para reproduzir uma análise, guarde o manifesto e os arquivos correspondentes. Se um arquivo desaparecer durante o download, releia o manifesto e reinicie a leitura da mesma versão publicada.
