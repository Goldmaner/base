"""
Blueprint de Gestão Financeira
Acompanhamento de Reservas, Empenhos e Controles Financeiros
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access

gestao_financeira_bp = Blueprint('gestao_financeira', __name__, url_prefix='/gestao_financeira')


@gestao_financeira_bp.route('/')
@login_required
@requires_access('gestao_financeira')
def index():
    """
    Página principal da Gestão Financeira
    Menu com opções de navegação
    """
    return render_template('gestao_financeira/gestao_financeira.html')


@gestao_financeira_bp.route('/reservas-empenhos')
@login_required
@requires_access('gestao_financeira')
def reservas_empenhos():
    """
    Acompanhamento de Reservas e Empenhos
    Exibe tabela com informações detalhadas de reservas e empenhos por parcela
    """
    cur = get_cursor()
    
    try:
        # Query será preenchida posteriormente
        # Por enquanto, retorna estrutura vazia
        registros = []
        
        cur.close()
        
        return render_template(
            'gestao_financeira/gestao_financeira_res_emp.html',
            registros=registros
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao carregar reservas e empenhos: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao carregar dados: {str(e)}', 'danger')
        return redirect(url_for('gestao_financeira.index'))


@gestao_financeira_bp.route('/api/termos', methods=['GET'])
@login_required
@requires_access('gestao_financeira')
def api_termos():
    """
    API para buscar termos únicos da tabela temp_reservas_empenhos
    Retorna lista de termos para Select2
    """
    q = request.args.get('q', '').strip()
    
    cur = get_cursor()
    
    try:
        # Buscar termos únicos que contenham o termo de busca
        if q:
            cur.execute("""
                SELECT DISTINCT numero_termo
                FROM gestao_financeira.temp_reservas_empenhos
                WHERE numero_termo ILIKE %s
                ORDER BY numero_termo
                LIMIT 50
            """, (f'%{q}%',))
        else:
            cur.execute("""
                SELECT DISTINCT numero_termo
                FROM gestao_financeira.temp_reservas_empenhos
                ORDER BY numero_termo
                LIMIT 50
            """)
        
        termos = cur.fetchall()
        
        # Formatar para Select2
        resultado = [{'id': row['numero_termo'], 'text': row['numero_termo']} 
                     for row in termos if row['numero_termo']]
        
        cur.close()
        return jsonify(resultado)
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar termos: {str(e)}")
        return jsonify([]), 500


@gestao_financeira_bp.route('/encaminhamento', methods=['GET'])
@login_required
@requires_access('gestao_financeira')
def encaminhamento():
    """
    Formulário para encaminhamento de reservas e empenhos
    Permite selecionar termo e parcelas para gerar documento automático
    """
    return render_template('gestao_financeira/gestao_financeira_encaminhamento.html')


@gestao_financeira_bp.route('/api/parcelas-termo', methods=['GET'])
@login_required
@requires_access('gestao_financeira')
def api_parcelas_termo():
    """
    API para buscar parcelas de um termo específico
    Retorna lista de parcelas disponíveis para seleção
    """
    numero_termo = request.args.get('numero_termo', '').strip()
    
    if not numero_termo:
        return jsonify([])
    
    cur = get_cursor()
    
    try:
        # Buscar parcelas do termo na tabela temp_reservas_empenhos
        cur.execute("""
            SELECT 
                numero_parcela,
                tipo_parcela,
                parcela_total_previsto,
                elemento_23,
                elemento_24
            FROM gestao_financeira.temp_reservas_empenhos
            WHERE numero_termo = %s
            ORDER BY numero_parcela
        """, (numero_termo,))
        
        parcelas = cur.fetchall()
        
        # Formatar resultado
        resultado = []
        for row in parcelas:
            resultado.append({
                'numero': row['numero_parcela'],
                'tipo': row['tipo_parcela'],
                'valor': float(row['parcela_total_previsto']) if row['parcela_total_previsto'] else None,
                'elemento_23': float(row['elemento_23']) if row['elemento_23'] else None,
                'elemento_24': float(row['elemento_24']) if row['elemento_24'] else None
            })
        
        cur.close()
        return jsonify(resultado)
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar parcelas: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify([]), 500


@gestao_financeira_bp.route('/encaminhamento/gerar', methods=['POST'])
@login_required
@requires_access('gestao_financeira')
def gerar_encaminhamento():
    """
    Gera documento de encaminhamento usando modelo_texto id 19
    Substitui campos específicos baseado nos dados do formulário
    """
    try:
        numero_termo = request.form.get('numero_termo', '').strip()
        parcelas_selecionadas = request.form.getlist('parcelas[]')
        
        if not numero_termo:
            flash('Número do termo é obrigatório!', 'danger')
            return redirect(url_for('gestao_financeira.encaminhamento'))
        
        if not parcelas_selecionadas:
            flash('Selecione pelo menos uma parcela!', 'danger')
            return redirect(url_for('gestao_financeira.encaminhamento'))
        
        cur = get_cursor()
        
        # Buscar modelo de texto id 19
        cur.execute("""
            SELECT modelo_texto
            FROM categoricas.c_geral_modelo_textos
            WHERE id = 19
        """)
        
        modelo = cur.fetchone()
        
        if not modelo:
            flash('Modelo de texto não encontrado (id 19)!', 'danger')
            cur.close()
            return redirect(url_for('gestao_financeira.encaminhamento'))
        
        texto_base = modelo['modelo_texto']
        
        # Buscar dados das parcelas selecionadas
        placeholders_parcelas = ','.join(['%s'] * len(parcelas_selecionadas))
        
        cur.execute(f"""
            SELECT 
                numero_termo,
                vigencia_inicial,
                vigencia_final,
                aditivo,
                numero_parcela,
                tipo_parcela,
                elemento_23,
                elemento_24,
                parcela_total_previsto
            FROM gestao_financeira.temp_reservas_empenhos
            WHERE numero_termo = %s
              AND numero_parcela IN ({placeholders_parcelas})
            ORDER BY numero_parcela
        """, [numero_termo] + parcelas_selecionadas)
        
        parcelas_dados = cur.fetchall()
        
        if not parcelas_dados:
            flash('Nenhuma parcela encontrada com os dados informados!', 'warning')
            cur.close()
            return redirect(url_for('gestao_financeira.encaminhamento'))
        
        # ========== SUBSTITUIÇÕES DE PLACEHOLDERS ==========
        
        # 1. Buscar informações de SEI do termo em parcerias_sei
        cur.execute("""
            SELECT termo_sei_doc, aditamento, apostilamento
            FROM public.parcerias_sei
            WHERE TRIM(numero_termo) = TRIM(%s)
            ORDER BY 
                CASE 
                    WHEN aditamento ~ '^[0-9]+$' THEN CAST(aditamento AS INTEGER)
                    ELSE 0
                END DESC,
                id DESC
        """, (numero_termo,))
        
        sei_records = cur.fetchall()
        
        # 2. Identificar SEI do termo original (aditamento="-" e apostilamento="-")
        sei_termo_original = None
        for record in sei_records:
            if record['aditamento'] == '-' and record['apostilamento'] == '-':
                sei_termo_original = record['termo_sei_doc']
                break
        
        # Se não encontrar com "-", pegar o primeiro disponível
        if not sei_termo_original and sei_records:
            sei_termo_original = sei_records[0]['termo_sei_doc']
        
        # 3. Identificar último aditamento (maior número diferente de "-")
        ultimo_aditamento = None
        sei_aditamento = None
        
        for record in sei_records:
            if record['aditamento'] != '-':
                # Tentar converter para número para pegar o maior
                try:
                    num_aditamento = int(record['aditamento'])
                    if ultimo_aditamento is None or num_aditamento > ultimo_aditamento:
                        ultimo_aditamento = num_aditamento
                        sei_aditamento = record['termo_sei_doc']
                except ValueError:
                    # Se não for número, considera como texto
                    if ultimo_aditamento is None:
                        ultimo_aditamento = record['aditamento']
                        sei_aditamento = record['termo_sei_doc']
                break  # Já ordenamos DESC, então o primeiro é o último/maior
        
        # 4. Calcular total previsto (soma das parcelas selecionadas)
        total_previsto = sum(
            float(p['parcela_total_previsto'] or 0) for p in parcelas_dados
        )
        total_previsto_formatado = f"R$ {total_previsto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # 5. Preparar texto base para substituições
        texto_final = texto_base
        
        # 6. SUBSTITUIÇÃO DO BLOCO CONDICIONAL DE ADITAMENTO
        # Padrão: [info_aditamento_usuario: texto aqui com placeholders]
        import re
        
        if ultimo_aditamento:
            # Há aditamento - substituir o bloco condicional pelo conteúdo
            def substituir_bloco_aditamento(match):
                conteudo_bloco = match.group(1)
                # Substituir placeholders dentro do bloco
                conteudo_bloco = conteudo_bloco.replace('numero_aditamento_usuario', str(ultimo_aditamento))
                conteudo_bloco = conteudo_bloco.replace('sei_aditamento_usuario', sei_aditamento or '')
                return conteudo_bloco
            
            texto_final = re.sub(
                r'\[info_aditamento_usuario:\s*(.*?)\]',
                substituir_bloco_aditamento,
                texto_final,
                flags=re.DOTALL
            )
        else:
            # Não há aditamento - remover o bloco condicional inteiro
            texto_final = re.sub(
                r'\[info_aditamento_usuario:.*?\]',
                '',
                texto_final,
                flags=re.DOTALL
            )
        
        # 7. SUBSTITUIR PLACEHOLDERS SIMPLES
        texto_final = texto_final.replace('numero_termo_usuario', numero_termo)
        texto_final = texto_final.replace('sei_termo_usuario', sei_termo_original or '')
        texto_final = texto_final.replace('total_previsto_usuario', total_previsto_formatado)
        
        # TODO: Substituir tabela de parcelas (próxima etapa)
        
        cur.close()
        
        # Renderizar página com HTML compilado
        return render_template(
            'gestao_financeira/gestao_financeira_resultado.html',
            texto_html=texto_final,
            numero_termo=numero_termo,
            parcelas=parcelas_dados
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao gerar encaminhamento: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao gerar encaminhamento: {str(e)}', 'danger')
        return redirect(url_for('gestao_financeira.encaminhamento'))
