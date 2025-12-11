"""
Decorators para controle de acesso por módulo
"""
from functools import wraps
from flask import session, redirect, url_for, flash

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
            
            # Verificar se o usuário tem acesso ao módulo
            acessos = session.get('acessos', '')
            
            # FALLBACK: Se sessão não tem acessos, buscar do banco
            if not acessos and 'user_id' in session:
                from db import get_cursor
                try:
                    cursor = get_cursor()
                    cursor.execute("""
                        SELECT acessos FROM usuarios WHERE id = %s
                    """, (session['user_id'],))
                    result = cursor.fetchone()
                    if result:
                        acessos = result['acessos'] or ''
                        session['acessos'] = acessos  # Atualizar sessão
                except Exception as e:
                    print(f"[ERRO FALLBACK ACESSOS] {e}")
                    acessos = ''
            
            if not acessos:
                # Se não tem acessos definidos, negar acesso
                flash(f'Você não tem permissão para acessar o módulo: {modulo}. Faça login novamente.', 'danger')
                return redirect(url_for('main.index'))
            
            # Verificar se o módulo está na lista de acessos
            lista_acessos = [a.strip() for a in acessos.split(';') if a.strip()]
            
            if modulo not in lista_acessos:
                flash(f'Você não tem permissão para acessar o módulo: {modulo}', 'danger')
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
    if not user_acessos:
        return False
    
    lista_acessos = [a.strip() for a in user_acessos.split(';') if a.strip()]
    return modulo in lista_acessos
