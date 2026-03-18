"""
routes/orcamento_ocr.py
-----------------------
Blueprint para parsing estruturado de modelos de Proposta Orçamentária.

Arquitetura
-----------
  - Cada modelo tem uma entrada em MODELOS (catálogo exibido na UI).
  - A detecção automática compara assinaturas textuais do arquivo baixado.
  - Um dispatcher chama o parser específico de cada modelo.
  - Todos os parsers devolvem (rows, avisos) onde `rows` é uma lista de dicts
    compatível com a função importFromJson() do frontend
    (chaves: Rubrica, Quantidade, Categoria de Despesa, Mês 1, Mês 2, …).

Modelos suportados
------------------
  modelo_1_anexo_iii
      Planilha "Anexo III – Modelo para Elaboração da Proposta Orçamentária"
      Estrutura:
        Tabela 1 – Equipe Técnica          → rubrica "Pessoal"
        Tabela 2 – Serviços Contratados   → rubrica "Serviços de Terceiros"
        (sub-seção Despesas Administrativas) → rubrica "Administrativas"
        Tabela 3 – Comunicação/Outras     → rubrica "Outras Despesas"

Adicionando novos modelos
-------------------------
  1. Adicione uma entrada em MODELOS.
  2. Adicione as assinaturas textuais em MODELO_ASSINATURAS.
  3. Escreva a função _parse_<modelo_id>(linhas, num_meses) → (rows, avisos).
  4. Registre-a no dicionário `parsers` dentro de `parse()`.
"""

import re
import csv
from io import BytesIO, StringIO

from flask import Blueprint, request, jsonify
from utils import login_required


orcamento_ocr_bp = Blueprint('orcamento_ocr', __name__, url_prefix='/orcamento/ocr')


# ===========================================================================
# CATÁLOGO DE MODELOS SUPORTADOS
# ===========================================================================

MODELOS = {
    'modelo_1_anexo_iii': {
        'nome': 'Modelo 1 — Anexo III (Proposta Orçamentária)',
        'descricao': (
            'Planilha com Tabela 1 (Equipe Técnica → Pessoal), '
            'Tabela 2 (Serviços Contratados → Serv. de Terceiros / Administrativas) '
            'e Tabela 3 (Comunicação → Outras Despesas). '
            'Formatos aceitos: xlsx, xls, csv.'
        ),
        'formatos': ['xlsx', 'xls', 'csv'],
    },
    'modelo_2_dieese': {
        'nome': 'Modelo 2 — DIEESE (Proposta Orçamentária CLT)',
        'descricao': (
            'Planilha DIEESE com bloco Recursos Humanos CLT: cada funcionário '
            'tem nº de meses de atuação explícito na coluna (a). '
            'Encargos (INSS, FGTS, PIS) são agregados por mês (apenas funcionários '
            'ativos naquele mês). Incluí Tabela 2 (Despesas Correntes), '
            'Tabela 3/3a (Materiais) e Tabela 4 (Serviços de Terceiros). '
            'Tabela 4a (proporções) é ignorada.'
        ),
        'formatos': ['xlsx', 'xls', 'csv'],
    },
}

# Assinaturas para auto-detecção: todas as strings da lista devem aparecer
# no texto normalizado do arquivo para que o modelo seja reconhecido.
MODELO_ASSINATURAS = {
    'modelo_1_anexo_iii': [
        'equipe técnica',
        'valor estimado mensal',
    ],
    'modelo_2_dieese': [
        'recursos humanos',
        'carga horária',
        'número de meses de atuação',
    ],
}


# ===========================================================================
# ENDPOINTS
# ===========================================================================

@orcamento_ocr_bp.route('/modelos', methods=['GET'])
@login_required
def listar_modelos():
    """Retorna o catálogo de modelos disponíveis (para preencher a UI)."""
    return jsonify({'modelos': MODELOS}), 200


@orcamento_ocr_bp.route('/parse', methods=['POST'])
@login_required
def parse():
    """
    Endpoint principal de parsing estruturado.

    Form fields:
      arquivo    — arquivo xlsx, xls ou csv
      modelo     — (opcional) model_id; se omitido, tenta auto-detecção
      num_meses  — (opcional) número de meses do projeto; se omitido, detecta na planilha

    Resposta (200):
      {
        modelo, modelo_nome,
        rows: [ {Rubrica, Quantidade, Categoria de Despesa, Mês 1, ...} ],
        avisos: [...],
        total, message
      }

    Erros:
      400 — arquivo faltando / formato inválido
      422 — modelo não identificado (inclui preview das primeiras linhas)
      500 — erro interno
      501 — modelo sem parser implementado
    """
    try:
        modelo_hint = (request.form.get('modelo') or '').strip() or None
        num_meses_hint = request.form.get('num_meses', type=int)

        arquivo = request.files.get('arquivo')
        if not arquivo:
            return jsonify({'error': 'Nenhum arquivo enviado (campo "arquivo")'}), 400

        ext = arquivo.filename.rsplit('.', 1)[-1].lower() if '.' in arquivo.filename else ''
        linhas = _extrair_linhas(arquivo, ext)

        if linhas is None:
            return jsonify({
                'error': f'Formato não suportado: .{ext}. Use xlsx, xls ou csv.'
            }), 400

        # Detectar modelo
        modelo_id = modelo_hint if modelo_hint in MODELOS else detectar_modelo(linhas)
        if not modelo_id:
            return jsonify({
                'error': (
                    'Modelo não identificado automaticamente. '
                    'Selecione o modelo manualmente no dropdown.'
                ),
                'modelos_disponiveis': list(MODELOS.keys()),
                'preview_primeiras_linhas': [list(r) for r in linhas[:6]],
            }), 422

        # Inferir num_meses
        num_meses = num_meses_hint or _inferir_num_meses(linhas)

        # Dispatcher
        parsers = {
            'modelo_1_anexo_iii': _parse_modelo_1_anexo_iii,
            'modelo_2_dieese':    _parse_modelo_2_dieese,
        }
        parser_fn = parsers.get(modelo_id)
        if not parser_fn:
            return jsonify({
                'error': f'Parser para "{modelo_id}" ainda não implementado.'
            }), 501

        rows, avisos = parser_fn(linhas, num_meses)

        return jsonify({
            'modelo': modelo_id,
            'modelo_nome': MODELOS[modelo_id]['nome'],
            'rows': rows,
            'avisos': avisos,
            'total': len(rows),
            'message': (
                f'{len(rows)} linha(s) extraída(s) — '
                f'{num_meses} mês/meses — '
                f'modelo: {MODELOS[modelo_id]["nome"]}'
            ),
        }), 200

    except Exception as exc:
        return jsonify({'error': f'Erro ao processar arquivo: {exc}'}), 500


# ===========================================================================
# EXTRAÇÃO BRUTA DE LINHAS
# ===========================================================================

def _extrair_linhas(arquivo, ext):
    """
    Lê o arquivo e devolve lista de listas de strings.
    Retorna None se o formato não for suportado.
    """
    conteudo = arquivo.read()

    if ext in ('xlsx', 'xls'):
        import openpyxl
        wb = openpyxl.load_workbook(BytesIO(conteudo), data_only=True)
        ws = wb.active
        return [[_cel_str(cel) for cel in row] for row in ws.iter_rows()]

    if ext == 'csv':
        texto = conteudo.decode('utf-8-sig', errors='replace')
        try:
            dialect = csv.Sniffer().sniff(texto[:4096], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(StringIO(texto), dialect)
        return [row for row in reader]

    return None


def _cel_str(cel):
    """Célula openpyxl → string limpa."""
    return '' if cel.value is None else str(cel.value).strip()


# ===========================================================================
# DETECÇÃO DE MODELO
# ===========================================================================

def detectar_modelo(linhas):
    """
    Analisa o texto normalizado de todas as células e devolve o model_id
    que casar com todas as suas assinaturas. Devolve None se nenhum casar.
    Quando mais de um casar, devolve o de maior número de assinaturas (mais específico).
    """
    texto = ' '.join(
        cel.lower()
        for linha in linhas
        for cel in linha
        if cel
    )

    melhor = (0, None)
    for modelo_id, assinaturas in MODELO_ASSINATURAS.items():
        if all(sig in texto for sig in assinaturas):
            if len(assinaturas) > melhor[0]:
                melhor = (len(assinaturas), modelo_id)

    return melhor[1]


# ===========================================================================
# UTILITÁRIOS COMUNS AOS PARSERS
# ===========================================================================

_RX_TOTAL    = re.compile(r'^\s*total', re.IGNORECASE)
_RX_TABELA   = re.compile(r'tabela\s*(\d+)', re.IGNORECASE)
_RX_FOOTNOTE = re.compile(r'^[¹²³⁴⁵⁶⁷⁸⁹]|^\(\d\)')


def _normalizar_valor(s):
    """
    Converte string de valor monetário para float.
    Aceita "1.234,56" (BR), "1234.56" (US) e "1234" (inteiro).
    Devolve 0.0 para strings vazias ou não-numéricas.
    """
    s = str(s).strip().replace(' ', '').replace('R$', '').replace('r$', '')
    if not s or s == '-':
        return 0.0
    # Formato BR: 1.234,56
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def _primeiro_cel_nao_vazio(celulas):
    return next((c.strip() for c in celulas if c and c.strip()), '')


def _eh_linha_vazia(celulas):
    return not any(c.strip() for c in celulas)


def _eh_linha_total(celulas):
    primeiro = _primeiro_cel_nao_vazio(celulas)
    return bool(_RX_TOTAL.match(primeiro))


def _eh_linha_rodape(celulas):
    primeiro = _primeiro_cel_nao_vazio(celulas)
    return bool(_RX_FOOTNOTE.match(primeiro))


def _inferir_num_meses(linhas):
    """
    Detecta o número de meses procurando padrões como "×12", "x 6", "*4"
    nos textos das células. Padrão: 12.
    """
    for linha in linhas:
        for cel in linha:
            m = re.search(r'[×xX\*]\s*(\d+)', str(cel))
            if m:
                n = int(m.group(1))
                if 2 <= n <= 60:
                    return n
    return 12


# ===========================================================================
# PARSER: MODELO 1 — ANEXO III
# ===========================================================================
#
# Estrutura esperada
#   Tabela 1 – Equipe Técnica
#     [cabeçalho: Item | (A) Valor estimado mensal | (B) Encargos | Total (A+B)×N]
#     [linhas de dados]
#     TOTAL (ignorar)
#
#   Tabela 2 – Serviços Contratados
#     [cabeçalho]   [linhas — rubrica "Serviços de Terceiros"]
#     Despesas Administrativas   ← muda rubrica para "Administrativas"
#     [cabeçalho]   [linhas]
#     TOTAL (ignorar)
#
#   Tabela 3 – Comunicação / Outras Despesas
#     [cabeçalho: apenas total, sem breakdown mensal]
#     [linhas — rubrica "Outras Despesas"; valor total concentrado no Mês 1]
#     TOTAL (ignorar)
#
# Cálculo de meses por linha (Tabelas 1 & 2):
#   n_meses_item = round(total / mensal), limitado a num_meses do projeto.
#   Quando não há coluna de total, usa num_meses do projeto inteiro.
# Tabela 3:
#   Sem valor mensal → total inteiro colocado no Mês 1 apenas.
#
# Notas
#   - Nomes duplicados (ex: três "Articulador(a)") recebem sufixo 1, 2, 3…
#   - Linhas com valor mensal = 0 geram aviso e são ignoradas.
# ===========================================================================

_SECAO_DESCONHECIDA  = 0
_SECAO_TAB1          = 1   # Equipe Técnica       → Pessoal
_SECAO_TAB2_SERVICO  = 2   # Serviços             → Serviços de Terceiros
_SECAO_TAB2_ADMIN    = 3   # Desp. Administrativas → Administrativas
_SECAO_TAB3          = 4   # Comunicação/Outras   → Outras Despesas

_RUBRICA_MAP = {
    _SECAO_TAB1:        'Pessoal',
    _SECAO_TAB2_SERVICO:'Serviços de Terceiros',
    _SECAO_TAB2_ADMIN:  'Administrativas',
    _SECAO_TAB3:        'Outras Despesas',
}

# Detectores de transição de seção (match no PRIMEIRO cel não-vazio da linha)
_RX_TAB_INICIO   = re.compile(r'^tabela\s*\d+', re.IGNORECASE)
_RX_DESP_ADM     = re.compile(r'^despesas\s+administrativas', re.IGNORECASE)
# Detectores de linha de cabeçalho (devem ser puladas)
_RX_THEAD_ITEM   = re.compile(r'^item$', re.IGNORECASE)
_RX_THEAD_VALOR  = re.compile(r'valor\s+estimado', re.IGNORECASE)


def _parse_modelo_1_anexo_iii(linhas, num_meses):
    """
    Parser para o Modelo 1 (Anexo III).
    Retorna (rows, avisos).
    """
    avisos = []
    rows = []

    secao = _SECAO_DESCONHECIDA
    aguardando_header = False   # True logo após detectar início de seção/sub-seção

    # Rastreia quantas vezes cada nome aparece para deduplicar
    contagem_nomes: dict[str, int] = {}

    for linha in linhas:
        celulas = [str(c).strip() for c in linha]
        primeiro = _primeiro_cel_nao_vazio(celulas)

        # ------------------------------------------------------------------
        # Transições de seção
        # ------------------------------------------------------------------
        if _RX_TAB_INICIO.match(primeiro):
            m = _RX_TABELA.search(primeiro)
            num_tab = int(m.group(1)) if m else 0
            secao = {1: _SECAO_TAB1, 2: _SECAO_TAB2_SERVICO, 3: _SECAO_TAB3}.get(
                num_tab, _SECAO_DESCONHECIDA
            )
            aguardando_header = True
            continue

        if _RX_DESP_ADM.match(primeiro) and secao in (_SECAO_TAB2_SERVICO, _SECAO_TAB2_ADMIN):
            secao = _SECAO_TAB2_ADMIN
            aguardando_header = True
            continue

        # ------------------------------------------------------------------
        # Ignorar linhas estruturais
        # ------------------------------------------------------------------
        if _eh_linha_vazia(celulas):
            continue
        if _eh_linha_total(celulas):
            continue
        if _eh_linha_rodape(celulas):
            continue

        # Se seção desconhecida ainda não iniciou, pular
        if secao == _SECAO_DESCONHECIDA:
            continue

        # ------------------------------------------------------------------
        # Detectar e pular linha de cabeçalho
        # ------------------------------------------------------------------
        if aguardando_header and (
            _RX_THEAD_ITEM.match(primeiro) or _RX_THEAD_VALOR.search(primeiro)
        ):
            aguardando_header = False
            continue

        # ------------------------------------------------------------------
        # Processar linha de despesa
        # ------------------------------------------------------------------
        nome = primeiro
        if not nome:
            continue

        # Coletar todos os valores numéricos da linha (exceto a primeira célula)
        valores = []
        for c in celulas:
            if c == nome:
                continue
            v = _normalizar_valor(c)
            if v > 0:
                valores.append(v)

        # Sem nenhum número → provavelmente cabeçalho residual ou lixo
        if not valores:
            continue

        rubrica = _RUBRICA_MAP.get(secao, 'Outras Despesas')

        # Valor mensal:
        #   Tabelas 1 e 2 → primeira coluna de valor (coluna A = valor mensal)
        #   Tabela 3       → apenas total disponível; dividir por num_meses
        # ------------------------------------------------------------------
        # Calcular valor por mês e número de meses ativos para este item
        # ------------------------------------------------------------------
        if secao == _SECAO_TAB3:
            # Tabela 3: apenas valor total disponível → concentrar no Mês 1
            valor_row = valores[-1]
            n_meses_row = 1
        else:
            # Tabelas 1 & 2: valores[0] = estimado mensal; valores[-1] = total
            valor_row = valores[0]           # coluna (A) ou (C)
            if len(valores) >= 2:
                total = valores[-1]
                if valor_row > 0 and total > valor_row:
                    # n de meses = total / mensal, limitado à duração do projeto
                    n_meses_row = min(round(total / valor_row), num_meses)
                else:
                    n_meses_row = num_meses
            else:
                n_meses_row = num_meses      # sem coluna total: assume todos os meses

        if valor_row == 0.0:
            avisos.append(f'"{nome}" ({rubrica}): valor = 0, linha ignorada')
            continue

        # ------------------------------------------------------------------
        # Deduplicar nomes repetidos (ex: "Articulador(a)" ×3)
        # ------------------------------------------------------------------
        contagem_nomes[nome] = contagem_nomes.get(nome, 0) + 1
        ocorrencia = contagem_nomes[nome]

        if ocorrencia > 1:
            nome_final = f'{nome} {ocorrencia}'
            # Renomear retroativamente a PRIMEIRA ocorrência ao detectar a segunda
            if ocorrencia == 2:
                for r in rows:
                    if r['Categoria de Despesa'] == nome and r['Rubrica'] == rubrica:
                        r['Categoria de Despesa'] = f'{nome} 1'
                        break
        else:
            nome_final = nome

        # ------------------------------------------------------------------
        # Montar row compatível com importFromJson()
        # Meses além de n_meses_row ficam com 0 (item não se aplica a esse período)
        # ------------------------------------------------------------------
        row = {
            'Rubrica': rubrica,
            'Quantidade': 1,
            'Categoria de Despesa': nome_final,
        }
        for m_idx in range(1, num_meses + 1):
            row[f'Mês {m_idx}'] = valor_row if m_idx <= n_meses_row else 0.0

        rows.append(row)

    if not rows:
        avisos.append(
            'Nenhuma linha extraída. Verifique se o arquivo corresponde '
            'ao Modelo 1 (Anexo III) e se possui as tabelas esperadas.'
        )

    return rows, avisos


# ===========================================================================
# PARSER: MODELO 2 — DIEESE (Proposta Orçamentária com RH CLT)
# ===========================================================================
#
# Estrutura esperada:
#   Recursos Humanos - CLT
#     [cabeçalho: Cargo | Carga h. | Val.Hora | (a) Nº meses | (b) Salário |
#                (c) INSS 20% | (d) FGTS 8% | (e) PIS 1% | (f) Sal+enc | ...]
#     [linhas de dados — um funcionário por linha]
#     TOTAL 1 (ignorar)
#
#   Tabela 2  — Despesas Correntes       → rubrica "Administrativas"
#   Tabela 3  — Materiais de consumo     → rubrica "Outras Despesas"
#   Tabela 3a — Materiais/equipamentos   → rubrica "Outras Despesas"
#   Tabela 4  — Serviços de Terceiros    → rubrica "Serviços de Terceiros"
#               col 1 = mensal (pode ser vazio); col 2 = total
#               Se mensal vazio  → total entra apenas no Mês 1
#   Tabela 4a — Proporções/redistribuição → IGNORAR
#   Tabela 5  — Total geral              → IGNORAR
#
# Lógica de encargos (INSS, FGTS, PIS):
#   Cada funcionário tem seus encargos próprios (colunas c, d, e).
#   Para o mês M, somam-se os encargos de todos os funcionários
#   cujo n_meses_emp >= M. Isso gera 3 linhas extras com valores
#   variáveis por mês (correspondendo exatamente ao resultado esperado).
# ===========================================================================

_S2_INICIO = 0
_S2_RH     = 1   # Recursos Humanos → Pessoal (salário) + encargos agregados
_S2_TAB2   = 2   # Despesas Correntes → Administrativas
_S2_TAB3   = 3   # Materiais de consumo → Outras Despesas
_S2_TAB3A  = 4   # Materiais/equipamentos → Outras Despesas
_S2_TAB4   = 5   # Serviços de Terceiros
_S2_IGNORE = 9   # Tabela 4a, Tabela 5, preamble


def _parse_modelo_2_dieese(linhas, num_meses):
    """
    Parser para o Modelo 2 (DIEESE-style, RH CLT com encargos por funcionário).
    Retorna (rows, avisos).
    """
    avisos = []

    secao            = _S2_INICIO
    aguardando_header = False

    # Posições das colunas no bloco RH (detectadas do cabeçalho; fallback = posições conhecidas)
    col_n_meses = 3
    col_salario = 4
    col_inss    = 5
    col_fgts    = 6
    col_pis     = 7

    employees = []  # dicts: nome_key, nome_display, n_meses, salario, inss, fgts, pis
    outras    = []  # dicts: nome, rubrica, valor, n_meses  (Tab2, Tab3, Tab3a)
    servicos  = []  # dicts: nome, valor, n_meses           (Tab4)

    contagem_nomes = {}

    # Closure: acessa `celulas` do escopo externo (valor atual na iteração do loop)
    def _sv(idx):
        return _normalizar_valor(celulas[idx]) if idx < len(celulas) else 0.0

    celulas = []  # inicializa para evitar referência antes da atribuição

    for linha in linhas:
        celulas = [str(c).strip() for c in linha]
        primeiro = _primeiro_cel_nao_vazio(celulas)
        texto_linha = ' '.join(c.lower() for c in celulas if c)

        # ── Transições de seção ────────────────────────────────────────────
        if re.match(r'^recursos humanos', primeiro, re.IGNORECASE):
            secao = _S2_RH
            aguardando_header = True
            contagem_nomes = {}
            continue

        if re.match(r'^tabela', primeiro, re.IGNORECASE):
            m_tab = _RX_TABELA.search(primeiro)
            if m_tab:
                num_tab = int(m_tab.group(1))
                # Detectar sub-tabelas (3a, 4a) pelo sufixo após o número
                sufixo = primeiro[m_tab.end():].strip().lower()
                is_sub = sufixo.startswith('a') or sufixo.startswith('.a')
                if is_sub:
                    secao = _S2_TAB3A if num_tab == 3 else _S2_IGNORE
                else:
                    secao = {2: _S2_TAB2, 3: _S2_TAB3, 4: _S2_TAB4}.get(num_tab, _S2_IGNORE)
                aguardando_header = True
                contagem_nomes = {}
            continue

        # ── Linhas sempre ignoradas ────────────────────────────────────────
        if secao == _S2_IGNORE:
            continue
        if _eh_linha_vazia(celulas):
            continue
        if _eh_linha_total(celulas):
            continue
        if _eh_linha_rodape(celulas):
            continue
        if secao == _S2_INICIO:
            continue

        # ── Cabeçalhos / rótulos de seção ─────────────────────────────────
        if aguardando_header:
            if secao == _S2_RH:
                # Header RH: linha que tem "(a)" em alguma célula
                if any(re.search(r'\(a\)', c, re.IGNORECASE) for c in celulas):
                    for i, c in enumerate(celulas):
                        cl = c.replace('\xa0', ' ').strip().lower()
                        m_code = re.match(r'^\s*\(([a-z])\)', cl)
                        if m_code:
                            code = m_code.group(1)
                            if   code == 'a': col_n_meses = i
                            elif code == 'b': col_salario = i
                            elif code == 'c': col_inss    = i
                            elif code == 'd': col_fgts    = i
                            elif code == 'e': col_pis     = i
                    aguardando_header = False
                # Pular a linha de header (e qualquer linha anterior a ele em RH)
                continue
            # --- Seções não-RH -------------------------------------------------

            # Cabeçalhos genéricos: contém "valor estimado", sub-linhas "(B) x ...",
            # ou rótulos de sub-seção sem dados
            if 'valor estimado' in texto_linha:
                continue
            if re.match(r'^\(', primeiro):
                continue
            if re.match(r'^(outros pagamentos|materiais|despesas correntes|serviços)',
                         primeiro, re.IGNORECASE):
                continue
            aguardando_header = False

        if not primeiro:
            continue

        # ── Processar dado por seção ───────────────────────────────────────
        if secao == _S2_RH:
            _nm = _sv(col_n_meses)
            n_meses_emp = min(int(_nm), num_meses) if _nm > 0 else num_meses
            salario = _sv(col_salario)
            if salario == 0:
                continue
            inss = _sv(col_inss)
            fgts = _sv(col_fgts)
            pis  = _sv(col_pis)

            contagem_nomes[primeiro] = contagem_nomes.get(primeiro, 0) + 1
            oc = contagem_nomes[primeiro]
            nome_display = primeiro[0].upper() + primeiro[1:] if primeiro else primeiro
            if oc > 1:
                nome_display = f'{nome_display} {oc}'
                if oc == 2:
                    # Renomear retroativamente a primeira ocorrência
                    for emp in employees:
                        if emp['nome_key'] == primeiro:
                            emp['nome_display'] = emp['nome_display'] + ' 1'
                            break
            employees.append({
                'nome_key':    primeiro,
                'nome_display': nome_display,
                'n_meses': n_meses_emp,
                'salario': salario,
                'inss':    inss,
                'fgts':    fgts,
                'pis':     pis,
            })

        elif secao in (_S2_TAB2, _S2_TAB3, _S2_TAB3A):
            vals = [_normalizar_valor(c) for c in celulas[1:] if _normalizar_valor(c) > 0]
            if not vals:
                continue
            mensal = vals[0]
            total  = vals[-1] if len(vals) >= 2 else mensal
            n = min(round(total / mensal), num_meses) if total > mensal else 1
            rubrica = 'Administrativas' if secao == _S2_TAB2 else 'Outras Despesas'
            outras.append({'nome': primeiro, 'rubrica': rubrica, 'valor': mensal, 'n_meses': n})

        elif secao == _S2_TAB4:
            mensal = _normalizar_valor(celulas[1]) if len(celulas) > 1 else 0.0
            total  = _normalizar_valor(celulas[2]) if len(celulas) > 2 else 0.0
            if total == 0:  total  = mensal
            if mensal == 0: mensal = total
            if mensal == 0:
                continue
            n = min(round(total / mensal), num_meses) if total > mensal else 1
            servicos.append({'nome': primeiro, 'valor': mensal, 'n_meses': n})

    # ── Construir rows de saída ────────────────────────────────────────────
    rows = []

    # 1. Salários individuais (rubrica Pessoal)
    for emp in employees:
        row = {
            'Rubrica': 'Pessoal',
            'Quantidade': 1,
            'Categoria de Despesa': emp['nome_display'],
        }
        for m in range(1, num_meses + 1):
            row[f'Mês {m}'] = emp['salario'] if m <= emp['n_meses'] else 0.0
        rows.append(row)

    # 2. Encargos agregados por mês (INSS, FGTS, PIS)
    #    Soma apenas os funcionários ativos no mês m (m <= n_meses_emp)
    for label, campo in [('INSS Patronal', 'inss'), ('FGTS', 'fgts'), ('PIS', 'pis')]:
        valores_mes = [
            round(sum(e[campo] for e in employees if m <= e['n_meses']), 2)
            for m in range(1, num_meses + 1)
        ]
        if any(v > 0 for v in valores_mes):
            row = {'Rubrica': 'Pessoal', 'Quantidade': 1, 'Categoria de Despesa': label}
            for m, v in enumerate(valores_mes, 1):
                row[f'Mês {m}'] = v
            rows.append(row)

    # 3. Outras despesas (Tabelas 2, 3, 3a)
    for item in outras:
        row = {
            'Rubrica': item['rubrica'],
            'Quantidade': 1,
            'Categoria de Despesa': item['nome'],
        }
        for m in range(1, num_meses + 1):
            row[f'Mês {m}'] = item['valor'] if m <= item['n_meses'] else 0.0
        rows.append(row)

    # 4. Serviços de Terceiros (Tabela 4)
    for svc in servicos:
        row = {
            'Rubrica': 'Serviços de Terceiros',
            'Quantidade': 1,
            'Categoria de Despesa': svc['nome'],
        }
        for m in range(1, num_meses + 1):
            row[f'Mês {m}'] = svc['valor'] if m <= svc['n_meses'] else 0.0
        rows.append(row)

    # Aviso sobre num_meses do projeto vs máximo de meses dos funcionários
    if employees:
        max_meses_emp = max(e['n_meses'] for e in employees)
        if max_meses_emp > num_meses:
            avisos.append(
                f'Atenção: o maior nº de meses de um funcionário ({max_meses_emp}) '
                f'é maior que os meses configurados na tabela ({num_meses}). '
                f'Colunas extras foram truncadas.'
            )

    if not rows:
        avisos.append(
            'Nenhuma linha extraída do Modelo 2 (DIEESE). '
            'Verifique se o arquivo contém as seções "Recursos Humanos" e "Tabela 4".'
        )

    return rows, avisos
