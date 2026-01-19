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


@gestao_financeira_bp.route('/api/termos', methods=['GET'])
@login_required
@requires_access('gestao_financeira')
def api_termos():
    """
    API para buscar termos únicos da tabela temp_reservas_empenhos
    Exclui termos que já foram salvos em temp_acomp_empenhos
    Retorna lista de termos para Select2
    """
    q = request.args.get('q', '').strip()
    
    cur = get_cursor()
    
    try:
        # Buscar termos únicos que NÃO estão em temp_acomp_empenhos
        if q:
            cur.execute("""
                SELECT DISTINCT numero_termo
                FROM gestao_financeira.temp_reservas_empenhos
                WHERE numero_termo ILIKE %s
                  AND numero_termo NOT IN (
                      SELECT DISTINCT numero_termo 
                      FROM gestao_financeira.temp_acomp_empenhos
                  )
                ORDER BY numero_termo
                LIMIT 50
            """, (f'%{q}%',))
        else:
            cur.execute("""
                SELECT DISTINCT numero_termo
                FROM gestao_financeira.temp_reservas_empenhos
                WHERE numero_termo NOT IN (
                    SELECT DISTINCT numero_termo 
                    FROM gestao_financeira.temp_acomp_empenhos
                )
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
            # Verificar se aditamento não é None e não é '-'
            if record['aditamento'] and record['aditamento'] != '-':
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
        
        # 8. GERAR TABELA DE PARCELAS
        # Função auxiliar para formatar data como "mês-ano" (ex: "janeiro-25")
        def formatar_data_mes_ano(data_str):
            if not data_str:
                return ''
            try:
                from datetime import datetime
                data = datetime.strptime(str(data_str).split(' ')[0], '%Y-%m-%d')
                meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
                         'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
                mes_nome = meses[data.month - 1]
                ano = str(data.year)[-2:]  # Últimos 2 dígitos do ano
                return f"{mes_nome}-{ano}"
            except:
                return str(data_str)
        
        # Função auxiliar para formatar valor monetário
        def formatar_moeda(valor):
            if valor is None or valor == '':
                return 'R$ 0,00'
            try:
                valor_float = float(valor)
                return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            except:
                return 'R$ 0,00'
        
        # Gerar linhas da tabela
        linhas_tabela = []
        for parcela in parcelas_dados:
            vigencia_inicial = formatar_data_mes_ano(parcela['vigencia_inicial'])
            vigencia_final = formatar_data_mes_ano(parcela['vigencia_final'])
            aditivo = parcela['aditivo'] if parcela['aditivo'] else '-'
            termo = parcela['numero_termo']
            
            # Formatar parcela: número + tipo
            numero_parcela = parcela['numero_parcela']
            tipo_parcela = parcela['tipo_parcela'] if parcela['tipo_parcela'] else ''
            parcela_texto = f"{numero_parcela} {tipo_parcela}".strip()
            
            elemento_23 = formatar_moeda(parcela['elemento_23'])
            elemento_24 = formatar_moeda(parcela['elemento_24'])
            total_parcela = formatar_moeda(parcela['parcela_total_previsto'])
            
            # Criar linha HTML
            linha_html = f"""
                <tr>
                    <td style="border-bottom:1px solid #a3a3a3; vertical-align:top; padding:5px; border-top:1px solid #a3a3a3; border-right:1px solid #a3a3a3; border-left:1px solid #a3a3a3">
                        <p class="Tabela_Texto_Centralizado">{vigencia_inicial}</p>
                    </td>
                    <td style="border-bottom:1px solid #a3a3a3; vertical-align:top; padding:5px; border-top:1px solid #a3a3a3; border-right:1px solid #a3a3a3; border-left:1px solid #a3a3a3">
                        <p class="Tabela_Texto_Centralizado">{vigencia_final}</p>
                    </td>
                    <td style="border-bottom:1px solid #a3a3a3; vertical-align:top; padding:5px; border-top:1px solid #a3a3a3; border-right:1px solid #a3a3a3; border-left:1px solid #a3a3a3">
                        <p class="Tabela_Texto_Centralizado">{aditivo}</p>
                    </td>
                    <td style="border-bottom:1px solid #a3a3a3; vertical-align:top; padding:5px; border-top:1px solid #a3a3a3; border-right:1px solid #a3a3a3; border-left:1px solid #a3a3a3">
                        <p class="Tabela_Texto_Centralizado">{termo}</p>
                    </td>
                    <td style="border-bottom:1px solid #a3a3a3; vertical-align:top; padding:5px; border-top:1px solid #a3a3a3; border-right:1px solid #a3a3a3; border-left:1px solid #a3a3a3">
                        <p class="Tabela_Texto_Centralizado">{parcela_texto}</p>
                    </td>
                    <td style="border-bottom:1px solid #a3a3a3; vertical-align:top; padding:5px; border-top:1px solid #a3a3a3; border-right:1px solid #a3a3a3; border-left:1px solid #a3a3a3">
                        <p class="Tabela_Texto_Centralizado">{elemento_23}</p>
                    </td>
                    <td style="border-bottom:1px solid #a3a3a3; vertical-align:top; padding:5px; border-top:1px solid #a3a3a3; border-right:1px solid #a3a3a3; border-left:1px solid #a3a3a3">
                        <p class="Tabela_Texto_Centralizado">{elemento_24}</p>
                    </td>
                    <td style="border-bottom:1px solid #a3a3a3; vertical-align:top; padding:5px; border-top:1px solid #a3a3a3; border-right:1px solid #a3a3a3; border-left:1px solid #a3a3a3">
                        <p class="Tabela_Texto_Centralizado">{total_parcela}</p>
                    </td>
                </tr>
            """
            linhas_tabela.append(linha_html.strip())
        
        # Juntar todas as linhas
        tabela_completa = '\n'.join(linhas_tabela)
        
        # Substituir placeholder da tabela no texto
        # Padrão: Inserir após o cabeçalho da tabela (após </tr> do <thead>)
        # Ou usar um placeholder específico como <!-- LINHAS_TABELA_PARCELAS -->
        import re
        
        # Tentar encontrar a estrutura da tabela e inserir as linhas após o cabeçalho
        # Procurar por </tr> seguido de </thead> ou início do tbody
        padrao_tabela = r'(</tr>\s*</thead>\s*<tbody>)'
        
        if re.search(padrao_tabela, texto_final):
            texto_final = re.sub(
                padrao_tabela,
                r'\1\n' + tabela_completa,
                texto_final,
                count=1
            )
        else:
            # Se não encontrar, tentar outro padrão (comentário placeholder)
            texto_final = texto_final.replace('<!-- LINHAS_TABELA_PARCELAS -->', tabela_completa)
            # Ou substituir um marcador genérico
            texto_final = texto_final.replace('TABELA_PARCELAS_AQUI', tabela_completa)
        
        # ========== INSERIR NO RELATÓRIO DE ACOMPANHAMENTO ==========
        
        # Buscar nome do responsável (usuário logado)
        usuario_id = session.get('user_id')
        
        cur.execute("""
            SELECT u.d_usuario, u.email
            FROM gestao_pessoas.usuarios u
            WHERE u.id = %s
        """, (usuario_id,))
        
        usuario_data = cur.fetchone()
        responsavel_nome = "N/A"
        
        print(f"[DEBUG] Usuario ID: {usuario_id}")
        print(f"[DEBUG] Usuario data: {usuario_data}")
        
        if usuario_data and usuario_data['d_usuario']:
            # Formato em usuarios: "d843702"
            # Formato em c_dac_analistas: "843.702-5"
            # Remover o 'd' ou 'x' e limpar
            d_usuario_original = usuario_data['d_usuario']
            d_usuario_limpo = d_usuario_original.lower().replace('d', '').replace('x', '').strip()
            
            print(f"[DEBUG] d_usuario original: {d_usuario_original}")
            print(f"[DEBUG] d_usuario limpo: {d_usuario_limpo}")
            
            # Tentar buscar nome em c_dac_analistas
            # Comparar removendo pontos e hífens de ambos os lados
            cur.execute("""
                SELECT nome_analista, d_usuario
                FROM categoricas.c_dac_analistas
                WHERE REPLACE(REPLACE(REPLACE(LOWER(d_usuario), '.', ''), '-', ''), ' ', '') = %s
                  AND status = 'Ativo'
            """, (d_usuario_limpo,))
            
            analista_data = cur.fetchone()
            
            print(f"[DEBUG] Analista encontrado: {analista_data}")
            
            if analista_data:
                responsavel_nome = analista_data['nome_analista']
                print(f"[DEBUG] Responsável encontrado: {responsavel_nome}")
            else:
                # Fallback: usar email sem domínio
                email = usuario_data.get('email', '')
                if email:
                    # Extrair nome do email (parte antes do @)
                    responsavel_nome = email.split('@')[0].replace('.', ' ').title()
                    print(f"[DEBUG] Usando email como fallback: {responsavel_nome}")
                else:
                    responsavel_nome = d_usuario_original
                    print(f"[DEBUG] Usando d_usuario como fallback: {responsavel_nome}")
        
        # Inserir cada parcela selecionada na tabela de acompanhamento
        for idx, parcela in enumerate(parcelas_dados, start=1):
            cur.execute("""
                INSERT INTO gestao_financeira.temp_acomp_empenhos (
                    numero, aditivo, numero_termo, responsavel
                ) VALUES (%s, %s, %s, %s)
            """, (
                idx,
                parcela['aditivo'] or '-',
                numero_termo,
                responsavel_nome
            ))
        
        get_db().commit()
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


@gestao_financeira_bp.route('/relatorio-empenhos')
@login_required
@requires_access('gestao_financeira')
def relatorio_empenhos():
    """
    Relatório de Acompanhamento de Empenhos
    Exibe tabela editável com status e informações de empenho
    """
    return render_template('gestao_financeira/gestao_financeira_relatorio.html')


@gestao_financeira_bp.route('/api/relatorio-empenhos', methods=['GET'])
@login_required
@requires_access('gestao_financeira')
def api_relatorio_empenhos():
    """
    API para buscar dados do relatório de empenhos
    Suporta filtros por termo, responsável e status
    """
    cur = get_cursor()
    
    try:
        # Parâmetros de filtro
        termo = request.args.get('termo', '').strip()
        responsavel = request.args.get('responsavel', '').strip()
        status = request.args.get('status', '').strip()
        
        # Query base com JOIN para buscar numero_parcela
        query = """
            SELECT 
                t.id,
                t.numero,
                t.aditivo,
                t.numero_termo,
                t.responsavel,
                t.status,
                t.nota_empenho_23,
                t.sei_nota_empenho_23,
                t.nota_empenho_24,
                t.sei_nota_empenho_24,
                t.total_empenhado_23,
                t.total_empenhado_24,
                t.observacoes,
                t.criado_em,
                r.numero_parcela,
                r.tipo_parcela
            FROM gestao_financeira.temp_acomp_empenhos t
            LEFT JOIN LATERAL (
                SELECT numero_parcela, tipo_parcela
                FROM gestao_financeira.temp_reservas_empenhos
                WHERE numero_termo = t.numero_termo
                  AND (aditivo = t.aditivo OR (aditivo IS NULL AND t.aditivo = '-'))
                ORDER BY numero_parcela
                LIMIT 1 OFFSET (t.numero - 1)
            ) r ON true
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if termo:
            query += " AND numero_termo ILIKE %s"
            params.append(f'%{termo}%')
        
        if responsavel:
            query += " AND responsavel ILIKE %s"
            params.append(f'%{responsavel}%')
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY criado_em DESC, numero_termo, numero"
        
        cur.execute(query, params)
        registros = cur.fetchall()
        
        # Formatar dados para JSON
        resultado = []
        for r in registros:
            resultado.append({
                'id': r['id'],
                'numero': r['numero'],
                'aditivo': r['aditivo'],
                'numero_termo': r['numero_termo'],
                'responsavel': r['responsavel'],
                'status': r['status'],
                'nota_empenho_23': r['nota_empenho_23'],
                'sei_nota_empenho_23': r['sei_nota_empenho_23'] or '',
                'nota_empenho_24': r['nota_empenho_24'],
                'sei_nota_empenho_24': r['sei_nota_empenho_24'] or '',
                'total_empenhado_23': float(r['total_empenhado_23'] or 0),
                'total_empenhado_24': float(r['total_empenhado_24'] or 0),
                'observacoes': r['observacoes'] or '',
                'criado_em': r['criado_em'].strftime('%d/%m/%Y %H:%M') if r['criado_em'] else '',
                'numero_parcela': r['numero_parcela'] or '-',
                'tipo_parcela': r['tipo_parcela'] or ''
            })
        
        cur.close()
        
        return jsonify({
            'success': True,
            'data': resultado
        })
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar relatório: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gestao_financeira_bp.route('/api/atualizar-empenho/<int:id>', methods=['PUT'])
@login_required
@requires_access('gestao_financeira')
def api_atualizar_empenho(id):
    """
    API para atualizar um campo específico de um registro de empenho
    """
    cur = get_cursor()
    
    try:
        data = request.get_json()
        campo = data.get('campo')
        valor = data.get('valor')
        
        # Campos permitidos para atualização
        campos_permitidos = [
            'status', 'nota_empenho_23', 'sei_nota_empenho_23',
            'nota_empenho_24', 'sei_nota_empenho_24',
            'total_empenhado_23', 'total_empenhado_24', 'observacoes'
        ]
        
        if campo not in campos_permitidos:
            return jsonify({
                'success': False,
                'error': 'Campo não permitido para atualização'
            }), 400
        
        # Converter valores vazios para NULL
        if valor == '' or valor is None:
            valor = None
        
        # Executar update
        query = f"UPDATE gestao_financeira.temp_acomp_empenhos SET {campo} = %s WHERE id = %s"
        cur.execute(query, (valor, id))
        get_db().commit()
        cur.close()
        
        return jsonify({
            'success': True,
            'message': 'Campo atualizado com sucesso'
        })
        
    except Exception as e:
        print(f"[ERRO] Erro ao atualizar empenho: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gestao_financeira_bp.route('/api/excluir-empenho/<int:id>', methods=['DELETE'])
@login_required
@requires_access('gestao_financeira')
def api_excluir_empenho(id):
    """
    API para excluir um registro de empenho
    """
    cur = get_cursor()
    
    try:
        # Verificar se o registro existe
        cur.execute("""
            SELECT id FROM gestao_financeira.temp_acomp_empenhos
            WHERE id = %s
        """, (id,))
        
        if not cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Registro não encontrado'
            }), 404
        
        # Excluir registro
        cur.execute("""
            DELETE FROM gestao_financeira.temp_acomp_empenhos
            WHERE id = %s
        """, (id,))
        
        get_db().commit()
        cur.close()
        
        return jsonify({
            'success': True,
            'message': 'Registro excluído com sucesso'
        })
        
    except Exception as e:
        print(f"[ERRO] Erro ao excluir empenho: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gestao_financeira_bp.route('/ver-encaminhamento')
@login_required
@requires_access('gestao_financeira')
def ver_encaminhamento():
    """
    Reconstrói e exibe o encaminhamento de uma parcela específica do relatório
    """
    import re
    
    cur = get_cursor()
    
    try:
        numero_termo = request.args.get('termo', '').strip()
        numero_seq = request.args.get('numero', '').strip()  # Número sequencial do relatório
        
        if not numero_termo or not numero_seq:
            flash('Parâmetros inválidos!', 'danger')
            return redirect(url_for('gestao_financeira.relatorio_empenhos'))
        
        # Buscar informações do registro e numero_parcela via JOIN
        cur.execute("""
            SELECT 
                t.aditivo,
                r.numero_parcela
            FROM gestao_financeira.temp_acomp_empenhos t
            LEFT JOIN LATERAL (
                SELECT numero_parcela
                FROM gestao_financeira.temp_reservas_empenhos
                WHERE numero_termo = t.numero_termo
                  AND (aditivo = t.aditivo OR (aditivo IS NULL AND t.aditivo = '-'))
                ORDER BY numero_parcela
                LIMIT 1 OFFSET (t.numero - 1)
            ) r ON true
            WHERE t.numero_termo = %s AND t.numero = %s
            LIMIT 1
        """, (numero_termo, numero_seq))
        
        registro = cur.fetchone()
        
        if not registro or not registro['numero_parcela']:
            flash('Registro ou parcela não encontrada!', 'warning')
            return redirect(url_for('gestao_financeira.relatorio_empenhos'))
        
        # Pegar o numero_parcela do JOIN
        numero_parcela_real = registro['numero_parcela']
        
        print(f"[DEBUG] Ver encaminhamento - Termo: {numero_termo}, Seq: {numero_seq}, Parcela Real: {numero_parcela_real}")
        
        # Buscar modelo de texto (id 19)
        cur.execute("""
            SELECT modelo_texto
            FROM categoricas.c_geral_modelo_textos
            WHERE id = 19
        """)
        
        modelo = cur.fetchone()
        
        if not modelo:
            flash('Modelo de texto não encontrado (id 19)!', 'danger')
            cur.close()
            return redirect(url_for('gestao_financeira.relatorio_empenhos'))
        
        texto_base = modelo['modelo_texto']
        
        # Buscar dados da parcela específica usando numero_parcela real
        cur.execute("""
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
              AND numero_parcela = %s
            LIMIT 1
        """, (numero_termo, numero_parcela_real))
        
        parcela_dados = cur.fetchone()
        
        if not parcela_dados:
            flash('Parcela não encontrada na base de dados!', 'warning')
            cur.close()
            return redirect(url_for('gestao_financeira.relatorio_empenhos'))
        
        parcelas_dados = [parcela_dados]  # Colocar em lista para compatibilidade
        
        # ========== SUBSTITUIÇÕES DE PLACEHOLDERS (mesma lógica do gerar_encaminhamento) ==========
        
        # Buscar informações de SEI
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
        
        # Identificar SEI do termo original
        sei_termo_original = None
        for record in sei_records:
            if record['aditamento'] == '-' and record['apostilamento'] == '-':
                sei_termo_original = record['termo_sei_doc']
                break
        
        if not sei_termo_original and sei_records:
            sei_termo_original = sei_records[0]['termo_sei_doc']
        
        # Identificar último aditamento
        ultimo_aditamento = None
        sei_aditamento = None
        
        for record in sei_records:
            if record['aditamento'] != '-':
                try:
                    num_aditamento = int(record['aditamento'])
                    if ultimo_aditamento is None or num_aditamento > ultimo_aditamento:
                        ultimo_aditamento = num_aditamento
                        sei_aditamento = record['termo_sei_doc']
                except ValueError:
                    if ultimo_aditamento is None:
                        ultimo_aditamento = record['aditamento']
                        sei_aditamento = record['termo_sei_doc']
                break
        
        # Calcular total previsto
        total_previsto = float(parcela_dados['parcela_total_previsto'] or 0)
        total_previsto_formatado = f"R$ {total_previsto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # Substituições condicionais e simples (mesma lógica)
        texto_final = texto_base
        
        if ultimo_aditamento and sei_aditamento:
            padrao_condicional = r'\[info_aditamento_usuario:([^\]]+)\]'
            match = re.search(padrao_condicional, texto_final)
            if match:
                bloco_condicional = match.group(1)
                bloco_substituido = bloco_condicional.replace('numero_aditamento_usuario', str(ultimo_aditamento))
                bloco_substituido = bloco_substituido.replace('sei_aditamento_usuario', sei_aditamento or '')
                texto_final = re.sub(padrao_condicional, bloco_substituido, texto_final)
        else:
            texto_final = re.sub(r'\[info_aditamento_usuario:[^\]]+\]', '', texto_final)
        
        texto_final = texto_final.replace('numero_termo_usuario', numero_termo)
        texto_final = texto_final.replace('sei_termo_usuario', sei_termo_original or '')
        texto_final = texto_final.replace('total_previsto_usuario', total_previsto_formatado)
        
        # ========== GERAR TABELA ==========
        
        def formatar_data_mes_ano(data_str):
            if not data_str:
                return ''
            try:
                from datetime import datetime
                if isinstance(data_str, str):
                    data = datetime.strptime(data_str, '%Y-%m-%d')
                else:
                    data = data_str
                meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
                        'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
                mes_nome = meses[data.month - 1]
                ano_curto = str(data.year)[-2:]
                return f"{mes_nome}-{ano_curto}"
            except:
                return str(data_str)
        
        def formatar_moeda(valor):
            if valor is None or valor == '':
                return 'R$ 0,00'
            try:
                valor_float = float(valor)
                return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            except:
                return 'R$ 0,00'
        
        linhas_tabela = []
        for p in parcelas_dados:
            vigencia_inicial_fmt = formatar_data_mes_ano(p['vigencia_inicial'])
            vigencia_final_fmt = formatar_data_mes_ano(p['vigencia_final'])
            aditivo_text = p['aditivo'] if p['aditivo'] else '-'
            parcela_text = f"{p['numero_parcela']} ({p['tipo_parcela']})"
            elemento_23_fmt = formatar_moeda(p['elemento_23'])
            elemento_24_fmt = formatar_moeda(p['elemento_24'])
            total_fmt = formatar_moeda(p['parcela_total_previsto'])
            
            linha = f"""
            <tr>
                <td style="text-align: center;">{vigencia_inicial_fmt}</td>
                <td style="text-align: center;">{vigencia_final_fmt}</td>
                <td style="text-align: center;">{aditivo_text}</td>
                <td style="text-align: center;">{numero_termo}</td>
                <td style="text-align: center;">{parcela_text}</td>
                <td style="text-align: center;">{elemento_23_fmt}</td>
                <td style="text-align: center;">{elemento_24_fmt}</td>
                <td style="text-align: center;">{total_fmt}</td>
            </tr>
            """
            linhas_tabela.append(linha)
        
        tabela_html = '\n'.join(linhas_tabela)
        
        # Inserir tabela (3 estratégias)
        if '</thead>' in texto_final and '<tbody>' in texto_final:
            padrao_tbody = r'(</thead>\s*<tbody>)'
            texto_final = re.sub(padrao_tbody, r'\1' + tabela_html, texto_final, count=1)
        elif '<!-- LINHAS_TABELA_PARCELAS -->' in texto_final:
            texto_final = texto_final.replace('<!-- LINHAS_TABELA_PARCELAS -->', tabela_html)
        else:
            texto_final = texto_final.replace('TABELA_PARCELAS_AQUI', tabela_html)
        
        cur.close()
        
        # Renderizar página (mesmo template do resultado)
        return render_template(
            'gestao_financeira/gestao_financeira_resultado.html',
            texto_html=texto_final,
            numero_termo=numero_termo,
            parcelas=parcelas_dados
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao visualizar encaminhamento: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao visualizar encaminhamento: {str(e)}', 'danger')
        return redirect(url_for('gestao_financeira.relatorio_empenhos'))
