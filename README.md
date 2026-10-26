# Observatório de Crédito — versão online

Dashboard Python de Lukas Monken com 24 séries oficiais BCB/SGS.
Esta distribuição contém o snapshot real de 26/10/2026 e não depende de PostgreSQL, SQLite ou do computador do autor para exibir os dados.

## Publicar no Streamlit Community Cloud
1. Crie um repositório GitHub chamado `observatorio-credito-brasil` e envie o CONTEÚDO desta pasta, preservando suas subpastas. Não envie apenas o ZIP.
2. Entre em https://share.streamlit.io com sua conta e conecte o repositório GitHub conforme solicitado pela plataforma.
3. Clique em **Create app** → **Yup, I have an app**.
4. Selecione o repositório e a branch `main`.
5. Em **Main file path**, use `dashboard/app.py`.
6. Em **Advanced settings**, selecione **Python 3.14**. Não são necessários secrets.
7. Escolha um subdomínio disponível e clique em **Deploy**.
8. Ao abrir, confira as seis páginas e o download CSV. Configure o acesso para permitir visitantes se for compartilhar no portfólio.

O link definitivo só existe após a publicação bem-sucedida. Não há URL publicada nesta entrega.

## Atualização dos dados
Os dados são um snapshot, com corte identificado na interface. Não há atualização agendada nesta distribuição.
No projeto completo, execute a coleta, depois `python scripts/prepare_streamlit_cloud.py`. Envie os arquivos atualizados ao mesmo repositório para republicar. Não publique `.env`, `.venv`, senhas ou bancos locais.

## Execução local
```bash
python -m pip install -r requirements.txt
streamlit run dashboard/app.py
```

Fonte: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
