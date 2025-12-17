"""
Rotas para Conciliação - Relatório
Geração de tabelas de cálculos para diferentes tipos de responsabilidade
"""

from flask import Blueprint, render_template, request, jsonify, session, Response
from db import get_cursor, get_db
from functools import wraps
from decorators import requires_access
from datetime import datetime
from dateutil.relativedelta import relativedelta
import csv
from io import StringIO

bp = Blueprint('conc_relatorio', __name__, url_prefix='/conc_relatorio')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Não autorizado'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
@requires_access('conc_relatorio')
def index():
    """Página principal do relatório de conciliação"""
    return render_template('analises_pc/conc_relatorio.html')


@bp.route('/api/test', methods=['GET'])
@login_required
@requires_access('conc_relatorio')
def test():
    """Endpoint de teste"""
    return jsonify({'status': 'ok', 'message': 'Blueprint funcionando'})


@bp.route('/api/dados-relatorio', methods=['GET'])
@login_required
@requires_access('conc_relatorio')
def dados_relatorio():
    """Retorna dados do relatório conforme o tipo de responsabilidade"""
    conn = None
    try:
        numero_termo = request.args.get('numero_termo')
        considerar_liquido = request.args.get('considerar_liquido', 'false').lower() == 'true'
        forcar_modo = request.args.get('forcar_modo', None)  # 'pg' ou 'dp'
        
        print(f"[DEBUG RELATORIO] Iniciando busca para termo: {numero_termo}")
        if forcar_modo:
            print(f"[DEBUG RELATORIO] Modo forçado: {forcar_modo}")
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo não informado'}), 400
        
        print(f"[DEBUG RELATORIO] Conectando ao banco...")
        conn = get_db()
        cursor = get_cursor()
        
        print(f"[DEBUG RELATORIO] Executando query de parceria...")
        
        # Verificar se existe prestação com responsabilidade mista (2)
        cursor.execute("""
            SELECT COUNT(*) as total_mista
            FROM public.parcerias_analises
            WHERE numero_termo = %s
              AND responsabilidade_analise = 2
        """, (numero_termo,))
        tem_mista = cursor.fetchone()['total_mista'] > 0

        # Se tiver mista, usar responsabilidade 2 (Misto)
        # Senão, pegar a responsabilidade da primeira análise
        if tem_mista:
            responsabilidade_usar = 2
            print(f"[DEBUG RELATORIO] Detectada prestação MISTA - usando responsabilidade 2")
        else:
            cursor.execute("""
                SELECT responsabilidade_analise
                FROM public.parcerias_analises
                WHERE numero_termo = %s
                LIMIT 1
            """, (numero_termo,))
            result = cursor.fetchone()
            responsabilidade_usar = result['responsabilidade_analise'] if result else 1
            print(f"[DEBUG RELATORIO] Responsabilidade detectada: {responsabilidade_usar}")
        
        # Buscar informações da parceria
        cursor.execute("""
            SELECT 
                p.numero_termo,
                p.total_previsto,
                p.total_pago
            FROM public.parcerias p
            WHERE p.numero_termo = %s
        """, (numero_termo,))
        
        parceria = cursor.fetchone()
        
        if not parceria:
            conn.close()
            return jsonify({'erro': 'Termo não encontrado'}), 404
        
        # Usar responsabilidade detectada
        responsabilidade = responsabilidade_usar
        
        # Forçar modo se solicitado
        if forcar_modo == 'dp':
            responsabilidade = 1
            print(f"[DEBUG RELATORIO] MODO FORÇADO: DP (original: {responsabilidade_usar})")
        elif forcar_modo == 'pg':
            responsabilidade = 3
            print(f"[DEBUG RELATORIO] MODO FORÇADO: PG (original: {responsabilidade_usar})")
        
        # DEBUG: Verificar valor real
        print(f"[DEBUG RELATORIO] Termo: {numero_termo}")
        print(f"[DEBUG RELATORIO] Parceria completa: {parceria}")
        print(f"[DEBUG RELATORIO] Responsabilidade FINAL: {responsabilidade} (tipo: {type(responsabilidade)})")
        print(f"[DEBUG RELATORIO] Total previsto: {parceria['total_previsto']}")
        print(f"[DEBUG RELATORIO] Total pago: {parceria['total_pago']}")
        
        # Valores: DP=1, Misto=2, PG=3
        print(f"[DEBUG RELATORIO] Tipo de relatório detectado: {'DP' if responsabilidade == 1 else 'Misto' if responsabilidade == 2 else 'PG' if responsabilidade == 3 else 'Desconhecido'}")
        
        # Buscar rendimentos
        cursor.execute("""
            SELECT 
                COALESCE(SUM(rendimento_bruto), 0) as total_bruto,
                COALESCE(SUM(rendimento_ir), 0) as total_ir,
                COALESCE(SUM(rendimento_iof), 0) as total_iof
            FROM analises_pc.conc_rendimentos
            WHERE numero_termo = %s
        """, (numero_termo,))
        
        rendimentos_data = cursor.fetchone()
        print(f"[DEBUG RELATORIO] Rendimentos raw: {rendimentos_data}")
        total_bruto = float(rendimentos_data['total_bruto']) if rendimentos_data and rendimentos_data['total_bruto'] else 0
        total_ir = float(rendimentos_data['total_ir']) if rendimentos_data and rendimentos_data['total_ir'] else 0
        total_iof = float(rendimentos_data['total_iof']) if rendimentos_data and rendimentos_data['total_iof'] else 0
        total_liquido = total_bruto - total_ir - total_iof
        
        # Buscar contrapartida
        cursor.execute("""
            SELECT COALESCE(SUM(valor_previsto), 0) as total_contrapartida
            FROM analises_pc.conc_contrapartida
            WHERE numero_termo = %s
        """, (numero_termo,))
        
        contrapartida_data = cursor.fetchone()
        print(f"[DEBUG RELATORIO] Contrapartida raw: {contrapartida_data}")
        total_contrapartida = float(contrapartida_data['total_contrapartida']) if contrapartida_data and contrapartida_data['total_contrapartida'] else 0
        
        # Buscar categorias de transação do extrato
        cursor.execute("""
            SELECT 
                cat_transacao,
                cat_avaliacao,
                COALESCE(SUM(ABS(discriminacao)), 0) as total_valor
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s AND discriminacao IS NOT NULL
            GROUP BY cat_transacao, cat_avaliacao
        """, (numero_termo,))
        
        extrato_categorias = cursor.fetchall()
        print(f"[DEBUG RELATORIO] Categorias extrato: {extrato_categorias}")
        
        # Definir rendimento_usado (usado em ambos DP e PG)
        rendimento_usado = total_liquido if considerar_liquido else total_bruto
        
        # ==== CÁLCULOS ESPECÍFICOS PARA DEPARTAMENTO DE PARCERIAS (DP) ====
        if responsabilidade == 1:
            # 1. Valor executado e Aprovado (JOIN entre cat_transacao e categoria_despesa)
            print(f"[DEBUG DP] ===== INICIANDO CÁLCULO VALOR EXECUTADO E APROVADO =====")
            
            # Primeiro, ver quais categorias de despesa estão previstas
            cursor.execute("""
                SELECT categoria_despesa, COUNT(*) as qtd_linhas
                FROM public.parcerias_despesas
                WHERE numero_termo = %s
                GROUP BY categoria_despesa
                ORDER BY categoria_despesa
            """, (numero_termo,))
            categorias_previstas = cursor.fetchall()
            print(f"[DEBUG DP] Categorias de despesa previstas:")
            for cat in categorias_previstas:
                print(f"  - '{cat['categoria_despesa']}': {cat['qtd_linhas']} linha(s) na tabela parcerias_despesas")
            
            # Agora ver o que tem no extrato com detalhes
            cursor.execute("""
                SELECT 
                    ce.cat_transacao,
                    ce.cat_avaliacao,
                    COUNT(*) as qtd_linhas,
                    SUM(ABS(ce.discriminacao)) as total_categoria
                FROM analises_pc.conc_extrato ce
                WHERE ce.numero_termo = %s 
                    AND ce.discriminacao IS NOT NULL
                GROUP BY ce.cat_transacao, ce.cat_avaliacao
                ORDER BY ce.cat_transacao, ce.cat_avaliacao
            """, (numero_termo,))
            extrato_resumo = cursor.fetchall()
            print(f"[DEBUG DP] === Resumo do Extrato ===")
            for linha in extrato_resumo:
                print(f"  - cat_transacao: '{linha['cat_transacao']}' | cat_avaliacao: '{linha['cat_avaliacao']}' | qtd: {linha['qtd_linhas']} | total: R$ {linha['total_categoria']:.2f}")
            
            # Query CORRIGIDA: usar EXISTS ao invés de JOIN para evitar duplicação
            cursor.execute("""
                SELECT COALESCE(SUM(ABS(ce.discriminacao)), 0) as total_executado_aprovado
                FROM analises_pc.conc_extrato ce
                WHERE ce.numero_termo = %s 
                    AND ce.cat_avaliacao = 'Avaliado'
                    AND ce.discriminacao IS NOT NULL
                    AND EXISTS (
                        SELECT 1 
                        FROM public.parcerias_despesas pd
                        WHERE LOWER(pd.categoria_despesa) = LOWER(ce.cat_transacao)
                            AND pd.numero_termo = ce.numero_termo
                    )
            """, (numero_termo,))
            
            executado_aprovado_data = cursor.fetchone()
            valor_executado_aprovado = float(executado_aprovado_data['total_executado_aprovado']) if executado_aprovado_data else 0
            print(f"[DEBUG DP] Valor Executado e Aprovado FINAL: R$ {valor_executado_aprovado:.2f}")
            print(f"[DEBUG DP] ===== FIM DO DEBUG =====\n")
            
            # 2. Descontos de Contrapartida
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(GREATEST(valor_previsto - valor_executado, 0)), 0) as desconto_previsto_executado,
                    COALESCE(SUM(GREATEST(valor_executado - valor_considerado, 0)), 0) as desconto_executado_considerado
                FROM analises_pc.conc_contrapartida
                WHERE numero_termo = %s
            """, (numero_termo,))
            
            contrapartida_descontos = cursor.fetchone()
            desconto_contrapartida = 0
            if contrapartida_descontos:
                desconto_prev_exec = float(contrapartida_descontos['desconto_previsto_executado']) if contrapartida_descontos['desconto_previsto_executado'] else 0
                desconto_exec_cons = float(contrapartida_descontos['desconto_executado_considerado']) if contrapartida_descontos['desconto_executado_considerado'] else 0
                desconto_contrapartida = desconto_prev_exec + desconto_exec_cons
            print(f"[DEBUG RELATORIO DP] Descontos de Contrapartida: {desconto_contrapartida}")
            
            # 3. Despesas Passíveis de Glosa (cat_avaliacao='Glosar', exceto Taxas Bancárias)
            cursor.execute("""
                SELECT COALESCE(SUM(ABS(discriminacao)), 0) as total_glosas
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s 
                    AND cat_avaliacao = 'Glosar'
                    AND LOWER(cat_transacao) != 'taxas bancárias'
                    AND discriminacao IS NOT NULL
            """, (numero_termo,))
            
            glosas_data = cursor.fetchone()
            despesas_glosa = float(glosas_data['total_glosas']) if glosas_data else 0
            print(f"[DEBUG RELATORIO DP] Despesas Passíveis de Glosa: {despesas_glosa}")
            
            # 4. Taxas Bancárias não Devolvidas
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN LOWER(cat_transacao) = 'taxas bancárias' THEN ABS(discriminacao) ELSE 0 END), 0) as total_taxas,
                    COALESCE(SUM(CASE WHEN LOWER(cat_transacao) = 'devolução de taxas bancárias' THEN ABS(discriminacao) ELSE 0 END), 0) as total_devolucao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s AND discriminacao IS NOT NULL
            """, (numero_termo,))
            
            taxas_data = cursor.fetchone()
            taxas_bancarias = float(taxas_data['total_taxas']) if taxas_data else 0
            devolucao_taxas = float(taxas_data['total_devolucao']) if taxas_data else 0
            taxas_nao_devolvidas_dp = taxas_bancarias - devolucao_taxas
            print(f"[DEBUG RELATORIO DP] Taxas não Devolvidas: {taxas_nao_devolvidas_dp}")
            
            # 5. Valores já devolvidos (cat_transacao='Restituição de Verba')
            cursor.execute("""
                SELECT COALESCE(SUM(ABS(discriminacao)), 0) as total_restituicao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s 
                    AND LOWER(cat_transacao) = 'restituição de verba'
                    AND discriminacao IS NOT NULL
            """, (numero_termo,))
            
            restituicao_data = cursor.fetchone()
            valores_devolvidos = float(restituicao_data['total_restituicao']) if restituicao_data else 0
            print(f"[DEBUG RELATORIO DP] Valores já Devolvidos: {valores_devolvidos}")
            
            # 6. Descontos já Realizados (buscar do conc_banco, default 0)
            cursor.execute("""
                SELECT descontos_realizados
                FROM analises_pc.conc_banco
                WHERE numero_termo = %s
            """, (numero_termo,))
            desc_result = cursor.fetchone()
            descontos_realizados = float(desc_result['descontos_realizados']) if desc_result else 0
            print(f"[DEBUG RELATORIO DP] Descontos já Realizados: {descontos_realizados}")
            
            # 7. Valor Total do Projeto (igual PG)
            rendimento_usado = total_liquido if considerar_liquido else total_bruto
            valor_total_projeto = float(parceria['total_pago']) + rendimento_usado + total_contrapartida
            
            # 8. Saldos não Utilizados Remanescentes = Valor Total - Executado - Glosas - Taxas não Devolvidas
            saldos_remanescentes = (
                valor_total_projeto - 
                valor_executado_aprovado - 
                despesas_glosa - 
                taxas_nao_devolvidas_dp
            )
            print(f"[DEBUG RELATORIO DP] Saldos Remanescentes: {saldos_remanescentes}")
            
            # 9. Total de Descontos = Saldos Remanescentes + Descontos já Realizados + Descontos Contrapartida + Despesas Glosa + Taxas não Devolvidas
            total_descontos = (
                saldos_remanescentes + 
                descontos_realizados + 
                desconto_contrapartida + 
                despesas_glosa + 
                taxas_nao_devolvidas_dp
            )
            print(f"[DEBUG RELATORIO DP] Total de Descontos: {total_descontos}")
            
            # 10. Valor a ser Ressarcido
            valor_ressarcido = total_descontos - valores_devolvidos
            print(f"[DEBUG RELATORIO DP] Valor a ser Ressarcido: {valor_ressarcido}")
        
        # ==== CÁLCULOS PARA RESPONSABILIDADE MISTA (DP + PESSOA GESTORA) ====
        elif responsabilidade == 2:
            print(f"[DEBUG RELATORIO MISTO] ===== INICIANDO CÁLCULOS MISTO =====")
            
            # ===== DETERMINAR DATA DE CORTE (TRANSIÇÃO ENTRE PORTARIAS) =====
            
            # Buscar portaria e data de início do termo
            cursor.execute("""
                SELECT inicio, portaria
                FROM public.parcerias
                WHERE numero_termo = %s
            """, (numero_termo,))
            info_parceria = cursor.fetchone()
            
            data_inicio = info_parceria['inicio']
            portaria = info_parceria['portaria']
            
            print(f"[DEBUG MISTO] Portaria: {portaria}")
            print(f"[DEBUG MISTO] Data início: {data_inicio}")
            
            # Buscar data de término da portaria na tabela c_legislacao
            cursor.execute("""
                SELECT termino
                FROM categoricas.c_legislacao
                WHERE lei = %s
            """, (portaria,))
            legislacao = cursor.fetchone()
            
            if legislacao and legislacao['termino']:
                data_corte = legislacao['termino']
                print(f"[DEBUG MISTO] Data de corte (término da portaria): {data_corte}")
            else:
                # Fallback: usar 28/02/2023 como padrão
                data_corte = '2023-02-28'
                print(f"[DEBUG MISTO] Data de corte (padrão): {data_corte}")
            
            # ===== BUSCAR CATEGORIAS DE PROVISÃO DO BANCO =====
            
            # Buscar lista oficial de categorias de provisão
            cursor.execute("""
                SELECT DISTINCT despesa_provisao
                FROM categoricas.c_despesas_provisao
                WHERE despesa_provisao IS NOT NULL
            """)
            categorias_provisao_db = [row['despesa_provisao'] for row in cursor.fetchall()]
            print(f"[DEBUG MISTO] Categorias de provisão (do banco): {categorias_provisao_db}")
            
            def is_provisao(categoria):
                """Verifica se uma categoria é de provisão (case-insensitive)"""
                if not categoria:
                    return False
                categoria_lower = categoria.lower().strip()
                # Comparar com cada categoria do banco (case-insensitive)
                for cat_provisao in categorias_provisao_db:
                    if cat_provisao and categoria_lower == cat_provisao.lower().strip():
                        return True
                return False
            
            # ===== CALCULAR ORÇAMENTO POR PERÍODO =====
            
            # Buscar despesas previstas com valores mensais
            cursor.execute("""
                SELECT 
                    categoria_despesa,
                    mes,
                    valor
                FROM public.parcerias_despesas
                WHERE numero_termo = %s
                ORDER BY categoria_despesa, mes
            """, (numero_termo,))
            despesas_previstas = cursor.fetchall()
            
            # Calcular meses do período DP (antes do corte)
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            
            data_inicio_dt = datetime.strptime(str(data_inicio), '%Y-%m-%d')
            data_corte_dt = datetime.strptime(str(data_corte), '%Y-%m-%d')
            
            # Calcular número de meses no período DP
            meses_dp = 0
            mes_atual = data_inicio_dt
            while mes_atual <= data_corte_dt:
                meses_dp += 1
                mes_atual += relativedelta(months=1)
            
            print(f"[DEBUG MISTO] Meses no período DP: {meses_dp}")
            
            # Somar valores do orçamento por período
            total_periodo_dp = 0
            provisoes_previstas_dp = 0
            
            # Agrupar despesas por categoria
            despesas_por_categoria = {}
            for despesa in despesas_previstas:
                categoria = despesa['categoria_despesa']
                mes = despesa['mes']
                valor_mes = float(despesa['valor']) if despesa['valor'] else 0
                
                if categoria not in despesas_por_categoria:
                    despesas_por_categoria[categoria] = {}
                
                despesas_por_categoria[categoria][mes] = valor_mes
            
            print(f"[DEBUG MISTO] Categorias encontradas no orçamento: {list(despesas_por_categoria.keys())}")
            
            # Calcular totais por período
            for categoria, meses_valores in despesas_por_categoria.items():
                valor_dp = 0
                
                # Somar apenas os meses do período DP (1 até meses_dp)
                for mes_num in range(1, meses_dp + 1):
                    if mes_num in meses_valores:
                        valor_dp += meses_valores[mes_num]
                
                total_periodo_dp += valor_dp
                
                # Se for provisão, acumular separadamente (case-insensitive)
                if is_provisao(categoria):
                    provisoes_previstas_dp += valor_dp
                    print(f"[DEBUG MISTO]    + Provisão prevista DP '{categoria}': R$ {valor_dp:.2f}")
            
            print(f"[DEBUG MISTO] Total orçamento período DP: R$ {total_periodo_dp:.2f}")
            print(f"[DEBUG MISTO] Provisões previstas período DP: R$ {provisoes_previstas_dp:.2f}")
            
            # ===== CALCULAR PROVISÕES EXECUTADAS NO PERÍODO DP =====
            
            provisoes_executadas_dp = 0
            for cat in extrato_categorias:
                cat_transacao = cat['cat_transacao']
                cat_avaliacao = cat['cat_avaliacao']
                
                # Provisões executadas = cat_avaliacao='Avaliado' + cat_transacao em provisões
                if cat_avaliacao == 'Avaliado' and is_provisao(cat_transacao):
                    # Verificar se a competência está no período DP
                    cursor.execute("""
                        SELECT COALESCE(SUM(discriminacao), 0) as total_dp
                        FROM analises_pc.conc_extrato
                        WHERE numero_termo = %s
                          AND cat_transacao = %s
                          AND cat_avaliacao = %s
                          AND competencia <= %s
                    """, (numero_termo, cat_transacao, cat_avaliacao, data_corte))
                    
                    result = cursor.fetchone()
                    valor_dp = float(result['total_dp']) if result else 0
                    
                    provisoes_executadas_dp += valor_dp
                    print(f"[DEBUG MISTO]    + Provisão executada DP '{cat_transacao}': R$ {valor_dp:.2f}")
            
            print(f"[DEBUG MISTO] Total Provisões Executadas (período DP): R$ {provisoes_executadas_dp:.2f}")
            
            # ===== CALCULAR TOTAL DE PROVISÕES NO ORÇAMENTO ANUAL =====
            
            # Somar TODAS as provisões previstas no orçamento (todos os meses)
            total_provisoes_orcamento = 0
            for categoria, meses_valores in despesas_por_categoria.items():
                if is_provisao(categoria):
                    valor_total_categoria = sum(meses_valores.values())
                    total_provisoes_orcamento += valor_total_categoria
                    print(f"[DEBUG MISTO]    + Total provisão orçamento '{categoria}': R$ {valor_total_categoria:.2f}")
            
            print(f"[DEBUG MISTO] Total Provisões no Orçamento Anual: R$ {total_provisoes_orcamento:.2f}")
            
            # ===== CALCULAR PROVISÕES EXECUTADAS NO PROJETO INTEIRO =====
            
            # Provisões executadas em TODO o projeto (sem filtro de data)
            provisoes_executadas_total = 0
            for cat in extrato_categorias:
                cat_transacao = cat['cat_transacao']
                cat_avaliacao = cat['cat_avaliacao']
                
                if cat_avaliacao == 'Avaliado' and is_provisao(cat_transacao):
                    # Sem filtro de competencia - todo o projeto
                    cursor.execute("""
                        SELECT COALESCE(SUM(discriminacao), 0) as total_projeto
                        FROM analises_pc.conc_extrato
                        WHERE numero_termo = %s
                          AND cat_transacao = %s
                          AND cat_avaliacao = %s
                    """, (numero_termo, cat_transacao, cat_avaliacao))
                    
                    result = cursor.fetchone()
                    valor_total = float(result['total_projeto']) if result else 0
                    
                    provisoes_executadas_total += valor_total
                    print(f"[DEBUG MISTO]    + Provisão executada TOTAL '{cat_transacao}': R$ {valor_total:.2f}")
            
            print(f"[DEBUG MISTO] Total Provisões Executadas (projeto inteiro): R$ {provisoes_executadas_total:.2f}")
            
            # ===== CALCULAR SALDOS DE PROVISÕES RESIDUAIS =====
            
            saldos_provisoes_residuais = total_provisoes_orcamento - provisoes_executadas_total
            print(f"[DEBUG MISTO] Saldos de Provisões Residuais: R$ {saldos_provisoes_residuais:.2f}")
            
            # ===== TABELA 1 - ANÁLISE DAC =====
            
            # Calcular o valor total do orçamento (soma de todas as despesas previstas)
            total_orcamento_anual = sum(
                sum(meses_valores.values()) 
                for meses_valores in despesas_por_categoria.values()
            )
            print(f"[DEBUG MISTO] Total do Orçamento Anual (parcerias_despesas): R$ {total_orcamento_anual:.2f}")
            
            # NOTA: Precisamos calcular saldos_provisoes_residuais antes do Valor Repassado
            # (já foi calculado acima como: total_provisoes_orcamento - provisoes_executadas_total)
            
            # 1. Valor Repassado = Total Orçamento DP - Provisões Executadas - Saldos Residuais
            valor_repassado_dac = total_periodo_dp - provisoes_executadas_dp - saldos_provisoes_residuais
            print(f"[DEBUG MISTO] 1. Valor Repassado (DAC): R$ {valor_repassado_dac:.2f}")
            print(f"[DEBUG MISTO]    = Total Orçamento DP ({total_periodo_dp:.2f}) - Provisões Executadas ({provisoes_executadas_dp:.2f}) - Saldos Residuais ({saldos_provisoes_residuais:.2f})")
            
            # 2. Rendimentos (usar líquido ou bruto conforme flag)
            rendimentos_dac = rendimento_usado
            print(f"[DEBUG MISTO] 2. Rendimentos (DAC): {rendimentos_dac}")
            
            # 3. Contrapartida
            contrapartida_dac = total_contrapartida
            print(f"[DEBUG MISTO] 3. Contrapartida (DAC): {contrapartida_dac}")
            
            # 4. Provisões Executadas
            provisoes_executadas = provisoes_executadas_dp
            print(f"[DEBUG MISTO] 4. Provisões Executadas (DAC): R$ {provisoes_executadas:.2f}")
            
            # 5. Valor Total do Projeto = Valor Repassado + Rendimentos + Contrapartida + Provisões Executadas
            valor_total_projeto_dac = valor_repassado_dac + rendimentos_dac + contrapartida_dac + provisoes_executadas
            print(f"[DEBUG MISTO] 5. Valor Total do Projeto (DAC): R$ {valor_total_projeto_dac:.2f}")
            print(f"[DEBUG MISTO]    = Valor Repassado ({valor_repassado_dac:.2f}) + Rendimentos ({rendimentos_dac}) + Contrapartida ({contrapartida_dac}) + Provisões Executadas ({provisoes_executadas:.2f})")
            
            # Buscar categorias previstas
            cursor.execute("""
                SELECT DISTINCT categoria_despesa
                FROM public.parcerias_despesas
                WHERE numero_termo = %s
                ORDER BY categoria_despesa
            """, (numero_termo,))
            categorias_previstas = [row['categoria_despesa'] for row in cursor.fetchall()]
            
            # 6. Valor Executado e Aprovado = Soma de discriminacao onde cat_avaliacao = 'Avaliado'
            #    E cat_transacao está nas categorias previstas (case insensitive)
            if categorias_previstas:
                # Converter categorias previstas para lowercase para comparação
                cursor.execute("""
                    SELECT COALESCE(SUM(ABS(discriminacao)), 0) as total_considerado
                    FROM analises_pc.conc_extrato
                    WHERE numero_termo = %s
                      AND discriminacao IS NOT NULL
                      AND cat_avaliacao = 'Avaliado'
                      AND LOWER(cat_transacao) = ANY(SELECT LOWER(unnest(%s::text[])))
                """, (numero_termo, categorias_previstas))
                
                resultado_considerado = cursor.fetchone()
                valor_executado_aprovado_dac = float(resultado_considerado['total_considerado']) if resultado_considerado else 0
            else:
                valor_executado_aprovado_dac = 0
            
            print(f"[DEBUG MISTO] 6. Valor Executado e Aprovado (DAC): {valor_executado_aprovado_dac}")
            print(f"[DEBUG MISTO]    = Soma ABS(discriminacao) onde cat_avaliacao='Avaliado' E cat_transacao em categorias previstas")
            
            # 7. Total de Descontos (a preencher depois de calcular os itens)
            # Será calculado após itens 8, 9, 10, 11, 12, 13
            # NOTA: Saldos não Utilizados será calculado APÓS item 11 (Despesas Glosa)
            
            # 9. Descontos já realizados (buscar do conc_banco, default 0)
            cursor.execute("""
                SELECT descontos_realizados
                FROM analises_pc.conc_banco
                WHERE numero_termo = %s
            """, (numero_termo,))
            desc_dac_result = cursor.fetchone()
            descontos_realizados_dac = float(desc_dac_result['descontos_realizados']) if desc_dac_result else 0
            print(f"[DEBUG MISTO] 9. Descontos já Realizados (DAC): {descontos_realizados_dac}")
            
            # 10. Descontos de Contrapartida
            descontos_contrapartida_dac = total_contrapartida
            print(f"[DEBUG MISTO] 10. Descontos de Contrapartida (DAC): {descontos_contrapartida_dac}")
            
            # 11. Despesas Passíveis de Glosa
            despesas_glosa_dac = 0
            for cat in extrato_categorias:
                if cat['cat_avaliacao'] == 'Glosar':
                    despesas_glosa_dac += float(cat['total_valor']) if cat['total_valor'] else 0
            print(f"[DEBUG MISTO] 11. Despesas Passíveis de Glosa (DAC): {despesas_glosa_dac}")
            
            # 8. Saldos não Utilizados = Valor Total do Projeto - Valor Executado e Aprovado - Despesas Glosa
            saldos_nao_utilizados_dac = valor_total_projeto_dac - valor_executado_aprovado_dac - despesas_glosa_dac
            print(f"[DEBUG MISTO] 8. Saldos não Utilizados (DAC) RECALCULADO: {saldos_nao_utilizados_dac}")
            print(f"[DEBUG MISTO]    = Valor Total Projeto ({valor_total_projeto_dac:.2f}) - Valor Executado Aprovado ({valor_executado_aprovado_dac:.2f}) - Despesas Glosa ({despesas_glosa_dac:.2f})")
            
            # 12. Valores já Devolvidos (cat_transacao='Restituição de Verba')
            cursor.execute("""
                SELECT COALESCE(SUM(ABS(discriminacao)), 0) as total_restituicao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s 
                    AND LOWER(cat_transacao) = 'restituição de verba'
                    AND discriminacao IS NOT NULL
            """, (numero_termo,))
            
            restituicao_dac_data = cursor.fetchone()
            valores_devolvidos_dac = float(restituicao_dac_data['total_restituicao']) if restituicao_dac_data else 0
            print(f"[DEBUG MISTO] 12. Valores já Devolvidos (DAC): {valores_devolvidos_dac}")
            
            # 7. Total de Descontos = Saldos Remanescentes + Descontos já Realizados + Descontos Contrapartida + Despesas Glosa
            total_descontos_dac = (
                saldos_nao_utilizados_dac + 
                descontos_realizados_dac + 
                descontos_contrapartida_dac + 
                despesas_glosa_dac
            )
            print(f"[DEBUG MISTO] 7. Total de Descontos (DAC): {total_descontos_dac}")
            
            # 13. Valor a ser Ressarcido = Total de Descontos - Valores já Devolvidos
            valor_ressarcido_dac = total_descontos_dac - valores_devolvidos_dac
            print(f"[DEBUG MISTO] 13. Valor a ser Ressarcido (DAC): {valor_ressarcido_dac}")
            print(f"[DEBUG MISTO]    = Total Descontos ({total_descontos_dac:.2f}) - Valores Devolvidos ({valores_devolvidos_dac:.2f})")
            
            # ===== TABELA 2 - PESSOA GESTORA =====
            
            # 1. Rendimentos (mesmo valor da tabela DAC)
            rendimentos_pg = rendimentos_dac
            print(f"[DEBUG MISTO PG] 1. Rendimentos (PG): {rendimentos_pg}")
            
            # 2. Saldos de Provisões Residuais - já calculado acima
            print(f"[DEBUG MISTO PG] 2. Saldos de Provisões Residuais (PG): R$ {saldos_provisoes_residuais:.2f}")
            
            # 3. Saldos de Execução = Total Orçamento Anual - Valor Total Projeto DAC - Saldos Provisões Residuais
            saldos_execucao_pg = total_orcamento_anual - valor_total_projeto_dac - saldos_provisoes_residuais
            print(f"[DEBUG MISTO PG] 3. Saldos de Execução (PG): {saldos_execucao_pg}")
            print(f"[DEBUG MISTO PG]    = Total Orçamento Anual ({total_orcamento_anual:.2f}) - Valor Total Projeto DAC ({valor_total_projeto_dac:.2f}) - Saldos Provisões Residuais ({saldos_provisoes_residuais:.2f})")
            
            # 4. Total da Análise do Gestor
            total_analise_gestor = rendimentos_pg + saldos_provisoes_residuais + saldos_execucao_pg
            print(f"[DEBUG MISTO PG] 4. Total da Análise do Gestor (PG): {total_analise_gestor}")
            
            print(f"[DEBUG RELATORIO MISTO] ===== CÁLCULOS COMPLETOS =====")
        
        # ==== CÁLCULOS PARA PESSOA GESTORA (PG) ====
        else:
            # Calcular valores específicos
            valor_dest_identificado = 0
            valor_dest_nao_identificado = 0
            valor_credito_externo = 0
            valor_taxas_bancarias = 0
            valor_devolucao_taxas = 0
            valor_glosas = 0
        
            for cat in extrato_categorias:
                cat_transacao = cat['cat_transacao']
                cat_avaliacao = cat['cat_avaliacao']
                total_valor = float(cat['total_valor']) if cat['total_valor'] else 0
                
                if cat_transacao == 'Destinatário Identificado':
                    valor_dest_identificado += total_valor
                elif cat_transacao == 'Destinatário não Identificado':
                    valor_dest_nao_identificado += total_valor
                elif cat_transacao == 'Crédito Externo da OSC':
                    valor_credito_externo += total_valor
                elif cat_transacao.lower() == 'taxas bancárias':
                    valor_taxas_bancarias += total_valor
                elif cat_transacao.lower() == 'devolução de taxas bancárias':
                    valor_devolucao_taxas += total_valor
                
                # Glosas (exceto Taxas Bancárias - case insensitive)
                if cat_avaliacao == 'Glosar' and cat_transacao.lower() != 'taxas bancárias':
                    valor_glosas += total_valor
            
            print(f"[DEBUG RELATORIO PG] Taxas bancárias: {valor_taxas_bancarias}")
            print(f"[DEBUG RELATORIO PG] Devolução taxas: {valor_devolucao_taxas}")
            
            # Taxas bancárias não devolvidas
            taxas_nao_devolvidas = valor_taxas_bancarias - valor_devolucao_taxas
            
            # Saldos não utilizados (rendimento_usado já definido anteriormente)
            saldos_nao_utilizados = (
                float(parceria['total_pago']) + rendimento_usado - 
                valor_dest_identificado - valor_dest_nao_identificado - taxas_nao_devolvidas
            )
        
        if conn:
            conn.close()
        
        # Preparar resposta baseada no tipo de responsabilidade
        if responsabilidade == 1:  # Departamento de Parcerias
            resultado = {
                'numero_termo': numero_termo,
                'tipo_relatorio': 'departamento_parcerias',
                'responsabilidade': responsabilidade,
                'valor_total_previsto': float(parceria['total_previsto']) if parceria['total_previsto'] else 0,
                'valor_repassado': float(parceria['total_pago']) if parceria['total_pago'] else 0,
                'rendimentos': {
                    'bruto': total_bruto,
                    'ir': total_ir,
                    'iof': total_iof,
                    'liquido': total_liquido,
                    'valor_usado': rendimento_usado
                },
                'contrapartida': total_contrapartida,
                'tem_contrapartida': total_contrapartida > 0,
                'considerar_liquido': considerar_liquido,
                'valor_total_projeto': valor_total_projeto,
                'valor_executado_aprovado': valor_executado_aprovado,
                'total_descontos': total_descontos,
                'saldos_remanescentes': saldos_remanescentes,
                'descontos_realizados': descontos_realizados,
                'desconto_contrapartida': desconto_contrapartida,
                'despesas_glosa': despesas_glosa,
                'taxas_nao_devolvidas': taxas_nao_devolvidas_dp,
                'valores_devolvidos': valores_devolvidos,
                'valor_ressarcido': valor_ressarcido
            }
        elif responsabilidade == 2:  # Responsabilidade Mista (DP + PG)
            resultado = {
                'numero_termo': numero_termo,
                'tipo_relatorio': 'misto',
                'responsabilidade': responsabilidade,
                'considerar_liquido': considerar_liquido,
                'rendimentos': {
                    'bruto': total_bruto,
                    'ir': total_ir,
                    'iof': total_iof,
                    'liquido': total_liquido,
                    'valor_usado': rendimento_usado
                },
                # Tabela 1 - Análise DAC
                'tabela_dac': {
                    'valor_total_projeto': valor_total_projeto_dac,
                    'valor_repassado': valor_repassado_dac,
                    'rendimentos': rendimentos_dac,
                    'contrapartida': contrapartida_dac,
                    'provisoes_executadas': provisoes_executadas,
                    'valor_executado_aprovado': valor_executado_aprovado_dac,
                    'total_descontos': total_descontos_dac,
                    'saldos_nao_utilizados': saldos_nao_utilizados_dac,
                    'descontos_realizados': descontos_realizados_dac,
                    'descontos_contrapartida': descontos_contrapartida_dac,
                    'despesas_glosa': despesas_glosa_dac,
                    'valores_devolvidos': valores_devolvidos_dac,
                    'valor_ressarcido': valor_ressarcido_dac
                },
                # Tabela 2 - Análise Pessoa Gestora
                'tabela_pg': {
                    'rendimentos': rendimentos_pg,
                    'saldos_provisoes_residuais': saldos_provisoes_residuais,
                    'saldos_execucao': saldos_execucao_pg,
                    'total_analise_gestor': total_analise_gestor
                },
                # Quadro Geral
                'quadro_geral': {
                    'valor_analise_dac': valor_total_projeto_dac,
                    'valor_analise_gestor': total_analise_gestor,
                    'total': valor_total_projeto_dac + total_analise_gestor
                }
            }
        else:  # Pessoa Gestora ou Misto
            resultado = {
                'numero_termo': numero_termo,
                'tipo_relatorio': 'pessoa_gestora',
                'responsabilidade': responsabilidade,
                'valor_total_disponivel': float(parceria['total_previsto']) if parceria['total_previsto'] else 0,
                'valor_repassado': float(parceria['total_pago']) if parceria['total_pago'] else 0,
                'rendimentos': {
                    'bruto': total_bruto,
                    'ir': total_ir,
                    'iof': total_iof,
                    'liquido': total_liquido,
                    'valor_usado': rendimento_usado
                },
                'contrapartida': total_contrapartida,
                'tem_contrapartida': total_contrapartida > 0,
                'considerar_liquido': considerar_liquido,
                'valor_dest_identificado': valor_dest_identificado,
                'valor_dest_nao_identificado': valor_dest_nao_identificado,
                'saldos_nao_utilizados': saldos_nao_utilizados,
                'credito_externo': valor_credito_externo,
                'tem_credito_externo': valor_credito_externo > 0,
                'taxas_nao_devolvidas': taxas_nao_devolvidas,
                'glosas': valor_glosas,
                'tem_glosas': valor_glosas > 0
            }
        
        print(f"[DEBUG RELATORIO] Retornando resultado: {resultado}")
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"[ERRO RELATORIO] Tipo do erro: {type(e).__name__}")
        print(f"[ERRO RELATORIO] Mensagem: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if conn:
            conn.close()
        
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/debug-executado-aprovado', methods=['GET'])
@login_required
@requires_access('conc_relatorio')
def debug_executado_aprovado():
    """Gera CSV detalhado do cálculo de Valor Executado e Aprovado"""
    conn = None
    try:
        numero_termo = request.args.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo não informado'}), 400
        
        conn = get_db()
        cursor = get_cursor()
        
        # Buscar todas as linhas do extrato que têm categoria prevista (sem duplicação)
        cursor.execute("""
            SELECT DISTINCT ON (ce.id)
                ce.id,
                ce.data,
                ce.discriminacao,
                ce.cat_transacao,
                ce.cat_avaliacao,
                ce.origem_destino,
                (SELECT categoria_despesa 
                 FROM public.parcerias_despesas pd 
                 WHERE pd.categoria_despesa = ce.cat_transacao 
                    AND pd.numero_termo = ce.numero_termo 
                 LIMIT 1) as categoria_despesa,
                CASE 
                    WHEN ce.cat_avaliacao = 'Avaliado' 
                        AND EXISTS (
                            SELECT 1 
                            FROM public.parcerias_despesas pd
                            WHERE pd.categoria_despesa = ce.cat_transacao
                                AND pd.numero_termo = ce.numero_termo
                        )
                    THEN 'SIM'
                    ELSE 'NÃO'
                END as incluido_no_calculo
            FROM analises_pc.conc_extrato ce
            WHERE ce.numero_termo = %s 
                AND ce.discriminacao IS NOT NULL
                AND EXISTS (
                    SELECT 1 
                    FROM public.parcerias_despesas pd
                    WHERE pd.categoria_despesa = ce.cat_transacao
                        AND pd.numero_termo = ce.numero_termo
                )
            ORDER BY ce.id, ce.cat_avaliacao DESC, ce.cat_transacao, ce.data
        """, (numero_termo,))
        
        linhas = cursor.fetchall()
        
        # Gerar CSV
        output = StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Cabeçalho
        writer.writerow([
            'ID',
            'Data',
            'Valor (R$)',
            'Cat. Transação (Extrato)',
            'Cat. Despesa (Prevista)',
            'Origem/Destino',
            'Avaliação',
            'Incluído no Cálculo?'
        ])
        
        total_incluido = 0
        total_excluido = 0
        
        # Dados
        for linha in linhas:
            valor = abs(float(linha['discriminacao'])) if linha['discriminacao'] else 0
            incluido = linha['incluido_no_calculo'] == 'SIM'
            
            if incluido:
                total_incluido += valor
            else:
                total_excluido += valor
            
            writer.writerow([
                linha['id'],
                linha['data'].strftime('%d/%m/%Y') if linha['data'] else '',
                f"{valor:.2f}".replace('.', ','),
                linha['cat_transacao'] or '',
                linha['categoria_despesa'] or '',
                linha['origem_destino'] or '',
                linha['cat_avaliacao'] or '',
                linha['incluido_no_calculo']
            ])
        
        # Totais
        writer.writerow([])
        writer.writerow(['TOTAIS', '', '', '', '', '', '', ''])
        writer.writerow(['Incluído (Avaliado)', '', '', f"{total_incluido:.2f}".replace('.', ','), '', '', '', ''])
        writer.writerow(['Excluído (Outros)', '', '', f"{total_excluido:.2f}".replace('.', ','), '', '', '', ''])
        writer.writerow(['TOTAL GERAL', '', '', f"{(total_incluido + total_excluido):.2f}".replace('.', ','), '', '', '', ''])
        
        if conn:
            conn.close()
        
        # Retornar CSV
        output.seek(0)
        return Response(
            '\ufeff' + output.getvalue(),  # BOM para UTF-8
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=debug_executado_aprovado_{numero_termo.replace("/", "_")}.csv'
            }
        )
        
    except Exception as e:
        print(f"[ERRO DEBUG] {str(e)}")
        import traceback
        traceback.print_exc()
        
        if conn:
            conn.close()
        
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/relatorio-valor-executado-aprovado', methods=['GET'])
@login_required
@requires_access('conc_relatorio')
def relatorio_valor_executado_aprovado():
    """Retorna relatório detalhado do Valor Executado e Aprovado (DAC)"""
    try:
        numero_termo = request.args.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo não informado'}), 400
        
        cursor = get_cursor()
        
        # Buscar categorias previstas
        cursor.execute("""
            SELECT DISTINCT categoria_despesa
            FROM public.parcerias_despesas
            WHERE numero_termo = %s
            ORDER BY categoria_despesa
        """, (numero_termo,))
        categorias_previstas = [row['categoria_despesa'] for row in cursor.fetchall()]
        
        if not categorias_previstas:
            return jsonify({'erro': 'Não há categorias previstas para este termo'}), 404
        
        # Buscar detalhamento completo
        cursor.execute("""
            SELECT 
                id,
                data,
                cat_transacao,
                competencia,
                discriminacao,
                cat_avaliacao,
                avaliacao_analista,
                origem_destino,
                credito,
                debito
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s
              AND discriminacao IS NOT NULL
              AND cat_avaliacao = 'Avaliado'
              AND cat_transacao = ANY(%s)
            ORDER BY data, id
        """, (numero_termo, categorias_previstas))
        
        registros = cursor.fetchall()
        
        # Criar CSV com UTF-8 BOM e delimitador ponto e vírgula
        output = StringIO()
        # Adicionar BOM para UTF-8
        output.write('\ufeff')
        writer = csv.writer(output, delimiter=';')
        
        # Cabeçalho
        writer.writerow([
            'ID',
            'Data',
            'Categoria Transação',
            'Competência',
            'Discriminação (Valor)',
            'ABS(Discriminação)',
            'Cat. Avaliação',
            'Avaliação Analista',
            'Origem/Destino',
            'Crédito',
            'Débito'
        ])
        
        # Dados
        total_abs_discriminacao = 0
        for reg in registros:
            abs_disc = abs(float(reg['discriminacao'])) if reg['discriminacao'] else 0
            total_abs_discriminacao += abs_disc
            
            writer.writerow([
                reg['id'],
                reg['data'].strftime('%d/%m/%Y') if reg['data'] else '',
                reg['cat_transacao'] or '',
                reg['competencia'].strftime('%d/%m/%Y') if reg['competencia'] else '',
                f"{float(reg['discriminacao']):.2f}" if reg['discriminacao'] else '0.00',
                f"{abs_disc:.2f}",
                reg['cat_avaliacao'] or '',
                reg['avaliacao_analista'] or '',
                reg['origem_destino'] or '',
                f"{float(reg['credito']):.2f}" if reg['credito'] else '',
                f"{float(reg['debito']):.2f}" if reg['debito'] else ''
            ])
        
        # Linha de total
        writer.writerow([])
        writer.writerow(['', '', '', '', 'TOTAL GERAL:', f'R$ {total_abs_discriminacao:.2f}', '', '', '', '', ''])
        writer.writerow([])
        writer.writerow(['Filtros Aplicados:'])
        writer.writerow(['- cat_avaliacao = "Avaliado"'])
        writer.writerow(['- cat_transacao está nas categorias previstas do orçamento'])
        writer.writerow(['- discriminacao IS NOT NULL'])
        writer.writerow([])
        writer.writerow(['Categorias Previstas Consideradas:'])
        for cat in categorias_previstas:
            writer.writerow([f'  - {cat}'])
        
        cursor.close()
        
        csv_content = output.getvalue()
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=relatorio_valor_executado_aprovado_{numero_termo.replace("/", "_")}.csv',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        import traceback
        error_msg = f"Erro ao gerar relatório: {str(e)}"
        print(f"\n{'='*80}")
        print(f"ERRO NO RELATÓRIO VALOR EXECUTADO E APROVADO")
        print(f"Termo: {numero_termo if 'numero_termo' in locals() else 'N/A'}")
        print(f"Mensagem: {error_msg}")
        print(f"Traceback:\n{traceback.format_exc()}")
        print(f"{'='*80}\n")
        return jsonify({'erro': error_msg}), 500


@bp.route('/api/descontos-realizados', methods=['GET'])
@login_required
@requires_access('conc_relatorio')
def get_descontos_realizados():
    """Busca o valor de Descontos já Realizados para um termo"""
    try:
        numero_termo = request.args.get('numero_termo')
        if not numero_termo:
            return jsonify({'erro': 'Número do termo não informado'}), 400
        
        cursor = get_cursor()
        
        # Buscar valor da tabela conc_banco
        cursor.execute("""
            SELECT descontos_realizados
            FROM analises_pc.conc_banco
            WHERE numero_termo = %s
        """, (numero_termo,))
        
        result = cursor.fetchone()
        valor = float(result['descontos_realizados']) if result else 0
        
        return jsonify({'valor': valor})
        
    except Exception as e:
        import traceback
        print(f"Erro ao buscar descontos realizados: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/descontos-realizados', methods=['POST'])
@login_required
@requires_access('conc_relatorio')
def save_descontos_realizados():
    """Salva o valor de Descontos já Realizados para um termo"""
    conn = None
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        valor = data.get('valor', 0)
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo não informado'}), 400
        
        conn = get_db()
        cursor = get_cursor()
        
        # Atualizar valor na tabela conc_banco
        cursor.execute("""
            UPDATE analises_pc.conc_banco
            SET descontos_realizados = %s
            WHERE numero_termo = %s
        """, (valor, numero_termo))
        
        # Se não atualizou nenhuma linha, inserir
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO analises_pc.conc_banco (numero_termo, descontos_realizados)
                VALUES (%s, %s)
            """, (numero_termo, valor))
        
        conn.commit()
        
        return jsonify({'success': True, 'valor': float(valor)})
        
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        print(f"Erro ao salvar descontos realizados: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'erro': str(e)}), 500
