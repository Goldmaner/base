"""
Rotas para Conciliação Bancária - Análise de Prestação de Contas
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor, get_db
from functools import wraps
from datetime import datetime, date
from decorators import requires_access

bp = Blueprint('conc_bancaria', __name__, url_prefix='/conc_bancaria')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Sessão expirada'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
@requires_access('conc_bancaria')
def index():
    """Página principal de conciliação bancária"""
    return render_template('analises_pc/conc_bancaria.html')


@bp.route('/api/extrato', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_listar_extrato():
    """
    API para listar movimentações do extrato
    Query params: numero_termo, limite
    """
    try:
        import time
        inicio = time.time()
        
        cur = get_cursor()
        
        numero_termo = request.args.get('numero_termo', '').strip()
        limite = request.args.get('limite', '100').strip()
        
        query = """
            SELECT 
                id,
                indice,
                data,
                credito,
                debito,
                discriminacao,
                cat_transacao,
                competencia,
                origem_destino,
                cat_avaliacao,
                avaliacao_analista,
                mesclado_com,
                numero_termo
            FROM analises_pc.conc_extrato
            WHERE 1=1
        """
        
        params = []
        
        if numero_termo:
            query += " AND numero_termo = %s"
            params.append(numero_termo)
        
        # Ordenar por índice
        query += " ORDER BY indice ASC, id ASC"
        
        # Adicionar limite
        if limite.lower() != 'todas':
            try:
                limite_num = int(limite)
                query += f" LIMIT {limite_num}"
            except ValueError:
                query += " LIMIT 100"
        
        tempo_query = time.time()
        cur.execute(query, params)
        tempo_execute = (time.time() - tempo_query) * 1000
        
        tempo_fetch = time.time()
        extrato = cur.fetchall()
        tempo_fetchall = (time.time() - tempo_fetch) * 1000
        
        # Processar dados
        tempo_process = time.time()
        resultado = []
        for item in extrato:
            row = dict(item)
            
            # Converter datas para string ISO
            if row.get('data'):
                row['data'] = row['data'].isoformat()
            if row.get('competencia'):
                row['competencia'] = row['competencia'].isoformat()
            
            # Converter valores numéricos para float
            if row.get('credito'):
                row['credito'] = float(row['credito'])
            if row.get('debito'):
                row['debito'] = float(row['debito'])
            if row.get('discriminacao'):
                row['discriminacao'] = float(row['discriminacao'])
            
            # Converter mesclado_com (array PostgreSQL para lista Python)
            if row.get('mesclado_com'):
                row['mesclado_com'] = list(row['mesclado_com'])
            else:
                row['mesclado_com'] = []
            
            resultado.append(row)
        
        tempo_processing = (time.time() - tempo_process) * 1000
        tempo_total = (time.time() - inicio) * 1000
        print(f"[GET EXTRATO] Total: {tempo_total:.2f}ms | Execute: {tempo_execute:.2f}ms | Fetch: {tempo_fetchall:.2f}ms | Process: {tempo_processing:.2f}ms | Linhas: {len(resultado)}")
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar extrato: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/extrato', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
def api_salvar_extrato():
    """API para salvar múltiplas linhas do extrato de uma vez"""
    try:
        import time
        inicio = time.time()
        
        dados = request.get_json()
        linhas = dados.get('linhas', [])
        numero_termo = dados.get('numero_termo')
        modo_completo = dados.get('modo_completo', False)  # Flag para indicar se está salvando tudo
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400
        
        cur = get_cursor()
        db = get_db()
        
        # Coletar IDs das linhas enviadas
        ids_enviados = [linha.get('id') for linha in linhas if linha.get('id')]
        
        # DELETAR apenas se modo_completo = True (garantia de que temos todas as linhas)
        if modo_completo:
            if ids_enviados:
                placeholders = ','.join(['%s'] * len(ids_enviados))
                cur.execute(f"""
                    DELETE FROM analises_pc.conc_extrato 
                    WHERE numero_termo = %s AND id NOT IN ({placeholders})
                """, [numero_termo] + ids_enviados)
            else:
                # Se não há IDs (todas linhas novas), deletar tudo do termo
                cur.execute("DELETE FROM analises_pc.conc_extrato WHERE numero_termo = %s", (numero_termo,))
        
        # UPSERT: UPDATE se existe, INSERT se não existe
        ids_processados = []
        for linha in linhas:
            # Validar campos obrigatórios
            if not linha.get('indice'):
                continue  # Pular linhas sem índice
            
            # Validar: não pode ter crédito e débito ao mesmo tempo
            credito = linha.get('credito')
            debito = linha.get('debito')
            
            if credito and debito:
                return jsonify({'erro': 'Não é possível ter crédito e débito na mesma linha'}), 400
            
            linha_id = linha.get('id')
            
            if linha_id:
                # UPDATE: linha já existe
                cur.execute("""
                    UPDATE analises_pc.conc_extrato SET
                        indice = %s,
                        data = %s,
                        credito = %s,
                        debito = %s,
                        discriminacao = %s,
                        cat_transacao = %s,
                        competencia = %s,
                        origem_destino = %s,
                        cat_avaliacao = %s,
                        avaliacao_analista = %s,
                        mesclado_com = %s
                    WHERE id = %s AND numero_termo = %s
                    RETURNING id
                """, (
                    linha.get('indice'),
                    linha.get('data') or None,
                    credito or None,
                    debito or None,
                    linha.get('discriminacao') or None,
                    linha.get('cat_transacao') or None,
                    linha.get('competencia') or None,
                    linha.get('origem_destino') or None,
                    linha.get('cat_avaliacao') or None,
                    linha.get('avaliacao_analista') or None,
                    linha.get('mesclado_com') or None,
                    linha_id,
                    numero_termo
                ))
                result = cur.fetchone()
                if result:
                    ids_processados.append(result['id'])
            else:
                # INSERT: nova linha
                cur.execute("""
                    INSERT INTO analises_pc.conc_extrato (
                        indice, data, credito, debito, discriminacao,
                        cat_transacao, competencia, origem_destino,
                        cat_avaliacao, avaliacao_analista, mesclado_com, numero_termo
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id
                """, (
                    linha.get('indice'),
                    linha.get('data') or None,
                    credito or None,
                    debito or None,
                    linha.get('discriminacao') or None,
                    linha.get('cat_transacao') or None,
                    linha.get('competencia') or None,
                    linha.get('origem_destino') or None,
                    linha.get('cat_avaliacao') or None,
                    linha.get('avaliacao_analista') or None,
                    linha.get('mesclado_com') or None,
                    numero_termo
                ))
                novo_id = cur.fetchone()['id']
                ids_processados.append(novo_id)
        
        # ============================================================
        # AUTOMAÇÃO: Destinatário Identificado/Não Identificado
        # ============================================================
        # Buscar portaria e transição do termo
        cur.execute("""
            SELECT portaria, transicao 
            FROM public.parcerias 
            WHERE numero_termo = %s
        """, (numero_termo,))
        termo_info = cur.fetchone()
        
        if termo_info:
            portaria = termo_info['portaria'] or ''
            transicao = termo_info['transicao'] or 0
            
            print(f"[AUTOMAÇÃO] Termo: {numero_termo}, Portaria: {portaria}, Transição: {transicao}")
            
            # Determinar data de corte baseada na portaria
            data_corte = None
            
            # Portarias 021 (2019 ou 2023)
            if 'Portaria nº 021/SMDHC/2019' in portaria or 'Portaria n° 021/SMDHC/2019' in portaria or \
               'Portaria nº 021/SMDHC/2023' in portaria or 'Portaria n° 021/SMDHC/2023' in portaria:
                data_corte = date(2023, 3, 1)  # mar/23
                print(f"[AUTOMAÇÃO] Portaria 021 detectada, corte: mar/23")
            # Portarias 090 (2019 ou 2023)
            elif 'Portaria nº 090/SMDHC/2019' in portaria or 'Portaria n° 090/SMDHC/2019' in portaria or \
                 'Portaria nº 090/SMDHC/2023' in portaria or 'Portaria n° 090/SMDHC/2023' in portaria:
                data_corte = date(2024, 1, 1)  # jan/24
                print(f"[AUTOMAÇÃO] Portaria 090 detectada, corte: jan/24")
            # Portarias 121 com transição = 1
            elif (('Portaria nº 121/SMDHC/2019' in portaria or 'Portaria n° 121/SMDHC/2019' in portaria or \
                   'Portaria nº 121/SMDHC/2023' in portaria or 'Portaria n° 121/SMDHC/2023' in portaria) and transicao == 1):
                data_corte = date(2023, 3, 1)  # mar/23
                print(f"[AUTOMAÇÃO] Portaria 121 com transição, corte: mar/23")
            # Portarias 140 com transição = 1
            elif (('Portaria nº 140/SMDHC/2019' in portaria or 'Portaria n° 140/SMDHC/2019' in portaria or \
                   'Portaria nº 140/SMDHC/2023' in portaria or 'Portaria n° 140/SMDHC/2023' in portaria) and transicao == 1):
                data_corte = date(2024, 1, 1)  # jan/24
                print(f"[AUTOMAÇÃO] Portaria 140 com transição, corte: jan/24")
            
            # Aplicar automação apenas se houver data de corte definida
            if data_corte:
                print(f"[AUTOMAÇÃO] Aplicando regra para competências >= {data_corte}")
                print(f"[AUTOMAÇÃO] Regras: Apenas células VAZIAS + Competência >= corte + Créditos E Débitos")
                
                linhas_atualizadas = 0
                
                # Processar cada linha salva
                for linha_id in ids_processados:
                    cur.execute("""
                        SELECT id, competencia, origem_destino, cat_transacao, credito, debito
                        FROM analises_pc.conc_extrato
                        WHERE id = %s
                    """, (linha_id,))
                    linha_data = cur.fetchone()
                    
                    if not linha_data:
                        continue
                    
                    competencia = linha_data['competencia']
                    cat_transacao_atual = (linha_data['cat_transacao'] or '').strip()
                    origem_destino = (linha_data['origem_destino'] or '').strip()
                    credito = linha_data['credito'] or 0
                    debito = linha_data['debito'] or 0
                    
                    # REGRA 1: Se competência não está preenchida, pular
                    if not competencia:
                        continue
                    
                    # REGRA 2: Verificar se competência é >= data de corte
                    if competencia < data_corte:
                        continue
                    
                    # REGRA 3: NUNCA sobrescrever categoria já preenchida (proteção total)
                    if cat_transacao_atual:
                        continue
                    
                    # REGRA 4: Aplicar apenas a DÉBITOS e CRÉDITOS (qualquer tipo de transação)
                    # (Removida a restrição de apenas débitos)
                    
                    # Determinar nova categoria baseada em Origem/Destino
                    nova_categoria = None
                    
                    if origem_destino:
                        # Origem/Destino preenchido → Destinatário Identificado
                        nova_categoria = 'Destinatário Identificado'
                    else:
                        # Origem/Destino vazio → Destinatário não Identificado
                        nova_categoria = 'Destinatário não Identificado'
                    
                    # Atualizar categoria e marcar como "Avaliado"
                    if nova_categoria:
                        cur.execute("""
                            UPDATE analises_pc.conc_extrato
                            SET cat_transacao = %s,
                                cat_avaliacao = 'Avaliado'
                            WHERE id = %s
                        """, (nova_categoria, linha_id))
                        linhas_atualizadas += 1
                
                if linhas_atualizadas > 0:
                    print(f"[AUTOMAÇÃO] ✅ {linhas_atualizadas} linhas categorizadas automaticamente")
        
        db.commit()
        
        tempo_total = (time.time() - inicio) * 1000
        print(f"\n[SAVE] Tempo total: {tempo_total:.2f}ms | Linhas: {len(ids_processados)}")
        
        return jsonify({
            'mensagem': f'{len(ids_processados)} linhas salvas com sucesso',
            'ids': ids_processados
        }), 200
        
    except Exception as e:
        print(f"[ERRO] ao salvar extrato: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/extrato/<int:extrato_id>', methods=['DELETE'])
@login_required
@requires_access('conc_bancaria')
def api_excluir_extrato(extrato_id):
    """API para excluir uma linha do extrato"""
    try:
        cur = get_cursor()
        db = get_db()
        
        cur.execute("DELETE FROM analises_pc.conc_extrato WHERE id = %s", (extrato_id,))
        db.commit()
        
        return jsonify({'mensagem': 'Linha excluída com sucesso'}), 200
        
    except Exception as e:
        print(f"[ERRO] ao excluir linha {extrato_id}: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/termos', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_listar_termos():
    """API para listar números de termos (de parcerias + extratos existentes)"""
    try:
        cur = get_cursor()
        
        # Buscar termos de parcerias (todos os termos válidos) + termos com extrato existente
        cur.execute("""
            SELECT DISTINCT numero_termo 
            FROM public.parcerias 
            WHERE numero_termo IS NOT NULL
            UNION
            SELECT DISTINCT numero_termo 
            FROM analises_pc.conc_extrato 
            WHERE numero_termo IS NOT NULL 
            ORDER BY numero_termo
        """)
        
        termos = [row['numero_termo'] for row in cur.fetchall()]
        
        return jsonify(termos), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar termos: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-despesas', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_categorias_despesas():
    """API para listar categorias de despesas de um termo específico"""
    import time
    start_time = time.time()
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        filtro = request.args.get('filtro', '').strip()
        
        if not numero_termo:
            return jsonify([]), 200
        
        query = """
            SELECT DISTINCT categoria_despesa 
            FROM public.parcerias_despesas 
            WHERE numero_termo = %s 
              AND categoria_despesa IS NOT NULL
        """
        params = [numero_termo]
        
        if filtro:
            query += " AND categoria_despesa ILIKE %s"
            params.append(f'%{filtro}%')
        
        query += " ORDER BY categoria_despesa"
        
        cur.execute(query, params)
        
        categorias = [{'categoria_despesa': row['categoria_despesa']} for row in cur.fetchall()]
        
        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/categorias-despesas: {elapsed:.2f}ms")
        return jsonify(categorias), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar categorias de despesas: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-analise', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_categorias_analise():
    """API para listar categorias de análise"""
    import time
    start_time = time.time()
    try:
        cur = get_cursor()
        filtro = request.args.get('filtro', '').strip()
        
        query = """
            SELECT categoria_extra, tipo_transacao, descricao, correspondente
            FROM categoricas.c_despesas_analise
        """
        params = []
        
        if filtro:
            query += " WHERE categoria_extra ILIKE %s"
            params.append(f'%{filtro}%')
        
        query += " ORDER BY categoria_extra"
        
        cur.execute(query, params)
        
        categorias = [dict(row) for row in cur.fetchall()]
        
        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/categorias-analise: {elapsed:.2f}ms")
        return jsonify(categorias), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar categorias de análise: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/periodo-termo', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_periodo_termo():
    """API para obter período (datas início e final) de um termo de parceria"""
    import time
    start_time = time.time()
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
        
        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/periodo-termo: {elapsed:.2f}ms")
        
        return jsonify(periodo), 200
        
    except Exception as e:
        print(f"[ERRO] ao buscar período do termo: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/banco', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_get_banco():
    """API para obter o banco do extrato e conta específica de um termo"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        # Buscar banco_extrato e conta_execucao de analises_pc.conc_banco
        query_banco = """
            SELECT banco_extrato, conta_execucao
            FROM analises_pc.conc_banco
            WHERE numero_termo = %s
        """
        
        cur.execute(query_banco, (numero_termo,))
        resultado_banco = cur.fetchone()
        
        # Buscar conta de public.parcerias
        query_conta = """
            SELECT conta
            FROM public.parcerias
            WHERE numero_termo = %s
        """
        
        cur.execute(query_conta, (numero_termo,))
        resultado_conta = cur.fetchone()
        
        return jsonify({
            'banco_extrato': resultado_banco['banco_extrato'] if resultado_banco else None,
            'conta': resultado_conta['conta'] if resultado_conta else None,
            'conta_execucao': resultado_banco['conta_execucao'] if resultado_banco else None
        }), 200
        
    except Exception as e:
        print(f"[ERRO] ao buscar banco: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/salvar-termo-session', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
def api_salvar_termo_session():
    """API para salvar o termo atual na session"""
    try:
        dados = request.get_json()
        numero_termo = dados.get('numero_termo')
        
        if numero_termo:
            session['numero_termo'] = numero_termo
            return jsonify({'sucesso': True}), 200
        else:
            return jsonify({'erro': 'numero_termo não fornecido'}), 400
            
    except Exception as e:
        print(f"[ERRO] Erro ao salvar termo na session: {str(e)}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/banco', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
def api_save_banco():
    """API para salvar o banco do extrato e conta específica de um termo"""
    try:
        dados = request.get_json()
        numero_termo = dados.get('numero_termo')
        banco_extrato = dados.get('banco_extrato')
        conta = dados.get('conta')
        conta_execucao = dados.get('conta_execucao')
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        cur = get_cursor()
        db = get_db()
        
        # Salvar banco_extrato e conta_execucao em analises_pc.conc_banco
        if banco_extrato is not None or conta_execucao is not None:
            # Verificar se já existe
            cur.execute("""
                SELECT id FROM analises_pc.conc_banco 
                WHERE numero_termo = %s
            """, (numero_termo,))
            
            existe = cur.fetchone()
            
            if existe:
                # Atualizar campos individualmente
                if banco_extrato is not None:
                    cur.execute("""
                        UPDATE analises_pc.conc_banco 
                        SET banco_extrato = %s
                        WHERE numero_termo = %s
                    """, (banco_extrato, numero_termo))
                
                if conta_execucao is not None:
                    cur.execute("""
                        UPDATE analises_pc.conc_banco 
                        SET conta_execucao = %s
                        WHERE numero_termo = %s
                    """, (conta_execucao, numero_termo))
            else:
                # Inserir
                cur.execute("""
                    INSERT INTO analises_pc.conc_banco (numero_termo, banco_extrato, conta_execucao)
                    VALUES (%s, %s, %s)
                """, (numero_termo, banco_extrato, conta_execucao))
        
        # Salvar conta em public.parcerias
        if conta is not None:
            cur.execute("""
                UPDATE public.parcerias
                SET conta = %s
                WHERE numero_termo = %s
            """, (conta, numero_termo))
        
        db.commit()
        
        return jsonify({'mensagem': 'Banco e conta salvos com sucesso'}), 200
        
    except Exception as e:
        print(f"[ERRO] ao salvar banco: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/notas-fiscais', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_listar_notas_fiscais():
    """API para listar notas fiscais de um termo"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        query = """
            SELECT 
                id,
                conc_extrato_id,
                numero_nota,
                chave_acesso,
                cnpj_nota,
                numero_termo
            FROM analises_pc.conc_extrato_notas_fiscais
            WHERE numero_termo = %s
            ORDER BY conc_extrato_id ASC
        """
        
        cur.execute(query, (numero_termo,))
        notas = cur.fetchall()
        
        resultado = [dict(nota) for nota in notas]
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar notas fiscais: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/notas-fiscais', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
def api_salvar_notas_fiscais():
    """API para salvar notas fiscais com UPSERT (UPDATE prioritário)"""
    try:
        import time
        inicio = time.time()
        
        dados = request.get_json()
        notas = dados.get('notas', [])
        numero_termo = dados.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400
        
        cur = get_cursor()
        db = get_db()
        
        ids_processados = []
        
        for nota in notas:
            conc_extrato_id = nota.get('conc_extrato_id')
            
            if not conc_extrato_id:
                continue  # Pular se não tiver FK
            
            # Verificar se tem dados preenchidos (não salvar linha vazia)
            numero_nota = nota.get('numero_nota')
            chave_acesso = nota.get('chave_acesso') or ''
            cnpj_nota = nota.get('cnpj_nota') or ''
            
            # Strip apenas se não for None
            chave_acesso = chave_acesso.strip() if chave_acesso else None
            cnpj_nota = cnpj_nota.strip() if cnpj_nota else None
            
            # Se não tem número da nota, deletar registro se existir
            if not numero_nota:
                cur.execute("""
                    DELETE FROM analises_pc.conc_extrato_notas_fiscais
                    WHERE conc_extrato_id = %s AND numero_termo = %s
                """, (conc_extrato_id, numero_termo))
                continue
            
            # Verificar se já existe registro para este conc_extrato_id
            cur.execute("""
                SELECT id FROM analises_pc.conc_extrato_notas_fiscais
                WHERE conc_extrato_id = %s AND numero_termo = %s
            """, (conc_extrato_id, numero_termo))
            
            existe = cur.fetchone()
            
            if existe:
                # UPDATE: registro já existe
                cur.execute("""
                    UPDATE analises_pc.conc_extrato_notas_fiscais SET
                        numero_nota = %s,
                        chave_acesso = %s,
                        cnpj_nota = %s
                    WHERE conc_extrato_id = %s AND numero_termo = %s
                    RETURNING id
                """, (
                    numero_nota,
                    chave_acesso,
                    cnpj_nota,
                    conc_extrato_id,
                    numero_termo
                ))
                result = cur.fetchone()
                if result:
                    ids_processados.append(result['id'])
            else:
                # INSERT: novo registro
                cur.execute("""
                    INSERT INTO analises_pc.conc_extrato_notas_fiscais (
                        conc_extrato_id, numero_nota, chave_acesso, 
                        cnpj_nota, numero_termo
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    conc_extrato_id,
                    numero_nota,
                    chave_acesso,
                    cnpj_nota,
                    numero_termo
                ))
                novo_id = cur.fetchone()['id']
                ids_processados.append(novo_id)
        
        db.commit()
        
        tempo_total = (time.time() - inicio) * 1000
        print(f"\n[SAVE NF] Tempo total: {tempo_total:.2f}ms | Notas: {len(ids_processados)}")
        
        return jsonify({
            'mensagem': f'{len(ids_processados)} notas fiscais salvas',
            'ids': ids_processados
        }), 200
        
    except Exception as e:
        print(f"[ERRO] ao salvar notas fiscais: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-aplicabilidade', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_categorias_aplicabilidade():
    """API para buscar aplicabilidade de documentos por categoria"""
    import time
    start_time = time.time()
    try:
        cur = get_cursor()
        
        query = """
            SELECT categoria_extra, COALESCE(aplicacao, false) as aplicacao
            FROM categoricas.c_despesas_analise
            WHERE categoria_extra IS NOT NULL
        """
        
        cur.execute(query)
        categorias = cur.fetchall()
        
        # Retornar como dicionário { categoria: aplicacao }
        resultado = {cat['categoria_extra']: cat['aplicacao'] for cat in categorias}
        
        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/categorias-aplicabilidade: {elapsed:.2f}ms")
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"[ERRO] ao buscar categorias aplicabilidade: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-rubricas', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_categorias_rubricas():
    """API para buscar rubricas das categorias por termo"""
    import time
    start_time = time.time()
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        query = """
            SELECT categoria_despesa, rubrica
            FROM public.parcerias_despesas
            WHERE numero_termo = %s 
              AND categoria_despesa IS NOT NULL
              AND rubrica IS NOT NULL
        """
        
        cur.execute(query, (numero_termo,))
        categorias = cur.fetchall()
        
        # Retornar como dicionário { categoria: rubrica }
        resultado = {cat['categoria_despesa']: cat['rubrica'] for cat in categorias}
        
        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/categorias-rubricas: {elapsed:.2f}ms")
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"[ERRO] ao buscar rubricas: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/documentos-analise', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_listar_documentos_analise():
    """API para listar documentos de análise de um termo"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        query = """
            SELECT 
                id,
                conc_extrato_id,
                COALESCE(avaliacao_guia, 'pendente') as avaliacao_guia,
                COALESCE(avaliacao_comprovante, 'pendente') as avaliacao_comprovante,
                COALESCE(avaliacao_contratos, 'pendente') as avaliacao_contratos,
                COALESCE(avaliacao_fora_municipio, 'pendente') as avaliacao_fora_municipio,
                numero_termo
            FROM analises_pc.conc_analise
            WHERE numero_termo = %s
            ORDER BY conc_extrato_id ASC
        """
        
        cur.execute(query, (numero_termo,))
        documentos = cur.fetchall()
        
        resultado = [dict(doc) for doc in documentos]
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar documentos de análise: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/documentos-analise', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
def api_salvar_documentos_analise():
    """API para salvar documentos de análise com UPSERT e auto-marcação"""
    try:
        import time
        inicio = time.time()
        
        dados = request.get_json()
        documentos = dados.get('documentos', [])
        numero_termo = dados.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400
        
        cur = get_cursor()
        db = get_db()
        
        ids_processados = []
        
        for doc in documentos:
            conc_extrato_id = doc.get('conc_extrato_id')
            
            if not conc_extrato_id:
                continue
            
            # Valores possíveis: textos descritivos ou vazios
            # Coluna 14 (Guia): "Guia apresentada", "Não apresentada"
            # Coluna 15 (Comprovante): "Apresentado corretamente", "Cartão de Crédito", "Pago em Espécie", "Pago em Cheque"
            # Coluna 16 (Contratos): "Contratos apresentados", "Não apresentado"
            # Coluna 17 (Fora Município): "São Paulo", "Fora do município"
            avaliacao_guia = doc.get('avaliacao_guia', '')
            avaliacao_comprovante = doc.get('avaliacao_comprovante', '')
            avaliacao_contratos = doc.get('avaliacao_contratos', '')
            avaliacao_fora_municipio = doc.get('avaliacao_fora_municipio', '')
            
            # ============================================================
            # REGRA DE AUTO-MARCAÇÃO:
            # Se linha está completa E avaliada como "Avaliado",
            # selecionar automaticamente valores padrão (opções positivas)
            # MAS SOMENTE se a categoria for aplicável
            # ============================================================
            
            # Buscar dados da linha do extrato + aplicabilidade da categoria
            cur.execute("""
                SELECT 
                    e.data, e.credito, e.debito, e.discriminacao, e.cat_transacao, 
                    e.competencia, e.origem_destino, e.cat_avaliacao,
                    ca.aplicacao
                FROM analises_pc.conc_extrato e
                LEFT JOIN categoricas.c_despesas_analise ca ON e.cat_transacao = ca.categoria_extra
                WHERE e.id = %s
            """, (conc_extrato_id,))
            
            linha_extrato = cur.fetchone()
            
            if linha_extrato:
                # Verificar se categoria é não aplicável (aplicacao = true significa NÃO aplicável)
                categoria_nao_aplicavel = linha_extrato.get('aplicacao') == True
                
                # IMPORTANTE: Se categoria não aplicável, LIMPAR todos os valores
                # (não deve haver valores salvos para categorias não aplicáveis)
                if categoria_nao_aplicavel:
                    avaliacao_guia = ''
                    avaliacao_comprovante = ''
                    avaliacao_contratos = ''
                    avaliacao_fora_municipio = ''
                else:
                    # Verificar se a linha está completa e avaliada
                    linha_completa = (
                        linha_extrato['data'] is not None and
                        (linha_extrato['credito'] is not None or linha_extrato['debito'] is not None) and
                        linha_extrato['discriminacao'] is not None and
                        linha_extrato['cat_transacao'] is not None and linha_extrato['cat_transacao'].strip() != '' and
                        linha_extrato['competencia'] is not None and
                        linha_extrato['origem_destino'] is not None and linha_extrato['origem_destino'].strip() != '' and
                        linha_extrato['cat_avaliacao'] == 'Avaliado'
                    )
                    
                    # Auto-marcar SOMENTE se linha completa E categoria aplicável
                    if linha_completa:
                        # Auto-marcar com valores padrão se estiverem vazios
                        # NÃO modificar se já tiver algum valor selecionado (respeitar escolha do usuário)
                        if not avaliacao_guia or avaliacao_guia.strip() == '':
                            avaliacao_guia = 'Guia apresentada'
                        if not avaliacao_comprovante or avaliacao_comprovante.strip() == '':
                            avaliacao_comprovante = 'Apresentado corretamente'
                        if not avaliacao_contratos or avaliacao_contratos.strip() == '':
                            avaliacao_contratos = 'Contratos apresentados'
                        if not avaliacao_fora_municipio or avaliacao_fora_municipio.strip() == '':
                            avaliacao_fora_municipio = 'São Paulo'
            
            # Verificar se já existe registro
            cur.execute("""
                SELECT id FROM analises_pc.conc_analise
                WHERE conc_extrato_id = %s AND numero_termo = %s
            """, (conc_extrato_id, numero_termo))
            
            existe = cur.fetchone()
            
            if existe:
                # UPDATE
                cur.execute("""
                    UPDATE analises_pc.conc_analise SET
                        avaliacao_guia = %s,
                        avaliacao_comprovante = %s,
                        avaliacao_contratos = %s,
                        avaliacao_fora_municipio = %s
                    WHERE conc_extrato_id = %s AND numero_termo = %s
                    RETURNING id
                """, (
                    avaliacao_guia,
                    avaliacao_comprovante,
                    avaliacao_contratos,
                    avaliacao_fora_municipio,
                    conc_extrato_id,
                    numero_termo
                ))
                result = cur.fetchone()
                if result:
                    ids_processados.append(result['id'])
            else:
                # INSERT
                cur.execute("""
                    INSERT INTO analises_pc.conc_analise (
                        conc_extrato_id, avaliacao_guia, avaliacao_comprovante,
                        avaliacao_contratos, avaliacao_fora_municipio, numero_termo
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    conc_extrato_id,
                    avaliacao_guia,
                    avaliacao_comprovante,
                    avaliacao_contratos,
                    avaliacao_fora_municipio,
                    numero_termo
                ))
                novo_id = cur.fetchone()['id']
                ids_processados.append(novo_id)
        
        db.commit()
        
        tempo_total = (time.time() - inicio) * 1000
        print(f"\n[SAVE DOC] Tempo total: {tempo_total:.2f}ms | Documentos: {len(ids_processados)}")
        
        return jsonify({
            'mensagem': f'{len(ids_processados)} documentos salvos',
            'ids': ids_processados
        }), 200
        
    except Exception as e:
        print(f"[ERRO] ao salvar documentos de análise: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/limpar-termo', methods=['DELETE'])
@login_required
@requires_access('conc_bancaria')
def api_limpar_termo():
    """
    API para limpar TODOS os dados de um termo específico
    Remove: extrato, rendimentos, notas fiscais e contrapartida
    """
    try:
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400
        
        db = get_db()
        cur = get_cursor()
        
        # Contar registros antes da exclusão
        cur.execute("SELECT COUNT(*) as total FROM analises_pc.conc_extrato WHERE numero_termo = %s", (numero_termo,))
        total_extrato = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as total FROM analises_pc.conc_rendimentos WHERE numero_termo = %s", (numero_termo,))
        total_rendimentos = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as total FROM analises_pc.conc_extrato_notas_fiscais WHERE numero_termo = %s", (numero_termo,))
        total_notas = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as total FROM analises_pc.conc_contrapartida WHERE numero_termo = %s", (numero_termo,))
        total_contrapartida = cur.fetchone()['total']
        
        # Deletar todos os dados do termo
        cur.execute("DELETE FROM analises_pc.conc_extrato_notas_fiscais WHERE numero_termo = %s", (numero_termo,))
        cur.execute("DELETE FROM analises_pc.conc_rendimentos WHERE numero_termo = %s", (numero_termo,))
        cur.execute("DELETE FROM analises_pc.conc_contrapartida WHERE numero_termo = %s", (numero_termo,))
        cur.execute("DELETE FROM analises_pc.conc_extrato WHERE numero_termo = %s", (numero_termo,))
        
        db.commit()
        
        print(f"[LIMPAR TERMO] Termo: {numero_termo}")
        print(f"  - Extrato: {total_extrato} registros deletados")
        print(f"  - Rendimentos: {total_rendimentos} registros deletados")
        print(f"  - Notas Fiscais: {total_notas} registros deletados")
        print(f"  - Contrapartida: {total_contrapartida} registros deletados")
        
        return jsonify({
            'mensagem': 'Dados do termo limpos com sucesso',
            'termo': numero_termo,
            'registros_deletados': {
                'extrato': total_extrato,
                'rendimentos': total_rendimentos,
                'notas_fiscais': total_notas,
                'contrapartida': total_contrapartida,
                'total': total_extrato + total_rendimentos + total_notas + total_contrapartida
            }
        }), 200
        
    except Exception as e:
        print(f"[ERRO] ao limpar termo: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500

