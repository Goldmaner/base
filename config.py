"""
Configurações da aplicação Flask
"""

import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do banco de dados LOCAL
DB_CONFIG_LOCAL = {
    'host': os.environ.get('DB_LOCAL_HOST', 'localhost'),
    'port': os.environ.get('DB_LOCAL_PORT', '5432'),
    'database': os.environ.get('DB_LOCAL_DATABASE', 'projeto_parcerias'),
    'user': os.environ.get('DB_LOCAL_USER', 'postgres'),
    'password': os.environ.get('DB_LOCAL_PASSWORD', '')
}

# Configuração do banco de dados RAILWAY
DB_CONFIG_RAILWAY = {
    'host': os.environ.get('DB_RAILWAY_HOST', 'shinkansen.proxy.rlwy.net'),
    'port': os.environ.get('DB_RAILWAY_PORT', '38157'),
    'database': os.environ.get('DB_RAILWAY_DATABASE', 'railway'),
    'user': os.environ.get('DB_RAILWAY_USER', 'postgres'),
    'password': os.environ.get('DB_RAILWAY_PASSWORD', '')
}

# Mantém DB_CONFIG como referência ao Railway (padrão para produção)
DB_CONFIG = DB_CONFIG_RAILWAY

SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-padrao')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'