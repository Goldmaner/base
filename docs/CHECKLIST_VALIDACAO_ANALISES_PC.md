# ✅ Checklist de Validação - Módulo Analises PC

Use este checklist para validar a implementação do módulo.

## 🔧 Infraestrutura

- [x] Tabelas criadas no schema `analises_pc`
  - [x] `checklist_termo`
  - [x] `checklist_analista`
  - [x] `checklist_recursos`
- [x] Índices de performance criados (11 índices)
- [x] Constraint UNIQUE configurada
- [x] Dependências externas existem
  - [x] `public.parcerias.numero_termo`
  - [x] `categoricas.c_analistas.nome_analista`

## 📁 Arquivos

- [x] Routes criadas
  - [x] `routes/analises_pc/__init__.py`
  - [x] `routes/analises_pc/routes.py`
- [x] Templates criados
  - [x] `templates/analises_pc/index.html`
- [x] Scripts utilitários
  - [x] `scripts/criar_indices_analises_pc.sql`
  - [x] `scripts/criar_indices_analises_pc.py`
  - [x] `scripts/inicializar_analises_pc.py`
- [x] Testes
  - [x] `testes/test_analises_pc_api.py`
- [x] Documentação
  - [x] `docs/MODULO_ANALISES_PC.md`
  - [x] `docs/SUMARIO_ANALISES_PC.md`
  - [x] `docs/README_ANALISES_PC.md`
  - [x] `docs/GUIA_RAPIDO_ANALISES_PC.md`

## 🔗 Integrações

- [x] Blueprint registrado em `app.py`
- [x] Botão atualizado em `templates/instrucoes.html` (linha 44)
- [x] Imports corretos (usando `get_db()` ao invés de `get_db_connection()`)

## 🖥️ Interface (Frontend)

### Página Inicial

- [ ] **Botão "Voltar"** funciona?
- [ ] **Dropdown "Número do Termo"** carrega dados?
- [ ] **Campo "Meses em Análise"** aceita texto?
- [ ] **Multi-select "Analistas"** funciona?
  - [ ] Permite múltiplas seleções?
  - [ ] Busca funciona? (Select2)
- [ ] **Botão "Prosseguir"** abre o checklist?
- [ ] **Validação** impede prosseguir sem preencher campos?

### Área do Checklist

- [ ] **Informações** aparecem no topo (Termo, Meses, Analistas)?
- [ ] **12 checkboxes** principais aparecem?
- [ ] **Marcação cascata** funciona?
  - [ ] Marcar checkbox 5 marca 1-4 automaticamente?
  - [ ] Marcar checkbox 12 marca todas?
- [ ] **Feedback visual** funciona?
  - [ ] Checkbox marcada fica verde?
  - [ ] Hover funciona?
- [ ] **Botão "Incluir Fase Recursal"** adiciona recurso?
  - [ ] Mostra 3 checkboxes do recurso?
  - [ ] Numeração correta (Recurso 1, 2, 3...)?
- [ ] **Botão "Remover"** exclui recurso?
  - [ ] Pede confirmação?
- [ ] **Botão "Salvar Avanços"** salva dados?
  - [ ] Mostra mensagem de sucesso?
- [ ] **Botão "Voltar para Configuração"** funciona?
  - [ ] Pede confirmação?

## 🔌 APIs (Backend)

### GET /analises_pc/

- [ ] Página carrega sem erros?
- [ ] Dropdowns populados?

### POST /analises_pc/api/carregar_checklist

- [ ] **Checklist vazio** retorna `null`?
- [ ] **Checklist existente** retorna dados corretos?
- [ ] **Analistas** retornam em array?
- [ ] **Recursos** retornam ordenados por `tipo_recurso`?
- [ ] **Erro** retorna status 400/500 apropriado?

### POST /analises_pc/api/salvar_checklist

- [ ] **Insert** funciona (primeira vez)?
- [ ] **Update** funciona (salvar novamente)?
- [ ] **Analistas** salvam corretamente?
  - [ ] Múltiplos analistas?
  - [ ] Deletar + reinserir funciona?
- [ ] **Recursos** salvam corretamente?
  - [ ] Múltiplos recursos?
  - [ ] Numeração correta?
- [ ] **Transação** faz rollback em caso de erro?
- [ ] **Mensagem de sucesso** retorna?

## 🗄️ Banco de Dados

### Integridade

- [ ] **Chave composta** funciona?
  - [ ] Não permite duplicatas (termo + meses)?
- [ ] **Analistas múltiplos** salvam?
  - [ ] Múltiplas linhas para mesmo termo/meses?
- [ ] **Recursos múltiplos** salvam?
  - [ ] `tipo_recurso` incrementa corretamente?

### Performance

- [ ] **Consultas rápidas** com índices?
  - [ ] SELECT por termo + meses < 50ms?
- [ ] **Insert/Update rápidos** < 100ms?

## 🧪 Testes Automatizados

- [ ] Testes executam sem erros?
  ```bash
  python testes/test_analises_pc_api.py
  ```
- [ ] Todos os 5 testes passam?

## 🎯 Fluxo Completo (Teste Manual)

### Cenário 1: Nova Análise

1. [ ] Acesse `/analises_pc/`
2. [ ] Selecione um termo (ex: "123/2024")
3. [ ] Digite meses (ex: "01/2024")
4. [ ] Selecione 2 analistas
5. [ ] Clique "Prosseguir"
6. [ ] Marque 5 etapas
7. [ ] Adicione 1 recurso e marque 2 checkboxes
8. [ ] Clique "Salvar Avanços"
9. [ ] Verifique mensagem de sucesso

### Cenário 2: Continuar Análise

1. [ ] Volte para configuração
2. [ ] Selecione mesmo termo e meses do Cenário 1
3. [ ] Clique "Prosseguir"
4. [ ] Verifique que as 5 etapas estão marcadas
5. [ ] Verifique que 1 recurso aparece
6. [ ] Marque mais 3 etapas
7. [ ] Adicione 1 segundo recurso
8. [ ] Clique "Salvar Avanços"
9. [ ] Verifique mensagem de sucesso

### Cenário 3: Marcação Cascata

1. [ ] Inicie nova análise (termo diferente)
2. [ ] Marque apenas a etapa 12 (última)
3. [ ] Verifique que etapas 1-11 foram marcadas automaticamente
4. [ ] Salve e carregue novamente
5. [ ] Verifique que todas estão marcadas

## 📱 Responsividade

- [ ] **Mobile** (< 768px)
  - [ ] Layout se adapta?
  - [ ] Botões acessíveis?
  - [ ] Dropdowns funcionam?
- [ ] **Tablet** (768-1024px)
  - [ ] Layout OK?
- [ ] **Desktop** (> 1024px)
  - [ ] Layout ideal?

## 🔒 Segurança

- [ ] **SQL Injection** protegido?
  - [ ] Prepared statements usados?
- [ ] **XSS** protegido?
  - [ ] Inputs escapados no template?
- [ ] **CSRF** não aplicável (API JSON)
- [ ] **Validação** frontend + backend?

## 📊 Logs e Monitoramento

- [ ] **Erros** logam no console do servidor?
- [ ] **Queries SQL** podem ser debugadas?
- [ ] **Performance** pode ser medida?

## 📚 Documentação

- [ ] **README** completo e claro?
- [ ] **GUIA_RAPIDO** útil para iniciantes?
- [ ] **Comentários no código** suficientes?
- [ ] **Docstrings** em funções Python?

---

## 🎉 Validação Final

**Todos os checkboxes marcados?**

✅ **SIM** → Módulo pronto para produção!  
❌ **NÃO** → Revise itens pendentes acima

---

## 📝 Notas de Validação

Use este espaço para anotar problemas encontrados:

```
Data: ___/___/______
Validador: ________________

Problemas encontrados:
- 
- 
- 

Ações tomadas:
- 
- 
- 
```

---

*Checklist criado em: 07/11/2024*  
*Versão: 1.0*
