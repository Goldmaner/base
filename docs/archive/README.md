# 📊 FAF - Ferramenta de Análise Financeira

> **Sistema integrado de gestão de parcerias, orçamentos e prestações de contas**  
> Divisão de Análise de Contas - Secretaria Municipal de Direitos Humanos e Cidadania de São Paulo

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-green.svg)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17+-blue.svg)](https://postgresql.org)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3.0-purple.svg)](https://getbootstrap.com)

---

## 📋 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Funcionalidades Principais](#-funcionalidades-principais)
- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Arquitetura do Sistema](#-arquitetura-do-sistema)
- [Requisitos](#-requisitos)
- [Instalação e Configuração](#-instalação-e-configuração)
- [Estrutura de Pastas](#-estrutura-de-pastas)
- [Módulos do Sistema](#-módulos-do-sistema)
- [Controle de Acesso](#-controle-de-acesso)
- [Banco de Dados](#-banco-de-dados)
- [Scripts Utilitários](#-scripts-utilitários)
- [Troubleshooting](#-troubleshooting)
- [Contribuindo](#-contribuindo)

---

## 🎯 Sobre o Projeto

O **FAF** é uma aplicação web desenvolvida para gerenciar termos de parceria e fomento, orçamentos anuais, conciliações bancárias e análises de prestações de contas. O sistema oferece:

- **Gestão completa de parcerias**: Cadastro, edição, consulta e exportação de termos (TFM, TCC, TAP)
- **Orçamento anual detalhado**: Planejamento por rubrica, mês e categoria de despesa com dicionário inteligente
- **Conciliação bancária**: Importação de extratos, categorização e avaliação de transações
- **Análise de prestações de contas**: Checklist completo com instruções automatizadas e badges interativos
- **Controle de acesso granular**: Permissões por módulo para diferentes perfis de usuário
- **Sistema de backup automático**: Mantém automaticamente os 10 backups mais recentes
- **Duplo ambiente**: Banco local (desenvolvimento) e Railway (produção)

---

## ⚡ Funcionalidades Principais

### 1. **Gestão de Parcerias**
- ✅ Cadastro e edição de termos (TFM, TCC, TAP)
- ✅ Informações adicionais (responsável legal, objeto, beneficiários)
- ✅ Gerenciamento de endereços (logradouro, CEP, distrito)
- ✅ Alterações DGP com histórico completo
- ✅ Visualização de dados consolidados por termo
- ✅ Filtros avançados (OSC, tipo, responsabilidade, vigência)
- ✅ Exportação para CSV/Excel
- ✅ Sistema de busca global
- ✅ Gerenciamento de termos rescindidos com validação de execução mínima
- ✅ Cálculo automático de prestações de contas

### 2. **Alterações DGP**
- ✅ Cadastro de alterações (aditamentos, apostilamentos, informações)
- ✅ 25+ tipos de alteração com campos dinâmicos
- ✅ Interface especial para "Localização do projeto" (edição de múltiplos endereços)
- ✅ Captura automática de valores antigos para histórico
- ✅ Atualização automática das tabelas originais ao concluir
- ✅ Suporte a múltiplos responsáveis
- ✅ Status: Em análise prévia, Iniciado, Em andamento, Concluído
- ✅ Filtros por termo, instrumento, status, tipo e responsável

### 3. **Orçamento Anual**
- ✅ Editor de orçamento por mês e rubrica
- ✅ Importação de dados do Excel (cola inteligente)
- ✅ **Dicionário de Categorias**: Padronização em massa com sincronização
- ✅ Filtros por aditivo e situação
- ✅ Totalizadores automáticos (linha, coluna, geral)
- ✅ **Sistema de Undo**: Desfazer até 10 edições (Ctrl+Z)
- ✅ **Validação de formato monetário**: Aceita BR, rejeita US
- ✅ Barra de progresso no salvamento
- ✅ Exportação para CSV

### 4. **Conciliação Bancária**
- ✅ Importação de extratos bancários (Excel/CSV)
- ✅ Categorização de transações (cat_transacao)
- ✅ Avaliação de conformidade (cat_avaliacao)
- ✅ Mesclagem de lançamentos
- ✅ Filtros por tipo, período e avaliação
- ✅ Relatório consolidado de conciliação
- ✅ Sincronização automática com categorias de despesa
- ✅ Gestão de rendimentos e contrapartida

### 5. **Análise de Prestações de Contas**
- ✅ Checklist completo com 15+ etapas
- ✅ Instruções automatizadas com badges interativos
- ✅ Gerenciamento de fases recursais
- ✅ Preenchimento de dados base
- ✅ Geração de textos automáticos (SEI) pré-2023 e pós-2023
- ✅ Central de modelos de texto parametrizados
- ✅ Exportação de dados para relatórios

### 6. **Administração**
- ✅ Gerenciamento de usuários com tipos (Agente Público/Pessoa Gestora)
- ✅ **Sistema de Controle de Acesso**: Permissões granulares por módulo
- ✅ Gerenciamento de portarias e legislações
- ✅ Modelos de texto parametrizados com variáveis
- ✅ Auditoria de ações (audit_log)
- ✅ Gestão de pessoas gestoras e distritos

---

## 🛠️ Tecnologias Utilizadas

### **Backend**
- **Python 3.12+**: Linguagem principal
- **Flask 3.1.0**: Framework web minimalista e flexível
- **psycopg2**: Adapter PostgreSQL com suporte a DictCursor
- **python-dotenv**: Gerenciamento de variáveis de ambiente
- **Werkzeug**: Segurança de senhas (hashing PBKDF2)
- **dateutil**: Manipulação avançada de datas

### **Frontend**
- **HTML5/CSS3**: Estrutura e estilização modernas
- **Bootstrap 5.3.0**: Framework CSS responsivo
- **JavaScript ES6+**: Lógica client-side com features modernas
- **Bootstrap Icons**: Biblioteca de ícones vetoriais
- **Select2 4.1**: Dropdowns avançados com busca e AJAX
- **jQuery 3.6**: Manipulação DOM e requisições AJAX
- **SheetJS (xlsx)**: Importação/exportação Excel no browser

### **Banco de Dados**
- **PostgreSQL 17**: Banco de dados relacional robusto
- **Schema duplo**: 
  - `public` - Parcerias, orçamentos, usuários, catálogos
  - `analises_pc` - Conciliações bancárias, dados de análise
  - `categoricas` - Tabelas de categorização
- **Railway**: Hospedagem em nuvem para produção

### **Deploy e Infraestrutura**
- **Railway**: Plataforma de produção
- **Git**: Controle de versão distribuído
- **pg_dump**: Backups automáticos (mantém últimos 10)

---

## 🏗️ Arquitetura do Sistema

### **Padrão MVC com Blueprints Modulares**

```
┌──────────────────────────────────────────────────────┐
│                   FRONTEND                            │
│  ┌──────────────────────────────────────────────┐   │
│  │  Templates Jinja2 + Bootstrap 5              │   │
│  │  - Formulários dinâmicos                     │   │
│  │  - Modals e Toasts responsivos               │   │
│  │  - Progress bars e spinners                  │   │
│  │  - Select2 com AJAX                          │   │
│  │  - Validação client-side                     │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
                         ↕
┌──────────────────────────────────────────────────────┐
│               BACKEND (Flask Blueprints)              │
│  ┌─────────────────────────────────────────────┐    │
│  │  BLUEPRINTS (17 módulos)                    │    │
│  │  • main.py           - Dashboard            │    │
│  │  • auth.py           - Autenticação         │    │
│  │  • parcerias.py      - CRUD parcerias       │    │
│  │  • orcamento.py      - Orçamentos           │    │
│  │  • analises.py       - Menu análises PC     │    │
│  │  • analises_pc/*     - Módulos de análise   │    │
│  │  • conc_*.py         - Conciliações         │    │
│  │  • instrucoes.py     - CRUD instruções      │    │
│  │  • listas.py         - Listas catalogas     │    │
│  │  • pesquisa_parcerias.py - Busca/relatórios│    │
│  │  • despesas.py       - Gestão despesas      │    │
│  │  • parcerias_notificacoes.py - Notificações│    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │  CORE MODULES                               │    │
│  │  • decorators.py - Auth & Access Control    │    │
│  │  • db.py         - Database Layer           │    │
│  │  • utils.py      - Helper Functions         │    │
│  │  • config.py     - Settings                 │    │
│  │  • audit_log.py  - Sistema de auditoria     │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
                         ↕
┌──────────────────────────────────────────────────────┐
│             DATABASE (PostgreSQL 17)                  │
│  ┌─────────────────────────────────────────────┐    │
│  │  Schema: public                             │    │
│  │  • parcerias                                │    │
│  │  • parcerias_infos_adicionais              │    │
│  │  • parcerias_enderecos                     │    │
│  │  • parcerias_despesas                      │    │
│  │  • parcerias_pg (pessoas gestoras)         │    │
│  │  • parcerias_sei                           │    │
│  │  • termos_alteracoes (DGP)                 │    │
│  │  • termos_rescindidos                      │    │
│  │  • usuarios                                │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │  Schema: analises_pc                        │    │
│  │  • conc_extrato                            │    │
│  │  • dados_base                              │    │
│  │  • analistas                               │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │  Schema: categoricas                        │    │
│  │  • c_alt_tipo (tipos de alteração)         │    │
│  │  • c_geral_* (catálogos gerais)            │    │
│  │  • c_portarias                             │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

---

## 📦 Requisitos

### **Software Necessário**
- Python 3.12 ou superior
- PostgreSQL 17 ou superior
- Git (para controle de versão)
- pip (gerenciador de pacotes Python)

### **Navegadores Suportados**
- Chrome 90+
- Firefox 88+
- Edge 90+
- Safari 14+

---

## 🚀 Instalação e Configuração

### **1. Clone o Repositório**
```bash
git clone https://github.com/seu-usuario/faf.git
cd faf
```

### **2. Crie o Ambiente Virtual**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### **3. Instale as Dependências**
```bash
pip install -r requirements.txt
```

### **4. Configure as Variáveis de Ambiente**

Copie o arquivo `.env.example` para `.env` e configure:

```env
# Banco de Dados
DB_HOST=localhost
DB_PORT=5432
DB_DATABASE=projeto_parcerias
DB_USER=postgres
DB_PASSWORD=sua_senha_aqui

# Flask
SECRET_KEY=chave-secreta-super-complexa-aqui
FLASK_ENV=development
PORT=5000
```

### **5. Configure o Banco de Dados**

```sql
-- Criar banco de dados
CREATE DATABASE projeto_parcerias;

-- Conectar ao banco
\c projeto_parcerias

-- Criar schemas
CREATE SCHEMA IF NOT EXISTS analises_pc;
CREATE SCHEMA IF NOT EXISTS categoricas;

-- Executar scripts SQL da pasta scripts/archive/ conforme necessário
```

### **6. Execute a Aplicação**

```bash
# Desenvolvimento (porta 8080, hot reload ativado)
python run_dev.py

# Produção (porta 5000, sem hot reload)
python run_prod.py
```

**Desenvolvimento**: `http://localhost:8080`  
**Produção**: `http://localhost:5000`

---

## 📁 Estrutura de Pastas

```
FAF/
├── app.py                      # Aplicação Flask principal
├── config.py                   # Configurações centralizadas
├── db.py                       # Camada de banco de dados
├── decorators.py               # Decoradores (@login_required, @requires_access)
├── utils.py                    # Funções utilitárias
├── audit_log.py                # Sistema de auditoria de ações
├── run_dev.py                  # Servidor desenvolvimento (hot reload)
├── run_prod.py                 # Servidor produção
├── start_help.py               # Helper de inicialização
├── listar_rotas.py             # Utilitário para listar todas as rotas
├── requirements.txt            # Dependências Python
├── .env                        # Variáveis de ambiente (NÃO commitar)
├── .env.example                # Template de configuração
├── .gitignore                  # Arquivos ignorados pelo Git
├── Procfile                    # Deploy Railway
│
├── routes/                     # Blueprints (Módulos de Rotas)
│   ├── __init__.py            # Registro de blueprints
│   ├── main.py                # Dashboard e rotas principais
│   ├── auth.py                # Login, logout, sessões
│   ├── parcerias.py           # CRUD parcerias (3100+ linhas)
│   ├── orcamento.py           # Gestão de orçamentos
│   ├── analises.py            # Menu de análises PC
│   ├── instrucoes.py          # CRUD instruções
│   ├── listas.py              # Listas catalogas (portarias, PGs, etc)
│   ├── pesquisa_parcerias.py  # Busca e relatórios
│   ├── parcerias_notificacoes.py # Sistema de notificações
│   ├── despesas.py            # Gestão de despesas
│   ├── conc_bancaria.py       # Conciliação bancária principal
│   ├── conc_rendimentos.py    # Rendimentos de aplicação
│   ├── conc_contrapartida.py  # Contrapartida
│   ├── conc_demonstrativo.py  # Demonstrativos
│   ├── conc_relatorio.py      # Relatório consolidado
│   ├── conc_exportacao.py     # Exportação de dados
│   ├── analises_pc/           # Submódulo de análises
│   │   ├── routes.py          # Rotas do checklist
│   │   └── routes_dados.py    # APIs de dados
│   └── gestao_financeira/     # (Módulo futuro)
│  │  - utils.py      (Helper Functions)    │    │
│  │  - config.py     (Settings)            │    │
│  └────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
                       ↕
┌─────────────────────────────────────────────────┐
│           DATABASE (PostgreSQL)                  │
│  ┌────────────────────────────────────────┐    │
│  │  Schema: public                        │    │
│  │  - Parcerias                           │    │
│  │  - Parcerias_Despesas                  │    │
│  │  - Usuarios                            │    │
│  │  - c_* (Tabelas catalogas)             │    │
│  └────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────┐    │
│  │  Schema: analises_pc                   │    │
│  │  - conc_extrato                        │    │
│  │  - dados_base                          │    │
│  │  - termos_rescindidos                  │    │
│  └────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

---

## 📦 Requisitos

### **Software Necessário**
- Python 3.8 ou superior
- PostgreSQL 12 ou superior
- Git (para controle de versão)
- pip (gerenciador de pacotes Python)

### **Navegadores Suportados**
- Chrome 90+
- Firefox 88+
- Edge 90+
- Safari 14+

---

## 🚀 Instalação e Configuração

### **1. Clone o Repositório**
```bash
git clone https://github.com/Goldmaner/base.git
cd base
```

### **2. Crie o Ambiente Virtual**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### **3. Instale as Dependências**
```bash
pip install -r requirements.txt
```

### **4. Configure as Variáveis de Ambiente**

Crie um arquivo `.env` na raiz do projeto:

```env
# Banco LOCAL (desenvolvimento)
DB_LOCAL_HOST=localhost
DB_LOCAL_PORT=5432
DB_LOCAL_NAME=faf_db
DB_LOCAL_USER=postgres
DB_LOCAL_PASSWORD=sua_senha_local

# Flask
SECRET_KEY=chave-secreta-super-complexa-aqui
FLASK_ENV=development
```

### **5. Configure o Banco de Dados**

```sql
-- Criar banco de dados local
CREATE DATABASE faf_db;

-- Conectar ao banco
\c faf_db

-- Criar schema de análises
CREATE SCHEMA IF NOT EXISTS analises_pc;

-- Executar scripts de criação de tabelas (se disponíveis)
-- Ver pasta scripts/ para SQL de inicialização
```

### **6. Execute a Aplicação**

```bash
# Desenvolvimento (porta 5000)
python run_dev.py

# Produção (porta 8080)
python run_prod.py
```

Acesse: `http://localhost:5000`

---

## 📁 Estrutura de Pastas

```
FAF/
├── app.py                      # Aplicação Flask principal
├── config.py                   # Configurações centralizadas
├── db.py                       # Camada de banco de dados
├── decorators.py               # Decoradores (@requires_access)
├── utils.py                    # Funções utilitárias
├── audit_log.py                # Sistema de auditoria
├── run_dev.py                  # Iniciar em desenvolvimento
├── run_prod.py                 # Iniciar em produção
├── requirements.txt            # Dependências Python
├── .env                        # Variáveis de ambiente (NÃO commitar)
├── .env.example                # Template de configuração
├── .gitignore                  # Arquivos ignorados pelo Git
├── Procfile                    # Deploy Railway
│
├── routes/                     # Blueprints (Módulos de Rotas)
│   ├── __init__.py
│   ├── main.py                 # Dashboard e rotas principais
│   ├── parcerias.py            # CRUD de parcerias (1300+ linhas)
│   ├── orcamento.py            # Gestão de orçamentos
│   ├── analises.py             # Menu de análises PC
│   ├── instrucoes.py           # CRUD de instruções
│   ├── listas.py               # Listas catalogas
│   ├── pesquisa_parcerias.py   # Busca e relatórios
│   ├── parcerias_notificacoes.py # Notificações
│   ├── conc_bancaria.py        # Conciliação principal
│   ├── conc_rendimentos.py     # Rendimentos bancários
│   ├── conc_contrapartida.py   # Contrapartida
│   ├── conc_relatorio.py       # Relatório de conciliação
│   └── conc_exportacao.py      # Exportação de dados
│
├── templates/                  # Templates HTML (Jinja2)
│   ├── tela_inicial.html       # Dashboard principal
│   ├── login.html              # Tela de login
│   ├── analises.html           # Menu de análises
│   ├── orcamento_2.html        # Editor de orçamento
│   ├── orcamento_3_dict.html   # Dicionário de categorias
│   ├── parcerias_*.html        # 10+ templates de parcerias
│   └── analises_pc/            # Templates de análise PC
│       ├── index.html          # Checklist principal
│       ├── conc_bancaria.html  # Conciliação bancária
│       ├── conc_rendimentos.html
│       ├── conc_contrapartida.html
│       └── conc_relatorio.html
│
├── static/                     # Arquivos estáticos
│   ├── css/                    # Estilos customizados
│   ├── js/                     # Scripts JavaScript
│   └── img/                    # Imagens e ícones
│
├── scripts/                    # Scripts SQL e utilitários
│   ├── funcoes_texto.py        # Geração de textos automáticos
│   └── *.sql                   # Scripts de banco de dados
│
├── backups/                    # Backups do banco (SQL dumps)
│   ├── fazer_backup.bat        # Script Windows de backup
│   └── backup_faf_*.sql        # Arquivos de backup
│
├── docs/                       # Documentação técnica
│   ├── ESTRUTURA_MODULAR.md    # Arquitetura do projeto
│   ├── README_ANALISES_PC.md   # Módulo de análises
│   ├── MODULARIZACAO_PARCERIAS.md
│   ├── IMPLEMENTACAO_*.md      # Implementações específicas
│   └── MELHORIAS_*.md          # Histórico de melhorias
│
├── testes/                     # Scripts de teste e importação
│   ├── tests/                  # Testes unitários
│   └── *.py                    # Scripts diversos
│
└── modelos/                    # Templates de documentos
    └── README.md
```

---

## 🧩 Módulos do Sistema

### **1. Dashboard (`main.py`)**
- Tela inicial com visão geral do sistema
- Atalhos para módulos principais
- Informações do usuário logado

### **2. Parcerias (`parcerias.py`)**
- Listar termos com filtros avançados
- Cadastrar novo termo
- Editar termo existente
- Visualizar detalhes completos
- Exportar dados para CSV/Excel
- Conferência de dados (OSC, vigência, portaria)
- Dicionário de OSCs com CNPJ
- Gerenciamento de termos rescindidos

### **3. Orçamento (`orcamento.py`)**
- Listar orçamentos por termo
- Editor visual com 12 meses
- Importação de Excel (cola de células)
- Validação de formato monetário
- Sistema de Undo (Ctrl+Z)
- Dicionário de categorias com sincronização
- Totalizadores automáticos
- Filtros por aditivo

### **4. Análises de PC (`analises.py` + `analises_pc/*`)**
- Menu de prestações de contas
- Checklist de 15 etapas
- Instruções automatizadas
- Preenchimento de dados base
- Fases recursais
- Exportação para PDF
- Central de modelos de texto

### **5. Conciliação Bancária (`conc_*.py`)**
- **Bancária**: Importação de extratos, categorização, mesclagem
- **Rendimentos**: Análise de rendimentos de aplicação
- **Contrapartida**: Gestão de contrapartidas
- **Relatório**: Consolidação e exportação

### **6. Instruções (`instrucoes.py`)**
- CRUD de instruções parametrizadas
- Vínculo com portarias
- Visualização formatada

### **7. Listas Catalogas (`listas.py`)**
- Gerenciamento de tipos de contrato
- Portarias/legislações
- Pessoas gestoras
- Categorias de despesa

### **8. Administração (`main.py`)**
- Gerenciamento de usuários
- Controle de acessos por módulo
- Modelos de texto
- Auditoria de ações

---

## 🔐 Controle de Acesso

### **Sistema de Permissões Granulares**

O FAF implementa um sistema de controle de acesso baseado em **módulos** através do decorador `@requires_access(modulo)`.

#### **Tipos de Usuário**
1. **Agente Público**: Acesso total irrestrito (bypass automático)
2. **Pessoa Gestora**: Acesso controlado por campo `acessos`

#### **Módulos Disponíveis**
```python
parcerias          # Gestão de parcerias
orcamento          # Orçamentos anuais
analises           # Análises de PC
instrucoes         # Instruções parametrizadas
listas             # Listas catalogas
pesquisa           # Busca e relatórios
notificacoes       # Notificações
conc_bancaria      # Conciliação bancária
conc_rendimentos   # Rendimentos
conc_contrapartida # Contrapartida
conc_relatorio     # Relatórios de conciliação
portarias          # Admin: Portarias
usuarios           # Admin: Usuários
modelos_textos     # Admin: Modelos de texto
```

#### **Formato de Armazenamento**
Campo `acessos` na tabela `usuarios`: `"parcerias;orcamento;analises"`

#### **Exemplo de Uso**
```python
@orcamento_bp.route('/editar/<numero_termo>')
@login_required
@requires_access('orcamento')
def editar_orcamento(numero_termo):
    # Apenas usuários com permissão 'orcamento' ou Agente Público
    # podem acessar esta rota
    ...
```

---

## 🗄️ Banco de Dados

### **Dual Database Architecture**

O sistema suporta **dois ambientes** de banco de dados:

- **LOCAL**: PostgreSQL local para desenvolvimento (`DB_LOCAL_*`)
- **RAILWAY**: PostgreSQL na nuvem para produção (`DB_RAILWAY_*`)

**Detecção automática**: Se a variável `RAILWAY_ENVIRONMENT` existe, usa Railway; caso contrário, usa Local.

### **Principais Tabelas**

#### **Schema `public`**

| Tabela | Descrição |
|--------|-----------|
| `Parcerias` | Termos de parceria/fomento |
| `Parcerias_Despesas` | Despesas mensais por rubrica |
| `Usuarios` | Controle de acesso |
| `c_geral_tipo_contrato` | Catálogo de tipos de contrato |
| `c_portarias` | Portarias e legislações |
| `c_pessoas_gestoras` | Pessoas gestoras |
| `c_geral_legislacao` | Modelos de texto parametrizados |
| `termos_rescindidos` | Termos rescindidos |

#### **Schema `analises_pc`**

| Tabela | Descrição |
|--------|-----------|
| `conc_extrato` | Movimentações bancárias |
| `dados_base` | Dados base das análises |
| `analistas` | Analistas responsáveis |

### **Funcionalidades Avançadas**

- **UPSERT Inteligente**: Compara dados existentes e salva apenas diferenças
- **Batch Operations**: INSERT/UPDATE em lote para alta performance
- **Sincronização Cross-Table**: Atualização automática de categorias entre `Parcerias_Despesas` e `conc_extrato`

---

## 🐛 Troubleshooting

### **Erro de Conexão com Banco de Dados**

**Sintoma**: `FATAL: password authentication failed`

**Solução**:
1. Verifique credenciais no `.env`
2. Confirme que PostgreSQL está rodando: `psql --version`
3. Teste conexão manual: `psql -h localhost -U postgres -d faf_db`

### **Módulos não Carregam**

**Sintoma**: `ModuleNotFoundError: No module named 'decorators'`

**Solução**:
```bash
# Verifique se está no diretório correto
pwd

# Reinstale dependências
pip install -r requirements.txt

# Verifique imports circulares
python -c "import decorators; print('OK')"
```

### **Erro 403 - Acesso Negado**

**Sintoma**: Usuário não consegue acessar módulo

**Solução**:
1. Verifique campo `acessos` na tabela `usuarios`
2. Confirme que o módulo está escrito corretamente (ex: `parcerias`, não `parceria`)
3. Agente Público tem acesso total por padrão

### **Dados Duplicados no Banco**

**Sintoma**: Registros aparecem várias vezes

**Solução**:
```sql
-- Verificar duplicatas em Parcerias
SELECT numero_termo, COUNT(*) 
FROM Parcerias 
GROUP BY numero_termo 
HAVING COUNT(*) > 1;

-- Sistema de UPSERT deve prevenir isso, mas caso ocorra:
DELETE FROM Parcerias 
WHERE id NOT IN (
    SELECT MIN(id) FROM Parcerias GROUP BY numero_termo
);
```

### **Formatação Monetária Inválida**

**Sintoma**: Alerta de "formato americano detectado"

**Solução**:
- ✅ **Aceito**: `10000`, `10.000,00`, `10000,05`
- ❌ **Rejeitado**: `10,000.00` (formato US)

Use sempre **vírgula** como separador decimal e **ponto** como separador de milhares.

---

## 🤝 Contribuindo

### **Como Contribuir**

1. **Fork** o projeto
2. Crie uma **branch** para sua feature:
   ```bash
   git checkout -b feature/nova-funcionalidade
   ```
3. **Commit** suas mudanças:
   ```bash
   git commit -m "feat: Adiciona nova funcionalidade X"
   ```
4. **Push** para a branch:
   ```bash
   git push origin feature/nova-funcionalidade
   ```
5. Abra um **Pull Request**

### **Padrões de Commit**

- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Atualização de documentação
- `style:` Formatação de código
- `refactor:` Refatoração sem mudança de comportamento
- `test:` Adição ou correção de testes
- `chore:` Manutenção geral

---

## 📄 Licença

Este projeto é de uso interno da **Divisão de Análise de Contas - SMDHC**.

---

## 📞 Suporte e Contato

Para dúvidas, sugestões ou problemas:

- **Email**: jeffersonluiz@prefeitura.sp.gov.br
- **Issues**: [GitHub Issues](https://github.com/Goldmaner/base/issues)
- **Documentação**: Pasta `docs/` deste repositório

---

## 🎉 Agradecimentos

Desenvolvido com dedicação pela equipe de tecnologia da Divisão de Análise de Contas.

**Versão**: 3.0  
**Última Atualização**: Dezembro/2025  
**Autor**: Sistema FAF - Gestão de Parcerias

---

## 📊 Estatísticas do Projeto

- **Linhas de código**: ~15.000+
- **Módulos (Blueprints)**: 13
- **Templates HTML**: 25+
- **Rotas (endpoints)**: 80+
- **Tabelas no banco**: 15+
- **Tempo de desenvolvimento**: 2 anos
- **Usuários ativos**: 20+

---

**🚀 Pronto para começar? Execute `python run_dev.py` e acesse `http://localhost:5000`!**
