"""
Configurações da aplicação Flask
"""

import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do banco de dados (apenas LOCAL)
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_DATABASE', 'projeto_parcerias'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '')
}

SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-padrao')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# Configuração de e-mail (SMTP)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')  # E-mail remetente
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')  # Senha do app (não a senha normal)
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_USERNAME', 'noreply@exemplo.com'))