"""
Funções utilitárias e decoradores
"""

from flask import session, redirect, url_for
from functools import wraps


def format_sei(sei_number):
    """
    Formata número SEI no padrão: 6074.2022/0008210-7
    Entrada: 6074202200082107 -> Saída: 6074.2022/0008210-7
    """
    if not sei_number:
        return '-'
    
    sei_str = str(sei_number).strip()
    if len(sei_str) < 16:
        return sei_str  # retorna como está se for menor que 16 dígitos
    
    # Formato: XXXX.XXXX/XXXXXXX-X
    parte1 = sei_str[:4]    # 6074
    parte2 = sei_str[4:8]   # 2022
    parte3 = sei_str[8:15]  # 0008210
    parte4 = sei_str[15]    # 7
    
    return f"{parte1}.{parte2}/{parte3}-{parte4}"


def login_required(f):
    """
    Decorador para proteger rotas que requerem autenticação.
    Redireciona para a página de login se o usuário não estiver autenticado.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated
