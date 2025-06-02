# Copyright (c) Microsoft Corporation. Todos os direitos reservados.
# Licenciado sob a Licença MIT.

# Bibliotecas padrão
import sys
import traceback
from datetime import datetime

# Bibliotecas web/aiohttp
from aiohttp import web
from aiohttp.web import Request, Response, json_response

# Componentes do Bot Framework
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    TurnContext,
    BotFrameworkAdapter,
    ConversationState,  # Estado da conversa
    UserState,          # Estado do usuário
    MemoryStorage       # Armazenamento volátil (memória)
)
from botbuilder.schema import Activity, ActivityTypes

# Módulos locais
from bots.tralhobot import Tralhobot  # Classe principal do bot
from config import DefaultConfig      # Configurações

# Carrega configurações (App ID, Password, Porta, etc.)
CONFIG = DefaultConfig()

# --------------------------------------------------
# 1. CONFIGURAÇÃO DO ADAPTADOR
# --------------------------------------------------
# Define credenciais e cria adaptador (conector com o Bot Framework)
SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)

# --------------------------------------------------
# 2. TRATAMENTO DE ERROS GLOBAL
# --------------------------------------------------
async def on_error(context: TurnContext, error: Exception):
    """Captura exceções não tratadas durante a execução do bot."""
    
    # Log no console (em produção, usar Application Insights)
    print(f"\n [on_turn_error] ERRO: {error}", file=sys.stderr)
    traceback.print_exc()  # Stack trace completo

    # Notifica o usuário
    await context.send_activity("Desculpe, algo deu errado no Tralhobot.")
    
    # Se no Emulator, envia detalhes técnicos
    if context.activity.channel_id == "emulator":
        trace_activity = Activity(
            label="ErroDetalhado",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        await context.send_activity(trace_activity)

# Registra o handler de erros
ADAPTER.on_turn_error = on_error

# --------------------------------------------------
# 3. CONFIGURAÇÃO DE ESTADO (MEMÓRIA)
# --------------------------------------------------
# Armazenamento temporário (não persistente)
MEMORY = MemoryStorage()

# Estados para gerenciar dados do usuário e da conversa
USER_STATE = UserState(MEMORY)           # Ex: preferências do usuário
CONVERSATION_STATE = ConversationState(MEMORY)  # Ex: histórico da conversa

# --------------------------------------------------
# 4. INICIALIZAÇÃO DO BOT
# --------------------------------------------------
# Cria a instância do bot com os estados configurados
BOT = Tralhobot(CONVERSATION_STATE, USER_STATE)

# --------------------------------------------------
# 5. ENDPOINT PRINCIPAL (/api/messages)
# --------------------------------------------------
async def messages(req: Request) -> Response:
    """Endpoint que recebe todas as mensagens do usuário."""
    
    # Verifica se o conteúdo é JSON
    if "application/json" not in req.headers.get("Content-Type", ""):
        return Response(status=415)  # Código 415 - Tipo de mídia não suportado
    
    try:
        body = await req.json()  # Extrai os dados da requisição
    except Exception as e:
        return Response(status=400, text=f"Erro ao parsear JSON: {e}")

    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    try:
        response = await ADAPTER.process_activity(
            activity, 
            auth_header, 
            BOT.on_turn  # Método que processa a mensagem
        )
    except Exception as e:
        traceback.print_exc() # Imprime o traceback
        return Response(status=500, text=f"Erro interno do adaptador: {e}")

    if response:
        return json_response(data=response.body, status=response.status)
    return json_response(data={}, status=201)  # 201 - Criado

# --------------------------------------------------
# 6. SERVIDOR WEB
# --------------------------------------------------
APP = web.Application()
APP.router.add_post("/api/messages", messages)  # Registra o endpoint

if __name__ == "__main__":
    try:
        # Inicia o servidor na porta configurada
        print(f"\n======== Servidor web rodando em http://127.0.0.1:{CONFIG.PORT} ========")
        web.run_app(APP, host="127.0.0.1", port=CONFIG.PORT) # host="127.0.0.1" forçado para IPv4
    except Exception as error:
        traceback.print_exc()
        raise error