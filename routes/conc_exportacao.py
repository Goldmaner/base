"""
Rotas para Exportação e Importação de Conciliação Bancária
"""

from flask import Blueprint, request, jsonify, session, Response
from db import get_cursor
from functools import wraps
import csv
import io
from datetime import datetime

bp = Blueprint('conc_exportacao', __name__, url_prefix='/conc_bancaria')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Sessão expirada'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/api/exportar-csv', methods=['GET'])
@login_required
def exportar_csv():
    """Exportar dados da conciliação bancária em formato CSV"""
    try:
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400
        
        cur = get_cursor()
        
        # Buscar dados do extrato
        cur.execute("""
            SELECT 
                indice,
                data,
                credito,
                debito,
                discriminacao,
                cat_transacao,
                competencia,
                origem_destino,
                cat_avaliacao,
                avaliacao_analista
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s
            ORDER BY indice ASC
        """, (numero_termo,))
        
        dados = cur.fetchall()
        
        # Criar CSV em memória
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        # Cabeçalho
        writer.writerow([
            'Índice',
            'Data',
            'Crédito (R$)',
            'Débito (R$)',
            'Composição do Valor (R$)',
            'Categoria de Transação',
            'Competência',
            'Origem ou Destino',
            'Avaliação',
            'Observações'
        ])
        
        # Dados
        for row in dados:
            # Formatar data
            data_formatada = ''
            if row['data']:
                data_formatada = row['data'].strftime('%d/%m/%Y')
            
            # Formatar competência
            competencia_formatada = ''
            if row['competencia']:
                meses = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 
                        'jul', 'ago', 'set', 'out', 'nov', 'dez']
                competencia_formatada = f"{meses[row['competencia'].month - 1]}/{row['competencia'].year}"
            
            # Formatar valores monetários
            credito = ''
            if row['credito']:
                credito = f"{float(row['credito']):.2f}".replace('.', ',')
            
            debito = ''
            if row['debito']:
                debito = f"{float(row['debito']):.2f}".replace('.', ',')
            
            discriminacao = ''
            if row['discriminacao']:
                discriminacao = f"{float(row['discriminacao']):.2f}".replace('.', ',')
            
            writer.writerow([
                row['indice'] or '',
                data_formatada,
                credito,
                debito,
                discriminacao,
                row['cat_transacao'] or '',
                competencia_formatada,
                row['origem_destino'] or '',
                row['cat_avaliacao'] or '',
                row['avaliacao_analista'] or ''
            ])
        
        # Preparar resposta com BOM UTF-8 para Excel
        output.seek(0)
        csv_content = '\ufeff' + output.getvalue()  # BOM UTF-8
        
        # Nome do arquivo com data
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"conciliacao_{numero_termo.replace('/', '_')}_{data_atual}.csv"
        
        return Response(
            csv_content.encode('utf-8'),
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{nome_arquivo}"',
                'Content-Type': 'text/csv; charset=utf-8-sig'
            }
        )
        
    except Exception as e:
        print(f"[ERRO] ao exportar CSV: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/modelo-importacao', methods=['GET'])
def modelo_importacao():
    """Baixar modelo de importação com instruções"""
    import zipfile
    
    try:
        # Criar ZIP em memória
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # ==================== MODELO CSV ====================
            csv_content = io.StringIO()
            writer = csv.writer(csv_content, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # Cabeçalho
            writer.writerow([
                'Índice',
                'Data',
                'Crédito (R$)',
                'Débito (R$)',
                'Composição do Valor (R$)',
                'Categoria de Transação',
                'Competência',
                'Origem ou Destino',
                'Avaliação',
                'Observações'
            ])
            
            # Linhas de exemplo
            writer.writerow([
                '1',
                '01/06/2025',
                '1.500,00',
                '',
                '1.500,00',
                'Parcela',
                'jun/2025',
                'Administração Pública',
                'Avaliado',
                'Primeira parcela do repasse'
            ])
            writer.writerow([
                '2',
                '05/06/2025',
                '',
                '150,00',
                '150,00',
                'Coordenador (CLT)',
                'jun/2025',
                'João Silva',
                'Avaliado',
                ''
            ])
            writer.writerow([
                '3',
                '10/06/2025',
                '',
                '25,50',
                '25,50',
                'Taxas Bancárias',
                'jun/2025',
                'Banco do Brasil',
                'Glosar',
                'Taxa de manutenção da conta'
            ])
            
            # Adicionar BOM UTF-8 para Excel
            csv_with_bom = '\ufeff' + csv_content.getvalue()
            zip_file.writestr('modelo_conciliacao.csv', csv_with_bom.encode('utf-8'))
            
            # ==================== INSTRUÇÕES TXT ====================
            instrucoes = """
================================================================================
        INSTRUÇÕES PARA PREENCHIMENTO DO MODELO DE CONCILIAÇÃO BANCÁRIA
================================================================================

Este arquivo contém orientações para o preenchimento correto do modelo de 
importação da Conciliação Bancária.

--------------------------------------------------------------------------------
                            COLUNAS DO MODELO
--------------------------------------------------------------------------------

1. ÍNDICE
   - Número sequencial que define a ordem dos lançamentos
   - Deve ser um número inteiro positivo (1, 2, 3...)
   - Garante ordenação correta mesmo com inserções posteriores
   - OBRIGATÓRIO

2. DATA
   - Data da movimentação conforme consta no extrato bancário
   - Formato: DD/MM/AAAA (exemplo: 01/06/2025)
   - OBRIGATÓRIO

3. CRÉDITO (R$)
   - Valores positivos de entrada na conta
   - Formato: 1.500,00 (ponto para milhar, vírgula para decimal)
   - Deixe em branco se for débito
   - NÃO preencha crédito e débito na mesma linha

4. DÉBITO (R$)
   - Valores negativos de saída da conta
   - Formato: 1.500,00 (ponto para milhar, vírgula para decimal)
   - Deixe em branco se for crédito
   - NÃO preencha crédito e débito na mesma linha

5. COMPOSIÇÃO DO VALOR (R$)
   - Valores que compõem o crédito ou débito
   - Normalmente igual ao valor de crédito ou débito
   - Pode ser diferente em casos de mesclagem de linhas
   - Formato: 1.500,00 (ponto para milhar, vírgula para decimal)

6. CATEGORIA DE TRANSAÇÃO
   - Categoria da despesa ou receita
   - Deve corresponder às categorias do termo de parceria
   - Exemplos de categorias de crédito:
     * Parcela
     * Aplicação - Poupança
     * Resgate
   - Exemplos de categorias de débito:
     * Coordenador (CLT)
     * Material de Escritório
     * Taxas Bancárias

7. COMPETÊNCIA
   - Mês e ano de competência da transação
   - Formato: mmm/AAAA (exemplo: jun/2025)
   - Meses válidos: jan, fev, mar, abr, mai, jun, jul, ago, set, out, nov, dez
   - Deve estar dentro do período do projeto (com tolerância)

8. ORIGEM OU DESTINO
   - Para CRÉDITO: de onde veio o recurso
   - Para DÉBITO: para onde foi o pagamento
   - Exemplos:
     * Administração Pública (para repasses)
     * Banco do Brasil (para rendimentos/taxas)
     * Nome do funcionário (para salários)
     * Nome do fornecedor (para pagamentos)

9. AVALIAÇÃO
   - Status da avaliação da transação
   - Valores aceitos:
     * Avaliado (verde) - aprovado
     * Aguardando resposta (rosa) - pendente de informação
     * Pessoa Gestora (azul) - responsabilidade da Pessoa Gestora
     * Glosar (laranja) - reprovado/glosado
   - Deixe em branco para definir posteriormente

10. OBSERVAÇÕES
    - Campo livre para anotações do analista
    - Útil para registrar justificativas, pendências ou informações adicionais
    - Opcional

--------------------------------------------------------------------------------
                         REGRAS AUTOMÁTICAS DE AVALIAÇÃO
--------------------------------------------------------------------------------

O sistema aplica automaticamente algumas avaliações:

GLOSAR AUTOMÁTICO:
- Categoria "Taxas Bancárias" → Avaliação = Glosar

AVALIADO AUTOMÁTICO:
- Origem/Destino = "Banco do Brasil" → Avaliação = Avaliado
- Origem/Destino = "Administração Pública" → Avaliação = Avaliado

--------------------------------------------------------------------------------
                              DICAS IMPORTANTES
--------------------------------------------------------------------------------

1. O arquivo deve estar no formato CSV com separador ponto-e-vírgula (;)

2. Mantenha o cabeçalho exatamente como está no modelo

3. Valores monetários:
   - Use ponto (.) para separar milhares
   - Use vírgula (,) para separar decimais
   - Não inclua o símbolo R$

4. Datas:
   - Sempre no formato DD/MM/AAAA
   - Com barras, não hífens

5. Competência:
   - Sempre no formato mmm/AAAA (ex: jun/2025)
   - Mês abreviado com 3 letras minúsculas

6. Não deixe linhas em branco no meio do arquivo

7. Você pode copiar dados do Excel e colar diretamente na tabela do sistema
   (Ctrl+C no Excel, clique em uma célula na aplicação, Ctrl+V)

--------------------------------------------------------------------------------
                              SUPORTE
--------------------------------------------------------------------------------

Em caso de dúvidas sobre o preenchimento, consulte o sistema ou entre em 
contato com a equipe de suporte.

================================================================================
"""
            
            zip_file.writestr('INSTRUCOES_PREENCHIMENTO.txt', instrucoes.encode('utf-8'))
        
        # Preparar resposta
        zip_buffer.seek(0)
        
        return Response(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': 'attachment; filename="modelo_importacao_conciliacao.zip"',
                'Content-Type': 'application/zip'
            }
        )
        
    except Exception as e:
        print(f"[ERRO] ao gerar modelo: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/exportar-pdf', methods=['GET'])
@login_required
def exportar_pdf():
    """Exportar dados da conciliação bancária em formato PDF panorâmico"""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        numero_termo = request.args.get('numero_termo', '').strip()
        colunas_param = request.args.get('colunas', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400
        
        if not colunas_param:
            return jsonify({'erro': 'Selecione pelo menos uma coluna'}), 400
        
        # Parsear colunas selecionadas
        colunas_selecionadas = colunas_param.split(',')
        
        # Mapeamento de colunas
        mapeamento_colunas = {
            'indice': ('Índice', 'indice'),
            'data': ('Data', 'data'),
            'credito': ('Crédito (R$)', 'credito'),
            'debito': ('Débito (R$)', 'debito'),
            'discriminacao': ('Composição', 'discriminacao'),
            'cat_transacao': ('Categoria', 'cat_transacao'),
            'competencia': ('Competência', 'competencia'),
            'origem_destino': ('Origem/Destino', 'origem_destino'),
            'cat_avaliacao': ('Avaliação', 'cat_avaliacao'),
            'avaliacao_analista': ('Observações', 'avaliacao_analista')
        }
        
        # Construir SELECT dinâmico
        campos_select = []
        cabecalhos = []
        for col in colunas_selecionadas:
            if col in mapeamento_colunas:
                cabecalhos.append(mapeamento_colunas[col][0])
                campos_select.append(mapeamento_colunas[col][1])
        
        if not campos_select:
            return jsonify({'erro': 'Nenhuma coluna válida selecionada'}), 400
        
        cur = get_cursor()
        
        # Buscar dados
        query = f"""
            SELECT {', '.join(campos_select)}
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s
            ORDER BY indice ASC
        """
        cur.execute(query, (numero_termo,))
        dados = cur.fetchall()
        
        if not dados:
            return jsonify({'erro': 'Nenhum dado encontrado para este termo'}), 404
        
        # Criar PDF em memória
        buffer = io.BytesIO()
        
        # Configurar documento em modo paisagem (panorâmico)
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1*cm,
            leftMargin=1*cm,
            topMargin=1.5*cm,
            bottomMargin=1*cm
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        titulo_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            alignment=1  # Center
        )
        
        titulo = Paragraph(f"<b>Conciliação Bancária - Termo {numero_termo}</b>", titulo_style)
        elements.append(titulo)
        elements.append(Spacer(1, 0.3*cm))
        
        # Preparar dados da tabela com detecção de grupos de composição
        tabela_dados = [cabecalhos]  # Cabeçalho
        
        # Primeiro, vamos processar todos os dados para identificar grupos de composição
        # Isso requer buscar também informações adicionais que não estão nos campos selecionados
        cur.execute("""
            SELECT indice, data, credito, debito, discriminacao
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s
            ORDER BY indice ASC
        """, (numero_termo,))
        dados_completos = cur.fetchall()
        
        # Função para identificar grupos de composição (mesma lógica do frontend)
        def identificar_grupo_composicao(index, dados_list):
            linha = dados_list[index]
            valor_referencia = linha['credito'] or linha['debito']
            
            if not valor_referencia:
                return {'ehGrupo': False}
            
            # Se composição = valor (débito/crédito), não faz parte de grupo composto
            composicao = linha['discriminacao'] or 0
            if abs(composicao - valor_referencia) < 0.01:
                return {'ehGrupo': False}
            
            data = linha['data']
            tipo = 'credito' if linha['credito'] else 'debito'
            
            # Buscar início do grupo
            # Apenas linhas com composição DIFERENTE do valor principal
            inicio_grupo = index
            for i in range(index - 1, -1, -1):
                linha_ant = dados_list[i]
                valor_ant = linha_ant['credito'] if tipo == 'credito' else linha_ant['debito']
                composicao_ant = linha_ant['discriminacao'] or 0
                
                # Verificar: mesma data, mesmo valor, composição ≠ valor
                if (linha_ant['data'] == data and 
                    abs((valor_ant or 0) - valor_referencia) < 0.01 and
                    abs(composicao_ant - valor_referencia) >= 0.01):
                    inicio_grupo = i
                else:
                    break
            
            # Buscar fim do grupo
            # Apenas linhas com composição DIFERENTE do valor principal
            fim_grupo = index
            for i in range(index + 1, len(dados_list)):
                linha_post = dados_list[i]
                valor_post = linha_post['credito'] if tipo == 'credito' else linha_post['debito']
                composicao_post = linha_post['discriminacao'] or 0
                
                # Verificar: mesma data, mesmo valor, composição ≠ valor
                if (linha_post['data'] == data and 
                    abs((valor_post or 0) - valor_referencia) < 0.01 and
                    abs(composicao_post - valor_referencia) >= 0.01):
                    fim_grupo = i
                else:
                    break
            
            # Se há apenas 1 linha, não é grupo
            if inicio_grupo == fim_grupo:
                return {'ehGrupo': False}
            
            # É um grupo válido!
            # (composições podem ser iguais ou diferentes, o importante é que composição ≠ valor)
            return {
                'ehGrupo': True,
                'ehPrimeira': index == inicio_grupo,
                'tipo': tipo
            }
        
        # Processar cada linha dos dados originais
        for row_idx, row in enumerate(dados):
            linha_formatada = []
            
            # Identificar se faz parte de grupo de composição
            grupo_info = identificar_grupo_composicao(row_idx, dados_completos)
            
            # Criar estilo de parágrafo centralizado para células
            estilo_celula = ParagraphStyle(
                'CelulaPDF',
                parent=styles['Normal'],
                fontSize=7,
                alignment=1,  # Center
                leading=9,
                wordWrap='CJK'
            )
            
            for i, campo in enumerate(campos_select):
                valor = row[campo]
                
                # Formatar de acordo com o tipo de campo
                if campo == 'data' and valor:
                    valor_formatado = Paragraph(valor.strftime('%d/%m/%Y'), estilo_celula)
                elif campo == 'competencia' and valor:
                    meses = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 
                            'jul', 'ago', 'set', 'out', 'nov', 'dez']
                    texto_competencia = f"{meses[valor.month - 1]}/{valor.year}"
                    valor_formatado = Paragraph(texto_competencia, estilo_celula)
                elif campo == 'credito':
                    # Verificar se é linha secundária de grupo de composição de crédito
                    if grupo_info['ehGrupo'] and grupo_info['tipo'] == 'credito' and not grupo_info['ehPrimeira']:
                        valor_formatado = Paragraph("<i>Crédito composto</i>", estilo_celula)
                    elif valor:
                        texto_credito = f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                        valor_formatado = Paragraph(texto_credito, estilo_celula)
                    else:
                        valor_formatado = Paragraph('', estilo_celula)
                elif campo == 'debito':
                    # Verificar se é linha secundária de grupo de composição de débito
                    if grupo_info['ehGrupo'] and grupo_info['tipo'] == 'debito' and not grupo_info['ehPrimeira']:
                        valor_formatado = Paragraph("<i>Débito composto</i>", estilo_celula)
                    elif valor:
                        texto_debito = f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                        valor_formatado = Paragraph(texto_debito, estilo_celula)
                    else:
                        valor_formatado = Paragraph('', estilo_celula)
                elif campo == 'discriminacao' and valor:
                    texto_disc = f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    valor_formatado = Paragraph(texto_disc, estilo_celula)
                elif campo == 'indice':
                    valor_formatado = Paragraph(str(valor) if valor else '', estilo_celula)
                elif campo in ['cat_transacao', 'origem_destino', 'cat_avaliacao', 'avaliacao_analista']:
                    # Usar Paragraph para quebra automática de texto longo
                    valor_formatado = Paragraph(str(valor) if valor else '', estilo_celula)
                else:
                    valor_formatado = Paragraph(str(valor) if valor else '', estilo_celula)
                
                linha_formatada.append(valor_formatado)
            
            tabela_dados.append(linha_formatada)
        
        # Calcular largura das colunas dinamicamente com base no tipo de conteúdo
        largura_pagina = landscape(A4)[0] - 2*cm  # Largura disponível
        num_colunas = len(cabecalhos)
        
        # Definir larguras específicas para cada tipo de coluna
        larguras_colunas = []
        for col in colunas_selecionadas:
            if col == 'indice':
                larguras_colunas.append(1.2*cm)
            elif col == 'data':
                larguras_colunas.append(2.2*cm)
            elif col in ['credito', 'debito', 'discriminacao']:
                larguras_colunas.append(2.5*cm)
            elif col == 'competencia':
                larguras_colunas.append(2*cm)
            elif col == 'cat_avaliacao':
                larguras_colunas.append(3*cm)
            elif col in ['cat_transacao', 'origem_destino', 'avaliacao_analista']:
                # Colunas de texto longo - dividir espaço restante
                larguras_colunas.append(None)  # Será calculado depois
            else:
                larguras_colunas.append(2.5*cm)
        
        # Calcular largura das colunas de texto (espaço restante)
        largura_fixa_total = sum(l for l in larguras_colunas if l is not None)
        largura_restante = largura_pagina - largura_fixa_total
        num_colunas_texto = sum(1 for l in larguras_colunas if l is None)
        largura_texto = largura_restante / num_colunas_texto if num_colunas_texto > 0 else 3*cm
        
        # Substituir None pelas larguras calculadas
        larguras_colunas = [l if l is not None else largura_texto for l in larguras_colunas]
        
        # Criar tabela com larguras específicas
        tabela = Table(tabela_dados, colWidths=larguras_colunas, repeatRows=1)
        
        # Estilo da tabela - uniforme e organizado
        estilo = TableStyle([
            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            
            # Corpo - todas as células uniformes
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            
            # Garantir altura mínima de linha
            ('ROWHEIGHT', (0, 1), (-1, -1), None),  # Auto-ajuste baseado no conteúdo
        ])
        
        tabela.setStyle(estilo)
        elements.append(tabela)
        
        # Gerar PDF
        doc.build(elements)
        
        # Preparar resposta
        buffer.seek(0)
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"conciliacao_{numero_termo.replace('/', '_')}_{data_atual}.pdf"
        
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{nome_arquivo}"'
            }
        )
        
    except ImportError as e:
        print(f"[ERRO] Biblioteca reportlab não instalada: {e}")
        return jsonify({'erro': 'Biblioteca de geração de PDF não está instalada. Execute: pip install reportlab'}), 500
    except Exception as e:
        print(f"[ERRO] ao exportar PDF: {e}")
        return jsonify({'erro': str(e)}), 500
