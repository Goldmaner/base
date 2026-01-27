# -*- coding: utf-8 -*-
"""
Blueprint para Gestão Orçamentária
Sistema de controle e acompanhamento orçamentário
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_db, get_cursor
from utils import login_required
from decorators import requires_access
import re

gestao_orcamentaria_bp = Blueprint('gestao_orcamentaria', __name__, url_prefix='/gestao_orcamentaria')


@gestao_orcamentaria_bp.route('/')
@login_required
@requires_access('gestao_orcamentaria')
def index():
    """Página principal - Gestão Orçamentária"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        usuario_nome = session.get('usuario_nome', 'Usuário')
        
        return render_template(
            'gestao_orcamentaria/index.html',
            usuario_nome=usuario_nome
        )
    
    finally:
        cur.close()


@gestao_orcamentaria_bp.route('/orcamento-detalhado')
@login_required
@requires_access('gestao_orcamentaria')
def orcamento_detalhado():
    """Página de relatório - Orçamento Detalhado"""
    return render_template('gestao_orcamentaria/orcamento_detalhado.html')


@gestao_orcamentaria_bp.route('/api/orcamento-detalhado')
@login_required
@requires_access('gestao_orcamentaria')
def api_orcamento_detalhado():
    """API para obter dados do orçamento detalhado"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        ano_referencia = request.args.get('ano_referencia')
        
        if not ano_referencia:
            return jsonify({'success': False, 'error': 'Ano de referência não fornecido'}), 400
        
        # 1. Buscar termos únicos com parcelas no ano de referência
        # Separar soma de Programada vs Projetada usando valor_previsto
        cur.execute("""
            SELECT 
                ul.numero_termo,
                SUM(CASE WHEN ul.parcela_tipo = 'Programada' THEN ul.valor_previsto ELSE 0 END) as total_programado,
                SUM(CASE WHEN ul.parcela_tipo = 'Projetada' THEN ul.valor_previsto ELSE 0 END) as total_projetado
            FROM gestao_financeira.ultra_liquidacoes ul
            WHERE EXTRACT(YEAR FROM ul.vigencia_inicial) = %s
            GROUP BY ul.numero_termo
            ORDER BY ul.numero_termo
        """, (ano_referencia,))
        
        termos = cur.fetchall()
        
        if not termos:
            return jsonify({'success': True, 'dados': []})
        
        # 2. Para cada termo, buscar dotação e informações adicionais
        resultado = []
        
        for termo in termos:
            numero_termo = termo['numero_termo']
            total_programado = float(termo['total_programado'] or 0)
            total_projetado = float(termo['total_projetado'] or 0)
            total_global = total_programado + total_projetado
            
            # Extrair informações do termo
            # Formato esperado: TCL/055/2023/SMDHC/SESANA
            partes_termo = numero_termo.split('/')
            
            if len(partes_termo) < 5:
                # Termo com formato inválido, pular
                continue
            
            tipo_termo = partes_termo[0]  # Ex: TCL, TFM
            unidade = partes_termo[4] if len(partes_termo) > 4 else None  # Ex: SESANA, FUMCAD
            
            # Buscar informações da parceria (OSC, CNPJ, Projeto, SEI Celebração, SEI PC, tipo_termo, final)
            cur.execute("""
                SELECT osc, cnpj, projeto, sei_celeb, sei_pc, tipo_termo, final
                FROM public.parcerias
                WHERE numero_termo = %s
            """, (numero_termo,))
            
            parceria = cur.fetchone()
            osc = parceria['osc'] if parceria else None
            cnpj = parceria['cnpj'] if parceria else None
            projeto = parceria['projeto'] if parceria else None
            sei_celeb = parceria['sei_celeb'] if parceria else None
            sei_pc = parceria['sei_pc'] if parceria else None
            tipo_contrato = parceria['tipo_termo'] if parceria else None
            data_termino = parceria['final'].strftime('%d/%m/%Y') if parceria and parceria['final'] else None
            
            # Buscar dotação orçamentária
            # Prioridade 1: Termo + Unidade + OSC
            # Prioridade 2: Termo + Unidade
            # Prioridade 3: Termo
            dotacao = None
            programatica = None
            
            if osc and unidade:
                cur.execute("""
                    SELECT dotacao_numero, programa_aplicacao
                    FROM categoricas.c_geral_dotacoes
                    WHERE condicoes_termo = %s 
                      AND condicoes_unidade = %s 
                      AND condicoes_osc = %s
                    LIMIT 1
                """, (tipo_termo, unidade, osc))
                dotacao_row = cur.fetchone()
                if dotacao_row:
                    dotacao = dotacao_row['dotacao_numero']
                    programatica = dotacao_row['programa_aplicacao']
            
            # Se não encontrou com OSC, tentar sem OSC
            if not dotacao and unidade:
                cur.execute("""
                    SELECT dotacao_numero, programa_aplicacao
                    FROM categoricas.c_geral_dotacoes
                    WHERE condicoes_termo = %s 
                      AND condicoes_unidade = %s 
                      AND (condicoes_osc IS NULL OR condicoes_osc = '')
                    LIMIT 1
                """, (tipo_termo, unidade))
                dotacao_row = cur.fetchone()
                if dotacao_row:
                    dotacao = dotacao_row['dotacao_numero']
                    programatica = dotacao_row['programa_aplicacao']
            
            # Se ainda não encontrou, tentar só com tipo de termo
            if not dotacao:
                cur.execute("""
                    SELECT dotacao_numero, programa_aplicacao
                    FROM categoricas.c_geral_dotacoes
                    WHERE condicoes_termo = %s
                    LIMIT 1
                """, (tipo_termo,))
                dotacao_row = cur.fetchone()
                if dotacao_row:
                    dotacao = dotacao_row['dotacao_numero']
                    programatica = dotacao_row['programa_aplicacao']
            
            # Extrair Projeto-Atividade da dotação
            # Formato: 34.10.14.422.3013.2.053.33503900.00.1.500.9001.0
            # Projeto-Atividade está na posição após 3013 (sempre 4 dígitos após o 5º ponto)
            projeto_atividade = None
            if dotacao:
                partes_dotacao = dotacao.split('.')
                if len(partes_dotacao) >= 7:
                    # Posição 5 é o código (ex: 3013), posição 6 é o projeto-atividade (ex: 2.053)
                    projeto_atividade = partes_dotacao[5] + '.' + partes_dotacao[6]
            
            # Só adicionar se tiver algum valor (programado ou projetado)
            if total_programado > 0 or total_projetado > 0:
                resultado.append({
                    'numero_termo': numero_termo,
                    'dotacao_orcamentaria': dotacao or 'Não identificada',
                    'projeto_atividade': projeto_atividade or '-',
                    'programatica': programatica or 'Não identificada',
                    'cnpj': cnpj or '-',
                    'sei_pc': sei_pc or '-',
                    'osc': osc or '-',
                    'projeto': projeto or '-',
                    'sei_celeb': sei_celeb or '-',
                    'tipo_contrato': tipo_contrato or '-',
                    'data_termino': data_termino or '-',
                    'total_programado': total_programado,
                    'total_projetado': total_projetado,
                    'total_global': total_global
                })
        
        return jsonify({
            'success': True,
            'dados': resultado,
            'total_registros': len(resultado)
        })
    
    except Exception as e:
        print(f"Erro em api_orcamento_detalhado: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@gestao_orcamentaria_bp.route('/api/cronograma-mensal')
@login_required
@requires_access('gestao_orcamentaria')
def api_cronograma_mensal():
    """API para obter dados do cronograma mensal dos termos baseado em vigência"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        ano_referencia = request.args.get('ano_referencia')
        
        if not ano_referencia:
            return jsonify({'success': False, 'error': 'Ano de referência não fornecido'}), 400
        
        print(f"[DEBUG CRONOGRAMA] Buscando cronograma para ano: {ano_referencia}")
        
        # Buscar parcelas do ano com vigência que cruza os meses
        # Para cada parcela, verificar em quais meses ela está vigente
        cur.execute("""
            SELECT 
                ul.numero_termo,
                ul.vigencia_inicial,
                ul.vigencia_final,
                ul.valor_previsto,
                ul.parcela_tipo
            FROM gestao_financeira.ultra_liquidacoes ul
            WHERE EXTRACT(YEAR FROM ul.vigencia_inicial) = %s
               OR (ul.vigencia_inicial < DATE_TRUNC('year', %s::date) 
                   AND ul.vigencia_final >= DATE_TRUNC('year', %s::date))
            ORDER BY ul.numero_termo, ul.vigencia_inicial
        """, (ano_referencia, f"{ano_referencia}-01-01", f"{ano_referencia}-01-01"))
        
        parcelas = cur.fetchall()
        print(f"[DEBUG CRONOGRAMA] Parcelas encontradas: {len(parcelas)}")
        
        # Organizar dados por termo, tipo e mês
        dados_programados = {}
        dados_projetados = {}
        
        for parcela in parcelas:
            numero_termo = parcela['numero_termo']
            vig_inicial = parcela['vigencia_inicial']
            vig_final = parcela['vigencia_final']
            valor_previsto = float(parcela['valor_previsto']) if parcela['valor_previsto'] else 0
            parcela_tipo = parcela['parcela_tipo']
            
            # Calcular quantos meses a parcela cobre no ano de referência
            from datetime import date
            ano_int = int(ano_referencia)
            
            # Limitar vigência ao ano de referência
            inicio_ano = date(ano_int, 1, 1)
            fim_ano = date(ano_int, 12, 31)
            
            inicio_efetivo = max(vig_inicial, inicio_ano) if vig_inicial else inicio_ano
            fim_efetivo = min(vig_final, fim_ano) if vig_final else fim_ano
            
            # Se a vigência está dentro do ano
            if inicio_efetivo <= fim_efetivo:
                # Distribuir o valor pelos meses de vigência
                mes_inicio = inicio_efetivo.month
                mes_fim = fim_efetivo.month
                
                meses_vigencia = mes_fim - mes_inicio + 1
                valor_por_mes = valor_previsto / meses_vigencia if meses_vigencia > 0 else 0
                
                # Selecionar o dict correto baseado no tipo
                dados_dict = dados_programados if parcela_tipo == 'Programada' else dados_projetados
                
                if numero_termo not in dados_dict:
                    dados_dict[numero_termo] = {}
                
                # Distribuir valor pelos meses
                for mes in range(mes_inicio, mes_fim + 1):
                    if mes not in dados_dict[numero_termo]:
                        dados_dict[numero_termo][mes] = 0
                    dados_dict[numero_termo][mes] += valor_por_mes
        
        print(f"[DEBUG CRONOGRAMA] Termos programados: {len(dados_programados)}, Termos projetados: {len(dados_projetados)}")
        
        return jsonify({
            'success': True,
            'dados_programados': dados_programados,
            'dados_projetados': dados_projetados
        })
    
    except Exception as e:
        print(f"Erro em api_cronograma_mensal: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()
