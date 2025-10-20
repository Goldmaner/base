"""
Blueprint de despesas e APIs relacionadas a orçamento
"""

from flask import Blueprint, request, jsonify, session
from datetime import datetime
import psycopg2
from db import get_db, get_cursor, execute_dual, get_cursor_local, get_cursor_railway
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
        
        print(f"DEBUG: Retornando: {resultado}")
        return jsonify(resultado)
        
    except Exception as e:
        print(f"Erro no endpoint get_termo_info: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500


@despesas_bp.route('/despesa', methods=['POST'])
@login_required
def criar_despesa():
    """
    Endpoint para inserir múltiplas despesas de um termo.
    Espera JSON com: numero_termo, despesas (array com rubrica, quantidade, categoria_despesa, valores_por_mes), aditivo
    """
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        despesas = data.get('despesas', [])
        aditivo = data.get('aditivo', 0)  # Padrão: 0 (Base)
        
        if not numero_termo or not despesas:
            return {"error": "numero_termo e despesas são obrigatórios"}, 400

        cur = get_cursor()
        
        # Verificar se o termo existe
        cur.execute("SELECT total_previsto FROM Parcerias WHERE numero_termo = %s", (numero_termo,))
        termo = cur.fetchone()
        if not termo:
            return {"error": "Termo não encontrado"}, 404
            
        total_previsto = float(termo["total_previsto"] or 0)
        
        # Calcular total inserido (soma de TODAS as despesas de TODOS os meses)
        total_inserido = 0
        registros_para_inserir = []
        
        for despesa in despesas:
            rubrica = despesa.get('rubrica')
            quantidade = despesa.get('quantidade')
            categoria = despesa.get('categoria_despesa', '')
            valores_por_mes = despesa.get('valores_por_mes', {})
            
            if not rubrica:
                continue
                
            # Processar cada mês
            for mes_str, valor_str in valores_por_mes.items():
                if not valor_str or str(valor_str).strip() == '' or str(valor_str).strip() == '-':
                    continue
                    
                try:
                    mes = int(mes_str)
                    # Limpar e converter o valor (pode vir formatado como "52.499,56" ou "52499.56")
                    valor_limpo = str(valor_str).replace('R$', '').replace(' ', '').strip()
                    # Se tiver ponto E vírgula, é formato BR (1.234,56)
                    if '.' in valor_limpo and ',' in valor_limpo:
                        valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
                    # Se tiver apenas vírgula, trocar por ponto
                    elif ',' in valor_limpo:
                        valor_limpo = valor_limpo.replace(',', '.')
                    
                    valor = float(valor_limpo)
                    total_inserido += valor
                    
                    registros_para_inserir.append({
                        'numero_termo': numero_termo,
                        'rubrica': rubrica,
                        'quantidade': quantidade if quantidade != '-' else None,
                        'categoria_despesa': categoria,
                        'valor': valor,
                        'mes': mes,
                        'aditivo': aditivo
                    })
                except (ValueError, TypeError) as e:
                    print(f"[ERRO] Falha ao converter valor '{valor_str}' para float: {e}")
                    continue
        
        # Verificar se total bate com previsto (permitir diferença de até R$ 0.01)
        diferenca = abs(total_inserido - total_previsto)
        if diferenca > 0.01:
            return {
                "warning": True,
                "message": f"Total inserido (R$ {total_inserido:.2f}) diferente do previsto (R$ {total_previsto:.2f}). Diferença: R$ {diferenca:.2f}",
                "total_inserido": total_inserido,
                "total_previsto": total_previsto,
                "registros": len(registros_para_inserir)
            }

        # Se chegou aqui, os totais batem dentro da tolerância: substituir (deletar+inserir)
        try:
            # Deletar despesas antigas do aditivo em ambos os bancos
            delete_query = "DELETE FROM Parcerias_Despesas WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s"
            execute_dual(delete_query, (numero_termo, aditivo))
            
            # Inserir novas despesas em ambos os bancos
            insert_query = """
                INSERT INTO Parcerias_Despesas 
                (numero_termo, rubrica, quantidade, categoria_despesa, valor, mes, aditivo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            for registro in registros_para_inserir:
                execute_dual(insert_query, (
                    registro['numero_termo'],
                    registro['rubrica'], 
                    registro['quantidade'],
                    registro['categoria_despesa'],
                    registro['valor'],
                    registro['mes'],
                    registro['aditivo']
                ))
            
            return {
                "message": f"Inseridas {len(registros_para_inserir)} despesas com sucesso",
                "total_inserido": total_inserido,
                "registros": len(registros_para_inserir)
            }, 201
        except Exception as e:
            return {"error": f"Erro ao inserir despesas: {str(e)}"}, 500
        
    except Exception as e:
        return {"error": f"Erro inesperado: {str(e)}"}, 500


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

        registros_inseridos = 0

        # Antes de inserir, deletar registros existentes do mesmo aditivo para substituir
        delete_query = "DELETE FROM Parcerias_Despesas WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s"
        execute_dual(delete_query, (numero_termo, aditivo))

        # Inserir despesas em ambos os bancos
        insert_query = """
            INSERT INTO Parcerias_Despesas 
            (numero_termo, rubrica, quantidade, categoria_despesa, valor, mes, aditivo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

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

                    execute_dual(insert_query, (
                        numero_termo, 
                        rubrica, 
                        quantidade if quantidade != '-' else None, 
                        categoria, 
                        valor, 
                        mes, 
                        aditivo
                    ))

                    registros_inseridos += 1
                except (ValueError, TypeError):
                    continue

        return {"message": f"Inseridas {registros_inseridos} despesas com sucesso"}, 201
        
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
