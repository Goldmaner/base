# Guia de Testes de Regressão — FAF

> **Propósito:** Referência rápida para incluir **novas páginas, decorators e APIs** na suite de testes.  
> Leia junto com `docs/PADRONIZACAO_VISUAL.md` ao criar qualquer módulo novo.

---

## 1. Estrutura da Suite

```
testes/
├── conftest.py              ← fixtures globais (app, clientes HTTP)
├── test_routes.py           ← testa rotas HTTP (status, acesso, HTML)
├── test_query_parcerias.py  ← testa contrato da query CTE de parcerias
├── test_api_json.py         ← testa endpoints que retornam JSON
└── test_performance.py      ← guarda de tempo de resposta por rota
```

Configuração em `pytest.ini` (raiz do projeto) — apenas arquivos `test_*.py` são coletados.

Para executar:
```bash
python -m pytest -q --tb=short
# ou pelo painel web: /admin/testes → "Executar Agora"
```

---

## 2. Quando Criar Uma Nova Página

### 2.1 Checklist de testes mínimos

| Cenário | Arquivo de teste | O que verificar |
|---------|-----------------|-----------------|
| Rota retorna 200 para usuário com acesso | `test_routes.py` | `assert r.status_code == 200` |
| Rota redireciona usuário sem acesso | `test_routes.py` | `assert r.status_code in (302, 308)` |
| Rota redireciona usuário sem sessão | `test_routes.py` (lista `ROTAS_PROTEGIDAS`) | `assert 'login' in Location` |
| Endpoint JSON tem campos mínimos | `test_api_json.py` | `assert 'campo_chave' in data` |
| Tempo de carregamento aceitável | `test_performance.py` | adicionar na dict `LIMITES` |

### 2.2 Adicionar rota à lista de rotas protegidas

Em `testes/test_routes.py`, dentro de `TestAcessoNaoAutenticado`:

```python
ROTAS_PROTEGIDAS = [
    '/',
    '/parcerias/',
    '/gestao_financeira/',
    '/minha_nova_rota/',      # ← adicionar aqui
    '/admin/painel-erros',
]
```

### 2.3 Adicionar guarda de performance

Em `testes/test_performance.py`:

```python
LIMITES = {
    '/parcerias/?limite=50': 6.0,
    '/minha_nova_rota/':     3.0,   # ← adicionar aqui (segundos)
}
```

---

## 3. Decorators do FAF e Como Testá-los

### 3.1 `@login_required` (utils.py)

**O que faz:** Redireciona para `/login` se não houver `session['user_id']`.

**Como testar:**
```python
def test_redirect_sem_sessao(client):           # client = sem sessão
    r = client.get('/minha_rota/', follow_redirects=False)
    assert r.status_code in (302, 308)
    assert 'login' in r.headers['Location'].lower()
```

**Fixture sem sessão:** `client` (definido em `conftest.py`)

---

### 3.2 `@requires_access('nome_modulo')` (decorators.py)

**O que faz:** Verifica `session['acessos']` — se o módulo não estiver listado, redireciona.

**Como testar:**
```python
def test_acesso_negado(client_usuario):         # acessos = 'parcerias' apenas
    r = client_usuario.get('/gestao_financeira/', follow_redirects=False)
    assert r.status_code in (302, 308)

def test_acesso_permitido(client_admin):        # acessos = tudo
    r = client_admin.get('/gestao_financeira/')
    assert r.status_code == 200
```

**Para testar um módulo específico**, crie uma fixture com exatamente os acessos necessários:
```python
@pytest.fixture()
def client_modulo_x(app):
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 10
            sess['email'] = 'user@test.com'
            sess['d_usuario'] = 'd000010'
            sess['tipo_usuario'] = 'Agente DGP'
            sess['acessos'] = 'modulo_x'   # só este módulo
        yield c
```

---

### 3.3 `@capture_errors` (decorators.py)

**O que faz:** Captura exceções não tratadas → grava em `gestao_pessoas.log_erros` → re-lança.

**Quando usar:** Rotas críticas onde você quer que erros apareçam no Painel de Erros  
(`/admin/painel-erros`) mesmo sem tratamento explícito.

**Como aplicar:**
```python
from decorators import requires_access, capture_errors

@meu_bp.route('/minha_rota/')
@login_required
@requires_access('meu_modulo')
@capture_errors                   # ← por último entre os decorators FAF
def minha_view():
    ...
```

**Ordem correta dos decorators:**
```
@rota
@login_required
@requires_access('modulo')
@capture_errors       ← sempre o último decorator FAF (mais interno na pilha)
def view():
```

**Como testar que erros são capturados:**
```python
def test_erro_capturado_no_log(client_admin, app):
    with app.app_context():
        from db import get_cursor
        cur = get_cursor()
        cur.execute("SELECT COUNT(*) AS n FROM gestao_pessoas.log_erros WHERE endpoint LIKE '%minha_rota%'")
        antes = cur.fetchone()['n']

    # Forçar um erro (mock ou rota de teste)
    client_admin.get('/minha_rota/?forcar_erro=1')

    with app.app_context():
        cur = get_cursor()
        cur.execute("SELECT COUNT(*) AS n FROM gestao_pessoas.log_erros WHERE endpoint LIKE '%minha_rota%'")
        depois = cur.fetchone()['n']

    assert depois > antes
```

---

### 3.4 `registrar_erro()` chamado manualmente (decorators.py)

**Quando usar:** Blocos de erro controlados (try/except), APIs externas, queries lentas.

```python
from decorators import registrar_erro

try:
    resposta = requests.get(url, timeout=10)
    resposta.raise_for_status()
except requests.HTTPError as e:
    registrar_erro(
        tipo_erro='api_externa',
        api_nome='NOME_API',
        api_endpoint=url,
        mensagem=str(e),
        status_codigo=getattr(e.response, 'status_code', None),
    )
    return jsonify({'erro': 'Serviço indisponível'}), 502
```

**Campos disponíveis em `registrar_erro()`:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tipo_erro` | str | `'http_erro'`, `'query_lenta'`, `'api_externa'`, `'exception'` |
| `endpoint` | str | URL da rota (auto-detectado se em contexto Flask) |
| `metodo` | str | `GET`, `POST`, etc. |
| `status_codigo` | int | Código HTTP |
| `usuario_email` | str | (auto-detectado da sessão) |
| `ip_address` | str | (auto-detectado) |
| `duracao_ms` | float | Tempo em ms (para queries lentas) |
| `query_preview` | str | Trecho da query SQL |
| `api_nome` | str | Nome da API externa |
| `api_endpoint` | str | URL da API |
| `mensagem` | str | Mensagem de erro resumida |
| `detalhes` | dict | Qualquer dado extra (serializado como JSONB) |

---

## 4. APIs Externas — Padrão de Teste

Para qualquer nova integração com API externa (SOF, FUMCAD, etc.):

### 4.1 Teste de contrato básico

```python
class TestMinhaApi:
    def test_sem_params_retorna_erro(self, client_admin):
        r = client_admin.post('/meu_modulo/api/consultar', json={})
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            data = r.get_json()
            assert data.get('success') is False or data.get('erro')

    def test_acesso_negado_sem_sessao(self, client):
        r = client.post('/meu_modulo/api/consultar', json={'param': 'valor'})
        assert r.status_code in (302, 308, 401, 403)

    def test_resposta_json_valida(self, client_admin):
        r = client_admin.post(
            '/meu_modulo/api/consultar',
            json={'ano': '2025', 'orgao': '16'},
            content_type='application/json'
        )
        if r.status_code == 200:
            data = r.get_json()
            assert data is not None
            assert isinstance(data, (list, dict))
```

### 4.2 Erro de API deve aparecer no log

Após acionar um erro conhecido de API, verificar:
```python
with app.app_context():
    cur = get_cursor()
    cur.execute("""
        SELECT COUNT(*) AS n FROM gestao_pessoas.log_erros
        WHERE tipo_erro = 'api_externa' AND api_nome = 'NOME_API'
    """)
    assert cur.fetchone()['n'] > 0
```

---

## 5. Fixtures Disponíveis (conftest.py)

| Fixture | Tipo de usuário | Acessos |
|---------|----------------|---------|
| `client` | sem sessão | nenhum |
| `client_admin` | Agente Público | todos os módulos |
| `client_usuario` | Agente DGP | `parcerias` apenas |
| `app` | — | instância Flask TESTING |
| `db_cursor` | — | cursor de banco (em `test_query_parcerias.py`) |

---

## 6. Convenções

- Arquivos de teste: sempre `test_*.py` dentro de `testes/`
- Classes de teste: `class TestNomeDoModulo:`
- Métodos: `def test_descricao_clara(self, fixture):`
- Usar `pytest.skip("motivo")` se o banco não tiver dados suficientes
- Não depender de dados específicos — testar apenas contratos (estrutura, status, campos)
- `client_admin` para testes funcionais, `client` para testes de segurança/acesso
