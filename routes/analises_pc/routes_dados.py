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
    """Lista todas as pessoas gestoras únicas do sistema (incluindo inativas)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("""
            SELECT DISTINCT nome_pg
            FROM public.parcerias_pg
            WHERE nome_pg IS NOT NULL AND nome_pg != ''
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
