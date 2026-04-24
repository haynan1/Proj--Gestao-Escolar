/**
 * Lógica do Dashboard Planax
 * Separada do HTML para evitar conflitos de sintaxe no editor
 */

document.addEventListener('DOMContentLoaded', () => {
    const escolaId = document.body.dataset.escolaId;

    // Gerenciamento de Modais de Edição via Event Delegation
    document.addEventListener('click', (e) => {
        // Editar Disciplina
        if (e.target.closest('.btn-edit-disc')) {
            const btn = e.target.closest('.btn-edit-disc');
            const { id, nome, cor } = btn.dataset;

            document.getElementById('edit-disc-nome').value = nome;
            document.getElementById('cor-disciplina-edit').value = cor;
            document.getElementById('form-disc-edit').action = `/escola/${escolaId}/disciplina/${id}/editar`;
            openModal('modal-disc-edit');
        }

        // Editar Professor
        if (e.target.closest('.btn-edit-prof')) {
            const btn = e.target.closest('.btn-edit-prof');
            const { id, nome, discId, max, dias, turmas } = btn.dataset;
            const diasLista = JSON.parse(dias || '[]');
            const turmaIds = JSON.parse(turmas || '[]').map(String);

            document.getElementById('edit-prof-nome').value = nome;
            document.getElementById('edit-prof-disc').value = discId;
            document.getElementById('edit-prof-max').value = max;

            document.querySelectorAll('.edit-dia-check').forEach(cb => {
                cb.checked = diasLista.includes(cb.value);
            });

            document.querySelectorAll('.edit-turma-check').forEach(cb => {
                cb.checked = turmaIds.includes(cb.value);
            });

            document.getElementById('form-prof-edit').action = `/escola/${escolaId}/professor/${id}/editar`;
            openModal('modal-prof-edit');
        }

        // Editar Turma
        if (e.target.closest('.btn-edit-turma')) {
            const btn = e.target.closest('.btn-edit-turma');
            const { id, nome } = btn.dataset;

            document.getElementById('edit-turma-nome').value = nome;
            document.getElementById('form-turma-edit').action = `/escola/${escolaId}/turma/${id}/editar`;
            openModal('modal-turma-edit');
        }
    });
});
