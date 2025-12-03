"""
Blueprint de despesas e APIs relacionadas a orçamento
"""

from flask import Blueprint, request, jsonify, session
from datetime import datetime
import psycopg2
from db import get_db, get_cursor, execute_query, execute_batch
from utils import login_required

despesas_bp = Blueprint('despesas', __name__, url_prefix='/api')


@despesas_bp.route('/termo/<numero_termo>', methods=['GET'])
def get_termo_info(numero_termo):
    """
    Retorna informações do termo para o modal de orçamento
    """
    try:
        # Checar autenticação manualmente para não retornar HTML de login
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        print(f"DEBUG: Buscando termo: {numero_termo}")
        cur = get_cursor()
        cur.execute("""
            SELECT numero_termo, inicio, final, total_previsto, meses
            FROM Parcerias 
            WHERE numero_termo = %s
        """, (numero_termo,))
        termo = cur.fetchone()
        cur.close()
        
        print(f"DEBUG: Termo encontrado: {termo}")
        
        if not termo:
            print(f"DEBUG: Termo {numero_termo} não encontrado")
            return jsonify({"error": "Termo não encontrado"}), 404
        
        # Usar a coluna meses quando disponível, caso contrário tentar calcular pelas datas
        meses = None
        if termo and termo['meses'] is not None:
            try:
                meses = int(termo['meses'])
            except (ValueError, TypeError):
                meses = None
                
        if meses is None:
            # Calcular número de meses baseado nas datas
            meses = 12  # valor padrão
            try:
                if termo["inicio"] and termo["final"]:
                    inicio = datetime.strptime(termo["inicio"], "%Y-%m-%d")
                    final = datetime.strptime(termo["final"], "%Y-%m-%d")
                    # Calcular diferença em meses
                    meses = (final.year - inicio.year) * 12 + (final.month - inicio.month) + 1
                    print(f"DEBUG: Calculado {meses} meses entre {termo['inicio']} e {termo['final']}")
            except (ValueError, TypeError) as e:
                print(f"Erro ao calcular meses: {e}")
        
        resultado = {
            "numero_termo": termo["numero_termo"],
            "inicio": termo["inicio"],
            "final": termo["final"],
            "total_previsto": float(termo["total_previsto"]) if termo["total_previsto"] else 0.0,
            "meses": max(1, meses)  # pelo menos 1 mês
        }
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"Erro no endpoint get_termo_info: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500


# ROTAS ESPECÍFICAS DE DESPESA - DEVEM VIR ANTES DAS ROTAS GENÉRICAS
@despesas_bp.route('/despesa/preview-limpar', methods=['POST'])
@login_required
def preview_limpar_despesas():
    """
    Retorna informações sobre as despesas que serão deletadas
    """
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        aditivo = data.get('aditivo', 0)
        
        if not numero_termo:
            return jsonify({"error": "numero_termo é obrigatório"}), 400

        # Consultar registros que serão afetados
        query = """
            SELECT 
                numero_termo,
                rubrica,
                categoria_despesa,
                COUNT(*) as total_registros,
                SUM(valor) as total_valor,
                MIN(mes) as mes_inicial,
                MAX(mes) as mes_final,
                aditivo
            FROM Parcerias_Despesas 
            WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s
            GROUP BY numero_termo, rubrica, categoria_despesa, aditivo
            ORDER BY rubrica
        """
        
        cursor = get_cursor()
        if not cursor:
            return jsonify({"error": "Falha ao conectar ao banco de dados"}), 500
            
        cursor.execute(query, (numero_termo, aditivo))
        despesas = cursor.fetchall()
        
        if not despesas:
            return jsonify({
                "total_registros": 0,
                "total_valor": 0,
                "despesas": [],
                "numero_termo": numero_termo,
                "aditivo": aditivo
            }), 200
        
        total_registros = sum(d['total_registros'] for d in despesas)
        total_valor = sum(d['total_valor'] for d in despesas)
        
        return jsonify({
            "total_registros": total_registros,
            "total_valor": float(total_valor),
            "despesas": [
                {
                    "rubrica": d['rubrica'],
                    "categoria": d['categoria_despesa'] or 'Sem categoria',
                    "registros": d['total_registros'],
                    "valor": float(d['total_valor']),
                    "meses": f"{d['mes_inicial']}-{d['mes_final']}"
                }
                for d in despesas
            ],
            "numero_termo": numero_termo,
            "aditivo": aditivo
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Erro ao consultar despesas: {str(e)}"}), 500


@despesas_bp.route('/despesa/limpar', methods=['POST'])
@login_required
def limpar_despesas():
    """
    Deleta TODAS as despesas de um termo específico e aditivo do banco de dados
    """
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        aditivo = data.get('aditivo', 0)  # Padrão: 0 (Base)
        
        if not numero_termo:
            return jsonify({"error": "numero_termo é obrigatório"}), 400

        # Deletar TODOS os registros do termo/aditivo
        delete_query = "DELETE FROM Parcerias_Despesas WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s"
        execute_query(delete_query, (numero_termo, aditivo))

        return jsonify({"message": f"Todas as despesas do termo {numero_termo} (Aditivo {aditivo}) foram deletadas com sucesso"}), 200
        
    except Exception as e:
        return jsonify({"error": f"Erro ao limpar despesas: {str(e)}"}), 500


@despesas_bp.route('/despesa', methods=['POST'])
@login_required
def criar_despesa():
    """
    Endpoint INTELIGENTE para salvar despesas de um termo.
    Compara dados existentes e só salva as diferenças (UPSERT).
    Espera JSON com: numero_termo, despesas (array com rubrica, quantidade, categoria_despesa, valores_por_mes), aditivo
    """
    import time
    start_time = time.time()
    
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        despesas = data.get('despesas', [])
        aditivo = data.get('aditivo', 0)  # Padrão: 0 (Base)
        
        if not numero_termo or not despesas:
            return {"error": "numero_termo e despesas são obrigatórios"}, 400

        # Obter cursor
        cursor = get_cursor()
        if not cursor:
            return {"error": "Falha ao conectar ao banco de dados"}, 500
        
        t1 = time.time()
        print(f"[PERF] Setup: {(t1-start_time)*1000:.0f}ms")
        
        # 1. BUSCAR DADOS EXISTENTES no banco
        query_existentes = """
            SELECT rubrica, quantidade, categoria_despesa, valor, mes, aditivo
            FROM Parcerias_Despesas 
            WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s
        """
        cursor.execute(query_existentes, (numero_termo, aditivo))
        registros_existentes = cursor.fetchall()
        
        t2 = time.time()
        print(f"[PERF] Query existentes ({len(registros_existentes)} registros): {(t2-t1)*1000:.0f}ms")
        
        # Criar conjunto de registros existentes (para comparação rápida)
        existentes_set = set()
        for reg in registros_existentes:
            # Criar chave única: rubrica|mes|valor|quantidade|categoria
            chave = f"{reg['rubrica']}|{reg['mes']}|{float(reg['valor']):.2f}|{reg['quantidade']}|{reg['categoria_despesa']}"
            existentes_set.add(chave)
        
        print(f"[INFO] Registros existentes no banco: {len(existentes_set)}")
        
        t3 = time.time()
        print(f"[PERF] Criar set existentes: {(t3-t2)*1000:.0f}ms")
        
        # 2. PROCESSAR NOVOS DADOS vindos do frontend
        novos_registros = []
        novos_set = set()
        
        for despesa in despesas:
            rubrica = despesa.get('rubrica')
            quantidade = despesa.get('quantidade')
            categoria = despesa.get('categoria_despesa', '')
            valores_por_mes = despesa.get('valores_por_mes', {})
            
            if not rubrica:
                continue
                
            for mes_str, valor_str in valores_por_mes.items():
                if not valor_str or str(valor_str).strip() == '' or str(valor_str).strip() == '-':
                    continue
                    
                try:
                    mes = int(mes_str)
                    # Limpar e converter o valor
                    valor_limpo = str(valor_str).replace('R$', '').replace(' ', '').strip()
                    if '.' in valor_limpo and ',' in valor_limpo:
                        valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
                    elif ',' in valor_limpo:
                        valor_limpo = valor_limpo.replace(',', '.')
                    
                    valor = float(valor_limpo)
                    
                    # Criar chave única para comparação
                    chave = f"{rubrica}|{mes}|{valor:.2f}|{quantidade if quantidade != '-' else None}|{categoria}"
                    novos_set.add(chave)
                    
                    novos_registros.append({
                        'numero_termo': numero_termo,
                        'rubrica': rubrica,
                        'quantidade': quantidade if quantidade != '-' else None,
                        'categoria_despesa': categoria,
                        'valor': valor,
                        'mes': mes,
                        'aditivo': aditivo,
                        'chave': chave
                    })
                except (ValueError, TypeError) as e:
                    print(f"[ERRO] Falha ao converter valor '{valor_str}': {e}")
                    continue
        
        t4 = time.time()
        print(f"[PERF] Processar novos dados ({len(novos_registros)} registros): {(t4-t3)*1000:.0f}ms")
        print(f"[INFO] Novos registros a processar: {len(novos_set)}")
        
        # 3. IDENTIFICAR DIFERENÇAS
        registros_para_inserir = []  # Estão nos novos mas NÃO nos existentes
        registros_para_deletar = []  # Estão nos existentes mas NÃO nos novos
        
        # Registros que precisam ser INSERIDOS (novos que não existem)
        for registro in novos_registros:
            if registro['chave'] not in existentes_set:
                registros_para_inserir.append(registro)
        
        # Registros que precisam ser DELETADOS (existentes que não estão nos novos)
        for reg in registros_existentes:
            chave = f"{reg['rubrica']}|{reg['mes']}|{float(reg['valor']):.2f}|{reg['quantidade']}|{reg['categoria_despesa']}"
            if chave not in novos_set:
                registros_para_deletar.append(reg)
        
        t5 = time.time()
        print(f"[PERF] Identificar diferenças: {(t5-t4)*1000:.0f}ms")
        t5 = time.time()
        print(f"[PERF] Identificar diferenças: {(t5-t4)*1000:.0f}ms")
        print(f"[INFO] Registros a INSERIR: {len(registros_para_inserir)}")
        print(f"[INFO] Registros a DELETAR: {len(registros_para_deletar)}")
        
        # 4. SE NÃO HÁ MUDANÇAS, retornar sucesso sem fazer nada
        if len(registros_para_inserir) == 0 and len(registros_para_deletar) == 0:
            total_time = (time.time() - start_time) * 1000
            print(f"[PERF] TOTAL (sem mudanças): {total_time:.0f}ms")
            return {
                "message": "Nenhuma alteração detectada. Dados já estão sincronizados!",
                "alteracoes": 0,
                "inseridos": 0,
                "deletados": 0
            }, 200
        
        # 5. OTIMIZAÇÃO RADICAL: Se houver muitas mudanças, DELETAR TUDO E REINSERIR
        # Isso é mais rápido que múltiplos DELETEs seletivos
        total_mudancas = len(registros_para_inserir) + len(registros_para_deletar)
        usar_delete_all = total_mudancas > 50  # Threshold: se > 50 mudanças, deletar tudo
        
        t6 = time.time()
        
        if usar_delete_all:
            # ESTRATÉGIA 1: DELETAR TUDO + INSERIR TUDO (mais rápido para muitas mudanças)
            print(f"[PERF] Usando DELETE ALL (muitas mudanças: {total_mudancas})")
            
            delete_query = "DELETE FROM Parcerias_Despesas WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s"
            execute_query(delete_query, (numero_termo, aditivo))
            
            t7 = time.time()
            print(f"[PERF] DELETE ALL: {(t7-t6)*1000:.0f}ms")
            
            # Inserir TODOS os novos registros
            params_batch = []
            for registro in novos_registros:
                params_batch.append((
                    registro['numero_termo'],
                    registro['rubrica'], 
                    registro['quantidade'],
                    registro['categoria_despesa'],
                    registro['valor'],
                    registro['mes'],
                    registro['aditivo']
                ))
            
            insert_query = """
                INSERT INTO Parcerias_Despesas 
                (numero_termo, rubrica, quantidade, categoria_despesa, valor, mes, aditivo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            result = execute_batch(insert_query, params_batch)
            
            t8 = time.time()
            print(f"[PERF] INSERT BATCH ({len(params_batch)} registros): {(t8-t7)*1000:.0f}ms")
            
            total_time = (t8 - start_time) * 1000
            print(f"[PERF] TOTAL: {total_time:.0f}ms")
            
            if not result['success']:
                return {"error": "Falha ao inserir despesas no banco de dados"}, 500

            return {
                "message": f"Sincronização concluída! {len(novos_registros)} registros salvos (estratégia: DELETE ALL)",
                "alteracoes": len(novos_registros),
                "inseridos": len(novos_registros),
                "deletados": len(registros_existentes),
                "environment": result.get('environment', 'LOCAL'),
                "tempo_ms": int(total_time)
            }, 201
        
        else:
            # ESTRATÉGIA 2: DELETE SELETIVO + INSERT (para poucas mudanças)
            print(f"[PERF] Usando DELETE SELETIVO (poucas mudanças: {total_mudancas})")
            
            # Deletar registros obsoletos
            if registros_para_deletar:
                # Construir condições WHERE para delete em batch
                delete_conditions = []
                for reg in registros_para_deletar:
                    # Escapar aspas simples na rubrica
                    rubrica_escaped = reg['rubrica'].replace("'", "''")
                    delete_conditions.append(
                        f"(rubrica = '{rubrica_escaped}' AND mes = {reg['mes']} AND valor = {float(reg['valor'])})"
                    )
                
                # Deletar em um único comando
                delete_query = f"""
                    DELETE FROM Parcerias_Despesas 
                    WHERE numero_termo = %s 
                    AND COALESCE(aditivo, 0) = %s
                    AND ({' OR '.join(delete_conditions)})
                """
                execute_query(delete_query, (numero_termo, aditivo))
                
                t7 = time.time()
                print(f"[PERF] DELETE SELETIVO ({len(registros_para_deletar)} registros): {(t7-t6)*1000:.0f}ms")
            else:
                t7 = t6
            
            # Inserir novos registros
            if registros_para_inserir:
                params_batch = []
                for registro in registros_para_inserir:
                    params_batch.append((
                        registro['numero_termo'],
                        registro['rubrica'], 
                        registro['quantidade'],
                        registro['categoria_despesa'],
                        registro['valor'],
                        registro['mes'],
                        registro['aditivo']
                    ))
                
                insert_query = """
                    INSERT INTO Parcerias_Despesas 
                    (numero_termo, rubrica, quantidade, categoria_despesa, valor, mes, aditivo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                
                result = execute_batch(insert_query, params_batch)
                
                t8 = time.time()
                print(f"[PERF] INSERT BATCH ({len(params_batch)} registros): {(t8-t7)*1000:.0f}ms")
                
                total_time = (t8 - start_time) * 1000
                print(f"[PERF] TOTAL: {total_time:.0f}ms")
                
                if not result['success']:
                    return {"error": "Falha ao inserir despesas no banco de dados"}, 500

                return {
                    "message": f"Sincronização concluída! {len(registros_para_inserir)} inseridos, {len(registros_para_deletar)} deletados",
                    "alteracoes": len(registros_para_inserir) + len(registros_para_deletar),
                    "inseridos": len(registros_para_inserir),
                    "deletados": len(registros_para_deletar),
                    "environment": result.get('environment', 'LOCAL'),
                    "tempo_ms": int(total_time)
                }, 201
            
            # Se chegou aqui, só houve deleções
            total_time = (time.time() - start_time) * 1000
            print(f"[PERF] TOTAL (só deleções): {total_time:.0f}ms")
            return {
                "message": f"Sincronização concluída! {len(registros_para_deletar)} registros obsoletos removidos",
                "alteracoes": len(registros_para_deletar),
                "inseridos": 0,
                "deletados": len(registros_para_deletar),
                "tempo_ms": int(total_time)
            }, 200
        
    except Exception as e:
        print(f"[ERRO] Falha no endpoint /despesa: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Erro ao processar despesas: {str(e)}"}, 500


@despesas_bp.route('/despesas/<path:numero_termo>', methods=['GET'])
@login_required
def get_despesas_termo(numero_termo):
    """
    Retorna todas as despesas de um termo específico agrupadas por rubrica/categoria
    Aceita parâmetro opcional ?aditivo=N para filtrar por aditivo específico
    """
    try:
        # Obter aditivo da query string (padrão: 0 = Base)
        aditivo = request.args.get('aditivo', '0')
        try:
            aditivo_int = int(aditivo)
        except ValueError:
            aditivo_int = 0
        
        cur = get_cursor()
        cur.execute("""
            SELECT rubrica, quantidade, categoria_despesa, mes, valor, aditivo
            FROM Parcerias_Despesas 
            WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s
            ORDER BY id
        """, (numero_termo, aditivo_int))
        despesas_raw = cur.fetchall()
        cur.close()
        
        if not despesas_raw:
            return {"despesas": []}, 200
        
        # Agrupar por rubrica + categoria para formar as linhas da tabela
        despesas_agrupadas = {}
        for row in despesas_raw:
            key = f"{row['rubrica']}|{row['categoria_despesa']}|{row['quantidade'] or 1}"
            if key not in despesas_agrupadas:
                despesas_agrupadas[key] = {
                    'rubrica': row['rubrica'],
                    'quantidade': row['quantidade'] or 1,
                    'categoria_despesa': row['categoria_despesa'],
                    'valores_por_mes': {}
                }
            despesas_agrupadas[key]['valores_por_mes'][str(row['mes'])] = float(row['valor'])
        
        # Converter para lista
        despesas = list(despesas_agrupadas.values())
        
        return {"despesas": despesas}, 200
        
    except Exception as e:
        return {"error": f"Erro ao carregar despesas: {str(e)}"}, 500


@despesas_bp.route('/despesa/confirmar', methods=['POST'])
@login_required
def confirmar_despesa():
    """
    Confirma inserção mesmo com diferença no total
    """
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        despesas = data.get('despesas', [])
        aditivo = data.get('aditivo', 0)  # Padrão: 0 (Base)
        
        if not numero_termo or not despesas:
            return {"error": "numero_termo e despesas são obrigatórios"}, 400

        # Antes de inserir, deletar registros existentes do mesmo aditivo para substituir
        delete_query = "DELETE FROM Parcerias_Despesas WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s"
        execute_query(delete_query, (numero_termo, aditivo))

        # Preparar lista de parâmetros para INSERT em BATCH
        params_batch = []
        
        for despesa in despesas:
            rubrica = despesa.get('rubrica')
            quantidade = despesa.get('quantidade')
            categoria = despesa.get('categoria_despesa', '')
            valores_por_mes = despesa.get('valores_por_mes', {})

            if not rubrica:
                continue

            for mes_str, valor_str in valores_por_mes.items():
                if not valor_str or str(valor_str).strip() == '' or str(valor_str).strip() == '-':
                    continue

                try:
                    mes = int(mes_str)
                    # Limpar e converter o valor
                    valor_limpo = str(valor_str).replace('R$', '').replace(' ', '').strip()
                    if '.' in valor_limpo and ',' in valor_limpo:
                        valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
                    elif ',' in valor_limpo:
                        valor_limpo = valor_limpo.replace(',', '.')
                    
                    valor = float(valor_limpo)

                    params_batch.append((
                        numero_termo, 
                        rubrica, 
                        quantidade if quantidade != '-' else None, 
                        categoria, 
                        valor, 
                        mes, 
                        aditivo
                    ))
                except (ValueError, TypeError):
                    continue

        # Inserir todas as despesas de uma vez em BATCH
        insert_query = """
            INSERT INTO Parcerias_Despesas 
            (numero_termo, rubrica, quantidade, categoria_despesa, valor, mes, aditivo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        result = execute_batch(insert_query, params_batch)
        
        if not result['success']:
            return {"error": "Falha ao inserir despesas no banco de dados"}, 500

        return {
            "message": f"Inseridas {result['count']} despesas com sucesso em batch",
            "registros": result['count'],
            "batch_result": result
        }, 201
        
    except Exception as e:
        return {"error": f"Erro: {str(e)}"}, 500


@despesas_bp.route('/categorias', methods=['GET'])
@login_required
def get_categorias():
    """
    Retorna lista de categorias de despesa únicas do banco de dados
    """
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT DISTINCT categoria_despesa
            FROM Parcerias_Despesas
            WHERE categoria_despesa IS NOT NULL AND categoria_despesa != ''
            ORDER BY categoria_despesa
        """)
        categorias = [row['categoria_despesa'] for row in cur.fetchall()]
        cur.close()
        return {"categorias": categorias}, 200
    except Exception as e:
        return {"error": f"Erro: {str(e)}"}, 500


@despesas_bp.route('/rubrica-sugerida/<path:categoria>', methods=['GET'])
@login_required
def get_rubrica_sugerida(categoria):
    """
    Retorna a rubrica mais comum para uma categoria de despesa específica
    """
    try:
        cur = get_cursor()
        # Buscar a rubrica mais frequente para esta categoria
        cur.execute("""
            SELECT rubrica, COUNT(*) as freq
            FROM Parcerias_Despesas
            WHERE categoria_despesa = %s AND rubrica IS NOT NULL AND rubrica != ''
            GROUP BY rubrica
            ORDER BY freq DESC
            LIMIT 1
        """, (categoria,))
        resultado = cur.fetchone()
        cur.close()
        
        if resultado:
            return {"rubrica": resultado['rubrica']}, 200
        else:
            return {"rubrica": None}, 200
    except Exception as e:
        return {"error": f"Erro: {str(e)}"}, 500
