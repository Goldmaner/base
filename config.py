"""
Configurações da aplicação Flask
"""

import os

DB_CONFIG = {
    'host': 'shinkansen.proxy.rlwy.net',  # valor do host público
    'port': '38157',                      # valor da porta pública
    'database': 'railway',                # nome do banco
    'user': 'postgres',                   # usuário
    'password': 'sKOzVlsxAUcRIXXLynePvvHDQpXlmTVT'  # sua senha
}

SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-padrao')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'