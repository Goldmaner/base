# -*- coding: utf-8 -*-
"""
Blueprint para Gestão Financeira - Ultra Liquidações
Sistema de controle de parcelas com validações e filtros avançados
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_db, get_cursor
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from utils import login_required
from decimal import Decimal
import csv
import io
import calendar
import re

ultra_liquidacoes_bp = Blueprint('ultra_liquidacoes', __name__, url_prefix='/gestao_financeira/ultra-liquidacoes')


def formatar_moeda_br(valor):
    """Formata valor Decimal para string em formato brasileiro"""
    if valor is None:
        return 'R$ 0,00'
    return f"R$ {float(valor):,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')


def formatar_data_br(data):
    """Formata date para string dd/mm/yyyy"""
    if data is None:
        return ''
    if isinstance(data, str):
        return data
    return data.strftime('%d/%m/%Y')


def formatar_data_mes_ano(data):
    """Formata date para string 'mês/ano' (ex: jan/26)"""
    if data is None:
        return ''
    if isinstance(data, str):
        # Se já for string, tentar parsear
        try:
            data = datetime.strptime(data, '%d/%m/%Y').date()
        except:
            return data
    
    # Mapeamento de meses em português
    meses = {
        1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
        7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
    }
    
    mes_abrev = meses.get(data.month, '')
    ano_curto = str(data.year)[2:]  # Últimos 2 dígitos do ano
    
    return f"{mes_abrev}/{ano_curto}"


def parse_data_br(data_str):
    """Parse string dd/mm/yyyy para date"""
    if not data_str:
        return None
    try:
        return datetime.strptime(data_str, '%d/%m/%Y').date()
    except:
        return None


def converter_sei_para_cod_sof(sei_celeb):
    """
    Converte SEI do formato '6074.2023/0001930-0' para '6074202300019300'
    Remove pontos, barras e hífens
    """
    if not sei_celeb:
        return None
    return re.sub(r'[.\-/]', '', sei_celeb)


def calcular_empenhos_disponiveis(cur, hoje):
    """
    Retorna detalhes de empenhos disponíveis por termo/ano.
    Retorna: (empenhos_detalhados, pagos_por_elemento, avisos)
    empenhos_detalhados = {(cod_sof, ano): [lista de dicts com cod_eph, val_tot_eph, etc]}
    pagos_por_elemento = {(cod_sof, ano, elemento): total_pago}
    """
    empenhos_por_termo_ano = {}
    pagos_por_elemento = {}  # Novo: agregar valores pagos por elemento
    avisos = []
    
    try:
        # Verificar se tabela existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'gestao_financeira' 
                AND table_name = 'back_empenhos'
            ) as existe
        """)
        
        resultado = cur.fetchone()
        tabela_existe = resultado['existe'] if resultado else False
        
        if not tabela_existe:
            avisos.append({
                'tipo': 'tabela_inexistente',
                'mensagem': 'Tabela gestao_financeira.back_empenhos não encontrada'
            })
            return {}, avisos
        
        # Buscar todos os termos com sei_celeb
        cur.execute("""
            SELECT DISTINCT 
                p.numero_termo,
                p.sei_celeb
            FROM public.parcerias p
            WHERE p.sei_celeb IS NOT NULL AND p.sei_celeb != ''
        """)
        termos_sei = cur.fetchall()
        print(f"   Total de termos com SEI: {len(termos_sei)}")
        
        # Contador para limitar debug
        contador_debug = 0
        max_debug = 5
        
        for termo_sei in termos_sei:
            numero_termo = termo_sei['numero_termo']
            sei_celeb = termo_sei['sei_celeb']
            cod_sof = converter_sei_para_cod_sof(sei_celeb)
            
            if not cod_sof:
                continue
            
            try:
                # Buscar TODOS os campos de empenhos por ano
                # IMPORTANTE: campos são VARCHAR em formato BR (vírgula decimal)
                cur.execute("""
                    SELECT 
                        cod_eph,
                        EXTRACT(YEAR FROM dt_eph)::integer as ano_eph,
                        COALESCE(NULLIF(REPLACE(val_tot_eph, ',', '.'), '')::numeric, 0) as val_tot_eph,
                        COALESCE(NULLIF(REPLACE(val_tot_lqdc_eph, ',', '.'), '')::numeric, 0) as val_tot_lqdc_eph,
                        COALESCE(NULLIF(REPLACE(val_tot_pago_eph, ',', '.'), '')::numeric, 0) as val_tot_pago_eph,
                        COALESCE(NULLIF(REPLACE(val_tot_canc_eph, ',', '.'), '')::numeric, 0) as val_tot_canc_eph,
                        cod_item_desp_sof
                    FROM gestao_financeira.back_empenhos
                    WHERE cod_nro_pcss_sof = %s
                    ORDER BY dt_eph, cod_eph
                """, [cod_sof])
                
                empenhos = cur.fetchall()
                
                # Agrupar por COD_SOF + ANO (não por termo!)
                for emp in empenhos:
                    ano = int(emp['ano_eph'])
                    elemento = emp['cod_item_desp_sof']  # '23' ou '24'
                    chave = (cod_sof, ano)  # CHAVE: (cod_sof, ano) não (termo, ano)!
                    chave_elemento = (cod_sof, ano, elemento)  # CHAVE para pagos por elemento
                    
                    if chave not in empenhos_por_termo_ano:
                        empenhos_por_termo_ano[chave] = []
                    
                    # Cálculo do disponível: Total - Cancelado - Pago (NÃO considerar liquidado)
                    disponivel = (
                        float(emp['val_tot_eph']) - 
                        float(emp['val_tot_canc_eph']) - 
                        float(emp['val_tot_pago_eph'])
                    )
                    
                    # Agregar valor pago por elemento
                    if chave_elemento not in pagos_por_elemento:
                        pagos_por_elemento[chave_elemento] = 0
                    pagos_por_elemento[chave_elemento] += float(emp['val_tot_pago_eph'])
                    
                    empenhos_por_termo_ano[chave].append({
                        'cod_eph': emp['cod_eph'],
                        'ano_eph': ano,
                        'val_tot_eph': float(emp['val_tot_eph']),
                        'val_tot_lqdc_eph': float(emp['val_tot_lqdc_eph']),
                        'val_tot_pago_eph': float(emp['val_tot_pago_eph']),
                        'val_tot_canc_eph': float(emp['val_tot_canc_eph']),
                        'cod_item_desp_sof': elemento,
                        'disponivel': disponivel
                    })
                    
            except Exception as e:
                # ROLLBACK para não quebrar próximas queries
                try:
                    conn = get_db()
                    conn.rollback()
                except:
                    pass
                
                avisos.append({
                    'tipo': 'erro_empenho',
                    'termo': numero_termo,
                    'mensagem': str(e)
                })
                print(f"   ❌ ERRO ao buscar empenhos para {numero_termo}: {str(e)}")
                continue
        
    except Exception as e:
        import traceback
        avisos.append({
            'tipo': 'erro_geral',
            'mensagem': f'Funcionalidade de empenhos desabilitada: {str(e)}'
        })
        print(f"\n❌ ERRO GERAL em calcular_empenhos_disponiveis:")
        print(f"   Erro: {str(e)}")
        print(f"   Tipo: {type(e).__name__}")
        print(f"   Traceback:")
        traceback.print_exc()
        print()
        return {}, avisos
    
    return empenhos_por_termo_ano, pagos_por_elemento, avisos


@ultra_liquidacoes_bp.route('/')
@login_required
def index():
    """Página principal - Ultra Liquidações"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Buscar lista de termos para o filtro
        cur.execute("""
            SELECT DISTINCT numero_termo 
            FROM gestao_financeira.ultra_liquidacoes 
            ORDER BY numero_termo
        """)
        termos = [r['numero_termo'] for r in cur.fetchall()]
        
        # Buscar tipos de parcela
        cur.execute("""
            SELECT DISTINCT parcela_tipo 
            FROM categoricas.c_dac_tipos_parcelas 
            ORDER BY parcela_tipo
        """)
        tipos_parcela = [r['parcela_tipo'] for r in cur.fetchall()]
        
        # Buscar status disponíveis
        status_disponiveis = [
            'Não Pago',
            'Encaminhado para Pagamento',
            'Pago'
        ]
        
        # Buscar tipos de contrato disponíveis
        cur.execute("""
            SELECT DISTINCT tipo_termo 
            FROM public.parcerias 
            WHERE tipo_termo IS NOT NULL 
            ORDER BY tipo_termo
        """)
        tipos_contrato = [r['tipo_termo'] for r in cur.fetchall()]
        
        # Buscar OSCs para filtro (das parcerias)
        cur.execute("""
            SELECT DISTINCT osc 
            FROM public.parcerias 
            WHERE osc IS NOT NULL 
            ORDER BY osc
        """)
        oscs = [r['osc'] for r in cur.fetchall()]
        
        return render_template(
            'gestao_financeira/ultra_liquidacoes.html',
            termos=termos,
            tipos_parcela=tipos_parcela,
            tipos_contrato=tipos_contrato,
            status_disponiveis=status_disponiveis,
            oscs=oscs
        )
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/filtros-dados')
@login_required
def api_filtros_dados():
    """API para obter dados dos filtros (autocomplete)"""
    cur = get_cursor()
    
    try:
        # Buscar termos distintos
        cur.execute("""
            SELECT DISTINCT numero_termo 
            FROM gestao_financeira.ultra_liquidacoes 
            WHERE numero_termo IS NOT NULL 
            ORDER BY numero_termo
        """)
        termos = [r['numero_termo'] for r in cur.fetchall()]
        
        # Buscar OSCs, CNPJs e processos via JOIN com parcerias
        cur.execute("""
            SELECT DISTINCT p.osc, p.cnpj, p.sei_celeb, p.sei_pc, p.tipo_termo
            FROM gestao_financeira.ultra_liquidacoes ul
            LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
            WHERE p.osc IS NOT NULL OR p.cnpj IS NOT NULL 
               OR p.sei_celeb IS NOT NULL OR p.sei_pc IS NOT NULL
               OR p.tipo_termo IS NOT NULL
        """)
        
        oscs = set()
        cnpjs = set()
        seis_celeb = set()
        seis_pc = set()
        tipos_termo = set()
        
        for r in cur.fetchall():
            if r['osc']:
                oscs.add(r['osc'])
            if r['cnpj']:
                cnpjs.add(r['cnpj'])
            if r['sei_celeb']:
                seis_celeb.add(r['sei_celeb'])
            if r['sei_pc']:
                seis_pc.add(r['sei_pc'])
            if r['tipo_termo']:
                tipos_termo.add(r['tipo_termo'])
        
        return jsonify({
            'success': True,
            'termos': sorted(list(termos)),
            'oscs': sorted(list(oscs)),
            'cnpjs': sorted(list(cnpjs)),
            'tipos_contrato': sorted(list(tipos_termo)),
            'seis_celeb': sorted(list(seis_celeb)),
            'seis_pc': sorted(list(seis_pc))
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/parcelas')
@login_required
def api_listar_parcelas():
    """API para listar parcelas com filtros e paginação"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Parâmetros de filtro
        secao = request.args.get('secao', 'nao_pago')  # nao_pago, encaminhado, pago
        pagina = int(request.args.get('pagina', 1))
        por_pagina = 100
        
        # Filtros adicionais
        filtro_termo = request.args.get('numero_termo', '')
        filtro_tipo = request.args.get('parcela_tipo', '')
        filtro_numero = request.args.get('parcela_numero', '')
        filtro_vigencia_inicial = request.args.get('vigencia_inicial', '')
        filtro_vigencia_final = request.args.get('vigencia_final', '')
        filtro_vig_inicial_mes = request.args.get('vigencia_inicial_mes', '')
        filtro_vig_inicial_ano = request.args.get('vigencia_inicial_ano', '')
        filtro_vig_final_mes = request.args.get('vigencia_final_mes', '')
        filtro_vig_final_ano = request.args.get('vigencia_final_ano', '')
        filtro_data_pagamento = request.args.get('data_pagamento', '')
        filtro_observacoes = request.args.get('observacoes', '')
        filtro_osc = request.args.get('osc', '')
        filtro_cnpj = request.args.get('cnpj', '')
        filtro_sei_celeb = request.args.get('sei_celeb', '')
        filtro_sei_pc = request.args.get('sei_pc', '')
        filtro_status_secundarios = request.args.get('status_secundarios', '')
        filtro_tipo_termo = request.args.get('tipo_termo', '')
        filtro_tipo_pendencia = request.args.get('tipo_pendencia', '')  # sem_cor, amarelo, verde_claro, verde_escuro
        filtro_ano_termino_termo = request.args.get('ano_termino_termo', '')  # Ano de término da PARCERIA
        
        # Filtro padrão: apenas parcelas "Programada" se usuário não especificar
        # Não aplicar filtro de tipo se não for especificado (mostrar todos)
        # Padrão: se não enviar nada, considera "Programada"
        if filtro_tipo is None or filtro_tipo == 'Programada':
            filtro_tipo = 'Programada'
        elif filtro_tipo == '':
            # Usuário selecionou "Todos" explicitamente - não filtrar
            filtro_tipo = None
        
        # Processar filtro de status secundário
        # Se não especificado e for seção "Não Pago", excluir Antigos e Rescisão
        status_sec_lista = []
        if filtro_status_secundarios:
            status_sec_lista = [s.strip() for s in filtro_status_secundarios.split(',') if s.strip()]
        elif secao == 'nao_pago':
            # Padrão para Não Pago: todos exceto Antigos e Rescisão
            status_sec_lista = ['Parcial', 'Integral', 'Glosa', 'Falta Certidão', 
                               'Falta encarte de Prestações', 'Aguardando Alteração', '-']
        
        # Colunas expandidas solicitadas
        mostrar_osc = request.args.get('mostrar_osc', 'false') == 'true'
        mostrar_cnpj = request.args.get('mostrar_cnpj', 'false') == 'true'
        mostrar_projeto = request.args.get('mostrar_projeto', 'false') == 'true'
        mostrar_sei_celeb = request.args.get('mostrar_sei_celeb', 'false') == 'true'
        mostrar_sei_pc = request.args.get('mostrar_sei_pc', 'false') == 'true'
        
        # Inicializar lista de parâmetros
        params = []
        
        # Construir WHERE baseado na seção
        where_secao = []
        
        if secao == 'nao_pago':
            # Aceita variações: 'Nao Pago', 'Não Pago', 'NAO PAGO', etc
            where_secao.append("(ul.parcela_status ILIKE %s OR ul.parcela_status ILIKE %s)")
            params.extend(['%nao pago%', '%não pago%'])
        elif secao == 'encaminhado':
            where_secao.append("ul.parcela_status = %s")
            params.append('Encaminhado para Pagamento')
        elif secao == 'pago':
            # Aceita variações: 'Pago', 'pago', 'PAGO'
            where_secao.append("LOWER(ul.parcela_status) = %s")
            params.append('pago')
        
        # Construir WHERE adicional
        where_filtros = []
        
        if filtro_termo:
            where_filtros.append("ul.numero_termo ILIKE %s")
            params.append(f'%{filtro_termo}%')
        
        # Só aplicar filtro de tipo se não for vazio (vazio = Todos)
        if filtro_tipo:
            where_filtros.append("ul.parcela_tipo = %s")
            params.append(filtro_tipo)
        
        if filtro_numero:
            where_filtros.append("ul.parcela_numero ILIKE %s")
            params.append(f'%{filtro_numero}%')
        
        if filtro_vigencia_inicial:
            data = parse_data_br(filtro_vigencia_inicial)
            if data:
                where_filtros.append("ul.vigencia_inicial = %s")
                params.append(data)
        
        # Filtro por mês/ano de vigência inicial
        if filtro_vig_inicial_mes and filtro_vig_inicial_ano:
            where_filtros.append("EXTRACT(MONTH FROM ul.vigencia_inicial) = %s AND EXTRACT(YEAR FROM ul.vigencia_inicial) = %s")
            params.extend([int(filtro_vig_inicial_mes), int(filtro_vig_inicial_ano)])
        elif filtro_vig_inicial_mes:
            where_filtros.append("EXTRACT(MONTH FROM ul.vigencia_inicial) = %s")
            params.append(int(filtro_vig_inicial_mes))
        elif filtro_vig_inicial_ano:
            where_filtros.append("EXTRACT(YEAR FROM ul.vigencia_inicial) = %s")
            params.append(int(filtro_vig_inicial_ano))
        
        if filtro_vigencia_final:
            data = parse_data_br(filtro_vigencia_final)
            if data:
                where_filtros.append("ul.vigencia_final = %s")
                params.append(data)
        
        # Filtro por mês/ano de vigência final
        if filtro_vig_final_mes and filtro_vig_final_ano:
            where_filtros.append("EXTRACT(MONTH FROM ul.vigencia_final) = %s AND EXTRACT(YEAR FROM ul.vigencia_final) = %s")
            params.extend([int(filtro_vig_final_mes), int(filtro_vig_final_ano)])
        elif filtro_vig_final_mes:
            where_filtros.append("EXTRACT(MONTH FROM ul.vigencia_final) = %s")
            params.append(int(filtro_vig_final_mes))
        elif filtro_vig_final_ano:
            where_filtros.append("EXTRACT(YEAR FROM ul.vigencia_final) = %s")
            params.append(int(filtro_vig_final_ano))
        
        if filtro_data_pagamento:
            data = parse_data_br(filtro_data_pagamento)
            if data:
                where_filtros.append("ul.data_pagamento = %s")
                params.append(data)
        
        if filtro_observacoes:
            where_filtros.append("ul.observacoes ILIKE %s")
            params.append(f'%{filtro_observacoes}%')
        
        if filtro_osc:
            where_filtros.append("p.osc ILIKE %s")
            params.append(f'%{filtro_osc}%')
        
        if filtro_cnpj:
            where_filtros.append("p.cnpj ILIKE %s")
            params.append(f'%{filtro_cnpj}%')
        
        if filtro_sei_celeb:
            where_filtros.append("p.sei_celeb ILIKE %s")
            params.append(f'%{filtro_sei_celeb}%')
        
        if filtro_sei_pc:
            where_filtros.append("p.sei_pc ILIKE %s")
            params.append(f'%{filtro_sei_pc}%')
        
        if filtro_tipo_termo:
            where_filtros.append("p.tipo_termo = %s")
            params.append(filtro_tipo_termo)
        
        # Filtro de ano de término da PARCERIA (data_final da tabela parcerias)
        if filtro_ano_termino_termo:
            where_filtros.append("EXTRACT(YEAR FROM p.final) = %s")
            params.append(int(filtro_ano_termino_termo))
        
        # Filtro de status secundário
        if status_sec_lista:
            # Construir lista de condições para cada status
            status_conditions = []
            for status in status_sec_lista:
                if status == '-':
                    # Para "-", verificar NULL ou vazio ou "-"
                    status_conditions.append("(ul.parcela_status_secundario IS NULL OR ul.parcela_status_secundario = '' OR ul.parcela_status_secundario = '-')")
                else:
                    params.append(status)
                    status_conditions.append("ul.parcela_status_secundario = %s")
            
            if status_conditions:
                where_filtros.append(f"({' OR '.join(status_conditions)})")
        
        # Combinar WHERE
        where_clause = ' AND '.join(where_secao + where_filtros)
        
        # Query principal - usar subquery se filtro de pendência ativo
        if filtro_tipo_pendencia:
            # Subquery para incluir cálculo de pendências
            query = f"""
            SELECT * FROM (
                SELECT 
                    ul.id,
                    ul.vigencia_inicial,
                    ul.vigencia_final,
                    ul.numero_termo,
                    ul.parcela_tipo,
                    ul.parcela_numero,
                    ul.valor_elemento_53_23,
                    ul.valor_elemento_53_24,
                    ul.valor_previsto,
                    ul.valor_subtraido,
                    ul.valor_encaminhado,
                    ul.valor_pago,
                    ul.parcela_status,
                    ul.parcela_status_secundario,
                    ul.data_pagamento,
                    ul.observacoes,
                    p.osc,
                    p.cnpj,
                    p.projeto,
                    p.sei_celeb,
                    p.sei_pc,
                    -- Calcular se tem inconsistência (REGRA 1: elementos vs previsto OU REGRA 2: soma parcelas vs total termo)
                    CASE 
                        WHEN (
                            -- REGRA 1: Elementos não batem com previsto
                            (LOWER(ul.parcela_status) LIKE '%%nao pago%%' OR LOWER(ul.parcela_status) LIKE '%%não pago%%' OR LOWER(ul.parcela_status) = 'encaminhado para pagamento')
                            AND ABS((COALESCE(ul.valor_elemento_53_23, 0) + COALESCE(ul.valor_elemento_53_24, 0)) - COALESCE(ul.valor_previsto, 0)) > 0.01
                        ) OR (
                            -- REGRA 2: Soma das parcelas programadas do termo ≠ total previsto do termo
                            validacao.tem_divergencia = true
                        )
                        THEN true
                        ELSE false
                    END as tem_inconsistencia,
                    -- Calcular se necessita pagamento (prazo crítico - 5 dias)
                    CASE 
                        WHEN (LOWER(ul.parcela_status) LIKE '%%nao pago%%' OR LOWER(ul.parcela_status) LIKE '%%não pago%%')
                             AND ul.vigencia_inicial < (CURRENT_DATE - INTERVAL '5 days')
                        THEN true
                        ELSE false
                    END as necessita_regularizacao,
                    -- Calcular se empenho cobre valor (placeholder - ajustar se tiver lógica real)
                    false as empenho_cobre
                FROM gestao_financeira.ultra_liquidacoes ul
                LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
                LEFT JOIN (
                    -- Subquery para calcular divergências por termo
                    SELECT 
                        ul2.numero_termo,
                        CASE 
                            WHEN ABS(SUM(COALESCE(ul2.valor_previsto, 0)) - COALESCE(MAX(p2.total_previsto), 0)) > 0.01
                            THEN true
                            ELSE false
                        END as tem_divergencia
                    FROM gestao_financeira.ultra_liquidacoes ul2
                    LEFT JOIN public.parcerias p2 ON p2.numero_termo = ul2.numero_termo
                    WHERE ul2.parcela_tipo = 'Programada'
                    GROUP BY ul2.numero_termo
                ) validacao ON validacao.numero_termo = ul.numero_termo
                WHERE {where_clause}
            ) subq
            WHERE 
                ('{filtro_tipo_pendencia}' = 'amarelo' AND subq.tem_inconsistencia = true)
                OR ('{filtro_tipo_pendencia}' = 'verde_claro' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = true)
                OR ('{filtro_tipo_pendencia}' = 'verde_escuro' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = false AND subq.empenho_cobre = true)
                OR ('{filtro_tipo_pendencia}' = 'sem_cor' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = false AND subq.empenho_cobre = false)
            ORDER BY 
                -- Ano atual primeiro
                CASE WHEN EXTRACT(YEAR FROM subq.vigencia_inicial) = EXTRACT(YEAR FROM CURRENT_DATE) THEN 0 ELSE 1 END ASC,
                -- Pendências primeiro
                CASE 
                    WHEN subq.tem_inconsistencia = true THEN 0
                    ELSE 1
                END ASC,
                -- Ordem padrão
                subq.vigencia_inicial ASC, 
                subq.numero_termo ASC
            """
        else:
            query = f"""
            SELECT 
                ul.id,
                ul.vigencia_inicial,
                ul.vigencia_final,
                ul.numero_termo,
                ul.parcela_tipo,
                ul.parcela_numero,
                ul.valor_elemento_53_23,
                ul.valor_elemento_53_24,
                ul.valor_previsto,
                ul.valor_subtraido,
                ul.valor_encaminhado,
                ul.valor_pago,
                ul.parcela_status,
                ul.parcela_status_secundario,
                ul.data_pagamento,
                ul.observacoes,
                p.osc,
                p.cnpj,
                p.projeto,
                p.sei_celeb,
                p.sei_pc
            FROM gestao_financeira.ultra_liquidacoes ul
            LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
            WHERE {where_clause}
            ORDER BY 
                -- Ano atual primeiro
                CASE WHEN EXTRACT(YEAR FROM ul.vigencia_inicial) = EXTRACT(YEAR FROM CURRENT_DATE) THEN 0 ELSE 1 END ASC,
                -- Pendências primeiro (apenas para Não Pago e Encaminhado)
                CASE 
                    WHEN ul.parcela_status IN ('Não Pago', 'Nao Pago', 'Encaminhado para Pagamento')
                         AND (COALESCE(ul.valor_elemento_53_23, 0) + COALESCE(ul.valor_elemento_53_24, 0) != COALESCE(ul.valor_previsto, 0))
                    THEN 0
                    ELSE 1
                END ASC,
                -- Para Não Pago: priorizar status secundário null/- do ano atual
                CASE 
                    WHEN ul.parcela_status IN ('Não Pago', 'Nao Pago')
                         AND (ul.parcela_status_secundario IS NULL OR ul.parcela_status_secundario = '-' OR ul.parcela_status_secundario = '')
                         AND EXTRACT(YEAR FROM ul.vigencia_inicial) = EXTRACT(YEAR FROM CURRENT_DATE)
                    THEN 0
                    ELSE 1
                END ASC,
                -- Para Pago: ordenar por data DESC
                CASE WHEN LOWER(ul.parcela_status) = 'pago' THEN ul.data_pagamento END DESC NULLS LAST,
                -- Ordem padrão
                ul.vigencia_inicial ASC, 
                ul.numero_termo ASC
            """
        
        # Adicionar LIMIT e OFFSET
        query += " LIMIT %s OFFSET %s"
        params.extend([por_pagina, (pagina - 1) * por_pagina])
        
        cur.execute(query, params)
        parcelas = cur.fetchall()
        
        # Contar total
        if filtro_tipo_pendencia:
            query_count = f"""
            SELECT COUNT(*) as total FROM (
                SELECT ul.id,
                    CASE 
                        WHEN (
                            -- REGRA 1: Elementos não batem com previsto
                            (LOWER(ul.parcela_status) LIKE '%%nao pago%%' OR LOWER(ul.parcela_status) LIKE '%%não pago%%' OR LOWER(ul.parcela_status) = 'encaminhado para pagamento')
                            AND ABS((COALESCE(ul.valor_elemento_53_23, 0) + COALESCE(ul.valor_elemento_53_24, 0)) - COALESCE(ul.valor_previsto, 0)) > 0.01
                        ) OR (
                            -- REGRA 2: Soma das parcelas programadas do termo ≠ total previsto do termo
                            validacao.tem_divergencia = true
                        )
                        THEN true
                        ELSE false
                    END as tem_inconsistencia,
                    CASE 
                        WHEN (LOWER(ul.parcela_status) LIKE '%%nao pago%%' OR LOWER(ul.parcela_status) LIKE '%%não pago%%')
                             AND ul.vigencia_inicial < (CURRENT_DATE - INTERVAL '5 days')
                        THEN true
                        ELSE false
                    END as necessita_regularizacao,
                    false as empenho_cobre
                FROM gestao_financeira.ultra_liquidacoes ul
                LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
                LEFT JOIN (
                    -- Subquery para calcular divergências por termo
                    SELECT 
                        ul2.numero_termo,
                        CASE 
                            WHEN ABS(SUM(COALESCE(ul2.valor_previsto, 0)) - COALESCE(MAX(p2.total_previsto), 0)) > 0.01
                            THEN true
                            ELSE false
                        END as tem_divergencia
                    FROM gestao_financeira.ultra_liquidacoes ul2
                    LEFT JOIN public.parcerias p2 ON p2.numero_termo = ul2.numero_termo
                    WHERE ul2.parcela_tipo = 'Programada'
                    GROUP BY ul2.numero_termo
                ) validacao ON validacao.numero_termo = ul.numero_termo
                WHERE {where_clause}
            ) subq
            WHERE 
                ('{filtro_tipo_pendencia}' = 'amarelo' AND subq.tem_inconsistencia = true)
                OR ('{filtro_tipo_pendencia}' = 'verde_claro' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = true)
                OR ('{filtro_tipo_pendencia}' = 'verde_escuro' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = false AND subq.empenho_cobre = true)
                OR ('{filtro_tipo_pendencia}' = 'sem_cor' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = false AND subq.empenho_cobre = false)
            """
            cur.execute(query_count, params[:-2])  # Sem LIMIT/OFFSET
        else:
            query_count = f"""
                SELECT COUNT(*) as total
                FROM gestao_financeira.ultra_liquidacoes ul
                LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
                WHERE {where_clause}
            """
            cur.execute(query_count, params[:-2])  # Sem LIMIT/OFFSET
        total = cur.fetchone()['total']
        
        # Formatar resultado
        resultado = []
        from datetime import datetime, timedelta
        import calendar
        
        hoje = datetime.now().date()
        
        # Calcular soma de valores previstos por termo para validação
        # Apenas para parcelas Programadas (NÃO Projetadas)
        cur.execute("""
            SELECT ul.numero_termo, 
                   SUM(COALESCE(ul.valor_previsto, 0)) as soma_previsto_parcelas,
                   p.total_previsto
            FROM gestao_financeira.ultra_liquidacoes ul
            LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
            WHERE ul.parcela_tipo = 'Programada'
            GROUP BY ul.numero_termo, p.total_previsto
        """)
        validacao_termos = {r['numero_termo']: {
            'soma_parcelas': float(r['soma_previsto_parcelas'] or 0),
            'total_termo': float(r['total_previsto'] or 0)
        } for r in cur.fetchall()}
        
        # Calcular empenhos disponíveis por termo/ano
        # USAR CURSOR SEPARADO para evitar quebrar a transação
        cur_empenhos = get_cursor()
        try:
            empenhos_disponiveis, pagos_por_elemento, avisos_empenhos = calcular_empenhos_disponiveis(cur_empenhos, hoje)
        finally:
            cur_empenhos.close()
        
        # Salvar avisos no session para o relatório DEBUG (última execução)
        session['debug_avisos_empenhos'] = avisos_empenhos
        
        # Criar mapeamento termo → sei_celeb para buscar empenhos depois
        # (evitar query dentro do loop)
        cur.execute("""
            SELECT numero_termo, sei_celeb
            FROM public.parcerias
            WHERE sei_celeb IS NOT NULL AND sei_celeb != ''
        """)
        termo_para_sei = {r['numero_termo']: r['sei_celeb'] for r in cur.fetchall()}
        
        for p in parcelas:
            # Calcular pendências
            pendencias = []
            valor_23 = float(p['valor_elemento_53_23'] or 0)
            valor_24 = float(p['valor_elemento_53_24'] or 0)
            valor_previsto = float(p['valor_previsto'] or 0)
            
            # Regra de pendência: elementos não batem com previsto
            status_lower = (p['parcela_status'] or '').lower()
            if 'nao pago' in status_lower or 'não pago' in status_lower or 'encaminhado' in status_lower:
                if abs((valor_23 + valor_24) - valor_previsto) > 0.01:
                    pendencias.append('Elementos 53/23+24 ≠ Previsto')
            
            # Regra de pendência: Soma de parcelas ≠ Total previsto do termo
            numero_termo = p['numero_termo']
            if numero_termo in validacao_termos:
                validacao = validacao_termos[numero_termo]
                if abs(validacao['soma_parcelas'] - validacao['total_termo']) > 0.01:
                    pendencias.append(f"Soma das parcelas (R$ {validacao['soma_parcelas']:,.2f}) ≠ Total do termo (R$ {validacao['total_termo']:,.2f})")
            
            # Regra VERDE CLARO: Necessita pagamento (prazo crítico - 5 dias)
            # Regra VERDE ESCURO: Empenho cobre o valor previsto
            necessita_pagamento = False
            empenho_cobre_valor = False
            detalhes_empenhos = []
            
            if len(pendencias) == 0:  # Só marca como verde se NÃO tem inconsistências (amarelo)
                if 'nao pago' in status_lower or 'não pago' in status_lower:
                    # Buscar empenhos disponíveis
                    vigencia_inicial = p['vigencia_inicial']
                    if vigencia_inicial:
                        ano_parcela = vigencia_inicial.year
                        
                        # Usar mapeamento pré-carregado (sem query adicional)
                        sei_celeb = termo_para_sei.get(numero_termo)
                        cod_sof = None
                        chave = None
                        
                        if sei_celeb:
                            cod_sof = converter_sei_para_cod_sof(sei_celeb)
                            chave = (cod_sof, ano_parcela)
                            detalhes_empenhos = empenhos_disponiveis.get(chave, [])
                        
                        # Calcular total disponível
                        total_disponivel = sum(emp['disponivel'] for emp in detalhes_empenhos)
                        
                        # VERDE ESCURO: empenho disponível >= valor previsto
                        if total_disponivel >= valor_previsto:
                            empenho_cobre_valor = True
                        
                        # VERDE CLARO: prazo crítico (apenas se não tem empenho cobrindo)
                        if not empenho_cobre_valor:
                            data_limite = hoje - timedelta(days=5)
                            if vigencia_inicial < data_limite:
                                necessita_pagamento = True
            
            resultado.append({
                'id': p['id'],
                'vigencia_inicial': formatar_data_mes_ano(p['vigencia_inicial']),
                'vigencia_final': formatar_data_mes_ano(p['vigencia_final']),
                'vigencia_inicial_raw': p['vigencia_inicial'],  # Para ordenação em cascata
                'numero_termo': p['numero_termo'],
                'parcela_tipo': p['parcela_tipo'] or '',
                'parcela_numero': p['parcela_numero'] or '',
                'valor_elemento_53_23': valor_23,
                'valor_elemento_53_24': valor_24,
                'valor_previsto': valor_previsto,
                'valor_subtraido': float(p['valor_subtraido'] or 0),
                'valor_encaminhado': float(p['valor_encaminhado'] or 0),
                'valor_pago': float(p['valor_pago'] or 0),
                'parcela_status': p['parcela_status'] or '',
                'parcela_status_secundario': p['parcela_status_secundario'] or '',
                'data_pagamento': formatar_data_br(p['data_pagamento']),
                'observacoes': p['observacoes'] or '',
                'osc': p['osc'] or '' if mostrar_osc else None,
                'cnpj': p['cnpj'] or '' if mostrar_cnpj else None,
                'projeto': p['projeto'] or '' if mostrar_projeto else None,
                'sei_celeb': p['sei_celeb'] or '' if mostrar_sei_celeb else None,
                'sei_pc': p['sei_pc'] or '' if mostrar_sei_pc else None,
                'pendencias': pendencias,
                'pendencias_descricao': ' | '.join(pendencias) if pendencias else '',
                'tem_pendencia': len(pendencias) > 0,
                'necessita_pagamento': necessita_pagamento,
                'empenho_cobre_valor': empenho_cobre_valor,
                'pago_integral': False,  # Será calculado em cascata
                'pago_parcial': False,   # Será calculado em cascata
                'valor_pago_23': 0,      # Será calculado em cascata
                'valor_pago_24': 0,      # Será calculado em cascata
                'detalhes_empenhos': detalhes_empenhos
            })
        
        # ========================================================================
        # DISTRIBUIÇÃO EM CASCATA: Valores pagos para parcelas "Encaminhado"
        # ========================================================================
        # Separar parcelas "Encaminhado para Pagamento" e ordenar por vigência
        parcelas_encaminhadas = [r for r in resultado if r['parcela_status'] == 'Encaminhado para Pagamento']
        parcelas_encaminhadas.sort(key=lambda x: x['vigencia_inicial_raw'] if x['vigencia_inicial_raw'] else datetime(2099, 1, 1).date())
        
        # Agrupar por (termo, ano) para distribuir valores pagos
        from collections import defaultdict
        controle_cascata = defaultdict(lambda: {'pago_23': 0, 'pago_24': 0})
        
        for parcela in parcelas_encaminhadas:
            if parcela['tem_pendencia']:
                continue  # Pular parcelas com inconsistências (amarelo tem prioridade)
            
            vigencia_raw = parcela['vigencia_inicial_raw']
            if not vigencia_raw:
                continue
            
            ano_parcela = vigencia_raw.year
            sei_celeb = termo_para_sei.get(parcela['numero_termo'])
            
            if not sei_celeb:
                continue
            
            cod_sof = converter_sei_para_cod_sof(sei_celeb)
            
            # Buscar total pago por elemento neste ano
            chave_elemento_23 = (cod_sof, ano_parcela, '23')
            chave_elemento_24 = (cod_sof, ano_parcela, '24')
            
            total_pago_23 = pagos_por_elemento.get(chave_elemento_23, 0)
            total_pago_24 = pagos_por_elemento.get(chave_elemento_24, 0)
            
            # Chave para controle de cascata (por termo+ano)
            chave_controle = (parcela['numero_termo'], ano_parcela)
            
            # Distribuir elemento 23
            if total_pago_23 > 0:
                ja_distribuido_23 = controle_cascata[chave_controle]['pago_23']
                restante_23 = total_pago_23 - ja_distribuido_23
                
                if restante_23 > 0:
                    valor_elemento_23 = parcela['valor_elemento_53_23']
                    valor_a_distribuir_23 = min(restante_23, valor_elemento_23)
                    
                    parcela['valor_pago_23'] = valor_a_distribuir_23
                    controle_cascata[chave_controle]['pago_23'] += valor_a_distribuir_23
            
            # Distribuir elemento 24
            if total_pago_24 > 0:
                ja_distribuido_24 = controle_cascata[chave_controle]['pago_24']
                restante_24 = total_pago_24 - ja_distribuido_24
                
                if restante_24 > 0:
                    valor_elemento_24 = parcela['valor_elemento_53_24']
                    valor_a_distribuir_24 = min(restante_24, valor_elemento_24)
                    
                    parcela['valor_pago_24'] = valor_a_distribuir_24
                    controle_cascata[chave_controle]['pago_24'] += valor_a_distribuir_24
            
            # Determinar status: PAGO INTEGRAL ou PAGO PARCIAL
            valor_pago_total = parcela['valor_pago_23'] + parcela['valor_pago_24']
            valor_elemento_total = parcela['valor_elemento_53_23'] + parcela['valor_elemento_53_24']
            
            if valor_pago_total > 0:
                if valor_pago_total >= valor_elemento_total - 0.01:  # Tolerância de 1 centavo
                    parcela['pago_integral'] = True
                else:
                    parcela['pago_parcial'] = True
        
        # ========================================================================
        
        # Filtrar por tipo de pendência se solicitado
        # (Removido - tipo_pendencia não existe mais)
        
        # Contar pendências por seção
        total_pendencias = sum(1 for r in resultado if r['tem_pendencia'])
        total_necessita_pagamento = sum(1 for r in resultado if r['necessita_pagamento'])
        total_empenho_cobre = sum(1 for r in resultado if r['empenho_cobre_valor'])
        total_pago_integral = sum(1 for r in resultado if r.get('pago_integral', False))
        total_pago_parcial = sum(1 for r in resultado if r.get('pago_parcial', False))
        
        return jsonify({
            'success': True,
            'data': resultado,
            'total': total,
            'pagina': pagina,
            'por_pagina': por_pagina,
            'total_paginas': (total + por_pagina - 1) // por_pagina,
            'total_pendencias': total_pendencias,
            'total_necessita_pagamento': total_necessita_pagamento,
            'total_empenho_cobre': total_empenho_cobre,
            'total_pago_integral': total_pago_integral,
            'total_pago_parcial': total_pago_parcial
        })
    
    except Exception as e:
        import traceback
        print(f"\n{'='*60}")
        print(f"ERRO em api_listar_parcelas:")
        print(f"Seção: {secao}")
        print(f"Página: {pagina}")
        print(f"Erro: {str(e)}")
        print(f"Tipo: {type(e).__name__}")
        print(f"\nTraceback completo:")
        traceback.print_exc()
        print(f"{'='*60}\n")
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/parcela/<int:parcela_id>')
@login_required
def api_obter_parcela(parcela_id):
    """API para obter dados de uma parcela específica"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        cur.execute("""
            SELECT 
                ul.*,
                p.osc,
                p.cnpj,
                p.sei_celeb,
                p.sei_pc,
                p.inicio,
                p.final
            FROM gestao_financeira.ultra_liquidacoes ul
            LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
            WHERE ul.id = %s
        """, (parcela_id,))
        
        parcela = cur.fetchone()
        
        if not parcela:
            return jsonify({'success': False, 'error': 'Parcela não encontrada'}), 404
        
        # Buscar tipos de parcela disponíveis
        cur.execute("""
            SELECT parcela_tipo 
            FROM categoricas.c_dac_tipos_parcelas 
            ORDER BY parcela_tipo
        """)
        tipos_parcela = [r['parcela_tipo'] for r in cur.fetchall()]
        
        resultado = {
            'id': parcela['id'],
            'vigencia_inicial': formatar_data_br(parcela['vigencia_inicial']),
            'vigencia_final': formatar_data_br(parcela['vigencia_final']),
            'numero_termo': parcela['numero_termo'],
            'parcela_tipo': parcela['parcela_tipo'] or '',
            'parcela_numero': parcela['parcela_numero'] or '',
            'valor_elemento_53_23': float(parcela['valor_elemento_53_23'] or 0),
            'valor_elemento_53_24': float(parcela['valor_elemento_53_24'] or 0),
            'valor_previsto': float(parcela['valor_previsto'] or 0),
            'valor_subtraido': float(parcela['valor_subtraido'] or 0),
            'valor_encaminhado': float(parcela['valor_encaminhado'] or 0),
            'valor_pago': float(parcela['valor_pago'] or 0),
            'parcela_status': parcela['parcela_status'] or '',
            'data_pagamento': formatar_data_br(parcela['data_pagamento']),
            'observacoes': parcela['observacoes'] or '',
            'parcela_status_secundario': parcela['parcela_status_secundario'] or '',
            'osc': parcela['osc'] or '',
            'cnpj': parcela['cnpj'] or '',
            'sei_celeb': parcela['sei_celeb'] or '',
            'sei_pc': parcela['sei_pc'] or '',
            'inicio_parceria': formatar_data_br(parcela['inicio']),
            'final_parceria': formatar_data_br(parcela['final']),
            'tipos_parcela_disponiveis': tipos_parcela
        }
        
        return jsonify({'success': True, 'data': resultado})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/parcela/<int:parcela_id>', methods=['PUT'])
@login_required
def api_atualizar_parcela(parcela_id):
    """API para atualizar uma parcela"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        dados = request.get_json()
        print(f"[DEBUG] Atualizando parcela ID: {parcela_id}")
        print(f"[DEBUG] Dados recebidos: {dados}")
        
        # Parse de datas
        vigencia_inicial = parse_data_br(dados.get('vigencia_inicial'))
        vigencia_final = parse_data_br(dados.get('vigencia_final'))
        data_pagamento = parse_data_br(dados.get('data_pagamento'))
        
        # Parse de valores numéricos
        valor_elemento_53_23 = Decimal(str(dados.get('valor_elemento_53_23', 0)))
        valor_elemento_53_24 = Decimal(str(dados.get('valor_elemento_53_24', 0)))
        valor_previsto = Decimal(str(dados.get('valor_previsto', 0)))
        valor_subtraido = Decimal(str(dados.get('valor_subtraido', 0)))
        valor_encaminhado = Decimal(str(dados.get('valor_encaminhado', 0)))
        valor_pago = Decimal(str(dados.get('valor_pago', 0)))
        
        # Campos texto
        parcela_tipo = dados.get('parcela_tipo', '')
        parcela_numero = dados.get('parcela_numero', '')
        parcela_status = dados.get('parcela_status', '')
        parcela_status_secundario = dados.get('parcela_status_secundario', '')
        observacoes = dados.get('observacoes', '')
        
        usuario = session.get('usuario_nome', 'Sistema')
        
        # Update
        cur.execute("""
            UPDATE gestao_financeira.ultra_liquidacoes
            SET 
                vigencia_inicial = %s,
                vigencia_final = %s,
                parcela_tipo = %s,
                parcela_numero = %s,
                valor_elemento_53_23 = %s,
                valor_elemento_53_24 = %s,
                valor_previsto = %s,
                valor_subtraido = %s,
                valor_encaminhado = %s,
                valor_pago = %s,
                parcela_status = %s,
                parcela_status_secundario = %s,
                data_pagamento = %s,
                observacoes = %s,
                atualizado_por = %s,
                atualizado_em = NOW()
            WHERE id = %s
        """, (
            vigencia_inicial,
            vigencia_final,
            parcela_tipo,
            parcela_numero,
            valor_elemento_53_23,
            valor_elemento_53_24,
            valor_previsto,
            valor_subtraido,
            valor_encaminhado,
            valor_pago,
            parcela_status,
            parcela_status_secundario,
            data_pagamento,
            observacoes,
            usuario,
            parcela_id
        ))
        
        linhas_afetadas = cur.rowcount
        print(f"[DEBUG] Linhas afetadas: {linhas_afetadas}")
        
        conn.commit()
        print(f"[DEBUG] Commit realizado com sucesso")
        
        return jsonify({'success': True, 'message': 'Parcela atualizada com sucesso'})
    
    except Exception as e:
        print(f"[ERRO] Erro ao atualizar parcela: {str(e)}")
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/parcela/<int:parcela_id>', methods=['DELETE'])
@login_required
def api_excluir_parcela(parcela_id):
    """API para excluir uma parcela"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        cur.execute("""
            DELETE FROM gestao_financeira.ultra_liquidacoes
            WHERE id = %s
        """, (parcela_id,))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Parcela excluída com sucesso'})
    
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/exportar-csv')
@login_required
def api_exportar_csv():
    """API para exportar dados em CSV"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        modo = request.args.get('modo', 'tudo')  # tudo, secao, filtrado
        secao = request.args.get('secao', 'nao_pago')
        
        # Mesma lógica de filtros da listagem
        where_clause = "1=1"
        params = []
        
        if modo == 'secao' or modo == 'filtrado':
            if secao == 'nao_pago':
                where_clause = "ul.parcela_status = 'Não Pago'"
            elif secao == 'encaminhado':
                where_clause = "ul.parcela_status = 'Encaminhado para Pagamento'"
            elif secao == 'pago':
                where_clause = "ul.parcela_status = 'Pago'"
        
        if modo == 'filtrado':
            # Aplicar filtros adicionais (mesma lógica da API de listagem)
            pass  # TODO: implementar filtros se necessário
        
        query = f"""
            SELECT 
                ul.vigencia_inicial,
                ul.vigencia_final,
                ul.numero_termo,
                ul.parcela_tipo,
                ul.parcela_numero,
                ul.valor_elemento_53_23,
                ul.valor_elemento_53_24,
                ul.valor_previsto,
                ul.valor_subtraido,
                ul.valor_encaminhado,
                ul.valor_pago,
                ul.parcela_status,
                ul.parcela_status_secundario,
                ul.data_pagamento,
                ul.observacoes,
                p.osc,
                p.cnpj,
                p.sei_celeb,
                p.sei_pc
            FROM gestao_financeira.ultra_liquidacoes ul
            LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
            WHERE {where_clause}
            ORDER BY ul.vigencia_inicial ASC
        """
        
        cur.execute(query, params)
        parcelas = cur.fetchall()
        
        # Criar CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Cabeçalho
        writer.writerow([
            'Vigência Inicial', 'Vigência Final', 'Número do Termo',
            'Tipo Parcela', 'Número Parcela', 
            'Valor Elemento 53/23', 'Valor Elemento 53/24', 'Valor Previsto',
            'Valor Subtraído', 'Valor Encaminhado', 'Valor Pago',
            'Status', 'Status Secundário', 'Data Pagamento', 'Observações',
            'OSC', 'CNPJ', 'Processo Celebração', 'Processo PGTO/PC'
        ])
        
        # Dados
        for p in parcelas:
            writer.writerow([
                formatar_data_br(p['vigencia_inicial']),
                formatar_data_br(p['vigencia_final']),
                p['numero_termo'],
                p['parcela_tipo'] or '',
                p['parcela_numero'] or '',
                formatar_moeda_br(p['valor_elemento_53_23']),
                formatar_moeda_br(p['valor_elemento_53_24']),
                formatar_moeda_br(p['valor_previsto']),
                formatar_moeda_br(p['valor_subtraido']),
                formatar_moeda_br(p['valor_encaminhado']),
                formatar_moeda_br(p['valor_pago']),
                p['parcela_status'] or '',
                p['parcela_status_secundario'] or '',
                formatar_data_br(p['data_pagamento']),
                p['observacoes'] or '',
                p['osc'] or '',
                p['cnpj'] or '',
                p['sei_celeb'] or '',
                p['sei_pc'] or ''
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=ultra_liquidacoes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/termo-info/<path:numero_termo>')
@login_required
def get_termo_info(numero_termo):
    """Retorna informações sobre um termo (total de parcelas)"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        cur.execute("""
            SELECT COUNT(*) as total
            FROM gestao_financeira.ultra_liquidacoes
            WHERE numero_termo = %s
        """, [numero_termo])
        
        result = cur.fetchone()
        
        return jsonify({
            'success': True,
            'total': result['total']
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/termo/<path:numero_termo>/atualizar-coletivo', methods=['PUT'])
@login_required
def atualizar_termo_coletivo(numero_termo):
    """Atualiza todas as parcelas de um termo de uma vez (edição coletiva)"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        dados = request.get_json()
        
        if not dados or len(dados) == 0:
            return jsonify({'success': False, 'error': 'Nenhum campo para atualizar'}), 400
        
        # Construir query dinâmica apenas com campos fornecidos
        campos_update = []
        valores = []
        
        # Mapear campos do frontend para o banco
        campos_mapeamento = {
            'parcela_tipo': 'parcela_tipo',
            'vigencia_inicial': 'vigencia_inicial',
            'vigencia_final': 'vigencia_final',
            'valor_elemento_53_23': 'valor_elemento_53_23',
            'valor_elemento_53_24': 'valor_elemento_53_24',
            'valor_previsto': 'valor_previsto',
            'valor_subtraido': 'valor_subtraido',
            'valor_encaminhado': 'valor_encaminhado',
            'valor_pago': 'valor_pago',
            'parcela_status': 'parcela_status',
            'parcela_status_secundario': 'parcela_status_secundario',
            'data_pagamento': 'data_pagamento'
        }
        
        for campo_front, campo_db in campos_mapeamento.items():
            if campo_front in dados:
                valor = dados[campo_front]
                
                # Converter datas
                if campo_front in ['vigencia_inicial', 'vigencia_final', 'data_pagamento']:
                    if valor:
                        valor = parse_data_br(valor)
                
                # Converter valores numéricos
                if campo_front.startswith('valor_'):
                    if valor:
                        valor = Decimal(str(valor))
                    else:
                        valor = None
                
                # Status secundário vazio vira NULL
                if campo_front == 'parcela_status_secundario' and valor == '':
                    valor = None
                
                campos_update.append(f"{campo_db} = %s")
                valores.append(valor)
        
        if not campos_update:
            return jsonify({'success': False, 'error': 'Nenhum campo válido fornecido'}), 400
        
        # Adicionar numero_termo ao final dos parâmetros
        valores.append(numero_termo)
        
        # Executar UPDATE
        query = f"""
            UPDATE gestao_financeira.ultra_liquidacoes
            SET {', '.join(campos_update)}
            WHERE numero_termo = %s
        """
        
        cur.execute(query, valores)
        parcelas_atualizadas = cur.rowcount
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'{parcelas_atualizadas} parcelas atualizadas',
            'parcelas_atualizadas': parcelas_atualizadas
        })
    
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/termo/<path:numero_termo>/parcelas')
@login_required
def get_parcelas_termo(numero_termo):
    """Retorna todas as parcelas de um termo para edição coletiva"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Buscar todas as parcelas do termo
        cur.execute("""
            SELECT 
                id,
                vigencia_inicial,
                vigencia_final,
                parcela_tipo,
                parcela_numero,
                valor_elemento_53_23,
                valor_elemento_53_24,
                valor_previsto,
                valor_subtraido,
                valor_encaminhado,
                valor_pago,
                parcela_status,
                parcela_status_secundario,
                data_pagamento
            FROM gestao_financeira.ultra_liquidacoes
            WHERE numero_termo = %s
            ORDER BY vigencia_inicial, parcela_numero
        """, [numero_termo])
        
        parcelas = []
        for row in cur.fetchall():
            parcelas.append({
                'id': row['id'],
                'vigencia_inicial': formatar_data_br(row['vigencia_inicial']),
                'vigencia_final': formatar_data_br(row['vigencia_final']),
                'parcela_tipo': row['parcela_tipo'],
                'parcela_numero': row['parcela_numero'],
                'valor_elemento_53_23': float(row['valor_elemento_53_23']) if row['valor_elemento_53_23'] else None,
                'valor_elemento_53_24': float(row['valor_elemento_53_24']) if row['valor_elemento_53_24'] else None,
                'valor_previsto': float(row['valor_previsto']) if row['valor_previsto'] else None,
                'valor_subtraido': float(row['valor_subtraido']) if row['valor_subtraido'] else None,
                'valor_encaminhado': float(row['valor_encaminhado']) if row['valor_encaminhado'] else None,
                'valor_pago': float(row['valor_pago']) if row['valor_pago'] else None,
                'parcela_status': row['parcela_status'],
                'parcela_status_secundario': row['parcela_status_secundario'],
                'data_pagamento': formatar_data_br(row['data_pagamento'])
            })
        
        # Buscar tipos de parcela disponíveis
        cur.execute("""
            SELECT DISTINCT parcela_tipo 
            FROM categoricas.c_dac_tipos_parcelas 
            ORDER BY parcela_tipo
        """)
        tipos_parcela = [r['parcela_tipo'] for r in cur.fetchall()]
        
        return jsonify({
            'success': True,
            'parcelas': parcelas,
            'tipos_parcela': tipos_parcela
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/termo/<path:numero_termo>/atualizar-multiplas', methods=['PUT'])
@login_required
def atualizar_multiplas_parcelas(numero_termo):
    """Atualiza múltiplas parcelas de um termo (edição em tabela)"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        dados = request.get_json()
        parcelas = dados.get('parcelas', [])
        
        if not parcelas:
            return jsonify({'success': False, 'error': 'Nenhuma parcela fornecida'}), 400
        
        parcelas_atualizadas = 0
        
        for parcela in parcelas:
            parcela_id = parcela.get('id')
            
            if not parcela_id:
                continue
            
            # Construir UPDATE dinâmico
            campos_update = []
            valores = []
            
            if parcela.get('vigencia_inicial'):
                campos_update.append('vigencia_inicial = %s')
                valores.append(parse_data_br(parcela['vigencia_inicial']))
            
            if parcela.get('vigencia_final'):
                campos_update.append('vigencia_final = %s')
                valores.append(parse_data_br(parcela['vigencia_final']))
            
            if parcela.get('parcela_tipo'):
                campos_update.append('parcela_tipo = %s')
                valores.append(parcela['parcela_tipo'])
            
            if 'parcela_numero' in parcela:
                campos_update.append('parcela_numero = %s')
                valores.append(parcela['parcela_numero'])
            
            # Valores monetários
            for campo in ['valor_elemento_53_23', 'valor_elemento_53_24', 'valor_previsto', 
                         'valor_subtraido', 'valor_encaminhado', 'valor_pago']:
                if campo in parcela:
                    valor = parcela[campo]
                    campos_update.append(f'{campo} = %s')
                    valores.append(Decimal(str(valor)) if valor else None)
            
            if parcela.get('parcela_status'):
                campos_update.append('parcela_status = %s')
                valores.append(parcela['parcela_status'])
            
            if 'parcela_status_secundario' in parcela:
                campos_update.append('parcela_status_secundario = %s')
                valores.append(parcela['parcela_status_secundario'] if parcela['parcela_status_secundario'] else None)
            
            if 'data_pagamento' in parcela:
                campos_update.append('data_pagamento = %s')
                valores.append(parse_data_br(parcela['data_pagamento']) if parcela['data_pagamento'] else None)
            
            if campos_update:
                valores.append(parcela_id)
                query = f"UPDATE gestao_financeira.ultra_liquidacoes SET {', '.join(campos_update)} WHERE id = %s"
                cur.execute(query, valores)
                parcelas_atualizadas += cur.rowcount
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'{parcelas_atualizadas} parcelas atualizadas',
            'parcelas_atualizadas': parcelas_atualizadas
        })
    
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/termos-disponiveis')
@login_required
def get_termos_disponiveis():
    """
    Retorna termos de parcerias que:
    1. Ainda não possuem parcelas em ultra_liquidacoes (termos novos)
    2. Possuem prorrogação/meses faltantes (termos prorrogados)
    
    Regras:
    - Data de início (coluna inicio) deve ser posterior a 01/01/2018
    - Comparar vigência em ultra_liquidacoes vs public.parcerias
    - Considerar apenas mês/ano (ignorar dia)
    - Se início/fim < 5 dias do fim do mês, considerar mês seguinte
    """
    conn = get_db()
    cur = get_cursor()
    
    try:
        from datetime import timedelta
        import calendar
        
        # 1. Termos completamente novos (não existem em ultra_liquidacoes)
        cur.execute("""
            SELECT DISTINCT
                p.numero_termo,
                p.osc,
                p.cnpj,
                p.inicio,
                p.final,
                p.tipo_termo,
                p.total_previsto,
                p.edital_nome,
                p.sei_celeb,
                p.sei_pc,
                'novo' as tipo_disponibilidade
            FROM public.parcerias p
            WHERE p.numero_termo NOT IN (
                SELECT DISTINCT numero_termo 
                FROM gestao_financeira.ultra_liquidacoes
            )
            AND p.inicio > '2018-01-01'
            AND p.numero_termo NOT ILIKE '%ACP%'
            AND p.numero_termo NOT ILIKE '%TCC%'
            AND p.numero_termo NOT ILIKE '%TCP%'
            AND p.numero_termo NOT ILIKE '%TCV%'
            AND NOT (
                -- Excluir TFMs que encerraram antes de 2023
                p.numero_termo ILIKE '%TFM%' 
                AND p.final < '2023-01-01'
            )
        """)
        termos_novos = cur.fetchall()
        
        # 2. Termos com prorrogação (existem em ultra_liquidacoes mas faltam MESES)
        # EXCLUIR "Sem Edital (Emenda Parlamentar)" das prorrogações
        # Comparar QUANTIDADE DE MESES (não apenas início/fim)
        # AJUSTE DE COMPETÊNCIA: Se início for dias 27-31, considerar mês seguinte
        cur.execute("""
            WITH vigencias AS (
                SELECT 
                    ul.numero_termo,
                    MIN(ul.vigencia_inicial) as min_vig_ul,
                    MAX(ul.vigencia_final) as max_vig_ul,
                    -- Calcular quantidade de meses preenchidos
                    EXTRACT(YEAR FROM AGE(MAX(ul.vigencia_final), MIN(ul.vigencia_inicial))) * 12 +
                    EXTRACT(MONTH FROM AGE(MAX(ul.vigencia_final), MIN(ul.vigencia_inicial))) + 1 as meses_preenchidos
                FROM gestao_financeira.ultra_liquidacoes ul
                GROUP BY ul.numero_termo
            ),
            datas_ajustadas AS (
                SELECT 
                    p.numero_termo,
                    p.osc,
                    p.cnpj,
                    p.inicio,
                    p.final,
                    p.tipo_termo,
                    p.total_previsto,
                    p.edital_nome,
                    p.sei_celeb,
                    p.sei_pc,
                    -- Ajustar data de início: se dia >= 27, usar primeiro dia do mês seguinte
                    CASE 
                        WHEN EXTRACT(DAY FROM p.inicio) >= 27 THEN 
                            DATE_TRUNC('month', p.inicio + INTERVAL '1 month')::date
                        ELSE 
                            DATE_TRUNC('month', p.inicio)::date
                    END as inicio_ajustado,
                    -- Data final: sempre primeiro dia do mês da data final
                    DATE_TRUNC('month', p.final)::date as final_ajustado
                FROM public.parcerias p
                WHERE p.inicio > '2018-01-01'
                AND p.numero_termo NOT ILIKE '%ACP%'
                AND p.numero_termo NOT ILIKE '%TCC%'
                AND p.numero_termo NOT ILIKE '%TCP%'
                AND p.numero_termo NOT ILIKE '%TCV%'
                AND COALESCE(p.edital_nome, '') != 'Sem Edital (Emenda Parlamentar)'
            )
            SELECT 
                da.numero_termo,
                da.osc,
                da.cnpj,
                da.inicio,
                da.final,
                da.tipo_termo,
                da.total_previsto,
                da.edital_nome,
                da.sei_celeb,
                da.sei_pc,
                v.min_vig_ul,
                v.max_vig_ul,
                v.meses_preenchidos,
                -- Calcular meses usando datas ajustadas (competência)
                EXTRACT(YEAR FROM AGE(da.final_ajustado, da.inicio_ajustado)) * 12 +
                EXTRACT(MONTH FROM AGE(da.final_ajustado, da.inicio_ajustado)) + 1 as meses_parceria,
                'prorrogacao' as tipo_disponibilidade
            FROM datas_ajustadas da
            INNER JOIN vigencias v ON v.numero_termo = da.numero_termo
            WHERE (
                -- Tolerância de ±1 mês: só prorrogação se diferença > 1 mês
                v.meses_preenchidos < (
                    EXTRACT(YEAR FROM AGE(da.final_ajustado, da.inicio_ajustado)) * 12 + 
                    EXTRACT(MONTH FROM AGE(da.final_ajustado, da.inicio_ajustado)) + 1
                ) - 1
            )
            AND NOT (
                -- Excluir TFMs que encerraram antes de 2023
                da.numero_termo ILIKE '%TFM%' 
                AND da.final < '2023-01-01'
            )
        """)
        termos_prorrogados = cur.fetchall()
        
        # Helper: ajustar data se faltam <= 5 dias para fim do mês
        def ajustar_data_inicio(data):
            """Se faltam <= 5 dias para fim do mês, considerar próximo mês"""
            if not data:
                return None
            from datetime import datetime as dt
            ultimo_dia = calendar.monthrange(data.year, data.month)[1]
            dias_restantes = ultimo_dia - data.day
            if dias_restantes <= 5:
                # Primeiro dia do próximo mês
                if data.month == 12:
                    return dt(data.year + 1, 1, 1).date()
                else:
                    return dt(data.year, data.month + 1, 1).date()
            return dt(data.year, data.month, 1).date()
        
        def ajustar_data_fim(data):
            """Se faltam <= 5 dias para fim do mês, considerar mês atual, senão mês anterior"""
            if not data:
                return None
            from datetime import datetime as dt
            ultimo_dia = calendar.monthrange(data.year, data.month)[1]
            dias_restantes = ultimo_dia - data.day
            if dias_restantes <= 5:
                # Último dia do mês atual
                return dt(data.year, data.month, ultimo_dia).date()
            else:
                # Mês anterior
                if data.month == 1:
                    ano_ant = data.year - 1
                    mes_ant = 12
                else:
                    ano_ant = data.year
                    mes_ant = data.month - 1
                ultimo_dia_ant = calendar.monthrange(ano_ant, mes_ant)[1]
                return dt(ano_ant, mes_ant, ultimo_dia_ant).date()
        
        termos = []
        
        # Processar termos novos
        for row in termos_novos:
            inicio_ajustado = ajustar_data_inicio(row['inicio'])
            fim_ajustado = ajustar_data_fim(row['final'])
            
            termos.append({
                'numero_termo': row['numero_termo'],
                'osc': row['osc'],
                'cnpj': row['cnpj'],
                'inicio': formatar_data_br(row['inicio']),
                'final': formatar_data_br(row['final']),
                'tipo_contrato': row['tipo_termo'],
                'total_previsto': float(row['total_previsto'] or 0),
                'edital_nome': row['edital_nome'] or '',
                'data_inicio_vigencia': inicio_ajustado.strftime('%Y-%m-%d') if inicio_ajustado else None,
                'data_fim_vigencia': fim_ajustado.strftime('%Y-%m-%d') if fim_ajustado else None,
                'sei_celeb': row['sei_celeb'] or '',
                'sei_pc': row['sei_pc'] or '',
                'tipo_disponibilidade': 'novo',
                'meses_preenchidos': None,
                'info_prorrogacao': None
            })
        
        # Processar termos com prorrogação
        debug_prorrogacoes = []  # Lista para debug
        
        for row in termos_prorrogados:
            inicio_parceria = ajustar_data_inicio(row['inicio'])
            fim_parceria = ajustar_data_fim(row['final'])
            
            min_ul = row['min_vig_ul']  # Já é date
            max_ul = row['max_vig_ul']  # Já é date
            
            # Formatar meses preenchidos
            min_ul_mes = min_ul.strftime('%m/%y') if min_ul else ''
            max_ul_mes = max_ul.strftime('%m/%y') if max_ul else ''
            
            # Calcular total em ultra_liquidacoes cronograma
            cur.execute("""
                SELECT SUM(COALESCE(valor_mes, 0)) as total_cronograma
                FROM gestao_financeira.ultra_liquidacoes_cronograma
                WHERE numero_termo = %s
            """, [row['numero_termo']])
            total_result = cur.fetchone()
            total_cronograma = float(total_result['total_cronograma'] or 0) if total_result else 0
            
            # DEBUG: Salvar informação da comparação (QUANTIDADE DE MESES)
            meses_preenchidos = int(row['meses_preenchidos'])
            meses_parceria = int(row['meses_parceria'])
            meses_faltantes = meses_parceria - meses_preenchidos
            
            debug_prorrogacoes.append({
                'termo': row['numero_termo'],
                'edital_nome': row['edital_nome'] or 'N/A',
                'osc': row['osc'] or 'N/A',
                'inicio_parceria': formatar_data_br(row['inicio']),
                'fim_parceria': formatar_data_br(row['final']),
                'meses_parceria': meses_parceria,
                'min_vigencia_ul': formatar_data_br(min_ul),
                'max_vigencia_ul': formatar_data_br(max_ul),
                'meses_preenchidos_ul': meses_preenchidos,
                'meses_faltantes': meses_faltantes,
                'motivo_inclusao': f'{meses_faltantes} meses faltantes (Parceria: {meses_parceria} meses, Preenchido: {meses_preenchidos} meses)',
                'total_cronograma': f"R$ {total_cronograma:,.2f}"
            })
            
            termos.append({
                'numero_termo': row['numero_termo'],
                'osc': row['osc'],
                'cnpj': row['cnpj'],
                'inicio': formatar_data_br(row['inicio']),
                'final': formatar_data_br(row['final']),
                'tipo_contrato': row['tipo_termo'],
                'total_previsto': float(row['total_previsto'] or 0),
                'edital_nome': row['edital_nome'] or '',
                'data_inicio_vigencia': inicio_parceria.strftime('%Y-%m-%d') if inicio_parceria else None,
                'data_fim_vigencia': fim_parceria.strftime('%Y-%m-%d') if fim_parceria else None,
                'sei_celeb': row['sei_celeb'] or '',
                'sei_pc': row['sei_pc'] or '',
                'tipo_disponibilidade': 'prorrogacao',
                'meses_preenchidos': f"{min_ul_mes} a {max_ul_mes}",
                'info_prorrogacao': f"Meses preenchidos: {min_ul_mes} a {max_ul_mes} (R$ {total_cronograma:,.2f})"
            })
        
        # Salvar debug no session para relatório
        session['debug_prorrogacoes'] = debug_prorrogacoes
        
        # Ordenar por data DESC
        termos.sort(key=lambda x: x['data_inicio_vigencia'] if x['data_inicio_vigencia'] else '', reverse=True)
        
        return jsonify({
            'success': True,
            'termos': termos
        })
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/cronograma')
@login_required
def get_cronograma():
    """Buscar cronograma mensal de um termo"""
    cur = get_cursor()
    
    try:
        numero_termo = request.args.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'success': False, 'error': 'Número do termo não fornecido'}), 400
        
        cur.execute("""
            SELECT 
                id,
                numero_termo,
                info_alteracao,
                nome_mes,
                valor_mes_23,
                valor_mes_24,
                valor_mes,
                parcela_numero,
                created_por,
                created_em,
                atualizado_por,
                atualizado_em
            FROM gestao_financeira.ultra_liquidacoes_cronograma
            WHERE numero_termo = %s
            ORDER BY nome_mes
        """, [numero_termo])
        
        registros = cur.fetchall()
        
        if not registros:
            return jsonify({
                'success': True,
                'cronograma': [],
                'message': 'Nenhum cronograma encontrado para este termo'
            })
        
        cronograma = []
        for reg in registros:
            cronograma.append({
                'id': reg['id'],
                'numero_termo': reg['numero_termo'],
                'info_alteracao': reg['info_alteracao'],
                'nome_mes': reg['nome_mes'].strftime('%Y-%m-%d') if reg['nome_mes'] else None,
                'valor_mes_23': float(reg['valor_mes_23']) if reg['valor_mes_23'] else 0,
                'valor_mes_24': float(reg['valor_mes_24']) if reg['valor_mes_24'] else 0,
                'valor_mes': float(reg['valor_mes']) if reg['valor_mes'] else 0,
                'parcela_numero': reg['parcela_numero'],
                'created_por': reg['created_por'],
                'created_em': reg['created_em'].strftime('%Y-%m-%d %H:%M:%S') if reg['created_em'] else None,
                'atualizado_por': reg['atualizado_por'],
                'atualizado_em': reg['atualizado_em'].strftime('%Y-%m-%d %H:%M:%S') if reg['atualizado_em'] else None
            })
        
        return jsonify({
            'success': True,
            'cronograma': cronograma,
            'total_registros': len(cronograma)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ultra_liquidacoes_bp.route('/api/termos-vigentes-colaboracao')
@login_required
def get_termos_vigentes_colaboracao():
    """
    Retorna termos de Colaboração ainda vigentes
    
    Regras:
    - tipo_termo contém "Colaboração" (TCL)
    - Data final (coluna final) deve ser posterior à data atual
    - Retorna número do termo, OSC, vigência e tipo
    """
    from psycopg2.extras import RealDictCursor
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        from datetime import date
        data_hoje = date.today()
        
        print(f"[DEBUG] Buscando termos de colaboração vigentes. Data hoje: {data_hoje}")
        
        cur.execute("""
            SELECT 
                numero_termo,
                osc,
                cnpj,
                inicio,
                final,
                tipo_termo,
                sei_celeb,
                sei_pc,
                total_previsto
            FROM public.parcerias
            WHERE tipo_termo ILIKE %s
            AND final >= %s
            ORDER BY numero_termo
        """, ('%Colaboração%', data_hoje))
        
        termos = cur.fetchall()
        print(f"[DEBUG] Termos encontrados: {len(termos)}")
        
        resultado = []
        for termo in termos:
            resultado.append({
                'numero_termo': termo['numero_termo'],
                'osc': termo['osc'] or '-',
                'cnpj': termo['cnpj'] or '-',
                'vigencia_inicio': termo['inicio'].strftime('%d/%m/%Y') if termo['inicio'] else '-',
                'vigencia_final': termo['final'].strftime('%d/%m/%Y') if termo['final'] else '-',
                'tipo_termo': termo['tipo_termo'] or '-',
                'sei_celeb': termo['sei_celeb'] or '-',
                'sei_pc': termo['sei_pc'] or '-',
                'total_previsto': float(termo['total_previsto']) if termo['total_previsto'] else 0
            })
        
        return jsonify({
            'success': True,
            'termos': resultado,
            'total': len(resultado)
        })
    
    except Exception as e:
        print(f"[ERRO] get_termos_vigentes_colaboracao: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        cur.close()


@ultra_liquidacoes_bp.route('/api/salvar-cronograma', methods=['POST'])
@login_required
def salvar_cronograma():
    """Salvar ou atualizar cronograma mensal"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        dados = request.get_json()
        print(f"🔍 DEBUG salvar_cronograma: Dados recebidos: {dados}")
        
        numero_termo = dados.get('numero_termo')
        cronograma = dados.get('cronograma', [])
        info_alteracao_global = dados.get('info_alteracao', 'Base')  # Fallback (não será mais usado)
        
        print(f"🔍 DEBUG: numero_termo={numero_termo}, total_meses={len(cronograma)}")
        
        if not numero_termo:
            return jsonify({'success': False, 'error': 'Número do termo não fornecido'}), 400
        
        if not cronograma:
            return jsonify({'success': False, 'error': 'Cronograma vazio'}), 400
        
        # Debug: mostrar primeiro mês
        if cronograma:
            print(f"🔍 DEBUG: Primeiro mês: {cronograma[0]}")
        
        # Inserir novos registros (permite duplicatas para acréscimos no mesmo mês)
        # Cada mês agora pode ter seu próprio info_alteracao
        linhas_inseridas = 0
        
        for idx, mes_dados in enumerate(cronograma):
            # Pegar info_alteracao específico deste mês, ou usar 'Base' como fallback
            info_alteracao = mes_dados.get('info_alteracao', 'Base')
            
            print(f"🔍 DEBUG: Inserindo mês {idx + 1}/{len(cronograma)}: {mes_dados['nome_mes']} - Info: {info_alteracao}")
            
            cur.execute("""
                INSERT INTO gestao_financeira.ultra_liquidacoes_cronograma (
                    numero_termo,
                    info_alteracao,
                    nome_mes,
                    valor_mes_23,
                    valor_mes_24,
                    valor_mes,
                    parcela_numero,
                    created_por,
                    created_em
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
            """, [
                numero_termo,
                info_alteracao,
                mes_dados['nome_mes'],
                mes_dados.get('valor_mes_23'),
                mes_dados.get('valor_mes_24'),
                mes_dados.get('valor_mes'),
                mes_dados.get('parcela_numero'),
                session.get('username', 'Sistema')
            ])
            
            linhas_inseridas += cur.rowcount
        
        print(f"✅ DEBUG: Total inserido={linhas_inseridas}")
        conn.commit()
        print(f"✅ DEBUG: Commit realizado com sucesso!")
        
        return jsonify({
            'success': True,
            'message': f'Cronograma salvo com sucesso. {linhas_inseridas} meses inseridos.',
            'linhas_afetadas': linhas_inseridas
        })
    
    except Exception as e:
        print(f"❌ ERRO em salvar_cronograma: {str(e)}")
        import traceback
        print("❌ Traceback completo:")
        print(traceback.format_exc())
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@ultra_liquidacoes_bp.route('/api/debug-termo')
@login_required
def api_debug_termo():
    """Endpoint de debug para validar cálculos de um termo"""
    numero_termo = request.args.get('numero_termo')
    
    if not numero_termo:
        return jsonify({'success': False, 'error': 'Número do termo não fornecido'}), 400
    
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Buscar todas as parcelas do termo
        cur.execute("""
            SELECT 
                id,
                parcela_tipo,
                parcela_numero,
                vigencia_inicial,
                vigencia_final,
                valor_previsto
            FROM gestao_financeira.ultra_liquidacoes
            WHERE numero_termo = %s
            ORDER BY parcela_numero
        """, [numero_termo])
        
        parcelas = cur.fetchall()
        
        if not parcelas:
            return jsonify({
                'success': False,
                'error': f'Nenhuma parcela encontrada para o termo {numero_termo}'
            }), 404
        
        # Contar e somar por tipo
        total_parcelas = len(parcelas)
        parcelas_programadas = sum(1 for p in parcelas if p['parcela_tipo'] == 'Programada')
        parcelas_projetadas = sum(1 for p in parcelas if p['parcela_tipo'] == 'Projetada')
        parcelas_outras = total_parcelas - parcelas_programadas - parcelas_projetadas
        
        soma_programadas = sum(float(p['valor_previsto'] or 0) for p in parcelas if p['parcela_tipo'] == 'Programada')
        soma_projetadas = sum(float(p['valor_previsto'] or 0) for p in parcelas if p['parcela_tipo'] == 'Projetada')
        soma_total = sum(float(p['valor_previsto'] or 0) for p in parcelas)
        
        # Buscar total previsto na parceria
        cur.execute("""
            SELECT total_previsto
            FROM public.parcerias
            WHERE numero_termo = %s
        """, [numero_termo])
        
        parceria = cur.fetchone()
        total_previsto_parceria = float(parceria['total_previsto']) if parceria and parceria['total_previsto'] else 0
        
        # Calcular diferença
        diferenca = soma_programadas - total_previsto_parceria
        
        # Status de validação
        if abs(diferenca) < 0.01:  # Tolerância de 1 centavo
            status_validacao = "✅ CORRETO - Soma de Programadas = Total Parceria"
        elif diferenca > 0:
            status_validacao = f"⚠️ MAIOR - Programadas excedem parceria em R$ {abs(diferenca):.2f}"
        else:
            status_validacao = f"⚠️ MENOR - Programadas menores que parceria em R$ {abs(diferenca):.2f}"
        
        # Detalhes das parcelas
        detalhes_parcelas = []
        for p in parcelas:
            detalhes_parcelas.append({
                'id': p['id'],
                'tipo': p['parcela_tipo'],
                'numero': p['parcela_numero'],
                'vigencia': f"{p['vigencia_inicial'].strftime('%d/%m/%Y') if p['vigencia_inicial'] else '-'} a {p['vigencia_final'].strftime('%d/%m/%Y') if p['vigencia_final'] else '-'}",
                'valor_previsto': float(p['valor_previsto'] or 0)
            })
        
        return jsonify({
            'success': True,
            'numero_termo': numero_termo,
            'total_parcelas': total_parcelas,
            'parcelas_programadas': parcelas_programadas,
            'parcelas_projetadas': parcelas_projetadas,
            'parcelas_outras': parcelas_outras,
            'soma_programadas': soma_programadas,
            'soma_projetadas': soma_projetadas,
            'soma_total': soma_total,
            'total_previsto_parceria': total_previsto_parceria,
            'diferenca': diferenca,
            'status_validacao': status_validacao,
            'detalhes_parcelas': detalhes_parcelas
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ultra_liquidacoes_bp.route('/api/debug-relatorio')
@login_required
def api_debug_relatorio():
    """
    Retorna relatório completo de debug com:
    1. Comparações de datas para prorrogações
    2. Avisos de cálculo de empenhos
    """
    
    # Buscar dados salvos no session
    debug_prorrogacoes = session.get('debug_prorrogacoes', [])
    debug_avisos_empenhos = session.get('debug_avisos_empenhos', [])
    
    return jsonify({
        'success': True,
        'total_prorrogacoes': len(debug_prorrogacoes),
        'prorrogacoes': debug_prorrogacoes,
        'total_avisos_empenhos': len(debug_avisos_empenhos),
        'avisos_empenhos': debug_avisos_empenhos
    })


@ultra_liquidacoes_bp.route('/api/salvar-cronograma', methods=['POST'])
@login_required
def api_salvar_cronograma():
    """
    Salva cronograma mensal em ultra_liquidacoes_cronograma
    """
    try:
        dados = request.get_json()
        numero_termo = dados.get('numero_termo')
        cronograma = dados.get('cronograma', [])
        info_alteracao = dados.get('info_alteracao', 'Base')
        
        if not numero_termo or not cronograma:
            return jsonify({'success': False, 'error': 'Dados incompletos'}), 400
        
        conn = get_db()
        cur = get_cursor()
        
        # Deletar registros existentes para este termo
        cur.execute("""
            DELETE FROM gestao_financeira.ultra_liquidacoes_cronograma
            WHERE numero_termo = %s
        """, (numero_termo,))
        
        # Inserir novos registros
        linhas_inseridas = 0
        for mes in cronograma:
            cur.execute("""
                INSERT INTO gestao_financeira.ultra_liquidacoes_cronograma
                (numero_termo, nome_mes, valor_mes_23, valor_mes_24, valor_mes, parcela_numero, info_alteracao)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                numero_termo,
                mes['nome_mes'],
                mes['valor_mes_23'],
                mes['valor_mes_24'],
                mes['valor_mes'],
                mes['parcela_numero'],
                info_alteracao
            ))
            linhas_inseridas += 1
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'linhas_afetadas': linhas_inseridas
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@ultra_liquidacoes_bp.route('/api/carregar-cronograma', methods=['GET'])
@login_required
def api_carregar_cronograma():
    """
    Carrega cronograma salvo de ultra_liquidacoes_cronograma
    """
    try:
        numero_termo = request.args.get('numero_termo')
        
        print(f'🔍 Carregando cronograma para: {numero_termo}')
        
        if not numero_termo:
            return jsonify({'success': False, 'error': 'Número do termo não fornecido'}), 400
        
        conn = get_db()
        cur = get_cursor()
        
        cur.execute("""
            SELECT nome_mes, valor_mes_23, valor_mes_24, valor_mes, parcela_numero, info_alteracao
            FROM gestao_financeira.ultra_liquidacoes_cronograma
            WHERE numero_termo = %s
            ORDER BY nome_mes
        """, (numero_termo,))
        
        cronograma = cur.fetchall()
        
        print(f'📋 Encontrado {len(cronograma)} linhas')
        if len(cronograma) > 0:
            print(f'📋 Primeira linha:', dict(cronograma[0]))
        
        return jsonify({
            'success': True,
            'cronograma': [dict(c) for c in cronograma]
        })
        
    except Exception as e:
        print(f'❌ Erro ao carregar cronograma: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500


@ultra_liquidacoes_bp.route('/api/status-pagamento', methods=['GET'])
@login_required
def api_status_pagamento():
    """
    Retorna lista de status de pagamento da tabela categoricas
    """
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT DISTINCT parcela_status, status_secundario
            FROM categoricas.c_dac_status_pagamento
            ORDER BY parcela_status
        """)
        
        status = cur.fetchall()
        
        return jsonify({
            'success': True,
            'status': [dict(s) for s in status]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ultra_liquidacoes_bp.route('/api/adicionar-parcelas', methods=['POST'])
@login_required
def api_adicionar_parcelas():
    """
    Adiciona parcelas finais em ultra_liquidacoes
    Se upsert_mode=True, faz UPSERT baseado em (numero_termo, vigencia_inicial)
    """
    try:
        dados = request.get_json()
        print(f'🔍 DEBUG api_adicionar_parcelas - Dados recebidos: {dados}')
        
        parcelas = dados.get('parcelas', [])
        upsert_mode = dados.get('upsert_mode', False)  # Flag para modo UPSERT
        print(f'🔍 DEBUG - Total de parcelas: {len(parcelas)}')
        print(f'🔍 DEBUG - Modo UPSERT: {upsert_mode}')
        
        if not parcelas:
            return jsonify({'success': False, 'error': 'Nenhuma parcela para adicionar'}), 400
        
        # Validar se todas as parcelas têm numero_termo
        for idx, p in enumerate(parcelas):
            print(f'🔍 DEBUG - Parcela {idx + 1}: numero_termo = "{p.get("numero_termo")}", tipo = {type(p.get("numero_termo"))}')
            if not p.get('numero_termo'):
                return jsonify({'success': False, 'error': f'Número do termo não fornecido na parcela {idx + 1}'}), 400
        
        # Obter email do usuário logado
        email_usuario = session.get('email')
        if not email_usuario:
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
        
        conn = get_db()
        cur = get_cursor()
        
        linhas_inseridas = 0
        
        # Simplesmente inserir todas as parcelas marcadas - sem lógica de ON CONFLICT
        # Se houver duplicatas, deixa duplicar (usuário é responsável pela limpeza)
        for p in parcelas:
            cur.execute("""
                INSERT INTO gestao_financeira.ultra_liquidacoes
                (vigencia_inicial, vigencia_final, numero_termo, parcela_tipo, parcela_numero,
                 valor_elemento_53_23, valor_elemento_53_24, valor_previsto,
                 valor_subtraido, valor_encaminhado, valor_pago,
                 parcela_status, parcela_status_secundario, data_pagamento, observacoes,
                 created_por, created_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                p['vigencia_inicial'],
                p['vigencia_final'],
                p['numero_termo'],
                p['parcela_tipo'],
                p['parcela_numero'],
                p['valor_elemento_53_23'],
                p['valor_elemento_53_24'],
                p['valor_previsto'],
                p['valor_subtraido'],
                p['valor_encaminhado'],
                p['valor_pago'],
                p['parcela_status'],
                p['parcela_status_secundario'],
                p['data_pagamento'],
                p['observacoes'],
                email_usuario
            ))
            linhas_inseridas += 1
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'linhas_inseridas': linhas_inseridas,
            'mensagem': f'{linhas_inseridas} parcelas inseridas com sucesso'
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
