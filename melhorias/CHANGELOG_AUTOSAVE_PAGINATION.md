# Changelog - Paginação, Dropdowns e Autosave

**Data:** 14 de Outubro de 2025

## Resumo das Alterações

Este documento descreve as alterações implementadas para adicionar funcionalidades de paginação, dropdowns categóricos e autosave ao sistema FAF.

---

## 1. Paginação ("Mostrar somente X linhas")

### Páginas Afetadas
- `parcerias.html` - Lista de parcerias
- `orcamento_1.html` - Lista de orçamentos

### Funcionalidades Implementadas
- **Opções de paginação:** 10, 50, 100, 1000, ou "Todas" linhas
- **Padrão:** 100 linhas
- **Persistência de filtros:** Ao alterar a paginação, os filtros aplicados são mantidos
- **Implementação backend:** Query SQL com cláusula `LIMIT` dinâmica

### Arquivos Modificados

#### Backend
- `routes/parcerias.py`
  - Adicionado parâmetro `limite` na função `listar()`
  - Query SQL modificada para incluir `LIMIT` quando não for "todas"
  - Passa o valor de `limite` para o template

- `routes/orcamento.py`
  - Importado `request` do Flask
  - Adicionado parâmetro `limite` na função `listar()`
  - Query SQL modificada para incluir `LIMIT` quando não for "todas"
  - Passa o valor de `limite` para o template

#### Frontend
- `templates/parcerias.html`
  - Adicionado dropdown "Mostrar somente" com 5 opções
  - Dropdown mantém a seleção atual através de `{% if limite == 'X' %}selected{% endif %}`
  - Submit automático do formulário ao mudar a seleção

- `templates/orcamento_1.html`
  - Adicionado dropdown "Mostrar somente" na seção de filtros
  - Função JavaScript `atualizarLimite()` para recarregar a página com novo limite
  - Mantém URL parameters para preservar outros filtros

---

## 2. Dropdowns Categóricos

### Tabelas do Banco de Dados Utilizadas
- `c_tipo_contrato` - Coluna: `informacao`
  - Valores: Acordo de Cooperação, Colaboração, Convênio, Convênio de Cooperação, Fomento, etc.
  
- `c_legislacao` - Coluna: `lei`
  - Valores: Decreto nº 6.170, Portaria nº 006/2008/SF-SEMPLA, Portaria nº 072/SMPP/2012, etc.

### Implementação

#### Filtro de Parcerias
**Arquivo:** `templates/parcerias.html`
- Campo "Tipo de Termo" convertido de input text para dropdown
- Opções carregadas dinamicamente da tabela `c_tipo_contrato`
- Opção "-- Todos --" para limpar o filtro

#### Formulário de Parcerias
**Arquivo:** `templates/parcerias_form.html`
- Campo "Tipo de Termo" convertido para dropdown (select)
- Campo "Portaria" convertido para dropdown (select)
- Opções carregadas das tabelas categóricas
- Seleção automática do valor atual ao editar

#### Backend
**Arquivo:** `routes/parcerias.py`
- Função `listar()`:
  - Query para buscar `tipos_contrato` de `c_tipo_contrato`
  - Passa lista para o template

- Função `nova()`:
  - Query para buscar `tipos_contrato` e `legislacoes`
  - Passa ambas as listas para o template

- Função `editar()`:
  - Query para buscar `tipos_contrato` e `legislacoes`
  - Passa ambas as listas junto com os dados da parceria

---

## 3. Autosave (Salvamento Automático)

### Funcionalidades Implementadas
**Arquivo:** `templates/parcerias_form.html`

#### Mecânica de Salvamento
1. **Salvamento por tempo:** Após 60 segundos de inatividade ao digitar
2. **Salvamento por evento:** Ao sair de um campo (blur event), se passou mais de 5 segundos
3. **Salvamento periódico:** A cada 2 minutos automaticamente
4. **Armazenamento:** LocalStorage do navegador (não vai para o banco de dados)

#### Fluxo de Uso
1. Usuário preenche formulário
2. Sistema salva automaticamente no navegador
3. Se o usuário sair da página ou fechar o navegador
4. Ao retornar, sistema pergunta: "Dados não salvos foram encontrados. Deseja restaurá-los?"
5. Se confirmar, todos os campos são restaurados

#### Indicadores Visuais
- **Indicador de salvamento:** Aparece no canto inferior direito
- **Badge verde:** "✓ Salvo automaticamente" por 2 segundos
- **Mensagem de restauração:** Alert azul no topo do formulário com timestamp

#### Limpeza Automática
- Ao submeter o formulário (salvar), o autosave é limpo do localStorage
- Evita restauração após salvamento bem-sucedido

### Código JavaScript Implementado
```javascript
// Principais funções:
- autosaveForm() - Salva todos os campos no localStorage
- showSaveIndicator() - Mostra indicador visual
- Event listeners em todos inputs para detectar mudanças
- DOMContentLoaded para restaurar dados ao carregar
- Submit handler para limpar autosave
- setInterval para backup periódico
```

---

## 4. Melhorias Adicionais

### Consistência de UX
- Todos os filtros mantêm valores após aplicação
- Paginação preserva filtros aplicados
- Dropdowns melhoram UX ao evitar erros de digitação

### Performance
- Queries otimizadas com LIMIT
- LocalStorage é rápido e não sobrecarrega servidor
- Autosave inteligente (não salva a cada tecla)

### Segurança
- Dados de autosave ficam apenas no navegador do usuário
- Não há risco de dados parciais no banco
- Validação mantida no servidor

---

## Testes Recomendados

### Paginação
1. Acessar `/parcerias/` e `/orcamento/`
2. Mudar "Mostrar somente" para cada opção
3. Aplicar filtros e mudar paginação (verificar que filtros permanecem)
4. Testar com "Todas" para ver lista completa

### Dropdowns
1. Acessar filtro de parcerias e testar dropdown "Tipo de Termo"
2. Criar nova parceria e verificar dropdowns de "Tipo de Termo" e "Portaria"
3. Editar parceria existente e verificar que valores corretos estão selecionados

### Autosave
1. Abrir formulário de nova parceria
2. Preencher alguns campos
3. Esperar 60 segundos ou sair de um campo
4. Verificar mensagem "Salvo automaticamente"
5. Fechar navegador e reabrir
6. Verificar prompt de restauração
7. Confirmar e verificar que dados foram restaurados
8. Submeter formulário e verificar que autosave foi limpo

---

## Estrutura de Arquivos Modificados

```
FAF/
├── routes/
│   ├── parcerias.py        [MODIFICADO - queries, parâmetros, dropdowns]
│   └── orcamento.py         [MODIFICADO - paginação]
├── templates/
│   ├── parcerias.html       [MODIFICADO - dropdown filtro, paginação]
│   ├── parcerias_form.html  [MODIFICADO - dropdowns, autosave]
│   └── orcamento_1.html     [MODIFICADO - paginação, JS]
└── testes/
    └── check_tables.py      [CRIADO - script para verificar estrutura BD]
```

---

## Dependências

### Banco de Dados
- Tabelas `c_tipo_contrato` e `c_legislacao` devem existir e estar populadas
- Queries SELECT para buscar opções dos dropdowns

### Frontend
- Bootstrap 5.3.0 (já utilizado)
- Bootstrap Icons (já utilizado)
- JavaScript nativo (sem bibliotecas adicionais)

### Backend
- Flask (já instalado)
- psycopg2 (já instalado)
- RealDictCursor para queries

---

## Configurações

### Valores Padrão
- Paginação padrão: **100 linhas**
- Intervalo de autosave: **60 segundos após última edição**
- Backup automático: **A cada 2 minutos**
- Delay mínimo entre saves: **5 segundos**

### Personalização Fácil
Todos os valores podem ser ajustados nos templates:
- Opções de paginação: modificar `<select id="limite">` em `parcerias.html` e `orcamento_1.html`
- Intervalos de autosave: modificar `setTimeout()` e `setInterval()` em `parcerias_form.html`

---

## Notas Técnicas

### Armazenamento LocalStorage
- **Chave:** `parceriaForm_{numero_termo}` ou `parceriaForm_nova`
- **Formato:** JSON com todos os campos do formulário + timestamp
- **Limite:** ~5-10MB por domínio (mais que suficiente)

### SQL LIMIT
```sql
-- Exemplo de query com LIMIT dinâmico
SELECT * FROM Parcerias 
WHERE ... 
ORDER BY numero_termo
LIMIT {limite_sql}  -- None = sem limite
```

### Preservação de Estado
- URL parameters mantidos ao mudar paginação
- Formulário mantém valores em todos os dropdowns
- Autosave restaura estado completo do formulário

---

## Suporte e Manutenção

### Adicionar Nova Opção de Paginação
1. Editar templates `parcerias.html` e `orcamento_1.html`
2. Adicionar nova `<option value="X">X linhas</option>`

### Adicionar Novo Dropdown
1. Criar tabela categórica no banco com estrutura similar a `c_tipo_contrato`
2. Adicionar query no route correspondente
3. Passar lista para template
4. Criar `<select>` no template HTML

### Modificar Intervalo de Autosave
1. Editar `templates/parcerias_form.html`
2. Modificar linha: `autosaveTimeout = setTimeout(autosaveForm, 60000);`
3. Valor em milissegundos (60000 = 1 minuto)

---

## Conclusão

Todas as funcionalidades solicitadas foram implementadas com sucesso:
- ✅ Paginação com persistência de filtros
- ✅ Dropdowns categóricos em filtros e formulários
- ✅ Autosave inteligente com localStorage
- ✅ UX melhorada com indicadores visuais
- ✅ Performance otimizada

O sistema está pronto para uso e testes!
