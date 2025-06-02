# Tralhobot - Agente de IA para Atendimento e SDR

## Visão Geral

O Tralhobot é um protótipo de bot conversacional em Python, usando o Microsoft Bot Framework. Ele atua como um assistente de atendimento (FAQ) e qualifica leads para o time de SDR da Tralhotec.

## Arquivos Principais

* **`app.py`**: Ponto de entrada do bot. Inicia o servidor web e conecta o bot ao Bot Framework.
* **`bots/tralhobot.py`**: Contém toda a lógica de conversação do bot (FAQ, fluxos de suporte e SDR).
* **`config.py`**: Armazena configurações como a porta do servidor, IDs do aplicativo e credenciais de e-mail.
* **`email_utils.py`**: Módulo para envio de logs de conversa por e-mail para stakeholders.

## Como Rodar

1.  **Requisitos:** Python 3.7+, Git, Visual Studio Code, Bot Framework Emulator.
2.  **Preparação:**
    * Navegue até a pasta `Codigo` do projeto.
    * Crie e ative um ambiente virtual (`python -m venv .venv` e `.venv\Scripts\activate.bat`).
    * Instale as dependências (`pip install botbuilder-core aiohttp`).
    * (Opcional) Configure `config.py` para as credenciais de e-mail.
3.  **Executar o Bot:** No terminal, com o ambiente virtual ativo, rode:
    ```bash
    python app.py
    ```
    O bot estará rodando em `http://127.0.0.1:3979`.

## Como Testar

1.  **Bot Framework Emulator:** Baixe e abra o Emulator.
2.  **Conectar:** Use a URL `http://127.0.0.1:3979/api/messages`. Deixe os campos de ID/Senha do App Microsoft vazios.
3.  **Interagir:** Digite "Olá", "preço", "suporte" ou "orçamento" para testar os fluxos.

## Versionamento

O projeto segue o Versionamento Semântico (`MAJOR.MINOR.PATCH`). A versão atual do protótipo é **`v1.0.0`**. Novas funcionalidades serão desenvolvidas em branches separadas (ex: `feature/nlp-integration`) antes de serem mescladas na branch `main`.
