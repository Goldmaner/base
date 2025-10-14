"""
Blueprint de instruções (CRUD de instruções)
"""

from flask import Blueprint, render_template, request, jsonify
import psycopg2
from db import get_db, get_cursor
from utils import login_required

instrucoes_bp = Blueprint('instrucoes', __name__, url_prefix='/instrucoes')


@instrucoes_bp.route("/", methods=["GET"])
@login_required
def listar_view():
    """
    Página de listagem de instruções
    """
    cur = get_cursor()
    cur.execute("SELECT * FROM Instrucoes ORDER BY data_criacao DESC")
    instrucoes = cur.fetchall()
    cur.close()
    return render_template("instrucoes.html", instrucoes=instrucoes)


@instrucoes_bp.route("/api", methods=["GET"])
@login_required
def listar_api():
    """
    API para listar todas as instruções (JSON)
    """
    cur = get_cursor()
    cur.execute("SELECT * FROM Instrucoes ORDER BY data_criacao DESC")
    instrucoes = cur.fetchall()
    cur.close()
    # Converter para lista de dicionários para JSON
    return [dict(row) for row in instrucoes]


@instrucoes_bp.route("/api/<int:id>", methods=["DELETE"])
@login_required
def deletar(id):
    """
    API para deletar uma instrução por ID
    """
    try:
        db = get_db()
        cur = get_cursor()
        cur.execute("DELETE FROM Instrucoes WHERE id = %s", (id,))
        db.commit()
        cur.close()
        return {"message": "Instrução excluída com sucesso"}, 200
    except psycopg2.Error as e:
        return {"error": f"Erro ao excluir instrução: {str(e)}"}, 500


@instrucoes_bp.route("/api", methods=["POST"])
@login_required
def criar():
    """
    API para criar uma nova instrução
    """
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
