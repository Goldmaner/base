"""
Blueprint de relatos de usuários — reporte de erros, sugestões, melhorias e dúvidas.
Acessível por todos os usuários autenticados.
"""

import json
from flask import Blueprint, jsonify, request, session
from db import get_cursor, get_db
from utils import login_required

relatos_bp = Blueprint('relatos', __name__, url_prefix='/api/relatos')

LIMITE_DIARIO    = 5
TIPOS_VALIDOS    = {'Erro', 'Sugestão', 'Melhoria', 'Dúvida'}
PRIORIDADES_VALIDAS = {'Urgente', 'Normal', 'Baixa'}


def _contar_relatos_hoje(cur, email):
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM gestao_pessoas.relatos_usuarios
        WHERE usuario_email = %s
          AND criado_em::date = CURRENT_DATE
    """, (email,))
    return cur.fetchone()['total']


# =============================================================================
# USUÁRIO — novo relato
# =============================================================================

@relatos_bp.route('/novo', methods=['POST'])
@login_required
def novo_relato():
    data = request.get_json(silent=True) or {}

    email        = session.get('email', '')
    nome         = session.get('d_usuario', '')
    tipo_usuario = session.get('tipo_usuario', '')

    tipo_relato  = (data.get('tipo_relato')       or '').strip()
    modulo       = (data.get('modulo')             or '').strip()
    titulo       = (data.get('titulo')             or '').strip()
    descricao    = (data.get('descricao')          or '').strip()
    passos       = (data.get('passos_reproducao')  or '').strip()
    url_pagina   = (data.get('url_pagina')         or '').strip()[:500]
    prioridade   = (data.get('prioridade_usuario') or 'Normal').strip()
    det_tec      = data.get('detalhes_tecnicos')   or {}

    # ── Validações ────────────────────────────────────────────────────────
    if tipo_relato not in TIPOS_VALIDOS:
        return jsonify({'erro': 'Tipo de relato inválido.'}), 400
    if not modulo:
        return jsonify({'erro': 'Módulo é obrigatório.'}), 400
    if not titulo:
        return jsonify({'erro': 'Título é obrigatório.'}), 400
    if len(titulo) > 255:
        return jsonify({'erro': 'Título muito longo (máx. 255 caracteres).'}), 400
    if not descricao:
        return jsonify({'erro': 'Descrição é obrigatória.'}), 400
    if prioridade not in PRIORIDADES_VALIDAS:
        prioridade = 'Normal'

    db  = get_db()
    cur = get_cursor()

    # ── Limite diário ─────────────────────────────────────────────────────
    if _contar_relatos_hoje(cur, email) >= LIMITE_DIARIO:
        return jsonify({
            'erro': f'Limite diário de {LIMITE_DIARIO} relatos atingido. Tente novamente amanhã.'
        }), 429

    cur.execute("""
        INSERT INTO gestao_pessoas.relatos_usuarios (
            tipo_relato, modulo, titulo, descricao, passos_reproducao,
            url_pagina, prioridade_usuario, status,
            detalhes_tecnicos, usuario_email, usuario_nome, tipo_usuario,
            criado_em
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Aberto', %s, %s, %s, %s, NOW())
        RETURNING id
    """, (
        tipo_relato, modulo, titulo, descricao,
        passos    or None,
        url_pagina or None,
        prioridade,
        json.dumps(det_tec, ensure_ascii=False) if det_tec else None,
        email, nome, tipo_usuario,
    ))
    novo_id = cur.fetchone()['id']
    db.commit()

    return jsonify({'success': True, 'id': novo_id, 'mensagem': 'Relato enviado com sucesso!'}), 201


# =============================================================================
# USUÁRIO — listar meus relatos
# =============================================================================

@relatos_bp.route('/meus', methods=['GET'])
@login_required
def meus_relatos():
    email = session.get('email', '')
    cur   = get_cursor()

    cur.execute("""
        SELECT id, tipo_relato, modulo, titulo, descricao, passos_reproducao,
               prioridade_usuario, status, resposta_admin, criado_em, atualizado_em
        FROM gestao_pessoas.relatos_usuarios
        WHERE usuario_email = %s
        ORDER BY criado_em DESC
        LIMIT 50
    """, (email,))
    relatos = cur.fetchall()

    resultado = []
    for r in relatos:
        resultado.append({
            'id':                r['id'],
            'tipo_relato':       r['tipo_relato'],
            'modulo':            r['modulo'],
            'titulo':            r['titulo'],
            'descricao':         r['descricao'],
            'passos_reproducao': r['passos_reproducao'],
            'prioridade_usuario': r['prioridade_usuario'],
            'status':            r['status'],
            'resposta_admin':    r['resposta_admin'],
            'criado_em':         r['criado_em'].strftime('%d/%m/%Y %H:%M') if r['criado_em'] else None,
            'atualizado_em':     r['atualizado_em'].strftime('%d/%m/%Y %H:%M') if r['atualizado_em'] else None,
        })

    return jsonify({'relatos': resultado})


# =============================================================================
# USUÁRIO — editar relato próprio (somente status = 'Aberto')
# =============================================================================

@relatos_bp.route('/<int:relato_id>/editar', methods=['PATCH'])
@login_required
def editar_relato(relato_id):
    email = session.get('email', '')
    data  = request.get_json(silent=True) or {}

    cur = get_cursor()
    cur.execute("""
        SELECT id, status, usuario_email
        FROM gestao_pessoas.relatos_usuarios
        WHERE id = %s
    """, (relato_id,))
    relato = cur.fetchone()

    if not relato:
        return jsonify({'erro': 'Relato não encontrado.'}), 404
    if relato['usuario_email'] != email:
        return jsonify({'erro': 'Acesso negado.'}), 403
    if relato['status'] != 'Aberto':
        return jsonify({'erro': 'Somente relatos com status "Aberto" podem ser editados.'}), 403

    tipo_relato = (data.get('tipo_relato')       or '').strip()
    modulo      = (data.get('modulo')             or '').strip()
    titulo      = (data.get('titulo')             or '').strip()
    descricao   = (data.get('descricao')          or '').strip()
    passos      = (data.get('passos_reproducao')  or '').strip()
    prioridade  = (data.get('prioridade_usuario') or 'Normal').strip()

    if tipo_relato not in TIPOS_VALIDOS:
        return jsonify({'erro': 'Tipo de relato inválido.'}), 400
    if not modulo:
        return jsonify({'erro': 'Módulo é obrigatório.'}), 400
    if not titulo:
        return jsonify({'erro': 'Título é obrigatório.'}), 400
    if len(titulo) > 255:
        return jsonify({'erro': 'Título muito longo (máx. 255 caracteres).'}), 400
    if not descricao:
        return jsonify({'erro': 'Descrição é obrigatória.'}), 400
    if prioridade not in PRIORIDADES_VALIDAS:
        prioridade = 'Normal'

    db = get_db()
    cur.execute("""
        UPDATE gestao_pessoas.relatos_usuarios
        SET tipo_relato       = %s,
            modulo            = %s,
            titulo            = %s,
            descricao         = %s,
            passos_reproducao = %s,
            prioridade_usuario = %s,
            atualizado_em     = NOW()
        WHERE id = %s
    """, (tipo_relato, modulo, titulo, descricao, passos or None, prioridade, relato_id))
    db.commit()

    return jsonify({'success': True, 'mensagem': 'Relato atualizado com sucesso!'})
