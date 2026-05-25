# 📊 SPEC: Conciliação Bancária v2 (`conc_bancaria_2`)

> **Versão:** 2.0  
> **Criado em:** 20/05/2026  
> **Status:** Em desenvolvimento  
> **Blueprint:** `/conc_bancaria_2`  
> **Baseado em:** `conc_bancaria` (v1) — mantém 100% das funcionalidades

---

## 🎯 Objetivo

Versão refatorada do módulo de conciliação bancária com foco em **performance de renderização**. O v1 apresenta lentidão com 1.000+ linhas, especialmente durante paste massivo, devido à criação de `<option>` elements em excesso e re-renders desnecessários.

---

## ⚡ Diferenças técnicas em relação ao v1

| Aspecto | v1 (`conc_bancaria`) | v2 (`conc_bancaria_2`) |
|---------|---------------------|------------------------|
| **Datalists de categoria** | Um `<datalist>` por linha (~250.000 `<option>` com 5.000 linhas) | 3 datalists globais (~150 `<option>` total) |
| **Atualização de linha** | `renderizarTabela()` completo (recria tudo) | `atualizarLinhaDOM(index)` cirúrgico |
| **Navegação Tab/Enter** | `tbody.children[index]` (bug com filtros ativos) | `querySelector('tr[data-index]')` (correto) |
| **Exclusão em lote** | N chamadas DELETE individuais via `Promise.all` | 1 chamada `DELETE /api/extrato/bulk` |
| **Handlers de ação** | `onclick` inline em cada linha | Event delegation com `data-action` |
| **CSS/JS** | Inline no template (290KB) | Arquivos estáticos (cacheáveis) |
| **URL prefix** | `/conc_bancaria` | `/conc_bancaria_2` |

### Por que não ag-Grid / Handsontable?
- **ag-Grid Community:** Clipboard (paste do Excel) é funcionalidade **Enterprise paga** — inviável
- **Handsontable Community (GPL):** Merged Cells (composição de linhas — core do módulo) é **Enterprise paga** — inviável
- **Conclusão:** Abordagem incremental sobre o código existente é a correta para este caso

---

## 🔗 Backend — Endpoints da API

### Herdados do v1 (sem alteração de lógica)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/extrato` | Lista movimentações do extrato |
| POST | `/api/extrato` | Salva múltiplas linhas (UPSERT) + automação de categorização |
| DELETE | `/api/extrato/<int:id>` | Exclui 1 linha específica |
| GET | `/api/termos` | Lista números de termos disponíveis |
| GET | `/api/categorias-despesas` | Categorias de despesa por termo |
| GET | `/api/categorias-analise` | Categorias de análise (todas) |
| GET | `/api/categorias-aplicabilidade` | Aplicabilidade das categorias (bool) |
| GET | `/api/categorias-rubricas` | Rubricas por termo |
| GET | `/api/periodo-termo` | Datas início/fim do termo |
| GET | `/api/banco` | Banco e conta de execução do extrato |
| POST | `/api/banco` | Salva banco e conta |
| POST | `/api/salvar-termo-session` | Salva termo atual na sessão |
| GET | `/api/notas-fiscais` | Lista notas fiscais do termo |
| POST | `/api/notas-fiscais` | Salva notas fiscais (UPSERT) |
| GET | `/api/documentos-analise` | Lista documentos de análise |
| POST | `/api/documentos-analise` | Salva documentos de análise (UPSERT + auto-marcação) |
| DELETE | `/api/limpar-termo` | Remove todos os dados de um termo |

### Novo no v2

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| DELETE | `/api/extrato/bulk` | Exclui múltiplas linhas em 1 query (`WHERE id = ANY(%s)`) |

---

## 📋 Tabelas do banco utilizadas

Todas em `analises_pc` e `public` — **sem alterações de schema**:

| Tabela | Operações |
|--------|-----------|
| `analises_pc.conc_extrato` | SELECT, INSERT, UPDATE, DELETE |
| `analises_pc.conc_extrato_notas_fiscais` | SELECT, INSERT, UPDATE, DELETE |
| `analises_pc.conc_analise` | SELECT, INSERT, UPDATE |
| `analises_pc.conc_banco` | SELECT, INSERT, UPDATE |
| `public.parcerias` | SELECT (numero_termo, portaria, transicao, inicio, final, conta) |
| `public.parcerias_despesas` | SELECT (categorias, rubricas por termo) |
| `categoricas.c_dac_despesas_analise` | SELECT (categorias de análise) |

---

## ✅ Checklist de paridade funcional (regressão obrigatória)

### Carregamento e navegação
- [ ] Seletor de termo: popula lista de termos ao abrir a página
- [ ] Carregar extrato por termo (modo 100, 200, todas, paginas)
- [ ] Modo 'paginas': filtrar por mês selecionado
- [ ] Recuperação de cache do IndexedDB ao trocar de termo
- [ ] Limpar cache ao salvar com sucesso

### Edição de células
- [ ] Campo Data (dd/mm/aaaa): aceita input e converte para ISO internamente
- [ ] Campo Crédito / Débito / Discriminação: formatação monetária BR no blur
- [ ] Validação: não pode ter crédito e débito na mesma linha (feedback visual)
- [ ] Campo Categoria: autocomplete via datalist (crédito vs débito filtra opções)
- [ ] Campo Competência: autocomplete + formatação mm/aaaa no blur
- [ ] Campo Competência: validação de intervalo do termo (± tolerância)
- [ ] Campo Origem/Destino: autocomplete com origem/destino anteriores
- [ ] Campo Avaliação: autocomplete + cor da linha (Avaliado=verde, Aguardando=amarelo, etc.)
- [ ] Campo Observações: texto livre

### Auto-preenchimento
- [ ] Data → preenche Competência automaticamente (1º do mês), respeitando `_competencia_deletada`
- [ ] Crédito/Débito → preenche Discriminação se vazio e não `_composicao_editada`
- [ ] Categoria → preenche Origem/Destino com correspondente (ou banco se "Banco")
- [ ] Categoria → preenche Avaliação "Glosar" se categoria nas regras de glosa

### Navegação por teclado
- [ ] Tab: próxima coluna editável
- [ ] Ctrl+Tab: coluna anterior
- [ ] Enter: próxima linha (mesma coluna)
- [ ] Navegação funciona com filtros ativos (sem pular linhas)

### Copy/Paste do Excel
- [ ] Paste de 1 coluna na coluna de data
- [ ] Paste de 1 coluna em crédito/débito/discriminação
- [ ] Paste de múltiplas colunas (até 9 colunas de uma vez)
- [ ] Paste nas colunas de Notas Fiscais (3 colunas)
- [ ] Paste insere linhas suficientes automaticamente se necessário
- [ ] Paste limpa filtros ativos antes de executar

### Operações de linha
- [ ] Inserir N linhas acima (prompt com quantidade)
- [ ] Adicionar 1 linha acima
- [ ] Adicionar 1 linha abaixo
- [ ] Duplicar linha acima
- [ ] Duplicar linha abaixo
- [ ] Mover linha para cima
- [ ] Mover linha para baixo
- [ ] Copiar data da linha acima
- [ ] Excluir linha (individual)
- [ ] Excluir por intervalo (botão)

### Composição de grupos (mescla)
- [ ] Detectar linhas de mesmo valor/data como grupo composto
- [ ] Indicador visual "Crédito composto" / "Débito composto" em linhas 2+
- [ ] Validação: soma do grupo ≈ valor de referência ±0.02
- [ ] Mesclar linhas
- [ ] Desmesclar linha

### Notas Fiscais (seção opcional)
- [ ] Toggle ativar/desativar seção
- [ ] Campos: Nº Nota, Chave de Acesso, CNPJ
- [ ] Validação CNPJ (14 dígitos)
- [ ] Paste de NF do Excel
- [ ] Salvar NF junto com o extrato

### Documentos de Análise (seção opcional)
- [ ] Toggle ativar/desativar seção
- [ ] Campos: Guia, Comprovante, Contratos, Fora do Município
- [ ] Dropdowns condicionais por categoria aplicável
- [ ] Auto-marcação de valores padrão quando linha completa + avaliada
- [ ] Limpeza de valores se categoria não aplicável

### Salvamento e sincronização
- [ ] Autosave no IndexedDB a cada 3s (debounce)
- [ ] Ctrl+S / botão "Salvar": salva apenas linhas dirty (modo_completo=false)
- [ ] Ctrl+B / botão "Salvar Tudo": salva todas as linhas (modo_completo=true)
- [ ] Após salvar: atualiza IDs das linhas novas inseridas
- [ ] Exclusão de linhas marcadas para delete (bulk endpoint no v2)
- [ ] Dirty tracking: marcador visual de linhas não salvas

### Automação de categorização (backend)
- [ ] Portaria 021 (2019/2023): corte em mar/23
- [ ] Portaria 090 (2019/2023): corte em jan/24
- [ ] Portaria 121 com transição=1: corte em mar/23
- [ ] Portaria 140 com transição=1: corte em jan/24
- [ ] Células vazias + competência >= corte + origem preenchida → "Destinatário Identificado"
- [ ] Células vazias + competência >= corte + origem vazia → "Destinatário não Identificado"
- [ ] Nunca sobrescrever categoria já preenchida

### Filtros e visualização
- [ ] Filtro por data (múltipla seleção)
- [ ] Filtro por competência (múltipla seleção)
- [ ] Filtro por categoria
- [ ] Filtro por avaliação
- [ ] Filtro por observações
- [ ] Busca livre (texto em qualquer campo)
- [ ] Limpar todos os filtros
- [ ] Contador de linhas visíveis / total

### Outros
- [ ] Desfazer (Ctrl+Z) — histórico de estados
- [ ] Banco e conta de execução (campos no cabeçalho)
- [ ] Indicador visual de mudança de mês (borda entre linhas de meses diferentes)
- [ ] Exportação CSV
- [ ] Exportação PDF / relatório
- [ ] Botão "Limpar termo" (apaga todos os dados do termo no banco)
- [ ] Toast notifications de sucesso/erro
- [ ] Modal de confirmação para operações destrutivas

---

## 📐 Implementação técnica v2: detalhes dos 3 datalists globais

### Problema do v1

```javascript
// v1: dentro do loop forEach de renderizarTabela() — executa para CADA linha
const datalistId = `datalist-cat-${index}`;
let htmlCategoria = `<input list="${datalistId}" ...>
  <datalist id="${datalistId}">`;
categoriasFiltradas.forEach(cat => {
    htmlCategoria += `<option value="${cat.valor}">`;
});
// 5.000 linhas × 50 opções = 250.000 <option> elements recriados
```

### Solução do v2

```html
<!-- Adicionado uma vez no HTML, fora da tabela -->
<datalist id="datalistCategoriasCredito"></datalist>
<datalist id="datalistCategoriasDebito"></datalist>
<datalist id="datalistCategoriasAmbos"></datalist>
```

```javascript
// Chamado 1× em carregarCategorias(), não no loop de render
function atualizarDatalistsCategorias() {
    const dlCredito = document.getElementById('datalistCategoriasCredito');
    const dlDebito  = document.getElementById('datalistCategoriasDebito');
    const dlAmbos   = document.getElementById('datalistCategoriasAmbos');
    
    const fragCredito = document.createDocumentFragment();
    const fragDebito  = document.createDocumentFragment();
    const fragAmbos   = document.createDocumentFragment();
    
    categoriasAnalise.forEach(cat => {
        const opt = document.createElement('option');
        opt.value = cat.categoria_extra;
        const tipo = (cat.tipo_transacao || '').toLowerCase();
        if (tipo.includes('crédito') && tipo.includes('débito')) {
            fragAmbos.appendChild(opt.cloneNode(true));
        } else if (tipo.includes('crédito')) {
            fragCredito.appendChild(opt.cloneNode(true));
        } else if (tipo.includes('débito')) {
            fragDebito.appendChild(opt.cloneNode(true));
        } else {
            // Tipo não especificado → aparece em todos
            fragCredito.appendChild(opt.cloneNode(true));
            fragDebito.appendChild(opt.cloneNode(true));
            fragAmbos.appendChild(opt.cloneNode(true));
        }
    });
    
    dlCredito.replaceChildren(fragCredito);
    dlDebito.replaceChildren(fragDebito);
    dlAmbos.replaceChildren(fragAmbos);
}

// No loop de renderizarTabela():
const listId = linha.credito ? 'datalistCategoriasCredito'
             : linha.debito  ? 'datalistCategoriasDebito'
             : 'datalistCategoriasAmbos';
// Substituir: list="datalist-cat-${index}" → list="${listId}"
```

---

## 📐 Implementação técnica v2: `atualizarLinhaDOM(index)`

```javascript
// Extração: conteúdo do forEach de renderizarTabela → função pura
function construirHTMLLinha(index, grupoInfo) {
    // Retorna string HTML completa do <tr> interno
    // (mesma lógica do forEach atual, sem os wrappers de DocumentFragment)
    const linha = linhas[index];
    const htmlParts = [];
    // ... (lógica idêntica ao forEach atual) ...
    return htmlParts.join('');
}

// Nova função cirúrgica
function atualizarLinhaDOM(index) {
    const tbody = document.getElementById('tbodyConciliacao');
    const trExistente = tbody.querySelector(`tr[data-index="${index}"]`);
    if (!trExistente) return; // Linha não está no DOM (filtrada/fora do chunk)
    
    const grupoInfo = calcularGrupoComposicaoLocal(index);
    const novoTr = document.createElement('tr');
    novoTr.dataset.index = index;
    // Aplicar classes de avaliação, mudança-mes, etc.
    novoTr.innerHTML = construirHTMLLinha(index, grupoInfo);
    tbody.replaceChild(novoTr, trExistente);
}

// Corrigir bug latente em focarCelula:
// ANTES: const linhaElement = tbody.children[linhaIndex];
// DEPOIS:
const linhaElement = tbody.querySelector(`tr[data-index="${linhaIndex}"]`);
```

---

## 🔧 Dependências externas

Idênticas ao v1 — sem novas dependências:

| Lib | Versão | Origem |
|-----|--------|--------|
| Bootstrap CSS | 5.3.0 | CDN |
| Bootstrap JS Bundle | 5.3.0 | CDN |
| Bootstrap Icons | 1.10.0 | CDN |
| idb-keyval | 6 | CDN (unpkg) |

---

## 📏 Métricas de performance alvo

| Operação | v1 (estimado) | v2 (alvo) | Como medir |
|----------|---------------|-----------|------------|
| Render completo 5.000 linhas | ~10-15s | < 2s | `perfToggle()` + `perfSummary()` |
| Render completo 300 linhas (1 mês) | ~500ms | < 100ms | `perfToggle()` + `perfSummary()` |
| Atualização de 1 linha | ~500ms (render completo) | < 16ms (1 frame) | DevTools > Performance > Paint |
| Paste 100 linhas | ~2-3s | < 500ms | Cronômetro manual |
| Exclusão em lote (10 linhas) | 10 requests | 1 request | DevTools > Network |

---

## 🧪 Protocolo de teste de regressão

### Pré-requisito
- Acessar `/conc_bancaria_2` com um termo que tenha 1.000+ linhas

### Teste de smoke (5 min)
1. Carregar extrato → verificar que linhas aparecem corretamente
2. Editar célula de categoria → verificar autocomplete
3. Paste de 5 linhas do Excel → verificar distribuição nas colunas
4. Salvar (Ctrl+S) → verificar toast de sucesso sem erro no console
5. Trocar de termo → verificar que estado anterior é limpo

### Teste de performance (5 min)
1. Abrir console → `perfToggle()`
2. Carregar modo 'todas' em termo com 1.000+ linhas
3. `perfSummary()` → verificar que `renderizarTabela` < 2.000ms
4. Editar valor de uma célula e verificar que não há render completo (< 16ms no console)

### Teste de regressão completo
Percorrer todos os itens do checklist de paridade funcional acima.

---

*Spec criada em: 20/05/2026 | Baseada em análise completa do v1 (conc_bancaria.py + conc_bancaria.html)*
