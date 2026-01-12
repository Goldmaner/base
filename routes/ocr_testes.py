"""
Rotas para OCR de Testes - Conversão de Extratos Bancários
"""

from flask import Blueprint, render_template, request, jsonify, send_file, session
from db import get_cursor, get_db
from functools import wraps
import re
import csv
import io
from datetime import datetime
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("[AVISO] pdfplumber não instalado. Funcionalidade de PDF desabilitada.")

bp = Blueprint('ocr_testes', __name__, url_prefix='/ocr_testes')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Não autorizado'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
def index():
    """Página principal do OCR de testes"""
    return render_template('analises_pc/ocr_testes.html')


@bp.route('/api/processar-ocr', methods=['POST'])
@login_required
def processar_ocr():
    """Processa o texto do extrato e retorna CSV"""
    try:
        data = request.get_json()
        texto = data.get('texto', '')
        
        print(f"[OCR-DEBUG] Texto recebido: {len(texto)} caracteres")
        print(f"[OCR-DEBUG] Primeiras 200 chars: {texto[:200] if texto else 'VAZIO'}")
        
        if not texto.strip():
            print("[OCR-ERRO] Texto vazio recebido")
            return jsonify({'erro': 'Texto vazio'}), 400
        
        # Processar o texto
        linhas_processadas = processar_extrato(texto)
        print(f"[OCR-DEBUG] Linhas processadas: {len(linhas_processadas)}")
        
        if not linhas_processadas:
            print("[OCR-AVISO] Nenhuma linha foi processada do texto fornecido")
            return jsonify({'erro': 'Não foi possível processar nenhuma linha do extrato. Verifique o formato do texto.'}), 400
        
        # Gerar CSV em memória
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Cabeçalho
        campos = [
            "Data", "Credito", "Debito", "Composição de valor", 
            "Categoria da transação", "Competência", "Origem ou Destino", "Saldo"
        ]
        writer.writerow(campos)
        writer.writerows(linhas_processadas)
        
        # Preparar para download
        output.seek(0)
        csv_content = output.getvalue()
        
        # Criar arquivo em bytes para download
        mem = io.BytesIO()
        mem.write(csv_content.encode('utf-8-sig'))  # BOM para Excel
        mem.seek(0)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'extrato_convertido_{timestamp}.csv'
        
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao processar OCR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/processar-pdf', methods=['POST'])
@login_required
def processar_pdf():
    """Processa PDF do extrato e retorna CSV"""
    if not PDF_AVAILABLE:
        return jsonify({'erro': 'Biblioteca pdfplumber não instalada. Execute: pip install pdfplumber'}), 500
    
    try:
        if 'pdf' not in request.files:
            return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
        
        arquivo = request.files['pdf']
        
        if arquivo.filename == '':
            return jsonify({'erro': 'Arquivo sem nome'}), 400
        
        if not arquivo.filename.lower().endswith('.pdf'):
            return jsonify({'erro': 'Arquivo deve ser PDF'}), 400
        
        # Extrair texto do PDF (com timeout implícito para PDFs grandes)
        print(f"[OCR-PDF] Processando arquivo: {arquivo.filename}")
        texto_extraido = extrair_texto_pdf(arquivo)
        
        if not texto_extraido.strip():
            return jsonify({'erro': 'Não foi possível extrair texto do PDF'}), 400
        
        print(f"[OCR-PDF] Texto extraído: {len(texto_extraido)} caracteres")
        
        # Processar o texto extraído (reutiliza a mesma função)
        linhas_processadas = processar_extrato(texto_extraido)
        
        print(f"[OCR-PDF] Linhas processadas: {len(linhas_processadas)}")
        
        if not linhas_processadas:
            print("[OCR-PDF-AVISO] Nenhuma linha foi processada do PDF")
            return jsonify({'erro': 'Não foi possível processar nenhuma linha do PDF. Verifique o formato do extrato.'}), 400
        
        # Gerar CSV em memória
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Cabeçalho
        campos = [
            "Data", "Credito", "Debito", "Composição de valor", 
            "Categoria da transação", "Competência", "Origem ou Destino", "Saldo"
        ]
        writer.writerow(campos)
        writer.writerows(linhas_processadas)
        
        # Preparar para download
        output.seek(0)
        csv_content = output.getvalue()
        
        # Criar arquivo em bytes para download
        mem = io.BytesIO()
        mem.write(csv_content.encode('utf-8-sig'))  # BOM para Excel
        mem.seek(0)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'extrato_pdf_{timestamp}.csv'
        
        print(f"[OCR-PDF] Gerando arquivo: {filename}")
        
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao processar PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': f'Erro ao processar PDF: {str(e)}'}), 500


def extrair_texto_pdf(arquivo_pdf):
    """
    Extrai texto de PDF usando pdfplumber
    Retorna string com todo o texto extraído
    """
    texto_completo = []
    
    with pdfplumber.open(arquivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                texto_completo.append(texto)
    
    return '\n'.join(texto_completo)


def detectar_formato(texto):
    """
    Detecta qual formato de extrato está sendo processado
    Retorna 1 (formato antigo) ou 2 (formato novo)
    """
    linhas = [l.strip() for l in texto.split('\n') if l.strip()]
    
    print(f"[OCR-DEBUG] Total de linhas não vazias: {len(linhas)}")
    print(f"[OCR-DEBUG] Primeiras 5 linhas:")
    for i, linha in enumerate(linhas[:5]):
        print(f"  [{i}]: {linha[:100]}")
    
    # Contador de padrões de cada formato
    formato1_count = 0
    formato2_count = 0
    
    for linha in linhas[:30]:  # Analisa primeiras 30 linhas (aumentado para pegar mais amostras)
        # Formato 1: Data no início + C/D no final
        if re.match(r'^\d{2}/\d{2}/\d{4}.*[CD]$', linha):
            formato1_count += 1
            print(f"[OCR-DEBUG] Match F1: {linha[:80]}")
        
        # Formato 2: Valor no início + (+) ou (-) + Data
        if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}\s+\([+-]\)\s+\d{2}/\d{2}/\d{4}', linha):
            formato2_count += 1
            print(f"[OCR-DEBUG] Match F2: {linha[:80]}")
        
        # Formato 2 alternativo: apenas VALOR (SINAL) (sem data na mesma linha ainda)
        # Indica que provavelmente é formato 2 que foi quebrado
        if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}\s+\([+-]\)\s*$', linha):
            formato2_count += 0.5  # Conta meio ponto como indicativo
            print(f"[OCR-DEBUG] Match F2 parcial: {linha[:80]}")
    
    print(f"[OCR] Detecção de formato - F1: {formato1_count}, F2: {formato2_count}")
    
    # Se detectou qualquer indicativo de formato 2, usa formato 2
    return 2 if formato2_count >= 1 else 1


def processar_extrato(texto):
    """
    Processa o texto do extrato e retorna lista de linhas processadas
    Detecta automaticamente o formato e usa o processador adequado
    """
    # Pré-processar texto para juntar linhas quebradas (comum em PDFs/OCR)
    texto = preprocessar_texto(texto)
    
    formato = detectar_formato(texto)
    
    print(f"[OCR] Usando processador para Formato {formato}")
    
    if formato == 2:
        return processar_extrato_formato2(texto)
    else:
        return processar_extrato_formato1(texto)


def preprocessar_texto(texto):
    """
    Pré-processa o texto para juntar linhas que foram quebradas indevidamente
    Especialmente útil para formato 2 onde: VALOR (SINAL) DATA podem estar em linhas separadas
    """
    linhas = texto.split('\n')
    linhas_reconstruidas = []
    i = 0
    
    while i < len(linhas):
        linha_atual = linhas[i].strip()
        
        # Padrão: VALOR (SINAL) em uma linha, seguido de DATA na próxima
        # Ex: "0,00 (+)" seguido de "10/09/2024"
        if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}\s+\([+-]\)\s*$', linha_atual):
            # Próxima linha deve conter data
            if i + 1 < len(linhas):
                proxima = linhas[i + 1].strip()
                if re.match(r'^\d{2}/\d{2}/\d{4}', proxima):
                    # Juntar as linhas
                    linha_junta = f"{linha_atual} {proxima}"
                    linhas_reconstruidas.append(linha_junta)
                    print(f"[OCR-PREPROC] Juntou: '{linha_atual}' + '{proxima}' -> '{linha_junta}'")
                    i += 2  # Pula as duas linhas
                    continue
        
        linhas_reconstruidas.append(linha_atual)
        i += 1
    
    texto_reconstruido = '\n'.join(linhas_reconstruidas)
    print(f"[OCR-PREPROC] Linhas originais: {len(linhas)}, Linhas reconstruídas: {len(linhas_reconstruidas)}")
    
    return texto_reconstruido


def processar_extrato_formato1(texto):
    """
    Processa extrato no FORMATO 1 (antigo)
    Formato: DD/MM/YYYY ... VALOR C/D [SALDO C/D]
    """
    linhas = [l.strip() for l in texto.split('\n')]
    print(f"[OCR-F1] Processando {len(linhas)} linhas")
    
    # Expressão regular para detectar linha de movimentação
    # Captura: data, valor da transação, tipo (C/D), opcionalmente saldo e tipo do saldo
    regex_mov = re.compile(
        r'^(\d{2}/\d{2}/\d{4}).*?(\d{1,3}(?:\.\d{3})*,\d{2})\s*([CD])(?:\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*([CD]))?$'
    )
    
    saida = []
    matches_count = 0
    i = 0
    
    while i < len(linhas):
        linha = linhas[i].strip()
        m = regex_mov.match(linha)
        
        if m:
            matches_count += 1
            data, valor_transacao, tipo_transacao, saldo_valor, saldo_tipo = m.groups()
            
            # Categoria
            categoria = categoriza(linha)
            
            # Crédito/Débito da transação
            if tipo_transacao == 'C':
                credito, debito = valor_transacao.replace('.', ''), ''
            else:
                credito, debito = '', valor_transacao.replace('.', '')
            
            comp_valor = valor_transacao.replace('.', '')
            
            # Formatar saldo (se existir)
            saldo_formatado = ""
            if saldo_valor and saldo_tipo:
                saldo_formatado = f"{saldo_valor.replace('.', '')} {saldo_tipo}"
            
            # Origem/destino: linha seguinte, exceto resgate/taxa ("Banco do Brasil")
            nome_origem_destino = ""
            
            if categoria in ["Resgate", "Taxas Bancárias"]:
                nome_origem_destino = "Banco do Brasil"
            else:
                # Pula para a próxima linha não vazia, que não começa com data completa
                j = i + 1
                while j < len(linhas):
                    prox = linhas[j].strip()
                    # Ignora linhas vazias ou que começam com data completa
                    if prox and not re.match(r'^\d{2}/\d{2}/\d{4}', prox):
                        # Remove horário se houver e extrai o nome
                        nome_origem_destino = extrair_nome(prox)
                        if nome_origem_destino:  # Se conseguiu extrair um nome válido
                            break
                    if prox == "":
                        break
                    j += 1
            
            # Primeira linha do arquivo pode ser saldo anterior, não movimentação
            if "Saldo Anterior" in linha:
                saida.append([data, "", "", "", "", "", "", saldo_formatado])
            else:
                saida.append([
                    data,
                    credito if credito != "0,00" else "",
                    debito if debito != "0,00" else "",
                    comp_valor if comp_valor != "0,00" else "",
                    categoria,
                    "",
                    nome_origem_destino,
                    saldo_formatado
                ])
        
        i += 1
    
    print(f"[OCR-F1] Matches encontrados: {matches_count}")
    print(f"[OCR-F1] Linhas de saída: {len(saida)}")
    return saida


def processar_extrato_formato2(texto):
    """
    Processa extrato no FORMATO 2 (novo)
    Formato: VALOR (+/-) DD/MM/YYYY LOTE DOC HISTORICO
    Nome/origem na linha seguinte
    """
    linhas = [l.strip() for l in texto.split('\n')]
    print(f"[OCR-F2] Processando {len(linhas)} linhas")
    
    # Regex para formato 2: VALOR (SINAL) DATA
    regex_mov = re.compile(
        r'^(\d{1,3}(?:\.\d{3})*,\d{2})\s+\(([+-])\)\s+(\d{2}/\d{2}/\d{4})'
    )
    
    saida = []
    matches_count = 0
    i = 0
    
    while i < len(linhas):
        linha = linhas[i].strip()
        m = regex_mov.match(linha)
        
        if m:
            matches_count += 1
            valor_transacao, sinal, data = m.groups()
            
            # Extrair histórico da mesma linha (após a data e códigos)
            # Remove o padrão inicial capturado
            resto_linha = linha[m.end():].strip()
            # Remove números de lote/documento no início (apenas 2 grupos de números)
            historico = re.sub(r'^\d+\s+\d+\s+', '', resto_linha, count=1).strip()
            # Se ainda começar com muitos dígitos seguidos (ex: doc longo), remove
            historico = re.sub(r'^\d{10,}\s+', '', historico).strip()
            
            # Se o histórico é apenas números/códigos, buscar na próxima linha
            if not historico or re.match(r'^[\d\s]+$', historico):
                print(f"[OCR-F2-DEBUG] Histórico vazio ou só códigos, buscando próxima linha...")
                # Busca próxima linha não vazia
                j = i + 1
                while j < len(linhas):
                    proxima = linhas[j].strip()
                    if proxima and not regex_mov.match(proxima):
                        historico = proxima
                        print(f"[OCR-F2-DEBUG] Histórico encontrado na linha seguinte: '{historico}'")
                        break
                    if proxima == "":
                        break
                    j += 1
            
            print(f"[OCR-F2-DEBUG] Linha completa: '{linha[:100]}'")
            print(f"[OCR-F2-DEBUG] Histórico extraído: '{historico}'")
            
            # Categoria baseada no histórico
            categoria = categoriza_formato2(historico)
            
            print(f"[OCR-F2-DEBUG] Categoria atribuída: '{categoria}'")
            
            # Crédito/Débito
            if sinal == '+':
                credito, debito = valor_transacao.replace('.', ''), ''
            else:
                credito, debito = '', valor_transacao.replace('.', '')
            
            comp_valor = valor_transacao.replace('.', '')
            
            # Origem/destino: linha seguinte
            nome_origem_destino = ""
            
            # Se for "Saldo Anterior", deixa em branco
            if "Saldo Anterior" in historico:
                saida.append([data, "", "", "", "", "", "", comp_valor])
                i += 1
                continue
            
            # Se for categoria específica do BB, usa "Banco do Brasil"
            if categoria in ["Resgate", "Taxas Bancárias"]:
                nome_origem_destino = "Banco do Brasil"
            # ESPECIAL: Se o histórico contém "Pix - Enviado" ou "Pagamento de Boleto", busca o nome na próxima linha
            elif ("PIX" in historico.upper() and "ENVIADO" in historico.upper()) or \
                 ("PAGAMENTO" in historico.upper() and "BOLETO" in historico.upper()):
                # Busca a linha seguinte que contém o nome do destinatário
                j = i + 1
                while j < len(linhas):
                    prox = linhas[j].strip()
                    # Ignora linhas vazias ou que são novas movimentações
                    if prox and not regex_mov.match(prox):
                        # Verifica se não é uma linha de tarifa/histórico
                        if not prox.startswith("Tar.") and not prox.startswith("Tarifa"):
                            nome_extraido = extrair_nome_formato2(prox)
                            if nome_extraido and nome_extraido != "Banco do Brasil":
                                nome_origem_destino = nome_extraido
                                break
                    if prox == "":
                        break
                    j += 1
            else:
                # Busca próxima linha não vazia que não seja uma movimentação
                j = i + 1
                while j < len(linhas):
                    prox = linhas[j].strip()
                    # Ignora linhas vazias ou que são novas movimentações
                    if prox and not regex_mov.match(prox):
                        # Extrai nome (remove códigos e horários)
                        nome_origem_destino = extrair_nome_formato2(prox)
                        if nome_origem_destino:
                            break
                    if prox == "":
                        break
                    j += 1
            
            saida.append([
                data,
                credito if credito else "",
                debito if debito else "",
                comp_valor,
                categoria,
                "",  # Competência vazia
                nome_origem_destino,
                ""   # Saldo vazio (formato 2 não tem saldo em cada linha)
            ])
        
        i += 1
    
    print(f"[OCR-F2] Matches encontrados: {matches_count}")
    print(f"[OCR-F2] Linhas de saída: {len(saida)}")
    return saida


def extrair_nome_formato2(linha):
    """
    Extrai nome do formato 2
    Remove horários (HH:MM) e datas (DD/MM) do início
    """
    if not linha:
        return ""
    
    nome = linha.strip()
    
    # Remove horário no formato HH:MM
    nome = re.sub(r'^\d{2}:\d{2}\s+', '', nome)
    
    # Remove data DD/MM no início
    nome = re.sub(r'^\d{2}/\d{2}\s+', '', nome)
    
    # Remove texto de tarifa agrupada (caso especial)
    if "Tar. agrupadas" in nome or "ocorrencia" in nome.lower() or "Tarifa" in nome:
        return "Banco do Brasil"
    
    # Remove "SECRETARIA MUNICIPAL" duplicado
    nome = re.sub(r'^SECRETARIA MUNICIPAL\s+SECRETARIA MUNICIPAL', 'SECRETARIA MUNICIPAL', nome, flags=re.IGNORECASE)
    
    # Remove códigos de agência/documento se existirem no início
    # Ex: "260 0001 053246086000101 COMPANHIA PLA" -> "COMPANHIA PLA"
    nome = re.sub(r'^\d{3}\s+\d{4}\s+\d+\s+', '', nome)
    
    # Remove apenas números longos (CPF/CNPJ) seguidos de espaço no início
    nome = re.sub(r'^\d{11,14}\s+', '', nome)
    
    nome = nome.strip()
    
    # Se a linha é apenas "Pix - Enviado" ou similar, retorna vazio para buscar próxima
    if nome.lower() in ["pix - enviado", "pagamento de boleto", "pix", "ted"]:
        return ""
    
    # Title case para nomes próprios
    nome = nome.title()
    
    return nome if nome else ""


def categoriza_formato2(historico):
    """
    Categoriza transação do formato 2 baseada no histórico
    """
    s = historico.upper()
    
    print(f"[CATEGORIZA-F2] Analisando: '{s[:80]}'")
    
    # Resgate
    if "BB RENDA FIXA" in s or "RESGATE" in s:
        print(f"[CATEGORIZA-F2] -> Resgate")
        return "Resgate"
    
    # Taxas (incluindo Tarifa Pix Enviado)
    if "TARIFA" in s or "TAR." in s or "TAR " in s or "TARIFA PIX" in s:
        print(f"[CATEGORIZA-F2] -> Taxas Bancárias")
        return "Taxas Bancárias"
    
    # PIX devolvido/rejeitado
    if "PIX - REJEITADO" in s or "PIX - DEVOLVIDO" in s or "DEVOLVID" in s:
        print(f"[CATEGORIZA-F2] -> Pix / TED Devolvido")
        return "Pix / TED Devolvido"
    
    # Parcela (pagamento de fornecedor da prefeitura)
    if "SECRETARIA MUNICIPAL" in s and "FAZENDA" in s:
        print(f"[CATEGORIZA-F2] -> Parcela")
        return "Parcela"
    
    if "RECEBIMENTO FORNECEDOR" in s:
        print(f"[CATEGORIZA-F2] -> Parcela")
        return "Parcela"
    
    # Outros vazios
    print(f"[CATEGORIZA-F2] -> (vazio)")
    return ""


def extrair_nome(linha):
    """Extrai nome próprio/nome fantasia da linha"""
    if not linha:
        return ""
    
    nome = linha.strip()
    
    # Remove horário no formato HH:MM do início
    # Ex: "15:33 Igor Canova" -> "Igor Canova"
    nome = re.sub(r'^\d{2}:\d{2}\s+', '', nome)
    
    # Se começou com data (DD/MM), remove a data e mantém o resto
    # Ex: "27/11 LUISIANA SOUZA PRODUCOES" -> "LUISIANA SOUZA PRODUCOES"
    nome = re.sub(r'^\d{2}/\d{2}\s+', '', nome)
    
    # Se começou com data completa (DD/MM/YYYY), não é nome
    if re.match(r'^\d{2}/\d{2}/\d{4}', nome):
        return ""
    
    # Remove agência e códigos no formato: XXX XXXX NNNNNNNNNNNN Nome
    # Ex: "260 0001 053246086000101 COMPANHIA PLA" -> "COMPANHIA PLA"
    # Ex: "104 0689 018113566000195 18.113.566 LI" -> "18.113.566 LI"
    nome = re.sub(r'^\d{3}\s+\d{4}\s+\d+\s+', '', nome)
    
    # Remove apenas números longos (CPF/CNPJ) seguidos de espaço no início
    # CPF: 11 dígitos, CNPJ: 14 dígitos
    nome = re.sub(r'^\d{11,14}\s+', '', nome)
    
    # Remove códigos curtos do tipo "0001" no início
    nome = re.sub(r'^\d{1,4}\s+', '', nome)
    
    nome = nome.strip()
    
    # Maiúscula só nas iniciais
    nome = nome.title()
    
    # Corrige abreviações comuns
    if nome.endswith(" Li"):
        # Mantém "LI" em maiúsculo quando for sufixo
        nome = nome[:-3] + " LI"
    
    return nome if nome else ""


def categoriza(linha):
    """Categoriza a transação baseada no conteúdo da linha"""
    s = linha.upper()
    
    # BB Renda Fixa LP é sempre Resgate (quando for crédito)
    if "BB RENDA FIXA LP" in s:
        return "Resgate"
    elif "TED DEVOLVIDA" in s or "PIX - REJEITADO" in s or "PIX - DEVOLVIDO" in s:
        return "Pix / TED Devolvido"
    elif ("RESGATE" in s and "FUNDO" in s) or re.search(r'\bRESGATE\b', s):
        return "Resgate"
    elif "TAR DOC/TED ELETRÔNICO" in s or "TARIFA PACOTE DE SERVIÇOS" in s or "TAR. AGRUPADAS" in s or "TARIFA" in s or "TARIFA PIX" in s:
        return "Taxas Bancárias"
    elif "SECRETARIA MUNICIPAL" in s and "FAZENDA" in s:
        return "Parcela"
    else:
        return ""
