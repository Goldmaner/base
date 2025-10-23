"""
Blueprint de parcerias (listagem e formulário)
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from db import get_cursor, get_db, execute_query
from utils import login_required
import csv
from io import StringIO, BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

parcerias_bp = Blueprint('parcerias', __name__, url_prefix='/parcerias')


@parcerias_bp.route("/", methods=["GET"])
@login_required
def listar():
    """
    Listagem de todas as parcerias/termos com filtros e busca
    """
    # Obter parâmetros de filtro e busca
    filtro_termo = request.args.get('filtro_termo', '').strip()
    filtro_osc = request.args.get('filtro_osc', '').strip()
    filtro_projeto = request.args.get('filtro_projeto', '').strip()
    filtro_tipo_termo = request.args.get('filtro_tipo_termo', '').strip()
    busca_sei_celeb = request.args.get('busca_sei_celeb', '').strip()
    busca_sei_pc = request.args.get('busca_sei_pc', '').strip()
    
    # Obter parâmetro de paginação (padrão: 100)
    limite = request.args.get('limite', '100')
    if limite == 'todas':
        limite_sql = None
    else:
        try:
            limite_sql = int(limite)
        except ValueError:
            limite_sql = 100
    
    cur = get_cursor()
    
    # Buscar tipos de contrato para o dropdown de filtro
    cur.execute("SELECT informacao FROM categoricas.c_tipo_contrato ORDER BY informacao")
    tipos_contrato_raw = cur.fetchall()
    tipos_contrato = [row['informacao'] for row in tipos_contrato_raw]
    
    # DEBUG: Verificar duplicação
    print(f"[DEBUG] Total de tipos_contrato retornados: {len(tipos_contrato)}")
    print(f"[DEBUG] Tipos únicos: {len(set(tipos_contrato))}")
    if len(tipos_contrato) != len(set(tipos_contrato)):
        print(f"[ALERTA] DUPLICAÇÃO DETECTADA em c_tipo_contrato!")
        print(f"[DEBUG] Tipos com duplicação: {[t for t in tipos_contrato if tipos_contrato.count(t) > 1]}")
    
    # Construir query dinamicamente com filtros
    query = """
        SELECT 
            numero_termo,
            osc,
            projeto,
            tipo_termo,
            inicio,
            final,
            meses,
            total_previsto,
            total_pago,
            sei_celeb,
            sei_pc
        FROM Parcerias
        WHERE 1=1
    """
    
    params = []
    
    # Adicionar filtros se fornecidos
    if filtro_termo:
        query += " AND numero_termo ILIKE %s"
        params.append(f"%{filtro_termo}%")
    
    if filtro_osc:
        query += " AND osc ILIKE %s"
        params.append(f"%{filtro_osc}%")
    
    if filtro_projeto:
        query += " AND projeto ILIKE %s"
        params.append(f"%{filtro_projeto}%")
    
    if filtro_tipo_termo:
        query += " AND tipo_termo ILIKE %s"
        params.append(f"%{filtro_tipo_termo}%")
    
    if busca_sei_celeb:
        query += " AND sei_celeb ILIKE %s"
        params.append(f"%{busca_sei_celeb}%")
    
    if busca_sei_pc:
        query += " AND sei_pc ILIKE %s"
        params.append(f"%{busca_sei_pc}%")
    
    query += " ORDER BY numero_termo"
    
    # Adicionar LIMIT se não for "todas"
    if limite_sql is not None:
        query += f" LIMIT {limite_sql}"
    
    cur.execute(query, params)
    parcerias = cur.fetchall()
    cur.close()
    
    # DEBUG: Verificar duplicação de parcerias
    print(f"[DEBUG] Total de parcerias retornadas: {len(parcerias)}")
    termos = [p['numero_termo'] for p in parcerias]
    print(f"[DEBUG] Termos únicos: {len(set(termos))}")
    if len(termos) != len(set(termos)):
        print(f"[ALERTA] DUPLICAÇÃO DETECTADA em Parcerias!")
        duplicados = [t for t in termos if termos.count(t) > 1]
        print(f"[DEBUG] Termos duplicados: {set(duplicados)}")
    
    return render_template("parcerias.html", 
                         parcerias=parcerias,
                         tipos_contrato=tipos_contrato,
                         filtro_termo=filtro_termo,
                         filtro_osc=filtro_osc,
                         filtro_projeto=filtro_projeto,
                         filtro_tipo_termo=filtro_tipo_termo,
                         busca_sei_celeb=busca_sei_celeb,
                         busca_sei_pc=busca_sei_pc,
                         limite=limite)


@parcerias_bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova():
    """
    Criar nova parceria
    """
    if request.method == "POST":
        try:
            query = """
                INSERT INTO Parcerias (
                    numero_termo, osc, projeto, tipo_termo, portaria, cnpj,
                    inicio, final, meses, total_previsto, total_pago, conta,
                    transicao, sei_celeb, sei_pc, endereco, sei_plano, 
                    sei_orcamento, contrapartida
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            params = (
                request.form.get('numero_termo'),
                request.form.get('osc'),
                request.form.get('projeto'),
                request.form.get('tipo_termo'),
                request.form.get('portaria'),
                request.form.get('cnpj'),
                request.form.get('inicio') or None,
                request.form.get('final') or None,
                request.form.get('meses') or None,
                request.form.get('total_previsto_hidden') or request.form.get('total_previsto') or None,
                request.form.get('total_pago_hidden') or request.form.get('total_pago') or 0,
                request.form.get('conta'),
                1 if request.form.get('transicao') == 'on' else 0,
                request.form.get('sei_celeb'),
                request.form.get('sei_pc'),
                request.form.get('endereco'),
                request.form.get('sei_plano'),
                request.form.get('sei_orcamento'),
                1 if request.form.get('contrapartida') == 'on' else 0
            )
            
            if execute_query(query, params):
                flash("Parceria criada com sucesso!", "success")
                return redirect(url_for('parcerias.nova'))
            else:
                flash("Erro ao criar parceria no banco de dados!", "danger")
            
        except Exception as e:
            flash(f"Erro ao criar parceria: {str(e)}", "danger")
    
    # GET - retornar formulário vazio
    # Buscar dados dos dropdowns
    cur = get_cursor()
    cur.execute("SELECT informacao FROM categoricas.c_tipo_contrato ORDER BY informacao")
    tipos_contrato = [row['informacao'] for row in cur.fetchall()]
    cur.execute("SELECT lei FROM categoricas.c_legislacao ORDER BY lei")
    legislacoes = [row['lei'] for row in cur.fetchall()]
    cur.close()
    
    return render_template("parcerias_form.html", 
                         parceria=None,
                         tipos_contrato=tipos_contrato,
                         legislacoes=legislacoes)


@parcerias_bp.route("/editar/<path:numero_termo>", methods=["GET", "POST"])
@login_required
def editar(numero_termo):
    """
    Formulário completo de edição de parceria
    """
    if request.method == "POST":
        # Atualizar os dados da parceria
        try:
            query = """
                UPDATE Parcerias SET
                    osc = %s,
                    projeto = %s,
                    tipo_termo = %s,
                    portaria = %s,
                    cnpj = %s,
                    inicio = %s,
                    final = %s,
                    meses = %s,
                    total_previsto = %s,
                    total_pago = %s,
                    conta = %s,
                    transicao = %s,
                    sei_celeb = %s,
                    sei_pc = %s,
                    endereco = %s,
                    sei_plano = %s,
                    sei_orcamento = %s,
                    contrapartida = %s
                WHERE numero_termo = %s
            """
            
            params = (
                request.form.get('osc'),
                request.form.get('projeto'),
                request.form.get('tipo_termo'),
                request.form.get('portaria'),
                request.form.get('cnpj'),
                request.form.get('inicio') or None,
                request.form.get('final') or None,
                request.form.get('meses') or None,
                request.form.get('total_previsto_hidden') or request.form.get('total_previsto') or None,
                request.form.get('total_pago_hidden') or request.form.get('total_pago') or 0,
                request.form.get('conta'),
                1 if request.form.get('transicao') == 'on' else 0,  # checkbox como integer
                request.form.get('sei_celeb'),
                request.form.get('sei_pc'),
                request.form.get('endereco'),
                request.form.get('sei_plano'),
                request.form.get('sei_orcamento'),
                1 if request.form.get('contrapartida') == 'on' else 0,  # checkbox como integer
                numero_termo
            )
            
            if execute_query(query, params):
                flash("Parceria atualizada com sucesso!", "success")
                return redirect(url_for('parcerias.listar'))
            else:
                flash("Erro ao atualizar parceria no banco de dados!", "danger")
            
        except Exception as e:
            flash(f"Erro ao atualizar parceria: {str(e)}", "danger")
    
    # GET - buscar dados da parceria
    cur = get_cursor()
    cur.execute("""
        SELECT 
            numero_termo,
            osc,
            projeto,
            tipo_termo,
            portaria,
            cnpj,
            inicio,
            final,
            meses,
            total_previsto,
            total_pago,
            conta,
            transicao,
            sei_celeb,
            sei_pc,
            endereco,
            sei_plano,
            sei_orcamento,
            contrapartida
        FROM Parcerias
        WHERE numero_termo = %s
    """, (numero_termo,))
    
    parceria = cur.fetchone()
    
    # Buscar dados dos dropdowns
    cur.execute("SELECT informacao FROM categoricas.c_tipo_contrato ORDER BY informacao")
    tipos_contrato = [row['informacao'] for row in cur.fetchall()]
    cur.execute("SELECT lei FROM categoricas.c_legislacao ORDER BY lei")
    legislacoes = [row['lei'] for row in cur.fetchall()]
    cur.close()
    
    if not parceria:
        flash("Parceria não encontrada!", "danger")
        return redirect(url_for('parcerias.listar'))
    
    return render_template("parcerias_form.html", 
                         parceria=parceria,
                         tipos_contrato=tipos_contrato,
                         legislacoes=legislacoes)


@parcerias_bp.route("/api/oscs", methods=["GET"])
@login_required
def api_oscs():
    """
    API para buscar lista de OSCs únicas para autocomplete
    """
    from flask import jsonify
    
    cur = get_cursor()
    cur.execute("""
        SELECT DISTINCT osc, cnpj 
        FROM Parcerias 
        WHERE osc IS NOT NULL AND osc != ''
        ORDER BY osc
    """)
    oscs = cur.fetchall()
    cur.close()
    
    # Criar dicionário com OSC e CNPJ
    result = {}
    for row in oscs:
        if row['osc']:
            result[row['osc']] = row['cnpj'] or ''
    
    return jsonify(result)


@parcerias_bp.route("/api/sigla-tipo-termo", methods=["GET"])
@login_required
def api_sigla_tipo_termo():
    """
    API para buscar mapeamento de siglas para tipos de termo
    """
    from flask import jsonify
    
    cur = get_cursor()
    cur.execute("SELECT id, informacao, sigla FROM categoricas.c_tipo_contrato ORDER BY sigla")
    tipos = cur.fetchall()
    cur.close()
    
    # Criar mapeamento sigla -> tipo
    mapeamento = {}
    for row in tipos:
        if row['sigla']:
            mapeamento[row['sigla'].upper()] = row['informacao']
    
    return jsonify(mapeamento)


@parcerias_bp.route("/exportar-csv", methods=["GET"])
@login_required
def exportar_csv():
    """
    Exporta TODAS as parcerias para CSV
    """
    try:
        cur = get_cursor()
        
        # Query para buscar TODAS as parcerias
        query = """
            SELECT 
                numero_termo,
                tipo_termo,
                osc,
                cnpj,
                projeto,
                portaria,
                inicio,
                final,
                meses,
                total_previsto,
                sei_celeb,
                sei_pc,
                sei_plano,
                sei_orcamento,
                transicao
            FROM Parcerias
            ORDER BY numero_termo
        """
        
        cur.execute(query)
        parcerias = cur.fetchall()
        cur.close()
        
        # Criar arquivo CSV em memória
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Cabeçalho do CSV
        writer.writerow([
            'Número do Termo',
            'Tipo de Termo',
            'OSC',
            'CNPJ',
            'Projeto',
            'Portaria',
            'Coordenação',
            'Data Início',
            'Data Término',
            'Meses',
            'Total Previsto',
            'SEI Celebração',
            'SEI P&C',
            'SEI Plano',
            'SEI Orçamento',
            'Transição'
        ])
        
        # Escrever dados
        for parceria in parcerias:
            total_previsto = float(parceria['total_previsto'] or 0)
            
            writer.writerow([
                parceria['numero_termo'],
                parceria['tipo_termo'] or '-',
                parceria['osc'] or '-',
                parceria['cnpj'] or '-',
                parceria['projeto'] or '-',
                parceria['portaria'] or '-',
                parceria['inicio'].strftime('%d/%m/%Y') if parceria['inicio'] else '-',
                parceria['final'].strftime('%d/%m/%Y') if parceria['final'] else '-',
                parceria['meses'] if parceria['meses'] is not None else '-',
                f"R$ {total_previsto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                parceria['sei_celeb'] or '-',
                parceria['sei_pc'] or '-',
                parceria['sei_plano'] or '-',
                parceria['sei_orcamento'] or '-',
                'Sim' if parceria['transicao'] else 'Não'
            ])
        
        # Preparar resposta
        output.seek(0)
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'parcerias_{data_atual}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        return f"Erro ao exportar CSV: {str(e)}", 500


@parcerias_bp.route("/exportar-pdf", methods=["GET"])
@login_required
def exportar_pdf():
    """
    Exporta uma parceria específica para PDF
    """
    try:
        # Obter número do termo da query string
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return "Número do termo não informado", 400
        
        cur = get_cursor()
        
        # Query para buscar a parceria
        query = """
            SELECT 
                numero_termo,
                tipo_termo,
                osc,
                cnpj,
                projeto,
                portaria,
                inicio,
                final,
                meses,
                total_previsto,
                sei_celeb,
                sei_pc,
                sei_plano,
                sei_orcamento,
                transicao
            FROM Parcerias
            WHERE numero_termo = %s
        """
        
        cur.execute(query, (numero_termo,))
        parceria = cur.fetchone()
        cur.close()
        
        if not parceria:
            return "Parceria não encontrada", 404
        
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
            textColor=colors.HexColor('#1a73e8'),
            spaceAfter=30,
            alignment=1  # Centralizado
        )
        
        # Estilo para labels
        label_style = ParagraphStyle(
            'Label',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            spaceAfter=2
        )
        
        # Estilo para valores
        value_style = ParagraphStyle(
            'Value',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12
        )
        
        # Título
        titulo = Paragraph(f"Parceria - {parceria['numero_termo']}", title_style)
        elements.append(titulo)
        elements.append(Spacer(1, 0.5*cm))
        
        # Preparar dados
        total_previsto = float(parceria['total_previsto'] or 0)
        data_inicio_fmt = parceria['inicio'].strftime('%d/%m/%Y') if parceria['inicio'] else '-'
        data_termino_fmt = parceria['final'].strftime('%d/%m/%Y') if parceria['final'] else '-'
        total_previsto_fmt = f"R$ {total_previsto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # Dados da parceria em formato de tabela
        dados = [
            ['Número do Termo:', parceria['numero_termo']],
            ['Tipo de Termo:', parceria['tipo_termo'] or '-'],
            ['OSC:', parceria['osc'] or '-'],
            ['CNPJ:', parceria['cnpj'] or '-'],
            ['Projeto:', parceria['projeto'] or '-'],
            ['Portaria:', parceria['portaria'] or '-'],
            ['Data de Início:', data_inicio_fmt],
            ['Data de Término:', data_termino_fmt],
            ['Meses:', str(parceria['meses']) if parceria['meses'] is not None else '-'],
            ['Total Previsto:', total_previsto_fmt],
            ['SEI Celebração:', parceria['sei_celeb'] or '-'],
            ['SEI P&C:', parceria['sei_pc'] or '-'],
            ['SEI Plano:', parceria['sei_plano'] or '-'],
            ['SEI Orçamento:', parceria['sei_orcamento'] or '-'],
            ['Transição:', 'Sim' if parceria['transicao'] else 'Não']
        ]
        
        # Criar tabela
        tabela = Table(dados, colWidths=[5*cm, 12*cm])
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(tabela)
        elements.append(Spacer(1, 1*cm))
        
        # Rodapé
        data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M')
        rodape = Paragraph(f"<i>Documento gerado em {data_geracao}</i>", 
                          ParagraphStyle('Footer', parent=styles['Normal'], 
                                       fontSize=8, textColor=colors.grey))
        elements.append(rodape)
        
        # Gerar PDF
        doc.build(elements)
        
        # Preparar resposta
        buffer.seek(0)
        filename = f'parceria_{numero_termo.replace("/", "-")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        return f"Erro ao gerar PDF: {str(e)}", 500


@parcerias_bp.route("/conferencia", methods=["GET"])
@login_required
def conferencia():
    """
    Compara as parcerias do CSV (coluna A) com as do banco (coluna B)
    e mostra as parcerias não inseridas no sistema
    """
    import pandas as pd
    import os
    
    try:
        # Caminho do CSV gerado pelo script import_conferencia.py
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'saida.csv')
        
        # Verifica se o arquivo existe
        if not os.path.exists(csv_path):
            flash("Arquivo de conferência não encontrado. Execute o script import_conferencia.py primeiro.", "warning")
            return redirect(url_for('parcerias.listar'))
        
        # Lê o CSV
        df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig')
        
        # Extrai as colunas
        termos_planilha = df['Planilha'].dropna().tolist()
        termos_database = df['Database'].dropna().tolist()
        
        # Converte para sets para facilitar a comparação
        set_planilha = set(termos_planilha)
        set_database = set(termos_database)
        
        # Encontra os termos que estão na planilha mas NÃO estão no banco
        termos_nao_inseridos = sorted(set_planilha - set_database)
        
        # Estatísticas
        total_planilha = len(set_planilha)
        total_database = len(set_database)
        total_nao_inseridos = len(termos_nao_inseridos)
        total_inseridos = len(set_planilha & set_database)
        
        return render_template(
            'temp_conferencia.html',
            termos_nao_inseridos=termos_nao_inseridos,
            total_planilha=total_planilha,
            total_database=total_database,
            total_nao_inseridos=total_nao_inseridos,
            total_inseridos=total_inseridos
        )
        
    except Exception as e:
        flash(f"Erro ao processar conferência: {str(e)}", "danger")
        return redirect(url_for('parcerias.listar'))
