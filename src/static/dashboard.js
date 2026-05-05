/**
 * Lógica do Dashboard Flowter
 * Separada do HTML para evitar conflitos de sintaxe no editor
 */

document.addEventListener('DOMContentLoaded', () => {
    const escolaId = document.body.dataset.escolaId;
    const turno = document.body.dataset.turno || 'matutino';
    const turnoQuery = `?turno=${encodeURIComponent(turno)}`;

    const syncCargaRows = (form) => {
        const disciplinas = new Set(
            Array.from(form.querySelectorAll('input[name="disciplina_ids"]:checked')).map(cb => cb.value)
        );
        const turmas = new Set(
            Array.from(form.querySelectorAll('input[name="turma_ids"]:checked')).map(cb => cb.value)
        );
        const hasZeroToggle = Boolean(form.querySelector('[data-carga-zero-toggle]'));
        const showZeroCargas = !hasZeroToggle || form.dataset.showZeroCargas === 'true';
        let visibleRows = 0;
        let eligibleZeroRows = 0;
        let totalAulas = 0;

        form.querySelectorAll('.carga-row').forEach(row => {
            const selected = disciplinas.has(row.dataset.disciplinaId) && turmas.has(row.dataset.turmaId);
            const input = row.querySelector('.carga-input');
            const cargaValue = parseInt(input?.value || '0', 10);
            const hasCarga = cargaValue > 0;
            const isEditing = input && document.activeElement === input;
            const visible = selected && (showZeroCargas || hasCarga || isEditing);
            row.hidden = !visible;
            if (visible) visibleRows += 1;
            if (selected && !hasCarga) eligibleZeroRows += 1;
            if (selected && cargaValue > 0) totalAulas += cargaValue;
            if (input) {
                input.disabled = !selected;
                if (!selected) input.value = 0;
            }
        });

        const totalLabel = form.querySelector('[data-carga-total]');
        if (totalLabel) {
            totalLabel.textContent = `${totalAulas} ${totalAulas === 1 ? 'aula/sem' : 'aulas/sem'}`;
        }

        const toggle = form.querySelector('[data-carga-zero-toggle]');
        if (toggle) {
            toggle.textContent = showZeroCargas ? 'Ocultar zeradas' : 'Mostrar zeradas';
            toggle.setAttribute('aria-pressed', showZeroCargas ? 'true' : 'false');
            toggle.disabled = !showZeroCargas && eligibleZeroRows === 0;
        }

        const emptyState = form.querySelector('[data-carga-empty]');
        if (emptyState) {
            emptyState.hidden = visibleRows > 0;
        }
    };

    const syncChecksFromCargas = (form) => {
        const turmas = new Set();
        const disciplinas = new Set();

        form.querySelectorAll('.carga-input').forEach(input => {
            if (parseInt(input.value || '0', 10) > 0) {
                turmas.add(input.dataset.turmaId);
                disciplinas.add(input.dataset.disciplinaId);
            }
        });

        form.querySelectorAll('input[name="turma_ids"]').forEach(cb => {
            cb.checked = cb.checked || turmas.has(cb.value);
        });
        form.querySelectorAll('input[name="disciplina_ids"]').forEach(cb => {
            cb.checked = cb.checked || disciplinas.has(cb.value);
        });
    };

    document.querySelectorAll('#modal-prof form, #modal-prof-edit form').forEach(form => {
        form.addEventListener('change', (event) => {
            if (event.target.matches('input[name="disciplina_ids"], input[name="turma_ids"]')) {
                syncCargaRows(form);
            }
            if (event.target.matches('.carga-input')) {
                syncCargaRows(form);
            }
        });
        form.addEventListener('input', (event) => {
            if (event.target.matches('.carga-input')) {
                syncCargaRows(form);
            }
        });
        form.addEventListener('submit', () => {
            syncChecksFromCargas(form);
            syncCargaRows(form);
        });
        syncCargaRows(form);
    });

    // Gerenciamento de Modais de Edição via Event Delegation
    document.addEventListener('click', (e) => {
        const scrollTopButton = e.target.closest('.mobile-modal-scroll-top');
        if (scrollTopButton) {
            const modal = scrollTopButton.closest('.modal-professor');
            const scrollArea = modal?.querySelector('.professor-main-grid');
            if (scrollArea) {
                scrollArea.scrollTo({ top: 0, behavior: 'smooth' });
            }
            return;
        }

        const zeroToggle = e.target.closest('[data-carga-zero-toggle]');
        if (zeroToggle) {
            const form = zeroToggle.closest('form');
            if (form) {
                form.dataset.showZeroCargas = form.dataset.showZeroCargas === 'true' ? 'false' : 'true';
                syncCargaRows(form);
            }
            return;
        }

        // Editar Disciplina
        if (e.target.closest('.btn-edit-disc')) {
            const btn = e.target.closest('.btn-edit-disc');
            const { id, nome, cor } = btn.dataset;

            document.getElementById('edit-disc-nome').value = nome;
            const corInput = document.getElementById('cor-disciplina-edit');
            corInput.value = cor || '';
            corInput.dispatchEvent(new Event('input', { bubbles: true }));
            document.getElementById('form-disc-edit').action = `/escola/${escolaId}/disciplina/${id}/editar${turnoQuery}`;
            openModal('modal-disc-edit');
        }

        // Editar Professor
        if (e.target.closest('.btn-edit-prof')) {
            const btn = e.target.closest('.btn-edit-prof');
            const { id, nome, cor, disciplinaIds, dias, turmas, cargas } = btn.dataset;
            const disciplinaIdsLista = JSON.parse(disciplinaIds || '[]').map(String);
            const diasLista = JSON.parse(dias || '[]');
            const turmaIds = JSON.parse(turmas || '[]').map(String);
            const cargasMapa = JSON.parse(cargas || '{}');
            const form = document.getElementById('form-prof-edit');

            document.getElementById('edit-prof-nome').value = nome;
            const corInput = document.getElementById('cor-professor-edit');
            if (corInput) {
                corInput.value = cor || '';
                corInput.dispatchEvent(new Event('input', { bubbles: true }));
            }

            document.querySelectorAll('.edit-disciplina-check').forEach(cb => {
                cb.checked = disciplinaIdsLista.includes(cb.value);
            });

            document.querySelectorAll('.edit-dia-check').forEach(cb => {
                cb.checked = diasLista.includes(cb.value);
            });

            document.querySelectorAll('.edit-turma-check').forEach(cb => {
                cb.checked = turmaIds.includes(cb.value);
            });

            document.querySelectorAll('.edit-carga-input').forEach(input => {
                input.value = cargasMapa[`${input.dataset.turmaId}:${input.dataset.disciplinaId}`] || 0;
            });

            document.getElementById('form-prof-edit').action = `/escola/${escolaId}/professor/${id}/editar${turnoQuery}`;
            form.dataset.showZeroCargas = 'false';
            syncCargaRows(form);
            openModal('modal-prof-edit');
        }

        // Editar Turma
        if (e.target.closest('.btn-edit-turma')) {
            const btn = e.target.closest('.btn-edit-turma');
            const { id, nome, aulasPorDia } = btn.dataset;

            document.getElementById('edit-turma-nome').value = nome;
            document.querySelectorAll('.edit-turma-aulas-dia').forEach(input => {
                input.checked = input.value === (aulasPorDia || '5');
            });
            document.getElementById('form-turma-edit').action = `/escola/${escolaId}/turma/${id}/editar${turnoQuery}`;
            openModal('modal-turma-edit');
        }
    });
});
