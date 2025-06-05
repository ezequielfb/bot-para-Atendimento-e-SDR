from flask import Flask, request, jsonify
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext, ConversationState, UserState, MemoryStorage
from botbuilder.schema import Activity
from bots.tralhobot import Tralhobot
from config import DefaultConfig
from azure.ai.language.conversations import ConversationAnalysisClient
from azure.core.credentials import AzureKeyCredential
import asyncio
import traceback # Adicionado para traceback

app = Flask(__name__)

CONFIG = DefaultConfig()
SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)
BOT = Tralhobot(CONVERSATION_STATE, USER_STATE)

# Usar asyncio.run() no contexto Flask se possível, ou gerenciar o loop cuidadosamente.
# Para simplicidade em muitos frameworks web, rodar código assíncrono pode precisar de padrões específicos.
# Este gerenciamento básico de loop pode funcionar para casos simples, mas pode ser complexo.
# Considere extensões Flask como Flask-Executor ou usar Quart se o assíncrono se tornar pesado.
loop = asyncio.get_event_loop()

@app.route("/api/messages", methods=["POST"])
def messages():
    if "application/json" not in request.headers.get("Content-Type", ""):
        return jsonify({"error": "Tipo de conteúdo não suportado"}), 415

    try:
        body = request.json
    except Exception as e:
        print(f"Erro ao parsear JSON: {e}")
        return jsonify({"error": "Bad Request - JSON Inválido"}), 400

    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    async def call_bot():
        try:
            # Nota: O process_activity do Adaptador Bot Framework é assíncrono
            # e espera lidar com o envio da resposta de volta ao canal.
            # No Flask, podemos não receber um objeto de resposta direto desta forma
            # a menos que o adaptador seja especificamente projetado para integração com Flask
            # que modifique este comportamento. O objetivo principal é o processamento.
            await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        except Exception as e:
            print(f"Erro ao processar atividade: {e}")
            traceback.print_exc()
            # Opcionalmente, tente enviar uma mensagem de erro de volta se possível,
            # mas isso pode falhar se o contexto da requisição inicial for perdido.

    # Executa a função assíncrona dentro do loop de eventos existente
    # Tenha cuidado com chamadas bloqueantes em contextos assíncronos dentro do Flask
    try:
        # Garante que o loop esteja rodando se já não estiver (pode ser necessário dependendo da configuração Flask/Gunicorn)
        if not loop.is_running():
             # Para workers síncronos padrão do Gunicorn/Flask, run_until_complete pode funcionar
             loop.run_until_complete(call_bot())
        else:
            # Se o loop já estiver rodando (ex: em uma configuração async do Flask como Quart ou workers Gunicorn específicos),
            # agende a tarefa de forma diferente.
            # Para workers síncronos padrão do Flask, run_until_complete pode bloquear inadequadamente.
            # Uma abordagem comum é usar asyncio.run_coroutine_threadsafe se rodando de uma thread diferente,
            # ou garantir que a configuração do worker Flask suporte tarefas assíncronas corretamente.
            # Abordagem mais simples para workers síncronos básicos do Gunicorn:
            asyncio.run(call_bot()) # Usa asyncio.run por simplicidade se o gerenciamento do loop for complexo

    except RuntimeError as e:
         # Fallback se o loop já estiver rodando e asyncio.run causar problemas
         print(f"RuntimeError ao executar tarefa assíncrona, tentando create_task: {e}")
         # Isso não espera pela conclusão, o que pode ser ok para tarefas "dispare e esqueça"
         # mas não se a resposta depender disso.
         # Considerar alternativas mais robustas para produção.
         task = loop.create_task(call_bot())


    # Retorna 201 Accepted imediatamente, pois a resposta do bot é enviada assincronamente pelo adaptador.
    return jsonify({"status": "Solicitação recebida, processamento iniciado."}), 201

# Remova o bloco a seguir, pois o Gunicorn iniciará o app diretamente
# usando a instância 'app' definida acima.
# if __name__ == '__main__':
#     # Este bloco é para desenvolvimento/depuração local, não para deploy com Gunicorn
#     # Gunicorn usa o comando 'gunicorn src.app_flask:app'
#     # Ele automaticamente se liga a 0.0.0.0 e à variável de ambiente PORT
#     print("Iniciando servidor de desenvolvimento Flask...")
#     app.run(host="0.0.0.0", port=3979, debug=True)
