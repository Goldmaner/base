"""
Configurações da aplicação Flask
"""

import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do banco de dados
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_DATABASE', 'projeto_parcerias'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'sslmode': os.environ.get('DB_SSLMODE', 'prefer'),
    # Keepalives TCP: evita que o SO/firewall/NAT encerre conexões ociosas silenciosamente
    'keepalives': 1,
    'keepalives_idle': 60,      # envia keepalive após 60s de idle
    'keepalives_interval': 10,  # re-envia a cada 10s se sem resposta
    'keepalives_count': 5,      # fecha após 5 tentativas sem resposta
    'connect_timeout': 10,      # falha rápida se o servidor não responder
}

SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-padrao')

# Módulos liberados automaticamente para todo usuário cadastrado (pack básico).
# Esses módulos não precisam de permissão explícita — são garantidos pelo decorator
# e adicionados à sessão no login, para que os botões da home apareçam corretamente.
ACESSOS_BASICOS = ['ferias', 'manuais']

# Tipos de usuário com suas propriedades.
# Para adicionar um novo tipo no futuro: insira uma entrada aqui + adicione ao dropdown do template.
# escrita_padrao=False → tipo recebe apenas leitura por default; escrita precisa ser liberada
# por módulo via Controle de Acessos.
TIPOS_USUARIO = {
    "Agente Público":    {"admin": True,  "unidade": None,                            "escrita_padrao": True},
    "Agente DAC":        {"admin": False, "unidade": "Divisão de Análise de Contas",   "escrita_padrao": True},
    "Agente DGP":        {"admin": False, "unidade": "Divisão de Gestão de Parcerias", "escrita_padrao": True},
    "Agente DP":         {"admin": False, "unidade": "Departamento de Parcerias",      "escrita_padrao": True},
    "Externo":           {"admin": False, "unidade": None,                             "escrita_padrao": True},
    "Externo: Gabinete": {"admin": False, "unidade": "Gabinete",                       "escrita_padrao": False},
}

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# Configuração de e-mail (SMTP)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')  # E-mail remetente
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')  # Senha do app (não a senha normal)
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_USERNAME', 'noreply@exemplo.com'))

# Configuração da API SOF (Sistema Orçamentário e Financeiro)
# IMPORTANTE: Valores devem estar no arquivo .env (não commitar credenciais no Git!)
SOF_API_USERNAME = os.environ.get('SOF_API_USERNAME', '')
SOF_API_PASSWORD = os.environ.get('SOF_API_PASSWORD', '')
SOF_AUTH_BASE64 = os.environ.get('SOF_AUTH_BASE64', '')

# Supabase Storage
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')
# True = usa Supabase Storage; False = usa disco local (comportamento original)
USE_SUPABASE_STORAGE = os.environ.get('USE_SUPABASE_STORAGE', 'False').upper() == 'TRUE'