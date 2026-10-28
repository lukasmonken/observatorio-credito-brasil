# Monitoramento da atualização

O monitoramento distingue três situações: falha da coleta ou publicação, ausência de execução e defasagem da referência econômica. Não altera indicadores nem a periodicidade de divulgação do Bacen.

## Onde consultar

- **Painel → Fontes e qualidade:** última tentativa, último sucesso, duração, etapa, códigos das séries com falha e tabela de atualidade das séries.
- **GitHub Actions → Atualizar dados do Bacen:** execução diária, resumo operacional e evidências técnicas.
- **GitHub Actions → Monitorar atualização do Bacen:** verificação independente a cada seis horas.

O painel mostra um aviso global após 30 horas sem atualização validada ou quando o estado registrado indica falha. O aviso é recalculado ao carregar/interagir com a aplicação; uma aba deixada aberta não é um monitor ativo em segundo plano.

## Registro da tentativa

`data/processed/monitoring.json` guarda status, início, término, duração, último sucesso, etapa e códigos das séries que falharam. Horários são armazenados com fuso UTC e apresentados em Brasília. A duração vai do início da preparação até o registro do resultado, incluindo instalação, testes e coleta; não inclui o envio ao GitHub.

O workflow registra o resultado com `if: always()`. Quando há falha antes da publicação, envia apenas o arquivo de monitoramento, preservando o snapshot publicado. Em caso de sucesso, envia juntos o snapshot validado e o estado operacional. Uma recuperação limpa os códigos de falha anteriores. Não são publicados tokens, caminhos de erro ou stack traces nesse resumo; detalhes ficam nos logs e artifacts por sete dias.

O estado em andamento é local ao runner; o painel recebe a tentativa concluída após o commit. Se o runner for encerrado abruptamente ou o push falhar, esse resumo pode não chegar ao site. Por isso o verificador independente também consulta a conclusão real do workflow na API do GitHub.

Antes da primeira execução instrumentada, o painel usa a data de criação do snapshot como referência do último sucesso e informa que os detalhes da tentativa não estão registrados. Não inventa duração ou horário de tentativa.

## Verificação independente

`.github/workflows/monitor-data.yml` executa às **21h47, 03h47, 09h47 e 15h47 de Brasília** (cron UTC `47 0,6,12,18 * * *`). Também é acionado após a conclusão do workflow diário, para detectar falhas sem esperar a próxima janela de seis horas. O workflow diário permanece às 19h17 de Brasília.

`scripts/monitor_update.py check` verifica:

- Mais de 30 horas sem sucesso registrado na base publicada.
- Falha ou cancelamento na última execução do job diário, inclusive erro no push.
- Nenhuma execução do job diário nas últimas 30 horas.
- Execução pendente ou em andamento há mais de uma hora.
- Metadados inválidos ou impossibilidade de consultar a API (o verificador termina com erro, sem declarar estado saudável).

O verificador tem apenas `contents: read` e `actions: read`. Usa o token efêmero do GitHub Actions, com timeout na consulta. Não precisa de senha, token pessoal, serviço pago nem dependências Python adicionais.

Falhas aparecem em vermelho no Actions e no resumo da execução. Notificações por e-mail/web dependem das preferências da conta em **GitHub → Settings → Notifications → Actions**. Este recurso não configura a conta do usuário nem envia mensagens externas por conta própria.

Com verificação a cada seis horas, a detecção pode ocorrer até aproximadamente seis horas depois do limiar de 30 horas, mais eventuais atrasos do agendador. Como ambos os jobs dependem do GitHub, indisponibilidade geral ou desativação dos agendamentos exige verificação externa/manual. Isso não é uma garantia de disponibilidade contínua.

## Atualidade da fonte

A tabela do painel usa a última referência com valor numérico de cada série e o `max_lag_days` específico do catálogo. Os dias são contados a partir do primeiro dia do mês de referência, como nas verificações de qualidade existentes. A Selic exibida é mensal e considera meses concluídos.

“Acima do limite” é um alerta operacional, não uma afirmação de descumprimento do calendário oficial do Bacen. Uma coleta bem-sucedida sem mês novo pode ser perfeitamente normal. A tabela é recalculada na data de consulta, mesmo que o snapshot não tenha mudado.

## Diagnóstico e recuperação

1. Abra a execução com falha no Actions e identifique a etapa.
2. Se a falha for de coleta/validação, consulte os códigos no painel e os artifacts da execução. A última base válida deve continuar disponível.
3. Se for de publicação, confira o erro de push/permissão. O monitor independente detecta a conclusão com falha mesmo quando o painel ainda mostra a tentativa anterior.
4. Corrija a causa e execute **Atualizar dados do Bacen → Run workflow**. A nova tentativa continua sujeita às mesmas validações; não edite o snapshot para contorná-las.
5. Depois do sucesso, execute **Monitorar atualização do Bacen → Run workflow** para confirmar a recuperação.

## Código e testes

`observatorio/monitoring.py` lê/valida metadados e calcula os estados. `scripts/monitor_update.py` registra início/fim e consulta as execuções. `dashboard/app.py` apresenta os resultados.

Os testes cobrem o limiar de 30 horas, falhas com base recente, interrupções, execução ausente ou presa, recuperação, preservação do último sucesso, ausência/erro de metadados, omissão de detalhes internos e separação entre defasagem da fonte e falha operacional. A interface é testada mantendo os gráficos disponíveis em caso de falha.
