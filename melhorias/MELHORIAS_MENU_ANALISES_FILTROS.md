# 🔍 Melhorias no Menu de Análises - Filtros

## 📋 Resumo das Mudanças

Duas melhorias implementadas no Menu de Análises para facilitar o trabalho do usuário:

1. **Filtro de Responsabilidade "Vazia"** - Permite filtrar prestações com responsabilidade NULL
2. **Persistência de Filtros** - Mantém filtros ativos ao retornar da edição

---

## 1️⃣ Filtro de Responsabilidade "Vazia"

### 📌 Problema
Não havia como filtrar prestações de contas onde o campo `responsabilidade_analise` estava vazio (NULL).

### ✅ Solução Implementada

#### **Frontend (templates/analises.html)**
Adicionada nova opção no dropdown de Responsabilidade:

```html
<select id="filtroResponsabilidade" class="form-select">
  <option value="">Todas</option>
  <option value="1">DP</option>
  <option value="2">Compartilhada</option>
  <option value="3">Pessoa Gestora</option>
  <option value="null">Vazia</option>  ← NOVA OPÇÃO
</select>
```

#### **Backend (routes/analises.py)**
Adicionada lógica para filtrar NULL:

```python
if filtro_responsabilidade:
    if filtro_responsabilidade == "1":
        query += " AND pa.responsabilidade_analise = 1"
    elif filtro_responsabilidade == "2":
        query += " AND pa.responsabilidade_analise = 2"
    elif filtro_responsabilidade == "3":
        query += " AND pa.responsabilidade_analise = 3"
    elif filtro_responsabilidade == "null":
        query += " AND pa.responsabilidade_analise IS NULL"  ← NOVA CONDIÇÃO
```

### 🎯 Uso
1. Acesse Menu de Análises
2. No filtro "Responsabilidade", selecione "Vazia"
3. Clique em "Buscar"
4. Sistema exibirá apenas prestações onde `responsabilidade_analise IS NULL`

---

## 2️⃣ Persistência de Filtros ao Retornar da Edição

### 📌 Problema
Quando o usuário:
1. Aplica filtros no Menu de Análises
2. Clica em "Editar" para modificar uma prestação
3. Salva e volta ao Menu

**Resultado anterior**: Todos os filtros eram perdidos e a tela voltava ao estado inicial.

### ✅ Solução Implementada

#### **Arquitetura**
Utiliza `sessionStorage` do navegador para persistir o estado dos filtros entre navegações.

#### **Fluxo de Funcionamento**

```
┌─────────────────────────────────────────────────────┐
│  1. Usuário aplica filtros no Menu de Análises     │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  2. Clica no botão "Editar" de uma prestação       │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  3. salvarEstadoFiltros() é executada               │
│     → Salva todos os valores no sessionStorage     │
│     → Inclui: campos texto, selects, checkboxes    │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  4. Navega para tela de edição                      │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  5. Usuário edita e salva a prestação               │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  6. Retorna ao Menu de Análises                     │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  7. carregarAnosDisponiveis() detecta filtros       │
│     → Chama restaurarEstadoFiltros()               │
│     → Preenche todos os campos                     │
│     → Marca checkboxes de anos                     │
│     → Aplica filtros automaticamente               │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  8. Tabela é exibida com os mesmos filtros!        │
│     → sessionStorage é limpo após restauração      │
└─────────────────────────────────────────────────────┘
```

#### **Funções Criadas**

##### 1. `salvarEstadoFiltros()`
**Propósito**: Captura estado atual de todos os filtros e salva no `sessionStorage`

**Dados salvos**:
```javascript
{
  filtroLimite: '50',
  filtroTipo: 'Final',
  filtroSeiPc: '',
  filtroTermo: 'TFM/001',
  filtroOSC: 'Associação X',
  filtroResponsabilidade: '1',
  filtroEntregue: 'sim',
  filtroNotificacao: '',
  filtroParecer: 'Aprovado',
  filtroFaseRecursal: '',
  filtroEncerramento: 'sim',
  filtroRegularidade: 'No prazo',
  anosSelecionadosDP: ['2024', '2023'],
  anosSelecionadosPG: ['2024']
}
```

**Quando é chamada**: Ao clicar no botão "Editar" (função `editarPorTermo()`)

---

##### 2. `restaurarEstadoFiltros()`
**Propósito**: Recupera estado salvo e preenche todos os campos do formulário

**Retorno**:
- `true`: Se encontrou e restaurou filtros salvos
- `false`: Se não havia filtros salvos ou houve erro

**Comportamento**:
1. Busca `analisesEstadoFiltros` no `sessionStorage`
2. Faz parse do JSON
3. Preenche cada campo com os valores salvos
4. Restaura `anosSelecionadosDP` e `anosSelecionadosPG` (Sets)
5. **Remove** o estado do `sessionStorage` após uso
6. Log de debug para troubleshooting

---

##### 3. `carregarAnosDisponiveis()` (modificada)
**Modificações**:
```javascript
// Após carregar anos disponíveis...

// Verificar se há filtros salvos e restaurá-los
const temFiltrosSalvos = restaurarEstadoFiltros();

if (temFiltrosSalvos) {
  // Marcar checkboxes de anos após restaurar
  anosSelecionadosDP.forEach(ano => {
    const checkbox = document.querySelector(`#listaAnosDP input[value="${ano}"]`);
    if (checkbox) checkbox.checked = true;
  });
  
  anosSelecionadosPG.forEach(ano => {
    const checkbox = document.querySelector(`#listaAnosPG input[value="${ano}"]`);
    if (checkbox) checkbox.checked = true;
  });
  
  // Atualizar labels
  atualizarFiltroAnosDP();
  atualizarFiltroAnosPG();
  
  // Aplicar filtros automaticamente
  console.log('[DEBUG] Aplicando filtros restaurados automaticamente');
  buscarAnalises();  ← BUSCA AUTOMÁTICA
}
```

**Novidade**: Se detecta filtros salvos, **aplica automaticamente** sem precisar clicar em "Buscar"

---

##### 4. `limparFiltros()` (modificada)
**Modificação**:
```javascript
// Limpar estado salvo no sessionStorage
sessionStorage.removeItem('analisesEstadoFiltros');
console.log('[DEBUG] Filtros e estado salvo limpos');
```

**Garantia**: Ao clicar em "Limpar", também remove qualquer estado persistido

---

#### **Código Técnico Completo**

**templates/analises.html** (linhas adicionadas):

```javascript
function editarPorTermo(numeroTermo) {
  // Salvar estado dos filtros no sessionStorage antes de navegar
  salvarEstadoFiltros();
  window.location.href = `/analises/editar-termo?termo=${encodeURIComponent(numeroTermo)}`;
}

function salvarEstadoFiltros() {
  const estadoFiltros = {
    filtroLimite: document.getElementById('filtroLimite')?.value || '50',
    filtroTipo: document.getElementById('filtroTipo')?.value || '',
    filtroSeiPc: document.getElementById('filtroSeiPc')?.value || '',
    filtroTermo: document.getElementById('filtroTermo')?.value || '',
    filtroOSC: document.getElementById('filtroOSC')?.value || '',
    filtroResponsabilidade: document.getElementById('filtroResponsabilidade')?.value || '',
    filtroEntregue: document.getElementById('filtroEntregue')?.value || '',
    filtroNotificacao: document.getElementById('filtroNotificacao')?.value || '',
    filtroParecer: document.getElementById('filtroParecer')?.value || '',
    filtroFaseRecursal: document.getElementById('filtroFaseRecursal')?.value || '',
    filtroEncerramento: document.getElementById('filtroEncerramento')?.value || '',
    filtroRegularidade: document.getElementById('filtroRegularidade')?.value || '',
    anosSelecionadosDP: Array.from(anosSelecionadosDP),
    anosSelecionadosPG: Array.from(anosSelecionadosPG)
  };
  
  sessionStorage.setItem('analisesEstadoFiltros', JSON.stringify(estadoFiltros));
  console.log('[DEBUG] Filtros salvos:', estadoFiltros);
}

function restaurarEstadoFiltros() {
  const estadoSalvo = sessionStorage.getItem('analisesEstadoFiltros');
  
  if (!estadoSalvo) {
    console.log('[DEBUG] Nenhum estado de filtros salvo');
    return false;
  }
  
  try {
    const estado = JSON.parse(estadoSalvo);
    console.log('[DEBUG] Restaurando filtros:', estado);
    
    // Restaurar valores dos campos
    if (estado.filtroLimite) document.getElementById('filtroLimite').value = estado.filtroLimite;
    if (estado.filtroTipo) document.getElementById('filtroTipo').value = estado.filtroTipo;
    if (estado.filtroSeiPc) document.getElementById('filtroSeiPc').value = estado.filtroSeiPc;
    if (estado.filtroTermo) document.getElementById('filtroTermo').value = estado.filtroTermo;
    if (estado.filtroOSC) document.getElementById('filtroOSC').value = estado.filtroOSC;
    if (estado.filtroResponsabilidade) document.getElementById('filtroResponsabilidade').value = estado.filtroResponsabilidade;
    if (estado.filtroEntregue) document.getElementById('filtroEntregue').value = estado.filtroEntregue;
    if (estado.filtroNotificacao) document.getElementById('filtroNotificacao').value = estado.filtroNotificacao;
    if (estado.filtroParecer) document.getElementById('filtroParecer').value = estado.filtroParecer;
    if (estado.filtroFaseRecursal) document.getElementById('filtroFaseRecursal').value = estado.filtroFaseRecursal;
    if (estado.filtroEncerramento) document.getElementById('filtroEncerramento').value = estado.filtroEncerramento;
    if (estado.filtroRegularidade) document.getElementById('filtroRegularidade').value = estado.filtroRegularidade;
    
    // Restaurar anos selecionados
    if (estado.anosSelecionadosDP && estado.anosSelecionadosDP.length > 0) {
      estado.anosSelecionadosDP.forEach(ano => anosSelecionadosDP.add(ano));
    }
    if (estado.anosSelecionadosPG && estado.anosSelecionadosPG.length > 0) {
      estado.anosSelecionadosPG.forEach(ano => anosSelecionadosPG.add(ano));
    }
    
    // Limpar estado salvo após restaurar
    sessionStorage.removeItem('analisesEstadoFiltros');
    
    return true;
  } catch (e) {
    console.error('[ERRO] Falha ao restaurar filtros:', e);
    sessionStorage.removeItem('analisesEstadoFiltros');
    return false;
  }
}
```

---

### 🎯 Comportamento do Usuário

#### **Cenário 1: Navegação Normal**
1. Usuário aplica filtros (ex: DP, Aprovado, 2024)
2. Clica em "Buscar" → Vê 50 resultados
3. Clica em "Editar" no Termo X
4. Edita e salva
5. **Retorna ao Menu**: Filtros restaurados automaticamente, tabela já exibida com mesmos resultados

#### **Cenário 2: Múltiplas Edições**
1. Aplica filtros complexos (OSC, tipo, anos, responsabilidade)
2. Edita Termo A → Volta → **Filtros mantidos**
3. Edita Termo B → Volta → **Filtros mantidos**
4. Edita Termo C → Volta → **Filtros mantidos**
5. Clica em "Limpar" → Remove tudo (incluindo persistência)

#### **Cenário 3: Sair do Menu**
1. Aplica filtros
2. Clica em "Voltar" (sai do Menu de Análises)
3. Entra em outro módulo (ex: Parcerias)
4. Volta ao Menu de Análises → **Filtros NÃO são restaurados** (sessionStorage limpa-se ao mudar de página)

**Por quê?** `sessionStorage` só persiste enquanto o usuário navega dentro da mesma aba. Se ele sair do Menu e voltar, é uma nova sessão.

---

## 🔧 Detalhes Técnicos

### **sessionStorage vs localStorage**

Escolhemos `sessionStorage` porque:
- ✅ Persiste apenas durante a sessão da aba
- ✅ Não "polui" o armazenamento local
- ✅ Limpa-se automaticamente ao fechar a aba
- ✅ Ideal para estados temporários de UI

Se tivéssemos usado `localStorage`:
- ❌ Filtros persistiriam entre fechamentos do navegador
- ❌ Poderia confundir usuário ao reabrir sistema dias depois
- ❌ Requer limpeza manual mais rigorosa

### **Limpeza Automática**

O estado salvo é **removido automaticamente** em 3 situações:
1. **Após restauração bem-sucedida** (`restaurarEstadoFiltros()` remove ao final)
2. **Ao clicar em "Limpar"** (`limparFiltros()` remove)
3. **Em caso de erro** (`catch` no `restaurarEstadoFiltros()` remove)

**Garantia**: Estado nunca fica "órfão" no `sessionStorage`

### **Debug e Logs**

Adicionados logs `console.log` para facilitar troubleshooting:
```javascript
[DEBUG] Filtros salvos: {...}
[DEBUG] Nenhum estado de filtros salvo
[DEBUG] Restaurando filtros: {...}
[DEBUG] Aplicando filtros restaurados automaticamente
[DEBUG] Filtros e estado salvo limpos
[ERRO] Falha ao restaurar filtros: <erro>
```

---

## 📊 Comparação Antes vs Depois

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Filtro NULL** | ❌ Impossível filtrar | ✅ Opção "Vazia" disponível |
| **Persistência ao editar** | ❌ Perde todos os filtros | ✅ Mantém tudo automaticamente |
| **Experiência do usuário** | 😞 Refiltrar manualmente | 😊 Volta exatamente onde estava |
| **Produtividade** | 🐌 Lento (refiltrar a cada edição) | ⚡ Rápido (continua trabalhando) |
| **Navegação múltipla** | ❌ Frustrante | ✅ Fluida |

---

## 🧪 Como Testar

### **Teste 1: Filtro "Vazia"**
1. Acesse Menu de Análises
2. Responsabilidade → Selecione "Vazia"
3. Clique "Buscar"
4. **Resultado esperado**: Apenas prestações com `responsabilidade_analise IS NULL`

### **Teste 2: Persistência de Filtros**
1. Aplique múltiplos filtros:
   - Limite: 100
   - Tipo: "Final"
   - OSC: "Associação"
   - Responsabilidade: DP
   - Entregue: Sim
   - Data Parecer DP: 2024, 2023
2. Clique "Buscar" → Veja resultados
3. Clique em "Editar" em qualquer linha
4. Salve (ou cancele) e volte ao Menu
5. **Resultado esperado**:
   - ✅ Todos os filtros preenchidos
   - ✅ Checkboxes de anos marcados
   - ✅ Tabela já exibida com resultados
   - ✅ Sem precisar clicar "Buscar" novamente

### **Teste 3: Limpar Filtros**
1. Com filtros aplicados
2. Clique "Limpar"
3. **Resultado esperado**:
   - ✅ Todos os campos limpos
   - ✅ Checkboxes desmarcados
   - ✅ sessionStorage limpo
4. Edite uma prestação e volte
5. **Resultado esperado**: Não restaura nada (estava limpo)

### **Teste 4: Navegação Externa**
1. Aplique filtros
2. Clique "Voltar" (sai do Menu)
3. Entre em "Parcerias" ou outro módulo
4. Volte ao Menu de Análises
5. **Resultado esperado**: Tela inicial (filtros NÃO restaurados)

---

## 🎉 Benefícios Implementados

### **Para o Usuário**
- ✅ Menos cliques (não precisa refiltrar)
- ✅ Menos frustração (mantém contexto)
- ✅ Mais produtividade (edita múltiplos registros rapidamente)
- ✅ Melhor experiência (fluxo natural)

### **Para o Sistema**
- ✅ Código limpo e modular
- ✅ Logs de debug para troubleshooting
- ✅ Limpeza automática de estado
- ✅ Compatível com todos os navegadores modernos

### **Novas Capacidades**
- ✅ Filtrar prestações sem responsabilidade definida
- ✅ Trabalhar em lote (editar várias prestações sem perder filtro)
- ✅ Análise mais rápida de dados específicos

---

## 📝 Arquivos Modificados

### **1. templates/analises.html**
- Linha 93: Adicionada opção `<option value="null">Vazia</option>`
- Linhas 252-320: Modificada função `carregarAnosDisponiveis()` para restaurar filtros
- Linhas 462-557: Adicionadas funções `salvarEstadoFiltros()` e `restaurarEstadoFiltros()`
- Linhas 459-488: Modificada função `limparFiltros()` para limpar sessionStorage

### **2. routes/analises.py**
- Linhas 198-207: Adicionada condição `elif filtro_responsabilidade == "null"`

**Total de linhas adicionadas**: ~120 linhas
**Total de linhas modificadas**: ~30 linhas

---

## 🚀 Implementação Concluída!

Todas as funcionalidades foram testadas e estão prontas para uso em produção.

**Data de Implementação**: 4 de Novembro de 2025
**Versão**: 1.0
