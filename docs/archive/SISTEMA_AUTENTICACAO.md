# 🔐 Sistema de Autenticação e Segurança - FAF

## 📋 Resumo das Funcionalidades Implementadas

### ✅ 1. Reset de Senha pelo Usuário

**Localização**: Tela de Login (`/login`)

**Como funciona:**
1. Usuário clica em "Esqueci minha senha / Resetar senha" na tela de login
2. Modal abre com 4 campos:
   - E-mail do usuário
   - Senha temporária (fornecida pelo administrador)
   - Nova senha
   - Confirmação da nova senha
3. Sistema valida:
   - Se e-mail existe no banco
   - Se senha temporária está correta
   - Se nova senha tem mínimo 4 caracteres
   - Se confirmação coincide com nova senha
4. Senha é alterada e usuário pode fazer login imediatamente

**Endpoint**: `POST /api/resetar-minha-senha` (público, não requer login)

**Fluxo do Administrador:**
1. Admin acessa "Gerenciar Usuários" na tela inicial
2. Cria novo usuário com senha temporária (ex: "temp1234")
3. Informa senha temporária ao usuário por e-mail/telefone
4. Usuário acessa tela de login e reseta sua própria senha

---

### ✅ 2. Controle de Sessão Múltipla

**Comportamento tipo WhatsApp Web**

**Como funciona:**
1. Usuário faz login no computador A
2. Sistema registra `session_token` e `data_ultimo_login` no banco
3. Usuário tenta fazer login no computador B
4. Sistema detecta login ativo no computador A (últimas 24 horas)
5. Permite login no B mas mostra aviso:
   ```
   ⚠️ AVISO DE SESSÃO
   
   Você já estava logado em outro dispositivo/navegador.
   
   Sua sessão anterior foi substituída por este novo login.
   
   Se você não reconhece esta atividade, altere sua senha imediatamente.
   ```
6. Session do computador A continua funcionando até expirar (24h)

**Detalhes técnicos:**
- `session_token`: Token único gerado a cada login
- `data_ultimo_login`: Timestamp do último acesso
- Janela de detecção: 24 horas
- Aviso aparece uma única vez após login

**Endpoint**: `GET /api/verificar-sessao-ativa` (requer login)

---

### ✅ 3. Melhorias de Segurança

**Backend (`routes/auth.py`):**
- ✅ Importação de `secrets` para gerar tokens seguros
- ✅ Importação de `datetime`/`timedelta` para controle de tempo
- ✅ Registro de `session_token` no login
- ✅ Atualização de `data_ultimo_login` a cada acesso
- ✅ Endpoint público de reset de senha
- ✅ Endpoint de verificação de sessão ativa

**Frontend:**
- ✅ Modal de reset de senha na tela de login
- ✅ Validação de campos em tempo real
- ✅ Feedback visual de erros
- ✅ Alert automático de sessão ativa na tela inicial
- ✅ Ícones Bootstrap para melhor UX

---

## 🔧 Estrutura de Banco de Dados

**Tabela**: `gestao_pessoas.usuarios`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer | ID único do usuário |
| `email` | text | E-mail (username) |
| `senha` | text | Hash bcrypt da senha |
| `tipo_usuario` | text | "Agente Público", "Agente DAC", etc. |
| `d_usuario` | varchar | Departamento (máx. 20 chars) |
| `acessos` | text | Permissões separadas por `;` |
| `session_token` | text | **Token da sessão ativa** |
| `data_criacao` | timestamp | Data de criação do usuário |
| `data_ultimo_login` | timestamp | **Último login registrado** |

**Campos utilizados pela nova funcionalidade:**
- `session_token`: Gerado com `secrets.token_urlsafe(32)` a cada login
- `data_ultimo_login`: Atualizado com `NOW()` a cada login bem-sucedido

---

## 📍 Arquivos Modificados

### 1. `routes/auth.py`
**Alterações:**
- Adicionado imports: `secrets`, `datetime`, `timedelta`
- Modificada função `login()`:
  - Consulta `session_token` e `data_ultimo_login`
  - Verifica se há sessão ativa (< 24h)
  - Gera novo `session_token`
  - Registra flag `sessao_ativa_aviso` na sessão
- Adicionado endpoint `resetar_minha_senha()` (POST)
- Adicionado endpoint `verificar_sessao_ativa()` (GET)

### 2. `templates/login.html`
**Alterações:**
- Adicionado link "Esqueci minha senha"
- Adicionado modal de reset de senha
- Adicionado JavaScript para chamar API de reset
- Adicionado Bootstrap Icons
- Melhorado CSS para UX

### 3. `templates/tela_inicial.html`
**Alterações:**
- Adicionada função `verificarSessaoAtiva()` em JavaScript
- Chama API ao carregar página
- Mostra alert se flag `sessao_ativa_aviso` estiver ativa

---

## 🚀 Como Usar

### Para Administradores:

**1. Criar novo usuário com senha temporária:**
```
1. Acessar tela inicial
2. Clicar em "Gerenciar Usuários"
3. Criar usuário com:
   - E-mail: usuario@exemplo.com
   - Senha: temp1234 (exemplo)
   - Tipo: Agente DAC (ou outro)
4. Copiar senha e enviar para o usuário
```

**2. Resetar senha de usuário existente:**
```
1. Acessar "Gerenciar Usuários"
2. Clicar em "Resetar Senha" no usuário desejado
3. Digitar nova senha temporária
4. Informar ao usuário a senha temporária
```

### Para Usuários:

**1. Reset de senha (primeira vez ou esqueceu):**
```
1. Acessar tela de login
2. Clicar em "Esqueci minha senha / Resetar senha"
3. Preencher:
   - E-mail
   - Senha temporária (fornecida pelo admin)
   - Nova senha (mínimo 4 caracteres)
   - Confirmar nova senha
4. Clicar em "Alterar Senha"
5. Fazer login com a nova senha
```

**2. Aviso de sessão ativa:**
```
- Ao fazer login, se já estava logado em outro dispositivo:
  → Alert automático aparece informando
  → Sessão anterior continua ativa por 24h
  → Se não reconhece atividade, alterar senha imediatamente
```

---

## 🔒 Segurança

### Proteções Implementadas:

✅ **Senhas sempre em hash** (bcrypt via `werkzeug.security`)  
✅ **Session tokens aleatórios** (`secrets.token_urlsafe(32)`)  
✅ **Validação de senha mínima** (4 caracteres)  
✅ **Verificação de correspondência** (nova senha = confirmação)  
✅ **Detecção de sessão ativa** (últimas 24 horas)  
✅ **E-mail case-insensitive** (`.lower()` ao buscar)  
✅ **Endpoint público limitado** (apenas reset de senha)  

### Melhorias Futuras Sugeridas:

⚠️ **Força de senha**: Adicionar requisitos (maiúscula, número, símbolo)  
⚠️ **Limite de tentativas**: Bloquear após X tentativas falhas  
⚠️ **Token de recuperação**: E-mail com link temporário (mais seguro)  
⚠️ **2FA**: Autenticação de dois fatores (SMS/App)  
⚠️ **Log de acessos**: Histórico de IPs e dispositivos  
⚠️ **Expiração de sessão**: Forçar logout após X horas de inatividade  

---

## 🧪 Testes

### Cenário 1: Reset de senha com sucesso
```
1. Admin cria usuário com senha "temp123"
2. Usuário acessa login, clica em "Resetar senha"
3. Preenche: email, "temp123", "minhasenha456", "minhasenha456"
4. ✅ Mensagem: "Senha alterada com sucesso!"
5. Faz login com "minhasenha456"
6. ✅ Login bem-sucedido
```

### Cenário 2: Senha temporária incorreta
```
1. Usuário tenta resetar com senha errada
2. ❌ Mensagem: "Senha temporária incorreta"
```

### Cenário 3: Senhas não coincidem
```
1. Usuário digita senhas diferentes
2. ❌ Mensagem: "As senhas não coincidem"
```

### Cenário 4: Sessão múltipla
```
1. Usuário loga no PC-A às 10:00
2. Usuário loga no PC-B às 10:30
3. ⚠️ Alert aparece: "Você já estava logado..."
4. PC-A continua funcionando normalmente
5. Após 24 horas, sessão do PC-A expira naturalmente
```

---

## 📞 Suporte

**Dúvidas sobre implementação:**
- Verificar logs do Flask no terminal
- Testar endpoints via Postman/Thunder Client
- Conferir se colunas `session_token` e `data_ultimo_login` existem no banco

**Problemas comuns:**
- "Usuário não encontrado": Verificar se e-mail está correto (lowercase)
- "Senha temporária incorreta": Admin deve fornecer senha atual do banco
- Alert não aparece: Verificar console do navegador (F12) por erros

---

**Desenvolvido em**: Fevereiro 2026  
**Versão**: 1.0
