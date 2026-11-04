# Dashboard no GitHub Pages

A interface estática mantém as oito páginas do Streamlit. Python continua responsável pela coleta, SQL, validação, inflação, médias e variações. O navegador recebe somente dados públicos do snapshot validado. O Streamlit permanece disponível durante a migração.

## Arquitetura

1. `Atualizar dados do Bacen` coleta diariamente às 19h17 de Brasília e publica o snapshot ou o diagnóstico de falha.
2. `Publicar dashboard no GitHub Pages` roda após a conclusão dessa rotina, inclusive quando ela falha. O evento `workflow_run` é necessário porque commits feitos pelo `GITHUB_TOKEN` não iniciam outro workflow por `push`.
3. `scripts/build_pages_data.py` usa os validadores existentes de snapshot e revisões. Gera JSON público com nome e checksum SHA-256, catálogo, metodologia, qualidade e monitoramento.
4. `web/build.mjs` empacota HTML, CSS e JavaScript. Gráficos e Excel são carregados sob demanda. Não há consulta ao Bacen quando alguém abre ou filtra a página.
5. O deploy depende de testes de cálculo e navegador. Uma falha no build mantém a publicação anterior.

O site verifica novas versões a cada cinco minutos e verifica a idade da coleta a cada minuto, inclusive quando nenhum job executa. O checksum detecta corrupção de transporte/publicação, não substitui a segurança da conta GitHub. A publicação não contém banco, arquivos brutos, secrets ou credenciais de backup.

## Funcionalidades preservadas

| Página | Funcionalidades |
|---|---|
| Visão geral | KPIs, mudanças da última coleta, crescimento real e inadimplência |
| Juros e crédito | Segmentos, seleção de séries, cores estáveis, comparação com dois eixos e gráficos separados |
| Famílias | Endividamento, comprometimento de renda e inadimplência |
| Explorador | Transformações permitidas, período, base 100 no recorte, CSV e Excel com quatro abas |
| Relações | Correlação de Pearson, alinhamento por mês calendário, defasagens de 0 a 24 meses |
| Revisões | Filtros, histórico completo, comparações sem eventos, comparação líquida entre duas coletas e CSV |
| Dicionário | Busca, fonte oficial, unidades, fórmulas, limitações e catálogo JSON |
| Fontes e qualidade | Última tentativa/sucesso/duração, falhas por série, defasagem e validações |

Os testes comparam resultados JavaScript com o Python. Revisões são mantidas como texto decimal e subtraídas com inteiros de precisão arbitrária; não passam por ponto flutuante. Correlações utilizam tolerância numérica de 1e-12. Valores ausentes continuam ausentes. O Excel contém valores, sem fórmulas executáveis.

## Executar localmente

Requisitos: Python 3.14 e Node.js 22 com npm.

```bash
python -m pip install -r requirements-update.txt
python scripts/build_pages_data.py
python web/tests/parity.py
cd web
npm ci --ignore-scripts
npm test
npm run build
python3 -m http.server 4173 --bind 127.0.0.1
```

Abra `http://127.0.0.1:4173/dist/`. Testar em um subdiretório também verifica a compatibilidade com o caminho do repositório no Pages.

Para testes reais de interface, em outro terminal, pare antes o servidor manual:

```bash
cd web
npx playwright install chromium
npm run test:browser
```

No Linux/CI, use `npx playwright install --with-deps chromium`. A suíte verifica oito páginas, seleção e legendas, exportações CSV/Excel, busca, responsividade e falhas de integridade/rede. Diagnósticos ficam nos artifacts `pages-qa-*` por sete dias.

## Ativar a hospedagem

No repositório, **Settings → Pages → Build and deployment → Source → GitHub Actions**. Depois execute **Actions → Publicar dashboard no GitHub Pages → Run workflow** na branch `main`.

Endereço previsto: https://lukasmonken.github.io/observatorio-credito-brasil/

Ativar Pages exige administração do repositório. Se `configure-pages` retornar 404, confira essa configuração. Não é necessário criar token ou secret novo. O job de deploy usa apenas `pages: write` e `id-token: write`; pull requests apenas testam e nunca publicam.

## Limites e manutenção

- A melhoria elimina a inicialização do servidor Streamlit e o processamento Python por interação. O tempo real ainda depende da rede, dispositivo, volume dos dados e disponibilidade do Pages.
- Os arquivos são públicos e servidos pelo GitHub. Não adicione dados privados ao snapshot.
- Indisponibilidade geral do GitHub também pode afetar publicação e monitoramento; o backup externo existente continua necessário.
- GitHub Actions pode atrasar agendamentos. A frequência diária não muda a periodicidade econômica das séries.
- O frontend usa Plotly basic e o bundle de navegador do ExcelJS. `npm audit` apontou avisos moderados nas dependências transitivas de ferramentas Node do ExcelJS (glob/minimatch e uuid); glob/minimatch pertencem ao writer de streams Node, que não faz parte da interface de navegador. O aviso de uuid afeta v3/v5/v6 com buffer; o ExcelJS referencia v4 na formatação condicional, recurso que esta exportação não utiliza. O build não recebe padrões glob enviados por usuários. Não foram aplicados overrides de versões principais incompatíveis. Reavaliar ao atualizar ExcelJS; não interpretar os testes como certificação de segurança.
- Streamlit e Pages compartilham os dados e fórmulas Python, mas têm camadas de apresentação distintas. Mudanças de regras ou novas páginas devem atualizar os testes de equivalência e ambas as interfaces durante a transição.
