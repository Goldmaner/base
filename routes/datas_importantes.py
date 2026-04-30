"""
Blueprint de Datas Importantes
Gerencia abonos, folgas, consultas médicas e eventos por usuário.
"""

import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access
from datetime import datetime


def sanitizar_nome_doc(nome):
    """Sanitiza nome para uso como nome de arquivo (chars inválidos removidos, espaços → _)."""
    nome = nome.strip()
    nome = re.sub(r'[\\/:*?"<>|]', '', nome)
    nome = re.sub(r'\s+', '_', nome)
    nome = re.sub(r'_+', '_', nome)
    return nome.strip('_') or 'documento'

datas_importantes_bp = Blueprint('datas_importantes', __name__, url_prefix='/datas-importantes')


def _get_user_info():
    """Retorna tupla (d_usuario, email, tipo_usuario) da sessão."""
    return (
        session.get('d_usuario', ''),
        session.get('email', ''),
        session.get('tipo_usuario', ''),
    )


def _pode_ver_tudo(email, tipo_usuario):
    """Retorna True se o usuário tem visibilidade total (Agente Público, admin ou flag ligada)."""
    if tipo_usuario in ('Agente Público', 'admin'):
        return True
    cur = get_cursor()
    try:
        cur.execute(
            "SELECT visualizar_todos_eventos FROM gestao_pessoas.usuarios_infos WHERE usuario_email = %s",
            (email,)
        )
        row = cur.fetchone()
        return bool(row and row['visualizar_todos_eventos'])
    finally:
        cur.close()


@datas_importantes_bp.route("/", methods=["GET"])
@login_required
@requires_access('ferias')
def index():
    """
    Página principal com duas abas:
      - Aba 1: Registros Pessoais (abonos, folgas, consultas médicas)
      - Aba 2: Eventos
    Cada usuário vê apenas seus próprios registros.
    """
    d_usuario, email, tipo_usuario = _get_user_info()
    eh_gerente = tipo_usuario in ('Agente Público', 'admin')
    ver_tudo = _pode_ver_tudo(email, tipo_usuario)
    cur = get_cursor()

    try:
        # Tipos de evento para o dropdown (lista suspensa)
        cur.execute("""
            SELECT nome_data, descricao_nome_data
            FROM categoricas.c_geral_eventos
            WHERE status = 'ativo'
            ORDER BY nome_data
        """)
        tipos_evento = cur.fetchall()

        # Registros pessoais — visibilidade total ou só os próprios
        if ver_tudo:
            cur.execute("""
                SELECT di.id, di.nome_data, di.data_inicio, di.data_fim,
                       di.horario_inicio, di.horario_fim, di.observacoes,
                       di.created_at, di.updated_at,
                       ui.usuario_nome, di.usuario_email
                FROM calendario.datas_importantes di
                LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = di.usuario_email
                WHERE di.nome_data <> 'Evento'
                ORDER BY di.data_inicio ASC
            """)
        else:
            cur.execute("""
                SELECT id, nome_data, data_inicio, data_fim,
                       horario_inicio, horario_fim, observacoes,
                       created_at, updated_at,
                       NULL AS usuario_nome, usuario_email
                FROM calendario.datas_importantes
                WHERE usuario_email = %s
                  AND nome_data <> 'Evento'
                ORDER BY data_inicio ASC
            """, (email,))
        registros_pessoais = cur.fetchall()

        # Eventos institucionais — visibilidade total ou só os próprios
        if ver_tudo:
            cur.execute("""
                SELECT de.id, de.nome_atividade, de.descritivo, de.data_inicio, de.datas_adicionais,
                       de.participacao, de.local, de.necessita_infraestrutura,
                       de.valor_alimentacao, de.alinhamento_aev, de.observacoes,
                       de.cancelado, de.created_at, de.updated_at,
                       ui.usuario_nome, de.usuario_email
                FROM calendario.datas_eventos de
                LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = de.usuario_email
                ORDER BY de.data_inicio ASC NULLS LAST
            """)
        else:
            cur.execute("""
                SELECT id, nome_atividade, descritivo, data_inicio, datas_adicionais,
                       participacao, local, necessita_infraestrutura,
                       valor_alimentacao, alinhamento_aev, observacoes,
                       cancelado, created_at, updated_at,
                       NULL AS usuario_nome, usuario_email
                FROM calendario.datas_eventos
                WHERE usuario_email = %s
                ORDER BY data_inicio ASC NULLS LAST
            """, (email,))
        datas_eventos = cur.fetchall()

        # Responsáveis indexados por evento_id
        cur.execute("""
            SELECT id, datas_evento_id, responsavel_atividade, responsavel_tipo
            FROM calendario.datas_eventos_responsaveis
            ORDER BY id
        """)
        resp_rows = cur.fetchall()
        responsaveis_por_evento = {}
        for r in resp_rows:
            responsaveis_por_evento.setdefault(r['datas_evento_id'], []).append(r)

        # Documentos indexados por evento_id
        cur.execute("""
            SELECT id, datas_evento_id, nome_doc, nome_doc_link
            FROM calendario.datas_eventos_documentos
            ORDER BY id
        """)
        doc_rows = cur.fetchall()
        documentos_por_evento = {}
        for d in doc_rows:
            documentos_por_evento.setdefault(d['datas_evento_id'], []).append(d)

        # Lista de nomes para dropdown de responsáveis
        cur.execute("""
            SELECT usuario_nome, usuario_email
            FROM gestao_pessoas.usuarios_infos
            WHERE usuario_status = 'Ativo' AND usuario_nome IS NOT NULL AND usuario_nome <> ''
            ORDER BY usuario_nome
        """)
        usuarios_nomes = cur.fetchall()

        # Checklist de acesso (apenas para gerentes)
        usuarios_acesso_lista = []
        if eh_gerente:
            cur.execute("""
                SELECT u.id, u.email, u.tipo_usuario, u.d_usuario,
                       COALESCE(ui.usuario_nome, u.email) AS nome_exibicao,
                       COALESCE(ui.visualizar_todos_eventos, FALSE) AS visualizar_todos_eventos
                FROM gestao_pessoas.usuarios u
                LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = u.email
                WHERE u.tipo_usuario NOT IN ('Agente Público', 'admin')
                ORDER BY nome_exibicao
            """)
            usuarios_acesso_lista = cur.fetchall()

        # Lista de usuários para campo "Registrar para" (visível ao ver_tudo)
        usuarios_para_registro = []
        if ver_tudo:
            cur.execute("""
                SELECT u.email, COALESCE(ui.usuario_nome, u.email) AS nome_exibicao
                FROM gestao_pessoas.usuarios u
                LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = u.email
                WHERE u.tipo_usuario NOT IN ('admin')
                ORDER BY nome_exibicao
            """)
            usuarios_para_registro = cur.fetchall()

        cur.close()

        # Flatten to list of name strings for JS template
        nomes_lista = [r['usuario_nome'] for r in usuarios_nomes]

        return render_template(
            'datas_importantes.html',
            tipos_evento=tipos_evento,
            registros_pessoais=registros_pessoais,
            datas_eventos=datas_eventos,
            responsaveis_por_evento=responsaveis_por_evento,
            documentos_por_evento=documentos_por_evento,
            usuarios_nomes=nomes_lista,
            usuarios_acesso_lista=usuarios_acesso_lista,
            usuarios_para_registro=usuarios_para_registro,
            eh_gerente=eh_gerente,
            ver_tudo=ver_tudo,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao carregar dados: {str(e)}', 'danger')
        cur.close()
        return redirect(url_for('main.index'))


@datas_importantes_bp.route("/criar", methods=["POST"])
@login_required
@requires_access('ferias')
def criar():
    """Cria um novo registro em datas_importantes."""
    d_usuario, email, tipo_usuario = _get_user_info()
    ver_tudo = _pode_ver_tudo(email, tipo_usuario)

    nome_data      = request.form.get('nome_data', '').strip()
    data_inicio    = request.form.get('data_inicio', '').strip()
    data_fim       = request.form.get('data_fim', '').strip() or None
    horario_inicio = request.form.get('horario_inicio', '').strip() or None
    horario_fim    = request.form.get('horario_fim', '').strip() or None
    observacoes    = request.form.get('observacoes', '').strip() or None

    if not nome_data or not data_inicio:
        flash('Tipo e data de início são obrigatórios.', 'danger')
        return redirect(url_for('datas_importantes.index'))

    # Se ver_tudo, permite registrar para outro usuário
    target_email     = email
    target_d_usuario = d_usuario
    target_tipo      = tipo_usuario
    if ver_tudo:
        para_email = request.form.get('para_usuario_email', '').strip()
        if para_email and para_email != email:
            cur_lu = get_cursor()
            cur_lu.execute(
                "SELECT d_usuario, tipo_usuario FROM gestao_pessoas.usuarios WHERE email = %s",
                (para_email,)
            )
            row_lu = cur_lu.fetchone()
            cur_lu.close()
            if row_lu:
                target_email     = para_email
                target_d_usuario = row_lu['d_usuario']
                target_tipo      = row_lu['tipo_usuario']

    cur = get_cursor()
    try:
        cur.execute("""
            INSERT INTO calendario.datas_importantes
                (nome_data, data_inicio, data_fim,
                 horario_inicio, horario_fim, observacoes,
                 d_usuario, usuario_email, tipo_usuario,
                 created_at, created_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
        """, (
            nome_data, data_inicio, data_fim,
            horario_inicio, horario_fim, observacoes,
            target_d_usuario, target_email, target_tipo,
            email
        ))
        get_db().commit()
        flash(f'{nome_data} registrado com sucesso!', 'success')

    except Exception as e:
        get_db().rollback()
        import traceback
        traceback.print_exc()
        flash(f'Erro ao registrar: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('datas_importantes.index'))


@datas_importantes_bp.route("/editar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def editar(id):
    """Edita um registro: dono ou usuário com ver_tudo."""
    d_usuario, email, tipo_usuario = _get_user_info()
    ver_tudo = _pode_ver_tudo(email, tipo_usuario)

    nome_data      = request.form.get('nome_data', '').strip()
    data_inicio    = request.form.get('data_inicio', '').strip()
    data_fim       = request.form.get('data_fim', '').strip() or None
    horario_inicio = request.form.get('horario_inicio', '').strip() or None
    horario_fim    = request.form.get('horario_fim', '').strip() or None
    observacoes    = request.form.get('observacoes', '').strip() or None

    if not nome_data or not data_inicio:
        flash('Tipo e data de início são obrigatórios.', 'danger')
        return redirect(url_for('datas_importantes.index'))

    cur = get_cursor()
    try:
        if ver_tudo:
            where_clause = "WHERE id = %s"
            params_update = (nome_data, data_inicio, data_fim, horario_inicio,
                             horario_fim, observacoes, email, id)
        else:
            where_clause = "WHERE id = %s AND usuario_email = %s"
            params_update = (nome_data, data_inicio, data_fim, horario_inicio,
                             horario_fim, observacoes, email, id, email)

        cur.execute(f"""
            UPDATE calendario.datas_importantes
            SET nome_data      = %s,
                data_inicio    = %s,
                data_fim       = %s,
                horario_inicio = %s,
                horario_fim    = %s,
                observacoes    = %s,
                updated_at     = NOW(),
                updated_por    = %s
            {where_clause}
        """, params_update)

        if cur.rowcount == 0:
            flash('Registro não encontrado ou sem permissão para editar.', 'warning')
        else:
            get_db().commit()
            flash('Registro atualizado com sucesso!', 'success')

    except Exception as e:
        get_db().rollback()
        import traceback
        traceback.print_exc()
        flash(f'Erro ao atualizar: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('datas_importantes.index'))


@datas_importantes_bp.route("/deletar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def deletar(id):
    """Remove um registro: dono ou usuário com ver_tudo."""
    d_usuario, email, tipo_usuario = _get_user_info()
    ver_tudo = _pode_ver_tudo(email, tipo_usuario)

    cur = get_cursor()
    try:
        if ver_tudo:
            cur.execute("SELECT nome_data FROM calendario.datas_importantes WHERE id = %s", (id,))
        else:
            cur.execute(
                "SELECT nome_data FROM calendario.datas_importantes WHERE id = %s AND usuario_email = %s",
                (id, email)
            )
        registro = cur.fetchone()

        if not registro:
            flash('Registro não encontrado ou sem permissão para excluir.', 'warning')
            cur.close()
            return redirect(url_for('datas_importantes.index'))

        if ver_tudo:
            cur.execute("DELETE FROM calendario.datas_importantes WHERE id = %s", (id,))
        else:
            cur.execute(
                "DELETE FROM calendario.datas_importantes WHERE id = %s AND usuario_email = %s",
                (id, email)
            )
        get_db().commit()
        flash(f'{registro["nome_data"]} excluído com sucesso!', 'success')

    except Exception as e:
        get_db().rollback()
        import traceback
        traceback.print_exc()
        flash(f'Erro ao excluir: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('datas_importantes.index'))


# ─────────────────────────────────────────────────────────────────────────────
# CRUD — calendario.datas_eventos (atividades/eventos institucionais)
# ─────────────────────────────────────────────────────────────────────────────

@datas_importantes_bp.route("/eventos/criar", methods=["POST"])
@login_required
@requires_access('ferias')
def criar_evento():
    """Cria um novo registro em datas_eventos."""
    d_usuario, email, tipo_usuario = _get_user_info()

    nome_atividade          = request.form.get('nome_atividade', '').strip()
    descritivo              = request.form.get('descritivo', '').strip() or None
    data_inicio             = request.form.get('data_inicio', '').strip() or None
    datas_adicionais        = request.form.get('datas_adicionais', '').strip() or None
    participacao            = request.form.get('participacao', '').strip() or None
    local                   = request.form.get('local', '').strip() or None
    necessita_infraestrutura = request.form.get('necessita_infraestrutura') == '1'
    valor_alimentacao       = request.form.get('valor_alimentacao', '').strip() or None
    alinhamento_aev         = request.form.get('alinhamento_aev') == '1'
    observacoes             = request.form.get('observacoes', '').strip() or None
    cancelado               = request.form.get('cancelado') == '1'

    # Responsáveis (listas paralelas)
    resp_nomes = request.form.getlist('responsavel_atividade[]')
    resp_tipos = request.form.getlist('responsavel_tipo[]')

    if not nome_atividade:
        flash('Nome da atividade é obrigatório.', 'danger')
        return redirect(url_for('datas_importantes.index') + '#tab-eventos')

    cur = get_cursor()
    try:
        cur.execute("""
            INSERT INTO calendario.datas_eventos
                (nome_atividade, descritivo, data_inicio, datas_adicionais,
                 participacao, local, necessita_infraestrutura,
                 valor_alimentacao, alinhamento_aev, observacoes, cancelado,
                 d_usuario, usuario_email, tipo_usuario,
                 created_at, created_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            RETURNING id
        """, (
            nome_atividade, descritivo, data_inicio, datas_adicionais,
            participacao, local, necessita_infraestrutura,
            valor_alimentacao, alinhamento_aev, observacoes, cancelado,
            d_usuario, email, tipo_usuario,
            email
        ))
        evento_id = cur.fetchone()['id']

        # Inserir responsáveis
        for nome_r, tipo_r in zip(resp_nomes, resp_tipos):
            nome_r = nome_r.strip()
            tipo_r = tipo_r.strip()
            if nome_r:
                cur.execute("""
                    INSERT INTO calendario.datas_eventos_responsaveis
                        (datas_evento_id, nome_atividade, responsavel_atividade, responsavel_tipo,
                         created_at, created_por)
                    VALUES (%s, %s, %s, %s, NOW(), %s)
                """, (evento_id, nome_atividade, nome_r, tipo_r or None, email))

        # Inserir documentos
        doc_nomes = request.form.getlist('doc_nome[]')
        doc_links = request.form.getlist('doc_link[]')
        for nome_d, link_d in zip(doc_nomes, doc_links):
            nome_d = sanitizar_nome_doc(nome_d)
            if nome_d:
                cur.execute("""
                    INSERT INTO calendario.datas_eventos_documentos
                        (datas_evento_id, nome_atividade, nome_doc, nome_doc_link,
                         created_at, created_por)
                    VALUES (%s, %s, %s, %s, NOW(), %s)
                """, (evento_id, nome_atividade, nome_d, link_d.strip() or None, email))

        get_db().commit()
        flash(f'Atividade "{nome_atividade}" registrada com sucesso!', 'success')

    except Exception as e:
        get_db().rollback()
        import traceback
        traceback.print_exc()
        flash(f'Erro ao registrar atividade: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('datas_importantes.index'))


@datas_importantes_bp.route("/eventos/editar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def editar_evento(id):
    """Edita um registro de datas_eventos do usuário logado."""
    _, email, tipo_usuario = _get_user_info()
    eh_gerente = tipo_usuario in ('Agente Público', 'admin')

    nome_atividade          = request.form.get('nome_atividade', '').strip()
    descritivo              = request.form.get('descritivo', '').strip() or None
    data_inicio             = request.form.get('data_inicio', '').strip() or None
    datas_adicionais        = request.form.get('datas_adicionais', '').strip() or None
    participacao            = request.form.get('participacao', '').strip() or None
    local                   = request.form.get('local', '').strip() or None
    necessita_infraestrutura = request.form.get('necessita_infraestrutura') == '1'
    valor_alimentacao       = request.form.get('valor_alimentacao', '').strip() or None
    alinhamento_aev         = request.form.get('alinhamento_aev') == '1'
    observacoes             = request.form.get('observacoes', '').strip() or None
    cancelado               = request.form.get('cancelado') == '1'

    resp_nomes = request.form.getlist('responsavel_atividade[]')
    resp_tipos = request.form.getlist('responsavel_tipo[]')

    if not nome_atividade:
        flash('Nome da atividade é obrigatório.', 'danger')
        return redirect(url_for('datas_importantes.index'))

    cur = get_cursor()
    try:
        # Agente Público pode editar qualquer evento
        where_extra = "" if eh_gerente else " AND usuario_email = %s"
        params_update = [
            nome_atividade, descritivo, data_inicio, datas_adicionais,
            participacao, local, necessita_infraestrutura,
            valor_alimentacao, alinhamento_aev, observacoes, cancelado,
            email, id
        ]
        if not eh_gerente:
            params_update.append(email)

        cur.execute(f"""
            UPDATE calendario.datas_eventos
            SET nome_atividade          = %s,
                descritivo              = %s,
                data_inicio             = %s,
                datas_adicionais        = %s,
                participacao            = %s,
                local                   = %s,
                necessita_infraestrutura = %s,
                valor_alimentacao       = %s,
                alinhamento_aev         = %s,
                observacoes             = %s,
                cancelado               = %s,
                updated_at              = NOW(),
                updated_por             = %s
            WHERE id = %s{where_extra}
        """, params_update)

        if cur.rowcount == 0:
            flash('Atividade não encontrada ou sem permissão para editar.', 'warning')
        else:
            # Substituir responsáveis
            cur.execute("DELETE FROM calendario.datas_eventos_responsaveis WHERE datas_evento_id = %s", (id,))
            for nome_r, tipo_r in zip(resp_nomes, resp_tipos):
                nome_r = nome_r.strip()
                tipo_r = tipo_r.strip()
                if nome_r:
                    cur.execute("""
                        INSERT INTO calendario.datas_eventos_responsaveis
                            (datas_evento_id, nome_atividade, responsavel_atividade, responsavel_tipo,
                             created_at, created_por)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                    """, (id, nome_atividade, nome_r, tipo_r or None, email))

            # Substituir documentos
            cur.execute("DELETE FROM calendario.datas_eventos_documentos WHERE datas_evento_id = %s", (id,))
            doc_nomes = request.form.getlist('doc_nome[]')
            doc_links = request.form.getlist('doc_link[]')
            for nome_d, link_d in zip(doc_nomes, doc_links):
                nome_d = sanitizar_nome_doc(nome_d)
                if nome_d:
                    cur.execute("""
                        INSERT INTO calendario.datas_eventos_documentos
                            (datas_evento_id, nome_atividade, nome_doc, nome_doc_link,
                             created_at, created_por)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                    """, (id, nome_atividade, nome_d, link_d.strip() or None, email))

            get_db().commit()
            flash('Atividade atualizada com sucesso!', 'success')

    except Exception as e:
        get_db().rollback()
        import traceback
        traceback.print_exc()
        flash(f'Erro ao atualizar atividade: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('datas_importantes.index'))


@datas_importantes_bp.route("/eventos/deletar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def deletar_evento(id):
    """Remove um registro de datas_eventos."""
    _, email, tipo_usuario = _get_user_info()
    eh_gerente = tipo_usuario in ('Agente Público', 'admin')

    cur = get_cursor()
    try:
        if eh_gerente:
            cur.execute("SELECT nome_atividade FROM calendario.datas_eventos WHERE id = %s", (id,))
        else:
            cur.execute(
                "SELECT nome_atividade FROM calendario.datas_eventos WHERE id = %s AND usuario_email = %s",
                (id, email)
            )
        registro = cur.fetchone()

        if not registro:
            flash('Atividade não encontrada ou sem permissão para excluir.', 'warning')
            cur.close()
            return redirect(url_for('datas_importantes.index'))

        if eh_gerente:
            cur.execute("DELETE FROM calendario.datas_eventos WHERE id = %s", (id,))
        else:
            cur.execute(
                "DELETE FROM calendario.datas_eventos WHERE id = %s AND usuario_email = %s",
                (id, email)
            )
        get_db().commit()
        flash(f'"{registro["nome_atividade"]}" excluída com sucesso!', 'success')

    except Exception as e:
        get_db().rollback()
        import traceback
        traceback.print_exc()
        flash(f'Erro ao excluir atividade: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('datas_importantes.index'))


# ─────────────────────────────────────────────────────────────────────────────
# Gerenciar acesso total a eventos (apenas Agente Público)
# ─────────────────────────────────────────────────────────────────────────────

@datas_importantes_bp.route("/acesso/toggle", methods=["POST"])
@login_required
@requires_access('ferias')
def toggle_acesso():
    """Alterna visualizar_todos_eventos para um usuário (apenas Agente Público)."""
    _, email, tipo_usuario = _get_user_info()
    if tipo_usuario not in ('Agente Público', 'admin'):
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('datas_importantes.index'))

    usuario_email = request.form.get('usuario_email', '').strip()
    novo_valor    = request.form.get('valor') == '1'

    cur = get_cursor()
    try:
        # Atualizar se já existe, senão inserir
        cur.execute(
            "UPDATE gestao_pessoas.usuarios_infos SET visualizar_todos_eventos = %s WHERE usuario_email = %s",
            (novo_valor, usuario_email)
        )
        if cur.rowcount == 0:
            cur.execute(
                "INSERT INTO gestao_pessoas.usuarios_infos (usuario_email, visualizar_todos_eventos) VALUES (%s, %s)",
                (usuario_email, novo_valor)
            )
        get_db().commit()
        flash(f'Acesso {"liberado" if novo_valor else "revogado"} com sucesso.', 'success')
    except Exception as e:
        get_db().rollback()
        flash(f'Erro ao atualizar acesso: {str(e)}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('datas_importantes.index') + '?aba=acesso')


# ─────────────────────────────────────────────────────────────────────────────
# CRUD — calendario.datas_eventos_responsaveis
# ─────────────────────────────────────────────────────────────────────────────

@datas_importantes_bp.route("/responsaveis/deletar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def deletar_responsavel(id):
    """Remove um responsável de um evento."""
    _, email, tipo_usuario = _get_user_info()
    cur = get_cursor()
    try:
        # Verificar ownership via evento
        cur.execute("""
            SELECT de.usuario_email, de.id AS evento_id
            FROM calendario.datas_eventos_responsaveis der
            JOIN calendario.datas_eventos de ON de.id = der.datas_evento_id
            WHERE der.id = %s
        """, (id,))
        row = cur.fetchone()
        if not row:
            flash('Responsável não encontrado.', 'warning')
        elif row['usuario_email'] != email and tipo_usuario not in ('Agente Público', 'admin'):
            flash('Sem permissão para remover este responsável.', 'danger')
        else:
            cur.execute("DELETE FROM calendario.datas_eventos_responsaveis WHERE id = %s", (id,))
            get_db().commit()
            flash('Responsável removido.', 'success')
    except Exception as e:
        get_db().rollback()
        flash(f'Erro: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('datas_importantes.index'))


@datas_importantes_bp.route("/eventos/documentos/deletar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def deletar_documento_evento(id):
    """Remove um documento vinculado a um evento."""
    _, email, tipo_usuario = _get_user_info()
    eh_gerente = tipo_usuario in ('Agente Público', 'admin')
    cur = get_cursor()
    try:
        cur.execute("""
            SELECT ded.id, de.usuario_email
            FROM calendario.datas_eventos_documentos ded
            JOIN calendario.datas_eventos de ON de.id = ded.datas_evento_id
            WHERE ded.id = %s
        """, (id,))
        row = cur.fetchone()
        if not row:
            flash('Documento não encontrado.', 'warning')
        elif row['usuario_email'] != email and not eh_gerente:
            flash('Sem permissão para remover este documento.', 'danger')
        else:
            cur.execute("DELETE FROM calendario.datas_eventos_documentos WHERE id = %s", (id,))
            get_db().commit()
            flash('Documento removido.', 'success')
    except Exception as e:
        get_db().rollback()
        flash(f'Erro: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('datas_importantes.index'))
