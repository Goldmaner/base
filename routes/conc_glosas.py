"""
Rotas para Relação de Despesas Glosadas.

Exibe todas as despesas marcadas como "Glosar" no extrato, organizadas por
competência e agrupadas por motivo automático de glosa.
"""

from datetime import datetime
from functools import wraps

from dateutil.relativedelta import relativedelta
from flask import Blueprint, jsonify, render_template, request, session

from db import get_cursor
from decorators import requires_access

bp = Blueprint('conc_glosas', __name__, url_prefix='/conc_glosas')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Não autorizado'}), 401
        return f(*args, **kwargs)

    return decorated_function


def _sort_competencia_key(comp_key):
    if not comp_key or comp_key == 'sem_competencia':
        return (1, '9999-12-31')
    return (0, comp_key)


def _formatar_glosa(glosa):
    texto = glosa.get('texto') or ''
    if texto:
        texto = texto[0].lower() + texto[1:]
    return f"{glosa.get('nome', '')}: {texto}" if texto else glosa.get('nome', '')


def _adicionar_linha_mes(meses_map, comp_key, linha):
    if comp_key not in meses_map:
        meses_map[comp_key] = {
            'competencia': comp_key,
            'total': 0.0,
            'linhas': []
        }

    meses_map[comp_key]['total'] += linha['valor_glosado']
    meses_map[comp_key]['linhas'].append(linha)


def _carregar_catalogo_glosas(cur):
    cur.execute("""
        SELECT id, glosa_nome, glosa_texto, glosa_inconsistencia
        FROM categoricas.c_dac_glosas
        WHERE glosa_inconsistencia IS NOT NULL
          AND TRIM(glosa_inconsistencia) != ''
    """)

    glosas_list = []
    glosas_by_id = {}

    for row in cur.fetchall():
        tags = frozenset(
            parte.strip().lower()
            for parte in (row['glosa_inconsistencia'] or '').split(';')
            if parte.strip()
        )
        glosa = {
            'id': row['id'],
            'nome': row['glosa_nome'] or '',
            'texto': row['glosa_texto'] or '',
            'tags': tags,
        }
        glosas_by_id[glosa['id']] = glosa
        if tags:
            glosas_list.append(glosa)

    return glosas_list, glosas_by_id


def _calcular_glosas_uso_maior(cur, numero_termo, data_inicio, motivo_automatico):
    """
    Calcula glosas sintéticas por "uso à maior" com base no demonstrativo.

    Considera apenas categorias previstas em public.parcerias_despesas.
    """
    if not data_inicio:
        return []

    cur.execute("""
        SELECT categoria_despesa, mes, COALESCE(SUM(valor), 0) AS previsto
        FROM public.parcerias_despesas
        WHERE numero_termo = %s
        GROUP BY categoria_despesa, mes
        ORDER BY MIN(id), mes
    """, (numero_termo,))

    despesas_previstas = {}
    categorias_previstas = []
    categorias_vistas = set()
    total_meses = 0

    for row in cur.fetchall():
        categoria = row['categoria_despesa']
        mes = int(row['mes'] or 0)

        if categoria not in categorias_vistas:
            categorias_previstas.append(categoria)
            categorias_vistas.add(categoria)

        despesas_previstas.setdefault(categoria, {})[mes] = float(row['previsto'] or 0)
        total_meses = max(total_meses, mes)

    if not categorias_previstas or total_meses <= 0:
        return []

    cur.execute("""
        SELECT
            cat_transacao,
            DATE_TRUNC('month', competencia) AS mes_ref,
            COALESCE(SUM(CASE WHEN cat_avaliacao IS NOT NULL THEN ABS(discriminacao) ELSE 0 END), 0) AS executado
        FROM analises_pc.conc_extrato
        WHERE numero_termo = %s
          AND discriminacao IS NOT NULL
          AND cat_transacao IS NOT NULL
          AND cat_avaliacao IS NOT NULL
          AND cat_avaliacao != 'Pessoa Gestora'
        GROUP BY cat_transacao, DATE_TRUNC('month', competencia)
    """, (numero_termo,))

    despesas_executadas = {}
    for row in cur.fetchall():
        categoria = (row['cat_transacao'] or '').strip().lower()
        if not categoria:
            continue

        mes_ref = row['mes_ref']
        mes_ref_key = mes_ref.date().isoformat() if hasattr(mes_ref, 'date') else str(mes_ref)[:10]
        despesas_executadas.setdefault(categoria, {})[mes_ref_key] = float(row['executado'] or 0)

    data_base = data_inicio.date() if isinstance(data_inicio, datetime) else data_inicio
    linhas = []

    for mes_num in range(1, total_meses + 1):
        data_mes = (datetime.combine(data_base, datetime.min.time()) + relativedelta(months=mes_num - 1)).date()
        comp_key = data_mes.replace(day=1).isoformat()

        for categoria in categorias_previstas:
            previsto = float(despesas_previstas.get(categoria, {}).get(mes_num, 0) or 0)
            executado = float(
                despesas_executadas
                .get(categoria.lower().strip(), {})
                .get(comp_key, 0) or 0
            )
            uso_a_maior = max(0.0, round(executado - previsto, 2))

            if uso_a_maior <= 0:
                continue

            linhas.append({
                'id': f'uso-maior:{comp_key}:{categoria}',
                'indice': None,
                'data': comp_key,
                'debito': None,
                'valor_glosado': uso_a_maior,
                'cat_transacao': categoria,
                'competencia': comp_key,
                'origem_destino': 'Uso à maior apurado automaticamente no demonstrativo',
                'avaliacao_analista': '',
                'motivo_automatico': motivo_automatico,
            })

    return linhas


@bp.route('/')
@login_required
@requires_access('conc_bancaria')
def index():
    """Página principal da relação de despesas glosadas."""
    return render_template('analises_pc/conc_glosas.html')


@bp.route('/api/dados')
@login_required
@requires_access('conc_bancaria')
def api_dados():
    """
    Retorna todas as despesas com cat_avaliacao = 'Glosar', agrupadas por competência.

    Query params:
      - termo: numero_termo
      - incluir_uso_maior: true/false
    """
    try:
        numero_termo = request.args.get('termo', '').strip()
        incluir_uso_maior = request.args.get('incluir_uso_maior', 'false').strip().lower() in (
            '1', 'true', 'yes', 'on'
        )

        if not numero_termo:
            return jsonify({'erro': 'Termo não informado'}), 400

        cur = get_cursor()

        cur.execute("""
            SELECT osc, inicio, final
            FROM public.parcerias
            WHERE numero_termo = %s
        """, (numero_termo,))
        parceria = cur.fetchone()

        parceria_inicio = parceria['inicio'] if parceria and parceria['inicio'] else None
        entidade = parceria['osc'] if parceria and parceria['osc'] else ''
        inicio = parceria_inicio.isoformat() if parceria_inicio else None
        final = parceria['final'].isoformat() if parceria and parceria['final'] else None

        glosas_list, glosas_by_id = _carregar_catalogo_glosas(cur)

        # Traduz valores da seção 3 da conciliação para as tags usadas no catálogo.
        analise_tag_map = [
            ('avaliacao_guia', 'não apresentada', 'despesa sem guia'),
            ('avaliacao_comprovante', 'pago em cheque', 'pago em cheque'),
            ('avaliacao_comprovante', 'pago em espécie', 'pago em espécie'),
            ('avaliacao_comprovante', 'cartão de crédito', 'pago por cartão de crédito'),
            ('avaliacao_comprovante', 'não apresentado', 'comprovante não apresentado'),
            ('avaliacao_contratos', 'não apresentado', 'despesa sem contrato'),
        ]

        # Categorias que precisam expandir semanticamente para casar com o catálogo.
        cat_transacao_extra_tags = {
            'débitos indevidos': frozenset({
                'despesas não previstas',
                'despesa sem previsão no período',
            }),
            'juros e/ou multas': frozenset({
                'juros e multas',
                'restituição de multas e juros',
            }),
        }

        # Palavras-chave em observações/origem-destino que disparam motivos conhecidos.
        texto_livre_tag_map = [
            ('reembolso', 'reembolsos sem comprovação'),
            ('duplicidade', 'pagamento em duplicidade'),
            ('outro favorecido', 'pagamento para outro favorecido'),
            ('alteração do vínculo', 'alteração de vínculo de contratado'),
            ('alteracao do vinculo', 'alteração de vínculo de contratado'),
            ('taxa bancária', 'taxas bancárias'),
            ('taxas bancárias', 'taxas bancárias'),
            ('multas e juros', 'restituição de multas e juros'),
            ('juros e multas', 'restituição de multas e juros'),
            ('especificar', 'ausência de descrição de despesa'),
        ]

        def _build_motivo(
            cat_transacao,
            avaliacao_analista,
            avaliacao_guia=None,
            avaliacao_comprovante=None,
            avaliacao_contratos=None,
            avaliacao_fora_municipio=None,
            origem_destino=None,
        ):
            tx_tags = set()

            if cat_transacao and cat_transacao.strip():
                categoria_lower = cat_transacao.strip().lower()
                tx_tags.add(categoria_lower)
                tx_tags.update(cat_transacao_extra_tags.get(categoria_lower, set()))

            analise_vals = {
                'avaliacao_guia': (avaliacao_guia or '').strip().lower(),
                'avaliacao_comprovante': (avaliacao_comprovante or '').strip().lower(),
                'avaliacao_contratos': (avaliacao_contratos or '').strip().lower(),
            }
            for field, cond, tag in analise_tag_map:
                if analise_vals.get(field) == cond:
                    tx_tags.add(tag)

            if avaliacao_fora_municipio and avaliacao_fora_municipio.strip():
                tx_tags.add(avaliacao_fora_municipio.strip().lower())

            texto_analista = (avaliacao_analista or '').lower()
            texto_destino = (origem_destino or '').lower()
            for keyword, tag in texto_livre_tag_map:
                if keyword in texto_analista or keyword in texto_destino:
                    tx_tags.add(tag)

            if not tx_tags:
                return avaliacao_analista or ''

            all_full = []
            best_partial = []
            best_partial_n = 0

            for glosa in glosas_list:
                intersecao = glosa['tags'] & tx_tags
                if not intersecao:
                    continue

                if intersecao == glosa['tags']:
                    all_full.append(glosa)
                else:
                    tamanho = len(intersecao)
                    if tamanho > best_partial_n:
                        best_partial_n = tamanho
                        best_partial = [glosa]
                    elif tamanho == best_partial_n:
                        best_partial.append(glosa)

            if all_full:
                all_full.sort(key=lambda glosa: len(glosa['tags']), reverse=True)
                candidates = [
                    glosa for glosa in all_full
                    if not any(glosa['tags'] < outra['tags'] for outra in all_full if outra is not glosa)
                ]
            else:
                candidates = best_partial

            if not candidates:
                return avaliacao_analista or ''

            if len(candidates) == 1:
                return _formatar_glosa(candidates[0])

            return '\n'.join(
                f"{idx}. {_formatar_glosa(glosa)}"
                for idx, glosa in enumerate(candidates, 1)
            )

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

        meses_map = {}
        total_glosado = 0.0
        total_linhas = len(rows)
        total_linhas_uso_maior = 0

        for row in rows:
            comp = row['competencia']
            comp_key = comp.isoformat() if comp else 'sem_competencia'
            valor = float(row['valor_glosado'] or 0)
            total_glosado += valor

            cat_transacao = row['cat_transacao'] or ''
            avaliacao_analista = row['avaliacao_analista'] or ''

            _adicionar_linha_mes(meses_map, comp_key, {
                'id': row['id'],
                'indice': row['indice'],
                'data': row['data'].isoformat() if row['data'] else None,
                'debito': float(row['debito']) if row['debito'] else None,
                'valor_glosado': valor,
                'cat_transacao': cat_transacao,
                'competencia': comp_key,
                'origem_destino': row['origem_destino'] or '',
                'avaliacao_analista': avaliacao_analista,
                'motivo_automatico': _build_motivo(
                    cat_transacao,
                    avaliacao_analista,
                    avaliacao_guia=row.get('avaliacao_guia'),
                    avaliacao_comprovante=row.get('avaliacao_comprovante'),
                    avaliacao_contratos=row.get('avaliacao_contratos'),
                    avaliacao_fora_municipio=row.get('avaliacao_fora_municipio'),
                    origem_destino=row.get('origem_destino'),
                ),
            })

        if incluir_uso_maior:
            glosa_uso_maior = glosas_by_id.get(7)
            motivo_uso_maior = (
                _formatar_glosa(glosa_uso_maior)
                if glosa_uso_maior
                else 'Execução de montante superior ao previsto'
            )

            linhas_uso_maior = _calcular_glosas_uso_maior(
                cur,
                numero_termo,
                parceria_inicio,
                motivo_uso_maior,
            )

            for linha in linhas_uso_maior:
                _adicionar_linha_mes(meses_map, linha['competencia'], linha)
                total_glosado += linha['valor_glosado']
                total_linhas += 1
                total_linhas_uso_maior += 1

        meses = []
        for comp_key in sorted(meses_map.keys(), key=_sort_competencia_key):
            mes = meses_map[comp_key]
            grupos_map = {}
            grupos_order = []

            for linha in mes['linhas']:
                motivo = linha['motivo_automatico'] or ''
                if motivo not in grupos_map:
                    grupos_map[motivo] = {'motivo': motivo, 'total': 0.0, 'linhas': []}
                    grupos_order.append(motivo)

                grupos_map[motivo]['total'] = round(
                    grupos_map[motivo]['total'] + linha['valor_glosado'],
                    2,
                )
                grupos_map[motivo]['linhas'].append(linha)

            mes['grupos'] = sorted(
                (grupos_map[key] for key in grupos_order),
                key=lambda grupo: (grupo['motivo'] == '', -grupo['total'])
            )
            del mes['linhas']
            meses.append(mes)

        return jsonify({
            'numero_termo': numero_termo,
            'entidade': entidade,
            'inicio': inicio,
            'final': final,
            'total_glosado': round(total_glosado, 2),
            'total_linhas': total_linhas,
            'incluir_uso_maior': incluir_uso_maior,
            'total_linhas_uso_maior': total_linhas_uso_maior,
            'meses': meses,
        })

    except Exception as e:
        import traceback

        print(f"[ERRO] conc_glosas/api/dados: {e}")
        print(traceback.format_exc())
        return jsonify({'erro': str(e)}), 500
