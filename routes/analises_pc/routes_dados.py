"""
Blueprint de rotas para dados e formulários do checklist de análise PC
Arquivo modular para manter routes.py mais organizado
"""

from flask import jsonify, request, Response
from . import analises_pc_bp
from db import get_db
import psycopg2
import psycopg2.extras
import traceback
import re
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


@analises_pc_bp.route('/api/buscar_dados_base', methods=['POST'])
def buscar_dados_base():
    """Busca dados base da parceria para preenchimento/conferência"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    
    print(f"[DEBUG] buscar_dados_base - numero_termo: '{numero_termo}'")
    
    if not numero_termo:
        return jsonify({'error': 'Número do termo não fornecido'}), 400
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Buscar dados da parceria
        cur.execute("""
            SELECT 
                numero_termo, osc, projeto, tipo_termo, portaria, cnpj,
                inicio, final, meses, total_previsto, total_pago, conta,
                transicao, sei_celeb, sei_pc, sei_plano, sei_orcamento, contrapartida
            FROM public.parcerias
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        parceria = cur.fetchone()
        
        if not parceria:
            cur.close()
            return jsonify({'error': 'Termo não encontrado'}), 404
        
        # Buscar pessoa gestora
        cur.execute("""
            SELECT nome_pg
            FROM public.parcerias_pg
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        pg_row = cur.fetchone()
        nome_pg = pg_row['nome_pg'] if pg_row else None
        
        # Verificar se é termo rescindido e buscar data de rescisão
        cur.execute("""
            SELECT data_rescisao
            FROM public.termos_rescisao
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        rescisao_row = cur.fetchone()
        is_rescindido = rescisao_row is not None
        data_rescisao = rescisao_row['data_rescisao'] if rescisao_row else None
        
        cur.close()
        
        # Converter data para string se necessário
        parceria_dict = dict(parceria)
        if parceria_dict.get('inicio'):
            parceria_dict['inicio'] = str(parceria_dict['inicio'])
        if parceria_dict.get('final'):
            parceria_dict['final'] = str(parceria_dict['final'])
        
        result = {
            'parceria': parceria_dict,
            'nome_pg': nome_pg,
            'is_rescindido': is_rescindido,
            'data_rescisao': str(data_rescisao) if data_rescisao else None
        }
        
        print(f"[DEBUG] Dados retornados - rescindido: {is_rescindido}, data_rescisao: {data_rescisao}, nome_pg: {nome_pg}")
        
        return jsonify(result)
    
    except Exception as e:
        cur.close()
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"[ERRO] buscar_dados_base: {error_details}")
        return jsonify(error_details), 500


@analises_pc_bp.route('/api/listar_portarias', methods=['GET'])
def listar_portarias():
    """Lista todas as portarias/legislações do sistema"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("""
            SELECT DISTINCT lei
            FROM categoricas.c_legislacao
            WHERE lei IS NOT NULL AND lei != ''
            ORDER BY lei
        """)
        portarias = cur.fetchall()
        cur.close()
        
        return jsonify({
            'portarias': portarias
        })
    
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/listar_pessoas_gestoras', methods=['GET'])
def listar_pessoas_gestoras():
    """Lista todas as pessoas gestoras do sistema"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("""
            SELECT nome_pg, setor, numero_rf, status_pg
            FROM categoricas.c_pessoa_gestora
            ORDER BY nome_pg
        """)
        pessoas_gestoras = cur.fetchall()
        cur.close()
        
        return jsonify({
            'pessoas_gestoras': pessoas_gestoras
        })
    
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/salvar_dados_base', methods=['POST'])
def salvar_dados_base():
    """Salva/atualiza dados base da parceria"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    dados = data.get('dados', {})
    
    print(f"[DEBUG] salvar_dados_base - numero_termo: '{numero_termo}'")
    print(f"[DEBUG] Dados recebidos: {dados}")
    
    if not numero_termo:
        return jsonify({'error': 'Número do termo não fornecido'}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Construir UPDATE apenas com campos que têm valores
        campos_update = []
        valores = []
        
        # Mapeamento de campos do formulário para colunas do banco
        campos_permitidos = {
            'osc': 'osc',
            'projeto': 'projeto',
            'tipo_termo': 'tipo_termo',
            'portaria': 'portaria',
            'cnpj': 'cnpj',
            'inicio': 'inicio',
            'final': 'final',
            'total_previsto': 'total_previsto',
            'total_pago': 'total_pago',
            'conta': 'conta',
            'transicao': 'transicao',
            'sei_celeb': 'sei_celeb',
            'sei_pc': 'sei_pc',
            'sei_plano': 'sei_plano',
            'sei_orcamento': 'sei_orcamento',
            'contrapartida': 'contrapartida'
        }
        
        for campo_form, campo_db in campos_permitidos.items():
            if campo_form in dados and dados[campo_form] != '':
                campos_update.append(f"{campo_db} = %s")
                
                # Converter valores especiais
                valor = dados[campo_form]
                if campo_form in ['transicao', 'contrapartida']:
                    valor = int(valor) if valor else 0
                elif campo_form in ['total_previsto', 'total_pago']:
                    # Remover formatação monetária se houver
                    valor = valor.replace('.', '').replace(',', '.') if isinstance(valor, str) else valor
                    valor = float(valor) if valor else None
                
                valores.append(valor)
        
        if campos_update:
            valores.append(numero_termo)
            query = f"""
                UPDATE public.parcerias
                SET {', '.join(campos_update)}
                WHERE TRIM(numero_termo) = TRIM(%s)
            """
            print(f"[DEBUG] Query UPDATE: {query}")
            print(f"[DEBUG] Valores: {valores}")
            cur.execute(query, valores)
        
        # Atualizar pessoa gestora se fornecida
        if 'nome_pg' in dados and dados['nome_pg']:
            # Verificar se já existe registro
            cur.execute("""
                SELECT 1 FROM public.parcerias_pg
                WHERE TRIM(numero_termo) = TRIM(%s)
            """, (numero_termo,))
            
            if cur.fetchone():
                cur.execute("""
                    UPDATE public.parcerias_pg
                    SET nome_pg = %s
                    WHERE TRIM(numero_termo) = TRIM(%s)
                """, (dados['nome_pg'], numero_termo))
            else:
                cur.execute("""
                    INSERT INTO public.parcerias_pg (numero_termo, nome_pg)
                    VALUES (%s, %s)
                """, (numero_termo, dados['nome_pg']))
        
        conn.commit()
        cur.close()
        
        print(f"[DEBUG] Dados salvos com sucesso!")
        
        return jsonify({
            'success': True,
            'message': 'Dados atualizados com sucesso'
        })
    
    except Exception as e:
        conn.rollback()
        cur.close()
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"[ERRO] salvar_dados_base: {error_details}")
        return jsonify(error_details), 500


@analises_pc_bp.route('/api/exportar_dados_base_pdf', methods=['GET'])
def exportar_dados_base_pdf():
    """Exporta os dados base da parceria para PDF"""
    try:
        # Obter número do termo da query string
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return "Número do termo não informado", 400
        
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Buscar dados da parceria
        cur.execute("""
            SELECT 
                numero_termo, osc, projeto, tipo_termo, portaria, cnpj,
                inicio, final, meses, total_previsto, total_pago, conta,
                transicao, sei_celeb, sei_pc, sei_plano, sei_orcamento, contrapartida
            FROM public.parcerias
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        parceria = cur.fetchone()
        
        if not parceria:
            cur.close()
            return "Termo não encontrado", 404
        
        # Buscar pessoa gestora
        cur.execute("""
            SELECT nome_pg
            FROM public.parcerias_pg
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        pg_row = cur.fetchone()
        nome_pg = pg_row['nome_pg'] if pg_row else None
        
        # Verificar se é termo rescindido
        cur.execute("""
            SELECT 1
            FROM public.termos_rescisao
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        is_rescindido = cur.fetchone() is not None
        
        cur.close()
        
        # Criar PDF em memória
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        # Container para os elementos do PDF
        elements = []
        styles = getSampleStyleSheet()
        
        # Estilo personalizado para o título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#17a2b8'),
            spaceAfter=20,
            alignment=1
        )
        
        # Estilo para subtítulos de seção
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#ffffff'),
            backColor=colors.HexColor('#6c757d'),
            spaceAfter=12,
            spaceBefore=12,
            leftIndent=5,
            rightIndent=5,
            leading=16
        )
        
        # Título principal
        titulo = Paragraph("✏️ Dados Base da Parceria", title_style)
        elements.append(titulo)
        
        # Alerta de rescisão
        if is_rescindido:
            alerta_style = ParagraphStyle(
                'Alert',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#842029'),
                backColor=colors.HexColor('#f8d7da'),
                borderColor=colors.HexColor('#f5c2c7'),
                borderWidth=1,
                borderPadding=10,
                spaceAfter=20
            )
            alerta = Paragraph("<b>⚠ ATENÇÃO:</b> Este termo consta como <b>RESCINDIDO</b> no sistema.", alerta_style)
            elements.append(alerta)
        
        elements.append(Spacer(1, 0.3*cm))
        
        # SEÇÃO 1: Identificação
        elements.append(Paragraph("IDENTIFICAÇÃO DO TERMO", section_style))
        dados_identificacao = [
            ['Número do Termo:', parceria['numero_termo'] or '-'],
            ['Tipo de Termo:', parceria['tipo_termo'] or '-'],
            ['OSC:', parceria['osc'] or '-'],
            ['Projeto:', parceria['projeto'] or '-'],
            ['Portaria:', parceria['portaria'] or '-'],
            ['CNPJ:', parceria['cnpj'] or '-']
        ]
        
        tabela_id = Table(dados_identificacao, colWidths=[5*cm, 12*cm])
        tabela_id.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(tabela_id)
        elements.append(Spacer(1, 0.5*cm))
        
        # SEÇÃO 2: Vigência e Valores
        elements.append(Paragraph("VIGÊNCIA E VALORES", section_style))
        
        data_inicio_fmt = parceria['inicio'].strftime('%d/%m/%Y') if parceria['inicio'] else '-'
        data_final_fmt = parceria['final'].strftime('%d/%m/%Y') if parceria['final'] else '-'
        total_previsto = float(parceria['total_previsto'] or 0)
        total_pago = float(parceria['total_pago'] or 0)
        total_previsto_fmt = f"R$ {total_previsto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        total_pago_fmt = f"R$ {total_pago:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        dados_vigencia = [
            ['Data de Início:', data_inicio_fmt],
            ['Data de Término:', data_final_fmt],
            ['Meses:', str(parceria['meses']) if parceria['meses'] is not None else '-'],
            ['Total Previsto:', total_previsto_fmt],
            ['Total Pago:', total_pago_fmt]
        ]
        
        tabela_vig = Table(dados_vigencia, colWidths=[5*cm, 12*cm])
        tabela_vig.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(tabela_vig)
        elements.append(Spacer(1, 0.5*cm))
        
        # SEÇÃO 3: Dados Bancários
        elements.append(Paragraph("DADOS BANCÁRIOS E CARACTERÍSTICAS", section_style))
        
        transicao_txt = 'Sim' if parceria['transicao'] == 1 else 'Não' if parceria['transicao'] == 0 else '-'
        contrapartida_txt = 'Sim' if parceria['contrapartida'] == 1 else 'Não' if parceria['contrapartida'] == 0 else '-'
        
        dados_bancarios = [
            ['Conta:', parceria['conta'] or '-'],
            ['É transição de Portaria?', transicao_txt],
            ['Tem contrapartida?', contrapartida_txt]
        ]
        
        tabela_banc = Table(dados_bancarios, colWidths=[5*cm, 12*cm])
        tabela_banc.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(tabela_banc)
        elements.append(Spacer(1, 0.5*cm))
        
        # SEÇÃO 4: Processos SEI
        elements.append(Paragraph("PROCESSOS SEI", section_style))
        
        dados_sei = [
            ['SEI Celebração:', parceria['sei_celeb'] or '-'],
            ['SEI Prestação de Contas:', parceria['sei_pc'] or '-'],
            ['SEI Plano de Trabalho:', parceria['sei_plano'] or '-'],
            ['SEI Orçamento:', parceria['sei_orcamento'] or '-']
        ]
        
        tabela_sei = Table(dados_sei, colWidths=[5*cm, 12*cm])
        tabela_sei.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(tabela_sei)
        elements.append(Spacer(1, 0.5*cm))
        
        # SEÇÃO 5: Pessoa Gestora
        if nome_pg:
            elements.append(Paragraph("PESSOA GESTORA", section_style))
            
            dados_pg = [['Nome da Pessoa Gestora:', nome_pg]]
            
            tabela_pg = Table(dados_pg, colWidths=[5*cm, 12*cm])
            tabela_pg.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(tabela_pg)
            elements.append(Spacer(1, 0.5*cm))
        
        # Rodapé
        elements.append(Spacer(1, 1*cm))
        data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M')
        rodape = Paragraph(f"<i>Documento gerado em {data_geracao}</i>", 
                          ParagraphStyle('Footer', parent=styles['Normal'], 
                                       fontSize=8, textColor=colors.grey))
        elements.append(rodape)
        
        # Gerar PDF
        doc.build(elements)
        
        # Preparar resposta
        buffer.seek(0)
        filename = f'dados_base_{numero_termo.replace("/", "-")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao gerar PDF: {e}")
        traceback.print_exc()
        return f"Erro ao gerar PDF: {str(e)}", 500


@analises_pc_bp.route('/api/verificar_orcamento', methods=['POST'])
def verificar_orcamento():
    """Verifica se o termo possui orçamento anual cadastrado"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    
    print(f"[DEBUG] verificar_orcamento - numero_termo: '{numero_termo}'")
    
    if not numero_termo:
        return jsonify({'error': 'Número do termo não fornecido'}), 400
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Verificar se existe orçamento para o termo
        cur.execute("""
            SELECT COUNT(*) as total
            FROM public.parcerias_despesas
            WHERE TRIM(numero_termo) = TRIM(%s)
        """, (numero_termo,))
        
        result = cur.fetchone()
        tem_orcamento = result['total'] > 0
        
        cur.close()
        
        # Construir URL de redirecionamento
        # Formato: /orcamento/editar/TCL/001/2017/SMDHC/CPLGBTI
        termo_parts = numero_termo.split('/')
        if len(termo_parts) >= 5:
            url_orcamento = f"/orcamento/editar/{'/'.join(termo_parts)}"
        else:
            url_orcamento = f"/orcamento/editar/{numero_termo}"
        
        return jsonify({
            'tem_orcamento': tem_orcamento,
            'url_orcamento': url_orcamento,
            'total_despesas': result['total']
        })
    
    except Exception as e:
        cur.close()
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"[ERRO] verificar_orcamento: {error_details}")
        return jsonify(error_details), 500


@analises_pc_bp.route('/api/listar-informacoes-pg', methods=['GET'])
def listar_informacoes_pg():
    """Lista todas as Informações à Pessoa Gestora cadastradas"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("""
            SELECT id, numero_doc, ano_doc, numero_termo
            FROM public.parcerias_notificacoes
            WHERE tipo_doc = 'Informação à Pessoa Gestora'
            ORDER BY ano_doc DESC, numero_doc DESC
        """)
        
        informacoes = cur.fetchall()
        cur.close()
        
        return jsonify({'informacoes': informacoes})
    
    except Exception as e:
        cur.close()
        print(f"[ERRO] listar_informacoes_pg: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/dados-informacao-pg/<int:informacao_id>', methods=['GET'])
def dados_informacao_pg(informacao_id):
    """Busca dados completos de uma informação específica (com join em parcerias)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                pn.numero_termo,
                p.osc,
                p.projeto,
                p.portaria
            FROM public.parcerias_notificacoes pn
            LEFT JOIN public.parcerias p ON p.numero_termo = pn.numero_termo
            WHERE pn.id = %s
            LIMIT 1
        """, (informacao_id,))
        
        resultado = cur.fetchone()
        cur.close()
        
        if not resultado:
            return jsonify({'error': 'Informação não encontrada'}), 404
        
        return jsonify(dict(resultado))
    
    except Exception as e:
        cur.close()
        print(f"[ERRO] dados_informacao_pg: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/gerar-texto-ausencia-extratos', methods=['POST'])
def gerar_texto_ausencia_extratos():
    """Gera texto substituindo placeholders no modelo"""
    data = request.get_json()
    
    # Validar dados recebidos
    numero_informacao = data.get('numero_informacao', '')
    numero_termo = data.get('numero_termo', '')
    osc = data.get('osc', '')
    projeto = data.get('projeto', '')
    portaria = data.get('portaria', '')
    sei_termo = data.get('sei_termo', '')
    possui_conciliacao = data.get('possui_conciliacao', False)
    
    if not all([numero_informacao, numero_termo, osc, projeto, portaria, sei_termo]):
        return jsonify({'error': 'Dados incompletos'}), 400
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Buscar modelo de texto
        cur.execute("""
            SELECT modelo_texto
            FROM categoricas.c_modelo_textos
            WHERE titulo_texto = 'Análise de Contas: Ausência de extratos bancários pós-2023'
            LIMIT 1
        """)
        
        resultado = cur.fetchone()
        cur.close()
        
        if not resultado or not resultado['modelo_texto']:
            return jsonify({'error': 'Modelo de texto não encontrado'}), 404
        
        texto = resultado['modelo_texto']
        
        # Log para debug
        print(f"[DEBUG] Texto original (primeiros 500 chars): {texto[:500]}")
        print(f"[DEBUG] Dados recebidos:")
        print(f"  - numero_informacao: '{numero_informacao}'")
        print(f"  - numero_termo: '{numero_termo}'")
        print(f"  - osc: '{osc}'")
        print(f"  - projeto: '{projeto}'")
        print(f"  - portaria: '{portaria}'")
        print(f"  - sei_termo: '{sei_termo}'")
        print(f"  - possui_conciliacao: {possui_conciliacao}")
        
        # Substituir placeholders básicos (sem colchetes e com colchetes)
        texto = texto.replace('numero_informacao_usuario', numero_informacao)
        texto = texto.replace('[numero_informacao_usuario]', numero_informacao)
        
        texto = texto.replace('termo_usuario', numero_termo)
        texto = texto.replace('[termo_usuario]', numero_termo)
        
        texto = texto.replace('osc_usuario', osc)
        texto = texto.replace('[osc_usuario]', osc)
        
        texto = texto.replace('projeto_usuario', projeto)
        texto = texto.replace('[projeto_usuario]', projeto)
        
        texto = texto.replace('portaria_usuario', portaria)
        texto = texto.replace('[portaria_usuario]', portaria)
        
        texto = texto.replace('sei_informado_termo_usuario', sei_termo)
        texto = texto.replace('[sei_informado_termo_usuario]', sei_termo)
        
        # Substituir SEI de solicitação
        sei_solicitacao = data.get('sei_solicitacao', '')
        texto = texto.replace('sei_informado_1', sei_solicitacao)
        texto = texto.replace('[sei_informado_1]', sei_solicitacao)
        
        # Substituir SEI do relatório sintético
        sei_relatorio = data.get('sei_relatorio', '')
        texto = texto.replace('sei_informado_relatorio_usuario', sei_relatorio)
        texto = texto.replace('[sei_informado_relatorio_usuario]', sei_relatorio)
        
        # Substituição condicional: possui conciliação
        if possui_conciliacao:
            texto = texto.replace('opcao_1_usuario', 'contendo apenas a conciliação bancária, ')
            texto = texto.replace('[opcao_1_usuario]', 'contendo apenas a conciliação bancária, ')
        else:
            texto = texto.replace('opcao_1_usuario', '')
            texto = texto.replace('[opcao_1_usuario]', '')
        
        # Substituição condicional: artigos baseados na portaria
        if '021/2023' in portaria or '21/2023' in portaria:
            artigo_1 = '60, 64 §3º, 67, 80 §3º'
            artigo_2 = ' 72 §2º e Artigo 59'
        else:  # Portaria 090/2023 ou outras
            artigo_1 = '64, 67 §3º, 71, 77 §2º e 81 §3º'
            artigo_2 = ' 74 §2º e artigo 63'
        
        texto = texto.replace('numero_artigo_1_usuario', artigo_1)
        texto = texto.replace('[numero_artigo_1_usuario]', artigo_1)
        
        texto = texto.replace('numero_artigo_2_usuario', artigo_2)
        texto = texto.replace('[numero_artigo_2_usuario]', artigo_2)
        
        print(f"[DEBUG] Texto após substituições (primeiros 500 chars): {texto[:500]}")
        
        return jsonify({'texto_gerado': texto})
    
    except Exception as e:
        cur.close()
        print(f"[ERRO] gerar_texto_ausencia_extratos: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# API: Listar Relatórios de Inconsistências Disponíveis
# ============================================================
@analises_pc_bp.route('/api/listar-relatorios-inconsistencias', methods=['GET'])
def listar_relatorios_inconsistencias():
    """
    Lista todos os Relatórios de Inconsistências disponíveis.
    Filtra por tipo_doc = 'Relatório de Inconsistências' em public.parcerias_notificacoes
    """
    print("[DEBUG] ========================================")
    print("[DEBUG] API: /api/listar-relatorios-inconsistencias")
    print("[DEBUG] ========================================")
    
    cur = None
    try:
        print("[DEBUG] Obtendo cursor do banco...")
        cur = get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Query com variações do nome do tipo de documento
        query = """
            SELECT 
                pn.id,
                pn.numero_doc,
                pn.ano_doc,
                pn.numero_termo,
                p.osc,
                p.projeto
            FROM public.parcerias_notificacoes pn
            LEFT JOIN public.parcerias p ON p.numero_termo = pn.numero_termo
            WHERE pn.tipo_doc ILIKE %s
            ORDER BY pn.ano_doc DESC, pn.numero_doc DESC
        """
        
        print("[DEBUG] Executando query...")
        # Usar ILIKE para ignorar case e acentos potenciais
        cur.execute(query, ('%Relatório%Inconsistências%',))
        
        print("[DEBUG] Fazendo fetchall()...")
        resultados = cur.fetchall()
        
        print(f"[DEBUG] ✅ Encontrados {len(resultados)} relatórios de inconsistências")
        
        relatorios = []
        for row in resultados:
            relatorios.append({
                'id': row['id'],
                'numero_doc': row['numero_doc'],
                'ano_doc': row['ano_doc'],
                'numero_termo': row['numero_termo'] or '',
                'osc': row['osc'] or '',
                'projeto': row['projeto'] or '',
                'formatado': f"{row['numero_doc']}/{row['ano_doc']}"
            })
        
        return jsonify({'dados': relatorios})
    
    except Exception as e:
        print(f"[ERRO] listar_relatorios_inconsistencias: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cur:
            cur.close()

# ============================================================
# API: Buscar Meses Disponíveis para Análise (por termo)
# ============================================================
@analises_pc_bp.route('/api/meses-disponiveis/<path:numero_termo>', methods=['GET'])
def meses_disponiveis_termo(numero_termo):
    """
    Retorna os meses disponíveis na tabela analises_pc.conc_extrato
    para um determinado termo.
    """
    cur = None
    try:
        cur = get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print(f"[DEBUG] Buscando meses para termo: {numero_termo}")
        
        query = """
            SELECT DISTINCT 
                DATE_TRUNC('month', data) AS mes
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s
            ORDER BY mes ASC
        """
        
        cur.execute(query, (numero_termo,))
        resultados = cur.fetchall()
        
        print(f"[DEBUG] Encontrados {len(resultados)} meses distintos")
        
        meses = []
        for row in resultados:
            if row['mes']:
                # Formatar como "janeiro/2024"
                mes_obj = row['mes']
                meses_nomes = {
                    1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril',
                    5: 'maio', 6: 'junho', 7: 'julho', 8: 'agosto',
                    9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
                }
                mes_nome = meses_nomes.get(mes_obj.month, str(mes_obj.month))
                ano = mes_obj.year
                meses.append({
                    'valor': f"{mes_nome}/{ano}",
                    'data_iso': mes_obj.strftime('%Y-%m-%d')
                })
        
        return jsonify({'meses': meses})
    
    except Exception as e:
        print(f"[ERRO] meses_disponiveis_termo: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cur:
            cur.close()

# ============================================================
# API: Gerar Texto do Relatório de Inconsistências
# ============================================================
@analises_pc_bp.route('/api/gerar-texto-relatorio-inconsistencias', methods=['POST'])
def gerar_texto_relatorio_inconsistencias():
    """
    Gera o texto do Relatório de Inconsistências com substituição de variáveis.
    
    Espera JSON:
    {
        "numero_doc": "123",
        "ano_doc": "2024",
        "numero_termo": "001/2023",
        "mes_inicio": "agosto/2024",
        "mes_fim": "dezembro/2025"
    }
    """
    try:
        data = request.get_json()
        
        numero_doc = data.get('numero_doc', '')
        ano_doc = data.get('ano_doc', '')
        numero_termo = data.get('numero_termo', '')
        mes_inicio = data.get('mes_inicio', '')
        mes_fim = data.get('mes_fim', '')
        
        if not numero_doc or not ano_doc or not numero_termo:
            return jsonify({'error': 'Parâmetros obrigatórios: numero_doc, ano_doc, numero_termo'}), 400
        
        cur = get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Buscar dados da parceria
        query_parceria = """
            SELECT 
                p.osc,
                p.projeto,
                p.portaria,
                p.sei_pc
            FROM public.parcerias p
            WHERE p.numero_termo = %s
        """
        
        cur.execute(query_parceria, (numero_termo,))
        parceria = cur.fetchone()
        
        if not parceria:
            cur.close()
            return jsonify({'error': 'Termo não encontrado'}), 404
        
        osc = parceria['osc'] or ''
        projeto = parceria['projeto'] or ''
        portaria = parceria['portaria'] or ''
        sei_pagamento = parceria['sei_pc'] or ''
        
        # Determinar qual modelo usar baseado na portaria
        if '121' in portaria or '140' in portaria:
            titulo_modelo = 'Análise de Contas: Relatório de Inconsistências'
            print(f"[DEBUG] Portaria 121/140 detectada - usando modelo padrão")
        elif '021' in portaria or '090' in portaria:
            titulo_modelo = 'Análise de Contas: Relatório de Inconsistências pós-2023'
            print(f"[DEBUG] Portaria 021/090 detectada - usando modelo pós-2023")
        else:
            # Fallback para modelo padrão
            titulo_modelo = 'Análise de Contas: Relatório de Inconsistências'
            print(f"[DEBUG] Portaria não identificada - usando modelo padrão")
        
        # Buscar template do modelo de texto
        query_modelo = """
            SELECT titulo_texto, modelo_texto 
            FROM categoricas.c_modelo_textos 
            WHERE titulo_texto = %s
        """
        
        cur.execute(query_modelo, (titulo_modelo,))
        resultado = cur.fetchone()
        cur.close()
        
        if not resultado or not resultado['modelo_texto']:
            return jsonify({'error': f'Modelo de texto "{titulo_modelo}" não encontrado'}), 404
        
        texto = resultado['modelo_texto']
        print(f"[DEBUG] Modelo carregado: {titulo_modelo}")
        
        # ======= SUBSTITUIÇÕES DE VARIÁVEIS =======
        
        # 1. numero_informacao_usuario = numero_doc/ano_doc
        numero_informacao_formatado = f"{numero_doc}/{ano_doc}"
        texto = texto.replace('numero_informacao_usuario', numero_informacao_formatado)
        
        # 2. sei_pagamento_usuario = sei_pc
        texto = texto.replace('sei_pagamento_usuario', sei_pagamento)
        
        # 3. osc_usuario
        texto = texto.replace('osc_usuario', osc)
        
        # 4. projeto_usuario
        texto = texto.replace('projeto_usuario', projeto)
        
        # 5. termo_usuario
        texto = texto.replace('termo_usuario', numero_termo)
        
        # 6. meses_usuario = "mes_inicio a mes_fim"
        if mes_inicio and mes_fim:
            periodo = f"{mes_inicio} a {mes_fim}"
        elif mes_inicio:
            periodo = mes_inicio
        else:
            periodo = '[período não informado]'
        texto = texto.replace('meses_usuario', periodo)
        
        # 7. portaria_usuario
        texto = texto.replace('portaria_usuario', portaria)
        
        # 8. numero_artigo_1_usuario - Lógica condicional baseada na portaria
        if '121/SMDHC/2019' in portaria or '121/2019' in portaria:
            numero_artigo_1 = '95'
        elif '140/SMDHC/2019' in portaria or '140/2019' in portaria:
            numero_artigo_1 = '98'
        elif '021/SMDHC/2023' in portaria or '021/2023' in portaria or '21/2023' in portaria:
            numero_artigo_1 = '75'
        elif '090/SMDHC/2023' in portaria or '090/2023' in portaria or '90/2023' in portaria:
            numero_artigo_1 = '77'
        else:
            numero_artigo_1 = '[artigo não identificado]'
        
        texto = texto.replace('numero_artigo_1_usuario', numero_artigo_1)
        
        # ============================================================
        # BUSCAR E FORMATAR INCONSISTÊNCIAS EM HTML
        # ============================================================
        print(f"[DEBUG] Buscando inconsistências ratificadas para termo: {numero_termo}")
        
        cur = get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. Buscar da tabela padrão (com transações)
        cur.execute("""
            SELECT 
                li.nome_item,
                ce.data,
                ce.credito,
                ce.debito,
                ce.discriminacao,
                ce.cat_transacao,
                ce.competencia,
                ce.origem_destino,
                ce.indice
            FROM analises_pc.lista_inconsistencias li
            INNER JOIN analises_pc.conc_extrato ce ON li.id_conc_extrato = ce.id
            WHERE li.numero_termo = %s
            ORDER BY li.nome_item, ce.data, ce.indice
        """, (numero_termo,))
        transacoes_padrao = cur.fetchall()
        
        # 2. Buscar da tabela global (sem transações) e textos processados
        cur.execute("""
            SELECT DISTINCT nome_item, texto
            FROM analises_pc.lista_inconsistencias_globais
            WHERE numero_termo = %s
        """, (numero_termo,))
        dados_globais = cur.fetchall()
        inconsistencias_globais = [row['nome_item'] for row in dados_globais]
        
        # Criar dicionário de textos processados
        texto_processado_globais = {row['nome_item']: row['texto'] for row in dados_globais if row['texto']}
        
        # 3. Buscar da tabela agregada (dados especiais)
        cur.execute("""
            SELECT 
                nome_item,
                campo1,
                campo2,
                valor_previsto,
                valor_executado,
                diferenca
            FROM analises_pc.lista_inconsistencias_agregadas
            WHERE numero_termo = %s
            ORDER BY nome_item, campo1, campo2
        """, (numero_termo,))
        transacoes_agregadas = cur.fetchall()
        
        # Organizar transações por nome_item
        transacoes_por_item = {}
        for t in transacoes_padrao:
            nome = t['nome_item']
            if nome not in transacoes_por_item:
                transacoes_por_item[nome] = []
            transacoes_por_item[nome].append(t)
        
        # Organizar agregadas por nome_item
        agregadas_por_item = {}
        for t in transacoes_agregadas:
            nome = t['nome_item']
            if nome not in agregadas_por_item:
                agregadas_por_item[nome] = []
            agregadas_por_item[nome].append(t)
        
        # Buscar modelos de texto para todas as inconsistências encontradas
        todos_nomes = list(set(
            list(transacoes_por_item.keys()) + 
            inconsistencias_globais + 
            list(agregadas_por_item.keys())
        ))
        
        if todos_nomes:
            cur.execute("""
                SELECT id, nome_item, modelo_texto, ordem
                FROM categoricas.c_modelo_textos_inconsistencias
                WHERE nome_item = ANY(%s)
                ORDER BY ordem
            """, (todos_nomes,))
            modelos_inconsistencias = cur.fetchall()
        else:
            modelos_inconsistencias = []
        
        cur.close()
        
        print(f"[DEBUG] Encontradas {len(modelos_inconsistencias)} inconsistências ratificadas")
        
        # ============================================================
        # FORMATAR LISTA DE INCONSISTÊNCIAS EM HTML RICO
        # ============================================================
        lista_formatada_html = '<ol>'
        
        if modelos_inconsistencias:
            for idx, modelo in enumerate(modelos_inconsistencias, start=1):
                nome = modelo['nome_item']
                
                # Usar texto processado do banco se disponível, senão usar modelo padrão
                if nome in texto_processado_globais:
                    texto_inc = texto_processado_globais[nome]
                else:
                    texto_inc = modelo['modelo_texto']
                
                # Limpar HTML do texto (remover tags, manter apenas conteúdo)
                texto_inc_limpo = re.sub(r'<[^>]+>', '', texto_inc)
                
                # Abrir item da lista
                lista_formatada_html += f'<li class="Texto_Justificado" style="margin-bottom: 11px;">'
                lista_formatada_html += f'<p class="Texto_Justificado"><b>{nome}:&nbsp;</b>{texto_inc_limpo}<br></p>'
                
                # ========== ADICIONAR TABELA SE HOUVER TRANSAÇÕES PADRÃO ==========
                if nome in transacoes_por_item and transacoes_por_item[nome]:
                    transacoes = transacoes_por_item[nome]
                    
                    lista_formatada_html += '<p class="Texto_Justificado">&nbsp;Transações Identificadas</p>'
                    lista_formatada_html += '<div><table style="border-color: rgb(222, 226, 230); margin-bottom: 16px; margin-left: auto; margin-right: auto; vertical-align: top; width: 100%;" class="table table-bordered">'
                    
                    # Cabeçalho da tabela
                    lista_formatada_html += '<thead style="border-color: rgb(55, 59, 62); background-color: #212529; color: rgb(255, 255, 255); vertical-align: bottom;"><tr>'
                    lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Índice</th>'
                    lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Data</th>'
                    lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Crédito (R$)</th>'
                    lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Débito (R$)</th>'
                    lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Discriminação (R$)</th>'
                    lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Categoria</th>'
                    lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Competência</th>'
                    lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255);">Origem/Destino</th>'
                    lista_formatada_html += '</tr></thead>'
                    
                    # Corpo da tabela
                    lista_formatada_html += '<tbody style="vertical-align: inherit;">'
                    for t in transacoes:
                        credito = f"R$ {float(t['credito'] or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if t['credito'] else 'R$ 0,00'
                        debito = f"R$ {float(t['debito'] or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if t['debito'] else 'R$ 0,00'
                        discriminacao = f"R$ {float(t['discriminacao'] or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if t['discriminacao'] else 'R$ 0,00'
                        data_fmt = t['data'].strftime('%d/%m/%Y') if t['data'] else '-'
                        indice = t['indice'] if t['indice'] else '-'
                        categoria = t['cat_transacao'] if t['cat_transacao'] else '-'
                        competencia = t['competencia'] if t['competencia'] else '-'
                        origem_destino = t['origem_destino'] if t['origem_destino'] else '-'
                        
                        lista_formatada_html += '<tr>'
                        lista_formatada_html += f'<td style="padding: 0.25rem; text-align: center !important;">{indice}</td>'
                        lista_formatada_html += f'<td style="padding: 0.25rem; text-align: center !important;">{data_fmt}</td>'
                        lista_formatada_html += f'<td style="padding: 0.25rem; text-align: right !important;">{credito}</td>'
                        lista_formatada_html += f'<td style="padding: 0.25rem; text-align: right !important;">{debito}</td>'
                        lista_formatada_html += f'<td style="padding: 0.25rem; text-align: right !important;">{discriminacao}</td>'
                        lista_formatada_html += f'<td style="padding: 0.25rem; text-align: center !important;">{categoria}</td>'
                        lista_formatada_html += f'<td style="padding: 0.25rem; text-align: center !important;">{competencia}</td>'
                        lista_formatada_html += f'<td style="padding: 0.25rem;">{origem_destino}</td>'
                        lista_formatada_html += '</tr>'
                    
                    lista_formatada_html += '</tbody></table></div>'
                
                # ========== ADICIONAR TABELA AGREGADA (Cards 17, 18, 21, 22) ==========
                elif nome in agregadas_por_item and agregadas_por_item[nome]:
                    dados = agregadas_por_item[nome]
                    
                    # Card 17: Divergências trimestrais (campo1=rubrica, campo2=trimestre)
                    if dados[0].get('campo2') and str(dados[0]['campo2']).isdigit() and int(dados[0]['campo2']) <= 4:
                        lista_formatada_html += '<p class="Texto_Justificado">&nbsp;Divergências Identificadas</p>'
                        lista_formatada_html += '<div><table style="border-color: rgb(222, 226, 230); margin-bottom: 16px; margin-left: auto; margin-right: auto; vertical-align: top; width: 100%;" class="table table-bordered">'
                        
                        # Cabeçalho
                        lista_formatada_html += '<thead style="border-color: rgb(55, 59, 62); background-color: #212529; color: rgb(255, 255, 255); vertical-align: bottom;"><tr>'
                        lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Rubrica</th>'
                        lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Trimestre</th>'
                        lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Previsto</th>'
                        lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Executado</th>'
                        lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Diferença</th>'
                        lista_formatada_html += '</tr></thead>'
                        
                        # Corpo
                        lista_formatada_html += '<tbody style="vertical-align: inherit;">'
                        for d in dados:
                            previsto = f"R$ {float(d['valor_previsto'] or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                            executado = f"R$ {float(d['valor_executado'] or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                            diferenca = f"R$ {float(d['diferenca'] or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                            
                            lista_formatada_html += '<tr>'
                            lista_formatada_html += f'<td style="padding: 0.25rem; text-align: center !important;">{d["campo1"]}</td>'
                            lista_formatada_html += f'<td style="padding: 0.25rem; text-align: center !important;">{d["campo2"]}º Trimestre</td>'
                            lista_formatada_html += f'<td style="padding: 0.25rem; text-align: right !important;">{previsto}</td>'
                            lista_formatada_html += f'<td style="padding: 0.25rem; text-align: right !important;">{executado}</td>'
                            lista_formatada_html += f'<td style="padding: 0.25rem; text-align: right !important;">{diferenca}</td>'
                            lista_formatada_html += '</tr>'
                        
                        lista_formatada_html += '</tbody></table></div>'
                    
                    # Distinguir entre Card 18 (Despesas sem previsão) e Cards 21/22 (Aplicações)
                    elif dados[0].get('valor_executado') or dados[0].get('campo1'):
                        # Verificar se é Card 18 (tem campo2 como mês numérico E valor_executado)
                        # Cards 21/22 têm campo1 como data (formato YYYY-MM-DD ou DD/MM/YYYY)
                        primeiro_campo1 = str(dados[0].get('campo1', ''))
                        eh_card_18 = dados[0].get('valor_executado') and dados[0].get('campo2') and not ('-' in primeiro_campo1 or '/' in primeiro_campo1)
                        
                        if eh_card_18:
                            # Card 18: Despesas sem previsão
                            lista_formatada_html += '<p class="Texto_Justificado">&nbsp;Despesas sem previsão identificadas</p>'
                            lista_formatada_html += '<div><table style="border-color: rgb(222, 226, 230); margin-bottom: 16px; margin-left: auto; margin-right: auto; vertical-align: top; width: 100%;" class="table table-bordered">'
                            
                            # Cabeçalho
                            lista_formatada_html += '<thead style="border-color: rgb(55, 59, 62); background-color: #212529; color: rgb(255, 255, 255); vertical-align: bottom;"><tr>'
                            lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Categoria</th>'
                            lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Mês</th>'
                            lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Valor Executado</th>'
                            lista_formatada_html += '</tr></thead>'
                            
                            # Corpo
                            lista_formatada_html += '<tbody style="vertical-align: inherit;">'
                            for d in dados:
                                executado = f"R$ {float(d['valor_executado'] or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                
                                lista_formatada_html += '<tr>'
                                lista_formatada_html += f'<td style="padding: 0.25rem; text-align: center !important;">{d["campo1"]}</td>'
                                lista_formatada_html += f'<td style="padding: 0.25rem; text-align: center !important;">{d["campo2"]}º mês</td>'
                                lista_formatada_html += f'<td style="padding: 0.25rem; text-align: right !important;">{executado}</td>'
                                lista_formatada_html += '</tr>'
                            
                            lista_formatada_html += '</tbody></table></div>'
                        else:
                            # Cards 21/22: Aplicação 48h / Aplicação Divergente (apenas Data e Valor)
                            lista_formatada_html += '<p class="Texto_Justificado">&nbsp;Aplicações Identificadas</p>'
                            lista_formatada_html += '<div><table style="border-color: rgb(222, 226, 230); margin-bottom: 16px; margin-left: auto; margin-right: auto; vertical-align: top; width: 100%;" class="table table-bordered">'
                            
                            # Cabeçalho
                            lista_formatada_html += '<thead style="border-color: rgb(55, 59, 62); background-color: #212529; color: rgb(255, 255, 255); vertical-align: bottom;"><tr>'
                            lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Data</th>'
                            lista_formatada_html += '<th style="padding: 0.25rem; background-color: rgb(33, 37, 41); color: rgb(255, 255, 255); text-align: center !important;">Valor (R$)</th>'
                            lista_formatada_html += '</tr></thead>'
                            
                            # Corpo
                            lista_formatada_html += '<tbody style="vertical-align: inherit;">'
                            for d in dados:
                                # campo1 contém a data
                                data_str = d['campo1'] if d['campo1'] else '-'
                                
                                # Converter data para formato brasileiro (dd/mm/yyyy)
                                if data_str != '-':
                                    try:
                                        # Se está no formato YYYY-MM-DD
                                        if '-' in data_str and len(data_str) == 10:
                                            partes = data_str.split('-')
                                            data_aplicacao = f"{partes[2]}/{partes[1]}/{partes[0]}"
                                        else:
                                            data_aplicacao = data_str
                                    except:
                                        data_aplicacao = data_str
                                else:
                                    data_aplicacao = '-'
                                
                                # Valor pode estar em valor_executado ou campo2
                                if d.get('valor_executado'):
                                    valor_aplicacao = d['valor_executado']
                                elif d.get('valor_previsto'):
                                    valor_aplicacao = d['valor_previsto']
                                else:
                                    valor_aplicacao = d.get('campo2', '0')
                                
                                # Formatar valor
                                try:
                                    valor_fmt = f"R$ {float(valor_aplicacao):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                except:
                                    valor_fmt = f"R$ {valor_aplicacao}"
                                
                                lista_formatada_html += '<tr>'
                                lista_formatada_html += f'<td style="padding: 0.25rem; text-align: center !important;">{data_aplicacao}</td>'
                                lista_formatada_html += f'<td style="padding: 0.25rem; text-align: right !important;">{valor_fmt}</td>'
                                lista_formatada_html += '</tr>'
                            
                            lista_formatada_html += '</tbody></table></div>'
                
                # Fechar item da lista
                lista_formatada_html += '</li>'
        
        else:
            lista_formatada_html += '<li><i>Nenhuma inconsistência foi ratificada para este termo.</i></li>'
        
        lista_formatada_html += '</ol>'
        
        # Substituir placeholder no texto
        texto = texto.replace('lista_inconsistencias', lista_formatada_html)
        print(f"[DEBUG] Lista de inconsistências formatada em HTML e inserida no texto")
        
        return jsonify({'texto_gerado': texto})
    
    except Exception as e:
        print(f"[ERRO] gerar_texto_relatorio_inconsistencias: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# API: Gerar PDF do Relatório de Inconsistências - REMOVIDA
# PDF agora é gerado apenas através do editor de texto rico
# ============================================================


# ============================================================
# API: Resetar Inconsistências de um Termo
# ============================================================
@analises_pc_bp.route('/api/resetar-inconsistencias/<path:numero_termo>', methods=['DELETE'])
def resetar_inconsistencias(numero_termo):
    """
    Remove todas as inconsistências ratificadas de um termo específico.
    DELETE nas 3 tabelas: lista_inconsistencias, lista_inconsistencias_agregadas, lista_inconsistencias_globais
    """
    try:
        print(f"[DEBUG] Resetando inconsistências do termo: {numero_termo}")
        
        conn = get_db()
        cur = conn.cursor()
        
        # Deletar das 3 tabelas
        cur.execute("""
            DELETE FROM analises_pc.lista_inconsistencias
            WHERE numero_termo = %s
        """, (numero_termo,))
        deletados_lista = cur.rowcount
        
        cur.execute("""
            DELETE FROM analises_pc.lista_inconsistencias_agregadas
            WHERE numero_termo = %s
        """, (numero_termo,))
        deletados_agregadas = cur.rowcount
        
        cur.execute("""
            DELETE FROM analises_pc.lista_inconsistencias_globais
            WHERE numero_termo = %s
        """, (numero_termo,))
        deletados_globais = cur.rowcount
        
        conn.commit()
        cur.close()
        
        total_deletados = deletados_lista + deletados_agregadas + deletados_globais
        
        print(f"[DEBUG] Inconsistências resetadas: {deletados_lista} padrão, {deletados_agregadas} agregadas, {deletados_globais} globais")
        
        return jsonify({
            'sucesso': True,
            'total_deletados': total_deletados,
            'detalhes': {
                'lista_inconsistencias': deletados_lista,
                'lista_inconsistencias_agregadas': deletados_agregadas,
                'lista_inconsistencias_globais': deletados_globais
            }
        })
    
    except Exception as e:
        print(f"[ERRO] resetar_inconsistencias: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'erro': str(e)}), 500
