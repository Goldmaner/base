# Funcionalidade "Meus Processos"

## Visão Geral
Sistema que permite aos analistas visualizarem apenas os checklists de análise de prestação de contas que foram atribuídos a eles, com funcionalidades especiais para administradores.

## Funcionalidades Implementadas

### 1. Auto-carregamento de Checklist
**Problema resolvido:** Quando o usuário clicava em "Abrir" na lista de processos, era redirecionado para a página do checklist, mas precisava preencher manualmente os campos e clicar em "Prosseguir".

**Solução implementada:**
- Ao clicar em "Abrir" na lista de "Meus Processos", o sistema:
  1. Redireciona para `/analises_pc/?termo=XXX&meses=YYY&autoload=true`
  2. Pré-preenche automaticamente o Número do Termo
  3. Carrega os meses disponíveis
  4. Seleciona o período correto
  5. Busca os analistas já cadastrados no checklist
  6. **Carrega automaticamente o checklist completo** sem necessidade de clicar em "Prosseguir"

**Arquivos modificados:**
- `templates/analises_pc/index.html`: Adicionada função `carregarChecklistAutomatico()`
- `templates/analises_pc/meus_processos.html`: Botão "Abrir" agora inclui `autoload=true`

### 2. Filtro de Analista para Admin
**Funcionalidade:** Agentes Públicos (admin) podem visualizar os processos atribuídos a qualquer analista.

**Como funciona:**
- Admin acessa `/analises_pc/meus_processos`
- Visualiza um card de "Filtro de Analista (Admin)" no topo da página
- Pode selecionar qualquer analista ativo do dropdown
- Ao clicar em "Filtrar", visualiza todos os processos atribuídos àquele analista
- Se não selecionar nenhum analista, visualiza seus próprios processos (baseado no R.F.)

**Regras de negócio:**
- Usuários normais: Veem apenas seus processos (matching por R.F.)
- Admins: Podem ver processos de qualquer analista OU seus próprios processos
- Filtro aparece apenas para usuários com `tipo_usuario = 'Agente Público'`

**Arquivos modificados:**
- `routes/analises_pc/routes.py`: Rota `meus_processos()` atualizada com lógica de admin
- `templates/analises_pc/meus_processos.html`: Adicionado card de filtro com Select2

## Fluxo de Uso

### Usuário Normal (Analista)
1. Acessa "Meus Processos" no menu
2. Visualiza lista de processos onde está cadastrado como analista
3. Clica em "Abrir" em um processo
4. **Checklist é carregado automaticamente**, pronto para trabalhar

### Admin (Agente Público)
1. Acessa "Meus Processos" no menu
2. Visualiza filtro de analista no topo
3. **Opção A:** Seleciona um analista específico
   - Vê mensagem: "Visualizando processos de: [Nome do Analista]"
   - Lista mostra todos os processos daquele analista
4. **Opção B:** Deixa filtro vazio
   - Vê seus próprios processos (baseado no R.F.)
5. Clica em "Abrir" para carregar checklist automaticamente

## Matching de R.F. (Registro Funcional)

### Formatos Suportados
- `d843702` (formato do usuário em `public.usuarios`)
- `843.702-5` (formato do analista em `categoricas.c_analistas`)

### Lógica de Normalização
```python
def normalizar_rf(rf):
    # Remove 'd' inicial, extrai apenas dígitos
    # Retorna primeiros 6 dígitos (ignora dígito verificador)
    # Exemplo: "d843702" → "843702"
    # Exemplo: "843.702-5" → "843702"
```

### Processo de Matching
1. Busca R.F. do usuário em `public.usuarios.d_usuario`
2. Normaliza R.F. do usuário
3. Busca todos os analistas em `categoricas.c_analistas`
4. Normaliza R.F. de cada analista
5. Compara valores normalizados (primeiros 6 dígitos)
6. Retorna lista de nomes de analistas correspondentes

## Estrutura de Dados

### Rota: `/analises_pc/meus_processos`
**Parâmetros GET:**
- `analista` (opcional): Nome do analista para filtrar (apenas admin)

**Template variables:**
- `processos`: Lista de processos com `numero_termo`, `meses_analisados`, `analistas`, `total_analistas`
- `todos_analistas`: Lista de todos os analistas ativos (apenas para admin)
- `is_admin`: Boolean indicando se usuário é Agente Público
- `analista_selecionado`: Nome do analista filtrado (se houver)
- `mensagem`: Mensagem de contexto ou erro

## Segurança
- ✅ Verificação de login obrigatória
- ✅ Usuários normais só veem seus próprios processos
- ✅ Filtro de admin validado server-side
- ✅ Queries SQL parametrizadas (proteção contra SQL injection)

## Testes Sugeridos

### Teste 1: Usuário Normal
1. Login como analista
2. Verificar que não vê filtro de analista
3. Verificar que lista mostra apenas processos atribuídos ao seu R.F.
4. Clicar em "Abrir" e verificar carregamento automático

### Teste 2: Admin - Próprios Processos
1. Login como Agente Público
2. Verificar que filtro aparece
3. Deixar filtro vazio
4. Verificar que mostra processos do próprio R.F.

### Teste 3: Admin - Processos de Outro Analista
1. Login como Agente Público
2. Selecionar analista no filtro
3. Clicar em "Filtrar"
4. Verificar mensagem "Visualizando processos de: [Nome]"
5. Verificar que lista mostra processos do analista selecionado

### Teste 4: Auto-carregamento
1. Acessar "Meus Processos"
2. Clicar em "Abrir" em qualquer processo
3. Verificar que:
   - Número do Termo é pré-preenchido
   - Meses em Análise é pré-selecionado
   - Analistas são carregados
   - Checklist é exibido automaticamente
   - Não é necessário clicar em "Prosseguir"

## Melhorias Futuras Sugeridas
- [ ] Adicionar paginação na lista de processos
- [ ] Adicionar ordenação por colunas (termo, meses, etc.)
- [ ] Adicionar busca/filtro por número do termo
- [ ] Adicionar indicador visual de progresso do checklist (% completo)
- [ ] Exportar lista de processos para Excel
- [ ] Adicionar coluna com data de última modificação (requer ALTER TABLE)
