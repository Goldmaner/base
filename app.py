"""
Aplicação Flask - FAF (Ferramenta de Análise Financeira)

Arquivo principal que inicializa a aplicação e registra os blueprints.
"""

from flask import Flask
from config import SECRET_KEY, DEBUG
from db import close_db
from utils import format_sei

# Importar blueprints
from routes.main import main_bp
from routes.auth import auth_bp
from routes.orcamento import orcamento_bp
from routes.instrucoes import instrucoes_bp
from routes.despesas import despesas_bp
from routes.parcerias import parcerias_bp


def create_app():
    """
    Factory function para criar e configurar a aplicação Flask
    """
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    app.config["DEBUG"] = DEBUG
    
    # Registrar função de limpeza do banco de dados
    app.teardown_appcontext(close_db)
    
    # Registrar filtro Jinja2 para formatação de SEI
    @app.template_filter("format_sei")
    def format_sei_filter(sei_number):
        return format_sei(sei_number)
    
    # Registrar filtro Jinja2 para formatação de moeda brasileira
    @app.template_filter("format_brl")
    def format_brl_filter(valor):
        """
        Formata valor numérico para padrão brasileiro de moeda
        Exemplo: 1551410.40 -> 1.551.410,40
        """
        if valor is None:
            return "0,00"
        try:
            valor_float = float(valor)
            # Formatar com 2 casas decimais, vírgula como separador decimal e ponto como milhar
            formatado = f"{valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return formatado
        except (ValueError, TypeError):
            return "0,00"
    
    # Registrar blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(orcamento_bp)
    app.register_blueprint(instrucoes_bp)
    app.register_blueprint(despesas_bp)
    app.register_blueprint(parcerias_bp)
    
    return app


# Criar instância da aplicação
app = create_app()


import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)