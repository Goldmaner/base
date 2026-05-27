"""
Rotas para Relação de Despesas Glosadas
Exibe todas as despesas marcadas como 'Glosar' no extrato, organizadas por competência
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor
from functools import wraps
from decorators import requires_access

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

        # ── Carregar catálogo de glosas uma vez para lookup de motivo automático ──
        cur.execute("""
            SELECT id, glosa_nome, glosa_texto, glosa_inconsistencia
            FROM categoricas.c_dac_glosas
            WHERE glosa_inconsistencia IS NOT NULL
              AND TRIM(glosa_inconsistencia) != ''
        """)
        glosas_catalogo = cur.fetchall()

        # Mapa: inconsistencia_lower → lista de {nome, texto}
        _glosa_lookup = {}
        for g in glosas_catalogo:
            for parte in g['glosa_inconsistencia'].split(';'):
                chave = parte.strip().lower()
                if chave:
                    _glosa_lookup.setdefault(chave, []).append({
                        'nome': g['glosa_nome'] or '',
                        'texto': g['glosa_texto'] or ''
                    })

        def _build_motivo(cat_transacao, avaliacao_analista):
            """
            Retorna o motivo automático baseado em c_dac_glosas.
            Fallback: avaliacao_analista ou string vazia.
            """
            if cat_transacao:
                matches = _glosa_lookup.get(cat_transacao.strip().lower(), [])
                if matches:
                    if len(matches) == 1:
                        g = matches[0]
                        texto = g['texto']
                        if texto:
                            texto = texto[0].lower() + texto[1:]
                        return f"{g['nome']}: {texto}" if texto else g['nome']
                    else:
                        linhas_motivo = []
                        for i, g in enumerate(matches, 1):
                            texto = g['texto']
                            if texto:
                                texto = texto[0].lower() + texto[1:]
                            linhas_motivo.append(
                                f"{i}. {g['nome']}: {texto}" if texto else f"{i}. {g['nome']}"
                            )
                        return '\n'.join(linhas_motivo)
            # Sem match: usar avaliacao_analista como fallback
            return avaliacao_analista or ''

        # Buscar todas as glosas do termo ordenadas por competência e índice
        cur.execute("""
            SELECT
                id,
                indice,
                data,
                debito,
                COALESCE(ABS(discriminacao), debito) AS valor_glosado,
                cat_transacao,
                competencia,
                origem_destino,
                avaliacao_analista
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s
              AND cat_avaliacao = 'Glosar'
            ORDER BY competencia ASC NULLS LAST, indice ASC
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

            cat = row['cat_transacao'] or ''
            aval = row['avaliacao_analista'] or ''
            meses_map[comp_key]['linhas'].append({
                'id': row['id'],
                'indice': row['indice'],
                'data': row['data'].isoformat() if row['data'] else None,
                'debito': float(row['debito']) if row['debito'] else None,
                'valor_glosado': valor,
                'cat_transacao': cat,
                'competencia': comp_key,
                'origem_destino': row['origem_destino'] or '',
                'avaliacao_analista': aval,
                'motivo_automatico': _build_motivo(cat, aval)
            })

        meses = [meses_map[k] for k in meses_order]

        return jsonify({
            'numero_termo': numero_termo,
            'entidade': entidade,
            'inicio': inicio,
            'final': final,
            'total_glosado': round(total_glosado, 2),
            'total_linhas': len(rows),
            'meses': meses
        })

    except Exception as e:
        import traceback
        print(f"[ERRO] conc_glosas/api/dados: {e}")
        print(traceback.format_exc())
        return jsonify({'erro': str(e)}), 500
