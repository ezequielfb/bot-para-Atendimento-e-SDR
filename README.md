# Tralhobot - Agente de IA para Atendimento e SDR

## Visão Geral

O Tralhobot é um protótipo de bot conversacional em Python, usando o Microsoft Bot Framework. Ele atua como um assistente de atendimento (FAQ) e qualifica leads para o time de SDR de uma empresa.

## Status do Projeto

Este protótipo está implantado e operacional na plataforma Render.

## Como Rodar Localmente

1.  **Requisitos:** Python 3.7+, Git, Bot Framework Emulator.
2.  **Configuração:**
    * Clone este repositório.
    * Navegue até a pasta `Codigo` (ou a raiz do projeto onde `app_flask.py` está).
    * Crie e ative um ambiente virtual.
    * Instale as dependências: `pip install -r requirements.txt`
    * Configure as variáveis de ambiente `APP_ID` e `APP_PASSWORD` (use um `.env` ou defina no ambiente).
3.  **Executar:**
    ```bash
    python app_flask.py
    ```
    O bot estará rodando em `http://127.0.0.1:3979`.

## Como Testar Localmente (Bot Framework Emulator)

1.  Baixe e abra o [Bot Framework Emulator](https://github.com/microsoft/BotFramework-Emulator).
2.  Conecte-se à URL: `http://127.0.0.1:3979/api/messages`. Deixe os campos de ID/Senha do App Microsoft vazios.
3.  Comece a interagir com o bot.

## Deploy Online

O Tralhobot está disponível publicamente em:

* **URL do Serviço:** `https://bot-sdr.onrender.com/`
* **Endpoint do Bot:** Para interagir com o bot, envie requisições **POST** para `https://bot-sdr.onrender.com/api/messages`.

### Exemplo de Interação (cURL):

```bash
curl -X POST \
  [https://bot-sdr.onrender.com/api/messages](https://bot-sdr.onrender.com/api/messages) \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "message",
    "text": "Olá, bot!",
    "from": { "id": "usuarioteste", "name": "Usuário Teste" },
    "conversation": { "id": "conv001", "name": "Conversa Exemplo" },
    "recipient": { "id": "botsdr", "name": "Tralhobot" }
  }'
