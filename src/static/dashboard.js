/**
 * Lógica do Dashboard Flowter
 * Separada do HTML para evitar conflitos de sintaxe no editor
 */

document.addEventListener('DOMContentLoaded', () => {
    const escolaId = document.body.dataset.escolaId;
    const turno = document.body.dataset.turno || 'matutino';
    const turnoQuery = `?turno=${encodeURIComponent(turno)}`;
    const dashboardScrollKey = `flowter:dashboard-scroll:${escolaId || 'default'}:${turno}`;

    const getResourceTargetFromAction = (action = '') => {
        if (action.includes('/professor/')) return 'professores';
        if (action.includes('/disciplina/')) return 'disciplinas';
        if (action.includes('/turma/')) return 'turmas';
        return '';
    };

    const saveDashboardScrollPosition = (form) => {
        const targetId = getResourceTargetFromAction(form?.getAttribute('action') || '');
        if (!targetId) return;

        sessionStorage.setItem(dashboardScrollKey, JSON.stringify({
            targetId,
            scrollX: window.scrollX || 0,
            scrollY: window.scrollY || 0,
            savedAt: Date.now(),
        }));
    };

    const restoreDashboardScrollPosition = () => {
        let saved = null;
        try {
            saved = JSON.parse(sessionStorage.getItem(dashboardScrollKey) || 'null');
            sessionStorage.removeItem(dashboardScrollKey);
        } catch (error) {
            sessionStorage.removeItem(dashboardScrollKey);
        }

        if (!saved || Date.now() - Number(saved.savedAt || 0) > 15000) return;

        const target = document.getElementById(saved.targetId);
        requestAnimationFrame(() => {
            if (Number.isFinite(Number(saved.scrollY))) {
                window.scrollTo(Number(saved.scrollX || 0), Number(saved.scrollY));
            } else if (target) {
                target.scrollIntoView({ block: 'start', inline: 'nearest' });
            }
        });
    };

    restoreDashboardScrollPosition();

    const applyDynamicColors = () => {
        document.querySelectorAll('.dot-dynamic').forEach(el => {
            const color = el.dataset.color;
            if (color) el.style.backgroundColor = color;
        });
        document.querySelectorAll('.badge-dynamic').forEach(el => {
            const color = el.dataset.color;
            if (color) {
                el.style.backgroundColor = color + '15';
                el.style.color = color;
                el.style.borderColor = color + '30';
            }
        });
    };

    const initDashboardColorPickers = () => {
        if (typeof initColorPicker !== 'function') return;
        initColorPicker('cor-disciplina', 'swatches-disciplina');
        initColorPicker('cor-disciplina-edit', 'swatches-disciplina-edit');
        initColorPicker('cor-professor', 'swatches-professor');
        initColorPicker('cor-professor-edit', 'swatches-professor-edit');
    };

    const getDashboardContainer = (root = document) => (
        root.querySelector('.dashboard-page-header')?.closest('.container')
    );

    const replaceElementFromDocument = (selector, nextDoc) => {
        const current = document.querySelector(selector);
        const next = nextDoc.querySelector(selector);
        if (current && next) current.replaceWith(next);
    };

    const applyDashboardHtml = (html, targetId, scrollPosition) => {
        const nextDoc = new DOMParser().parseFromString(html, 'text/html');
        const currentFlash = document.querySelector('body > .container');
        const nextFlash = nextDoc.querySelector('body > .container');
        const currentDashboard = getDashboardContainer(document);
        const nextDashboard = getDashboardContainer(nextDoc);

        if (currentFlash && nextFlash) currentFlash.replaceWith(nextFlash);
        if (currentDashboard && nextDashboard) currentDashboard.replaceWith(nextDashboard);

        ['modal-disc', 'modal-disc-edit', 'modal-prof', 'modal-prof-edit', 'modal-turma', 'modal-turma-edit'].forEach((id) => {
            replaceElementFromDocument(`#${id}`, nextDoc);
        });

        applyDynamicColors();
        initDashboardColorPickers();
        initProfessorForms();
        initResourceForms();
        closeAiAuditMenu();

        const target = document.getElementById(targetId);
        requestAnimationFrame(() => {
            if (scrollPosition && Number.isFinite(Number(scrollPosition.scrollY))) {
                window.scrollTo(Number(scrollPosition.scrollX || 0), Number(scrollPosition.scrollY));
            } else if (target) {
                target.scrollIntoView({ block: 'start', inline: 'nearest' });
            }
        });
    };

    const closeAiAuditMenu = () => {
        const menu = document.querySelector('.ai-audit-menu');
        const trigger = menu?.querySelector('.ai-audit-trigger');
        if (!menu) return;
        menu.classList.remove('is-open');
        trigger?.setAttribute('aria-expanded', 'false');
    };

    const copyAiAuditPayload = async () => {
        const payload = document.getElementById('ai-audit-payload')?.value || '';
        if (!payload.trim()) {
            throw new Error('Sem dados para copiar.');
        }

        if (navigator.clipboard?.writeText && window.isSecureContext) {
            await navigator.clipboard.writeText(payload);
            return;
        }

        const temp = document.createElement('textarea');
        temp.value = payload;
        temp.setAttribute('readonly', '');
        temp.style.position = 'fixed';
        temp.style.left = '-9999px';
        temp.style.top = '0';
        document.body.appendChild(temp);
        temp.select();
        const copied = document.execCommand('copy');
        temp.remove();
        if (!copied) throw new Error('Falha ao copiar.');
    };

    const notifyAiAuditCopy = (message, type = 'success') => {
        if (typeof showToast === 'function') {
            showToast(message, type);
        } else {
            alert(message);
        }
    };

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

    const initProfessorForms = () => {
        document.querySelectorAll('#modal-prof form, #modal-prof-edit form').forEach(form => {
            if (form.dataset.professorFormInitialized === 'true') {
                syncCargaRows(form);
                return;
            }
            form.dataset.professorFormInitialized = 'true';

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
    };

    initProfessorForms();

    // Gerenciamento de Modais de Edição via Event Delegation
    const initResourceForms = () => {
        Array.from(document.querySelectorAll('form'))
            .filter(form => String(form.getAttribute('method') || '').toLowerCase() === 'post')
            .forEach(form => {
            if (form.dataset.resourceSubmitInitialized === 'true') return;
            form.dataset.resourceSubmitInitialized = 'true';

            form.addEventListener('submit', async (event) => {
                if (event.defaultPrevented) return;
                const targetId = getResourceTargetFromAction(form.getAttribute('action') || '');
                if (!targetId) return;

                event.preventDefault();
                if (form.dataset.submitting === 'true') return;

                saveDashboardScrollPosition(form);
                form.dataset.submitting = 'true';
                const scrollPosition = { scrollX: window.scrollX || 0, scrollY: window.scrollY || 0 };
                const submitButtons = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]'));
                submitButtons.forEach(button => { button.disabled = true; });

                try {
                    const resp = await fetch(form.action, {
                        method: 'POST',
                        body: new FormData(form),
                        credentials: 'same-origin',
                        headers: { 'X-Requested-With': 'fetch' },
                    });
                    const html = await resp.text();
                    if (!resp.ok) throw new Error('Falha ao salvar.');
                    applyDashboardHtml(html, targetId, scrollPosition);
                } catch (error) {
                    if (typeof showToast === 'function') {
                        showToast('Não foi possível salvar agora. Tente novamente.', 'error');
                    } else {
                        alert('Não foi possível salvar agora. Tente novamente.');
                    }
                    submitButtons.forEach(button => { button.disabled = false; });
                    form.dataset.submitting = 'false';
                }
            });
        });
    };

    initResourceForms();

    document.addEventListener('click', async (e) => {
        const aiAuditTrigger = e.target.closest('.ai-audit-trigger');
        if (aiAuditTrigger) {
            const menu = aiAuditTrigger.closest('.ai-audit-menu');
            const isOpen = menu?.classList.toggle('is-open');
            aiAuditTrigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            return;
        }

        const aiAuditAction = e.target.closest('[data-ai-audit-action]');
        if (aiAuditAction) {
            const action = aiAuditAction.dataset.aiAuditAction;
            const shouldOpenAi = action === 'open';
            closeAiAuditMenu();
            if (shouldOpenAi) {
                window.open('https://chatgpt.com/g/g-69fbfd0d34bc8191b3646131992a571c-flowter', '_blank', 'noopener');
            }
            try {
                await copyAiAuditPayload();
                notifyAiAuditCopy(shouldOpenAi ? 'Dados copiados para a IA.' : 'Dados copiados.', 'success');
            } catch (error) {
                notifyAiAuditCopy('Não foi possível copiar os dados.', 'error');
            }
            return;
        }

        if (!e.target.closest('.ai-audit-menu')) {
            closeAiAuditMenu();
        }

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
