from flask import Flask, request, jsonify
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext, ConversationState, UserState, MemoryStorage
from botbuilder.schema import Activity
from bots.tralhobot import Tralhobot
from config import DefaultConfig
import asyncio

app = Flask(__name__)

CONFIG = DefaultConfig()
SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)
BOT = Tralhobot(CONVERSATION_STATE, USER_STATE)

loop = asyncio.get_event_loop()

@app.route("/api/messages", methods=["POST"])
def messages():
    if "application/json" in request.headers["Content-Type"]:
        body = request.json
    else:
        return jsonify({"error": "Tipo de conteúdo não suportado"}), 415

    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    async def call_bot():
        await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)

    task = loop.create_task(call_bot())
    loop.run_until_complete(task)
    return jsonify({"status": "mensagem processada"})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3979, debug=True)
