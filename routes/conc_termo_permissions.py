import re
import unicodedata

from flask import g, jsonify, session


WRITE_DENIED_MESSAGE = (
    'Este termo nao esta atribuido a voce. Voce pode visualizar, mas nao editar.'
)


def _is_admin_or_agente_publico():
    tipo = (session.get('tipo_usuario') or '').strip()
    return _is_admin_tipo(tipo)


def _normalizar_texto(valor):
    texto = str(valor or '').strip().lower()
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(ch for ch in texto if not unicodedata.combining(ch))
    return texto


def _is_admin_tipo(tipo):
    tipo_norm = _normalizar_texto(tipo)
    return tipo_norm in {'agente publico', 'admin', 'administrador'}


def _normalizar_rf(valor):
    return re.sub(r'\D', '', str(valor or '')).lstrip('0')


def _cache_key(numero_termo, email):
    return (str(numero_termo or '').strip(), str(email or '').strip().lower())


def get_termo_permission(cur, numero_termo):
    """
    Retorna o escopo de edicao do usuario logado para um termo.

    A consulta e cacheada por request e usa os indices ja existentes em
    checklist_analista(numero_termo) e checklist_analista(nome_analista).
    """
    numero_termo = str(numero_termo or '').strip()
    email = str(session.get('email') or '').strip().lower()

    if not numero_termo:
        return {
            'pode_editar': False,
            'motivo': 'numero_termo ausente',
            'usuario_nome': None,
            'is_admin': _is_admin_or_agente_publico(),
        }

    if _is_admin_or_agente_publico():
        return {
            'pode_editar': True,
            'motivo': 'usuario_admin_ou_agente_publico',
            'usuario_nome': session.get('user_name') or session.get('username'),
            'is_admin': True,
        }

    if not email:
        return {
            'pode_editar': False,
            'motivo': WRITE_DENIED_MESSAGE,
            'usuario_nome': None,
            'is_admin': False,
        }

    cache = getattr(g, '_conc_termo_permission_cache', None)
    if cache is None:
        cache = {}
        g._conc_termo_permission_cache = cache

    key = _cache_key(numero_termo, email)
    if key in cache:
        return cache[key]

    cur.execute("""
        SELECT email, tipo_usuario, d_usuario
        FROM gestao_pessoas.usuarios
        WHERE LOWER(email) = %s
        LIMIT 1
    """, (email,))
    usuario = cur.fetchone()

    if usuario and _is_admin_tipo(usuario.get('tipo_usuario')):
        session['tipo_usuario'] = usuario.get('tipo_usuario')
        payload = {
            'pode_editar': True,
            'motivo': 'usuario_admin_ou_agente_publico',
            'usuario_nome': session.get('user_name') or session.get('username'),
            'is_admin': True,
        }
        cache[key] = payload
        return payload

    cur.execute("""
        SELECT ui.usuario_nome
        FROM analises_pc.checklist_analista ca
        JOIN gestao_pessoas.usuarios_infos ui
          ON ui.usuario_nome = ca.nome_analista
        WHERE ca.numero_termo = %s
          AND LOWER(ui.usuario_email) = %s
        LIMIT 1
    """, (numero_termo, email))
    row = cur.fetchone()

    if not row and usuario and usuario.get('d_usuario'):
        rf_usuario = _normalizar_rf(usuario.get('d_usuario'))
        if rf_usuario:
            cur.execute("""
                SELECT ca.nome_analista
                FROM analises_pc.checklist_analista ca
                JOIN categoricas.c_dac_analistas da
                  ON da.nome_analista = ca.nome_analista
                WHERE ca.numero_termo = %s
                  AND REGEXP_REPLACE(LOWER(da.d_usuario), '[^0-9]', '', 'g') LIKE %s || '%%'
                LIMIT 1
            """, (numero_termo, rf_usuario))
            row = cur.fetchone()

    payload = {
        'pode_editar': bool(row),
        'motivo': 'termo_atribuido' if row else WRITE_DENIED_MESSAGE,
        'usuario_nome': row.get('usuario_nome') or row.get('nome_analista') if row else None,
        'is_admin': False,
    }
    cache[key] = payload
    return payload


def ensure_can_edit_termo(cur, numero_termo):
    permission = get_termo_permission(cur, numero_termo)
    if permission.get('pode_editar'):
        return True, None
    return False, (
        jsonify({
            'erro': WRITE_DENIED_MESSAGE,
            'pode_editar': False,
            'motivo': permission.get('motivo') or WRITE_DENIED_MESSAGE,
        }),
        403,
    )
