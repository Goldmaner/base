"""
Blueprint de Central de Certidões
Gerenciamento centralizado de certidões por OSC/CNPJ
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access
from werkzeug.utils import secure_filename
import os
from datetime import datetime, date
from PyPDF2 import PdfMerger
import io

certidoes_bp = Blueprint('certidoes', __name__, url_prefix='/certidoes')

# Configuração de upload
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'modelos', 'Certidoes')
ALLOWED_EXTENSIONS = {'pdf'}  # Apenas PDF permitido

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@certidoes_bp.route("/", methods=["GET"])
@login_required
@requires_access('certidoes')
def index():
    """
    Página principal da Central de Certidões
    Exibe grid de OSCs com pastas criadas
    """
    import time
    start_time = time.time()
    
    cur = get_cursor()
    
    # Obter filtro de busca
    filtro_busca = request.args.get('filtro_busca', '').strip().lower()
    
    print(f"[DEBUG] Inicio do carregamento - Filtro: {filtro_busca}")
    
    # Listar todas as pastas de OSCs
    oscs_com_pastas = []
    
    if os.path.exists(UPLOAD_FOLDER):
        t1 = time.time()
        pastas = os.listdir(UPLOAD_FOLDER)
        print(f"[DEBUG] Listou {len(pastas)} pastas em {(time.time() - t1)*1000:.2f}ms")
        
        # Buscar todos os CNPJs de uma vez para otimizar
        t2 = time.time()
        cur.execute("""
            SELECT DISTINCT 
                LOWER(SUBSTRING(osc FROM 1 FOR 50)) as osc_inicio,
                osc as osc_completo,
                cnpj
            FROM public.parcerias
        """)
        
        oscs_banco = cur.fetchall()
        # Criar mapa de busca
        mapa_cnpj = {}
        for row in oscs_banco:
            # Remover acentos e caracteres especiais para indexar
            chave = row['osc_completo'].lower()
            chave_limpa = chave.replace('á', 'a').replace('à', 'a').replace('ã', 'a').replace('â', 'a')\
                              .replace('é', 'e').replace('è', 'e').replace('ê', 'e')\
                              .replace('í', 'i').replace('ì', 'i').replace('î', 'i')\
                              .replace('ó', 'o').replace('ò', 'o').replace('õ', 'o').replace('ô', 'o')\
                              .replace('ú', 'u').replace('ù', 'u').replace('û', 'u')\
                              .replace('ç', 'c')\
                              .replace('-', ' ').replace(':', ' ').replace('.', ' ')
            
            # Indexar por várias versões
            mapa_cnpj[chave_limpa] = row['cnpj']
            mapa_cnpj[chave_limpa.replace(' ', '')] = row['cnpj']  # Sem espaços
            
        print(f"[DEBUG] Carregou {len(oscs_banco)} OSCs do banco em {(time.time() - t2)*1000:.2f}ms")
        
        t3 = time.time()
        for pasta in pastas:
            caminho_completo = os.path.join(UPLOAD_FOLDER, pasta)
            
            # Verificar se é um diretório
            if os.path.isdir(caminho_completo):
                # Converter nome da pasta para nome legível
                nome_osc = pasta.replace('_', ' ')
                
                # Aplicar filtro de busca se houver
                if not filtro_busca or filtro_busca in nome_osc.lower():
                    # Contar quantos arquivos tem na pasta
                    try:
                        arquivos = [f for f in os.listdir(caminho_completo) if os.path.isfile(os.path.join(caminho_completo, f))]
                        total_certidoes = len(arquivos)
                    except:
                        total_certidoes = 0
                    
                    # Buscar CNPJ no mapa
                    cnpj = 'N/A'
                    
                    # Tentar várias versões do nome
                    nome_busca = nome_osc.lower()
                    nome_busca_limpo = nome_busca.replace(' ', '')
                    
                    # Procurar no mapa
                    if nome_busca in mapa_cnpj:
                        cnpj = mapa_cnpj[nome_busca]
                    elif nome_busca_limpo in mapa_cnpj:
                        cnpj = mapa_cnpj[nome_busca_limpo]
                    else:
                        # Tentar busca parcial pelas primeiras palavras
                        palavras = nome_busca.split()[:3]  # Primeiras 3 palavras
                        for chave, valor_cnpj in mapa_cnpj.items():
                            if all(palavra in chave for palavra in palavras):
                                cnpj = valor_cnpj
                                break
                    
                    oscs_com_pastas.append({
                        'nome_pasta': pasta,
                        'nome_exibicao': nome_osc,
                        'cnpj': cnpj,
                        'total_certidoes': total_certidoes
                    })
        
        print(f"[DEBUG] Processou pastas em {(time.time() - t3)*1000:.2f}ms")
    
    # Ordenar por nome
    oscs_com_pastas.sort(key=lambda x: x['nome_exibicao'])
    
    total_time = (time.time() - start_time) * 1000
    print(f"[DEBUG] Tempo total: {total_time:.2f}ms")
    
    return render_template(
        'certidoes.html',
        oscs_com_pastas=oscs_com_pastas,
        filtro_busca=filtro_busca,
        total_oscs=len(oscs_com_pastas)
    )


@certidoes_bp.route("/osc/<nome_pasta>", methods=["GET"])
@login_required
@requires_access('certidoes')
def gestao_osc(nome_pasta):
    """
    Página de gestão de certidões de uma OSC específica
    Exibe grid das 7 certidões obrigatórias com upload
    """
    import time
    start_time = time.time()
    
    cur = get_cursor()
    
    # Buscar dados da OSC
    nome_busca = nome_pasta.replace('_', ' ').lower()
    print(f"[DEBUG OSC] Buscando OSC: {nome_busca}")
    
    # Busca simples: primeiras 3 palavras
    palavras = nome_busca.split()[:3]
    
    t1 = time.time()
    cur.execute("""
        SELECT DISTINCT osc, cnpj 
        FROM public.parcerias 
        WHERE LOWER(osc) LIKE %s
        LIMIT 1
    """, [f'%{" ".join(palavras)}%'])
    
    osc_data = cur.fetchone()
    print(f"[DEBUG OSC] Busca 1 em {(time.time() - t1)*1000:.2f}ms - Resultado: {osc_data is not None}")
    
    # Se não encontrou, tentar apenas primeira palavra
    if not osc_data and palavras:
        t2 = time.time()
        cur.execute("""
            SELECT DISTINCT osc, cnpj 
            FROM public.parcerias 
            WHERE LOWER(osc) LIKE %s
            LIMIT 1
        """, [f'{palavras[0]}%'])
        osc_data = cur.fetchone()
        print(f"[DEBUG OSC] Busca 2 em {(time.time() - t2)*1000:.2f}ms - Resultado: {osc_data is not None}")
    
    if not osc_data:
        print(f"[DEBUG OSC] OSC não encontrada: {nome_busca}")
        flash(f'OSC não encontrada: {nome_busca}. Verifique se o nome está correto na tabela parcerias.', 'error')
        return redirect(url_for('certidoes.index'))
    
    print(f"[DEBUG OSC] OSC encontrada: {osc_data['osc']} - CNPJ: {osc_data['cnpj']}")
    
    # Buscar lista de certidões obrigatórias com seus prazos
    t3 = time.time()
    cur.execute("""
        SELECT 
            certidao_nome_resumido,
            certidao_nome_completo,
            certidao_prazo,
            certidao_aplicabilidade,
            certidao_link,
            certidao_passos
        FROM categoricas.c_geral_certidoes
        WHERE certidao_nome_resumido IN ('CNPJ', 'CND', 'CNDT', 'CRF', 'CADIN Municipal', 'CTM', 'CENTS')
        ORDER BY 
            CASE certidao_nome_resumido
                WHEN 'CNPJ' THEN 1
                WHEN 'CND' THEN 2
                WHEN 'CNDT' THEN 3
                WHEN 'CRF' THEN 4
                WHEN 'CADIN Municipal' THEN 5
                WHEN 'CTM' THEN 6
                WHEN 'CENTS' THEN 7
            END
    """)
    
    certidoes_obrigatorias = cur.fetchall()
    print(f"[DEBUG OSC] Buscou certidões obrigatórias em {(time.time() - t3)*1000:.2f}ms")
    
    # Buscar certidões já cadastradas para esta OSC
    t4 = time.time()
    cur.execute("""
        SELECT 
            id,
            certidao_nome,
            certidao_emissor,
            certidao_vencimento,
            certidao_path,
            certidao_arquivo_nome,
            certidao_arquivo_size,
            certidao_status,
            observacoes,
            created_at,
            updated_at
        FROM public.certidoes
        WHERE osc = %s
    """, [osc_data['osc']])
    
    certidoes_cadastradas = cur.fetchall()
    print(f"[DEBUG OSC] Buscou certidões cadastradas em {(time.time() - t4)*1000:.2f}ms")
    print(f"[DEBUG OSC] Certidões cadastradas: {[cert['certidao_nome'] for cert in certidoes_cadastradas]}")
    
    # Criar mapa de certidões cadastradas por nome resumido
    certidoes_map = {}
    for cert in certidoes_cadastradas:
        # Usar o certidao_nome diretamente como chave (já é o nome resumido)
        certidoes_map[cert['certidao_nome']] = dict(cert)
        print(f"[DEBUG OSC] Mapeou: {cert['certidao_nome']}")
    
    print(f"[DEBUG OSC] Certidões no mapa: {list(certidoes_map.keys())}")
    
    total_time = (time.time() - start_time) * 1000
    print(f"[DEBUG OSC] Tempo total: {total_time:.2f}ms")
    
    return render_template(
        'certidoes_osc.html',
        osc=osc_data['osc'],
        cnpj=osc_data['cnpj'],
        nome_pasta=nome_pasta,
        certidoes_obrigatorias=certidoes_obrigatorias,
        certidoes_map=certidoes_map,
        usuario_email=session.get('email', ''),
        now=datetime.now
    )


@certidoes_bp.route("/api/oscs-ativas", methods=["GET"])
@login_required
@requires_access('certidoes')
def listar_oscs_ativas():
    """
    API: Lista OSCs com parcelas futuras não pagas (programadas/projetadas)
    Retorna relatório detalhado para visualização antes de gerar pastas
    """
    cur = get_cursor()
    
    # Query para buscar OSCs e suas parcelas detalhadas
    query = """
        SELECT 
            p.osc,
            p.cnpj,
            p.numero_termo,
            ul.vigencia_inicial,
            ul.vigencia_final,
            ul.parcela_tipo,
            ul.valor_previsto,
            ul.parcela_status,
            TO_CHAR(ul.vigencia_inicial, 'MM/YYYY') as mes_referencia,
            EXTRACT(YEAR FROM ul.vigencia_inicial) as ano,
            EXTRACT(MONTH FROM ul.vigencia_inicial) as mes
        FROM gestao_financeira.ultra_liquidacoes ul
        INNER JOIN public.parcerias p ON ul.numero_termo = p.numero_termo
        WHERE ul.vigencia_inicial >= '2026-01-01'
          AND ul.parcela_tipo IN ('Programada', 'Projetada')
          AND ul.parcela_status = 'Não Pago'
        ORDER BY p.osc, ul.vigencia_inicial
    """
    
    cur.execute(query)
    parcelas = cur.fetchall()
    
    # Agrupar por OSC
    oscs_detalhadas = {}
    for parcela in parcelas:
        osc_nome = parcela['osc']
        
        if osc_nome not in oscs_detalhadas:
            # Verificar se pasta já existe
            nome_pasta = secure_filename(osc_nome.replace(' ', '_'))
            caminho_pasta = os.path.join(UPLOAD_FOLDER, nome_pasta)
            pasta_existe = os.path.exists(caminho_pasta)
            
            oscs_detalhadas[osc_nome] = {
                'osc': osc_nome,
                'cnpj': parcela['cnpj'],
                'termos': set(),
                'parcelas': [],
                'total_valor': 0,
                'meses': set(),
                'pasta_existe': pasta_existe,
                'nome_pasta': nome_pasta
            }
        
        oscs_detalhadas[osc_nome]['termos'].add(parcela['numero_termo'])
        oscs_detalhadas[osc_nome]['parcelas'].append({
            'numero_termo': parcela['numero_termo'],
            'vigencia_inicial': parcela['vigencia_inicial'].strftime('%d/%m/%Y') if parcela['vigencia_inicial'] else '',
            'vigencia_final': parcela['vigencia_final'].strftime('%d/%m/%Y') if parcela['vigencia_final'] else '',
            'parcela_tipo': parcela['parcela_tipo'],
            'parcela_valor': float(parcela['valor_previsto']) if parcela['valor_previsto'] else 0,
            'mes_referencia': parcela['mes_referencia'],
            'ano': parcela['ano'],
            'mes': parcela['mes']
        })
        oscs_detalhadas[osc_nome]['total_valor'] += float(parcela['valor_previsto']) if parcela['valor_previsto'] else 0
        oscs_detalhadas[osc_nome]['meses'].add(parcela['mes_referencia'])
    
    # Converter para lista e formatar
    resultado = []
    total_novas = 0
    total_existentes = 0
    
    for osc_data in oscs_detalhadas.values():
        osc_data['termos'] = list(osc_data['termos'])
        osc_data['meses'] = sorted(list(osc_data['meses']))
        osc_data['total_parcelas'] = len(osc_data['parcelas'])
        osc_data['total_termos'] = len(osc_data['termos'])
        resultado.append(osc_data)
        
        if osc_data['pasta_existe']:
            total_existentes += 1
        else:
            total_novas += 1
    
    return jsonify({
        'success': True,
        'oscs': resultado,
        'total_oscs': len(resultado),
        'total_parcelas_geral': sum(len(osc['parcelas']) for osc in resultado),
        'total_pastas_novas': total_novas,
        'total_pastas_existentes': total_existentes
    })


@certidoes_bp.route("/api/gerar-pastas", methods=["POST"])
@login_required
@requires_access('certidoes')
def gerar_pastas_oscs():
    """
    Gera pastas físicas para cada OSC com parcelas futuras
    """
    try:
        cur = get_cursor()
        
        # Buscar OSCs ativas
        query = """
            SELECT DISTINCT
                p.osc,
                p.cnpj
            FROM gestao_financeira.ultra_liquidacoes ul
            INNER JOIN public.parcerias p ON ul.numero_termo = p.numero_termo
            WHERE ul.vigencia_inicial >= '2026-01-01'
              AND ul.parcela_tipo IN ('Programada', 'Projetada')
              AND ul.parcela_status = 'Não Pago'
            ORDER BY p.osc
        """
        
        cur.execute(query)
        oscs = cur.fetchall()
        
        pastas_criadas = []
        pastas_existentes = []
        erros = []
        
        # Criar pastas para cada OSC
        for osc in oscs:
            nome_osc = osc['osc']
            cnpj = osc['cnpj']
            
            # Sanitizar nome para usar como nome de pasta
            nome_pasta = secure_filename(nome_osc.replace(' ', '_'))
            caminho_pasta = os.path.join(UPLOAD_FOLDER, nome_pasta)
            
            try:
                if not os.path.exists(caminho_pasta):
                    os.makedirs(caminho_pasta)
                    pastas_criadas.append({
                        'osc': nome_osc,
                        'cnpj': cnpj,
                        'caminho': nome_pasta
                    })
                else:
                    pastas_existentes.append({
                        'osc': nome_osc,
                        'cnpj': cnpj,
                        'caminho': nome_pasta
                    })
            except Exception as e:
                erros.append({
                    'osc': nome_osc,
                    'erro': str(e)
                })
        
        return jsonify({
            'success': True,
            'pastas_criadas': pastas_criadas,
            'pastas_existentes': pastas_existentes,
            'erros': erros,
            'total_oscs': len(oscs)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': str(e)
        }), 500


@certidoes_bp.route("/api/certidoes/<int:certidao_id>", methods=["GET"])
@login_required
@requires_access('certidoes')
def obter_certidao(certidao_id):
    """
    API: Obter dados de uma certidão específica
    """
    cur = get_cursor()
    
    cur.execute("""
        SELECT 
            id,
            osc,
            cnpj,
            certidao_nome,
            certidao_emissor,
            certidao_vencimento,
            certidao_path,
            certidao_arquivo_nome,
            certidao_arquivo_size,
            certidao_status,
            observacoes,
            encartado_por,
            created_at,
            updated_at
        FROM public.certidoes
        WHERE id = %s
    """, [certidao_id])
    
    certidao = cur.fetchone()
    
    if certidao:
        return jsonify({
            'success': True,
            'certidao': dict(certidao)
        })
    else:
        return jsonify({
            'success': False,
            'erro': 'Certidão não encontrada'
        }), 404


@certidoes_bp.route("/api/certidoes/upload-individual", methods=["POST"])
@login_required
@requires_access('certidoes')
def upload_certidao_individual():
    """
    API: Upload de certidão individual (para grid da OSC)
    Atualiza ou cria nova certidão
    """
    try:
        # Validar se arquivo foi enviado
        if 'arquivo' not in request.files:
            return jsonify({'success': False, 'erro': 'Nenhum arquivo enviado'}), 400
        
        arquivo = request.files['arquivo']
        
        if arquivo.filename == '':
            return jsonify({'success': False, 'erro': 'Nenhum arquivo selecionado'}), 400
        
        if not allowed_file(arquivo.filename):
            return jsonify({'success': False, 'erro': 'Apenas arquivos PDF são permitidos'}), 400
        
        # Validar se é realmente um PDF
        if not arquivo.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'erro': 'Apenas arquivos PDF são permitidos'}), 400
        
        # Validar tamanho (máximo 200KB)
        arquivo.seek(0, os.SEEK_END)
        tamanho_arquivo = arquivo.tell()
        arquivo.seek(0)
        
        if tamanho_arquivo > 300 * 1024:  # 300KB
            return jsonify({'success': False, 'erro': 'Arquivo muito grande. Máximo: 300KB'}), 400
        
        # Obter dados do formulário
        osc = request.form.get('osc', '').strip()
        cnpj = request.form.get('cnpj', '').strip()
        certidao_nome_resumido = request.form.get('certidao_nome_resumido', '').strip()
        certidao_vencimento = request.form.get('certidao_vencimento', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        certidao_id_existente = request.form.get('certidao_id', '').strip()  # Se já existe, atualizar
        
        # Validar campos obrigatórios
        if not all([osc, cnpj, certidao_nome_resumido, certidao_vencimento]):
            return jsonify({'success': False, 'erro': 'Campos obrigatórios não preenchidos'}), 400
        
        # Preparar nome do arquivo
        nome_arquivo_original = secure_filename(arquivo.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"{certidao_nome_resumido}_{timestamp}_{nome_arquivo_original}"
        
        # Criar pasta da OSC se não existir
        nome_pasta_osc = secure_filename(osc.replace(' ', '_'))
        caminho_pasta_osc = os.path.join(UPLOAD_FOLDER, nome_pasta_osc)
        
        if not os.path.exists(caminho_pasta_osc):
            os.makedirs(caminho_pasta_osc)
        
        # Salvar arquivo
        caminho_completo = os.path.join(caminho_pasta_osc, nome_arquivo)
        arquivo.save(caminho_completo)
        
        # Caminho relativo para salvar no banco
        caminho_relativo = os.path.join(nome_pasta_osc, nome_arquivo)
        
        # Obter usuário logado
        usuario = session.get('email', 'Sistema')
        
        cur = get_cursor()
        conn = get_db()
        
        # Verificar se já existe uma certidão com o mesmo nome para esta OSC
        cur.execute("""
            SELECT id, certidao_path 
            FROM public.certidoes 
            WHERE osc = %s AND certidao_nome = %s
            LIMIT 1
        """, [osc, certidao_nome_resumido])
        
        cert_existente = cur.fetchone()
        
        # Se já existe certidão, atualizar (deletar arquivo antigo)
        if cert_existente:
            certidao_id_existente = cert_existente['id']
            
            # Deletar arquivo antigo
            if cert_existente['certidao_path']:
                caminho_antigo = os.path.join(UPLOAD_FOLDER, cert_existente['certidao_path'])
                try:
                    if os.path.exists(caminho_antigo):
                        os.remove(caminho_antigo)
                        print(f"[INFO] Arquivo antigo deletado: {caminho_antigo}")
                except Exception as e:
                    print(f"[AVISO] Erro ao deletar arquivo antigo: {e}")
            
            # Atualizar registro
            cur.execute("""
                UPDATE public.certidoes
                SET certidao_vencimento = %s,
                    certidao_path = %s,
                    certidao_arquivo_nome = %s,
                    certidao_arquivo_size = %s,
                    observacoes = %s,
                    certidao_emissor = %s,
                    certidao_status = 'Ativa',
                    updated_at = now()
                WHERE id = %s
                RETURNING id
            """, [
                certidao_vencimento, caminho_relativo, nome_arquivo_original,
                tamanho_arquivo, observacoes, usuario, certidao_id_existente
            ])
            
            certidao_id = certidao_id_existente
            print(f"[INFO] Certidão atualizada: {certidao_nome_resumido} - ID: {certidao_id}")
        else:
            # Inserir novo registro
            cur.execute("""
                INSERT INTO public.certidoes (
                    osc, cnpj, certidao_nome, certidao_emissor, 
                    certidao_vencimento, certidao_path, certidao_arquivo_nome,
                    certidao_arquivo_size, observacoes, certidao_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, [
                osc, cnpj, certidao_nome_resumido, usuario,
                certidao_vencimento, caminho_relativo, nome_arquivo_original,
                tamanho_arquivo, observacoes, 'Ativa'
            ])
            
            certidao_id = cur.fetchone()['id']
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'mensagem': 'Certidão salva com sucesso!',
            'certidao_id': certidao_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': f'Erro ao salvar certidão: {str(e)}'
        }), 500


@certidoes_bp.route("/api/certidoes", methods=["POST"])
@login_required
@requires_access('certidoes')
def criar_certidao():
    """
    API: Criar nova certidão (com upload de arquivo)
    """
    try:
        # Validar se arquivo foi enviado
        if 'arquivo' not in request.files:
            return jsonify({'success': False, 'erro': 'Nenhum arquivo enviado'}), 400
        
        arquivo = request.files['arquivo']
        
        if arquivo.filename == '':
            return jsonify({'success': False, 'erro': 'Nenhum arquivo selecionado'}), 400
        
        if not allowed_file(arquivo.filename):
            return jsonify({'success': False, 'erro': 'Tipo de arquivo não permitido'}), 400
        
        # Obter dados do formulário
        osc = request.form.get('osc', '').strip()
        cnpj = request.form.get('cnpj', '').strip()
        certidao_nome = request.form.get('certidao_nome', '').strip()
        certidao_emissor = request.form.get('certidao_emissor', '').strip()
        certidao_vencimento = request.form.get('certidao_vencimento', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        
        # Validar campos obrigatórios
        if not all([osc, cnpj, certidao_nome, certidao_emissor, certidao_vencimento]):
            return jsonify({'success': False, 'erro': 'Todos os campos obrigatórios devem ser preenchidos'}), 400
        
        # Preparar nome do arquivo
        nome_arquivo_original = secure_filename(arquivo.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"{timestamp}_{nome_arquivo_original}"
        
        # Criar pasta da OSC se não existir
        nome_pasta_osc = secure_filename(osc.replace(' ', '_'))
        caminho_pasta_osc = os.path.join(UPLOAD_FOLDER, nome_pasta_osc)
        
        if not os.path.exists(caminho_pasta_osc):
            os.makedirs(caminho_pasta_osc)
        
        # Salvar arquivo
        caminho_completo = os.path.join(caminho_pasta_osc, nome_arquivo)
        arquivo.save(caminho_completo)
        
        # Obter tamanho do arquivo
        tamanho_arquivo = os.path.getsize(caminho_completo)
        
        # Caminho relativo para salvar no banco
        caminho_relativo = os.path.join(nome_pasta_osc, nome_arquivo)
        
        # Obter usuário logado
        usuario = session.get('email', 'Sistema')
        
        # Inserir no banco de dados
        cur = get_cursor()
        conn = get_db()
        
        cur.execute("""
            INSERT INTO public.certidoes (
                osc, cnpj, certidao_nome, certidao_emissor, 
                certidao_vencimento, certidao_path, certidao_arquivo_nome,
                certidao_arquivo_size, observacoes, encartado_por
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, [
            osc, cnpj, certidao_nome, certidao_emissor,
            certidao_vencimento, caminho_relativo, nome_arquivo_original,
            tamanho_arquivo, observacoes, usuario
        ])
        
        certidao_id = cur.fetchone()['id']
        conn.commit()
        
        return jsonify({
            'success': True,
            'mensagem': 'Certidão cadastrada com sucesso!',
            'certidao_id': certidao_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': f'Erro ao cadastrar certidão: {str(e)}'
        }), 500


@certidoes_bp.route("/api/certidoes/<int:certidao_id>", methods=["PUT"])
@login_required
@requires_access('certidoes')
def atualizar_certidao(certidao_id):
    """
    API: Atualizar dados de uma certidão (sem alterar arquivo)
    """
    try:
        data = request.get_json()
        
        cur = get_cursor()
        conn = get_db()
        
        # Verificar se certidão existe
        cur.execute("SELECT id FROM public.certidoes WHERE id = %s", [certidao_id])
        if not cur.fetchone():
            return jsonify({'success': False, 'erro': 'Certidão não encontrada'}), 404
        
        # Atualizar campos permitidos
        campos_atualizaveis = []
        valores = []
        
        if 'certidao_nome' in data:
            campos_atualizaveis.append("certidao_nome = %s")
            valores.append(data['certidao_nome'])
        
        if 'certidao_emissor' in data:
            campos_atualizaveis.append("certidao_emissor = %s")
            valores.append(data['certidao_emissor'])
        
        if 'certidao_vencimento' in data:
            campos_atualizaveis.append("certidao_vencimento = %s")
            valores.append(data['certidao_vencimento'])
        
        if 'certidao_status' in data:
            campos_atualizaveis.append("certidao_status = %s")
            valores.append(data['certidao_status'])
        
        if 'observacoes' in data:
            campos_atualizaveis.append("observacoes = %s")
            valores.append(data['observacoes'])
        
        if not campos_atualizaveis:
            return jsonify({'success': False, 'erro': 'Nenhum campo para atualizar'}), 400
        
        # Adicionar updated_at
        campos_atualizaveis.append("updated_at = now()")
        valores.append(certidao_id)
        
        query = f"""
            UPDATE public.certidoes 
            SET {', '.join(campos_atualizaveis)}
            WHERE id = %s
        """
        
        cur.execute(query, valores)
        conn.commit()
        
        return jsonify({
            'success': True,
            'mensagem': 'Certidão atualizada com sucesso!'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': f'Erro ao atualizar certidão: {str(e)}'
        }), 500


@certidoes_bp.route("/api/certidoes/deletar-individual/<int:certidao_id>", methods=["DELETE"])
@login_required
@requires_access('certidoes')
def deletar_certidao_individual(certidao_id):
    """
    API: Deletar certidão individual (para grid da OSC)
    Remove arquivo e registro do banco
    """
    try:
        cur = get_cursor()
        conn = get_db()
        
        # Buscar certidão para obter caminho do arquivo
        cur.execute("""
            SELECT certidao_path 
            FROM public.certidoes 
            WHERE id = %s
        """, [certidao_id])
        
        certidao = cur.fetchone()
        
        if not certidao:
            return jsonify({'success': False, 'erro': 'Certidão não encontrada'}), 404
        
        # Excluir arquivo físico
        if certidao['certidao_path']:
            caminho_completo = os.path.join(UPLOAD_FOLDER, certidao['certidao_path'])
            try:
                if os.path.exists(caminho_completo):
                    os.remove(caminho_completo)
            except Exception as e:
                print(f"[AVISO] Erro ao deletar arquivo físico: {e}")
        
        # Excluir registro do banco
        cur.execute("DELETE FROM public.certidoes WHERE id = %s", [certidao_id])
        conn.commit()
        
        return jsonify({
            'success': True,
            'mensagem': 'Certidão deletada com sucesso!'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': f'Erro ao deletar certidão: {str(e)}'
        }), 500


@certidoes_bp.route("/api/certidoes/<int:certidao_id>", methods=["DELETE"])
@login_required
@requires_access('certidoes')
def excluir_certidao(certidao_id):
    """
    API: Excluir uma certidão (remove arquivo e registro)
    """
    try:
        cur = get_cursor()
        conn = get_db()
        
        # Buscar certidão para obter caminho do arquivo
        cur.execute("""
            SELECT certidao_path 
            FROM public.certidoes 
            WHERE id = %s
        """, [certidao_id])
        
        certidao = cur.fetchone()
        
        if not certidao:
            return jsonify({'success': False, 'erro': 'Certidão não encontrada'}), 404
        
        # Tentar excluir arquivo físico
        if certidao['certidao_path']:
            caminho_completo = os.path.join(UPLOAD_FOLDER, certidao['certidao_path'])
            try:
                if os.path.exists(caminho_completo):
                    os.remove(caminho_completo)
            except Exception as e:
                print(f"[AVISO] Não foi possível excluir arquivo físico: {e}")
        
        # Excluir registro do banco
        cur.execute("DELETE FROM public.certidoes WHERE id = %s", [certidao_id])
        conn.commit()
        
        return jsonify({
            'success': True,
            'mensagem': 'Certidão excluída com sucesso!'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': f'Erro ao excluir certidão: {str(e)}'
        }), 500


@certidoes_bp.route("/api/juntar-pdfs/<nome_pasta>", methods=["GET"])
@login_required
@requires_access('certidoes')
def juntar_pdfs(nome_pasta):
    """
    API: Junta todas as certidões válidas em um único PDF
    Só permite se todas as 7 certidões obrigatórias estiverem presentes e válidas
    """
    try:
        cur = get_cursor()
        
        # Buscar dados da OSC
        nome_busca = nome_pasta.replace('_', ' ').lower()
        print(f"[DEBUG PDF] Buscando OSC: {nome_busca}")
        
        # Busca simples: primeiras 3 palavras
        palavras = nome_busca.split()[:3]
        
        cur.execute("""
            SELECT DISTINCT osc, cnpj 
            FROM public.parcerias 
            WHERE LOWER(osc) LIKE %s
            LIMIT 1
        """, [f'%{" ".join(palavras)}%'])
        
        osc_data = cur.fetchone()
        print(f"[DEBUG PDF] Busca 1 - Resultado: {osc_data is not None}")
        
        # Se não encontrou, tentar apenas primeira palavra
        if not osc_data and palavras:
            cur.execute("""
                SELECT DISTINCT osc, cnpj 
                FROM public.parcerias 
                WHERE LOWER(osc) LIKE %s
                LIMIT 1
            """, [f'{palavras[0]}%'])
            osc_data = cur.fetchone()
            print(f"[DEBUG PDF] Busca 2 - Resultado: {osc_data is not None}")
        
        if not osc_data:
            print(f"[DEBUG PDF] OSC não encontrada: {nome_busca}")
            return jsonify({'success': False, 'erro': 'OSC não encontrada'}), 404
        
        print(f"[DEBUG PDF] OSC encontrada: {osc_data['osc']}")
        
        # Buscar todas as certidões da OSC
        cur.execute("""
            SELECT 
                certidao_nome,
                certidao_path,
                certidao_vencimento,
                certidao_status
            FROM public.certidoes
            WHERE osc = %s
            ORDER BY 
                CASE certidao_nome
                    WHEN 'CNPJ' THEN 1
                    WHEN 'CND' THEN 2
                    WHEN 'CNDT' THEN 3
                    WHEN 'CRF' THEN 4
                    WHEN 'CADIN Municipal' THEN 5
                    WHEN 'CTM' THEN 6
                    WHEN 'CENTS' THEN 7
                    ELSE 8
                END
        """, [osc_data['osc']])
        
        certidoes = cur.fetchall()
        print(f"[DEBUG PDF] Certidões encontradas: {len(certidoes)} - {[c['certidao_nome'] for c in certidoes]}")
        
        # Validar se tem pelo menos 2 certidões
        if len(certidoes) < 2:
            return jsonify({
                'success': False, 
                'erro': f'Apenas {len(certidoes)} certidão cadastrada. É necessário ter pelo menos 2 certidões para gerar o PDF unificado.'
            }), 400
        
        # Validar se todas estão válidas (não vencidas)
        hoje = date.today()
        certidoes_vencidas = []
        
        for cert in certidoes:
            if cert['certidao_vencimento'] < hoje:
                certidoes_vencidas.append(cert['certidao_nome'])
        
        if certidoes_vencidas:
            return jsonify({
                'success': False,
                'erro': f'Existem certidões vencidas: {", ".join(certidoes_vencidas)}. Atualize-as antes de gerar o PDF unificado.'
            }), 400
        
        # Juntar PDFs
        merger = PdfMerger()
        
        for cert in certidoes:
            caminho_completo = os.path.join(UPLOAD_FOLDER, cert['certidao_path'])
            
            if not os.path.exists(caminho_completo):
                return jsonify({
                    'success': False,
                    'erro': f'Arquivo não encontrado: {cert["certidao_nome"]}'
                }), 404
            
            try:
                merger.append(caminho_completo)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'erro': f'Erro ao processar {cert["certidao_nome"]}: {str(e)}. Certifique-se de que é um PDF válido.'
                }), 400
        
        # Criar PDF em memória
        output = io.BytesIO()
        merger.write(output)
        merger.close()
        output.seek(0)
        
        # Nome do arquivo unificado
        nome_arquivo = f"Certidoes_{nome_pasta}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=nome_arquivo
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': f'Erro ao juntar PDFs: {str(e)}'
        }), 500


@certidoes_bp.route("/api/debug/oscs", methods=["GET"])
@login_required
@requires_access('certidoes')
def debug_oscs():
    """
    API de debug: Lista todas as OSCs na tabela parcerias para comparação
    """
    cur = get_cursor()
    
    cur.execute("""
        SELECT DISTINCT osc, cnpj 
        FROM public.parcerias 
        ORDER BY osc
    """)
    
    oscs = cur.fetchall()
    
    return jsonify({
        'success': True,
        'total': len(oscs),
        'oscs': [{'osc': osc['osc'], 'cnpj': osc['cnpj']} for osc in oscs]
    })


@certidoes_bp.route("/download/<int:certidao_id>", methods=["GET"])
@login_required
@requires_access('certidoes')
def download_certidao(certidao_id):
    """
    Download de arquivo de certidão
    """
    try:
        cur = get_cursor()
        
        cur.execute("""
            SELECT certidao_path, certidao_arquivo_nome 
            FROM public.certidoes 
            WHERE id = %s
        """, [certidao_id])
        
        certidao = cur.fetchone()
        
        if not certidao:
            flash('Certidão não encontrada', 'error')
            return redirect(url_for('certidoes.index'))
        
        caminho_completo = os.path.join(UPLOAD_FOLDER, certidao['certidao_path'])
        
        if not os.path.exists(caminho_completo):
            flash('Arquivo não encontrado no servidor', 'error')
            return redirect(url_for('certidoes.index'))
        
        return send_file(
            caminho_completo,
            as_attachment=True,
            download_name=certidao['certidao_arquivo_nome']
        )
        
    except Exception as e:
        flash(f'Erro ao baixar arquivo: {str(e)}', 'error')
        return redirect(url_for('certidoes.index'))
