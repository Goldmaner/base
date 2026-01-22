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
    Inclui estatísticas de parcelas e termos enviados
    """
    cur = get_cursor()
    
    try:
        # Estatística 1: Parcelas enviadas vs total
        cur.execute("SELECT COUNT(*) as total FROM gestao_financeira.temp_acomp_empenhos")
        parcelas_enviadas = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as total FROM gestao_financeira.temp_reservas_empenhos")
        parcelas_total = cur.fetchone()['total']
        
        percentual_parcelas = (parcelas_enviadas / parcelas_total * 100) if parcelas_total > 0 else 0
        
        # Estatística 2: Termos únicos enviados vs total
        cur.execute("SELECT COUNT(DISTINCT numero_termo) as total FROM gestao_financeira.temp_acomp_empenhos")
        termos_enviados = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(DISTINCT numero_termo) as total FROM gestao_financeira.temp_reservas_empenhos")
        termos_total = cur.fetchone()['total']
        
        percentual_termos = (termos_enviados / termos_total * 100) if termos_total > 0 else 0
        
        cur.close()
        
        return render_template(
            'gestao_financeira/gestao_financeira_relatorio.html',
            parcelas_enviadas=parcelas_enviadas,
            parcelas_total=parcelas_total,
            percentual_parcelas=percentual_parcelas,
            termos_enviados=termos_enviados,
            termos_total=termos_total,
            percentual_termos=percentual_termos
        )
        
    except Exception as e:
        print(f"[ERRO] relatorio_empenhos: {str(e)}")
        return render_template(
            'gestao_financeira/gestao_financeira_relatorio.html',
            parcelas_enviadas=0,
            parcelas_total=0,
            percentual_parcelas=0,
            termos_enviados=0,
            termos_total=0,
            percentual_termos=0
        )


@gestao_financeira_bp.route('/api/relatorio-empenhos-termos', methods=['GET'])
@login_required
@requires_access('gestao_financeira')
def api_relatorio_empenhos_termos():
    """
    API para buscar lista de termos disponíveis em temp_acomp_empenhos
    """
    cur = get_cursor()
    
    try:
        cur.execute("""
            SELECT DISTINCT numero_termo 
            FROM gestao_financeira.temp_acomp_empenhos 
            WHERE numero_termo IS NOT NULL 
            ORDER BY numero_termo
        """)
        
        termos = [r['numero_termo'] for r in cur.fetchall()]
        
        cur.close()
        
        return jsonify({
            'success': True,
            'termos': termos
        })
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar termos: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
        
        # Query base com JOIN para buscar numero_parcela e processo de celebração
        query = """
            SELECT 
                t.id,
                t.numero,
                t.aditivo,
                t.numero_termo,
                p.sei_celeb AS processo_celebracao,
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
            LEFT JOIN public.parcerias p ON p.numero_termo = t.numero_termo
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
                'processo_celebracao': r['processo_celebracao'] or '',
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


# ============================================================================
# RELATÓRIOS SOF - IMPORTAÇÃO DE CSV
# ============================================================================

@gestao_financeira_bp.route('/relatorios-sof')
@login_required
@requires_access('gestao_financeira')
def relatorios_sof():
    """
    Página de importação de relatórios SOF (Dotação, Reservas, Empenhos)
    """
    cur = get_cursor()
    
    try:
        # Buscar data da última atualização de cada tabela
        cur.execute("SELECT MAX(criado_em) as ultima FROM gestao_financeira.back_dotacao")
        result_dotacao = cur.fetchone()
        data_dotacao = result_dotacao['ultima'] if result_dotacao else None
        
        cur.execute("SELECT MAX(criado_em) as ultima FROM gestao_financeira.back_reservas")
        result_reservas = cur.fetchone()
        data_reservas = result_reservas['ultima'] if result_reservas else None
        
        cur.execute("SELECT MAX(criado_em) as ultima FROM gestao_financeira.back_empenhos")
        result_empenhos = cur.fetchone()
        data_empenhos = result_empenhos['ultima'] if result_empenhos else None
        
        cur.close()
        
        # Formatar datas em pt-br
        from datetime import datetime
        data_dotacao_fmt = data_dotacao.strftime('%d/%m/%Y') if data_dotacao else None
        data_reservas_fmt = data_reservas.strftime('%d/%m/%Y') if data_reservas else None
        data_empenhos_fmt = data_empenhos.strftime('%d/%m/%Y') if data_empenhos else None
        
        return render_template(
            'gestao_financeira/gestao_financeira_relatorios_sof.html',
            data_dotacao=data_dotacao_fmt,
            data_reservas=data_reservas_fmt,
            data_empenhos=data_empenhos_fmt
        )
        
    except Exception as e:
        print(f"[ERRO] relatorios_sof: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template(
            'gestao_financeira/gestao_financeira_relatorios_sof.html',
            data_dotacao=None,
            data_reservas=None,
            data_empenhos=None
        )


@gestao_financeira_bp.route('/api/importar-dotacao', methods=['POST'])
@login_required
@requires_access('gestao_financeira')
def api_importar_dotacao():
    """
    API para importar arquivos CSV de dotação orçamentária
    """
    import csv
    from io import StringIO
    
    try:
        conn = get_db()
        cur = conn.cursor()
        total_importados = 0
        
        # Processar cada arquivo enviado
        arquivos = ['dotacao_3410', 'dotacao_3420', 'dotacao_0810', 'dotacao_9010', 'dotacao_7810']
        
        for arquivo_key in arquivos:
            if arquivo_key not in request.files:
                continue
                
            arquivo = request.files[arquivo_key]
            if arquivo.filename == '':
                continue
            
            # Ler conteúdo do CSV com encoding robusto
            conteudo_bytes = arquivo.read()
            for encoding in ['utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    conteudo = conteudo_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return jsonify({'success': False, 'error': f'Não foi possível decodificar o arquivo {arquivo.filename}'}), 400
            
            csv_reader = csv.DictReader(StringIO(conteudo), delimiter=';')
            
            # Inserir registros
            for linha in csv_reader:
                try:
                    cur.execute("""
                        INSERT INTO gestao_financeira.back_dotacao (
                            COD_IDT_DOTA, COD_ORG_EMP, TXT_ORG_EMP, COD_UNID_ORCM_SOF, TXT_UNID_ORCM,
                            COD_FCAO_GOVR, TXT_FCAO_GOVR, COD_SUB_FCAO_GOVR, TXT_SUB_FCAO_GOVR,
                            COD_PGM_GOVR, TXT_PGM_GOVR, COD_PROJ_ATVD_SOF, TXT_PROJ_ATVD,
                            COD_CTA_DESP, TXT_CTA_DESP, COD_FONT_REC, TXT_FONT_REC,
                            COD_EX_FONT_REC, COD_DSTN_REC, COD_VINC_REC_PMSP, COD_TIP_CRED_ORCM,
                            IND_ACTC_REDC, IND_CNTR_COTA_PESL, IND_COTA_PESL, IND_DOTA_LQDD_PAGO,
                            DT_CRIA_DOTA, VAL_DOTA_AUTR, VAL_TOT_CRED_SPLM, VAL_TOT_CRED_ESPC,
                            VAL_TOT_CRED_EXT, VAL_TOT_REDC, ORCADO_ATUAL, VAL_TOT_CNGL,
                            VAL_TOT_BLOQ_DECR, ORCADO_DISPONIVEL, VAL_SLDO_RESV_DOTA, SALDO_DOTACAO,
                            VAL_TOT_EPH, VAL_TOT_CANC_EPH, SALDO_EMPENHADO, SALDO_RESERVADO,
                            VAL_TOT_LQDC_EPH, VAL_TOT_PGTO_DOTA, IND_EMND_ORCM, DOTACAO_FORMATADA,
                            IND_DVDA_PUBC, IND_LANC_RCTA
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                  %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (COD_IDT_DOTA) DO UPDATE SET
                            TXT_ORG_EMP = EXCLUDED.TXT_ORG_EMP,
                            ORCADO_ATUAL = EXCLUDED.ORCADO_ATUAL,
                            SALDO_DOTACAO = EXCLUDED.SALDO_DOTACAO,
                            criado_em = NOW()
                    """, (
                        linha.get('COD_IDT_DOTA'), linha.get('COD_ORG_EMP'), linha.get('TXT_ORG_EMP'),
                        linha.get('COD_UNID_ORCM_SOF'), linha.get('TXT_UNID_ORCM'), linha.get('COD_FCAO_GOVR'),
                        linha.get('TXT_FCAO_GOVR'), linha.get('COD_SUB_FCAO_GOVR'), linha.get('TXT_SUB_FCAO_GOVR'),
                        linha.get('COD_PGM_GOVR'), linha.get('TXT_PGM_GOVR'), linha.get('COD_PROJ_ATVD_SOF'),
                        linha.get('TXT_PROJ_ATVD'), linha.get('COD_CTA_DESP'), linha.get('TXT_CTA_DESP'),
                        linha.get('COD_FONT_REC'), linha.get('TXT_FONT_REC'), linha.get('COD_EX_FONT_REC'),
                        linha.get('COD_DSTN_REC'), linha.get('COD_VINC_REC_PMSP'), linha.get('COD_TIP_CRED_ORCM'),
                        linha.get('IND_ACTC_REDC'), linha.get('IND_CNTR_COTA_PESL'), linha.get('IND_COTA_PESL'),
                        linha.get('IND_DOTA_LQDD_PAGO'), linha.get('DT_CRIA_DOTA'), linha.get('VAL_DOTA_AUTR'),
                        linha.get('VAL_TOT_CRED_SPLM'), linha.get('VAL_TOT_CRED_ESPC'), linha.get('VAL_TOT_CRED_EXT'),
                        linha.get('VAL_TOT_REDC'), linha.get('ORCADO_ATUAL'), linha.get('VAL_TOT_CNGL'),
                        linha.get('VAL_TOT_BLOQ_DECR'), linha.get('ORCADO_DISPONIVEL'), linha.get('VAL_SLDO_RESV_DOTA'),
                        linha.get('SALDO_DOTACAO'), linha.get('VAL_TOT_EPH'), linha.get('VAL_TOT_CANC_EPH'),
                        linha.get('SALDO_EMPENHADO'), linha.get('SALDO_RESERVADO'), linha.get('VAL_TOT_LQDC_EPH'),
                        linha.get('VAL_TOT_PGTO_DOTA'), linha.get('IND_EMND_ORCM'), linha.get('DOTACAO_FORMATADA'),
                        linha.get('IND_DVDA_PUBC'), linha.get('IND_LANC_RCTA')
                    ))
                    total_importados += 1
                except Exception as e:
                    conn.rollback()
                    colunas_faltando = [col for col in ['COD_IDT_DOTA', 'COD_ORG_EMP', 'TXT_ORG_EMP'] if col not in linha]
                    return jsonify({
                        'success': False,
                        'error': f'Erro na linha: {str(e)}',
                        'detalhes': f'Verifique se o CSV tem as colunas corretas. Colunas obrigatórias ausentes: {colunas_faltando if colunas_faltando else "Erro de dados"}'
                    }), 400
        
        conn.commit()
        
        # Buscar data atualizada
        cur.execute("SELECT MAX(criado_em) as ultima FROM gestao_financeira.back_dotacao")
        result = cur.fetchone()
        data_atual = result[0] if result and result[0] else None
        cur.close()
        
        from datetime import datetime
        data_fmt = data_atual.strftime('%d/%m/%Y') if data_atual else None
        
        return jsonify({
            'success': True,
            'message': 'Dotação importada com sucesso!',
            'total_importados': total_importados,
            'data_atualizacao': data_fmt
        })
        
    except Exception as e:
        print(f"[ERRO] api_importar_dotacao: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'detalhes': 'Verifique o formato do arquivo CSV e tente novamente.'
        }), 500


@gestao_financeira_bp.route('/api/importar-reservas', methods=['POST'])
@login_required
@requires_access('gestao_financeira')
def api_importar_reservas():
    """
    API para importar arquivo CSV de reservas
    """
    import csv
    from io import StringIO
    
    try:
        conn = get_db()
        cur = conn.cursor()
        total_importados = 0
        
        # Processar arquivo único
        if 'reservas_3410' not in request.files:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
            
        arquivo = request.files['reservas_3410']
        if arquivo.filename == '':
            return jsonify({'success': False, 'error': 'Arquivo vazio'}), 400
        
        # Ler conteúdo do CSV com encoding robusto
        conteudo_bytes = arquivo.read()
        for encoding in ['utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                conteudo = conteudo_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return jsonify({'success': False, 'error': 'Não foi possível decodificar o arquivo'}), 400
        
        csv_reader = csv.DictReader(StringIO(conteudo), delimiter=';')
        
        # Debug: verificar colunas do CSV
        colunas_esperadas = [
            'COD_RESV_DOTA_SOF', 'DT_EFET_RESV', 'ANO_RESV', 'DOTACAO_FORMATADA', 'COD_NRO_PCSS_SOF',
            'HIST_RESV', 'VL_RESV', 'VL_TRANSF_RESV', 'VL_CANC_RESV', 'VL_EPH', 'VL_SALDO_RESV',
            'COD_ORG_EMP', 'COD_UNID_ORCM_SOF', 'ORGDESC', 'TXT_UNID_ORCM', 'COD_ORG_EMP_EXEC',
            'COD_UNID_ORCM_SOF_EXEC', 'TXT_ORG_EMP_EXECT', 'TXT_UNID_ORCM_EXECT',
            'COD_CATG_ECMC', 'COD_GRUP_DESP', 'COD_MODL_APLC', 'COD_ELEM_DESP', 'COD_SUB_ELEM_CONTA_DESP',
            'COD_FCAO_GOVR', 'TXT_FCAO_GOVR', 'COD_SUB_FCAO_GOVR', 'TXT_SUB_FCAO_GOVR',
            'COD_PGM_GOVR', 'TXT_PGM_GOVR', 'COD_PROJ_ATVD_SOF', 'COD_CTA_DESP', 'COD_FONT_REC'
        ]
        
        primeira_linha = next(csv_reader, None)
        if primeira_linha:
            colunas_csv = list(primeira_linha.keys())
            colunas_faltando = [col for col in colunas_esperadas if col not in colunas_csv]
            colunas_extras = [col for col in colunas_csv if col not in colunas_esperadas]
            
            if colunas_faltando or colunas_extras:
                conn.rollback()
                mensagem = ""
                if colunas_faltando:
                    mensagem += f"Colunas faltando: {', '.join(colunas_faltando[:5])}{'...' if len(colunas_faltando) > 5 else ''}. "
                if colunas_extras:
                    mensagem += f"Colunas extras: {', '.join(colunas_extras[:5])}{'...' if len(colunas_extras) > 5 else ''}. "
                mensagem += f"Total no CSV: {len(colunas_csv)} colunas, esperado: {len(colunas_esperadas)} colunas."
                return jsonify({
                    'success': False,
                    'error': 'Estrutura do CSV incompatível',
                    'detalhes': mensagem
                }), 400
        
        # Inserir registros
        for linha in csv_reader:
            try:
                cur.execute("""
                    INSERT INTO gestao_financeira.back_reservas (
                        COD_RESV_DOTA_SOF, DT_EFET_RESV, ANO_RESV, DOTACAO_FORMATADA, COD_NRO_PCSS_SOF,
                        HIST_RESV, VL_RESV, VL_TRANSF_RESV, VL_CANC_RESV, VL_EPH, VL_SALDO_RESV,
                        COD_ORG_EMP, COD_UNID_ORCM_SOF, ORGDESC, TXT_UNID_ORCM, COD_ORG_EMP_EXEC,
                        COD_UNID_ORCM_SOF_EXEC, TXT_ORG_EMP_EXECT, TXT_UNID_ORCM_EXECT,
                        COD_CATG_ECMC, COD_GRUP_DESP, COD_MODL_APLC, COD_ELEM_DESP, COD_SUB_ELEM_CONTA_DESP,
                        COD_FCAO_GOVR, TXT_FCAO_GOVR, COD_SUB_FCAO_GOVR, TXT_SUB_FCAO_GOVR,
                        COD_PGM_GOVR, TXT_PGM_GOVR, COD_PROJ_ATVD_SOF, COD_CTA_DESP, COD_FONT_REC
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (COD_RESV_DOTA_SOF) DO UPDATE SET
                        VL_RESV = EXCLUDED.VL_RESV,
                        VL_SALDO_RESV = EXCLUDED.VL_SALDO_RESV,
                        criado_em = NOW()
                """, (
                    linha.get('COD_RESV_DOTA_SOF'), linha.get('DT_EFET_RESV'), linha.get('ANO_RESV'),
                    linha.get('DOTACAO_FORMATADA'), linha.get('COD_NRO_PCSS_SOF'), linha.get('HIST_RESV'),
                    linha.get('VL_RESV'), linha.get('VL_TRANSF_RESV'), linha.get('VL_CANC_RESV'),
                    linha.get('VL_EPH'), linha.get('VL_SALDO_RESV'), linha.get('COD_ORG_EMP'),
                    linha.get('COD_UNID_ORCM_SOF'), linha.get('ORGDESC'), linha.get('TXT_UNID_ORCM'),
                    linha.get('COD_ORG_EMP_EXEC'), linha.get('COD_UNID_ORCM_SOF_EXEC'),
                    linha.get('TXT_ORG_EMP_EXECT'), linha.get('TXT_UNID_ORCM_EXECT'),
                    linha.get('COD_CATG_ECMC'), linha.get('COD_GRUP_DESP'), linha.get('COD_MODL_APLC'),
                    linha.get('COD_ELEM_DESP'), linha.get('COD_SUB_ELEM_CONTA_DESP'),
                    linha.get('COD_FCAO_GOVR'), linha.get('TXT_FCAO_GOVR'), linha.get('COD_SUB_FCAO_GOVR'),
                    linha.get('TXT_SUB_FCAO_GOVR'), linha.get('COD_PGM_GOVR'), linha.get('TXT_PGM_GOVR'),
                    linha.get('COD_PROJ_ATVD_SOF'), linha.get('COD_CTA_DESP'), linha.get('COD_FONT_REC')
                ))
                total_importados += 1
            except Exception as e:
                conn.rollback()
                return jsonify({
                    'success': False,
                    'error': f'Erro na linha: {str(e)}',
                    'detalhes': 'Verifique se o CSV tem todas as colunas necessárias.'
                }), 400
        
        conn.commit()
        
        # Buscar data atualizada
        cur.execute("SELECT MAX(criado_em) as ultima FROM gestao_financeira.back_reservas")
        result = cur.fetchone()
        data_atual = result[0] if result and result[0] else None
        cur.close()
        
        from datetime import datetime
        data_fmt = data_atual.strftime('%d/%m/%Y') if data_atual else None
        
        return jsonify({
            'success': True,
            'message': 'Reservas importadas com sucesso!',
            'total_importados': total_importados,
            'data_atualizacao': data_fmt
        })
        
    except Exception as e:
        print(f"[ERRO] api_importar_reservas: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gestao_financeira_bp.route('/api/importar-empenhos', methods=['POST'])
@login_required
@requires_access('gestao_financeira')
def api_importar_empenhos():
    """
    API para importar arquivos CSV de empenhos
    """
    import csv
    from io import StringIO
    
    try:
        conn = get_db()
        cur = conn.cursor()
        total_importados = 0
        
        # Processar cada arquivo enviado
        arquivos = ['empenhos_3410', 'empenhos_3420', 'empenhos_0810', 'empenhos_9010', 'empenhos_7810']
        
        for arquivo_key in arquivos:
            if arquivo_key not in request.files:
                continue
                
            arquivo = request.files[arquivo_key]
            if arquivo.filename == '':
                continue
            
            # Ler conteúdo do CSV com encoding robusto
            conteudo_bytes = arquivo.read()
            for encoding in ['utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    conteudo = conteudo_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return jsonify({'success': False, 'error': f'Não foi possível decodificar o arquivo {arquivo.filename}'}), 400
            
            csv_reader = csv.DictReader(StringIO(conteudo), delimiter=';')
            
            # Debug: mostrar colunas do CSV
            primeira_linha = next(csv_reader, None)
            if primeira_linha:
                colunas_csv = list(primeira_linha.keys())
                print(f"[DEBUG] Arquivo {arquivo_key}: CSV tem {len(colunas_csv)} colunas")
                print(f"[DEBUG] Primeiras 10 colunas: {colunas_csv[:10]}")
                print(f"[DEBUG] Últimas 10 colunas: {colunas_csv[-10:]}")
                
                # Processar primeira linha
                try:
                    # Debug: contar colunas e valores
                    colunas_insert = [
                        'COD_IDT_EPH', 'DT_EPH', 'COD_EPH', 'ANO_EPH', 'COD_TIP_EPH_SOF', 'COD_NRO_PCSS_SOF',
                        'COD_TIP_DOC', 'COD_IDT_MODL_LICI', 'TXT_OBS_EPH', 'VAL_TOT_EPH', 'VAL_TOT_CANC_EPH',
                        'VAL_TOT_LQDC_EPH', 'VAL_TOT_PAGO_EPH', 'VAL_TOT_A_LIQ_EPH', 'VAL_TOT_A_PAG_EPH',
                        'COD_IDT_CRDR_SOF', 'NOM_RZAO_SOCI_SOF', 'COD_NAT_CRDR', 'COD_CPF_CNPJ_SOF',
                        'COD_IDT_ITEM_DESP', 'COD_ITEM_DESP_SOF', 'TXT_ITEM_DESP', 'COD_IDT_SUB_ELEM',
                        'COD_SUB_ELEM_DESP', 'TXT_SUB_ELEM', 'COD_IDT_CTA_DESP', 'IND_CTA_SINT_ANLT',
                        'COD_CATG_ECMC', 'COD_GRUP_DESP', 'COD_MODL_APLC', 'COD_ELEM_DESP',
                        'COD_SUB_ELEM_CONTA_DESP', 'COD_IDT_FCAO_GOVR', 'COD_IDT_SUB_FCAO',
                        'COD_IDT_PGM_GOVR', 'COD_IDT_PROJ_ATVD', 'COD_ORG_EMP_EXECT', 'TXT_ORG_EMP_EXECT',
                        'COD_UNID_ORCM_SOF_EXECT', 'TXT_UNID_ORCM_EXECT', 'TXT_DOTACAO_FMT',
                        'COD_FCAO_GOVR', 'TXT_FCAO_GOVR', 'COD_PGM_GOVR', 'TXT_PGM_GOVR',
                        'COD_SUB_FCAO_GOVR', 'TXT_SUB_FCAO_GOVR', 'COD_PROJ_ATVD_SOF_P', 'TXT_PROJ_ATVD_P',
                        'COD_MODL_LICI_SOF', 'TXT_MODL_LICI', 'COD_EMP_PMSP', 'NOM_EMP_SOF',
                        'COD_IDT_FONT_REC', 'COD_IDT_DOTA', 'COD_IDT_CTA_DESP1', 'COD_CTA_DESP',
                        'TXT_CTA_DESP', 'COD_FONT_REC', 'TXT_FONT_REC', 'COD_FONT_REC_EXEC',
                        'TXT_FONT_REC_EXEC', 'COD_CAR', 'DESC_CAR'
                    ]
                    
                    # Colunas que são INTEGER e precisam converter string vazia para NULL
                    colunas_integer = {
                        'COD_IDT_EPH', 'COD_EPH', 'ANO_EPH', 'COD_IDT_MODL_LICI', 'COD_IDT_CRDR_SOF',
                        'COD_IDT_ITEM_DESP', 'COD_ITEM_DESP_SOF', 'COD_IDT_SUB_ELEM', 'COD_SUB_ELEM_DESP',
                        'COD_IDT_CTA_DESP', 'COD_CATG_ECMC', 'COD_GRUP_DESP', 'COD_MODL_APLC', 'COD_ELEM_DESP',
                        'COD_SUB_ELEM_CONTA_DESP', 'COD_IDT_FCAO_GOVR', 'COD_IDT_SUB_FCAO', 'COD_IDT_PGM_GOVR',
                        'COD_IDT_PROJ_ATVD', 'COD_ORG_EMP_EXECT', 'COD_UNID_ORCM_SOF_EXECT', 'COD_FCAO_GOVR',
                        'COD_PGM_GOVR', 'COD_SUB_FCAO_GOVR', 'COD_PROJ_ATVD_SOF_P', 'COD_MODL_LICI_SOF',
                        'COD_EMP_PMSP', 'COD_IDT_FONT_REC', 'COD_IDT_DOTA', 'COD_IDT_CTA_DESP1', 'COD_CAR'
                    }
                    
                    def limpar_valor(col, val):
                        # Limpar formato Excel ="número" para apenas número
                        if val and isinstance(val, str):
                            # Remove ="..." deixando só o conteúdo
                            if val.startswith('="') and val.endswith('"'):
                                val = val[2:-1]  # Remove =" do início e " do fim
                        
                        # Converter string vazia para None apenas em colunas INTEGER
                        if (val == '' or val is None) and col in colunas_integer:
                            return None
                        return val
                    
                    valores = tuple(limpar_valor(col, primeira_linha.get(col)) for col in colunas_insert)
                    
                    print(f"[DEBUG] Colunas INSERT: {len(colunas_insert)}")
                    print(f"[DEBUG] Valores tuple: {len(valores)}")
                    print(f"[DEBUG] Colunas faltando no CSV: {[col for col in colunas_insert if col not in primeira_linha.keys()]}")
                    print(f"[DEBUG] Colunas extras no CSV: {[col for col in primeira_linha.keys() if col not in colunas_insert]}")
                    
                    # Debug: mostrar tamanho dos valores VARCHAR
                    print("\n[DEBUG] Tamanho dos valores VARCHAR:")
                    for i, col in enumerate(colunas_insert):
                        val = valores[i]
                        if val and isinstance(val, str) and len(val) > 50:
                            print(f"  {col}: {len(val)} chars - '{val[:100]}...'")
                    
                    cur.execute("""
                        INSERT INTO gestao_financeira.back_empenhos (
                            COD_IDT_EPH, DT_EPH, COD_EPH, ANO_EPH, COD_TIP_EPH_SOF, COD_NRO_PCSS_SOF,
                            COD_TIP_DOC, COD_IDT_MODL_LICI, TXT_OBS_EPH, VAL_TOT_EPH, VAL_TOT_CANC_EPH,
                            VAL_TOT_LQDC_EPH, VAL_TOT_PAGO_EPH, VAL_TOT_A_LIQ_EPH, VAL_TOT_A_PAG_EPH,
                            COD_IDT_CRDR_SOF, NOM_RZAO_SOCI_SOF, COD_NAT_CRDR, COD_CPF_CNPJ_SOF,
                            COD_IDT_ITEM_DESP, COD_ITEM_DESP_SOF, TXT_ITEM_DESP, COD_IDT_SUB_ELEM,
                            COD_SUB_ELEM_DESP, TXT_SUB_ELEM, COD_IDT_CTA_DESP, IND_CTA_SINT_ANLT,
                            COD_CATG_ECMC, COD_GRUP_DESP, COD_MODL_APLC, COD_ELEM_DESP,
                            COD_SUB_ELEM_CONTA_DESP, COD_IDT_FCAO_GOVR, COD_IDT_SUB_FCAO,
                            COD_IDT_PGM_GOVR, COD_IDT_PROJ_ATVD, COD_ORG_EMP_EXECT, TXT_ORG_EMP_EXECT,
                            COD_UNID_ORCM_SOF_EXECT, TXT_UNID_ORCM_EXECT, TXT_DOTACAO_FMT,
                            COD_FCAO_GOVR, TXT_FCAO_GOVR, COD_PGM_GOVR, TXT_PGM_GOVR,
                            COD_SUB_FCAO_GOVR, TXT_SUB_FCAO_GOVR, COD_PROJ_ATVD_SOF_P, TXT_PROJ_ATVD_P,
                            COD_MODL_LICI_SOF, TXT_MODL_LICI, COD_EMP_PMSP, NOM_EMP_SOF,
                            COD_IDT_FONT_REC, COD_IDT_DOTA, COD_IDT_CTA_DESP1, COD_CTA_DESP,
                            TXT_CTA_DESP, COD_FONT_REC, TXT_FONT_REC, COD_FONT_REC_EXEC,
                            TXT_FONT_REC_EXEC, COD_CAR, DESC_CAR
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                  %s, %s, %s, %s)
                        ON CONFLICT (COD_IDT_EPH) DO UPDATE SET
                            VAL_TOT_EPH = EXCLUDED.VAL_TOT_EPH,
                            VAL_TOT_LQDC_EPH = EXCLUDED.VAL_TOT_LQDC_EPH,
                            VAL_TOT_PAGO_EPH = EXCLUDED.VAL_TOT_PAGO_EPH,
                            criado_em = NOW()
                    """, valores)
                    total_importados += 1
                except Exception as e:
                    print(f"[ERRO] Erro ao inserir primeira linha: {str(e)}")
                    conn.rollback()
                    return jsonify({
                        'success': False,
                        'error': f'Erro ao inserir dados: {str(e)}',
                        'detalhes': 'Verifique se o CSV tem todas as colunas necessárias'
                    }), 400
            
            # Inserir restante dos registros
            for linha in csv_reader:
                try:
                    cur.execute("""
                        INSERT INTO gestao_financeira.back_empenhos (
                            COD_IDT_EPH, DT_EPH, COD_EPH, ANO_EPH, COD_TIP_EPH_SOF, COD_NRO_PCSS_SOF,
                            COD_TIP_DOC, COD_IDT_MODL_LICI, TXT_OBS_EPH, VAL_TOT_EPH, VAL_TOT_CANC_EPH,
                            VAL_TOT_LQDC_EPH, VAL_TOT_PAGO_EPH, VAL_TOT_A_LIQ_EPH, VAL_TOT_A_PAG_EPH,
                            COD_IDT_CRDR_SOF, NOM_RZAO_SOCI_SOF, COD_NAT_CRDR, COD_CPF_CNPJ_SOF,
                            COD_IDT_ITEM_DESP, COD_ITEM_DESP_SOF, TXT_ITEM_DESP, COD_IDT_SUB_ELEM,
                            COD_SUB_ELEM_DESP, TXT_SUB_ELEM, COD_IDT_CTA_DESP, IND_CTA_SINT_ANLT,
                            COD_CATG_ECMC, COD_GRUP_DESP, COD_MODL_APLC, COD_ELEM_DESP,
                            COD_SUB_ELEM_CONTA_DESP, COD_IDT_FCAO_GOVR, COD_IDT_SUB_FCAO,
                            COD_IDT_PGM_GOVR, COD_IDT_PROJ_ATVD, COD_ORG_EMP_EXECT, TXT_ORG_EMP_EXECT,
                            COD_UNID_ORCM_SOF_EXECT, TXT_UNID_ORCM_EXECT, TXT_DOTACAO_FMT,
                            COD_FCAO_GOVR, TXT_FCAO_GOVR, COD_PGM_GOVR, TXT_PGM_GOVR,
                            COD_SUB_FCAO_GOVR, TXT_SUB_FCAO_GOVR, COD_PROJ_ATVD_SOF_P, TXT_PROJ_ATVD_P,
                            COD_MODL_LICI_SOF, TXT_MODL_LICI, COD_EMP_PMSP, NOM_EMP_SOF,
                            COD_IDT_FONT_REC, COD_IDT_DOTA, COD_IDT_CTA_DESP1, COD_CTA_DESP,
                            TXT_CTA_DESP, COD_FONT_REC, TXT_FONT_REC, COD_FONT_REC_EXEC,
                            TXT_FONT_REC_EXEC, COD_CAR, DESC_CAR
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                  %s, %s, %s, %s)
                        ON CONFLICT (COD_IDT_EPH) DO UPDATE SET
                            VAL_TOT_EPH = EXCLUDED.VAL_TOT_EPH,
                            VAL_TOT_LQDC_EPH = EXCLUDED.VAL_TOT_LQDC_EPH,
                            VAL_TOT_PAGO_EPH = EXCLUDED.VAL_TOT_PAGO_EPH,
                            criado_em = NOW()
                    """, tuple(limpar_valor(col, linha.get(col)) for col in colunas_insert))
                    total_importados += 1
                except Exception as e:
                    conn.rollback()
                    return jsonify({
                        'success': False,
                        'error': f'Erro na linha: {str(e)}',
                        'detalhes': 'Verifique se o CSV tem todas as colunas necessárias.'
                    }), 400
        
        conn.commit()
        
        # Buscar data atualizada
        cur.execute("SELECT MAX(criado_em) as ultima FROM gestao_financeira.back_empenhos")
        result = cur.fetchone()
        data_atual = result[0] if result and result[0] else None
        cur.close()
        
        from datetime import datetime
        data_fmt = data_atual.strftime('%d/%m/%Y') if data_atual else None
        
        return jsonify({
            'success': True,
            'message': 'Empenhos importados com sucesso!',
            'total_importados': total_importados,
            'data_atualizacao': data_fmt
        })
        
    except Exception as e:
        print(f"[ERRO] api_importar_empenhos: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gestao_financeira_bp.route('/api/importar-todos', methods=['POST'])
@login_required
@requires_access('gestao_financeira')
def api_importar_todos():
    """
    API para importar todos os arquivos CSV de uma vez
    """
    try:
        resultados = {
            'dotacao_importados': 0,
            'reservas_importados': 0,
            'empenhos_importados': 0,
            'datas': {}
        }
        
        # Importar Dotação
        arquivos_dotacao = ['dotacao_3410', 'dotacao_3420', 'dotacao_0810', 'dotacao_9010', 'dotacao_7810']
        tem_dotacao = any(key in request.files and request.files[key].filename != '' for key in arquivos_dotacao)
        
        if tem_dotacao:
            resp = api_importar_dotacao()
            data = resp.get_json() if hasattr(resp, 'get_json') else {}
            if data.get('success'):
                resultados['dotacao_importados'] = data.get('total_importados', 0)
                resultados['datas']['dotacao'] = data.get('data_atualizacao')
        
        # Importar Reservas
        if 'reservas_3410' in request.files and request.files['reservas_3410'].filename != '':
            resp = api_importar_reservas()
            data = resp.get_json() if hasattr(resp, 'get_json') else {}
            if data.get('success'):
                resultados['reservas_importados'] = data.get('total_importados', 0)
                resultados['datas']['reservas'] = data.get('data_atualizacao')
        
        # Importar Empenhos
        arquivos_empenhos = ['empenhos_3410', 'empenhos_3420', 'empenhos_0810', 'empenhos_9010', 'empenhos_7810']
        tem_empenhos = any(key in request.files and request.files[key].filename != '' for key in arquivos_empenhos)
        
        if tem_empenhos:
            resp = api_importar_empenhos()
            data = resp.get_json() if hasattr(resp, 'get_json') else {}
            if data.get('success'):
                resultados['empenhos_importados'] = data.get('total_importados', 0)
                resultados['datas']['empenhos'] = data.get('data_atualizacao')
        
        total_geral = sum([resultados['dotacao_importados'], 
                          resultados['reservas_importados'], 
                          resultados['empenhos_importados']])
        
        return jsonify({
            'success': True,
            'message': 'Importação geral concluída!',
            'total_importados': total_geral,
            **resultados
        })
        
    except Exception as e:
        print(f"[ERRO] api_importar_todos: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gestao_financeira_bp.route("/api/sincronizar-empenhos", methods=["POST"])
@login_required
@requires_access('gestao_financeira')
def api_sincronizar_empenhos():
    """
    Sincroniza empenhos do SOF (back_empenhos) com acompanhamento de parcelas (temp_acomp_empenhos)
    
    Lógica:
    1. Busca empenhos em back_empenhos
    2. Vincula com parcerias através do processo de celebração normalizado
    3. Vincula com temp_acomp_empenhos e temp_reservas_empenhos através do numero_termo
    4. Distribui valores empenhados nas parcelas programadas
    5. Atualiza status e valores em temp_acomp_empenhos
    
    Parâmetros:
        apenas_relatorio (bool): Se True, gera relatório sem atualizar banco
    """
    try:
        dados = request.get_json() or {}
        apenas_relatorio = dados.get('apenas_relatorio', True)
        
        cur = get_cursor()
        conn = get_db()
        
        # Função auxiliar para normalizar processo (remove pontos, traços, barras)
        def normalizar_processo(processo):
            if not processo:
                return ''
            return str(processo).replace('.', '').replace('/', '').replace('-', '').strip()
        
        # Função para determinar status baseado em valores previstos vs empenhados
        def calcular_status(previsto, empenhado, status_anterior):
            previsto = float(previsto or 0)
            empenhado = float(empenhado or 0)
            
            if empenhado == 0:
                # Nada empenhado
                if status_anterior == 'DEOF: Enviado para empenho':
                    return 'Enviado, mas não empenhado'
                return status_anterior
            elif empenhado >= previsto:
                return 'Empenhado'
            else:
                return 'Empenhado Parcialmente'
        
        # PASSO 1: Buscar todos os empenhos do back_empenhos
        print("[DEBUG] Buscando empenhos do SOF...")
        cur.execute("""
            SELECT 
                cod_idt_eph,
                cod_nro_pcss_sof,
                cod_eph,
                cod_item_desp_sof,
                val_tot_eph,
                val_tot_canc_eph,
                dt_eph
            FROM gestao_financeira.back_empenhos
            WHERE cod_nro_pcss_sof IS NOT NULL
            ORDER BY cod_nro_pcss_sof, cod_item_desp_sof, cod_eph
        """)
        
        empenhos_sof = cur.fetchall()
        print(f"[DEBUG] Encontrados {len(empenhos_sof)} empenhos no SOF")
        
        # Debug: verificar tipo de retorno
        if empenhos_sof:
            print(f"[DEBUG] Tipo do primeiro elemento: {type(empenhos_sof[0])}")
            print(f"[DEBUG] Primeiro elemento: {empenhos_sof[0]}")
        
        # Organizar empenhos por processo normalizado
        empenhos_por_processo = {}
        for emp in empenhos_sof:
            # Acessar por nome de coluna (compatível com RealDictCursor)
            try:
                processo_norm = normalizar_processo(emp['cod_nro_pcss_sof'])
                elemento = emp['cod_item_desp_sof']  # pode ser 23 ou 24
                ne = emp['cod_eph']  # número da nota de empenho
                val_total = emp['val_tot_eph']
                val_canc = emp['val_tot_canc_eph']
                dt_eph = emp['dt_eph']
            except (KeyError, TypeError):
                # Se falhar, tentar acesso por índice (tupla normal)
                processo_norm = normalizar_processo(emp[1])
                elemento = emp[3]
                ne = emp[2]
                val_total = emp[4]
                val_canc = emp[5]
                dt_eph = emp[6]
            
            # Calcular valor líquido (total - cancelado)
            val_total_str = str(val_total or '0').replace('.', '').replace(',', '.')
            val_canc_str = str(val_canc or '0').replace('.', '').replace(',', '.')
            
            try:
                valor_liquido = float(val_total_str) - float(val_canc_str)
            except (ValueError, TypeError):
                print(f"[AVISO] Erro ao converter valores para empenho {ne}: total={val_total}, canc={val_canc}")
                valor_liquido = 0
            
            if processo_norm not in empenhos_por_processo:
                empenhos_por_processo[processo_norm] = {}
            
            if elemento not in empenhos_por_processo[processo_norm]:
                empenhos_por_processo[processo_norm][elemento] = []
            
            empenhos_por_processo[processo_norm][elemento].append({
                'ne': ne,
                'valor': valor_liquido,
                'data': dt_eph
            })
        
        # PASSO 2: Vincular com parcerias e buscar numero_termo
        print("[DEBUG] Vinculando processos com parcerias...")
        cur.execute("""
            SELECT 
                sei_celeb,
                numero_termo
            FROM public.parcerias
            WHERE sei_celeb IS NOT NULL
              AND numero_termo IS NOT NULL
        """)
        
        parcerias = cur.fetchall()
        
        # Mapa processo -> numero_termo
        processo_to_termo = {}
        for parc in parcerias:
            try:
                sei_celeb_norm = normalizar_processo(parc['sei_celeb'])
                numero_termo = parc['numero_termo']
            except (KeyError, TypeError):
                sei_celeb_norm = normalizar_processo(parc[0])
                numero_termo = parc[1]
            
            processo_to_termo[sei_celeb_norm] = numero_termo
        
        print(f"[DEBUG] Mapeados {len(processo_to_termo)} processos para termos")
        
        # PASSO 3: Buscar parcelas programadas de temp_reservas_empenhos
        print("[DEBUG] Buscando parcelas programadas...")
        cur.execute("""
            SELECT 
                id,
                numero_termo,
                numero_parcela,
                elemento_23,
                elemento_24,
                parcela_total_previsto
            FROM gestao_financeira.temp_reservas_empenhos
            ORDER BY numero_termo, id
        """)
        
        parcelas_programadas = cur.fetchall()
        
        # Organizar por termo (lista ordenada por id)
        parcelas_por_termo = {}
        for parcela in parcelas_programadas:
            try:
                id_reserva = parcela['id']
                termo = parcela['numero_termo']
                num_parcela = parcela['numero_parcela']
                elem_23 = parcela['elemento_23']
                elem_24 = parcela['elemento_24']
                total_prev = parcela['parcela_total_previsto']
            except (KeyError, TypeError):
                id_reserva = parcela[0]
                termo = parcela[1]
                num_parcela = parcela[2]
                elem_23 = parcela[3]
                elem_24 = parcela[4]
                total_prev = parcela[5]
            
            if termo not in parcelas_por_termo:
                parcelas_por_termo[termo] = []
            
            parcelas_por_termo[termo].append({
                'id_reserva': id_reserva,
                'numero_parcela': num_parcela,
                'previsto_23': float(elem_23 or 0),
                'previsto_24': float(elem_24 or 0),
                'previsto_total': float(total_prev or 0)
            })
        
        # PASSO 3.5: Buscar parcelas de temp_acomp_empenhos (ordenadas por numero)
        print("[DEBUG] Buscando parcelas de acompanhamento...")
        cur.execute("""
            SELECT 
                id,
                numero,
                numero_termo,
                status
            FROM gestao_financeira.temp_acomp_empenhos
            ORDER BY numero_termo, numero
        """)
        
        parcelas_acomp = cur.fetchall()
        
        # Organizar por termo
        acomp_por_termo = {}
        for acomp in parcelas_acomp:
            try:
                id_acomp = acomp['id']
                numero = acomp['numero']
                termo = acomp['numero_termo']
                status_atual = acomp['status']
            except (KeyError, TypeError):
                id_acomp = acomp[0]
                numero = acomp[1]
                termo = acomp[2]
                status_atual = acomp[3] if len(acomp) > 3 else ''
            
            if termo not in acomp_por_termo:
                acomp_por_termo[termo] = []
            
            acomp_por_termo[termo].append({
                'id': id_acomp,
                'numero': numero,
                'status_atual': status_atual
            })
        
        # PASSO 4: Processar cada termo e distribuir empenhos nas parcelas
        relatorio = {
            'total_termos': 0,
            'total_parcelas': 0,
            'total_empenhos': len(empenhos_sof),
            'detalhes': [],
            'alertas': []
        }
        
        termos_atualizados = 0
        parcelas_atualizadas = 0
        
        for processo_norm, empenhos_elementos in empenhos_por_processo.items():
            # Buscar termo correspondente
            if processo_norm not in processo_to_termo:
                relatorio['alertas'].append(f"⚠️ Processo {processo_norm} não encontrado em parcerias")
                continue
            
            numero_termo = processo_to_termo[processo_norm]
            
            # Verificar se tem parcelas programadas E parcelas de acompanhamento
            if numero_termo not in parcelas_por_termo:
                relatorio['alertas'].append(f"⚠️ Termo {numero_termo} não tem parcelas em temp_reservas_empenhos")
                continue
            
            if numero_termo not in acomp_por_termo:
                relatorio['alertas'].append(f"⚠️ Termo {numero_termo} não tem parcelas em temp_acomp_empenhos")
                continue
            
            parcelas_reservas = parcelas_por_termo[numero_termo]
            parcelas_enviadas = acomp_por_termo[numero_termo]
            
            # Verificar se quantidade bate (posicional)
            if len(parcelas_reservas) != len(parcelas_enviadas):
                relatorio['alertas'].append(
                    f"⚠️ {numero_termo}: Quantidade de parcelas não bate - "
                    f"Reservas: {len(parcelas_reservas)}, Enviadas: {len(parcelas_enviadas)}"
                )
                # Usa o mínimo para evitar erro de índice
                qtd_parcelas = min(len(parcelas_reservas), len(parcelas_enviadas))
            else:
                qtd_parcelas = len(parcelas_reservas)
            
            relatorio['total_termos'] += 1
            relatorio['total_parcelas'] += qtd_parcelas
            
            # Somar totais empenhados por elemento
            total_empenhado_23 = sum([e['valor'] for e in empenhos_elementos.get(23, [])])
            total_empenhado_24 = sum([e['valor'] for e in empenhos_elementos.get(24, [])])
            
            # Somar totais previstos por elemento
            total_previsto_23 = sum([p['previsto_23'] for p in parcelas_reservas])
            total_previsto_24 = sum([p['previsto_24'] for p in parcelas_reservas])
            
            # Alertas de discrepância
            if total_empenhado_23 > total_previsto_23 * 1.01:  # Tolerância de 1%
                relatorio['alertas'].append(
                    f"⚠️ {numero_termo}: Empenhado no elemento 23 (R$ {total_empenhado_23:,.2f}) "
                    f"excede previsto (R$ {total_previsto_23:,.2f})"
                )
            
            if total_empenhado_24 > total_previsto_24 * 1.01:
                relatorio['alertas'].append(
                    f"⚠️ {numero_termo}: Empenhado no elemento 24 (R$ {total_empenhado_24:,.2f}) "
                    f"excede previsto (R$ {total_previsto_24:,.2f})"
                )
            
            # Distribuir valores nas parcelas EM CASCATA
            detalhes_termo = {
                'numero_termo': numero_termo,
                'processo_celebracao': processo_norm,
                'parcelas': []
            }
            
            saldo_23 = total_empenhado_23
            saldo_24 = total_empenhado_24
            
            # Concatenar notas de empenho
            nes_23 = ';'.join([str(e['ne']) for e in empenhos_elementos.get(23, [])])
            nes_24 = ';'.join([str(e['ne']) for e in empenhos_elementos.get(24, [])])
            
            # DISTRIBUIÇÃO EM CASCATA (ordem sequencial)
            for i in range(qtd_parcelas):
                parcela_reserva = parcelas_reservas[i]
                parcela_enviada = parcelas_enviadas[i]
                
                # Alocar valores até esgotar saldo ou previsto (CASCATA)
                empenhado_23 = min(saldo_23, parcela_reserva['previsto_23'])
                empenhado_24 = min(saldo_24, parcela_reserva['previsto_24'])
                
                saldo_23 -= empenhado_23
                saldo_24 -= empenhado_24
                
                # Determinar status
                previsto_total_parcela = parcela_reserva['previsto_23'] + parcela_reserva['previsto_24']
                empenhado_total_parcela = empenhado_23 + empenhado_24
                
                status_anterior = parcela_enviada['status_atual']
                status = calcular_status(previsto_total_parcela, empenhado_total_parcela, status_anterior)
                
                # Determinar quais NEs usar (só incluir se houver valor empenhado)
                ne_23_parcela = nes_23 if empenhado_23 > 0 else ''
                ne_24_parcela = nes_24 if empenhado_24 > 0 else ''
                
                detalhes_termo['parcelas'].append({
                    'numero': parcela_enviada['numero'],
                    'numero_parcela': parcela_reserva['numero_parcela'],
                    'previsto_23': parcela_reserva['previsto_23'],
                    'empenhado_23': empenhado_23,
                    'ne_23': ne_23_parcela,
                    'previsto_24': parcela_reserva['previsto_24'],
                    'empenhado_24': empenhado_24,
                    'ne_24': ne_24_parcela,
                    'status': status
                })
                
                # ATUALIZAR BANCO (se não for apenas relatório)
                if not apenas_relatorio:
                    # UPDATE direto usando id de temp_acomp_empenhos
                    cur.execute("""
                        UPDATE gestao_financeira.temp_acomp_empenhos
                        SET 
                            nota_empenho_23 = CASE WHEN %s > 0 THEN %s ELSE nota_empenho_23 END,
                            nota_empenho_24 = CASE WHEN %s > 0 THEN %s ELSE nota_empenho_24 END,
                            total_empenhado_23 = %s,
                            total_empenhado_24 = %s,
                            status = %s
                        WHERE id = %s
                    """, (
                        empenhado_23, ne_23_parcela.split(';')[0] if ne_23_parcela else None,
                        empenhado_24, ne_24_parcela.split(';')[0] if ne_24_parcela else None,
                        empenhado_23, empenhado_24, status,
                        parcela_enviada['id']
                    ))
                    
                    parcelas_atualizadas += 1
            
            detalhes_termo['total_empenhado_23'] = total_empenhado_23
            detalhes_termo['total_empenhado_24'] = total_empenhado_24
            detalhes_termo['total_previsto_23'] = total_previsto_23
            detalhes_termo['total_previsto_24'] = total_previsto_24
            
            relatorio['detalhes'].append(detalhes_termo)
            termos_atualizados += 1
        
        # Commit se não for apenas relatório
        if not apenas_relatorio:
            conn.commit()
            print(f"[DEBUG] Sincronização concluída: {termos_atualizados} termos, {parcelas_atualizadas} parcelas")
        
        return jsonify({
            'success': True,
            'relatorio': relatorio,
            'termos_atualizados': termos_atualizados,
            'parcelas_atualizadas': parcelas_atualizadas,
            'alertas': relatorio['alertas']
        })
        
    except Exception as e:
        print(f"[ERRO] api_sincronizar_empenhos: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@gestao_financeira_bp.route("/api/adicionar-encaminhamento", methods=["POST"])
@login_required
@requires_access('gestao_financeira')
def api_adicionar_encaminhamento():
    """
    Adiciona novo registro em temp_acomp_empenhos
    
    Campos:
    - numero_termo (required)
    - aditivo (optional)
    - numero (required) - número sequencial da parcela
    - responsavel (required)
    - status (required)
    - nota_empenho_23, sei_nota_empenho_23, total_empenhado_23
    - nota_empenho_24, sei_nota_empenho_24, total_empenhado_24
    - observacoes
    """
    try:
        dados = request.get_json()
        
        # Validações básicas
        if not dados.get('numero_termo'):
            return jsonify({'success': False, 'error': 'Número do termo é obrigatório'}), 400
        
        if not dados.get('numero'):
            return jsonify({'success': False, 'error': 'Número da parcela é obrigatório'}), 400
        
        if not dados.get('responsavel'):
            return jsonify({'success': False, 'error': 'Responsável é obrigatório'}), 400
        
        if not dados.get('status'):
            return jsonify({'success': False, 'error': 'Status é obrigatório'}), 400
        
        cur = get_cursor()
        conn = get_db()
        
        # Inserir registro
        cur.execute("""
            INSERT INTO gestao_financeira.temp_acomp_empenhos (
                numero_termo,
                aditivo,
                numero,
                responsavel,
                status,
                nota_empenho_23,
                sei_nota_empenho_23,
                nota_empenho_24,
                sei_nota_empenho_24,
                total_empenhado_23,
                total_empenhado_24,
                observacoes,
                criado_em
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            ) RETURNING id
        """, (
            dados['numero_termo'],
            dados.get('aditivo'),
            dados['numero'],
            dados['responsavel'],
            dados['status'],
            dados.get('nota_empenho_23'),
            dados.get('sei_nota_empenho_23'),
            dados.get('nota_empenho_24'),
            dados.get('sei_nota_empenho_24'),
            dados.get('total_empenhado_23', 0),
            dados.get('total_empenhado_24', 0),
            dados.get('observacoes')
        ))
        
        novo_id = cur.fetchone()
        try:
            novo_id = novo_id['id']
        except (KeyError, TypeError):
            novo_id = novo_id[0] if novo_id else None
        
        conn.commit()
        
        print(f"[DEBUG] Novo encaminhamento criado: ID {novo_id}, Termo: {dados['numero_termo']}, Parcela: {dados['numero']}")
        
        return jsonify({
            'success': True,
            'message': 'Encaminhamento adicionado com sucesso',
            'id': novo_id
        })
        
    except Exception as e:
        print(f"[ERRO] api_adicionar_encaminhamento: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
