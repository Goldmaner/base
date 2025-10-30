# Sistema FAF - Gestão de Parcerias e Orçamento

Sistema de gerenciamento de parcerias, orçamento e prestação de contas desenvolvido em Flask para controle financeiro e administrativo.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Tecnologias Utilizadas](#tecnologias-utilizadas)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Documentação Adicional](#documentação-adicional)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

O Sistema FAF é uma aplicação web completa para gestão de:
- **Parcerias**: Cadastro, acompanhamento e análise de termos de parceria
- **Orçamento**: Controle orçamentário com categorias e despesas
- **Análises**: Prestação de contas e pareceres técnicos
- **Instruções**: Gestão de portarias e instruções normativas

---

## 📁 Estrutura do Projeto

```
FAF/
│
├── app.py                          # Aplicação principal Flask
├── config.py                       # Configurações e variáveis de ambiente
├── db.py                           # Gerenciamento de conexões ao banco de dados
├── utils.py                        # Funções utilitárias compartilhadas
├── requirements.txt                # Dependências Python
├── Procfile                        # Configuração para deploy (Railway/Heroku)
├── README.md                       # Este arquivo
├── SETUP.md                        # Instruções detalhadas de instalação
│
├── routes/                         # Blueprints Flask (módulos de rotas)
│   ├── __init__.py
│   ├── main.py                     # Rotas principais e tela inicial
│   ├── auth.py                     # Autenticação e login
│   ├── parcerias.py                # Gestão de parcerias (1317 linhas)
│   ├── despesas.py                 # Gestão de despesas
│   ├── orcamento.py                # Gestão orçamentária
│   ├── analises.py                 # Análises e prestações de contas
│   ├── instrucoes.py               # Portarias e instruções
│   └── listas.py                   # Listas auxiliares (setores, analistas)
│
├── templates/                      # Templates HTML (Jinja2)
│   ├── tela_inicial.html           # Menu principal
│   ├── login.html                  # Página de login
│   ├── parcerias.html              # Listagem de parcerias
│   ├── parcerias_form.html         # Formulário de parceria
│   ├── parcerias_osc_dict.html     # Dicionário de OSCs (novo)
│   ├── orcamento_1.html            # Visão orçamentária
│   ├── orcamento_2.html            # Extrato orçamentário
│   ├── orcamento_3_dict.html       # Dicionário de categorias
│   ├── analises.html               # Listagem de análises
│   ├── editar_analises_termo.html  # Edição de termo individual
│   ├── portarias_analise.html      # Análise de portarias
│   ├── instrucoes.html             # Gestão de instruções
│   ├── listas.html                 # Listas auxiliares
│   ├── extrato.html                # Extrato detalhado
│   └── temp_conferencia.html       # Conferência temporária
│
├── scripts/                        # Scripts SQL e de importação
│   ├── add_pessoa_gestora_column.sql
│   ├── import_conferencia.py
│   └── saida.csv
│
├── tests/                          # Testes e verificações (anteriormente 'testes/')
│   ├── check_aditivos.py
│   ├── check_tables.py
│   ├── check_termos.py
│   ├── export_sqlite_to_csv.py
│   ├── sincronizar_pessoas_gestoras.py
│   ├── t_check_db.py
│   ├── t_check_db2.py
│   ├── t_check_instrucoes.py
│   ├── t_check_pareceres.py
│   ├── t_check_setores.py
│   ├── t_create_parcerias_despesas.py
│   ├── t_importa_parcerias.py
│   ├── t_teste_obterdados.py
│   ├── t_update_siglas.py
│   ├── t_upsert_users.py
│   ├── test_save_api.py
│   ├── testar_email_pg.py
│   ├── verificar_colunas_pg.py
│   ├── verificar_duplicatas.py
│   ├── verificar_email_pg.py
│   └── verificar_sincronizacao.py
│
├── docs/                           # Documentação técnica (anteriormente 'outras coisas/' e 'melhorias/')
│   ├── CHANGELOG_AUTOSAVE_PAGINATION.md
│   ├── CORRECOES_FILTRO_FORMATACAO.md
│   ├── CORRECOES_IMPORTACAO_BADGES.md
│   ├── IMPLEMENTACAO_DUAL_DATABASE.md
│   ├── MELHORIAS_UX_FORMULARIO.md
│   ├── MELHORIAS_UX_ORCAMENTO.md
│   ├── MIGRACAO_BANCO_LOCAL.md
│   ├── ESTRUTURA_MODULAR.md
│   ├── create_users.py             # Script de criação de usuários
│   ├── debug_table.py              # Debug de tabelas
│   ├── fix_sequence.py             # Correção de sequences PostgreSQL
│   ├── import_1.py / import_2.py   # Scripts de importação
│   ├── test_flask_apis.py
│   ├── test_insert.py / test_insert2.py
│   ├── test_postgres_connection.py
│   ├── parcerias_despesas.csv
│   ├── parcerias.csv
│   └── README.md                   # Documentação adicional
│
├── backups/                        # Versões antigas do código
│   ├── app_new_modular.py
│   └── app_old.py
│
├── static/                         # Arquivos estáticos (CSS, JS, imagens) [novo]
│
└── __pycache__/                    # Cache Python (gitignore)
```

---

## 🛠️ Tecnologias Utilizadas

### Backend
- **Python 3.10+**
- **Flask 3.1.0** - Framework web
- **psycopg2** - Adaptador PostgreSQL
- **python-dotenv** - Gerenciamento de variáveis de ambiente
- **gunicorn** - Servidor WSGI para produção

### Frontend
- **Bootstrap 5.3.0** - Framework CSS responsivo
- **JavaScript ES6+** - Lógica client-side
- **Jinja2** - Template engine

### Banco de Dados
- **PostgreSQL 12+** - Banco principal (produção)
- **SQLite** - Banco local (desenvolvimento)

### Deploy
- **Railway** - Plataforma de hospedagem (produção)
- Suporte para Heroku via Procfile

---

## 💻 Instalação

### Pré-requisitos
- Python 3.10 ou superior
- PostgreSQL 12+ (produção) ou SQLite (desenvolvimento)
- pip (gerenciador de pacotes Python)

### Passos

1. **Clone o repositório**
```bash
git clone <url-do-repositorio>
cd FAF
```

2. **Crie um ambiente virtual**
```bash
python -m venv venv
```

3. **Ative o ambiente virtual**
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

4. **Instale as dependências**
```bash
pip install -r requirements.txt
```

5. **Configure as variáveis de ambiente**
```bash
# Crie um arquivo .env na raiz do projeto
# Veja seção Configuração abaixo
```

6. **Execute o servidor**
```bash
# Desenvolvimento
python run_dev.py

# Produção
python run_prod.py
```

---

## ⚙️ Configuração

### Arquivo `.env`

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
# Banco de Dados Local (SQLite)
DATABASE_URL_LOCAL=sqlite:///local_database.db

# Banco de Dados Produção (PostgreSQL Railway)
DATABASE_URL=postgresql://usuario:senha@host:porta/database

# Configuração Flask
FLASK_SECRET_KEY=sua-chave-secreta-aqui
FLASK_ENV=development  # ou production

# Ambiente Ativo
DB_ENV=LOCAL  # LOCAL para SQLite, RAILWAY para PostgreSQL
```

### Dual Database Support

O sistema suporta dois ambientes de banco de dados:

1. **LOCAL (SQLite)**: Para desenvolvimento local
   - Arquivo: `local_database.db`
   - Configurado via `DATABASE_URL_LOCAL`

2. **RAILWAY (PostgreSQL)**: Para produção
   - Hospedado no Railway
   - Configurado via `DATABASE_URL`

Altere a variável `DB_ENV` no `.env` para trocar entre ambientes.

---

## 🚀 Uso

### Executar Localmente

```bash
# Ambiente de desenvolvimento (debug ativo)
python run_dev.py

# Ambiente de produção (sem debug)
python run_prod.py
```

A aplicação estará disponível em `http://localhost:5000`

### Deploy em Produção (Railway)

1. Configure as variáveis de ambiente no Railway:
   - `DATABASE_URL` (fornecido automaticamente pelo Railway PostgreSQL)
   - `FLASK_SECRET_KEY`
   - `DB_ENV=RAILWAY`

2. O deploy é automático via `Procfile`:
```
web: gunicorn app:app
```

---

## ✨ Funcionalidades

### 1. **Gestão de Parcerias** (`routes/parcerias.py`)
- ✅ Cadastro completo de termos de parceria
- ✅ Aditivos e alterações contratuais
- ✅ Busca e filtros avançados
- ✅ Exportação para CSV/Excel
- ✅ **NOVO: Dicionário de OSCs** - Gestão centralizada de organizações
  - Visualização de todas as OSCs cadastradas
  - Edição em lote de nomes de OSCs
  - Listagem de todos os termos por OSC
  - Busca em tempo real
  - Paginação (50 registros por página)

### 2. **Gestão Orçamentária** (`routes/orcamento.py`)
- ✅ Controle de categorias de despesa
- ✅ Lançamento de despesas
- ✅ Extrato orçamentário detalhado
- ✅ Dicionário de categorias (similar ao dicionário de OSCs)
- ✅ Relatórios de saldo e execução

### 3. **Análises e Prestação de Contas** (`routes/analises.py`)
- ✅ Acompanhamento de prestações de contas
- ✅ Registro de pareceres técnicos (DP e PG)
- ✅ **NOVO: Filtros por ano de parecer**
  - Filtro multi-seleção para Data Parecer DP
  - Filtro multi-seleção para Data Parecer PG
  - Dropdown com checkboxes por ano
- ✅ Formatação monetária (R$ 0,00) para valores de devolução
- ✅ Cálculo automático de prazos (sem destaque visual)
- ✅ Status de aprovação/pendência

### 4. **Instruções e Portarias** (`routes/instrucoes.py`)
- ✅ Cadastro de instruções normativas
- ✅ Vínculo com portarias
- ✅ Análise de conformidade

### 5. **Listas Auxiliares** (`routes/listas.py`)
- ✅ Gestão de setores
- ✅ Gestão de analistas
- ✅ Outras listas de apoio

### 6. **Autenticação** (`routes/auth.py`)
- ✅ Login com usuário e senha
- ✅ Controle de sessão
- ✅ Logout seguro

---

## 🏗️ Arquitetura

### Estrutura Modular com Blueprints

A aplicação utiliza **Flask Blueprints** para organização modular:

```python
# app.py
from routes import (
    main_bp,       # Rotas principais
    auth_bp,       # Autenticação
    parcerias_bp,  # Parcerias
    despesas_bp,   # Despesas
    orcamento_bp,  # Orçamento
    analises_bp,   # Análises
    instrucoes_bp, # Instruções
    listas_bp      # Listas
)

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
# ... outros blueprints
```

### Fluxo de Dados

1. **Request** → Blueprint Route Handler
2. **Route** → Database Query (via `db.py`)
3. **Query Results** → Data Processing (via `utils.py`)
4. **Processed Data** → Template Rendering (Jinja2)
5. **Response** → HTML/JSON para Client

### Banco de Dados

#### Principais Tabelas
- `Parcerias` - Termos de parceria e aditivos
- `parcerias_analises` - Análises e pareceres
- `parcerias_despesas` - Despesas vinculadas a parcerias
- `c_orcamento` - Categorias orçamentárias
- `c_analistas` - Cadastro de analistas
- `c_setores` - Setores organizacionais
- `c_instrucoes` - Instruções normativas
- `users` - Usuários do sistema

#### Relacionamentos
- Parcerias ↔ parcerias_analises (1:N)
- Parcerias ↔ parcerias_despesas (1:N)
- parcerias_analises ↔ c_analistas (N:1)
- c_orcamento ↔ parcerias_despesas (1:N)

---

## 📚 Documentação Adicional

Consulte a pasta `docs/` para documentação técnica detalhada:

- **CHANGELOG_AUTOSAVE_PAGINATION.md** - Histórico de salvamento automático e paginação
- **CORRECOES_FILTRO_FORMATACAO.md** - Correções em filtros e formatação
- **CORRECOES_IMPORTACAO_BADGES.md** - Ajustes em importação e badges
- **IMPLEMENTACAO_DUAL_DATABASE.md** - Implementação de dual database (LOCAL/RAILWAY)
- **MELHORIAS_UX_FORMULARIO.md** - Melhorias de UX em formulários
- **MELHORIAS_UX_ORCAMENTO.md** - Melhorias de UX em orçamento
- **MIGRACAO_BANCO_LOCAL.md** - Processo de migração para banco local
- **ESTRUTURA_MODULAR.md** - Documentação da estrutura modular

---

## 🐛 Troubleshooting

### Erro: "No module named 'psycopg2'"
```bash
pip install psycopg2-binary
```

### Erro: "Connection refused" ao conectar no PostgreSQL
- Verifique se o banco está rodando
- Confirme as credenciais no `.env`
- Teste com `test_postgres_connection.py` em `docs/`

### Erro: "Table doesn't exist"
- Execute os scripts de migração em `scripts/`
- Verifique se está usando o ambiente correto (LOCAL vs RAILWAY)

### Sessão expirada constantemente
- Verifique a `FLASK_SECRET_KEY` no `.env`
- Certifique-se de que a chave é consistente entre reinicializações

### Filtros de data não funcionam
- Limpe o cache do navegador
- Verifique o console JavaScript (F12) para erros
- Confirme que a coluna de data existe no banco

### Dicionário de OSCs não atualiza
- Verifique se a conexão com o banco está ativa
- Teste a rota `/buscar-oscs` diretamente
- Confira logs no terminal

---

## 📝 Notas de Versão

### Versão Atual (Janeiro 2025)

#### Novas Funcionalidades
- ✨ **Dicionário de OSCs**: Interface completa para gestão de organizações
- ✨ **Filtros de Data Parecer**: Multi-seleção por ano com checkboxes
- ✨ **Formatação Monetária**: Valores padrão R$ 0,00 em análises

#### Melhorias
- ⚡ Remoção do filtro de "Prazo" (mantido apenas cálculo)
- ⚡ Botão "Menu de Prestações de Contas" na tela inicial
- ⚡ Reorganização de pastas (docs, tests, static)
- ⚡ Código JavaScript mais robusto com optional chaining

#### Correções
- 🐛 Extração de anos de datas via PostgreSQL EXTRACT(YEAR)
- 🐛 Null checks em elementos DOM
- 🐛 Ordem de declaração de funções JavaScript

---

## 👥 Contribuindo

Para contribuir com o projeto:

1. Crie uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
2. Faça commit das mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
3. Push para a branch (`git push origin feature/nova-funcionalidade`)
4. Abra um Pull Request

---

## 📄 Licença

Este projeto é de uso interno. Todos os direitos reservados.

---

## 📧 Contato

Para dúvidas ou suporte, entre em contato com a equipe de desenvolvimento.

---

**Última atualização**: Janeiro 2025
