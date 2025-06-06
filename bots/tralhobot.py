# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
from datetime import datetime
from typing import Any, Dict

from botbuilder.core import (
    ActivityHandler, TurnContext, MessageFactory, UserState, 
    ConversationState, CardFactory
)
from botbuilder.schema import ChannelAccount, ActivityTypes, Attachment, ActionTypes, CardAction

from config import DefaultConfig
from email_utils import send_log_to_stakeholders

from azure.ai.language.conversations import ConversationAnalysisClient
from azure.core.credentials import AzureKeyCredential

CONFIG = DefaultConfig()

FAQ_DATA = {
    "preço": "Nossos preços variam dependendo da solução e do escopo do projeto. Para obter um orçamento personalizado, por favor, agende uma conversa com um de nossos especialistas.",
    "implementação": "Nosso processo de implementação para pequenas empresas geralmente inclui: 1. Análise de requisitos, 2. Configuração da plataforma, 3. Migração de dados (se aplicável), 4. Treinamento, 5. Suporte pós-implementação. Podemos detalhar isso em uma reunião.",
    "microsoft teams": "Sim, somos especialistas em soluções Microsoft, incluindo a implementação e otimização do Microsoft Teams para colaboração.",
    "documentação": "Oferecemos soluções para gestão de documentação em nuvem utilizando ferramentas como SharePoint Online, garantindo segurança e acesso facilitado.",
    "contratos": "Podemos ajudar a otimizar seus processos de criação e gestão de contratos com soluções digitais integradas ao Microsoft 365.",
    "suporte": "Oferecemos diferentes níveis de suporte técnico para nossas soluções. Se precisar de ajuda, pode descrever seu problema aqui ou abrir um chamado em nosso portal."
}

SUPPORT_SUGGESTIONS = {
    "acesso": "Verifique se está usando as credenciais corretas ou tente redefinir sua senha: [link]",
    "não consigo": "Poderia detalhar um pouco mais o que você não está conseguindo fazer? Qual sistema ou funcionalidade?",
    "problema": "Para problemas gerais, reiniciar o aplicativo ou o computador pode ajudar. Se persistir, por favor, me dê mais detalhes."
}

SDR_KEYWORDS = ["vendas", "comercial", "interesse", "solução", "consultor", "especialista", "orçamento", "proposta"]

class Tralhobot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState, user_state: UserState, clu_client: ConversationAnalysisClient, clu_project_name: str, clu_deployment_name: str):
        if conversation_state is None:
            raise TypeError(
                "[DialogBot]: Missing parameter. conversation_state is required"
            )
        if user_state is None:
            raise TypeError("[DialogBot]: Missing parameter. user_state is required")
            
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.support_state_accessor = self.conversation_state.create_property("SupportState")
        self.sdr_state_accessor = self.conversation_state.create_property("SDRState")
        self.log_accessor = self.conversation_state.create_property("ConversationLog") 

        self.clu_client = clu_client
        self.clu_project_name = clu_project_name
        self.clu_deployment_name = clu_deployment_name

    async def on_turn(self, turn_context: TurnContext):
        log = await self.log_accessor.get(turn_context, lambda: "")
        if turn_context.activity.type == ActivityTypes.message:
            prefix = "User:" if turn_context.activity.from_property.role == "user" else "Tralhobot:"
            log += f"{prefix} {turn_context.activity.text}\n"
            await self.log_accessor.set(turn_context, log)

        await super().on_turn(turn_context)
        
        await self.conversation_state.save_changes(turn_context, False)
        await self.user_state.save_changes(turn_context, False)

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                welcome_text = ("Olá! Bem-vindo(a) à Tralhotec. Sou Tralhobot, seu assistente virtual. "
                                "Como posso ajudar você hoje? Você pode me perguntar sobre nossos produtos, "
                                "solicitar suporte ou tirar dúvidas gerais.")
                await turn_context.send_activity(MessageFactory.text(welcome_text))
                await self.support_state_accessor.set(turn_context, {"state": "none"})
                await self.sdr_state_accessor.set(turn_context, {"state": "none", "name": None, "role": None, "company": None, "needs": None, "size": None, "qualified": None, "email": None})
                await self.log_accessor.set(turn_context, f"Tralhobot: {welcome_text}\n")

    async def on_message_activity(self, turn_context: TurnContext):
        user_message_lower = turn_context.activity.text.lower()
        user_message_original = turn_context.activity.text

        support_state_info = await self.support_state_accessor.get(turn_context, lambda: {"state": "none"})
        sdr_state_info = await self.sdr_state_accessor.get(turn_context, lambda: {"state": "none"})
        current_support_state = support_state_info.get("state", "none")
        current_sdr_state = sdr_state_info.get("state", "none")

        default_response_text = "Desculpe, não entendi sua pergunta. Pode tentar reformular? Você pode perguntar sobre preços, implementação, Microsoft Teams, documentação, contratos ou suporte."
        response_activity = MessageFactory.text(default_response_text)
        handled = False

        if current_support_state != "none":
            response_text = await self._handle_support_flow(turn_context, user_message_lower, support_state_info)
            response_activity = MessageFactory.text(response_text)
            handled = True
        elif current_sdr_state != "none":
            response_activity = await self._handle_sdr_flow(turn_context, user_message_original, sdr_state_info)
            handled = True

        if not handled and self.clu_client and self.clu_project_name and self.clu_deployment_name:
            try:
                task_payload: Dict[str, Any] = {
                    "kind": "Conversation",
                    "analysisInput": {
                        "conversationItem": {
                            "participantId": turn_context.activity.from_property.id, 
                            "id": turn_context.activity.id, 
                            "text": user_message_original,
                            "modality": "text", 
                            "language": "pt-br"
                        }
                    },
                    "parameters": {
                        "projectName": self.clu_project_name,
                        "deploymentName": self.clu_deployment_name,
                        "verbose": True, 
                    }
                }
                
                response_dict: Dict[str, Any] = await self.clu_client.analyze_conversation(
                    task_payload
                )
                
                if response_dict and "result" in response_dict:
                    result = response_dict["result"]
                    if "prediction" in result:
                        prediction = result["prediction"]
                        top_intent = prediction.get("topIntent")
                        confidence_score = 0.0
                        
                        if "intents" in prediction and top_intent:
                            for intent_info in prediction["intents"]:
                                if intent_info.get("category") == top_intent:
                                    confidence_score = intent_info.get("confidenceScore", 0.0)
                                    break
                        
                        entities = prediction.get("entities", [])

                        if top_intent == "Saudacao":
                            response_text = "Olá! Como posso ajudar você hoje?"
                        elif top_intent == "PerguntarPreco":
                            response_text = "Nossos preços variam de acordo com o serviço. Você gostaria de informações sobre algum plano específico?"
                        elif top_intent == "SolicitarSuporte":
                            response_text = "Entendo que você precisa de suporte. Para que eu possa ajudar melhor, poderia descrever o problema que está enfrentando?"
                            await self.support_state_accessor.set(turn_context, {"state": "awaiting_problem_description"})
                        elif top_intent == "QualificarSDR":
                            sdr_state_info["state"] = "awaiting_name_role"
                            await self.sdr_state_accessor.set(turn_context, sdr_state_info)
                            response_text = ("Claro! Posso direcionar você para um de nossos especialistas. "
                                            "Para começarmos, poderia me dizer seu nome completo e sua função/cargo atual na empresa, por favor?")
                        elif top_intent == "Despedida":
                            response_text = "Até logo! Foi um prazer ajudar. Tenha um ótimo dia!"
                        elif top_intent == "None":
                            response_text = default_response_text
                        else:
                            response_text = default_response_text 
                        
                        response_activity = MessageFactory.text(response_text)
                        handled = True

            except Exception as e:
                print(f"ERRO ao chamar o CLU: {e}")
                traceback.print_exc(file=sys.stdout)
        
        if not handled:
            for keyword, answer in FAQ_DATA.items():
                if keyword in user_message_lower:
                    response_text = answer
                    response_text += "\n\nEssa informação foi útil? Posso ajudar com mais alguma pergunta?"
                    response_activity = MessageFactory.text(response_text)
                    handled = True
                    break
            
            if not handled:
                response_activity = MessageFactory.text(default_response_text)
        
        await turn_context.send_activity(response_activity)
        log = await self.log_accessor.get(turn_context, lambda: "")
        if hasattr(response_activity, 'text') and response_activity.text:
             log += f"Tralhobot: {response_activity.text}\n"
             await self.log_accessor.set(turn_context, log)
        elif hasattr(response_activity, 'attachments') and response_activity.attachments:
             card_text = response_activity.attachments[0].content.get('body', [{}])[0].get('text', '[Card Sent]')
             log += f"Tralhobot: {card_text}\n"
             await self.log_accessor.set(turn_context, log)

    async def _handle_support_flow(self, turn_context: TurnContext, state: Dict) -> str:
        current_state = state.get("state", "none") # Usar .get() para evitar KeyError
        response = "Ocorreu um erro no fluxo de suporte."

        if current_state == "awaiting_problem_description":
            suggestion_found = False
            for keyword, suggestion in SUPPORT_SUGGESTIONS.items():
                if keyword in turn_context.activity.text.lower(): # Usar turn_context.activity.text.lower()
                    response = f"Sugestão: {suggestion} Isso resolveu? (Sim/Não)"
                    state["state"] = "awaiting_resolution_confirmation"
                    suggestion_found = True
                    break
            if not suggestion_found: # Corrigido para verificar se foi encontrada sugestão
                response = "Ainda precisa de ajuda? (Sim/Não)"
                state["state"] = "awaiting_resolution_confirmation"

        elif current_state == "awaiting_resolution_confirmation":
            if "sim" in turn_context.activity.text.lower(): # Usar turn_context.activity.text.lower()
                response = "Ótimo! Posso ajudar em algo mais?"
                state["state"] = "none"
            else:
                response = "Por favor, informe seu nome, e-mail e empresa para escalarmos."
                state["state"] = "awaiting_escalation_details"

        elif current_state == "awaiting_escalation_details":
            response = f"Seu ticket foi criado (TRALHO-{turn_context.activity.id[:5]}). Nossa equipe entrará em contato."
            state["state"] = "none"

        await self.support_state_accessor.set(turn_context, state)
        return response

    async def _handle_sdr_flow(self, turn_context: TurnContext, state: Dict):
        current_state = state.get("state", "none") # Usar .get() para evitar KeyError
        response = MessageFactory.text("Ocorreu um erro no fluxo de vendas.")

        if current_state == "awaiting_name_role":
            state.update({"name": turn_context.activity.text, "state": "awaiting_company"}) # Usar turn_context.activity.text
            response = MessageFactory.text(f"Obrigado, {state.get('name')}. Qual o nome da sua empresa?")

        elif current_state == "awaiting_company":
            state.update({"company": turn_context.activity.text, "state": "awaiting_needs"}) # Usar turn_context.activity.text
            response = MessageFactory.text("Quais são seus principais desafios atuais?")

        elif current_state == "awaiting_needs":
            state.update({"needs": turn_context.activity.text, "state": "awaiting_size"}) # Usar turn_context.activity.text
            response = MessageFactory.text("Qual o tamanho da sua empresa? (Ex: até 10, 11-50, 50+)")

        elif current_state == "awaiting_size":
            state["size"] = turn_context.activity.text # Usar turn_context.activity.text
            is_qualified = False
            # Ajuste a qualificação para usar os dados do state, não user_message (agora é turn_context.activity.text)
            # ou defina user_message como um parâmetro nas funções _handle_sdr_flow e _handle_support_flow.
            # Vamos ajustar para usar o user_message passado.
            
            # Aqui user_message já é a resposta do usuário para a pergunta de 'size'
            size_lower = turn_context.activity.text.lower()
            if "10" in size_lower or "50" in size_lower or "grande" in size_lower:
                is_qualified = True
            
            state["qualified"] = is_qualified
            
            if is_qualified:
                state["state"] = "awaiting_email"
                response = MessageFactory.text(
                    "Perfeito! Com base nas informações, podemos ajudar. Qual seu e-mail profissional?"
                )
            else:
                state["state"] = "none"
                response = MessageFactory.text(
                    "Obrigado! Temos soluções para seu porte. Confira em: [link_pacote_pequenas_empresas]."
                )
            # Removido state["state"] = "awaiting_final_confirmation" duplicado ou incorreto
            # A lógica SDR precisa ser revisada para garantir o fluxo correto após qualificação.

        elif current_state == "awaiting_email":
            state["email"] = turn_context.activity.text # Usar turn_context.activity.text
            response = MessageFactory.text(f"Informações enviadas para {state.get('email')}. Obrigado!")
            send_log = True
            state["state"] = "none"

        await self.sdr_state_accessor.set(turn_context, state)
        return response

    def _create_yes_no_card(self, text: str, yes_value: str, no_value: str) -> Attachment:
        return CardFactory.hero_card(
            text=text,
            buttons=[
                CardAction(title="Sim", type=ActionTypes.im_back, value=yes_value),
                CardAction(title="Não", type=ActionTypes.im_back, value=no_value),
            ],
        ).attachments[0]
