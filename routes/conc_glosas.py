"""
Rotas para Relação de Despesas Glosadas
Exibe todas as despesas marcadas como 'Glosar' no extrato, organizadas por competência
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor
from functools import wraps
from decorators import requires_access, requires_write_access

bp = Blueprint('conc_glosas', __name__, url_prefix='/conc_glosas')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Não autorizado'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
@requires_access('conc_bancaria')
def index():
    """Página principal da relação de despesas glosadas"""
    return render_template('analises_pc/conc_glosas.html')


@bp.route('/api/dados')
@login_required
@requires_access('conc_bancaria')
def api_dados():
    """
    Retorna todas as despesas com cat_avaliacao = 'Glosar', agrupadas por competência.
    Query param: termo (numero_termo)
    """
    try:
        numero_termo = request.args.get('termo', '').strip()

        if not numero_termo:
            return jsonify({'erro': 'Termo não informado'}), 400

        cur = get_cursor()

        # Buscar dados do termo
        cur.execute("""
            SELECT osc, inicio, final
            FROM public.parcerias
            WHERE numero_termo = %s
        """, (numero_termo,))
        parceria = cur.fetchone()

        entidade = parceria['osc'] if parceria and parceria['osc'] else ''
        inicio = parceria['inicio'].isoformat() if parceria and parceria['inicio'] else None
        final = parceria['final'].isoformat() if parceria and parceria['final'] else None

        # ── Carregar catálogo de glosas e montar lista de tags para matching ──
        cur.execute("""
            SELECT id, glosa_nome, glosa_texto, glosa_inconsistencia
            FROM categoricas.c_dac_glosas
            WHERE glosa_inconsistencia IS NOT NULL
              AND TRIM(glosa_inconsistencia) != ''
        """)
        glosas_catalogo = cur.fetchall()

        # Cada entrada: {nome, texto, tags: frozenset of lower-case tags}
        _glosas_list = []
        for g in glosas_catalogo:
            tags = frozenset(
                p.strip().lower()
                for p in (g['glosa_inconsistencia'] or '').split(';')
                if p.strip()
            )
            if tags:
                _glosas_list.append({
                    'nome': g['glosa_nome'] or '',
                    'texto': g['glosa_texto'] or '',
                    'tags': tags,
                })

        # ── Mapeamento semântico: (campo_analise, valor_lower) → tag_lower ─────
        # Traduz valores de conc_analise para as labels usadas em glosa_inconsistencia.
        # Adicione aqui novos mapeamentos conforme necessário.
        _ANALISE_TAG_MAP = [
            ('avaliacao_guia',        'não apresentada',   'despesa sem guia'),
            ('avaliacao_comprovante', 'pago em cheque',    'pago em cheque'),
            ('avaliacao_comprovante', 'pago em espécie',   'pago em espécie'),
            ('avaliacao_comprovante', 'cartão de crédito', 'cartão de crédito'),
            ('avaliacao_contratos',   'não apresentado',   'despesa sem contrato'),
        ]

        # ── Mapeamento de cat_transacao → tags semânticas ────────────────────
        # Certos valores de cat_transacao correspondem a inconsistências com labels
        # diferentes em glosa_inconsistencia (ex.: card 8 do relatório de análise).
        # Cada entrada: cat_transacao_lower → frozenset de tags adicionais a injetar.
        _CAT_TRANSACAO_EXTRA_TAGS = {
            # Card 8: "Débitos Indevidos" → inconsistência "Despesas não previstas"
            'débitos indevidos': frozenset({
                'despesas não previstas',
                'despesa sem previsão no período',
            }),
        }

        # ── Mapeamento de texto livre (avaliacao_analista / origem_destino) → tags ─
        # Cards 13-16 de routes.py usam ILIKE em campos de texto livre.
        # Cada entrada: (keyword_lower, tag_lower) — correspondência por substring.
        _TEXTO_LIVRE_TAG_MAP = [
            ('reembolso',             'reembolsos sem comprovação'),     # Card 13
            ('duplicidade',           'pagamento em duplicidade'),        # Card 14
            ('outro favorecido',      'pagamento para outro favorecido'), # Card 15
            ('alteração do vínculo',  'alteração de vínculo de contratado'),  # Card 16
            ('alteração de vínculo',  'alteração de vínculo de contratado'),  # Card 16 (alt.)
            ('taxa bancária',         'taxas bancárias'),
            ('taxas bancárias',       'taxas bancárias'),
            ('multas e juros',        'restituição de multas e juros'),
        ]

        def _build_motivo(cat_transacao, avaliacao_analista,
                          avaliacao_guia=None, avaliacao_comprovante=None,
                          avaliacao_contratos=None, avaliacao_fora_municipio=None,
                          origem_destino=None):
            """
            Retorna o motivo automático com base no catálogo c_dac_glosas.

            Estratégia:
              1. Constrói o conjunto de tags da transação (cat_transacao +
                 mapeamentos semânticos de conc_analise + extra tags por cat).
              2. Encontra TODAS as glosas com full match (todos os seus tags
                 presentes em tx_tags) — uma transação pode ter motivos independentes.
              3. Fallback para partial match (maior cobertura) se não houver full.
              4. Fallback final: avaliacao_analista.
            """
            # 1. Construir conjunto de tags para esta transação
            tx_tags = set()

            if cat_transacao and cat_transacao.strip():
                ct_lower = cat_transacao.strip().lower()
                tx_tags.add(ct_lower)
                # Injetar tags semânticas extras para categorias conhecidas
                extra = _CAT_TRANSACAO_EXTRA_TAGS.get(ct_lower)
                if extra:
                    tx_tags.update(extra)

            analise_vals = {
                'avaliacao_guia':        (avaliacao_guia        or '').strip().lower(),
                'avaliacao_comprovante': (avaliacao_comprovante or '').strip().lower(),
                'avaliacao_contratos':   (avaliacao_contratos   or '').strip().lower(),
            }
            for field, cond, tag in _ANALISE_TAG_MAP:
                if analise_vals.get(field) == cond:
                    tx_tags.add(tag)

            # avaliacao_fora_municipio: adicionar o valor diretamente como tag
            if avaliacao_fora_municipio and avaliacao_fora_municipio.strip():
                tx_tags.add(avaliacao_fora_municipio.strip().lower())

            # Texto livre: procurar keywords em avaliacao_analista e origem_destino
            _texto_analista = (avaliacao_analista or '').lower()
            _texto_destino  = (origem_destino     or '').lower()
            for keyword, tag in _TEXTO_LIVRE_TAG_MAP:
                if keyword in _texto_analista or keyword in _texto_destino:
                    tx_tags.add(tag)

            if not tx_tags:
                return avaliacao_analista or ''

            # 2. Coletar TODOS os full matches (todas as tags da glosa presentes em
            #    tx_tags). Uma transação com dois problemas independentes deve exibir
            #    as duas glosas, não apenas a "melhor".
            all_full = []
            best_partial = []
            best_partial_n = 0

            for g in _glosas_list:
                isect = g['tags'] & tx_tags
                if not isect:
                    continue
                if isect == g['tags']:          # full match: todos os requisitos atendidos
                    all_full.append(g)
                else:                           # partial match: fallback
                    n = len(isect)
                    if n > best_partial_n:
                        best_partial_n = n
                        best_partial = [g]
                    elif n == best_partial_n:
                        best_partial.append(g)

            if all_full:
                # Ordenar por especificidade (mais tags = mais específico = primeiro)
                all_full.sort(key=lambda g: len(g['tags']), reverse=True)

                # Domination pruning: descartar glosa g se outra glosa h em all_full
                # possui g.tags ⊂ h.tags (subconjunto próprio).
                # Exemplo: se "sem guia + cheque" (2 tags) aplica, "sem guia" (1 tag)
                # e "cheque" (1 tag) são redundantes e não aparecem separadas.
                # Dois motivos independentes (tags disjuntas) nunca se dominam.
                candidates = [
                    g for g in all_full
                    if not any(g['tags'] < h['tags'] for h in all_full if h is not g)
                ]
            else:
                candidates = best_partial

            if not candidates:
                return avaliacao_analista or ''

            def _fmt_glosa(g):
                texto = g['texto']
                if texto:
                    texto = texto[0].lower() + texto[1:]
                return f"{g['nome']}: {texto}" if texto else g['nome']

            if len(candidates) == 1:
                return _fmt_glosa(candidates[0])

            return '\n'.join(
                f"{i}. {_fmt_glosa(g)}" for i, g in enumerate(candidates, 1)
            )

        # ── Buscar todas as glosas do termo, incluindo campos de conc_analise ──
        cur.execute("""
            SELECT
                ce.id,
                ce.indice,
                ce.data,
                ce.debito,
                COALESCE(ABS(ce.discriminacao), ce.debito) AS valor_glosado,
                ce.cat_transacao,
                ce.competencia,
                ce.origem_destino,
                ce.avaliacao_analista,
                ca.avaliacao_guia,
                ca.avaliacao_comprovante,
                ca.avaliacao_contratos,
                ca.avaliacao_fora_municipio
            FROM analises_pc.conc_extrato ce
            LEFT JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND ce.cat_avaliacao = 'Glosar'
            ORDER BY ce.competencia ASC NULLS LAST, ce.indice ASC
        """, (numero_termo,))

        rows = cur.fetchall()

        # Agrupar por competência
        meses_map = {}
        meses_order = []
        total_glosado = 0.0

        for row in rows:
            comp = row['competencia']
            comp_key = comp.isoformat() if comp else 'sem_competencia'

            if comp_key not in meses_map:
                meses_map[comp_key] = {
                    'competencia': comp_key,
                    'total': 0.0,
                    'linhas': []
                }
                meses_order.append(comp_key)

            valor = float(row['valor_glosado']) if row['valor_glosado'] else 0.0
            meses_map[comp_key]['total'] += valor
            total_glosado += valor

            cat  = row['cat_transacao']  or ''
            aval = row['avaliacao_analista'] or ''

            meses_map[comp_key]['linhas'].append({
                'id':               row['id'],
                'indice':           row['indice'],
                'data':             row['data'].isoformat() if row['data'] else None,
                'debito':           float(row['debito']) if row['debito'] else None,
                'valor_glosado':    valor,
                'cat_transacao':    cat,
                'competencia':      comp_key,
                'origem_destino':   row['origem_destino'] or '',
                'avaliacao_analista': aval,
                'motivo_automatico': _build_motivo(
                    cat, aval,
                    avaliacao_guia=row.get('avaliacao_guia'),
                    avaliacao_comprovante=row.get('avaliacao_comprovante'),
                    avaliacao_contratos=row.get('avaliacao_contratos'),
                    avaliacao_fora_municipio=row.get('avaliacao_fora_municipio'),
                    origem_destino=row.get('origem_destino'),
                ),
            })

        # ── Agrupar linhas por motivo dentro de cada mês ──────────────────
        # Transações com o mesmo motivo ficam juntas sob um cabeçalho de grupo.
        # Grupos sem motivo identificado vêm por último; dentro de cada grupo,
        # a ordem original (por índice) é preservada.
        for comp_key in meses_order:
            mes = meses_map[comp_key]
            grupos_map: dict = {}
            grupos_order: list = []
            for linha in mes['linhas']:
                motivo = linha['motivo_automatico'] or ''
                if motivo not in grupos_map:
                    grupos_map[motivo] = {'motivo': motivo, 'total': 0.0, 'linhas': []}
                    grupos_order.append(motivo)
                grupos_map[motivo]['total'] = round(
                    grupos_map[motivo]['total'] + linha['valor_glosado'], 2
                )
                grupos_map[motivo]['linhas'].append(linha)

            # Ordenar: motivos identificados por valor desc → sem motivo por último
            mes['grupos'] = sorted(
                (grupos_map[k] for k in grupos_order),
                key=lambda g: (g['motivo'] == '', -g['total'])
            )
            del mes['linhas']   # já está em grupos[].linhas

        meses = [meses_map[k] for k in meses_order]

        return jsonify({
            'numero_termo':  numero_termo,
            'entidade':      entidade,
            'inicio':        inicio,
            'final':         final,
            'total_glosado': round(total_glosado, 2),
            'total_linhas':  len(rows),
            'meses':         meses,
        })

    except Exception as e:
        import traceback
        print(f"[ERRO] conc_glosas/api/dados: {e}")
        print(traceback.format_exc())
        return jsonify({'erro': str(e)}), 500
