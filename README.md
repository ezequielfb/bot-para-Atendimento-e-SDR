# Tralhobot - Agente de IA para Atendimento e SDR

## Visão Geral

O Tralhobot é um protótipo de bot conversacional em Python, usando o Microsoft Bot Framework. Ele atua como um assistente de atendimento (FAQ) e qualifica leads para o time de SDR de uma empresa (Tralhotec como exemplo).

## Arquivos Principais

* **`app_flask.py`**: Ponto de entrada do bot. Inicia o servidor web Flask e conecta o bot ao Bot Framework.
* **`bots/tralhobot.py`**: Contém toda a lógica de conversação do bot (FAQ, fluxos de suporte e SDR).
* **`config.py`**: Armazena configurações como a porta do servidor, IDs do aplicativo e credenciais de e-mail.
* **`email_utils.py`**: Módulo para envio de logs de conversa por e-mail para stakeholders.
* **`requirements.txt`**: Lista todas as dependências Python necessárias para o projeto, incluindo `gunicorn` para o deploy.

## Como Rodar (Localmente)

1.  **Requisitos:** Python 3.7+, Git, Terminal de sua escolha, Bot Framework Emulator, e **`ngrok`** (para testes com o Emulator).
2.  **Preparação:**
    * Clone este repositório.
    * Navegue até a pasta `Codigo` do projeto (ou a raiz do repositório).
    * Crie e ative um ambiente virtual (`python -m venv .venv` e `.venv\Scripts\activate.bat` no Windows).
    * Instale as dependências: `pip install -r requirements.txt`.
    * Configure as variáveis de ambiente `MicrosoftAppId` e `MicrosoftAppPassword` no seu ambiente local (ex: usando um arquivo `.env` com `python-dotenv`).
    * Se não tiver o `ngrok`, baixe em [ngrok.com/download](https://ngrok.com/download) e configure-o.
3.  **Executar o Bot:** No terminal, com o ambiente virtual ativo, rode:
    ```bash
    python app_flask.py
    ```
    O bot estará rodando em `http://127.0.0.1:3979`.

## Como Testar

O Tralhobot pode ser testado de duas formas:

1.  **Testando Localmente (com `ngrok` e Bot Framework Emulator):**
    * Com seu bot rodando localmente (passo 3 acima), abra um **novo terminal**.
    * Inicie o `ngrok` para tunelar a porta do seu bot: `ngrok http 3979`.
    * **Copie a URL HTTPS** que o `ngrok` gerar (ex: `https://abcd.ngrok-free.app`). **Esta URL muda a cada vez que o `ngrok` é iniciado na versão gratuita.**
    * Abra o **Bot Framework Emulator**.
    * Clique em "Connect to a bot" e use a URL copiada do `ngrok` **adicionando `/api/messages` no final** (ex: `https://abcd.ngrok-free.app/api/messages`). Deixe os campos de ID/Senha do App Microsoft vazios para testes locais.
    * Digite "Olá", "preço", "suporte" ou "orçamento" para testar os fluxos.

2.  **Testando o Bot Implantado Online (no Render):**
    * O bot está implantado e disponível em: `https://bot-sdr.onrender.com/`
    * Para interagir com ele, você precisa enviar requisições **POST** para o endpoint: `https://bot-sdr.onrender.com/api/messages`.
    * Você pode usar o **Bot Framework Emulator** (conectando com a URL do Render e fornecendo o `MicrosoftAppId` e o `MicrosoftAppPassword` reais que você obteve do Azure) ou ferramentas como Postman/Insomnia/cURL.

## Versionamento

A versão atual do protótipo é a **`v1.0.0`**. Novas funcionalidades serão desenvolvidas em branches separadas (ex: `feature/nlp-integration`) antes de serem mescladas na branch `main`.