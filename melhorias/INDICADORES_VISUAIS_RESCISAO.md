# Indicadores Visuais - Termos Rescindidos

## 🎨 Resumo das Melhorias Visuais

Este documento mostra as melhorias visuais implementadas para identificar termos rescindidos nos templates.

---

## 📋 Template: adicionar_analises.html

### ✅ ANTES (Sem Indicação de Rescisão)
```
┌─────────────────────────────────────────────────┐
│ ○ Termo 001/2024                                │
│   Período: 10/01/2024 até 31/12/2024            │
│   Portaria: Portaria nº 090/SMDHC/2023          │
└─────────────────────────────────────────────────┘
```

### ✨ DEPOIS (Com Indicadores)
```
┌─────────────────────────────────────────────────┐
│ ○ Termo 001/2024  [🔴 RESCINDIDO]               │
│   Período: 10/01/2024 até 15/08/2024 (rescindido)│
│   31/12/2024 (riscado)                          │
│   Portaria: Portaria nº 090/SMDHC/2023          │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ ⚠️ ATENÇÃO!                                     │
│ Este termo foi rescindido em 15/08/2024.       │
│ As prestações foram calculadas até esta data.  │
└─────────────────────────────────────────────────┘
```

**Elementos Adicionados:**
1. **Badge vermelho** `🔴 RESCINDIDO` ao lado do número do termo
2. **Data de rescisão em vermelho** com texto "(rescindido)"
3. **Data final original riscada** em cinza
4. **Alerta amarelo** após calcular prestações

---

## 📊 Template: atualizar_prestacoes.html

### ✅ ANTES (Sem Indicação de Rescisão)
```
┌─────────────────────────────────────────────────┐
│ 📄 Termo 001/2024                               │
│ Processo SEI: 6037.2024/0001234-5               │
│ Portaria: Portaria nº 090/SMDHC/2023            │
├─────────────────────────────────────────────────┤
│ ℹ️ Vigência do Termo:                           │
│ 10/01/2024 até 31/12/2024                       │
└─────────────────────────────────────────────────┘
```

### ✨ DEPOIS (Com Indicadores)
```
┌─────────────────────────────────────────────────┐
│ 📄 Termo 001/2024  [🔴 RESCINDIDO]              │
│ Processo SEI: 6037.2024/0001234-5               │
│ Portaria: Portaria nº 090/SMDHC/2023            │
├─────────────────────────────────────────────────┤
│ ⚠️ Termo Rescindido!                            │
│ Este termo foi rescindido em 15/08/2024.       │
│ As prestações serão recalculadas até esta data.│
│ Data final original: 31/12/2024                 │
├─────────────────────────────────────────────────┤
│ ℹ️ Vigência do Termo:                           │
│ 10/01/2024 até 15/08/2024 (rescindido)         │
└─────────────────────────────────────────────────┘
```

**Elementos Adicionados:**
1. **Badge escuro** `🔴 RESCINDIDO` no cabeçalho do card
2. **Alerta amarelo** explicando a rescisão
3. **Data final original** mostrada no alerta
4. **Vigência efetiva em vermelho** com indicador "(rescindido)"

---

## 🎨 Paleta de Cores Utilizada

### Badges
| Contexto | Classe CSS | Cor | Uso |
|----------|-----------|-----|-----|
| Adicionar Análises | `bg-danger` | Vermelho (#dc3545) | Badge "RESCINDIDO" |
| Atualizar Prestações | `bg-dark` | Cinza Escuro (#212529) | Badge "RESCINDIDO" |

### Texto
| Elemento | Classe CSS | Cor | Uso |
|----------|-----------|-----|-----|
| Data de Rescisão | `text-danger` | Vermelho | Destacar data efetiva |
| Indicador "(rescindido)" | `text-danger` | Vermelho | Marcador de status |
| Data Original | `text-muted` | Cinza | Data riscada (obsoleta) |

### Alertas
| Tipo | Classe CSS | Cor de Fundo | Ícone | Uso |
|------|-----------|--------------|-------|-----|
| Aviso | `alert-warning` | Amarelo (#fff3cd) | ⚠️ | Notificar sobre rescisão |
| Informação | `alert-info` | Azul (#cfe2ff) | ℹ️ | Dados do termo |

---

## 📱 Responsividade

Todos os elementos visuais são responsivos e se adaptam a diferentes tamanhos de tela:

### Desktop (≥992px)
```
┌──────────────────────────────────────────────────────┐
│ ○ Termo 001/2024  [🔴 RESCINDIDO]                    │
│   Período: 10/01/2024 até 15/08/2024 (rescindido)   │
│   31/12/2024  |  Portaria: Portaria nº 090/2023     │
└──────────────────────────────────────────────────────┘
```

### Mobile (<576px)
```
┌────────────────────────────┐
│ ○ Termo 001/2024           │
│   [🔴 RESCINDIDO]          │
│   Período:                 │
│   10/01/2024 até           │
│   15/08/2024 (rescindido)  │
│   31/12/2024               │
│   Portaria: 090/2023       │
└────────────────────────────┘
```

---

## 🔍 Detalhes Técnicos

### 1. Badge de Rescisão
```html
<span class="badge bg-danger ms-2" 
      title="Termo rescindido em {{ data_rescisao }}">
  🔴 RESCINDIDO
</span>
```

**Características:**
- Tooltip (title) mostra data de rescisão ao passar o mouse
- Margin-left de 2 unidades (ms-2) para espaçamento
- Emoji 🔴 para reforço visual
- Background vermelho (bg-danger)

### 2. Data de Rescisão Destacada
```html
<strong class="text-danger">15/08/2024</strong>
<span class="text-danger">(rescindido)</span>
```

**Características:**
- Negrito (strong) para destaque
- Cor vermelha (text-danger)
- Texto explicativo "(rescindido)"

### 3. Data Original Riscada
```html
<span class="text-muted" style="text-decoration: line-through;">
  31/12/2024
</span>
```

**Características:**
- Cor cinza desbotada (text-muted)
- Linha atravessada (line-through)
- Indica que a data não é mais válida

### 4. Alerta de Rescisão
```html
<div class="alert alert-warning alert-dismissible fade show" role="alert">
  <i class="bi bi-exclamation-triangle-fill me-2"></i>
  <strong>Atenção!</strong> Este termo foi rescindido...
  <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>
```

**Características:**
- Fundo amarelo (alert-warning)
- Ícone de aviso (bi-exclamation-triangle-fill)
- Dismissível (pode ser fechado pelo usuário)
- Animação fade-in ao aparecer

---

## 🎯 Padrões de UX Aplicados

### 1. **Hierarquia Visual**
- Badge vermelho chama atenção imediatamente
- Data de rescisão em negrito e vermelho
- Data original apagada (riscada + cinza)

### 2. **Feedback Progressivo**
- Indicador na listagem de termos
- Alerta ao calcular prestações
- Confirmação visual após salvar

### 3. **Consistência**
- Mesmos ícones em todos os templates (🔴)
- Mesma paleta de cores (vermelho para rescisão)
- Mesmo padrão de texto "(rescindido)"

### 4. **Affordance**
- Tooltip nos badges (hover = mais informação)
- Alertas dismissíveis (usuário pode fechar)
- Cores semânticas (vermelho = atenção/problema)

### 5. **Prevenção de Erros**
- Avisos claros antes de calcular prestações
- Data original visível mas desativada
- Explicação do impacto da rescisão

---

## 📊 Comparação Visual

### Estado Normal vs Rescindido

#### Normal
```
┌─────────────────────────────────┐
│ ○ Termo 001/2024                │
│   10/01/2024 até 31/12/2024     │
└─────────────────────────────────┘
✅ Sem destaque especial
✅ Todas as informações em cinza/preto
✅ Sem badges ou alertas
```

#### Rescindido
```
┌─────────────────────────────────┐
│ ○ Termo 001/2024 [🔴 RESCINDIDO]│
│   10/01/2024 até 15/08/2024     │
│   (rescindido) 31/12/2024       │
└─────────────────────────────────┘
🔴 Badge vermelho destaca status
🔴 Data efetiva em vermelho
🔴 Data original riscada
⚠️ Alerta amarelo ao calcular
```

---

## 🧪 Casos de Uso Visual

### Caso 1: Usuário buscando termo normal
**Comportamento:**
- Visualiza lista sem badges
- Seleciona termo
- Calcula prestações normalmente
- Nenhum alerta aparece

### Caso 2: Usuário buscando termo rescindido
**Comportamento:**
1. **Visualiza lista:** Badge `🔴 RESCINDIDO` chama atenção
2. **Lê datas:** Vê data efetiva (15/08) e original riscada (31/12)
3. **Seleciona termo:** Badge no tooltip mostra data de rescisão
4. **Calcula prestações:** Alerta amarelo avisa sobre recálculo
5. **Salva:** Prestações salvas apenas até data de rescisão

### Caso 3: Usuário atualizando termo rescindido
**Comportamento:**
1. **Acessa atualização:** Card com badge escuro `🔴 RESCINDIDO`
2. **Lê alerta:** "Termo rescindido em 15/08/2024"
3. **Vê vigência:** Original (31/12) mostrada como referência
4. **Confirma atualização:** Prestações recalculadas até rescisão
5. **Vê resultado:** Log mostra prestações deletadas (se houver)

---

## ✅ Checklist de Implementação

### Adicionar Análises (adicionar_analises.html)
- [x] Badge "RESCINDIDO" ao lado do número do termo
- [x] Data de rescisão em vermelho com indicador
- [x] Data original riscada em cinza
- [x] Alerta amarelo após calcular prestações
- [x] Tooltip no badge com data de rescisão
- [x] Badge no display do termo selecionado
- [x] JavaScript atualizado para receber campos rescindido/aviso

### Atualizar Prestações (atualizar_prestacoes.html)
- [x] Badge "RESCINDIDO" no cabeçalho do card
- [x] Alerta amarelo explicando rescisão
- [x] Data final original mostrada no alerta
- [x] Vigência efetiva em vermelho com indicador
- [x] Tooltip no badge com data de rescisão

### Termos Rescindidos (termos_rescindidos.html)
- [x] Interface completa de gerenciamento
- [x] Select2 para busca de termos
- [x] Date picker para data de rescisão
- [x] Tabela com todas as rescisões
- [x] Ações de editar/deletar
- [x] Alerta informativo sobre regras

---

## 🚀 Próximos Passos

### Testes Recomendados
1. ✅ Verificar badge aparece corretamente
2. ✅ Confirmar data riscada visível
3. ✅ Validar alerta após cálculo
4. ✅ Testar tooltip no hover
5. ✅ Verificar responsividade mobile

### Melhorias Futuras
- [ ] Adicionar animação no badge (pulse)
- [ ] Gráfico mostrando período executado vs planejado
- [ ] Linha do tempo visual da rescisão
- [ ] Indicador de "dias executados" (badge numérico)

---

**Documentação atualizada em:** Janeiro 2025  
**Templates modificados:** 2 (adicionar_analises.html, atualizar_prestacoes.html)  
**Componentes visuais adicionados:** 7 (badges, alertas, tooltips, textos destacados)
