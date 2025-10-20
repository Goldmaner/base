# Melhorias UX no Orçamento (Orcamento_2.html)

## Data: 20/10/2025

## Melhorias Implementadas

### ✅ 1. Coluna "Total" por Linha
**Objetivo:** Mostrar o total de cada rubrica/categoria somando todos os meses

**Implementação:**
- Adicionada coluna `<th class="col-total-linha">Total</th>` no cabeçalho
- Adicionada célula `<td class="col-total-linha text-end total-linha">0,00</td>` em cada linha do tbody
- Modificada função `recalcTotals()` para calcular e exibir o total por linha
- Estilo com `background-color: #f8f9fa` e `font-weight: bold` para destacar

### ✅ 2. Botão Ocultar/Mostrar Meses
**Objetivo:** Permitir visualizar apenas rubricas, categorias e totais, ocultando colunas de meses

**Implementação:**
- Adicionado botão `👁️ Ocultar Meses` / `👁️ Mostrar Meses`
- CSS classe `.hide-months` que oculta `.month-th` e `.month-td` com `display: none !important`
- JavaScript toggle que adiciona/remove a classe ao clicar

**Uso:**
- Clique no botão para alternar entre visualizações
- Útil para ver apenas totais quando não precisa editar valores mensais

### ✅ 3. Navegação com Enter
**Objetivo:** Ao pressionar Enter em uma célula, ir para a mesma coluna na linha de baixo

**Implementação:**
- Event listener `keydown` que detecta Enter em inputs com classe `.valor`
- Calcula índice da coluna atual
- Busca próxima linha (`nextElementSibling`)
- Move foco para input na mesma coluna da próxima linha
- Seleciona todo o conteúdo do input automaticamente (`select()`)

**Benefício:** Agiliza preenchimento vertical (coluna por coluna)

### ✅ 4. Expansão para 100% da Largura
**Objetivo:** Eliminar espaços em branco nas laterais, usar toda a tela

**Mudanças CSS:**
```css
body { margin: 0; padding: 0; }
.container { max-width: 100%; padding: 1rem; }
.table-wrapper{ overflow-x: auto; width: 100%; max-width: 100%; margin: 0; }
```

**Antes:** `width: 95vw` com espaços laterais  
**Depois:** `width: 100%` ocupando toda a tela

### ✅ 5. Botão "Limpar Tudo"
**Objetivo:** Resetar todos os dados do termo para recomeçar

**Implementação:**
- Botão amarelo (`.btn-warning`) com ícone 🗑️
- Verifica se há dados preenchidos antes de limpar
- Se houver dados, mostra `confirm()` com "Tem certeza?"
- Limpa todos os inputs (valores ficam vazios, quantidades voltam para "1")
- Reexecuta `recalcTotals()` para zerar totais
- Alert de confirmação "Dados limpos com sucesso!"

**Segurança:** Não limpa se usuário cancelar o confirm

### 🔄 6. Melhorias no Botão Salvar (EM PROGRESSO)
**Objetivo:** Feedback visual durante salvamento e logs para debug

**Implementação Parcial:**
- HTML: Adicionado `<span id="salvarSpinner">` com spinner Bootstrap
- Estado inicial: Spinner oculto (`.d-none`)
- **PENDENTE:** Modificar JavaScript para:
  1. Desabilitar botão ao iniciar (`disabled=true`)
  2. Mostrar spinner, ocultar texto "Salvar"
  3. Trocar texto para "Salvando..."
  4. Adicionar `console.log()` em cada etapa
  5. Resetar botão em caso de erro ou sucesso
  6. Delay de 500ms antes de redirecionar

**Status:** HTML pronto, JavaScript precisa ser atualizado (conflito no replace)

## Melhorias Pendentes

### ❌ 7. Corrigir Badges no Orcamento_3 (CRÍTICO)
**Problema:** Modal de termos não abre ao clicar nas badges verdes

**Possível Causa:** Mudanças no dual database podem ter quebrado rota `/orcamento/termos-por-categoria/<categoria>`

**Ação:** Verificar logs do console do navegador (F12) e conferir se rota está retornando 401/404/500

## Testes Recomendados

### Teste 1: Coluna Total
1. Preencha valores em 3 meses de uma linha
2. Verifique se coluna "Total" mostra a soma correta
3. Edite um valor e veja atualização em tempo real

### Teste 2: Ocultar/Mostrar Meses
1. Clique em "👁️ Ocultar Meses"
2. Verifique que apenas Rubrica, Quantidade, Categoria, Total e Ação ficam visíveis
3. Clique novamente para mostrar

### Teste 3: Navegação com Enter
1. Clique em uma célula de valor (ex: Mês 1, Linha 1)
2. Digite um número
3. Pressione Enter
4. Foco deve ir para Mês 1, Linha 2

### Teste 4: Largura 100%
1. Abra em tela cheia
2. Verifique que tabela ocupa toda a largura
3. Role horizontalmente se necessário (muitas colunas)

### Teste 5: Limpar
1. Preencha alguns valores
2. Clique em "🗑️ Limpar Tudo"
3. Confirme na mensagem
4. Verifique que todos os inputs foram limpos

## Próximos Passos

1. **Finalizar botão Salvar** - Adicionar spinner funcional e logs
2. **Corrigir badges** - Investigar erro no orcamento_3_dict.html
3. **Testar performance** - Verificar se salvamento está lento (pode ser dual write)
4. **Otimizar dual write** - Considerar batch insert em vez de um por um

## Arquivos Modificados

- ✅ `templates/orcamento_2.html` - Todas as melhorias de UX
- ❌ `templates/orcamento_3_dict.html` - Pendente (badges)
- ❌ `routes/orcamento.py` - Verificar rota termos-por-categoria
