# Plano de Modularização: routes/parcerias.py

## 📊 Situação Atual

**Arquivo**: `routes/parcerias.py`  
**Linhas de código**: 1317  
**Problema**: Arquivo muito extenso, difícil manutenção e navegação

---

## 🎯 Objetivo

Dividir `parcerias.py` em módulos menores e mais gerenciáveis, mantendo funcionalidades organizadas por responsabilidade.

---

## 📋 Análise de Funcionalidades

### Funcionalidades Identificadas no `parcerias.py`:

1. **Visualização/Listagem** (Routes de consulta)
   - `/parcerias` - Listagem principal
   - `/parcerias/ver/<id>` - Visualizar termo individual
   - `/parcerias/detalhes/<id>` - Detalhes JSON

2. **CRUD de Parcerias** (Routes de manipulação)
   - `/parcerias/nova` - Criar nova parceria
   - `/parcerias/editar/<id>` - Editar parceria
   - `/parcerias/deletar/<id>` - Deletar parceria
   - `/parcerias/salvar` - Salvar alterações (API)

3. **Conferência e Validação**
   - `/conferir-parcerias` - Interface de conferência
   - `/api/conferir-parceria` - API de conferência

4. **Exportação**
   - `/parcerias/exportar` - Exportar para CSV
   - `/parcerias/exportar-excel` - Exportar para Excel

5. **Dicionário de OSCs** (Novo - 4 rotas)
   - `/dicionario-oscs` - Interface principal
   - `/buscar-oscs` - API de busca
   - `/termos-por-osc/<osc>` - Termos por OSC
   - `/atualizar-osc` - Atualizar nome OSC

6. **Aditivos e Alterações**
   - `/parcerias/aditivos/<id>` - Gestão de aditivos
   - `/parcerias/novo-aditivo` - Criar aditivo

7. **APIs Auxiliares**
   - `/api/pessoa-gestora` - Buscar pessoa gestora
   - `/api/validar-termo` - Validar termo
   - Outras APIs de suporte

---

## 🏗️ Proposta de Estrutura Modular

### Opção 1: Subpasta com Múltiplos Módulos (RECOMENDADO)

```
routes/
├── __init__.py
├── main.py
├── auth.py
├── despesas.py
├── orcamento.py
├── analises.py
├── instrucoes.py
├── listas.py
└── parcerias/                    # Nova subpasta
    ├── __init__.py               # Blueprint unificado
    ├── views.py                  # Rotas de visualização (~250 linhas)
    ├── crud.py                   # Rotas CRUD (~300 linhas)
    ├── api.py                    # APIs auxiliares (~200 linhas)
    ├── export.py                 # Exportação CSV/Excel (~150 linhas)
    ├── conferencia.py            # Sistema de conferência (~200 linhas)
    ├── osc_dict.py               # Dicionário de OSCs (~150 linhas)
    └── utils.py                  # Funções auxiliares compartilhadas (~100 linhas)
```

**Vantagens**:
- ✅ Separação clara de responsabilidades
- ✅ Arquivos menores (150-300 linhas cada)
- ✅ Facilita testes unitários
- ✅ Blueprint único mantém URLs organizadas
- ✅ Escalável para futuras funcionalidades

**Como Implementar**:

1. Criar pasta `routes/parcerias/`
2. Mover funções para módulos específicos
3. Importar tudo no `__init__.py`
4. Manter compatibilidade com código existente

---

### Opção 2: Múltiplos Blueprints (Alternativa)

```
routes/
├── parcerias_main.py             # Blueprint principal (~400 linhas)
├── parcerias_api.py              # Blueprint API (~350 linhas)
├── parcerias_export.py           # Blueprint exportação (~200 linhas)
├── parcerias_conferencia.py      # Blueprint conferência (~200 linhas)
└── parcerias_osc.py              # Blueprint OSC (~150 linhas)
```

**Vantagens**:
- ✅ Blueprints independentes
- ✅ Prefixos URL diferentes possíveis

**Desvantagens**:
- ❌ Múltiplos registros em `app.py`
- ❌ Pode criar confusão de URLs

---

## 📝 Estrutura Detalhada do Módulo (Opção 1)

### `routes/parcerias/__init__.py`
```python
from flask import Blueprint

# Criar blueprint único
parcerias_bp = Blueprint('parcerias', __name__, url_prefix='/parcerias')

# Importar todas as rotas (isso registra automaticamente)
from . import views
from . import crud
from . import api
from . import export
from . import conferencia
from . import osc_dict
```

### `routes/parcerias/views.py`
```python
from . import parcerias_bp
from flask import render_template, request

@parcerias_bp.route('/')
def listar_parcerias():
    """Listagem principal de parcerias"""
    # Código da listagem...
    pass

@parcerias_bp.route('/ver/<int:id>')
def ver_parceria(id):
    """Visualizar termo individual"""
    # Código de visualização...
    pass

@parcerias_bp.route('/detalhes/<int:id>')
def detalhes_parceria(id):
    """Detalhes JSON de parceria"""
    # Retorna JSON...
    pass
```

### `routes/parcerias/crud.py`
```python
from . import parcerias_bp
from flask import request, redirect, url_for, flash

@parcerias_bp.route('/nova', methods=['GET', 'POST'])
def nova_parceria():
    """Criar nova parceria"""
    # Código de criação...
    pass

@parcerias_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_parceria(id):
    """Editar parceria existente"""
    # Código de edição...
    pass

@parcerias_bp.route('/deletar/<int:id>', methods=['POST'])
def deletar_parceria(id):
    """Deletar parceria"""
    # Código de deleção...
    pass

@parcerias_bp.route('/salvar', methods=['POST'])
def salvar_parceria():
    """API para salvar alterações"""
    # Código de salvamento...
    pass
```

### `routes/parcerias/api.py`
```python
from . import parcerias_bp
from flask import jsonify, request

@parcerias_bp.route('/api/pessoa-gestora')
def buscar_pessoa_gestora():
    """API: Buscar pessoa gestora por email"""
    # Retorna JSON...
    pass

@parcerias_bp.route('/api/validar-termo')
def validar_termo():
    """API: Validar se termo já existe"""
    # Retorna JSON...
    pass
```

### `routes/parcerias/export.py`
```python
from . import parcerias_bp
from flask import send_file, Response
import csv
import io

@parcerias_bp.route('/exportar')
def exportar_csv():
    """Exportar parcerias para CSV"""
    # Código de exportação CSV...
    pass

@parcerias_bp.route('/exportar-excel')
def exportar_excel():
    """Exportar parcerias para Excel"""
    # Código de exportação Excel...
    pass
```

### `routes/parcerias/conferencia.py`
```python
from . import parcerias_bp
from flask import render_template, request, jsonify

@parcerias_bp.route('/conferir')
def conferir_parcerias():
    """Interface de conferência"""
    # Código da interface...
    pass

@parcerias_bp.route('/api/conferir-parceria', methods=['POST'])
def api_conferir_parceria():
    """API: Conferir parceria individual"""
    # Retorna resultado da conferência...
    pass
```

### `routes/parcerias/osc_dict.py`
```python
from . import parcerias_bp
from flask import render_template, request, jsonify

@parcerias_bp.route('/dicionario-oscs')
def dicionario_oscs():
    """Dicionário de OSCs com paginação"""
    # Código do dicionário...
    pass

@parcerias_bp.route('/buscar-oscs')
def buscar_oscs():
    """API: Buscar OSCs"""
    # Retorna JSON com OSCs...
    pass

@parcerias_bp.route('/termos-por-osc/<osc>')
def termos_por_osc(osc):
    """API: Listar termos de uma OSC"""
    # Retorna termos...
    pass

@parcerias_bp.route('/atualizar-osc', methods=['POST'])
def atualizar_osc():
    """API: Atualizar nome de OSC"""
    # Atualiza OSC...
    pass
```

### `routes/parcerias/utils.py`
```python
"""Funções auxiliares compartilhadas entre módulos de parcerias"""

def formatar_cnpj(cnpj):
    """Formata CNPJ para exibição"""
    if not cnpj:
        return ''
    # Código de formatação...
    pass

def calcular_prazo_vigencia(data_inicio, data_fim):
    """Calcula prazo de vigência em meses"""
    # Código de cálculo...
    pass

def validar_dados_parceria(dados):
    """Valida dados de parceria antes de salvar"""
    erros = []
    # Validações...
    return erros
```

---

## 🔄 Processo de Migração

### Fase 1: Preparação (Sem Breaking Changes)
1. ✅ Criar estrutura de pastas `routes/parcerias/`
2. ✅ Criar `__init__.py` com blueprint
3. ✅ Manter `parcerias.py` original temporariamente

### Fase 2: Migração Gradual
1. ✅ Copiar funções para novos módulos
2. ✅ Testar cada módulo individualmente
3. ✅ Atualizar imports em `app.py`:
   ```python
   # Antes
   from routes.parcerias import parcerias_bp
   
   # Depois
   from routes.parcerias import parcerias_bp
   ```
4. ✅ Verificar todas as rotas funcionando

### Fase 3: Finalização
1. ✅ Remover `parcerias.py` original
2. ✅ Mover para `backups/parcerias_old.py`
3. ✅ Atualizar documentação

---

## 🧪 Testes Recomendados

### Após Cada Módulo Migrado:

```python
# test_parcerias_views.py
def test_listar_parcerias():
    """Testa listagem de parcerias"""
    response = client.get('/parcerias/')
    assert response.status_code == 200

def test_ver_parceria():
    """Testa visualização individual"""
    response = client.get('/parcerias/ver/1')
    assert response.status_code == 200

# test_parcerias_crud.py
def test_criar_parceria():
    """Testa criação de parceria"""
    data = {
        'osc': 'Teste OSC',
        'termo': '001/2025',
        # ...
    }
    response = client.post('/parcerias/nova', data=data)
    assert response.status_code in [200, 302]

# test_parcerias_api.py
def test_buscar_oscs():
    """Testa API de busca de OSCs"""
    response = client.get('/parcerias/buscar-oscs?busca=teste')
    assert response.status_code == 200
    assert response.json is not None
```

---

## 📊 Benefícios Esperados

### Antes da Modularização
- ❌ 1317 linhas em um arquivo
- ❌ Difícil navegação
- ❌ Conflitos de merge frequentes
- ❌ Tempo de carregamento lento no editor

### Depois da Modularização
- ✅ ~150-300 linhas por arquivo
- ✅ Navegação clara por responsabilidade
- ✅ Desenvolvimento paralelo facilitado
- ✅ Editor mais responsivo
- ✅ Testes mais específicos
- ✅ Manutenção simplificada

---

## 🎯 Cronograma Sugerido

### Semana 1: Preparação
- Criar estrutura de pastas
- Configurar blueprint
- Documentar funções atuais

### Semana 2-3: Migração Core
- Migrar `views.py`
- Migrar `crud.py`
- Testes de regressão

### Semana 4: APIs e Exportação
- Migrar `api.py`
- Migrar `export.py`
- Testes de integração

### Semana 5: Finalização
- Migrar `conferencia.py`
- Migrar `osc_dict.py`
- Cleanup e documentação

---

## ⚠️ Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| URLs quebradas | Alto | Manter blueprint com mesmo nome e prefixos |
| Imports circulares | Médio | Usar imports locais nas funções |
| Perda de funcionalidades | Alto | Testes abrangentes antes de remover original |
| Regressões | Médio | Manter backup e git tags |

---

## 📚 Referências

- [Flask Blueprints Documentation](https://flask.palletsprojects.com/en/3.0.x/blueprints/)
- [Python Project Structure Best Practices](https://docs.python-guide.org/writing/structure/)
- Documento interno: `docs/ESTRUTURA_MODULAR.md`

---

## ✅ Checklist de Implementação

- [ ] Criar `routes/parcerias/` folder
- [ ] Criar `__init__.py` com blueprint
- [ ] Migrar e testar `views.py`
- [ ] Migrar e testar `crud.py`
- [ ] Migrar e testar `api.py`
- [ ] Migrar e testar `export.py`
- [ ] Migrar e testar `conferencia.py`
- [ ] Migrar e testar `osc_dict.py`
- [ ] Criar `utils.py` com funções compartilhadas
- [ ] Atualizar `app.py` (se necessário)
- [ ] Rodar suite completa de testes
- [ ] Mover `parcerias.py` para backups
- [ ] Atualizar documentação
- [ ] Deploy em produção
- [ ] Monitoramento pós-deploy

---

**Status**: 📋 Planejamento Completo  
**Prioridade**: Média  
**Esforço Estimado**: 3-5 semanas  
**Última Atualização**: Janeiro 2025
