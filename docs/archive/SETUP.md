# Setup do Projeto FAF

## Arquivos Criados/Atualizados

### 1. `.env.example` ✅
- Template de configuração sem credenciais sensíveis
- Inclui todas as variáveis de ambiente necessárias
- Documentação inline para cada variável
- Instruções de uso

### 2. `.gitignore` ✅
- Atualizado para ignorar `.env` e variações
- **Exceção**: Permite commit de `.env.example`
- Protege credenciais sensíveis

### 3. `README.md` ✅
- Seção completa de "Configuração do Ambiente"
- Instruções passo a passo para setup
- Documentação de arquitetura de banco dual
- Seção de troubleshooting
- Tecnologias utilizadas
- Scripts úteis

## Para Novos Desenvolvedores

### Setup Rápido:

```bash
# 1. Clone o repositório
git clone https://github.com/Goldmaner/FAF.git
cd FAF

# 2. Crie ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Instale dependências
pip install -r requirements.txt

# 4. Configure ambiente
cp .env.example .env
# Edite .env com suas credenciais

# 5. Execute
python app.py
```

### Variáveis de Ambiente Necessárias:

**Banco LOCAL (desenvolvimento):**
- `DB_LOCAL_HOST`: localhost
- `DB_LOCAL_PORT`: 5432
- `DB_LOCAL_NAME`: nome_do_banco
- `DB_LOCAL_USER`: usuario_postgres
- `DB_LOCAL_PASSWORD`: senha

**Banco RAILWAY (produção):**
- `DB_RAILWAY_HOST`: fornecido pelo Railway
- `DB_RAILWAY_PORT`: 5432
- `DB_RAILWAY_NAME`: railway
- `DB_RAILWAY_USER`: postgres
- `DB_RAILWAY_PASSWORD`: fornecido pelo Railway

**Flask:**
- `SECRET_KEY`: chave secreta para sessões

## Detecção Automática de Ambiente

O código detecta automaticamente em qual ambiente está rodando:

- **LOCAL**: Se `RAILWAY_ENVIRONMENT` NÃO existe
- **RAILWAY**: Se `RAILWAY_ENVIRONMENT` existe (definida automaticamente)

Não é necessário mudar código ou configuração ao fazer deploy!

## Comandos Git Úteis

```bash
# Verificar status
git status

# Adicionar arquivos (incluindo .env.example)
git add .env.example .gitignore README.md

# Commit
git commit -m "docs: Adiciona .env.example e atualiza documentação"

# Push para GitHub
git push origin main
```

## Importante

⚠️ **NUNCA** faça commit do arquivo `.env` com credenciais reais!

✅ O `.env.example` é seguro para commit (sem credenciais)

✅ Outros desenvolvedores copiarão `.env.example` para `.env` e preencherão suas próprias credenciais
