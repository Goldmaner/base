"""
Blueprint da Central de Páginas — FParcerias
Mapa visual de navegação em árvore para orientação do usuário.
"""

from flask import Blueprint, render_template, jsonify, request, session
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access
from config import ACESSOS_BASICOS
from decorators import get_module_access_status

central_paginas_bp = Blueprint('central_paginas', __name__, url_prefix='/central-paginas')


def _user_access_set():
    """Retorna (set de módulos liberados, is_admin) para o usuário logado."""
    is_admin = session.get('tipo_usuario') == 'Agente Público'
    raw = session.get('acessos', '')
    acessos = set(a.strip() for a in raw.split(';') if a.strip())
    acessos.update(ACESSOS_BASICOS)
    return acessos, is_admin


def _has_access(acessos_set, is_admin, modulo_acesso):
    """Verifica acesso a um módulo respeitando herança (ex: analises → conc_bancaria)."""
    if is_admin or not modulo_acesso:
        return True
    return get_module_access_status(acessos_set, modulo_acesso)['tem_acesso']


def _build_tree(paginas, acessos_set, is_admin):
    """
    Constrói árvore agrupada por área e pré-computa o acesso por nó.
    Retorna dict: { area: [pagina_com_filhos, ...] }
    """
    por_id = {}
    for p in paginas:
        node = dict(p)
        node['filhos'] = []
        node['tem_acesso'] = _has_access(acessos_set, is_admin, p.get('modulo_acesso'))
        por_id[node['id']] = node

    areas = {}
    for p in paginas:
        node = por_id[p['id']]
        parent_id = p.get('parent_id')
        if parent_id is None:
            area = p['area'] or 'Apoio / Outros'
            areas.setdefault(area, []).append(node)
        else:
            pai = por_id.get(parent_id)
            if pai:
                pai['filhos'].append(node)

    return areas


@central_paginas_bp.route('/', methods=['GET'])
@login_required
@requires_access('central_paginas')
def index():
    cur = get_cursor()
    cur.execute("""
        SELECT id, nome_pagina, rota, area, descricao, responsavel,
               icone, ordem, parent_id, modulo_acesso
        FROM sistema.mapa_paginas
        WHERE ativo = TRUE
        ORDER BY area, ordem, nome_pagina
    """)
    paginas = cur.fetchall()
    acessos_set, is_admin = _user_access_set()
    areas = _build_tree(paginas, acessos_set, is_admin)
    return render_template('central_paginas.html', areas=areas, is_admin=is_admin)


@central_paginas_bp.route('/api/lista', methods=['GET'])
@login_required
def api_lista():
    cur = get_cursor()
    cur.execute("""
        SELECT id, nome_pagina, rota, area, descricao, responsavel,
               icone, ordem, parent_id, modulo_acesso
        FROM sistema.mapa_paginas
        WHERE ativo = TRUE
        ORDER BY area, ordem, nome_pagina
    """)
    paginas = cur.fetchall()
    return jsonify([dict(p) for p in paginas])


@central_paginas_bp.route('/api/pagina/<int:pagina_id>', methods=['PUT'])
@login_required
def atualizar_pagina(pagina_id):
    """Atualiza campos editáveis de uma página (apenas admin)."""
    _, is_admin = _user_access_set()
    if not is_admin:
        return jsonify({'erro': 'Sem permissão.'}), 403

    dados = request.get_json(silent=True) or {}
    campos_permitidos = {'responsavel', 'icone', 'descricao', 'ordem'}
    atualizacoes = {k: v for k, v in dados.items() if k in campos_permitidos}

    if not atualizacoes:
        return jsonify({'erro': 'Nenhum campo válido.'}), 400

    set_clause = ', '.join(f"{k} = %s" for k in atualizacoes)
    valores = list(atualizacoes.values()) + [pagina_id]

    cur = get_cursor()
    cur.execute(
        f"UPDATE sistema.mapa_paginas SET {set_clause} WHERE id = %s",
        valores
    )
    get_db().commit()
    return jsonify({'ok': True})
