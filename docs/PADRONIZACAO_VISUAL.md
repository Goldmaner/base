# Padronização Visual — FAF

> Referência de CSS e HTML para manter consistência visual em todas as páginas do sistema.  
> Última revisão: Março 2026

---

## 1. Sistema de Cores

Cada módulo tem um gradiente próprio. Use-o no cabeçalho (`page-header`), no cabeçalho de tabelas e nos botões principais.

| Módulo / Seção            | Gradiente (`from → to`)            | Classe sugerida  |
|---------------------------|------------------------------------|------------------|
| Geral / Home              | `#1e3a5f → #2563eb`                | `.s-geral`       |
| Parcerias                 | `#4c1d95 → #7c3aed`                | `.s-parc`        |
| Análise / DAC             | `#065f46 → #059669`                | `.s-analise`     |
| Dados / Orçamento         | `#78350f → #d97706`                | `.s-dados`       |
| Pessoas / DGP             | `#312e81 → #4f46e5`                | `.s-pessoas`     |
| Admin / Configurações     | `#7f1d1d → #dc2626`                | `.s-admin`       |
| Listas Suspensas          | `#4c1d95 → #7c3aed`                | `.s-listas`      |

**Exemplo de uso em CSS:**
```css
.page-header {
  background: linear-gradient(135deg, #4c1d95 0%, #7c3aed 100%);
  color: #fff;
  padding: 22px 28px;
  border-radius: 12px;
  margin-bottom: 20px;
  box-shadow: 0 4px 18px rgba(124, 58, 237, .28);
}
.page-header h2 { margin: 0; font-size: 1.5rem; font-weight: 700; }
.page-header p  { margin: 4px 0 0; opacity: .85; font-size: .9rem; }
```

---

## 2. Estrutura de Cabeçalho de Página

Use sempre o padrão abaixo. O botão "Voltar" fica à direita com variante `outline`.

```html
<div class="page-header">
  <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
    <div>
      <h2><i class="bi bi-ICONE me-2"></i>Título da Página</h2>
      <p>Subtítulo descritivo breve</p>
    </div>
    <div class="d-flex gap-2 flex-wrap">
      <!-- Botões de ação adicionais -->
      <a href="{{ url_for('main.index') }}" class="btn-parc outline">
        <i class="bi bi-arrow-left"></i> Voltar
      </a>
    </div>
  </div>
</div>
```

---

## 3. Botões Padrão (`.btn-parc`)

Substitui os botões Bootstrap padrão nas páginas com o novo design.

```css
.btn-parc {
  background: linear-gradient(135deg, #4c1d95, #7c3aed);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 7px 16px;
  font-weight: 600;
  transition: opacity .15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-decoration: none;
  cursor: pointer;
  font-size: .875rem;
}
.btn-parc:hover { opacity: .88; color: #fff; }

/* Variante outline (fundo transparente, para usar sobre gradientes) */
.btn-parc.outline {
  background: transparent;
  border: 1.5px solid rgba(255, 255, 255, .7);
  color: #fff;
}
.btn-parc.outline:hover { background: rgba(255, 255, 255, .15); opacity: 1; }
```

**Variantes de cor** (troque o `background`):

| Variante  | Gradiente                          | Uso                        |
|-----------|------------------------------------|----------------------------|
| Principal | `#4c1d95 → #7c3aed`               | Ação primária              |
| Sucesso   | `#065f46 → #059669`               | Salvar / Confirmar         |
| Aviso     | `#b45309 → #d97706`               | Limpar / Atenção           |
| Perigo    | `#7f1d1d → #dc2626`               | Excluir / Ação destrutiva  |

```html
<!-- Exemplos -->
<button class="btn-parc"><i class="bi bi-plus-circle"></i> Adicionar</button>
<button class="btn-parc" style="background:linear-gradient(135deg,#065f46,#059669);">
  <i class="bi bi-check-all"></i> Salvar Todos
</button>
<button class="btn-parc" style="background:linear-gradient(135deg,#b45309,#d97706);">
  <i class="bi bi-x-circle"></i> Limpar Filtros
</button>
<button class="btn-parc" style="background:linear-gradient(135deg,#7f1d1d,#dc2626);">
  <i class="bi bi-trash"></i> Excluir
</button>
```

---

## 4. Secção de Filtros / Painéis Secundários

```css
.filter-section {
  background: #fff;
  padding: 20px;
  border-radius: 10px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, .07);
  border-left: 4px solid #7c3aed; /* use a cor do módulo */
}
```

```html
<div class="filter-section">
  <h6 class="mb-3">
    <i class="bi bi-funnel me-1" style="color:#7c3aed;"></i>Filtros
  </h6>
  <!-- conteúdo -->
</div>
```

---

## 5. Cards de Conteúdo com Tabela

```css
.content-card {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, .07);
  overflow: hidden;
}
.content-card-header {
  background: linear-gradient(135deg, #4c1d95, #7c3aed); /* cor do módulo */
  color: #fff;
  padding: 14px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.content-card-header h5 { margin: 0; font-weight: 700; font-size: 1rem; }
.content-card-body { padding: 16px; }
```

**Cabeçalho de tabela:**
```css
/* Aplique ao seletor da tabela específica */
#minhaTabela thead tr th {
  background: linear-gradient(135deg, #4c1d95, #7c3aed);
  color: #fff;
  border: none;
  white-space: nowrap;
}
#minhaTabela tbody tr:hover { background-color: #f5f0ff; }
```

---

## 6. Cabeçalho de Modal

```css
.modal .modal-header {
  background: linear-gradient(135deg, #4c1d95, #7c3aed);
  color: #fff;
}
.modal .modal-header .btn-close { filter: invert(1); }
```

---

## 7. Background da Página

```css
body {
  background-color: #f4f3f8; /* levemente roxo/neutro para páginas com módulo Parcerias/Listas */
  padding: 20px;
}
/* Para outros módulos, use tons neutros adequados: */
/* Análise: #f0fdf4 */
/* Geral: #f0f4ff */
/* Pessoas: #f5f3ff */
```

---

## 8. Seletores Tipáveis com Datalist

Para filtros e seletores que devem ser tanto digitáveis quanto clicáveis, use `<input list="...">` com `<datalist>`.

```html
<div class="selector-input-wrapper" style="position:relative;">
  <i class="bi bi-search" style="position:absolute;left:12px;top:50%;transform:translateY(-50%);color:#7c3aed;pointer-events:none;"></i>
  <input type="text" id="meuInput" list="minha-datalist"
         class="form-control"
         style="padding-left:36px; border-color:#d8b4fe;"
         placeholder="Digite para filtrar..."
         autocomplete="off">
</div>
<datalist id="minha-datalist">
  <option value="Opção A"></option>
  <option value="Opção B"></option>
</datalist>
```

**Com localStorage** (persistir seleção entre visitas):
```javascript
// Salvar
localStorage.setItem('minha_chave', valor);

// Restaurar no DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  const salvo = localStorage.getItem('minha_chave');
  if (salvo) {
    document.getElementById('meuInput').value = salvo;
    // acionar ação correspondente
  }
});
```

---

## 9. Body base e imports

Sempre usar Bootstrap 5.3.0 e Bootstrap Icons 1.10.x:

```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nome da Página - FAF</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
  <style>
    body { background-color: #f4f3f8; padding: 20px; }
    /* ... estilos da página ... */
  </style>
</head>
...
<!-- Antes de </body> -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
```

---

## 10. Páginas já padronizadas (referência)

| Arquivo                                    | Módulo      | Cor principal       |
|--------------------------------------------|-------------|---------------------|
| `templates/tela_inicial.html`              | Home        | `#1e3a5f → #2563eb` |
| `templates/login.html`                     | Login       | `#4c1d95 → #7c3aed` |
| `templates/parcerias/parcerias.html`       | Parcerias   | `#4c1d95 → #7c3aed` |
| `templates/parcerias/parcerias_form.html`  | Parcerias   | `#4c1d95 → #7c3aed` |
| `templates/parcerias/parcerias_osc_dict.html` | Parcerias | `#4c1d95 → #7c3aed` |
| `templates/listas.html`                    | Listas      | `#4c1d95 → #7c3aed` |
