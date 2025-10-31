# Pasta de Backups - FAF

Esta pasta contém os backups automáticos do banco de dados PostgreSQL.

## 📁 Estrutura dos Arquivos

Os backups são salvos com o seguinte formato:
```
backup_faf_YYYYMMDD_HHMMSS.sql
```

Exemplo: `backup_faf_20251030_143522.sql`

## 🔧 Como Fazer Backup

### Opção 1: Script Python
```bash
python backup_database.py
```

### Opção 2: Manualmente com pg_dump
```bash
pg_dump -h <host> -p <port> -U <user> -d <database> -F p --no-owner --no-acl -f backups/backup_manual.sql
```

## 🔄 Como Restaurar um Backup

### Opção 1: psql
```bash
psql -h <host> -p <port> -U <user> -d <database> -f backups/backup_faf_20251030_143522.sql
```

### Opção 2: pgAdmin
1. Abra o pgAdmin
2. Conecte ao servidor PostgreSQL
3. Clique com botão direito no banco de dados → Restore
4. Selecione o arquivo .sql

## ⚠️ Importante

- **Não commitar backups no Git**: Arquivos `.sql` estão no `.gitignore`
- **Fazer backup regularmente**: Recomendado antes de grandes mudanças
- **Verificar espaço em disco**: Backups podem ocupar bastante espaço
- **Guardar backups em local seguro**: Considere copiar para outro local/nuvem

## 🧹 Limpeza Automática

O script `backup_database.py` pode limpar backups antigos automaticamente.
Para ativar, descomente a linha no final do script:

```python
limpar_backups_antigos(dias=30)  # Remove backups com mais de 30 dias
```

## 📊 Informações dos Backups

O script mostra automaticamente:
- Nome do arquivo
- Tamanho (MB)
- Data e hora de criação
- Lista de todos os backups existentes
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
