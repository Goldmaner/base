"""
Blueprint de Relatórios de Desempenho — gestao_pessoas
"""

from datetime import date, timedelta
from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access

relatorios_desempenho_bp = Blueprint(
    'relatorios_desempenho', __name__, url_prefix='/relatorios_desempenho'
)

TIPOS_AFERICAO = ['Processo SEI', 'Outros']


def _ensure_tables():
    """Garante que as tabelas e a coluna de permissão existam."""
    try:
        cur = get_cursor()
        db = get_db()
        if not cur or not db:
            return
        cur.execute("""
            ALTER TABLE gestao_pessoas.usuarios_infos
            ADD COLUMN IF NOT EXISTS usuario_relatorios_permissao BOOLEAN DEFAULT FALSE
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gestao_pessoas.relatorios_desempenho (
                id               SERIAL PRIMARY KEY,
                usuario_email    TEXT NOT NULL,
                operacao_tipo    TEXT NOT NULL,
                operacao_nome    TEXT NOT NULL,
                operacao_subtipo TEXT,
                criado_por       TEXT,
                criado_em        TIMESTAMP DEFAULT NOW(),
                atualizado_por   TEXT,
                atualizado_em    TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gestao_pessoas.relatorios_desempenho_auxiliar (
                id                     SERIAL PRIMARY KEY,
                operacao_id            INTEGER NOT NULL
                    REFERENCES gestao_pessoas.relatorios_desempenho(id) ON DELETE CASCADE,
                operacao_tipo_afericao TEXT,
                operacao_afericao      TEXT,
                operacao_descricao     TEXT,
                criado_por             TEXT,
                criado_em              TIMESTAMP DEFAULT NOW(),
                atualizado_por         TEXT,
                atualizado_em          TIMESTAMP
            )
        """)
        db.commit()
    except Exception as e:
        print(f'[relatorios_desempenho] Erro ao garantir tabelas: {e}')
        try:
            get_db().rollback()
        except Exception:
            pass


_ensure_tables()


def _tem_permissao_total():
    """True se o usuário pode ver registros de todos."""
    if session.get('tipo_usuario') == 'Agente Público':
        return True
    try:
        cur = get_cursor()
        if not cur:
            return False
        cur.execute("""
            SELECT usuario_relatorios_permissao
            FROM gestao_pessoas.usuarios_infos
            WHERE usuario_email = %s
        """, (session.get('email'),))
        row = cur.fetchone()
        return bool(row and row['usuario_relatorios_permissao'])
    except Exception:
        return False


def _semana_inicio_de(d):
    """Retorna a segunda-feira da semana de d."""
    return d - timedelta(days=d.weekday())


def _info_teletrabalho(email):
    """Retorna dict com data_teletrabalho e eh_hoje para a semana corrente."""
    hoje = date.today()
    semana_inicio = _semana_inicio_de(hoje)
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT data_teletrabalho
            FROM calendario.escala_teletrabalho
            WHERE usuario_email = %s AND semana_inicio = %s
        """, (email, semana_inicio))
        row = cur.fetchone()
        if row and row['data_teletrabalho']:
            data_tt = row['data_teletrabalho']
            return {
                'tem_teletrabalho': True,
                'data_teletrabalho': str(data_tt),
                'eh_hoje': data_tt == hoje,
            }
    except Exception:
        pass
    return {'tem_teletrabalho': False, 'data_teletrabalho': None, 'eh_hoje': False}


# ---------------------------------------------------------------------------
# Página principal
# ---------------------------------------------------------------------------

@relatorios_desempenho_bp.route('/')
@requires_access('relatorios_desempenho')
def index():
    permissao_total = _tem_permissao_total()
    return render_template(
        'gestao_pessoas/relatorios_desempenho.html',
        permissao_total=permissao_total,
        tipos_afericao=TIPOS_AFERICAO,
    )


# ---------------------------------------------------------------------------
# Página gerencial (somente permissao_total)
# ---------------------------------------------------------------------------

@relatorios_desempenho_bp.route('/gerencial')
@requires_access('relatorios_desempenho')
def gerencial():
    if not _tem_permissao_total():
        from flask import abort
        abort(403)
    return render_template('gestao_pessoas/relatorios_desempenho_gerencial.html')


# ---------------------------------------------------------------------------
# API — teletrabalho do usuário corrente
# ---------------------------------------------------------------------------

@relatorios_desempenho_bp.route('/api/meu_dia_teletrabalho')
@login_required
def api_meu_dia_teletrabalho():
    """Informa se hoje é o dia de teletrabalho do usuário logado."""
    info = _info_teletrabalho(session['email'])
    return jsonify(info)


# ---------------------------------------------------------------------------
# API — dados gerenciais por semana
# ---------------------------------------------------------------------------

@relatorios_desempenho_bp.route('/api/gerencial_semana')
@login_required
def api_gerencial_semana():
    if not _tem_permissao_total():
        return jsonify({'erro': 'Acesso negado.'}), 403

    semana_str = request.args.get('semana_inicio', '').strip()
    try:
        if semana_str:
            semana_inicio = date.fromisoformat(semana_str)
        else:
            semana_inicio = _semana_inicio_de(date.today())
    except ValueError:
        return jsonify({'erro': 'Data inválida.'}), 400

    semana_fim = semana_inicio + timedelta(days=4)

    DIAS_PT = {
        0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira',
        3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo',
    }

    try:
        cur = get_cursor()
        cur.execute("""
            SELECT
                et.usuario_email,
                COALESCE(ui.usuario_nome, et.usuario_email) AS nome_usuario,
                COALESCE(ui.usuario_unidade_alocada, 'Sem departamento') AS unidade,
                et.data_teletrabalho,
                (
                    SELECT COUNT(*)
                    FROM gestao_pessoas.relatorios_desempenho rd
                    WHERE rd.usuario_email = et.usuario_email
                      AND (rd.criado_em AT TIME ZONE 'America/Sao_Paulo')::date = et.data_teletrabalho
                ) AS total_registros
            FROM calendario.escala_teletrabalho et
            LEFT JOIN gestao_pessoas.usuarios_infos ui
                   ON ui.usuario_email = et.usuario_email
            WHERE et.semana_inicio = %s
              AND et.data_teletrabalho IS NOT NULL
            ORDER BY ui.usuario_unidade_alocada NULLS LAST,
                     et.data_teletrabalho,
                     COALESCE(ui.usuario_nome, et.usuario_email)
        """, (semana_inicio,))

        pessoas = []
        for row in cur.fetchall():
            dt = row['data_teletrabalho']
            pessoas.append({
                'email': row['usuario_email'],
                'nome': row['nome_usuario'],
                'data_teletrabalho': str(dt) if dt else None,
                'data_fmt': dt.strftime('%d/%m/%Y') if dt else '—',
                'dia_semana': DIAS_PT.get(dt.weekday(), '') if dt else '—',
                'unidade': row['unidade'],
                'relatorio_preenchido': int(row['total_registros']) > 0,
                'total_registros': int(row['total_registros']),
            })

        return jsonify({
            'semana_inicio': str(semana_inicio),
            'semana_inicio_fmt': semana_inicio.strftime('%d/%m/%Y'),
            'semana_fim_fmt': semana_fim.strftime('%d/%m/%Y'),
            'pessoas': pessoas,
        })
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# ---------------------------------------------------------------------------
# API — opções de formulário
# ---------------------------------------------------------------------------

@relatorios_desempenho_bp.route('/api/tipos')
@login_required
def api_tipos():
    """Retorna os valores distintos de manual_area da tabela manuais_lista."""
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT DISTINCT manual_area
            FROM public.manuais_lista
            WHERE manual_area IS NOT NULL AND manual_area <> ''
            ORDER BY manual_area
        """)
        return jsonify({'tipos': [r['manual_area'] for r in cur.fetchall()]})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@relatorios_desempenho_bp.route('/api/nomes')
@login_required
def api_nomes():
    """Retorna os manual_nome de manuais_lista filtrados por manual_area."""
    tipo = request.args.get('tipo', '').strip()
    if not tipo:
        return jsonify({'nomes': []})
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT id, manual_nome
            FROM public.manuais_lista
            WHERE manual_area = %s
            ORDER BY manual_nome
        """, (tipo,))
        return jsonify({'nomes': [dict(r) for r in cur.fetchall()]})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# ---------------------------------------------------------------------------
# API — CRUD registros
# ---------------------------------------------------------------------------

@relatorios_desempenho_bp.route('/api/registros', methods=['GET'])
@login_required
def api_listar():
    permissao_total = _tem_permissao_total()
    email_filtro = request.args.get('usuario_email', '').strip()
    busca = request.args.get('q', '').strip()

    where = []
    params = []

    if not permissao_total:
        where.append('r.usuario_email = %s')
        params.append(session['email'])
    elif email_filtro:
        where.append('r.usuario_email = %s')
        params.append(email_filtro)

    if busca:
        where.append('(r.operacao_tipo ILIKE %s OR r.operacao_nome ILIKE %s OR r.operacao_subtipo ILIKE %s)')
        like = f'%{busca}%'
        params.extend([like, like, like])

    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    try:
        cur = get_cursor()
        cur.execute(f"""
            SELECT r.id, r.usuario_email,
                   COALESCE(i.usuario_nome, r.usuario_email) AS nome_usuario,
                   r.operacao_tipo, r.operacao_nome, r.operacao_subtipo,
                   TO_CHAR(r.criado_em AT TIME ZONE 'America/Sao_Paulo',
                           'DD/MM/YYYY HH24:MI') AS criado_em_fmt,
                   (SELECT COUNT(*) FROM gestao_pessoas.relatorios_desempenho_auxiliar a
                    WHERE a.operacao_id = r.id) AS total_afericoes
            FROM gestao_pessoas.relatorios_desempenho r
            LEFT JOIN gestao_pessoas.usuarios_infos i ON i.usuario_email = r.usuario_email
            {where_sql}
            ORDER BY r.criado_em DESC, r.id DESC
        """, params)
        return jsonify({'registros': [dict(row) for row in cur.fetchall()]})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@relatorios_desempenho_bp.route('/api/registros', methods=['POST'])
@login_required
def api_criar():
    data = request.get_json(silent=True) or {}
    tipo      = (data.get('operacao_tipo') or '').strip()
    nome      = (data.get('operacao_nome') or '').strip()
    subtipo   = (data.get('operacao_subtipo') or '').strip() or None
    auxiliares = data.get('auxiliares', [])

    if not tipo or not nome:
        return jsonify({'erro': 'Tipo e Nome da operação são obrigatórios.'}), 400

    try:
        cur = get_cursor()
        db = get_db()

        cur.execute("""
            INSERT INTO gestao_pessoas.relatorios_desempenho
                (usuario_email, operacao_tipo, operacao_nome, operacao_subtipo, criado_por)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (session['email'], tipo, nome, subtipo, session['email']))
        new_id = cur.fetchone()['id']

        for aux in auxiliares:
            _inserir_auxiliar(cur, new_id, aux)

        db.commit()
        return jsonify({'success': True, 'id': new_id}), 201
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@relatorios_desempenho_bp.route('/api/registros/<int:reg_id>', methods=['PUT'])
@login_required
def api_editar(reg_id):
    permissao_total = _tem_permissao_total()
    data = request.get_json(silent=True) or {}

    try:
        cur = get_cursor()
        cur.execute('SELECT usuario_email FROM gestao_pessoas.relatorios_desempenho WHERE id = %s', (reg_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'erro': 'Registro não encontrado.'}), 404
        if not permissao_total and row['usuario_email'] != session['email']:
            return jsonify({'erro': 'Acesso negado.'}), 403

        tipo    = (data.get('operacao_tipo') or '').strip()
        nome    = (data.get('operacao_nome') or '').strip()
        subtipo = (data.get('operacao_subtipo') or '').strip() or None
        auxiliares = data.get('auxiliares', [])

        if not tipo or not nome:
            return jsonify({'erro': 'Tipo e Nome são obrigatórios.'}), 400

        db = get_db()
        cur.execute("""
            UPDATE gestao_pessoas.relatorios_desempenho
            SET operacao_tipo = %s, operacao_nome = %s, operacao_subtipo = %s,
                atualizado_por = %s, atualizado_em = NOW()
            WHERE id = %s
        """, (tipo, nome, subtipo, session['email'], reg_id))

        cur.execute('DELETE FROM gestao_pessoas.relatorios_desempenho_auxiliar WHERE operacao_id = %s', (reg_id,))
        for aux in auxiliares:
            _inserir_auxiliar(cur, reg_id, aux)

        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@relatorios_desempenho_bp.route('/api/registros/<int:reg_id>', methods=['DELETE'])
@login_required
def api_excluir(reg_id):
    permissao_total = _tem_permissao_total()
    try:
        cur = get_cursor()
        cur.execute('SELECT usuario_email FROM gestao_pessoas.relatorios_desempenho WHERE id = %s', (reg_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'erro': 'Registro não encontrado.'}), 404
        if not permissao_total and row['usuario_email'] != session['email']:
            return jsonify({'erro': 'Acesso negado.'}), 403

        db = get_db()
        cur.execute('DELETE FROM gestao_pessoas.relatorios_desempenho WHERE id = %s', (reg_id,))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


# ---------------------------------------------------------------------------
# API — aferições de um registro
# ---------------------------------------------------------------------------

@relatorios_desempenho_bp.route('/api/registros/<int:reg_id>/auxiliares', methods=['GET'])
@login_required
def api_listar_auxiliares(reg_id):
    permissao_total = _tem_permissao_total()
    try:
        cur = get_cursor()
        cur.execute('SELECT usuario_email FROM gestao_pessoas.relatorios_desempenho WHERE id = %s', (reg_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'erro': 'Registro não encontrado.'}), 404
        if not permissao_total and row['usuario_email'] != session['email']:
            return jsonify({'erro': 'Acesso negado.'}), 403

        cur.execute("""
            SELECT id, operacao_tipo_afericao, operacao_afericao, operacao_descricao
            FROM gestao_pessoas.relatorios_desempenho_auxiliar
            WHERE operacao_id = %s
            ORDER BY id ASC
        """, (reg_id,))
        return jsonify({'auxiliares': [dict(r) for r in cur.fetchall()]})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# ---------------------------------------------------------------------------
# API — usuários para filtro
# ---------------------------------------------------------------------------

@relatorios_desempenho_bp.route('/api/usuarios_lista')
@login_required
def api_usuarios_lista():
    if not _tem_permissao_total():
        return jsonify({'erro': 'Acesso negado.'}), 403
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT u.email, COALESCE(i.usuario_nome, u.email) AS nome
            FROM gestao_pessoas.usuarios u
            LEFT JOIN gestao_pessoas.usuarios_infos i ON i.usuario_email = u.email
            WHERE (i.usuario_vinculo IS NULL OR i.usuario_vinculo != 'Estagiário(a)')
            ORDER BY COALESCE(i.usuario_nome, u.email)
        """)
        return jsonify({'usuarios': [dict(r) for r in cur.fetchall()]})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _inserir_auxiliar(cur, operacao_id, aux):
    tipo_af = (aux.get('operacao_tipo_afericao') or '').strip() or None
    afericao = (aux.get('operacao_afericao') or '').strip() or None
    descricao = (aux.get('operacao_descricao') or '').strip() or None
    criado_por = session.get('email')
    cur.execute("""
        INSERT INTO gestao_pessoas.relatorios_desempenho_auxiliar
            (operacao_id, operacao_tipo_afericao, operacao_afericao, operacao_descricao, criado_por)
        VALUES (%s, %s, %s, %s, %s)
    """, (operacao_id, tipo_af, afericao, descricao, criado_por))
