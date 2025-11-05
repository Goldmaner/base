# Implementação: Termos Mistos com Dropdown (Prestações DP + Pós-2023)

## Data: 05/11/2025

## Problema Identificado

O sistema não estava lidando corretamente com **termos mistos** - termos que possuem prestações de contas com diferentes responsabilidades ao longo do tempo.

### Exemplo Real
**TCL/230/2019/SMADS/CPLGBTI** possui:
- Prestações 2020-2021: responsabilidade DP (1)
- Prestações 2023: responsabilidade Compartilhada (2)
- Prestações 2024: responsabilidade Pessoa Gestora (3)

## Solução Implementada: DROPDOWN INTERATIVO

### Decisão de Design
Após tentativa inicial de concatenar todos os encaminhamentos (que não funcionou visualmente), optamos por uma **interface com dropdown** que permite ao usuário **selecionar qual encaminhamento visualizar**.

### Vantagens do Dropdown:
1. ✅ Interface limpa e organizada
2. ✅ Usuário escolhe qual texto copiar
3. ✅ Todos os encaminhamentos estão disponíveis
4. ✅ Evita confusão visual com múltiplos textos concatenados

## Implementação Técnica

### 1. Nova Função: `criar_tabela_pre2023(osc_nome)`

**Arquivo**: `scripts/funcoes_texto.py`

**Funcionalidade**: Gera tabela HTML com 4 colunas (incluindo Situação) para termos que possuem **pelo menos uma** prestação com responsabilidade DP (1).

**Query SQL**:
```sql
SELECT DISTINCT 
    p.numero_termo,
    p.sei_pc,
    p.projeto,
    p.situacao
FROM public.parcerias p
INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
WHERE p.osc = %s
  AND pa.responsabilidade_analise = 1
ORDER BY p.numero_termo
```

### 2. Função: `criar_tabela_pos2023(osc_nome, coordenacao_sigla)`

**Query SQL** (já existente, mantida):
```sql
SELECT DISTINCT 
    p.numero_termo,
    p.sei_pc,
    p.projeto
FROM public.parcerias p
INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
WHERE p.osc = %s
  AND pa.responsabilidade_analise IN (2, 3)
  AND p.numero_termo LIKE %s  -- Filtro: '%/COORDENACAO'
ORDER BY p.numero_termo
```

### 3. Função `gerar_texto_misto()` - REESCRITA COM DROPDOWN

**Componentes gerados**:

#### A) Interface com Dropdown
```html
<div style="background-color: #fff3cd; ...">
    <h3>⚠️ ATENÇÃO: Esta OSC possui parcerias com responsabilidades mistas</h3>
    <p>Selecione abaixo qual encaminhamento deseja visualizar:</p>
    <select id="dropdown_encaminhamento" onchange="mostrarEncaminhamento(this.value)">
        <option value="">Selecione um encaminhamento...</option>
        <option value="encaminhamento_pre">SMDHC/DP/DGP (Parcerias pré-2023)</option>
        <option value="encaminhamento_CPLGBTI">SMDHC/CPDDH/CPLGBTI (Parcerias pós-2023)</option>
        <!-- Uma option para cada coordenação -->
    </select>
</div>
```

#### B) JavaScript para Toggle
```javascript
function mostrarEncaminhamento(valor) {
    // Ocultar todos os encaminhamentos
    var encaminhamentos = document.querySelectorAll('[id^="encaminhamento_"]');
    encaminhamentos.forEach(function(elem) {
        elem.style.display = 'none';
    });
    
    // Mostrar apenas o selecionado
    if (valor) {
        var selecionado = document.getElementById(valor);
        if (selecionado) {
            selecionado.style.display = 'block';
        }
    }
}
```

#### C) Encaminhamentos Ocultos (display: none)
```html
<!-- Encaminhamento Pré-2023 -->
<div id="encaminhamento_pre" style="display: none;">
    <div style="background-color: #0e7a8b; ...">ENCAMINHAMENTO - SMDHC/DP/DGP</div>
    [TEXTO MODELO PRÉ-2023 COM TABELA]
</div>

<!-- Encaminhamento Pós-2023 CPLGBTI -->
<div id="encaminhamento_CPLGBTI" style="display: none;">
    <div style="background-color: #0e7a8b; ...">ENCAMINHAMENTO - SMDHC/CPDDH/CPLGBTI</div>
    [TEXTO MODELO PÓS-2023 COM TABELA]
</div>

<!-- Mais encaminhamentos conforme coordenações -->
```

### 4. Atualização: `processar_texto_automatico()`

**Adicionado reconhecimento** de nova função:
```python
# Processar função criar_tabela_pre2023 se existir
padrao_pre2023 = r'criar_tabela_pre2023\s*\([^)]*\)'
match_pre2023 = re.search(padrao_pre2023, texto_processado)

if match_pre2023:
    osc_nome = variaveis.get('osc_informado_usuario', variaveis.get('nome_osc', ''))
    if osc_nome:
        tabela_html = criar_tabela_pre2023(osc_nome)
        texto_processado = re.sub(padrao_pre2023, tabela_html, texto_processado)
```

### 5. Atualização no Banco de Dados

**Script**: `scripts/atualizar_modelo_pre2023.py`

**Alteração**: Modelo ID 7 ("Pesquisa de Parcerias: Parcerias pré-2023")
- **Antes**: `criar_tabela_informado_usuario(...)`
- **Depois**: `criar_tabela_pre2023(...)`

**Status**: ✅ Executado com sucesso

## Comportamento Final

### Caso 1: OSC não existe
- Retorna modelo "OSC sem parcerias"

### Caso 2: OSC com apenas termos DP
- Retorna modelo "Parcerias pré-2023"
- Tabela gerada por `criar_tabela_pre2023()` (4 colunas)
- Mostra apenas termos que têm prestações DP

### Caso 3: OSC com apenas termos Pós-2023
- Retorna modelo(s) "Parcerias pós-2023" (um por coordenação se múltiplas)
- Tabela gerada por `criar_tabela_pos2023()` (3 colunas)
- Filtra por coordenação + responsabilidade (2 ou 3)

### Caso 4: OSC com termos DP E Pós-2023 (MISTO) - **DROPDOWN**
1. **Aviso visual** destacando responsabilidades mistas
2. **Dropdown interativo** listando todos os encaminhamentos disponíveis:
   - SMDHC/DP/DGP (Parcerias pré-2023)
   - [Coordenação 1] (Parcerias pós-2023)
   - [Coordenação 2] (Parcerias pós-2023)
   - ...
3. **Usuário seleciona** qual encaminhamento visualizar
4. **JavaScript mostra/oculta** o conteúdo correspondente

## Cenários de Termos (Lógica de Filtro)

### A) Termo Exclusivamente DP
Exemplo: TCL/001/2020 com apenas prestações 2020-2021 (responsabilidade 1)
- ✅ Aparece no dropdown "SMDHC/DP/DGP"
- ✅ Aparece na tabela pré-2023
- ❌ NÃO aparece em dropdowns pós-2023

### B) Termo Exclusivamente Pós-2023
Exemplo: TFM/042/2025/SMDHC/CPM com apenas prestações 2025 (responsabilidade 3)
- ❌ NÃO aparece no dropdown "SMDHC/DP/DGP"
- ✅ Aparece no dropdown da CPM
- ✅ Aparece na tabela pós-2023 da CPM

### C) Termo Misto (DP + Pós-2023) ⭐
Exemplo: TCL/230/2019/SMADS/CPLGBTI
- ✅ Aparece no dropdown "SMDHC/DP/DGP"
- ✅ Aparece na tabela pré-2023 (tem prestações com responsabilidade 1)
- ✅ Aparece no dropdown da CPLGBTI
- ✅ Aparece na tabela pós-2023 da CPLGBTI (tem prestações com responsabilidade 2 ou 3)

### D) OSC com Múltiplos Termos de Coordenações Diferentes
Exemplo: OSC com:
- TCL/230/2019/SMADS/CPLGBTI (misto)
- TFM/042/2025/SMDHC/CPM (só pós-2023)

**Dropdown mostrará**:
- SMDHC/DP/DGP (Parcerias pré-2023)
- SMDHC/CPDDH/CPLGBTI (Parcerias pós-2023)
- SMDHC/CPDDH/CPM (Parcerias pós-2023)

**Ao selecionar "SMDHC/DP/DGP"**:
- Tabela mostra: TCL/230/2019 (tem prestações DP)

**Ao selecionar "SMDHC/CPDDH/CPLGBTI"**:
- Tabela mostra: TCL/230/2019 (tem prestações pós-2023 da CPLGBTI)

**Ao selecionar "SMDHC/CPDDH/CPM"**:
- Tabela mostra: TFM/042/2025 (tem prestações pós-2023 da CPM)

## Experiência do Usuário

1. **Sistema detecta** que OSC tem responsabilidades mistas
2. **Página mostra**:
   - ⚠️ Aviso amarelo explicando a situação
   - 📋 Dropdown com lista de encaminhamentos
   - 👁️ Inicialmente nenhum texto visível
3. **Usuário seleciona** no dropdown qual encaminhamento deseja ver
4. **JavaScript exibe** apenas o texto do encaminhamento selecionado
5. **Usuário copia** o texto completo
6. **Pode trocar** seleção no dropdown para ver outros encaminhamentos

## Testes Necessários

- [ ] Caso 1: OSC inexistente
- [ ] Caso 2: OSC apenas DP (sem termos pós-2023)
- [ ] Caso 3: OSC apenas Pós-2023 (IGLA - já testado anteriormente)
- [ ] Caso 4: OSC mista com dropdown
  - [ ] Dropdown aparece corretamente
  - [ ] Opções listadas corretas
  - [ ] JavaScript funciona (mostra/oculta)
  - [ ] Termos mistos aparecem em múltiplos encaminhamentos
  - [ ] Tabelas filtram corretamente por responsabilidade

## Arquivos Modificados

1. ✅ `scripts/funcoes_texto.py` 
   - Nova função `criar_tabela_pre2023()`
   - Função `gerar_texto_misto()` reescrita com dropdown + JavaScript
   - `processar_texto_automatico()` reconhece `criar_tabela_pre2023()`
2. ✅ `scripts/atualizar_modelo_pre2023.py` - Script de migração criado e executado
3. ✅ Banco de dados - Modelo ID 7 atualizado
4. ✅ `melhorias/IMPLEMENTACAO_TERMOS_MISTOS.md` - Documentação atualizada

## Próximos Passos

1. Reiniciar servidor de desenvolvimento
2. Testar dropdown com OSC mista no navegador
3. Validar que JavaScript funciona corretamente
4. Verificar que termos mistos aparecem nas tabelas corretas
5. Ajustar estilo visual se necessário
