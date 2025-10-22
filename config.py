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