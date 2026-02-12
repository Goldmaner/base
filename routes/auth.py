"""
Blueprint de autenticação (login, logout) e gerenciamento de usuários
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_cursor, get_db
from utils import login_required
import secrets
import random
from datetime import datetime, timedelta
from email_utils import enviar_email, gerar_email_reset_senha

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
        cur.execute("""
            SELECT id, email, senha, tipo_usuario, acessos, d_usuario, session_token, data_ultimo_login 
            FROM gestao_pessoas.usuarios 
            WHERE email = %s
        """, (email_input,))
        user = cur.fetchone()
        
        if user is None:
            cur.close()
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("auth.login"))

        # senha armazenada é hash
        stored_hash = user["senha"]
        if check_password_hash(stored_hash, senha_input):
            # Verificar se há sessão ativa em outra máquina
            sessao_ativa = False
            if user["session_token"] and user["data_ultimo_login"]:
                # Considerar sessão ativa se último login foi há menos de 24 horas
                ultimo_login = user["data_ultimo_login"]
                if datetime.now() - ultimo_login < timedelta(hours=24):
                    sessao_ativa = True
            
            # Gerar novo session_token
            novo_token = secrets.token_urlsafe(32)
            
            # Atualizar session_token e data_ultimo_login no banco
            cur.execute("""
                UPDATE gestao_pessoas.usuarios 
                SET session_token = %s, data_ultimo_login = NOW()
                WHERE id = %s
            """, (novo_token, user["id"]))
            get_db().commit()
            cur.close()
            
            # sucesso: criar sessão
            session.clear()
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["tipo_usuario"] = user["tipo_usuario"]
            session["acessos"] = user["acessos"] or ""
            session["d_usuario"] = user["d_usuario"] or ""
            session["session_token"] = novo_token
            session["sessao_ativa_aviso"] = sessao_ativa  # Flag para mostrar aviso
            
            flash("Logado com sucesso.", "success")
            return redirect(url_for("main.index"))
        else:
            cur.close()
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
            SELECT id, email, tipo_usuario, d_usuario, data_criacao, acessos
            FROM gestao_pessoas.usuarios 
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
                "data_criacao": user["data_criacao"].isoformat() if user["data_criacao"] else None,
                "acessos": user["acessos"]
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
                INSERT INTO gestao_pessoas.usuarios (email, senha, tipo_usuario, d_usuario)
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


@auth_bp.route("/api/usuarios/<int:user_id>", methods=["GET"])
@login_required
def obter_usuario(user_id):
    """
    API para obter dados completos de um usuário específico (apenas para Agente Público)
    """
    # Verificar se é Agente Público
    if session.get("tipo_usuario") != "Agente Público":
        return jsonify({"erro": "Acesso negado"}), 403
    
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT id, email, tipo_usuario, d_usuario, data_criacao, acessos
            FROM gestao_pessoas.usuarios 
            WHERE id = %s
        """, (user_id,))
        
        usuario = cur.fetchone()
        cur.close()
        
        if not usuario:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        resultado = {
            "id": usuario["id"],
            "email": usuario["email"],
            "tipo_usuario": usuario["tipo_usuario"],
            "d_usuario": usuario["d_usuario"],
            "data_criacao": usuario["data_criacao"].isoformat() if usuario["data_criacao"] else None,
            "acessos": usuario["acessos"]
        }
        
        return jsonify(resultado), 200
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
        acessos = data.get("acessos", "").strip()
        
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
        
        if "acessos" in data:  # Permite enviar vazio para limpar
            updates.append("acessos = %s")
            params.append(acessos if acessos else None)
        
        if not updates:
            return jsonify({"erro": "Nenhum campo para atualizar"}), 400
        
        params.append(user_id)
        
        cur.execute(f"""
            UPDATE gestao_pessoas.usuarios 
            SET {', '.join(updates)}
            WHERE id = %s
        """, params)
        
        if cur.rowcount == 0:
            cur.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        get_db().commit()
        cur.close()
        
        # IMPORTANTE: Atualizar sessão do usuário se ele estiver logado
        # Isso permite que as permissões sejam aplicadas imediatamente
        if 'user_id' in session and session['user_id'] == user_id:
            # Recarregar dados do usuário na sessão atual
            cur = get_cursor()
            cur.execute("SELECT tipo_usuario, acessos, d_usuario FROM gestao_pessoas.usuarios WHERE id = %s", (user_id,))
            updated_user = cur.fetchone()
            cur.close()
            
            if updated_user:
                session['tipo_usuario'] = updated_user['tipo_usuario']
                session['acessos'] = updated_user['acessos'] or ""
                session['d_usuario'] = updated_user['d_usuario'] or ""
                print(f"[INFO] Sessão atualizada para usuário ID {user_id}")
        
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
        cur.execute("DELETE FROM gestao_pessoas.usuarios WHERE id = %s", (user_id,))
        
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
        
        if len(nova_senha) < 6:
            return jsonify({"erro": "Senha muito curta. Mínimo 6 caracteres"}), 400
        
        # Gerar hash da nova senha
        senha_hash = generate_password_hash(nova_senha)
        
        # Atualizar no banco
        cur = get_cursor()
        cur.execute("""
            UPDATE gestao_pessoas.usuarios 
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


@auth_bp.route("/api/solicitar-reset-senha", methods=["POST"])
def solicitar_reset_senha():
    """
    API pública para usuário solicitar reset de senha por e-mail
    Gera token de 6 dígitos e envia por e-mail
    """
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        
        if not email:
            return jsonify({"erro": "E-mail é obrigatório"}), 400
        
        # Buscar usuário
        cur = get_cursor()
        cur.execute("""
            SELECT id, email 
            FROM gestao_pessoas.usuarios 
            WHERE email = %s
        """, (email,))
        
        user = cur.fetchone()
        
        # IMPORTANTE: Não informar se e-mail existe ou não (segurança)
        # Sempre retorna sucesso mesmo se e-mail não existir
        if not user:
            cur.close()
            # Simular delay para evitar timing attack
            import time
            time.sleep(random.uniform(0.5, 1.5))
            return jsonify({"mensagem": "Se o e-mail estiver cadastrado, você receberá um código de reset em instantes."}), 200
        
        # Gerar token de 6 dígitos
        token = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Calcular expiração (30 minutos)
        expiracao = datetime.now() + timedelta(minutes=30)
        
        # Salvar token no banco (adicionar coluna reset_token e reset_token_expira na tabela)
        cur.execute("""
            UPDATE gestao_pessoas.usuarios 
            SET reset_token = %s, reset_token_expira = %s
            WHERE id = %s
        """, (token, expiracao, user["id"]))
        
        get_db().commit()
        
        # Enviar e-mail
        assunto, corpo_html, corpo_texto = gerar_email_reset_senha(user["email"], token)
        email_enviado = enviar_email(user["email"], assunto, corpo_html, corpo_texto)
        
        cur.close()
        
        if email_enviado:
            print(f"[RESET SENHA] ✅ E-mail enviado para {user['email']} com token {token}")
            return jsonify({"mensagem": "Se o e-mail estiver cadastrado, você receberá um código de reset em instantes."}), 200
        else:
            # Não revelar erro de e-mail ao usuário (segurança)
            print(f"[RESET SENHA] ❌ Erro ao enviar e-mail para {user['email']}")
            return jsonify({"mensagem": "Se o e-mail estiver cadastrado, você receberá um código de reset em instantes."}), 200
            
    except Exception as e:
        print(f"[ERRO RESET] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"erro": "Erro ao processar solicitação. Tente novamente."}), 500


@auth_bp.route("/api/validar-token-reset", methods=["POST"])
def validar_token_reset():
    """
    API pública para validar token de reset antes de permitir mudança de senha
    """
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        token = data.get("token", "").strip()
        
        if not email or not token:
            return jsonify({"erro": "E-mail e token são obrigatórios"}), 400
        
        # Buscar usuário com token válido
        cur = get_cursor()
        cur.execute("""
            SELECT id, email, reset_token, reset_token_expira 
            FROM gestao_pessoas.usuarios 
            WHERE email = %s AND reset_token = %s
        """, (email, token))
        
        user = cur.fetchone()
        cur.close()
        
        if not user:
            return jsonify({"erro": "Token inválido"}), 401
        
        # Verificar expiração
        if not user["reset_token_expira"] or datetime.now() > user["reset_token_expira"]:
            return jsonify({"erro": "Token expirado. Solicite um novo código."}), 401
        
        return jsonify({"mensagem": "Token válido", "email": user["email"]}), 200
        
    except Exception as e:
        print(f"[ERRO VALIDAR TOKEN] {str(e)}")
        return jsonify({"erro": "Erro ao validar token"}), 500


@auth_bp.route("/api/resetar-senha-com-token", methods=["POST"])
def resetar_senha_com_token():
    """
    API pública para resetar senha usando token enviado por e-mail
    """
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        token = data.get("token", "").strip()
        nova_senha = data.get("nova_senha", "").strip()
        confirma_senha = data.get("confirma_senha", "").strip()
        
        # Validações
        if not email or not token or not nova_senha or not confirma_senha:
            return jsonify({"erro": "Todos os campos são obrigatórios"}), 400
        
        if nova_senha != confirma_senha:
            return jsonify({"erro": "As senhas não coincidem"}), 400
        
        if len(nova_senha) < 4:
            return jsonify({"erro": "Senha muito curta. Mínimo 4 caracteres"}), 400
        
        # Buscar usuário com token válido
        cur = get_cursor()
        cur.execute("""
            SELECT id, email, reset_token, reset_token_expira 
            FROM gestao_pessoas.usuarios 
            WHERE email = %s AND reset_token = %s
        """, (email, token))
        
        user = cur.fetchone()
        
        if not user:
            cur.close()
            return jsonify({"erro": "Token inválido"}), 401
        
        # Verificar expiração
        if not user["reset_token_expira"] or datetime.now() > user["reset_token_expira"]:
            cur.close()
            return jsonify({"erro": "Token expirado. Solicite um novo código."}), 401
        
        # Gerar hash da nova senha
        senha_hash = generate_password_hash(nova_senha)
        
        # Atualizar senha e limpar token
        cur.execute("""
            UPDATE gestao_pessoas.usuarios 
            SET senha = %s, reset_token = NULL, reset_token_expira = NULL
            WHERE id = %s
        """, (senha_hash, user["id"]))
        
        get_db().commit()
        cur.close()
        
        print(f"[RESET SENHA] ✅ Senha alterada com sucesso para {user['email']}")
        return jsonify({"mensagem": "Senha alterada com sucesso! Você já pode fazer login com a nova senha."}), 200
        
    except Exception as e:
        get_db().rollback()
        print(f"[ERRO RESET SENHA] {str(e)}")
        return jsonify({"erro": "Erro ao resetar senha"}), 500


@auth_bp.route("/api/resetar-minha-senha", methods=["POST"])
def resetar_minha_senha():
    """
    API pública para usuário resetar sua própria senha usando senha temporária
    NÃO requer login - usado na tela de login
    """
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        senha_temporaria = data.get("senha_temporaria", "").strip()
        nova_senha = data.get("nova_senha", "").strip()
        confirma_senha = data.get("confirma_senha", "").strip()
        
        # Validações
        if not email or not senha_temporaria or not nova_senha or not confirma_senha:
            return jsonify({"erro": "Todos os campos são obrigatórios"}), 400
        
        if nova_senha != confirma_senha:
            return jsonify({"erro": "As senhas não coincidem"}), 400
        
        if len(nova_senha) < 6:
            return jsonify({"erro": "Senha muito curta. Mínimo 6 caracteres"}), 400
        
        # Buscar usuário
        cur = get_cursor()
        cur.execute("""
            SELECT id, senha 
            FROM gestao_pessoas.usuarios 
            WHERE email = %s
        """, (email,))
        
        user = cur.fetchone()
        
        if not user:
            cur.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Verificar se senha temporária está correta
        if not check_password_hash(user["senha"], senha_temporaria):
            cur.close()
            return jsonify({"erro": "Senha temporária incorreta"}), 401
        
        # Gerar hash da nova senha
        senha_hash = generate_password_hash(nova_senha)
        
        # Atualizar senha no banco
        cur.execute("""
            UPDATE gestao_pessoas.usuarios 
            SET senha = %s 
            WHERE id = %s
        """, (senha_hash, user["id"]))
        
        get_db().commit()
        cur.close()
        
        return jsonify({"mensagem": "Senha alterada com sucesso! Você já pode fazer login com a nova senha."}), 200
    except Exception as e:
        get_db().rollback()
        return jsonify({"erro": str(e)}), 500


@auth_bp.route("/api/verificar-sessao-ativa", methods=["GET"])
@login_required
def verificar_sessao_ativa():
    """
    API para verificar se há aviso de sessão ativa e limpar flag
    """
    sessao_ativa = session.pop("sessao_ativa_aviso", False)
    return jsonify({"sessao_ativa": sessao_ativa}), 200


@auth_bp.route("/api/alterar-minha-senha", methods=["POST"])
@login_required
def alterar_minha_senha():
    """
    API para usuário logado alterar sua própria senha
    """
    try:
        data = request.get_json()
        senha_atual = data.get("senha_atual", "").strip()
        nova_senha = data.get("nova_senha", "").strip()
        confirma_senha = data.get("confirma_senha", "").strip()
        
        # Validações
        if not senha_atual or not nova_senha or not confirma_senha:
            return jsonify({"erro": "Todos os campos são obrigatórios"}), 400
        
        if nova_senha != confirma_senha:
            return jsonify({"erro": "As senhas não coincidem"}), 400
        
        if len(nova_senha) < 6:
            return jsonify({"erro": "A nova senha deve ter no mínimo 6 caracteres"}), 400
        
        # Buscar senha atual do usuário
        user_id = session.get("user_id")
        cur = get_cursor()
        cur.execute("SELECT senha FROM gestao_pessoas.usuarios WHERE id = %s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            cur.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Verificar se senha atual está correta
        if not check_password_hash(user["senha"], senha_atual):
            cur.close()
            return jsonify({"erro": "Senha atual incorreta"}), 401
        
        # Gerar hash da nova senha
        senha_hash = generate_password_hash(nova_senha)
        
        # Atualizar senha no banco
        cur.execute("""
            UPDATE gestao_pessoas.usuarios 
            SET senha = %s 
            WHERE id = %s
        """, (senha_hash, user_id))
        
        get_db().commit()
        cur.close()
        
        return jsonify({"mensagem": "Senha alterada com sucesso!"}), 200
    except Exception as e:
        get_db().rollback()
        return jsonify({"erro": str(e)}), 500


@auth_bp.route("/api/usuarios-ativos", methods=["GET"])
@login_required
def usuarios_ativos():
    """
    API para listar usuários ativos nos últimos 15 minutos
    Apenas para Agente Público
    """
    # Verificar se é Agente Público
    if session.get("tipo_usuario") != "Agente Público":
        return jsonify({"erro": "Acesso negado"}), 403
    
    try:
        cur = get_cursor()
        
        # Buscar usuários com atividade nos últimos 15 minutos
        cur.execute("""
            SELECT 
                id,
                email,
                tipo_usuario,
                d_usuario,
                ultima_atividade,
                EXTRACT(EPOCH FROM (NOW() - ultima_atividade)) as segundos_inativo
            FROM gestao_pessoas.usuarios 
            WHERE ultima_atividade IS NOT NULL
              AND ultima_atividade > NOW() - INTERVAL '15 minutes'
            ORDER BY ultima_atividade DESC
        """)
        
        usuarios = cur.fetchall()
        cur.close()
        
        # Formatar resultado
        resultado = []
        for user in usuarios:
            segundos = int(user["segundos_inativo"]) if user["segundos_inativo"] else 0
            
            # Calcular tempo de forma legível
            if segundos < 60:
                tempo_ativo = "agora mesmo"
            elif segundos < 120:
                tempo_ativo = "1 min atrás"
            elif segundos < 3600:
                minutos = segundos // 60
                tempo_ativo = f"{minutos} min atrás"
            else:
                horas = segundos // 3600
                tempo_ativo = f"{horas}h atrás"
            
            resultado.append({
                "id": user["id"],
                "email": user["email"],
                "tipo_usuario": user["tipo_usuario"],
                "d_usuario": user["d_usuario"],
                "ultima_atividade": user["ultima_atividade"].isoformat() if user["ultima_atividade"] else None,
                "tempo_ativo": tempo_ativo,
                "segundos_inativo": segundos
            })
        
        return jsonify({
            "total": len(resultado),
            "usuarios": resultado
        }), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
