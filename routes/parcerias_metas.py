"""
Blueprint de Quadro de Metas — Plano de Trabalho
Gerenciamento das metas vinculadas a processos SEI (celebração, parcerias, editais).
"""

import csv
import io
from datetime import datetime
from flask import (
    Blueprint, render_template, request, jsonify, session, Response
)
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access

parcerias_metas_bp = Blueprint(
    'parcerias_metas', __name__, url_prefix='/parcerias-metas'
)


# ── Helpers de retroalimentação ───────────────────────────────────────────────

def _resolve_indicador(texto, usuario):
    """Retorna id do indicador pelo texto (str), criando-o se não existir."""
    if not texto:
        return None
    cur = get_cursor()
    cur.execute(
        "SELECT id FROM categoricas.c_dgp_indicadores WHERE LOWER(indicador) = LOWER(%s)",
        (texto,)
    )
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute(
        "INSERT INTO categoricas.c_dgp_indicadores (indicador, criado_por) "
        "VALUES (%s, %s) RETURNING id",
        (texto, usuario)
    )
    return cur.fetchone()['id']


def _resolve_indicadores(textos, usuario):
    """Resolve lista de textos → lista de ids (cria os que não existem)."""
    ids = []
    for t in textos:
        t = (t or '').strip()
        if t:
            ids.append(_resolve_indicador(t, usuario))
    return ids or None


def _resolve_meio(texto, usuario):
    """Retorna id do meio de aferição pelo texto (str), criando-o se não existir."""
    if not texto:
        return None
    cur = get_cursor()
    cur.execute(
        "SELECT id FROM categoricas.c_dgp_meios_afericao WHERE LOWER(meios_afericao) = LOWER(%s)",
        (texto,)
    )
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute(
        "INSERT INTO categoricas.c_dgp_meios_afericao (meios_afericao, criado_por) "
        "VALUES (%s, %s) RETURNING id",
        (texto, usuario)
    )
    return cur.fetchone()['id']


def _resolve_meios(textos, usuario):
    """Resolve lista de textos → lista de ids (cria os que não existem)."""
    ids = []
    for t in textos:
        t = (t or '').strip()
        if t:
            ids.append(_resolve_meio(t, usuario))
    return ids or None


# ── Rota principal ────────────────────────────────────────────────────────────

@parcerias_metas_bp.route("/", methods=["GET"])
@login_required
@requires_access('parcerias_metas')
def index():
    cur = get_cursor()
    filtro_sei = request.args.get('filtro_sei', '').strip()

    # Catálogos para os modais
    cur.execute("""
        SELECT id, meta_tipo, tipo_classificacao
        FROM categoricas.c_dgp_meta_tipos
        ORDER BY tipo_classificacao, meta_tipo
    """)
    meta_tipos = cur.fetchall()

    cur.execute("SELECT id, indicador FROM categoricas.c_dgp_indicadores ORDER BY indicador")
    indicadores = cur.fetchall()

    cur.execute("SELECT id, meios_afericao FROM categoricas.c_dgp_meios_afericao ORDER BY meios_afericao")
    meios_afericao = cur.fetchall()

    # Query principal com numero_termo e osc via JOIN
    where_clause = ""
    params = []
    if filtro_sei:
        where_clause = "WHERE cm.sei_numero ILIKE %s"
        params.append(f"%{filtro_sei}%")

    cur.execute(f"""
        SELECT
            cm.id,
            cm.sei_numero,
            cm.meta_titulo,
            cm.meta_descricao,
            cm.meta_objetivo,
            cm.meta_tipo_ids,
            cm.tipos_ni,
            cm.indicadores_ids,
            cm.indicadores_ni,
            cm.meta_obs_indicadores,
            COALESCE(
                (SELECT STRING_AGG(ind.indicador, ' | ' ORDER BY ind.indicador)
                 FROM categoricas.c_dgp_indicadores ind
                 WHERE ind.id = ANY(cm.indicadores_ids)),
                NULL
            ) AS indicador_label,
            cm.meios_afericao_ids,
            cm.meios_ni,
            COALESCE(
                (SELECT STRING_AGG(ma.meios_afericao, ' | ' ORDER BY ma.meios_afericao)
                 FROM categoricas.c_dgp_meios_afericao ma
                 WHERE ma.id = ANY(cm.meios_afericao_ids)),
                NULL
            ) AS meios_afericao_label,
            cm.observacoes,
            cm.ordem,
            COALESCE(p.numero_termo, cp.numero_termo, '-') AS numero_termo,
            COALESCE(p.osc, cp.osc, '-')                   AS osc,
            cm.criado_por,
            cm.criado_em,
            cm.atualizado_por,
            cm.atualizado_em
        FROM celebracao.celebracao_metas cm
        LEFT JOIN public.parcerias p
            ON p.sei_celeb = cm.sei_numero
        LEFT JOIN celebracao.celebracao_parcerias cp
            ON cp.sei_celeb = cm.sei_numero
        {where_clause}
        ORDER BY cm.sei_numero, cm.ordem, cm.id
    """, params)
    metas = cur.fetchall()

    # Expande labels dos tipos (INTEGER[])
    tipo_map = {r['id']: r for r in meta_tipos}
    ind_map  = {r['id']: r['indicador'] for r in indicadores}
    meio_map = {r['id']: r['meios_afericao'] for r in meios_afericao}
    metas_com_tipos = []
    for m in metas:
        row = dict(m)
        ids = row.get('meta_tipo_ids') or []
        row['meta_tipos_labels'] = [tipo_map[i] for i in ids if i in tipo_map]
        # Listas de textos para repopular o modal de edição
        ind_ids  = row.get('indicadores_ids')  or []
        meio_ids = row.get('meios_afericao_ids') or []
        row['indicadores_textos']  = [ind_map[i]  for i in ind_ids  if i in ind_map]
        row['meios_textos']        = [meio_map[i] for i in meio_ids if i in meio_map]
        # Obs paralelas (array TEXT[])
        row['obs_indicadores'] = list(row.get('meta_obs_indicadores') or [])
        metas_com_tipos.append(row)

    return render_template(
        'parcerias_metas.html',
        metas=metas_com_tipos,
        meta_tipos=meta_tipos,
        indicadores=indicadores,
        meios_afericao=meios_afericao,
        filtro_sei=filtro_sei,
    )


# ── Dicionário de Indicadores e Meios de Aferição ─────────────────────────────

@parcerias_metas_bp.route("/dicionario", methods=["GET"])
@login_required
@requires_access('parcerias_metas')
def dicionario():
    cur = get_cursor()
    cur.execute("""
        SELECT id, indicador, descricao, observacao
        FROM categoricas.c_dgp_indicadores
        ORDER BY indicador
    """)
    indicadores = cur.fetchall()

    cur.execute("""
        SELECT id, meios_afericao, descricao, observacao
        FROM categoricas.c_dgp_meios_afericao
        ORDER BY meios_afericao
    """)
    meios_afericao = cur.fetchall()

    return render_template(
        'parcerias_metas_dicionario.html',
        indicadores=indicadores,
        meios_afericao=meios_afericao,
    )


# ── API: SEI numbers (3 fontes) ───────────────────────────────────────────────

@parcerias_metas_bp.route("/api/sei-numeros", methods=["GET"])
@login_required
def api_sei_numeros():
    cur = get_cursor()
    # SEIs firmados em parcerias (prioridade máxima — sem rótulo de celebração)
    cur.execute("""
        WITH sei_parceria AS (
            SELECT TRIM(sei_celeb) AS sei_numero
            FROM public.parcerias
            WHERE sei_celeb IS NOT NULL AND TRIM(sei_celeb) != ''
        ),
        sei_celebracao AS (
            SELECT TRIM(sei_celeb) AS sei_numero
            FROM celebracao.celebracao_parcerias
            WHERE sei_celeb IS NOT NULL AND TRIM(sei_celeb) != ''
        ),
        sei_edital AS (
            SELECT TRIM(edital_processo_sei) AS sei_numero
            FROM public.parcerias_edital
            WHERE edital_processo_sei IS NOT NULL AND TRIM(edital_processo_sei) != ''
        )
        SELECT sei_numero, 'Parceria' AS fonte FROM sei_parceria
        UNION
        -- Celebrações só aparecem se não há parceria firmada com o mesmo SEI
        SELECT sei_numero, 'Celebração' AS fonte
        FROM sei_celebracao
        WHERE sei_numero NOT IN (SELECT sei_numero FROM sei_parceria)
        UNION
        SELECT sei_numero, 'Edital' AS fonte
        FROM sei_edital
        WHERE sei_numero NOT IN (SELECT sei_numero FROM sei_parceria)
          AND sei_numero NOT IN (SELECT sei_numero FROM sei_celebracao)
        ORDER BY sei_numero
    """)
    rows = cur.fetchall()
    return jsonify([{'sei_numero': r['sei_numero'], 'fonte': r['fonte']} for r in rows])


# ── API: Meta tipos agrupados ─────────────────────────────────────────────────

@parcerias_metas_bp.route("/api/meta-tipos", methods=["GET"])
@login_required
def api_meta_tipos():
    cur = get_cursor()
    cur.execute("""
        SELECT id, meta_tipo, tipo_classificacao, descricao
        FROM categoricas.c_dgp_meta_tipos
        ORDER BY tipo_classificacao NULLS LAST, meta_tipo
    """)
    rows = cur.fetchall()

    # Agrupar por tipo_classificacao
    grupos = {}
    for r in rows:
        cls = r['tipo_classificacao'] or 'Sem classificação'
        if cls not in grupos:
            grupos[cls] = []
        grupos[cls].append({'id': r['id'], 'meta_tipo': r['meta_tipo'], 'descricao': r['descricao']})

    return jsonify(grupos)


# ── API: Definições (glossário) ───────────────────────────────────────────────

@parcerias_metas_bp.route("/api/definicoes", methods=["GET"])
@login_required
def api_definicoes():
    cur = get_cursor()
    cur.execute("""
        SELECT id, conceito, definicao, observacoes
        FROM categoricas.c_dgp_plano_definicoes
        ORDER BY conceito
    """)
    rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


# ── API: Indicadores (retroalimentação + dicionário) ──────────────────────────

@parcerias_metas_bp.route("/api/indicadores", methods=["GET"])
@login_required
def api_indicadores():
    cur = get_cursor()
    cur.execute("SELECT id, indicador, descricao FROM categoricas.c_dgp_indicadores ORDER BY indicador")
    return jsonify([dict(r) for r in cur.fetchall()])


@parcerias_metas_bp.route("/api/indicadores", methods=["POST"])
@login_required
@requires_access('parcerias_metas')
def api_indicador_criar():
    data = request.get_json() or {}
    usuario = session.get('d_usuario', 'sistema')
    indicador = (data.get('indicador') or '').strip()
    if not indicador:
        return jsonify({'erro': 'indicador é obrigatório'}), 400
    cur = get_cursor()
    # Verifica duplicata antes de inserir
    cur.execute("SELECT id FROM categoricas.c_dgp_indicadores WHERE LOWER(indicador) = LOWER(%s)", (indicador,))
    row = cur.fetchone()
    if row:
        return jsonify({'erro': 'Indicador já existe', 'id': row['id']}), 409
    cur.execute(
        "INSERT INTO categoricas.c_dgp_indicadores (indicador, descricao, observacao, criado_por) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (indicador, data.get('descricao') or None, data.get('observacao') or None, usuario)
    )
    novo_id = cur.fetchone()['id']
    get_db().commit()
    return jsonify({'sucesso': True, 'id': novo_id}), 201


@parcerias_metas_bp.route("/api/indicadores/<int:ind_id>", methods=["PUT"])
@login_required
@requires_access('parcerias_metas')
def api_indicador_editar(ind_id):
    data = request.get_json() or {}
    usuario = session.get('d_usuario', 'sistema')
    indicador = (data.get('indicador') or '').strip()
    if not indicador:
        return jsonify({'erro': 'indicador é obrigatório'}), 400
    cur = get_cursor()
    cur.execute("""
        UPDATE categoricas.c_dgp_indicadores
        SET indicador = %s, descricao = %s, observacao = %s, atualizado_por = %s
        WHERE id = %s
    """, (indicador, data.get('descricao') or None, data.get('observacao') or None, usuario, ind_id))
    get_db().commit()
    return jsonify({'sucesso': True})


@parcerias_metas_bp.route("/api/indicadores/<int:ind_id>", methods=["DELETE"])
@login_required
@requires_access('parcerias_metas')
def api_indicador_excluir(ind_id):
    cur = get_cursor()
    cur.execute("DELETE FROM categoricas.c_dgp_indicadores WHERE id = %s", (ind_id,))
    get_db().commit()
    return jsonify({'sucesso': True})


# ── API: Meios de Aferição (retroalimentação + dicionário) ────────────────────

@parcerias_metas_bp.route("/api/meios-afericao", methods=["GET"])
@login_required
def api_meios():
    cur = get_cursor()
    cur.execute("SELECT id, meios_afericao, descricao FROM categoricas.c_dgp_meios_afericao ORDER BY meios_afericao")
    return jsonify([dict(r) for r in cur.fetchall()])


@parcerias_metas_bp.route("/api/meios-afericao", methods=["POST"])
@login_required
@requires_access('parcerias_metas')
def api_meio_criar():
    data = request.get_json() or {}
    usuario = session.get('d_usuario', 'sistema')
    meios_afericao = (data.get('meios_afericao') or '').strip()
    if not meios_afericao:
        return jsonify({'erro': 'meios_afericao é obrigatório'}), 400
    cur = get_cursor()
    cur.execute("SELECT id FROM categoricas.c_dgp_meios_afericao WHERE LOWER(meios_afericao) = LOWER(%s)", (meios_afericao,))
    row = cur.fetchone()
    if row:
        return jsonify({'erro': 'Meio de aferição já existe', 'id': row['id']}), 409
    cur.execute(
        "INSERT INTO categoricas.c_dgp_meios_afericao (meios_afericao, descricao, observacao, criado_por) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (meios_afericao, data.get('descricao') or None, data.get('observacao') or None, usuario)
    )
    novo_id = cur.fetchone()['id']
    get_db().commit()
    return jsonify({'sucesso': True, 'id': novo_id}), 201


@parcerias_metas_bp.route("/api/meios-afericao/<int:meio_id>", methods=["PUT"])
@login_required
@requires_access('parcerias_metas')
def api_meio_editar(meio_id):
    data = request.get_json() or {}
    usuario = session.get('d_usuario', 'sistema')
    meios_afericao = (data.get('meios_afericao') or '').strip()
    if not meios_afericao:
        return jsonify({'erro': 'meios_afericao é obrigatório'}), 400
    cur = get_cursor()
    cur.execute("""
        UPDATE categoricas.c_dgp_meios_afericao
        SET meios_afericao = %s, descricao = %s, observacao = %s, atualizado_por = %s
        WHERE id = %s
    """, (meios_afericao, data.get('descricao') or None, data.get('observacao') or None, usuario, meio_id))
    get_db().commit()
    return jsonify({'sucesso': True})


@parcerias_metas_bp.route("/api/meios-afericao/<int:meio_id>", methods=["DELETE"])
@login_required
@requires_access('parcerias_metas')
def api_meio_excluir(meio_id):
    cur = get_cursor()
    cur.execute("DELETE FROM categoricas.c_dgp_meios_afericao WHERE id = %s", (meio_id,))
    get_db().commit()
    return jsonify({'sucesso': True})


# ── Criar ─────────────────────────────────────────────────────────────────────

@parcerias_metas_bp.route("/criar", methods=["POST"])
@login_required
@requires_access('parcerias_metas')
def criar():
    data = request.get_json() or {}
    usuario = session.get('d_usuario', 'sistema')

    sei_numero = (data.get('sei_numero') or '').strip()
    meta_titulo = (data.get('meta_titulo') or '').strip()
    if not sei_numero or not meta_titulo:
        return jsonify({'erro': 'sei_numero e meta_titulo são obrigatórios'}), 400

    # NI flags
    tipos_ni       = bool(data.get('tipos_ni'))
    indicadores_ni = bool(data.get('indicadores_ni'))
    meios_ni       = bool(data.get('meios_ni'))

    meta_tipo_ids = []
    if not tipos_ni:
        raw = data.get('meta_tipo_ids') or []
        if isinstance(raw, list):
            meta_tipo_ids = [int(i) for i in raw if str(i).strip().isdigit()]

    # Retroalimentação: resolve listas (ignorar se NI marcado)
    indicadores_ids    = None if indicadores_ni else _resolve_indicadores(data.get('indicadores_textos') or [], usuario)
    meios_afericao_ids = None if meios_ni       else _resolve_meios(data.get('meios_textos') or [], usuario)

    # Obs paralelas por indicador
    obs_indicadores = data.get('obs_indicadores') or []
    obs_indicadores = [str(o) if o else '' for o in obs_indicadores] or None

    cur = get_cursor()
    # Ordem automática: próximo número para este SEI
    cur.execute(
        "SELECT COALESCE(MAX(ordem), 0) + 1 AS prox_ordem FROM celebracao.celebracao_metas WHERE sei_numero = %s",
        (sei_numero,)
    )
    ordem = cur.fetchone()['prox_ordem']

    cur.execute("""
        INSERT INTO celebracao.celebracao_metas
            (sei_numero, meta_titulo, meta_descricao, meta_objetivo,
             meta_tipo_ids, tipos_ni, indicadores_ids, indicadores_ni,
             meta_obs_indicadores, meios_afericao_ids, meios_ni,
             observacoes, ordem, criado_por)
        VALUES (%s, %s, %s, %s, %s::INTEGER[], %s, %s::INTEGER[], %s, %s::TEXT[], %s::INTEGER[], %s, %s, %s, %s)
        RETURNING id
    """, (
        sei_numero,
        meta_titulo,
        data.get('meta_descricao') or None,
        data.get('meta_objetivo') or None,
        meta_tipo_ids if meta_tipo_ids else None,
        tipos_ni,
        indicadores_ids,
        indicadores_ni,
        obs_indicadores,
        meios_afericao_ids,
        meios_ni,
        data.get('observacoes') or None,
        ordem,
        usuario,
    ))
    novo_id = cur.fetchone()['id']
    get_db().commit()

    return jsonify({'sucesso': True, 'id': novo_id}), 201


# ── Editar ────────────────────────────────────────────────────────────────────

@parcerias_metas_bp.route("/editar/<int:meta_id>", methods=["PUT"])
@login_required
@requires_access('parcerias_metas')
def editar(meta_id):
    data = request.get_json() or {}
    usuario = session.get('d_usuario', 'sistema')

    meta_titulo = (data.get('meta_titulo') or '').strip()
    if not meta_titulo:
        return jsonify({'erro': 'meta_titulo é obrigatório'}), 400

    tipos_ni       = bool(data.get('tipos_ni'))
    indicadores_ni = bool(data.get('indicadores_ni'))
    meios_ni       = bool(data.get('meios_ni'))

    meta_tipo_ids = []
    if not tipos_ni:
        raw = data.get('meta_tipo_ids') or []
        if isinstance(raw, list):
            meta_tipo_ids = [int(i) for i in raw if str(i).strip().isdigit()]

    indicadores_ids    = None if indicadores_ni else _resolve_indicadores(data.get('indicadores_textos') or [], usuario)
    meios_afericao_ids = None if meios_ni       else _resolve_meios(data.get('meios_textos') or [], usuario)

    obs_indicadores = data.get('obs_indicadores') or []
    obs_indicadores = [str(o) if o else '' for o in obs_indicadores] or None

    ordem = int(data.get('ordem') or 0)

    cur = get_cursor()
    cur.execute("""
        UPDATE celebracao.celebracao_metas SET
            sei_numero            = %s,
            meta_titulo           = %s,
            meta_descricao        = %s,
            meta_objetivo         = %s,
            meta_tipo_ids         = %s::INTEGER[],
            tipos_ni              = %s,
            indicadores_ids       = %s::INTEGER[],
            indicadores_ni        = %s,
            meta_obs_indicadores  = %s::TEXT[],
            meios_afericao_ids    = %s::INTEGER[],
            meios_ni              = %s,
            observacoes           = %s,
            ordem                 = %s,
            atualizado_por        = %s,
            atualizado_em         = NOW()
        WHERE id = %s
    """, (
        (data.get('sei_numero') or '').strip(),
        meta_titulo,
        data.get('meta_descricao') or None,
        data.get('meta_objetivo') or None,
        meta_tipo_ids if meta_tipo_ids else None,
        tipos_ni,
        indicadores_ids,
        indicadores_ni,
        obs_indicadores,
        meios_afericao_ids,
        meios_ni,
        data.get('observacoes') or None,
        ordem,
        usuario,
        meta_id,
    ))
    get_db().commit()

    return jsonify({'sucesso': True})


# ── Excluir ───────────────────────────────────────────────────────────────────

@parcerias_metas_bp.route("/excluir/<int:meta_id>", methods=["DELETE"])
@login_required
@requires_access('parcerias_metas')
def excluir(meta_id):
    cur = get_cursor()
    cur.execute("DELETE FROM celebracao.celebracao_metas WHERE id = %s", (meta_id,))
    get_db().commit()
    return jsonify({'sucesso': True})


# ── Exportar CSV ──────────────────────────────────────────────────────────────

@parcerias_metas_bp.route("/exportar-csv", methods=["GET"])
@login_required
@requires_access('parcerias_metas')
def exportar_csv():
    cur = get_cursor()
    filtro_sei = request.args.get('filtro_sei', '').strip()

    where_clause = ""
    params = []
    if filtro_sei:
        where_clause = "WHERE cm.sei_numero ILIKE %s"
        params.append(f"%{filtro_sei}%")

    cur.execute(f"""
        SELECT
            cm.sei_numero,
            COALESCE(p.numero_termo, cp.numero_termo, '-') AS numero_termo,
            COALESCE(p.osc, cp.osc, '-')                   AS osc,
            cm.ordem,
            cm.meta_titulo,
            cm.meta_descricao,
            cm.meta_objetivo,
            COALESCE(
                (SELECT STRING_AGG(mt.meta_tipo || ' (' || COALESCE(mt.tipo_classificacao,'') || ')', ' | '
                                   ORDER BY mt.tipo_classificacao, mt.meta_tipo)
                 FROM categoricas.c_dgp_meta_tipos mt
                 WHERE mt.id = ANY(cm.meta_tipo_ids)),
                ''
            ) AS tipos_labels,
            COALESCE(
                (SELECT STRING_AGG(ind.indicador, ' | ' ORDER BY ind.indicador)
                 FROM categoricas.c_dgp_indicadores ind
                 WHERE ind.id = ANY(cm.indicadores_ids)),
                ''
            ) AS indicador,
            cm.meta_obs_indicadores,
            COALESCE(
                (SELECT STRING_AGG(ma.meios_afericao, ' | ' ORDER BY ma.meios_afericao)
                 FROM categoricas.c_dgp_meios_afericao ma
                 WHERE ma.id = ANY(cm.meios_afericao_ids)),
                ''
            ) AS meios_afericao,
            cm.observacoes,
            cm.criado_por,
            cm.criado_em,
            cm.atualizado_por,
            cm.atualizado_em
        FROM celebracao.celebracao_metas cm
        LEFT JOIN public.parcerias p ON p.sei_celeb = cm.sei_numero
        LEFT JOIN celebracao.celebracao_parcerias cp ON cp.sei_celeb = cm.sei_numero
        {where_clause}
        ORDER BY cm.sei_numero, cm.ordem, cm.id
    """, params)
    rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
    writer.writerow([
        'SEI', 'Número de Termo', 'OSC', 'Ordem', 'Título', 'Descrição', 'Objetivo',
        'Tipos de Meta', 'Indicador', 'Obs. Indicador',
        'Meios de Aferição', 'Observações',
        'Criado Por', 'Criado Em', 'Atualizado Por', 'Atualizado Em'
    ])
    for r in rows:
        writer.writerow([
            r['sei_numero'], r['numero_termo'], r['osc'],
            r['ordem'], r['meta_titulo'],
            r['meta_descricao'] or '', r['meta_objetivo'] or '',
            r['tipos_labels'] or '', r['indicador'] or '',
            ' | '.join(r['meta_obs_indicadores'] or []) or '', r['meios_afericao'] or '',
            r['observacoes'] or '',
            r['criado_por'] or '',
            r['criado_em'].strftime('%d/%m/%Y %H:%M') if r['criado_em'] else '',
            r['atualizado_por'] or '',
            r['atualizado_em'].strftime('%d/%m/%Y %H:%M') if r['atualizado_em'] else '',
        ])

    output.seek(0)
    filename = f"quadro_metas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
