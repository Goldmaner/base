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
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

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
                SUM(CASE WHEN ul.parcela_tipo = 'Projetada' THEN ul.valor_previsto ELSE 0 END) as total_projetado,
                SUM(CASE WHEN ul.parcela_status = 'Pago' THEN ul.valor_previsto ELSE 0 END) as total_pago,
                SUM(CASE WHEN ul.parcela_status = 'Encaminhado para Pagamento' THEN ul.valor_previsto ELSE 0 END) as total_comprometido
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
            total_pago = float(termo['total_pago'] or 0)
            total_comprometido = float(termo['total_comprometido'] or 0)
            
            # Extrair informações do termo
            # Formato esperado: TCL/055/2023/SMDHC/SESANA
            partes_termo = numero_termo.split('/')
            
            if len(partes_termo) < 5:
                # Termo com formato inválido, pular
                continue
            
            tipo_termo = partes_termo[0]  # Ex: TCL, TFM
            unidade = partes_termo[4] if len(partes_termo) > 4 else None  # Ex: SESANA, FUMCAD
            
            # Buscar informações da parceria (OSC, CNPJ, Projeto, SEI Celebração, SEI PC, tipo_termo, final, inicio)
            cur.execute("""
                SELECT 
                    osc, cnpj, projeto, sei_celeb, sei_pc, tipo_termo, final, inicio, total_previsto,
                    CASE 
                        WHEN final IS NOT NULL AND inicio IS NOT NULL THEN
                            EXTRACT(YEAR FROM AGE(final, inicio)) * 12 + EXTRACT(MONTH FROM AGE(final, inicio))
                        ELSE NULL
                    END as meses_vigencia
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
            data_inicio = parceria['inicio'].strftime('%d/%m/%Y') if parceria and parceria['inicio'] else None
            meses_vigencia = int(parceria['meses_vigencia']) if parceria and parceria['meses_vigencia'] is not None else None
            valor_atualizado = float(parceria['total_previsto']) if parceria and parceria['total_previsto'] is not None else None
            
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
                    'data_inicio': data_inicio or '-',
                    'data_termino': data_termino or '-',
                    'meses_vigencia': meses_vigencia if meses_vigencia is not None else '-',
                    'valor_atualizado': valor_atualizado if valor_atualizado is not None else 0,
                    'total_programado': total_programado,
                    'total_projetado': total_projetado,
                    'total_global': total_global,
                    'total_pago': total_pago,
                    'total_comprometido': total_comprometido
                })
        
        # 3. Buscar EDITAIS da tabela orcamento_edital_nova
        # Editais NUNCA têm valor programado, apenas projetado
        # Usa subquery para:
        #   - somar apenas os meses do ano de referência (total_projetado)
        #   - mas mostrar as datas reais do edital (inicio/termino globais)
        #   - e calcular meses_vigencia sobre o span total do edital
        cur.execute("""
            SELECT 
                edital_nome,
                dotacao_formatada,
                projeto_atividade,
                SUM(CASE WHEN EXTRACT(YEAR FROM nome_mes) = %(ano)s THEN valor_mes ELSE 0 END) as total_projetado,
                SUM(valor_mes) as total_edital,
                MIN(nome_mes) as data_inicio,
                MAX(nome_mes) as data_termino,
                EXTRACT(YEAR FROM AGE(MAX(nome_mes), MIN(nome_mes))) * 12 + 
                EXTRACT(MONTH FROM AGE(MAX(nome_mes), MIN(nome_mes))) + 1 as meses_vigencia
            FROM gestao_financeira.orcamento_edital_nova
            WHERE edital_nome IN (
                SELECT DISTINCT edital_nome
                FROM gestao_financeira.orcamento_edital_nova
                WHERE EXTRACT(YEAR FROM nome_mes) = %(ano)s
            )
            GROUP BY edital_nome, dotacao_formatada, projeto_atividade
            HAVING SUM(CASE WHEN EXTRACT(YEAR FROM nome_mes) = %(ano)s THEN valor_mes ELSE 0 END) > 0
            ORDER BY edital_nome
        """, {'ano': ano_referencia})
        
        editais = cur.fetchall()
        
        for edital in editais:
            edital_nome = edital['edital_nome']
            dotacao_formatada = edital['dotacao_formatada']
            projeto_atividade_edital = edital['projeto_atividade']
            total_projetado_edital = float(edital['total_projetado'] or 0)
            data_inicio_edital = edital['data_inicio'].strftime('%d/%m/%Y') if edital.get('data_inicio') else None
            data_termino_edital = edital['data_termino'].strftime('%d/%m/%Y') if edital.get('data_termino') else None
            meses_vigencia_edital = int(edital['meses_vigencia']) if edital.get('meses_vigencia') is not None else None
            # Para editais, valor_atualizado = soma de todos os meses (span completo do edital)
            valor_atualizado_edital = float(edital['total_edital'] or 0)
            
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
                    'data_inicio': data_inicio_edital or '-',  # ⚡ Data de Início do edital (MIN(nome_mes))
                    'data_termino': data_termino_edital or '-',  # ⚡ Data de Término do edital (MAX(nome_mes))
                    'meses_vigencia': meses_vigencia_edital if meses_vigencia_edital is not None else '-',  # ⚡ Meses de vigência
                    'valor_atualizado': valor_atualizado_edital,  # ⚡ Valor Atualizado (soma de valor_mes)
                    'total_programado': 0,  # ⚡ Editais NUNCA têm valor programado
                    'total_projetado': total_projetado_edital,
                    'total_global': total_projetado_edital,  # Global = Projetado (sem Programado)
                    'total_pago': 0,  # Editais não têm pagamentos
                    'total_comprometido': 0  # Editais não têm comprometido
                })
        
        # 4. Buscar TERMOS EM CELEBRAÇÃO da tabela celebracao.celebracao_parcerias
        # Termos em celebração têm valor projetado dinâmico baseado na data atual
        hoje = date.today()
        ano_ref_int = int(ano_referencia)
        
        cur.execute("""
            SELECT 
                id, edital_nome, unidade_gestora, tipo_termo, sei_celeb,
                osc, cnpj, projeto, meses, dias, total_previsto,
                inicio, final, status_generico, numero_termo
            FROM celebracao.celebracao_parcerias
            WHERE status_generico = 'Em celebração'
              AND total_previsto IS NOT NULL
              AND total_previsto > 0
        """)
        
        celebracoes = cur.fetchall()
        
        # Cronograma mensal para celebrações (será retornado junto)
        cronograma_celebracoes = {}
        
        for cel in celebracoes:
            # --- Determinar datas ---
            data_inicio_cel = cel['inicio']
            
            meses_cel = cel['meses'] if cel['meses'] else 12
            total_previsto = float(cel['total_previsto'] or 0)
            
            # --- Calcular projetado mensal dinâmico ---
            valor_mensal = total_previsto / meses_cel if meses_cel > 0 else 0
            
            # Início da projeção (dinâmico):
            # - Se início real for definido e ainda no futuro → usar ele
            # - Se início real for definido e já passou → projetar a partir de hoje
            # - Se início não definido (null):
            #     - Ano de referência futuro → usar 1º dia desse ano (projetar ano todo)
            #     - Ano de referência atual → usar 1º dia do mês atual (projetar de hoje)
            #     - Ano de referência passado → usar hoje (resultará em 0 para anos passados, comportamento esperado)
            hoje_mes1 = date(hoje.year, hoje.month, 1)
            if data_inicio_cel:
                data_proj_inicio = max(data_inicio_cel, hoje_mes1)
            else:
                if ano_ref_int > hoje.year:
                    data_proj_inicio = date(ano_ref_int, 1, 1)
                else:
                    data_proj_inicio = hoje_mes1
            
            mes_inicio_proj = data_proj_inicio.month
            ano_inicio_proj = data_proj_inicio.year
            
            # Data de início real para exibição (usar data_proj_inicio se início nulo)
            if not data_inicio_cel:
                data_inicio_cel = data_proj_inicio
            
            # Data de término: início real + meses
            data_termino_cel = data_inicio_cel + relativedelta(months=meses_cel) - timedelta(days=1)
            
            # Calcular quantos meses do projetado caem no ano de referência
            cronograma_mensal_cel = {}
            total_projetado_cel = 0
            
            for i in range(meses_cel):
                mes_proj = mes_inicio_proj + i
                ano_proj = ano_inicio_proj
                while mes_proj > 12:
                    mes_proj -= 12
                    ano_proj += 1
                
                if ano_proj == ano_ref_int:
                    cronograma_mensal_cel[mes_proj] = cronograma_mensal_cel.get(mes_proj, 0) + valor_mensal
                    total_projetado_cel += valor_mensal
            
            # Se não tem valor projetado neste ano, pular
            if total_projetado_cel <= 0:
                continue
            
            # --- Buscar dotação orçamentária ---
            tipo_termo_cel = cel['tipo_termo'] or ''
            unidade_gestora = cel['unidade_gestora'] or ''
            edital_nome_cel = cel['edital_nome'] or ''
            
            # Mapear tipo_termo para condicoes_termo
            mapa_tipo_termo = {
                'Fomento': 'TFM',
                'Colaboração': 'TCL',
                'Acordo de Cooperação': 'ACO'
            }
            condicoes_termo = mapa_tipo_termo.get(tipo_termo_cel, '')
            
            # Regra especial: verificar edital_nome para override de unidade
            condicoes_unidade = unidade_gestora
            
            # Se edital_nome contém "FUMCAD" e unidade_gestora é CPCA → usar FUMCAD
            if 'FUMCAD' in edital_nome_cel.upper() and unidade_gestora.upper() == 'CPCA':
                condicoes_unidade = 'FUMCAD'
                condicoes_termo = 'TFM'
            
            # Se edital_nome contém "FMID" → usar FMID
            if 'FMID' in edital_nome_cel.upper():
                condicoes_unidade = 'FMID'
                condicoes_termo = 'TFM'
            
            dotacao_cel = None
            programatica_cel = None
            
            if condicoes_termo and condicoes_unidade:
                # Tentar buscar dotação com OSC primeiro
                if cel['osc']:
                    cur.execute("""
                        SELECT dotacao_numero, programa_aplicacao
                        FROM categoricas.c_geral_dotacoes
                        WHERE condicoes_termo = %s 
                          AND condicoes_unidade = %s
                          AND condicoes_osc = %s
                        LIMIT 1
                    """, (condicoes_termo, condicoes_unidade, cel['osc']))
                    dotacao_row = cur.fetchone()
                    if dotacao_row:
                        dotacao_cel = dotacao_row['dotacao_numero']
                        programatica_cel = dotacao_row['programa_aplicacao']
                
                # Se não encontrou com OSC, tentar sem
                if not dotacao_cel:
                    cur.execute("""
                        SELECT dotacao_numero, programa_aplicacao
                        FROM categoricas.c_geral_dotacoes
                        WHERE condicoes_termo = %s 
                          AND condicoes_unidade = %s
                          AND (condicoes_osc IS NULL OR condicoes_osc = '')
                        LIMIT 1
                    """, (condicoes_termo, condicoes_unidade))
                    dotacao_row = cur.fetchone()
                    if dotacao_row:
                        dotacao_cel = dotacao_row['dotacao_numero']
                        programatica_cel = dotacao_row['programa_aplicacao']
            
            # Extrair Projeto-Atividade da dotação
            projeto_atividade_cel = None
            if dotacao_cel:
                partes_dotacao = dotacao_cel.split('.')
                if len(partes_dotacao) >= 7:
                    projeto_atividade_cel = partes_dotacao[5] + '.' + partes_dotacao[6]
            
            # Formatar datas para exibição
            data_inicio_fmt = data_inicio_cel.strftime('%d/%m/%Y') if data_inicio_cel else '-'
            data_termino_fmt = data_termino_cel.strftime('%d/%m/%Y') if data_termino_cel else '-'
            
            # Identificador para o cronograma: usar "Termo em celebração" + sei_celeb ou id
            id_termo_celeb = f"Termo em celebração ({cel['sei_celeb']})" if cel['sei_celeb'] else f"Termo em celebração #{cel['id']}"
            
            # Se não identificou dotação, não incluir
            if not dotacao_cel:
                continue

            resultado.append({
                'numero_termo': id_termo_celeb,
                'dotacao_orcamentaria': dotacao_cel,
                'projeto_atividade': projeto_atividade_cel or '-',
                'programatica': programatica_cel or '-',
                'cnpj': cel['cnpj'] or '-',
                'sei_pc': '-',  # Termos em celebração não têm SEI PC
                'osc': cel['osc'] or '-',
                'projeto': cel['projeto'] or '-',
                'sei_celeb': cel['sei_celeb'] or '-',
                'tipo_contrato': tipo_termo_cel or '-',
                'data_inicio': data_inicio_fmt,
                'data_termino': data_termino_fmt,
                'meses_vigencia': meses_cel,
                'valor_atualizado': total_previsto,
                'total_programado': 0,  # Celebração NUNCA tem valor programado
                'total_projetado': round(total_projetado_cel, 2),
                'total_global': round(total_projetado_cel, 2),
                'total_pago': 0,  # Termos em celebração ainda não foram pagos
                'total_comprometido': 0  # Termos em celebração ainda não foram encaminhados
            })
            
            # Salvar cronograma mensal para uso no frontend
            cronograma_celebracoes[id_termo_celeb] = {
                str(mes): round(val, 2) for mes, val in cronograma_mensal_cel.items()
            }
        
        # 5. Buscar valor disponível de back_reservas, cruzando pelo SEI de celebração
        # total_disponivel = (vl_saldo_resv + vl_eph) - total_pago
        try:
            cur.execute("""
                SELECT cod_nro_pcss_sof,
                       SUM(
                           REPLACE(vl_saldo_resv::text, ',', '.')::numeric +
                           REPLACE(vl_eph::text, ',', '.')::numeric
                       ) as valor_disponivel
                FROM gestao_financeira.back_reservas
                GROUP BY cod_nro_pcss_sof
            """)
            reservas_rows = cur.fetchall()
            disponivel_por_sei = {
                row['cod_nro_pcss_sof'].strip(): float(row['valor_disponivel'] or 0)
                for row in reservas_rows
            }
        except Exception as e_resv:
            print(f"[ERRO back_reservas] {e_resv}")
            import traceback; traceback.print_exc()
            disponivel_por_sei = {}

        # Enriquecer resultado com total_disponivel e valor_residual
        for item in resultado:
            sei = item.get('sei_celeb', '-')
            sei_strip = sei.strip() if sei and sei != '-' else None
            valor_disponivel = disponivel_por_sei.get(sei_strip, 0) if sei_strip else 0
            total_pago_item = float(item.get('total_pago') or 0)
            td = max(valor_disponivel - total_pago_item, 0)
            item['total_disponivel'] = round(td, 2)
            total_global_item = item.get('total_global') or 0
            residual = td - total_global_item
            item['valor_residual'] = round(residual, 2) if residual > 0 else 0

        return jsonify({
            'success': True,
            'dados': resultado,
            'total_registros': len(resultado),
            'cronograma_celebracoes': cronograma_celebracoes
        })
    
    except Exception as e:
        print(f"Erro em api_orcamento_detalhado: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@gestao_orcamentaria_bp.route('/api/cronograma-pago')
@login_required
@requires_access('gestao_orcamentaria')
def api_cronograma_pago():
    """API para obter cronograma mensal de valores PAGOS por termo (ano de referência)"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        ano_referencia = request.args.get('ano_referencia')
        if not ano_referencia:
            return jsonify({'success': False, 'error': 'Ano de referência não fornecido'}), 400
        
        cur.execute("""
            SELECT
                numero_termo,
                EXTRACT(MONTH FROM vigencia_inicial)::int AS mes,
                SUM(valor_previsto) AS valor
            FROM gestao_financeira.ultra_liquidacoes
            WHERE parcela_status = 'Pago'
              AND EXTRACT(YEAR FROM vigencia_inicial) = %s
            GROUP BY numero_termo, EXTRACT(MONTH FROM vigencia_inicial)
            ORDER BY numero_termo, mes
        """, (ano_referencia,))
        
        rows = cur.fetchall()
        
        dados_pago = {}
        for row in rows:
            nt = row['numero_termo']
            mes = int(row['mes'])
            valor = float(row['valor'] or 0)
            if nt not in dados_pago:
                dados_pago[nt] = {}
            dados_pago[nt][mes] = dados_pago[nt].get(mes, 0) + valor
        
        return jsonify({'success': True, 'dados_pago': dados_pago})
    
    except Exception as e:
        print(f"Erro em api_cronograma_pago: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@gestao_orcamentaria_bp.route('/api/cronograma-comprometido')
@login_required
@requires_access('gestao_orcamentaria')
def api_cronograma_comprometido():
    """API para obter cronograma mensal de valores COMPROMETIDOS por termo (Encaminhado para Pagamento)"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        ano_referencia = request.args.get('ano_referencia')
        if not ano_referencia:
            return jsonify({'success': False, 'error': 'Ano de referência não fornecido'}), 400
        
        cur.execute("""
            SELECT
                numero_termo,
                EXTRACT(MONTH FROM vigencia_inicial)::int AS mes,
                SUM(valor_previsto) AS valor
            FROM gestao_financeira.ultra_liquidacoes
            WHERE parcela_status = 'Encaminhado para Pagamento'
              AND EXTRACT(YEAR FROM vigencia_inicial) = %s
            GROUP BY numero_termo, EXTRACT(MONTH FROM vigencia_inicial)
            ORDER BY numero_termo, mes
        """, (ano_referencia,))
        
        rows = cur.fetchall()
        
        dados_comprometido = {}
        for row in rows:
            nt = row['numero_termo']
            mes = int(row['mes'])
            valor = float(row['valor'] or 0)
            if nt not in dados_comprometido:
                dados_comprometido[nt] = {}
            dados_comprometido[nt][mes] = dados_comprometido[nt].get(mes, 0) + valor
        
        return jsonify({'success': True, 'dados_comprometido': dados_comprometido})
    
    except Exception as e:
        print(f"Erro em api_cronograma_comprometido: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


def _distribuir_cronograma_por_status(ano_referencia, parcela_status):
    """
    Distribui valores de ultra_liquidacoes_cronograma pelos meses do ano,
    respeitando o valor_previsto de cada parcela (fill-from-start).

    Algoritmo:
      - Para cada parcela (numero_termo, parcela_numero) com o status dado:
          1. Obtém valor_previsto de ultra_liquidacoes.
          2. Obtém entradas mensais de ultra_liquidacoes_cronograma para o ano.
          3. Ordena meses ASC e preenche do início até esgotar valor_previsto.
          4. Se valor_previsto > soma do cronograma, o excesso vai para o último mês
             e este mês é marcado como "destacado" (fundo diferente no front).

    Retorna dict: {numero_termo: {"meses": {1..12: float}, "highlighted": [int]}}
    """
    conn = get_db()
    cur = get_cursor()
    try:
        # 1. Parcelas com valor_previsto para o status/ano
        cur.execute("""
            SELECT
                numero_termo,
                parcela_numero,
                SUM(valor_previsto)::float AS valor_previsto
            FROM gestao_financeira.ultra_liquidacoes
            WHERE parcela_status = %s
              AND EXTRACT(YEAR FROM vigencia_inicial) = %s
            GROUP BY numero_termo, parcela_numero
        """, (parcela_status, ano_referencia))
        parcelas = {}
        for r in cur.fetchall():
            key = (r['numero_termo'], r['parcela_numero'])
            parcelas[key] = float(r['valor_previsto'] or 0)

        if not parcelas:
            return {}

        # 2. Cronograma mensal para o ano
        termos_list = list({k[0] for k in parcelas})
        cur.execute("""
            SELECT
                numero_termo,
                parcela_numero,
                EXTRACT(MONTH FROM nome_mes)::int AS mes,
                valor_mes::float AS valor_mes
            FROM gestao_financeira.ultra_liquidacoes_cronograma
            WHERE EXTRACT(YEAR FROM nome_mes) = %s
              AND numero_termo = ANY(%s)
            ORDER BY numero_termo, parcela_numero, nome_mes
        """, (ano_referencia, termos_list))

        cronograma_raw = {}  # {(termo, parcela): [(mes, valor), ...]}
        for r in cur.fetchall():
            key = (r['numero_termo'], r['parcela_numero'])
            cronograma_raw.setdefault(key, []).append(
                (int(r['mes']), float(r['valor_mes'] or 0))
            )

        # 3. Aplicar algoritmo fill-from-start por parcela
        resultado = {}  # {termo: {"meses": {mes: float}, "highlighted": [mes]}}

        for (termo, parcela), valor_previsto in parcelas.items():
            entries = sorted(cronograma_raw.get((termo, parcela), []), key=lambda x: x[0])
            if not entries:
                continue

            if termo not in resultado:
                resultado[termo] = {'meses': {}, 'highlighted': []}

            remaining = valor_previsto

            for i, (mes, cronograma_val) in enumerate(entries):
                is_last = (i == len(entries) - 1)

                if remaining <= 0:
                    month_value = 0.0
                elif is_last:
                    # Último mês: recebe todo o restante (pode ser > cronograma_val)
                    month_value = remaining
                    if remaining > cronograma_val:
                        resultado[termo]['highlighted'].append(mes)
                    remaining = 0.0
                elif remaining >= cronograma_val:
                    month_value = cronograma_val
                    remaining -= cronograma_val
                else:
                    # Mês parcial
                    month_value = remaining
                    remaining = 0.0

                resultado[termo]['meses'][mes] = (
                    resultado[termo]['meses'].get(mes, 0.0) + month_value
                )

        return resultado
    finally:
        cur.close()


@gestao_orcamentaria_bp.route('/api/cronograma-pago-detalhado')
@login_required
@requires_access('gestao_orcamentaria')
def api_cronograma_pago_detalhado():
    """Cronograma detalhado de PAGOS (fill-from-start via ultra_liquidacoes_cronograma)"""
    ano_referencia = request.args.get('ano_referencia')
    if not ano_referencia:
        return jsonify({'success': False, 'error': 'Ano de referência não fornecido'}), 400
    try:
        dados = _distribuir_cronograma_por_status(ano_referencia, 'Pago')
        return jsonify({'success': True, 'dados': dados})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@gestao_orcamentaria_bp.route('/api/cronograma-comprometido-detalhado')
@login_required
@requires_access('gestao_orcamentaria')
def api_cronograma_comprometido_detalhado():
    """Cronograma detalhado de COMPROMETIDOS (fill-from-start via ultra_liquidacoes_cronograma)"""
    ano_referencia = request.args.get('ano_referencia')
    if not ano_referencia:
        return jsonify({'success': False, 'error': 'Ano de referência não fornecido'}), 400
    try:
        dados = _distribuir_cronograma_por_status(ano_referencia, 'Encaminhado para Pagamento')
        return jsonify({'success': True, 'dados': dados})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


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


@gestao_orcamentaria_bp.route('/api/dotacoes/csv-completo')
@login_required
@requires_access('gestao_orcamentaria')
def api_dotacoes_csv_completo():
    """API para exportar CSV completo de todas as dotações"""
    from flask import Response
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Query para buscar TODAS as colunas da tabela
        query = """
            SELECT 
                cod_idt_dota,
                cod_org_emp,
                txt_org_emp,
                cod_unid_orcm_sof,
                txt_unid_orcm,
                cod_fcao_govr,
                txt_fcao_govr,
                cod_sub_fcao_govr,
                txt_sub_fcao_govr,
                cod_pgm_govr,
                txt_pgm_govr,
                cod_proj_atvd_sof,
                txt_proj_atvd,
                cod_cta_desp,
                txt_cta_desp,
                cod_font_rec,
                txt_font_rec,
                cod_ex_font_rec,
                cod_dstn_rec,
                cod_vinc_rec_pmsp,
                cod_tip_cred_orcm,
                ind_actc_redc,
                ind_cntr_cota_pesl,
                ind_cota_pesl,
                ind_dota_lqdd_pago,
                dt_cria_dota,
                val_dota_autr,
                val_tot_cred_splm,
                val_tot_cred_espc,
                val_tot_cred_ext,
                val_tot_redc,
                orcado_atual,
                val_tot_cngl,
                val_tot_bloq_decr,
                orcado_disponivel,
                val_sldo_resv_dota,
                saldo_dotacao,
                val_tot_eph,
                val_tot_canc_eph,
                saldo_empenhado,
                saldo_reservado,
                val_tot_lqdc_eph,
                val_tot_pgto_dota,
                ind_emnd_orcm,
                dotacao_formatada,
                ind_dvda_pubc,
                ind_lanc_rcta,
                criado_em
            FROM gestao_financeira.back_dotacao
            ORDER BY dotacao_formatada
        """
        
        cur.execute(query)
        dotacoes = cur.fetchall()
        
        # Converter valores monetários
        def converter_valor(valor_str):
            if not valor_str:
                return 0
            valor_limpo = str(valor_str).replace(',', '.')
            try:
                return float(valor_limpo)
            except:
                return 0
        
        def formatar_valor_csv(valor):
            """Formatar valor para CSV no formato brasileiro"""
            num = float(valor) if valor else 0
            return f"{num:.2f}".replace('.', ',')
        
        def formatar_data(data):
            """Formatar data para CSV"""
            if not data:
                return ""
            try:
                return data.strftime("%d/%m/%Y %H:%M") if hasattr(data, 'strftime') else str(data)
            except:
                return str(data)
        
        # Criar CSV com BOM UTF-8
        csv_lines = []
        csv_lines.append('\ufeff')  # BOM UTF-8
        
        # Cabeçalho com TODAS as colunas
        cabecalho = [
            'Código ID Dotação',
            'Código Órgão Empenhador',
            'Texto Órgão Empenhador',
            'Código Unidade Orçamentária SOF',
            'Texto Unidade Orçamentária',
            'Código Função Governo',
            'Texto Função Governo',
            'Código Sub-Função Governo',
            'Texto Sub-Função Governo',
            'Código Programa Governo',
            'Texto Programa Governo',
            'Código Projeto-Atividade SOF',
            'Texto Projeto-Atividade',
            'Código Conta Despesa',
            'Texto Conta Despesa',
            'Código Fonte Recurso',
            'Texto Fonte Recurso',
            'Código Exercício Fonte Recurso',
            'Código Destino Recurso',
            'Código Vínculo Recurso PMSP',
            'Código Tipo Crédito Orçamentário',
            'Indicador ACTC REDC',
            'Indicador Controle Cota Pessoal',
            'Indicador Cota Pessoal',
            'Indicador Dotação Liquidada Paga',
            'Data Criação Dotação',
            'Valor Dotação Autorizada',
            'Valor Total Crédito Suplementar',
            'Valor Total Crédito Especial',
            'Valor Total Crédito Extraordinário',
            'Valor Total Redução',
            'Orçado Atual',
            'Valor Total Congelado',
            'Valor Total Bloqueio Decreto',
            'Orçado Disponível',
            'Valor Saldo Reserva Dotação',
            'Saldo Dotação',
            'Valor Total Empenhado',
            'Valor Total Cancelado Empenho',
            'Saldo Empenhado',
            'Saldo Reservado',
            'Valor Total Liquidado Empenho',
            'Valor Total Pago Dotação',
            'Indicador Emenda Orçamentária',
            'Dotação Formatada',
            'Indicador Dívida Pública',
            'Indicador Lançamento RCTA',
            'Criado Em'
        ]
        csv_lines.append(';'.join(cabecalho) + '\n')
        
        # Dados
        for d in dotacoes:
            linha = [
                f'"{d["cod_idt_dota"] or ""}"',
                f'"{d["cod_org_emp"] or ""}"',
                f'"{d["txt_org_emp"] or ""}"',
                f'"{d["cod_unid_orcm_sof"] or ""}"',
                f'"{d["txt_unid_orcm"] or ""}"',
                f'"{d["cod_fcao_govr"] or ""}"',
                f'"{d["txt_fcao_govr"] or ""}"',
                f'"{d["cod_sub_fcao_govr"] or ""}"',
                f'"{d["txt_sub_fcao_govr"] or ""}"',
                f'"{d["cod_pgm_govr"] or ""}"',
                f'"{d["txt_pgm_govr"] or ""}"',
                f'"{d["cod_proj_atvd_sof"] or ""}"',
                f'"{d["txt_proj_atvd"] or ""}"',
                f'"{d["cod_cta_desp"] or ""}"',
                f'"{d["txt_cta_desp"] or ""}"',
                f'"{d["cod_font_rec"] or ""}"',
                f'"{d["txt_font_rec"] or ""}"',
                f'"{d["cod_ex_font_rec"] or ""}"',
                f'"{d["cod_dstn_rec"] or ""}"',
                f'"{d["cod_vinc_rec_pmsp"] or ""}"',
                f'"{d["cod_tip_cred_orcm"] or ""}"',
                f'"{d["ind_actc_redc"] or ""}"',
                f'"{d["ind_cntr_cota_pesl"] or ""}"',
                f'"{d["ind_cota_pesl"] or ""}"',
                f'"{d["ind_dota_lqdd_pago"] or ""}"',
                f'"{formatar_data(d["dt_cria_dota"])}"',
                formatar_valor_csv(converter_valor(d['val_dota_autr'])),
                formatar_valor_csv(converter_valor(d['val_tot_cred_splm'])),
                formatar_valor_csv(converter_valor(d['val_tot_cred_espc'])),
                formatar_valor_csv(converter_valor(d['val_tot_cred_ext'])),
                formatar_valor_csv(converter_valor(d['val_tot_redc'])),
                formatar_valor_csv(converter_valor(d['orcado_atual'])),
                formatar_valor_csv(converter_valor(d['val_tot_cngl'])),
                formatar_valor_csv(converter_valor(d['val_tot_bloq_decr'])),
                formatar_valor_csv(converter_valor(d['orcado_disponivel'])),
                formatar_valor_csv(converter_valor(d['val_sldo_resv_dota'])),
                formatar_valor_csv(converter_valor(d['saldo_dotacao'])),
                formatar_valor_csv(converter_valor(d['val_tot_eph'])),
                formatar_valor_csv(converter_valor(d['val_tot_canc_eph'])),
                formatar_valor_csv(converter_valor(d['saldo_empenhado'])),
                formatar_valor_csv(converter_valor(d['saldo_reservado'])),
                formatar_valor_csv(converter_valor(d['val_tot_lqdc_eph'])),
                formatar_valor_csv(converter_valor(d['val_tot_pgto_dota'])),
                f'"{d["ind_emnd_orcm"] or ""}"',
                f'"{d["dotacao_formatada"] or ""}"',
                f'"{d["ind_dvda_pubc"] or ""}"',
                f'"{d["ind_lanc_rcta"] or ""}"',
                f'"{formatar_data(d["criado_em"])}"'
            ]
            csv_lines.append(';'.join(linha) + '\n')
        
        csv_content = ''.join(csv_lines)
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=dotacoes_completo_{__import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                'Content-Type': 'text/csv; charset=utf-8-sig'
            }
        )
    
    except Exception as e:
        print(f"Erro em api_dotacoes_csv_completo: {str(e)}")
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
                vl_resv,
                vl_transf_resv,
                vl_canc_resv,
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
            vl_resv = converter_valor(r['vl_resv'])
            vl_transf = converter_valor(r['vl_transf_resv'])
            vl_canc = converter_valor(r['vl_canc_resv'])
            resultado.append({
                'cod_resv_dota_sof': r['cod_resv_dota_sof'],
                'dt_efet_resv': r['dt_efet_resv'].strftime('%d/%m/%Y') if r['dt_efet_resv'] else None,
                'dotacao_formatada': r['dotacao_formatada'],
                'hist_resv': r['hist_resv'],
                'valor_reservado': round(vl_resv + vl_transf - vl_canc, 2),
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


@gestao_orcamentaria_bp.route('/api/reservas/csv-completo')
@login_required
@requires_access('gestao_orcamentaria')
def api_reservas_csv_completo():
    """API para exportar CSV completo de todas as reservas"""
    from flask import Response
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Query para buscar TUDO sem filtros
        query = """
            SELECT 
                cod_resv_dota_sof,
                dt_efet_resv,
                dotacao_formatada,
                hist_resv,
                vl_resv,
                vl_transf_resv,
                vl_canc_resv,
                vl_saldo_resv
            FROM gestao_financeira.back_reservas
            ORDER BY dt_efet_resv DESC, cod_resv_dota_sof DESC
        """
        
        cur.execute(query)
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
        
        def formatar_valor_csv(valor):
            """Formatar valor para CSV no formato brasileiro"""
            num = float(valor) if valor else 0
            return f"{num:.2f}".replace('.', ',')
        
        # Criar CSV com BOM UTF-8
        csv_lines = []
        csv_lines.append('\ufeff')  # BOM UTF-8
        csv_lines.append('Código da Reserva;Data da Reserva;Dotação Formatada;Histórico da Reserva;Valor Reservado;Saldo de Reserva\n')
        
        for r in reservas:
            vl_resv = converter_valor(r['vl_resv'])
            vl_transf = converter_valor(r['vl_transf_resv'])
            vl_canc = converter_valor(r['vl_canc_resv'])
            valor_reservado = vl_resv + vl_transf - vl_canc
            linha = [
                f'"{r["cod_resv_dota_sof"] or ""}"',
                f'"{r["dt_efet_resv"].strftime("%d/%m/%Y") if r["dt_efet_resv"] else ""}"',
                f'"{r["dotacao_formatada"] or ""}"',
                f'"{r["hist_resv"] or ""}"',
                formatar_valor_csv(valor_reservado),
                formatar_valor_csv(converter_valor(r['vl_saldo_resv']))
            ]
            csv_lines.append(';'.join(linha) + '\n')
        
        csv_content = ''.join(csv_lines)
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=reservas_completo_{__import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                'Content-Type': 'text/csv; charset=utf-8-sig'
            }
        )
    
    except Exception as e:
        print(f"Erro em api_reservas_csv_completo: {str(e)}")
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


@gestao_orcamentaria_bp.route('/api/empenhos/csv-completo')
@requires_access('gestao_orcamentaria')
def api_empenhos_csv_completo():
    """API para exportar CSV completo de todos os empenhos"""
    from flask import Response
    try:
        cur = get_cursor()
        
        # Query para buscar TUDO sem filtros
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
            ORDER BY dt_eph DESC, cod_eph DESC
        """
        
        cur.execute(query)
        empenhos = cur.fetchall()
        
        # Converter valores monetários
        def converter_valor(valor_str):
            if not valor_str:
                return 0
            try:
                valor_limpo = str(valor_str).replace(',', '.')
                return float(valor_limpo)
            except:
                return 0
        
        def formatar_valor_csv(valor):
            """Formatar valor para CSV no formato brasileiro"""
            num = float(valor) if valor else 0
            return f"{num:.2f}".replace('.', ',')
        
        # Criar CSV com BOM UTF-8
        csv_lines = []
        csv_lines.append('\ufeff')  # BOM UTF-8
        csv_lines.append('Data do Empenho;Código;SEI de Celebração;Texto do Empenho;Valor Total;Valor Cancelado;Valor Liquidado;Valor Pago;Cód. Despesa;Razão Social;CNPJ;Dotação Formatada\n')
        
        for e in empenhos:
            linha = [
                f'"{e["dt_eph"].strftime("%d/%m/%Y") if e["dt_eph"] else ""}"',
                f'"{e["cod_eph"] or ""}"',
                f'"{e["cod_nro_pcss_sof"] or ""}"',
                f'"{(e["txt_obs_eph"] or "").replace(chr(34), chr(34)+chr(34))}"',  # Escapar aspas duplas
                formatar_valor_csv(converter_valor(e['val_tot_eph'])),
                formatar_valor_csv(converter_valor(e['val_tot_canc_eph'])),
                formatar_valor_csv(converter_valor(e['val_tot_lqdc_eph'])),
                formatar_valor_csv(converter_valor(e['val_tot_pago_eph'])),
                f'"{e["cod_item_desp_sof"] or ""}"',
                f'"{(e["nom_rzao_soci_sof"] or "").replace(chr(34), chr(34)+chr(34))}"',
                f'"{e["cod_cpf_cnpj_sof"] or ""}"',
                f'"{e["txt_dotacao_fmt"] or ""}"'
            ]
            csv_lines.append(';'.join(linha) + '\n')
        
        csv_content = ''.join(csv_lines)
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=empenhos_completo_{__import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                'Content-Type': 'text/csv; charset=utf-8-sig'
            }
        )
    
    except Exception as e:
        print(f"Erro em api_empenhos_csv_completo: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()
