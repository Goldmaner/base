"""
Rotas para Ofícios, Documentos e Notificações de Parcerias
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor, get_db, execute_query
from functools import wraps
from decorators import requires_access
from datetime import timedelta, date, datetime

bp = Blueprint('parcerias_notificacoes', __name__, url_prefix='/parcerias_notificacoes')


def login_required(f):
    """Decorator para exigir login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Não autenticado'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
@requires_access('parcerias_notificacoes')
def listar():
    """Página principal de listagem de notificações"""
    user = {
        'id': session.get('user_id'),
        'email': session.get('email'),
        'tipo_usuario': session.get('tipo_usuario')
    }
    return render_template('parcerias_notificacoes.html', user=user)


@bp.route('/api/notificacoes', methods=['GET'])
@login_required
@requires_access('parcerias_notificacoes')
def api_listar_notificacoes():
    """
    API para listar notificações com filtros
    Query params: tipo_doc, ano_doc, numero_doc, numero_termo, nome_responsavel, limite
    """
    try:
        cur = get_cursor()
        
        # Parâmetros de filtro
        filtro_tipo = request.args.get('tipo_doc', '').strip()
        filtro_ano = request.args.get('ano_doc', '').strip()
        filtro_numero = request.args.get('numero_doc', '').strip()
        filtro_termo = request.args.get('numero_termo', '').strip()
        filtro_responsavel = request.args.get('nome_responsavel', '').strip()
        filtro_status = request.args.get('status', '').strip()
        filtro_doc_respondido = request.args.get('doc_respondido', '').strip()
        limite = request.args.get('limite', '100').strip()
        
        # Query base com JOIN para pegar OSC, sei_pc e calcular prazo
        query = """
            SELECT 
                pn.id,
                pn.tipo_doc,
                pn.ano_doc,
                pn.numero_doc,
                pn.numero_termo,
                pn.processo_doc,
                p.sei_pc,
                p.osc,
                p.portaria,
                pn.nome_responsavel,
                pn.data_doc,
                pn.data_pub,
                pn.data_email_ar,
                pn.sei_doc,
                pn.observacoes,
                pn.dilacao,
                pn.dilacao_dias,
                pn.doc_respondido,
                cdp.prazo_dias
            FROM parcerias_notificacoes pn
            LEFT JOIN parcerias p ON pn.numero_termo = p.numero_termo
            LEFT JOIN categoricas.c_documentos_dp_prazos cdp 
                ON pn.tipo_doc = cdp.tipo_documento 
                AND p.portaria = cdp.lei
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if filtro_tipo:
            query += " AND LOWER(pn.tipo_doc) LIKE LOWER(%s)"
            params.append(f'%{filtro_tipo}%')
        
        if filtro_ano:
            query += " AND pn.ano_doc = %s"
            params.append(int(filtro_ano))
        
        if filtro_numero:
            query += " AND pn.numero_doc = %s"
            params.append(int(filtro_numero))
        
        if filtro_termo:
            query += " AND LOWER(pn.numero_termo) LIKE LOWER(%s)"
            params.append(f'%{filtro_termo}%')
        
        if filtro_responsavel:
            query += " AND LOWER(pn.nome_responsavel) LIKE LOWER(%s)"
            params.append(f'%{filtro_responsavel}%')
        
        # Ordenar pelos mais recentes
        query += " ORDER BY pn.id DESC"
        
        # Adicionar limite se não for "todas"
        if limite.lower() != 'todas':
            try:
                limite_num = int(limite)
                query += f" LIMIT {limite_num}"
            except ValueError:
                query += " LIMIT 100"
        
        cur.execute(query, params)
        notificacoes = cur.fetchall()
        
        # Processar dados para incluir processo_doc (processo_doc ou sei_pc) e calcular prazo
        resultado = []
        for notif in notificacoes:
            item = dict(notif)
            # Se processo_doc for NULL, usar sei_pc da parceria
            item['processo_final'] = item['processo_doc'] if item['processo_doc'] else item.get('sei_pc')
            
            # Calcular prazo e status
            prazo_calculado = None
            prazo_dias_valor = item.get('prazo_dias')
            status_prazo = 'Não aplicável'  # Default para documentos sem prazo definido
            
            if prazo_dias_valor:
                # Usar data_pub como prioridade, senão data_email_ar
                data_base = item.get('data_pub') or item.get('data_email_ar')
                
                if data_base:
                    # Converter datetime para date se necessário
                    if isinstance(data_base, datetime):
                        data_base = data_base.date()
                    
                    data_prazo = data_base + timedelta(days=prazo_dias_valor)
                    item['prazo_final'] = data_prazo.strftime('%d/%m/%Y')
                    item['prazo_info'] = f"{data_prazo.strftime('%d/%m/%Y')} ({prazo_dias_valor} dias)"
                    
                    # Calcular status (comparar com data de hoje)
                    hoje = date.today()
                    if data_prazo < hoje:
                        status_prazo = 'Atrasado'
                    else:
                        status_prazo = 'No prazo'
                else:
                    item['prazo_final'] = '-'
                    item['prazo_info'] = '-'
            else:
                item['prazo_final'] = '-'
                item['prazo_info'] = '-'
            
            item['status_prazo'] = status_prazo
            
            # Documento respondido (só mostra se tem prazo definido)
            if prazo_dias_valor:
                item['doc_respondido_texto'] = 'Sim' if item.get('doc_respondido') else 'Não'
            else:
                item['doc_respondido_texto'] = '-'
            
            # Converter datas para string ISO para JSON
            if item.get('data_doc'):
                item['data_doc'] = item['data_doc'].isoformat()
            if item.get('data_pub'):
                item['data_pub'] = item['data_pub'].isoformat()
            if item.get('data_email_ar'):
                item['data_email_ar'] = item['data_email_ar'].isoformat()
            
            # Aplicar filtros de status e doc_respondido (após cálculo)
            if filtro_status and item['status_prazo'] != filtro_status:
                continue
            if filtro_doc_respondido and item['doc_respondido_texto'] != filtro_doc_respondido:
                continue
            
            resultado.append(item)
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar notificações: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/notificacoes/<int:notif_id>', methods=['GET'])
@login_required
@requires_access('parcerias_notificacoes')
def api_obter_notificacao(notif_id):
    """API para obter uma notificação específica"""
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT 
                pn.*,
                p.osc,
                p.sei_pc
            FROM parcerias_notificacoes pn
            LEFT JOIN parcerias p ON pn.numero_termo = p.numero_termo
            WHERE pn.id = %s
        """, (notif_id,))
        
        notificacao = cur.fetchone()
        
        if not notificacao:
            return jsonify({'erro': 'Notificação não encontrada'}), 404
        
        # Converter para dict e processar datas
        item = dict(notificacao)
        
        # Converter datas para string ISO para JSON
        if item.get('data_doc'):
            item['data_doc'] = item['data_doc'].isoformat()
        if item.get('data_pub'):
            item['data_pub'] = item['data_pub'].isoformat()
        if item.get('data_email_ar'):
            item['data_email_ar'] = item['data_email_ar'].isoformat()
        
        return jsonify(item), 200
        
    except Exception as e:
        print(f"[ERRO] ao obter notificação {notif_id}: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/notificacoes', methods=['POST'])
@login_required
@requires_access('parcerias_notificacoes')
def api_criar_notificacao():
    """API para criar uma nova notificação"""
    try:
        dados = request.get_json()
        
        # Validações básicas
        if not dados.get('tipo_doc'):
            return jsonify({'erro': 'Tipo de documento é obrigatório'}), 400
        if not dados.get('ano_doc'):
            return jsonify({'erro': 'Ano do documento é obrigatório'}), 400
        if not dados.get('numero_doc'):
            return jsonify({'erro': 'Número do documento é obrigatório'}), 400
        
        cur = get_cursor()
        db = get_db()
        
        # Inserir notificação
        cur.execute("""
            INSERT INTO parcerias_notificacoes (
                tipo_doc, ano_doc, numero_doc, numero_termo, nome_responsavel,
                data_doc, data_pub, data_email_ar, processo_doc, sei_doc,
                observacoes, dilacao, dilacao_dias, doc_respondido
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
        """, (
            dados.get('tipo_doc'),
            dados.get('ano_doc'),
            dados.get('numero_doc'),
            dados.get('numero_termo') or None,
            dados.get('nome_responsavel') or None,
            dados.get('data_doc') or None,
            dados.get('data_pub') or None,
            dados.get('data_email_ar') or None,
            dados.get('processo_doc') or None,
            dados.get('sei_doc') or None,
            dados.get('observacoes') or None,
            dados.get('dilacao', False),
            dados.get('dilacao_dias', 0),
            dados.get('doc_respondido', False)
        ))
        
        novo_id = cur.fetchone()['id']
        db.commit()
        
        return jsonify({'id': novo_id, 'mensagem': 'Notificação criada com sucesso'}), 201
        
    except Exception as e:
        print(f"[ERRO] ao criar notificação: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/notificacoes/<int:notif_id>', methods=['PUT'])
@login_required
@requires_access('parcerias_notificacoes')
def api_editar_notificacao(notif_id):
    """API para editar uma notificação existente"""
    try:
        dados = request.get_json()
        
        cur = get_cursor()
        db = get_db()
        
        # Atualizar notificação
        cur.execute("""
            UPDATE parcerias_notificacoes
            SET 
                tipo_doc = %s,
                ano_doc = %s,
                numero_doc = %s,
                numero_termo = %s,
                nome_responsavel = %s,
                data_doc = %s,
                data_pub = %s,
                data_email_ar = %s,
                processo_doc = %s,
                sei_doc = %s,
                observacoes = %s,
                dilacao = %s,
                dilacao_dias = %s,
                doc_respondido = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (
            dados.get('tipo_doc'),
            dados.get('ano_doc'),
            dados.get('numero_doc'),
            dados.get('numero_termo') or None,
            dados.get('nome_responsavel') or None,
            dados.get('data_doc') or None,
            dados.get('data_pub') or None,
            dados.get('data_email_ar') or None,
            dados.get('processo_doc') or None,
            dados.get('sei_doc') or None,
            dados.get('observacoes') or None,
            dados.get('dilacao', False),
            dados.get('dilacao_dias', 0),
            dados.get('doc_respondido', False),
            notif_id
        ))
        
        db.commit()
        
        return jsonify({'mensagem': 'Notificação atualizada com sucesso'}), 200
        
    except Exception as e:
        print(f"[ERRO] ao editar notificação {notif_id}: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/notificacoes/<int:notif_id>', methods=['DELETE'])
@login_required
@requires_access('parcerias_notificacoes')
def api_excluir_notificacao(notif_id):
    """API para excluir uma notificação"""
    try:
        cur = get_cursor()
        db = get_db()
        
        # Verificar se existe
        cur.execute("SELECT id FROM parcerias_notificacoes WHERE id = %s", (notif_id,))
        if not cur.fetchone():
            return jsonify({'erro': 'Notificação não encontrada'}), 404
        
        # Excluir
        cur.execute("DELETE FROM parcerias_notificacoes WHERE id = %s", (notif_id,))
        db.commit()
        
        return jsonify({'mensagem': 'Notificação excluída com sucesso'}), 200
        
    except Exception as e:
        print(f"[ERRO] ao excluir notificação {notif_id}: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/tipos-documento', methods=['GET'])
@login_required
@requires_access('parcerias_notificacoes')
def api_listar_tipos_documento():
    """
    API para listar tipos de documento filtrados por órgão emissor
    conforme o tipo de usuário
    """
    try:
        user_tipo = session.get('tipo_usuario')
        print(f"[DEBUG] Tipo de usuário: {user_tipo}")
        
        cur = get_cursor()
        
        # Definir filtro baseado no tipo de usuário
        if user_tipo in ['Agente Público', 'Agente DP']:
            # Mostrar todos os tipos
            cur.execute("""
                SELECT DISTINCT tipo_documento, orgao_emissor
                FROM categoricas.c_dp_documentos
                WHERE tipo_documento IS NOT NULL
                ORDER BY tipo_documento
            """)
        elif user_tipo == 'Agente DAC':
            # Apenas documentos da Divisão de Análise de Contas
            cur.execute("""
                SELECT DISTINCT tipo_documento, orgao_emissor
                FROM categoricas.c_dp_documentos
                WHERE orgao_emissor = 'Divisão de Análise de Contas'
                  AND tipo_documento IS NOT NULL
                ORDER BY tipo_documento
            """)
        elif user_tipo == 'Agente DGP':
            # Apenas documentos da Divisão de Gestão de Parcerias
            cur.execute("""
                SELECT DISTINCT tipo_documento, orgao_emissor
                FROM categoricas.c_dp_documentos
                WHERE orgao_emissor = 'Divisão de Gestão de Parcerias'
                  AND tipo_documento IS NOT NULL
                ORDER BY tipo_documento
            """)
        else:
            # Sem permissão
            print(f"[DEBUG] Usuário sem permissão: {user_tipo}")
            return jsonify([]), 200
        
        tipos = cur.fetchall()
        print(f"[DEBUG] Tipos de documento encontrados: {len(tipos)}")
        
        return jsonify([dict(t) for t in tipos]), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar tipos de documento: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/analistas', methods=['GET'])
@login_required
@requires_access('parcerias_notificacoes')
def api_listar_analistas():
    """
    API para listar analistas filtrados por tipo de usuário
    """
    try:
        user_tipo = session.get('tipo_usuario')
        print(f"[DEBUG] Carregando analistas para tipo de usuário: {user_tipo}")
        
        cur = get_cursor()
        analistas = []
        
        # Definir filtro baseado no tipo de usuário
        if user_tipo in ['Agente Público', 'Agente DP']:
            # Buscar de ambas as tabelas
            cur.execute("""
                SELECT DISTINCT nome_analista
                FROM categoricas.c_dac_analistas
                WHERE nome_analista IS NOT NULL AND nome_analista != ''
                UNION
                SELECT DISTINCT nome_analista
                FROM categoricas.c_dgp_analistas
                WHERE nome_analista IS NOT NULL AND nome_analista != ''
                ORDER BY nome_analista
            """)
            analistas = cur.fetchall()
            
        elif user_tipo == 'Agente DAC':
            # Apenas analistas DAC
            cur.execute("""
                SELECT DISTINCT nome_analista
                FROM categoricas.c_dac_analistas
                WHERE nome_analista IS NOT NULL AND nome_analista != ''
                ORDER BY nome_analista
            """)
            analistas = cur.fetchall()
            
        elif user_tipo == 'Agente DGP':
            # Apenas analistas DGP
            cur.execute("""
                SELECT DISTINCT nome_analista
                FROM categoricas.c_dgp_analistas
                WHERE nome_analista IS NOT NULL AND nome_analista != ''
                ORDER BY nome_analista
            """)
            analistas = cur.fetchall()
        
        # Externos não veem nada (lista vazia)
        
        print(f"[DEBUG] Analistas encontrados: {len(analistas)}")
        
        return jsonify([a['nome_analista'] for a in analistas]), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar analistas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/numeros-termo', methods=['GET'])
@login_required
@requires_access('parcerias_notificacoes')
def api_numeros_termo():
    """
    API unificada para buscar números de termo com autocomplete
    Query params: q (query de busca opcional)
    
    - Com parâmetro 'q': retorna termos filtrados (autocomplete)
    - Sem parâmetro 'q': retorna todos os termos (inicialização)
    """
    try:
        query_busca = request.args.get('q', '').strip()
        
        cur = get_cursor()
        
        if query_busca:
            # Buscar termos que contenham a string (case-insensitive) - AUTOCOMPLETE
            print(f"[DEBUG] Buscando termos com filtro: '{query_busca}'")
            cur.execute("""
                SELECT DISTINCT numero_termo
                FROM public.parcerias
                WHERE LOWER(numero_termo) LIKE LOWER(%s)
                ORDER BY numero_termo DESC
                LIMIT 20
            """, (f'%{query_busca}%',))
            
            termos = [row['numero_termo'] for row in cur.fetchall()]
            print(f"[DEBUG] Encontrados {len(termos)} termos com filtro")
            
            # Retornar no formato esperado pelo frontend (com chave 'termos')
            return jsonify({'termos': termos}), 200
        else:
            # Retornar todos os termos (limitado a 100 para performance) - INICIALIZAÇÃO
            print(f"[DEBUG] Carregando todos os termos (limite 100)")
            cur.execute("""
                SELECT DISTINCT numero_termo
                FROM public.parcerias
                WHERE numero_termo IS NOT NULL AND numero_termo != ''
                ORDER BY numero_termo DESC
                LIMIT 100
            """)
            
            termos = [row['numero_termo'] for row in cur.fetchall()]
            print(f"[DEBUG] Carregados {len(termos)} termos iniciais")
            
            # Retornar como array simples (compatibilidade com código antigo)
            return jsonify(termos), 200
        
    except Exception as e:
        print(f"[ERRO] ao buscar números de termo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/proximo-numero', methods=['GET'])
@login_required
@requires_access('parcerias_notificacoes')
def api_proximo_numero():
    """
    API para obter o próximo número de documento para um tipo e ano específico
    """
    try:
        tipo_doc = request.args.get('tipo_doc')
        ano_doc = request.args.get('ano_doc')
        
        if not tipo_doc or not ano_doc:
            return jsonify({'proximo_numero': 1}), 200
        
        cur = get_cursor()
        
        cur.execute("""
            SELECT MAX(numero_doc) as max_numero
            FROM parcerias_notificacoes
            WHERE tipo_doc = %s AND ano_doc = %s
        """, (tipo_doc, int(ano_doc)))
        
        resultado = cur.fetchone()
        max_numero = resultado['max_numero'] if resultado and resultado['max_numero'] else 0
        
        return jsonify({'proximo_numero': max_numero + 1}), 200
        
    except Exception as e:
        print(f"[ERRO] ao calcular próximo número: {e}")
        return jsonify({'erro': str(e)}), 500





@bp.route('/api/calcular-prazo', methods=['GET'])
@login_required
@requires_access('parcerias_notificacoes')
def api_calcular_prazo():
    """
    API para calcular prazo baseado em tipo_doc, numero_termo e data
    Query params: tipo_doc, numero_termo, data_pub, data_email_ar
    """
    try:
        tipo_doc = request.args.get('tipo_doc')
        numero_termo = request.args.get('numero_termo')
        data_pub = request.args.get('data_pub')
        data_email_ar = request.args.get('data_email_ar')
        
        if not tipo_doc or not numero_termo:
            return jsonify({'prazo_info': '-', 'prazo_dias': None}), 200
        
        # Determinar data base (prioridade: data_pub, senão data_email_ar)
        data_base_str = data_pub or data_email_ar
        if not data_base_str:
            return jsonify({'prazo_info': '-', 'prazo_dias': None}), 200
        
        cur = get_cursor()
        
        # Buscar prazo_dias baseado em tipo_doc e portaria do termo
        cur.execute("""
            SELECT cdp.prazo_dias
            FROM categoricas.c_documentos_dp_prazos cdp
            INNER JOIN parcerias p ON cdp.lei = p.portaria
            WHERE cdp.tipo_documento = %s 
            AND p.numero_termo = %s
            LIMIT 1
        """, (tipo_doc, numero_termo))
        
        resultado = cur.fetchone()
        
        if not resultado or not resultado['prazo_dias']:
            return jsonify({'prazo_info': '-', 'prazo_dias': None}), 200
        
        prazo_dias = resultado['prazo_dias']
        
        # Calcular data final
        # Converter string de data para datetime
        if 'T' in data_base_str:
            data_base = datetime.fromisoformat(data_base_str.replace('Z', '+00:00'))
        else:
            data_base = datetime.strptime(data_base_str, '%Y-%m-%d')
        
        data_prazo = data_base + timedelta(days=prazo_dias)
        prazo_final = data_prazo.strftime('%d/%m/%Y')
        prazo_info = f"{prazo_final} ({prazo_dias} dias)"
        
        return jsonify({
            'prazo_info': prazo_info,
            'prazo_final': prazo_final,
            'prazo_dias': prazo_dias
        }), 200
        
    except Exception as e:
        print(f"[ERRO] ao calcular prazo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e), 'prazo_info': '-'}), 500
