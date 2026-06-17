/* Central de Páginas — FParcerias (tree view) */

document.addEventListener('DOMContentLoaded', function () {

    // ── Inicializar popovers ──────────────────────────────────────────
    document.querySelectorAll('[data-bs-toggle="popover"]').forEach(function (el) {
        new bootstrap.Popover(el, { trigger: 'hover focus', placement: 'top', html: false });
    });

    // ── Expand / Collapse ─────────────────────────────────────────────
    document.querySelectorAll('.cp-page-row.cp-has-children').forEach(function (row) {
        row.addEventListener('click', function (e) {
            // Não colapsar quando clicar num botão/link interno
            if (e.target.closest('button, a, input')) return;
            toggleNode(this);
        });
    });

    function toggleNode(row) {
        var wrap = row.closest('.cp-node').querySelector('.cp-children-wrap');
        if (!wrap) return;

        var expanded = row.classList.contains('cp-expanded');
        if (expanded) {
            row.classList.remove('cp-expanded');
            wrap.style.display = 'none';
        } else {
            row.classList.add('cp-expanded');
            wrap.style.display = 'block';
        }
    }

    // ── Busca em tempo real ───────────────────────────────────────────
    var input      = document.getElementById('cp-busca');
    var noResults  = document.getElementById('cp-no-results');
    var termSpan   = document.getElementById('cp-term');
    var clearBtn   = document.getElementById('cp-clear');

    if (!input) return;

    input.addEventListener('input', function () {
        buscar(this.value.trim().toLowerCase());
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            input.value = '';
            buscar('');
            input.focus();
        });
    }

    function buscar(termo) {
        var areas        = document.querySelectorAll('.cp-area');
        var totalVis     = 0;

        areas.forEach(function (areaEl) {
            var nodes         = areaEl.querySelectorAll('.cp-node');
            var areaVisiveis  = 0;

            nodes.forEach(function (nodeEl) {
                /* Verificar se o próprio nó ou algum filho corresponde */
                var parentMatch = nodeMatches(nodeEl, termo);
                var children    = nodeEl.querySelectorAll('.cp-child-node');
                var childMatches = [];

                children.forEach(function (child) {
                    var m = nodeMatches(child, termo);
                    child.classList.toggle('cp-hidden', !!termo && !m);
                    child.classList.toggle('cp-match', !!termo && m);
                    if (m) childMatches.push(child);
                });

                var anyChildMatch = childMatches.length > 0;
                var visible       = !termo || parentMatch || anyChildMatch;

                nodeEl.classList.toggle('cp-hidden', !visible);
                nodeEl.classList.toggle('cp-match', !!termo && parentMatch && !anyChildMatch);

                /* Auto-expandir se algum filho bate */
                var row  = nodeEl.querySelector('.cp-page-row.cp-has-children');
                var wrap = nodeEl.querySelector('.cp-children-wrap');
                if (row && wrap) {
                    if (termo && anyChildMatch) {
                        row.classList.add('cp-expanded');
                        wrap.style.display = 'block';
                    } else if (!termo) {
                        row.classList.remove('cp-expanded');
                        wrap.style.display = 'none';
                    }
                }

                if (visible) areaVisiveis++;
            });

            areaEl.style.display = areaVisiveis > 0 ? '' : 'none';
            totalVis += areaVisiveis;
        });

        /* Exibir "sem resultados" */
        if (noResults) {
            if (totalVis === 0 && termo) {
                if (termSpan) termSpan.textContent = termo;
                noResults.style.display = 'block';
            } else {
                noResults.style.display = 'none';
            }
        }
    }

    function nodeMatches(el, termo) {
        if (!termo) return true;
        return (
            (el.dataset.nome        || '').includes(termo) ||
            (el.dataset.area        || '').includes(termo) ||
            (el.dataset.descricao   || '').includes(termo) ||
            (el.dataset.responsavel || '').includes(termo)
        );
    }

    // ── Editar Responsável (admin only) ──────────────────────────────
    var modalEl     = document.getElementById('modalEditResp');
    var inputId     = document.getElementById('editRespId');
    var inputValor  = document.getElementById('editRespValor');
    var btnSalvar   = document.getElementById('editRespSalvar');

    if (!modalEl) return; // não é admin, nada a fazer

    var modal = new bootstrap.Modal(modalEl);

    /* Abrir modal ao clicar no lápis */
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.cp-edit-resp-btn');
        if (!btn) return;
        e.stopPropagation();
        inputId.value    = btn.dataset.id    || '';
        inputValor.value = btn.dataset.valor || '';
        modal.show();
        setTimeout(function () { inputValor.focus(); inputValor.select(); }, 300);
    });

    /* Salvar ao pressionar Enter no input */
    inputValor.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') salvarResponsavel();
    });

    /* Botão Salvar */
    btnSalvar.addEventListener('click', salvarResponsavel);

    function salvarResponsavel() {
        var id    = parseInt(inputId.value, 10);
        var valor = inputValor.value.trim();
        if (!id) return;

        btnSalvar.disabled = true;
        btnSalvar.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Salvando…';

        fetch('/central-paginas/api/pagina/' + id, {
            method:  'PUT',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ responsavel: valor })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.ok) {
                /* Atualizar todos os spans de display para este id */
                document.querySelectorAll('.cp-resp-display[data-id="' + id + '"]').forEach(function (span) {
                    span.textContent = valor || '—';
                });
                /* Atualizar data-valor dos lápis com este id */
                document.querySelectorAll('.cp-edit-resp-btn[data-id="' + id + '"]').forEach(function (btn) {
                    btn.dataset.valor = valor;
                });
                modal.hide();
            } else {
                alert('Erro ao salvar: ' + (data.erro || 'desconhecido'));
            }
        })
        .catch(function () {
            alert('Erro de comunicação ao salvar.');
        })
        .finally(function () {
            btnSalvar.disabled = false;
            btnSalvar.innerHTML = '<i class="bi bi-check-lg me-1"></i>Salvar';
        });
    }

});
