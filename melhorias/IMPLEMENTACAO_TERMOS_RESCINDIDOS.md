# Implementação do Sistema de Termos Rescindidos

## 📋 Resumo

Sistema completo para gerenciar termos rescindidos no sistema FAF, incluindo:
- Cadastro CRUD de termos rescindidos
- Integração com cálculo de prestações de contas
- Validação de execução mínima (5 dias)
- Indicadores visuais nos templates

## 🗄️ Estrutura do Banco de Dados

### Tabela: `public.termos_rescisao`

```sql
CREATE TABLE public.termos_rescisao (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_termo VARCHAR(30) NOT NULL UNIQUE,
    data_rescisao DATE NOT NULL,
    sei_rescisao VARCHAR(12)
);
```

**Campos:**
- `id`: Identificador único (auto-incremento)
- `numero_termo`: Número do termo rescindido (único)
- `data_rescisao`: Data em que o termo foi rescindido
- `sei_rescisao`: Número do processo SEI da rescisão

**Relacionamento:**
- `numero_termo` → `parcerias.numero_termo` (LEFT JOIN)

## 📁 Arquivos Modificados

### 1. **routes/parcerias.py**
Rotas CRUD para gerenciar rescisões:

#### `/parcerias/rescisoes` (GET)
- Lista todos os termos rescindidos
- Exibe formulário para cadastro
- LEFT JOIN com `parcerias` para mostrar nome da OSC

#### `/parcerias/rescisao/salvar` (POST)
- Valida existência do termo
- Previne duplicatas
- Inserta novo registro de rescisão

#### `/parcerias/rescisao/editar/<id>` (GET/POST)
- GET: Carrega dados para edição
- POST: Atualiza data_rescisao e sei_rescisao
- `numero_termo` não pode ser alterado (disabled)

#### `/parcerias/rescisao/deletar/<id>` (POST)
- Deleta registro de rescisão
- Mostra confirmação modal

### 2. **routes/analises.py**
Integração da rescisão nas análises de prestação de contas:

#### Função: `obter_data_rescisao(numero_termo)`
```python
def obter_data_rescisao(numero_termo):
    """
    Busca a data de rescisão de um termo, se houver.
    Retorna None se o termo não foi rescindido.
    """
    cur = get_cursor()
    cur.execute("""
        SELECT data_rescisao 
        FROM public.termos_rescisao 
        WHERE numero_termo = %s
    """, (numero_termo,))
    resultado = cur.fetchone()
    cur.close()
    return resultado['data_rescisao'] if resultado else None
```

#### Rota: `adicionar_analises()` - GET
**Modificação na query:**
```sql
SELECT DISTINCT 
    p.numero_termo, 
    p.inicio, 
    p.final,
    p.portaria,
    tr.data_rescisao,
    CASE 
        WHEN tr.data_rescisao IS NOT NULL THEN tr.data_rescisao
        ELSE p.final
    END as vigencia_efetiva
FROM Parcerias p
LEFT JOIN public.termos_rescisao tr ON p.numero_termo = tr.numero_termo
WHERE p.numero_termo NOT IN (
    SELECT DISTINCT numero_termo FROM parcerias_analises
)
AND p.inicio IS NOT NULL
AND p.final IS NOT NULL
-- Excluir termos rescindidos em até 5 dias após o início (execução mínima)
AND (tr.data_rescisao IS NULL OR tr.data_rescisao > p.inicio + INTERVAL '5 days')
ORDER BY p.numero_termo DESC
```

**Regra de Negócio:**
- Termos rescindidos ≤5 dias após início NÃO aparecem na lista
- Apenas termos com execução mínima de 6+ dias são mostrados

#### Rota: `calcular_prestacoes()` - API POST
**Validação de 5 dias:**
```python
if data_rescisao:
    dias_execucao = (data_rescisao - data_inicio).days
    if dias_execucao <= 5:
        return jsonify({
            'erro': f'Termo foi rescindido em {data_rescisao.strftime("%d/%m/%Y")}, 
                     apenas {dias_execucao} dia(s) após o início. 
                     Não há prestações de contas a serem geradas 
                     (execução mínima não atingida).',
            'data_rescisao': data_rescisao.strftime('%d/%m/%Y'),
            'dias_execucao': dias_execucao
        }), 400
```

**Resposta com rescisão:**
```python
if data_rescisao:
    resposta['rescindido'] = True
    resposta['data_rescisao'] = data_rescisao.strftime('%d/%m/%Y')
    resposta['aviso'] = f'⚠️ Este termo foi rescindido em {data_rescisao.strftime("%d/%m/%Y")}. 
                          As prestações foram calculadas até esta data.'
```

#### Rota: `atualizar_prestacoes()` - POST
**Recalculo com rescisão:**
```python
# Usar data de rescisão como término se existir
data_termino = data_rescisao if data_rescisao else data_termino_original

# Validar execução mínima
if data_rescisao:
    dias_execucao = (data_rescisao - data_inicio).days
    if dias_execucao <= 5:
        return jsonify({
            'erro': f'Termo foi rescindido apenas {dias_execucao} dia(s) após o início. 
                     Execução mínima não atingida.',
            'numero_termo': numero_termo
        }), 400

# Recalcular prestações
prestacoes_corretas = gerar_prestacoes(numero_termo, data_inicio, data_termino, portaria)
```

**Logging de prestações deletadas:**
```python
prestacoes_deletadas_entregues = []
for prestacao in prestacoes_cadastradas:
    if prestacao['id'] not in ids_atualizados:
        # Log se já estava entregue
        cur.execute("""
            SELECT data_entrega_pg 
            FROM parcerias_analises 
            WHERE id = %s AND data_entrega_pg IS NOT NULL
        """, (prestacao['id'],))
        if cur.fetchone():
            prestacoes_deletadas_entregues.append(
                f"{prestacao['tipo_prestacao']} {prestacao['numero_prestacao']}"
            )
        
        # Deletar
        cur.execute("DELETE FROM parcerias_analises WHERE id = %s", (prestacao['id'],))

# Mensagem com prestações deletadas
if prestacoes_deletadas_entregues:
    mensagem += f" ⚠️ Prestações já entregues foram excluídas: {', '.join(prestacoes_deletadas_entregues)}"
```

#### Rota: `atualizar_prestacoes()` - GET
**Dados para template:**
```python
termos_divergentes[numero_termo] = {
    'numero_termo': numero_termo,
    'sei_celeb': termo['sei_celeb'],
    'data_inicio_termo': data_inicio,
    'data_final_termo': data_termino,
    'data_final_original': data_termino_original,  # Original da tabela parcerias
    'data_rescisao': data_rescisao,  # Data de rescisão se houver
    'rescindido': data_rescisao is not None,  # Boolean para template
    # ... outros campos
}
```

### 3. **templates/termos_rescindidos.html**
Interface completa para gerenciar rescisões:

**Recursos:**
- ✅ Select2 para busca de termos (dropdown com pesquisa)
- ✅ Date picker para data_rescisao
- ✅ Campo SEI com validação (pattern="[0-9.-/]+")
- ✅ Tabela com todas as rescisões cadastradas
- ✅ Ações: Editar e Deletar (com modal de confirmação)
- ✅ Alerta informativo sobre regras de negócio
- ✅ Prevenção de duplicatas
- ✅ Campo `numero_termo` disabled na edição

**Validações JavaScript:**
```javascript
// Prevenir rescisão duplicada
if (termoJaRescindido) {
    alert('Este termo já foi marcado como rescindido!');
    return;
}

// Campo disabled na edição + hidden input
document.getElementById('numero_termo').disabled = true;
```

### 4. **templates/adicionar_analises.html**
Indicadores visuais de rescisão na seleção de termos:

**Badge de status:**
```html
{% if termo.data_rescisao %}
  <span class="badge bg-danger ms-2" 
        title="Termo rescindido em {{ termo.data_rescisao.strftime('%d/%m/%Y') }}">
    🔴 RESCINDIDO
  </span>
{% endif %}
```

**Exibição de datas:**
```html
Período: {{ termo.inicio.strftime('%d/%m/%Y') }} 
até 
{% if termo.data_rescisao %}
  <strong class="text-danger">{{ termo.data_rescisao.strftime('%d/%m/%Y') }}</strong>
  <span class="text-danger">(rescindido)</span>
  <span class="text-muted" style="text-decoration: line-through;">
    {{ termo.final.strftime('%d/%m/%Y') }}
  </span>
{% else %}
  {{ termo.final.strftime('%d/%m/%Y') }}
{% endif %}
```

**Alerta ao gerar prestações:**
```javascript
// Receber dados da API
renderizarPrestacoes(numeroTermo, prestacoesGeradas, result.rescindido, result.aviso);

// Mostrar alerta
if (rescindido && aviso) {
  const alertHtml = `
    <div class="alert alert-warning alert-dismissible fade show" role="alert">
      <i class="bi bi-exclamation-triangle-fill me-2"></i>
      <strong>Atenção!</strong> ${aviso}
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>
  `;
  container.innerHTML = alertHtml;
}
```

### 5. **templates/atualizar_prestacoes.html**
Indicadores visuais de rescisão na atualização de prestações:

**Badge no cabeçalho:**
```html
{% if termo.rescindido %}
  <span class="badge bg-dark ms-2" 
        title="Termo rescindido em {{ termo.data_rescisao.strftime('%d/%m/%Y') }}">
    🔴 RESCINDIDO
  </span>
{% endif %}
```

**Alerta de rescisão:**
```html
{% if termo.rescindido %}
<div class="alert alert-warning mb-3">
  <i class="bi bi-exclamation-triangle-fill me-2"></i>
  <strong>Termo Rescindido!</strong> 
  Este termo foi rescindido em <strong>{{ termo.data_rescisao.strftime('%d/%m/%Y') }}</strong>.
  As prestações serão recalculadas até esta data.
  {% if termo.data_final_original %}
  <br>
  <small class="text-muted">
    Data final original: {{ termo.data_final_original.strftime('%d/%m/%Y') }}
  </small>
  {% endif %}
</div>
{% endif %}
```

**Vigência com indicador:**
```html
<strong>Vigência do Termo:</strong>
{{ termo.data_inicio_termo.strftime('%d/%m/%Y') }}
até
{% if termo.rescindido %}
  <strong class="text-danger">{{ termo.data_final_termo.strftime('%d/%m/%Y') }}</strong>
  <span class="text-danger">(rescindido)</span>
{% else %}
  {{ termo.data_final_termo.strftime('%d/%m/%Y') }}
{% endif %}
```

### 6. **templates/parcerias.html**
Botão de acesso ao gerenciamento de rescisões:

```html
<a href="{{ url_for('parcerias.rescisoes') }}" 
   class="btn btn-danger" 
   title="Cadastrar termos que foram rescindidos">
  <i class="bi bi-x-circle me-2"></i>Cadastrar Termos Rescindidos
</a>
```

## 🎯 Regras de Negócio

### 1. **Execução Mínima de 5 Dias**
Termos rescindidos em até 5 dias após o início são **excluídos** do sistema de prestações:

**Exemplo 1 - Excluído:**
- Início: 19/01/2022
- Rescisão: 23/01/2022 (4 dias depois)
- ❌ Não aparece em "Adicionar Análises"
- ❌ API retorna erro se tentar calcular

**Exemplo 2 - Incluído:**
- Início: 19/01/2022
- Rescisão: 25/01/2022 (6 dias depois)
- ✅ Aparece em "Adicionar Análises"
- ✅ Prestações calculadas até 25/01/2022

### 2. **Data de Rescisão como Término Efetivo**
Quando um termo é rescindido:
- `data_rescisao` substitui `p.final` em **todos** os cálculos
- Prestações são calculadas apenas até a data de rescisão
- `vigencia_efetiva = data_rescisao ?? p.final`

### 3. **Exclusão de Prestações Excedentes**
Na atualização de prestações:
- Prestações com `vigencia_final > data_rescisao` são **deletadas**
- Se a prestação estava marcada como "entregue", o sistema **registra no log**
- Mensagem exibe: "⚠️ Prestações já entregues foram excluídas: Trimestral 1, Semestral 2"

### 4. **Prevenção de Duplicatas**
- Cada `numero_termo` pode ter apenas UMA rescisão
- Constraint UNIQUE na coluna `numero_termo`
- Validação na interface: "Este termo já foi marcado como rescindido!"

### 5. **Imutabilidade do Termo na Edição**
- Ao editar uma rescisão, o `numero_termo` **não pode ser alterado**
- Campo aparece disabled no formulário
- Hidden input garante envio do valor original

## 📊 Fluxo de Dados

### Fluxo 1: Cadastro de Rescisão
```
1. Usuário acessa /parcerias/rescisoes
2. Seleciona termo no dropdown (Select2)
3. Define data_rescisao e sei_rescisao
4. Sistema valida:
   - Termo existe em parcerias?
   - Termo já foi rescindido?
5. Insere em public.termos_rescisao
6. Flash message: "Rescisão cadastrada com sucesso!"
```

### Fluxo 2: Adicionar Análises (com Rescisão)
```
1. Usuário acessa /analises/adicionar
2. Sistema busca termos pendentes:
   - LEFT JOIN com termos_rescisao
   - Filtra: data_rescisao > inicio + 5 dias
3. Template exibe badge "🔴 RESCINDIDO"
4. Usuário seleciona termo e clica "Gerar Prestações"
5. API /api/calcular-prestacoes:
   - Valida execução mínima (5 dias)
   - Calcula prestações até data_rescisao
   - Retorna: {rescindido: true, aviso: "..."}
6. Template exibe alerta amarelo com aviso
7. Usuário salva normalmente
```

### Fluxo 3: Atualizar Prestações (com Rescisão)
```
1. Usuário acessa /analises/atualizar
2. Sistema busca termos com divergências:
   - LEFT JOIN com termos_rescisao
   - Compara vigencia_efetiva com cadastradas
3. Template exibe:
   - Badge "🔴 RESCINDIDO" no cabeçalho
   - Alerta: "Termo rescindido em DD/MM/YYYY"
   - Vigência com data riscada e efetiva em vermelho
4. Usuário confirma atualização
5. Sistema recalcula:
   - Usa data_rescisao como término
   - Deleta prestações excedentes
   - Loga prestações entregues deletadas
6. Resposta mostra termos atualizados + log
```

## 🧪 Casos de Teste

### Teste 1: Rescisão Imediata (< 5 dias)
```
Dado: Termo 001/2024 iniciou em 10/01/2024
Quando: Rescindido em 14/01/2024 (4 dias)
Então:
  - Não aparece em /analises/adicionar
  - API retorna: {"erro": "apenas 4 dia(s) após o início"}
  - Status HTTP: 400
```

### Teste 2: Rescisão Válida (> 5 dias)
```
Dado: Termo 002/2024 iniciou em 10/01/2024
Quando: Rescindido em 20/01/2024 (10 dias)
Então:
  - Aparece em /analises/adicionar com badge
  - API calcula prestações até 20/01/2024
  - Resposta: {rescindido: true, aviso: "..."}
```

### Teste 3: Atualização com Deletação de Prestações
```
Dado: Termo com Trimestral 1, 2, 3, 4 cadastradas
  - Trimestral 1: 01/01 - 31/03 (entregue)
  - Trimestral 2: 01/04 - 30/06 (entregue)
  - Trimestral 3: 01/07 - 30/09 (não entregue)
  - Trimestral 4: 01/10 - 31/12 (não entregue)
Quando: Rescindido em 15/08/2024
Então:
  - Trimestral 1 e 2 mantidas
  - Trimestral 3 e 4 deletadas
  - Log: "Prestações já entregues foram excluídas: Trimestral 2"
```

### Teste 4: Duplicata Bloqueada
```
Dado: Termo 003/2024 já rescindido em 10/02/2024
Quando: Tentar cadastrar nova rescisão
Então:
  - Banco rejeita (UNIQUE constraint)
  - Mensagem: "Este termo já foi marcado como rescindido!"
```

### Teste 5: Edição de Rescisão
```
Dado: Rescisão cadastrada (termo 004/2024, data 15/03/2024)
Quando: Editar data para 20/03/2024
Então:
  - numero_termo permanece 004/2024 (disabled)
  - data_rescisao atualiza para 20/03/2024
  - sei_rescisao atualiza se alterado
```

## 📝 Mensagens do Sistema

### Sucesso
- ✅ "Rescisão cadastrada com sucesso!"
- ✅ "Rescisão atualizada com sucesso!"
- ✅ "Rescisão deletada com sucesso!"
- ✅ "X prestações atualizadas, Y adicionadas, Z removidas para N termos."

### Avisos
- ⚠️ "Este termo foi rescindido em DD/MM/YYYY. As prestações foram calculadas até esta data."
- ⚠️ "Prestações já entregues foram excluídas: Trimestral 1, Semestral 2"

### Erros
- ❌ "Termo foi rescindido em DD/MM/YYYY, apenas X dia(s) após o início. Não há prestações de contas a serem geradas (execução mínima não atingida)."
- ❌ "Este termo já foi marcado como rescindido!"
- ❌ "Termo não encontrado na tabela de parcerias."

## 🎨 Elementos Visuais

### Badges
```html
<!-- Template: adicionar_analises.html -->
<span class="badge bg-danger ms-2">🔴 RESCINDIDO</span>

<!-- Template: atualizar_prestacoes.html -->
<span class="badge bg-dark ms-2">🔴 RESCINDIDO</span>
```

### Alertas
```html
<!-- Alerta amarelo (warning) -->
<div class="alert alert-warning alert-dismissible fade show">
  <i class="bi bi-exclamation-triangle-fill me-2"></i>
  <strong>Atenção!</strong> Este termo foi rescindido...
</div>

<!-- Alerta informativo -->
<div class="alert alert-info mb-3">
  <i class="bi bi-info-circle me-2"></i>
  Rescisões cadastradas são usadas para calcular...
</div>
```

### Datas Riscadas
```html
<span class="text-muted" style="text-decoration: line-through;">
  31/12/2024
</span>
```

### Cores
- 🔴 Vermelho (`text-danger`, `bg-danger`): Rescisões
- ⚠️ Amarelo (`alert-warning`): Avisos importantes
- ℹ️ Azul (`alert-info`): Informações gerais

## 🚀 Deploy e Testes

### 1. Criar Tabela no PostgreSQL
```sql
CREATE TABLE public.termos_rescisao (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_termo VARCHAR(30) NOT NULL UNIQUE,
    data_rescisao DATE NOT NULL,
    sei_rescisao VARCHAR(12)
);
```

### 2. Verificar Integridade
```sql
-- Verificar rescisões cadastradas
SELECT * FROM public.termos_rescisao;

-- Verificar LEFT JOIN com parcerias
SELECT p.numero_termo, p.inicio, p.final, tr.data_rescisao
FROM Parcerias p
LEFT JOIN public.termos_rescisao tr ON p.numero_termo = tr.numero_termo
WHERE tr.data_rescisao IS NOT NULL;
```

### 3. Teste de Fluxo Completo
```
1. Cadastrar rescisão: /parcerias/rescisoes
2. Verificar exclusão em: /analises/adicionar
3. Tentar calcular prestações (deve avisar sobre rescisão)
4. Verificar atualização em: /analises/atualizar
5. Editar data de rescisão
6. Recalcular prestações (deve usar nova data)
7. Deletar rescisão
8. Verificar que termo volta a aparecer normalmente
```

## 📚 Documentação Adicional

### Arquivos Relacionados
- `routes/parcerias.py` - CRUD de rescisões
- `routes/analises.py` - Integração com prestações
- `templates/termos_rescindidos.html` - Interface de gerenciamento
- `templates/adicionar_analises.html` - Indicadores na adição
- `templates/atualizar_prestacoes.html` - Indicadores na atualização
- `templates/parcerias.html` - Botão de acesso

### Dependências
- Bootstrap 5.3.0 (badges, alerts, cards)
- Bootstrap Icons 1.10.5 (ícones)
- Select2 4.1.0 (dropdown com busca)
- jQuery 3.6.0 (manipulação DOM)

## 🔧 Manutenção

### Adicionar Nova Validação
```python
# Em routes/analises.py
def validar_rescisao_customizada(numero_termo, data_inicio, data_rescisao):
    """Adicione validações customizadas aqui"""
    # Exemplo: Não permitir rescisão em finais de semana
    if data_rescisao.weekday() >= 5:  # Sábado ou Domingo
        raise ValueError("Rescisão não pode ser em final de semana")
```

### Adicionar Novos Campos
```sql
-- Adicionar coluna motivo_rescisao
ALTER TABLE public.termos_rescisao 
ADD COLUMN motivo_rescisao TEXT;

-- Atualizar formulário em termos_rescindidos.html
-- Atualizar rotas em routes/parcerias.py
```

## 📈 Melhorias Futuras

### Curto Prazo
- [ ] Relatório de termos rescindidos por período
- [ ] Exportar rescisões para CSV/Excel
- [ ] Filtro por data de rescisão

### Médio Prazo
- [ ] Histórico de alterações em rescisões
- [ ] Anexar documentos da rescisão (SEI)
- [ ] Notificações automáticas para analistas

### Longo Prazo
- [ ] Dashboard com estatísticas de rescisões
- [ ] Integração com API do SEI para buscar processos
- [ ] Workflow de aprovação de rescisões

---

**Data de Implementação:** Janeiro 2025
**Autor:** Sistema FAF - Gestão de Parcerias
**Versão:** 1.0
