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

    # Configurações para o Azure Ai Language (CLU)

    CLU_ENDPOINT = os.environ.get("CLU_ENDPOINT", "https://sdr-language-ai.cognitiveservices.azure.com/")  # Endpoint da API
    CLU_API_KEY = os.environ.get("CLU_API_KEY", "9fH7Dt5goNSnlWTbfR4dq8Fm9yZP4IOvJC1boq5zSdoFY0I76XdhJQQJ99BFACYeBjFXJ3w3AAAaACOG26ju")  # Chave de API
    CLU_PROJECT_NAME = os.environ.get("CLU_PROJECT_NAME", "Tralhobot_CLU")  # Nome do projeto CLU
    CLU_DEPLOYMENT_NAME = os.environ.get("CLU_DEPLOYMENT_NAME", "production-deployment")  # Nome do deployment CLU