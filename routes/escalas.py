"""
Blueprint de Escalas (Teletrabalho e Almoço)
Gerencia escalas semanais de teletrabalho e horários fixos de almoço.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access
from datetime import date, timedelta, datetime

escalas_bp = Blueprint('escalas', __name__, url_prefix='/escalas')

# Mapeamento tipo_usuario → unidade alocada (auto-preenchimento)
UNIDADE_POR_TIPO = {
    'Agente DAC': 'Divisão de Análise de Contas',
    'Agente DGP': 'Divisão de Gestão de Parcerias',
    'Agente DP':  'Departamento de Parcerias',
}


def _get_user_info():
    return (
        session.get('d_usuario', ''),
        session.get('email', ''),
        session.get('tipo_usuario', ''),
    )


def _pode_editar_escala(email, tipo_usuario):
    """True se o usuário pode construir/editar escalas."""
    if tipo_usuario in ('Agente Público', 'admin'):
        return True
    cur = get_cursor()
    try:
        cur.execute(
            "SELECT usuario_escala_permissao FROM gestao_pessoas.usuarios_infos WHERE usuario_email = %s",
            (email,)
        )
        row = cur.fetchone()
        return bool(row and row['usuario_escala_permissao'])
    finally:
        cur.close()


def _monday_of_week(d: date) -> date:
    """Retorna a segunda-feira da semana de uma data."""
    return d - timedelta(days=d.weekday())


def _check_conflitos(usuario_email: str, data_tt: date) -> dict | None:
    """
    Verifica se data_tt conflita com férias ou folga do servidor.
    Retorna dict com detalhes do conflito, ou None se não houver.
    """
    cur = get_cursor()
    try:
        # Verificar férias
        cur.execute("""
            SELECT ferias_inicio, ferias_fim
            FROM calendario.datas_ferias df
            JOIN gestao_pessoas.usuarios u ON df.d_usuario = u.d_usuario
            WHERE u.email = %s
              AND %s BETWEEN df.ferias_inicio AND df.ferias_fim
            LIMIT 1
        """, (usuario_email, data_tt))
        ferias = cur.fetchone()
        if ferias:
            return {'tipo': 'Férias', 'inicio': ferias['ferias_inicio'], 'fim': ferias['ferias_fim']}

        # Verificar folga/abono em datas_importantes
        cur.execute("""
            SELECT nome_data, data_inicio, data_fim
            FROM calendario.datas_importantes
            WHERE usuario_email = %s
              AND nome_data IN ('Folga', 'Abono')
              AND %s BETWEEN data_inicio AND COALESCE(data_fim, data_inicio)
            LIMIT 1
        """, (usuario_email, data_tt))
        folga = cur.fetchone()
        if folga:
            return {
                'tipo': folga['nome_data'],
                'inicio': folga['data_inicio'],
                'fim': folga['data_fim'],
            }
        return None
    finally:
        cur.close()


# ─────────────────────────────────────────────────────────────────────────────
# ESCALA DE TELETRABALHO
# ─────────────────────────────────────────────────────────────────────────────

@escalas_bp.route("/teletrabalho", methods=["GET"])
@login_required
@requires_access('ferias')
def teletrabalho():
    """
    Exibe a grade semanal de teletrabalho.
    ?semana=YYYY-MM-DD (segunda-feira da semana desejada; default = semana atual)
    """
    _, email, tipo_usuario = _get_user_info()
    pode_editar = _pode_editar_escala(email, tipo_usuario)

    # Calcular semana a exibir
    semana_param = request.args.get('semana', '')
    try:
        semana_inicio = date.fromisoformat(semana_param)
        # Garantir que seja segunda-feira
        semana_inicio = _monday_of_week(semana_inicio)
    except ValueError:
        semana_inicio = _monday_of_week(date.today())

    semana_anterior = semana_inicio - timedelta(weeks=1)
    semana_seguinte = semana_inicio + timedelta(weeks=1)

    # Dias da semana (Seg a Sex)
    dias_semana = [semana_inicio + timedelta(days=i) for i in range(5)]

    cur = get_cursor()
    try:
        # Carregar todos os servidores ativos (excluindo Externo)
        cur.execute("""
            SELECT u.id, u.email, u.tipo_usuario, u.d_usuario,
                   COALESCE(ui.usuario_nome, u.email) AS usuario_nome,
                   ui.usuario_unidade_alocada,
                   ui.usuario_status
            FROM gestao_pessoas.usuarios u
            LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = u.email
            WHERE u.tipo_usuario != 'Externo'
              AND COALESCE(ui.usuario_status, 'Ativo') = 'Ativo'
              AND COALESCE(ui.usuario_vinculo, '') != 'Estagiário(a)'
            ORDER BY ui.usuario_unidade_alocada NULLS LAST, ui.usuario_nome
        """)
        servidores = cur.fetchall()

        # Carregar escala da semana
        cur.execute("""
            SELECT usuario_email, data_teletrabalho, observacoes
            FROM calendario.escala_teletrabalho
            WHERE semana_inicio = %s
        """, (semana_inicio,))
        escala_rows = cur.fetchall()
        escala_map = {r['usuario_email']: r for r in escala_rows}

        # Checar conflitos para todos os servidores em batch (2 queries em vez de N×5×2)
        emails_list = [s['email'] for s in servidores]
        conflitos = {s['email']: {} for s in servidores}
        if emails_list and dias_semana:
            semana_fim = dias_semana[-1]

            # Férias que se sobrepõem à semana
            cur.execute("""
                SELECT u.email, df.ferias_inicio, df.ferias_fim
                FROM calendario.datas_ferias df
                JOIN gestao_pessoas.usuarios u ON df.d_usuario = u.d_usuario
                WHERE u.email = ANY(%s)
                  AND df.ferias_inicio <= %s
                  AND df.ferias_fim   >= %s
            """, (emails_list, semana_fim, semana_inicio))
            for row in cur.fetchall():
                for dia in dias_semana:
                    if row['ferias_inicio'] <= dia <= row['ferias_fim']:
                        conflitos[row['email']][dia.isoformat()] = 'Férias'

            # Folgas / abonos que se sobrepõem à semana
            cur.execute("""
                SELECT usuario_email, nome_data,
                       data_inicio, COALESCE(data_fim, data_inicio) AS data_fim
                FROM calendario.datas_importantes
                WHERE usuario_email = ANY(%s)
                  AND nome_data IN ('Folga', 'Abono')
                  AND data_inicio                    <= %s
                  AND COALESCE(data_fim, data_inicio) >= %s
            """, (emails_list, semana_fim, semana_inicio))
            for row in cur.fetchall():
                for dia in dias_semana:
                    if row['data_inicio'] <= dia <= row['data_fim']:
                        conflitos[row['usuario_email']][dia.isoformat()] = row['nome_data']

    finally:
        cur.close()

    # Agrupar por equipe
    equipes_tt = []
    servidores_por_equipe_tt = {}
    for srv in servidores:
        dep = srv['usuario_unidade_alocada'] or 'Sem departamento'
        if dep not in servidores_por_equipe_tt:
            equipes_tt.append(dep)
            servidores_por_equipe_tt[dep] = []
        servidores_por_equipe_tt[dep].append(srv)

    srv_atual_tt = next((s for s in servidores if s['email'] == email), None)
    user_unidade_tt = (srv_atual_tt['usuario_unidade_alocada'] if srv_atual_tt else None) or 'Sem departamento'

    return render_template(
        'escala_teletrabalho.html',
        servidores=servidores,
        equipes=equipes_tt,
        servidores_por_equipe=servidores_por_equipe_tt,
        semana_inicio=semana_inicio,
        semana_anterior=semana_anterior,
        semana_seguinte=semana_seguinte,
        dias_semana=dias_semana,
        escala_map=escala_map,
        conflitos=conflitos,
        pode_editar=pode_editar,
        pode_ver_todas=pode_editar,
        user_unidade=user_unidade_tt,
    )


@escalas_bp.route("/teletrabalho/salvar", methods=["POST"])
@login_required
@requires_access('ferias')
def teletrabalho_salvar():
    """Salva (upsert) a escala de teletrabalho de uma semana inteira."""
    _, email, tipo_usuario = _get_user_info()
    if not _pode_editar_escala(email, tipo_usuario):
        flash('Sem permissão para editar escalas.', 'danger')
        return redirect(url_for('escalas.teletrabalho'))

    semana_str = request.form.get('semana_inicio', '').strip()
    try:
        semana_inicio = date.fromisoformat(semana_str)
    except ValueError:
        flash('Data de semana inválida.', 'danger')
        return redirect(url_for('escalas.teletrabalho'))

    cur = get_cursor()
    avisos = []
    try:
        # Coletar todos os emails presentes no form
        emails_form = request.form.getlist('usuario_email[]')
        datas_form  = request.form.getlist('data_teletrabalho[]')  # '' ou 'YYYY-MM-DD'

        for srv_email, data_str in zip(emails_form, datas_form):
            srv_email = srv_email.strip()
            if not srv_email:
                continue

            data_tt = None
            if data_str.strip():
                try:
                    data_tt = date.fromisoformat(data_str.strip())
                except ValueError:
                    continue

            # Verificar conflito (aviso)
            if data_tt:
                conflito = _check_conflitos(srv_email, data_tt)
                if conflito:
                    # Buscar nome do servidor
                    cur.execute(
                        "SELECT COALESCE(ui.usuario_nome, u.email) AS nome "
                        "FROM gestao_pessoas.usuarios u "
                        "LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = u.email "
                        "WHERE u.email = %s", (srv_email,)
                    )
                    row = cur.fetchone()
                    nome = row['nome'] if row else srv_email
                    avisos.append(
                        f"⚠️ {nome}: {data_tt.strftime('%d/%m')} conflita com {conflito['tipo']} "
                        f"(salvo mesmo assim)"
                    )

            # UPSERT
            cur.execute("""
                INSERT INTO calendario.escala_teletrabalho
                    (usuario_email, semana_inicio, data_teletrabalho, criado_por, criado_em)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (usuario_email, semana_inicio)
                DO UPDATE SET
                    data_teletrabalho = EXCLUDED.data_teletrabalho,
                    atualizado_por    = EXCLUDED.criado_por,
                    atualizado_em     = NOW()
            """, (srv_email, semana_inicio, data_tt, email))

        get_db().commit()

        # Auditoria
        try:
            _, _, tipo_usuario = _get_user_info()
            nome_usuario = session.get('usuario_nome', email)
            resumo = {e: d for e, d in zip(emails_form, datas_form) if e.strip()}
            cur.execute("""
                INSERT INTO gestao_pessoas.log_atividades
                    (usuario_nome, usuario_email, tipo_usuario,
                     acao_tipo, acao_categoria, acao_endpoint, acao_metodo,
                     recurso_tipo, recurso_id,
                     status_codigo, sucesso, ip_address, user_agent, duracao_ms,
                     detalhes, created_at)
                VALUES (%s, %s, %s,
                        'UPDATE', 'escala_teletrabalho', '/escalas/teletrabalho/salvar', 'POST',
                        'escala_teletrabalho', %s,
                        200, TRUE,
                        %s, %s, 0,
                        %s::jsonb, NOW())
            """, (
                nome_usuario, email, tipo_usuario,
                semana_inicio.isoformat(),
                request.remote_addr,
                request.headers.get('User-Agent', '')[:200],
                __import__('json').dumps({'semana': semana_inicio.isoformat(), 'registros': resumo}),
            ))
            get_db().commit()
        except Exception as e_log:
            print(f'[escalas] Aviso: falha ao gravar log de auditoria: {e_log}')

        if avisos:
            flash('Escala salva com avisos de conflito:<br>' + '<br>'.join(avisos), 'warning')
        else:
            flash('Escala de teletrabalho salva com sucesso!', 'success')

    except Exception as e:
        get_db().rollback()
        import traceback; traceback.print_exc()
        flash(f'Erro ao salvar escala: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('escalas.teletrabalho', semana=semana_inicio.isoformat()))


# ─────────────────────────────────────────────────────────────────────────────
# ESCALA DE ALMOÇO
# ─────────────────────────────────────────────────────────────────────────────

@escalas_bp.route("/almoco", methods=["GET"])
@login_required
@requires_access('ferias')
def almoco():
    """Exibe a escala de horários de almoço de todos os servidores."""
    _, email, tipo_usuario = _get_user_info()
    pode_editar = _pode_editar_escala(email, tipo_usuario)

    cur = get_cursor()
    try:
        cur.execute("""
            SELECT u.id, u.email, u.tipo_usuario, u.d_usuario,
                   COALESCE(ui.usuario_nome, u.email) AS usuario_nome,
                   ui.usuario_unidade_alocada,
                   ui.usuario_status,
                   ea.horario_inicio,
                   ea.horario_fim,
                   ea.observacoes AS almoco_obs
            FROM gestao_pessoas.usuarios u
            LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = u.email
            LEFT JOIN calendario.escala_almoco ea ON ea.usuario_email = u.email
            WHERE u.tipo_usuario != 'Externo'
              AND COALESCE(ui.usuario_status, 'Ativo') = 'Ativo'
            ORDER BY ui.usuario_unidade_alocada NULLS LAST, ui.usuario_nome
        """)
        servidores = cur.fetchall()
    finally:
        cur.close()

    # Agrupar por equipe (mantendo ordem de aparição)
    equipes = []
    servidores_por_equipe = {}
    for srv in servidores:
        dep = srv['usuario_unidade_alocada'] or 'Sem departamento'
        if dep not in servidores_por_equipe:
            equipes.append(dep)
            servidores_por_equipe[dep] = []
        servidores_por_equipe[dep].append(srv)

    # Equipe do usuário logado
    srv_atual = next((s for s in servidores if s['email'] == email), None)
    user_unidade = (srv_atual['usuario_unidade_alocada'] if srv_atual else None) or 'Sem departamento'

    return render_template(
        'escala_almoco.html',
        servidores=servidores,
        equipes=equipes,
        servidores_por_equipe=servidores_por_equipe,
        pode_editar=pode_editar,
        pode_ver_todas=pode_editar,   # admin ou usuario_escala_permissao
        user_unidade=user_unidade,
        current_user_email=email,
    )


@escalas_bp.route("/almoco/salvar", methods=["POST"])
@login_required
@requires_access('ferias')
def almoco_salvar():
    """Upsert do horário de almoço de um servidor."""
    _, email, tipo_usuario = _get_user_info()
    srv_email      = request.form.get('usuario_email', '').strip()
    horario_inicio = request.form.get('horario_inicio', '').strip() or None
    horario_fim    = request.form.get('horario_fim', '').strip() or None
    observacoes    = request.form.get('observacoes', '').strip() or None

    if not srv_email:
        flash('E-mail do servidor é obrigatório.', 'danger')
        return redirect(url_for('escalas.almoco'))

    is_own = (srv_email == email)
    if not is_own and not _pode_editar_escala(email, tipo_usuario):
        flash('Sem permissão para editar o horário de outros servidores.', 'danger')
        return redirect(url_for('escalas.almoco'))

    cur = get_cursor()
    try:
        cur.execute("""
            INSERT INTO calendario.escala_almoco
                (usuario_email, horario_inicio, horario_fim, observacoes, criado_por, criado_em)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (usuario_email)
            DO UPDATE SET
                horario_inicio = EXCLUDED.horario_inicio,
                horario_fim    = EXCLUDED.horario_fim,
                observacoes    = EXCLUDED.observacoes,
                atualizado_por = EXCLUDED.criado_por,
                atualizado_em  = NOW()
        """, (srv_email, horario_inicio, horario_fim, observacoes, email))
        get_db().commit()
        flash('Horário de almoço atualizado com sucesso!', 'success')
    except Exception as e:
        get_db().rollback()
        import traceback; traceback.print_exc()
        flash(f'Erro ao salvar: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('escalas.almoco'))


@escalas_bp.route("/almoco/remover/<path:srv_email>", methods=["POST"])
@login_required
@requires_access('ferias')
def almoco_remover(srv_email):
    """Remove o horário de almoço de um servidor."""
    _, email, tipo_usuario = _get_user_info()
    is_own = (srv_email == email)
    if not is_own and not _pode_editar_escala(email, tipo_usuario):
        flash('Sem permissão para remover o horário de outros servidores.', 'danger')
        return redirect(url_for('escalas.almoco'))

    cur = get_cursor()
    try:
        cur.execute("DELETE FROM calendario.escala_almoco WHERE usuario_email = %s", (srv_email,))
        get_db().commit()
        flash('Horário de almoço removido.', 'success')
    except Exception as e:
        get_db().rollback()
        flash(f'Erro: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('escalas.almoco'))
