# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
from datetime import datetime
from typing import Any, Dict # Importar Dict para tipagem de dicionários

from botbuilder.core import (
    ActivityHandler, TurnContext, MessageFactory, UserState, 
    ConversationState, CardFactory
)
from botbuilder.schema import ChannelAccount, ActivityTypes, Attachment, ActionTypes, CardAction

from config import DefaultConfig
from email_utils import send_log_to_stakeholders

# Importações do Azure AI Language
from azure.ai.language.conversations import ConversationAnalysisClient
from azure.core.credentials import AzureKeyCredential
# REMOVIDAS TODAS AS IMPORTAÇÕES DE 'models' OU '_models'
# As classes ConversationItem e ConversationalTask serão criadas como dicionários.
# A classe ConversationAnalysisResult não será importada, e o retorno será tratado como um dicionário.


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
        print(f"ON_TURN: Activity Type: {turn_context.activity.type}, User ID: {turn_context.activity.from_property.id}")
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
        print("ON_MEMBERS_ADDED_ACTIVITY: Novo membro adicionado.")
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
        print(f"ON_MESSAGE_ACTIVITY: Mensagem do usuário: '{user_message_original}'")

        support_state_info = await self.support_state_accessor.get(turn_context, lambda: {"state": "none"})
        sdr_state_info = await self.sdr_state_accessor.get(turn_context, lambda: {"state": "none"})
        current_support_state = support_state_info.get("state", "none")
        current_sdr_state = sdr_state_info.get("state", "none")
        print(f"ON_MESSAGE_ACTIVITY: Estados atuais - Suporte: '{current_support_state}', SDR: '{current_sdr_state}'")


        default_response_text = "Desculpe, não entendi sua pergunta. Pode tentar reformular? Você pode perguntar sobre preços, implementação, Microsoft Teams, documentação, contratos ou suporte."
        response_activity = MessageFactory.text(default_response_text)
        handled = False

        if current_support_state != "none":
            print(f"ON_MESSAGE_ACTIVITY: Entrando em fluxo de suporte.")
            response_text = await self._handle_support_flow(turn_context, user_message_lower, support_state_info)
            response_activity = MessageFactory.text(response_text)
            handled = True
        elif current_sdr_state != "none":
            print(f"ON_MESSAGE_ACTIVITY: Entrando em fluxo SDR.")
            response_activity = await self._handle_sdr_flow(turn_context, user_message_original, sdr_state_info)
            handled = True

        if not handled and self.clu_client and self.clu_project_name and self.clu_deployment_name:
            print(f"ON_MESSAGE_ACTIVITY: CLU ativado. Chamando analyze_conversation.")
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
                        "verbose": True, # Para ver mais detalhes, incluindo entidades
                    }
                }
                
                response_dict: Dict[str, Any] = await self.clu_client.analyze_conversation(
                    task_payload
                )
                
                print(f"ON_MESSAGE_ACTIVITY: Resposta CLU bruta: {response_dict}") # Printando o dicionário CLU
                if response_dict and "result" in response_dict:
                    result = response_dict["result"]
                    if "prediction" in result:
                        prediction = result["prediction"]
                        top_intent = prediction.get("topIntent")
                        confidence_score = 0.0
                        
                        if "intents" in prediction and top_intent:
                            # Acessando a confiança da intenção principal
                            for intent_info in prediction["intents"]:
                                if intent_info.get("category") == top_intent:
                                    confidence_score = intent_info.get("confidenceScore", 0.0)
                                    break
                        
                        entities = prediction.get("entities", [])

                        print(f"CLU: Intenção detectada: '{top_intent}' com confiança: {confidence_score:.2f}")
                        if entities:
                            print(f"CLU: Entidades detectadas: {entities}")

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
                else:
                    print("ON_MESSAGE_ACTIVITY: Resposta CLU inesperada ou incompleta.")

            except Exception as e:
                print(f"ON_MESSAGE_ACTIVITY: ERRO ao chamar o CLU: {e}")
                traceback.print_exc(file=sys.stdout)
        
        if not handled:
            print("ON_MESSAGE_ACTIVITY: Entrando em fluxo de fallback (FAQ/padrão).")
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
        print(f"ON_MESSAGE_ACTIVITY: Bot respondeu com: {response_activity.text or response_activity.attachments}")
        log = await self.log_accessor.get(turn_context, lambda: "")
        if hasattr(response_activity, 'text') and response_activity.text:
             log += f"Tralhobot: {response_activity.text}\n"
             await self.log_accessor.set(turn_context, log)
        elif hasattr(response_activity, 'attachments') and response_activity.attachments:
             card_text = response_activity.attachments[0].content.get('body', [{}])[0].get('text', '[Card Sent]')
             log += f"Tralhobot: {card_text}\n"
             await self.log_accessor.set(turn_context, log)


    async def _handle_support_flow(self, turn_context: TurnContext, state: Dict) -> str:
        current_state = state.get("state", "none") 
        response = "Ocorreu um erro no fluxo de suporte."
        print(f"HANDLE_SUPPORT_FLOW: Estado atual: '{current_state}', Mensagem: '{turn_context.activity.text}'")


        if current_state == "awaiting_problem_description":
            suggestion_found = False
            for keyword, suggestion in SUPPORT_SUGGESTIONS.items():
                if keyword in turn_context.activity.text.lower():
                    response = f"Sugestão: {suggestion} Isso resolveu? (Sim/Não)"
                    state["state"] = "awaiting_resolution_confirmation"
                    suggestion_found = True
                    break
            if not suggestion_found:
                response = "Ainda precisa de ajuda? (Sim/Não)"
                state["state"] = "awaiting_resolution_confirmation"

        elif current_state == "awaiting_resolution_confirmation":
            if "sim" in turn_context.activity.text.lower():
                response = "Ótimo! Posso ajudar em algo mais?"
                state["state"] = "none"
            else:
                response = "Por favor, informe seu nome, e-mail e empresa para escalarmos."
                state["state"] = "awaiting_escalation_details"

        elif current_state == "awaiting_escalation_details":
            user_details = turn_context.activity.text
            response = (f"Seu ticket foi criado (TRALHO-{turn_context.activity.id[:5]}). Nossa equipe entrará em contato."
                        f"Detalhes: {user_details}. Posso ajudar em algo mais agora?")
            state["state"] = "none"

        await self.support_state_accessor.set(turn_context, state)
        return response

    async def _handle_sdr_flow(self, turn_context: TurnContext, state: Dict):
        current_state = state.get("state", "none")
        response = MessageFactory.text("Ocorreu um erro no fluxo de vendas.")
        print(f"HANDLE_SDR_FLOW: Estado atual: '{current_state}', Mensagem: '{turn_context.activity.text}'")


        if current_state == "awaiting_name_role":
            state.update({"name": turn_context.activity.text, "state": "awaiting_company"})
            response = MessageFactory.text(f"Obrigado, {state.get('name')}. Qual o nome da sua empresa?")

        elif current_state == "awaiting_company":
            state.update({"company": turn_context.activity.text, "state": "awaiting_needs"})
            response = MessageFactory.text("Quais são seus principais desafios atuais?")

        elif current_state == "awaiting_needs":
            state.update({"needs": turn_context.activity.text, "state": "awaiting_size"})
            response = MessageFactory.text("Qual o tamanho da sua empresa? (Ex: até 10, 11-50, 50+)")

        elif current_state == "awaiting_size":
            state["size"] = turn_context.activity.text
            is_qualified = False
            
            size_lower = turn_context.activity.text.lower()
            if "10" in size_lower or "50" in size_lower or "grande" in size_lower:
                is_qualified = True
            
            state["qualified"] = is_qualified
            
            if is_qualified:
                state["state"] = "proposing_meeting" # Ajustado para o próximo estado correto
                response_activity = self._create_yes_no_card(
                    "Com base no que conversamos, acredito que nossas soluções podem realmente agregar valor à sua empresa. "
                    "Gostaria de agendar uma conversa com um de nossos especialistas? Ele(a) poderá apresentar demonstrações personalizadas e discutir como podemos atender às suas necessidades específicas.",
                    "schedule_meeting_yes", "schedule_meeting_no"
                )
            else:
                state["state"] = "handling_unqualified" # Ajustado para o próximo estado correto
                response_activity = self._create_yes_no_card(
                    "Obrigado pelas informações. No momento, parece que nossas soluções podem não ser o encaixe ideal para as suas necessidades atuais / perfil da sua empresa. "
                    "Gostaria de receber alguns materiais informativos sobre [Tópico Relevante] por e-mail para referência futura? (Sim/Não)",
                    "send_materials_yes", "send_materials_no"
                )
            await self.sdr_state_accessor.set(turn_context, state) # Salva o estado
            return response_activity # Retorna a activity

        elif current_state == "proposing_meeting":
            if turn_context.activity.text.lower() == "schedule_meeting_yes":
                state["state"] = "awaiting_email_for_schedule"
                response = MessageFactory.text("Excelente! Para qual e-mail posso enviar o convite da reunião?")
            else:
                response = MessageFactory.text("Entendido. Se mudar de ideia ou precisar de algo mais, é só chamar!"
                state["state"] = "none"
            await self.sdr_state_accessor.set(turn_context, state)
            return response # Retorna a activity

        elif current_state == "awaiting_email_for_schedule":
            state["email"] = turn_context.activity.text
            response = MessageFactory.text(f"Perfeito! Agendamento confirmado. O convite foi enviado para {state.get('email')}. "
                                        f"Há mais algo em que posso ajudar agora?")
            send_log = True
            state["state"] = "none" # Reset SDR state after confirmation
            await self.sdr_state_accessor.set(turn_context, state)
            return response # Retorna a activity

        elif current_state == "handling_unqualified":
            if turn_context.activity.text.lower() == "send_materials_yes":
                state["state"] = "awaiting_email_for_materials"
                response = MessageFactory.text("Ótimo! Para qual e-mail posso enviar os materiais?")
            else:
                response = MessageFactory.text("Entendido. Agradeço seu tempo e interesse na Tralhotec. Tenha um ótimo dia!")
                state["state"] = "none"
            await self.sdr_state_accessor.set(turn_context, state)
            return response # Retorna a activity
        
        elif current_state == "awaiting_email_for_materials":
            state["email"] = turn_context.activity.text
            response = MessageFactory.text(f"Materiais enviados para {state.get('email')}. Agradeço seu tempo e interesse na Tralhotec. Tenha um ótimo dia!")
            send_log = True
            state["state"] = "none" # Reset SDR state after sending materials
            await self.sdr_state_accessor.set(turn_context, state)
            return response # Retorna a activity


    def _create_yes_no_card(self, text: str, yes_value: str, no_value: str) -> Attachment:
        return CardFactory.hero_card(
            text=text,
            buttons=[
                CardAction(title="Sim", type=ActionTypes.im_back, value=yes_value),
                CardAction(title="Não", type=ActionTypes.im_back, value=no_value),
            ],
        ).attachments[0]
