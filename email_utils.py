import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import DefaultConfig

CONFIG = DefaultConfig()

def send_log_to_stakeholders(conversation_log: str, sdr_data: dict) -> bool:
    """
    Sends the conversation log and SDR data to stakeholders via email.
    Returns True if successful, False otherwise.
    """
    if not CONFIG.EMAIL_FROM_ADDRESS or not CONFIG.EMAIL_PASSWORD or not CONFIG.EMAIL_TO_ADDRESS:
        print("Erro: As configurações de e-mail (EMAIL_FROM_ADDRESS, EMAIL_PASSWORD, EMAIL_TO_ADDRESS) não estão preenchidas no config.py.")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = CONFIG.EMAIL_FROM_ADDRESS
        msg["To"] = CONFIG.EMAIL_TO_ADDRESS
        
        # Define o assunto do e-mail com base na qualificação
        subject = f"Log de Conversa Tralhobot - Contato {'Qualificado' if sdr_data.get('qualified') else 'Não Qualificado'}"
        msg["Subject"] = subject

        body = (
            f"Prezados(as) Stakeholders,\n\n"
            f"Uma nova interação com o Tralhobot foi concluída. Abaixo estão os detalhes da conversa e os dados coletados:\n\n"
            f"--- Dados do Contato ---\n"
            f"Nome: {sdr_data.get('name', 'N/A')}\n"
            f"Cargo: {sdr_data.get('role', 'N/A')}\n"
            f"Empresa: {sdr_data.get('company', 'N/A')}\n"
            f"Necessidades: {sdr_data.get('needs', 'N/A')}\n"
            f"Porte da Empresa: {sdr_data.get('size', 'N/A')}\n"
            f"Email de Contato: {sdr_data.get('email', 'N/A')}\n"
            f"Qualificado para SDR: {'Sim' if sdr_data.get('qualified') else 'Não'}\n\n"
            f"--- Log da Conversa ---\n"
            f"{conversation_log}\n"
            f"-----------------------\n\n"
            f"Atenciosamente,\n"
            f"Tralhobot Automatizado"
        )
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(CONFIG.EMAIL_SMTP_SERVER, CONFIG.EMAIL_SMTP_PORT) as server:
            server.starttls()  # Inicia TLS para conexão segura
            server.login(CONFIG.EMAIL_FROM_ADDRESS, CONFIG.EMAIL_PASSWORD)
            server.send_message(msg)
        print("E-mail de log enviado com sucesso!")
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail de log: {e}")
        return False

# Você pode descomentar o bloco abaixo para testar o envio de e-mail separadamente
# if __name__ == "__main__":
#     # Preencha as configurações de e-mail no config.py antes de testar
#     test_log = "User: Olá!\nBot: Bem-vindo!\nUser: Quero agendar uma reunião.\nBot: Ok, me diga seu nome."
#     test_sdr_data = {
#         "name": "João Teste",
#         "role": "Analista",
#         "company": "Empresa Teste",
#         "needs": "Automatização",
#         "size": "Pequena",
#         "qualified": True,
#         "email": "teste@exemplo.com"
#     }
#     send_log_to_stakeholders(test_log, test_sdr_data)