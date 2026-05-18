"""
Utilitários para envio de e-mail
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER


def enviar_email(destinatario, assunto, corpo_html, corpo_texto=None):
    """
    Envia e-mail via SMTP
    
    Args:
        destinatario (str): E-mail do destinatário
        assunto (str): Assunto do e-mail
        corpo_html (str): Corpo do e-mail em HTML
        corpo_texto (str, optional): Versão texto simples (fallback)
    
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    try:
        # Validar configurações
        if not MAIL_USERNAME or not MAIL_PASSWORD:
            print("[ERRO EMAIL] Configurações de e-mail não definidas (MAIL_USERNAME/MAIL_PASSWORD)")
            return False
        
        # Criar mensagem
        msg = MIMEMultipart('alternative')
        msg['From'] = MAIL_DEFAULT_SENDER
        msg['To'] = destinatario
        msg['Subject'] = assunto
        
        # Adicionar versão texto (se fornecida)
        if corpo_texto:
            part1 = MIMEText(corpo_texto, 'plain', 'utf-8')
            msg.attach(part1)
        
        # Adicionar versão HTML
        part2 = MIMEText(corpo_html, 'html', 'utf-8')
        msg.attach(part2)
        
        # Conectar ao servidor SMTP
        print(f"[EMAIL] Conectando ao servidor {MAIL_SERVER}:{MAIL_PORT}...")
        
        if MAIL_USE_TLS:
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT)
        
        # Login
        print(f"[EMAIL] Autenticando como {MAIL_USERNAME}...")
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        
        # Enviar
        print(f"[EMAIL] Enviando e-mail para {destinatario}...")
        server.send_message(msg)
        server.quit()
        
        print(f"[EMAIL] ✅ E-mail enviado com sucesso para {destinatario}")
        return True
        
    except Exception as e:
        print(f"[ERRO EMAIL] Falha ao enviar e-mail: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def gerar_email_reset_senha(email_usuario, token):
    """
    Gera HTML do e-mail de reset de senha
    
    Args:
        email_usuario (str): E-mail do usuário
        token (str): Token de reset
    
    Returns:
        tuple: (assunto, corpo_html, corpo_texto)
    """
    assunto = "Reset de Senha - Módulo de Análise FAF"
    
    corpo_html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 50px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ padding: 30px; }}
            .token-box {{ background: #f8f9fa; border: 2px dashed #667eea; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }}
            .token {{ font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 3px; font-family: 'Courier New', monospace; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Reset de Senha</h1>
                <p>Módulo de Análise de Contas - FAF</p>
            </div>
            <div class="content">
                <p>Olá,</p>
                <p>Você solicitou o reset de senha para a conta associada ao e-mail <strong>{email_usuario}</strong>.</p>
                
                <p>Use o código abaixo para redefinir sua senha:</p>
                
                <div class="token-box">
                    <div class="token">{token}</div>
                    <p style="margin: 10px 0 0 0; color: #666; font-size: 14px;">Código válido por 30 minutos</p>
                </div>
                
                <p><strong>Como usar:</strong></p>
                <ol>
                    <li>Acesse a tela de login do sistema</li>
                    <li>Clique em "Esqueci minha senha"</li>
                    <li>Digite este código de 6 dígitos</li>
                    <li>Defina sua nova senha</li>
                </ol>
                
                <div class="warning">
                    <strong>⚠️ Atenção:</strong><br>
                    • Este código expira em 30 minutos<br>
                    • Se você não solicitou este reset, ignore este e-mail<br>
                    • Não compartilhe este código com ninguém
                </div>
            </div>
            <div class="footer">
                <p>Este é um e-mail automático. Não responda.</p>
                <p>Módulo de Análise de Contas - Fundo de Apoio à Família</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    corpo_texto = f"""
    Reset de Senha - Módulo de Análise FAF
    
    Olá,
    
    Você solicitou o reset de senha para a conta: {email_usuario}
    
    Código de Reset: {token}
    
    Válido por: 30 minutos
    
    Como usar:
    1. Acesse a tela de login
    2. Clique em "Esqueci minha senha"
    3. Digite o código de 6 dígitos
    4. Defina sua nova senha
    
    ⚠️ Se você não solicitou este reset, ignore este e-mail.
    
    ---
    Módulo de Análise de Contas - FAF
    """
    
    return assunto, corpo_html, corpo_texto
