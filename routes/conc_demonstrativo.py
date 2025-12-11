"""
Rotas para Demonstrativo de Execução Financeira
Exibe demonstrativo mensal de execução financeira para prestações de contas do DP ou Misto
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor
from functools import wraps
from decorators import requires_access
from datetime import datetime
from dateutil.relativedelta import relativedelta

bp = Blueprint('conc_demonstrativo', __name__, url_prefix='/conc_demonstrativo')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Não autorizado'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
@requires_access('conc_demonstrativo')
def index():
    """Página principal do demonstrativo de execução financeira"""
    return render_template('analises_pc/conc_demonstrativo.html')


@bp.route('/api/dados')
@login_required
@requires_access('conc_demonstrativo')
def obter_dados():
    """
    Retorna os dados do demonstrativo de execução financeira
    Apenas para termos com responsabilidade_analise = 1 (DP) ou 2 (Misto)
    """
    try:
        numero_termo = request.args.get('termo')
        ocultar_taxas = request.args.get('ocultar_taxas', 'true').lower() == 'true'
        excluir_pg = request.args.get('excluir_pg', 'true').lower() == 'true'
        
        if not numero_termo:
            return jsonify({'erro': 'Termo não informado'}), 400
        
        cursor = get_cursor()
        
        # Verificar se o termo tem análise do DP ou Mista
        cursor.execute("""
            SELECT pa.responsabilidade_analise, p.inicio
            FROM public.parcerias_analises pa
            INNER JOIN public.parcerias p ON p.numero_termo = pa.numero_termo
            WHERE pa.numero_termo = %s
        """, (numero_termo,))
        
        analise = cursor.fetchone()
        
        if not analise:
            return jsonify({'erro': 'Termo não encontrado ou sem prestação de contas cadastrada'}), 404
        
        responsabilidade = analise['responsabilidade_analise']
        
        if responsabilidade not in [1, 2]:
            return jsonify({'erro': 'Demonstrativo disponível apenas para análises do DP ou Mistas'}), 403
        
        data_inicio = analise['inicio']
        
        # Buscar número máximo de meses
        cursor.execute("""
            SELECT MAX(mes) as total_meses
            FROM public.parcerias_despesas
            WHERE numero_termo = %s
        """, (numero_termo,))
        
        resultado = cursor.fetchone()
        total_meses = resultado['total_meses'] if resultado and resultado['total_meses'] else 0
        
        if total_meses == 0:
            return jsonify({'erro': 'Não há despesas cadastradas para este termo'}), 404
        
        # ===== OTIMIZAÇÃO: BUSCAR TODOS OS DADOS DE UMA VEZ =====
        
        # 1. Buscar TODAS as despesas previstas de uma vez
        cursor.execute("""
            SELECT categoria_despesa, mes, COALESCE(SUM(valor), 0) as previsto
            FROM public.parcerias_despesas
            WHERE numero_termo = %s
            GROUP BY categoria_despesa, mes
            ORDER BY MIN(id), mes
        """, (numero_termo,))
        
        despesas_previstas = {}
        categorias_previstas = []
        categorias_vistas = set()
        
        for row in cursor.fetchall():
            cat = row['categoria_despesa']
            mes = row['mes']
            
            # Manter ordem de inserção (primeiro ID)
            if cat not in categorias_vistas:
                categorias_previstas.append(cat)
                categorias_vistas.add(cat)
            
            if cat not in despesas_previstas:
                despesas_previstas[cat] = {}
            despesas_previstas[cat][mes] = float(row['previsto'])
        
        # 2. Buscar TODAS as despesas executadas de uma vez
        cursor.execute("""
            SELECT 
                cat_transacao,
                DATE_TRUNC('month', competencia) as mes_ref,
                COALESCE(SUM(CASE WHEN cat_avaliacao IS NOT NULL THEN ABS(discriminacao) ELSE 0 END), 0) as executado,
                COALESCE(SUM(CASE WHEN cat_avaliacao = 'Avaliado' THEN ABS(discriminacao) ELSE 0 END), 0) as considerado
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s
          AND discriminacao IS NOT NULL
          AND cat_transacao IS NOT NULL
          AND (NOT %s OR cat_avaliacao != 'Pessoa Gestora')
        GROUP BY cat_transacao, DATE_TRUNC('month', competencia)
    """, (numero_termo, excluir_pg))
    
        despesas_executadas = {}
        despesas_executadas_map = {}  # Mapa categoria_lower -> categoria_original
        resultado_extrato = cursor.fetchall()
        
        for row in resultado_extrato:
            cat = row['cat_transacao']
            if not cat:  # Skip if NULL
                continue
                
            cat_lower = cat.lower().strip()
            mes_ref = row['mes_ref']
            executado = float(row['executado'])
            considerado = float(row['considerado'])
            
            # Converter datetime com timezone para datetime sem timezone (apenas date)
            if hasattr(mes_ref, 'replace'):
                mes_ref_key = mes_ref.replace(tzinfo=None)
            else:
                mes_ref_key = mes_ref
            
            # Usar lowercase como chave, mas guardar original
            if cat_lower not in despesas_executadas_map:
                despesas_executadas_map[cat_lower] = cat
            
            if cat_lower not in despesas_executadas:
                despesas_executadas[cat_lower] = {}
            despesas_executadas[cat_lower][mes_ref_key] = {
                'executado': executado,
                'considerado': considerado
            }
        
        # Adicionar categorias extras
        categorias_extras = ['Débitos Indevidos']
        
        # Adicionar Taxas Bancárias apenas se não for para ocultar
        if not ocultar_taxas:
            categorias_extras.append('Taxas Bancárias')
        
        categorias_extras.extend(['Juros e/ou multas', 'Débitos não Identificados'])
        
        todas_categorias = categorias_previstas + categorias_extras
        
        # ===== GERAR DADOS PARA CADA MÊS (SEM QUERIES NO LOOP) =====
        meses_dados = []
        
        for mes_num in range(1, total_meses + 1):
            # Calcular competência do mês
            data_mes = datetime.strptime(str(data_inicio), '%Y-%m-%d') + relativedelta(months=mes_num - 1)
            competencia_str = data_mes.strftime('%b/%y').lower()
            competencia_date = data_mes.replace(day=1)
            
            linhas = []
            
            for categoria in todas_categorias:
                # PREVISTO: buscar do dicionário
                previsto = despesas_previstas.get(categoria, {}).get(mes_num, 0)
                
                # EXECUTADO e CONSIDERADO: buscar do dicionário (case-insensitive)
                cat_lower = categoria.lower().strip()
                exec_data = despesas_executadas.get(cat_lower, {}).get(competencia_date, {'executado': 0, 'considerado': 0})
                executado = exec_data['executado']
                considerado = exec_data['considerado']
                
                # Cálculos derivados
                nao_utilizado = max(0, previsto - executado)
                glosa = executado - considerado
                uso_a_maior = max(0, executado - previsto)
                
                linhas.append({
                    'categoria': categoria,
                    'previsto': previsto,
                    'executado': executado,
                    'considerado': considerado,
                    'nao_utilizado': nao_utilizado,
                    'glosa': glosa,
                    'uso_a_maior': uso_a_maior
                })
            
            # Calcular totais do mês
            total_previsto = sum(l['previsto'] for l in linhas)
            total_executado = sum(l['executado'] for l in linhas)
            total_considerado = sum(l['considerado'] for l in linhas)
            total_nao_utilizado = sum(l['nao_utilizado'] for l in linhas)
            total_glosa = sum(l['glosa'] for l in linhas)
            total_uso_a_maior = sum(l['uso_a_maior'] for l in linhas)
            
            meses_dados.append({
                'mes_numero': mes_num,
                'mes_nome': competencia_str,
                'linhas': linhas,
                'totais': {
                    'previsto': total_previsto,
                    'executado': total_executado,
                    'considerado': total_considerado,
                    'nao_utilizado': total_nao_utilizado,
                    'glosa': total_glosa,
                    'uso_a_maior': total_uso_a_maior
                }
            })
        
        # QUADRO DE CÁLCULO GERAL (compilado de todos os meses)
        quadro_geral = []
        
        for categoria in todas_categorias:
            previsto_total = 0
            executado_total = 0
            considerado_total = 0
            
            for mes_data in meses_dados:
                linha_cat = next((l for l in mes_data['linhas'] if l['categoria'] == categoria), None)
                if linha_cat:
                    previsto_total += linha_cat['previsto']
                    executado_total += linha_cat['executado']
                    considerado_total += linha_cat['considerado']
            
            nao_utilizado_total = max(0, previsto_total - executado_total)
            glosa_total = executado_total - considerado_total
            uso_a_maior_total = max(0, executado_total - previsto_total)
            descontado = nao_utilizado_total + glosa_total
            
            quadro_geral.append({
                'categoria': categoria,
                'previsto': previsto_total,
                'executado': executado_total,
                'considerado': considerado_total,
                'nao_utilizado': nao_utilizado_total,
                'glosa': glosa_total,
                'uso_a_maior': uso_a_maior_total,
                'descontado': descontado
            })
        
        # Totais do quadro geral
        totais_gerais = {
            'previsto': sum(q['previsto'] for q in quadro_geral),
            'executado': sum(q['executado'] for q in quadro_geral),
            'considerado': sum(q['considerado'] for q in quadro_geral),
            'nao_utilizado': sum(q['nao_utilizado'] for q in quadro_geral),
            'glosa': sum(q['glosa'] for q in quadro_geral),
            'uso_a_maior': sum(q['uso_a_maior'] for q in quadro_geral),
        'descontado': sum(q['descontado'] for q in quadro_geral)
    }
    
        cursor.close()
        
        return jsonify({
            'numero_termo': numero_termo,
            'responsabilidade': responsabilidade,
            'total_meses': total_meses,
            'meses': meses_dados,
            'quadro_geral': quadro_geral,
            'totais_gerais': totais_gerais
        })
    
    except Exception as e:
        import traceback
        error_msg = f"Erro ao processar demonstrativo: {str(e)}"
        print(f"\n{'='*80}")
        print(f"ERRO NO DEMONSTRATIVO - Termo: {numero_termo if 'numero_termo' in locals() else 'N/A'}")
        print(f"Mensagem: {error_msg}")
        print(f"Traceback:\n{traceback.format_exc()}")
        print(f"{'='*80}\n")
        return jsonify({'erro': error_msg}), 500
