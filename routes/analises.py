"""
Blueprint de gerenciamento de análises de prestação de contas
"""

from flask import Blueprint, render_template, request, jsonify, make_response
from db import get_cursor, execute_query
from utils import login_required
from datetime import datetime, timedelta
import io


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


analises_bp = Blueprint('analises', __name__, url_prefix='/analises')


@analises_bp.route("/api/anos-disponiveis", methods=["GET"])
@login_required
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


@analises_bp.route("/", methods=["GET"])
@login_required
def listar():
    """
    Página principal de análises
    """
    return render_template('analises.html')


@analises_bp.route("/api/dados", methods=["GET"])
@login_required
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
