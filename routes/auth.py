"""
Blueprint de autenticação (login, logout) e gerenciamento de usuários
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_cursor, get_db
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


# ========== APIs DE GERENCIAMENTO DE USUÁRIOS ==========

@auth_bp.route("/api/usuarios", methods=["GET"])
@login_required
def listar_usuarios():
    """
    API para listar todos os usuários (apenas para Agente Público)
    """
    print(f"[DEBUG] Listar usuários - Tipo do usuário logado: {session.get('tipo_usuario')}")
    
    # Verificar se é Agente Público
    if session.get("tipo_usuario") != "Agente Público":
        print(f"[DEBUG] Acesso negado para tipo: {session.get('tipo_usuario')}")
        return jsonify({"erro": "Acesso negado"}), 403
    
    try:
        print("[DEBUG] Executando query para listar usuários...")
        cur = get_cursor()
        cur.execute("""
            SELECT id, email, tipo_usuario, d_usuario, data_criacao 
            FROM usuarios 
            ORDER BY data_criacao DESC
        """)
        usuarios = cur.fetchall()
        cur.close()
        
        print(f"[DEBUG] {len(usuarios)} usuários encontrados")
        
        # Converter para lista de dicionários
        resultado = []
        for user in usuarios:
            resultado.append({
                "id": user["id"],
                "email": user["email"],
                "tipo_usuario": user["tipo_usuario"],
                "d_usuario": user["d_usuario"],
                "data_criacao": user["data_criacao"].isoformat() if user["data_criacao"] else None
            })
        
        print(f"[DEBUG] Retornando {len(resultado)} usuários")
        return jsonify(resultado), 200
    except Exception as e:
        print(f"[ERRO] Erro ao listar usuários: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500


@auth_bp.route("/api/usuarios", methods=["POST"])
@login_required
def criar_usuario():
    """
    API para criar novo usuário (apenas para Agente Público)
    """
    # Verificar se é Agente Público
    if session.get("tipo_usuario") != "Agente Público":
        return jsonify({"erro": "Acesso negado"}), 403
    
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        senha = data.get("senha", "").strip()
        tipo_usuario = data.get("tipo_usuario", "").strip()
        d_usuario = data.get("d_usuario", "").strip()
        
        # Validações
        if not email or not senha or not tipo_usuario:
            return jsonify({"erro": "Email, senha e tipo de usuário são obrigatórios"}), 400
        
        if d_usuario and len(d_usuario) > 20:
            return jsonify({"erro": "Departamento do usuário deve ter no máximo 20 caracteres"}), 400
        
        tipos_validos = ["Agente Público", "Agente DAC", "Agente DGP", "Agente DP", "Externo"]
        if tipo_usuario not in tipos_validos:
            return jsonify({"erro": "Tipo de usuário inválido"}), 400
        
        # Gerar hash da senha
        senha_hash = generate_password_hash(senha)
        
        # Inserir no banco
        cur = get_cursor()
        try:
            cur.execute("""
                INSERT INTO usuarios (email, senha, tipo_usuario, d_usuario)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (email, senha_hash, tipo_usuario, d_usuario if d_usuario else None))
            
            novo_id = cur.fetchone()["id"]
            get_db().commit()
            cur.close()
            
            return jsonify({
                "mensagem": "Usuário criado com sucesso",
                "id": novo_id,
                "email": email
            }), 201
        except Exception as e:
            get_db().rollback()
            cur.close()
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                return jsonify({"erro": "E-mail já cadastrado"}), 400
            raise
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@auth_bp.route("/api/usuarios/<int:user_id>", methods=["PUT"])
@login_required
def atualizar_usuario(user_id):
    """
    API para atualizar tipo de usuário e departamento (apenas para Agente Público)
    """
    # Verificar se é Agente Público
    if session.get("tipo_usuario") != "Agente Público":
        return jsonify({"erro": "Acesso negado"}), 403
    
    try:
        data = request.get_json()
        tipo_usuario = data.get("tipo_usuario", "").strip()
        d_usuario = data.get("d_usuario", "").strip()
        
        # Validações
        tipos_validos = ["Agente Público", "Agente DAC", "Agente DGP", "Agente DP", "Externo"]
        if tipo_usuario and tipo_usuario not in tipos_validos:
            return jsonify({"erro": "Tipo de usuário inválido"}), 400
        
        if d_usuario and len(d_usuario) > 20:
            return jsonify({"erro": "Departamento do usuário deve ter no máximo 20 caracteres"}), 400
        
        # Atualizar no banco
        cur = get_cursor()
        
        # Construir query dinâmica baseado nos campos fornecidos
        updates = []
        params = []
        
        if tipo_usuario:
            updates.append("tipo_usuario = %s")
            params.append(tipo_usuario)
        
        if "d_usuario" in data:  # Permite enviar vazio para limpar
            updates.append("d_usuario = %s")
            params.append(d_usuario if d_usuario else None)
        
        if not updates:
            return jsonify({"erro": "Nenhum campo para atualizar"}), 400
        
        params.append(user_id)
        
        cur.execute(f"""
            UPDATE usuarios 
            SET {', '.join(updates)}
            WHERE id = %s
        """, params)
        
        if cur.rowcount == 0:
            cur.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        get_db().commit()
        cur.close()
        
        return jsonify({"mensagem": "Usuário atualizado com sucesso"}), 200
    except Exception as e:
        get_db().rollback()
        return jsonify({"erro": str(e)}), 500


@auth_bp.route("/api/usuarios/<int:user_id>", methods=["DELETE"])
@login_required
def excluir_usuario(user_id):
    """
    API para excluir usuário (apenas para Agente Público)
    """
    # Verificar se é Agente Público
    if session.get("tipo_usuario") != "Agente Público":
        return jsonify({"erro": "Acesso negado"}), 403
    
    # Não permitir excluir a si mesmo
    if session.get("user_id") == user_id:
        return jsonify({"erro": "Você não pode excluir sua própria conta"}), 400
    
    try:
        cur = get_cursor()
        cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
        
        if cur.rowcount == 0:
            cur.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        get_db().commit()
        cur.close()
        
        return jsonify({"mensagem": "Usuário excluído com sucesso"}), 200
    except Exception as e:
        get_db().rollback()
        return jsonify({"erro": str(e)}), 500


@auth_bp.route("/api/usuarios/<int:user_id>/resetar-senha", methods=["PUT"])
@login_required
def resetar_senha(user_id):
    """
    API para resetar senha de usuário (apenas para Agente Público)
    """
    # Verificar se é Agente Público
    if session.get("tipo_usuario") != "Agente Público":
        return jsonify({"erro": "Acesso negado"}), 403
    
    try:
        data = request.get_json()
        nova_senha = data.get("nova_senha", "").strip()
        
        # Validações
        if not nova_senha:
            return jsonify({"erro": "Nova senha é obrigatória"}), 400
        
        if len(nova_senha) < 4:
            return jsonify({"erro": "Senha muito curta. Mínimo 4 caracteres"}), 400
        
        # Gerar hash da nova senha
        senha_hash = generate_password_hash(nova_senha)
        
        # Atualizar no banco
        cur = get_cursor()
        cur.execute("""
            UPDATE usuarios 
            SET senha = %s 
            WHERE id = %s
        """, (senha_hash, user_id))
        
        if cur.rowcount == 0:
            cur.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        get_db().commit()
        cur.close()
        
        return jsonify({"mensagem": "Senha resetada com sucesso"}), 200
    except Exception as e:
        get_db().rollback()
        return jsonify({"erro": str(e)}), 500
