import os

class DefaultConfig:
    """Bot Configuration"""

    PORT = 3979  # Porta padrão para bots do Bot Framework
    APP_ID = os.environ.get("MicrosoftAppId", "") # Deixe vazio para testes locais no Emulator
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "") # Deixe vazio para testes locais no Emulator
    
    # Configurações para o envio de e-mail (ATENÇÃO: ajuste conforme seu provedor de e-mail)
    EMAIL_FROM_ADDRESS = os.environ.get("EMAIL_FROM_ADDRESS", "seu_email@exemplo.com") # Seu e-mail de remetente
    EMAIL_TO_ADDRESS = os.environ.get("EMAIL_TO_ADDRESS", "destinatario@exemplo.com") # E-mail(s) do(s) stakeholder(s)
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "sua_senha_de_app_ou_email") # Senha do seu e-mail (ou senha de app se usar Gmail/Outlook com 2FA)
    EMAIL_SMTP_SERVER = os.environ.get("EMAIL_SMTP_SERVER", "smtp.gmail.com") # Ex: smtp.gmail.com (Gmail), smtp.office365.com (Outlook)
    EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", 587)) # Porta: 587 (TLS) ou 465 (SSL)