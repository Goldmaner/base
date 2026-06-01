"""
Decorators para controle de acesso por módulo e captura de erros
"""
from functools import wraps
from threading import Thread
import json
import traceback as _traceback
from flask import session, redirect, url_for, flash, request, current_app, jsonify
from config import ACESSOS_BASICOS, TIPOS_USUARIO

ACCESS_INHERITANCE = {
    'analises': [
        'conc_bancaria',
        'conc_rendimentos',
        'conc_contrapartida',
        'conc_relatorio',
        'conc_demonstrativo',
        'ocr_testes',
    ],
    'manuais': [
        'portarias',
    ],
}


def parse_access_list(user_acessos):
    """Normaliza a lista de acessos do usuário a partir de string ou coleção."""
    if not user_acessos:
        return []
    if isinstance(user_acessos, str):
        return [a.strip() for a in user_acessos.split(';') if a.strip()]
    if isinstance(user_acessos, (list, tuple, set)):
        return [str(a).strip() for a in user_acessos if str(a).strip()]
    return []


def get_module_access_status(user_acessos, modulo):
    """
    Retorna o status de acesso ao módulo, incluindo acesso herdado.

    Returns:
        dict: {
            'tem_acesso': bool,
            'tem_acesso_direto': bool,
            'tem_acesso_herdado': bool,
            'origem': str | None
        }
    """
    acessos_lista = parse_access_list(user_acessos)
    acessos_set = set(acessos_lista)

    if modulo in acessos_set:
        return {
            'tem_acesso': True,
            'tem_acesso_direto': True,
            'tem_acesso_herdado': False,
            'origem': modulo,
        }

    for modulo_origem, modulos_herdados in ACCESS_INHERITANCE.items():
        if modulo in modulos_herdados and modulo_origem in acessos_set:
            return {
                'tem_acesso': True,
                'tem_acesso_direto': False,
                'tem_acesso_herdado': True,
                'origem': modulo_origem,
            }

    return {
        'tem_acesso': False,
        'tem_acesso_direto': False,
        'tem_acesso_herdado': False,
        'origem': None,
    }


# =============================================================================
# LOGGING DE ERROS ASSÍNCRONO
# =============================================================================

def _salvar_erro_async(dados, app_instance):
    """Grava um registro em gestao_pessoas.log_erros em thread daemon."""
    conn = None
    try:
        with app_instance.app_context():
            from db import get_db
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO gestao_pessoas.log_erros (
                    tipo_erro, endpoint, metodo, status_codigo, usuario_email,
                    ip_address, duracao_ms, query_preview, api_nome, api_endpoint,
                    mensagem, detalhes
                ) VALUES (
                    %(tipo_erro)s, %(endpoint)s, %(metodo)s, %(status_codigo)s,
                    %(usuario_email)s, %(ip_address)s, %(duracao_ms)s,
                    %(query_preview)s, %(api_nome)s, %(api_endpoint)s,
                    %(mensagem)s, %(detalhes)s
                )
            """, dados)
            conn.commit()
    except Exception as e:
        print(f"[LOG_ERROS_AVISO] Falha ao salvar erro (não afeta aplicação): {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass


def registrar_erro(tipo_erro, **kwargs):
    """
    Registra um erro de forma assíncrona em gestao_pessoas.log_erros.
    Pode ser chamado de qualquer lugar com contexto Flask ativo.

    Args:
        tipo_erro (str): 'http_erro', 'query_lenta' ou 'api_externa'
        **kwargs: endpoint, metodo, status_codigo, usuario_email, ip_address,
                  duracao_ms, query_preview, api_nome, api_endpoint,
                  mensagem, detalhes (dict/list serializado para JSONB)
    """
    detalhes_raw = kwargs.get('detalhes')
    dados = {
        'tipo_erro':     tipo_erro,
        'endpoint':      kwargs.get('endpoint'),
        'metodo':        kwargs.get('metodo'),
        'status_codigo': kwargs.get('status_codigo'),
        'usuario_email': kwargs.get('usuario_email'),
        'ip_address':    kwargs.get('ip_address'),
        'duracao_ms':    kwargs.get('duracao_ms'),
        'query_preview': kwargs.get('query_preview'),
        'api_nome':      kwargs.get('api_nome'),
        'api_endpoint':  kwargs.get('api_endpoint'),
        'mensagem':      kwargs.get('mensagem'),
        'detalhes':      json.dumps(detalhes_raw, ensure_ascii=False)
                         if detalhes_raw is not None else None,
    }
    try:
        app = current_app._get_current_object()
        Thread(
            target=_salvar_erro_async,
            args=(dados, app),
            daemon=True
        ).start()
    except Exception as e:
        print(f"[LOG_ERROS_AVISO] Não foi possível disparar thread de erro: {e}")


def capture_errors(f):
    """
    Decorator que captura exceções não tratadas numa rota Flask,
    grava em gestao_pessoas.log_erros e re-propaga o erro.
    Não engole a exceção — o handler de erro padrão do Flask ainda é acionado.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as exc:
            tb = _traceback.format_exc()
            try:
                registrar_erro(
                    tipo_erro='http_erro',
                    endpoint=request.path,
                    metodo=request.method,
                    status_codigo=500,
                    usuario_email=session.get('email'),
                    ip_address=request.remote_addr,
                    mensagem=f"{type(exc).__name__}: {str(exc)}",
                    detalhes={'traceback': tb[-2000:]},
                )
            except Exception:
                pass
            raise
    return decorated

def requires_access(modulo):
    """
    Decorator que verifica se o usuário tem acesso ao módulo especificado.
    
    Args:
        modulo (str): Nome do módulo (ex: 'instrucoes', 'analises', 'parcerias')
    
    Usage:
        @requires_access('parcerias')
        def minha_rota():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar se usuário está logado
            if 'user_id' not in session:
                flash('Você precisa estar logado para acessar esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            # Agente Público tem acesso total
            if session.get('tipo_usuario') == 'Agente Público':
                return f(*args, **kwargs)

            # Módulos do pack básico são liberados para todo usuário autenticado
            if modulo in ACESSOS_BASICOS:
                return f(*args, **kwargs)
            
            # Verificar se o usuário tem acesso ao módulo
            acessos = session.get('acessos', '')
            
            # FALLBACK: Se sessão não tem acessos, buscar do banco e atualizar sessão
            if not acessos and 'user_id' in session:
                from db import get_cursor
                try:
                    cursor = get_cursor()
                    cursor.execute("""
                        SELECT acessos, acessos_escrita, tipo_usuario FROM gestao_pessoas.usuarios WHERE id = %s
                    """, (session['user_id'],))
                    result = cursor.fetchone()
                    cursor.close()
                    
                    if result:
                        acessos = result['acessos'] or ''
                        session['acessos'] = acessos
                        session['tipo_usuario'] = result['tipo_usuario']
                        session['acessos_escrita'] = result.get('acessos_escrita') or ''

                        # Se virou Agente Público, permitir acesso
                        if result['tipo_usuario'] == 'Agente Público':
                            print(f"[INFO FALLBACK] Usuário {session['user_id']} é Agente Público - acesso total")
                            return f(*args, **kwargs)
                except Exception as e:
                    print(f"[ERRO FALLBACK ACESSOS] {e}")
                    acessos = ''
            
            if not acessos:
                # Se não tem acessos definidos, negar acesso
                print(f"[ACESSO NEGADO] Usuário {session.get('user_id')} - Email: {session.get('email')} - Tipo: {session.get('tipo_usuario')} - Módulo: {modulo} - Acessos: (vazio)")
                flash(f'Você não tem permissão para acessar o módulo: {modulo}. Entre em contato com o administrador.', 'danger')
                return redirect(url_for('main.index'))
            
            # Verificar se o módulo está na lista de acessos
            lista_acessos = parse_access_list(acessos)
            status_acesso = get_module_access_status(lista_acessos, modulo)
            
            if not status_acesso['tem_acesso']:
                print(f"[ACESSO NEGADO] Módulo '{modulo}' não encontrado na lista de acessos do usuário")
                flash(f'Você não tem permissão para acessar o módulo: {modulo}. Entre em contato com o administrador.', 'danger')
                return redirect(url_for('main.index'))
            
            # Usuário tem acesso, continuar
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def check_module_access(user_acessos, modulo):
    """
    Função auxiliar para verificar acesso a um módulo.
    Útil para usar em templates.

    Args:
        user_acessos (str): String de acessos do usuário (ex: 'instrucoes;analises')
        modulo (str): Nome do módulo a verificar

    Returns:
        bool: True se tem acesso, False caso contrário
    """
    return get_module_access_status(user_acessos, modulo)['tem_acesso']


def has_write_access(modulo):
    """
    Verifica se o usuário logado tem permissão de escrita no módulo.
    Tipos com escrita_padrao=True (agentes internos) passam direto.
    Tipos com escrita_padrao=False (Externo: Gabinete) precisam de liberação explícita.
    """
    tipo = session.get('tipo_usuario', '')
    cfg = TIPOS_USUARIO.get(tipo, {})
    if cfg.get('admin') or cfg.get('escrita_padrao', True):
        return True
    acessos_esc = parse_access_list(session.get('acessos_escrita', ''))
    return modulo in acessos_esc


def requires_write_access(modulo):
    """
    Decorador para rotas POST/PUT/DELETE que exigem permissão de escrita no módulo.
    Retorna 403 com tipo='sem_permissao_escrita' quando bloqueado, para que o
    frontend exiba a mensagem amigável 'Solicite permissão ao admin'.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not has_write_access(modulo):
                return jsonify({
                    "erro": "Você não tem permissão para realizar esta ação.",
                    "detalhe": "Solicite permissão ao administrador do sistema.",
                    "tipo": "sem_permissao_escrita"
                }), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator
