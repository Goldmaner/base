"""
Blueprint do Email Assistente.

Permite que usuários administrativos leiam e recebam resumos automáticos
dos emails recebidos via Outlook COM Automation (sem senha/IMAP).

Acesso: apenas usuários do tipo 'Agente Público' (is_admin).
"""

from flask import (
    render_template, jsonify, request,
    session, redirect, url_for, flash
)
from utils import login_required
from .email_reader import listar_emails, testar_conexao_imap, listar_pastas, listar_compromissos
from .ia_resumo import resumir_lote, testar_api
from . import email_assistente_bp


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _apenas_admin() -> bool:
    return session.get('tipo_usuario') == 'Agente Público'


# ─── Rotas ────────────────────────────────────────────────────────────────────

@email_assistente_bp.route('/')
@login_required
def index():
    if not _apenas_admin():
        flash('Acesso restrito a administradores.', 'danger')
        return redirect(url_for('main.index'))
    return render_template('email_assistente/index.html')


@email_assistente_bp.route('/testar-credenciais', methods=['POST'])
@login_required
def testar_credenciais():
    """Testa se o Outlook local está acessível via COM."""
    if not _apenas_admin():
        return jsonify({'error': 'Acesso negado'}), 403
    try:
        testar_conexao_imap()
        return jsonify({'ok': True, 'mensagem': 'Outlook conectado com sucesso.'})
    except Exception as e:
        return jsonify({'ok': False, 'mensagem': f'Falha na conexão: {e}'})


@email_assistente_bp.route('/emails-hoje', methods=['GET'])
@login_required
def emails_hoje():
    """Busca emails da Inbox, resume com IA e retorna JSON.
    Query param: dias (int, default 0 = hoje)
    """
    if not _apenas_admin():
        return jsonify({'error': 'Acesso negado'}), 403

    dias = int(request.args.get('dias', 0))

    try:
        emails = listar_emails(dias=dias, limite=50)
    except Exception as e:
        return jsonify({'error': f'Erro ao acessar Outlook: {e}'}), 500

    if not emails:
        return jsonify({'emails': [], 'total': 0, 'resumidos': 0})

    emails_resumidos = resumir_lote(emails)

    return jsonify({
        'emails': emails_resumidos,
        'total': len(emails_resumidos),
        'resumidos': sum(1 for e in emails_resumidos if 'ia' in e),
    })


@email_assistente_bp.route('/testar-ia', methods=['GET'])
@login_required
def testar_ia():
    """Testa a conexão com a API de IA."""
    if not _apenas_admin():
        return jsonify({'error': 'Acesso negado'}), 403
    return jsonify(testar_api())


@email_assistente_bp.route('/pastas', methods=['GET'])
@login_required
def listar_pastas_email():
    """Lista pastas disponíveis na Inbox."""
    if not _apenas_admin():
        return jsonify({'error': 'Acesso negado'}), 403
    try:
        return jsonify({'pastas': listar_pastas()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@email_assistente_bp.route('/calendario', methods=['GET'])
@login_required
def calendario():
    """Retorna compromissos do calendário nos próximos N dias (default 7)."""
    if not _apenas_admin():
        return jsonify({'error': 'Acesso negado'}), 403
    dias = int(request.args.get('dias', 7))
    try:
        compromissos = listar_compromissos(dias=dias)
        return jsonify({'compromissos': compromissos, 'total': len(compromissos)})
    except Exception as e:
        return jsonify({'error': f'Erro ao acessar calendário: {e}'}), 500

