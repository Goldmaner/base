# Novas Funcionalidades - Sistema de Análises

## 📅 Data: 30/01/2025

---

## ✨ Funcionalidades Implementadas

### 1. Filtro de ACP/TCC em "Adicionar Análise"

**Objetivo**: Ocultar termos ACP e TCC por padrão, mostrando apenas quando solicitado

**Implementação**:

#### Arquivo: `templates/adicionar_analises.html`

**Checkbox de Controle**:
```html
<div class="form-check mb-3">
  <input class="form-check-input" type="checkbox" id="mostrarAcpTcc">
  <label class="form-check-label" for="mostrarAcpTcc">
    <strong>Mostrar ACP e TCC?</strong>
    <small class="text-muted">(Por padrão, estes tipos de termo ficam ocultos)</small>
  </label>
</div>
```

**Identificação de Termos**:
- Atributo `data-tipo-termo` adicionado a cada termo
- Detecta "ACP" ou "TCC" no número do termo (case-insensitive)

**Comportamento**:
- ✅ Por padrão: ACP/TCC ficam **ocultos**
- ✅ Ao marcar checkbox: ACP/TCC são **exibidos**
- ✅ Ao desmarcar: ACP/TCC voltam a ficar **ocultos**

**JavaScript**:
```javascript
// Filtrar termos ACP/TCC
document.getElementById('mostrarAcpTcc')?.addEventListener('change', function() {
  const mostrar = this.checked;
  const termosAcpTcc = document.querySelectorAll('[data-tipo-termo="acp-tcc"]');
  
  termosAcpTcc.forEach(termo => {
    termo.style.display = mostrar ? 'block' : 'none';
  });
});

// Inicializar: ocultar ACP/TCC por padrão
document.addEventListener('DOMContentLoaded', function() {
  const termosAcpTcc = document.querySelectorAll('[data-tipo-termo="acp-tcc"]');
  termosAcpTcc.forEach(termo => {
    termo.style.display = 'none';
  });
});
```

---

### 2. Funcionalidade "Atualizar Prestações de Contas"

**Objetivo**: Identificar e corrigir divergências entre datas de vigência dos termos e suas prestações finais

#### Lógica de Detecção

**Comparação**:
```sql
-- Tabela: public.Parcerias
inicio, final  -- Datas do termo

-- Tabela: parcerias_analises  
vigencia_inicial, vigencia_final  -- Datas das prestações

-- Condição de divergência:
WHERE tipo_prestacao = 'Final'
AND (vigencia_inicial != inicio OR vigencia_final != final)
```

**Cenário de Uso**:
1. Usuário cadastra termo: 01/01/2025 - 31/12/2025
2. Sistema gera prestação Final: 01/01/2025 - 31/12/2025
3. Usuário **atualiza** termo: 01/01/2025 - 31/03/2026 (estende vigência)
4. Prestação Final fica **desatualizada**: ainda 01/01/2025 - 31/12/2025
5. **Sistema detecta** a divergência e permite correção

#### Nova Rota: `/analises/atualizar-prestacoes`

**Arquivo**: `routes/analises.py`

**Funcionalidade GET**:
- Busca todos os termos com prestações do tipo "Final" divergentes
- Agrupa por termo
- Exibe comparação lado a lado

**Query SQL**:
```sql
SELECT 
    p.numero_termo,
    p.inicio as data_inicio_termo,
    p.final as data_final_termo,
    pa.id as analise_id,
    pa.tipo_prestacao,
    pa.numero_prestacao,
    pa.vigencia_inicial,
    pa.vigencia_final
FROM Parcerias p
INNER JOIN parcerias_analises pa ON p.numero_termo = pa.numero_termo
WHERE pa.tipo_prestacao = 'Final'
AND (
    pa.vigencia_inicial != p.inicio 
    OR pa.vigencia_final != p.final
)
ORDER BY p.numero_termo DESC
```

**Funcionalidade POST**:
- Recebe array de prestações com novas datas
- Atualiza `vigencia_inicial` e `vigencia_final` em `parcerias_analises`
- Valida e confirma alterações

#### Novo Template: `atualizar_prestacoes.html`

**Estrutura**:

1. **Alerta Informativo**:
   - Mostra quantos termos têm divergências
   - Explica o que será corrigido

2. **Cards de Divergência** (um por termo):
   - **Header vermelho**: Indica problema
   - **Comparação Visual**:
     - Caixa amarela: Datas antigas (nas prestações)
     - Seta azul: Indicador de mudança
     - Caixa verde: Datas corretas (no termo)

3. **Formulário de Atualização**:
   - Campos de data pré-preenchidos com valores corretos
   - Botão individual: "Atualizar Prestações deste Termo"

4. **Botão Global**:
   - "Atualizar Todos os Termos": Processa todos de uma vez

**Layout Visual**:
```
┌─────────────────────────────────────────────┐
│ ⚠️ Divergências Encontradas                │
│ 3 termo(s) com prestações desatualizadas   │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 📄 TFM/001/2025/SMDHC                      │
├─────────────────────────────────────────────┤
│ ANTIGAS (Amarelo)  →  CORRETAS (Verde)     │
│                                             │
│ Final 1:           →  Termo:               │
│ 01/01/25-31/12/25  →  01/01/25-31/03/26    │
│                                             │
│ [Campos de data editáveis]                 │
│           [Atualizar Prestações] 🔄        │
└─────────────────────────────────────────────┘

         [Atualizar Todos os Termos] ✅
```

**JavaScript - Funcionalidades**:

1. **Atualização Individual**:
```javascript
// Ao submeter formulário de um termo específico
form.addEventListener('submit', async function(e) {
  // Coleta dados das prestações
  // Envia via POST para /analises/atualizar-prestacoes
  // Confirma e recarrega página
});
```

2. **Atualização em Lote**:
```javascript
btnAtualizarTudo.addEventListener('click', async function() {
  // Itera sobre todos os formulários
  // Envia cada um sequencialmente
  // Conta sucessos e erros
  // Exibe resumo final
});
```

#### Integração com Menu de Análises

**Arquivo**: `templates/analises.html`

**Novo Botão**:
```html
<a href="{{ url_for('analises.atualizar_prestacoes') }}" 
   class="btn btn-warning me-2">
  <i class="bi bi-arrow-repeat"></i> Atualizar Prestações
</a>
```

**Posição**: Entre "Adicionar Análise" (verde) e "Voltar" (cinza)

---

## 📊 Fluxos de Uso

### Fluxo 1: Filtrar ACP/TCC

```
1. Acesse /analises
2. Clique "Adicionar Análise"
3. Por padrão: lista mostra apenas termos normais
4. Marque "Mostrar ACP e TCC?"
5. ACP/TCC aparecem na lista
6. Desmarque para ocultar novamente
```

### Fluxo 2: Atualizar Prestações

```
1. Acesse /analises
2. Clique "Atualizar Prestações" (botão amarelo)
3. Sistema mostra termos com divergências
4. Revise comparação (amarelo vs verde)
5. Opção A: Clique "Atualizar Prestações deste Termo" (individual)
   OU
   Opção B: Clique "Atualizar Todos os Termos" (lote)
6. Confirme a operação
7. Sistema atualiza e recarrega página
```

---

## 🎨 Elementos Visuais

### Cores e Ícones

| Elemento | Cor | Ícone | Significado |
|----------|-----|-------|-------------|
| Card de divergência | Borda vermelha | 📄 | Problema detectado |
| Datas antigas | Fundo amarelo | 🕐 | Valores desatualizados |
| Datas corretas | Fundo verde | ✓ | Valores corretos |
| Botão atualizar | Amarelo (warning) | 🔄 | Ação de correção |
| Botão atualizar tudo | Verde (success) | ✓✓ | Ação em lote |

---

## 🧪 Testes Recomendados

### Teste 1: Filtro ACP/TCC
```
1. Crie termos: TFM/001/2025, ACP/001/2025, TCC/001/2025
2. Acesse "Adicionar Análise"
3. Verifique: apenas TFM/001/2025 aparece
4. Marque checkbox "Mostrar ACP e TCC?"
5. Verifique: todos os 3 termos aparecem
6. Desmarque checkbox
7. Verifique: apenas TFM/001/2025 aparece novamente
```

### Teste 2: Detectar Divergências
```
1. Crie termo: TFM/001/2025 (01/01/2025 - 31/12/2025)
2. Adicione prestações (sistema gera Final 1)
3. Edite termo em Parcerias: altere final para 31/03/2026
4. Acesse "Atualizar Prestações"
5. Verifique: TFM/001/2025 aparece na lista
6. Confirme: amarelo mostra 31/12/2025, verde mostra 31/03/2026
```

### Teste 3: Atualizar Individual
```
1. Na tela de divergências
2. Selecione um termo
3. Verifique campos pré-preenchidos com datas corretas
4. Clique "Atualizar Prestações deste Termo"
5. Confirme
6. Verifique: página recarrega sem aquele termo
7. Confirme no banco: vigencia_final = 31/03/2026
```

### Teste 4: Atualizar em Lote
```
1. Crie múltiplos termos com divergências (3+)
2. Acesse "Atualizar Prestações"
3. Clique "Atualizar Todos os Termos"
4. Confirme ação em lote
5. Aguarde processamento
6. Verifique mensagem: "X sucesso(s), 0 erro(s)"
7. Confirme: página sem divergências
```

---

## 📁 Arquivos Modificados/Criados

### Modificados:
1. ✏️ `templates/adicionar_analises.html` - Checkbox + JavaScript filtro
2. ✏️ `routes/analises.py` - Nova rota `/atualizar-prestacoes`
3. ✏️ `templates/analises.html` - Novo botão "Atualizar Prestações"

### Criados:
4. ✨ `templates/atualizar_prestacoes.html` (238 linhas)

---

## 🎯 Benefícios

### Filtro ACP/TCC
- ✅ Reduz poluição visual (ACP/TCC geralmente não precisam de prestações)
- ✅ Mantém opção de exibir quando necessário
- ✅ Facilita navegação na lista

### Atualizar Prestações
- ✅ **Detecção automática** de divergências
- ✅ **Comparação visual** clara (amarelo vs verde)
- ✅ **Correção em lote** ou individual
- ✅ **Auditoria**: identifica inconsistências rapidamente
- ✅ **Segurança**: confirmação antes de atualizar

### Casos de Uso Cobertos

| Cenário | Solução |
|---------|---------|
| Termo estendido | Atualizar prestação Final com nova data |
| Termo reduzido | Ajustar prestação Final para data anterior |
| Múltiplos termos alterados | Atualização em lote |
| Revisão periódica | Verificar se há divergências |

---

## ⚠️ Observações Importantes

1. **Apenas Prestações Finais**: O sistema só verifica e atualiza prestações do tipo "Final"
   - Motivo: Prestações parciais (Trimestral, Semestral) têm períodos fixos

2. **Validação Manual**: O usuário deve revisar as datas antes de confirmar
   - Sistema sugere datas do termo, mas permite edição

3. **Atualização Irreversível**: Após confirmar, as datas antigas são substituídas
   - Recomendação: Fazer backup antes de atualizações em lote

4. **Performance**: Atualização em lote é sequencial
   - Para muitos termos (50+), pode levar alguns segundos

---

## 📚 Estrutura de Dados

### Tabela: `public.Parcerias`
```
numero_termo | inicio      | final
-------------|-------------|------------
TFM/001/2025 | 2025-01-01  | 2026-03-31  ← Datas corretas
```

### Tabela: `parcerias_analises`
```
id | numero_termo | tipo_prestacao | vigencia_inicial | vigencia_final
---|--------------|----------------|------------------|----------------
1  | TFM/001/2025 | Final          | 2025-01-01       | 2025-12-31  ← Desatualizado
```

### Após Atualização:
```
id | numero_termo | tipo_prestacao | vigencia_inicial | vigencia_final
---|--------------|----------------|------------------|----------------
1  | TFM/001/2025 | Final          | 2025-01-01       | 2026-03-31  ← Corrigido ✅
```

---

**Status**: ✅ Implementação Completa  
**Testado**: Pendente de validação pelo usuário  
**Última Atualização**: 30/01/2025
