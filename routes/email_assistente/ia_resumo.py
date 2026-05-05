"""
Módulo de integração com IA para o Email Assistente.
Suporta dois backends configuráveis via .env (IA_BACKEND):
  - gemini  → Google Gemini (chave vinculada a conta de serviço GCP)
              Tenta modelos em ordem: gemini-2.5-flash → 2.0-flash → 2.0-flash-lite
  - groq    → Groq API (Llama 3.3-70B, gratuito)
"""

import os
import re
import json
import time
import requests

# ─── Configuração ─────────────────────────────────────────────────────────────
IA_BACKEND    = os.environ.get('IA_BACKEND', 'groq').lower()

# Groq
GROQ_API_KEY  = os.environ.get('GROQ_API_KEY', '')
GROQ_URL      = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL    = 'llama-3.3-70b-versatile'

# Gemini
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
_GEMINI_BASE   = 'https://generativelanguage.googleapis.com/v1beta/models'
_GEMINI_MODELS = [
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
]

# Cache simples em memória: evita rechamar a API para o mesmo email
# Chave: f"{remetente}|{assunto}", Valor: dict com resumo
_cache: dict = {}

# ─── Prompt base ──────────────────────────────────────────────────────────────
_PROMPT_SISTEMA = (
    'Você é um assistente que analisa emails corporativos para um servidor público '
    'da Prefeitura de São Paulo. Responda SOMENTE com um JSON válido, sem nenhum '
    'texto adicional fora do JSON, no seguinte formato:\n'
    '{\n'
    '  "resumo": "resumo em 2-3 frases diretas do conteúdo",\n'
    '  "urgencia": "Alta" ou "Normal" ou "Baixa",\n'
    '  "acao": "descrição curta da ação necessária, ou Nenhuma se for informativo"\n'
    '}'
)


# ─── Exponential backoff ──────────────────────────────────────────────────────

def _com_retry(fn, max_tentativas: int = 3):
    """
    Chama fn() com exponential backoff em caso de 429 (rate limit).
    Tentativas: imediata → 2s → 4s → desiste.
    """
    delay = 2
    for tentativa in range(max_tentativas):
        try:
            return fn()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and tentativa < max_tentativas - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError('Número máximo de tentativas atingido.')


# ─── Backends ─────────────────────────────────────────────────────────────────

def _chamar_groq(prompt_usuario: str) -> str:
    """Chama a API Groq (OpenAI-compatible) e retorna o texto da resposta."""
    if not GROQ_API_KEY:
        raise ValueError('GROQ_API_KEY não configurada no .env')
    resp = requests.post(
        GROQ_URL,
        headers={'Authorization': f'Bearer {GROQ_API_KEY}'},
        json={
            'model': GROQ_MODEL,
            'messages': [
                {'role': 'system', 'content': _PROMPT_SISTEMA},
                {'role': 'user',   'content': prompt_usuario},
            ],
            'temperature': 0.1,
            'max_tokens': 350,
        },
        timeout=20
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content'].strip()


def _chamar_gemini(prompt_usuario: str) -> str:
    """Chama a API Google Gemini e retorna o texto da resposta.
    Tenta cada modelo em _GEMINI_MODELS até obter resposta válida.
    """
    if not GEMINI_API_KEY:
        raise ValueError('GEMINI_API_KEY não configurada no .env')
    payload = {
        'system_instruction': {'parts': [{'text': _PROMPT_SISTEMA}]},
        'contents': [{'parts': [{'text': prompt_usuario}]}],
        'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 350},
    }
    last_error = None
    for model in _GEMINI_MODELS:
        url = f'{_GEMINI_BASE}/{model}:generateContent'
        try:
            resp = requests.post(
                url,
                params={'key': GEMINI_API_KEY},
                json=payload,
                timeout=20,
            )
            if resp.status_code in (400, 404):
                # modelo não existe/inválido → tenta próximo
                last_error = resp
                continue
            resp.raise_for_status()
            return resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except requests.exceptions.HTTPError as exc:
            last_error = exc
            if exc.response.status_code in (400, 404):
                continue
            raise
    if isinstance(last_error, Exception):
        raise last_error
    last_error.raise_for_status()


def _chamar_ia(prompt_usuario: str) -> str:
    """Despacha para o backend configurado em IA_BACKEND, com retry automático."""
    if IA_BACKEND == 'gemini':
        return _com_retry(lambda: _chamar_gemini(prompt_usuario))
    return _com_retry(lambda: _chamar_groq(prompt_usuario))


def _parsear_resposta(texto: str) -> dict:
    """Extrai JSON da resposta da IA de forma robusta.

    A IA pode retornar:
      - JSON puro
      - JSON dentro de ```json ... ```
      - JSON precedido/seguido de texto explicativo
      - JSON truncado (corpo muito longo)
    """
    # 1. Remove code fences se existirem
    texto = texto.strip()
    if texto.startswith('```'):
        linhas = texto.splitlines()
        # remove primeira linha (```json) e última (```)
        inner = linhas[1:]
        if inner and inner[-1].strip() == '```':
            inner = inner[:-1]
        texto = '\n'.join(inner).strip()

    # 2. Tenta encontrar o bloco JSON com regex (entre { })
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        texto = match.group(0)

    # 3. Tenta parse direto
    try:
        resultado = json.loads(texto)
    except json.JSONDecodeError:
        # 4. Última tentativa: trunca na última vírgula válida e fecha o JSON
        # (acontece quando o modelo para no meio do output)
        ultimo_valido = max(texto.rfind('",'), texto.rfind('",\n'))
        if ultimo_valido > 0:
            texto_cortado = texto[:ultimo_valido + 1] + '}'
            try:
                resultado = json.loads(texto_cortado)
            except json.JSONDecodeError:
                resultado = {}
        else:
            resultado = {}

    resultado.setdefault('resumo', '(Resumo indisponível)')
    resultado.setdefault('urgencia', 'Normal')
    resultado.setdefault('acao', 'Nenhuma')
    # Garante que urgencia é um dos valores esperados
    if resultado['urgencia'] not in ('Alta', 'Normal', 'Baixa'):
        resultado['urgencia'] = 'Normal'
    return resultado


# ─── Funções públicas ─────────────────────────────────────────────────────────

def resumir_email(assunto: str, corpo: str, remetente: str) -> dict:
    """
    Resume um email com IA. Retorna dict com resumo, urgencia e acao.
    Usa cache em memória para evitar chamadas duplicadas.
    """
    chave_cache = f'{remetente}|{assunto}'
    if chave_cache in _cache:
        return _cache[chave_cache]

    prompt_usuario = (
        f'Remetente: {remetente}\n'
        f'Assunto: {assunto}\n'
        f'Corpo do email:\n{corpo[:3000]}'
    )

    texto = _chamar_ia(prompt_usuario)
    resultado = _parsear_resposta(texto)
    _cache[chave_cache] = resultado
    return resultado


def resumir_lote(emails: list[dict]) -> list[dict]:
    """
    Adiciona o campo 'ia' a cada email da lista com o resultado do resumo.
    Emails sem corpo retornam resumo padrão sem chamar a API.
    """
    for em in emails:
        if not em.get('corpo', '').strip():
            em['ia'] = {'resumo': '(Email sem corpo de texto)', 'urgencia': 'Baixa', 'acao': 'Nenhuma'}
            continue
        try:
            em['ia'] = resumir_email(
                assunto=em.get('assunto', ''),
                corpo=em.get('corpo', ''),
                remetente=em.get('remetente', ''),
            )
        except Exception as e:
            em['ia'] = {'resumo': f'(Erro ao resumir: {e})', 'urgencia': 'Normal', 'acao': 'Nenhuma'}
    return emails


def testar_api() -> dict:
    """
    Testa se a API de IA configurada está funcionando.
    Retorna dict com 'ok' (bool), 'mensagem' e 'backend'.
    """
    try:
        texto = _chamar_ia('Responda apenas com a palavra: FUNCIONANDO')
        return {'ok': True, 'mensagem': f'{IA_BACKEND.upper()} respondeu: {texto[:80]}', 'backend': IA_BACKEND}
    except requests.exceptions.HTTPError as e:
        return {'ok': False, 'mensagem': f'Erro HTTP {e.response.status_code}: {e.response.text[:300]}', 'backend': IA_BACKEND}
    except Exception as e:
        return {'ok': False, 'mensagem': str(e), 'backend': IA_BACKEND}
