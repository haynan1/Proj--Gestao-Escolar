/**
 * dragdrop.js — Drag and Drop para a grade de horários com verificação de conflitos em tempo real
 */

let draggedCard = null;
let draggedAulaId = null;
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

async function destacarConflitos(profId) {
    if (!profId) return;

    try {
        const escolaId = document.body.dataset.escolaId;
        const resp = await fetch(`/escola/${escolaId}/professor/${profId}/ocupacao`);
        const ocupacao = await resp.json();

        // Limpa destaques anteriores
        document.querySelectorAll('.grade-cell').forEach(c => {
            c.classList.remove('conflict-busy');
            const label = c.querySelector('.conflict-label');
            if (label) label.remove();
        });

        // Aplica novos destaques
        ocupacao.forEach(slot => {
            const cell = document.querySelector(`.grade-cell[data-dia="${slot.dia}"][data-periodo="${slot.periodo}"]`);
            if (cell) {
                // Se a ocupação for em OUTRA turma, destaca como conflito
                const currentTurmaId = document.querySelector('.turma-tab.active')?.href.split('turma_id=')[1] ||
                    document.querySelector('.turma-tabs a.active')?.href.split('turma_id=')[1];

                if (slot.turma_id != currentTurmaId) {
                    cell.classList.add('conflict-busy');
                    const label = document.createElement('div');
                    label.className = 'conflict-label';
                    label.textContent = `Ocupado: ${slot.turma_nome}`;
                    cell.appendChild(label);
                }
            }
        });
    } catch (err) {
        console.error('Erro ao buscar ocupação:', err);
    }
}

function limparDestaques() {
    document.querySelectorAll('.grade-cell').forEach(c => {
        c.classList.remove('conflict-busy');
        c.classList.remove('drag-over');
        const label = c.querySelector('.conflict-label');
        if (label) label.remove();
    });
}

function initDragDrop() {
    // Configura cards arrastáveis
    document.querySelectorAll('.aula-card[data-aula-id]').forEach(card => {
        card.setAttribute('draggable', 'true');

        card.addEventListener('dragstart', async (e) => {
            draggedCard = card;
            draggedAulaId = card.dataset.aulaId;
            card.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', draggedAulaId);

            // Busca o ID do professor desta aula (está na legenda ou podemos pegar do card se adicionarmos)
            // Para simplificar, vamos buscar a ocupação do professor associado a este card
            // Precisamos que o card tenha o data-professor-id
            const profId = card.dataset.professorId;
            if (profId) {
                destacarConflitos(profId);
            }
        });

        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
            draggedCard = null;
            draggedAulaId = null;
            limparDestaques();
        });
    });

    // Configura células de destino
    document.querySelectorAll('.grade-cell').forEach(cell => {
        cell.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            cell.classList.add('drag-over');
        });

        cell.addEventListener('dragleave', () => {
            cell.classList.remove('drag-over');
        });

        cell.addEventListener('drop', async (e) => {
            e.preventDefault();
            cell.classList.remove('drag-over');

            const aulaId = e.dataTransfer.getData('text/plain');
            const novoDia = cell.dataset.dia;
            const novoPeriodo = cell.dataset.periodo;

            if (!aulaId || !novoDia || !novoPeriodo) return;

            if (cell.classList.contains('conflict-busy')) {
                showToast('Esse professor já possui aula nesse horário.', 'error');
                return;
            }

            // Verifica se célula já tem aula (conflito de turma)
            if (cell.querySelector('.aula-card') && cell.querySelector('.aula-card').dataset.aulaId !== aulaId) {
                showToast('Essa turma já possui outra aula nesse horário.', 'error');
                return;
            }

            if (draggedCard && draggedCard.closest('.grade-cell') === cell) {
                return;
            }

            try {
                const escolaId = document.body.dataset.escolaId;
                const resp = await fetch(`/escola/${escolaId}/mover_aula`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken,
                    },
                    body: JSON.stringify({ aula_id: parseInt(aulaId), dia: novoDia, periodo: parseInt(novoPeriodo) })
                });

                const data = await resp.json();

                if (resp.ok && data.status === 'ok') {
                    // Move o card visualmente
                    if (draggedCard) {
                        const oldCell = draggedCard.closest('.grade-cell');
                        cell.appendChild(draggedCard);
                        cell.classList.remove('empty');
                        if (oldCell && !oldCell.querySelector('.aula-card')) {
                            oldCell.classList.add('empty');
                        }
                    }
                    showToast('✓ Aula movida com sucesso!', 'success');
                } else {
                    const message = data?.error?.message || data.msg || 'Tente novamente';
                    showToast('Erro ao mover aula: ' + message, 'error');
                }
            } catch (err) {
                showToast('Erro de conexão ao mover aula.', 'error');
                console.error(err);
            }
        });
    });
}

function showToast(msg, type = 'success') {
    const existing = document.getElementById('toast-container');
    if (existing) existing.remove();

    const container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    display: flex; flex-direction: column; gap: 8px;
  `;

    const toast = document.createElement('div');
    const colors = {
        success: { bg: 'rgba(34,197,94,0.15)', border: 'rgba(34,197,94,0.4)', color: '#4ade80' },
        error: { bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.4)', color: '#f87171' },
        warning: { bg: 'rgba(234,179,8,0.15)', border: 'rgba(234,179,8,0.4)', color: '#fbbf24' },
    };
    const c = colors[type] || colors.success;

    toast.style.cssText = `
    background: ${c.bg}; border: 1px solid ${c.border}; color: ${c.color};
    padding: 12px 20px; border-radius: 10px; font-size: 0.875rem; font-weight: 500;
    backdrop-filter: blur(8px); box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    animation: toastIn 0.3s ease;
  `;
    toast.textContent = msg;

    // Adiciona animação CSS
    if (!document.getElementById('toast-style')) {
        const style = document.createElement('style');
        style.id = 'toast-style';
        style.textContent = `
      @keyframes toastIn { from { opacity:0; transform: translateY(10px); } to { opacity:1; transform: translateY(0); } }
      @keyframes toastOut { from { opacity:1; } to { opacity:0; transform: translateY(10px); } }
    `;
        document.head.appendChild(style);
    }

    container.appendChild(toast);
    document.body.appendChild(container);

    setTimeout(() => {
        toast.style.animation = 'toastOut 0.3s ease forwards';
        setTimeout(() => container.remove(), 300);
    }, 3000);
}

// Modal helpers
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('active');
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('active');
}

// Fecha modal ao clicar fora
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

// Fecha modal com Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    }
});

// Auto-dismiss flash messages
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.alert').forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 4000);
    });

    initDragDrop();
});
