"""
Configurações da aplicação Flask
"""

import os

DB_CONFIG = {
    'host': os.environ.get('PGHOST'),
    'port': os.environ.get('PGPORT', '5432'),
    'database': os.environ.get('PGDATABASE'),
    'user': os.environ.get('PGUSER'),
    'password': os.environ.get('PGPASSWORD')
}

SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-padrao')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
