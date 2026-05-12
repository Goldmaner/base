"""
Blueprint do Email Assistente.

Permite que usuários administrativos leiam e recebam resumos automáticos
dos emails recebidos via Outlook COM Automation (sem senha/IMAP).

Acesso: apenas usuários do tipo 'Agente Público' (is_admin).
"""

import os
import json
import tempfile
from flask import (
    render_template, jsonify, request,
    session, redirect, url_for, flash,
    Response, stream_with_context
)
from werkzeug.utils import secure_filename
from utils import login_required
from .email_reader import listar_emails, testar_conexao_imap, listar_pastas, listar_compromissos
from .ia_resumo import resumir_lote, testar_api
from . import email_assistente_bp

# Extensões de áudio aceitas
_AUDIO_EXTS = {'.mp3', '.mp4', '.m4a', '.wav', '.ogg', '.flac', '.webm', '.mpeg'}

# Modelo Whisper carregado uma única vez (lazy)
_whisper_model = None

def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper_model


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


@email_assistente_bp.route('/transcrever', methods=['POST'])
@login_required
def transcrever_audio():
    """Transcreve um arquivo de áudio via SSE — envia progresso % em tempo real."""
    if not _apenas_admin():
        return jsonify({'error': 'Acesso negado'}), 403

    if 'audio' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400

    arquivo = request.files['audio']
    if not arquivo.filename:
        return jsonify({'error': 'Nome de arquivo inválido.'}), 400

    ext = os.path.splitext(secure_filename(arquivo.filename))[1].lower()
    if ext not in _AUDIO_EXTS:
        return jsonify({'error': f'Formato não suportado: {ext}. Use mp3, wav, m4a, ogg, flac ou webm.'}), 400

    # Salva o arquivo ANTES do generator (fora do contexto de stream)
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    arquivo.save(tmp)
    tmp_path = tmp.name
    tmp.close()

    def _stream(path):
        try:
            model = _get_whisper_model()
            segments, info = model.transcribe(path, beam_size=5, language="pt")
            duracao = max(info.duration, 0.001)
            partes = []
            for seg in segments:
                partes.append(seg.text.strip())
                pct = min(int(seg.end / duracao * 100), 99)
                yield f"data: {json.dumps({'pct': pct, 'parcial': ' '.join(partes)})}\n\n"
            yield f"data: {json.dumps({'pct': 100, 'done': True, 'texto': ' '.join(partes), 'idioma': info.language, 'duracao': round(info.duration, 1)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if os.path.exists(path):
                os.remove(path)

    return Response(
        stream_with_context(_stream(tmp_path)),
        mimetype='text/event-stream',
        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'},
    )

