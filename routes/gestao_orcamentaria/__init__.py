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
        
        # 3. Buscar EDITAIS da tabela orcamento_edital_nova
        # Editais NUNCA têm valor programado, apenas projetado
        cur.execute("""
            SELECT 
                edital_nome,
                dotacao_formatada,
                projeto_atividade,
                SUM(valor_mes) as total_projetado
            FROM gestao_financeira.orcamento_edital_nova
            WHERE EXTRACT(YEAR FROM nome_mes) = %s
            GROUP BY edital_nome, dotacao_formatada, projeto_atividade
            ORDER BY edital_nome
        """, (ano_referencia,))
        
        editais = cur.fetchall()
        
        for edital in editais:
            edital_nome = edital['edital_nome']
            dotacao_formatada = edital['dotacao_formatada']
            projeto_atividade_edital = edital['projeto_atividade']
            total_projetado_edital = float(edital['total_projetado'] or 0)
            
            # Buscar Programática usando dotacao_formatada na tabela c_geral_dotacoes
            # A dotação contém o projeto-atividade, então buscamos pela dotação completa
            programatica_edital = None
            if dotacao_formatada:
                cur.execute("""
                    SELECT programa_aplicacao
                    FROM categoricas.c_geral_dotacoes
                    WHERE dotacao_numero = %s
                    LIMIT 1
                """, (dotacao_formatada,))
                prog_row = cur.fetchone()
                if prog_row:
                    programatica_edital = prog_row['programa_aplicacao']
            
            # Adicionar edital aos resultados
            # IMPORTANTE: Colunas auxiliares (CNPJ, Tipo de Contrato, etc.) = "-"
            if total_projetado_edital > 0:
                resultado.append({
                    'numero_termo': edital_nome,  # Nome do edital na coluna "Termo ou Edital"
                    'dotacao_orcamentaria': dotacao_formatada or 'Não identificada',
                    'projeto_atividade': projeto_atividade_edital or '-',
                    'programatica': programatica_edital or 'Não identificada',
                    'cnpj': '-',  # ⚡ Editais não têm CNPJ
                    'sei_pc': '-',  # ⚡ Editais não têm SEI PC
                    'osc': '-',  # ⚡ Editais não têm OSC
                    'projeto': '-',  # ⚡ Editais não têm Projeto
                    'sei_celeb': '-',  # ⚡ Editais não têm SEI Celebração
                    'tipo_contrato': '-',  # ⚡ Editais não têm Tipo de Contrato
                    'data_termino': '-',  # ⚡ Editais não têm Data de Término
                    'total_programado': 0,  # ⚡ Editais NUNCA têm valor programado
                    'total_projetado': total_projetado_edital,
                    'total_global': total_projetado_edital  # Global = Projetado (sem Programado)
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


@gestao_orcamentaria_bp.route('/api/cronograma-detalhado')
@login_required
@requires_access('gestao_orcamentaria')
def api_cronograma_detalhado():
    """API para obter cronograma detalhado da tabela ultra_liquidacoes_cronograma"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        ano_referencia = request.args.get('ano_referencia')
        
        if not ano_referencia:
            return jsonify({'success': False, 'error': 'Ano de referência não fornecido'}), 400
        
        print(f"[DEBUG CRONOGRAMA DETALHADO] Buscando cronograma detalhado para ano: {ano_referencia}")
        
        # Buscar dados da tabela ultra_liquidacoes_cronograma
        # Filtrar apenas meses do ano de referência
        cur.execute("""
            SELECT 
                numero_termo,
                nome_mes,
                valor_mes,
                parcela_numero
            FROM gestao_financeira.ultra_liquidacoes_cronograma
            WHERE EXTRACT(YEAR FROM nome_mes) = %s
            ORDER BY numero_termo, nome_mes
        """, (ano_referencia,))
        
        resultados = cur.fetchall()
        print(f"[DEBUG CRONOGRAMA DETALHADO] Registros encontrados: {len(resultados)}")
        
        # Organizar dados por termo e mês
        # dados[numero_termo][mes] = {valor: valor_mes, parcela: parcela_numero}
        dados = {}
        
        for row in resultados:
            numero_termo = row['numero_termo']
            nome_mes = row['nome_mes']  # DATE no formato YYYY-MM-01
            valor_mes = float(row['valor_mes']) if row['valor_mes'] else 0
            parcela_numero = row['parcela_numero']
            
            if numero_termo not in dados:
                dados[numero_termo] = {}
            
            # Extrair mês (1-12)
            mes = nome_mes.month
            
            # Acumular valor se já existe (caso haja múltiplas entradas para o mesmo mês)
            if mes not in dados[numero_termo]:
                dados[numero_termo][mes] = {
                    'valor': 0,
                    'parcelas': []
                }
            
            dados[numero_termo][mes]['valor'] += valor_mes
            if parcela_numero not in dados[numero_termo][mes]['parcelas']:
                dados[numero_termo][mes]['parcelas'].append(parcela_numero)
        
        print(f"[DEBUG CRONOGRAMA DETALHADO] Termos processados: {len(dados)}")
        
        return jsonify({
            'success': True,
            'dados': dados
        })
    
    except Exception as e:
        print(f"[ERRO CRONOGRAMA DETALHADO] {str(e)}")
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
        
        # Buscar parcelas do ano com vigência que começa no ano de referência
        # ⚡ IMPORTANTE: O valor integral da parcela aparece no mês de vigencia_inicial
        # Não dividimos o valor pelos meses, cada parcela é um "pagamento esperado" naquele mês
        cur.execute("""
            SELECT 
                ul.numero_termo,
                ul.vigencia_inicial,
                ul.vigencia_final,
                ul.valor_previsto,
                ul.parcela_tipo
            FROM gestao_financeira.ultra_liquidacoes ul
            WHERE EXTRACT(YEAR FROM ul.vigencia_inicial) = %s
            ORDER BY ul.numero_termo, ul.vigencia_inicial
        """, (ano_referencia,))
        
        parcelas = cur.fetchall()
        print(f"[DEBUG CRONOGRAMA] Parcelas encontradas: {len(parcelas)}")
        
        # Organizar dados por termo, tipo e mês
        # dados_programados[numero_termo][mes] = valor_total_do_mes
        # dados_projetados[numero_termo][mes] = valor_total_do_mes
        dados_programados = {}
        dados_projetados = {}
        
        for parcela in parcelas:
            numero_termo = parcela['numero_termo']
            vig_inicial = parcela['vigencia_inicial']
            valor_previsto = float(parcela['valor_previsto']) if parcela['valor_previsto'] else 0
            parcela_tipo = parcela['parcela_tipo']
            
            if not vig_inicial:
                continue
            
            # ⚡ LÓGICA CORRETA: Valor integral vai para o mês de vigencia_inicial
            mes_pagamento = vig_inicial.month
            
            # Selecionar o dict correto baseado no tipo
            dados_dict = dados_programados if parcela_tipo == 'Programada' else dados_projetados
            
            if numero_termo not in dados_dict:
                dados_dict[numero_termo] = {}
            
            # Acumular valor no mês de pagamento (pode haver múltiplas parcelas no mesmo mês)
            if mes_pagamento not in dados_dict[numero_termo]:
                dados_dict[numero_termo][mes_pagamento] = 0
            dados_dict[numero_termo][mes_pagamento] += valor_previsto
            
            print(f"[DEBUG] {numero_termo} | {parcela_tipo} | Mês {mes_pagamento} | R$ {valor_previsto:,.2f}")
        
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


@gestao_orcamentaria_bp.route('/api/cronograma-editais')
@login_required
@requires_access('gestao_orcamentaria')
def api_cronograma_editais():
    """API para obter dados do cronograma mensal dos editais"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        ano_referencia = request.args.get('ano_referencia')
        
        if not ano_referencia:
            return jsonify({'success': False, 'error': 'Ano de referência não fornecido'}), 400
        
        print(f"[DEBUG CRONOGRAMA EDITAIS] Buscando cronograma de editais para ano: {ano_referencia}")
        
        # Buscar dados mensais da tabela orcamento_edital_nova
        # ⚡ Para editais, não há diferença entre modo normal e detalhado
        # Ambos usam os mesmos dados mensais da tabela
        cur.execute("""
            SELECT 
                edital_nome,
                nome_mes,
                valor_mes
            FROM gestao_financeira.orcamento_edital_nova
            WHERE EXTRACT(YEAR FROM nome_mes) = %s
            ORDER BY edital_nome, nome_mes
        """, (ano_referencia,))
        
        resultados = cur.fetchall()
        print(f"[DEBUG CRONOGRAMA EDITAIS] Registros encontrados: {len(resultados)}")
        
        # Organizar dados por edital e mês
        # dados_editais[edital_nome][mes] = valor_mes
        dados_editais = {}
        
        for row in resultados:
            edital_nome = row['edital_nome']
            nome_mes = row['nome_mes']  # DATE no formato YYYY-MM-01
            valor_mes = float(row['valor_mes']) if row['valor_mes'] else 0
            
            if edital_nome not in dados_editais:
                dados_editais[edital_nome] = {}
            
            # Extrair mês (1-12)
            mes = nome_mes.month
            
            # Acumular valor se já existe (caso haja múltiplas entradas para o mesmo mês)
            if mes not in dados_editais[edital_nome]:
                dados_editais[edital_nome][mes] = 0
            dados_editais[edital_nome][mes] += valor_mes
            
            print(f"[DEBUG] {edital_nome} | Mês {mes} | R$ {valor_mes:,.2f}")
        
        print(f"[DEBUG CRONOGRAMA EDITAIS] Editais processados: {len(dados_editais)}")
        
        return jsonify({
            'success': True,
            'dados_editais': dados_editais
        })
    
    except Exception as e:
        print(f"[ERRO CRONOGRAMA EDITAIS] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@gestao_orcamentaria_bp.route('/relatorio-dotacao')
@login_required
@requires_access('gestao_orcamentaria')
def relatorio_dotacao():
    """Página de relatório - Dotações Orçamentárias"""
    return render_template('gestao_orcamentaria/relatorio_dotacao.html')


@gestao_orcamentaria_bp.route('/api/dotacoes')
@login_required
@requires_access('gestao_orcamentaria')
def api_dotacoes():
    """API para obter dados das dotações orçamentárias"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Filtros opcionais
        cod_cta_desp = request.args.get('cod_cta_desp', '33503900')  # Padrão: 33503900
        cod_proj_atvd = request.args.get('cod_proj_atvd', '')
        
        # Query base
        query = """
            SELECT 
                dotacao_formatada,
                cod_proj_atvd_sof,
                txt_proj_atvd,
                cod_cta_desp,
                saldo_dotacao,
                val_tot_eph,
                val_tot_pgto_dota,
                criado_em
            FROM gestao_financeira.back_dotacao
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtro de conta despesa
        if cod_cta_desp:
            query += " AND cod_cta_desp = %s"
            params.append(cod_cta_desp)
        
        # Aplicar filtro de projeto-atividade
        if cod_proj_atvd:
            query += " AND cod_proj_atvd_sof IS NOT NULL AND cod_proj_atvd_sof::text ILIKE %s"
            params.append(f'%{cod_proj_atvd}%')
        
        query += " ORDER BY dotacao_formatada"
        
        cur.execute(query, params)
        dotacoes = cur.fetchall()
        
        # Converter para formato JSON serializable
        resultado = []
        for d in dotacoes:
            # Converter valores monetários de string (com vírgula) para float
            def converter_valor(valor_str):
                if not valor_str:
                    return 0
                # Substituir vírgula por ponto e converter para float
                valor_limpo = str(valor_str).replace(',', '.')
                try:
                    return float(valor_limpo)
                except:
                    return 0
            
            resultado.append({
                'dotacao_formatada': d['dotacao_formatada'],
                'cod_proj_atvd_sof': d['cod_proj_atvd_sof'],
                'txt_proj_atvd': d['txt_proj_atvd'],
                'cod_cta_desp': d['cod_cta_desp'],
                'saldo_dotacao': converter_valor(d['saldo_dotacao']),
                'val_tot_eph': converter_valor(d['val_tot_eph']),
                'val_tot_pgto_dota': converter_valor(d['val_tot_pgto_dota']),
                'criado_em': d['criado_em'].strftime('%d/%m/%Y %H:%M') if d['criado_em'] else None
            })
        
        return jsonify({
            'success': True,
            'dados': resultado,
            'total_registros': len(resultado)
        })
    
    except Exception as e:
        print(f"Erro em api_dotacoes: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@gestao_orcamentaria_bp.route('/api/dotacoes/agrupado-projeto')
@login_required
@requires_access('gestao_orcamentaria')
def api_dotacoes_agrupado():
    """API para relatório agrupado por projeto-atividade"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        cod_cta_desp = request.args.get('cod_cta_desp', '33503900')
        
        # Buscar dados agrupados por dotacao_formatada (somente com saldo > 0)
        query = """
            SELECT 
                dotacao_formatada,
                cod_proj_atvd_sof,
                txt_proj_atvd,
                CAST(REPLACE(saldo_dotacao, ',', '.') AS NUMERIC) as total_saldo,
                cod_cta_desp,
                criado_em as ultima_atualizacao
            FROM gestao_financeira.back_dotacao
            WHERE cod_cta_desp = %s
              AND CAST(REPLACE(saldo_dotacao, ',', '.') AS NUMERIC) > 0
            ORDER BY dotacao_formatada
        """
        
        cur.execute(query, (cod_cta_desp,))
        agrupados = cur.fetchall()
        
        # Converter para formato JSON
        resultado = []
        for ag in agrupados:
            resultado.append({
                'dotacao_formatada': ag['dotacao_formatada'],
                'cod_proj_atvd_sof': ag['cod_proj_atvd_sof'],
                'txt_proj_atvd': ag['txt_proj_atvd'],
                'total_saldo': float(ag['total_saldo']) if ag['total_saldo'] else 0,
                'cod_cta_desp': ag['cod_cta_desp'],
                'ultima_atualizacao': ag['ultima_atualizacao'].strftime('%d/%m/%Y %H:%M') if ag['ultima_atualizacao'] else None
            })
        
        return jsonify({
            'success': True,
            'dados': resultado,
            'total_dotacoes': len(resultado)
        })
    
    except Exception as e:
        print(f"Erro em api_dotacoes_agrupado: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@gestao_orcamentaria_bp.route('/relatorio-reservas')
@login_required
@requires_access('gestao_orcamentaria')
def relatorio_reservas():
    """Página de relatório - Reservas Orçamentárias"""
    return render_template('gestao_orcamentaria/relatorio_reservas.html')


@gestao_orcamentaria_bp.route('/api/reservas')
@login_required
@requires_access('gestao_orcamentaria')
def api_reservas():
    """API para obter dados das reservas orçamentárias"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Filtro opcional por dotação
        dotacao_filter = request.args.get('dotacao', '')
        
        # Query base
        query = """
            SELECT 
                cod_resv_dota_sof,
                dt_efet_resv,
                dotacao_formatada,
                hist_resv,
                vl_saldo_resv
            FROM gestao_financeira.back_reservas
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtro de dotação com LIKE
        if dotacao_filter:
            query += " AND dotacao_formatada ILIKE %s"
            params.append(f'%{dotacao_filter}%')
        
        query += " ORDER BY dt_efet_resv DESC, cod_resv_dota_sof DESC"
        
        cur.execute(query, params)
        reservas = cur.fetchall()
        
        # Converter valores monetários
        def converter_valor(valor_str):
            if not valor_str:
                return 0
            valor_limpo = str(valor_str).replace(',', '.')
            try:
                return float(valor_limpo)
            except:
                return 0
        
        # Converter para formato JSON serializable
        resultado = []
        for r in reservas:
            resultado.append({
                'cod_resv_dota_sof': r['cod_resv_dota_sof'],
                'dt_efet_resv': r['dt_efet_resv'].strftime('%d/%m/%Y') if r['dt_efet_resv'] else None,
                'dotacao_formatada': r['dotacao_formatada'],
                'hist_resv': r['hist_resv'],
                'vl_saldo_resv': converter_valor(r['vl_saldo_resv'])
            })
        
        return jsonify({
            'success': True,
            'dados': resultado,
            'total_registros': len(resultado)
        })
    
    except Exception as e:
        print(f"Erro em api_reservas: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@gestao_orcamentaria_bp.route('/relatorio-empenhos')
@requires_access('gestao_orcamentaria')
def relatorio_empenhos():
    """Página do relatório de empenhos"""
    return render_template('gestao_orcamentaria/relatorio_empenhos.html')


@gestao_orcamentaria_bp.route('/api/empenhos')
@requires_access('gestao_orcamentaria')
def api_empenhos():
    """API para obter dados dos empenhos"""
    try:
        cur = get_cursor()
        
        # Pegar filtros (opcional)
        filtro_dotacao = request.args.get('dotacao_formatada', '').strip()
        
        # Função auxiliar para converter valores VARCHAR para float
        def converter_valor(valor_str):
            if not valor_str:
                return 0
            try:
                valor_limpo = str(valor_str).replace(',', '.')
                return float(valor_limpo)
            except:
                return 0
        
        # Query base
        query = """
            SELECT 
                dt_eph,
                cod_eph,
                cod_nro_pcss_sof,
                txt_obs_eph,
                val_tot_eph,
                val_tot_canc_eph,
                val_tot_lqdc_eph,
                val_tot_pago_eph,
                cod_item_desp_sof,
                nom_rzao_soci_sof,
                cod_cpf_cnpj_sof,
                txt_dotacao_fmt
            FROM gestao_financeira.back_empenhos
            WHERE 1=1
        """
        
        params = []
        
        # Adicionar filtro de dotação se fornecido
        if filtro_dotacao:
            query += " AND txt_dotacao_fmt ILIKE %s"
            params.append(f'%{filtro_dotacao}%')
        
        query += " ORDER BY dt_eph DESC, cod_eph DESC"
        
        cur.execute(query, params)
        resultados = cur.fetchall()
        
        # Processar resultados
        resultado = []
        for r in resultados:
            # Formatar data
            dt_eph_formatada = r['dt_eph'].strftime('%d/%m/%Y') if r['dt_eph'] else None
            
            resultado.append({
                'dt_eph': dt_eph_formatada,
                'cod_eph': r['cod_eph'],
                'cod_nro_pcss_sof': r['cod_nro_pcss_sof'],
                'txt_obs_eph': r['txt_obs_eph'],
                'val_tot_eph': converter_valor(r['val_tot_eph']),
                'val_tot_canc_eph': converter_valor(r['val_tot_canc_eph']),
                'val_tot_lqdc_eph': converter_valor(r['val_tot_lqdc_eph']),
                'val_tot_pago_eph': converter_valor(r['val_tot_pago_eph']),
                'cod_item_desp_sof': r['cod_item_desp_sof'],
                'nom_rzao_soci_sof': r['nom_rzao_soci_sof'],
                'cod_cpf_cnpj_sof': r['cod_cpf_cnpj_sof'],
                'txt_dotacao_fmt': r['txt_dotacao_fmt']
            })
        
        return jsonify({
            'success': True,
            'dados': resultado,
            'total_registros': len(resultado)
        })
    
    except Exception as e:
        print(f"Erro em api_empenhos: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()
