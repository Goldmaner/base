# app.py
from flask import Flask, g, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import check_password_hash
from functools import wraps

DB = "meu_banco.db"
SECRET_KEY = "troque_isso_por_uma_chave_aleatoria_e_secreta_em_producao"

app = Flask(__name__)
app.secret_key = SECRET_KEY

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

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
    db = get_db()
    cur = db.execute("SELECT id, email, tipo_usuario, data_criacao FROM usuarios WHERE id = ?", (session["user_id"],))
    user = cur.fetchone()
    return render_template("tela_inicial.html", user=user)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email_input = request.form["username"].strip().lower()
        senha_input = request.form["password"]

        db = get_db()
        cur = db.execute("SELECT id, email, senha, tipo_usuario FROM usuarios WHERE email = ?", (email_input,))
        user = cur.fetchone()
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

@app.route("/instrucoes", methods=["GET"])
@login_required
def instrucoes():
    db = get_db()
    # Buscar todas as instruções ordenadas pela data de criação
    cur = db.execute("SELECT * FROM Instrucoes ORDER BY data_criacao DESC")
    instrucoes = cur.fetchall()
    return render_template("instrucoes.html", instrucoes=instrucoes)

@app.route("/api/instrucoes", methods=["GET"])
@login_required
def listar_instrucoes():
    db = get_db()
    cur = db.execute("SELECT * FROM Instrucoes ORDER BY data_criacao DESC")
    instrucoes = cur.fetchall()
    # Converter para lista de dicionários para JSON
    return [dict(row) for row in instrucoes]

@app.route("/api/instrucoes/<int:id>", methods=["DELETE"])
@login_required
def deletar_instrucao(id):
    try:
        db = get_db()
        db.execute("DELETE FROM Instrucoes WHERE id = ?", (id,))
        db.commit()
        return {"message": "Instrução excluída com sucesso"}, 200
    except sqlite3.Error as e:
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
        try:
            db.execute(
                "INSERT INTO Instrucoes (titulo, texto, categoria) VALUES (?, ?, ?)",
                (titulo, texto, categoria)
            )
            db.commit()
        except sqlite3.Error as e:
            print(f"Erro SQL: {e}")  # Debug
            raise
        
        return {"message": "Instrução salva com sucesso"}, 201
    except sqlite3.Error as e:
        print(f"Erro SQLite: {e}")  # Debug
        return {"error": f"Erro ao salvar no banco de dados: {str(e)}"}, 500
    except Exception as e:
        print(f"Erro inesperado: {e}")  # Debug
        return {"error": f"Erro inesperado: {str(e)}"}, 500

if __name__ == "__main__":
    app.run(debug=True)
