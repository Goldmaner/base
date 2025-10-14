"""
Blueprint principal (tela inicial, dashboard)
"""

from flask import Blueprint, render_template, session
from db import get_cursor
from utils import login_required

main_bp = Blueprint('main', __name__)


@main_bp.route("/", methods=["GET"])
@login_required
def index():
    """
    Tela inicial / Dashboard
    """
    # Buscar dados do usuário para exibir nome / tipo
    cur = get_cursor()
    cur.execute("SELECT id, email, tipo_usuario, data_criacao FROM usuarios WHERE id = %s", (session["user_id"],))
    user = cur.fetchone()
    cur.close()
    return render_template("tela_inicial.html", user=user)
