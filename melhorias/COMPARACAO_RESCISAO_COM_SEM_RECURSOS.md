# Comparação Visual: Rescisão com Recursos vs Sem Recursos

## 📊 Matriz de Decisão

| Condição | Adicionar Análises | Atualizar Prestações | Ação |
|----------|-------------------|---------------------|------|
| **Rescindido ≤ 5 dias** | ❌ Não aparece | ❌ Erro se atualizar | Bloqueio total |
| **Rescindido > 5 dias + SEM recursos** | ❌ Não aparece | ✅ Aparece → Remove TUDO | Validação humana |
| **Rescindido > 5 dias + COM recursos** | ✅ Aparece | ✅ Aparece → Recalcula | Fluxo normal |

---

## 🎯 Cenário 1: Termo COM Recursos Repassados

### Dados:
```
Termo: TFM/001/2024
Vigência: 01/01/2024 a 31/12/2024 (12 meses)
Rescindido: 30/06/2024 (6 meses executados)
Total Pago: R$ 150.000,00 ✅
```

### Comportamento em "Adicionar Análises":
```
┌────────────────────────────────────────────┐
│ ✅ APARECE NA LISTA                        │
├────────────────────────────────────────────┤
│ ○ TFM/001/2024  [🔴 RESCINDIDO]           │
│   Período: 01/01/2024 até 30/06/2024     │
│   (rescindido) 31/12/2024                 │
│   Portaria: 090/2023                      │
└────────────────────────────────────────────┘

[Gerar Prestações] → ✅ Calcula até 30/06/2024

⚠️ Este termo foi rescindido em 30/06/2024.
As prestações foram calculadas até esta data.

Prestações Geradas:
├─ Semestral #1: 01/01/2024 a 30/06/2024
└─ Final #1: 01/01/2024 a 30/06/2024
```

### Comportamento em "Atualizar Prestações":
```
┌────────────────────────────────────────────┐
│ ✅ APARECE NA LISTA                        │
├────────────────────────────────────────────┤
│ TFM/001/2024  [🔴 RESCINDIDO]             │
│                                            │
│ ⚠️ Termo Rescindido!                      │
│ Rescindido em: 30/06/2024                 │
│ As prestações serão recalculadas          │
│ até esta data.                            │
├────────────────────────────────────────────┤
│ Vigência: 01/01/2024 até 30/06/2024      │
│ (rescindido)                              │
└────────────────────────────────────────────┘

Prestações Cadastradas (2):
├─ Semestral #1: 01/01/2024 a 30/06/2024
└─ Final #1: 01/01/2024 a 31/12/2024 ❌

Prestações Corretas (2):
├─ Semestral #1: 01/01/2024 a 30/06/2024 ✅
└─ Final #1: 01/01/2024 a 30/06/2024 ✅

[Atualizar] → ✅ Recalcula e ajusta datas
```

---

## ❌ Cenário 2: Termo SEM Recursos Repassados

### Dados:
```
Termo: TFM/002/2024
Vigência: 01/01/2024 a 31/12/2024 (12 meses)
Rescindido: 30/06/2024 (6 meses executados)
Total Pago: R$ 0,00 ❌
```

### Comportamento em "Adicionar Análises":
```
┌────────────────────────────────────────────┐
│ ❌ NÃO APARECE NA LISTA                    │
├────────────────────────────────────────────┤
│ (vazio - termo filtrado pela query)       │
└────────────────────────────────────────────┘

Motivo: Query exclui termos com:
  data_rescisao IS NOT NULL AND total_pago = 0

Se tentar via API:
POST /analises/api/calcular-prestacoes
Body: {"numero_termo": "TFM/002/2024"}

Response (400):
{
  "erro": "Termo foi rescindido sem ter recebido 
           recursos (total pago: R$ 0,00). 
           Não há prestações a serem geradas."
}
```

### Comportamento em "Atualizar Prestações":
```
┌────────────────────────────────────────────┐
│ ✅ APARECE NA LISTA (para validação)       │
├────────────────────────────────────────────┤
│ TFM/002/2024  [🔴 RESCINDIDO]             │
│                                            │
│ ⚠️ Termo Rescindido!                      │
│ Rescindido em: 30/06/2024                 │
│ ⚠️ SEM RECURSOS REPASSADOS (R$ 0,00)     │
│                                            │
│ ⚠️ Ao atualizar, TODAS as prestações     │
│ deste termo serão REMOVIDAS, pois não     │
│ houve execução financeira.                │
├────────────────────────────────────────────┤
│ Vigência: 01/01/2024 até 30/06/2024      │
│ (rescindido)                              │
└────────────────────────────────────────────┘

Prestações Cadastradas (2):
├─ Semestral #1: 01/01/2024 a 30/06/2024
└─ Final #1: 01/01/2024 a 31/12/2024

Prestações Corretas (0):
└─ (nenhuma - termo sem recursos)

[Atualizar] → 🗑️ Remove TODAS as prestações

Confirmação:
┌────────────────────────────────────────────┐
│ ⚠️ ATENÇÃO                                │
│                                            │
│ Confirma o recálculo de TODAS as          │
│ prestações do termo TFM/002/2024?         │
│                                            │
│ As prestações atuais serão deletadas      │
│ e recriadas com as datas corretas.        │
│                                            │
│         [Cancelar]    [Confirmar]         │
└────────────────────────────────────────────┘

Após confirmação:
✅ Termo TFM/002/2024 rescindido sem recursos (R$ 0,00). 
   2 prestação(ões) removida(s) 
   (incluindo 1 marcada(s) como entregue). 
   Vigência: 180 dia(s).

⚠️ Termo rescindido sem recursos repassados.
```

---

## 🔄 Fluxo Comparativo

### COM Recursos (R$ 150.000):
```
1. [Adicionar Análises]
   ↓
   ✅ Termo aparece na lista
   ↓
   Seleciona termo
   ↓
   Clica "Gerar Prestações"
   ↓
   API calcula até data_rescisao
   ↓
   Mostra alerta: "⚠️ Termo rescindido"
   ↓
   Salva prestações normalmente

2. [Atualizar Prestações]
   ↓
   ✅ Termo aparece na lista
   ↓
   Mostra alerta amarelo: "Termo rescindido"
   ↓
   Clica "Atualizar"
   ↓
   Recalcula prestações até data_rescisao
   ↓
   Remove prestações excedentes
   ↓
   ✅ "X prestações atualizadas"
```

### SEM Recursos (R$ 0,00):
```
1. [Adicionar Análises]
   ↓
   ❌ Termo NÃO aparece na lista
   ↓
   (bloqueio automático pela query)
   ↓
   Se tentar via API:
   ↓
   ❌ Erro: "Sem recursos, sem prestações"

2. [Atualizar Prestações]
   ↓
   ✅ Termo aparece na lista
   ↓
   Mostra alerta VERMELHO:
   "⚠️ SEM RECURSOS REPASSADOS"
   "TODAS prestações serão REMOVIDAS"
   ↓
   Clica "Atualizar"
   ↓
   Confirmação modal
   ↓
   Remove TODAS prestações (DELETE)
   ↓
   ✅ "X prestação(ões) removida(s)"
   ⚠️ "Termo sem recursos repassados"
```

---

## 📈 Tabela Comparativa de Ações

| Ação | COM Recursos | SEM Recursos |
|------|-------------|-------------|
| **Query Adicionar** | Inclui termo | Exclui termo |
| **API Calcular** | Retorna prestações até rescisão | Retorna erro 400 |
| **Lista Atualizar** | Mostra termo | Mostra termo |
| **Alerta Atualizar** | Amarelo: "Recalcula até rescisão" | Vermelho: "Remove TUDO" |
| **Ação Atualizar** | Recalcula + ajusta datas | DELETE todas prestações |
| **Prestações Corretas** | Lista até data_rescisao | Lista vazia (0) |
| **Mensagem Sucesso** | "X atualizadas, Y removidas" | "X removidas (sem recursos)" |

---

## 🎨 Diferenças Visuais

### Alerta COM Recursos:
```html
┌────────────────────────────────────────┐
│ ⚠️ Termo Rescindido!                  │
│ Rescindido em: 30/06/2024             │
│ As prestações serão recalculadas      │
│ até esta data.                        │
│                                        │
│ [Cor: Amarelo - alert-warning]        │
└────────────────────────────────────────┘
```

### Alerta SEM Recursos:
```html
┌────────────────────────────────────────┐
│ ⚠️ Termo Rescindido!                  │
│ Rescindido em: 30/06/2024             │
│ ⚠️ SEM RECURSOS REPASSADOS (R$ 0,00) │
│                                        │
│ ⚠️ Ao atualizar, TODAS as prestações │
│ deste termo serão REMOVIDAS, pois não │
│ houve execução financeira.            │
│                                        │
│ [Cor: Amarelo com badge vermelho]    │
│ [Badge: bg-danger]                    │
└────────────────────────────────────────┘
```

---

## 🧪 Casos de Teste Lado a Lado

### Teste A: Adicionar com 6 Meses de Vigência

| Aspecto | COM R$ 150k | SEM R$ 0 |
|---------|------------|----------|
| **Aparece na lista?** | ✅ Sim | ❌ Não |
| **Badge "RESCINDIDO"** | 🔴 Sim | N/A |
| **Data mostrada** | 30/06/2024 (rescindido) | N/A |
| **Botão "Gerar"** | ✅ Funciona | N/A |
| **API Response** | 200 OK | 400 Error |
| **Prestações geradas** | 2 (Semestral + Final) | 0 (erro) |

### Teste B: Atualizar com 2 Prestações Cadastradas

| Aspecto | COM R$ 150k | SEM R$ 0 |
|---------|------------|----------|
| **Aparece na lista?** | ✅ Sim | ✅ Sim |
| **Cor do alerta** | Amarelo | Amarelo + Badge Vermelho |
| **Texto do alerta** | "Recalcula até rescisão" | "REMOVE TUDO" |
| **Prestações Corretas** | 2 (ajustadas) | 0 (nenhuma) |
| **Ação ao clicar** | Recalcula | Deleta |
| **SQL executado** | UPDATE + INSERT | DELETE |
| **Mensagem retorno** | "2 atualizadas" | "2 removidas (sem recursos)" |

---

## 📝 Resumo Executivo

### 🎯 Objetivo da Regra:
Termos rescindidos sem recursos repassados não devem ter prestações de contas, pois não houve execução financeira a ser prestada.

### ✅ Benefícios:
1. **Eficiência:** Analistas não perdem tempo com termos sem execução
2. **Consistência:** Alinha lógica financeira com prestação de contas
3. **Auditoria:** Permite validação humana em "Atualizar Prestações"
4. **Transparência:** Avisos claros sobre remoção de prestações

### 🔧 Implementação:
- **Adicionar Análises:** Filtro automático na query (bloqueio preventivo)
- **Atualizar Prestações:** Validação humana com alerta vermelho (correção)
- **API Calcular:** Retorna erro 400 se tentar calcular

### 🎨 UX:
- Badge vermelho: "SEM RECURSOS REPASSADOS"
- Alerta explícito: "TODAS prestações serão REMOVIDAS"
- Confirmação modal antes de deletar
- Mensagem de sucesso detalhada com contagens

---

**Documentação Visual - Janeiro 2025**  
**Regra:** Rescisão + R$ 0,00 = Sem Prestações  
**Comparação:** COM vs SEM recursos repassados
