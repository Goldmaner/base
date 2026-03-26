"""
Blueprint de Gestão de Pessoas SMDHC
Importação de nomeações CDA a partir do Diário Oficial
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import execute_batch, get_cursor, get_db
from utils import login_required
from decorators import requires_access
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

gestao_pessoas_bp = Blueprint('gestao_pessoas', __name__, url_prefix='/gestao_pessoas')


def _recalcular_encerramento(vagas):
    """
    Para as vagas fornecidas, recalcula data_encerramento usando LEAD window function:
    cada titular recebe encerramento = data_publicacao_do_proximo - 1 dia.
    Registros com data_encerramento calculado recebem observacoes = 'Exonerado(a)'
    automaticamente (não sobrescreve quem não possui encerramento).
    """
    if not vagas:
        return
    cur = get_cursor()
    db = get_db()
    if not cur or not db:
        return
    try:
        placeholders = ','.join(['%s'] * len(vagas))
        cur.execute(f"""
            WITH recalc AS (
                SELECT id,
                    (LEAD(data_publicacao) OVER (
                        PARTITION BY numero_vaga ORDER BY data_publicacao ASC, id ASC
                    ) - INTERVAL '1 day')::date AS nova_enc
                FROM gestao_pessoas.smdhc_servidores
                WHERE numero_vaga IN ({placeholders})
            )
            UPDATE gestao_pessoas.smdhc_servidores AS s
            SET data_encerramento = r.nova_enc,
                observacoes = CASE
                    WHEN r.nova_enc IS NOT NULL THEN 'Exonerado(a)'
                    ELSE observacoes
                END
            FROM recalc r
            WHERE s.id = r.id
        """, vagas)
        db.commit()
    except Exception as e:
        print(f'[gestao_pessoas] Erro ao recalcular encerramento: {e}')
        try:
            db.rollback()
        except Exception:
            pass

DO_SEARCH_URL = 'https://diariooficial.prefeitura.sp.gov.br/md_epubli_controlador.php'
DO_SEARCH_TERM = '"Secretaria Municipal de Direitos Humanos e Cidadania, vaga"'
DO_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Referer': 'https://diariooficial.prefeitura.sp.gov.br/',
}


# ---------------------------------------------------------------------------
# Funções auxiliares de parsing
# ---------------------------------------------------------------------------

def _parse_int(value):
    """Extrai apenas dígitos de uma string e retorna como int, ou None."""
    if not value:
        return None
    digits = re.sub(r'\D', '', str(value))
    return int(digits) if digits else None


def _parse_date(date_str):
    """Converte 'DD/MM/YYYY' para objeto date, ou None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), '%d/%m/%Y').date()
    except (ValueError, TypeError):
        return None


def _parse_nominations_from_text(text, data_publicacao='', num_doc=''):
    """
    Extrai nomeações de cargo CDA a partir de texto plano do D.O.
    Retorna lista de dicts com: cda, numero_vaga, nome_servidor, numero_rf,
    data_publicacao, numero_documento, unidade, observacoes
    """
    results = []
    lines = text.split('\n')

    # Agrupa linhas em chunks: uma nomeação pode estar dividida em várias linhas.
    # Um novo chunk começa ao encontrar linha numerada ("1. NOME" / "1- NOME")
    # ou ao encontrar uma linha em branco. Linhas de continuação são concatenadas.
    chunks = []
    current = []
    for raw in lines:
        stripped = raw.strip()
        # Linha em branco = fim de bloco
        if not stripped:
            if current:
                chunks.append(' '.join(current))
                current = []
            continue
        # Nova entrada numerada ("1. NOME" ou "1- NOME") = novo bloco
        if re.match(r'^\d+[.\-]\s+[A-ZÁÉÍÓÚÀÂÊÎÔÛÃÕ]', stripped):
            if current:
                chunks.append(' '.join(current))
            current = [stripped]
        else:
            current.append(stripped)
    if current:
        chunks.append(' '.join(current))

    for chunk in chunks:
        upper = chunk.upper()
        if 'CDA' not in upper:
            continue

        # Nome: tudo antes de ", RG", ", RF" ou ", CPF"
        name_match = re.match(r'^(.+?),\s*(?:\w+/)?(?:RG|RF|CPF)(?:/\w+)?\s+', chunk, re.IGNORECASE)
        name = name_match.group(1).strip() if name_match else ''
        # Remove prefixos comuns
        name = re.sub(
            r'^Nomear\s+(?:o\s+senhor(?:a)?|a\s+senhora|o\s+servidor|a\s+servidora'
            r'|o\s+sr\.?|a\s+sr[aª]\.?)\s+',
            '', name, flags=re.IGNORECASE
        ).strip()
        name = re.sub(r'^Nomear\s+', '', name, flags=re.IGNORECASE).strip()
        # Remove prefixos de lista numerada: "1- ", "2- ", "1. ", etc.
        name = re.sub(r'^\d+[-\u2013.]\s*', '', name).strip()

        # RF
        rf_match = re.search(r'\bRF\s+([\d.]+(?:-\d)?)', chunk, re.IGNORECASE)
        numero_rf = _parse_int(rf_match.group(1)) if rf_match else None

        # CDA
        cda_match = re.search(r'\bCDA-?(\d+)', chunk, re.IGNORECASE)
        cda = int(cda_match.group(1)) if cda_match else None

        # Vaga (explícita: "vaga 21989"; ou implícita: número isolado entre vírgulas)
        vaga_match = re.search(r'\bvaga\s+(\d+)', chunk, re.IGNORECASE)
        if not vaga_match:
            vaga_match = re.search(r',\s*(\d{4,6})\s*[,.]', chunk)
        numero_vaga = int(vaga_match.group(1)) if vaga_match else None

        if cda and numero_vaga:
            results.append({
                'cda': cda,
                'numero_vaga': numero_vaga,
                'nome_servidor': name,
                'numero_rf': numero_rf,
                'data_publicacao': data_publicacao,
                'unidade': '',
                'numero_documento': _parse_int(num_doc),
                'observacoes': '',
            })
    return results


def _parse_doc_page(html, doc_number=''):
    """
    Parseia a página de um documento do D.O. e extrai nomeações.
    """
    soup = BeautifulSoup(html, 'html.parser')
    full_text = soup.get_text('\n')

    # Data de publicação
    data_pub = ''
    span_pub = soup.select_one('.info__publicacao, [class*="publicacao"]')
    if span_pub:
        m = re.search(r'Publica(?:ç|c)(?:ã|a)o:\s*(\d{2}/\d{2}/\d{4})', span_pub.get_text(), re.IGNORECASE)
        if m:
            data_pub = m.group(1)
    if not data_pub:
        m = re.search(r'Publica(?:ç|c)(?:ã|a)o:\s*(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
        if m:
            data_pub = m.group(1)

    # Número do documento (tentativa automática)
    if not doc_number:
        # 1. Prioridade: <title>ARQUIP | DOSP - XXXXXXXX - ...</title>
        title_tag = soup.find('title')
        if title_tag:
            m = re.search(r'DOSP\s*-\s*(\d+)', title_tag.get_text())
            if m:
                doc_number = m.group(1)
    if not doc_number:
        # 2. SEI nº XXXXXXXX (rodapé)
        m = re.search(r'SEI\s+n[°º.]\s*(\d+)', full_text, re.IGNORECASE)
        if m:
            doc_number = m.group(1)
    if not doc_number:
        # 3. Fallback: "o seguinte documento ... integra este ato XXXXXXXX"
        m = re.search(r'O seguinte documento\b[\w\s]*\bintegra este ato\s+(\d+)', full_text, re.IGNORECASE)
        if m:
            doc_number = m.group(1)

    return _parse_nominations_from_text(full_text, data_pub, doc_number)


# ---------------------------------------------------------------------------
# Scraping do Diário Oficial
# ---------------------------------------------------------------------------

def _scrape_do(data_inicio_str, data_fim_str, timeout_sec=15):
    """
    Busca Títulos de Nomeação da SMDHC no D.O. dentro do período informado.

    Args:
        data_inicio_str: 'DD/MM/YYYY'
        data_fim_str:    'DD/MM/YYYY'
        timeout_sec:     timeout por requisição HTTP

    Returns:
        dict com chaves 'documentos' (lista de {url, numero, data, tipo}) e 'erro' (str|None)
    """
    data_inicio = _parse_date(data_inicio_str)
    data_fim = _parse_date(data_fim_str)
    if not data_inicio or not data_fim:
        return {'documentos': [], 'erro': 'Datas inválidas.'}

    try:
        params = {
            'acao': 'materias_pesquisar',
            'textTermoPesquisa': DO_SEARCH_TERM,
        }
        resp = requests.get(DO_SEARCH_URL, params=params, headers=DO_HEADERS, timeout=timeout_sec)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {'documentos': [], 'erro': f'Erro ao acessar o D.O.: {e}'}

    soup = BeautifulSoup(resp.text, 'html.parser')
    documentos = []

    for div in soup.select('div.dadosDocumento'):
        # Tipo: verificar se é Título de Nomeação
        link = div.select_one('a.nroSei')
        if not link:
            continue

        tipo_span = link.find_next_sibling('span')
        tipo = tipo_span.get_text(strip=True) if tipo_span else ''
        if 'Título de Nomeação' not in tipo and 'titulo de nomeacao' not in tipo.lower():
            continue

        # Data de publicação
        data_span = div.select_one('span.dataPublicacao')
        data_pub_text = data_span.get_text(strip=True) if data_span else ''
        m = re.search(r'(\d{2}/\d{2}/\d{4})', data_pub_text)
        if not m:
            continue
        data_pub = _parse_date(m.group(1))
        if not data_pub:
            continue

        # Filtro por data
        if not (data_inicio <= data_pub <= data_fim):
            continue

        doc_url = link.get('href', '')
        doc_numero = link.get_text(strip=True)

        # Normaliza URL
        if doc_url and not doc_url.startswith('http'):
            doc_url = 'https://diariooficial.prefeitura.sp.gov.br/' + doc_url.lstrip('/')

        documentos.append({
            'url': doc_url,
            'numero': doc_numero,
            'data': m.group(1),
            'tipo': tipo.lstrip(' -').strip(),
        })

    return {'documentos': documentos, 'erro': None}


def _fetch_nominations_from_doc(doc_url, doc_numero, timeout_sec=15):
    """Acessa a URL de um documento do D.O. e retorna lista de nomeações parseadas."""
    try:
        resp = requests.get(doc_url, headers=DO_HEADERS, timeout=timeout_sec)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or 'utf-8'
        return _parse_doc_page(resp.text, doc_numero)
    except requests.RequestException as e:
        print(f'[gestao_pessoas] Erro ao buscar doc {doc_numero}: {e}')
        return []


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

SORT_COLUMNS = {
    'cda':      'cda',
    'vaga':     'numero_vaga',
    'nome':     'nome_servidor',
    'data_pub': 'data_publicacao',
    'data_enc': 'data_encerramento',
}

@gestao_pessoas_bp.route('/nomeacoes', methods=['GET'])
@login_required
@requires_access('gestao_pessoas')
def nomeacoes():
    try:
        per_page_raw = request.args.get('per_page', '100')
        per_page = 0 if per_page_raw == 'all' else int(per_page_raw)
        if per_page not in (0, 100, 200, 500):
            per_page = 100
    except (ValueError, TypeError):
        per_page = 100
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    sort_col = request.args.get('sort', 'data_pub')
    sort_dir = request.args.get('dir', 'desc')
    if sort_col not in SORT_COLUMNS:
        sort_col = 'data_pub'
    if sort_dir not in ('asc', 'desc'):
        sort_dir = 'desc'
    sql_col = SORT_COLUMNS[sort_col]
    sql_dir = 'DESC' if sort_dir == 'desc' else 'ASC'
    order_clause = f"{sql_col} {sql_dir} NULLS LAST, id {sql_dir}"
    search_q = request.args.get('q', '').strip()
    filter_obs = request.args.get('obs', '').strip()
    if filter_obs == '__all__':
        filter_obs = ''
    VALID_OBS_VALUES = {'Vaga Ocupada', 'Vacante', 'Exonerado(a)', 'Desconhecido'}
    filter_cda = request.args.get('cda', '').strip()
    if filter_cda == '__all__':
        filter_cda = ''
    where_parts = []
    where_params = []
    if search_q:
        where_parts.append("""
            (
                nome_servidor ILIKE %s
                OR CAST(numero_vaga AS TEXT) ILIKE %s
                OR CAST(cda AS TEXT) ILIKE %s
                OR unidade ILIKE %s
                OR CAST(numero_documento AS TEXT) ILIKE %s
                OR CAST(numero_rf AS TEXT) ILIKE %s
            )
        """)
        like = f'%{search_q}%'
        where_params.extend([like] * 6)
    if filter_obs == '__empty__':
        where_parts.append("(observacoes IS NULL OR observacoes = '')")
    elif filter_obs in VALID_OBS_VALUES:
        where_parts.append('observacoes = %s')
        where_params.append(filter_obs)
    if filter_cda and filter_cda.isdigit() and int(filter_cda) in range(1, 14):
        where_parts.append('cda = %s')
        where_params.append(int(filter_cda))
    where_clause = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''
    registros = []
    total_count = 0
    total_pages = 1
    try:
        cur = get_cursor()
        if cur:
            cur.execute(
                f"SELECT COUNT(*) AS total FROM gestao_pessoas.smdhc_servidores {where_clause}",
                tuple(where_params)
            )
            total_count = cur.fetchone()['total']
            if per_page == 0:
                total_pages = 1
                page = 1
                sql_limit = ''
                sql_params = tuple(where_params)
            else:
                total_pages = max(1, (total_count + per_page - 1) // per_page)
                page = min(page, total_pages)
                offset = (page - 1) * per_page
                sql_limit = 'LIMIT %s OFFSET %s'
                sql_params = tuple(where_params) + (per_page, offset)
            cur.execute(f"""
                SELECT id, cda, numero_vaga, nome_servidor, numero_rf,
                       TO_CHAR(data_publicacao, 'DD/MM/YYYY') AS data_publicacao,
                       TO_CHAR(data_encerramento, 'DD/MM/YYYY') AS data_encerramento,
                       unidade, numero_documento, observacoes,
                       TO_CHAR(created_at AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI') AS criado_em
                FROM gestao_pessoas.smdhc_servidores
                {where_clause}
                ORDER BY {order_clause}
                {sql_limit}
            """, sql_params)
            registros = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f'[gestao_pessoas] Erro ao carregar registros: {e}')
    return render_template('gestao_pessoas/nomeacoes.html', registros=registros,
                           page=page, total_pages=total_pages, total_count=total_count,
                           per_page=per_page, sort_col=sort_col, sort_dir=sort_dir,
                           q=search_q, filter_obs=filter_obs, filter_cda=filter_cda)


@gestao_pessoas_bp.route('/nomeacoes/salvar', methods=['POST'])
@login_required
@requires_access('gestao_pessoas')
def salvar_nomeacoes():
    """
    Recebe JSON com lista de nomeações e insere em lote no banco.
    Cada item: {cda, numero_vaga, nome_servidor, numero_rf, data_publicacao,
                unidade, numero_documento, observacoes}
    """
    dados = request.get_json(silent=True)
    if not dados or not isinstance(dados, list):
        return jsonify({'success': False, 'erro': 'Payload inválido'}), 400

    query = """
        INSERT INTO gestao_pessoas.smdhc_servidores
            (cda, numero_vaga, nome_servidor, numero_rf, data_publicacao,
             unidade, numero_documento, observacoes)
        VALUES
            (%(cda)s, %(numero_vaga)s, %(nome_servidor)s, %(numero_rf)s,
             %(data_publicacao)s, %(unidade)s, %(numero_documento)s, %(observacoes)s)
    """

    params_list = []
    for item in dados:
        cda_raw = item.get('cda') or ''
        cda_num = _parse_int(re.sub(r'CDA-', '', str(cda_raw), flags=re.IGNORECASE))

        data_pub = None
        data_str = item.get('data_publicacao') or ''
        if data_str:
            data_pub = _parse_date(data_str)

        params_list.append({
            'cda': cda_num,
            'numero_vaga': _parse_int(item.get('numero_vaga')),
            'nome_servidor': (item.get('nome_servidor') or '').strip() or None,
            'numero_rf': _parse_int(item.get('numero_rf')),
            'data_publicacao': data_pub,
            'unidade': (item.get('unidade') or '').strip() or None,
            'numero_documento': _parse_int(item.get('numero_documento')),
            'observacoes': (item.get('observacoes') or '').strip() or None,
        })

    # Verificar duplicatas (mesma vaga + mesma data já no banco)
    existing_pairs = set()
    pairs_to_check = [
        (p['numero_vaga'], p['data_publicacao'])
        for p in params_list
        if p['numero_vaga'] is not None and p['data_publicacao'] is not None
    ]
    if pairs_to_check:
        try:
            cur = get_cursor()
            if cur:
                placeholders = ','.join(['(%s,%s)'] * len(pairs_to_check))
                flat = [x for pair in pairs_to_check for x in pair]
                cur.execute(
                    f"SELECT numero_vaga, data_publicacao FROM gestao_pessoas.smdhc_servidores "
                    f"WHERE (numero_vaga, data_publicacao) IN ({placeholders})",
                    flat
                )
                existing_pairs = {
                    (row['numero_vaga'], row['data_publicacao']) for row in cur.fetchall()
                }
        except Exception as e:
            print(f'[gestao_pessoas] Erro ao verificar duplicatas: {e}')

    ignorados = 0
    filtered_params = []
    for p in params_list:
        key = (p['numero_vaga'], p['data_publicacao'])
        if key[0] is not None and key[1] is not None and key in existing_pairs:
            ignorados += 1
        else:
            filtered_params.append(p)

    if not filtered_params:
        return jsonify({'success': True, 'salvos': 0, 'ignorados': ignorados})

    resultado = execute_batch(query, filtered_params)
    if resultado['success']:
        # Recalcular data_encerramento para todas as vagas afetadas
        vagas_afetadas = list({p['numero_vaga'] for p in filtered_params if p['numero_vaga']})
        _recalcular_encerramento(vagas_afetadas)
        return jsonify({'success': True, 'salvos': resultado['count'], 'ignorados': ignorados})
    else:
        return jsonify({'success': False, 'erro': 'Falha ao salvar no banco.'}), 500


@gestao_pessoas_bp.route('/nomeacoes/buscar-do', methods=['POST'])
@login_required
@requires_access('gestao_pessoas')
def buscar_do():
    """
    Recebe {data_inicio: 'DD/MM/YYYY', data_fim: 'DD/MM/YYYY'}.
    Faz scraping do D.O. filtrando Títulos de Nomeação da SMDHC no período.
    Retorna lista de documentos encontrados e respectivas nomeações parseadas.
    """
    body = request.get_json(silent=True) or {}
    data_inicio = body.get('data_inicio', '')
    data_fim = body.get('data_fim', '')

    resultado = _scrape_do(data_inicio, data_fim)
    if resultado['erro']:
        return jsonify({'success': False, 'erro': resultado['erro']}), 422

    documentos = resultado['documentos']
    if not documentos:
        return jsonify({'success': True, 'documentos': [], 'nomeacoes': [],
                        'mensagem': 'Nenhum Título de Nomeação da SMDHC encontrado no período.'})

    # Para cada documento, buscar e parsear as nomeações
    todas_nomeacoes = []
    for doc in documentos:
        if doc['url']:
            noms = _fetch_nominations_from_doc(doc['url'], doc['numero'])
            # Enriquecer com info do documento
            for n in noms:
                n['_doc_numero'] = doc['numero']
                n['_doc_url'] = doc['url']
            todas_nomeacoes.extend(noms)

    return jsonify({
        'success': True,
        'documentos': documentos,
        'nomeacoes': todas_nomeacoes,
    })


@gestao_pessoas_bp.route('/nomeacoes/<int:record_id>/campo', methods=['PATCH'])
@login_required
@requires_access('gestao_pessoas')
def atualizar_campo(record_id):
    """Atualiza um campo editável de um registro (Nome, RF, Data Publicação, Nº Documento)."""
    CAMPOS_PERMITIDOS = {
        'nome_servidor':    ('nome_servidor',    'text'),
        'numero_rf':        ('numero_rf',        'int'),
        'data_publicacao':  ('data_publicacao',  'date'),
        'data_encerramento':('data_encerramento','date'),
        'numero_documento': ('numero_documento', 'int'),
    }
    body = request.get_json(silent=True) or {}
    campo = (body.get('campo') or '').strip()
    if campo not in CAMPOS_PERMITIDOS:
        return jsonify({'success': False, 'erro': 'Campo não permitido.'}), 400

    col, tipo = CAMPOS_PERMITIDOS[campo]
    raw = (body.get('valor') or '').strip()

    if tipo == 'text':
        valor = raw or None
    elif tipo == 'int':
        valor = _parse_int(raw)
    elif tipo == 'date':
        valor = _parse_date(raw)
        if raw and valor is None:
            return jsonify({'success': False, 'erro': 'Data inválida. Use DD/MM/AAAA.'}), 400
    else:
        valor = raw or None

    resultado = execute_batch(
        f"UPDATE gestao_pessoas.smdhc_servidores SET {col} = %(valor)s WHERE id = %(id)s",
        [{'valor': valor, 'id': record_id}]
    )
    if not resultado['success']:
        return jsonify({'success': False, 'erro': 'Falha ao atualizar.'}), 500

    # data_publicacao changed → recalculate encerramento for this vaga
    if campo == 'data_publicacao':
        try:
            cur = get_cursor()
            if cur:
                cur.execute(
                    "SELECT numero_vaga FROM gestao_pessoas.smdhc_servidores WHERE id = %s",
                    (record_id,)
                )
                row = cur.fetchone()
                if row and row['numero_vaga']:
                    _recalcular_encerramento([row['numero_vaga']])
        except Exception as e:
            print(f'[gestao_pessoas] Erro ao recalcular após update data: {e}')

    return jsonify({'success': True})


@gestao_pessoas_bp.route('/nomeacoes/<int:record_id>/unidade', methods=['PATCH'])
@login_required
@requires_access('gestao_pessoas')
def atualizar_unidade(record_id):
    """Atualiza apenas o campo 'unidade' de um registro."""
    body = request.get_json(silent=True) or {}
    unidade = (body.get('unidade') or '').strip() or None
    resultado = execute_batch(
        "UPDATE gestao_pessoas.smdhc_servidores SET unidade = %(unidade)s WHERE id = %(id)s",
        [{'unidade': unidade, 'id': record_id}]
    )
    if resultado['success']:
        return jsonify({'success': True})
    return jsonify({'success': False, 'erro': 'Falha ao atualizar unidade.'}), 500


@gestao_pessoas_bp.route('/nomeacoes/<int:record_id>/observacoes', methods=['PATCH'])
@login_required
@requires_access('gestao_pessoas')
def atualizar_observacoes(record_id):
    """Atualiza apenas o campo 'observacoes' de um registro."""
    body = request.get_json(silent=True) or {}
    OPCOES_VALIDAS = {'', 'Vaga Ocupada', 'Vacante', 'Exonerado(a)', 'Desconhecido'}
    obs = (body.get('observacoes') or '').strip()
    if obs not in OPCOES_VALIDAS:
        return jsonify({'success': False, 'erro': 'Valor inválido.'}), 400
    resultado = execute_batch(
        "UPDATE gestao_pessoas.smdhc_servidores SET observacoes = %(obs)s WHERE id = %(id)s",
        [{'obs': obs or None, 'id': record_id}]
    )
    if resultado['success']:
        return jsonify({'success': True})
    return jsonify({'success': False, 'erro': 'Falha ao atualizar observações.'}), 500


@gestao_pessoas_bp.route('/nomeacoes/<int:record_id>', methods=['DELETE'])
@login_required
@requires_access('gestao_pessoas')
def excluir_nomeacao(record_id):
    """Remove permanentemente um registro pelo ID."""
    resultado = execute_batch(
        "DELETE FROM gestao_pessoas.smdhc_servidores WHERE id = %(id)s",
        [{'id': record_id}]
    )
    if resultado['success']:
        return jsonify({'success': True})
    return jsonify({'success': False, 'erro': 'Falha ao excluir.'}), 500


# ---------------------------------------------------------------------------
# Calendário / Gantt de ocupação de vagas
# ---------------------------------------------------------------------------

@gestao_pessoas_bp.route('/calendario')
@login_required
@requires_access('gestao_pessoas')
def calendario():
    """Exibe visualização estilo calendário da ocupação de cada vaga CDA."""
    import json
    from datetime import date

    registros = []
    try:
        cur = get_cursor()
        if cur:
            cur.execute("""
                SELECT numero_vaga, cda, nome_servidor, numero_rf,
                       data_publicacao, data_encerramento, observacoes, unidade
                FROM gestao_pessoas.smdhc_servidores
                WHERE numero_vaga IS NOT NULL
                ORDER BY numero_vaga ASC, data_publicacao ASC NULLS LAST, id ASC
            """)
            registros = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f'[gestao_pessoas] Erro ao carregar calendário: {e}')

    # Agrupar por vaga
    vagas_map = {}
    for r in registros:
        v = r['numero_vaga']
        if v not in vagas_map:
            vagas_map[v] = {'cda': r['cda'], 'unidade': r.get('unidade') or '', 'periodos': []}
        if r['data_publicacao']:
            inicio = r['data_publicacao'].isoformat() if hasattr(r['data_publicacao'], 'isoformat') else str(r['data_publicacao'])
            fim = r['data_encerramento'].isoformat() if r['data_encerramento'] and hasattr(r['data_encerramento'], 'isoformat') else (str(r['data_encerramento']) if r['data_encerramento'] else None)
            vagas_map[v]['periodos'].append({
                'nome': r['nome_servidor'] or '',
                'rf': r['numero_rf'],
                'inicio': inicio,
                'fim': fim,
                'obs': r['observacoes'] or '',
            })
        # cda: set once; unidade: always overwrite so latest (ASC order) wins
        if not vagas_map[v]['cda'] and r['cda']:
            vagas_map[v]['cda'] = r['cda']
        if r.get('unidade'):
            vagas_map[v]['unidade'] = r['unidade']

    vagas_list = [
        {'numero': v, 'cda': vagas_map[v]['cda'], 'unidade': vagas_map[v]['unidade'], 'periodos': vagas_map[v]['periodos']}
        for v in sorted(vagas_map.keys())
    ]

    dados_json = json.dumps({'vagas': vagas_list}, ensure_ascii=False, default=str)
    return render_template('gestao_pessoas/calendario.html', dados_json=dados_json)
