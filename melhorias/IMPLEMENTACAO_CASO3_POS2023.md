# 🎯 Implementação do Caso 3: Parcerias pós-2023

## 📋 Resumo da Implementação

Este documento descreve a implementação do **Caso 3** do sistema de Pesquisa de Parcerias, que trata de OSCs com termos **pós-2023** (responsabilidade de **Pessoa Gestora** ou **Compartilhado**).

---

## 🔀 Lógica dos 3 Casos

O sistema agora identifica automaticamente qual modelo usar:

### **Caso 1: OSC não existe nos bancos**
- **Condição**: `verificar_osc_existe(nome_osc) == False`
- **Modelo**: "Pesquisa de Parcerias: OSC sem parcerias SMDHC"
- **Comportamento**: Texto simples com substituição de variáveis

### **Caso 2: OSC com termos pré-2023 (responsabilidade DP)**
- **Condição**: OSC existe + `responsabilidade_analise = 1`
- **Modelo**: "Pesquisa de Parcerias: Parcerias pré-2023"
- **Comportamento**: Tabela com 4 colunas (Termo, SEI, Projeto, **Situação**)
- **Função**: `criar_tabela_informado_usuario(osc_nome)`

### **Caso 3: OSC com termos pós-2023 (responsabilidade PG/Compartilhado)** ⭐ NOVO
- **Condição**: OSC existe + `responsabilidade_analise IN (2, 3)`
- **Modelo**: "Pesquisa de Parcerias: Parcerias pós-2023"
- **Comportamento**: 
  - Identifica coordenações distintas (ex: CPJ, CPPI)
  - Gera **múltiplos encaminhamentos** (um por coordenação)
  - Tabela com 3 colunas (Termo, SEI, Projeto) - **SEM** coluna Situação
- **Funções**: 
  - `verificar_osc_tem_pos2023(osc_nome)`
  - `gerar_encaminhamentos_pos2023(texto_modelo, variaveis)`

---

## 🛠️ Novas Funções Criadas

### 1️⃣ `criar_tabela_pos2023(osc_nome, coordenacao_sigla)`
**Arquivo**: `scripts/funcoes_texto.py` (linhas ~11-100)

**Propósito**: Gera tabela HTML simplificada (apenas 3 colunas) para uma coordenação específica.

**Query**:
```sql
SELECT DISTINCT 
    p.numero_termo,
    p.sei_pc,
    p.projeto
FROM public.parcerias p
INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
WHERE p.osc = %s
  AND pa.responsabilidade_analise IN (2, 3)
  AND p.numero_termo LIKE %s  -- Filtra por coordenação (ex: '%/CPJ')
ORDER BY p.numero_termo
```

**Saída**: HTML com formato SEI (border, Calibri 12pt, centralizado)

---

### 2️⃣ `identificar_coordenacoes(osc_nome)`
**Arquivo**: `scripts/funcoes_texto.py` (linhas ~103-150)

**Propósito**: Identifica todas as coordenações distintas que possuem termos pós-2023 para uma OSC.

**Lógica**:
1. Busca todos os termos com `responsabilidade_analise IN (2, 3)`
2. Extrai sigla após última barra (ex: `ACP/001/2024/SMDHC/CPJ` → `CPJ`)
3. Retorna lista ordenada de siglas únicas (ex: `['CPJ', 'CPPI']`)

**Retorno**: `List[str]` - Ex: `['CPJ', 'CPPI', 'CPAS']`

---

### 3️⃣ `obter_setor_sei(coordenacao_sigla)`
**Arquivo**: `scripts/funcoes_texto.py` (linhas ~153-180)

**Propósito**: Busca o setor SEI completo da coordenação.

**Query**:
```sql
SELECT setor_sei
FROM categoricas.c_coordenadores
WHERE coordenacao = %s
LIMIT 1
```

**Exemplo**:
- Input: `'CPJ'`
- Output: `'SMDHC/CPDDH/CPJ'`

**Retorno**: `str | None`

---

### 4️⃣ `verificar_osc_tem_pos2023(osc_nome)`
**Arquivo**: `scripts/funcoes_texto.py` (linhas ~233-260)

**Propósito**: Verifica se OSC possui ao menos 1 termo pós-2023.

**Query**:
```sql
SELECT COUNT(*) as total
FROM public.parcerias p
INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
WHERE p.osc = %s
  AND pa.responsabilidade_analise IN (2, 3)
LIMIT 1
```

**Retorno**: `bool` - `True` se tem termos pós-2023

---

### 5️⃣ `gerar_encaminhamentos_pos2023(texto_base_modelo, variaveis)`
**Arquivo**: `scripts/funcoes_texto.py` (linhas ~263-320)

**Propósito**: Gera **múltiplos encaminhamentos**, um para cada coordenação identificada.

**Fluxo**:
1. Chama `identificar_coordenacoes(osc_nome)` → `['CPJ', 'CPPI']`
2. Para cada coordenação:
   - Busca `setor_sei` com `obter_setor_sei(coord_sigla)`
   - Cria `variaveis` com:
     - `coordenacao_informado_usuario` → `'SMDHC/CPDDH/CPJ'`
     - `coordenacao_sigla` → `'CPJ'`
   - Processa texto com `processar_texto_automatico()`
   - Adiciona à lista de encaminhamentos
3. Concatena todos com `<hr style="margin: 30px 0;">` entre eles

**Exemplo de Saída**:
```html
SMDHC/CPDDH/CPJ
PESSOA GESTORA
...
<table>...</table> (só termos de CPJ)
...
<hr style="margin: 30px 0;">
SMDHC/CPDDH/CPPI
PESSOA GESTORA
...
<table>...</table> (só termos de CPPI)
...
```

---

## 🔄 Alterações nas Rotas

### **routes/pesquisa_parcerias.py**

#### 1️⃣ Importações atualizadas (linhas 14-28):
```python
from funcoes_texto import (
    processar_texto_automatico, 
    obter_modelo_texto, 
    verificar_osc_existe,
    verificar_osc_tem_pos2023,       # ⭐ NOVO
    gerar_encaminhamentos_pos2023    # ⭐ NOVO
)
```

#### 2️⃣ Rota `prosseguir_pesquisa()` - Detecção de Caso (linhas ~396-418):
```python
# Determinar qual modelo usar baseado em 3 casos:
if not osc_existe:
    # Caso 1: OSC não existe
    titulo_modelo = "Pesquisa de Parcerias: OSC sem parcerias SMDHC"
    usar_multiplos_encaminhamentos = False
else:
    # OSC existe - verificar se tem termos pós-2023
    tem_pos2023 = verificar_osc_tem_pos2023(nome_osc)
    
    if tem_pos2023:
        # Caso 3: Termos pós-2023 (responsabilidade 2 ou 3)
        titulo_modelo = "Pesquisa de Parcerias: Parcerias pós-2023"
        usar_multiplos_encaminhamentos = True  # ⭐ NOVO
    else:
        # Caso 2: Termos pré-2023 (responsabilidade 1)
        titulo_modelo = "Pesquisa de Parcerias: Parcerias pré-2023"
        usar_multiplos_encaminhamentos = False
```

#### 3️⃣ Processamento condicional (linhas ~435-441):
```python
# Se for Caso 3 (múltiplas coordenações), usar função especial
if usar_multiplos_encaminhamentos:
    texto_processado = gerar_encaminhamentos_pos2023(modelo['modelo_texto'], variaveis)
else:
    texto_processado = processar_texto_automatico(modelo['modelo_texto'], variaveis)
```

#### 4️⃣ Mesma lógica aplicada em `exibir_texto_automatico()` (linhas ~480-520)

---

## 📝 Modelo de Texto no Banco

### **Arquivo SQL**: `scripts/insert_modelo_pos2023.sql`

**Título**: `"Pesquisa de Parcerias: Parcerias pós-2023"`

**Estrutura do Texto**:
```
coordenacao_informado_usuario    ← Substituído por SMDHC/CPDDH/CPJ
PESSOA GESTORA

Em atendimento à solicitação registrada em SEI nº sei_informado_usuario...
...com a organização osc_informado_usuario, inscrita no CNPJ nº cnpj_informado_usuario...

...conferindo à Pessoa Gestora o acompanhamento da entrega da prestação de contas...

criar_tabela_pos2023(cabeçalho: Número do Termo; Processo SEI PC; Nome do Projeto)
                     ↑ Gera tabela com 3 colunas para esta coordenação

Desse modo, solicitamos:

Para entrega de prestação de contas REGULAR...
Para AUSÊNCIA de entrega de prestação de contas...
Somente após a efetiva apresentação da prestação de contas exigível...
```

**Variáveis Suportadas**:
- `coordenacao_informado_usuario` → Setor SEI completo (ex: `SMDHC/CPDDH/CPJ`)
- `sei_informado_usuario` → SEI do formulário
- `osc_informado_usuario` → Nome da OSC
- `cnpj_informado_usuario` → CNPJ ou "não informado"
- `nome_emissor` → Nome do emissor
- `numero_pesquisa` → Número da pesquisa

---

## 🎭 Exemplo de Uso Completo

### **Cenário**: OSC "Associação Comunitária X" tem termos em CPJ e CPPI

1. **Usuário preenche formulário**:
   - SEI: `6001.2024/1234567-8`
   - OSC: `Associação Comunitária X`
   - CNPJ: `12.345.678/0001-90`
   - Emissor: `João Silva`

2. **Sistema detecta**:
   - `verificar_osc_existe('Associação Comunitária X')` → `True`
   - `verificar_osc_tem_pos2023('Associação Comunitária X')` → `True`
   - Modelo: `"Pesquisa de Parcerias: Parcerias pós-2023"`
   - `usar_multiplos_encaminhamentos = True`

3. **Processamento**:
   - Chama `gerar_encaminhamentos_pos2023()`
   - `identificar_coordenacoes()` → `['CPJ', 'CPPI']`
   
4. **Para CPJ**:
   - `obter_setor_sei('CPJ')` → `'SMDHC/CPDDH/CPJ'`
   - Substitui `coordenacao_informado_usuario` → `SMDHC/CPDDH/CPJ`
   - Chama `criar_tabela_pos2023('Associação Comunitária X', 'CPJ')`
   - Query filtra: `numero_termo LIKE '%/CPJ'`
   - Gera tabela com termos: `ACP/001/2024/SMDHC/CPJ`, `ACP/005/2024/SMDHC/CPJ`

5. **Para CPPI**:
   - `obter_setor_sei('CPPI')` → `'SMDHC/CPDDH/CPPI'`
   - Substitui `coordenacao_informado_usuario` → `SMDHC/CPDDH/CPPI`
   - Chama `criar_tabela_pos2023('Associação Comunitária X', 'CPPI')`
   - Query filtra: `numero_termo LIKE '%/CPPI'`
   - Gera tabela com termos: `ACP/003/2024/SMDHC/CPPI`

6. **Resultado Final**:
```html
SMDHC/CPDDH/CPJ
PESSOA GESTORA

Em atendimento à solicitação... (texto completo)

<table border="1"...>
  <tr><td>ACP/001/2024/SMDHC/CPJ</td><td>6001.2024/111-1</td><td>Projeto A</td></tr>
  <tr><td>ACP/005/2024/SMDHC/CPJ</td><td>6001.2024/222-2</td><td>Projeto B</td></tr>
</table>

Desse modo, solicitamos... (texto completo)

<hr style="margin: 30px 0;">

SMDHC/CPDDH/CPPI
PESSOA GESTORA

Em atendimento à solicitação... (texto completo)

<table border="1"...>
  <tr><td>ACP/003/2024/SMDHC/CPPI</td><td>6001.2024/333-3</td><td>Projeto C</td></tr>
</table>

Desse modo, solicitamos... (texto completo)
```

---

## 🧪 Testando a Implementação

### **1. Preparar banco de dados**:
```powershell
# Execute o SQL para inserir o modelo
cd "C:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF"
python -c "from db import get_cursor; cur = get_cursor(); cur.execute(open('scripts/insert_modelo_pos2023.sql', 'r', encoding='utf-8').read()); print('✅ Modelo inserido!')"
```

### **2. Verificar se OSC tem termos pós-2023**:
```sql
SELECT p.osc, p.numero_termo, pa.responsabilidade_analise
FROM public.parcerias p
INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
WHERE pa.responsabilidade_analise IN (2, 3)
ORDER BY p.osc
LIMIT 10;
```

### **3. Testar no formulário**:
1. Acesse: `http://localhost:5000/pesquisa-parcerias`
2. Preencha com OSC que tem termos pós-2023
3. Clique "Prosseguir Pesquisa"
4. **Resultado esperado**:
   - Múltiplos encaminhamentos (um por coordenação)
   - Cada um com cabeçalho de coordenação (ex: `SMDHC/CPDDH/CPJ`)
   - Tabelas separadas por `<hr>`

### **4. Verificar logs**:
```
[SUCESSO] Coordenações identificadas: ['CPJ', 'CPPI']
[SUCESSO] Setor SEI para CPJ: SMDHC/CPDDH/CPJ
[SUCESSO] Tabela gerada para CPJ com 2 termos
[SUCESSO] Setor SEI para CPPI: SMDHC/CPDDH/CPPI
[SUCESSO] Tabela gerada para CPPI com 1 termo
```

---

## ⚠️ Troubleshooting

### **Problema**: Não gera múltiplos encaminhamentos
**Solução**: Verificar se `verificar_osc_tem_pos2023()` retorna `True`:
```python
from scripts.funcoes_texto import verificar_osc_tem_pos2023
print(verificar_osc_tem_pos2023('Nome da OSC'))  # Deve retornar True
```

### **Problema**: Coordenação não encontrada
**Solução**: Verificar se coordenação existe em `c_coordenadores`:
```sql
SELECT * FROM categoricas.c_coordenadores WHERE coordenacao = 'CPJ';
```

### **Problema**: Tabela vazia
**Solução**: Verificar se termos têm padrão correto (ex: `%/CPJ`):
```sql
SELECT numero_termo FROM public.parcerias WHERE numero_termo LIKE '%/CPJ';
```

---

## 📊 Comparação dos 3 Casos

| Aspecto | Caso 1 | Caso 2 | Caso 3 ⭐ |
|---------|--------|--------|----------|
| **OSC existe?** | ❌ Não | ✅ Sim | ✅ Sim |
| **Responsabilidade** | N/A | 1 (DP) | 2 ou 3 (PG/Comp.) |
| **Modelo** | "OSC sem parcerias" | "Parcerias pré-2023" | "Parcerias pós-2023" |
| **Tabela?** | ❌ Não | ✅ Sim (4 cols) | ✅ Sim (3 cols) |
| **Coluna Situação?** | ❌ N/A | ✅ Sim | ❌ Não |
| **Múltiplos Encaminhamentos?** | ❌ Não | ❌ Não | ✅ Sim |
| **Função Principal** | `processar_texto_automatico()` | `criar_tabela_informado_usuario()` | `gerar_encaminhamentos_pos2023()` |
| **Variável Especial** | - | - | `coordenacao_informado_usuario` |

---

## 🎉 Implementação Concluída!

**Arquivos modificados**:
- ✅ `scripts/funcoes_texto.py` (5 novas funções)
- ✅ `routes/pesquisa_parcerias.py` (lógica de 3 casos)
- ✅ `scripts/insert_modelo_pos2023.sql` (novo modelo)

**Funcionalidades**:
- ✅ Detecção automática de 3 casos
- ✅ Múltiplos encaminhamentos por coordenação
- ✅ Tabela simplificada (sem Situação)
- ✅ Substituição de `coordenacao_informado_usuario`
- ✅ Separador visual entre encaminhamentos (`<hr>`)

**Próximo passo**: Executar SQL e testar com OSC real! 🚀
