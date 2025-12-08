"""
Blueprint de gerenciamento de análises de prestação de contas
"""

from flask import Blueprint, render_template, request, jsonify, make_response
from db import get_cursor, execute_query
from utils import login_required
from decorators import requires_access
from datetime import datetime, timedelta
import io
import re


def determinar_responsabilidade_por_vigencia(portaria, vigencia_final):
    """
    Determina a responsabilidade da análise baseada na portaria do termo 
    e na data de término da vigência da prestação.
    
    Regras baseadas em períodos de transição:
    
    - Portaria 021 (TFM/TCL sem FUMCAD): 
      - Se vigencia_final >= 01/03/2023 → Pessoa Gestora (3)
      - Se vigencia_final < 01/03/2023 → Compartilhada (2) [era Portaria 121]
    
    - Portaria 090 (TFM/TCL com FUMCAD/FMID):
      - Se vigencia_final >= 01/01/2024 → Pessoa Gestora (3)
      - Se vigencia_final < 01/01/2024 → Compartilhada (2) [era Portaria 140]
    
    - Portaria 121 ou 140 diretamente → Compartilhada (2)
    - Outras portarias antigas (TCV, etc) → DP (1)
    
    Exemplo: Termo TFM/XXX/2023 com Portaria 090
    - Prestação 01/12/2023 a 28/02/2024 → Termina antes de 01/01/2024 = Compartilhada (2)
    - Prestação 01/03/2024 a 31/05/2024 → Termina depois de 01/01/2024 = Pessoa Gestora (3)
    
    Args:
        portaria (str): Nome da portaria (ex: 'Portaria nº 021/SMDHC/2023')
        vigencia_final (date/str): Data de término da vigência da prestação
    
    Returns:
        int: 1 (DP), 2 (Compartilhada) ou 3 (Pessoa Gestora)
    """
    if not portaria:
        return 1  # Default: DP
    
    # Converter vigencia_final para date se for string
    if isinstance(vigencia_final, str):
        try:
            vigencia_final = datetime.strptime(vigencia_final, '%Y-%m-%d').date()
        except:
            pass  # Se falhar, continua com o valor original
    
    # Datas de transição das portarias
    DATA_TRANSICAO_021 = datetime(2023, 3, 1).date()   # 01/03/2023 - Portaria 021 assume
    DATA_TRANSICAO_090 = datetime(2024, 1, 1).date()   # 01/01/2024 - Portaria 090 assume
    
    portaria_upper = portaria.upper()
    
    # Portaria 021 (TFM/TCL sem fundos) - verifica data de transição
    if '021/SMDHC/2023' in portaria_upper or '021' in portaria_upper and '2023' in portaria_upper:
        if vigencia_final and vigencia_final >= DATA_TRANSICAO_021:
            return 3  # Pessoa Gestora (prestação termina após 01/03/2023)
        else:
            return 2  # Compartilhada (prestação termina antes, ainda era Portaria 121)
    
    # Portaria 090 (TFM/TCL com FUMCAD/FMID) - verifica data de transição
    if '090/SMDHC/2023' in portaria_upper or '090' in portaria_upper and '2023' in portaria_upper:
        if vigencia_final and vigencia_final >= DATA_TRANSICAO_090:
            return 3  # Pessoa Gestora (prestação termina após 01/01/2024)
        else:
            return 2  # Compartilhada (prestação termina antes, ainda era Portaria 140)
    
    # Portarias 121 e 140 diretamente (período de transição 2017-2023)
    if '121/SMDHC/2019' in portaria_upper or '140/SMDHC/2019' in portaria_upper:
        return 2  # Compartilhada
    
    # Outras portarias antigas (TCV, Portarias 006, 072, 009, Decreto 6.170)
    return 1  # DP



def adicionar_dias_uteis(data_inicial, dias):
    """
    Adiciona dias úteis a uma data (não conta sábados e domingos)
    """
    data_atual = data_inicial
    dias_adicionados = 0
    
    while dias_adicionados < dias:
        data_atual += timedelta(days=1)
        # 0=Segunda, 6=Domingo
        if data_atual.weekday() < 5:  # Segunda a Sexta
            dias_adicionados += 1
    
    return data_atual


def calcular_prazo(vigencia_final, tipo_prestacao, portaria):
    """
    Calcula o prazo de entrega da prestação de contas
    Para Portarias 021 e 090:
    - Semestral: vigência final + 5 dias úteis
    - Final: vigência final + 45 dias corridos
    Retorna: (data_prazo, status_prazo)
    """
    if not vigencia_final:
        return None, ''
    
    # Verificar se é portaria 021 ou 090
    portarias_especiais = ['Portaria nº 021/SMDHC/2023', 'Portaria nº 090/SMDHC/2023']
    
    if portaria not in portarias_especiais:
        return None, ''
    
    hoje = datetime.now().date()
    
    if tipo_prestacao == 'Semestral':
        # Somar 5 dias úteis
        data_prazo = adicionar_dias_uteis(vigencia_final, 5)
    elif tipo_prestacao == 'Final':
        # Somar 45 dias corridos
        data_prazo = vigencia_final + timedelta(days=45)
    else:
        return None, ''
    
    # Verificar status
    if data_prazo < hoje:
        status = 'atrasado'  # Amarelo
    else:
        status = 'em_dia'  # Verde
    
    return data_prazo, status


def obter_data_rescisao(numero_termo):
    """
    Busca a data de rescisão de um termo na tabela termos_rescisao.
    
    Args:
        numero_termo (str): Número do termo
    
    Returns:
        date ou None: Data de rescisão ou None se não foi rescindido
    """
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT data_rescisao
            FROM public.termos_rescisao
            WHERE numero_termo = %s
            LIMIT 1
        """, (numero_termo,))
        
        resultado = cur.fetchone()
        cur.close()
        
        if resultado and resultado['data_rescisao']:
            return resultado['data_rescisao']
        return None
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar data de rescisão: {str(e)}")
        return None


analises_bp = Blueprint('analises', __name__, url_prefix='/analises')


@analises_bp.route("/api/anos-disponiveis", methods=["GET"])
@login_required
@requires_access('analises')
def obter_anos_disponiveis():
    """
    API para buscar os anos disponíveis nas datas de parecer
    """
    try:
        cur = get_cursor()
        
        # Buscar anos únicos de data_parecer_dp e data_parecer_pg
        query = """
            SELECT DISTINCT
                EXTRACT(YEAR FROM pa.data_parecer_dp) as ano_dp,
                EXTRACT(YEAR FROM pa.data_parecer_pg) as ano_pg
            FROM parcerias_analises pa
            WHERE pa.data_parecer_dp IS NOT NULL OR pa.data_parecer_pg IS NOT NULL
        """
        
        cur.execute(query)
        resultados = cur.fetchall()
        cur.close()
        
        # Coletar anos únicos
        anos_dp = set()
        anos_pg = set()
        
        for row in resultados:
            if row['ano_dp']:
                anos_dp.add(int(row['ano_dp']))
            if row['ano_pg']:
                anos_pg.add(int(row['ano_pg']))
        
        return jsonify({
            'anos_dp': sorted(list(anos_dp), reverse=True),
            'anos_pg': sorted(list(anos_pg), reverse=True)
        }), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar anos disponíveis: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@analises_bp.route("/api/modelo-ausencia-extratos", methods=["POST"])
@login_required
@requires_access('analises')
def obter_modelo_ausencia_extratos():
    """
    API para buscar modelo de texto de solicitação de extratos bancários
    baseado na portaria do termo.
    
    Regra:
    - Portarias 021/090 SMDHC/2019 → "Análise de Contas: Ausência de extratos bancários pós-2023"
    - Outras portarias → "Análise de Contas: Ausência de extratos bancários pré-2023"
    """
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo não fornecido'}), 400
        
        cur = get_cursor()
        
        # Buscar portaria do termo
        query_portaria = """
            SELECT portaria 
            FROM public.parcerias 
            WHERE numero_termo = %s
        """
        cur.execute(query_portaria, (numero_termo,))
        resultado = cur.fetchone()
        
        if not resultado:
            cur.close()
            return jsonify({'erro': 'Termo não encontrado'}), 404
        
        portaria = resultado['portaria']
        
        # Determinar qual modelo usar baseado na portaria
        if portaria and ('021/SMDHC/2019' in portaria or '090/SMDHC/2019' in portaria):
            titulo_modelo = 'Análise de Contas: Ausência de extratos bancários pós-2023'
        else:
            titulo_modelo = 'Análise de Contas: Ausência de extratos bancários pré-2023'
        
        # Buscar modelo de texto
        query_modelo = """
            SELECT titulo_texto, modelo_texto 
            FROM categoricas.c_modelo_textos 
            WHERE titulo_texto = %s
        """
        cur.execute(query_modelo, (titulo_modelo,))
        modelo = cur.fetchone()
        cur.close()
        
        if not modelo:
            return jsonify({
                'erro': f'Modelo "{titulo_modelo}" não encontrado no sistema'
            }), 404
        
        return jsonify({
            'titulo_texto': modelo['titulo_texto'],
            'modelo_texto': modelo['modelo_texto']
        }), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar modelo de texto: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@analises_bp.route("/", methods=["GET"])
@login_required
@requires_access('analises')
def listar():
    """
    Página principal de análises
    """
    return render_template('analises.html')


@analises_bp.route("/api/dados", methods=["GET"])
@login_required
@requires_access('analises')
def obter_dados():
    """
    API para buscar dados de análises com filtros
    """
    try:
        # Parâmetros de filtro
        limite = request.args.get('limite', '50')
        filtro_tipo = request.args.get('filtro_tipo', '')
        filtro_sei_pc = request.args.get('filtro_sei_pc', '')
        filtro_termo = request.args.get('filtro_termo', '')
        filtro_osc = request.args.get('filtro_osc', '')
        filtro_responsabilidade = request.args.get('filtro_responsabilidade', '')
        filtro_entregue = request.args.get('filtro_entregue', '')
        filtro_regularidade = request.args.get('filtro_regularidade', '')
        filtro_notificacao = request.args.get('filtro_notificacao', '')
        filtro_parecer = request.args.get('filtro_parecer', '')
        filtro_fase_recursal = request.args.get('filtro_fase_recursal', '')
        filtro_encerramento = request.args.get('filtro_encerramento', '')
        filtro_data_parecer_dp = request.args.get('filtro_data_parecer_dp', '')
        filtro_data_parecer_pg = request.args.get('filtro_data_parecer_pg', '')
        
        cur = get_cursor()
        
        # Query base com JOIN para buscar dados da tabela Parcerias e Analistas
        query = """
            SELECT 
                pa.id,
                pa.tipo_prestacao,
                pa.numero_prestacao,
                pa.vigencia_inicial,
                pa.vigencia_final,
                pa.numero_termo,
                pa.responsabilidade_analise,
                pa.entregue,
                pa.cobrado,
                pa.e_notificacao,
                pa.e_parecer,
                pa.e_fase_recursal,
                pa.e_encerramento,
                pa.data_parecer_dp,
                pa.valor_devolucao,
                pa.valor_devolvido,
                pa.responsavel_dp,
                pa.data_parecer_pg,
                pa.responsavel_pg,
                pa.observacoes,
                p.sei_pc,
                p.osc,
                p.portaria,
                a.nome_analista
            FROM parcerias_analises pa
            LEFT JOIN Parcerias p ON pa.numero_termo = p.numero_termo
            LEFT JOIN categoricas.c_analistas a ON pa.responsavel_dp = a.id
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if filtro_tipo:
            query += " AND pa.tipo_prestacao ILIKE %s"
            params.append(f'%{filtro_tipo}%')
        
        if filtro_sei_pc:
            query += " AND p.sei_pc ILIKE %s"
            params.append(f'%{filtro_sei_pc}%')
        
        if filtro_termo:
            query += " AND pa.numero_termo ILIKE %s"
            params.append(f'%{filtro_termo}%')
        
        if filtro_osc:
            query += " AND p.osc ILIKE %s"
            params.append(f'%{filtro_osc}%')
        
        if filtro_responsabilidade:
            if filtro_responsabilidade == "1":
                query += " AND pa.responsabilidade_analise = 1"
            elif filtro_responsabilidade == "2":
                query += " AND pa.responsabilidade_analise = 2"
            elif filtro_responsabilidade == "3":
                query += " AND pa.responsabilidade_analise = 3"
            elif filtro_responsabilidade == "null":
                query += " AND pa.responsabilidade_analise IS NULL"
        
        if filtro_entregue:
            if filtro_entregue == "sim":
                query += " AND pa.entregue = true"
            elif filtro_entregue == "nao":
                query += " AND pa.entregue = false"
        
        if filtro_notificacao:
            if filtro_notificacao == "sim":
                query += " AND pa.e_notificacao = true"
            elif filtro_notificacao == "nao":
                query += " AND pa.e_notificacao = false"
        
        if filtro_parecer:
            if filtro_parecer == "sim":
                query += " AND pa.e_parecer = true"
            elif filtro_parecer == "nao":
                query += " AND pa.e_parecer = false"
        
        if filtro_fase_recursal:
            if filtro_fase_recursal == "sim":
                query += " AND pa.e_fase_recursal = true"
            elif filtro_fase_recursal == "nao":
                query += " AND pa.e_fase_recursal = false"
        
        if filtro_encerramento:
            if filtro_encerramento == "sim":
                query += " AND pa.e_encerramento = true"
            elif filtro_encerramento == "nao":
                query += " AND pa.e_encerramento = false"
        
        # Filtros de ano para Data Parecer DP (aceita múltiplos anos separados por vírgula)
        if filtro_data_parecer_dp:
            anos_dp = [ano.strip() for ano in filtro_data_parecer_dp.split(',') if ano.strip()]
            if anos_dp:
                placeholders = ','.join(['%s'] * len(anos_dp))
                query += f" AND EXTRACT(YEAR FROM pa.data_parecer_dp) IN ({placeholders})"
                params.extend(anos_dp)
        
        # Filtros de ano para Data Parecer PG (aceita múltiplos anos separados por vírgula)
        if filtro_data_parecer_pg:
            anos_pg = [ano.strip() for ano in filtro_data_parecer_pg.split(',') if ano.strip()]
            if anos_pg:
                placeholders = ','.join(['%s'] * len(anos_pg))
                query += f" AND EXTRACT(YEAR FROM pa.data_parecer_pg) IN ({placeholders})"
                params.extend(anos_pg)
        
        # Ordenar por ID (ordem do banco de dados)
        query += """ ORDER BY pa.id ASC """
        
        # Aplicar limite
        if limite != 'todas':
            query += f" LIMIT {int(limite)}"
        
        cur.execute(query, params)
        resultados = cur.fetchall()
        cur.close()
        
        # Processar dados
        dados = []
        for row in resultados:
            # Calcular regularidade
            regularidade = calcular_regularidade(
                row['vigencia_final'],
                row['entregue'],
                row['tipo_prestacao']
            )
            
            # Filtrar por regularidade se especificado (comparação case-insensitive)
            if filtro_regularidade:
                if regularidade.lower() != filtro_regularidade.lower():
                    continue
            
            # Calcular prazo
            prazo_data, prazo_status = calcular_prazo(
                row['vigencia_final'],
                row['tipo_prestacao'],
                row['portaria']
            )
            prazo_formatado = prazo_data.strftime('%d/%m/%Y') if prazo_data else ''
            
            # Converter responsabilidade_analise
            resp_map = {1: 'DP', 2: 'Compartilhada', 3: 'Pessoa Gestora'}
            responsabilidade = resp_map.get(row['responsabilidade_analise'], '')
            
            # Extrair anos (para enviar ao frontend)
            ano_parecer_dp = str(row['data_parecer_dp'].year) if row['data_parecer_dp'] else ''
            ano_parecer_pg = str(row['data_parecer_pg'].year) if row['data_parecer_pg'] else ''
            
            # Formatar datas
            vigencia_inicial = row['vigencia_inicial'].strftime('%d/%m/%Y') if row['vigencia_inicial'] else ''
            vigencia_final = row['vigencia_final'].strftime('%d/%m/%Y') if row['vigencia_final'] else ''
            data_parecer_dp = row['data_parecer_dp'].strftime('%d/%m/%Y') if row['data_parecer_dp'] else ''
            data_parecer_pg = row['data_parecer_pg'].strftime('%d/%m/%Y') if row['data_parecer_pg'] else ''
            
            # Formatar valores monetários
            valor_devolucao = f"R$ {float(row['valor_devolucao']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if row['valor_devolucao'] else 'R$ 0,00'
            valor_devolvido = f"R$ {float(row['valor_devolvido']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if row['valor_devolvido'] else 'R$ 0,00'
            
            # Converter booleanos
            def bool_to_text(val):
                if val is None:
                    return ''
                return 'Sim' if val else 'Não'
            
            dados.append({
                'id': row['id'],
                'tipo_prestacao': row['tipo_prestacao'] or '',
                'numero_prestacao': row['numero_prestacao'],
                'vigencia_inicial': vigencia_inicial,
                'vigencia_final': vigencia_final,
                'numero_termo': row['numero_termo'] or '',
                'sei_pc': row['sei_pc'] or '',
                'osc': row['osc'] or '',
                'responsabilidade_analise': responsabilidade,
                'prazo': prazo_formatado,
                'prazo_status': prazo_status,
                'entregue': bool_to_text(row['entregue']),
                'regularidade': regularidade,
                'cobrado': bool_to_text(row['cobrado']),
                'e_notificacao': bool_to_text(row['e_notificacao']),
                'e_parecer': bool_to_text(row['e_parecer']),
                'e_fase_recursal': bool_to_text(row['e_fase_recursal']),
                'e_encerramento': bool_to_text(row['e_encerramento']),
                'data_parecer_dp': data_parecer_dp,
                'ano_parecer_dp': ano_parecer_dp,
                'valor_devolucao': valor_devolucao,
                'valor_devolvido': valor_devolvido,
                'responsavel_dp': row['nome_analista'] or '',
                'data_parecer_pg': data_parecer_pg,
                'ano_parecer_pg': ano_parecer_pg,
                'responsavel_pg': row['responsavel_pg'] or '',
                'observacoes': row['observacoes'] or ''
            })
        
        return jsonify(dados), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar análises: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


def calcular_regularidade(vigencia_final, entregue, tipo_prestacao):
    """
    Calcula a regularidade da prestação de contas
    Fórmula Excel: =SE([@[Vigência Final]]="";"";SE([@[Entregue?]]="Sim";"No prazo";
    SE(E([@[Tipo de Prestação]]="Final";[@[Vigência Final]]+45>HOJE());"Pendente";
    SE(E([@[Tipo de Prestação]]="Semestral";[@[Vigência Final]]+10>HOJE());"Pendente";"Atrasado"))))
    """
    if not vigencia_final:
        return ''
    
    if entregue:
        return 'No prazo'
    
    hoje = datetime.now().date()
    
    if tipo_prestacao == 'Final':
        prazo = vigencia_final + timedelta(days=45)
        return 'Pendente' if prazo > hoje else 'Atrasado'
    elif tipo_prestacao == 'Semestral':
        prazo = vigencia_final + timedelta(days=10)
        return 'Pendente' if prazo > hoje else 'Atrasado'
    
    return 'Atrasado'


@analises_bp.route("/api/exportar", methods=["GET"])
@login_required
@requires_access('analises')
def exportar_csv():
    """
    Exporta dados filtrados para CSV
    """
    try:
        # Reutilizar a mesma lógica de filtros
        # (código similar ao obter_dados, mas retorna CSV)
        
        # Buscar dados com os mesmos filtros
        from flask import request as req
        
        # Chamar a função obter_dados internamente
        response = obter_dados()
        dados = response[0].get_json()
        
        # Criar CSV
        output = io.StringIO()
        output.write('\ufeff')  # BOM para UTF-8
        
        # Cabeçalho
        colunas = [
            'Tipo de Prestação', 'Número', 'Vigência Inicial', 'Vigência Final',
            'Termo', 'Processo SEI PC', 'OSC', 'Responsabilidade', 'Prazo',
            'Entregue', 'Regularidade', 'Cobrado', 'Notificação', 'Parecer',
            'Fase Recursal', 'Encerramento', 'Data Parecer DP', 'Valor Devolução',
            'Valor Devolvido', 'Responsável DP', 'Data Parecer PG', 'Responsável PG',
            'Observações'
        ]
        output.write(';'.join(colunas) + '\n')
        
        # Dados
        for row in dados:
            linha = [
                row['tipo_prestacao'],
                str(row['numero_prestacao']),
                row['vigencia_inicial'],
                row['vigencia_final'],
                row['numero_termo'],
                row['sei_pc'],
                row['osc'],
                row['responsabilidade_analise'],
                row['prazo'],
                row['entregue'],
                row['regularidade'],
                row['cobrado'],
                row['e_notificacao'],
                row['e_parecer'],
                row['e_fase_recursal'],
                row['e_encerramento'],
                row['data_parecer_dp'],
                row['valor_devolucao'],
                row['valor_devolvido'],
                str(row['responsavel_dp']),
                row['data_parecer_pg'],
                row['responsavel_pg'],
                row['observacoes'].replace('\n', ' ').replace('\r', ' ')
            ]
            output.write(';'.join(linha) + '\n')
        
        # Preparar resposta
        csv_data = output.getvalue()
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=analises_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
        
    except Exception as e:
        print(f"[ERRO] Erro ao exportar CSV: {str(e)}")
        return jsonify({'erro': str(e)}), 500


@analises_bp.route("/editar-termo", methods=["GET", "POST"])
@login_required
@requires_access('analises')
def editar_por_termo():
    """
    Edita TODAS as análises de um termo específico de uma vez
    """
    if request.method == "GET":
        numero_termo = request.args.get('termo', '')
        
        if not numero_termo:
            return "Termo não especificado", 400
        
        # Buscar todas as análises deste termo com JOIN para nomes dos analistas
        cur = get_cursor()
        cur.execute("""
            SELECT pa.*, a.nome_analista
            FROM parcerias_analises pa
            LEFT JOIN categoricas.c_analistas a ON pa.responsavel_dp = a.id
            WHERE pa.numero_termo = %s
            ORDER BY pa.id ASC
        """, (numero_termo,))
        analises = cur.fetchall()
        
        # Buscar lista de analistas para dropdown
        cur.execute("""
            SELECT id, nome_analista
            FROM categoricas.c_analistas
            ORDER BY nome_analista
        """)
        analistas = cur.fetchall()
        cur.close()
        
        return render_template('editar_analises_termo.html', 
                             analises=analises,
                             analistas=analistas,
                             numero_termo=numero_termo)
    
    else:  # POST
        try:
            # Receber dados do formulário (JSON com array de análises)
            data = request.get_json()
            analises_atualizadas = data.get('analises', [])
            
            cur = get_cursor()
            for analise in analises_atualizadas:
                query = """
                    UPDATE parcerias_analises SET
                        responsabilidade_analise = %s,
                        entregue = %s,
                        cobrado = %s,
                        e_notificacao = %s,
                        e_parecer = %s,
                        e_fase_recursal = %s,
                        e_encerramento = %s,
                        data_parecer_dp = %s,
                        valor_devolucao = %s,
                        valor_devolvido = %s,
                        responsavel_dp = %s,
                        data_parecer_pg = %s,
                        responsavel_pg = %s,
                        observacoes = %s
                    WHERE id = %s
                """
                params = (
                    analise.get('responsabilidade_analise') or None,
                    analise.get('entregue'),
                    analise.get('cobrado'),
                    analise.get('e_notificacao'),
                    analise.get('e_parecer'),
                    analise.get('e_fase_recursal'),
                    analise.get('e_encerramento'),
                    analise.get('data_parecer_dp') or None,
                    analise.get('valor_devolucao') or None,
                    analise.get('valor_devolvido') or None,
                    analise.get('responsavel_dp') or None,
                    analise.get('data_parecer_pg') or None,
                    analise.get('responsavel_pg'),
                    analise.get('observacoes'),
                    analise.get('id')
                )
                cur.execute(query, params)
            
            from db import get_db
            get_db().commit()
            cur.close()
            
            return jsonify({'mensagem': 'Análises atualizadas com sucesso!'}), 200
            
        except Exception as e:
            print(f"[ERRO] Erro ao atualizar análises: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'erro': str(e)}), 500


@analises_bp.route('/adicionar', methods=['GET', 'POST'])
@login_required
@requires_access('analises')
def adicionar_analises():
    """
    Interface para adicionar novas análises de prestação de contas
    """
    from db import get_db
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            numero_termo = data.get('numero_termo')
            analises = data.get('analises', [])
            
            if not numero_termo or not analises:
                return jsonify({'erro': 'Dados incompletos'}), 400
            
            cur = get_cursor()
            
            # Buscar portaria do termo para determinar responsabilidade automática
            cur.execute("SELECT portaria FROM parcerias WHERE numero_termo = %s LIMIT 1", (numero_termo,))
            termo_info = cur.fetchone()
            portaria = termo_info['portaria'] if termo_info else None
            
            # Inserir cada análise
            for analise in analises:
                vigencia_final = analise.get('vigencia_final')
                
                # Determinar responsabilidade automática baseada na portaria E vigência final
                responsabilidade_auto = determinar_responsabilidade_por_vigencia(portaria, vigencia_final)
                
                query = """
                    INSERT INTO parcerias_analises (
                        numero_termo, tipo_prestacao, numero_prestacao,
                        vigencia_inicial, vigencia_final,
                        responsabilidade_analise,
                        entregue, cobrado, e_notificacao, e_parecer,
                        e_fase_recursal, e_encerramento,
                        data_parecer_dp, valor_devolucao, valor_devolvido,
                        responsavel_dp, data_parecer_pg, responsavel_pg, observacoes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    numero_termo,
                    analise.get('tipo_prestacao'),
                    analise.get('numero_prestacao'),
                    analise.get('vigencia_inicial'),
                    analise.get('vigencia_final'),
                    responsabilidade_auto,  # ← RESPONSABILIDADE AUTOMÁTICA
                    analise.get('entregue', False),
                    analise.get('cobrado', False),
                    analise.get('e_notificacao', False),
                    analise.get('e_parecer', False),
                    analise.get('e_fase_recursal', False),
                    analise.get('e_encerramento', False),
                    analise.get('data_parecer_dp') or None,
                    analise.get('valor_devolucao') or None,
                    analise.get('valor_devolvido') or None,
                    analise.get('responsavel_dp') or None,
                    analise.get('data_parecer_pg') or None,
                    analise.get('responsavel_pg'),
                    analise.get('observacoes')
                )
                cur.execute(query, params)
            
            get_db().commit()
            cur.close()
            
            return jsonify({'mensagem': 'Análises adicionadas com sucesso!'}), 200
            
        except Exception as e:
            print(f"[ERRO] Erro ao adicionar análises: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'erro': str(e)}), 500
    
    # GET - Buscar termos sem análises
    cur = get_cursor()
    
    # Buscar termos que não estão em parcerias_analises
    # EXCLUIR:
    # 1. Termos rescindidos em até 5 dias após o início (execução mínima)
    # 2. Termos rescindidos com total_pago = 0 (não recebeu recursos, logo não executou)
    query = """
        SELECT DISTINCT 
            p.numero_termo, 
            p.inicio, 
            p.final,
            p.portaria,
            tr.data_rescisao,
            p.total_pago,
            CASE 
                WHEN tr.data_rescisao IS NOT NULL THEN tr.data_rescisao
                ELSE p.final
            END as vigencia_efetiva
        FROM Parcerias p
        LEFT JOIN public.termos_rescisao tr ON p.numero_termo = tr.numero_termo
        WHERE p.numero_termo NOT IN (
            SELECT DISTINCT numero_termo FROM parcerias_analises
        )
        AND p.inicio IS NOT NULL
        AND p.final IS NOT NULL
        -- Excluir termos rescindidos em até 5 dias após o início (execução mínima)
        AND (tr.data_rescisao IS NULL OR tr.data_rescisao > p.inicio + INTERVAL '5 days')
        -- Excluir termos rescindidos com total_pago = 0 (não recebeu recursos)
        AND NOT (tr.data_rescisao IS NOT NULL AND COALESCE(p.total_pago, 0) = 0)
        ORDER BY p.numero_termo DESC
    """
    cur.execute(query)
    termos_pendentes = cur.fetchall()
    
    # Buscar analistas para dropdown
    cur.execute("SELECT id, nome_analista FROM categoricas.c_analistas ORDER BY nome_analista")
    analistas = cur.fetchall()
    cur.close()
    
    return render_template('adicionar_analises.html', 
                         termos_pendentes=termos_pendentes,
                         analistas=analistas)


@analises_bp.route('/api/adicionar-multiplos', methods=['POST'])
@login_required
@requires_access('analises')
def adicionar_analises_multiplos():
    """
    API para adicionar análises de múltiplos termos de uma vez
    Recebe lista de termos com suas prestações
    """
    from db import get_db
    
    try:
        data = request.get_json()
        termos = data.get('termos', [])
        
        if not termos:
            return jsonify({'erro': 'Nenhum termo informado'}), 400
        
        cur = get_cursor()
        
        termos_salvos = 0
        prestacoes_salvas = 0
        
        for termo_data in termos:
            numero_termo = termo_data.get('numero_termo')
            analises = termo_data.get('analises', [])
            
            if not numero_termo or not analises:
                continue
            
            # Buscar portaria do termo para determinar responsabilidade automática
            cur.execute("SELECT portaria FROM parcerias WHERE numero_termo = %s LIMIT 1", (numero_termo,))
            termo_info = cur.fetchone()
            portaria = termo_info['portaria'] if termo_info else None
            
            # Inserir cada análise
            for analise in analises:
                vigencia_final = analise.get('vigencia_final')
                
                # Determinar responsabilidade automática baseada na portaria E vigência final
                responsabilidade_auto = determinar_responsabilidade_por_vigencia(portaria, vigencia_final)
                
                query = """
                    INSERT INTO parcerias_analises (
                        numero_termo, tipo_prestacao, numero_prestacao,
                        vigencia_inicial, vigencia_final,
                        responsabilidade_analise,
                        entregue, cobrado, e_notificacao, e_parecer,
                        e_fase_recursal, e_encerramento,
                        data_parecer_dp, valor_devolucao, valor_devolvido,
                        responsavel_dp, data_parecer_pg, responsavel_pg, observacoes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    numero_termo,
                    analise.get('tipo_prestacao'),
                    analise.get('numero_prestacao'),
                    analise.get('vigencia_inicial'),
                    analise.get('vigencia_final'),
                    responsabilidade_auto,
                    analise.get('entregue', False),
                    analise.get('cobrado', False),
                    analise.get('e_notificacao', False),
                    analise.get('e_parecer', False),
                    analise.get('e_fase_recursal', False),
                    analise.get('e_encerramento', False),
                    analise.get('data_parecer_dp') or None,
                    analise.get('valor_devolucao') or None,
                    analise.get('valor_devolvido') or None,
                    analise.get('responsavel_dp') or None,
                    analise.get('data_parecer_pg') or None,
                    analise.get('responsavel_pg'),
                    analise.get('observacoes')
                )
                cur.execute(query, params)
                prestacoes_salvas += 1
            
            termos_salvos += 1
        
        get_db().commit()
        cur.close()
        
        return jsonify({
            'mensagem': f'{termos_salvos} termo(s) com {prestacoes_salvas} prestação(ões) adicionadas com sucesso!',
            'termos_salvos': termos_salvos,
            'prestacoes_salvas': prestacoes_salvas
        }), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao adicionar análises múltiplas: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@analises_bp.route('/api/calcular-prestacoes', methods=['POST'])
@login_required
@requires_access('analises')
def calcular_prestacoes():
    """
    API para calcular as prestações de contas baseado no termo selecionado
    Considera data de rescisão se o termo foi rescindido
    """
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Termo não informado'}), 400
        
        # Buscar dados do termo
        cur = get_cursor()
        query = """
            SELECT p.numero_termo, p.inicio, p.final, p.portaria,
                   tr.data_rescisao, p.total_pago
            FROM Parcerias p
            LEFT JOIN public.termos_rescisao tr ON p.numero_termo = tr.numero_termo
            WHERE p.numero_termo = %s
        """
        cur.execute(query, (numero_termo,))
        termo = cur.fetchone()
        cur.close()
        
        if not termo:
            return jsonify({'erro': 'Termo não encontrado'}), 404
        
        data_inicio = termo['inicio']
        data_termino_original = termo['final']
        data_rescisao = termo.get('data_rescisao')
        portaria = termo['portaria']
        total_pago = termo.get('total_pago') or 0
        
        # Se foi rescindido, validar execução
        if data_rescisao:
            dias_execucao = (data_rescisao - data_inicio).days
            
            # Validação 1: Rescindido em até 5 dias (execução mínima)
            if dias_execucao <= 5:
                return jsonify({
                    'erro': f'Termo foi rescindido em {data_rescisao.strftime("%d/%m/%Y")}, apenas {dias_execucao} dia(s) após o início. Não há prestações de contas a serem geradas (execução mínima não atingida).',
                    'data_rescisao': data_rescisao.strftime('%d/%m/%Y'),
                    'dias_execucao': dias_execucao
                }), 400
            
            # Validação 2: Rescindido com total_pago = 0 (não recebeu recursos)
            if total_pago == 0:
                return jsonify({
                    'erro': f'Termo foi rescindido em {data_rescisao.strftime("%d/%m/%Y")} sem ter recebido recursos (total pago: R$ 0,00). Não há prestações de contas a serem geradas, pois não houve execução financeira.',
                    'data_rescisao': data_rescisao.strftime('%d/%m/%Y'),
                    'dias_execucao': dias_execucao,
                    'total_pago': 0
                }), 400
        
        # Usar data de rescisão como término se existir
        data_termino = data_rescisao if data_rescisao else data_termino_original
        
        # Calcular prestações baseado na portaria e data efetiva
        prestacoes = gerar_prestacoes(numero_termo, data_inicio, data_termino, portaria)
        
        # Retornar com informação sobre rescisão se houver
        resposta = {
            'prestacoes': prestacoes,
            'total': len(prestacoes)
        }
        
        if data_rescisao:
            resposta['rescindido'] = True
            resposta['data_rescisao'] = data_rescisao.strftime('%d/%m/%Y')
            resposta['aviso'] = f'⚠️ Este termo foi rescindido em {data_rescisao.strftime("%d/%m/%Y")}. As prestações foram calculadas até esta data.'
        
        return jsonify(resposta), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao calcular prestações: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500
        
        return jsonify({'prestacoes': prestacoes}), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao calcular prestações: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


def gerar_prestacoes(numero_termo, data_inicio, data_termino, portaria):
    """
    Gera as prestações de contas baseado na portaria e período de vigência
    Usa lógica de dias para cálculos precisos
    
    IMPORTANTE: Considera transição de portarias:
    - Portaria 121 → 021 em 01/03/2023
    - Portaria 140 → 090 em 01/01/2024
    
    Após transição, trimestrais PARAM de ser geradas (só semestral + final)
    """
    from dateutil.relativedelta import relativedelta
    from datetime import date
    
    prestacoes = []
    
    # Definir tipo de prestações baseado na portaria
    portarias_semestral = ['Portaria nº 021/SMDHC/2023', 'Portaria nº 090/SMDHC/2023']
    portarias_trimestral_semestral = ['Portaria nº 121/SMDHC/2019', 'Portaria nº 140/SMDHC/2019']
    
    # Datas de transição de portarias
    DATA_TRANSICAO_121_PARA_021 = date(2023, 3, 1)  # 01/03/2023
    DATA_TRANSICAO_140_PARA_090 = date(2024, 1, 1)  # 01/01/2024
    
    # Determinar se há transição durante a vigência do termo
    data_transicao = None
    if portaria == 'Portaria nº 121/SMDHC/2019':
        if data_inicio < DATA_TRANSICAO_121_PARA_021 <= data_termino:
            data_transicao = DATA_TRANSICAO_121_PARA_021
    elif portaria == 'Portaria nº 140/SMDHC/2019':
        if data_inicio < DATA_TRANSICAO_140_PARA_090 <= data_termino:
            data_transicao = DATA_TRANSICAO_140_PARA_090
    
    # Calcular duração em meses
    duracao_meses = (data_termino.year - data_inicio.year) * 12 + (data_termino.month - data_inicio.month) + 1
    
    if portaria in portarias_semestral:
        # Portarias 021 e 090: Semestral + Final
        # REGRA: Só gerar semestral se houver MAIS de 6 meses de vigência
        # Se vigência <= 6 meses, gerar APENAS Final
        numero_prestacao = 1
        data_atual = data_inicio
        
        while data_atual < data_termino:
            # Calcular fim do semestre (6 meses)
            data_fim_semestre = data_atual + relativedelta(months=6) - relativedelta(days=1)
            
            # Se passou do término OU atingiu exatamente o término, NÃO gerar semestral
            # Nestes casos, a prestação Final já cobre todo o período
            if data_fim_semestre >= data_termino:
                # Esta seria a única semestral OU uma semestral parcial - NÃO gerar
                # A prestação Final já cobre todo o período
                break
            
            prestacoes.append({
                'tipo_prestacao': 'Semestral',
                'numero_prestacao': numero_prestacao,
                'vigencia_inicial': data_atual.strftime('%Y-%m-%d'),
                'vigencia_final': data_fim_semestre.strftime('%Y-%m-%d')
            })
            
            numero_prestacao += 1
            data_atual = data_fim_semestre + relativedelta(days=1)
            
            if data_atual > data_termino:
                break
        
        # Adicionar prestação final
        prestacoes.append({
            'tipo_prestacao': 'Final',
            'numero_prestacao': 1,
            'vigencia_inicial': data_inicio.strftime('%Y-%m-%d'),
            'vigencia_final': data_termino.strftime('%Y-%m-%d')
        })
        
    elif portaria in portarias_trimestral_semestral:
        # Portarias 121 e 140: Trimestral + Semestral + Final
        # COM TRANSIÇÃO: após data_transicao, NÃO gerar mais trimestrais
        
        # === TRIMESTRAIS ===
        # Só gera até a data de transição (se houver)
        data_limite_trimestral = data_transicao - relativedelta(days=1) if data_transicao else data_termino
        
        numero_prestacao = 1
        data_atual = data_inicio
        
        while data_atual < data_limite_trimestral:
            # Calcular fim do trimestre (3 meses)
            data_fim_trimestre = data_atual + relativedelta(months=3) - relativedelta(days=1)
            
            # Se passou do limite trimestral, ajustar para parar antes da transição
            if data_fim_trimestre > data_limite_trimestral:
                data_fim_trimestre = data_limite_trimestral
            
            prestacoes.append({
                'tipo_prestacao': 'Trimestral',
                'numero_prestacao': numero_prestacao,
                'vigencia_inicial': data_atual.strftime('%Y-%m-%d'),
                'vigencia_final': data_fim_trimestre.strftime('%Y-%m-%d')
            })
            
            numero_prestacao += 1
            data_atual = data_fim_trimestre + relativedelta(days=1)
            
            if data_atual >= data_limite_trimestral:
                break
        
        # === SEMESTRAIS ===
        # Gera para TODO o período (antes E depois da transição)
        # REGRA: Não gerar semestral parcial no final (menor que 6 meses)
        numero_semestral = 1
        data_atual = data_inicio
        
        while data_atual < data_termino:
            # Calcular fim do semestre (6 meses)
            data_fim_semestre = data_atual + relativedelta(months=6) - relativedelta(days=1)
            
            # Se passou do término, verificar se é semestre completo
            if data_fim_semestre > data_termino:
                # Esta seria uma semestral parcial - NÃO gerar
                # A prestação Final já cobre todo o período
                break
            
            prestacoes.append({
                'tipo_prestacao': 'Semestral',
                'numero_prestacao': numero_semestral,
                'vigencia_inicial': data_atual.strftime('%Y-%m-%d'),
                'vigencia_final': data_fim_semestre.strftime('%Y-%m-%d')
            })
            
            numero_semestral += 1
            data_atual = data_fim_semestre + relativedelta(days=1)
            
            if data_atual > data_termino:
                break
        
        # Adicionar prestação final
        prestacoes.append({
            'tipo_prestacao': 'Final',
            'numero_prestacao': 1,
            'vigencia_inicial': data_inicio.strftime('%Y-%m-%d'),
            'vigencia_final': data_termino.strftime('%Y-%m-%d')
        })
        
    else:
        # Outras portarias: Trimestral + Final
        
        # Gerar prestações trimestrais
        numero_prestacao = 1
        data_atual = data_inicio
        
        while data_atual < data_termino:
            # Calcular fim do trimestre (3 meses)
            data_fim_trimestre = data_atual + relativedelta(months=3) - relativedelta(days=1)
            
            # Se passou do término, ajustar
            if data_fim_trimestre > data_termino:
                data_fim_trimestre = data_termino
            
            prestacoes.append({
                'tipo_prestacao': 'Trimestral',
                'numero_prestacao': numero_prestacao,
                'vigencia_inicial': data_atual.strftime('%Y-%m-%d'),
                'vigencia_final': data_fim_trimestre.strftime('%Y-%m-%d')
            })
            
            numero_prestacao += 1
            data_atual = data_fim_trimestre + relativedelta(days=1)
            
            if data_atual > data_termino:
                break
        
        # Adicionar prestação final
        prestacoes.append({
            'tipo_prestacao': 'Final',
            'numero_prestacao': 1,
            'vigencia_inicial': data_inicio.strftime('%Y-%m-%d'),
            'vigencia_final': data_termino.strftime('%Y-%m-%d')
        })
    
    return prestacoes


@analises_bp.route('/atualizar-prestacoes', methods=['GET', 'POST'])
@login_required
@requires_access('analises')
def atualizar_prestacoes():
    """
    Interface para atualizar prestações de contas que estão com divergência de datas
    Compara datas de vigência da tabela Parcerias com parcerias_analises
    Considera data de rescisão se o termo foi rescindido
    """
    from db import get_db
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            numero_termo = data.get('numero_termo')
            
            if not numero_termo:
                return jsonify({'erro': 'Termo não informado'}), 400
            
            cur = get_cursor()
            
            # Buscar dados do termo (datas corretas, portaria, rescisão e total_pago)
            cur.execute("""
                SELECT p.inicio, p.final, p.portaria,
                       tr.data_rescisao, p.total_pago
                FROM Parcerias p
                LEFT JOIN public.termos_rescisao tr ON p.numero_termo = tr.numero_termo
                WHERE p.numero_termo = %s
            """, (numero_termo,))
            termo = cur.fetchone()
            
            if not termo:
                return jsonify({'erro': 'Termo não encontrado'}), 404
            
            data_inicio = termo['inicio']
            data_termino_original = termo['final']
            data_rescisao = termo.get('data_rescisao')
            portaria = termo['portaria']
            total_pago = termo.get('total_pago') or 0
            
            # Se foi rescindido, validar execução
            if data_rescisao:
                dias_execucao = (data_rescisao - data_inicio).days
                
                # Validação 1: Rescindido em até 5 dias (execução mínima)
                if dias_execucao <= 5:
                    return jsonify({
                        'erro': f'Termo foi rescindido em {data_rescisao.strftime("%d/%m/%Y")}, apenas {dias_execucao} dia(s) após o início. Não há prestações de contas (execução mínima não atingida).',
                        'data_rescisao': data_rescisao.strftime('%d/%m/%Y'),
                        'dias_execucao': dias_execucao
                    }), 400
                
                # Validação 2: Rescindido com total_pago = 0 (não recebeu recursos)
                # Neste caso, DELETAR todas as prestações existentes
                if total_pago == 0:
                    # Contar prestações antes de deletar para informar ao usuário
                    cur.execute("""
                        SELECT COUNT(*) as total,
                               COUNT(CASE WHEN entregue = true THEN 1 END) as entregues
                        FROM parcerias_analises
                        WHERE numero_termo = %s
                    """, (numero_termo,))
                    
                    contagem = cur.fetchone()
                    total_prestacoes = contagem['total'] if contagem else 0
                    prestacoes_entregues = contagem['entregues'] if contagem else 0
                    
                    # Deletar todas as prestações
                    cur.execute("DELETE FROM parcerias_analises WHERE numero_termo = %s", (numero_termo,))
                    get_db().commit()
                    cur.close()
                    
                    mensagem = f'Termo {numero_termo} rescindido sem recursos (R$ 0,00). '
                    mensagem += f'{total_prestacoes} prestação(ões) removida(s)'
                    if prestacoes_entregues > 0:
                        mensagem += f' (incluindo {prestacoes_entregues} marcada(s) como entregue)'
                    mensagem += f'. Vigência: {dias_execucao} dia(s).'
                    
                    return jsonify({
                        'mensagem': mensagem,
                        'prestacoes_removidas': total_prestacoes,
                        'prestacoes_entregues': prestacoes_entregues,
                        'sem_recursos': True
                    }), 200
            
            # Usar data de rescisão como término se existir
            data_termino = data_rescisao if data_rescisao else data_termino_original
            
            # Recalcular todas as prestações baseado na portaria e novas datas
            prestacoes_novas = gerar_prestacoes(numero_termo, data_inicio, data_termino, portaria)
            
            # Buscar prestações antigas para preservar dados preenchidos
            cur.execute("""
                SELECT id, tipo_prestacao, numero_prestacao, 
                       entregue, cobrado, e_notificacao, e_parecer,
                       e_fase_recursal, e_encerramento, data_parecer_dp,
                       valor_devolucao, valor_devolvido, responsavel_dp,
                       data_parecer_pg, responsavel_pg, observacoes,
                       vigencia_final
                FROM parcerias_analises
                WHERE numero_termo = %s
                ORDER BY tipo_prestacao, numero_prestacao
            """, (numero_termo,))
            prestacoes_antigas = cur.fetchall()
            
            # Criar mapa das prestações antigas (chave: tipo+numero)
            mapa_antigas = {}
            prestacoes_deletadas = []
            
            for p in prestacoes_antigas:
                chave = f"{p['tipo_prestacao']}_{p['numero_prestacao']}"
                mapa_antigas[chave] = p
                
                # Se foi rescindido e a prestação tinha vigência_final posterior à rescisão
                if data_rescisao and p['vigencia_final'] and p['vigencia_final'] > data_rescisao:
                    # Marcar para logging
                    obs_antiga = f"(vigência até {p['vigencia_final'].strftime('%d/%m/%Y')}"
                    if p['entregue']:
                        obs_antiga += ", estava marcada como entregue"
                    obs_antiga += ")"
                    prestacoes_deletadas.append(f"{p['tipo_prestacao']} {p['numero_prestacao']} {obs_antiga}")
            
            # Deletar todas as prestações antigas
            cur.execute("DELETE FROM parcerias_analises WHERE numero_termo = %s", (numero_termo,))
            
            # Inserir prestações novas, preservando dados se existiam antes
            for prestacao_nova in prestacoes_novas:
                chave = f"{prestacao_nova['tipo_prestacao']}_{prestacao_nova['numero_prestacao']}"
                antiga = mapa_antigas.get(chave)
                
                # Determinar responsabilidade baseada na vigência final de CADA prestação
                vigencia_final = prestacao_nova['vigencia_final']
                responsabilidade_auto = determinar_responsabilidade_por_vigencia(portaria, vigencia_final)
                
                # Se existia prestação com mesmo tipo+número, preservar dados
                if antiga:
                    query = """
                        INSERT INTO parcerias_analises (
                            numero_termo, tipo_prestacao, numero_prestacao,
                            vigencia_inicial, vigencia_final,
                            responsabilidade_analise,
                            entregue, cobrado, e_notificacao, e_parecer,
                            e_fase_recursal, e_encerramento, data_parecer_dp,
                            valor_devolucao, valor_devolvido, responsavel_dp,
                            data_parecer_pg, responsavel_pg, observacoes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    params = (
                        numero_termo,
                        prestacao_nova['tipo_prestacao'],
                        prestacao_nova['numero_prestacao'],
                        prestacao_nova['vigencia_inicial'],
                        prestacao_nova['vigencia_final'],
                        antiga.get('responsabilidade_analise') or responsabilidade_auto,  # ← Preservar se existe, senão usar auto
                        antiga['entregue'],
                        antiga['cobrado'],
                        antiga['e_notificacao'],
                        antiga['e_parecer'],
                        antiga['e_fase_recursal'],
                        antiga['e_encerramento'],
                        antiga['data_parecer_dp'],
                        antiga['valor_devolucao'],
                        antiga['valor_devolvido'],
                        antiga['responsavel_dp'],
                        antiga['data_parecer_pg'],
                        antiga['responsavel_pg'],
                        antiga['observacoes']
                    )
                else:
                    # Prestação nova (não existia antes), inserir vazia com responsabilidade automática
                    query = """
                        INSERT INTO parcerias_analises (
                            numero_termo, tipo_prestacao, numero_prestacao,
                            vigencia_inicial, vigencia_final,
                            responsabilidade_analise,
                            entregue, cobrado, e_notificacao, e_parecer,
                            e_fase_recursal, e_encerramento
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    params = (
                        numero_termo,
                        prestacao_nova['tipo_prestacao'],
                        prestacao_nova['numero_prestacao'],
                        prestacao_nova['vigencia_inicial'],
                        prestacao_nova['vigencia_final'],
                        responsabilidade_auto,  # ← RESPONSABILIDADE AUTOMÁTICA
                        False, False, False, False, False, False
                    )
                
                cur.execute(query, params)
            
            get_db().commit()
            cur.close()
            
            # Montar mensagem de sucesso
            mensagem = f'Prestações recalculadas com sucesso! Total: {len(prestacoes_novas)}'
            
            if data_rescisao:
                mensagem += f'\n⚠️ Termo rescindido em {data_rescisao.strftime("%d/%m/%Y")}.'
                
            if prestacoes_deletadas:
                mensagem += f'\n📋 Prestações removidas (vigência posterior à rescisão): {", ".join(prestacoes_deletadas)}'
            
            return jsonify({'mensagem': mensagem}), 200
            
        except Exception as e:
            print(f"[ERRO] Erro ao atualizar prestações: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'erro': str(e)}), 500
    
    # GET - Buscar termos com divergências
    cur = get_cursor()
    
    # Verificar se deve usar comparação exata (parâmetro da URL)
    modo_exato = request.args.get('exato', '0') == '1'
    
    # Buscar TODOS os termos que têm prestações cadastradas
    # Incluir informação sobre rescisão e total_pago
    # NÃO FILTRAR termos com total_pago = 0, pois precisam aparecer para validação humana
    query_termos = """
        SELECT DISTINCT 
            p.numero_termo,
            p.sei_celeb,
            p.inicio,
            p.final,
            p.portaria,
            tr.data_rescisao,
            p.total_pago,
            CASE 
                WHEN tr.data_rescisao IS NOT NULL THEN tr.data_rescisao
                ELSE p.final
            END as vigencia_efetiva
        FROM Parcerias p
        INNER JOIN parcerias_analises pa ON p.numero_termo = pa.numero_termo
        LEFT JOIN public.termos_rescisao tr ON p.numero_termo = tr.numero_termo
        WHERE p.inicio IS NOT NULL 
        AND p.final IS NOT NULL
        ORDER BY p.numero_termo DESC
    """
    
    cur.execute(query_termos)
    termos = cur.fetchall()
    
    termos_divergentes = {}
    
    for termo in termos:
        numero_termo = termo['numero_termo']
        data_inicio = termo['inicio']
        data_termino_original = termo['final']
        data_rescisao = termo.get('data_rescisao')
        portaria = termo['portaria']
        
        # Usar data de rescisão como término se existir
        data_termino = data_rescisao if data_rescisao else data_termino_original
        
        # Buscar APENAS a prestação Final cadastrada
        cur.execute("""
            SELECT id, tipo_prestacao, numero_prestacao, 
                   vigencia_inicial, vigencia_final
            FROM parcerias_analises
            WHERE numero_termo = %s
            AND tipo_prestacao = 'Final'
            LIMIT 1
        """, (numero_termo,))
        prestacao_final_cadastrada = cur.fetchone()
        
        # Se não existe Final cadastrada, tem divergência
        if not prestacao_final_cadastrada:
            tem_divergencia = True
        else:
            # Comparar mês/ano da Final com o termo
            if modo_exato:
                # Modo exato: compara dia/mês/ano
                inicial_bate = (prestacao_final_cadastrada['vigencia_inicial'] == data_inicio)
                final_bate = (prestacao_final_cadastrada['vigencia_final'] == data_termino)
            else:
                # Modo mês/ano: compara apenas mês e ano
                inicial_bate = (
                    prestacao_final_cadastrada['vigencia_inicial'].month == data_inicio.month and
                    prestacao_final_cadastrada['vigencia_inicial'].year == data_inicio.year
                )
                final_bate = (
                    prestacao_final_cadastrada['vigencia_final'].month == data_termino.month and
                    prestacao_final_cadastrada['vigencia_final'].year == data_termino.year
                )
            
            # Se a Final não bate com o termo, tem divergência
            tem_divergencia = not (inicial_bate and final_bate)
        
        # Se tem divergência, calcular todas as prestações corretas e cadastradas para mostrar no front
        if tem_divergencia:
            # Calcular prestações corretas baseado na portaria
            prestacoes_corretas = gerar_prestacoes(numero_termo, data_inicio, data_termino, portaria)
            
            # Ordenar prestações corretas
            ordem_tipo = {'Trimestral': 1, 'Semestral': 2, 'Final': 3}
            prestacoes_corretas_ordenadas = sorted(
                prestacoes_corretas, 
                key=lambda x: (ordem_tipo.get(x['tipo_prestacao'], 4), x['numero_prestacao'])
            )
            
            # Buscar TODAS as prestações cadastradas
            cur.execute("""
                SELECT id, tipo_prestacao, numero_prestacao, 
                       vigencia_inicial, vigencia_final
                FROM parcerias_analises
                WHERE numero_termo = %s
                ORDER BY 
                    CASE 
                        WHEN tipo_prestacao = 'Trimestral' THEN 1
                        WHEN tipo_prestacao = 'Semestral' THEN 2
                        WHEN tipo_prestacao = 'Final' THEN 3
                        ELSE 4
                    END,
                    numero_prestacao
            """, (numero_termo,))
            prestacoes_cadastradas = cur.fetchall()
            
            # Adicionar à lista de divergentes
            termos_divergentes[numero_termo] = {
                'numero_termo': numero_termo,
                'sei_celeb': termo['sei_celeb'],
                'data_inicio_termo': data_inicio,
                'data_final_termo': data_termino,
                'data_final_original': data_termino_original,  # Data original da tabela parcerias
                'data_rescisao': data_rescisao,  # Data de rescisão se houver
                'rescindido': data_rescisao is not None,  # Boolean para template
                'total_pago': termo.get('total_pago') or 0,  # Total pago (recursos repassados)
                'portaria': portaria,
                'prestacoes_cadastradas': [
                    {
                        'id': p['id'],
                        'tipo_prestacao': p['tipo_prestacao'],
                        'numero_prestacao': p['numero_prestacao'],
                        'vigencia_inicial': p['vigencia_inicial'],
                        'vigencia_final': p['vigencia_final']
                    } for p in prestacoes_cadastradas
                ],
                'prestacoes_corretas': prestacoes_corretas_ordenadas
            }
    
    cur.close()
    
    return render_template('atualizar_prestacoes.html', 
                         termos_divergentes=list(termos_divergentes.values()))


@analises_bp.route('/api/limpar-prestacoes-sem-recursos', methods=['POST'])
@login_required
@requires_access('analises')
def limpar_prestacoes_sem_recursos():
    """
    API para limpar prestações de termos rescindidos que não receberam recursos (total_pago = 0).
    Esta rota deve ser chamada para fazer manutenção na base de dados.
    
    Retorna:
    - Lista de termos que tiveram prestações removidas
    - Quantidade de prestações removidas por termo
    """
    from db import get_db
    
    try:
        cur = get_cursor()
        
        # Buscar termos rescindidos com total_pago = 0 que têm prestações cadastradas
        query = """
            SELECT DISTINCT 
                p.numero_termo,
                p.inicio,
                tr.data_rescisao,
                p.total_pago,
                (tr.data_rescisao - p.inicio) as dias_vigencia
            FROM Parcerias p
            INNER JOIN public.termos_rescisao tr ON p.numero_termo = tr.numero_termo
            INNER JOIN parcerias_analises pa ON p.numero_termo = pa.numero_termo
            WHERE COALESCE(p.total_pago, 0) = 0
            ORDER BY p.numero_termo
        """
        
        cur.execute(query)
        termos_invalidos = cur.fetchall()
        
        if not termos_invalidos:
            cur.close()
            return jsonify({
                'mensagem': 'Nenhum termo rescindido sem recursos foi encontrado com prestações cadastradas.',
                'termos_removidos': []
            }), 200
        
        termos_removidos = []
        
        for termo in termos_invalidos:
            numero_termo = termo['numero_termo']
            data_rescisao = termo['data_rescisao']
            dias_vigencia = termo['dias_vigencia'].days if termo['dias_vigencia'] else 0
            
            # Contar prestações antes de deletar
            cur.execute("""
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN entregue = true THEN 1 END) as entregues
                FROM parcerias_analises
                WHERE numero_termo = %s
            """, (numero_termo,))
            
            contagem = cur.fetchone()
            total_prestacoes = contagem['total']
            prestacoes_entregues = contagem['entregues']
            
            # Deletar todas as prestações deste termo
            cur.execute("DELETE FROM parcerias_analises WHERE numero_termo = %s", (numero_termo,))
            
            termos_removidos.append({
                'numero_termo': numero_termo,
                'data_rescisao': data_rescisao.strftime('%d/%m/%Y'),
                'dias_vigencia': dias_vigencia,
                'prestacoes_removidas': total_prestacoes,
                'prestacoes_entregues': prestacoes_entregues,
                'motivo': 'Termo rescindido sem recursos (total_pago = R$ 0,00)'
            })
        
        get_db().commit()
        cur.close()
        
        return jsonify({
            'mensagem': f'{len(termos_removidos)} termo(s) tiveram suas prestações removidas por não terem recebido recursos.',
            'termos_removidos': termos_removidos
        }), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao limpar prestações sem recursos: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500
