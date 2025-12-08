# Status da Implementação do Sistema de Controle de Acesso

## ✅ Componentes Implementados

### 1. Decorator de Controle de Acesso (`decorators.py`)
- ✅ Criado e funcional
- ✅ Função `@requires_access(modulo)` implementada
- ✅ Bypass automático para Agente Público
- ✅ Redirecionamento com flash message em caso de acesso negado
- ✅ Helper `check_module_access()` para templates

### 2. Backend - Sistema de Autenticação (`routes/auth.py`)
- ✅ Login armazena `acessos` na session
- ✅ GET `/api/usuarios` retorna `acessos`
- ✅ GET `/api/usuarios/<id>` retorna dados completos do usuário
- ✅ PUT `/api/usuarios/<id>` atualiza campo `acessos`
- ✅ Formato: string com módulos separados por ponto-e-vírgula

### 3. Frontend - Tela Inicial (`templates/tela_inicial.html`)
- ✅ Título dinâmico por tipo de usuário (DGP vs outros)
- ✅ Botões condicionalmente visíveis baseado em permissões
- ✅ Modal de edição com 14 checkboxes de módulos
- ✅ Funções JavaScript para marcar/desmarcar todos
- ✅ Salvar permissões via API

### 4. Banco de Dados
- ✅ Coluna `acessos` (TEXT) criada em `public.usuarios`
- ✅ Formato: `instrucoes;analises;orcamento;parcerias`

---

## 🔄 Pendente: Aplicação dos Decorators nas Rotas

### Análise Atual (39 rotas sem decorator):

#### ❌ **instrucoes.py** (4 rotas)
**Status**: Falta import + 4 decorators
- `listar_view()`
- `listar_api()`
- `deletar()`
- `criar()`

#### ❌ **analises.py** (10 rotas)
**Status**: Import OK, faltam 10 decorators
- `obter_anos_disponiveis()`
- `obter_modelo_ausencia_extratos()`
- `obter_dados()`
- `exportar_csv()`
- `editar_por_termo()`
- `adicionar_analises()`
- `adicionar_analises_multiplos()`
- `calcular_prestacoes()`
- `atualizar_prestacoes()`
- `limpar_prestacoes_sem_recursos()`

#### ❌ **orcamento.py** (7 rotas)
**Status**: Falta import + 7 decorators
- `listar()`
- `editar()`
- `dicionario_despesas()`
- `atualizar_categoria()`
- `termos_por_categoria()`
- `exportar_termo_csv()`
- `exportar_csv()`

#### ⚠️ **parcerias.py** (12 rotas)
**Status**: Import OK, faltam 12 decorators
- `api_sigla_tipo_termo()`
- `atualizar_conferencia()`
- `conferencia_pos_insercao()`
- `dicionario_oscs()`
- `buscar_oscs()`
- `termos_por_osc()`
- `atualizar_osc()`
- `termos_rescindidos()`
- `api_termos_disponiveis()`
- `salvar_rescisao()`
- `editar_rescisao()`
- `deletar_rescisao()`

#### ❌ **listas.py** (6 rotas)
**Status**: Falta import + 6 decorators
- `index()`
- `obter_dados()`
- `criar_registro()`
- `atualizar_registro()`
- `excluir_registro()`
- `salvar_lote()`

#### ❌ **Outros módulos** (falta import)
- `pesquisa_parcerias.py`
- `parcerias_notificacoes.py`
- `conc_bancaria.py`
- `conc_rendimentos.py`
- `conc_contrapartida.py`
- `conc_relatorio.py`

---

## 📋 Como Aplicar os Decorators

### Passo 1: Adicionar Import
Em CADA arquivo de blueprint, adicione após `from utils import login_required`:

\`\`\`python
from decorators import requires_access
\`\`\`

### Passo 2: Adicionar Decorator nas Rotas
Para CADA rota com `@login_required`, adicione o decorator logo após:

**ANTES:**
\`\`\`python
@orcamento_bp.route("/", methods=["GET"])
@login_required
def listar():
    ...
\`\`\`

**DEPOIS:**
\`\`\`python
@orcamento_bp.route("/", methods=["GET"])
@login_required
@requires_access('orcamento')  # ← ADICIONAR ESTA LINHA
def listar():
    ...
\`\`\`

### Passo 3: Módulos Corretos
Use o nome correto do módulo conforme a tabela:

| Arquivo                      | Módulo a usar                  |
|------------------------------|--------------------------------|
| `instrucoes.py`              | `'instrucoes'`                 |
| `analises.py`                | `'analises'`                   |
| `orcamento.py`               | `'orcamento'`                  |
| `parcerias.py`               | `'parcerias'`                  |
| `pesquisa_parcerias.py`      | `'pesquisa_parcerias'`         |
| `parcerias_notificacoes.py`  | `'parcerias_notificacoes'`     |
| `listas.py`                  | `'listas'`                     |
| `conc_bancaria.py`           | `'conc_bancaria'`              |
| `conc_rendimentos.py`        | `'conc_rendimentos'`           |
| `conc_contrapartida.py`      | `'conc_contrapartida'`         |
| `conc_relatorio.py`          | `'conc_relatorio'`             |

---

## 🎯 Exemplo Completo - instrucoes.py

\`\`\`python
"""
Blueprint de instruções
"""
from flask import Blueprint, render_template, jsonify, request
from db import get_cursor
from utils import login_required
from decorators import requires_access  # ← ADICIONAR IMPORT

instrucoes_bp = Blueprint('instrucoes', __name__, url_prefix='/instrucoes')

@instrucoes_bp.route("/", methods=["GET"])
@login_required
@requires_access('instrucoes')  # ← ADICIONAR DECORATOR
def listar_view():
    """
    Renderiza a página principal de instruções
    """
    return render_template("instrucoes.html")

@instrucoes_bp.route("/api", methods=["GET"])
@login_required
@requires_access('instrucoes')  # ← ADICIONAR DECORATOR
def listar_api():
    """
    Retorna JSON com todas as instruções
    """
    ...
\`\`\`

---

## ✅ Validação Após Aplicar

### Teste 1: Agente Público
- ✅ Deve ter acesso a TODOS os módulos (bypass automático)

### Teste 2: Usuário com Acessos Limitados
- ✅ Botões ocultos no dashboard para módulos sem permissão
- ✅ Acesso direto via URL bloqueado (redirecionamento + flash)

### Teste 3: Usuário sem Acessos
- ✅ Redirecionado ao index com mensagem "Acesso negado"

---

## 🚀 Próximos Passos

1. **Aplicar decorators sistematicamente** (use o script `verificar_decorators.py` para acompanhar)
2. **Testar cada módulo** após aplicar os decorators
3. **Verificar logs do servidor** em caso de erro
4. **Confirmar funcionamento** com diferentes tipos de usuário

---

## 📊 Mapeamento Completo dos Módulos

### Categoria: Principal (6 módulos)
- `instrucoes` - Instruções e normativos
- `analises` - Análises de prestação de contas
- `orcamento` - Orçamento e despesas
- `parcerias` - Gerenciamento de parcerias
- `pesquisa_parcerias` - Pesquisa de termos/OSCs
- `parcerias_notificacoes` - Notificações de parcerias

### Categoria: Análise PC (4 módulos)
- `conc_bancaria` - Conciliação bancária
- `conc_rendimentos` - Conciliação de rendimentos
- `conc_contrapartida` - Análise de contrapartida
- `conc_relatorio` - Relatório de conciliação

### Categoria: Gestão (1 módulo)
- `listas` - Listas suspensas

### Categoria: Administração (3 módulos)
- `portarias` - Portarias (usa blueprint `despesas`)
- `usuarios` - Gerenciamento de usuários (usa blueprint `auth`)
- `modelos_textos` - Modelos de textos automáticos

---

**Data**: 08/12/2025  
**Status**: Sistema 70% implementado, faltando aplicação de decorators
