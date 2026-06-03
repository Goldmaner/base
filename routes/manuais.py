"""
Blueprint de Biblioteca Informativa Operacionais
Rotas: listagem, criação, detalhamento, versionamento e upload de documentos.
"""

import os
from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, session, send_file, abort)
from werkzeug.utils import secure_filename
from db import get_cursor
from utils import login_required
from decorators import requires_access, requires_write_access
import utils_storage as storage

manuais_bp = Blueprint('manuais', __name__, url_prefix='/manuais')

# Pasta base para upload de arquivos (relativa à raiz do projeto)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(_BASE_DIR, 'modelos', 'Manuais')

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'png', 'jpg', 'jpeg', 'odt', 'ods'
}

# Ordem fixa das áreas para exibição agrupada
AREAS_ORDEM = [
    'Operações Gerais da Unidade (Compartilhadas)',
    'Departamento de Parcerias (DP)',
    'Divisão de Gestão de Parcerias (DGP)',
    'Divisão de Análise de Contas (DAC)',
]

AREAS_COR = {
    'Operações Gerais da Unidade (Compartilhadas)': {
        'from': '#1e3a5f', 'to': '#2563eb', 'shadow': 'rgba(37,99,235,.25)'
    },
    'Departamento de Parcerias (DP)': {
        'from': '#78350f', 'to': '#d97706', 'shadow': 'rgba(217,119,6,.25)'
    },
    'Divisão de Gestão de Parcerias (DGP)': {
        'from': '#312e81', 'to': '#4f46e5', 'shadow': 'rgba(79,70,229,.25)'
    },
    'Divisão de Análise de Contas (DAC)': {
        'from': '#065f46', 'to': '#059669', 'shadow': 'rgba(5,150,105,.25)'
    },
}


def _allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)


def _get_status_opcoes(cur):
    cur.execute("""
        SELECT status_manuais
        FROM categoricas.c_geral_status_documentos
        ORDER BY status_manuais
    """)
    return [r['status_manuais'] for r in cur.fetchall()]


def _get_tipos_doc_opcoes(cur):
    try:
        cur.execute("""
            SELECT tipos_documentos
            FROM categoricas.c_geral_tipos_documentos_manuais
            ORDER BY tipos_documentos
        """)
        return [r['tipos_documentos'] for r in cur.fetchall()]
    except Exception:
        cur.connection.rollback()
        return [
            'Checklist',
            'Fluxograma',
            'Formulário',
            'Guia Rápido',
            'Instrução Normativa',
            'Manual Operacional',
            'Procedimento Interno',
            'Protocolo',
            'Relatório Técnico',
            'Template / Modelo',
        ]


def _save_upload(arquivo, manual_id):
    """Salva o arquivo enviado via storage (local ou Supabase) e retorna o caminho relativo ou None."""
    if not arquivo or not arquivo.filename:
        return None
    if not _allowed_file(arquivo.filename):
        return None
    filename = secure_filename(arquivo.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    content_types = {
        'pdf': 'application/pdf',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xls': 'application/vnd.ms-excel',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'doc': 'application/msword',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'ppt': 'application/vnd.ms-powerpoint',
        'txt': 'text/plain',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'odt': 'application/vnd.oasis.opendocument.text',
        'ods': 'application/vnd.oasis.opendocument.spreadsheet',
    }
    content_type = content_types.get(ext, 'application/octet-stream')
    storage_path = f'Manuais/{manual_id}/{filename}'
    file_bytes = arquivo.read()
    storage.upload_file(storage_path, file_bytes, content_type)
    # Retorna caminho compatível com registros antigos no banco (prefixo modelos/)
    return f'modelos/Manuais/{manual_id}/{filename}'


# ─────────────────────────────────────────────────────────────
# LISTAGEM
# ─────────────────────────────────────────────────────────────

@manuais_bp.route('/', methods=['GET'])
@login_required
@requires_access('manuais')
def index():
    cur = get_cursor()
    cur.execute("""
        SELECT id, manual_tipo, manual_nome, manual_status,
               manual_relacionamento, manual_descricao, manual_area
        FROM public.manuais_lista
        ORDER BY manual_area, manual_nome
    """)
    manuais_raw = cur.fetchall()

    # Contagem de documentos por manual
    cur.execute("""
        SELECT manual_id, COUNT(*) AS total
        FROM public.manuais_documentos
        GROUP BY manual_id
    """)
    doc_counts = {r['manual_id']: r['total'] for r in cur.fetchall()}

    status_opcoes = _get_status_opcoes(cur)
    cur.close()

    areas = {area: [] for area in AREAS_ORDEM}
    for m in manuais_raw:
        area = m['manual_area'] or 'Outras'
        if area not in areas:
            areas[area] = []
        row = dict(m)
        row['doc_count'] = doc_counts.get(m['id'], 0)
        areas[area].append(row)
    areas = {k: v for k, v in areas.items() if v}

    return render_template(
        'Manuais/manuais.html',
        areas=areas,
        areas_cor=AREAS_COR,
        status_opcoes=status_opcoes,
        areas_ordem=AREAS_ORDEM,
    )


# ─────────────────────────────────────────────────────────────
# CRIAR NOVO CARD (manual na manuais_lista)
# ─────────────────────────────────────────────────────────────

@manuais_bp.route('/criar', methods=['POST'])
@login_required
@requires_access('manuais')
@requires_write_access('manuais')
def criar():
    area     = request.form.get('manual_area', '').strip()
    nome     = request.form.get('manual_nome', '').strip()
    tipo     = request.form.get('manual_tipo', 'Operação').strip()
    status   = request.form.get('manual_status', '').strip() or None
    descricao = request.form.get('manual_descricao', '').strip() or None

    if not nome or not area:
        flash('Nome e área são obrigatórios.', 'danger')
        return redirect(url_for('manuais.index'))

    cur = get_cursor()
    try:
        cur.execute("""
            INSERT INTO public.manuais_lista
                (manual_nome, manual_tipo, manual_status, manual_descricao, manual_area)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (nome, tipo, status, descricao, area))
        new_id = cur.fetchone()['id']
        cur.connection.commit()
        flash(f'Procedimento "{nome}" criado com sucesso.', 'success')
        return redirect(url_for('manuais.detalhe', manual_id=new_id))
    except Exception as e:
        cur.connection.rollback()
        flash(f'Erro ao criar procedimento: {str(e)}', 'danger')
        return redirect(url_for('manuais.index'))
    finally:
        cur.close()


# ─────────────────────────────────────────────────────────────
# DETALHAMENTO
# ─────────────────────────────────────────────────────────────

@manuais_bp.route('/detalhe/<int:manual_id>', methods=['GET'])
@login_required
@requires_access('manuais')
def detalhe(manual_id):
    cur = get_cursor()
    cur.execute("SELECT * FROM public.manuais_lista WHERE id = %s", (manual_id,))
    manual = cur.fetchone()
    if not manual:
        cur.close()
        flash('Procedimento não encontrado.', 'danger')
        return redirect(url_for('manuais.index'))

    cur.execute("""
        SELECT * FROM public.manuais_documentos
        WHERE manual_id = %s
        ORDER BY criado_em DESC
    """, (manual_id,))
    versoes = cur.fetchall()
    status_opcoes = _get_status_opcoes(cur)
    tipos_doc_opcoes = _get_tipos_doc_opcoes(cur)
    cur.close()

    cor = AREAS_COR.get(manual['manual_area'], AREAS_COR[AREAS_ORDEM[0]])

    return render_template(
        'Manuais/manuais_detalhamento.html',
        manual=dict(manual),
        versoes=[dict(v) for v in versoes],
        status_opcoes=status_opcoes,
        tipos_doc_opcoes=tipos_doc_opcoes,
        cor=cor,
    )


# ─────────────────────────────────────────────────────────────
# ATUALIZAR DESCRIÇÃO CENTRAL
# ─────────────────────────────────────────────────────────────

@manuais_bp.route('/detalhe/<int:manual_id>/descricao', methods=['POST'])
@login_required
@requires_access('manuais')
@requires_write_access('manuais')
def atualizar_descricao(manual_id):
    descricao = request.form.get('manual_descricao', '').strip() or None
    cur = get_cursor()
    try:
        cur.execute(
            "UPDATE public.manuais_lista SET manual_descricao = %s WHERE id = %s",
            (descricao, manual_id)
        )
        cur.connection.commit()
        flash('Descrição atualizada com sucesso.', 'success')
    except Exception as e:
        cur.connection.rollback()
        flash(f'Erro ao atualizar descrição: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('manuais.detalhe', manual_id=manual_id))


# ─────────────────────────────────────────────────────────────
# TOGGLE META
# ─────────────────────────────────────────────────────────────

@manuais_bp.route('/detalhe/<int:manual_id>/toggle_meta', methods=['POST'])
@login_required
@requires_access('manuais')
@requires_write_access('manuais')
def toggle_meta(manual_id):
    cur = get_cursor()
    try:
        cur.execute("SELECT manual_status FROM public.manuais_lista WHERE id = %s", (manual_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            flash('Manual não encontrado.', 'danger')
            return redirect(url_for('manuais.index'))
        novo_status = None if row['manual_status'] == 'Meta' else 'Meta'
        cur.execute(
            "UPDATE public.manuais_lista SET manual_status = %s WHERE id = %s",
            (novo_status, manual_id)
        )
        cur.connection.commit()
    except Exception as e:
        cur.connection.rollback()
        flash(f'Erro ao alterar status: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('manuais.detalhe', manual_id=manual_id))


# ─────────────────────────────────────────────────────────────
# VERSÕES — CRIAR
# ─────────────────────────────────────────────────────────────

@manuais_bp.route('/detalhe/<int:manual_id>/versao/nova', methods=['POST'])
@login_required
@requires_access('manuais')
@requires_write_access('manuais')
def criar_versao(manual_id):
    nome         = request.form.get('manual_nome', '').strip()
    versionamento = request.form.get('manual_versionamento', '').strip() or None
    status        = request.form.get('manual_status', '').strip() or None
    descricao     = request.form.get('manual_descricao', '').strip() or None
    pendencias    = request.form.get('manual_pendencias', '').strip() or None
    links_raw     = request.form.getlist('manual_link')
    link          = ';'.join(l.strip() for l in links_raw if l.strip()) or None
    tipo_doc      = request.form.get('tipo_doc', '').strip() or None
    publico_alvo_list = request.form.getlist('publico_alvo')
    publico_alvo  = ';'.join(publico_alvo_list) if publico_alvo_list else None
    usuario       = session.get('d_usuario') or session.get('email', 'Sistema')

    if not nome:
        flash('O nome do manual é obrigatório.', 'danger')
        return redirect(url_for('manuais.detalhe', manual_id=manual_id))

    doc_path = _save_upload(request.files.get('manual_doc'), manual_id)

    cur = get_cursor()
    try:
        cur.execute("""
            INSERT INTO public.manuais_documentos
                (manual_id, manual_nome, manual_versionamento, manual_status,
                 manual_descricao, manual_pendencias, manual_doc, manual_link,
                 tipo_doc, publico_alvo,
                 criado_por, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (manual_id, nome, versionamento, status,
              descricao, pendencias, doc_path, link, tipo_doc, publico_alvo, usuario))
        cur.connection.commit()
        flash('Versão adicionada com sucesso.', 'success')
    except Exception as e:
        cur.connection.rollback()
        flash(f'Erro ao criar versão: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('manuais.detalhe', manual_id=manual_id))


# ─────────────────────────────────────────────────────────────
# VERSÕES — EDITAR
# ─────────────────────────────────────────────────────────────

@manuais_bp.route('/versao/<int:versao_id>/editar', methods=['POST'])
@login_required
@requires_access('manuais')
@requires_write_access('manuais')
def editar_versao(versao_id):
    cur = get_cursor()
    cur.execute("SELECT manual_id, manual_doc FROM public.manuais_documentos WHERE id = %s",
                (versao_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        flash('Versão não encontrada.', 'danger')
        return redirect(url_for('manuais.index'))

    manual_id    = row['manual_id']
    nome         = request.form.get('manual_nome', '').strip()
    versionamento = request.form.get('manual_versionamento', '').strip() or None
    status        = request.form.get('manual_status', '').strip() or None
    descricao     = request.form.get('manual_descricao', '').strip() or None
    pendencias    = request.form.get('manual_pendencias', '').strip() or None
    links_raw     = request.form.getlist('manual_link')
    link          = ';'.join(l.strip() for l in links_raw if l.strip()) or None
    tipo_doc      = request.form.get('tipo_doc', '').strip() or None
    publico_alvo_list = request.form.getlist('publico_alvo')
    publico_alvo  = ';'.join(publico_alvo_list) if publico_alvo_list else None
    usuario       = session.get('d_usuario') or session.get('email', 'Sistema')

    if not nome:
        cur.close()
        flash('O nome do manual é obrigatório.', 'danger')
        return redirect(url_for('manuais.detalhe', manual_id=manual_id))

    # Processar novo upload (mantém doc anterior se não enviado novo)
    novo_doc = _save_upload(request.files.get('manual_doc'), manual_id)
    doc_path = novo_doc if novo_doc else row['manual_doc']

    try:
        cur.execute("""
            UPDATE public.manuais_documentos
            SET manual_nome = %s, manual_versionamento = %s, manual_status = %s,
                manual_descricao = %s, manual_pendencias = %s,
                manual_doc = %s, manual_link = %s,
                tipo_doc = %s, publico_alvo = %s,
                atualizado_por = %s, atualizado_em = NOW()
            WHERE id = %s
        """, (nome, versionamento, status, descricao, pendencias, doc_path, link,
              tipo_doc, publico_alvo, usuario, versao_id))
        cur.connection.commit()
        flash('Versão atualizada com sucesso.', 'success')
    except Exception as e:
        cur.connection.rollback()
        flash(f'Erro ao atualizar versão: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('manuais.detalhe', manual_id=manual_id))


# ─────────────────────────────────────────────────────────────
# VERSÕES — DELETAR
# ─────────────────────────────────────────────────────────────

@manuais_bp.route('/versao/<int:versao_id>/deletar', methods=['POST'])
@login_required
@requires_access('manuais')
@requires_write_access('manuais')
def deletar_versao(versao_id):
    manual_id = request.form.get('manual_id', type=int)
    cur = get_cursor()
    try:
        cur.execute("DELETE FROM public.manuais_documentos WHERE id = %s", (versao_id,))
        cur.connection.commit()
        flash('Versão removida.', 'success')
    except Exception as e:
        cur.connection.rollback()
        flash(f'Erro ao remover versão: {str(e)}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('manuais.detalhe', manual_id=manual_id))


# ─────────────────────────────────────────────────────────────
# DOWNLOAD DE DOCUMENTO ANEXO
# ─────────────────────────────────────────────────────────────

@manuais_bp.route('/versao/<int:versao_id>/download', methods=['GET'])
@login_required
@requires_access('manuais')
def download_doc(versao_id):
    cur = get_cursor()
    cur.execute("SELECT manual_doc, manual_nome FROM public.manuais_documentos WHERE id = %s",
                (versao_id,))
    row = cur.fetchone()
    cur.close()

    if not row or not row['manual_doc']:
        abort(404)

    # DB pode ter 'modelos/Manuais/{id}/{file}' (antigo) ou 'Manuais/{id}/{file}'
    # storage espera sem o prefixo 'modelos/'
    doc_path = row['manual_doc'].replace('\\', '/')
    if doc_path.startswith('modelos/'):
        storage_path = doc_path[len('modelos/'):]
    else:
        storage_path = doc_path

    try:
        file_bytes = storage.download_file(storage_path)
    except FileNotFoundError:
        abort(404)

    import io as _io
    return send_file(
        _io.BytesIO(file_bytes),
        as_attachment=True,
        download_name=os.path.basename(doc_path),
    )
