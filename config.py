"""
Configurações da aplicação Flask
"""

# Configuração do banco PostgreSQL
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'projeto_parcerias',
    'user': 'postgres',
    'password': 'Coração01'
}

# Chave secreta para sessões
SECRET_KEY = 'seu_secret_key_aqui'  # TODO: Alterar para uma chave segura em produção

# Configurações do Flask
DEBUG = True
