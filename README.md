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

O **FAF** é uma aplicação web completa desenvolvida para gerenciar termos de parceria e fomento (TFM, TCC, TAP), orçamentos anuais, conciliações bancárias e análises de prestações de contas da SMDHC.

**Principais diferenciais:**
- ✅ Gestão completa de parcerias com informações adicionais e endereços
- ✅ Sistema de **Alterações DGP** com 25+ tipos e histórico completo
- ✅ Orçamento anual com dicionário inteligente de categorias
- ✅ Conciliação bancária com categorização e avaliação
- ✅ Análises de prestações de contas com checklist e geração automática de textos
- ✅ Controle de acesso granular por módulo
- ✅ Backup automático (mantém últimos 10)

---

## ⚡ Funcionalidades Principais

### 1. **Gestão de Parcerias**
- Cadastro e edição completa de termos
- Informações adicionais (responsável legal, objeto, beneficiários, datas)
- Gerenciamento de múltiplos endereços (logradouro, CEP, distrito)
- Dicionário de OSCs com CNPJs
- Termos rescindidos com análise de execução
- Filtros avançados e exportação CSV/Excel

### 2. **Alterações DGP** 🆕
- **25+ tipos de alteração** (aditamentos, apostilamentos, informações DGP)
- **Campos dinâmicos** baseados no tipo selecionado
- **Interface especial** para "Localização do projeto" (edição de múltiplos endereços)
- **Histórico completo**: Captura automática de valores antigos
- **Atualização automática** das tabelas originais ao concluir
- Suporte a múltiplos responsáveis
- Filtros por termo, instrumento, status, tipo

### 3. **Orçamento Anual**
- Editor visual (12 meses × rubricas)
- Importação Excel com cola inteligente
- **Dicionário de Categorias**: Padronização em massa
- Sistema de **Undo** (Ctrl+Z, até 10 edições)
- Validação de formato monetário (BR vs US)
- Totalizadores automáticos
- Barra de progresso no salvamento

### 4. **Conciliação Bancária**
- Importação de extratos (Excel/CSV)
- Categorização e avaliação de transações
- Mesclagem de lançamentos
- Gestão de rendimentos e contrapartida
- Relatório consolidado
- Sincronização automática com despesas

### 5. **Análise de Prestações de Contas**
- Checklist com 15+ etapas
- Instruções automatizadas com badges interativos
- Geração de textos SEI (pré-2023 e pós-2023)
- Fases recursais
- Central de modelos de texto parametrizados
- Dados base preenchimento automático

### 6. **Administração**
- Gerenciamento de usuários (Agente Público / Pessoa Gestora)
- Controle de acesso granular por módulo
- Gestão de portarias e legislações
- Modelos de texto com variáveis
- Auditoria de ações

---

## 🛠️ Tecnologias Utilizadas

### **Backend**
- Python 3.12+ com Flask 3.1.0
- psycopg2 (PostgreSQL adapter)
- python-dotenv (variáveis de ambiente)
- Werkzeug (hash de senhas)
- dateutil (manipulação de datas)

### **Frontend**
- HTML5/CSS3 + Bootstrap 5.3.0
- JavaScript ES6+ com jQuery 3.6
- Select2 4.1 (dropdowns com AJAX)
- Bootstrap Icons
- SheetJS (importação/exportação Excel)

### **Banco de Dados**
- PostgreSQL 17
- 3 schemas: `public`, `analises_pc`, `categoricas`

---

## 📦 Requisitos

- Python 3.12 ou superior
- PostgreSQL 17 ou superior
- Git
- Navegador moderno (Chrome 90+, Firefox 88+, Edge 90+)

---

## 🚀 Instalação e Configuração

### **1. Clone e Configure o Ambiente**
```bash
git clone https://github.com/seu-usuario/faf.git
cd faf
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

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
SECRET_KEY=chave-secreta-complexa
FLASK_ENV=development
PORT=5000
```

### **3. Configure o Banco**
```sql
CREATE DATABASE projeto_parcerias;
\c projeto_parcerias
CREATE SCHEMA IF NOT EXISTS analises_pc;
CREATE SCHEMA IF NOT EXISTS categoricas;
```

### **4. Execute**
```bash
# Desenvolvimento (porta 8080, hot reload)
python run_dev.py

# Produção (porta 5000)
python run_prod.py
```

**Acesse**: http://localhost:8080 (dev) ou http://localhost:5000 (prod)

---

## 📁 Estrutura de Pastas

```
FAF/
├── app.py                      # Flask app principal
├── config.py                   # Configurações
├── db.py                       # Database layer
├── decorators.py               # @login_required, @requires_access
├── utils.py                    # Funções auxiliares
├── audit_log.py                # Auditoria
├── run_dev.py                  # Servidor dev (hot reload)
├── run_prod.py                 # Servidor prod
├── requirements.txt            # Dependências
│
├── routes/                     # 17 blueprints modulares
│   ├── main.py                # Dashboard
│   ├── auth.py                # Login/logout
│   ├── parcerias.py           # ⭐ CRUD parcerias (3100+ linhas)
│   ├── orcamento.py           # Orçamentos
│   ├── analises.py            # Menu análises PC
│   ├── instrucoes.py          # Instruções
│   ├── listas.py              # Listas catalogas
│   ├── pesquisa_parcerias.py  # Busca e relatórios
│   ├── conc_*.py              # Conciliações (5 módulos)
│   ├── analises_pc/           # Submódulo de análises
│   └── ...
│
├── templates/                  # 30+ templates Jinja2
│   ├── tela_inicial.html      # Dashboard
│   ├── parcerias*.html        # 10+ templates parcerias
│   ├── dgp_alteracoes.html    # ⭐ Alterações DGP
│   ├── orcamento_*.html       # Orçamentos
│   ├── analises_pc/           # Templates análises
│   └── ...
│
├── static/                     # CSS, JS, imagens
├── scripts/                    # ⭐ 2 scripts ativos
│   ├── funcoes_texto.py       # Geração textos SEI
│   ├── import_conferencia.py  # Atualização conferência
│   └── archive/               # Scripts históricos
│
├── backups/                    # ⭐ Backups automáticos
│   └── fazer_backup.py        # Mantém últimos 10
│
├── docs/                       # Documentação técnica
└── testes/                     # Scripts de teste
```

---

## 🧩 Módulos do Sistema

### **Parcerias** (`parcerias.py` - 3100 linhas)
- CRUD completo de termos
- **Alterações DGP**: 25+ tipos com campos dinâmicos
- Informações adicionais e endereços
- Conferência de dados
- Dicionário OSC
- Termos rescindidos
- 10+ APIs REST

### **Orçamento** (`orcamento.py`)
- Editor visual 12 meses × rubricas
- Dicionário de categorias
- Sistema Undo (Ctrl+Z)
- Importação Excel

### **Análises PC** (`analises.py` + `analises_pc/*`)
- Checklist 15 etapas
- Conciliação bancária
- Geração textos automáticos
- Instruções com badges

### **Outros Módulos**
- Instruções, Listas, Pesquisas, Notificações
- Conciliações (bancária, rendimentos, contrapartida, relatório)
- Administração (usuários, portarias, modelos)

---

## 🔐 Controle de Acesso

### **Sistema de Permissões Granulares**

Decorador `@requires_access(modulo)` controla acesso por módulo.

**Tipos de Usuário:**
- **Agente Público**: Acesso total (bypass)
- **Pessoa Gestora**: Acesso controlado (campo `acessos`)

**Módulos Disponíveis:**
```python
parcerias, orcamento, analises, instrucoes, listas,
pesquisa, notificacoes, conc_bancaria, conc_rendimentos,
conc_contrapartida, conc_relatorio, portarias, usuarios,
modelos_textos, despesas
```

**Formato**: `"parcerias;orcamento;analises"`

**Exemplo:**
```python
@parcerias_bp.route('/editar/<numero_termo>')
@login_required
@requires_access('parcerias')
def editar_parceria(numero_termo):
    ...
```

---

## 🗄️ Banco de Dados

### **3 Schemas PostgreSQL 17**

**Schema `public`** (Parcerias):
- `parcerias` - Termos principais
- `parcerias_infos_adicionais` - Responsável, objeto, beneficiários
- `parcerias_enderecos` - Múltiplos endereços por termo
- `parcerias_despesas` - Despesas mensais por rubrica
- `parcerias_pg` - Pessoas gestoras (histórico)
- `termos_alteracoes` - ⭐ Alterações DGP com histórico
- `termos_rescindidos` - Termos rescindidos
- `usuarios` - Controle de acesso

**Schema `analises_pc`** (Análises):
- `conc_extrato` - Movimentações bancárias
- `conc_rendimentos`, `conc_contrapartida`
- `dados_base` - Dados das análises
- `analistas` - Analistas responsáveis

**Schema `categoricas`** (Catálogos):
- `c_alt_tipo` - ⭐ 25+ tipos de alteração DGP
- `c_geral_tipo_contrato` - Tipos de contrato
- `c_portarias` - Portarias/legislações
- `c_pessoas_gestoras` - Pessoas gestoras
- `c_geral_legislacao` - Modelos de texto
- `c_geral_regionalizacao` - Distritos

### **Relacionamentos Principais**
```
parcerias (1) ←→ (N) parcerias_despesas
parcerias (1) ←→ (N) parcerias_enderecos
parcerias (1) ←→ (1) parcerias_infos_adicionais
parcerias (1) ←→ (N) parcerias_pg
parcerias (1) ←→ (N) termos_alteracoes
```

---

## 🔧 Scripts Utilitários

### **Scripts Ativos** (pasta `scripts/`)

| Script | Usado Por | Descrição |
|--------|-----------|-----------|
| **funcoes_texto.py** | pesquisa_parcerias.py | Geração automática de textos SEI |
| **import_conferencia.py** | parcerias.py | Atualização de conferência (subprocess) |

### **Backup Automático**
```bash
python backups/fazer_backup.py
```
- Cria dump SQL com pg_dump
- Mantém **últimos 10 backups** automaticamente
- Deleta backups antigos

### **Arquivo** (pasta `scripts/archive/`)
Scripts SQL e Python já executados para:
- Migrações de schema
- Criação de tabelas/índices
- Populações iniciais

---

## 🐛 Troubleshooting

### **Erro de Conexão com Banco**
```bash
# Verifique .env
DB_HOST=localhost
DB_DATABASE=projeto_parcerias
DB_USER=postgres
DB_PASSWORD=sua_senha

# Teste conexão
psql -h localhost -U postgres -d projeto_parcerias
```

### **Erro 403 - Acesso Negado**
```sql
-- Verifique permissões
SELECT username, tipo_usuario, acessos 
FROM usuarios 
WHERE username = 'seu_usuario';

-- Adicione permissão
UPDATE usuarios 
SET acessos = 'parcerias;orcamento;analises' 
WHERE username = 'seu_usuario';
```

### **Alterações DGP não Salvam**
- Campos HTML devem usar arrays: `parceria_logradouro[]`
- Campos info adicionais: prefixo `parceria_`
- Verifique nomes exatos no formulário

### **Backup Falha**
```bash
# Adicione PostgreSQL ao PATH
# Windows: C:\Program Files\PostgreSQL\17\bin
pg_dump --version
```

---

## 🤝 Contribuindo

### **Workflow**
1. Fork o projeto
2. `git checkout -b feature/nova-funcionalidade`
3. `git commit -m "feat: Adiciona funcionalidade X"`
4. `git push origin feature/nova-funcionalidade`
5. Abra Pull Request

### **Padrões de Commit**
- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Documentação
- `refactor:` Refatoração
- `chore:` Manutenção

### **Boas Práticas**
- Use `@login_required` e `@requires_access()` em novas rotas
- Documente funções complexas
- Mantenha consistência com Bootstrap 5
- Teste localmente antes de commitar

---

## 📞 Suporte

- **Email**: jeffersonluiz@prefeitura.sp.gov.br
- **Documentação**: Pasta `docs/`

---

## 📊 Estatísticas

- **Linhas de código**: ~18.000+
- **Blueprints**: 17 módulos
- **Templates**: 30+
- **Rotas**: 100+
- **Tabelas**: 25+ (3 schemas)
- **Scripts ativos**: 2
- **Tipos alteração DGP**: 25+
- **Usuários ativos**: 20+
- **Tempo de desenvolvimento**: 2 anos

---

**🚀 Pronto para começar?**

```bash
python run_dev.py
```

**Acesse**: http://localhost:8080

---

**Última Atualização**: Janeiro/2026  
**Versão**: 3.1  
**Desenvolvido por**: Equipe FAF - Divisão de Análise de Contas - SMDHC
