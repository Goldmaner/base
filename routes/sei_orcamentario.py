"""
Gerenciamento de SEI Orçamentário
Vinculado às tabelas:
 - celebracao.celebracao_emendas  (registro principal)
 - public.parcerias_emendas        (vereador / valor / info)
 - categoricas.c_geral_vereadores  (lista de vereadores)
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_db
from utils import login_required
import traceback
from datetime import date

sei_orcamentario_bp = Blueprint(
    'sei_orcamentario',
    __name__,
    url_prefix='/sei-orcamentario'
)

DISPONIBILIDADE_OPTS = [
    'Não Informado',
    'Emenda Disponível',
    'Valor não Disponível',
    'Exercício Orçamentário Encerrado',
]

EMENDA_STATUS_OPTS = [
    'Aguardando aceite',
    'Não aceita',
    'Aceita',
    'Processo vinculado',
]


# ── Página principal ──────────────────────────────────────────────────────
@sei_orcamentario_bp.route('/', methods=['GET'])
@login_required
def index():
    db = get_db()
    cur = db.cursor()

    # Filtros
    f_sei_orc    = request.args.get('filtro_sei_orc', '').strip()
    f_sei_celeb  = request.args.get('filtro_sei_celeb', '').strip()
    f_projeto    = request.args.get('filtro_projeto', '').strip()
    f_memorando  = request.args.get('filtro_memorando', '').strip()
    f_consulta   = request.args.get('filtro_consulta', '').strip()
    f_disp       = request.args.get('filtro_disp', '').strip()
    f_vereador   = request.args.get('filtro_vereador', '').strip()
    f_valor_min  = request.args.get('filtro_valor_min', '').strip()
    f_valor_max  = request.args.get('filtro_valor_max', '').strip()
    f_status     = request.args.get('filtro_status', '').strip()

    conds = []
    params = []

    if f_sei_orc:
        conds.append("ce.sei_orcamentario ILIKE %s")
        params.append(f'%{f_sei_orc}%')
    if f_sei_celeb:
        conds.append("ce.sei_celeb ILIKE %s")
        params.append(f'%{f_sei_celeb}%')
    if f_projeto:
        conds.append("unaccent(ce.projeto) ILIKE unaccent(%s)")
        params.append(f'%{f_projeto}%')
    if f_memorando:
        conds.append("ce.numero_memorando::text ILIKE %s")
        params.append(f'%{f_memorando}%')
    if f_consulta:
        conds.append("ce.numero_consulta::text ILIKE %s")
        params.append(f'%{f_consulta}%')
    if f_disp:
        conds.append("ce.disponibilidade_orcamentaria = %s")
        params.append(f_disp)
    if f_vereador:
        conds.append("unaccent(pe.vereador_nome) ILIKE unaccent(%s)")
        params.append(f'%{f_vereador}%')
    if f_valor_min:
        try:
            conds.append("pe.valor >= %s")
            params.append(float(f_valor_min.replace('.', '').replace(',', '.')))
        except ValueError:
            pass
    if f_valor_max:
        try:
            conds.append("pe.valor <= %s")
            params.append(float(f_valor_max.replace('.', '').replace(',', '.')))
        except ValueError:
            pass
    if f_status:
        conds.append("ce.status = %s")
        params.append(f_status)

    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''

    cur.execute(f"""
        SELECT
            ce.id,
            ce.sei_orcamentario,
            ce.sei_celeb,
            ce.projeto,
            ce.numero_memorando,
            ce.numero_consulta,
            ce.disponibilidade_orcamentaria,
            ce.status        AS ce_status,
            ce.created_at,
            ce.criado_por,
            pe.id            AS pe_id,
            pe.vereador_nome,
            pe.valor,
            pe.observacoes,
            pe.status        AS pe_status
        FROM celebracao.celebracao_emendas ce
        LEFT JOIN public.parcerias_emendas pe
               ON ce.sei_celeb = pe.sei_celeb
              AND pe.id = (
                    SELECT id FROM public.parcerias_emendas
                     WHERE sei_celeb = ce.sei_celeb
                     ORDER BY criado_em DESC NULLS LAST
                     LIMIT 1
                  )
        {where}
        ORDER BY ce.created_at DESC NULLS LAST
    """, params)
    registros = cur.fetchall()
    cols = [d[0] for d in cur.description]
    registros = [dict(zip(cols, row)) for row in registros]

    # Serialização segura para JSON
    for r in registros:
        for k, v in r.items():
            if hasattr(v, 'isoformat'):
                r[k] = v.isoformat()
            elif v is None:
                r[k] = None

    # Lista de vereadores com legislatura vigente
    hoje = date.today()
    cur.execute("""
        SELECT vereador_nome
        FROM categoricas.c_geral_vereadores
        WHERE legislatura_inicio <= %s AND legislatura_fim >= %s
        ORDER BY vereador_nome
    """, (hoje, hoje))
    vereadores = [row[0] for row in cur.fetchall()]

    return render_template(
        'sei_orcamentario.html',
        registros=registros,
        vereadores=vereadores,
        disponibilidade_opts=DISPONIBILIDADE_OPTS,
        emenda_status_opts=EMENDA_STATUS_OPTS,
        # filtros aktivos
        filtro_sei_orc=f_sei_orc,
        filtro_sei_celeb=f_sei_celeb,
        filtro_projeto=f_projeto,
        filtro_memorando=f_memorando,
        filtro_consulta=f_consulta,
        filtro_disp=f_disp,
        filtro_vereador=f_vereador,
        filtro_valor_min=f_valor_min,
        filtro_valor_max=f_valor_max,
        filtro_status=f_status,
        is_admin=session.get('is_admin', False),
    )


# ── API: próximo número de memorando ──────────────────────────────────
@sei_orcamentario_bp.route('/api/proximo-memorando', methods=['GET'])
@login_required
def api_proximo_memorando():
    sei_celeb = request.args.get('sei_celeb', '').strip()
    db = get_db()
    cur = db.cursor()
    # Se sei_celeb fornecido e já existir um registro com ele, reusar mesmo memorando
    if sei_celeb and sei_celeb not in ('-', 'A ser criado'):
        cur.execute("""
            SELECT numero_memorando FROM celebracao.celebracao_emendas
            WHERE sei_celeb = %s AND numero_memorando IS NOT NULL
            ORDER BY id ASC LIMIT 1
        """, [sei_celeb])
        row = cur.fetchone()
        if row and row[0] is not None:
            return jsonify(success=True, numero=int(row[0]), fonte='sei_celeb')
    # Próximo = MAX + 1
    cur.execute("SELECT COALESCE(MAX(numero_memorando), 0) + 1 AS proximo FROM celebracao.celebracao_emendas")
    row = cur.fetchone()
    return jsonify(success=True, numero=int(row[0]) if row else 1, fonte='maximo')


# ── Criar novo registro ───────────────────────────────────────────────────
@sei_orcamentario_bp.route('/criar', methods=['POST'])
@login_required
def criar():
    db = get_db()
    cur = db.cursor()
    d = request.get_json(force=True)

    sei_orc    = (d.get('sei_orcamentario') or '').strip()
    sei_celeb  = (d.get('sei_celeb') or '').strip()
    projeto    = (d.get('projeto') or '').strip() or None
    memorando  = d.get('numero_memorando') or None
    consulta   = d.get('numero_consulta') or None
    disp       = (d.get('disponibilidade_orcamentaria') or 'Não Informado').strip()
    ce_status  = (d.get('ce_status') or 'Aguardando aceite').strip()
    vereador   = (d.get('vereador_nome') or '').strip() or None
    valor_raw  = (d.get('valor') or '').strip()
    obs        = (d.get('observacoes') or '').strip() or None
    pe_status  = (d.get('pe_status') or 'Em celebração').strip()
    usuario    = session.get('d_usuario', 'sistema')

    if not sei_orc:
        return jsonify(success=False, erro='SEI Orçamentário é obrigatório.')

    # Converter valor
    valor = None
    if valor_raw:
        try:
            valor = float(valor_raw.replace('.', '').replace(',', '.'))
        except ValueError:
            return jsonify(success=False, erro='Valor inválido.')

    # Converter inteiros
    try:
        memorando = int(memorando) if memorando not in (None, '') else None
    except (ValueError, TypeError):
        memorando = None
    try:
        consulta = int(consulta) if consulta not in (None, '') else None
    except (ValueError, TypeError):
        consulta = None

    # Vínculo primário: sei_celeb; secundário: projeto gravado em observacoes
    sei_eff = sei_celeb if sei_celeb and sei_celeb != '-' else None
    if not sei_eff and projeto:
        obs = projeto  # gravar projeto como chave secundária em observacoes

    try:
        cur.execute("""
            INSERT INTO celebracao.celebracao_emendas
                (sei_orcamentario, sei_celeb, projeto, numero_memorando,
                 numero_consulta, disponibilidade_orcamentaria, status, criado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (sei_orc, sei_eff, projeto, memorando, consulta, disp, ce_status, usuario))
        new_id = cur.fetchone()[0]

        # Salvar em parcerias_emendas: pelo sei_celeb (primário) ou pelo projeto (secundário)
        if sei_eff or projeto:
            cur.execute("""
                INSERT INTO public.parcerias_emendas
                    (sei_celeb, vereador_nome, valor, observacoes, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (sei_eff, vereador, valor, obs, pe_status))

        db.commit()
        return jsonify(success=True, id=new_id, mensagem=f'SEI Orçamentário {sei_orc} criado com sucesso.')
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        return jsonify(success=False, erro=str(e))


# ── Editar registro ───────────────────────────────────────────────────────
@sei_orcamentario_bp.route('/editar/<int:id>', methods=['PUT'])
@login_required
def editar(id):
    db = get_db()
    cur = db.cursor()
    d = request.get_json(force=True)

    sei_orc   = (d.get('sei_orcamentario') or '').strip()
    sei_celeb = (d.get('sei_celeb') or '').strip() or None
    projeto   = (d.get('projeto') or '').strip() or None
    memorando = d.get('numero_memorando') or None
    consulta  = d.get('numero_consulta') or None
    disp      = (d.get('disponibilidade_orcamentaria') or 'Não Informado').strip()
    ce_status = (d.get('ce_status') or 'Aguardando aceite').strip()

    if not sei_orc:
        return jsonify(success=False, erro='SEI Orçamentário é obrigatório.')

    try:
        memorando = int(memorando) if memorando not in (None, '') else None
    except (ValueError, TypeError):
        memorando = None
    try:
        consulta = int(consulta) if consulta not in (None, '') else None
    except (ValueError, TypeError):
        consulta = None

    sei_eff = sei_celeb if sei_celeb and sei_celeb != '-' else None

    try:
        # Buscar valores antigos para sincronizar vínculo secundário
        cur.execute("SELECT sei_celeb, projeto FROM celebracao.celebracao_emendas WHERE id = %s", [id])
        old = cur.fetchone()
        old_sei     = (old[0] or '').strip() if old else ''
        old_projeto = (old[1] or '').strip() if old else ''

        cur.execute("""
            UPDATE celebracao.celebracao_emendas
               SET sei_orcamentario         = %s,
                   sei_celeb                = %s,
                   projeto                  = %s,
                   numero_memorando         = %s,
                   numero_consulta          = %s,
                   disponibilidade_orcamentaria = %s,
                   status                   = %s
             WHERE id = %s
        """, (sei_orc, sei_eff, projeto, memorando, consulta, disp, ce_status, id))

        # Sincronizar vínculo secundário em parcerias_emendas
        if not sei_eff and projeto:
            if old_sei:
                cur.execute(
                    "UPDATE public.parcerias_emendas SET observacoes = %s WHERE sei_celeb = %s",
                    [projeto, old_sei])
            if old_projeto and old_projeto != projeto:
                cur.execute(
                    "UPDATE public.parcerias_emendas SET observacoes = %s WHERE observacoes = %s",
                    [projeto, old_projeto])

        db.commit()
        return jsonify(success=True, mensagem='Registro atualizado com sucesso.')
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        return jsonify(success=False, erro=str(e))


# ── Excluir registro ──────────────────────────────────────────────────────
@sei_orcamentario_bp.route('/excluir/<int:id>', methods=['DELETE'])
@login_required
def excluir(id):
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("DELETE FROM celebracao.celebracao_emendas WHERE id = %s", (id,))
        db.commit()
        return jsonify(success=True, mensagem='Registro excluído.')
    except Exception as e:
        db.rollback()
        return jsonify(success=False, erro=str(e))
