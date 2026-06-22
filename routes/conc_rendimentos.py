"""
Rotas para Conciliação de Rendimentos de Ativos Financeiros - Análise PC
"""

from flask import Blueprint, render_template, request, jsonify, session, make_response
from db import get_cursor, get_db
from functools import wraps
from decorators import requires_access, requires_write_access
from datetime import datetime, date
import calendar

bp = Blueprint('conc_rendimentos', __name__, url_prefix='/conc_rendimentos')

MESES_PT_BR = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Sessão expirada'}), 401
        return f(*args, **kwargs)
    return decorated_function


def _to_float(valor):
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_data_referencia(valor):
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()[:10]
    try:
        return datetime.strptime(texto, '%Y-%m-%d').date()
    except ValueError:
        return None


def _formatar_mes_label(data_ref):
    data_obj = _parse_data_referencia(data_ref)
    if not data_obj:
        return ''
    return f"{MESES_PT_BR[data_obj.month - 1]}-{str(data_obj.year)[-2:]}"


def _proximo_mes(data_atual):
    if data_atual.month == 12:
        return date(data_atual.year + 1, 1, 1)
    return date(data_atual.year, data_atual.month + 1, 1)


def _obter_periodo_parceria(cur, numero_termo):
    cur.execute("""
        SELECT inicio, final
        FROM public.parcerias
        WHERE numero_termo = %s
    """, (numero_termo,))
    resultado = cur.fetchone()
    if not resultado:
        return {'inicio': None, 'final': None}
    return dict(resultado)


def _gerar_meses_projeto(data_inicio, data_fim):
    if not data_inicio or not data_fim:
        return []

    meses = []
    data_atual = date(data_inicio.year, data_inicio.month, 1)
    data_limite = date(data_fim.year, data_fim.month, 1)

    while data_atual <= data_limite:
        meses.append({
            'label': _formatar_mes_label(data_atual),
            'data': data_atual.isoformat(),
        })
        data_atual = _proximo_mes(data_atual)

    return meses


def _normalizar_linha_rendimento(item):
    data_ref = _parse_data_referencia(item.get('data_referencia'))
    if not data_ref:
        return None

    bruto = _to_float(item.get('rendimento_bruto'))
    ir = _to_float(item.get('rendimento_ir'))
    iof = _to_float(item.get('rendimento_iof'))

    return {
        'id': item.get('id'),
        'data_referencia': data_ref.isoformat(),
        'mes_label': _formatar_mes_label(data_ref),
        'rendimento_bruto': bruto,
        'rendimento_ir': ir,
        'rendimento_iof': iof,
        'valor_liquido': bruto - ir - iof,
        'observacoes': (item.get('observacoes') or '').strip(),
    }


def _montar_rendimentos_exportacao(cur, numero_termo, payload=None):
    periodo = _obter_periodo_parceria(cur, numero_termo)
    meses_base = _gerar_meses_projeto(periodo.get('inicio'), periodo.get('final'))

    if payload and isinstance(payload.get('rendimentos'), list):
        origem = payload.get('rendimentos', [])
    else:
        cur.execute("""
            SELECT
                id,
                rendimento_bruto,
                rendimento_ir,
                rendimento_iof,
                data_referencia,
                observacoes
            FROM analises_pc.conc_rendimentos
            WHERE numero_termo = %s
            ORDER BY data_referencia ASC
        """, (numero_termo,))
        origem = [dict(row) for row in cur.fetchall()]

    rendimentos_map = {}
    for item in origem:
        linha = _normalizar_linha_rendimento(item)
        if not linha:
            continue
        rendimentos_map[linha['data_referencia']] = linha

    linhas = []

    for mes in meses_base:
        data_ref = mes['data']
        linha = rendimentos_map.pop(data_ref, None)
        if linha:
            linha['mes_label'] = mes['label']
            linhas.append(linha)
        else:
            linhas.append({
                'id': None,
                'data_referencia': data_ref,
                'mes_label': mes['label'],
                'rendimento_bruto': 0.0,
                'rendimento_ir': 0.0,
                'rendimento_iof': 0.0,
                'valor_liquido': 0.0,
                'observacoes': '',
            })

    for data_ref in sorted(rendimentos_map):
        linhas.append(rendimentos_map[data_ref])

    linhas.sort(key=lambda item: item['data_referencia'])
    return periodo, linhas


@bp.route('/')
@login_required
@requires_access('conc_rendimentos')
def index():
    """Página principal de conciliação de rendimentos"""
    return render_template('analises_pc/conc_rendimentos.html')


@bp.route('/api/rendimentos', methods=['GET'])
@login_required
@requires_access('conc_rendimentos')
def api_listar_rendimentos():
    """
    API para listar rendimentos de um termo
    Query params: numero_termo
    """
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        query = """
            SELECT 
                id,
                numero_termo,
                rendimento_bruto,
                rendimento_ir,
                rendimento_iof,
                data_referencia,
                observacoes
            FROM analises_pc.conc_rendimentos
            WHERE numero_termo = %s
            ORDER BY data_referencia ASC
        """
        
        cur.execute(query, (numero_termo,))
        rendimentos = cur.fetchall()
        
        # Processar dados
        resultado = []
        for item in rendimentos:
            row = dict(item)
            
            # Converter data para string ISO
            if row.get('data_referencia'):
                row['data_referencia'] = row['data_referencia'].isoformat()
            
            # Converter valores numéricos para float
            if row.get('rendimento_bruto'):
                row['rendimento_bruto'] = float(row['rendimento_bruto'])
            if row.get('rendimento_ir'):
                row['rendimento_ir'] = float(row['rendimento_ir'])
            if row.get('rendimento_iof'):
                row['rendimento_iof'] = float(row['rendimento_iof'])
            
            resultado.append(row)
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar rendimentos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/rendimentos', methods=['POST'])
@login_required
@requires_access('conc_rendimentos')
@requires_write_access('conc_rendimentos')
def api_salvar_rendimentos():
    """API para salvar rendimentos"""
    try:
        dados = request.get_json()
        rendimentos = dados.get('rendimentos', [])
        numero_termo = dados.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400
        
        cur = get_cursor()
        db = get_db()
        
        ids_processados = []
        
        for rendimento in rendimentos:
            rendimento_id = rendimento.get('id')
            data_referencia = rendimento.get('data_referencia')
            
            if not data_referencia:
                continue  # Pular linhas sem data de referência
            
            rendimento_bruto = rendimento.get('rendimento_bruto') or 0
            rendimento_ir = rendimento.get('rendimento_ir') or 0
            rendimento_iof = rendimento.get('rendimento_iof') or 0
            observacoes = rendimento.get('observacoes') or ''
            
            if rendimento_id:
                # UPDATE: registro já existe
                cur.execute("""
                    UPDATE analises_pc.conc_rendimentos SET
                        rendimento_bruto = %s,
                        rendimento_ir = %s,
                        rendimento_iof = %s,
                        observacoes = %s
                    WHERE id = %s AND numero_termo = %s
                    RETURNING id
                """, (
                    rendimento_bruto,
                    rendimento_ir,
                    rendimento_iof,
                    observacoes,
                    rendimento_id,
                    numero_termo
                ))
                result = cur.fetchone()
                if result:
                    ids_processados.append(result['id'])
            else:
                # INSERT: novo registro
                cur.execute("""
                    INSERT INTO analises_pc.conc_rendimentos (
                        numero_termo, rendimento_bruto, rendimento_ir,
                        rendimento_iof, data_referencia, observacoes
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    numero_termo,
                    rendimento_bruto,
                    rendimento_ir,
                    rendimento_iof,
                    data_referencia,
                    observacoes
                ))
                novo_id = cur.fetchone()['id']
                ids_processados.append(novo_id)
        
        db.commit()
        
        return jsonify({
            'mensagem': f'{len(ids_processados)} rendimentos salvos com sucesso',
            'ids': ids_processados
        }), 200
        
    except Exception as e:
        print(f"[ERRO] ao salvar rendimentos: {e}")
        import traceback
        traceback.print_exc()
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/periodo-termo', methods=['GET'])
@login_required
@requires_access('conc_rendimentos')
def api_periodo_termo():
    """API para obter período (datas início e final) de um termo"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        query = """
            SELECT inicio, final
            FROM public.parcerias
            WHERE numero_termo = %s
        """
        
        cur.execute(query, (numero_termo,))
        resultado = cur.fetchone()
        
        if not resultado:
            return jsonify({'erro': 'Termo não encontrado'}), 404
        
        periodo = dict(resultado)
        
        # Converter datas para string ISO
        if periodo.get('inicio'):
            periodo['inicio'] = periodo['inicio'].isoformat()
        if periodo.get('final'):
            periodo['final'] = periodo['final'].isoformat()
        
        return jsonify(periodo), 200
        
    except Exception as e:
        print(f"[ERRO] ao buscar período do termo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/exportar-pdf', methods=['GET', 'POST'])
@login_required
@requires_access('conc_rendimentos')
def api_exportar_pdf():
    """Gera PDF dos rendimentos do termo."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    try:
        payload = request.get_json(silent=True) if request.method == 'POST' else None
        numero_termo = (
            (payload or {}).get('numero_termo')
            or request.args.get('numero_termo')
            or ''
        ).strip()

        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400

        cur = get_cursor()
        periodo, linhas = _montar_rendimentos_exportacao(cur, numero_termo, payload)

        def fmt_brl(valor):
            return (
                f'R$ {float(valor or 0):,.2f}'
                .replace(',', 'X')
                .replace('.', ',')
                .replace('X', '.')
            )

        def fmt_data_br(valor):
            if not valor:
                return ''
            if isinstance(valor, datetime):
                return valor.strftime('%d/%m/%Y')
            if isinstance(valor, date):
                return valor.strftime('%d/%m/%Y')
            data_obj = _parse_data_referencia(valor)
            return data_obj.strftime('%d/%m/%Y') if data_obj else str(valor)

        total_bruto = sum(item['rendimento_bruto'] for item in linhas)
        total_ir = sum(item['rendimento_ir'] for item in linhas)
        total_iof = sum(item['rendimento_iof'] for item in linhas)
        total_liquido = sum(item['valor_liquido'] for item in linhas)

        styles = getSampleStyleSheet()
        cor_titulo = colors.HexColor('#065f46')
        cor_fundo_claro = colors.HexColor('#f0fdf4')
        cor_grade = colors.HexColor('#d1fae5')

        estilo_titulo = ParagraphStyle(
            'TituloRendimentos',
            parent=styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=cor_titulo,
            spaceAfter=4,
        )
        estilo_subtitulo = ParagraphStyle(
            'SubtituloRendimentos',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#4b5563'),
            spaceAfter=6,
        )
        estilo_celula = ParagraphStyle(
            'CelulaRendimentos',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            wordWrap='LTR',
        )
        estilo_celula_centro = ParagraphStyle(
            'CelulaRendimentosCentro',
            parent=estilo_celula,
            alignment=TA_CENTER,
        )
        estilo_celula_direita = ParagraphStyle(
            'CelulaRendimentosDireita',
            parent=estilo_celula,
            alignment=TA_RIGHT,
        )

        periodo_texto = 'Período do projeto não localizado'
        if periodo.get('inicio') and periodo.get('final'):
            periodo_texto = (
                f"Período do projeto: {fmt_data_br(periodo['inicio'])} a "
                f"{fmt_data_br(periodo['final'])}"
            )

        table_data = [[
            Paragraph('<b>Mês/Ano</b>', estilo_celula_centro),
            Paragraph('<b>Rendimento Bruto (R$)</b>', estilo_celula_centro),
            Paragraph('<b>IR (R$)</b>', estilo_celula_centro),
            Paragraph('<b>IOF (R$)</b>', estilo_celula_centro),
            Paragraph('<b>Valor Líquido (R$)</b>', estilo_celula_centro),
            Paragraph('<b>Observações</b>', estilo_celula_centro),
        ]]

        for item in linhas:
            table_data.append([
                Paragraph(item['mes_label'], estilo_celula_centro),
                Paragraph(fmt_brl(item['rendimento_bruto']), estilo_celula_direita),
                Paragraph(fmt_brl(item['rendimento_ir']), estilo_celula_direita),
                Paragraph(fmt_brl(item['rendimento_iof']), estilo_celula_direita),
                Paragraph(fmt_brl(item['valor_liquido']), estilo_celula_direita),
                Paragraph(item['observacoes'] or '', estilo_celula),
            ])

        table_data.append([
            Paragraph('<b>TOTAL</b>', estilo_celula_centro),
            Paragraph(f"<b>{fmt_brl(total_bruto)}</b>", estilo_celula_direita),
            Paragraph(f"<b>{fmt_brl(total_ir)}</b>", estilo_celula_direita),
            Paragraph(f"<b>{fmt_brl(total_iof)}</b>", estilo_celula_direita),
            Paragraph(f"<b>{fmt_brl(total_liquido)}</b>", estilo_celula_direita),
            Paragraph('', estilo_celula),
        ])

        buffer = BytesIO()
        page_width, _ = landscape(A4)
        margin = 1.2 * cm

        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=margin,
            rightMargin=margin,
            topMargin=1.2 * cm,
            bottomMargin=1.2 * cm,
        )

        usable_width = page_width - (2 * margin)
        col_widths = [
            usable_width * 0.12,
            usable_width * 0.16,
            usable_width * 0.12,
            usable_width * 0.12,
            usable_width * 0.16,
            usable_width * 0.32,
        ]

        tabela = Table(table_data, colWidths=col_widths, repeatRows=1)
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cor_titulo),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.25, cor_grade),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, cor_fundo_claro]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#dcfce7')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        story = [
            Paragraph(f'Rendimentos de Ativos Financeiros — {numero_termo}', estilo_titulo),
            Paragraph(periodo_texto, estilo_subtitulo),
            Paragraph(f'{len(linhas)} mês(es) listados', estilo_subtitulo),
            Spacer(1, 0.3 * cm),
            tabela,
        ]

        def _rodape(canvas, doc_ref):
            canvas.saveState()
            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.HexColor('#6b7280'))
            canvas.drawRightString(
                page_width - margin,
                0.55 * cm,
                f'Página {doc_ref.page}'
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        nome_arquivo = f"rendimentos_{numero_termo.replace('/', '_').replace(' ', '_')}.pdf"
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
        response.headers['Content-Length'] = len(pdf_bytes)
        return response

    except Exception as e:
        print(f"[ERRO] ao exportar PDF de rendimentos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500
