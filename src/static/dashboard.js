/**
 * Lógica do Dashboard Planax
 * Separada do HTML para evitar conflitos de sintaxe no editor
 */

document.addEventListener('DOMContentLoaded', () => {
    const escolaId = document.body.dataset.escolaId;

    const syncCargaRows = (form) => {
        const disciplinas = new Set(
            Array.from(form.querySelectorAll('input[name="disciplina_ids"]:checked')).map(cb => cb.value)
        );
        const turmas = new Set(
            Array.from(form.querySelectorAll('input[name="turma_ids"]:checked')).map(cb => cb.value)
        );

        form.querySelectorAll('.carga-row').forEach(row => {
            const visible = disciplinas.has(row.dataset.disciplinaId) && turmas.has(row.dataset.turmaId);
            row.hidden = !visible;
            const input = row.querySelector('.carga-input');
            if (input) {
                input.disabled = !visible;
                if (!visible) input.value = 0;
            }
        });
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
        });
        form.addEventListener('submit', () => {
            syncChecksFromCargas(form);
            syncCargaRows(form);
        });
        syncCargaRows(form);
    });

    // Gerenciamento de Modais de Edição via Event Delegation
    document.addEventListener('click', (e) => {
        // Editar Disciplina
        if (e.target.closest('.btn-edit-disc')) {
            const btn = e.target.closest('.btn-edit-disc');
            const { id, nome, cor } = btn.dataset;

            document.getElementById('edit-disc-nome').value = nome;
            const corInput = document.getElementById('cor-disciplina-edit');
            corInput.value = cor || '';
            corInput.dispatchEvent(new Event('input', { bubbles: true }));
            document.getElementById('form-disc-edit').action = `/escola/${escolaId}/disciplina/${id}/editar`;
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

            document.getElementById('form-prof-edit').action = `/escola/${escolaId}/professor/${id}/editar`;
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
            document.getElementById('form-turma-edit').action = `/escola/${escolaId}/turma/${id}/editar`;
            openModal('modal-turma-edit');
        }
    });
});
