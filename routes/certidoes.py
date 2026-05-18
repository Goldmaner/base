"""
Blueprint de Central de Certidões
Gerenciamento centralizado de certidões por OSC/CNPJ
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file, current_app
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access
from werkzeug.utils import secure_filename
import os
from datetime import datetime, date
from PyPDF2 import PdfMerger
import io
import utils_storage as storage

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
    from datetime import datetime, date
    from dateutil.relativedelta import relativedelta
    
    start_total = time.time()
    cur = get_cursor()
    
    # Obter filtros
    filtro_busca = request.args.get('filtro_busca', '').strip().lower()
    filtro_data_parcela = request.args.get('filtro_data_parcela', '').strip()
    
    if filtro_data_parcela:
        current_app.logger.warning(f"🔍 FILTRO ATIVO: {filtro_data_parcela}")
    else:
        current_app.logger.info(f"📋 Carregando sem filtro de data")
    
    t1 = time.time()
    # Carregar OSCs com certidões direto do banco — zero chamadas ao Storage
    hoje = date.today()
    cur.execute("""
        SELECT
            c.osc,
            COALESCE(
                (SELECT MAX(p.cnpj) FROM public.parcerias p WHERE p.osc = c.osc),
                'N/A'
            )                                                                      AS cnpj,
            COUNT(c.id)::int                                                       AS total_certidoes,
            COUNT(c.id) FILTER (WHERE c.certidao_vencimento >= CURRENT_DATE)::int AS em_dia,
            COUNT(c.id) FILTER (WHERE c.certidao_vencimento < CURRENT_DATE)::int  AS atrasadas
        FROM public.certidoes c
        GROUP BY c.osc
        ORDER BY c.osc
    """)
    oscs_db = cur.fetchall()

    oscs_com_pastas   = []
    oscs_nomes_reais  = []
    certidoes_por_osc = {}

    for row in oscs_db:
        osc_nome = row['osc']
        if filtro_busca and filtro_busca not in osc_nome.lower():
            continue
        pasta = secure_filename(osc_nome.replace(' ', '_'))
        oscs_com_pastas.append({
            'nome_pasta':     pasta,
            'nome_exibicao':  osc_nome,
            'osc_nome_banco': osc_nome,
            'cnpj':           row['cnpj'] or 'N/A',
            'total_certidoes': row['total_certidoes'],
        })
        oscs_nomes_reais.append(osc_nome)
        certidoes_por_osc[osc_nome] = {
            'em_dia':    row['em_dia'],
            'atrasadas': row['atrasadas'],
            'total':     row['total_certidoes'],
        }

    print(f"⏱️ [PERF] Listar OSCs (DB): {(time.time() - t1)*1000:.0f}ms ({len(oscs_com_pastas)} OSCs)")

    # Query 2: Buscar TODAS as parcelas pendentes de uma vez
    t4 = time.time()
    parcelas_por_osc = {}
    
    if oscs_nomes_reais:
        placeholders = ','.join(['%s'] * len(oscs_nomes_reais))
        if filtro_data_parcela:
            # Filtro específico por data
            data_ref = datetime.strptime(filtro_data_parcela, '%Y-%m-%d').date()
            primeiro_dia = data_ref.replace(day=1)
            ultimo_dia = (primeiro_dia + relativedelta(months=1)) - relativedelta(days=1)
            
            cur.execute(f"""
                SELECT 
                    p.osc,
                    COUNT(*) as total,
                    TO_CHAR(%s, 'MM/YY') as mes_ref
                FROM gestao_financeira.ultra_liquidacoes ul
                INNER JOIN public.parcerias p ON ul.numero_termo = p.numero_termo
                WHERE p.osc IN ({placeholders})
                  AND ul.vigencia_inicial >= %s
                  AND ul.vigencia_inicial <= %s
                  AND ul.parcela_tipo IN ('Programada', 'Projetada')
                  AND ul.parcela_status = 'Não Pago'
                GROUP BY p.osc
            """, [data_ref] + oscs_nomes_reais + [primeiro_dia, ultimo_dia])
            
            for row in cur.fetchall():
                parcelas_por_osc[row['osc']] = {
                    'total': row['total'],
                    'mes_ref': row['mes_ref']
                }
        else:
            # Parcelas no mês atual ou passadas não pagas
            cur.execute(f"""
                WITH parcelas_agrupadas AS (
                    SELECT 
                        p.osc,
                        TO_CHAR(ul.vigencia_inicial, 'MM/YY') as mes_ref,
                        COUNT(*) as total,
                        MIN(ul.vigencia_inicial) as primeira_vigencia,
                        ROW_NUMBER() OVER (PARTITION BY p.osc ORDER BY MIN(ul.vigencia_inicial) DESC) as rn
                    FROM gestao_financeira.ultra_liquidacoes ul
                    INNER JOIN public.parcerias p ON ul.numero_termo = p.numero_termo
                    WHERE p.osc IN ({placeholders})
                      AND ul.vigencia_inicial <= CURRENT_DATE
                      AND ul.parcela_tipo IN ('Programada', 'Projetada')
                      AND ul.parcela_status = 'Não Pago'
                    GROUP BY p.osc, TO_CHAR(ul.vigencia_inicial, 'MM/YY')
                )
                SELECT osc, mes_ref, total
                FROM parcelas_agrupadas
                WHERE rn = 1
            """, oscs_nomes_reais)
            
            for row in cur.fetchall():
                parcelas_por_osc[row['osc']] = {
                    'total': row['total'],
                    'mes_ref': row['mes_ref']
                }
        
        print(f"⏱️ [PERF] Buscar parcelas (bulk): {(time.time() - t4)*1000:.0f}ms")
    
    # Aplicar dados agrupados aos objetos OSC
    t5 = time.time()
    for osc_data in oscs_com_pastas:
        nome_banco = osc_data.get('osc_nome_banco')
        
        if nome_banco:
            # Certidões
            if nome_banco in certidoes_por_osc:
                osc_data['certidoes_em_dia'] = certidoes_por_osc[nome_banco]['em_dia']
                osc_data['certidoes_atrasadas'] = certidoes_por_osc[nome_banco]['atrasadas']
                osc_data['total_certidoes_db'] = certidoes_por_osc[nome_banco]['total']
            else:
                osc_data['certidoes_em_dia'] = 0
                osc_data['certidoes_atrasadas'] = 0
                osc_data['total_certidoes_db'] = 0
            
            # Parcelas
            if nome_banco in parcelas_por_osc:
                osc_data['parcelas_pendentes'] = parcelas_por_osc[nome_banco]['total']
                osc_data['mes_parcela'] = parcelas_por_osc[nome_banco]['mes_ref']
            else:
                osc_data['parcelas_pendentes'] = 0
                osc_data['mes_parcela'] = None
        else:
            osc_data['certidoes_em_dia'] = 0
            osc_data['certidoes_atrasadas'] = 0
            osc_data['total_certidoes_db'] = 0
            osc_data['parcelas_pendentes'] = 0
            osc_data['mes_parcela'] = None
    
    print(f"⏱️ [PERF] Aplicar dados: {(time.time() - t5)*1000:.0f}ms")
    
    print(f"⏱️ [PERF] Aplicar dados: {(time.time() - t5)*1000:.0f}ms")
    
    # Filtrar por data de parcela se necessário
    if filtro_data_parcela:
        oscs_com_pastas = [osc for osc in oscs_com_pastas if osc.get('parcelas_pendentes', 0) > 0]
    
    # Ordenar por nome
    oscs_com_pastas.sort(key=lambda x: x['nome_exibicao'])
    
    tempo_total = (time.time() - start_total) * 1000
    print(f"✅ [PERF] TEMPO TOTAL: {tempo_total:.0f}ms ({len(oscs_com_pastas)} OSCs carregadas)")
    
    return render_template(
        'certidoes.html',
        oscs_com_pastas=oscs_com_pastas,
        filtro_busca=filtro_busca,
        filtro_data_parcela=filtro_data_parcela,
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
    cur = get_cursor()
    
    # Buscar dados da OSC
    osc_nome_direto = request.args.get('osc_nome', '').strip()
    nome_busca = nome_pasta.replace('_', ' ').lower()
    palavras = nome_busca.split()[:3]
    osc_data = None

    # Tentativa 0: Usar nome direto do banco (passado via query param pelo front-end)
    if osc_nome_direto:
        cur.execute("""
            SELECT osc, cnpj
            FROM public.parcerias
            WHERE osc = %s
            LIMIT 1
        """, [osc_nome_direto])
        osc_data = cur.fetchone()

        # Tentar em celebração se não encontrou em parcerias
        if not osc_data:
            cur.execute("""
                SELECT DISTINCT osc, cnpj
                FROM celebracao.celebracao_parcerias
                WHERE osc = %s AND status_generico = 'Em celebração'
                LIMIT 1
            """, [osc_nome_direto])
            osc_data = cur.fetchone()

    # Tentativa 1: Reconstrução pelo nome da pasta com 3 palavras (fallback)
    if not osc_data:
        cur.execute("""
            SELECT osc, cnpj
            FROM public.parcerias
            WHERE unaccent(LOWER(osc)) LIKE unaccent(%s)
            LIMIT 1
        """, [f'%{" ".join(palavras)}%'])
        osc_data = cur.fetchone()

    # Tentativa 2: Nome completo com LIKE inicial
    if not osc_data:
        cur.execute("""
            SELECT osc, cnpj 
            FROM public.parcerias 
            WHERE unaccent(LOWER(osc)) LIKE unaccent(%s)
            ORDER BY LENGTH(osc) ASC
            LIMIT 1
        """, [f'{nome_busca}%'])
        osc_data = cur.fetchone()

    # Tentativa 3: Apenas primeira palavra
    if not osc_data and palavras:
        cur.execute("""
            SELECT osc, cnpj 
            FROM public.parcerias 
            WHERE unaccent(LOWER(osc)) LIKE unaccent(%s)
            ORDER BY LENGTH(osc) ASC
            LIMIT 1
        """, [f'{palavras[0]}%'])
        osc_data = cur.fetchone()

    # Tentativa 4: match por secure_filename (cobre @ e outros chars especiais)
    if not osc_data:
        cur.execute("SELECT DISTINCT osc, cnpj FROM public.parcerias")
        todas_parcerias = cur.fetchall()
        pasta_lower = nome_pasta.lower()
        for row in todas_parcerias:
            computed = secure_filename(row['osc'].replace(' ', '_')).lower()
            if computed == pasta_lower:
                osc_data = row
                break

    if not osc_data:
        flash(f'OSC não encontrada: {nome_busca}. Verifique se o nome está correto na tabela parcerias.', 'error')
        return redirect(url_for('certidoes.index'))
    
    # Buscar lista de certidões obrigatórias com seus prazos
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
    
    # Buscar certidões já cadastradas para esta OSC
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
    
    # Criar mapa de certidões cadastradas por nome resumido
    certidoes_map = {}
    for cert in certidoes_cadastradas:
        certidoes_map[cert['certidao_nome']] = dict(cert)
    
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
                'nome_pasta': nome_pasta,
                'tipo_origem': 'parcela'
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

    # Adicionar OSCs em processo de celebração
    cur.execute("""
        SELECT DISTINCT osc, cnpj
        FROM celebracao.celebracao_parcerias
        WHERE status_generico = 'Em celebração'
        ORDER BY osc
    """)
    oscs_celebracao = cur.fetchall()

    cnpjs_existentes = {data['cnpj'] for data in oscs_detalhadas.values() if data.get('cnpj')}
    nomes_existentes = set(oscs_detalhadas.keys())

    for osc_celeb in oscs_celebracao:
        osc_nome = osc_celeb['osc']
        cnpj_celeb = osc_celeb['cnpj'] or 'N/A'
        # Ignorar duplicatas por nome ou CNPJ
        if osc_nome in nomes_existentes:
            continue
        if cnpj_celeb and cnpj_celeb != 'N/A' and cnpj_celeb in cnpjs_existentes:
            continue
        nome_pasta = secure_filename(osc_nome.replace(' ', '_'))
        caminho_pasta = os.path.join(UPLOAD_FOLDER, nome_pasta)
        pasta_existe = os.path.exists(caminho_pasta)
        oscs_detalhadas[osc_nome] = {
            'osc': osc_nome,
            'cnpj': cnpj_celeb,
            'termos': set(),
            'parcelas': [],
            'total_valor': 0,
            'meses': set(),
            'pasta_existe': pasta_existe,
            'nome_pasta': nome_pasta,
            'tipo_origem': 'celebracao'
        }

    # Converter para lista e formatar
    resultado = []
    total_novas = 0
    total_existentes = 0
    total_celebracao = 0

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

        if osc_data.get('tipo_origem') == 'celebracao':
            total_celebracao += 1

    return jsonify({
        'success': True,
        'oscs': resultado,
        'total_oscs': len(resultado),
        'total_parcelas_geral': sum(len(osc['parcelas']) for osc in resultado if osc.get('tipo_origem') != 'celebracao'),
        'total_pastas_novas': total_novas,
        'total_pastas_existentes': total_existentes,
        'total_celebracao': total_celebracao
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

        # Buscar também OSCs em processo de celebração
        cur.execute("""
            SELECT DISTINCT osc, cnpj
            FROM celebracao.celebracao_parcerias
            WHERE status_generico = 'Em celebração'
            ORDER BY osc
        """)
        oscs_celebracao = cur.fetchall()

        # Combinar listas evitando duplicatas por nome ou CNPJ
        oscs_combinadas = [{'osc': o['osc'], 'cnpj': o['cnpj']} for o in oscs]
        cnpjs_existentes = {o['cnpj'] for o in oscs_combinadas if o.get('cnpj')}
        nomes_existentes = {o['osc'] for o in oscs_combinadas}
        for osc_celeb in oscs_celebracao:
            cnpj_celeb = osc_celeb['cnpj'] or ''
            if osc_celeb['osc'] not in nomes_existentes:
                if not cnpj_celeb or cnpj_celeb not in cnpjs_existentes:
                    oscs_combinadas.append({'osc': osc_celeb['osc'], 'cnpj': cnpj_celeb or 'N/A'})

        pastas_criadas = []
        pastas_existentes = []
        erros = []

        # Criar pastas para cada OSC
        for osc in oscs_combinadas:
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
            'total_oscs': len(oscs_combinadas)
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
        
        # Caminho relativo para salvar no banco (barras normais para compatibilidade)
        nome_pasta_osc = secure_filename(osc.replace(' ', '_'))
        caminho_relativo = f"{nome_pasta_osc}/{nome_arquivo}"
        
        # Ler bytes e enviar ao storage (local ou Supabase conforme USE_SUPABASE_STORAGE)
        arquivo.seek(0)
        file_bytes = arquivo.read()
        storage.upload_file(f"Certidoes/{caminho_relativo}", file_bytes, 'application/pdf')
        
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
                try:
                    storage.delete_file(f"Certidoes/{cert_existente['certidao_path']}")
                    print(f"[INFO] Arquivo antigo deletado: {cert_existente['certidao_path']}")
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
        
        # Excluir arquivo do storage (local ou Supabase)
        if certidao['certidao_path']:
            try:
                storage.delete_file(f"Certidoes/{certidao['certidao_path']}")
            except Exception as e:
                print(f"[AVISO] Erro ao deletar arquivo do storage: {e}")
        
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
        
        # Excluir arquivo do storage (local ou Supabase)
        if certidao['certidao_path']:
            try:
                storage.delete_file(f"Certidoes/{certidao['certidao_path']}")
            except Exception as e:
                print(f"[AVISO] Não foi possível excluir arquivo do storage: {e}")
        
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
        print(f"[DEBUG PDF] Nome da pasta recebido: {nome_pasta}")
        
        osc_data = None
        certidoes_por_path = None
        
        # OPÇÃO 0: Buscar pelo certidao_path normalizado (suporta / e \)
        # REPLACE(certidao_path, chr(92), '/') converte barras invertidas antes do LIKE
        print(f"[DEBUG PDF] OPÇÃO 0: Buscando em certidoes pelo path da pasta...")
        cur.execute("""
            SELECT DISTINCT osc, cnpj 
            FROM public.certidoes 
            WHERE REPLACE(certidao_path, chr(92), '/') LIKE %s
            LIMIT 1
        """, [f'{nome_pasta}/%'])
        
        osc_data = cur.fetchone()
        print(f"[DEBUG PDF] OPÇÃO 0 - Resultado: {osc_data is not None}")
        
        if osc_data:
            cur.execute("""
                SELECT 
                    certidao_nome,
                    certidao_path,
                    certidao_vencimento,
                    certidao_status
                FROM public.certidoes
                WHERE REPLACE(certidao_path, chr(92), '/') LIKE %s
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
            """, [f'{nome_pasta}/%'])
            certidoes_por_path = cur.fetchall()
            print(f"[DEBUG PDF] OPÇÃO 0 - Certidões por path: {len(certidoes_por_path)} - {[c['certidao_nome'] for c in certidoes_por_path]}")
        
        # ========================================
        # OPÇÃO 2: Buscar diretamente na tabela certidoes pelo OSC (fallback)
        # ========================================
        if not osc_data:
            print(f"[DEBUG PDF] OPÇÃO 2: Buscando em certidoes pelo OSC...")
            
            palavras_busca = nome_busca.split()
            
            cur.execute("""
                SELECT DISTINCT osc, cnpj 
                FROM public.certidoes 
                WHERE LOWER(osc) LIKE %s
                LIMIT 1
            """, [f'%{" ".join(palavras_busca)}%'])
            
            osc_data = cur.fetchone()
            print(f"[DEBUG PDF] OPÇÃO 2 - Resultado: {osc_data is not None}")
        
        # ========================================
        # OPÇÃO 1: Se não encontrou, buscar em parcerias (fallback)
        # ========================================
        if not osc_data:
            print(f"[DEBUG PDF] OPÇÃO 1: Buscando em parcerias...")
            palavras = nome_busca.split()[:3]
            
            # Busca 1: primeiras 3 palavras
            if len(palavras) >= 3:
                cur.execute("""
                    SELECT DISTINCT osc, cnpj 
                    FROM public.parcerias 
                    WHERE LOWER(osc) LIKE %s
                    LIMIT 1
                """, [f'%{" ".join(palavras)}%'])
                
                osc_data = cur.fetchone()
                print(f"[DEBUG PDF] OPÇÃO 1.1 (3 palavras) - Resultado: {osc_data is not None}")
            
            # Busca 2: Se não encontrou, tentar com todas as palavras (sem fallback para 1ª palavra)
            if not osc_data and len(palavras) >= 2:
                cur.execute("""
                    SELECT DISTINCT osc, cnpj 
                    FROM public.parcerias 
                    WHERE LOWER(osc) LIKE %s AND LOWER(osc) LIKE %s
                    LIMIT 1
                """, [f'%{palavras[0]}%', f'%{palavras[-1]}%'])
                osc_data = cur.fetchone()
                print(f"[DEBUG PDF] OPÇÃO 1.2 (1ª e última palavra) - Resultado: {osc_data is not None}")
        
        # ========================================
        # OPÇÃO 3: Se não encontrou no banco, tentar ler arquivos físicos da pasta
        # ========================================
        if not osc_data:
            print(f"[DEBUG PDF] OPÇÃO 3: OSC não encontrada no banco. Tentando ler arquivos no storage...")
            
            arquivos_pdf = [f for f in storage.list_files(f'Certidoes/{nome_pasta}') if f.lower().endswith('.pdf')]
            print(f"[DEBUG PDF] OPÇÃO 3 - Arquivos no storage: {arquivos_pdf}")
            
            if len(arquivos_pdf) > 0:
                osc_data = {
                    'osc': nome_pasta.replace('_', ' ').title(),
                    'cnpj': 'Não cadastrado'
                }
                print(f"[DEBUG PDF] OPÇÃO 3 - Usando storage para OSC: {osc_data['osc']}")
            else:
                print(f"[DEBUG PDF] OSC não encontrada no banco e sem arquivos no storage: {nome_busca}")
                return jsonify({'success': False, 'erro': 'OSC não encontrada no banco de dados e sem arquivos no storage'}), 404
        
        print(f"[DEBUG PDF] OSC identificada: {osc_data['osc']}")
        
        # Se já temos certidões por path (OPÇÃO 0), usar diretamente
        if certidoes_por_path is not None:
            certidoes = certidoes_por_path
        else:
            # Buscar todas as certidões da OSC no banco pelo nome da OSC
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
        
        # Se não encontrou no banco, usar arquivos físicos
        if len(certidoes) == 0:
            print(f"[DEBUG PDF] Nenhuma certidão no banco. Usando arquivos do storage...")
            arquivos_pdf = sorted([f for f in storage.list_files(f'Certidoes/{nome_pasta}') if f.lower().endswith('.pdf')])
            
            certidoes = []
            for arquivo in arquivos_pdf:
                certidoes.append({
                    'certidao_nome': arquivo.replace('.pdf', '').replace('_', ' '),
                    'certidao_path': f'{nome_pasta}/{arquivo}',
                    'certidao_vencimento': None,  # Sem validação de vencimento
                    'certidao_status': 'física'
                })
            
            print(f"[DEBUG PDF] Arquivos do storage carregados: {len(certidoes)} - {[c['certidao_nome'] for c in certidoes]}")
        else:
            print(f"[DEBUG PDF] Certidões encontradas no banco: {len(certidoes)} - {[c['certidao_nome'] for c in certidoes]}")
        
        # Validar se tem pelo menos 2 certidões
        if len(certidoes) < 2:
            return jsonify({
                'success': False, 
                'erro': f'Apenas {len(certidoes)} certidão cadastrada. É necessário ter pelo menos 2 certidões para gerar o PDF unificado.'
            }), 400
        
        # Validar se todas estão válidas (não vencidas) - apenas para certidões cadastradas
        hoje = date.today()
        certidoes_vencidas = []
        
        for cert in certidoes:
            # Pular validação se for arquivo físico sem data de vencimento
            if cert['certidao_vencimento'] is not None and cert['certidao_vencimento'] < hoje:
                certidoes_vencidas.append(cert['certidao_nome'])
        
        if certidoes_vencidas:
            return jsonify({
                'success': False,
                'erro': f'Existem certidões vencidas: {", ".join(certidoes_vencidas)}. Atualize-as antes de gerar o PDF unificado.'
            }), 400
        
        # Juntar PDFs
        merger = PdfMerger()
        
        for cert in certidoes:
            try:
                cert_bytes = storage.download_file(f"Certidoes/{cert['certidao_path']}")
            except FileNotFoundError:
                return jsonify({
                    'success': False,
                    'erro': f'Arquivo não encontrado: {cert["certidao_nome"]}'
                }), 404
            
            try:
                merger.append(io.BytesIO(cert_bytes))
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


@certidoes_bp.route("/api/juntar-pdfs-selecionados", methods=["POST"])
@login_required
@requires_access('certidoes')
def juntar_pdfs_selecionados():
    """
    API: Junta certidões selecionadas (por ID) em um único PDF.
    Recebe JSON: { "ids": [1, 2, 3], "nome_pasta": "...", "osc": "..." }
    """
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        nome_pasta = data.get('nome_pasta', 'Certidoes')
        if not ids:
            return jsonify({'success': False, 'erro': 'Nenhuma certidão selecionada.'}), 400

        cur = get_cursor()
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f"""
            SELECT certidao_nome, certidao_path, certidao_vencimento
            FROM public.certidoes
            WHERE id IN ({placeholders})
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
        """, ids)
        certidoes = cur.fetchall()

        if not certidoes:
            return jsonify({'success': False, 'erro': 'Nenhuma certidão encontrada para os IDs fornecidos.'}), 404

        merger = PdfMerger()
        for cert in certidoes:
            try:
                cert_bytes = storage.download_file(f"Certidoes/{cert['certidao_path']}")
            except FileNotFoundError:
                return jsonify({'success': False, 'erro': f'Arquivo não encontrado: {cert["certidao_nome"]}'}), 404
            try:
                merger.append(io.BytesIO(cert_bytes))
            except Exception as e:
                return jsonify({'success': False, 'erro': f'Erro ao processar {cert["certidao_nome"]}: {str(e)}'}), 400

        output = io.BytesIO()
        merger.write(output)
        merger.close()
        output.seek(0)

        nome_arquivo = f"Certidoes_{nome_pasta}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name=nome_arquivo)

    except Exception as e:
        return jsonify({'success': False, 'erro': f'Erro ao juntar PDFs: {str(e)}'}), 500


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
        
        try:
            file_bytes = storage.download_file(f"Certidoes/{certidao['certidao_path']}")
        except FileNotFoundError:
            flash('Arquivo não encontrado no servidor', 'error')
            return redirect(url_for('certidoes.index'))
        
        return send_file(
            io.BytesIO(file_bytes),
            as_attachment=True,
            download_name=certidao['certidao_arquivo_nome'],
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'Erro ao baixar arquivo: {str(e)}', 'error')
        return redirect(url_for('certidoes.index'))
