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
Cada execução cria um diretório distinto. A rotina não apaga cópias anteriores.
Há também um artefato auxiliar no GitHub por sete dias; ele não substitui o Drive.
Revogar o acesso OAuth, esgotar a quota ou perder autorização causa falha explícita.
Se usar um cliente OAuth próprio em modo de teste, verifique a expiração da
credencial: ela pode exigir nova autorização. A conexão do Drive no ChatGPT
não fornece a credencial do runner.

Referências: https://rclone.org/drive/ e https://rclone.org/commands/rclone_check/.
