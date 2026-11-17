# Retenção dos snapshots publicados

Esta política cobre as versões do catálogo principal publicadas em `data/processed/<snapshot_id>/`. Define o destino, os prazos e os critérios para uma futura implantação. A rotina de backup do Drive já tem retenção própria. Os arquivos independentes de inflação do IBGE, as respostas brutas de coleta e os artefatos temporários do Actions ficam fora deste plano.

## Ponto de partida

Na árvore do [commit ffa745c07c](https://github.com/lukasmonken/observatorio-credito-brasil/tree/ffa745c07cb8213192f7239788a93f3f84b62505), havia 53 diretórios de snapshot com manifesto. Seus 463 arquivos somavam 142.316.766 bytes (135,7 MiB), somando os tamanhos lógicos dos arquivos na árvore publicada. O tamanho de um clone depende também da compressão, dos objetos reutilizados e dos commits anteriores. Para repetir a medição, liste os arquivos com `git ls-tree -rl HEAD -- data/processed` e considere somente os arquivos dentro dos diretórios de versão.

## Onde e por quanto tempo guardar

| Finalidade | Local e retenção planejada |
| --- | --- |
| Servir o painel e permitir recuperação recente | Na árvore atual da `main`, manter o snapshot apontado por `latest.json`, seu antecessor publicado e todas as versões publicadas nos últimos 30 dias. Usar o instante de publicação, em UTC, para essa janela. |
| Reproduzir uma publicação histórica | Guardar **cada snapshot publicado**, inclusive os sem alteração econômica, em arquivo histórico no Drive, por prazo indeterminado. Usar uma raiz dedicada, irmã da pasta de backup rotativo, com um pacote imutável por ID. Revisar anualmente custo, espaço e condições de armazenamento. Alterar o prazo exige decisão do responsável. |
| Recuperar a operação após falha | Manter a política existente do backup operacional no Drive. Ela preserva as cópias recentes por 30 dias e uma por mês nos últimos 12 meses, além das proteções descritas no [guia de backup](backup.md#retenção-aprovada). |

A regra de 30 dias para a árvore da `main` só passa a valer após a implantação e a conferência do arquivo histórico. Até lá, todas as versões continuam disponíveis no repositório. Remover diretórios em um commit futuro reduz a árvore atual, mas os objetos anteriores continuam no histórico Git. Uma eventual migração de repositório ou reescrita de histórico constitui uma decisão separada, com impacto em clones, referências a commits e links já publicados.

## Implantação futura

1. **Inventariar.** Listar os snapshots e identificar, para cada um, o commit que o publicou, o instante da publicação e o ponteiro correspondente. Conciliar esses dados com os IDs no histórico de revisões, inclusive comparações sem eventos. Registrar lacunas e versões anteriores à implantação do histórico de revisões.
2. **Copiar.** Começar pela base ativa para a frente e recuperar também o acervo anterior. Para exportar uma versão antiga, usar um checkout isolado do commit cujo `latest.json` apontava para ela. O exportador existente lê o ponteiro daquela árvore. Guardar ZIP, SHA-256 e commit de origem sob o ID do snapshot, fora da raiz alcançada pela limpeza de backups. Em nova tentativa, conferir o pacote já gravado. Uma divergência para o mesmo ID interrompe a operação.
3. **Conferir e indexar.** Baixar o pacote remoto, comparar o SHA-256 com o calculado na origem e restaurá-lo em diretório novo. Validar ID, manifesto, contagens e arquivos de revisão. Registrar em índice versionado o ID, antecessor quando identificável, commit, data de publicação, caminho remoto, tamanho, checksum e evidência da restauração. Guardar uma cópia do índice e dos checksums em local independente dos ZIPs para permitir conferência e recuperação.
4. **Simular a retenção.** Gerar somente um relatório das versões que sairiam da árvore da `main`. Proteger a versão ativa e a anterior. Manter localmente qualquer versão sem prova de restauração, com inconsistência ou cujo consumidor ainda dependa do diretório antigo. Conferir painel, geração do site, comparação entre coletas, testes e backup. Revalidar o ponteiro antes de qualquer alteração futura para respeitar uma coleta concorrente.
5. **Liberar a migração.** O responsável revisa o inventário e o relatório. A fase operacional só começa após comprovar a restauração das versões candidatas e a continuidade das revisões. Uma falha de quota, permissão, checksum, índice ou download conserva a cópia de origem.

## Recuperação e continuidade das revisões

Para reproduzir uma coleta, selecione o ID no índice, obtenha o pacote e o checksum de referência e siga a [recuperação em diretório isolado](backup.md). Use o commit registrado para interpretar versões antigas de esquema. Compare o ID recuperado, a contagem de observações e os metadados com o índice. Para reativar uma versão em produção, prepare uma proposta separada e passe pelas verificações da `main`.

O snapshot ativo conserva os arquivos cumulativos `revision_history.csv` e `revision_history.json` quando previstos pelo esquema. A conferência deve preservar os IDs das comparações, sua ordem, os eventos, seus valores e as comparações sem eventos. A ausência desses arquivos em uma publicação anterior ao recurso é registrada como histórica. Consulte as [regras das revisões](revisoes.md).

Antes de ativar a retenção e depois a cada trimestre, testar a recuperação de uma versão antiga e de uma recente. Registrar os IDs, resultados e tempo de recuperação. Medir mensalmente o tamanho lógico na branch, o volume do arquivo histórico e o número de snapshots sem cópia verificada. A primeira implantação exige que esse último número seja zero para todo snapshot que possa sair da branch.
