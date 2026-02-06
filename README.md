# 🤝 FPDH - Ferramenta de Parcerias de Direitos Humanos

> **Plataforma completa de gestão de parcerias, análises financeiras e controle administrativo**  
> Secretaria Municipal de Direitos Humanos e Cidadania de São Paulo

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-green.svg)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17+-blue.svg)](https://postgresql.org)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3.0-purple.svg)](https://getbootstrap.com)

---

## 📋 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Funcionalidades Principais](#-funcionalidades-principais)
- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Requisitos](#-requisitos)
- [Instalação e Configuração](#-instalação-e-configuração)
- [Estrutura de Pastas](#-estrutura-de-pastas)
- [Módulos do Sistema](#-módulos-do-sistema)
- [Controle de Acesso](#-controle-de-acesso)
- [Banco de Dados](#-banco-de-dados)
- [Scripts Utilitários](#-scripts-utilitários)
- [Performance](#-performance)
- [Troubleshooting](#-troubleshooting)
- [Contribuindo](#-contribuindo)

---

## 🎯 Sobre o Projeto

O **FPDH** é uma plataforma web enterprise desenvolvida para gerenciar todo o ciclo de vida de parcerias com organizações da sociedade civil (OSCs), incluindo termos de fomento (TFM), colaboração (TCC) e apostilamentos (TAP), com foco em transparência, eficiência e controle financeiro.

**Principais diferenciais:**
- ✅ Gestão completa de parcerias com 25+ tipos de alterações contratuais
- ✅ **Central de Certidões** - Gestão centralizada de 7 certidões obrigatórias por OSC
- ✅ **Gestão Financeira Integrada** - Ultra liquidações com cronogramas FASE 1/2/3
- ✅ **Sistema de Editais** - Controle orçamentário e processual de editais
- ✅ Orçamento anual com dicionário inteligente de categorias
- ✅ Conciliação bancária com IA para categorização
- ✅ Análises de prestações de contas com geração automática de textos
- ✅ **Sistema de Férias** - Gestão de calendário e substituições
- ✅ Controle de acesso granular por módulo
- ✅ Performance otimizada com bulk queries (< 1s para 100+ OSCs)
- ✅ Backup automático incremental

---

## ⚡ Funcionalidades Principais

### 1. **Gestão de Parcerias** 🏛️
- Cadastro e edição completa de termos com validação
- **25+ tipos de alterações DGP** (aditamentos, apostilamentos, rescisões)
- Interface especial para edição de múltiplos endereços
- Informações adicionais: responsável legal, objeto, beneficiários, datas
- Gerenciamento de múltiplos endereços por termo (logradouro, CEP, distrito)
- Histórico completo de alterações com captura de valores antigos
- Dicionário de OSCs com CNPJs e dados cadastrais
- Termos rescindidos com análise de execução
- Sistema de notificações automáticas
- Filtros avançados e exportação CSV/Excel/PDF

### 2. **Central de Certidões** 📄 🆕
- **Gestão de 7 certidões obrigatórias** por OSC:
  - CNPJ, CND, CNDT, CRF, CADIN Municipal, CTM, CENTS
- Upload de PDFs com validação de tamanho (máx. 300KB)
- **Junção automática** de certidões em PDF único
- Dashboard visual com status (válida/vence breve/vencida)
- Integração com parcelas programadas
- Filtros por OSC e data de parcela
- Performance otimizada: **3-4 queries SQL** para 100+ OSCs
- Geração automática de pastas por OSC

### 3. **Gestão Financeira** 💰 🆕
#### **Ultra Liquidações**
- Cronograma FASE 1, 2 e 3 com edição individual/coletiva
- Sistema de parcelas: Programada, Projetada, Parcela Única
- Elementos de despesa 53-23 e 53-24
- Validação automática: vigência, status "Não Pago"
- Formatação monetária brasileira (R$ 1.234,56)
- Edição inline com validação de valores

#### **Gestão Orçamentária**
- Controle de dotações orçamentárias
- Acompanhamento de reservas e empenhos
- Integração com cronogramas de desembolso

### 4. **Sistema de Editais** 📋 🆕
- Cadastro e gestão de editais
- Controle orçamentário por edital
- Acompanhamento processual (SEI)
- Status: Em elaboração, Publicado, Em análise, Homologado, Cancelado
- Valores previstos vs executados

### 5. **Orçamento Anual** 💵
- Editor visual 12 meses × rubricas
- Importação Excel com cola inteligente
- **Dicionário de Categorias**: Padronização em massa de descrições
- Sistema de **Undo** (Ctrl+Z, até 10 edições)
- Validação de formato monetário (BR vs US)
- Totalizadores automáticos por mês e rubrica
- Barra de progresso no salvamento
- Exportação para Excel/CSV

### 6. **Conciliação Bancária** 🏦
- Importação de extratos (Excel/CSV)
- **Categorização inteligente** de transações com IA
- Sistema de avaliação (Aprovado, Com ressalva, Reprovado)
- Mesclagem de lançamentos
- Gestão de rendimentos bancários
- Controle de contrapartida
- Demonstrativo consolidado
- Relatório final com totalizadores
- Sincronização automática com despesas

### 7. **Análise de Prestações de Contas** 📊
- Checklist com 15+ etapas
- Instruções automatizadas com badges interativos
- **Geração de textos SEI** (pré-2023 e pós-2023)
- Fases recursais e complementações
- Central de modelos de texto parametrizados
- Dados base com preenchimento automático
- Exportação em Word/PDF

### 8. **Sistema de Férias** 🏖️ 🆕
- Calendário anual visual
- Cadastro de períodos de férias por pessoa
- Sistema de substituições automático
- Alertas de conflitos
- Exportação para impressão

### 9. **Administração** ⚙️
- Gerenciamento de usuários (Agente Público / Pessoa Gestora)
- Controle de acesso granular por módulo (24+ módulos)
- Gestão de portarias e legislações
- **Listas suspensas** - 40+ catálogos editáveis
- Modelos de texto com variáveis dinâmicas
- Auditoria de ações (log completo)
- Painel de estatísticas

---

## 🛠️ Tecnologias Utilizadas

### **Backend**
- **Python 3.12+** com Flask 3.1.0
- **psycopg2-binary** 2.9.11 (PostgreSQL adapter)
- **python-dotenv** 1.0.0 (variáveis de ambiente)
- **Werkzeug** (hash de senhas bcrypt)
- **python-dateutil** 2.9+ (manipulação de datas)
- **pandas** 2.2.3 (processamento de dados)
- **openpyxl** 3.1.5 (Excel)
- **PyPDF2** 3.0.1 (manipulação de PDFs)
- **pdfplumber** 0.11.4 (extração de dados de PDFs)
- **beautifulsoup4** 4.12.3 (parsing HTML)
- **num2words** 0.5.13 (números por extenso)

### **Frontend**
- **HTML5/CSS3** + Bootstrap 5.3.0
- **JavaScript ES6+** com jQuery 3.6
- **Select2** 4.1 (dropdowns com AJAX e busca)
- **Bootstrap Icons** 1.10+
- **SheetJS** (importação/exportação Excel)
- **Chart.js** (gráficos e visualizações)

### **Banco de Dados**
- **PostgreSQL 17** com extensões:
  - `unaccent` (busca sem acentos)
  - `pg_trgm` (busca por similaridade)

---

## 📦 Requisitos

### **Obrigatórios**
- Python 3.12 ou superior
- PostgreSQL 17 ou superior
- Git 2.30+
- Navegador moderno:
  - Chrome 90+
  - Firefox 88+
  - Edge 90+
  - Safari 14+

### **Recomendados**
- 8GB RAM mínimo
- SSD para melhor performance
- Conexão de internet (para CDNs)

---

## 🚀 Instalação e Configuração

### **1. Clone e Configure o Ambiente**
```bash
# Clone o repositório
git clone https://github.com/seu-usuario/fpdh.git
cd fpdh

# Crie ambiente virtual
python -m venv venv

# Ative o ambiente
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Instale dependências
pip install -r requirements.txt
```

### **2. Configure o `.env`**
```env
# Banco de Dados
DB_HOST=localhost
DB_PORT=5432
DB_DATABASE=projeto_parcerias
DB_USER=postgres
DB_PASSWORD=sua_senha_aqui

# Flask
SECRET_KEY=chave-secreta-complexa-minimo-32-caracteres
FLASK_ENV=development
PORT=5000
DEBUG=True

# Upload (opcional)
MAX_CONTENT_LENGTH=10485760  # 10MB
UPLOAD_FOLDER=modelos/Certidoes
```

### **3. Configure o Banco de Dados**
```sql
-- Criar database
CREATE DATABASE projeto_parcerias;

-- Conectar ao database
\c projeto_parcerias

-- Criar schemas
CREATE SCHEMA IF NOT EXISTS analises_pc;
CREATE SCHEMA IF NOT EXISTS categoricas;
CREATE SCHEMA IF NOT EXISTS gestao_financeira;
CREATE SCHEMA IF NOT EXISTS gestao_orcamentaria;

-- Instalar extensões
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### **4. Execute as Migrations**
```bash
# Execute os scripts SQL na ordem:
psql -h localhost -U postgres -d projeto_parcerias -f scripts/01_create_tables.sql
psql -h localhost -U postgres -d projeto_parcerias -f scripts/02_populate_categoricas.sql
```

### **5. Inicie a Aplicação**
```bash
# Desenvolvimento (porta 8080, hot reload)
python run_dev.py

# Produção (porta 5000)
python run_prod.py
```

**Acesse**: 
- Desenvolvimento: http://localhost:8080
- Produção: http://localhost:5000

### **6. Login Inicial**
- Criar primeiro usuário via SQL:
```sql
INSERT INTO usuarios (username, senha, nome_completo, tipo_usuario, acessos)
VALUES (
    'admin',
    'scrypt:32768:8:1$HASH',  -- Gere hash com werkzeug
    'Administrador',
    'Agente Público',
    'parcerias;orcamento;analises;certidoes;gestao_financeira;editais;ferias;listas'
);
```

---

## 📁 Estrutura de Pastas

```
FPDH/
├── app.py                      # Flask app principal
├── config.py                   # Configurações (SECRET_KEY, DEBUG, DB)
├── db.py                       # Database layer (get_cursor, get_db)
├── decorators.py               # @login_required, @requires_access
├── utils.py                    # Funções auxiliares
├── audit_log.py                # Sistema de auditoria
├── run_dev.py                  # Servidor dev (porta 8080, hot reload)
├── run_prod.py                 # Servidor prod (porta 5000)
├── requirements.txt            # 50+ dependências Python
├── .env                        # Variáveis de ambiente
│
├── routes/                     # 24 blueprints modulares
│   ├── __init__.py
│   ├── main.py                 # Dashboard principal
│   ├── auth.py                 # Login/logout/autenticação
│   ├── parcerias.py            # ⭐ CRUD parcerias (3200+ linhas)
│   ├── orcamento.py            # Orçamentos anuais
│   ├── analises.py             # Menu análises PC
│   ├── instrucoes.py           # Instruções e checklist
│   ├── listas.py               # ⭐ 40+ listas catalogas (1400+ linhas)
│   ├── pesquisa_parcerias.py   # Busca avançada e relatórios
│   ├── despesas.py             # Gestão de despesas
│   ├── editais.py              # 🆕 Sistema de editais
│   ├── ferias.py               # 🆕 Gestão de férias
│   ├── certidoes.py            # 🆕 Central de certidões (1200+ linhas)
│   ├── parcerias_notificacoes.py # Notificações automáticas
│   │
│   ├── conc_bancaria.py        # Conciliação bancária
│   ├── conc_rendimentos.py     # Gestão de rendimentos
│   ├── conc_contrapartida.py   # Controle de contrapartida
│   ├── conc_demonstrativo.py   # Demonstrativo consolidado
│   ├── conc_exportacao.py      # Exportação de dados
│   ├── conc_relatorio.py       # Relatório final
│   │
│   ├── gestao_financeira.py    # 🆕 Gestão financeira principal
│   ├── gestao_financeira_ultra_liquidacoes.py  # 🆕 Ultra liquidações
│   ├── gestao_financeira_anuencia.py           # 🆕 Anuências
│   │
│   ├── ocr_testes.py           # Testes de OCR (experimental)
│   │
│   ├── analises_pc/            # Submódulo análises PC
│   │   ├── __init__.py
│   │   ├── dados_base.py       # Dados base da análise
│   │   ├── checklist.py        # Checklist de etapas
│   │   └── textos_sei.py       # Geração de textos
│   │
│   ├── gestao_financeira/      # Submódulo gestão financeira
│   │   ├── __init__.py
│   │   └── cronograma.py       # Cronogramas FASE 1/2/3
│   │
│   └── gestao_orcamentaria/    # Submódulo gestão orçamentária
│       ├── __init__.py
│       ├── dotacoes.py         # Dotações orçamentárias
│       └── empenhos.py         # Reservas e empenhos
│
├── templates/                  # 40+ templates Jinja2
│   ├── tela_inicial.html       # Dashboard principal
│   ├── login.html              # Tela de login
│   │
│   ├── parcerias*.html         # 12+ templates parcerias
│   │   ├── parcerias.html      # Listagem principal
│   │   ├── parcerias_form.html # Formulário CRUD
│   │   ├── dgp_alteracoes.html # ⭐ Sistema de alterações
│   │   ├── termos_rescindidos.html
│   │   └── ...
│   │
│   ├── certidoes.html          # 🆕 Central de certidões
│   ├── certidoes_osc.html      # 🆕 Gestão por OSC
│   │
│   ├── editais.html            # 🆕 Sistema de editais
│   ├── editais_orcamento.html  # 🆕 Orçamento de editais
│   │
│   ├── ferias.html             # 🆕 Gestão de férias
│   ├── ferias_calendario.html  # 🆕 Calendário anual
│   │
│   ├── orcamento_*.html        # Orçamentos
│   │   ├── orcamento_1.html    # Editor visual
│   │   ├── orcamento_2.html    # Importação
│   │   └── orcamento_3_dict.html # Dicionário
│   │
│   ├── listas.html             # Listas catalogas
│   ├── analises.html           # Menu análises
│   ├── instrucoes.html         # Instruções
│   ├── pesquisa_parcerias.html # Pesquisa avançada
│   │
│   ├── analises_pc/            # Templates análises PC
│   │   ├── dados_base.html
│   │   ├── checklist.html
│   │   └── textos_sei.html
│   │
│   ├── gestao_financeira/      # 🆕 Templates gestão financeira
│   │   ├── ultra_liquidacoes.html  # Cronogramas (6500+ linhas)
│   │   ├── anuencia.html
│   │   └── relatorios.html
│   │
│   ├── gestao_orcamentaria/    # 🆕 Templates gestão orçamentária
│   │   ├── dotacoes.html
│   │   └── empenhos.html
│   │
│   └── archive/                # Templates históricos
│
├── static/                     # Assets estáticos
│   ├── css/
│   ├── js/
│   └── images/
│
├── modelos/                    # 🆕 Arquivos e modelos
│   └── Certidoes/              # Pastas por OSC
│       ├── ABP_Associacao_Brasileira_de_Pipas/
│       ├── Instituto_Macedonia/
│       └── .../
│
├── scripts/                    # ⭐ Scripts utilitários
│   ├── funcoes_texto.py        # Geração textos SEI
│   ├── import_conferencia.py   # Atualização conferência
│   ├── importar_cronograma.py  # Import cronogramas
│   ├── importar_ultra_liquidacoes.py # Import ultra liq.
│   └── archive/                # Scripts históricos (SQL)
│
├── backups/                    # ⭐ Backups automáticos
│   ├── fazer_backup.py         # Script de backup
│   ├── fazer_backup.bat        # Execução Windows
│   └── backup_faf_*.sql        # Dumps (últimos 10)
│
├── docs/                       # Documentação técnica
│   ├── README.md               # Este arquivo
│   ├── PLANO_CONTINUACAO.md    # Roadmap
│   └── README_ANALISES_PC.md   # Doc análises PC
│
└── testes/                     # Scripts de teste
```

---

## 🧩 Módulos do Sistema

### **Core** (Parcerias e Alterações)

#### **1. Parcerias** (`parcerias.py` - 3200 linhas) ⭐
**Rotas principais:**
- `GET /parcerias` - Listagem com filtros avançados
- `POST /parcerias/criar` - Criar novo termo
- `GET /parcerias/editar/<termo>` - Editar termo existente
- `POST /parcerias/salvar` - Salvar alterações
- `GET /parcerias/conferir` - Conferência de dados
- `POST /parcerias/importar_conferencia` - Import CSV
- `GET /parcerias/dict_osc` - Dicionário OSCs
- `GET /parcerias/termos_rescindidos` - Termos rescindidos

**Alterações DGP:**
- `GET /parcerias/dgp_alteracoes` - Listagem alterações
- `GET /parcerias/dgp_alteracoes/nova` - Nova alteração
- `GET /parcerias/dgp_alteracoes/editar/<id>` - Editar
- `POST /parcerias/dgp_alteracoes/salvar` - Salvar
- `POST /parcerias/dgp_alteracoes/concluir/<id>` - Concluir

**25+ Tipos de Alteração:**
- Aditamento de prazo, valor, objeto
- Apostilamento de dados cadastrais
- Localização do projeto (múltiplos endereços)
- Responsável legal, conta bancária
- Plano de trabalho, metas, beneficiários
- Informações DGP (SEI, publicação, etc)

**Diferenciais:**
- Campos dinâmicos por tipo
- Histórico completo (antes/depois)
- Atualização automática das tabelas originais
- Validação de dados

---

### **Gestão Financeira** 💰 🆕

#### **2. Ultra Liquidações** (`gestao_financeira_ultra_liquidacoes.py`) ⭐
**Interface:** `templates/gestao_financeira/ultra_liquidacoes.html` (6500 linhas)

**Funcionalidades:**
- **FASE 1**: Importação inicial de cronogramas
- **FASE 2**: Ajustes mensais com edição coletiva/individual
- **FASE 3**: Ajustes finais antes da execução

**Recursos:**
- Tipos de parcela: Programada, Projetada, Parcela Única
- Elementos de despesa: 53-23 (custeio) e 53-24 (investimento)
- Edição coletiva: atualiza múltiplos registros
- Edição individual: modal com campos específicos
- Formatação monetária brasileira automática
- Validação: vigência, status, valores
- Sistema Undo para edições

**Rotas:**
- `GET /gestao_financeira/ultra_liquidacoes/<termo>` - Cronograma
- `POST /api/ultra_liquidacoes/salvar_coletivo` - Salvar lote
- `POST /api/ultra_liquidacoes/salvar_individual` - Salvar único
- `GET /api/ultra_liquidacoes/parcela/<id>` - Buscar dados

#### **3. Gestão Orçamentária** 🆕
- Dotações orçamentárias
- Reservas e empenhos
- Acompanhamento de execução

---

### **Central de Certidões** 📄 🆕

#### **4. Certidões** (`certidoes.py` - 1200 linhas) ⭐
**Performance otimizada**: 3-4 queries SQL para 100+ OSCs

**Funcionalidades:**
- Dashboard com grid de OSCs
- Upload de 7 certidões obrigatórias (CNPJ, CND, CNDT, CRF, CADIN, CTM, CENTS)
- Validação de tamanho (máx. 300KB por PDF)
- Status visual: válida (verde), vence breve (amarelo), vencida (vermelho)
- **Junção automática** em PDF único
- Filtros por OSC e data de parcela
- Integração com ultra liquidações (parcelas pendentes)

**Otimização de Performance:**
```python
# ANTES: ~240 queries (80 OSCs × 3 queries cada) = 5-10s
# DEPOIS: 3-4 queries bulk = <1s
```

**Técnicas aplicadas:**
- Bulk queries com `WHERE IN (...)`
- Agrupamento em Python (evita N+1 problem)
- `unaccent()` para busca sem acentos
- Índices otimizados

**Rotas:**
- `GET /certidoes` - Dashboard principal
- `GET /certidoes/osc/<pasta>` - Gestão por OSC
- `POST /certidoes/api/upload-individual` - Upload certidão
- `DELETE /certidoes/api/deletar-individual/<id>` - Deletar
- `GET /certidoes/api/juntar-pdfs/<pasta>` - PDF unificado
- `POST /certidoes/api/gerar-pastas` - Criar pastas OSCs

---

### **Editais e Processos** 📋 🆕

#### **5. Editais** (`editais.py`)
- Cadastro de editais
- Orçamento por edital
- Acompanhamento processual (SEI)
- Status: Elaboração, Publicado, Em análise, Homologado, Cancelado
- Controle de valores (previsto vs executado)

**Rotas:**
- `GET /editais` - Listagem
- `POST /editais/criar` - Criar novo
- `GET /editais/editar/<id>` - Editar
- `GET /editais/orcamento/<id>` - Orçamento

---

### **Recursos Humanos** 👥 🆕

#### **6. Férias** (`ferias.py`)
- Calendário anual visual
- Cadastro de períodos por pessoa
- Sistema de substituições
- Alertas de conflitos
- Exportação para impressão

**Rotas:**
- `GET /ferias` - Listagem
- `GET /ferias/calendario` - Calendário anual
- `POST /ferias/criar` - Criar período
- `DELETE /ferias/deletar/<id>` - Excluir

---

### **Orçamento** 💵

#### **7. Orçamento Anual** (`orcamento.py`)
- Editor visual 12 meses × rubricas
- Sistema Undo (Ctrl+Z, 10 níveis)
- Dicionário de categorias
- Importação Excel
- Totalizadores automáticos

**Rotas:**
- `GET /orcamento/<termo>` - Editor
- `POST /orcamento/salvar` - Salvar
- `GET /orcamento/dicionario` - Dicionário
- `POST /orcamento/importar` - Import Excel

---

### **Análises e Conciliações** 📊

#### **8. Análise de Prestações** (`analises.py` + `analises_pc/*`)
- Checklist 15 etapas
- Dados base da análise
- Geração de textos SEI
- Fases recursais

#### **9-13. Conciliações** (5 módulos)
- Bancária (extratos)
- Rendimentos
- Contrapartida
- Demonstrativo
- Relatório final

---

### **Administração** ⚙️

#### **14. Listas Suspensas** (`listas.py` - 1400 linhas) ⭐
**40+ catálogos editáveis:**

**Categorias DGP:**
- `c_dgp_analistas` - Agentes DGP
- `c_dgp_cents_status` - 🆕 Status de CENTS

**Categorias DAC:**
- `c_dac_analistas` - Analistas DAC
- `c_dac_despesas_analise` - Despesas
- `c_dac_modelo_textos_inconsistencias` - Modelos de texto

**Categorias ALT (Alterações):**
- `c_alt_instrumento` - Instrumentos jurídicos
- `c_alt_tipo` - 25+ tipos de alteração
- `c_alt_normas` - Normas e regimentos

**Categorias Gerais:**
- `c_geral_pessoa_gestora` - Pessoas gestoras
- `c_geral_tipo_contrato` - Tipos de contrato
- `c_geral_legislacao` - Portarias e leis
- `c_geral_regionalizacao` - Distritos de SP
- `c_geral_certidoes` - Tipos de certidão
- E 30+ outras...

**Funcionalidades:**
- CRUD completo com validação
- Edição inline em colunas específicas
- Filtros dinâmicos por coluna
- Ordenação por qualquer coluna
- Campos especiais: checkbox, select, textarea, datalist
- Reordenação drag-and-drop
- Salvamento em lote

**Rotas:**
- `GET /listas` - Interface principal
- `GET /listas/api/dados/<tabela>` - Buscar dados
- `POST /listas/api/dados/<tabela>` - Criar registro
- `PUT /listas/api/dados/<tabela>/<id>` - Atualizar
- `DELETE /listas/api/dados/<tabela>/<id>` - Deletar
- `POST /listas/api/dados/<tabela>/salvar-lote` - Salvar múltiplos

---

### **Outros Módulos**

#### **15. Pesquisa e Relatórios** (`pesquisa_parcerias.py`)
- Busca avançada multi-critério
- Geração de textos SEI automáticos
- Exportação CSV/Excel/PDF

#### **16. Notificações** (`parcerias_notificacoes.py`)
- Alertas automáticos
- E-mails programados

#### **17. Instruções** (`instrucoes.py`)
- Checklist interativo
- Badges de progresso

#### **18. Despesas** (`despesas.py`)
- Gestão de despesas mensais
- Categorização

#### **19. OCR Testes** (`ocr_testes.py`)
- Extração de dados de PDFs (experimental)

---

## 🔐 Controle de Acesso

### **Sistema de Permissões Granulares**

Baseado em decorador `@requires_access(modulo)` que controla acesso por módulo.

**Tipos de Usuário:**
- **Agente Público**: Acesso total irrestrito (bypass de validações)
- **Pessoa Gestora**: Acesso controlado pelo campo `acessos`

**24 Módulos Disponíveis:**
```python
# Core
'parcerias',          # Gestão de parcerias
'orcamento',          # Orçamento anual
'despesas',           # Despesas mensais

# Análises
'analises',           # Análises de PC
'instrucoes',         # Instruções e checklist

# Conciliações
'conc_bancaria',      # Conciliação bancária
'conc_rendimentos',   # Gestão de rendimentos
'conc_contrapartida', # Controle de contrapartida
'conc_relatorio',     # Relatório consolidado

# Gestão Financeira 🆕
'gestao_financeira',  # Ultra liquidações
'gestao_orcamentaria', # Dotações e empenhos

# Novos Módulos 🆕
'certidoes',          # Central de certidões
'editais',            # Sistema de editais
'ferias',             # Gestão de férias

# Pesquisa e Relatórios
'pesquisa',           # Pesquisa avançada
'notificacoes',       # Notificações

# Administração
'listas',             # Listas catalogas
'portarias',          # Portarias e legislações
'usuarios',           # Gestão de usuários
'modelos_textos'      # Modelos de texto
```

**Formato de Armazenamento:**
```sql
-- Campo acessos: string separada por ponto-e-vírgula
acessos = 'parcerias;orcamento;analises;certidoes;gestao_financeira'
```

**Exemplo de Uso:**
```python
from decorators import requires_access
from utils import login_required

@parcerias_bp.route('/editar/<numero_termo>')
@login_required
@requires_access('parcerias')
def editar_parceria(numero_termo):
    # Só usuários com acesso 'parcerias' podem acessar
    ...
```

**Configuração de Usuário:**
```sql
-- Agente Público (acesso total)
UPDATE usuarios 
SET tipo_usuario = 'Agente Público'
WHERE username = 'admin';

-- Pessoa Gestora (acesso limitado)
UPDATE usuarios 
SET tipo_usuario = 'Pessoa Gestora',
    acessos = 'parcerias;orcamento;certidoes'
WHERE username = 'gestor1';
```

---

## 🗄️ Banco de Dados

### **PostgreSQL 17 - Arquitetura**

**5 Schemas:**

#### **1. Schema `public`** (Parcerias e Core)
```sql
-- Parcerias principais
parcerias                      -- Termos (TFM, TCC, TAP)
parcerias_infos_adicionais     -- Responsável, objeto, beneficiários
parcerias_enderecos            -- Múltiplos endereços por termo
parcerias_despesas             -- Despesas mensais por rubrica
parcerias_pg                   -- Pessoas gestoras (histórico)

-- Alterações DGP
termos_alteracoes              -- ⭐ 25+ tipos de alteração com histórico
termos_alteracoes_historico    -- Valores antigos (antes/depois)

-- Gestão
termos_rescindidos             -- Termos rescindidos com análise
usuarios                       -- Controle de acesso e autenticação
certidoes                      -- 🆕 Certidões por OSC
editais                        -- 🆕 Gestão de editais
ferias                         -- 🆕 Períodos de férias
```

#### **2. Schema `analises_pc`** (Análises de Prestação)
```sql
conc_extrato                   -- Movimentações bancárias
conc_rendimentos               -- Rendimentos aplicados
conc_contrapartida             -- Contrapartida da OSC
conc_demonstrativo             -- Demonstrativo consolidado
dados_base                     -- Dados base da análise
checklist                      -- Etapas do checklist
analistas                      -- Analistas responsáveis
textos_sei                     -- Textos gerados
```

#### **3. Schema `categoricas`** (40+ Catálogos)
```sql
-- DGP
c_dgp_analistas                -- Agentes DGP
c_dgp_cents_status             -- 🆕 Status de CENTS

-- DAC
c_dac_analistas                -- Analistas DAC
c_dac_despesas_analise         -- Categorias de despesa
c_dac_modelo_textos_inconsistencias -- Modelos de texto

-- Alterações
c_alt_tipo                     -- ⭐ 25+ tipos de alteração
c_alt_instrumento              -- Instrumentos jurídicos
c_alt_normas                   -- Normas e regimentos

-- Geral
c_geral_pessoa_gestora         -- Pessoas gestoras
c_geral_tipo_contrato          -- Tipos de contrato
c_geral_legislacao             -- Portarias e leis
c_geral_regionalizacao         -- Distritos de SP
c_geral_certidoes              -- ⭐ 7 tipos de certidão
c_geral_coordenadores          -- Coordenadores por setor

-- E 30+ outras tabelas...
```

#### **4. Schema `gestao_financeira`** 🆕
```sql
ultra_liquidacoes              -- ⭐ Cronogramas FASE 1/2/3
  - Campos: numero_termo, mes_ano, valor_elemento_53_23, 
            valor_elemento_53_24, parcela_tipo, parcela_status,
            vigencia_inicial, vigencia_final

anuencia                       -- Anuências de desembolso
relatorios_financeiros         -- Relatórios consolidados
```

#### **5. Schema `gestao_orcamentaria`** 🆕
```sql
dotacoes                       -- Dotações orçamentárias
reservas                       -- Reservas orçamentárias
empenhos                       -- Empenhos realizados
cronograma_desembolso          -- Cronograma de pagamentos
```

### **Relacionamentos Principais**

```
parcerias (1) ←→ (N) parcerias_despesas
parcerias (1) ←→ (N) parcerias_enderecos
parcerias (1) ←→ (1) parcerias_infos_adicionais
parcerias (1) ←→ (N) parcerias_pg
parcerias (1) ←→ (N) termos_alteracoes
parcerias (1) ←→ (N) certidoes
parcerias (1) ←→ (N) gestao_financeira.ultra_liquidacoes

termos_alteracoes (1) ←→ (N) termos_alteracoes_historico

usuarios (1) ←→ (N) parcerias_pg
usuarios (1) ←→ (N) analises_pc.analistas
```

### **Índices Otimizados**

```sql
-- Performance de busca
CREATE INDEX idx_parcerias_numero_termo ON parcerias(numero_termo);
CREATE INDEX idx_parcerias_osc ON parcerias USING gin(to_tsvector('portuguese', osc));

-- Certidões: busca sem acentos
CREATE INDEX idx_parcerias_osc_unaccent ON parcerias(unaccent(LOWER(osc)));

-- Ultra liquidações
CREATE INDEX idx_ultra_liq_termo ON gestao_financeira.ultra_liquidacoes(numero_termo);
CREATE INDEX idx_ultra_liq_vigencia ON gestao_financeira.ultra_liquidacoes(vigencia_inicial);
```

### **Extensões PostgreSQL**

```sql
-- Busca sem acentos (macedonia = macedônia)
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Busca por similaridade (fuzzy search)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

## 🔧 Scripts Utilitários

### **Scripts Ativos** (pasta `scripts/`)

| Script | Usado Por | Descrição |
|--------|-----------|-----------|
| **funcoes_texto.py** | pesquisa_parcerias.py | Geração automática de textos SEI com templates |
| **import_conferencia.py** | parcerias.py | Atualização de conferência via subprocess |
| **importar_cronograma.py** | gestao_financeira | Import inicial de cronogramas |
| **importar_ultra_liquidacoes.py** | gestao_financeira | Import dados ultra liquidações |
| **importar_dotacoes.py** | gestao_orcamentaria | Import dotações orçamentárias |
| **importar_reservas_empenhos.py** | gestao_orcamentaria | Import reservas e empenhos |

### **Backup Automático** ⭐

```bash
# Executar backup manual
python backups/fazer_backup.py

# Windows (agendador de tarefas)
backups\fazer_backup.bat
```

**Funcionalidades:**
- Cria dump SQL completo com `pg_dump`
- Nomenclatura: `backup_fpdh_YYYYMMDD_HHMMSS.sql`
- **Mantém últimos 10 backups** automaticamente
- Deleta backups antigos (> 10)
- Log de execução
- Compressão opcional

**Configuração:**
```python
# backups/fazer_backup.py
BACKUPS_MANTER = 10  # Número de backups a manter
PASTA_BACKUPS = 'backups/'
```

### **Scripts Históricos** (pasta `scripts/archive/`)

Migrations e populações já executadas:
- `01_criar_tabelas_base.sql` - Estrutura inicial
- `02_popular_categoricas.sql` - População catálogos
- `03_criar_gestao_financeira.sql` - Schema gestão financeira
- `add_unique_constraint_*.sql` - Constraints adicionados
- `aumentar_colunas_empenhos.sql` - Alterações de schema

---

## 🚀 Performance

### **Otimizações Implementadas**

#### **1. Central de Certidões - Bulk Queries** ⚡

**ANTES (Problema N+1):**
```python
# Para cada OSC (ex: 80 OSCs):
for osc in oscs:
    # Query 1: Buscar nome OSC
    cur.execute("SELECT ... WHERE osc LIKE %s", [osc])
    
    # Query 2: Buscar certidões
    cur.execute("SELECT ... WHERE osc = %s", [osc])
    
    # Query 3: Buscar parcelas
    cur.execute("SELECT ... WHERE osc = %s", [osc])

# Total: 80 × 3 = 240 queries
# Tempo: 5-10 segundos 🐌
```

**DEPOIS (Bulk Queries):**
```python
# Query 1: Buscar TODAS as OSCs de uma vez
cur.execute("SELECT osc, unaccent(LOWER(osc)) FROM parcerias")
oscs_map = {row['normalized']: row['osc'] for row in cur.fetchall()}

# Query 2: Buscar TODAS as certidões de uma vez
placeholders = ','.join(['%s'] * len(oscs))
cur.execute(f"""
    SELECT osc, certidao_nome, certidao_vencimento
    FROM certidoes
    WHERE osc IN ({placeholders})
""", oscs_list)

# Query 3: Buscar TODAS as parcelas de uma vez
cur.execute(f"""
    SELECT p.osc, COUNT(*) as total, mes_ref
    FROM ultra_liquidacoes ul
    INNER JOIN parcerias p ON ul.numero_termo = p.numero_termo
    WHERE p.osc IN ({placeholders})
    GROUP BY p.osc
""", oscs_list)

# Total: 3 queries bulk
# Tempo: < 1 segundo ⚡
```

**Resultado:**
- **240 queries → 3 queries** (redução de 98.75%)
- **5-10s → <1s** (melhoria de 5-10×)

#### **2. Índices Estratégicos**

```sql
-- Busca de parcerias (usado em 50+ rotas)
CREATE INDEX idx_parcerias_numero_termo ON parcerias(numero_termo);

-- Busca sem acentos (Central de Certidões)
CREATE INDEX idx_parcerias_osc_unaccent 
ON parcerias(unaccent(LOWER(osc)));

-- Full-text search
CREATE INDEX idx_parcerias_osc_fts 
ON parcerias USING gin(to_tsvector('portuguese', osc));
```

#### **3. Caching de Listas Catalogas**

```python
# Carrega catálogos em memória no início da requisição
@listas_bp.before_request
def cache_catalogos():
    if 'catalogos' not in g:
        g.catalogos = carregar_todos_catalogos()
```

#### **4. Lazy Loading de Templates**

```javascript
// Carregar dados sob demanda
$('#tabelaCronograma').on('shown.bs.modal', function() {
    carregarDados();  // Só carrega quando modal abre
});
```

### **Métricas de Performance**

| Módulo | Operação | Registros | Tempo |
|--------|----------|-----------|-------|
| Certidões | Listar 100 OSCs | 100 OSCs + 700 cert | <1s ⚡ |
| Parcerias | Listar 500 termos | 500 termos | 1-2s |
| Ultra Liq | Carregar cronograma | 36 meses | 0.5s |
| Orçamento | Salvar 12 meses | 144 células | 0.3s |
| Listas | Editar lote | 50 registros | 0.8s |

---

## 🐛 Troubleshooting

### **Erro de Conexão com Banco de Dados**

```bash
# 1. Verifique variáveis no .env
DB_HOST=localhost
DB_PORT=5432
DB_DATABASE=projeto_parcerias
DB_USER=postgres
DB_PASSWORD=sua_senha

# 2. Teste conexão manual
psql -h localhost -U postgres -d projeto_parcerias

# 3. Verifique se PostgreSQL está rodando
# Windows
services.msc  # Procurar por "postgresql-x64-17"

# Linux
sudo systemctl status postgresql
```

**Erro comum:**
```
psycopg2.OperationalError: FATAL: password authentication failed
```
**Solução:** Verificar senha no `.env` e permissões no `pg_hba.conf`

---

### **Erro 403 - Acesso Negado**

```sql
-- Verifique permissões do usuário
SELECT username, tipo_usuario, acessos 
FROM usuarios 
WHERE username = 'seu_usuario';

-- Adicione permissões necessárias
UPDATE usuarios 
SET acessos = 'parcerias;orcamento;analises;certidoes;gestao_financeira' 
WHERE username = 'seu_usuario';

-- Transformar em Agente Público (acesso total)
UPDATE usuarios 
SET tipo_usuario = 'Agente Público'
WHERE username = 'admin';
```

---

### **Alterações DGP Não Salvam**

**Problema:** Campos não estão sendo salvos corretamente

**Checklist:**
1. Campos HTML devem usar arrays para múltiplos valores:
   ```html
   <input name="parceria_logradouro[]" />
   ```

2. Campos de info adicionais devem ter prefixo `parceria_`:
   ```html
   <input name="parceria_responsavel_legal" />
   ```

3. Verificar nomes exatos no `dgp_alteracoes.html`:
   ```javascript
   console.log('Dados enviados:', formData);
   ```

4. Campos obrigatórios por tipo de alteração em `parcerias.py`:
   ```python
   CAMPOS_OBRIGATORIOS = {
       'Aditamento de prazo': ['data_inicio', 'data_termino'],
       'Aditamento de valor': ['valor_global'],
       ...
   }
   ```

---

### **Central de Certidões - Performance Lenta**

**Sintoma:** Página demorando > 5s para carregar

**Debug:**
```python
# Adicionar logs temporários em routes/certidoes.py
import time

t1 = time.time()
# ... código ...
print(f"⏱️ [DEBUG] Operação X: {(time.time() - t1)*1000:.0f}ms")
```

**Soluções:**
1. Verificar se índices foram criados:
   ```sql
   SELECT indexname FROM pg_indexes 
   WHERE tablename = 'parcerias';
   ```

2. Verificar extensão `unaccent`:
   ```sql
   SELECT * FROM pg_extension WHERE extname = 'unaccent';
   -- Se não existir:
   CREATE EXTENSION unaccent;
   ```

3. Analisar queries lentas:
   ```sql
   EXPLAIN ANALYZE
   SELECT osc FROM parcerias WHERE unaccent(LOWER(osc)) LIKE '%termo%';
   ```

---

### **Ultra Liquidações - Valores Incorretos**

**Problema:** Valores multiplicados (318001.32 → R$ 31.800.132,00)

**Causa:** Formatação monetária duplicada

**Solução:**
```javascript
// Usar toLocaleString('pt-BR') uma única vez
const valorFormatado = parseFloat(valor).toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
});

// Parsear valor BR para número
function parseMoedaBR(valor) {
    return parseFloat(valor.replace(/\./g, '').replace(',', '.'));
}
```

---

### **Backup Falha no Windows**

**Erro:**
```
'pg_dump' não é reconhecido como um comando interno
```

**Solução:**
```bash
# Adicionar PostgreSQL ao PATH do Windows
# 1. Painel de Controle → Sistema → Configurações avançadas
# 2. Variáveis de Ambiente → PATH → Editar
# 3. Adicionar: C:\Program Files\PostgreSQL\17\bin

# Testar
pg_dump --version
```

---

### **Upload de Certidão Falha**

**Erro:** "Arquivo muito grande"

**Soluções:**
1. Verificar tamanho do arquivo (máx 300KB):
   ```python
   # routes/certidoes.py
   MAX_FILE_SIZE = 300 * 1024  # 300KB
   ```

2. Comprimir PDF antes de upload:
   - Online: https://www.ilovepdf.com/compress_pdf
   - Comando: `gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook`

3. Aumentar limite (se necessário):
   ```python
   # config.py
   app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
   ```

---

### **Editais - Orçamento Não Carrega**

**Problema:** Spinner infinito na tela de orçamento

**Debug:**
```javascript
// Console do navegador (F12)
console.log('Response:', response);
console.log('Data:', data);
```

**Soluções:**
1. Verificar se edital existe:
   ```sql
   SELECT * FROM editais WHERE id = 123;
   ```

2. Verificar rota no Flask:
   ```bash
   # Logs do terminal
   [GET] /editais/orcamento/123 - 404 Not Found
   ```

3. Limpar cache do navegador (Ctrl+Shift+Del)

---

### **Férias - Conflitos Não Detectados**

**Problema:** Sistema permite férias sobrepostas

**Verificar:**
```sql
-- Buscar sobreposições
SELECT f1.*, f2.*
FROM ferias f1
JOIN ferias f2 ON f1.pessoa_id = f2.pessoa_id
WHERE f1.id != f2.id
  AND f1.data_inicio <= f2.data_fim
  AND f1.data_fim >= f2.data_inicio;
```

**Adicionar validação:**
```python
# routes/ferias.py
def verificar_conflito(pessoa_id, data_inicio, data_fim):
    cur.execute("""
        SELECT COUNT(*) 
        FROM ferias 
        WHERE pessoa_id = %s 
          AND data_inicio <= %s 
          AND data_fim >= %s
    """, [pessoa_id, data_fim, data_inicio])
    return cur.fetchone()['count'] > 0
```

---

### **Listas Suspensas - Salvamento em Lote Falha**

**Erro:** "Nenhuma alteração pendente"

**Causa:** Linhas não marcadas como alteradas (classe `table-warning`)

**Solução:**
```javascript
// Marcar linha como alterada ao editar select inline
$('select[data-inline-edit]').on('change', function() {
    $(this).closest('tr').addClass('table-warning');
    $('#btnSalvarTodos').show();
});
```

---

### **Erro ao Gerar Texto SEI**

**Problema:** Variáveis não substituídas (ex: `{{osc}}` aparece no texto)

**Debug:**
```python
# scripts/funcoes_texto.py
print(f"Template: {template}")
print(f"Variáveis: {variaveis}")
print(f"Resultado: {texto_gerado}")
```

**Causa comum:** Variáveis com nomes diferentes
```python
# ERRADO
template = "A OSC {{nome_osc}} ..."
variaveis = {'osc': 'Instituto X'}  # Nome diferente!

# CORRETO
template = "A OSC {{osc}} ..."
variaveis = {'osc': 'Instituto X'}
```

---

### **Session Expira Muito Rápido**

**Problema:** Usuário deslogado a cada 5 minutos

**Solução:**
```python
# config.py
from datetime import timedelta

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

```python
# routes/auth.py
@auth_bp.route('/login', methods=['POST'])
def login():
    ...
    session.permanent = True  # Aplicar PERMANENT_SESSION_LIFETIME
    session['username'] = username
```

---

### **Logs para Debug**

```python
# Habilitar logs detalhados
# config.py
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fpdh.log'),
        logging.StreamHandler()
    ]
)

# Usar em routes
import logging
logger = logging.getLogger(__name__)

logger.debug('Dados recebidos: %s', dados)
logger.error('Erro ao salvar: %s', e)
```

---

## 🤝 Contribuindo

### **Workflow de Desenvolvimento**

1. **Fork o projeto**
   ```bash
   git clone https://github.com/seu-usuario/fpdh.git
   cd fpdh
   ```

2. **Crie branch feature**
   ```bash
   git checkout -b feature/nova-funcionalidade
   ```

3. **Faça alterações e teste**
   ```bash
   python run_dev.py  # Testar localmente
   ```

4. **Commit com mensagem descritiva**
   ```bash
   git commit -m "feat: Adiciona funcionalidade X"
   ```

5. **Push e Pull Request**
   ```bash
   git push origin feature/nova-funcionalidade
   # Abrir PR no GitHub
   ```

---

### **Padrões de Commit** (Conventional Commits)

- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Documentação
- `style:` Formatação (sem alterar lógica)
- `refactor:` Refatoração de código
- `perf:` Melhoria de performance
- `test:` Adição/correção de testes
- `chore:` Manutenção/configuração
- `build:` Build system ou dependências

**Exemplos:**
```bash
git commit -m "feat: Adiciona upload múltiplo de certidões"
git commit -m "fix: Corrige formatação monetária em ultra liquidações"
git commit -m "perf: Otimiza queries da central de certidões"
git commit -m "docs: Atualiza README com novos módulos"
```

---

### **Boas Práticas**

#### **1. Segurança**
```python
# SEMPRE usar @login_required
@app.route('/rota_protegida')
@login_required
@requires_access('modulo')
def rota():
    ...

# NUNCA expor senhas em logs
logger.debug(f"User: {username}")  # ✅ OK
logger.debug(f"Pass: {password}")  # ❌ NUNCA!
```

#### **2. Validação de Entrada**
```python
# Validar e sanitizar inputs
numero_termo = request.form.get('numero_termo', '').strip()
if not numero_termo:
    return jsonify({'erro': 'Número do termo obrigatório'}), 400

# Usar prepared statements (previne SQL injection)
cur.execute("SELECT * FROM parcerias WHERE numero_termo = %s", [numero_termo])
```

#### **3. Tratamento de Erros**
```python
try:
    # Código que pode falhar
    result = operacao_arriscada()
except Exception as e:
    logger.error(f"Erro em operacao_arriscada: {e}")
    return jsonify({'erro': 'Erro interno'}), 500
finally:
    # Cleanup (fechar cursors, etc)
    cur.close()
```

#### **4. Performance**
```python
# ✅ BOM: Bulk queries
cur.execute(f"SELECT * FROM tabela WHERE id IN ({placeholders})", ids)

# ❌ RUIM: Loop de queries (N+1 problem)
for id in ids:
    cur.execute("SELECT * FROM tabela WHERE id = %s", [id])
```

#### **5. Frontend**
```javascript
// Usar Bootstrap 5 consistentemente
<button class="btn btn-primary">Salvar</button>

// jQuery para manipulação DOM
$('#elemento').on('click', function() { ... });

// Validação antes de AJAX
if (!form.checkValidity()) {
    form.reportValidity();
    return;
}
```

#### **6. Documentação**
```python
def funcao_complexa(param1, param2):
    """
    Descrição curta da função
    
    Args:
        param1 (str): Descrição do parâmetro
        param2 (int): Descrição do parâmetro
        
    Returns:
        dict: Descrição do retorno
        
    Raises:
        ValueError: Quando parâmetro inválido
    """
    ...
```

---

### **Estrutura de Novos Módulos**

```python
# routes/novo_modulo.py
from flask import Blueprint, render_template, request, jsonify
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access

novo_modulo_bp = Blueprint('novo_modulo', __name__, url_prefix='/novo_modulo')

@novo_modulo_bp.route('/')
@login_required
@requires_access('novo_modulo')  # Adicionar em decorators.py
def index():
    """Página principal do módulo"""
    return render_template('novo_modulo.html')

@novo_modulo_bp.route('/api/dados', methods=['GET'])
@login_required
@requires_access('novo_modulo')
def api_dados():
    """API para buscar dados"""
    try:
        cur = get_cursor()
        cur.execute("SELECT * FROM tabela")
        dados = cur.fetchall()
        return jsonify({'success': True, 'dados': dados})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
```

```python
# app.py - Registrar blueprint
from routes.novo_modulo import novo_modulo_bp
app.register_blueprint(novo_modulo_bp)
```

---

### **Checklist de PR**

- [ ] Código testado localmente
- [ ] Sem erros no console do navegador
- [ ] Sem erros nos logs do Flask
- [ ] Decoradores de acesso aplicados
- [ ] Queries otimizadas (evitar N+1)
- [ ] Tratamento de erros implementado
- [ ] Documentação atualizada
- [ ] Commit message segue padrão
- [ ] Branch atualizado com main

---

## 📞 Suporte

- **Email**: jeffersonluiz@prefeitura.sp.gov.br
- **Documentação**: Pasta `docs/`
- **Issues**: GitHub Issues
- **Wiki**: GitHub Wiki (em construção)

---

## 📊 Estatísticas do Projeto

| Métrica | Valor |
|---------|-------|
| **Linhas de código** | ~25.000+ |
| **Blueprints** | 24 módulos |
| **Templates** | 45+ arquivos |
| **Rotas** | 150+ endpoints |
| **Tabelas** | 35+ (5 schemas) |
| **Listas catalogas** | 40+ catálogos |
| **Scripts ativos** | 6 utilitários |
| **Tipos alteração** | 25+ tipos |
| **Módulos com controle acesso** | 24 módulos |
| **Usuários ativos** | 25+ |
| **Tempo de desenvolvimento** | 2+ anos |
| **Última atualização** | Fevereiro/2026 |

---

## 🗺️ Roadmap

### **Em Desenvolvimento** 🚧
- [ ] Dashboard com gráficos (Chart.js)
- [ ] Exportação PDF de relatórios
- [ ] Notificações push (WebSockets)
- [ ] API REST documentada (Swagger)

### **Planejado** 📋
- [ ] Módulo de prestação de contas online
- [ ] Integração com SEI (API oficial)
- [ ] App mobile (Flutter)
- [ ] Sistema de workflows
- [ ] BI integrado (Power BI/Metabase)

### **Concluído** ✅
- [x] Central de Certidões
- [x] Gestão Financeira (Ultra Liquidações)
- [x] Sistema de Editais
- [x] Gestão de Férias
- [x] Otimização de performance (bulk queries)
- [x] 40+ listas catalogas editáveis

---

## 📜 Licença

Este projeto é de uso interno da **Secretaria Municipal de Direitos Humanos e Cidadania de São Paulo**.

Todos os direitos reservados © 2024-2026 SMDHC

---

## 🎉 Agradecimentos

Desenvolvido com 💙 pela equipe da Divisão de Análise de Contas e Divisão de Gestão de Parcerias.

**Principais contribuidores:**
- Jefferson Luiz (Desenvolvedor principal)
- Equipe DAC (Testes e validação)
- Equipe DGP (Requisitos e feedback)

---

**🚀 Pronto para começar?**

```bash
# Clonar repositório
git clone https://github.com/seu-usuario/fpdh.git
cd fpdh

# Configurar ambiente
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Configurar .env
cp .env.example .env
# Editar .env com suas credenciais

# Iniciar desenvolvimento
python run_dev.py
```

**Acesse**: http://localhost:8080

---

**Versão**: 4.0  
**Última Atualização**: Fevereiro/2026  
**Nome do Projeto**: FPDH - Ferramenta de Parcerias de Direitos Humanos  
**Organização**: Secretaria Municipal de Direitos Humanos e Cidadania - São Paulo
