# Backup dos dados

O comando abaixo exporta o snapshot ativo e seu histórico acumulado de revisões.
Use um destino fora da pasta do projeto e um nome novo para cada cópia:

```sh
python scripts/backup_data.py --output /caminho/externo/credito-2026-10-29.zip
```

O ZIP contém `data/processed/latest.json` e o snapshot correspondente, incluindo
catálogo, indicadores, cobertura, qualidade, manifesto e histórico de revisões
quando presente. Nenhum histórico anterior à implantação desse recurso é recriado.

A exportação valida o snapshot original, os bytes copiados e o ZIP final. O SHA256
exibido identifica o arquivo exportado. Arquivos existentes nunca são sobrescritos.
Credenciais, `.env`, banco temporário, logs e código não entram no arquivo.

**Operação:** copie o ZIP para armazenamento independente do repositório. Uma
pasta local fora do projeto, sozinha, não protege contra perda do computador.
O comando local não envia arquivos pela rede. O workflow descrito abaixo faz o envio automático após a configuração inicial.
A primeira cópia externa pode ser guardada manualmente; uma rotina automática
requer configurar um destino e sua autenticação no ambiente do job.

Este é um backup dos dados, não uma imagem completa da aplicação. Preserve também
uma referência à versão do código utilizada. Retenção e recuperação automatizada
são etapas separadas; nenhum backup antigo é apagado por esta rotina.

## Automação no Google Drive

O workflow `backup-data.yml` executa depois de uma coleta bem-sucedida na `main`,
ou manualmente em Actions. Ele lê a versão publicada mais recente da `main`,
valida o snapshot, exporta ZIP, SHA256 e commit de origem, envia para o Drive e
confere os bytes remotos. Uma publicação posterior pode ser incluída caso tenha
ocorrido antes do checkout; o commit registrado identifica exatamente a cópia.
Falhas no backup não impedem a atualização do painel, mas deixam este workflow
com status de falha. As notificações dependem da configuração da conta GitHub.

### Autorização inicial necessária

1. Instale o [rclone](https://rclone.org/install/) no seu computador.
2. Execute `rclone config` e crie um remote chamado **backup**, tipo Google Drive.
   Prefira o escopo `drive.file` (arquivos criados pelo aplicativo). Autorize no
   navegador a conta que deve receber os backups. Não use uma conta de serviço
   para um Drive pessoal. O rclone orienta a configuração OAuth.
3. Execute `rclone config file` para localizar o arquivo. Copie **somente a seção
   `[backup]`** para o secret `BACKUP_RCLONE_CONFIG` em GitHub → Settings → Secrets
   and variables → Actions. Não publique o token em código, logs ou chat.
   Esta configuração deve estar sem criptografia no secret; o arquivo temporário
   do runner recebe permissão privada e é removido ao terminar o envio.
4. Execute **Backup dos dados no Google Drive → Run workflow** e confirme sucesso
   na etapa de envio e verificação. Só então considere a automação operacional.

Destino: `Observatorio-Credito-Brasil/<run_id>-<tentativa>/` no Drive autorizado.
Cada execução cria um diretório distinto. Após a verificação, aplica a política de retenção abaixo.
Há também um artefato auxiliar no GitHub por sete dias; ele não substitui o Drive.
Revogar o acesso OAuth, esgotar a quota ou perder autorização causa falha explícita.
Se usar um cliente OAuth próprio em modo de teste, verifique a expiração da
credencial: ela pode exigir nova autorização. A conexão do Drive no ChatGPT
não fornece a credencial do runner.

Referências: https://rclone.org/drive/ e https://rclone.org/commands/rclone_check/.

## Retenção aprovada

Depois de um novo backup conferido, a rotina preserva todas as cópias dos últimos
30 dias (janela de 720 horas) e a mais recente de cada um dos últimos 12 meses
civis, incluindo o mês corrente, no horário de Brasília. A cópia atual e a mais
recente são sempre preservadas. Meses sem cópias não são preenchidos artificialmente.
A idade é a data de modificação do ZIP criado pelo workflow, não a referência
econômica das séries. Cada ZIP contém todo o histórico acumulado de revisões.

A limpeza é restrita à pasta Observatorio-Credito-Brasil e a subpastas no padrão
run_id-tentativa com exatamente os três arquivos conhecidos. Cópias incompletas,
nomes duplicados, datas inválidas, futuras ou arquivos desconhecidos são ignorados.
Uma nova conferência do backup atual é obrigatória antes de planejar a limpeza.
O plano é salvo antes da exclusão e as pastas são relidas para detectar mudanças.
Os arquivos elegíveis são enviados à lixeira do Drive, nunca apagados definitivamente
pela rotina. Ela não esvazia a lixeira; a liberação de espaço depende do Drive.
Se uma exclusão falhar no meio, o relatório registra os arquivos já removidos;
restos incompletos ficam preservados para revisão manual.

O relatório report.json acompanha o artefato auxiliar do workflow por sete dias.
Para simular, execute scripts/retain_backups.py com --config, --current,
--verified-local e --report, sem --apply. A simulação também exige uma cópia
atual conferida e não altera o Drive.

## Recuperação isolada e teste automático

Depois de cada envio conferido, o workflow baixa o backup do Drive novamente,
verifica o SHA256 contra a cópia original da execução e recupera os dados em uma
pasta temporária nova. A aplicação atual é executada com essa base recuperada:
todas as oito páginas precisam carregar sem exceções nem mensagens de erro.
O teste não lê os dados publicados como alternativa. A retenção só começa depois
de aprovada a recuperação. Se a verificação falhar, o workflow falha e preserva
os backups antigos. O relatório `recovery-report/result.json` identifica o snapshot,
quantidade de registros, séries, checksum e páginas verificadas.

Para recuperar uma cópia manualmente, baixe do Drive o ZIP e seu `SHA256SUMS`.
Copie os 64 caracteres do checksum correspondente ao ZIP e execute na pasta do
projeto com suas dependências instaladas:

```sh
python scripts/restore_backup.py /caminho/credito-RUN-TENTATIVA.zip \
  --destination /caminho/recuperacao-nova \
  --sha256 CHECKSUM_DE_64_CARACTERES \
  --check-dashboard \
  --report /caminho/relatorio-recuperacao.json
```

O destino não pode existir, nem estar vazio. ZIPs com caminhos externos, links
simbólicos, arquivos desconhecidos, nomes duplicados ou mais de 256 MiB compactados
ou descompactados são rejeitados. Após a extração restrita, os dados passam pelas
mesmas validações de esquema, hashes e histórico de revisões usadas pelo painel.
Uma falha de validação dos dados não publica o diretório recuperado. Se o teste da
interface falhar, a base já validada permanece disponível para diagnóstico, mas não
há relatório de sucesso. O SHA256 verifica integridade, não autenticidade: use uma
cópia e um checksum de origem confiável.

Esta operação recupera **os dados**, sem substituir `data/processed/latest.json`
da aplicação em produção e sem baixar/executar código do ZIP. A versão do código
é identificada por `source-commit.txt`; o teste automático usa o código atual.
Reverter a aplicação em produção continua sendo uma decisão separada. O teste de
interface usa AppTest e não substitui uma inspeção visual no navegador.
