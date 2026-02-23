"""
Blueprint de Celebração de Parcerias
Gerenciamento e acompanhamento de termos de celebração de parcerias com OSCs
"""

import re
import csv
import io
from datetime import datetime
from decimal import Decimal
from flask import (
    Blueprint, render_template, request, jsonify, session,
    Response
)
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access

celebracao_parcerias_bp = Blueprint(
    'celebracao_parcerias', __name__, url_prefix='/celebracao-parcerias'
)


# ── Utilidades ────────────────────────────────────────────────────────────────

def normalizar_rf(rf):
    """
    Normaliza o R.F. para comparação, extraindo apenas os primeiros 6 dígitos.
    Ignora o dígito verificador.
    Exemplos:
        'd843702' -> '843702'
        '843.702-5' -> '843702'
    """
    if not rf:
        return None
    rf_str = str(rf).lower().strip()
    rf_str = re.sub(r'^d', '', rf_str)
    digitos = re.sub(r'[^\d]', '', rf_str)
    return digitos[:6] if len(digitos) >= 6 else digitos


def obter_filtro_usuario(cur):
    """
    Determina se o usuário logado deve ver apenas seus próprios registros.

    Retorna (nome_analista, ver_todos):
      - nome_analista: nome do analista DGP correspondente ao usuário logado
      - ver_todos: True se o analista tem visualizacao_geral ou se não é DGP

    Lógica:
      1. Se tipo_usuario != 'Agente DGP' → ver_todos = True
      2. Se é 'Agente DGP', busca RF normalizado em c_dgp_analistas
      3. Se encontrou e visualizacao_geral = True → ver_todos = True
      4. Caso contrário → filtra por responsavel = nome_analista
    """
    tipo = session.get('tipo_usuario', '')
    if tipo != 'Agente DGP':
        return None, True

    d_usuario = session.get('d_usuario', '')
    rf_norm = normalizar_rf(d_usuario)
    if not rf_norm:
        return None, True

    cur.execute("""
        SELECT nome_analista,
               COALESCE(visualizacao_geral, FALSE) AS visualizacao_geral
        FROM categoricas.c_dgp_analistas
        WHERE REGEXP_REPLACE(LOWER(COALESCE(rf,'')), '[^0-9]', '', 'g')
              LIKE %s || '%%'
          AND status = 'Ativo'
        LIMIT 1
    """, (rf_norm,))
    row = cur.fetchone()

    if not row:
        # Analista não encontrado — mostrar tudo por segurança
        return None, True

    if row['visualizacao_geral']:
        return row['nome_analista'], True

    return row['nome_analista'], False


# ── Definição de filtros ──────────────────────────────────────────────────────

# Cada filtro: (param_name, coluna_sql, tipo)
#   tipo: 'text' → LIKE, 'exact' → =, 'date_from' → >=, 'date_to' → <=
FILTROS = [
    ('filtro_responsavel',    'responsavel',            'text'),
    ('filtro_status',         'status',                 'exact'),
    ('filtro_substatus',      'substatus',              'exact'),
    ('filtro_sei',            'sei_celeb',              'text'),
    ('filtro_tipo_termo',     'tipo_termo',             'exact'),
    ('filtro_osc',            'osc',                    'text'),
    ('filtro_projeto',        'projeto',                'text'),
    ('filtro_unidade',        'unidade_gestora',        'exact'),
    ('filtro_edital',         'edital_nome',            'text'),
    ('filtro_numero_termo',   'numero_termo',           'text'),
    ('filtro_status_generico','status_generico',        'exact'),
]


def construir_where(filtros_vals, nome_analista_filtro=None):
    """
    Constrói cláusula WHERE dinâmica a partir dos valores de filtro.
    Retorna (where_clause, params).
    """
    conditions = []
    params = []

    for param_name, coluna, tipo in FILTROS:
        valor = filtros_vals.get(param_name, '')
        if not valor:
            continue
        if tipo == 'text':
            conditions.append(
                f"unaccent(LOWER(COALESCE({coluna},''))) LIKE unaccent(LOWER(%s))"
            )
            params.append(f"%{valor}%")
        elif tipo == 'exact':
            conditions.append(f"{coluna} = %s")
            params.append(valor)
        elif tipo == 'date_from':
            conditions.append(f"{coluna} >= %s")
            params.append(valor)
        elif tipo == 'date_to':
            conditions.append(f"{coluna} <= %s")
            params.append(valor)

    # Filtro por responsável do usuário logado (se aplicável)
    if nome_analista_filtro:
        conditions.append(
            "unaccent(LOWER(COALESCE(responsavel,''))) = unaccent(LOWER(%s))"
        )
        params.append(nome_analista_filtro)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    return where_clause, params


def ler_filtros_request():
    """Lê todos os valores de filtro do request.args."""
    return {f[0]: request.args.get(f[0], '').strip() for f in FILTROS}


# ── Rota principal ────────────────────────────────────────────────────────────

@celebracao_parcerias_bp.route("/", methods=["GET"])
@login_required
@requires_access('celebracao_parcerias')
def index():
    """
    Página principal: tabela paginada com filtros e controle de visibilidade
    """
    cur = get_cursor()

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if per_page not in (10, 20, 50, 100):
        per_page = 20
    offset = (page - 1) * per_page

    # Filtros do formulário
    filtros_vals = ler_filtros_request()

    # Filtro por usuário
    nome_analista, ver_todos = obter_filtro_usuario(cur)
    nome_filtro_usuario = None if ver_todos else nome_analista

    where_clause, params = construir_where(filtros_vals, nome_filtro_usuario)

    # Contagem
    cur.execute(
        f"SELECT COUNT(*) AS total FROM celebracao.celebracao_parcerias {where_clause}",
        params
    )
    total = cur.fetchone()['total']
    total_pages = max(1, -(-total // per_page))

    # Registros
    cur.execute(f"""
        SELECT *
        FROM celebracao.celebracao_parcerias
        {where_clause}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    registros = cur.fetchall()

    # ── Listas para selects e autocomplete ──
    cur.execute("""
        SELECT nome_analista
        FROM categoricas.c_dgp_analistas
        WHERE status = true
        ORDER BY nome_analista
    """)
    responsaveis = cur.fetchall()

    # Status: ordenado por id, apenas ativos
    cur.execute("""
        SELECT id, status_novo, status_generico
        FROM categoricas.c_dgp_celebracao_status
        WHERE status_status = 'ativo'
        ORDER BY id
    """)
    _status_rows = cur.fetchall()
    status_list = [r['status_novo'] for r in _status_rows]
    status_generico_map = {r['status_novo']: r['status_generico'] for r in _status_rows}
    status_ids = {r['status_novo']: r['id'] for r in _status_rows}

    # Substatus: apenas ativos, com limite e id
    cur.execute("""
        SELECT substatus, substatus_limite
        FROM categoricas.c_dgp_celebracao_substatus
        WHERE substatus_status = 'ativo'
        ORDER BY substatus
    """)
    _sub_rows = cur.fetchall()
    substatus_list = [r['substatus'] for r in _sub_rows]
    substatus_limites = {r['substatus']: r['substatus_limite'] for r in _sub_rows}

    cur.execute("""
        SELECT DISTINCT tipo_termo FROM celebracao.celebracao_parcerias
        WHERE tipo_termo IS NOT NULL AND tipo_termo != ''
        ORDER BY tipo_termo
    """)
    tipo_termo_list = [r['tipo_termo'] for r in cur.fetchall()]

    cur.execute("""
        SELECT DISTINCT unidade_gestora FROM celebracao.celebracao_parcerias
        WHERE unidade_gestora IS NOT NULL AND unidade_gestora != ''
        ORDER BY unidade_gestora
    """)
    unidades_list = [r['unidade_gestora'] for r in cur.fetchall()]

    # Status genérico: para filtro da página (valores distintos existentes nos registros)
    cur.execute("""
        SELECT DISTINCT status_generico FROM categoricas.c_dgp_celebracao_status
        WHERE status_generico IS NOT NULL AND status_generico != ''
        ORDER BY status_generico
    """)
    status_generico_list = [r['status_generico'] for r in cur.fetchall()]

    cur.execute("""
        SELECT edital_nome FROM public.parcerias_edital
        WHERE status = 'Homologado'
          AND edital_nome IS NOT NULL AND edital_nome != ''
        ORDER BY edital_nome
    """)
    editais_list = [r['edital_nome'] for r in cur.fetchall()]

    # Nome PG: pessoas gestoras ativas
    cur.execute("""
        SELECT nome_pg FROM categoricas.c_geral_pessoa_gestora
        WHERE status_pg = 'Ativo'
        ORDER BY nome_pg
    """)
    nome_pg_list = [r['nome_pg'] for r in cur.fetchall()]

    # Lei / legislação aplicável
    cur.execute("""
        SELECT lei FROM categoricas.c_geral_legislacao
        ORDER BY lei
    """)
    lei_list = [r['lei'] for r in cur.fetchall()]

    # Regionalizacao: mapa distrito -> subprefeitura + regiao
    cur.execute("""
        SELECT distrito, subprefeitura, regiao
        FROM categoricas.c_geral_regionalizacao
        ORDER BY distrito
    """)
    regionalizacao_map = {
        r['distrito']: {'subprefeitura': r['subprefeitura'], 'regiao': r['regiao']}
        for r in cur.fetchall()
    }

    # Verificar se é admin
    is_admin = session.get('tipo_usuario') == 'Agente Público'

    return render_template(
        'celebracao_parcerias.html',
        registros=registros,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        responsaveis=responsaveis,
        status_list=status_list,
        status_generico_map=status_generico_map,
        status_ids=status_ids,
        substatus_list=substatus_list,
        substatus_limites=substatus_limites,
        tipo_termo_list=tipo_termo_list,
        unidades_list=unidades_list,
        status_generico_list=status_generico_list,
        editais_list=editais_list,
        nome_pg_list=nome_pg_list,
        lei_list=lei_list,
        regionalizacao_map=regionalizacao_map,
        is_admin=is_admin,
        nome_analista_logado=nome_analista,
        ver_todos=ver_todos,
        **filtros_vals
    )


# ── Exportar CSV ──────────────────────────────────────────────────────────────

@celebracao_parcerias_bp.route("/exportar-csv", methods=["GET"])
@login_required
@requires_access('celebracao_parcerias')
def exportar_csv():
    """Exporta registros filtrados para CSV (UTF-8, delimitador ;)"""
    cur = get_cursor()

    filtros_vals = ler_filtros_request()
    nome_analista, ver_todos = obter_filtro_usuario(cur)
    nome_filtro_usuario = None if ver_todos else nome_analista

    where_clause, params = construir_where(filtros_vals, nome_filtro_usuario)

    cur.execute(f"""
        SELECT id, responsavel, status, substatus, sei_celeb, tipo_termo,
               osc, cnpj, projeto, unidade_gestora, edital_nome,
               total_previsto, numero_termo, numeracao_termo,
               meses, dias, conta, lei,
               inicio, final, assinatura,
               nome_pg, celebracao_secretaria, status_generico,
               endereco_sede, observacoes
        FROM celebracao.celebracao_parcerias
        {where_clause}
        ORDER BY id DESC
    """, params)
    registros = cur.fetchall()

    # Gerar CSV em memória
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    # Cabeçalho
    cabecalho = [
        'ID', 'Responsável', 'Status', 'Substatus', 'SEI Celebração',
        'Tipo de Termo', 'OSC', 'CNPJ', 'Projeto', 'Unidade Gestora',
        'Edital', 'Total Previsto', 'Nº Termo', 'Numeração Termo',
        'Meses', 'Dias', 'Conta', 'Lei',
        'Início', 'Final', 'Assinatura',
        'Nome PG', 'Secretaria Celebração', 'Status Genérico',
        'Endereço Sede', 'Observações'
    ]
    writer.writerow(cabecalho)

    for r in registros:
        def fmt_date(d):
            return d.strftime('%d/%m/%Y') if d else ''

        def fmt_decimal(v):
            if v is None:
                return ''
            return str(v).replace('.', ',')

        writer.writerow([
            r['id'],
            r['responsavel'] or '',
            r['status'] or '',
            r['substatus'] or '',
            r['sei_celeb'] or '',
            r['tipo_termo'] or '',
            r['osc'] or '',
            r['cnpj'] or '',
            r['projeto'] or '',
            r['unidade_gestora'] or '',
            r['edital_nome'] or '',
            fmt_decimal(r['total_previsto']),
            r['numero_termo'] or '',
            r['numeracao_termo'] or '',
            r['meses'] or '',
            r['dias'] or '',
            r['conta'] or '',
            r['lei'] or '',
            fmt_date(r.get('inicio')),
            fmt_date(r.get('final')),
            fmt_date(r.get('assinatura')),
            r['nome_pg'] or '',
            r['celebracao_secretaria'] or '',
            r['status_generico'] or '',
            r['endereco_sede'] or '',
            r['observacoes'] or '',
        ])

    csv_content = output.getvalue()
    output.close()

    # BOM para Excel reconhecer UTF-8
    bom = '\ufeff'
    return Response(
        bom + csv_content,
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': 'attachment; filename=celebracao_parcerias.csv'
        }
    )


# ── Obter detalhes de um registro ─────────────────────────────────────────────

@celebracao_parcerias_bp.route("/detalhe/<int:id>", methods=["GET"])
@login_required
@requires_access('celebracao_parcerias')
def obter_detalhe(id):
    """Retorna todos os campos de um registro para modal de detalhes/edição"""
    cur = get_cursor()
    cur.execute("SELECT * FROM celebracao.celebracao_parcerias WHERE id = %s", [id])
    registro = cur.fetchone()

    if not registro:
        return jsonify({'success': False, 'erro': 'Registro não encontrado'}), 404

    dados = dict(registro)
    # Converter datas para string ISO
    for campo in ['inicio', 'final', 'assinatura']:
        if dados.get(campo):
            dados[campo] = dados[campo].isoformat()
    # Converter Decimal para float para JSON
    if dados.get('total_previsto') is not None:
        dados['total_previsto'] = float(dados['total_previsto'])

    return jsonify({'success': True, 'registro': dados})


# ── Gestão de Visualização Geral ──────────────────────────────────────────────

@celebracao_parcerias_bp.route("/visualizacao-geral", methods=["GET"])
@login_required
@requires_access('celebracao_parcerias')
def listar_visualizacao_geral():
    """
    Retorna a lista de analistas DGP com seu flag de visualizacao_geral.
    Apenas admins podem acessar.
    """
    if session.get('tipo_usuario') != 'Agente Público':
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    cur = get_cursor()
    cur.execute("""
        SELECT id, nome_analista, rf, status,
               COALESCE(visualizacao_geral, FALSE) AS visualizacao_geral
        FROM categoricas.c_dgp_analistas
        WHERE status = true
        ORDER BY nome_analista
    """)
    analistas = cur.fetchall()

    return jsonify({
        'success': True,
        'analistas': [dict(a) for a in analistas]
    })


@celebracao_parcerias_bp.route("/visualizacao-geral", methods=["POST"])
@login_required
@requires_access('celebracao_parcerias')
def atualizar_visualizacao_geral():
    """
    Atualiza os flags de visualizacao_geral para analistas DGP.
    Recebe JSON: { "analistas": [ { "id": 1, "visualizacao_geral": true }, ... ] }
    """
    if session.get('tipo_usuario') != 'Agente Público':
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    cur = get_cursor()
    db = get_db()

    try:
        data = request.get_json()
        lista = data.get('analistas', [])

        for item in lista:
            cur.execute("""
                UPDATE categoricas.c_dgp_analistas
                SET visualizacao_geral = %s
                WHERE id = %s
            """, [bool(item.get('visualizacao_geral', False)), item['id']])

        db.commit()
        print(f"[CELEBRAÇÃO] Visualização geral atualizada por {session.get('email')}")
        return jsonify({'success': True, 'mensagem': 'Visualização atualizada com sucesso!'})

    except Exception as e:
        db.rollback()
        print(f"[ERRO CELEBRAÇÃO] Erro ao atualizar visualização: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500


# ── Editar registro ────────────────────────────────────────────────────────────

@celebracao_parcerias_bp.route("/editar/<int:id>", methods=["PUT"])
@login_required
@requires_access('celebracao_parcerias')
def editar(id):
    """Atualiza os campos de um registro de Celebração de Parcerias"""
    cur = get_cursor()
    db = get_db()

    try:
        data = request.get_json()

        def s(campo):
            v = data.get(campo, '')
            return str(v).strip() if v and str(v).strip() else None

        def i(campo):
            v = data.get(campo)
            if v is None or str(v).strip() == '':
                return None
            try:
                return int(float(str(v)))
            except (ValueError, TypeError):
                return None

        def d(campo):
            v = s(campo)
            if not v:
                return None
            try:
                return datetime.strptime(v, '%Y-%m-%d').date()
            except ValueError:
                return None

        def dec(campo):
            v = data.get(campo)
            if v is None or str(v).strip() == '':
                return None
            try:
                return Decimal(str(v).replace(',', '.'))
            except Exception:
                return None

        cur.execute("""
            UPDATE celebracao.celebracao_parcerias
            SET edital_nome           = %s,
                unidade_gestora       = %s,
                tipo_termo            = %s,
                sei_celeb             = %s,
                osc                   = %s,
                cnpj                  = %s,
                status                = %s,
                substatus             = %s,
                projeto               = %s,
                endereco_sede         = %s,
                meses                 = %s,
                dias                  = %s,
                total_previsto        = %s,
                conta                 = %s,
                lei                   = %s,
                observacoes           = %s,
                numeracao_termo       = %s,
                inicio                = %s,
                final                 = %s,
                assinatura            = %s,
                nome_pg               = %s,
                celebracao_secretaria = %s,
                status_generico       = %s,
                numero_termo          = %s,
                responsavel           = %s
            WHERE id = %s
        """, [
            s('edital_nome'), s('unidade_gestora'), s('tipo_termo'),
            s('sei_celeb'), s('osc'), s('cnpj'), s('status'),
            s('substatus'), s('projeto'), s('endereco_sede'),
            i('meses'), i('dias'), dec('total_previsto'),
            s('conta'), s('lei'), s('observacoes'),
            i('numeracao_termo'), d('inicio'), d('final'),
            d('assinatura'), s('nome_pg'), s('celebracao_secretaria'),
            s('status_generico'), s('numero_termo'), s('responsavel'),
            id
        ])

        if cur.rowcount == 0:
            return jsonify({'success': False, 'erro': 'Registro não encontrado'}), 404

        # ── Salvar endereços de execução do projeto ──
        sei_celeb_val = s('sei_celeb')
        enderecos = data.get('enderecos', [])
        if sei_celeb_val:
            cur.execute(
                "DELETE FROM celebracao.celebracao_parcerias_enderecos WHERE sei_celeb = %s",
                [sei_celeb_val]
            )
            for enc in enderecos:
                def vs(f): return str(enc.get(f, '') or '').strip() or None
                def vi(f):
                    v = enc.get(f)
                    try: return int(str(v)) if v else None
                    except: return None
                cur.execute("""
                    INSERT INTO celebracao.celebracao_parcerias_enderecos
                        (sei_celeb, parceria_logradouro, parceria_complemento,
                         parceria_numero, parceria_cep, parceria_distrito, observacao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, [
                    sei_celeb_val, vs('parceria_logradouro'), vs('parceria_complemento'),
                    vi('parceria_numero'), vs('parceria_cep'), vs('parceria_distrito'),
                    vs('observacao')
                ])

        db.commit()
        print(f"[CELEBRAÇÃO] Registro #{id} atualizado por {session.get('email')}")
        return jsonify({'success': True, 'mensagem': 'Registro atualizado com sucesso!'})

    except Exception as e:
        db.rollback()
        print(f"[ERRO CELEBRAÇÃO] Erro ao editar #{id}: {e}")
        return jsonify({'success': False, 'erro': str(e)}), 500


# ── Endereços de execução (por id do registro) ─────────────────────────────────────

@celebracao_parcerias_bp.route("/enderecos/<int:id>", methods=["GET"])
@login_required
@requires_access('celebracao_parcerias')
def listar_enderecos(id):
    """Retorna os endereços de execução de um registro (por sei_celeb)"""
    cur = get_cursor()
    cur.execute("SELECT sei_celeb FROM celebracao.celebracao_parcerias WHERE id = %s", [id])
    row = cur.fetchone()
    if not row or not row['sei_celeb']:
        return jsonify({'success': True, 'enderecos': [], 'sem_sei': True})
    sei = row['sei_celeb']
    cur.execute("""
        SELECT id, parceria_logradouro, parceria_complemento, parceria_numero,
               parceria_cep, parceria_distrito, observacao
        FROM celebracao.celebracao_parcerias_enderecos
        WHERE sei_celeb = %s
        ORDER BY id
    """, [sei])
    enderecos = [dict(r) for r in cur.fetchall()]
    return jsonify({'success': True, 'enderecos': enderecos})


# ── API Distritos (para Select2 nos endereços) ─────────────────────────────────────

@celebracao_parcerias_bp.route("/api/distritos", methods=["GET"])
@login_required
@requires_access('celebracao_parcerias')
def api_distritos():
    """Retorna lista de distritos para Select2"""
    q = request.args.get('q', '').strip()
    cur = get_cursor()
    if q:
        cur.execute("""
            SELECT DISTINCT codigo_distrital, distrito
            FROM categoricas.c_geral_regionalizacao
            WHERE distrito ILIKE %s
            ORDER BY distrito LIMIT 60
        """, (f'%{q}%',))
    else:
        cur.execute("""
            SELECT DISTINCT codigo_distrital, distrito
            FROM categoricas.c_geral_regionalizacao
            ORDER BY distrito LIMIT 60
        """)
    rows = cur.fetchall()
    resultado = [{'id': r['codigo_distrital'], 'text': r['distrito']} for r in rows]
    return jsonify(resultado)


# ── Busca de OSC por CNPJ ─────────────────────────────────────────────────────────

@celebracao_parcerias_bp.route("/cnpj-lookup", methods=["GET"])
@login_required
@requires_access('celebracao_parcerias')
def cnpj_lookup():
    """
    Busca o nome da OSC a partir de um CNPJ nas tabelas public.parcerias
    e celebracao.gestao_cents, retornando todos os nomes distintos encontrados.
    """
    cnpj = request.args.get('cnpj', '').strip()
    if not cnpj:
        return jsonify({'success': False, 'erro': 'CNPJ não informado'}), 400

    cur = get_cursor()
    resultados = []

    try:
        # Busca em public.parcerias
        cur.execute("""
            SELECT DISTINCT osc FROM public.parcerias
            WHERE cnpj = %s AND osc IS NOT NULL AND osc != ''
            ORDER BY osc
        """, (cnpj,))
        for row in cur.fetchall():
            if row['osc'] not in resultados:
                resultados.append(row['osc'])

        # Busca em celebracao.gestao_cents
        cur.execute("""
            SELECT DISTINCT osc FROM celebracao.gestao_cents
            WHERE osc_cnpj = %s AND osc IS NOT NULL AND osc != ''
            ORDER BY osc
        """, (cnpj,))
        for row in cur.fetchall():
            if row['osc'] not in resultados:
                resultados.append(row['osc'])

        return jsonify({'success': True, 'resultados': resultados})

    except Exception as e:
        return jsonify({'success': False, 'erro': str(e)}), 500


# ── Sugestões para autocomplete ───────────────────────────────────────────────

@celebracao_parcerias_bp.route("/sugestoes/<campo>", methods=["GET"])
@login_required
@requires_access('celebracao_parcerias')
def sugestoes(campo):
    """
    Retorna valores distintos de uma coluna para autocomplete.
    Aceita ?q=texto para filtrar.
    """
    colunas_permitidas = [
        'responsavel', 'status', 'substatus', 'sei_celeb', 'tipo_termo',
        'osc', 'projeto', 'unidade_gestora', 'edital_nome', 'numero_termo',
        'status_generico', 'cnpj', 'nome_pg', 'celebracao_secretaria'
    ]

    if campo not in colunas_permitidas:
        return jsonify({'success': False, 'erro': 'Campo inválido'}), 400

    cur = get_cursor()
    q = request.args.get('q', '').strip()

    if q:
        cur.execute(f"""
            SELECT DISTINCT {campo}
            FROM celebracao.celebracao_parcerias
            WHERE {campo} IS NOT NULL AND {campo} != ''
              AND unaccent(LOWER({campo})) LIKE unaccent(LOWER(%s))
            ORDER BY {campo}
            LIMIT 20
        """, (f"%{q}%",))
    else:
        cur.execute(f"""
            SELECT DISTINCT {campo}
            FROM celebracao.celebracao_parcerias
            WHERE {campo} IS NOT NULL AND {campo} != ''
            ORDER BY {campo}
            LIMIT 50
        """)

    valores = [r[campo] for r in cur.fetchall()]
    return jsonify({'success': True, 'valores': valores})
