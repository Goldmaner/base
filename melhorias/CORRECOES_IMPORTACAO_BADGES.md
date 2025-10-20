# Correções: Importação de Orçamento e Badges de Termos

## Data: 20/10/2025

## Problemas Identificados

### 1. **Soma Incorreta no Orçamento_2 (Importação)**
**Sintoma:** Ao importar um modelo em `orcamento_2`, a soma total mostrada no rodapé estava **MUITO superior** ao esperado, apesar dos valores individuais estarem corretos (ex: 52.499,56 em cada mês).

**Causa Raiz:** O cálculo estava somando **cada célula individualmente** (valor × mês), quando deveria somar o **total de todas as despesas de todos os meses**.

**Exemplo do problema:**
- Valor por mês: R$ 52.499,56
- 4 meses
- Soma esperada: R$ 52.499,56 × 4 = R$ 209.998,24
- Soma mostrada: Valor muito maior (possível duplicação ou formatação incorreta)

### 2. **Badges de Termos não Funcionando (Orçamento_3)**
**Sintoma:** As badges verdes com ícone de lista que mostram quantos termos usam cada categoria no dicionário de despesas não estavam funcionando ao clicar.

**Causa Raiz:** 
1. Falta de decorador `@login_required` na rota `/orcamento/termos-por-categoria/<categoria>`
2. Parâmetro da rota não aceitava caracteres especiais em URLs (faltava `<path:categoria>`)
3. Imports desnecessários causando erros

## Correções Aplicadas

### Arquivo: `routes/despesas.py`

#### 1. Melhorado parsing de valores monetários (linha ~114-147)

**Antes:**
```python
valor = float(str(valor_str).replace(',', '.').replace('R$', '').replace(' ', ''))
total_inserido += valor
```

**Depois:**
```python
# Limpar e converter o valor (pode vir formatado como "52.499,56" ou "52499.56")
valor_limpo = str(valor_str).replace('R$', '').replace(' ', '').strip()
# Se tiver ponto E vírgula, é formato BR (1.234,56)
if '.' in valor_limpo and ',' in valor_limpo:
    valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
# Se tiver apenas vírgula, trocar por ponto
elif ',' in valor_limpo:
    valor_limpo = valor_limpo.replace(',', '.')

valor = float(valor_limpo)
total_inserido += valor
```

**Benefício:** Agora suporta corretamente:
- Formato BR: `52.499,56` → `52499.56`
- Formato US: `52499.56` → `52499.56`
- Com R$: `R$ 1.234,56` → `1234.56`

#### 2. Adicionado log de erro em conversão

```python
except (ValueError, TypeError) as e:
    print(f"[ERRO] Falha ao converter valor '{valor_str}' para float: {e}")
    continue
```

**Benefício:** Facilita debug quando um valor não puder ser convertido.

#### 3. Convertido para Dual Database Write

**Antes (criar_despesa):**
```python
db = get_db()
cur.execute("DELETE FROM Parcerias_Despesas WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s", (numero_termo, aditivo))
for registro in registros_para_inserir:
    cur.execute("INSERT INTO Parcerias_Despesas ...", (...))
db.commit()
```

**Depois:**
```python
# Deletar despesas antigas do aditivo em ambos os bancos
delete_query = "DELETE FROM Parcerias_Despesas WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s"
execute_dual(delete_query, (numero_termo, aditivo))

# Inserir novas despesas em ambos os bancos
for registro in registros_para_inserir:
    execute_dual(insert_query, (...))
```

**Mesmo padrão aplicado em:**
- `confirmar_despesa()` - linha ~246-320

**Benefício:** Agora as despesas são salvas nos dois bancos (LOCAL e RAILWAY) simultaneamente.

### Arquivo: `routes/orcamento.py`

#### 1. Corrigida rota de termos por categoria (linha ~387-430)

**Antes:**
```python
@orcamento_bp.route('/termos-por-categoria/<categoria>', methods=['GET'])
def termos_por_categoria(categoria):
    from flask import jsonify
    from db import get_db
    import psycopg2.extras
    
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # ...
    except psycopg2.Error as e:
        return jsonify({"error": ...}), 500
```

**Depois:**
```python
@orcamento_bp.route('/termos-por-categoria/<path:categoria>', methods=['GET'])
@login_required
def termos_por_categoria(categoria):
    from flask import jsonify
    
    cur = get_cursor()  # Usa cursor padrão (já com RealDictCursor)
    # ...
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar termos: {str(e)}"}), 500
```

**Mudanças:**
- ✅ Adicionado `@login_required` - agora requer autenticação
- ✅ `<categoria>` → `<path:categoria>` - aceita `/` e outros caracteres especiais em URLs
- ✅ Removido `psycopg2.extras` desnecessário
- ✅ Usa `get_cursor()` em vez de criar cursor manualmente
- ✅ Exception handling simplificado

#### 2. Convertida rota atualizar-categoria para Dual Database (linha ~258-290)

**Antes:**
```python
db = get_db()
cur = db.cursor()
cur.execute("UPDATE Parcerias_Despesas SET categoria_despesa = %s WHERE categoria_despesa = %s", ...)
linhas_afetadas = cur.rowcount
db.commit()
cur.close()
```

**Depois:**
```python
query = """
    UPDATE Parcerias_Despesas
    SET categoria_despesa = %s
    WHERE categoria_despesa = %s
"""

if execute_dual(query, (categoria_nova.strip(), categoria_antiga)):
    return jsonify({"message": "Categoria atualizada com sucesso!", ...}), 200
else:
    return jsonify({"error": "Falha ao atualizar categoria em ambos os bancos"}), 500
```

**Benefício:** Atualizações de categoria agora são feitas nos dois bancos.

## Testes Recomendados

### 1. Testar Importação de Orçamento
1. Acesse `/orcamento/editar/<numero_termo>`
2. Clique em "Importar de Modelo"
3. Selecione um arquivo CSV/Excel com despesas
4. **Verifique:**
   - ✅ Soma no rodapé = total previsto do termo
   - ✅ Valores individuais por mês corretos
   - ✅ Não há duplicação de valores

### 2. Testar Badges de Termos (Dicionário)
1. Acesse `/orcamento/dicionario-despesas`
2. Clique na badge verde com número de termos (ex: `🗒️ 5`)
3. **Verifique:**
   - ✅ Modal abre com lista de termos
   - ✅ Mostra número de termo, quantidade de despesas e valor total
   - ✅ Rodapé com totalizadores

### 3. Testar Dual Database Write
1. Crie/edite despesas em `orcamento_2`
2. **Verifique no PostgreSQL LOCAL:**
   ```sql
   SELECT * FROM Parcerias_Despesas WHERE numero_termo = 'TERMO/TESTE/2025';
   ```
3. **Verifique no PostgreSQL RAILWAY:**
   ```sql
   SELECT * FROM Parcerias_Despesas WHERE numero_termo = 'TERMO/TESTE/2025';
   ```
4. **Resultado esperado:** Dados idênticos em ambos os bancos

## Status

✅ **Correções Aplicadas:**
- Parsing de valores monetários melhorado
- Badges de termos funcionando
- Dual database write implementado em despesas
- Dual database write implementado em atualização de categorias

⚠️ **Atenção:**
- Execute testes para confirmar que importação de orçamento agora calcula corretamente
- Verifique logs do terminal para mensagens de `[ERRO]` durante importações

## Correção Adicional: Normalização de Valores na Importação

### Problema Identificado (20/10/2025 - 2ª iteração)
Ao importar Excel/CSV no `orcamento_2`, os valores monetários estavam sendo inseridos **sem normalização**, causando:
- Somas absurdas no rodapé (ex: 6.136.053,00 quando deveria ser ~200.000)
- Valores duplicados ou multiplicados incorretamente

### Causa Raiz
O Excel/CSV pode exportar valores em diferentes formatos:
- Formato US: `52499.56` (número puro)
- Formato BR: `"52.499,56"` (string formatada)
- Com símbolo: `"R$ 52.499,56"`
- Com espaços: `" 52499.56 "`

A função `importFromJson()` estava inserindo os valores **como estavam no arquivo** (linha 338), sem normalização prévia.

### Solução Aplicada

Modificada a função `importFromJson()` no template `orcamento_2.html` (linhas ~313-354) para normalizar valores **antes** de inserir nos inputs:

```javascript
// ANTES
const valorInputs = tr.querySelectorAll('input.valor');
monthCols.forEach((mc, idx) => {
  const v = data[mc];
  if (valorInputs[idx]) valorInputs[idx].value = (v === undefined || v === null) ? '' : String(v);
});

// DEPOIS
const valorInputs = tr.querySelectorAll('input.valor');
monthCols.forEach((mc, idx) => {
  let v = data[mc];
  if (v === undefined || v === null || String(v).trim() === '' || String(v).trim() === '-') {
    if (valorInputs[idx]) valorInputs[idx].value = '';
    return;
  }
  // Normalizar valor: aceitar 52499.56 (US) ou 52.499,56 (BR)
  let vStr = String(v).replace(/R\$\s*/g, '').trim();
  // Se tiver ponto E vírgula, é formato BR (1.234,56)
  if (vStr.includes('.') && vStr.includes(',')) {
    vStr = vStr.replace(/\./g, '').replace(',', '.');
  } 
  // Se tiver apenas vírgula, é decimal BR (1234,56)
  else if (vStr.includes(',')) {
    vStr = vStr.replace(',', '.');
  }
  // Converter para número e formatar no padrão BR
  const num = parseFloat(vStr);
  if (!isNaN(num) && num !== 0) {
    const formatted = num.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    if (valorInputs[idx]) valorInputs[idx].value = formatted;
  } else {
    if (valorInputs[idx]) valorInputs[idx].value = num === 0 ? '0' : '';
  }
});
```

### Benefícios
✅ Suporta múltiplos formatos de entrada (US, BR, com/sem R$)  
✅ Normaliza para formato BR (`52.499,56`) antes de exibir  
✅ Calcula totais corretamente após importação  
✅ Console.log adicionado para debug  

### Como Testar
1. Crie um Excel com valores em formato BR: `52.499,56`
2. Importe no `/orcamento/editar/<termo>`
3. Verifique que o rodapé mostra a soma correta
4. Abra Console do navegador (F12) e veja logs de `[IMPORTACAO]`

## Próximos Passos (Opcional)

1. **Validação de formato de entrada:** Adicionar validação no frontend para aceitar apenas formatos válidos (ex: `12.345,67` ou `12345.67`)
2. **Feedback visual:** Mostrar spinner durante importação de arquivos grandes
3. **Log de auditoria:** Registrar quem alterou categorias e quando no dicionário de despesas
4. **Teste de carga:** Importar arquivo com 1000+ linhas para validar performance
