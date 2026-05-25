"""
Blueprint de Datas Importantes
Gerencia abonos, folgas, consultas médicas e eventos por usuário.
"""

import re
import os
import io
import uuid
import zipfile
import boto3
from botocore.client import Config
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access
from datetime import datetime
from werkzeug.utils import secure_filename


def sanitizar_nome_doc(nome):
    """Sanitiza nome para uso como nome de arquivo (chars inválidos removidos, espaços → _)."""
    nome = nome.strip()
    nome = re.sub(r'[\\/:*?"<>|]', '', nome)
    nome = re.sub(r'\s+', '_', nome)
    nome = re.sub(r'_+', '_', nome)
    return nome.strip('_') or 'documento'


# ─────────────────────────────────────────────────────── R2 helpers ──────────

_R2_ALLOWED_EXTS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
    '.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.rar', '.7z', '.txt', '.csv',
}


def _r2_client():
    return boto3.client(
        's3',
        endpoint_url=os.environ.get('R2_ENDPOINT_URL'),
        aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY'),
        config=Config(signature_version='s3v4'),
        region_name='auto',
    )


def _upload_r2(file_storage, evento_id):
    """Envia um FileStorage para R2. Retorna (nome_original, url_publica) ou (None, None)."""
    original = secure_filename(file_storage.filename or '')
    if not original:
        return None, None
    ext = os.path.splitext(original)[1].lower()
    if ext not in _R2_ALLOWED_EXTS:
        return None, None
    key = f"{evento_id}/{uuid.uuid4().hex}{ext}"
    _r2_client().upload_fileobj(
        file_storage,
        os.environ.get('R2_BUCKET_NAME', 'eventos'),
        key,
        ExtraArgs={'ContentType': file_storage.content_type or 'application/octet-stream'},
    )
    base = os.environ.get('R2_PUBLIC_BASE_URL', '').rstrip('/')
    return original, f"{base}/{key}"


def _delete_r2(url):
    """Remove um arquivo do R2 pela URL pública. Falha silenciosa se não for R2."""
    base = os.environ.get('R2_PUBLIC_BASE_URL', '').rstrip('/')
    if not url or not base or not url.startswith(base):
        return
    key = url[len(base):].lstrip('/')
    if not key:
        return
    try:
        _r2_client().delete_object(
            Bucket=os.environ.get('R2_BUCKET_NAME', 'eventos'),
            Key=key,
        )
    except Exception:
        pass


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
        feriados = []
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

            cur.execute("""
                SELECT id, data_feriado, nome_feriado, tipo_feriado, ativo
                FROM calendario.data_feriados
                ORDER BY data_feriado
            """)
            feriados = cur.fetchall()

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

        # Relatório de abonos
        ano_atual = datetime.now().year
        meus_abonos_ano = [
            r for r in registros_pessoais
            if r['nome_data'] == 'Abono'
            and r['data_inicio'] is not None
            and r['data_inicio'].year == ano_atual
            and r['usuario_email'] == email
        ]
        relatorio_abonos_todos = []
        if ver_tudo:
            cur2 = get_cursor()
            try:
                cur2.execute("""
                    SELECT u.email, COALESCE(ui.usuario_nome, u.email) AS usuario_nome
                    FROM gestao_pessoas.usuarios u
                    LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = u.email
                    WHERE u.tipo_usuario NOT IN ('admin')
                      AND COALESCE(ui.usuario_status, 'Ativo') = 'Ativo'
                    ORDER BY usuario_nome
                """)
                todos_usuarios = {
                    r['email']: {'nome': r['usuario_nome'], 'email': r['email'], 'abonos': []}
                    for r in cur2.fetchall()
                }
                cur2.execute("""
                    SELECT usuario_email, data_inicio, observacoes
                    FROM calendario.datas_importantes
                    WHERE nome_data = 'Abono'
                      AND EXTRACT(YEAR FROM data_inicio) = %s
                    ORDER BY usuario_email, data_inicio
                """, (ano_atual,))
                for row in cur2.fetchall():
                    if row['usuario_email'] in todos_usuarios:
                        todos_usuarios[row['usuario_email']]['abonos'].append({
                            'data': row['data_inicio'],
                            'obs': row['observacoes']
                        })
                relatorio_abonos_todos = list(todos_usuarios.values())
            finally:
                cur2.close()

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
            feriados=feriados,
            eh_gerente=eh_gerente,
            ver_tudo=ver_tudo,
            ano_atual=ano_atual,
            meus_abonos_ano=meus_abonos_ano,
            relatorio_abonos_todos=relatorio_abonos_todos,
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

        # Inserir links manuais
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

        # Upload de arquivos para R2
        arquivos_enviados = 0
        for f in request.files.getlist('arquivos[]'):
            if not f or not f.filename:
                continue
            nome_arq, url_arq = _upload_r2(f, evento_id)
            if nome_arq:
                cur.execute("""
                    INSERT INTO calendario.datas_eventos_documentos
                        (datas_evento_id, nome_atividade, nome_doc, nome_doc_link,
                         created_at, created_por)
                    VALUES (%s, %s, %s, %s, NOW(), %s)
                """, (evento_id, nome_atividade, nome_arq, url_arq, email))
                arquivos_enviados += 1

        get_db().commit()
        msg = f'Atividade "{nome_atividade}" registrada com sucesso!'
        if arquivos_enviados:
            msg += f' ({arquivos_enviados} arquivo(s) enviado(s) ao R2)'
        flash(msg, 'success')

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
    ver_tudo = _pode_ver_tudo(email, tipo_usuario)

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
        # Gerente ou ver_tudo pode editar qualquer evento
        where_extra = "" if ver_tudo else " AND usuario_email = %s"
        params_update = [
            nome_atividade, descritivo, data_inicio, datas_adicionais,
            participacao, local, necessita_infraestrutura,
            valor_alimentacao, alinhamento_aev, observacoes, cancelado,
            email, id
        ]
        if not ver_tudo:
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

            # Substituir links manuais (mantém R2 re-submetidos via doc_link)
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

            # Novos uploads para R2
            for f in request.files.getlist('arquivos[]'):
                if not f or not f.filename:
                    continue
                nome_arq, url_arq = _upload_r2(f, id)
                if nome_arq:
                    cur.execute("""
                        INSERT INTO calendario.datas_eventos_documentos
                            (datas_evento_id, nome_atividade, nome_doc, nome_doc_link,
                             created_at, created_por)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                    """, (id, nome_atividade, nome_arq, url_arq, email))

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
    ver_tudo = _pode_ver_tudo(email, tipo_usuario)

    cur = get_cursor()
    try:
        if ver_tudo:
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

        if ver_tudo:
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
            SELECT ded.id, ded.nome_doc_link, de.usuario_email
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
            _delete_r2(row.get('nome_doc_link'))
            cur.execute("DELETE FROM calendario.datas_eventos_documentos WHERE id = %s", (id,))
            get_db().commit()
            flash('Documento removido.', 'success')
    except Exception as e:
        get_db().rollback()
        flash(f'Erro: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('datas_importantes.index'))


# ─────────────────────────────────────────────────────── Download ZIP ───────

_ZIP_MAX_BYTES = 50 * 1024 * 1024  # 50 MB por parte


def _pasta_por_tipo(nome_doc):
    """Retorna a subpasta do ZIP com base na extensão do arquivo."""
    ext = os.path.splitext(nome_doc)[1].lower()
    if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'):
        return 'Fotos'
    if ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'):
        return 'Videos'
    if ext in ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv'):
        return 'Documentos'
    return 'Outros'


def _nome_unico_zip(nome, pasta, vistos):
    """Evita colisão de nomes dentro de uma pasta do ZIP."""
    chave = f"{pasta}/{nome}"
    if chave not in vistos:
        vistos.add(chave)
        return chave
    stem, ext = os.path.splitext(nome)
    i = 1
    while True:
        candidato = f"{pasta}/{stem}_{i}{ext}"
        if candidato not in vistos:
            vistos.add(candidato)
            return candidato
        i += 1


def _construir_zip(itens):
    """Recebe lista de {'arcname': str, 'content': bytes}. Retorna BytesIO do ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for item in itens:
            zf.writestr(item['arcname'], item['content'])
    buf.seek(0)
    return buf


@datas_importantes_bp.route("/eventos/<int:id>/download-zip", methods=["GET"])
@login_required
@requires_access('ferias')
def download_zip_evento(id):
    """
    Baixa todos os arquivos R2 de um evento como ZIP.
    - ≤ 50 MB  → NomeEvento.zip
    - > 50 MB  → NomeEvento_partes.zip (contém parte1.zip, parte2.zip …)
    """
    _, email, tipo_usuario = _get_user_info()
    ver_tudo = _pode_ver_tudo(email, tipo_usuario)

    cur = get_cursor()
    try:
        if ver_tudo:
            cur.execute(
                "SELECT nome_atividade FROM calendario.datas_eventos WHERE id = %s", (id,)
            )
        else:
            cur.execute(
                "SELECT nome_atividade FROM calendario.datas_eventos "
                "WHERE id = %s AND usuario_email = %s", (id, email)
            )
        evento = cur.fetchone()
        if not evento:
            flash('Evento não encontrado ou sem permissão.', 'danger')
            return redirect(url_for('datas_importantes.index'))

        nome_atividade = evento['nome_atividade']

        cur.execute("""
            SELECT nome_doc, nome_doc_link
            FROM calendario.datas_eventos_documentos
            WHERE datas_evento_id = %s
            ORDER BY id
        """, (id,))
        docs = cur.fetchall()
    finally:
        cur.close()

    if not docs:
        flash('Este evento não possui documentos para download.', 'warning')
        return redirect(url_for('datas_importantes.index'))

    # ── Baixar arquivos do R2 ──────────────────────────────────────────────
    r2     = _r2_client()
    base   = os.environ.get('R2_PUBLIC_BASE_URL', '').rstrip('/')
    bucket = os.environ.get('R2_BUCKET_NAME', 'eventos')

    partes   = []          # lista de partes; cada parte é lista de {arcname, content}
    parte_atual = []
    tamanho_atual = 0

    for doc in docs:
        nome = doc['nome_doc'] or 'arquivo'
        url  = doc['nome_doc_link'] or ''

        # Somente arquivos R2
        if not (url and base and url.startswith(base)):
            continue
        key = url[len(base):].lstrip('/')
        try:
            resp    = r2.get_object(Bucket=bucket, Key=key)
            content = resp['Body'].read()
        except Exception:
            continue  # arquivo inacessível — pula

        pasta   = _pasta_por_tipo(nome)
        tamanho = len(content)

        # Nova parte se ultrapassar o limite (e já houver algo na parte atual)
        if parte_atual and (tamanho_atual + tamanho) > _ZIP_MAX_BYTES:
            partes.append(parte_atual)
            parte_atual   = []
            tamanho_atual = 0

        vistos_nesta_parte = {item['arcname'] for item in parte_atual}
        arcname = _nome_unico_zip(nome, pasta, vistos_nesta_parte)
        parte_atual.append({'arcname': arcname, 'content': content})
        tamanho_atual += tamanho

    if parte_atual:
        partes.append(parte_atual)

    if not partes:
        flash('Nenhum arquivo R2 encontrado para este evento.', 'warning')
        return redirect(url_for('datas_importantes.index'))

    nome_base = sanitizar_nome_doc(nome_atividade)

    # ── Gerar resposta ─────────────────────────────────────────────────────
    if len(partes) == 1:
        buf = _construir_zip(partes[0])
        return send_file(
            buf,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{nome_base}.zip",
        )

    # Múltiplas partes → ZIP externo contendo os ZIPs internos
    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, 'w', zipfile.ZIP_STORED) as outer_zf:
        for i, parte in enumerate(partes, 1):
            inner_buf = _construir_zip(parte)
            outer_zf.writestr(f"{nome_base}_parte{i}.zip", inner_buf.read())
    outer_buf.seek(0)
    return send_file(
        outer_buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{nome_base}_partes.zip",
    )


# ─────────────────────────────────────────────────────────── Feriados ──────

@datas_importantes_bp.route("/feriados/criar", methods=["POST"])
@login_required
@requires_access('ferias')
def feriados_criar():
    """Cria um novo feriado. Exclusivo para gerentes."""
    _, email, tipo_usuario = _get_user_info()
    if tipo_usuario not in ('Agente Público', 'admin'):
        flash('Sem permissão.', 'danger')
        return redirect(url_for('datas_importantes.index'))

    data = request.form.get('data_feriado', '').strip()
    nome = request.form.get('nome_feriado', '').strip()
    tipo = request.form.get('tipo_feriado', 'municipal').strip()
    ativo = request.form.get('ativo', '1') == '1'

    if not data or not nome:
        flash('Data e nome são obrigatórios.', 'warning')
        return redirect(url_for('datas_importantes.index') + '#tab-feriados')

    cur = get_cursor()
    try:
        cur.execute("""
            INSERT INTO calendario.data_feriados (data_feriado, nome_feriado, tipo_feriado, ativo)
            VALUES (%s, %s, %s, %s)
        """, (data, nome, tipo, ativo))
        get_db().commit()
        flash('Feriado criado com sucesso.', 'success')
    except Exception as e:
        get_db().rollback()
        flash(f'Erro: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('datas_importantes.index') + '#tab-feriados')


@datas_importantes_bp.route("/feriados/editar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def feriados_editar(id):
    """Edita um feriado existente. Exclusivo para gerentes."""
    _, email, tipo_usuario = _get_user_info()
    if tipo_usuario not in ('Agente Público', 'admin'):
        flash('Sem permissão.', 'danger')
        return redirect(url_for('datas_importantes.index'))

    data = request.form.get('data_feriado', '').strip()
    nome = request.form.get('nome_feriado', '').strip()
    tipo = request.form.get('tipo_feriado', 'municipal').strip()
    ativo = request.form.get('ativo', '1') == '1'

    if not data or not nome:
        flash('Data e nome são obrigatórios.', 'warning')
        return redirect(url_for('datas_importantes.index') + '#tab-feriados')

    cur = get_cursor()
    try:
        cur.execute("""
            UPDATE calendario.data_feriados
            SET data_feriado = %s, nome_feriado = %s, tipo_feriado = %s, ativo = %s
            WHERE id = %s
        """, (data, nome, tipo, ativo, id))
        get_db().commit()
        flash('Feriado atualizado.', 'success')
    except Exception as e:
        get_db().rollback()
        flash(f'Erro: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('datas_importantes.index') + '#tab-feriados')


@datas_importantes_bp.route("/feriados/deletar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def feriados_deletar(id):
    """Remove um feriado. Exclusivo para gerentes."""
    _, email, tipo_usuario = _get_user_info()
    if tipo_usuario not in ('Agente Público', 'admin'):
        flash('Sem permissão.', 'danger')
        return redirect(url_for('datas_importantes.index'))

    cur = get_cursor()
    try:
        cur.execute("DELETE FROM calendario.data_feriados WHERE id = %s", (id,))
        get_db().commit()
        flash('Feriado removido.', 'success')
    except Exception as e:
        get_db().rollback()
        flash(f'Erro: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('datas_importantes.index') + '#tab-feriados')

