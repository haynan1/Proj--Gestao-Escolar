let draggedCard = null;
let draggedAulaId = null;
let draggedOrigin = null;
const ocupacaoProfessorCache = new Map();
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';


function getCurrentTurmaId() {
    return document.body.dataset.turmaId || '';
}


function criarMarcadorOcupacao(texto) {
    const label = document.createElement('div');
    label.className = 'conflict-label';
    label.textContent = texto;
    return label;
}


function limparMarcadoresDeTroca() {
    document.querySelectorAll('.grade-cell.swap-conflict').forEach((cell) => {
        cell.classList.remove('swap-conflict');
        cell.querySelectorAll('.swap-conflict-label').forEach((label) => label.remove());
    });
}


async function buscarOcupacaoProfessor(profId) {
    if (!profId) return [];
    if (ocupacaoProfessorCache.has(String(profId))) {
        return ocupacaoProfessorCache.get(String(profId));
    }

    const escolaId = document.body.dataset.escolaId;
    const resp = await fetch(`/escola/${escolaId}/professor/${profId}/ocupacao`);
    const ocupacao = await resp.json();
    ocupacaoProfessorCache.set(String(profId), ocupacao);
    return ocupacao;
}


function professorTemAulaNoSlot(ocupacao, dia, periodo, ignorarAulaIds = []) {
    const ignorados = ignorarAulaIds.map(String);
    return ocupacao.some((slot) => (
        slot.dia === dia
        && String(slot.periodo) === String(periodo)
        && !ignorados.includes(String(slot.aula_id))
    ));
}


function marcarConflitoTroca(cell, texto) {
    if (cell.classList.contains('swap-conflict')) return;
    cell.classList.add('swap-conflict');
    const label = criarMarcadorOcupacao(texto);
    label.classList.add('swap-conflict-label');
    cell.appendChild(label);
}


async function destacarTrocasInvalidas() {
    if (!draggedOrigin || !draggedAulaId) return;

    limparMarcadoresDeTroca();
    const cards = Array.from(document.querySelectorAll('.aula-card[data-aula-id]'));
    const professorIds = [...new Set(cards.map((card) => card.dataset.professorId).filter(Boolean))];
    await Promise.all(professorIds.map((profId) => buscarOcupacaoProfessor(profId).catch(() => [])));

    cards.forEach((card) => {
        if (card.dataset.aulaId === draggedAulaId) return;

        const cell = card.closest('.grade-cell');
        if (!cell) return;

        const ocupacaoDestino = ocupacaoProfessorCache.get(String(card.dataset.professorId)) || [];
        const trocaInvalida = professorTemAulaNoSlot(
            ocupacaoDestino,
            draggedOrigin.dia,
            draggedOrigin.periodo,
            [draggedAulaId, card.dataset.aulaId],
        );

        if (trocaInvalida) {
            marcarConflitoTroca(cell, 'Troca bloqueada');
        }
    });
}


async function destacarConflitos(profId) {
    if (!profId) return;

    try {
        const ocupacao = await buscarOcupacaoProfessor(profId);

        document.querySelectorAll('.grade-cell').forEach((cell) => {
            cell.classList.remove('conflict-busy');
            cell.classList.remove('professor-busy');
            cell.classList.remove('professor-origin');
            cell.querySelectorAll('.conflict-label:not(.swap-conflict-label)').forEach((label) => label.remove());
        });

        ocupacao.forEach((slot) => {
            const cell = document.querySelector(`.grade-cell[data-dia="${slot.dia}"][data-periodo="${slot.periodo}"]`);
            if (!cell) return;

            if (slot.aula_id == draggedAulaId) {
                cell.classList.add('professor-origin');
                cell.appendChild(criarMarcadorOcupacao('Origem'));
                return;
            }

            const currentTurmaId = getCurrentTurmaId();
            if (String(slot.turma_id) !== String(currentTurmaId)) {
                cell.classList.add('conflict-busy');
                cell.appendChild(criarMarcadorOcupacao(`Prof. ocupado: ${slot.turma_nome}`));
            } else {
                cell.classList.add('professor-busy');
                cell.appendChild(criarMarcadorOcupacao('Mesmo professor'));
            }
        });
    } catch (err) {
        console.error('Erro ao buscar ocupacao:', err);
    }
}


function limparDestaques() {
    document.querySelectorAll('.grade-cell').forEach((cell) => {
        cell.classList.remove('conflict-busy');
        cell.classList.remove('professor-busy');
        cell.classList.remove('professor-origin');
        cell.classList.remove('drag-over');
        cell.classList.remove('swap-target');
        cell.querySelectorAll('.conflict-label').forEach((label) => label.remove());
    });
    limparMarcadoresDeTroca();
}


function initDragDrop() {
    if (document.body.dataset.canManageSchedule !== 'true') {
        return;
    }

    document.querySelectorAll('.aula-card[data-aula-id]').forEach((card) => {
        card.setAttribute('draggable', 'true');

        card.addEventListener('dragstart', async (e) => {
            draggedCard = card;
            draggedAulaId = card.dataset.aulaId;
            const originCell = card.closest('.grade-cell');
            draggedOrigin = originCell ? {
                dia: originCell.dataset.dia,
                periodo: originCell.dataset.periodo,
            } : null;
            card.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', draggedAulaId);

            const profId = card.dataset.professorId;
            if (profId) {
                destacarConflitos(profId);
            }
            destacarTrocasInvalidas();
        });

        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
            draggedCard = null;
            draggedAulaId = null;
            draggedOrigin = null;
            limparDestaques();
        });
    });

    document.querySelectorAll('.grade-cell').forEach((cell) => {
        cell.addEventListener('dragover', (e) => {
            e.preventDefault();
            const targetCard = cell.querySelector('.aula-card');
            e.dataTransfer.dropEffect = 'move';
            cell.classList.add('drag-over');
            if (targetCard && targetCard.dataset.aulaId !== draggedAulaId) {
                cell.classList.add('swap-target');
            }
        });

        cell.addEventListener('dragleave', () => {
            cell.classList.remove('drag-over');
            cell.classList.remove('swap-target');
        });

        cell.addEventListener('drop', async (e) => {
            e.preventDefault();
            cell.classList.remove('drag-over');
            cell.classList.remove('swap-target');

            const aulaId = e.dataTransfer.getData('text/plain');
            const novoDia = cell.dataset.dia;
            const novoPeriodo = cell.dataset.periodo;
            const cardToMove = draggedCard || document.querySelector(`.aula-card[data-aula-id="${aulaId}"]`);
            const oldCell = cardToMove?.closest('.grade-cell');
            const targetCard = cell.querySelector('.aula-card');
            const isSwap = targetCard && targetCard.dataset.aulaId !== aulaId;

            if (!aulaId || !novoDia || !novoPeriodo) return;

            if (cell.classList.contains('conflict-busy')) {
                showToast('Esse professor ja possui aula nesse horario.', 'error');
                return;
            }

            if (isSwap && cell.classList.contains('swap-conflict')) {
                const professorNome = targetCard?.dataset.professorNome || 'O professor da aula de destino';
                showToast(`${professorNome} ja possui aula no horario de origem.`, 'error');
                return;
            }

            if (oldCell === cell) {
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
                    body: JSON.stringify({ aula_id: parseInt(aulaId), dia: novoDia, periodo: parseInt(novoPeriodo) }),
                });

                const data = await resp.json();
                if (resp.ok && data.status === 'ok') {
                    if (cardToMove) {
                        if (data.action === 'swap' && isSwap && targetCard && oldCell) {
                            oldCell.appendChild(targetCard);
                            oldCell.classList.remove('empty');
                        }
                        cell.appendChild(cardToMove);
                        cell.classList.remove('empty');
                        if (oldCell && !oldCell.querySelector('.aula-card')) {
                            oldCell.classList.add('empty');
                        }
                        cardToMove.classList.remove('dragging');
                    }
                    ocupacaoProfessorCache.clear();
                    showToast(data.action === 'swap' ? 'Aulas trocadas com sucesso!' : 'Aula movida com sucesso!', 'success');
                } else {
                    const message = data?.error?.message || data.msg || 'Tente novamente';
                    showToast(`Erro ao mover aula: ${message}`, 'error');
                }
            } catch (err) {
                showToast('Erro de conexao ao mover aula.', 'error');
                console.error(err);
            } finally {
                limparDestaques();
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


document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.alert').forEach((alert) => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 4000);
    });

    initDragDrop();
});
