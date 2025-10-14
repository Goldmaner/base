"""
Blueprint de autenticação (login, logout)
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from db import get_cursor
from utils import login_required

auth_bp = Blueprint('auth', __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Rota de login: exibe formulário (GET) ou processa autenticação (POST)
    """
    if request.method == "POST":
        email_input = request.form["username"].strip().lower()
        senha_input = request.form["password"]

        cur = get_cursor()
        cur.execute("SELECT id, email, senha, tipo_usuario FROM usuarios WHERE email = %s", (email_input,))
        user = cur.fetchone()
        cur.close()
        
        if user is None:
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("auth.login"))

        # senha armazenada é hash
        stored_hash = user["senha"]
        if check_password_hash(stored_hash, senha_input):
            # sucesso: criar sessão simples
            session.clear()
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["tipo_usuario"] = user["tipo_usuario"]
            flash("Logado com sucesso.", "success")
            return redirect(url_for("main.index"))
        else:
            flash("Senha incorreta.", "danger")
            return redirect(url_for("auth.login"))
    else:
        return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """
    Rota de logout: limpa sessão e redireciona para login
    """
    session.clear()
    flash("Você saiu.", "info")
    return redirect(url_for("auth.login"))
