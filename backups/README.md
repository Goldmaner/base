# Pasta de Backups do Sistema FAF

Esta pasta contém backups do banco de dados PostgreSQL do sistema FAF (Gestão de Orçamento e Parcerias).

## 📦 Sobre os Backups

Os arquivos de backup são criados no formato SQL usando `pg_dump` e incluem:
- ✅ Toda a estrutura do banco (schemas, tabelas, sequences)
- ✅ Todos os dados das tabelas
- ✅ Comandos `DROP IF EXISTS` antes de cada `CREATE`
- ✅ Formato legível (plain SQL)

### Formato dos Arquivos

```
backup_faf_YYYYMMDD_HHMMSS.sql
```

Exemplo: `backup_faf_20251103_165713.sql`
- Data: 03/11/2025
- Hora: 16:57:13

## 🔧 Como Criar um Backup

### Opção 1: Script Python (Recomendado)

```bash
python scripts/fazer_backup.py
```

**Vantagens:**
- Lê credenciais automaticamente do `.env`
- Mostra listagem dos últimos backups
- Mensagens de erro detalhadas

### Opção 2: Script Batch (Windows)

```bash
fazer_backup.bat
```

**Nota:** Pode solicitar senha se `PGPASSWORD` não estiver configurada.

### Opção 3: Comando Manual

```bash
pg_dump -h localhost -p 5432 -U postgres -F p -f backups/backup_manual.sql --clean --if-exists --no-owner --no-privileges projeto_parcerias
```

## 🔄 Como Restaurar um Backup

### Atenção: Restaurar um backup irá **SOBRESCREVER** todos os dados atuais!

### Passo 1: Fazer backup de segurança (opcional mas recomendado)

```bash
python scripts/fazer_backup.py
```

### Passo 2: Restaurar o backup desejado

```bash
psql -h localhost -p 5432 -U postgres -d projeto_parcerias -f backups/backup_faf_20251103_165713.sql
```

### Passo 3: Verificar restauração

Conecte ao banco e verifique se os dados foram restaurados:

```bash
psql -h localhost -p 5432 -U postgres -d projeto_parcerias
```

```sql
-- Verificar tabelas
\dt public.*
\dt categoricas.*

-- Verificar quantidade de registros
SELECT COUNT(*) FROM public.parcerias;
SELECT COUNT(*) FROM public.o_orcamento;
```

## 📋 Backups Existentes

Atualmente existem **2 backups** nesta pasta:

1. `backup_faf_20251030_141449.sql` - 30/10/2025 14:14:49
2. `backup_faf_20251103_165713.sql` - 03/11/2025 16:57:13

## ⚙️ Configuração

### Requisitos

- PostgreSQL instalado (com `pg_dump` e `psql` no PATH)
- Python 3.8+ (para o script Python)
- Arquivo `.env` configurado com credenciais do banco

### Variáveis de Ambiente (.env)

```env
DB_HOST=localhost
DB_PORT=5432
DB_DATABASE=projeto_parcerias
DB_USER=postgres
DB_PASSWORD=sua_senha_aqui
```

### Adicionar PostgreSQL ao PATH (Windows)

Se o comando `pg_dump` não for encontrado:

1. Painel de Controle → Sistema → Configurações avançadas
2. Variáveis de Ambiente
3. Editar variável `PATH`
4. Adicionar: `C:\Program Files\PostgreSQL\17\bin`

## 🗑️ Limpeza de Backups Antigos

Para economizar espaço, você pode deletar backups antigos manualmente:

```bash
# Manter apenas os últimos 10 backups
# (No Windows, use o explorador de arquivos)
```

Ou criar um script de limpeza automática se necessário.

## 🚨 Importante

- ⚠️ **NUNCA** faça commit de backups no Git (arquivo muito grande)
- ⚠️ Backups contêm dados sensíveis - mantenha em local seguro
- ✅ Teste a restauração periodicamente para garantir integridade
- ✅ Mantenha backups em múltiplos locais (local + nuvem)
- ✅ Faça backup ANTES de migrações ou alterações grandes

## 📞 Suporte

Em caso de problemas com backup/restauração:

1. Verifique logs de erro do PostgreSQL
2. Confirme que o serviço PostgreSQL está rodando
3. Teste conexão: `psql -h localhost -U postgres -d projeto_parcerias`
4. Verifique permissões do usuário do banco

---

**Última atualização:** 05/11/2025

│   └── MELHORIAS_UX_FORMULARIO.md
│
└── __pycache__/          # Arquivos temporários do Python
```

## Principais Funcionalidades

- **Gestão de Orçamento:** Cadastro, edição e visualização de despesas por mês, com filtros e paginação.
- **Dicionário de Categorias:** Padronização em massa de categorias de despesas, busca global, edição em lote e visualização de termos.
- **Parcerias:** Cadastro e acompanhamento de parcerias, integração com despesas.
- **Sistema Inteligente de UPSERT:** Salva apenas as diferenças, evitando duplicações.
- **Batch INSERT:** Performance otimizada com inserções em lote.
- **Importação/Exportação:** Suporte a importação/exportação de dados via Excel/CSV.
- **Integração com PostgreSQL:** Persistência dos dados em banco relacional (LOCAL + RAILWAY).
- **Interface Moderna:** Utilização de Bootstrap 5, modals, progress bars, feedback visual e responsividade.

## Requisitos

- Python 3.8+
- PostgreSQL 12+
- pip (gerenciador de pacotes Python)

## Configuração do Ambiente

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/FAF.git
cd FAF
```

### 2. Crie e ative um ambiente virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Copie o arquivo de exemplo e preencha com suas credenciais:
```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações:

```env
# Banco LOCAL (desenvolvimento)
DB_LOCAL_HOST=localhost
DB_LOCAL_PORT=5432
DB_LOCAL_NAME=faf_db
DB_LOCAL_USER=postgres
DB_LOCAL_PASSWORD=sua_senha

# Banco RAILWAY (produção)
DB_RAILWAY_HOST=seu-host.railway.app
DB_RAILWAY_PORT=5432
DB_RAILWAY_NAME=railway
DB_RAILWAY_USER=postgres
DB_RAILWAY_PASSWORD=sua_senha_railway

# Flask
SECRET_KEY=sua-chave-secreta-aqui
```

### 5. Configure o banco de dados PostgreSQL

Crie o banco de dados local:
```sql
CREATE DATABASE faf_db;
```

Execute os scripts de criação de tabelas (se houver):
```bash
psql -U postgres -d faf_db -f schema.sql
```

## Como Executar

### Desenvolvimento (Local)
```bash
python app.py
```

A aplicação estará disponível em: [http://localhost:8080](http://localhost:8080)

### Produção (Railway)

O Railway detecta automaticamente a variável `RAILWAY_ENVIRONMENT` e usa o banco de dados de produção.

## Arquitetura do Banco de Dados

O sistema suporta **dois ambientes** de banco de dados:

- **LOCAL**: PostgreSQL local para desenvolvimento
- **RAILWAY**: PostgreSQL na nuvem para produção

A detecção de ambiente é automática:
- Se `RAILWAY_ENVIRONMENT` existe → usa banco RAILWAY
- Caso contrário → usa banco LOCAL

### Funcionalidades do DB:
- `execute_dual()`: Executa queries de escrita no ambiente apropriado
- `execute_dual_batch()`: Executa INSERT/UPDATE em lote (alta performance)
- Sistema de UPSERT inteligente: compara dados existentes e salva apenas diferenças

## Estrutura de Dados Principais

### Tabelas:
- `Parcerias`: Termos de parceria/fomento
- `Parcerias_Despesas`: Despesas detalhadas por mês
- `Usuarios`: Controle de acesso

## Tecnologias Utilizadas

- **Backend**: Flask 3.1.0, Python 3.8+
- **Banco de Dados**: PostgreSQL 12+
- **Frontend**: Bootstrap 5.3.0, JavaScript ES6+
- **ORM**: psycopg2 (PostgreSQL adapter)
- **Deploy**: Railway (produção)

## Scripts Úteis

Localizados em `outras coisas/`:
- `create_users.py`: Criação de usuários
- `test_postgres_connection.py`: Teste de conexão com BD
- `import_2.py`: Importação de dados CSV

## Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## Troubleshooting

### Erro de conexão com banco de dados
- Verifique se o PostgreSQL está rodando
- Confirme as credenciais no arquivo `.env`
- Teste a conexão: `python outras\ coisas/test_postgres_connection.py`

### Erro "ModuleNotFoundError"
- Ative o ambiente virtual: `venv\Scripts\activate`
- Reinstale dependências: `pip install -r requirements.txt`

### Dados duplicados no banco
- O sistema agora usa UPSERT inteligente
- Ao salvar, compara dados existentes e só insere diferenças
- Para limpar dados antigos, use o botão "Limpar Tudo" (reseta apenas interface)

1. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

2. Configure o banco de dados em `config.py`.

3. Execute a aplicação:
   ```
   python app.py
   ```

4. Acesse via navegador: [http://localhost:5000](http://localhost:5000)

## Observações

- Scripts auxiliares e documentação estão em `outras coisas/` e `melhorias/`.
- Testes e backups não estão incluídos neste resumo.
- Para padronização de categorias, utilize o dicionário disponível em `orcamento_3_dict.html`.

---

Projeto desenvolvido para facilitar a gestão de orçamento e parcerias, com foco em usabilidade, padronização e integração de dados.
