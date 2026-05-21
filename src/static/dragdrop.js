let draggedCard = null;
let draggedAulaId = null;
let draggedOrigin = null;
let activeDragToken = 0;
const ocupacaoProfessorCache = new Map();
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';


function getTurnoQuery() {
    return `turno=${encodeURIComponent(document.body.dataset.turno || 'matutino')}`;
}


function getCurrentTurmaId() {
    return document.body.dataset.turmaId || '';
}


function getCellTurmaId(cell) {
    return cell?.dataset?.turmaId || getCurrentTurmaId();
}


function getVisibleCellsForSlot(slot) {
    return Array.from(document.querySelectorAll(
        `.grade-cell[data-dia="${slot.dia}"][data-periodo="${slot.periodo}"]`
    ));
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


function limparMarcadoresDeConflito() {
    document.querySelectorAll('.grade-cell').forEach((cell) => {
        cell.classList.remove('conflict-busy');
        cell.classList.remove('professor-busy');
        cell.classList.remove('professor-origin');
        cell.querySelectorAll('.conflict-label:not(.swap-conflict-label)').forEach((label) => label.remove());
    });
}


async function buscarOcupacaoProfessor(profId) {
    if (!profId) return [];
    if (ocupacaoProfessorCache.has(String(profId))) {
        return ocupacaoProfessorCache.get(String(profId));
    }

    const escolaId = document.body.dataset.escolaId;
    const resp = await fetch(`/escola/${escolaId}/professor/${profId}/ocupacao?${getTurnoQuery()}`);
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
        if (draggedOrigin?.turmaId && String(getCellTurmaId(cell)) !== String(draggedOrigin.turmaId)) return;

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


async function destacarConflitos(profId, dragToken = activeDragToken) {
    if (!profId) return;

    try {
        const ocupacao = await buscarOcupacaoProfessor(profId);
        if (dragToken !== activeDragToken || !draggedAulaId || !draggedOrigin) return;

        limparMarcadoresDeConflito();

        ocupacao.forEach((slot) => {
            const cells = getVisibleCellsForSlot(slot);
            if (!cells.length) return;

            cells.forEach((cell) => {
                const cellTurmaId = getCellTurmaId(cell);
                const isOriginCell = cell.querySelector(`.aula-card[data-aula-id="${draggedAulaId}"]`);
                const isDropCandidateTurma = !draggedOrigin || String(cellTurmaId) === String(draggedOrigin.turmaId);

                if (isOriginCell) {
                    cell.classList.add('professor-origin');
                    cell.appendChild(criarMarcadorOcupacao('Origem'));
                    return;
                }

                if (!isDropCandidateTurma) return;

                if (String(slot.turma_id) !== String(cellTurmaId)) {
                    cell.classList.add('conflict-busy');
                    cell.appendChild(criarMarcadorOcupacao(`Prof. ocupado: ${slot.turma_nome}`));
                } else {
                    cell.classList.add('professor-busy');
                    cell.appendChild(criarMarcadorOcupacao('Mesmo professor'));
                }
            });
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
        cell.classList.remove('professor-unavailable');
        cell.classList.remove('drag-over');
        cell.classList.remove('swap-target');
        cell.querySelectorAll('.conflict-label').forEach((label) => label.remove());
    });
    limparMarcadoresDeTroca();
    document.querySelectorAll('.grade-day-header.day-unavailable').forEach((h) => {
        h.classList.remove('day-unavailable');
    });
}


function destacarDiasIndisponiveis(diasDisponiveis) {
    if (!diasDisponiveis || diasDisponiveis.length === 0) return;

    document.querySelectorAll('.grade-cell').forEach((cell) => {
        const dia = cell.dataset.dia;
        if (!dia || diasDisponiveis.includes(dia)) return;
        cell.classList.add('professor-unavailable');
        if (!cell.querySelector('.unavailable-label')) {
            const label = criarMarcadorOcupacao('Indisponível');
            label.classList.add('unavailable-label');
            cell.appendChild(label);
        }
    });

    document.querySelectorAll('[data-day-header]').forEach((header) => {
        const dia = header.dataset.dayHeader;
        if (dia && !diasDisponiveis.includes(dia)) {
            header.classList.add('day-unavailable');
        }
    });
}


function destacarOutrasTurmasBloqueadas() {
    if (document.body.dataset.scheduleView !== 'geral' || !draggedOrigin?.turmaId) return;

    document.querySelectorAll('.grade-cell').forEach((cell) => {
        if (String(getCellTurmaId(cell)) === String(draggedOrigin.turmaId)) return;
        cell.classList.add('conflict-busy');
        if (!cell.querySelector('.cross-class-label')) {
            const label = criarMarcadorOcupacao('Outra turma');
            label.classList.add('cross-class-label');
            cell.appendChild(label);
        }
    });
}


function removerBotaoManual(cell) {
    cell?.querySelector('[data-manual-slot]')?.remove();
}


function garantirBotaoManual(cell) {
    if (!cell || cell.querySelector('.aula-card') || cell.querySelector('[data-manual-slot]')) return;
    if (document.body.dataset.canManageSchedule !== 'true') return;
    if (document.body.dataset.scheduleLocked === 'true') return;
    if (document.body.dataset.scheduleView !== 'geral') return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'manual-slot-add';
    button.dataset.manualSlot = '';
    button.dataset.turmaId = getCellTurmaId(cell);
    button.dataset.turmaNome = cell.dataset.turmaNome || '';
    button.dataset.dia = cell.dataset.dia || '';
    button.dataset.periodo = cell.dataset.periodo || '';
    button.textContent = '+';
    cell.appendChild(button);
}


function initTrashDrop() {
    const trashZone = document.querySelector('[data-schedule-trash]');
    if (!trashZone) return;
    if (trashZone.dataset.dragdropInitialized === 'true') return;
    trashZone.dataset.dragdropInitialized = 'true';

    trashZone.addEventListener('dragover', (e) => {
        if (!draggedAulaId) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        trashZone.classList.add('drag-over');
    });

    trashZone.addEventListener('dragleave', () => {
        trashZone.classList.remove('drag-over');
    });

    trashZone.addEventListener('drop', async (e) => {
        e.preventDefault();
        trashZone.classList.remove('drag-over');

        const aulaId = e.dataTransfer.getData('text/plain') || draggedAulaId;
        const cardToDelete = draggedCard || document.querySelector(`.aula-card[data-aula-id="${aulaId}"]`);
        const oldCell = cardToDelete?.closest('.grade-cell');
        if (!aulaId) return;

        try {
            const escolaId = document.body.dataset.escolaId;
            const resp = await fetch(`/escola/${escolaId}/horarios/aula/${aulaId}/deletar?${getTurnoQuery()}`, {
                method: 'POST',
                headers: {
                    'X-CSRF-Token': csrfToken,
                },
            });
            const data = await resp.json();
            if (resp.ok && data.status === 'ok') {
                if (typeof window.registrarAulaPendenteManual === 'function') {
                    window.registrarAulaPendenteManual(data.aula);
                }
                cardToDelete?.remove();
                if (oldCell && !oldCell.querySelector('.aula-card')) {
                    oldCell.classList.add('empty');
                    garantirBotaoManual(oldCell);
                }
                ocupacaoProfessorCache.clear();
                showToast('Aula removida com sucesso!', 'success');
                return;
            }

            showToast(data?.error?.message || 'Não foi possível remover a aula.', 'error');
        } catch (err) {
            showToast('Erro de conexão ao remover aula.', 'error');
            console.error(err);
        } finally {
            limparDestaques();
        }
    });
}


function initDragDrop() {
    if (document.body.dataset.canManageSchedule !== 'true') {
        return;
    }
    if (document.body.dataset.scheduleLocked === 'true') {
        document.querySelectorAll('.aula-card[data-aula-id]').forEach((card) => {
            card.setAttribute('draggable', 'false');
        });
        return;
    }

    initTrashDrop();

    document.querySelectorAll('.aula-card[data-aula-id]').forEach((card) => {
        if (card.dataset.dragdropInitialized === 'true') return;
        card.dataset.dragdropInitialized = 'true';
        card.setAttribute('draggable', 'true');

        card.addEventListener('dragstart', async (e) => {
            const dragToken = ++activeDragToken;
            draggedCard = card;
            draggedAulaId = card.dataset.aulaId;
            const originCell = card.closest('.grade-cell');
            draggedOrigin = originCell ? {
                dia: originCell.dataset.dia,
                periodo: originCell.dataset.periodo,
                turmaId: getCellTurmaId(originCell),
            } : null;
            card.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', draggedAulaId);

            const profId = card.dataset.professorId;
            const diasRaw = card.dataset.professorDias || '';
            const diasDisponiveis = diasRaw.split(',').map((d) => d.trim()).filter(Boolean);
            destacarDiasIndisponiveis(diasDisponiveis);
            if (profId) {
                await destacarConflitos(profId, dragToken);
            } else {
                limparMarcadoresDeConflito();
            }
            if (dragToken !== activeDragToken || !draggedAulaId || !draggedOrigin) return;
            await destacarTrocasInvalidas();
            if (dragToken !== activeDragToken || !draggedAulaId || !draggedOrigin) return;
            destacarOutrasTurmasBloqueadas();
        });

        card.addEventListener('dragend', () => {
            activeDragToken += 1;
            card.classList.remove('dragging');
            draggedCard = null;
            draggedAulaId = null;
            draggedOrigin = null;
            limparDestaques();
        });
    });

    document.querySelectorAll('.grade-cell').forEach((cell) => {
        if (cell.dataset.dragdropInitialized === 'true') return;
        cell.dataset.dragdropInitialized = 'true';
        cell.addEventListener('dragover', (e) => {
            e.preventDefault();
            const targetCard = cell.querySelector('.aula-card');
            const targetTurmaId = getCellTurmaId(cell);
            const sameTurma = !draggedOrigin || String(draggedOrigin.turmaId) === String(targetTurmaId);
            e.dataTransfer.dropEffect = sameTurma ? 'move' : 'none';
            cell.classList.add('drag-over');
            if (!sameTurma && !cell.querySelector('.cross-class-label')) {
                const label = criarMarcadorOcupacao('Outra turma');
                label.classList.add('cross-class-label');
                cell.appendChild(label);
            }
            if (targetCard && targetCard.dataset.aulaId !== draggedAulaId && sameTurma) {
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
            const originTurmaId = getCellTurmaId(oldCell);
            const targetTurmaId = getCellTurmaId(cell);

            if (!aulaId || !novoDia || !novoPeriodo) return;

            if (String(originTurmaId) !== String(targetTurmaId)) {
                showToast('Arraste a aula apenas dentro da mesma turma.', 'warning');
                return;
            }

            if (cell.classList.contains('conflict-busy')) {
                showToast('Esse professor já possui aula nesse horário.', 'error');
                return;
            }

            if (isSwap && cell.classList.contains('swap-conflict')) {
                const professorNome = targetCard?.dataset.professorNome || 'O professor da aula de destino';
                showToast(`${professorNome} já possui aula no horário de origem.`, 'error');
                return;
            }

            if (oldCell === cell) {
                return;
            }

            try {
                const escolaId = document.body.dataset.escolaId;
                const resp = await fetch(`/escola/${escolaId}/mover_aula?${getTurnoQuery()}`, {
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
                        removerBotaoManual(cell);
                        if (data.action === 'swap' && isSwap && targetCard && oldCell) {
                            oldCell.appendChild(targetCard);
                            oldCell.classList.remove('empty');
                        }
                        cell.appendChild(cardToMove);
                        cell.classList.remove('empty');
                        if (oldCell && !oldCell.querySelector('.aula-card')) {
                            oldCell.classList.add('empty');
                            garantirBotaoManual(oldCell);
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
                showToast('Erro de conexão ao mover aula.', 'error');
                console.error(err);
            } finally {
                limparDestaques();
            }
        });
    });
}


window.FlowterSchedule = window.FlowterSchedule || {};
window.FlowterSchedule.initDragDrop = initDragDrop;
window.FlowterSchedule.clearProfessorOccupationCache = () => ocupacaoProfessorCache.clear();




document.addEventListener('DOMContentLoaded', () => {
    initDragDrop();
});
