# app.py
from flask import Flask, g, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import datetime

# Configuração do banco PostgreSQL
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'projeto_parcerias',
    'user': 'postgres',
    'password': 'Coração01'
}

SECRET_KEY = 'seu_secret_key_aqui'  # Substitua por uma chave secreta segura

app = Flask(__name__)
app.secret_key = SECRET_KEY

def format_sei(sei_number):
    """
    Formata número SEI no padrão: 6074.2022/0008210-7
    Entrada: 6074202200082107 -> Saída: 6074.2022/0008210-7
    """
    if not sei_number:
        return '-'
    
    sei_str = str(sei_number).strip()
    if len(sei_str) < 16:
        return sei_str  # retorna como está se for menor que 16 dígitos
    
    # Formato: XXXX.XXXX/XXXXXXX-X
    parte1 = sei_str[:4]    # 6074
    parte2 = sei_str[4:8]   # 2022
    parte3 = sei_str[8:15]  # 0008210
    parte4 = sei_str[15]    # 7
    
    return f"{parte1}.{parte2}/{parte3}-{parte4}"

# Registrar o filtro no Jinja2
@app.template_filter('format_sei')
def format_sei_filter(sei_number):
    return format_sei(sei_number)

def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(**DB_CONFIG)
        g.db.autocommit = False  # Para controlar transações manualmente
    return g.db

def get_cursor():
    """Retorna um cursor que funciona como dictionary (similar ao sqlite3.Row)"""
    db = get_db()
    return db.cursor(cursor_factory=RealDictCursor)

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/", methods=["GET"])
@login_required
def index():
    # Buscar dados do usuário para exibir nome / tipo
    cur = get_cursor()
    cur.execute("SELECT id, email, tipo_usuario, data_criacao FROM usuarios WHERE id = %s", (session["user_id"],))
    user = cur.fetchone()
    cur.close()
    return render_template("tela_inicial.html", user=user)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email_input = request.form["username"].strip().lower()
        senha_input = request.form["password"]

        cur = get_cursor()
        cur.execute("SELECT id, email, senha, tipo_usuario FROM usuarios WHERE email = %s", (email_input,))
        user = cur.fetchone()
        cur.close()
        if user is None:
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("login"))

        # senha armazenada é hash
        stored_hash = user["senha"]
        if check_password_hash(stored_hash, senha_input):
            # sucesso: criar sessão simples
            session.clear()
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["tipo_usuario"] = user["tipo_usuario"]
            flash("Logado com sucesso.", "success")
            return redirect(url_for("index"))
        else:
            flash("Senha incorreta.", "danger")
            return redirect(url_for("login"))
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu.", "info")
    return redirect(url_for("login"))

@app.route("/orcamento", methods=["GET"])
@login_required
def orcamento():
    cur = get_cursor()
    
    # Query principal: Parcerias LEFT JOIN Parcerias_Despesas para somar valores preenchidos
    # Filtrar convênios e acordos de cooperação conforme solicitado
    cur.execute("""
        SELECT 
            p.numero_termo,
            p.tipo_termo,
            p.meses,
            p.sei_celeb,
            p.total_previsto,
            COALESCE(SUM(pd.valor), 0) as total_preenchido
        FROM Parcerias p
        LEFT JOIN Parcerias_Despesas pd ON p.numero_termo = pd.numero_termo
        WHERE p.tipo_termo NOT IN ('Convênio de Cooperação', 'Convênio', 'Convênio - Passivo', 'Acordo de Cooperação')
        GROUP BY p.numero_termo, p.tipo_termo, p.meses, p.sei_celeb, p.total_previsto
        ORDER BY p.numero_termo
    """)
    parcerias = cur.fetchall()
    cur.close()
    
    # Calcular estatísticas de status
    total_parcerias = len(parcerias)
    nao_feito = 0
    feito_corretamente = 0
    feito_incorretamente = 0
    
    for parceria in parcerias:
        total_previsto = float(parceria["total_previsto"] or 0)
        total_preenchido = float(parceria["total_preenchido"] or 0)
        
        if total_preenchido == 0:
            nao_feito += 1
        elif abs(total_preenchido - total_previsto) < 0.01:  # tolerância para igualdade
            feito_corretamente += 1
        else:
            feito_incorretamente += 1
    
    # Calcular percentuais
    estatisticas = {
        'feito_corretamente': {
            'quantidade': feito_corretamente,
            'percentual': (feito_corretamente / total_parcerias * 100) if total_parcerias > 0 else 0
        },
        'nao_feito': {
            'quantidade': nao_feito,
            'percentual': (nao_feito / total_parcerias * 100) if total_parcerias > 0 else 0
        },
        'feito_incorretamente': {
            'quantidade': feito_incorretamente,
            'percentual': (feito_incorretamente / total_parcerias * 100) if total_parcerias > 0 else 0
        }
    }
    
    return render_template("orcamento_1.html", parcerias=parcerias, estatisticas=estatisticas)


@app.route('/orcamento/editar/<path:numero_termo>')
@login_required
def orcamento_editar(numero_termo):
    # Buscar total_previsto para exibir no subtítulo
    cur = get_cursor()
    cur.execute("SELECT total_previsto FROM Parcerias WHERE numero_termo = %s", (numero_termo,))
    row = cur.fetchone()
    cur.close()
    try:
        total_previsto_val = float(row['total_previsto']) if row and row['total_previsto'] is not None else 0.0
    except Exception:
        total_previsto_val = 0.0
    # formatar em pt-BR: R$ 1.234.567,89
    formatted_total = 'R$ ' + f"{total_previsto_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return render_template('orcamento_2.html', numero_termo=numero_termo, total_previsto=formatted_total, total_previsto_val=total_previsto_val)

@app.route("/instrucoes", methods=["GET"])
@login_required
def instrucoes():
    cur = get_cursor()
    # Buscar todas as instruções ordenadas pela data de criação
    cur.execute("SELECT * FROM Instrucoes ORDER BY data_criacao DESC")
    instrucoes = cur.fetchall()
    cur.close()
    return render_template("instrucoes.html", instrucoes=instrucoes)

@app.route("/api/instrucoes", methods=["GET"])
@login_required
def listar_instrucoes():
    cur = get_cursor()
    cur.execute("SELECT * FROM Instrucoes ORDER BY data_criacao DESC")
    instrucoes = cur.fetchall()
    cur.close()
    # Converter para lista de dicionários para JSON
    return [dict(row) for row in instrucoes]

@app.route("/api/instrucoes/<int:id>", methods=["DELETE"])
@login_required
def deletar_instrucao(id):
    try:
        db = get_db()
        cur = get_cursor()
        cur.execute("DELETE FROM Instrucoes WHERE id = %s", (id,))
        db.commit()
        cur.close()
        return {"message": "Instrução excluída com sucesso"}, 200
    except psycopg2.Error as e:
        return {"error": f"Erro ao excluir instrução: {str(e)}"}, 500

@app.route("/api/instrucoes", methods=["POST"])
@login_required
def criar_instrucao():
    try:
        dados = request.get_json()
        print("Dados recebidos:", dados)  # Debug
        
        titulo = dados.get('titulo')
        categoria = dados.get('categoria')
        texto = dados.get('texto')
        
        print(f"Titulo: {titulo}")  # Debug
        print(f"Categoria: {categoria}")  # Debug
        print(f"Texto: {texto}")  # Debug
        
        if not titulo or not texto:
            return {"error": "Título e texto são obrigatórios"}, 400
            
        db = get_db()
        cur = get_cursor()
        try:
            cur.execute(
                "INSERT INTO Instrucoes (titulo, texto, categoria) VALUES (%s, %s, %s)",
                (titulo, texto, categoria)
            )
            db.commit()
        except psycopg2.Error as e:
            print(f"Erro SQL: {e}")  # Debug
            cur.close()
            raise
        
        cur.close()
        return {"message": "Instrução salva com sucesso"}, 201
    except psycopg2.Error as e:
        print(f"Erro PostgreSQL: {e}")  # Debug
        return {"error": f"Erro ao salvar no banco de dados: {str(e)}"}, 500
    except Exception as e:
        print(f"Erro inesperado: {e}")  # Debug
        return {"error": f"Erro inesperado: {str(e)}"}, 500


@app.route('/api/termo/<numero_termo>', methods=['GET'])
def get_termo_info(numero_termo):
    """Retorna informações do termo para o modal de orçamento."""
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

@app.route('/api/despesa', methods=['POST'])
@login_required
def criar_despesa():
    """Endpoint para inserir múltiplas despesas de um termo.
    Espera JSON com: numero_termo, despesas (array com rubrica, quantidade, categoria_despesa, valores_por_mes)
    """
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        despesas = data.get('despesas', [])
        
        if not numero_termo or not despesas:
            return {"error": "numero_termo e despesas são obrigatórios"}, 400

        cur = get_cursor()
        
        # Verificar se o termo existe
        cur.execute("SELECT total_previsto FROM Parcerias WHERE numero_termo = %s", (numero_termo,))
        termo = cur.fetchone()
        if not termo:
            return {"error": "Termo não encontrado"}, 404
            
        total_previsto = float(termo["total_previsto"] or 0)
        
        # Calcular total inserido
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
                    valor = float(str(valor_str).replace(',', '.').replace('R$', '').replace(' ', ''))
                    total_inserido += valor
                    
                    registros_para_inserir.append({
                        'numero_termo': numero_termo,
                        'rubrica': rubrica,
                        'quantidade': quantidade if quantidade != '-' else None,
                        'categoria_despesa': categoria,
                        'valor': valor,
                        'mes': mes
                    })
                except (ValueError, TypeError):
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
            db = get_db()
            cur.execute("DELETE FROM Parcerias_Despesas WHERE numero_termo = %s", (numero_termo,))
            for registro in registros_para_inserir:
                cur.execute("""
                    INSERT INTO Parcerias_Despesas 
                    (numero_termo, rubrica, quantidade, categoria_despesa, valor, mes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    registro['numero_termo'],
                    registro['rubrica'], 
                    registro['quantidade'],
                    registro['categoria_despesa'],
                    registro['valor'],
                    registro['mes']
                ))
            db.commit()
            cur.close()
            return {
                "message": f"Inseridas {len(registros_para_inserir)} despesas com sucesso",
                "total_inserido": total_inserido,
                "registros": len(registros_para_inserir)
            }, 201
        except psycopg2.IntegrityError as e:
            cur.close()
            db.rollback()
            if "parcerias_despesas_numero_termo_fkey" in str(e):
                return {"error": f"Termo '{numero_termo}' não encontrado na base de dados. Verifique se o número do termo está correto."}, 400
            elif "duplicate key" in str(e):
                return {"error": "Registro duplicado encontrado. Verifique se os dados já não foram inseridos anteriormente."}, 400
            else:
                return {"error": f"Erro de integridade dos dados: {str(e)}"}, 400
        except psycopg2.Error as e:
            cur.close()
            db.rollback()
            return {"error": f"Erro no banco de dados: {str(e)}"}, 500
        
    except psycopg2.IntegrityError as e:
        if "parcerias_despesas_numero_termo_fkey" in str(e):
            return {"error": f"Termo '{numero_termo}' não encontrado na base de dados. Verifique se o número do termo está correto."}, 400
        else:
            return {"error": f"Erro de integridade: {str(e)}"}, 400
    except psycopg2.Error as e:
        return {"error": f"Erro PostgreSQL: {str(e)}"}, 500
    except Exception as e:
        return {"error": f"Erro inesperado: {str(e)}"}, 500

@app.route('/api/despesas/<path:numero_termo>', methods=['GET'])
@login_required
def get_despesas_termo(numero_termo):
    """Retorna todas as despesas de um termo específico agrupadas por rubrica/categoria."""
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT rubrica, quantidade, categoria_despesa, mes, valor 
            FROM Parcerias_Despesas 
            WHERE numero_termo = %s 
            ORDER BY rubrica, categoria_despesa, mes
        """, (numero_termo,))
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

@app.route('/api/despesa/confirmar', methods=['POST'])
@login_required
def confirmar_despesa():
    """Confirma inserção mesmo com diferença no total."""
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        despesas = data.get('despesas', [])
        
        if not numero_termo or not despesas:
            return {"error": "numero_termo e despesas são obrigatórios"}, 400

        db = get_db()
        cur = get_cursor()
        
        registros_inseridos = 0

        # Antes de inserir, deletar registros existentes para substituir
        try:
            cur.execute("DELETE FROM Parcerias_Despesas WHERE numero_termo = %s", (numero_termo,))
        except psycopg2.Error as e:
            cur.close()
            return {"error": f"Erro ao limpar despesas antigas: {str(e)}"}, 500

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
                    valor = float(str(valor_str).replace(',', '.').replace('R$', '').replace(' ', ''))

                    cur.execute("""
                        INSERT INTO Parcerias_Despesas 
                        (numero_termo, rubrica, quantidade, categoria_despesa, valor, mes)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (numero_termo, rubrica, quantidade if quantidade != '-' else None, categoria, valor, mes))

                    registros_inseridos += 1
                except (ValueError, TypeError):
                    continue

        db.commit()
        cur.close()
        return {"message": f"Inseridas {registros_inseridos} despesas com sucesso"}, 201
        
    except psycopg2.IntegrityError as e:
        if 'conn' in locals():
            db.rollback()
        if 'cur' in locals():
            cur.close()
        if "parcerias_despesas_numero_termo_fkey" in str(e):
            return {"error": f"Termo '{numero_termo}' não encontrado na base de dados. Verifique se o número do termo está correto."}, 400
        elif "duplicate key" in str(e):
            return {"error": "Registro duplicado encontrado. Verifique se os dados já não foram inseridos anteriormente."}, 400
        else:
            return {"error": f"Erro de integridade dos dados: {str(e)}"}, 400
    except psycopg2.Error as e:
        if 'conn' in locals():
            db.rollback()
        if 'cur' in locals():
            cur.close()
        return {"error": f"Erro no banco de dados: {str(e)}"}, 500
    except Exception as e:
        return {"error": f"Erro: {str(e)}"}, 500

if __name__ == "__main__":
    app.run(debug=True)
