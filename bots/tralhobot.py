# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
from datetime import datetime
from typing import Any # Mantido, caso precise, mas agora usamos tipos mais específicos

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
# AGORA REVERTEMOS PARA A IMPORTAÇÃO PADRÃO DE 'models'
# Esperamos que o downgrade da biblioteca resolva o ModuleNotFoundError
from azure.ai.language.conversations import ( 
    ConversationItem,            # Usado para o item da conversa de entrada
    ConversationalTask,          # Usado para a tarefa de análise conversacional
    ConversationAnalysisResult   # Para o type hint e acesso a resultados
)


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
    "acesso": "Verifique se está usando as credenciais corretas ou tente redefinir sua senha. Mais detalhes aqui: [link_redefinir_senha]",
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
                # AGORA USAMOS OS OBJETOS DO SDK, COMO ELE ESPERA
                conversation_item_obj = ConversationItem(
                    participant_id=turn_context.activity.from_property.id,
                    id=turn_context.activity.id,
                    text=user_message_original
                )

                conversational_task_obj = ConversationalTask(
                    analysis_input={"conversationItem": conversation_item_obj}, # Passar o objeto
                    parameters={
                        "projectName": self.clu_project_name,
                        "deploymentName": self.clu_deployment_name,
                        "verbose": True,
                    }
                )
                
                # A chamada analyze_conversation agora espera o OBJETO ConversationalTask
                response: ConversationAnalysisResult = await self.clu_client.analyze_conversation(
                    conversational_task_obj # Passar o objeto
                )
                
                if response and response.result and response.result.prediction:
                    top_intent = response.result.prediction.top_intent
                    confidence_score = 0.0
                    if response.result.prediction.intents:
                         confidence_score = response.result.prediction.intents[0].confidence
                    
                    entities = response.result.prediction.entities if response.result.prediction.entities else []

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

                    print(f"CLU: Intenção '{top_intent}' ({confidence_score:.2f})")
                    if entities:
                        print(f"CLU: Entidades: {[(e.text, e.category) for e in entities]}")

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

    async def _handle_support_flow(self, turn_context: TurnContext, user_message: str, support_state_info: dict) -> str:
        current_support_state = support_state_info.get("state", "none")
        response_text = "Houve um problema no fluxo de suporte."

        if current_support_state == "awaiting_problem_description":
            suggestion_found = False
            for keyword, suggestion in SUPPORT_SUGGESTIONS.items():
                if keyword in user_message:
                    response_text = f"Ok, obrigado pelos detalhes. Encontrei uma sugestão que pode ajudar: {suggestion} Isso resolveu o problema? (Sim/Não)"
                    suggestion_found = True
                    await self.support_state_accessor.set(turn_context, {"state": "awaiting_resolution_confirmation"})
                    break
            if not suggestion_found:
                    response_text = "Obrigado pelos detalhes. Não encontrei uma sugestão automática imediata. Isso resolveu o problema de alguma forma ou ainda precisa de ajuda? (Sim/Não)"
                    await self.support_state_accessor.set(turn_context, {"state": "awaiting_resolution_confirmation"})

        elif current_support_state == "awaiting_resolution_confirmation":
            if "sim" in user_message:
                response_text = "Ótimo! Fico feliz em ajudar. Há mais algo em que posso ser útil?"
                await self.support_state_accessor.set(turn_context, {"state": "none"})
            else:
                response_text = "Lamento que isso não tenha resolvido. Para que nossa equipe de suporte possa analisar seu caso, preciso coletar algumas informações. Poderia me informar seu nome completo, e-mail de contato e o nome da sua empresa, por favor?"
                await self.support_state_accessor.set(turn_context, {"state": "awaiting_escalation_details"})
        
        elif current_support_state == "awaiting_escalation_details":
             user_details = turn_context.activity.text
             response_text = (f"Obrigado pelas informações. Registrei sua solicitação com os detalhes fornecidos ({user_details}). "
                              f"Nossa equipe de suporte entrará em contato com você o mais breve possível. "
                              f"O número do seu ticket de suporte é TRALHO-{turn_context.activity.id[:5]}. Há mais algo em que posso ajudar agora?")
             await self.support_state_accessor.set(turn_context, {"state": "none"})
        
        return response_text

    async def _handle_sdr_flow(self, turn_context: TurnContext, user_message: str, sdr_state_info: dict):
        current_sdr_state = sdr_state_info.get("state", "none")
        response_text = "Houve um problema no fluxo de qualificação."
        response_activity = MessageFactory.text(response_text)
        send_log = False

        if current_sdr_state == "awaiting_name_role":
            sdr_state_info["name"] = user_message
            sdr_state_info["role"] = user_message
            sdr_state_info["state"] = "awaiting_company_name"
            await self.sdr_state_accessor.set(turn_context, sdr_state_info)
            response_text = "Obrigado! E qual é o nome da sua empresa?"
            response_activity = MessageFactory.text(response_text)

        elif current_sdr_state == "awaiting_company_name":
            sdr_state_info["company"] = user_message
            sdr_state_info["state"] = "awaiting_needs"
            await self.sdr_state_accessor.set(turn_context, sdr_state_info)
            response_text = (f"Obrigado, {sdr_state_info.get('name', 'Contato')}. Para entender melhor como podemos ajudar a {sdr_state_info.get('company', 'sua empresa')}, "
                             f"poderia me contar um pouco sobre os principais desafios que vocês enfrentam hoje em relação à colaboração entre equipes, gestão de documentos ou infraestrutura de TI?")
            response_activity = MessageFactory.text(response_text)

        elif current_sdr_state == "awaiting_needs":
            sdr_state_info["needs"] = user_message
            sdr_state_info["state"] = "awaiting_size"
            await self.sdr_state_accessor.set(turn_context, sdr_state_info)
            response_text = ("Entendido. E para contextualizar, sua empresa se enquadra em qual porte? "
                             "(Ex: até 10 funcionários, 11-50, mais de 50)")
            response_activity = MessageFactory.text(response_text)

        elif current_sdr_state == "awaiting_size":
            sdr_state_info["size"] = user_message
            is_qualified = False
            role_lower = str(sdr_state_info.get("role", "")).lower()
            size_lower = str(sdr_state_info.get("size", "")).lower()
            if any(r in role_lower for r in ["gerente", "diretor", "sócio", "coordenador"]) and \
               any(s in size_lower for s in ["até 10", "11-50", "pequeno"]):
                is_qualified = True
            
            sdr_state_info["qualified"] = is_qualified
            await self.sdr_state_accessor.set(turn_context, sdr_state_info)
            
            if is_qualified:
                sdr_state_info["state"] = "proposing_meeting"
                await self.sdr_state_accessor.set(turn_context, sdr_state_info)
                response_text = ("Com base no que conversamos, acredito que nossas soluções podem realmente agregar valor à sua empresa. "
                                 "Gostaria de agendar uma conversa com um de nossos especialistas? Ele(a) poderá apresentar demonstrações personalizadas e discutir como podemos atender às suas necessidades específicas.")
                response_activity = self._create_yes_no_card(turn_context, response_text, "schedule_meeting_yes", "schedule_meeting_no")
            else:
                sdr_state_info["state"] = "handling_unqualified"
                await self.sdr_state_accessor.set(turn_context, sdr_state_info)
                response_text = ("Obrigado pelas informações. No momento, parece que nossas soluções podem não ser o encaixe ideal para as suas necessidades atuais / perfil da sua empresa. "
                                 "Gostaria de receber alguns materiais informativos sobre [Tópico Relevante] por e-mail para referência futura? (Sim/Não)")
                response_activity = self._create_yes_no_card(turn_context, response_text, "send_materials_yes", "send_materials_no")

        elif current_sdr_state == "proposing_meeting":
            if user_message == "schedule_meeting_yes":
                sdr_state_info["state"] = "awaiting_email_for_schedule"
                await self.sdr_state_accessor.set(turn_context, sdr_state_info)
                response_text = "Excelente! Para qual e-mail posso enviar o convite da reunião?"
                response_activity = MessageFactory.text(response_text)
            else:
                response_text = "Entendido. Se mudar de ideia ou precisar de algo mais, é só chamar!"
                await self.sdr_state_accessor.set(turn_context, {"state": "none"})
                send_log = True
                response_activity = MessageFactory.text(response_text)

        elif current_sdr_state == "awaiting_email_for_schedule":
            sdr_state_info["email"] = user_message
            sdr_state_info["state"] = "scheduling_confirmed"
            await self.sdr_state_accessor.set(turn_context, sdr_state_info)
            specialist_name = "[Nome do Especialista]"
            response_text = (f"Perfeito! Agendamento confirmado com {specialist_name}. "
                             f"O convite foi enviado para {sdr_state_info['email']}. "
                             f"Confirmando os dados: Nome: {sdr_state_info.get('name', 'N/A')}, Cargo: {sdr_state_info.get('role', 'N/A')}. "
                             f"{specialist_name} está ansioso para conversar com você. Há mais algo em que posso ajudar agora?")
            send_log = True
            await self.sdr_state_accessor.set(turn_context, {"state": "none"})
            response_activity = MessageFactory.text(response_text)

        elif current_sdr_state == "handling_unqualified":
            if user_message == "send_materials_yes":
                sdr_state_info["state"] = "awaiting_email_for_materials"
                await self.sdr_state_accessor.set(turn_context, sdr_state_info)
                response_text = "Ótimo! Para qual e-mail posso enviar os materiais?"
                response_activity = MessageFactory.text(response_text)
            else:
                response_text = "Entendido. Agradeço seu tempo e interesse na Tralhotec. Tenha um ótimo dia!"
                await self.sdr_state_accessor.set(turn_context, {"state": "none"})
                send_log = True
                response_activity = MessageFactory.text(response_text)
        
        elif current_sdr_state == "awaiting_email_for_materials":
            sdr_state_info["email"] = user_message
            response_text = f"Materiais enviados para {sdr_state_info['email']}. Agradeço seu tempo e interesse na Tralhotec. Tenha um ótimo dia!"
            await self.sdr_state_accessor.set(turn_context, {"state": "none"})
            send_log = True
            response_activity = MessageFactory.text(response_text)

        if send_log:
            conversation_log = await self.log_accessor.get(turn_context, lambda: "")
            log_prefix_user = "User:" 
            log_prefix_bot = "Tralhobot:"
            conversation_log += f"{log_prefix_user} {user_message}\n"
            if hasattr(response_activity, 'text') and response_activity.text:
                conversation_log += f"{log_prefix_bot} {response_activity.text}\n"
            elif hasattr(response_activity, 'attachments') and response_activity.attachments:
                card_text = response_activity.attachments[0].content.get('body', [{}])[0].get('text', '[Card Sent]')
                conversation_log += f"Tralhobot: {card_text}\n"
                
            send_success = send_log_to_stakeholders(conversation_log, sdr_state_info)
            await self.log_accessor.set(turn_context, "")

        return response_activity

    def _create_yes_no_card(self, turn_context: TurnContext, text: str, yes_value: str, no_value: str) -> Attachment:
        card = CardFactory.hero_card(
            title=text,
            buttons=[
                CardAction(
                    title="Sim",
                    type=ActionTypes.im_back,
                    value=yes_value,
                ),
                CardAction(
                    title="Não",
                    type=ActionTypes.im_back,
                    value=no_value,
                ),
            ],
        )
        return card.attachments[0]
