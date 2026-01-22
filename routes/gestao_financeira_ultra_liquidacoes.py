# -*- coding: utf-8 -*-
"""
Blueprint para Gestão Financeira - Ultra Liquidações
Sistema de controle de parcelas com validações e filtros avançados
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_db, get_cursor
from datetime import datetime
from utils import login_required
from decimal import Decimal
import csv
import io

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


def parse_data_br(data_str):
    """Parse string dd/mm/yyyy para date"""
    if not data_str:
        return None
    try:
        return datetime.strptime(data_str, '%d/%m/%Y').date()
    except:
        return None


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
            SELECT DISTINCT p.osc, p.cnpj, p.sei_celeb, p.sei_pc
            FROM gestao_financeira.ultra_liquidacoes ul
            LEFT JOIN public.parcerias p ON p.numero_termo = ul.numero_termo
            WHERE p.osc IS NOT NULL OR p.cnpj IS NOT NULL 
               OR p.sei_celeb IS NOT NULL OR p.sei_pc IS NOT NULL
        """)
        
        oscs = set()
        cnpjs = set()
        seis_celeb = set()
        seis_pc = set()
        
        for r in cur.fetchall():
            if r['osc']:
                oscs.add(r['osc'])
            if r['cnpj']:
                cnpjs.add(r['cnpj'])
            if r['sei_celeb']:
                seis_celeb.add(r['sei_celeb'])
            if r['sei_pc']:
                seis_pc.add(r['sei_pc'])
        
        return jsonify({
            'success': True,
            'termos': sorted(list(termos)),
            'oscs': sorted(list(oscs)),
            'cnpjs': sorted(list(cnpjs)),
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
        filtro_data_pagamento = request.args.get('data_pagamento', '')
        filtro_observacoes = request.args.get('observacoes', '')
        filtro_osc = request.args.get('osc', '')
        filtro_cnpj = request.args.get('cnpj', '')
        filtro_sei_celeb = request.args.get('sei_celeb', '')
        filtro_sei_pc = request.args.get('sei_pc', '')
        filtro_status_secundarios = request.args.get('status_secundarios', '')
        
        # Filtro padrão: apenas parcelas "Programada" se usuário não especificar
        if not filtro_tipo:
            filtro_tipo = 'Programada'
        
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
        
        if filtro_vigencia_final:
            data = parse_data_br(filtro_vigencia_final)
            if data:
                where_filtros.append("ul.vigencia_final = %s")
                params.append(data)
        
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
        
        # Query principal
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
            LIMIT %s OFFSET %s
        """
        
        params.extend([por_pagina, (pagina - 1) * por_pagina])
        
        cur.execute(query, params)
        parcelas = cur.fetchall()
        
        # Contar total
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
            
            # Regra de pendência: Não Pago próximo do fim do mês (5 dias)
            if 'nao pago' in status_lower or 'não pago' in status_lower:
                # Calcular último dia do mês atual
                ultimo_dia_mes = calendar.monthrange(hoje.year, hoje.month)[1]
                fim_do_mes = datetime(hoje.year, hoje.month, ultimo_dia_mes).date()
                
                # Verificar se faltam 5 dias ou menos
                dias_restantes = (fim_do_mes - hoje).days
                if dias_restantes <= 5:
                    pendencias.append(f'Prazo: faltam {dias_restantes} dias para fim do mês')
            
            resultado.append({
                'id': p['id'],
                'vigencia_inicial': formatar_data_br(p['vigencia_inicial']),
                'vigencia_final': formatar_data_br(p['vigencia_final']),
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
                'sei_celeb': p['sei_celeb'] or '' if mostrar_sei_celeb else None,
                'sei_pc': p['sei_pc'] or '' if mostrar_sei_pc else None,
                'pendencias': pendencias,
                'pendencias_descricao': ' | '.join(pendencias) if pendencias else '',
                'tem_pendencia': len(pendencias) > 0
            })
        
        # Contar pendências por seção
        total_pendencias = sum(1 for r in resultado if r['tem_pendencia'])
        
        return jsonify({
            'success': True,
            'data': resultado,
            'total': total,
            'pagina': pagina,
            'por_pagina': por_pagina,
            'total_paginas': (total + por_pagina - 1) // por_pagina,
            'total_pendencias': total_pendencias
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
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Parcela atualizada com sucesso'})
    
    except Exception as e:
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
