# -*- coding: utf-8 -*-
"""
Rotas para Anuência da Pessoa Gestora
"""

from flask import request, jsonify, render_template
from routes.gestao_financeira_ultra_liquidacoes import (
    ultra_liquidacoes_bp, 
    login_required, 
    get_db, 
    get_cursor,
    formatar_moeda_br,
    formatar_data_mes_ano,
    formatar_lista_parcelas,
    mapear_coordenacao,
    valor_por_extenso,
    processar_texto_opcional,
    remover_bloco_condicional
)
from flask import session
from datetime import datetime


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
