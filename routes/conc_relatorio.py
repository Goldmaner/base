"""
Rotas para Conciliação - Relatório
Geração de tabelas de cálculos para diferentes tipos de responsabilidade
"""

from flask import Blueprint, render_template, request, jsonify, session, Response
from db import get_cursor, get_db
from functools import wraps
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
def index():
    """Página principal do relatório de conciliação"""
    return render_template('analises_pc/conc_relatorio.html')


@bp.route('/api/test', methods=['GET'])
@login_required
def test():
    """Endpoint de teste"""
    return jsonify({'status': 'ok', 'message': 'Blueprint funcionando'})


@bp.route('/api/dados-relatorio', methods=['GET'])
@login_required
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
        # Buscar informações básicas da parceria
        cursor.execute("""
            SELECT 
                p.numero_termo,
                p.total_previsto,
                p.total_pago,
                pa.responsabilidade_analise
            FROM public.parcerias p
            LEFT JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
            WHERE p.numero_termo = %s
        """, (numero_termo,))
        
        parceria = cursor.fetchone()
        
        if not parceria:
            conn.close()
            return jsonify({'erro': 'Termo não encontrado'}), 404
        
        # Usar chaves nomeadas (RealDictCursor)
        responsabilidade = parceria['responsabilidade_analise'] if parceria['responsabilidade_analise'] is not None else -1
        
        # Forçar modo se solicitado
        if forcar_modo == 'dp':
            responsabilidade = 1
            print(f"[DEBUG RELATORIO] MODO FORÇADO: DP (original: {parceria['responsabilidade_analise']})")
        elif forcar_modo == 'pg':
            responsabilidade = 3
            print(f"[DEBUG RELATORIO] MODO FORÇADO: PG (original: {parceria['responsabilidade_analise']})")
        
        # DEBUG: Verificar valor real
        print(f"[DEBUG RELATORIO] Termo: {numero_termo}")
        print(f"[DEBUG RELATORIO] Parceria completa: {parceria}")
        print(f"[DEBUG RELATORIO] Responsabilidade: {responsabilidade} (tipo: {type(responsabilidade)})")
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
                        WHERE pd.categoria_despesa = ce.cat_transacao
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
                    AND cat_transacao != 'Taxas Bancárias'
                    AND discriminacao IS NOT NULL
            """, (numero_termo,))
            
            glosas_data = cursor.fetchone()
            despesas_glosa = float(glosas_data['total_glosas']) if glosas_data else 0
            print(f"[DEBUG RELATORIO DP] Despesas Passíveis de Glosa: {despesas_glosa}")
            
            # 4. Taxas Bancárias não Devolvidas
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN cat_transacao = 'Taxas Bancárias' THEN ABS(discriminacao) ELSE 0 END), 0) as total_taxas,
                    COALESCE(SUM(CASE WHEN cat_transacao = 'Devolução de Taxas Bancárias' THEN ABS(discriminacao) ELSE 0 END), 0) as total_devolucao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s AND discriminacao IS NOT NULL
            """, (numero_termo,))
            
            taxas_data = cursor.fetchone()
            taxas_bancarias = float(taxas_data['total_taxas']) if taxas_data else 0
            devolucao_taxas = float(taxas_data['total_devolucao']) if taxas_data else 0
            taxas_nao_devolvidas_dp = taxas_bancarias - devolucao_taxas
            print(f"[DEBUG RELATORIO DP] Taxas não Devolvidas: {taxas_nao_devolvidas_dp}")
            
            # 5. Valores já devolvidos (cat_avaliacao='Restituição de Verba')
            cursor.execute("""
                SELECT COALESCE(SUM(ABS(discriminacao)), 0) as total_restituicao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s 
                    AND cat_avaliacao = 'Restituição de Verba'
                    AND discriminacao IS NOT NULL
            """, (numero_termo,))
            
            restituicao_data = cursor.fetchone()
            valores_devolvidos = float(restituicao_data['total_restituicao']) if restituicao_data else 0
            print(f"[DEBUG RELATORIO DP] Valores já Devolvidos: {valores_devolvidos}")
            
            # 6. Descontos já Realizados (por enquanto, manual - será 0)
            descontos_realizados = 0
            
            # 7. Valor Total do Projeto (igual PG)
            rendimento_usado = total_liquido if considerar_liquido else total_bruto
            valor_total_projeto = float(parceria['total_pago']) + rendimento_usado + total_contrapartida
            
            # 8. Saldos não Utilizados Remanescentes
            saldos_remanescentes = (
                valor_total_projeto - 
                valor_executado_aprovado - 
                descontos_realizados - 
                despesas_glosa - 
                taxas_nao_devolvidas_dp
            )
            print(f"[DEBUG RELATORIO DP] Saldos Remanescentes: {saldos_remanescentes}")
            
            # 9. Total de Descontos
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
                elif cat_transacao == 'Taxas Bancárias':
                    valor_taxas_bancarias += total_valor
                elif cat_transacao == 'Devolução de Taxas Bancárias':
                    valor_devolucao_taxas += total_valor
                
                # Glosas (exceto Taxas Bancárias)
                if cat_avaliacao == 'Glosar' and cat_transacao != 'Taxas Bancárias':
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
