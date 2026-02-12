# 📧 Guia de Configuração de E-mail - Reset de Senha

## 🎯 Visão Geral

Sistema de reset de senha por e-mail implementado com:
- ✅ Token de 6 dígitos enviado por e-mail
- ✅ Expiração automática em 30 minutos
- ✅ Botão "mostrar senha" nos campos
- ✅ Interface em 2 passos (solicitar código → resetar senha)
- ✅ Segurança contra timing attacks
- ✅ Compatibilidade com Gmail, Outlook, servidores próprios

---

## 📦 Pré-requisitos

### 1. Banco de Dados

Execute o script SQL para adicionar as colunas necessárias:

```bash
psql -U postgres -d projeto_parcerias -f scripts/adicionar_colunas_reset_senha.sql
```

**Ou execute manualmente no pgAdmin:**

```sql
ALTER TABLE gestao_pessoas.usuarios 
ADD COLUMN IF NOT EXISTS reset_token VARCHAR(6);

ALTER TABLE gestao_pessoas.usuarios 
ADD COLUMN IF NOT EXISTS reset_token_expira TIMESTAMP WITHOUT TIME ZONE;
```

### 2. Configurar E-mail

Edite o arquivo `.env` (copie de `.env.example` se não existir):

```bash
cp .env.example .env
```

---

## 🔧 Configuração por Provedor

### Gmail (Recomendado para testes)

**Passo 1:** Ativar verificação em 2 etapas
1. Acesse https://myaccount.google.com/security
2. Clique em "Verificação em duas etapas"
3. Siga as instruções para ativar

**Passo 2:** Criar senha de app
1. Acesse https://myaccount.google.com/apppasswords
2. Selecione "App: Mail" e "Dispositivo: Outro"
3. Digite "FAF Sistema" como nome
4. Copie a senha de 16 caracteres gerada

**Passo 3:** Configurar no `.env`

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=xxxx xxxx xxxx xxxx
MAIL_DEFAULT_SENDER=seu-email@gmail.com
```

⚠️ **IMPORTANTE:** Use a senha de app de 16 caracteres, NÃO sua senha normal do Gmail!

---

### Outlook / Hotmail

```env
MAIL_SERVER=smtp-mail.outlook.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=seu-email@outlook.com
MAIL_PASSWORD=sua-senha-normal
MAIL_DEFAULT_SENDER=seu-email@outlook.com
```

---

### Office 365 / Microsoft 365

```env
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=seu-email@empresa.com
MAIL_PASSWORD=sua-senha-corporativa
MAIL_DEFAULT_SENDER=noreply@empresa.com
```

---

### Servidor SMTP Próprio

**Com TLS (porta 587):**
```env
MAIL_SERVER=mail.seu-dominio.com.br
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=noreply@seu-dominio.com.br
MAIL_PASSWORD=senha-do-email
MAIL_DEFAULT_SENDER=noreply@seu-dominio.com.br
```

**Com SSL (porta 465):**
```env
MAIL_SERVER=mail.seu-dominio.com.br
MAIL_PORT=465
MAIL_USE_TLS=False
MAIL_USERNAME=noreply@seu-dominio.com.br
MAIL_PASSWORD=senha-do-email
MAIL_DEFAULT_SENDER=noreply@seu-dominio.com.br
```

---

## 🧪 Testando a Configuração

### Teste 1: Verificar Configurações

Crie um script `test_email.py`:

```python
from email_utils import enviar_email

# Enviar e-mail de teste
resultado = enviar_email(
    destinatario="seu-email@gmail.com",
    assunto="Teste de Configuração SMTP",
    corpo_html="<h1>Teste OK!</h1><p>E-mail configurado corretamente.</p>",
    corpo_texto="Teste OK! E-mail configurado corretamente."
)

if resultado:
    print("✅ E-mail enviado com sucesso!")
else:
    print("❌ Erro ao enviar e-mail. Verifique as configurações.")
```

Execute:
```bash
python test_email.py
```

### Teste 2: Reset de Senha Completo

1. Acesse a tela de login
2. Clique em "Esqueci minha senha"
3. Digite um e-mail cadastrado
4. Clique em "Enviar Código por E-mail"
5. Verifique sua caixa de entrada (e spam)
6. Digite o código de 6 dígitos recebido
7. Defina nova senha e confirme
8. Faça login com a nova senha

---

## 🔍 Troubleshooting

### Erro: "Configurações de e-mail não definidas"

**Causa:** Variáveis `MAIL_USERNAME` ou `MAIL_PASSWORD` vazias

**Solução:**
1. Verifique se o arquivo `.env` existe
2. Confirme que as variáveis estão preenchidas
3. Reinicie o servidor Flask

---

### Erro: "Authentication failed" (Gmail)

**Causa:** Usando senha normal em vez de senha de app

**Solução:**
1. Ative verificação em 2 etapas
2. Crie senha de app específica
3. Use a senha de 16 caracteres no `.env`

---

### Erro: "Connection refused" ou "Timeout"

**Causas possíveis:**
- Firewall bloqueando porta 587/465
- Servidor SMTP incorreto
- Porta incorreta

**Solução:**
1. Verifique se a porta está liberada no firewall
2. Confirme o servidor SMTP do provedor
3. Teste com `telnet mail.servidor.com 587`

---

### E-mail não chega na caixa de entrada

**Verificações:**
1. ✅ Verifique a pasta SPAM/Lixo eletrônico
2. ✅ Confirme que o e-mail está cadastrado no banco
3. ✅ Verifique logs do Flask para mensagem de sucesso
4. ✅ Aguarde alguns minutos (atraso do provedor)

**Logs esperados:**
```
[EMAIL] Conectando ao servidor smtp.gmail.com:587...
[EMAIL] Autenticando como seu-email@gmail.com...
[EMAIL] Enviando e-mail para usuario@exemplo.com...
[EMAIL] ✅ E-mail enviado com sucesso para usuario@exemplo.com
[RESET SENHA] ✅ E-mail enviado para usuario@exemplo.com com token 123456
```

---

## 🔐 Segurança

### Proteções Implementadas:

✅ **Token único por usuário:** Cada solicitação gera novo token  
✅ **Expiração automática:** 30 minutos de validade  
✅ **Limpeza após uso:** Token deletado ao resetar senha  
✅ **Sem revelação de e-mails:** Resposta genérica mesmo se e-mail não existir  
✅ **Timing attack protection:** Delay aleatório quando e-mail não existe  
✅ **Token numérico:** 6 dígitos = 1 milhão de combinações  
✅ **Logs detalhados:** Rastreamento de tentativas  

### Recomendações Adicionais:

⚠️ **Limite de tentativas:** Considere bloquear após 5 tentativas falhas  
⚠️ **Rate limiting:** Limitar 3 solicitações de código por hora  
⚠️ **CAPTCHA:** Adicionar reCAPTCHA na solicitação de código  
⚠️ **Notificação de segurança:** Enviar e-mail quando senha for alterada  
⚠️ **Log de auditoria:** Registrar todas as tentativas de reset  

---

## 🎨 Interface do Usuário

### Fluxo Completo:

**1. Tela de Login**
```
[Campo: E-mail]
[Campo: Senha] [👁️ Mostrar]
[Botão: Entrar]

🔑 Esqueci minha senha / Resetar senha
```

**2. Modal - Passo 1 (Solicitar Código)**
```
📧 Passo 1: Digite seu e-mail para receber código

[Campo: E-mail]
[Botão: Enviar Código por E-mail]

Já tem código? Clique aqui
```

**3. E-mail Recebido**
```
🔐 Reset de Senha
Módulo de Análise - FAF

Use o código abaixo:

┌─────────────┐
│   123456    │
└─────────────┘
Válido por 30 minutos

[Instruções de uso]
```

**4. Modal - Passo 2 (Resetar Senha)**
```
✅ Passo 2: Digite o código e sua nova senha

[Campo: E-mail]
[Campo: Código (6 dígitos)] 
[Campo: Nova Senha] [👁️]
[Campo: Confirmar Senha] [👁️]

[Botão: Alterar Senha]

← Voltar / Solicitar novo código
```

---

## 📊 Estatísticas e Monitoramento

### Logs a Observar:

```bash
# Sucesso completo
[EMAIL] ✅ E-mail enviado com sucesso para usuario@exemplo.com
[RESET SENHA] ✅ Senha alterada com sucesso para usuario@exemplo.com

# Tentativas com token inválido
[ERRO VALIDAR TOKEN] Token inválido para usuario@exemplo.com

# E-mail não cadastrado (protegido - não revela)
[RESET SENHA] Tentativa com e-mail não cadastrado: naoexiste@exemplo.com
```

### Queries Úteis:

```sql
-- Ver usuários com token ativo
SELECT email, reset_token, reset_token_expira
FROM gestao_pessoas.usuarios
WHERE reset_token IS NOT NULL;

-- Limpar tokens expirados manualmente
UPDATE gestao_pessoas.usuarios
SET reset_token = NULL, reset_token_expira = NULL
WHERE reset_token_expira < NOW();

-- Contar tokens ativos
SELECT COUNT(*) as tokens_ativos
FROM gestao_pessoas.usuarios
WHERE reset_token IS NOT NULL 
  AND reset_token_expira > NOW();
```

---

## 🚀 Produção

### Checklist antes de deploy:

- [ ] Colunas `reset_token` e `reset_token_expira` criadas
- [ ] Variáveis de e-mail configuradas no `.env` de produção
- [ ] Senha de app criada (Gmail) ou credenciais válidas
- [ ] Teste de envio de e-mail realizado
- [ ] Logs de e-mail monitorados
- [ ] Backup do banco antes das alterações
- [ ] Documentação atualizada para equipe
- [ ] Treinamento de usuários sobre nova funcionalidade

---

## 📝 Notas Finais

- Sistema mantém compatibilidade com método antigo (senha temporária do admin)
- Código de 6 dígitos é mais seguro que senha temporária genérica
- E-mail só é enviado se usuário existir (mas resposta não revela isso)
- Token expira automaticamente após 30 minutos
- Botão "mostrar senha" melhora UX sem comprometer segurança

**Desenvolvido em:** Fevereiro 2026  
**Versão:** 2.0
