"""
Aplicação Flask - FAF (Ferramenta de Análise Financeira)

Arquivo principal que inicializa a aplicação e registra os blueprints.
"""

from flask import Flask, request, session, g, current_app
from config import SECRET_KEY, DEBUG
from db import close_db, get_db
from utils import format_sei
import time
from threading import Thread

# Importar blueprints
from routes.main import main_bp
from routes.auth import auth_bp
from routes.orcamento import orcamento_bp
from routes.instrucoes import instrucoes_bp
from routes.despesas import despesas_bp
from routes.parcerias import parcerias_bp
from routes.listas import listas_bp
from routes.analises import analises_bp
from routes.pesquisa_parcerias import pesquisa_parcerias_bp
from routes.analises_pc import analises_pc_bp
from routes.parcerias_notificacoes import bp as parcerias_notificacoes_bp
from routes.conc_bancaria import bp as conc_bancaria_bp
from routes.conc_rendimentos import bp as conc_rendimentos_bp
from routes.conc_contrapartida import bp as conc_contrapartida_bp
from routes.conc_exportacao import bp as conc_exportacao_bp
from routes.conc_relatorio import bp as conc_relatorio_bp
from routes.conc_demonstrativo import bp as conc_demonstrativo_bp
from routes.ocr_testes import bp as ocr_testes_bp
from routes.gestao_financeira import gestao_financeira_bp
from routes.gestao_financeira_ultra_liquidacoes import ultra_liquidacoes_bp
from routes.gestao_orcamentaria import gestao_orcamentaria_bp
from routes.ferias import ferias_bp
from routes.editais import editais_bp
from routes.certidoes import certidoes_bp
from routes.cents import cents_bp
from routes.celebracao_parcerias import celebracao_parcerias_bp
from routes.sof_api import sof_api_bp


# ============================================================================
# FUNÇÕES DE LOGGING AUTOMÁTICO
# ============================================================================

def deve_logar_rota(path, method):
    """
    Define quais rotas devem ser logadas para evitar overhead desnecessário.
    
    Loga:
    - Todas as modificações (POST, PUT, DELETE)
    - GETs importantes (páginas principais, exports, downloads)
    
    NÃO loga:
    - Arquivos estáticos (CSS, JS, imagens)
    - Autocompletes e filtros (muito frequentes)
    - APIs de validação/checagem rápida
    """
    # NÃO logar arquivos estáticos
    if path.startswith('/static/'):
        return False
    if path.endswith(('.js', '.css', '.png', '.jpg', '.ico', '.svg', '.woff', '.woff2', '.ttf')):
        return False
    
    # NÃO logar autocompletes e filtros (muito frequentes)
    rotas_ignorar = [
        '/api/filtros-dados',
        '/api/termos-disponiveis',
        '/api/status-pagamento',
        '/heartbeat',
        '/health'
    ]
    if any(path.startswith(rota) for rota in rotas_ignorar):
        return False
    
    # Logar TODAS as modificações (POST, PUT, DELETE)
    if method in ['POST', 'PUT', 'DELETE']:
        return True
    
    # Para GET, logar apenas rotas importantes
    if method == 'GET':
        rotas_importantes = [
            '/api/exportar-csv',
            '/gerar-encaminhamento-pagamento',
            '/documento-anuencia-pessoa-gestora',
            '/gestao_financeira/ultra-liquidacoes',
            '/parcerias',
            '/editais',
            '/ferias',
            '/orcamento',
            '/analises',
            '/listas',
            '/gestao_orcamentaria'
        ]
        # Logar se começar com alguma rota importante
        return any(path.startswith(rota) for rota in rotas_importantes)
    
    return False


def identificar_categoria(endpoint):
    """Identifica categoria da ação baseada na URL"""
    categorias = {
        'ultra-liquidacoes': 'parcelas',
        'ultra_liquidacoes': 'parcelas',
        'parcerias': 'termos',
        'editais': 'editais',
        'ferias': 'ferias',
        'orcamento': 'orcamento',
        'analises': 'analises',
        'usuarios': 'usuarios',
        'alterar-senha': 'autenticacao',
        'alterar-minha-senha': 'autenticacao',
        'login': 'autenticacao',
        'logout': 'autenticacao',
        'despesas': 'despesas',
        'listas': 'listas',
        'conc_': 'conciliacoes',
        'gestao_financeira': 'gestao_financeira',
        'gestao_orcamentaria': 'gestao_orcamentaria',
        'certidoes': 'certidoes',
        'cents': 'cents'
    }
    
    endpoint_lower = endpoint.lower()
    for chave, categoria in categorias.items():
        if chave in endpoint_lower:
            return categoria
    
    return 'outros'


def mapear_acao_tipo(metodo, endpoint):
    """Mapeia método HTTP e endpoint para tipo de ação"""
    if metodo == 'GET':
        if 'exportar' in endpoint or 'gerar-' in endpoint or 'download' in endpoint:
            return 'download'
        return 'visualizacao'
    elif metodo == 'POST':
        return 'criacao'
    elif metodo == 'PUT':
        return 'edicao'
    elif metodo == 'DELETE':
        return 'exclusao'
    
    return 'outros'


def salvar_log_atividade(dados, app_instance):
    """
    Salva log de atividade no banco de dados.
    Executa em thread separada para não afetar performance.
    
    PROTEÇÕES DE PERFORMANCE:
    1. Executa em thread daemon (não bloqueia shutdown)
    2. Usa conexão independente (não afeta transações principais)
    3. Try-catch abrangente (nunca quebra aplicação)
    4. Timeout implícito (thread morre se demorar muito)
    5. Commit isolado (não interfere em outras operações)
    """
    conn = None
    cur = None
    
    try:
        # CRÍTICO: Thread precisa de contexto Flask para acessar get_db()
        with app_instance.app_context():
            conn = get_db()
            cur = conn.cursor()
            
            # INSERT com timeout implícito do PostgreSQL
            cur.execute("""
                INSERT INTO gestao_pessoas.log_atividades (
                    usuario_nome, usuario_email, tipo_usuario,
                    acao_tipo, acao_categoria, acao_endpoint, acao_metodo,
                    status_codigo, sucesso, ip_address, user_agent, duracao_ms,
                    created_at
                ) VALUES (
                    %(usuario_nome)s, %(usuario_email)s, %(tipo_usuario)s,
                    %(acao_tipo)s, %(acao_categoria)s, %(acao_endpoint)s, %(acao_metodo)s,
                    %(status_codigo)s, %(sucesso)s, %(ip_address)s, %(user_agent)s, %(duracao_ms)s,
                    NOW()
                )
            """, dados)
            
            # Commit isolado - não afeta outras transações
            conn.commit()
        
    except Exception as e:
        # CRÍTICO: NUNCA deixar log quebrar a aplicação
        # Silenciosamente falha e imprime aviso no console
        print(f"[LOG_AVISO] Falha ao salvar log (não afeta aplicação): {e}")
        
        # Rollback se necessário
        if conn:
            try:
                conn.rollback()
            except:
                pass
    
    finally:
        # Garantir limpeza de recursos
        if cur:
            try:
                cur.close()
            except:
                pass


# ============================================================================
# FIM DAS FUNÇÕES DE LOGGING
# ============================================================================


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
    app.register_blueprint(listas_bp)
    app.register_blueprint(analises_bp)
    app.register_blueprint(pesquisa_parcerias_bp)
    app.register_blueprint(analises_pc_bp)
    app.register_blueprint(parcerias_notificacoes_bp)
    app.register_blueprint(conc_bancaria_bp)
    app.register_blueprint(conc_rendimentos_bp)
    app.register_blueprint(conc_contrapartida_bp)
    app.register_blueprint(conc_exportacao_bp)
    app.register_blueprint(conc_relatorio_bp)
    app.register_blueprint(conc_demonstrativo_bp)
    app.register_blueprint(ocr_testes_bp)
    app.register_blueprint(gestao_financeira_bp)
    app.register_blueprint(ultra_liquidacoes_bp)
    app.register_blueprint(gestao_orcamentaria_bp)
    app.register_blueprint(ferias_bp)
    app.register_blueprint(editais_bp)
    app.register_blueprint(certidoes_bp)
    app.register_blueprint(cents_bp)
    app.register_blueprint(celebracao_parcerias_bp)
    app.register_blueprint(sof_api_bp)
    
    # ========================================================================
    # HOOKS GLOBAIS PARA LOGGING AUTOMÁTICO
    # ========================================================================
    
    @app.before_request
    def antes_da_requisicao():
        """
        Intercepta TODAS as requisições ANTES de executar.
        Marca tempo de início e salva dados do usuário.
        """
        g.inicio = time.time()
        # CORREÇÃO: Buscar dados corretos do session
        g.usuario_nome = session.get('d_usuario')  # Nome é o d_usuario (ex: d843702)
        g.usuario_email = session.get('email')      # Email vem do campo email
        g.tipo_usuario = session.get('tipo_usuario')
    
    @app.after_request
    def depois_da_requisicao(response):
        """
        Intercepta TODAS as respostas APÓS execução.
        Salva log de atividade se a rota for relevante.
        
        PERFORMANCE: Logging é assíncrono (thread separada) e não adiciona
        latência à resposta do usuário. Resposta retorna IMEDIATAMENTE.
        """
        try:
            # Verificar se deve logar esta rota
            if deve_logar_rota(request.path, request.method):
                duracao_ms = int((time.time() - g.get('inicio', time.time())) * 1000)
                
                # Preparar dados do log (limitar tamanhos para evitar overhead)
                dados_log = {
                    'usuario_nome': g.get('usuario_nome'),
                    'usuario_email': g.get('usuario_email'),
                    'tipo_usuario': g.get('tipo_usuario'),
                    'acao_endpoint': request.path[:500],  # Limitar a 500 chars
                    'acao_metodo': request.method,
                    'acao_tipo': mapear_acao_tipo(request.method, request.path),
                    'acao_categoria': identificar_categoria(request.path),
                    'status_codigo': response.status_code,
                    'sucesso': response.status_code < 400,
                    'ip_address': (request.remote_addr or 'unknown')[:45],  # IPv6 = 45 chars
                    'user_agent': (request.user_agent.string or '')[:500],  # Limitar a 500 chars
                    'duracao_ms': duracao_ms
                }
                
                # CRÍTICO: Salvar log em thread daemon separada
                # - Thread daemon = não impede shutdown da aplicação
                # - Start() retorna IMEDIATAMENTE (não espera thread terminar)
                # - Se thread falhar, não afeta a resposta ao usuário
                # - IMPORTANTE: Passar instância do app para ter contexto Flask
                Thread(
                    target=salvar_log_atividade, 
                    args=(dados_log, current_app._get_current_object()), 
                    daemon=True
                ).start()
        
        except Exception as e:
            # Se logging falhar, não quebrar resposta ao usuário
            print(f"[LOG_AVISO] Erro ao preparar log (ignorado): {e}")
            pass
        
        # SEMPRE retornar response (mesmo se log falhar)
        return response
    
    # ========================================================================
    # FIM DOS HOOKS DE LOGGING
    # ========================================================================
    
    return app


# Criar instância da aplicação
app = create_app()


import os

if __name__ == '__main__':
    # Se executar direto app.py (não recomendado), usa porta 8080
    port = int(os.environ.get('PORT', 8080))
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    print("⚠️  Executando app.py diretamente.")
    print(f"   Porta: {port}")
    print(f"   Use 'python run_dev.py' para desenvolvimento")
    print(f"   Use 'python run_prod.py' para produção")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port, use_reloader=debug_mode)