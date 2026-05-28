"""
Classificação Processual — analisa PDFs enviados via DeepSeek e classifica
cada página (ou bloco coerente) por tipo de documento.

Arquitetura de concorrência
───────────────────────────
• Triagem de PDF     → SSE streaming  (só leitura de PDF, rápido, sem API externa)
• Classificação IA   → background thread + polling
• Dividir+Classificar→ background thread + polling

O padrão de polling evita ERR_CONNECTION_RESET do Werkzeug dev-server no Windows,
que ocorre quando a resposta fica muito tempo sem enviar bytes (DeepSeek leva 60-120 s).
"""

import io
import os
import json
import time as _time
import traceback as _tb
import uuid
import zipfile
import threading
import requests
import pdfplumber
from flask import Blueprint, request, jsonify, session, send_file, Response, stream_with_context
from functools import wraps
from decorators import requires_access
from PyPDF2 import PdfReader, PdfWriter

# ── OCR opcional ──────────────────────────────────────────────────────────────
try:
    import pytesseract
    from pdf2image import convert_from_bytes

    _tesseract_cmd = os.environ.get('TESSERACT_CMD', '')
    if _tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

    _POPPLER_PATH = os.environ.get('POPPLER_PATH', '') or None
    _OCR_DISPONIVEL = True
except ImportError:
    _OCR_DISPONIVEL = False
    _POPPLER_PATH   = None

bp = Blueprint('conc_classificacao', __name__, url_prefix='/conc_banc')

_DEEPSEEK_URL    = 'https://api.deepseek.com/v1/chat/completions'
_DEEPSEEK_MODEL  = 'deepseek-chat'
_MIN_CHARS_PAGINA = 50
_MAX_CHARS_PROMPT = 120_000
_MAX_PAGINAS_DIRETO = 80   # acima disso, sugere usar Triagem para dividir primeiro

# ── Armazenamento de tarefas em memória ──────────────────────────────────────
# Formato: {task_id: {status, pct, label, resultado, erro, criada_em}}
_tarefas: dict = {}
_tarefas_lock   = threading.Lock()
_TAREFA_TTL_S   = 1800   # 30 min — limpa tarefas antigas


def _nova_tarefa() -> str:
    tid = str(uuid.uuid4())
    with _tarefas_lock:
        # Limpa tarefas velhas ao criar uma nova (evita vazamento de memória)
        agora = _time.time()
        expiradas = [k for k, v in _tarefas.items()
                     if agora - v.get('criada_em', agora) > _TAREFA_TTL_S]
        for k in expiradas:
            del _tarefas[k]

        _tarefas[tid] = {
            'status':    'running',
            'pct':       0,
            'label':     'Iniciando...',
            'resultado': None,
            'erro':      None,
            'criada_em': agora,
        }
    return tid


def _atualizar(tid: str, **kwargs):
    with _tarefas_lock:
        if tid in _tarefas:
            _tarefas[tid].update(kwargs)


# ── Autenticação ──────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Sessão expirada'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ── Extração de texto ─────────────────────────────────────────────────────────

def _extrair_texto_pagina(pagina_plumber, pagina_bytes=None, num_pagina=0):
    """pdfplumber primeiro; pytesseract/pdf2image como fallback."""
    texto = (pagina_plumber.extract_text() or '').strip()
    if len(texto) >= _MIN_CHARS_PAGINA:
        return texto

    if _OCR_DISPONIVEL and pagina_bytes:
        try:
            imagens = convert_from_bytes(
                pagina_bytes,
                first_page=num_pagina,
                last_page=num_pagina,
                dpi=200,
                poppler_path=_POPPLER_PATH,
            )
            if imagens:
                langs_disp = pytesseract.get_languages()
                lang = 'por+eng' if 'por' in langs_disp else 'eng'
                ocr_texto = pytesseract.image_to_string(imagens[0], lang=lang).strip()
                return ocr_texto or texto
        except Exception as ocr_err:
            print(f'[CLASSIF OCR] Falha pág {num_pagina}: {ocr_err}')

    return texto


# ── Triagem (detecção de quebras sem IA) ─────────────────────────────────────

_PALAVRAS_CABECALHO = [
    'nota fiscal', 'nf-e', 'nfs-e', 'danfe', 'cupom fiscal',
    'recibo de pagamento', 'recibo ',
    'comprovante de transferência', 'comprovante de pagamento', 'ted ', ' pix',
    'contrato de prestação', 'contrato de serviços', 'contrato ',
    'guia de recolhimento', 'guia darf', 'gps -', 'darf ',
    'folha de pagamento', 'holerite', 'contra-cheque', 'contracheque',
    'certidão', 'certidao', 'atestado de',
    'ata de reunião', 'ata de', 'procuração',
    'relatório de atividades', 'relatório mensal', 'prestação de contas',
    'extrato bancário', 'extrato de conta',
    'declaração ',
]


def _detectar_tipo_cabecalho(texto_inicio):
    t = texto_inicio[:300].lower()
    for kw in _PALAVRAS_CABECALHO:
        if kw in t:
            return kw.strip().title()
    return None


def _cor_barra(chars):
    if chars >= 500: return '#198754'
    if chars >= 300: return '#5cb85c'
    if chars >= 150: return '#b8a800'
    if chars >= 50:  return '#fd7e14'
    if chars >= 20:  return '#e86c00'
    return '#dc3545'


# ── Prompt e chamada DeepSeek ─────────────────────────────────────────────────

def _montar_prompt(paginas, nome_arquivo, numero_termo=None):
    ctx_termo = f' do termo de parceria {numero_termo}' if numero_termo else ''
    blocos_lista, chars_acumulados, truncado_em = [], 0, None

    for p in paginas:
        bloco = f'[Página {p["pagina"]}]\n{p["texto"] or "(sem texto extraído)"}'
        if chars_acumulados + len(bloco) > _MAX_CHARS_PROMPT:
            truncado_em = p['pagina']
            break
        blocos_lista.append(bloco)
        chars_acumulados += len(bloco)

    blocos = '\n\n'.join(blocos_lista)
    aviso  = (f'\n\n[AVISO: documento truncado — páginas {truncado_em} em diante omitidas]'
              if truncado_em else '')

    return f"""Você é especialista em análise de prestação de contas de convênios públicos do município de São Paulo.

Analise o texto extraído do arquivo "{nome_arquivo}"{ctx_termo} e classifique cada página ou bloco coerente de páginas por tipo de documento, identificando os dados-chave quando presentes.

Tipos possíveis: Nota Fiscal, Recibo de Pagamento, Comprovante de Transferência/TED/PIX, Extrato Bancário, Contrato de Prestação de Serviços, Folha de Pagamento/Holerite, Guia de Recolhimento (FGTS/INSS/ISS), Certidão, Relatório de Atividades, Ata/Procuração, Outros.

Regras:
- Agrupe páginas consecutivas que pertencem ao mesmo documento.
- Para cada grupo, retorne: paginas (ex: "1" ou "2-4"), tipo, fornecedor (se identificado), valor (se identificado, formatado em R$), data (se identificada, DD/MM/AAAA), observacoes (resumo de até 1 frase com informação relevante).
- Se a página estiver em branco ou ilegível, tipo = "Página em branco/ilegível".

Responda APENAS em json, sem texto extra, no formato:
{{"itens": [{{"paginas": "...", "tipo": "...", "fornecedor": "...", "valor": "...", "data": "...", "observacoes": "..."}}]}}

Texto extraído:{aviso}

{blocos}"""


def _chamar_deepseek(prompt: str) -> tuple[dict, str]:
    """Chama a API DeepSeek. Retorna (dict_resultado, conteudo_bruto)."""
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        raise ValueError('DEEPSEEK_API_KEY não configurada no .env')

    payload = {
        'model':           _DEEPSEEK_MODEL,
        'messages':        [{'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_object'},
        'temperature':     0.1,
        'max_tokens':      8192,
    }
    print(f'[DEEPSEEK ▶] POST {_DEEPSEEK_URL} | prompt={len(prompt)} chars')
    t0   = _time.time()
    resp = requests.post(
        _DEEPSEEK_URL,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=180,
    )
    print(f'[DEEPSEEK] HTTP {resp.status_code} em {round(_time.time()-t0,1)}s')
    resp.raise_for_status()

    body     = resp.json()
    conteudo = body['choices'][0]['message']['content']
    uso      = body.get('usage', {})
    print(f'[DEEPSEEK ✓] tokens: prompt={uso.get("prompt_tokens","?")} '
          f'completion={uso.get("completion_tokens","?")} | '
          f'raw (150): {conteudo[:150]}')
    return json.loads(conteudo), conteudo


# ── Helpers para dividir PDF ──────────────────────────────────────────────────

def _segmentos_do_corte(pontos_corte, total_paginas):
    pontos = sorted({int(p) for p in pontos_corte if 1 < int(p) <= total_paginas})
    bordas = [1] + pontos + [total_paginas + 1]
    return [(bordas[i], bordas[i + 1] - 1) for i in range(len(bordas) - 1)]


def _criar_subpdf(reader, inicio_0, fim_0):
    writer = PdfWriter()
    for pg in range(inicio_0, fim_0 + 1):
        writer.add_page(reader.pages[pg])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# ROTAS
# ═══════════════════════════════════════════════════════════════════════════════

# ── STATUS DE TAREFA (polling) ─────────────────────────────────────────────────

@bp.route('/api/task-status/<task_id>', methods=['GET'])
@login_required
def api_task_status(task_id):
    """Retorna o estado atual de uma tarefa de classificação."""
    with _tarefas_lock:
        tarefa = _tarefas.get(task_id)
    if not tarefa:
        return jsonify({'erro': 'Tarefa não encontrada ou expirada'}), 404
    return jsonify(tarefa)


# ── CLASSIFICAÇÃO PROCESSUAL (POST inicia tarefa → retorna task_id) ───────────

@bp.route('/api/classificacao-processual', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
def api_classificacao_processual():
    """
    Recebe PDFs, inicia processamento em background e devolve task_id imediatamente.
    O cliente deve fazer polling em GET /api/task-status/<task_id>.
    """
    arquivos_raw = request.files.getlist('arquivos')
    numero_termo = request.form.get('numero_termo', '').strip() or None

    if not arquivos_raw or all(f.filename == '' for f in arquivos_raw):
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    # Lê tudo na thread de request (file objects não são thread-safe)
    arquivos = [(f.filename, f.read()) for f in arquivos_raw if f.filename]
    if not arquivos:
        return jsonify({'erro': 'Nenhum arquivo válido'}), 400

    # Aviso antecipado para PDFs muito grandes
    avisos = []
    for nome, conteudo in arquivos:
        try:
            import pdfplumber as _pl
            with _pl.open(io.BytesIO(conteudo)) as _pdf:
                npags = len(_pdf.pages)
            if npags > _MAX_PAGINAS_DIRETO:
                avisos.append(
                    f'"{nome}" tem {npags} páginas. '
                    f'Recomendado: use a Triagem para dividir em partes de até {_MAX_PAGINAS_DIRETO} páginas '
                    f'antes de classificar. A classificação continuará, mas pode demorar muito.'
                )
        except Exception:
            pass

    tid = _nova_tarefa()
    print(f'[CLASSIF] Nova tarefa {tid} — {len(arquivos)} arquivo(s){" | AVISOS: " + str(avisos) if avisos else ""}')

    def _executar():
        resultados, erros = [], []
        n = len(arquivos)

        for idx, (nome, conteudo) in enumerate(arquivos, start=1):
            pct_base = round((idx - 1) / n * 100)
            print(f'[CLASSIF] [{tid[:8]}] [{idx}/{n}] {nome} — {len(conteudo)} bytes')

            try:
                if not conteudo:
                    erros.append({'arquivo': nome, 'mensagem': 'Arquivo vazio'})
                    continue

                # Extração página a página
                paginas = []
                with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
                    total_pags = len(pdf.pages)
                    print(f'[CLASSIF] [{tid[:8]}] PDF aberto: {total_pags} págs')
                    for i, pg in enumerate(pdf.pages, start=1):
                        texto = _extrair_texto_pagina(pg, conteudo, i)
                        paginas.append({'pagina': i, 'texto': texto})
                        pct   = pct_base + round((i / total_pags) * (50 / n))
                        label = (f'Extraindo pág {i}/{total_pags} — {nome}'
                                 if n == 1 else f'Arquivo {idx}/{n} · pág {i}/{total_pags}')
                        _atualizar(tid, pct=pct, label=label)

                chars_total = sum(len(p['texto']) for p in paginas)
                print(f'[CLASSIF] [{tid[:8]}] Extração: {len(paginas)} págs, {chars_total} chars')

                if not paginas:
                    erros.append({'arquivo': nome, 'mensagem': 'Sem páginas extraídas'})
                    continue

                pct_ia   = pct_base + round(50 / n)
                label_ia = (f'Classificando com IA — {nome}'
                            if n == 1 else f'Classificando {idx}/{n} com IA...')
                _atualizar(tid, pct=pct_ia, label=label_ia)

                prompt = _montar_prompt(paginas, nome, numero_termo)
                print(f'[CLASSIF] [{tid[:8]}] Chamando DeepSeek ({len(prompt)} chars prompt)...')

                resultado_ia, _ = _chamar_deepseek(prompt)
                itens = resultado_ia.get('itens', [])
                print(f'[CLASSIF] [{tid[:8]}] ✓ {len(itens)} itens')

                resultados.append({
                    'arquivo':       nome,
                    'total_paginas': len(paginas),
                    'itens':         itens,
                    'ocr_usado':     (_OCR_DISPONIVEL and
                                      chars_total < (_MIN_CHARS_PAGINA * len(paginas))),
                })

            except requests.HTTPError as http_err:
                msg = f'API DeepSeek {http_err.response.status_code}: {http_err.response.text[:200]}'
                print(f'[CLASSIF ERRO] [{tid[:8]}] {msg}')
                erros.append({'arquivo': nome, 'mensagem': msg})
            except Exception as exc:
                print(f'[CLASSIF ERRO] [{tid[:8]}] {type(exc).__name__}: {exc}')
                print(_tb.format_exc())
                erros.append({'arquivo': nome, 'mensagem': f'{type(exc).__name__}: {exc}'})

        resultado_final = {
            'resultados':    resultados,
            'erros':         erros,
            'ocr_disponivel': _OCR_DISPONIVEL,
        }
        print(f'[CLASSIF] [{tid[:8]}] Concluído: {len(resultados)} ok, {len(erros)} erros')
        _atualizar(tid, status='done', pct=100, label='Concluído!', resultado=resultado_final)

    threading.Thread(target=_executar, daemon=True).start()
    return jsonify({'task_id': tid, 'avisos': avisos})


# ── DIVIDIR + CLASSIFICAR (POST inicia tarefa → retorna task_id) ──────────────

@bp.route('/api/dividir-e-classificar', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
def api_dividir_e_classificar():
    """
    Divide PDF nos pontos de corte e classifica cada parte com DeepSeek.
    Mesmo protocolo de polling que /api/classificacao-processual.
    """
    arquivo = request.files.get('arquivo')
    pontos_raw   = request.form.get('pontos_corte', '[]')
    numero_termo = request.form.get('numero_termo', '').strip() or None

    if not arquivo or not arquivo.filename:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    try:
        pontos = json.loads(pontos_raw)
    except Exception:
        return jsonify({'erro': 'pontos_corte inválido'}), 400

    nome_original = arquivo.filename
    nome_base     = os.path.splitext(nome_original)[0]
    conteudo      = arquivo.read()

    tid = _nova_tarefa()
    print(f'[DIV+CLASSIF] Nova tarefa {tid} — {nome_original}')

    def _executar():
        try:
            reader     = PdfReader(io.BytesIO(conteudo))
            total_pags = len(reader.pages)
            segmentos  = _segmentos_do_corte(pontos, total_pags) if pontos else [(1, total_pags)]
            n          = len(segmentos)
            print(f'[DIV+CLASSIF] [{tid[:8]}] {total_pags} págs → {n} partes')
        except Exception as exc:
            print(f'[DIV+CLASSIF ERRO] [{tid[:8]}] ao ler PDF: {exc}')
            _atualizar(tid, status='error', erro=str(exc))
            return

        resultados, erros = [], []

        for idx, (ini, fim) in enumerate(segmentos, start=1):
            nome_parte = f'{nome_base}_parte{idx:02d}_pgs{ini}-{fim}.pdf'
            pct_base   = round((idx - 1) / n * 100)

            try:
                pdf_bytes = _criar_subpdf(reader, ini - 1, fim - 1)

                paginas = []
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    total_p = len(pdf.pages)
                    for i, pg in enumerate(pdf.pages, start=1):
                        texto = _extrair_texto_pagina(pg, pdf_bytes, i)
                        paginas.append({'pagina': i, 'texto': texto})
                        pct   = pct_base + round((i / total_p) * (50 / n))
                        label = f'Parte {idx}/{n} · extraindo pág {i}/{total_p}'
                        _atualizar(tid, pct=pct, label=label)

                if not paginas:
                    erros.append({'arquivo': nome_parte, 'mensagem': 'Sem páginas extraídas'})
                    continue

                pct_ia   = pct_base + round(50 / n)
                label_ia = f'Classificando parte {idx}/{n} com IA...'
                _atualizar(tid, pct=pct_ia, label=label_ia)

                prompt        = _montar_prompt(paginas, nome_parte, numero_termo)
                resultado_ia, _ = _chamar_deepseek(prompt)
                itens         = resultado_ia.get('itens', [])
                chars_total   = sum(len(p['texto']) for p in paginas)

                print(f'[DIV+CLASSIF] [{tid[:8]}] {nome_parte}: {len(itens)} itens')
                resultados.append({
                    'arquivo':           nome_parte,
                    'paginas_originais': f'{ini}-{fim}',
                    'total_paginas':     len(paginas),
                    'itens':             itens,
                    'ocr_usado':         (_OCR_DISPONIVEL and
                                          chars_total < (_MIN_CHARS_PAGINA * len(paginas))),
                })

            except requests.HTTPError as http_err:
                msg = f'DeepSeek {http_err.response.status_code}: {http_err.response.text[:150]}'
                print(f'[DIV+CLASSIF ERRO] [{tid[:8]}] {msg}')
                erros.append({'arquivo': nome_parte, 'mensagem': msg})
            except Exception as exc:
                print(f'[DIV+CLASSIF ERRO] [{tid[:8]}] {type(exc).__name__}: {exc}')
                print(_tb.format_exc())
                erros.append({'arquivo': nome_parte, 'mensagem': f'{type(exc).__name__}: {exc}'})

        resultado_final = {
            'resultados':    resultados,
            'erros':         erros,
            'ocr_disponivel': _OCR_DISPONIVEL,
        }
        print(f'[DIV+CLASSIF] [{tid[:8]}] Concluído: {len(resultados)} ok, {len(erros)} erros')
        _atualizar(tid, status='done', pct=100, label='Concluído!', resultado=resultado_final)

    threading.Thread(target=_executar, daemon=True).start()
    return jsonify({'task_id': tid})


# ── TRIAGEM DE PDF (SSE — sem IA, rápido, sem risco de idle timeout) ──────────

@bp.route('/api/triagem-pdf', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
def api_triagem_pdf():
    """
    Analisa PDF página a página (sem IA) via SSE.
    Eventos: progresso | resultado | erro
    """
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    nome     = arquivo.filename
    conteudo = arquivo.read()
    if not conteudo:
        return jsonify({'erro': 'Arquivo vazio'}), 400

    def _gerar():
        try:
            with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
                total = len(pdf.pages)
                if total == 0:
                    yield f"data: {json.dumps({'tipo': 'erro', 'mensagem': 'PDF sem páginas'})}\n\n"
                    return

                paginas_info = []
                for i, pg in enumerate(pdf.pages, start=1):
                    texto   = _extrair_texto_pagina(pg, conteudo, i)
                    chars   = len(texto)
                    tipo_kw = _detectar_tipo_cabecalho(texto)
                    paginas_info.append({
                        'pagina':         i,
                        'chars':          chars,
                        'cor':            _cor_barra(chars),
                        'preview':        texto[:90].replace('\n', ' ').strip(),
                        'tipo_detectado': tipo_kw,
                    })
                    pct = round(i / total * 100)
                    yield f"data: {json.dumps({'tipo': 'progresso', 'pagina': i, 'total': total, 'pct': pct})}\n\n"

            n, quebras = len(paginas_info), []
            for i, p in enumerate(paginas_info):
                if i == 0:
                    continue
                if p['tipo_detectado']:
                    quebras.append(p['pagina'])
                elif (p['chars'] < 50 and i + 1 < n
                      and paginas_info[i + 1]['chars'] > 100):
                    quebras.append(paginas_info[i + 1]['pagina'])

            vistos, quebras_unicas = set(), []
            for q in quebras:
                if q not in vistos:
                    vistos.add(q); quebras_unicas.append(q)

            print(f'[TRIAGEM] {nome}: {n} págs | {len(quebras_unicas)} quebras sugeridas')
            yield f"data: {json.dumps({'tipo': 'resultado', 'arquivo': nome, 'total_paginas': n, 'paginas': paginas_info, 'quebras_sugeridas': quebras_unicas, 'ocr_disponivel': _OCR_DISPONIVEL})}\n\n"

        except Exception as e:
            print(f'[TRIAGEM ERRO] {e}')
            yield f"data: {json.dumps({'tipo': 'erro', 'mensagem': str(e)})}\n\n"

    return Response(
        stream_with_context(_gerar()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ── TESTE DE CONECTIVIDADE IA ─────────────────────────────────────────────────

@bp.route('/api/testar-ia', methods=['GET'])
@login_required
def api_testar_ia():
    """Envia prompt mínimo (~50 tokens) para verificar conectividade com DeepSeek."""
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        return jsonify({'ok': False, 'erro': 'DEEPSEEK_API_KEY não configurada'}), 500

    t0 = _time.time()
    try:
        resp = requests.post(
            _DEEPSEEK_URL,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model':           _DEEPSEEK_MODEL,
                'messages':        [{'role': 'user', 'content':
                                     'Responda em json: {"status": "ok", "msg": "DeepSeek funcionando"}'}],
                'response_format': {'type': 'json_object'},
                'max_tokens':      50,
                'temperature':     0,
            },
            timeout=30,
        )
        resp.raise_for_status()
        latencia_ms = round((_time.time() - t0) * 1000)
        body        = resp.json()
        conteudo    = body['choices'][0]['message']['content']
        uso         = body.get('usage', {})
        return jsonify({'ok': True, 'latencia_ms': latencia_ms,
                        'resposta': json.loads(conteudo), 'tokens': uso})
    except requests.HTTPError as e:
        return jsonify({'ok': False, 'erro': f'HTTP {e.response.status_code}: {e.response.text[:200]}'}), 502
    except requests.Timeout:
        return jsonify({'ok': False, 'erro': 'Timeout >30 s — verifique conectividade'}), 504
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 500


# ── DIVIDIR PDF → ZIP ─────────────────────────────────────────────────────────

@bp.route('/api/dividir-pdf', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
def api_dividir_pdf():
    arquivo    = request.files.get('arquivo')
    pontos_raw = request.form.get('pontos_corte', '[]')

    if not arquivo or not arquivo.filename:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    try:
        pontos = json.loads(pontos_raw)
    except Exception:
        return jsonify({'erro': 'pontos_corte inválido'}), 400

    conteudo  = arquivo.read()
    nome_base = os.path.splitext(arquivo.filename)[0]
    reader    = PdfReader(io.BytesIO(conteudo))
    total     = len(reader.pages)

    if not pontos:
        return jsonify({'erro': 'Nenhum ponto de corte informado'}), 400

    segmentos = _segmentos_do_corte(pontos, total)
    print(f'[DIVIDIR] {arquivo.filename}: {total} págs → {len(segmentos)} partes {segmentos}')

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, (ini, fim) in enumerate(segmentos, start=1):
            pdf_part  = _criar_subpdf(reader, ini - 1, fim - 1)
            nome_part = f'{nome_base}_parte{i:02d}_pgs{ini}-{fim}.pdf'
            zf.writestr(nome_part, pdf_part)

    zip_buf.seek(0)
    return send_file(zip_buf, mimetype='application/zip',
                     as_attachment=True, download_name=f'{nome_base}_partes.zip')
