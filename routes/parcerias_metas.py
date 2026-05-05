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
from db import get_cursor
from utils import login_required
from decorators import requires_access

parcerias_metas_bp = Blueprint(
    'parcerias_metas', __name__, url_prefix='/parcerias-metas'
)


# ── Rota principal ────────────────────────────────────────────────────────────

@parcerias_metas_bp.route("/", methods=["GET"])
@login_required
@requires_access('parcerias_metas')
def index():
    cur = get_cursor()

    filtro_sei = request.args.get('filtro_sei', '').strip()

    # Carrega dados do catálogo para exibição na página
    cur.execute("""
        SELECT id, meta_tipo, tipo_classificacao
        FROM categoricas.c_dgp_meta_tipos
        ORDER BY tipo_classificacao, meta_tipo
    """)
    meta_tipos = cur.fetchall()

    cur.execute("""
        SELECT id, indicador FROM categoricas.c_dgp_indicadores
        ORDER BY indicador
    """)
    indicadores = cur.fetchall()

    cur.execute("""
        SELECT id, meios_afericao FROM categoricas.c_dgp_meios_afericao
        ORDER BY meios_afericao
    """)
    meios_afericao = cur.fetchall()

    # Query principal com JOINs para labels
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
            cm.indicadores_id,
            ind.indicador         AS indicador_label,
            cm.meta_obs_indicador,
            cm.meios_afericao_id,
            ma.meios_afericao     AS meios_afericao_label,
            cm.observacoes,
            cm.ordem,
            cm.criado_por,
            cm.criado_em,
            cm.atualizado_por,
            cm.atualizado_em
        FROM celebracao.celebracao_metas cm
        LEFT JOIN categoricas.c_dgp_indicadores ind
            ON ind.id = cm.indicadores_id
        LEFT JOIN categoricas.c_dgp_meios_afericao ma
            ON ma.id = cm.meios_afericao_id
        {where_clause}
        ORDER BY cm.sei_numero, cm.ordem, cm.id
    """, params)
    metas = cur.fetchall()

    # Monta labels de tipos para cada meta (array → lista de dicts)
    tipo_map = {r['id']: r for r in meta_tipos}
    metas_com_tipos = []
    for m in metas:
        row = dict(m)
        ids = row.get('meta_tipo_ids') or []
        row['meta_tipos_labels'] = [
            tipo_map[i] for i in ids if i in tipo_map
        ]
        metas_com_tipos.append(row)

    return render_template(
        'parcerias_metas.html',
        metas=metas_com_tipos,
        meta_tipos=meta_tipos,
        indicadores=indicadores,
        meios_afericao=meios_afericao,
        filtro_sei=filtro_sei,
    )


# ── API: SEI numbers (3 fontes) ───────────────────────────────────────────────

@parcerias_metas_bp.route("/api/sei-numeros", methods=["GET"])
@login_required
def api_sei_numeros():
    cur = get_cursor()
    cur.execute("""
        SELECT sei_celeb AS sei_numero, 'Parceria' AS fonte
          FROM public.parcerias
         WHERE sei_celeb IS NOT NULL AND TRIM(sei_celeb) != ''
        UNION
        SELECT sei_celeb, 'Celebração'
          FROM celebracao.celebracao_parcerias
         WHERE sei_celeb IS NOT NULL AND TRIM(sei_celeb) != ''
        UNION
        SELECT edital_processo_sei, 'Edital'
          FROM public.parcerias_edital
         WHERE edital_processo_sei IS NOT NULL AND TRIM(edital_processo_sei) != ''
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
        SELECT meta_definicao, indicador_definicao, meios_definicoes
        FROM categoricas.c_dgp_plano_definicoes
        ORDER BY id DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        return jsonify(dict(row))
    return jsonify({'meta_definicao': '', 'indicador_definicao': '', 'meios_definicoes': ''})


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

    meta_tipo_ids = data.get('meta_tipo_ids') or []
    if not isinstance(meta_tipo_ids, list):
        meta_tipo_ids = []
    meta_tipo_ids = [int(i) for i in meta_tipo_ids if str(i).strip().isdigit()]

    indicadores_id = data.get('indicadores_id') or None
    meios_afericao_id = data.get('meios_afericao_id') or None
    if indicadores_id:
        indicadores_id = int(indicadores_id)
    if meios_afericao_id:
        meios_afericao_id = int(meios_afericao_id)

    ordem = int(data.get('ordem') or 0)

    cur = get_cursor()
    cur.execute("""
        INSERT INTO celebracao.celebracao_metas
            (sei_numero, meta_titulo, meta_descricao, meta_objetivo,
             meta_tipo_ids, indicadores_id, meta_obs_indicador,
             meios_afericao_id, observacoes, ordem, criado_por)
        VALUES (%s, %s, %s, %s, %s::INTEGER[], %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        sei_numero,
        meta_titulo,
        data.get('meta_descricao') or None,
        data.get('meta_objetivo') or None,
        meta_tipo_ids if meta_tipo_ids else None,
        indicadores_id,
        data.get('meta_obs_indicador') or None,
        meios_afericao_id,
        data.get('observacoes') or None,
        ordem,
        usuario,
    ))
    novo_id = cur.fetchone()['id']
    from db import get_db
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

    meta_tipo_ids = data.get('meta_tipo_ids') or []
    if not isinstance(meta_tipo_ids, list):
        meta_tipo_ids = []
    meta_tipo_ids = [int(i) for i in meta_tipo_ids if str(i).strip().isdigit()]

    indicadores_id = data.get('indicadores_id') or None
    meios_afericao_id = data.get('meios_afericao_id') or None
    if indicadores_id:
        indicadores_id = int(indicadores_id)
    if meios_afericao_id:
        meios_afericao_id = int(meios_afericao_id)

    ordem = int(data.get('ordem') or 0)

    cur = get_cursor()
    cur.execute("""
        UPDATE celebracao.celebracao_metas SET
            sei_numero         = %s,
            meta_titulo        = %s,
            meta_descricao     = %s,
            meta_objetivo      = %s,
            meta_tipo_ids      = %s::INTEGER[],
            indicadores_id     = %s,
            meta_obs_indicador = %s,
            meios_afericao_id  = %s,
            observacoes        = %s,
            ordem              = %s,
            atualizado_por     = %s,
            atualizado_em      = NOW()
        WHERE id = %s
    """, (
        (data.get('sei_numero') or '').strip(),
        meta_titulo,
        data.get('meta_descricao') or None,
        data.get('meta_objetivo') or None,
        meta_tipo_ids if meta_tipo_ids else None,
        indicadores_id,
        data.get('meta_obs_indicador') or None,
        meios_afericao_id,
        data.get('observacoes') or None,
        ordem,
        usuario,
        meta_id,
    ))
    from db import get_db
    get_db().commit()

    return jsonify({'sucesso': True})


# ── Excluir ───────────────────────────────────────────────────────────────────

@parcerias_metas_bp.route("/excluir/<int:meta_id>", methods=["DELETE"])
@login_required
@requires_access('parcerias_metas')
def excluir(meta_id):
    cur = get_cursor()
    cur.execute("DELETE FROM celebracao.celebracao_metas WHERE id = %s", (meta_id,))
    from db import get_db
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
            ind.indicador         AS indicador,
            cm.meta_obs_indicador,
            ma.meios_afericao     AS meios_afericao,
            cm.observacoes,
            cm.criado_por,
            cm.criado_em,
            cm.atualizado_por,
            cm.atualizado_em
        FROM celebracao.celebracao_metas cm
        LEFT JOIN categoricas.c_dgp_indicadores ind ON ind.id = cm.indicadores_id
        LEFT JOIN categoricas.c_dgp_meios_afericao ma ON ma.id = cm.meios_afericao_id
        {where_clause}
        ORDER BY cm.sei_numero, cm.ordem, cm.id
    """, params)
    rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
    writer.writerow([
        'SEI', 'Ordem', 'Título', 'Descrição', 'Objetivo',
        'Tipos de Meta', 'Indicador', 'Obs. Indicador',
        'Meios de Aferição', 'Observações',
        'Criado Por', 'Criado Em', 'Atualizado Por', 'Atualizado Em'
    ])
    for r in rows:
        writer.writerow([
            r['sei_numero'], r['ordem'], r['meta_titulo'],
            r['meta_descricao'] or '', r['meta_objetivo'] or '',
            r['tipos_labels'] or '', r['indicador'] or '',
            r['meta_obs_indicador'] or '', r['meios_afericao'] or '',
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
