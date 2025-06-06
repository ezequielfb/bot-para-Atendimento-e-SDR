from flask import Flask, request, jsonify
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext, ConversationState, UserState, MemoryStorage
from botbuilder.schema import Activity
from bots.tralhobot import Tralhobot
from config import DefaultConfig
import asyncio
import traceback
import os # Garante que 'os' está importado

from azure.ai.language.conversations import ConversationAnalysisClient
from azure.core.credentials import AzureKeyCredential

app = Flask(__name__)

CONFIG = DefaultConfig()

SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)

# === CORREÇÃO AQUI: CLASSE ADAPTER CUSTOMIZADA PARA RESOLVER 'os' NÃO DEFINIDO ===
class CustomBotFrameworkAdapter(BotFrameworkAdapter):
    def __init__(self, settings: BotFrameworkAdapterSettings):
        super().__init__(settings)
        # O RENDER_HOSTNAME agora é inicializado dentro do construtor
        # onde 'os' está no escopo correto.
        self._prod_service_url = "https://" + (os.environ.get("RENDER_EXTERNAL_HOSTNAME") or "")
        if not os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
             print("AVISO: Variável de ambiente RENDER_EXTERNAL_HOSTNAME não encontrada. Pode afetar respostas em produção.")
        print(f"ADAPTER: _prod_service_url inicializado como: {self._prod_service_url}")

    async def get_service_url(self, turn_context: TurnContext) -> str:
        service_url = turn_context.activity.service_url

        if self._prod_service_url and ("localhost" in service_url or not service_url):
            print(f"ADAPTER: serviceUrl '{service_url}' da atividade substituído por '{self._prod_service_url}'")
            return self._prod_service_url
        
        print(f"ADAPTER: Usando serviceUrl da atividade: '{service_url}'")
        return service_url

# Inicialize o adaptador customizado
ADAPTER = CustomBotFrameworkAdapter(SETTINGS) # Não precisa passar prod_service_url aqui, pois é inicializado internamente
# === FIM DA CORREÇÃO AQUI ===


MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# --- INICIALIZAÇÃO DO CLIENTE CLU ---
CLU_CLIENT = None
if CONFIG.CLU_ENDPOINT and CONFIG.CLU_API_KEY:
    try:
        CLU_CLIENT = ConversationAnalysisClient(
            endpoint=CONFIG.CLU_ENDPOINT,
            credential=AzureKeyCredential(CONFIG.CLU_API_KEY)
        )
        print("CLU Client inicializado com sucesso.")
    except Exception as e:
        print(f"ERRO: Falha ao inicializar CLU Client: {e}")
        traceback.print_exc()
else:
    print("AVISO: Credenciais CLU (ENDPOINT/API_KEY) não configuradas. O bot não usará o CLU para NLU.")

BOT = Tralhobot(
    CONVERSATION_STATE,
    USER_STATE,
    CLU_CLIENT,
    CONFIG.CLU_PROJECT_NAME,
    CONFIG.CLU_DEPLOYMENT_NAME
)

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

    async def _process_activity_async():
        try:
            await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        except Exception as e:
            print(f"Erro ao processar atividade assíncrona: {e}")
            traceback.print_exc()

    try:
        asyncio.run(_process_activity_async())
    except RuntimeError as e:
        print(f"RuntimeError ao executar asyncio.run(): {e}. Tentando outra abordagem...")
        traceback.print_exc()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_process_activity_async())
            print("Tarefa agendada com sucesso.")
        except RuntimeError:
            print("Não foi possível agendar a tarefa assíncrona: nenhum loop de eventos rodando.")
            return jsonify({"error": "Erro interno no servidor ao agendar processamento do bot."}), 500

    return jsonify({"status": "Solicitação recebida, processamento iniciado."}), 201

if __name__ == '__main__':
    print("Iniciando servidor de desenvolvimento Flask (apenas para testes locais)...")
    app.run(host="0.0.0.0", port=3979, debug=True)