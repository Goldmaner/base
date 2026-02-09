"""
Blueprint de Gerenciamento e Análise dos CENTS
Gestão de Certificados de Entidades (CENTS) por OSC
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access
from datetime import datetime

cents_bp = Blueprint('cents', __name__, url_prefix='/cents')


@cents_bp.route("/", methods=["GET"])
@login_required
@requires_access('cents')
def index():
    """
    Página principal do Gerenciamento e Análise dos CENTS
    Exibe tabela paginada com filtros
    """
    cur = get_cursor()

    # ── Parâmetros de paginação ──
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if per_page not in (10, 20, 50, 100):
        per_page = 20
    offset = (page - 1) * per_page

    # ── Parâmetros de filtro ──
    filtro_osc = request.args.get('filtro_osc', '').strip()
    filtro_cnpj = request.args.get('filtro_cnpj', '').strip()
    filtro_sei = request.args.get('filtro_sei', '').strip()
    filtro_responsavel = request.args.get('filtro_responsavel', '').strip()
    filtro_status = request.args.get('filtro_status', '').strip()
    filtro_prioridade = request.args.get('filtro_prioridade', '').strip()

    # ── Construir WHERE dinâmico ──
    conditions = []
    params = []

    if filtro_osc:
        conditions.append("unaccent(LOWER(g.osc)) LIKE unaccent(LOWER(%s))")
        params.append(f"%{filtro_osc}%")
    if filtro_cnpj:
        conditions.append("g.osc_cnpj LIKE %s")
        params.append(f"%{filtro_cnpj}%")
    if filtro_sei:
        conditions.append("g.cents_sei LIKE %s")
        params.append(f"%{filtro_sei}%")
    if filtro_responsavel:
        conditions.append("unaccent(LOWER(g.cents_responsavel)) LIKE unaccent(LOWER(%s))")
        params.append(f"%{filtro_responsavel}%")
    if filtro_status:
        conditions.append("g.cents_status = %s")
        params.append(filtro_status)
    if filtro_prioridade:
        conditions.append("g.cents_prioridade = %s")
        params.append(filtro_prioridade)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # ── Contar total (para paginação) ──
    cur.execute(
        f"SELECT COUNT(*) as total FROM celebracao.gestao_cents g {where_clause}",
        params
    )
    total = cur.fetchone()['total']
    total_pages = max(1, -(-total // per_page))  # ceil division

    # ── Buscar registros paginados ──
    cur.execute(f"""
        SELECT g.*
        FROM celebracao.gestao_cents g
        {where_clause}
        ORDER BY g.id DESC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    registros = cur.fetchall()

    # ── Buscar listas para selects do formulário ──
    # OSCs (de public.parcerias)
    cur.execute("""
        SELECT DISTINCT osc, cnpj
        FROM public.parcerias
        WHERE osc IS NOT NULL AND osc != ''
        ORDER BY osc
    """)
    oscs_list = cur.fetchall()

    # Responsáveis (todos os analistas)
    cur.execute("""
        SELECT nome_analista, status
        FROM categoricas.c_dgp_analistas
        ORDER BY nome_analista
    """)
    responsaveis = cur.fetchall()

    # Status de CENTS (todos - necessário para edição de registros antigos)
    cur.execute("""
        SELECT cents_status
        FROM categoricas.c_dgp_cents_status
        ORDER BY cents_status
    """)
    status_list = [r['cents_status'] for r in cur.fetchall()]

    return render_template(
        'cents.html',
        registros=registros,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        filtro_osc=filtro_osc,
        filtro_cnpj=filtro_cnpj,
        filtro_sei=filtro_sei,
        filtro_responsavel=filtro_responsavel,
        filtro_status=filtro_status,
        filtro_prioridade=filtro_prioridade,
        oscs_list=oscs_list,
        responsaveis=responsaveis,
        status_list=status_list
    )


@cents_bp.route("/adicionar", methods=["POST"])
@login_required
@requires_access('cents')
def adicionar():
    """Adicionar novo registro de CENTS"""
    cur = get_cursor()
    db = get_db()

    try:
        osc = request.form.get('osc', '').strip()
        osc_cnpj = request.form.get('osc_cnpj', '').strip()
        cents_sei = request.form.get('cents_sei', '').strip()
        cents_responsavel = request.form.get('cents_responsavel', '').strip()
        cents_status = request.form.get('cents_status', '').strip()

        # Validação dos campos obrigatórios
        erros = []
        if not osc:
            erros.append('OSC é obrigatório')
        if not osc_cnpj:
            erros.append('CNPJ é obrigatório')
        if not cents_responsavel:
            erros.append('Responsável é obrigatório')
        if not cents_status:
            erros.append('Status é obrigatório')

        if erros:
            return jsonify({'success': False, 'erro': '; '.join(erros)}), 400

        # Campos opcionais
        cents_sei = cents_sei or None  # Permitir vazio
        cents_requerimento = request.form.get('cents_requerimento', '').strip() or None
        cents_ultima_not = request.form.get('cents_ultima_not', '').strip() or None
        cents_publicacao = request.form.get('cents_publicacao', '').strip() or None
        cents_vencimento = request.form.get('cents_vencimento', '').strip() or None
        cents_prioridade = request.form.get('cents_prioridade', '').strip() or None
        observacoes = request.form.get('observacoes', '').strip() or None

        cur.execute("""
            INSERT INTO celebracao.gestao_cents
                (osc, osc_cnpj, cents_sei, cents_responsavel,
                 cents_requerimento, cents_ultima_not, cents_publicacao,
                 cents_vencimento, cents_status, cents_prioridade, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, [
            osc, osc_cnpj, cents_sei, cents_responsavel,
            cents_requerimento, cents_ultima_not, cents_publicacao,
            cents_vencimento, cents_status, cents_prioridade, observacoes
        ])

        novo_id = cur.fetchone()['id']
        db.commit()

        print(f"[CENTS] Novo registro #{novo_id} criado por {session.get('email')}")
        return jsonify({'success': True, 'id': novo_id, 'mensagem': 'CENTS adicionado com sucesso!'})

    except Exception as e:
        db.rollback()
        print(f"[ERRO CENTS] Erro ao adicionar: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500


@cents_bp.route("/editar/<int:id>", methods=["GET"])
@login_required
@requires_access('cents')
def obter(id):
    """Obter dados de um registro para edição"""
    cur = get_cursor()

    cur.execute("SELECT * FROM celebracao.gestao_cents WHERE id = %s", [id])
    registro = cur.fetchone()

    if not registro:
        return jsonify({'success': False, 'erro': 'Registro não encontrado'}), 404

    # Converter datas para string ISO
    dados = dict(registro)
    for campo in ['cents_requerimento', 'cents_ultima_not', 'cents_publicacao', 'cents_vencimento']:
        if dados.get(campo):
            dados[campo] = dados[campo].isoformat()
    if dados.get('created_em'):
        dados['created_em'] = dados['created_em'].isoformat()

    return jsonify({'success': True, 'registro': dados})


@cents_bp.route("/editar/<int:id>", methods=["PUT"])
@login_required
@requires_access('cents')
def editar(id):
    """Atualizar registro de CENTS"""
    cur = get_cursor()
    db = get_db()

    try:
        data = request.get_json()

        osc = data.get('osc', '').strip()
        osc_cnpj = data.get('osc_cnpj', '').strip()
        cents_sei = data.get('cents_sei', '').strip()
        cents_responsavel = data.get('cents_responsavel', '').strip()
        cents_status = data.get('cents_status', '').strip()

        # Validação dos campos obrigatórios
        erros = []
        if not osc:
            erros.append('OSC é obrigatório')
        if not osc_cnpj:
            erros.append('CNPJ é obrigatório')
        if not cents_responsavel:
            erros.append('Responsável é obrigatório')
        if not cents_status:
            erros.append('Status é obrigatório')

        if erros:
            return jsonify({'success': False, 'erro': '; '.join(erros)}), 400

        # Campos opcionais
        cents_sei = cents_sei or None  # Permitir vazio
        cents_requerimento = data.get('cents_requerimento', '').strip() or None
        cents_ultima_not = data.get('cents_ultima_not', '').strip() or None
        cents_publicacao = data.get('cents_publicacao', '').strip() or None
        cents_vencimento = data.get('cents_vencimento', '').strip() or None
        cents_prioridade = data.get('cents_prioridade', '').strip() or None
        observacoes = data.get('observacoes', '').strip() or None

        cur.execute("""
            UPDATE celebracao.gestao_cents
            SET osc = %s,
                osc_cnpj = %s,
                cents_sei = %s,
                cents_responsavel = %s,
                cents_requerimento = %s,
                cents_ultima_not = %s,
                cents_publicacao = %s,
                cents_vencimento = %s,
                cents_status = %s,
                cents_prioridade = %s,
                observacoes = %s
            WHERE id = %s
        """, [
            osc, osc_cnpj, cents_sei, cents_responsavel,
            cents_requerimento, cents_ultima_not, cents_publicacao,
            cents_vencimento, cents_status, cents_prioridade, observacoes,
            id
        ])

        if cur.rowcount == 0:
            return jsonify({'success': False, 'erro': 'Registro não encontrado'}), 404

        db.commit()

        print(f"[CENTS] Registro #{id} atualizado por {session.get('email')}")
        return jsonify({'success': True, 'mensagem': 'CENTS atualizado com sucesso!'})

    except Exception as e:
        db.rollback()
        print(f"[ERRO CENTS] Erro ao editar #{id}: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500
