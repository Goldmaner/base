# -*- coding: utf-8 -*-
"""
Blueprint para Gestão Financeira - Ultra Liquidações
Sistema de controle de parcelas com validações e filtros avançados
"""

from flask import Blueprint, render_template, request, jsonify, session, g
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


def formatar_data_mes_ano(data, formato_completo=False):
    """Formata date para string 'mês/ano' (ex: jan/26) ou 'mês de ano' (ex: janeiro de 2026)"""
    if data is None:
        return ''
    if isinstance(data, str):
        # Se já for string, tentar parsear
        try:
            data = datetime.strptime(data, '%d/%m/%Y').date()
        except:
            return data
    
    # Mapeamento de meses em português
    meses_abrev = {
        1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
        7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
    }
    
    meses_completo = {
        1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril', 5: 'maio', 6: 'junho',
        7: 'julho', 8: 'agosto', 9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
    }
    
    if formato_completo:
        mes_nome = meses_completo.get(data.month, '')
        return f"{mes_nome} de {data.year}"
    else:
        mes_abrev = meses_abrev.get(data.month, '')
        ano_curto = str(data.year)[2:]  # Últimos 2 dígitos do ano
        return f"{mes_abrev}/{ano_curto}"


def parse_data_br(data_str):
    """Parse string dd/mm/yyyy ou mm/yyyy para date"""
    if not data_str:
        return None
    
    # Tentar formato DD/MM/YYYY
    try:
        return datetime.strptime(data_str, '%d/%m/%Y').date()
    except:
        pass
    
    # Tentar formato MM/YYYY (assumir dia 01)
    try:
        # Se vier '01/MM/YYYY' do converterInputParaData
        return datetime.strptime(data_str, '%d/%m/%Y').date()
    except:
        pass
    
    return None


def converter_sei_para_cod_sof(sei_celeb):
    """
    Converte SEI do formato '6074.2023/0004039-2' para '6074202300040392'
    Remove pontos, barras e hífens
    
    IMPORTANTE: Não remove zeros à esquerda! O valor já está correto no SEI.
    Exemplo: 6074.2023/0004039-2 → 6074202300040392
    """
    if not sei_celeb:
        return None
    # Remove apenas os separadores (pontos, barras, hífens)
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
    print("\n" + "="*80)
    print("🚀 API LISTAR PARCELAS CHAMADA")
    print("="*80)
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
        
        # DEBUG: Log do filtro de pendência
        print(f"\n🔍 DEBUG FILTRO PENDÊNCIA:")
        print(f"   tipo_pendencia = '{filtro_tipo_pendencia}'")
        print(f"   tipo_pendencia vazio? {filtro_tipo_pendencia == ''}")
        print(f"   tipo_pendencia bool? {bool(filtro_tipo_pendencia)}")
        print(f"   len(tipo_pendencia) = {len(filtro_tipo_pendencia)}")
        
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
        
        # DEBUG: Log para verificar se vai usar query com filtro de cor
        print(f"\n📊 DECISÃO DE QUERY:")
        print(f"   filtro_tipo_pendencia = '{filtro_tipo_pendencia}'")
        print(f"   bool(filtro_tipo_pendencia) = {bool(filtro_tipo_pendencia)}")
        if filtro_tipo_pendencia:
            print(f"   ✅ VAI USAR QUERY COM FILTRO DE COR (subquery complexa)")
        else:
            print(f"   ✅ VAI USAR QUERY SIMPLES (sem filtro de cor)")
        
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
                    ul.parcela_andamento,
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
                -- Se filtro vazio, mostrar todos; caso contrário, filtrar por cor
                ('{filtro_tipo_pendencia}' = '' OR
                 ('{filtro_tipo_pendencia}' = 'amarelo' AND subq.tem_inconsistencia = true) OR
                 ('{filtro_tipo_pendencia}' = 'verde_claro' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = true) OR
                 ('{filtro_tipo_pendencia}' = 'verde_escuro' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = false AND subq.empenho_cobre = true) OR
                 ('{filtro_tipo_pendencia}' = 'sem_cor' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = false AND subq.empenho_cobre = false))
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
                ul.parcela_andamento,
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
        
        print(f"\n🔄 EXECUTANDO QUERY...")
        print(f"   Total de parâmetros: {len(params)}")
        print(f"   Usando query COM filtro de cor? {bool(filtro_tipo_pendencia)}")
        print(f"\n📝 QUERY SQL (primeiros 1000 chars):")
        print(query[:1000])
        print(f"\n📝 Parâmetros (primeiros 5): {params[:5]}")
        cur.execute(query, params)
        parcelas = cur.fetchall()
        print(f"\n✅ QUERY EXECUTADA")
        print(f"   Resultados retornados: {len(parcelas)}")
        
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
                ('{filtro_tipo_pendencia}' = '' OR
                 ('{filtro_tipo_pendencia}' = 'amarelo' AND subq.tem_inconsistencia = true) OR
                 ('{filtro_tipo_pendencia}' = 'verde_claro' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = true) OR
                 ('{filtro_tipo_pendencia}' = 'verde_escuro' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = false AND subq.empenho_cobre = true) OR
                 ('{filtro_tipo_pendencia}' = 'sem_cor' AND subq.tem_inconsistencia = false AND subq.necessita_regularizacao = false AND subq.empenho_cobre = false))
            """
            cur.execute(query_count, params[:-2])  # Sem LIMIT/OFFSET
        else:
            # Query count SEM filtro de cor (query simples)
            query_count = f"""
                SELECT COUNT(*) as total
                FROM gestao_financeira.ultra_liquidacoes ul
                LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
                WHERE {where_clause}
            """
            cur.execute(query_count, params[:-2])  # Sem LIMIT/OFFSET
        total = cur.fetchone()['total']
        print(f"\n📈 TOTAL DE REGISTROS (query_count): {total}")
        
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
                'parcela_andamento': p['parcela_andamento'] or '',
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
        # DISTRIBUIÇÃO EM CASCATA: Valores pagos (corrigido para considerar parcelas "Pago")
        # ========================================================================
        # PASSO 1: Processar TODAS as parcelas ordenadas por vigência_inicial
        # para contabilizar consumo REAL (status "Pago" consome primeiro)
        
        from collections import defaultdict
        
        # Separar parcelas por status e ordenar por vigência
        todas_parcelas_ordenadas = sorted(
            resultado,
            key=lambda x: x['vigencia_inicial_raw'] if x['vigencia_inicial_raw'] else datetime(2099, 1, 1).date()
        )
        
        # Controle de valores já consumidos por parcelas "Pago"
        # Formato: {(numero_termo, ano, elemento): valor_consumido}
        valores_consumidos = defaultdict(float)
        
        # PASSO 2: Contabilizar consumo de parcelas com status "Pago"
        # CRÍTICO: buscar TODAS as parcelas "Pago" do banco, não só as da página atual.
        # Se o usuário está na aba "Encaminhado", as parcelas "Pago" não estão em `resultado`,
        # então precisamos de uma query separada para evitar que o saldo seja redistribuído
        # para parcelas erradas.
        try:
            cur.execute("""
                SELECT numero_termo,
                       vigencia_inicial,
                       COALESCE(valor_elemento_53_23, 0) AS valor_23,
                       COALESCE(valor_elemento_53_24, 0) AS valor_24
                FROM gestao_financeira.ultra_liquidacoes
                WHERE LOWER(parcela_status) = 'pago'
            """)
            parcelas_pagas_banco = cur.fetchall()
            for pp in parcelas_pagas_banco:
                vi = pp['vigencia_inicial']
                if vi is None:
                    continue
                ano_p = vi.year if hasattr(vi, 'year') else int(str(vi)[:4])
                nt = pp['numero_termo']
                valores_consumidos[(nt, ano_p, 23)] += float(pp['valor_23'])
                valores_consumidos[(nt, ano_p, 24)] += float(pp['valor_24'])
            print(f"[CASCADE] Parcelas pagas carregadas do banco: {len(parcelas_pagas_banco)}, chaves consumidas: {len(valores_consumidos)}")
        except Exception as e_pagas:
            print(f"[ERRO CASCADE parcelas_pagas] {e_pagas}")
            import traceback; traceback.print_exc()
        
        # PASSO 3: Distribuir saldo disponível para parcelas "Encaminhado para Pagamento"
        controle_cascata = defaultdict(lambda: {'pago_23': 0, 'pago_24': 0})
        
        for parcela in todas_parcelas_ordenadas:
            if parcela['parcela_status'] != 'Encaminhado para Pagamento':
                continue
            
            if parcela['tem_pendencia']:
                continue  # Pular parcelas com inconsistências (amarelo tem prioridade)
            
            vigencia_raw = parcela['vigencia_inicial_raw']
            if not vigencia_raw:
                continue
            
            ano_parcela = vigencia_raw.year
            numero_termo = parcela['numero_termo']
            sei_celeb = termo_para_sei.get(numero_termo)
            
            if not sei_celeb:
                continue
            
            cod_sof = converter_sei_para_cod_sof(sei_celeb)
            
            # Buscar total pago por elemento neste ano (do banco back_empenhos)
            # IMPORTANTE: cod_item_desp_sof retorna INT, não STRING
            chave_elemento_23 = (cod_sof, ano_parcela, 23)
            chave_elemento_24 = (cod_sof, ano_parcela, 24)
            
            total_pago_23 = pagos_por_elemento.get(chave_elemento_23, 0)
            total_pago_24 = pagos_por_elemento.get(chave_elemento_24, 0)
            
            # CORREÇÃO CRÍTICA: Subtrair valores já consumidos por parcelas "Pago"
            chave_consumo_23 = (numero_termo, ano_parcela, 23)
            chave_consumo_24 = (numero_termo, ano_parcela, 24)
            
            ja_consumido_23 = valores_consumidos[chave_consumo_23]
            ja_consumido_24 = valores_consumidos[chave_consumo_24]
            
            saldo_disponivel_23 = max(0, total_pago_23 - ja_consumido_23)
            saldo_disponivel_24 = max(0, total_pago_24 - ja_consumido_24)
            
            # Chave para controle de cascata entre parcelas "Encaminhado" (por termo+ano)
            chave_controle = (numero_termo, ano_parcela)
            
            # Distribuir elemento 23 (considerando saldo disponível)
            if saldo_disponivel_23 > 0:
                ja_distribuido_23 = controle_cascata[chave_controle]['pago_23']
                restante_23 = saldo_disponivel_23 - ja_distribuido_23
                
                if restante_23 > 0:
                    valor_elemento_23 = parcela['valor_elemento_53_23']
                    valor_a_distribuir_23 = min(restante_23, valor_elemento_23)
                    
                    parcela['valor_pago_23'] = valor_a_distribuir_23
                    controle_cascata[chave_controle]['pago_23'] += valor_a_distribuir_23
            
            # Distribuir elemento 24 (considerando saldo disponível)
            if saldo_disponivel_24 > 0:
                ja_distribuido_24 = controle_cascata[chave_controle]['pago_24']
                restante_24 = saldo_disponivel_24 - ja_distribuido_24
                
                if restante_24 > 0:
                    valor_elemento_24 = parcela['valor_elemento_53_24']
                    valor_a_distribuir_24 = min(restante_24, valor_elemento_24)
                    
                    parcela['valor_pago_24'] = valor_a_distribuir_24
                    controle_cascata[chave_controle]['pago_24'] += valor_a_distribuir_24
            
            # Determinar status: PAGO INTEGRAL ou PAGO PARCIAL
            # IMPORTANTE: Considerar valor_subtraido (glosas/deduções)
            # Valor Devido = Valor Previsto - Valor Subtraído
            valor_devido_23 = parcela['valor_elemento_53_23'] - parcela['valor_subtraido']
            valor_devido_24 = parcela['valor_elemento_53_24']
            valor_pago_total = parcela['valor_pago_23'] + parcela['valor_pago_24']
            valor_devido_total = valor_devido_23 + valor_devido_24
            
            if valor_pago_total > 0:
                if valor_pago_total >= valor_devido_total - 0.01:  # Tolerância de 1 centavo
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
        
        print(f"\n📦 RETORNANDO JSON:")
        print(f"   success: True")
        print(f"   data: {len(resultado)} parcelas")
        print(f"   total: {total}")
        print(f"   pagina: {pagina}")
        print(f"   total_paginas: {(total + por_pagina - 1) // por_pagina}")
        print(f"   total_pendencias: {total_pendencias}")
        print("="*80 + "\n")
        
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
        
        # Buscar opções de andamento
        cur.execute("""
            SELECT status_parcela
            FROM categoricas.c_dac_parcela_andamento_status
            WHERE LOWER(status_status) = 'ativo'
            ORDER BY status_parcela
        """)
        opcoes_andamento = [r['status_parcela'] for r in cur.fetchall()]
        
        # Histórico de alterações do status de andamento
        cur.execute("""
            SELECT
                TO_CHAR(created_at, 'DD/MM/YYYY HH24:MI') AS data_hora,
                usuario_nome,
                detalhes->'parcela_andamento'->>'de'   AS andamento_de,
                detalhes->'parcela_andamento'->>'para' AS andamento_para
            FROM gestao_pessoas.log_atividades
            WHERE recurso_tipo = 'parcela'
              AND recurso_id   = %s
              AND detalhes ? 'parcela_andamento'
            ORDER BY created_at DESC
            LIMIT 30
        """, (str(parcela_id),))
        historico_andamento = [
            {
                'data_hora':      r['data_hora'],
                'usuario':        r['usuario_nome'],
                'andamento_de':   r['andamento_de'],
                'andamento_para': r['andamento_para']
            }
            for r in cur.fetchall()
        ]
        
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
            'parcela_andamento': re.sub(r'^\d{2}/\d{2}/\d{4} - ', '', parcela['parcela_andamento'] or ''),
            'opcoes_andamento': opcoes_andamento,
            'historico_andamento': historico_andamento,
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
        
        # Parse de valores numéricos - converte None/null para 0
        def parse_valor_decimal(valor):
            """Converte valor para Decimal, tratando None, null, strings vazias"""
            if valor is None or valor == '' or valor == 'null' or valor == 'None':
                return Decimal('0')
            return Decimal(str(valor))
        
        valor_elemento_53_23 = parse_valor_decimal(dados.get('valor_elemento_53_23'))
        valor_elemento_53_24 = parse_valor_decimal(dados.get('valor_elemento_53_24'))
        valor_previsto = parse_valor_decimal(dados.get('valor_previsto'))
        valor_subtraido = parse_valor_decimal(dados.get('valor_subtraido'))
        valor_encaminhado = parse_valor_decimal(dados.get('valor_encaminhado'))
        valor_pago = parse_valor_decimal(dados.get('valor_pago'))
        
        # Campos texto
        parcela_tipo = dados.get('parcela_tipo', '')
        parcela_numero = dados.get('parcela_numero', '')
        parcela_status = dados.get('parcela_status', '')
        parcela_status_secundario = dados.get('parcela_status_secundario', '')
        parcela_andamento = dados.get('parcela_andamento', '') if dados.get('parcela_status') == 'Encaminhado para Pagamento' else ''
        observacoes = dados.get('observacoes', '')
        
        usuario = session.get('usuario_nome', 'Sistema')
        
        # ================================================================
        # DIFF: Buscar valores atuais para registrar o que mudou no log
        # ================================================================
        cur.execute("""
            SELECT vigencia_inicial, vigencia_final, parcela_tipo, parcela_numero,
                   valor_elemento_53_23, valor_elemento_53_24, valor_previsto,
                   valor_subtraido, valor_encaminhado, valor_pago,
                   parcela_status, parcela_status_secundario, parcela_andamento,
                   data_pagamento, observacoes
            FROM gestao_financeira.ultra_liquidacoes WHERE id = %s
        """, (parcela_id,))
        atual = cur.fetchone()
        
        if atual:
            def _fmt(v):
                if v is None or v == '': return None
                if isinstance(v, Decimal): return str(v)
                if hasattr(v, 'strftime'): return v.strftime('%d/%m/%Y')
                return str(v)
            
            # Calcular parcela_andamento_salvo com prefixo de data
            _andamento_base_atual = re.sub(r'^\d{2}/\d{2}/\d{4} - ', '', atual['parcela_andamento'] or '')
            if parcela_andamento and parcela_andamento != _andamento_base_atual:
                # Valor mudou: prepõe data de hoje
                parcela_andamento_salvo = f"{datetime.now().strftime('%d/%m/%Y')} - {parcela_andamento}"
            elif not parcela_andamento:
                parcela_andamento_salvo = ''
            else:
                # Valor igual: preserva o que está no banco (mantém data original)
                parcela_andamento_salvo = atual['parcela_andamento'] or ''
            
            campos_diff = {
                'parcela_status':            (_fmt(atual['parcela_status']),            parcela_status or None),
                'parcela_status_secundario': (_fmt(atual['parcela_status_secundario']), parcela_status_secundario or None),
                'parcela_andamento':         (_fmt(atual['parcela_andamento']),          parcela_andamento_salvo or None),
                'valor_previsto':            (_fmt(atual['valor_previsto']),             _fmt(valor_previsto)),
                'valor_elemento_53_23':      (_fmt(atual['valor_elemento_53_23']),       _fmt(valor_elemento_53_23)),
                'valor_elemento_53_24':      (_fmt(atual['valor_elemento_53_24']),       _fmt(valor_elemento_53_24)),
                'valor_subtraido':           (_fmt(atual['valor_subtraido']),            _fmt(valor_subtraido)),
                'valor_encaminhado':         (_fmt(atual['valor_encaminhado']),          _fmt(valor_encaminhado)),
                'valor_pago':                (_fmt(atual['valor_pago']),                _fmt(valor_pago)),
                'data_pagamento':            (_fmt(atual['data_pagamento']),             _fmt(data_pagamento)),
                'observacoes':               (_fmt(atual['observacoes']),               observacoes or None),
                'parcela_tipo':              (_fmt(atual['parcela_tipo']),               parcela_tipo or None),
                'parcela_numero':            (_fmt(atual['parcela_numero']),             parcela_numero or None),
                'vigencia_inicial':          (_fmt(atual['vigencia_inicial']),           _fmt(vigencia_inicial)),
                'vigencia_final':            (_fmt(atual['vigencia_final']),             _fmt(vigencia_final)),
            }
            
            diff = {c: {'de': v_ant, 'para': v_nov}
                    for c, (v_ant, v_nov) in campos_diff.items()
                    if v_ant != v_nov}
            
            if diff:
                g.log_detalhes = diff
                g.log_recurso_tipo = 'parcela'
                g.log_recurso_id = parcela_id
        else:
            # Se não achou registro atual (raro), usa o valor limpo
            parcela_andamento_salvo = f"{datetime.now().strftime('%d/%m/%Y')} - {parcela_andamento}" if parcela_andamento else ''
        # ================================================================
        
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
                parcela_andamento = %s,
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
            parcela_andamento_salvo,
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
        print(f"[ERRO] Erro ao atualizar parcela: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
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
        where_clauses = []
        params = []
        
        # Aplicar filtro de seção se não for 'tudo'
        if modo != 'tudo':
            if secao == 'nao_pago':
                where_clauses.append("ul.parcela_status = %s")
                params.append('Não Pago')
            elif secao == 'encaminhado':
                where_clauses.append("ul.parcela_status = %s")
                params.append('Encaminhado para Pagamento')
            elif secao == 'pago':
                where_clauses.append("ul.parcela_status = %s")
                params.append('Pago')
        
        # Aplicar filtros adicionais se modo='filtrado'
        if modo == 'filtrado':
            # Filtros de texto
            if request.args.get('numero_termo'):
                where_clauses.append("ul.numero_termo ILIKE %s")
                params.append(f"%{request.args.get('numero_termo')}%")
            
            if request.args.get('osc'):
                where_clauses.append("p.osc ILIKE %s")
                params.append(f"%{request.args.get('osc')}%")
            
            if request.args.get('cnpj'):
                where_clauses.append("p.cnpj ILIKE %s")
                params.append(f"%{request.args.get('cnpj')}%")
            
            if request.args.get('parcela_tipo'):
                where_clauses.append("ul.parcela_tipo = %s")
                params.append(request.args.get('parcela_tipo'))
            
            if request.args.get('parcela_numero'):
                where_clauses.append("ul.parcela_numero::text ILIKE %s")
                params.append(f"%{request.args.get('parcela_numero')}%")
            
            if request.args.get('status_secundario'):
                where_clauses.append("ul.parcela_status_secundario = %s")
                params.append(request.args.get('status_secundario'))
            
            # Filtros de data
            if request.args.get('vigencia_inicial_de'):
                where_clauses.append("ul.vigencia_inicial >= %s")
                params.append(request.args.get('vigencia_inicial_de'))
            
            if request.args.get('vigencia_inicial_ate'):
                where_clauses.append("ul.vigencia_inicial <= %s")
                params.append(request.args.get('vigencia_inicial_ate'))
            
            if request.args.get('vigencia_final_de'):
                where_clauses.append("ul.vigencia_final >= %s")
                params.append(request.args.get('vigencia_final_de'))
            
            if request.args.get('vigencia_final_ate'):
                where_clauses.append("ul.vigencia_final <= %s")
                params.append(request.args.get('vigencia_final_ate'))
            
            if request.args.get('data_pagamento_de'):
                where_clauses.append("ul.data_pagamento >= %s")
                params.append(request.args.get('data_pagamento_de'))
            
            if request.args.get('data_pagamento_ate'):
                where_clauses.append("ul.data_pagamento <= %s")
                params.append(request.args.get('data_pagamento_ate'))
            
            # Filtro de ano
            if request.args.get('ano_vigencia'):
                where_clauses.append("EXTRACT(YEAR FROM ul.vigencia_inicial) = %s")
                params.append(int(request.args.get('ano_vigencia')))
        
        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
        
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
                ul.parcela_andamento,
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
            'Status', 'Status Secundário', 'Andamento', 'Data Pagamento', 'Observações',
            'OSC', 'CNPJ', 'Projeto', 'Processo Celebração', 'Processo PGTO/PC'
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
                p['parcela_andamento'] or '',
                formatar_data_br(p['data_pagamento']),
                p['observacoes'] or '',
                p['osc'] or '',
                p['cnpj'] or '',
                p['projeto'] or '',
                p['sei_celeb'] or '',
                p['sei_pc'] or ''
            ])
        
        output.seek(0)
        
        # Adicionar BOM UTF-8 para Excel reconhecer encoding
        csv_content = '\ufeff' + output.getvalue()
        
        from flask import Response
        return Response(
            csv_content.encode('utf-8'),
            mimetype='text/csv; charset=utf-8',
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
    """Atualiza múltiplas parcelas de um termo (edição em tabela)
    Suporta: INSERT (sem ID), UPDATE (com ID), DELETE (lista de IDs)"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        dados = request.get_json()
        parcelas = dados.get('parcelas', [])
        ids_excluir = dados.get('ids_excluir', [])
        
        parcelas_atualizadas = 0
        parcelas_inseridas = 0
        parcelas_excluidas = 0
        
        # PASSO 1: EXCLUIR parcelas marcadas
        if ids_excluir:
            placeholders = ','.join(['%s'] * len(ids_excluir))
            query_delete = f"DELETE FROM gestao_financeira.ultra_liquidacoes WHERE id IN ({placeholders})"
            cur.execute(query_delete, ids_excluir)
            parcelas_excluidas = cur.rowcount
        
        # PASSO 2: INSERIR novas parcelas (sem ID) ou ATUALIZAR existentes (com ID)
        for parcela in parcelas:
            parcela_id = parcela.get('id')
            
            # Preparar dados comuns
            dados_parcela = {}
            
            if parcela.get('vigencia_inicial'):
                dados_parcela['vigencia_inicial'] = parse_data_br(parcela['vigencia_inicial'])
            
            if parcela.get('vigencia_final'):
                dados_parcela['vigencia_final'] = parse_data_br(parcela['vigencia_final'])
            
            if parcela.get('parcela_tipo'):
                dados_parcela['parcela_tipo'] = parcela['parcela_tipo']
            
            if 'parcela_numero' in parcela:
                dados_parcela['parcela_numero'] = parcela['parcela_numero']
            
            # Valores monetários
            for campo in ['valor_elemento_53_23', 'valor_elemento_53_24', 'valor_previsto', 
                         'valor_subtraido', 'valor_encaminhado', 'valor_pago']:
                if campo in parcela:
                    valor = parcela[campo]
                    dados_parcela[campo] = Decimal(str(valor)) if valor else None
            
            if parcela.get('parcela_status'):
                dados_parcela['parcela_status'] = parcela['parcela_status']
            
            if 'parcela_status_secundario' in parcela:
                dados_parcela['parcela_status_secundario'] = parcela['parcela_status_secundario'] if parcela['parcela_status_secundario'] else None
            
            if 'data_pagamento' in parcela:
                dados_parcela['data_pagamento'] = parse_data_br(parcela['data_pagamento']) if parcela['data_pagamento'] else None
            
            # Adicionar numero_termo sempre
            dados_parcela['numero_termo'] = numero_termo
            
            if parcela_id:
                # UPDATE: parcela existente
                if dados_parcela:
                    campos_update = [f"{k} = %s" for k in dados_parcela.keys()]
                    valores = list(dados_parcela.values())
                    valores.append(parcela_id)
                    
                    query = f"UPDATE gestao_financeira.ultra_liquidacoes SET {', '.join(campos_update)} WHERE id = %s"
                    cur.execute(query, valores)
                    parcelas_atualizadas += cur.rowcount
            else:
                # INSERT: nova parcela
                if dados_parcela:
                    campos = list(dados_parcela.keys())
                    placeholders = ', '.join(['%s'] * len(campos))
                    valores = list(dados_parcela.values())
                    
                    query = f"INSERT INTO gestao_financeira.ultra_liquidacoes ({', '.join(campos)}) VALUES ({placeholders})"
                    cur.execute(query, valores)
                    parcelas_inseridas += 1
        
        conn.commit()
        
        mensagem = []
        if parcelas_inseridas > 0:
            mensagem.append(f'{parcelas_inseridas} inserida(s)')
        if parcelas_atualizadas > 0:
            mensagem.append(f'{parcelas_atualizadas} atualizada(s)')
        if parcelas_excluidas > 0:
            mensagem.append(f'{parcelas_excluidas} excluída(s)')
        
        return jsonify({
            'success': True,
            'message': ', '.join(mensagem) if mensagem else 'Nenhuma alteração realizada',
            'parcelas_inseridas': parcelas_inseridas,
            'parcelas_atualizadas': parcelas_atualizadas,
            'parcelas_excluidas': parcelas_excluidas
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


# ⚠️ FUNÇÃO ANTIGA REMOVIDA - estava causando duplicação de parcelas
# A rota /api/salvar-cronograma agora é tratada por api_salvar_cronograma() (linha ~2300)
# que FAZ DELETE antes de INSERT, evitando duplicatas


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
    print("\n" + "="*80)
    print("💾 API SALVAR CRONOGRAMA CHAMADA")
    print("="*80)
    
    try:
        dados = request.get_json()
        print(f"📝 Dados recebidos: {dados.keys() if dados else 'None'}")
        
        numero_termo = dados.get('numero_termo')
        cronograma = dados.get('cronograma', [])
        info_alteracao = dados.get('info_alteracao', 'Base')
        
        print(f"🔑 numero_termo: {numero_termo}")
        print(f"📊 Total de meses no cronograma: {len(cronograma)}")
        print(f"🏷️ info_alteracao: {info_alteracao}")
        
        if not numero_termo or not cronograma:
            print("⚠️ Dados incompletos!")
            return jsonify({'success': False, 'error': 'Dados incompletos'}), 400
        
        conn = get_db()
        cur = get_cursor()
        
        print(f"🗑️ Deletando registros existentes para termo {numero_termo}...")
        # Deletar registros existentes para este termo
        cur.execute("""
            DELETE FROM gestao_financeira.ultra_liquidacoes_cronograma
            WHERE numero_termo = %s
        """, (numero_termo,))
        print(f"✅ Registros deletados")
        
        # Inserir novos registros
        print(f"📝 Inserindo {len(cronograma)} novos registros...")
        linhas_inseridas = 0
        email_usuario = session.get('username', 'Sistema')
        for idx, mes in enumerate(cronograma):
            if idx < 3:  # Log apenas os primeiros 3
                print(f"  - Mês {idx + 1}: {mes.get('nome_mes')} = {mes.get('valor_mes')} (info: {mes.get('info_alteracao', 'N/A')})")
            cur.execute("""
                INSERT INTO gestao_financeira.ultra_liquidacoes_cronograma
                (numero_termo, nome_mes, valor_mes_23, valor_mes_24, valor_mes, parcela_numero, info_alteracao, created_por, created_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                numero_termo,
                mes['nome_mes'],
                mes['valor_mes_23'],
                mes['valor_mes_24'],
                mes['valor_mes'],
                mes['parcela_numero'],
                info_alteracao,
                email_usuario
            ))
            linhas_inseridas += 1
        
        print(f"🔄 Executando COMMIT...")
        conn.commit()
        print(f"✅ COMMIT realizado com sucesso!")
        
        print(f"✅ Cronograma salvo: {linhas_inseridas} linhas inseridas")
        print("="*80)
        
        return jsonify({
            'success': True,
            'linhas_afetadas': linhas_inseridas
        })
        
    except Exception as e:
        print(f"\n❌ ERRO ao salvar cronograma:")
        print(f"❌ Tipo: {type(e).__name__}")
        print(f"❌ Mensagem: {str(e)}")
        import traceback
        print(f"❌ Traceback completo:")
        traceback.print_exc()
        print("="*80)
        
        if conn:
            print("🔄 Executando ROLLBACK...")
            conn.rollback()
            print("✅ ROLLBACK executado")
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
        cur = get_cursor()  # ⚡ CORRETO: usar get_cursor() que já tem RealDictCursor
        
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
        print(f"❌ ERRO em api_status_pagamento: {str(e)}")
        import traceback
        traceback.print_exc()
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


# ========== ENCAMINHAMENTO DE PAGAMENTO ==========

@ultra_liquidacoes_bp.route('/encaminhamento-pagamento/<path:numero_termo>')
@login_required
def encaminhamento_pagamento(numero_termo):
    """Página de seleção de parcelas para encaminhamento de pagamento"""
    return render_template('gestao_financeira/encaminhamento_pagamento.html', numero_termo=numero_termo)


@ultra_liquidacoes_bp.route('/api/parcelas-disponiveis-pagamento')
@login_required
def api_parcelas_disponiveis_pagamento():
    """API para listar parcelas disponíveis para encaminhamento de pagamento"""
    conn = None
    try:
        numero_termo = request.args.get('numero_termo', '')
        if not numero_termo:
            return jsonify({'success': False, 'error': 'Número do termo não fornecido'}), 400

        conn = get_db()
        cursor = conn.cursor()
        
        # Buscar parcelas:
        # - Status "Não Pago" OU ("Pago" E status_secundario "Parcial")
        # - Tipo "Programada" (não "Projetada")
        query = """
            SELECT 
                id,
                numero_termo,
                vigencia_inicial,
                vigencia_final,
                parcela_numero,
                parcela_status,
                parcela_status_secundario,
                parcela_tipo,
                valor_elemento_53_23,
                valor_elemento_53_24,
                valor_previsto
            FROM gestao_financeira.ultra_liquidacoes
            WHERE numero_termo = %s
              AND parcela_tipo = 'Programada'
              AND (
                  parcela_status = 'Não Pago'
                  OR parcela_status = 'Nao Pago'
                  OR (parcela_status = 'Pago' AND parcela_status_secundario = 'Parcial')
              )
            ORDER BY vigencia_inicial, parcela_numero
        """
        
        cursor.execute(query, (numero_termo,))
        rows = cursor.fetchall()
        
        parcelas = []
        for row in rows:
            parcelas.append({
                'id': row[0],
                'numero_termo': row[1],
                'vigencia_inicial': row[2].strftime('%d/%m/%Y') if row[2] else '',
                'vigencia_final': row[3].strftime('%d/%m/%Y') if row[3] else '',
                'parcela_numero': row[4],
                'parcela_status': row[5],
                'parcela_status_secundario': row[6],
                'parcela_tipo': row[7],
                'valor_elemento_53_23': float(row[8]) if row[8] else 0.0,
                'valor_elemento_53_23_fmt': formatar_moeda_br(row[8]) if row[8] else 'R$ 0,00',
                'valor_elemento_53_24': float(row[9]) if row[9] else 0.0,
                'valor_elemento_53_24_fmt': formatar_moeda_br(row[9]) if row[9] else 'R$ 0,00',
                'valor_previsto': float(row[10]) if row[10] else 0.0,
                'valor_previsto_fmt': formatar_moeda_br(row[10]) if row[10] else 'R$ 0,00',
            })
        
        return jsonify({'success': True, 'parcelas': parcelas})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@ultra_liquidacoes_bp.route('/gerar-encaminhamento-pagamento')
@login_required
def gerar_encaminhamento_pagamento():
    """Gera o documento de encaminhamento de pagamento com placeholders substituídos"""
    conn = None
    try:
        numero_termo = request.args.get('numero_termo', '')
        parcela_ids_str = request.args.get('parcela_ids', '')
        
        if not numero_termo or not parcela_ids_str:
            return "Parâmetros inválidos", 400
        
        parcela_ids = [int(x.strip()) for x in parcela_ids_str.split(',') if x.strip().isdigit()]
        if not parcela_ids:
            return "Nenhuma parcela selecionada", 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Buscar modelo de texto (id=20)
        cursor.execute("""
            SELECT modelo_texto 
            FROM categoricas.c_geral_modelo_textos 
            WHERE id = 20
        """)
        modelo_row = cursor.fetchone()
        if not modelo_row or not modelo_row[0]:
            return "Modelo de texto (ID 20) não encontrado", 404
        
        modelo_html = modelo_row[0]
        
        # 2. Buscar parcelas selecionadas
        placeholders = ','.join(['%s'] * len(parcela_ids))
        query_parcelas = f"""
            SELECT 
                id, numero_termo, vigencia_inicial, vigencia_final,
                parcela_numero, valor_previsto, 
                valor_elemento_53_23, valor_elemento_53_24
            FROM gestao_financeira.ultra_liquidacoes
            WHERE id IN ({placeholders})
            ORDER BY vigencia_inicial, parcela_numero
        """
        cursor.execute(query_parcelas, tuple(parcela_ids))
        parcelas_rows = cursor.fetchall()
        
        if not parcelas_rows:
            return "Parcelas não encontradas", 404
        
        # 3. Buscar dados da parceria (apenas portaria, coordenação vem do numero_termo)
        cursor.execute("""
            SELECT 
                numero_termo, portaria
            FROM public.parcerias
            WHERE numero_termo = %s
        """, (numero_termo,))
        parceria_row = cursor.fetchone()
        
        if not parceria_row:
            return f"Parceria {numero_termo} não encontrada", 404
        
        # Extrair coordenação do numero_termo (ex: TCL/004/2024/SMDHC/SESANA -> SESANA)
        partes_termo = numero_termo.split('/')
        coordenacao = partes_termo[-1] if len(partes_termo) > 0 else ''
        
        portaria = parceria_row[1] if parceria_row[1] else ''
        
        # 4. Buscar dados do SEI (termo original e aditamento)
        cursor.execute("""
            SELECT aditamento, termo_sei_doc
            FROM public.parcerias_sei
            WHERE numero_termo = %s
            ORDER BY id
        """, (numero_termo,))
        sei_rows = cursor.fetchall()
        
        sei_termo = ''
        numero_aditamento = ''
        sei_aditamento = ''
        
        # Buscar SEI do termo original (aditamento = "-")
        for row in sei_rows:
            if row[0] == '-':
                sei_termo = row[1] if row[1] else ''
                break
        
        # Buscar ÚLTIMO aditamento numérico (maior número)
        aditamentos_validos = []
        for row in sei_rows:
            if row[0] and row[0] != '-':
                try:
                    num_aditamento = int(row[0])
                    aditamentos_validos.append((num_aditamento, row[0], row[1]))
                except ValueError:
                    # Se não for número, adicionar mesmo assim
                    aditamentos_validos.append((0, row[0], row[1]))
        
        if aditamentos_validos:
            # Ordenar por número (maior primeiro) e pegar o primeiro da lista
            aditamentos_validos.sort(key=lambda x: x[0], reverse=True)
            ultimo_aditamento = aditamentos_validos[0]
            numero_aditamento = ultimo_aditamento[1]  # Texto original do aditamento
            sei_aditamento = ultimo_aditamento[2] if ultimo_aditamento[2] else ''
        
        # 5. Calcular valores e ranges das parcelas
        vigencias_iniciais = [row[2] for row in parcelas_rows if row[2]]
        vigencias_finais = [row[3] for row in parcelas_rows if row[3]]
        
        mes_vigencia_inicial = ''
        mes_vigencia_final = ''
        
        if vigencias_iniciais and vigencias_finais:
            data_inicial_min = min(vigencias_iniciais)
            data_final_max = max(vigencias_finais)
            
            # Mapeamento de meses completos
            meses_completo = {
                1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril', 5: 'maio', 6: 'junho',
                7: 'julho', 8: 'agosto', 9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
            }
            
            # Se mesmo mês/ano, usar formato "janeiro de 2026"
            if data_inicial_min.month == data_final_max.month and data_inicial_min.year == data_final_max.year:
                mes_vigencia_inicial = formatar_data_mes_ano(data_inicial_min, formato_completo=True)
                mes_vigencia_final = ''  # Vazio para remover bloco condicional
            # Se mesmo ano mas meses diferentes, usar "janeiro a fevereiro de 2026"
            elif data_inicial_min.year == data_final_max.year:
                mes_inicial = meses_completo.get(data_inicial_min.month, '')
                mes_final = meses_completo.get(data_final_max.month, '')
                mes_vigencia_inicial = f"{mes_inicial} a {mes_final} de {data_inicial_min.year}"
                mes_vigencia_final = ''  # Vazio pois já está tudo em mes_vigencia_inicial
            # Se anos diferentes, usar formato abreviado "jan/26 a dez/27"
            else:
                mes_vigencia_inicial = formatar_data_mes_ano(data_inicial_min)
                mes_vigencia_final = formatar_data_mes_ano(data_final_max)
        
        # Calcular total previsto
        total_previsto = sum([float(row[5]) if row[5] else 0.0 for row in parcelas_rows])
        
        # Formatar n_parcela usando texto direto do banco (já vem formatado)
        parcelas_texto = sorted(set([row[4] for row in parcelas_rows if row[4]]))
        n_parcela = formatar_lista_parcelas(parcelas_texto)
        
        # Verificar se alguma parcela é "1ª Parcela" (para condicional de glosa/retenção)
        tem_primeira_parcela = any('1ª Parcela' in p for p in parcelas_texto)
        
        # Gerar linhas da tabela de parcelas
        linhas_tabela_html = gerar_linhas_tabela_parcelas(parcelas_rows)
        
        # 6. Buscar empenhos correspondentes
        cursor.execute("""
            SELECT 
                nota_empenho_23, sei_nota_empenho_23, total_empenhado_23,
                nota_empenho_24, sei_nota_empenho_24, total_empenhado_24
            FROM gestao_financeira.temp_acomp_empenhos
            WHERE numero_termo = %s
        """, (numero_termo,))
        empenhos_row = cursor.fetchone()
        
        n_empenho_23 = ''
        sei_empenho_23 = ''
        n_empenho_24 = ''
        sei_empenho_24 = ''
        
        if empenhos_row:
            # Comparar valores para confirmar correspondência
            total_empenhado_23 = float(empenhos_row[2]) if empenhos_row[2] else 0.0
            total_empenhado_24 = float(empenhos_row[5]) if empenhos_row[5] else 0.0
            total_empenhado = total_empenhado_23 + total_empenhado_24
            
            # Tolerância de 0.01 para comparação
            if abs(total_empenhado - total_previsto) < 0.01:
                n_empenho_23 = empenhos_row[0] if empenhos_row[0] else ''
                sei_empenho_23 = empenhos_row[1] if empenhos_row[1] else ''
                n_empenho_24 = empenhos_row[3] if empenhos_row[3] else ''
                sei_empenho_24 = empenhos_row[4] if empenhos_row[4] else ''
        
        # 7. Mapear coordenação com regra SESANA (passa numero_termo para identificar TCL vs TFM)
        coordenacao_formatada = mapear_coordenacao(coordenacao, numero_termo)
        
        # 8. Converter valor para extenso
        valor_extenso = valor_por_extenso(total_previsto)
        
        # 9. Construir texto dos empenhos dinamicamente
        texto_empenhos = []
        if n_empenho_23 and sei_empenho_23:
            texto_empenhos.append(f"nº {n_empenho_23} sob SEI nº {sei_empenho_23}")
        if n_empenho_24 and sei_empenho_24:
            texto_empenhos.append(f"nº {n_empenho_24} sob SEI nº {sei_empenho_24}")
        
        # Formatação final do texto de empenhos
        # Suporta 1, 2, 3 ou mais empenhos com formatação correta
        if len(texto_empenhos) == 0:
            texto_empenhos_formatado = ""  # Nenhum empenho
        elif len(texto_empenhos) == 1:
            texto_empenhos_formatado = texto_empenhos[0]
        elif len(texto_empenhos) == 2:
            texto_empenhos_formatado = f"{texto_empenhos[0]} e {texto_empenhos[1]}"
        else:
            # 3 ou mais: "nº X sob SEI Y, nº A sob SEI B e nº C sob SEI D"
            texto_empenhos_formatado = ", ".join(texto_empenhos[:-1]) + " e " + texto_empenhos[-1]
        
        # DEBUG: Log valores importantes
        print(f"\n=== DEBUG ENCAMINHAMENTO PAGAMENTO ===")
        print(f"Termo: {numero_termo}")
        print(f"Aditamentos encontrados: {sei_rows}")
        print(f"numero_aditamento: '{numero_aditamento}'")
        print(f"sei_aditamento: '{sei_aditamento}'")
        print(f"mes_vigencia_inicial: '{mes_vigencia_inicial}'")
        print(f"mes_vigencia_final: '{mes_vigencia_final}'")
        print(f"\n--- EMPENHOS ---")
        print(f"n_empenho_23: '{n_empenho_23}'")
        print(f"sei_empenho_23: '{sei_empenho_23}'")
        print(f"n_empenho_24: '{n_empenho_24}'")
        print(f"sei_empenho_24: '{sei_empenho_24}'")
        print(f"=====================================\n")
        
        # 10. Substituir placeholders
        replacements = {
            'COORDENAÇÃO_INFORMADO_USUARIO': coordenacao_formatada,
            'numero_termo_usuario': numero_termo,
            'n_parcela_usuario': n_parcela,
            'mes_vigencia_inicial_usuario': mes_vigencia_inicial,
            'mês_vigência_final_usuario': mes_vigencia_final,
            'info_aditamento_usuario': numero_aditamento,  # Para bloco condicional do aditamento
            'numero_aditamento_usuario': numero_aditamento,
            'sei_aditamento_usuario': sei_aditamento,
            'sei_termo_usuario': sei_termo,
            'total_previsto_usuario': formatar_moeda_br(total_previsto),
            'valor_extenso': valor_extenso,
            'n_empenho_23_usuario': n_empenho_23,
            'sei_empenho_23_usuario': sei_empenho_23,
            'n_empenho_24_usuario': n_empenho_24,
            'sei_empenho_24_usuario': sei_empenho_24,
            'texto_empenhos_formatado': texto_empenhos_formatado,  # Novo placeholder com texto completo
            'portaria_usuario': portaria,
        }
        
        print(f"\n--- DEBUG PLACEHOLDERS ---")
        print(f"Total de placeholders: {len(replacements)}")
        
        # Verificar se placeholders de empenho existem no HTML
        placeholders_empenho = ['n_empenho_23_usuario', 'sei_empenho_23_usuario', 'n_empenho_24_usuario', 'sei_empenho_24_usuario']
        for ph in placeholders_empenho:
            existe = ph in modelo_html
            valor = replacements.get(ph, 'N/A')
            print(f"  • {ph}: existe no modelo? {existe}, valor='{valor}'")
        
        # Mostrar trecho do modelo onde aparece 'empenho'
        if 'empenho' in modelo_html.lower():
            idx = modelo_html.lower().find('empenho')
            trecho = modelo_html[max(0, idx-100):min(len(modelo_html), idx+300)]
            print(f"\n--- TRECHO DO MODELO COM 'EMPENHO' (400 chars) ---")
            print(f"{trecho}")
            print(f"--------------------------------------------------\n")
        
        # Substituir placeholders normais (sem chaves duplas)
        html_final = modelo_html
        substituicoes_realizadas = 0
        for placeholder, valor in replacements.items():
            ocorrencias = html_final.count(placeholder)
            if ocorrencias > 0:
                html_final = html_final.replace(placeholder, str(valor))
                substituicoes_realizadas += 1
                if placeholder in placeholders_empenho:
                    print(f"  ✓ '{placeholder}' substituído ({ocorrencias}x)")
            elif placeholder in placeholders_empenho:
                print(f"  ✗ '{placeholder}' NÃO ENCONTRADO no modelo")
        
        print(f"\nTotal de substituições realizadas: {substituicoes_realizadas}/{len(replacements)}")
        
        # 11. Substituir placeholder da tabela de parcelas
        html_final = html_final.replace('<!-- LINHAS_TABELA_PARCELAS -->', linhas_tabela_html)
        
        # 12. Remover parágrafos condicionais se houver "1ª Parcela"
        if tem_primeira_parcela:
            html_final = remover_bloco_condicional(html_final, 
                '<!-- CONDICIONAL_GLOSA_RETENCAO_INICIO -->', 
                '<!-- CONDICIONAL_GLOSA_RETENCAO_FIM -->')
        
        # 13. Processar texto opcional com colchetes
        # Formato: [info_aditamento_usuario: texto aqui]
        # Se info_aditamento_usuario tiver valor, mantém o texto; senão, remove o bloco inteiro
        html_final = processar_texto_opcional(html_final, replacements)
        
        # Renderizar template com formatação SEI completa
        return render_template(
            'gestao_financeira/documento_encaminhamento.html',
            numero_termo=numero_termo,
            html_content=html_final
        )
        
    except Exception as e:
        import traceback
        return f"Erro ao gerar documento: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500
    finally:
        if conn:
            conn.close()


# ========== FUNÇÕES AUXILIARES PARA ENCAMINHAMENTO ==========

def formatar_lista_parcelas(parcelas_texto):
    """
    Formata lista de parcelas (aceita texto já formatado do banco):
    ["1ª Parcela"] -> "1ª Parcela"
    ["1ª Parcela", "2ª Parcela"] -> "1ª e 2ª Parcela"
    ["1ª Parcela Complementar"] -> "1ª Parcela Complementar"
    """
    if not parcelas_texto:
        return ''
    
    # Se for apenas uma parcela, retornar o texto direto
    if len(parcelas_texto) == 1:
        return parcelas_texto[0]
    
    # Se tiver múltiplas parcelas, concatenar
    elif len(parcelas_texto) == 2:
        return f"{parcelas_texto[0]} e {parcelas_texto[1]}"
    else:
        partes = ', '.join(parcelas_texto[:-1])
        return f"{partes} e {parcelas_texto[-1]}"


def mapear_coordenacao(coordenacao, numero_termo=''):
    """
    Mapeia coordenação para formato do documento com caminho completo SEI.
    Regra especial SESANA:
    - TCL + SESANA -> SMDHC/SESANA/COSAN/RCE
    - TFM + SESANA -> SMDHC/SESANA/COSAN/EMENDAS
    """
    MAPA_COORDENACOES_SETOR = {
        'DP': 'SMDHC/DP',
        'CPCA': 'SMDHC/CPDDH/CPCA',
        'CPIR': 'SMDHC/CPDDH/CPIR',
        'CPJ': 'SMDHC/CPDDH/CPJ',
        'CPLGBTI': 'SMDHC/CPDDH/CPLGBTI',
        'CPPI': 'SMDHC/CPDDH/CPPI/EM',
        'CPM': 'SMDHC/CPDDH/CPM',
        'CPDDH': 'SMDHC/CPDDH',
        'COSAN': 'SMDHC/SESANA/COSAN/EMENDAS',
        'COPIND': 'SMDHC/CPDDH/COPIND',
        'ODH': 'SMDHC/CPDDH/ODH',
        'DPS': 'SMDHC/CPDDH/DPS',
        'CPD': 'SMDHC/CPDDH/CPD',
        'Eventos': 'SMDHC/GAB/AEV',
        'CAF': 'SMDHC/CAF',
        'EGRESSOS': 'SMDHC/CPDDH/CPEF',
        'DEDH': 'SMDHC/CPDDH/CEDH',
        'CEDH': 'SMDHC/CPDDH/CEDH',
        'CPIPTD': 'SMDHC/CPDDH/CPIPTD',
        'CIDADESOLIDÁRIA': 'SMDHC/SESANA/COSAN/EMENDAS',
        'CPPSR': 'SMDHC/CPDDH/CPPSR',
        'FUMCAD': 'SMDHC/CPDDH/CPCA/FUMCAD',
        'FMID': 'SMDHC/CPDDH/CPPI'
    }
    
    coordenacao_upper = coordenacao.strip().upper() if coordenacao else ''
    
    # Regra especial para SESANA: depende do tipo de termo (TCL vs TFM)
    if coordenacao_upper == 'SESANA':
        tipo_termo = numero_termo.split('/')[0].upper() if numero_termo else ''
        if tipo_termo == 'TCL':
            return 'SMDHC/SESANA/COSAN/RCE'
        else:  # TFM ou outros
            return 'SMDHC/SESANA/COSAN/EMENDAS'
    
    # Buscar no mapa (case-sensitive primeiro, depois case-insensitive)
    if coordenacao in MAPA_COORDENACOES_SETOR:
        return MAPA_COORDENACOES_SETOR[coordenacao]
    
    # Fallback para busca case-insensitive
    for key, value in MAPA_COORDENACOES_SETOR.items():
        if key.upper() == coordenacao_upper:
            return value
    
    # Se não encontrou, retornar com SMDHC/ na frente
    return f'SMDHC/{coordenacao}' if coordenacao else 'SMDHC'


def gerar_linhas_tabela_parcelas(parcelas_rows):
    """
    Gera as linhas HTML da tabela de parcelas para encaminhamento de pagamento.
    
    Estrutura de parcelas_rows:
    (id, numero_termo, vigencia_inicial, vigencia_final, 
     parcela_numero, valor_previsto, valor_elemento_53_23, valor_elemento_53_24)
    """
    linhas = []
    
    for row in parcelas_rows:
        parcela_numero = row[4] if row[4] else ''
        valor_53_23 = float(row[6]) if row[6] else 0.0
        valor_53_24 = float(row[7]) if row[7] else 0.0
        valor_previsto = float(row[5]) if row[5] else 0.0
        vigencia_inicial = row[2]
        vigencia_final = row[3]
        
        # Formatar valores monetários
        valor_53_23_fmt = formatar_moeda_br(valor_53_23)
        valor_53_24_fmt = formatar_moeda_br(valor_53_24)
        valor_previsto_fmt = formatar_moeda_br(valor_previsto)
        
        # Formatar datas
        vigencia_inicial_fmt = formatar_data_mes_ano(vigencia_inicial) if vigencia_inicial else ''
        vigencia_final_fmt = formatar_data_mes_ano(vigencia_final) if vigencia_final else ''
        
        # Construir linha da tabela
        linha_html = f'''        <tr>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; padding: 5px; text-align: center;">
                <p class="Tabela_Texto_Centralizado">{parcela_numero}</p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; padding: 5px; text-align: center;">
                <p class="Tabela_Texto_Centralizado">{valor_53_23_fmt}</p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; padding: 5px; text-align: center;">
                <p class="Tabela_Texto_Centralizado">{valor_53_24_fmt}</p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; padding: 5px; text-align: center;">
                <p class="Tabela_Texto_Centralizado">{valor_previsto_fmt}</p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; padding: 5px; text-align: center;">
                <p class="Tabela_Texto_Centralizado">{vigencia_inicial_fmt}</p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; padding: 5px; text-align: center;">
                <p class="Tabela_Texto_Centralizado">{vigencia_final_fmt}</p>
            </td>
        </tr>'''
        
        linhas.append(linha_html)
    
    return '\n'.join(linhas)


def remover_bloco_condicional(html, marcador_inicio, marcador_fim):
    """
    Remove um bloco de HTML entre dois marcadores (inclusive os marcadores).
    
    Args:
        html: String HTML completa
        marcador_inicio: Comentário HTML de início (ex: <!-- CONDICIONAL_INICIO -->)
        marcador_fim: Comentário HTML de fim (ex: <!-- CONDICIONAL_FIM -->)
    
    Returns:
        HTML com o bloco removido
    """
    inicio = html.find(marcador_inicio)
    fim = html.find(marcador_fim)
    
    if inicio != -1 and fim != -1 and inicio < fim:
        # Remover desde o início do marcador_inicio até o fim do marcador_fim
        fim_completo = fim + len(marcador_fim)
        html = html[:inicio] + html[fim_completo:]
    
    return html


    # Tentar case-insensitive
    for sigla, caminho in MAPA_COORDENACOES_SETOR.items():
        if sigla.upper() == coordenacao_upper:
            return caminho
    
    # Se não encontrou, retornar original
    return coordenacao if coordenacao else ''


def valor_por_extenso(valor):
    """
    Converte valor numérico para extenso em português.
    Exemplo: 150000.00 -> "cento e cinquenta mil reais"
    """
    try:
        from num2words import num2words
        valor_int = int(valor)
        valor_centavos = int((valor - valor_int) * 100)
        
        extenso_reais = num2words(valor_int, lang='pt_BR')
        
        if valor_centavos > 0:
            extenso_centavos = num2words(valor_centavos, lang='pt_BR')
            return f"{extenso_reais} reais e {extenso_centavos} centavos"
        else:
            return f"{extenso_reais} reais"
    except ImportError:
        # Fallback se num2words não estiver disponível
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def processar_texto_opcional(html, replacements):
    """
    Processa blocos opcionais no formato: [variavel: texto com variavel]
    Se 'variavel' tiver valor em replacements, mantém o texto.
    Senão, remove o bloco inteiro (incluindo colchetes).
    """
    import re
    
    # Regex para capturar APENAS variáveis válidas: letras, números, underscores, acentos
    # Deve começar com letra e ter pelo menos 3 caracteres para evitar capturar números soltos ou HTML
    pattern = r'\[([a-zA-ZÀ-ÿ_][a-zA-ZÀ-ÿ0-9_]{2,}):\s*(.*?)\]'
    
    def substituir(match):
        variavel = match.group(1).strip()  # Remover espaços do nome da variável
        texto = match.group(2)
        
        print(f"[DEBUG processar_texto_opcional] Encontrado bloco: [{variavel}: {texto[:50]}...]")
        
        # Verificar se variável tem valor
        valor = replacements.get(variavel, '')
        print(f"[DEBUG processar_texto_opcional] Variável '{variavel}' = '{valor}'")
        
        if valor and str(valor).strip():
            # Substituir placeholders dentro do texto opcional (SEM chaves duplas)
            texto_processado = texto
            for placeholder, val in replacements.items():
                texto_processado = texto_processado.replace(placeholder, str(val))
            print(f"[DEBUG processar_texto_opcional] MANTENDO bloco (variável tem valor)")
            return texto_processado
        else:
            # Remover bloco inteiro
            print(f"[DEBUG processar_texto_opcional] REMOVENDO bloco (variável vazia)")
            return ''
    
    return re.sub(pattern, substituir, html, flags=re.DOTALL)


# ========== ROTAS PARA ANUÊNCIA DA PESSOA GESTORA ==========

@ultra_liquidacoes_bp.route('/gerar-anuencia-pessoa-gestora', methods=['POST'])
@login_required
def gerar_anuencia_pessoa_gestora():
    """
    Salva auditoria do encaminhamento e redireciona para geração da anuência
    """
    conn = None
    try:
        dados = request.get_json()
        numero_termo = dados.get('numero_termo', '')
        parcela_ids_str = dados.get('parcela_ids', '')
        sei_encaminhamento = dados.get('sei_encaminhamento', '')
        html_encaminhamento = dados.get('html_encaminhamento', '')
        
        if not all([numero_termo, parcela_ids_str, sei_encaminhamento, html_encaminhamento]):
            return jsonify({'success': False, 'error': 'Dados incompletos'}), 400
        
        parcela_ids = [int(x.strip()) for x in parcela_ids_str.split(',') if x.strip().isdigit()]
        if not parcela_ids:
            return jsonify({'success': False, 'error': 'Nenhuma parcela selecionada'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Buscar parcelas para obter parcela_numero
        placeholders = ','.join(['%s'] * len(parcela_ids))
        query_parcelas = f"""
            SELECT parcela_numero
            FROM gestao_financeira.ultra_liquidacoes
            WHERE id IN ({placeholders})
            ORDER BY vigencia_inicial, parcela_numero
        """
        cursor.execute(query_parcelas, tuple(parcela_ids))
        parcelas_rows = cursor.fetchall()
        
        # Agregar parcela_numero como "1ª Parcela;2ª Parcela;3ª Parcela"
        parcelas_texto = [row[0] for row in parcelas_rows if row[0]]
        parcela_numero_agregado = ';'.join(parcelas_texto)
        
        # Salvar em auditoria_memoria.auditoria_enc_pagamento
        usuario = session.get('usuario_nome', 'Sistema')
        cursor.execute("""
            INSERT INTO auditoria_memoria.auditoria_enc_pagamento
            (numero_termo, enc_pagamento_completo, created_por, created_em, numero_sei, parcela_numero)
            VALUES (%s, %s, %s, NOW(), %s, %s)
        """, (
            numero_termo,
            html_encaminhamento,
            usuario,
            sei_encaminhamento,
            parcela_numero_agregado
        ))
        
        conn.commit()
        
        # Redirecionar para página de anuência
        redirect_url = f"/gestao_financeira/ultra-liquidacoes/documento-anuencia-pessoa-gestora?numero_termo={numero_termo}&parcela_ids={parcela_ids_str}&sei_encaminhamento={sei_encaminhamento}"
        
        return jsonify({
            'success': True,
            'redirect_url': redirect_url
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        print(f"[ERRO] Erro ao processar anuência: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@ultra_liquidacoes_bp.route('/documento-anuencia-pessoa-gestora')
@login_required
def documento_anuencia_pessoa_gestora():
    """Gera o documento de anuência da pessoa gestora com placeholders substituídos"""
    conn = None
    try:
        numero_termo = request.args.get('numero_termo', '')
        parcela_ids_str = request.args.get('parcela_ids', '')
        sei_encaminhamento = request.args.get('sei_encaminhamento', '')
        
        if not numero_termo or not parcela_ids_str:
            return "Parâmetros inválidos", 400
        
        parcela_ids = [int(x.strip()) for x in parcela_ids_str.split(',') if x.strip().isdigit()]
        if not parcela_ids:
            return "Nenhuma parcela selecionada", 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Buscar modelo de texto (id=21)
        cursor.execute("""
            SELECT modelo_texto 
            FROM categoricas.c_geral_modelo_textos 
            WHERE id = 21
        """)
        modelo_row = cursor.fetchone()
        if not modelo_row or not modelo_row[0]:
            return "Modelo de texto (ID 21) não encontrado", 404
        
        modelo_html = modelo_row[0]
        
        # 2. Buscar parcelas selecionadas
        placeholders = ','.join(['%s'] * len(parcela_ids))
        query_parcelas = f"""
            SELECT 
                id, numero_termo, vigencia_inicial, vigencia_final,
                parcela_numero, valor_previsto, 
                valor_elemento_53_23, valor_elemento_53_24
            FROM gestao_financeira.ultra_liquidacoes
            WHERE id IN ({placeholders})
            ORDER BY vigencia_inicial, parcela_numero
        """
        cursor.execute(query_parcelas, tuple(parcela_ids))
        parcelas_rows = cursor.fetchall()
        
        if not parcelas_rows:
            return "Parcelas não encontradas", 404
        
        # 3. Buscar dados da parceria (portaria, coordenação e OSC)
        cursor.execute("""
            SELECT 
                numero_termo, portaria, osc
            FROM public.parcerias
            WHERE numero_termo = %s
        """, (numero_termo,))
        parceria_row = cursor.fetchone()
        
        if not parceria_row:
            return f"Parceria {numero_termo} não encontrada", 404
        
        # Extrair coordenação do numero_termo
        partes_termo = numero_termo.split('/')
        coordenacao = partes_termo[-1] if len(partes_termo) > 0 else ''
        
        portaria = parceria_row[1] if parceria_row[1] else ''
        osc = parceria_row[2] if parceria_row[2] else ''
        
        # 4. Buscar dados do SEI (termo original e aditamento)
        cursor.execute("""
            SELECT aditamento, termo_sei_doc
            FROM public.parcerias_sei
            WHERE numero_termo = %s
            ORDER BY id
        """, (numero_termo,))
        sei_rows = cursor.fetchall()
        
        sei_termo = ''
        numero_aditamento = ''
        sei_aditamento = ''
        
        # Buscar SEI do termo original
        for row in sei_rows:
            if row[0] == '-':
                sei_termo = row[1] if row[1] else ''
                break
        
        # Buscar ÚLTIMO aditamento numérico
        aditamentos_validos = []
        for row in sei_rows:
            if row[0] and row[0] != '-':
                try:
                    num_aditamento = int(row[0])
                    aditamentos_validos.append((num_aditamento, row[0], row[1]))
                except ValueError:
                    aditamentos_validos.append((0, row[0], row[1]))
        
        if aditamentos_validos:
            aditamentos_validos.sort(key=lambda x: x[0], reverse=True)
            ultimo_aditamento = aditamentos_validos[0]
            numero_aditamento = ultimo_aditamento[1]
            sei_aditamento = ultimo_aditamento[2] if ultimo_aditamento[2] else ''
        
        # 5. Calcular valores e ranges das parcelas
        vigencias_iniciais = [row[2] for row in parcelas_rows if row[2]]
        vigencias_finais = [row[3] for row in parcelas_rows if row[3]]
        
        mes_vigencia_inicial = ''
        mes_vigencia_final = ''
        
        if vigencias_iniciais and vigencias_finais:
            data_inicial_min = min(vigencias_iniciais)
            data_final_max = max(vigencias_finais)
            
            meses_completo = {
                1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril', 5: 'maio', 6: 'junho',
                7: 'julho', 8: 'agosto', 9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
            }
            
            if data_inicial_min.month == data_final_max.month and data_inicial_min.year == data_final_max.year:
                mes_vigencia_inicial = formatar_data_mes_ano(data_inicial_min, formato_completo=True)
                mes_vigencia_final = ''
            elif data_inicial_min.year == data_final_max.year:
                mes_inicial = meses_completo.get(data_inicial_min.month, '')
                mes_final = meses_completo.get(data_final_max.month, '')
                mes_vigencia_inicial = f"{mes_inicial} a {mes_final} de {data_inicial_min.year}"
                mes_vigencia_final = ''
            else:
                mes_vigencia_inicial = formatar_data_mes_ano(data_inicial_min)
                mes_vigencia_final = formatar_data_mes_ano(data_final_max)
        
        # Calcular total previsto
        total_previsto = sum([float(row[5]) if row[5] else 0.0 for row in parcelas_rows])
        
        # Formatar n_parcela
        parcelas_texto = sorted(set([row[4] for row in parcelas_rows if row[4]]))
        n_parcela = formatar_lista_parcelas(parcelas_texto)
        
        # 6. Mapear coordenação
        coordenacao_formatada = mapear_coordenacao(coordenacao, numero_termo)
        
        # 7. Converter valor para extenso
        valor_extenso = valor_por_extenso(total_previsto)
        
        # 8. Substituir placeholders
        replacements = {
            'n_parcela_usuario': n_parcela,
            'mes_vigencia_inicial_usuario': mes_vigencia_inicial,
            'mes_vigencia_final_usuario': mes_vigencia_final,
            'info_aditamento_usuario': numero_aditamento,
            'numero_aditamento_usuario': numero_aditamento,
            'sei_aditamento_usuario': sei_aditamento,
            'numero_termo_usuario': numero_termo,
            'sei_termo_usuario': sei_termo,
            'osc_usuario': osc,
            'total_previsto_usuario': formatar_moeda_br(total_previsto),
            'valor_extenso': valor_extenso,
            'encaminhamento da DAC': sei_encaminhamento,
        }
        
        # Substituir placeholders normais
        html_final = modelo_html
        for placeholder, valor in replacements.items():
            html_final = html_final.replace(placeholder, str(valor))
        
        # Processar texto opcional com colchetes
        html_final = processar_texto_opcional(html_final, replacements)
        
        # Renderizar template
        return render_template(
            'gestao_financeira/documento_anuencia.html',
            numero_termo=numero_termo,
            html_content=html_final,
            sei_encaminhamento=sei_encaminhamento
        )
        
    except Exception as e:
        import traceback
        return f"Erro ao gerar documento: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500
    finally:
        if conn:
            conn.close()


# ============================================================================
# ROTAS: CONSULTA DE ENCAMINHAMENTOS (AUDITORIA)
# ============================================================================

@ultra_liquidacoes_bp.route('/consultar-encaminhamentos', methods=['GET'])
@login_required
def consultar_encaminhamentos_page():
    """Página para consultar encaminhamentos de pagamento"""
    return render_template('gestao_financeira/consultar_encaminhamentos.html')


@ultra_liquidacoes_bp.route('/api/encaminhamentos', methods=['GET'])
@login_required
def listar_encaminhamentos():
    """
    Lista todos os encaminhamentos de pagamento salvos na auditoria
    com filtro opcional por número do termo
    """
    conn = None
    try:
        numero_termo_filtro = request.args.get('numero_termo', '').strip()
        
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query base
        query = """
            SELECT 
                id,
                numero_termo,
                created_por,
                created_em,
                numero_sei,
                parcela_numero,
                enc_pagamento_completo
            FROM auditoria_memoria.auditoria_enc_pagamento
        """
        
        params = []
        
        # Filtro por número do termo
        if numero_termo_filtro:
            query += " WHERE numero_termo ILIKE %s"
            params.append(f'%{numero_termo_filtro}%')
        
        # Ordenar por data mais recente
        query += " ORDER BY created_em DESC"
        
        cursor.execute(query, params)
        encaminhamentos = cursor.fetchall()
        
        # Converter para lista de dicts
        resultado = []
        for enc in encaminhamentos:
            resultado.append({
                'id': enc['id'],
                'numero_termo': enc['numero_termo'],
                'created_por': enc['created_por'],
                'created_em': enc['created_em'].isoformat() if enc['created_em'] else None,
                'numero_sei': enc['numero_sei'],
                'parcela_numero': enc['parcela_numero'],
                'enc_pagamento_completo': enc['enc_pagamento_completo']
            })
        
        return jsonify({
            'success': True,
            'encaminhamentos': resultado,
            'total': len(resultado)
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'trace': traceback.format_exc()
        }), 500
    finally:
        if conn:
            conn.close()


@ultra_liquidacoes_bp.route('/api/encaminhamentos-termos', methods=['GET'])
@login_required
def listar_termos_encaminhamentos():
    """
    Lista todos os números de termo únicos que possuem encaminhamentos salvos
    para usar no autocomplete do filtro
    """
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT DISTINCT numero_termo
            FROM auditoria_memoria.auditoria_enc_pagamento
            WHERE numero_termo IS NOT NULL
            ORDER BY numero_termo
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        termos = [row[0] for row in rows]
        
        return jsonify({
            'success': True,
            'termos': termos
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'trace': traceback.format_exc()
        }), 500
    finally:
        if conn:
            conn.close()
