# Estrutura Modularizada do Projeto FAF

## 📁 Arquitetura do Projeto

A aplicação foi refatorada seguindo as melhores práticas de desenvolvimento Flask, separando responsabilidades em módulos independentes.

### Estrutura de Diretórios

```
FAF/
├── app.py                    # Arquivo principal (simplificado)
├── config.py                 # Configurações centralizadas
├── db.py                     # Gerenciamento de banco de dados
├── utils.py                  # Funções utilitárias e decoradores
├── routes/                   # Pacote de rotas (Blueprints)
│   ├── __init__.py          # Inicializador do pacote
│   ├── main.py              # Rotas principais (dashboard)
│   ├── auth.py              # Autenticação (login/logout)
│   ├── orcamento.py         # Gestão de orçamentos
│   ├── instrucoes.py        # CRUD de instruções
│   └── despesas.py          # APIs de despesas
├── templates/               # Templates HTML
├── static/                  # Arquivos estáticos (CSS, JS, imagens)
└── tests/                   # Scripts de teste

# Backups (manter por segurança)
├── app_old.py               # Backup do app.py original
└── app_new_modular.py       # Cópia do backup
```

---

## 📄 Descrição dos Módulos

### **1. app.py** (Arquivo Principal)
**Responsabilidade:** Inicializar a aplicação e registrar blueprints.

**Conteúdo:**
- Importação de configurações e blueprints
- Factory function `create_app()`
- Registro de blueprints
- Registro de filtros Jinja2
- Ponto de entrada da aplicação

**Antes:** 562 linhas com toda a lógica
**Depois:** 52 linhas focadas apenas em inicialização

---

### **2. config.py** (Configurações)
**Responsabilidade:** Armazenar todas as configurações da aplicação.

**Contém:**
- `DB_CONFIG`: Configurações do PostgreSQL
- `SECRET_KEY`: Chave secreta para sessões
- `DEBUG`: Flag de modo de depuração

**Vantagem:** Fácil modificar configurações sem mexer no código principal.

---

### **3. db.py** (Banco de Dados)
**Responsabilidade:** Gerenciar conexões com o PostgreSQL.

**Funções:**
- `get_db()`: Obtém/cria conexão com o banco
- `get_cursor()`: Retorna cursor com suporte a dicionários
- `close_db()`: Fecha conexão ao final do contexto

**Vantagem:** Lógica de banco centralizada e reutilizável.

---

### **4. utils.py** (Utilitários)
**Responsabilidade:** Funções auxiliares e decoradores.

**Contém:**
- `format_sei()`: Formata números SEI
- `login_required()`: Decorador de autenticação

**Vantagem:** Código reutilizável em qualquer parte da aplicação.

---

### **5. routes/** (Blueprints)

#### **5.1 main.py**
- **Prefixo:** `/`
- **Rotas:**
  - `GET /` → Dashboard/Tela inicial

#### **5.2 auth.py**
- **Prefixo:** Nenhum (rotas globais)
- **Rotas:**
  - `GET/POST /login` → Login
  - `GET /logout` → Logout

#### **5.3 orcamento.py**
- **Prefixo:** `/orcamento`
- **Rotas:**
  - `GET /orcamento/` → Listagem de parcerias
  - `GET /orcamento/editar/<numero_termo>` → Editor de orçamento

#### **5.4 instrucoes.py**
- **Prefixo:** `/instrucoes`
- **Rotas:**
  - `GET /instrucoes/` → Página de instruções
  - `GET /instrucoes/api` → API: listar instruções
  - `POST /instrucoes/api` → API: criar instrução
  - `DELETE /instrucoes/api/<id>` → API: deletar instrução

#### **5.5 despesas.py**
- **Prefixo:** `/api`
- **Rotas:**
  - `GET /api/termo/<numero_termo>` → Info do termo
  - `GET /api/despesas/<numero_termo>` → Listar despesas
  - `POST /api/despesa` → Criar despesas
  - `POST /api/despesa/confirmar` → Confirmar inserção

---

## 🎯 Benefícios da Modularização

### **1. Manutenibilidade**
- Código organizado por funcionalidade
- Fácil localizar e modificar features específicas
- Reduz complexidade do arquivo principal

### **2. Escalabilidade**
- Novos módulos/blueprints podem ser adicionados facilmente
- Cada blueprint pode ter sua própria lógica independente
- Estrutura pronta para crescimento do projeto

### **3. Testabilidade**
- Módulos independentes facilitam testes unitários
- Cada blueprint pode ser testado isoladamente
- Funções utilitárias podem ser testadas separadamente

### **4. Reutilização**
- Funções em `utils.py` e `db.py` podem ser importadas onde necessário
- Decoradores como `@login_required` aplicados em qualquer rota
- Configurações centralizadas evitam duplicação

### **5. Colaboração**
- Múltiplos desenvolvedores podem trabalhar em blueprints diferentes
- Menos conflitos no controle de versão (Git)
- Código mais legível para novos membros da equipe

---

## 🚀 Como Adicionar Novas Features

### **Adicionar Nova Rota ao Blueprint Existente**

Exemplo: Adicionar rota de relatórios ao `orcamento.py`:

```python
# routes/orcamento.py

@orcamento_bp.route('/relatorio', methods=['GET'])
@login_required
def relatorio():
    """Nova rota de relatórios"""
    # ... sua lógica aqui
    return render_template('relatorio.html')
```

### **Criar Novo Blueprint**

1. Criar arquivo `routes/relatorios.py`:
```python
from flask import Blueprint
from utils import login_required

relatorios_bp = Blueprint('relatorios', __name__, url_prefix='/relatorios')

@relatorios_bp.route('/')
@login_required
def listar():
    # ... sua lógica
    return render_template('relatorios.html')
```

2. Registrar no `app.py`:
```python
from routes.relatorios import relatorios_bp

def create_app():
    app = Flask(__name__)
    # ... outras configurações
    app.register_blueprint(relatorios_bp)  # Adicionar esta linha
    return app
```

---

## ⚙️ Configuração do Ambiente

### **Variáveis de Ambiente (Opcional)**

Para maior segurança em produção, você pode usar variáveis de ambiente:

```python
# config.py
import os

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'projeto_parcerias'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'senha_padrao')
}

SECRET_KEY = os.getenv('SECRET_KEY', 'chave_padrao')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
```

---

## 📝 Notas Importantes

1. **Backup:** O arquivo original foi salvo como `app_old.py`
2. **Compatibilidade:** Todas as rotas e funcionalidades foram mantidas
3. **URLs:** As URLs mudaram ligeiramente devido aos prefixos dos blueprints:
   - `/orcamento` → `/orcamento/` (listagem)
   - `/orcamento/editar/<termo>` → `/orcamento/editar/<termo>`
   - `/instrucoes` → `/instrucoes/`
   - `/api/instrucoes` → `/instrucoes/api`

4. **Templates:** Não precisam de alterações, exceto alguns URLs no código:
   - `url_for('login')` → `url_for('auth.login')`
   - `url_for('orcamento')` → `url_for('orcamento.listar')`
   - `url_for('index')` → `url_for('main.index')`

---

## 🧪 Testes

Para verificar se tudo está funcionando:

```bash
# Iniciar servidor
python app.py

# Testar endpoints principais
# - http://127.0.0.1:5000/
# - http://127.0.0.1:5000/login
# - http://127.0.0.1:5000/orcamento/
# - http://127.0.0.1:5000/instrucoes/
```

---

## 📚 Próximos Passos Sugeridos

1. **Adicionar testes automatizados** em uma pasta `tests/`
2. **Criar arquivo `requirements.txt`** com todas as dependências
3. **Implementar logging** para debugging em produção
4. **Adicionar validação de formulários** com Flask-WTF
5. **Implementar paginação** nas listagens grandes
6. **Adicionar cache** com Flask-Caching para melhor performance

---

## 📖 Referências

- [Flask Blueprints Documentation](https://flask.palletsprojects.com/en/2.3.x/blueprints/)
- [Flask Application Factory Pattern](https://flask.palletsprojects.com/en/2.3.x/patterns/appfactories/)
- [Best Practices for Flask](https://flask.palletsprojects.com/en/2.3.x/patterns/)

---

**Data da refatoração:** 14 de outubro de 2025  
**Versão anterior:** app_old.py (562 linhas)  
**Versão modular:** app.py (52 linhas) + 5 blueprints
