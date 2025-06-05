from flask import Flask, request, jsonify
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext, ConversationState, UserState, MemoryStorage
from botbuilder.schema import Activity
from bots.tralhobot import Tralhobot
from config import DefaultConfig
import asyncio
import traceback

from azure.ai.language.conversations import ConversationAnalysisClient
from azure.core.credentials import AzureKeyCredential

app = Flask(__name__)

CONFIG = DefaultConfig()
SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# --- INICIALIZAÇÃO DO CLIENTE CLU ---
CLU_CLIENT = None
if CONFIG.CLU_ENDPOINT and CONFIG.CLU_KEY:
    try:
        CLU_CLIENT = ConversationAnalysisClient(
            endpoint=CONFIG.CLU_ENDPOINT,
            credential=AzureKeyCredential(CONFIG.CLU_KEY)
        )
        print("CLU Client inicializado com sucesso.")
    except Exception as e:
        print(f"ERRO: Falha ao inicializar CLU Client: {e}")
        traceback.print_exc()
else:
    print("AVISO: Credenciais CLU (ENDPOINT/KEY) não configuradas. O bot não usará o CLU para NLU.")

# Passe o cliente CLU e outras configs para o bot
BOT = Tralhobot(
    CONVERSATION_STATE,
    USER_STATE,
    CLU_CLIENT,
    CONFIG.CLU_PROJECT_NAME,
    CONFIG.CLU_DEPLOYMENT_NAME
)
# --- FIM DA INICIALIZAÇÃO CLU ---

# Remover a declaração 'loop = asyncio.get_event_loop()' globalmente
# e o bloco __main__ se for para produção com Gunicorn.

@app.route("/api/messages", methods=["POST"])
def messages():
    if "application/json" not in request.headers.get("Content-Type", ""):
        return jsonify({"error": "Tipo de conteúdo não suportado"}), 415

    try:
        body = request.json
    except Exception as e:
        print(f"Erro ao parsear JSON: {e}")
        traceback.print_exc()
        return jsonify({"error": "Bad Request - JSON Inválido"}), 400

    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    # O Bot Framework Adapter.process_activity é assíncrono.
    # Em um contexto síncrono de Flask, precisamos de um loop de eventos para executá-lo.
    # A maneira mais segura para este padrão é criar uma nova tarefa e executá-la
    # de forma síncrona, ou usar um worker assíncrono no Gunicorn.
    # Para simplicidade inicial, vamos usar asyncio.run() dentro de uma função.

    async def _process_activity_async():
        try:
            await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        except Exception as e:
            print(f"Erro ao processar atividade assíncrona: {e}")
            traceback.print_exc()

    try:
        # Tenta executar a tarefa assíncrona de forma síncrona.
        # Isso pode causar "RuntimeError: This event loop is already running" se o Gunicorn
        # estiver usando workers assíncronos que já gerenciam o loop.
        # Para workers síncronos padrão (threaded ou sync), asyncio.run() geralmente funciona
        # criando um novo loop para a execução da corrotina.
        asyncio.run(_process_activity_async())
    except RuntimeError as e:
        # Se o loop já estiver rodando (ex: Gunicorn com workers gevent/eventlet ou uvicorn/gunicorn com workers async),
        # você não pode simplesmente chamar asyncio.run() ou run_until_complete() diretamente.
        # Para produção com Flask e async, o ideal seria usar um worker Gunicorn assíncrono (ex: gunicorn -k gevent).
        # Para manter a compatibilidade com workers síncronos, esta é uma área de complexidade.
        print(f"RuntimeError ao executar asyncio.run(): {e}. Tentando outra abordagem...")
        traceback.print_exc()
        # Se for um RuntimeError, e o loop já estiver rodando, geralmente é um problema de configuração
        # de worker do Gunicorn ou uma tentativa de usar um loop existente de forma incorreta.
        # Para este bot, o Adapter.process_activity é quem envia a resposta, então podemos apenas
        # retornar 200/201 e deixar o adapter lidar com a resposta assíncrona.
        # Para garantir que a tarefa seja agendada, podemos usar:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_process_activity_async())
            print("Tarefa agendada com sucesso.")
        except RuntimeError:
            # Se não houver um loop rodando, algo está fundamentalmente errado com o ambiente Flask/Gunicorn
            print("Não foi possível agendar a tarefa assíncrona: nenhum loop de eventos rodando.")
            return jsonify({"error": "Erro interno no servidor ao agendar processamento do bot."}), 500


    # Retorna 201 Accepted imediatamente, pois a resposta do bot é enviada assincronamente pelo adaptador.
    # O Bot Framework Adapter é projetado para lidar com o envio da resposta.
    return jsonify({"status": "Solicitação recebida, processamento iniciado."}), 201

# O bloco __main__ é mantido apenas para testes locais de desenvolvimento.
# No Render, o Gunicorn inicia o app diretamente.
if __name__ == '__main__':
    # Adicione as variáveis de ambiente necessárias para teste local
    # Ex: export MicrosoftAppId="SEU_ID"
    #     export MicrosoftAppPassword="SUA_SENHA"
    #     export CLU_ENDPOINT="SEU_ENDPOINT"
    #     export CLU_KEY="SUA_KEY"
    #     export CLU_PROJECT_NAME="Tralhoboto_CLU"
    #     export CLU_DEPLOYMENT_NAME="production-deployment"
    print("Iniciando servidor de desenvolvimento Flask (apenas para testes locais)...")
    app.run(host="0.0.0.0", port=3979, debug=True)