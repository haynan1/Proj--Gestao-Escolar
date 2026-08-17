function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('active');
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('active');
}

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay') && !e.target.hasAttribute('data-confirm-dialog')) {
        e.target.classList.remove('active');
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active:not([data-confirm-dialog])')
            .forEach((modal) => modal.classList.remove('active'));
    }
});

// ─── Toast notifications ────────────────────────────────────────────────────

function showToast(message, type) {
    const VALID_TYPES = ['success', 'error', 'warning'];
    type = VALID_TYPES.includes(type) ? type : 'error';

    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.setAttribute('aria-live', 'assertive');
        container.setAttribute('aria-atomic', 'false');
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.setAttribute('role', 'status');

    const prefix = type === 'success' ? '+' : type === 'warning' ? '⚠' : '!';
    const prefixEl = document.createElement('span');
    prefixEl.className = 'toast-prefix';
    prefixEl.textContent = prefix;

    const msgEl = document.createElement('span');
    msgEl.className = 'toast-message';
    msgEl.textContent = message;

    toast.appendChild(prefixEl);
    toast.appendChild(msgEl);
    container.appendChild(toast);

    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            toast.classList.add('toast-visible');
        });
    });

    const DURATION = 4500;
    let timer = setTimeout(() => _dismissToast(toast), DURATION);

    toast.addEventListener('click', () => {
        clearTimeout(timer);
        _dismissToast(toast);
    });
}

function _dismissToast(toast) {
    toast.classList.remove('toast-visible');
    toast.addEventListener('transitionend', () => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, { once: true });
}

// ─── Confirmação padronizada ────────────────────────────────────────────────
//
// Diálogo único, reaproveitado por todo o sistema, no lugar do confirm() nativo
// do navegador (que ignora o tema, expõe o host e não é estilizável).
//
// Uso declarativo — o elemento pede a confirmação, o diálogo cuida do resto:
//
//   <form method="POST" action="..."
//         data-confirm="Remover a turma 6 Ano A?"
//         data-confirm-title="Remover turma"
//         data-confirm-label="Remover"
//         data-confirm-tone="danger">
//
// Também funciona em <a href> e em <button> fora de formulário.
//
// Tons: 'danger' (destrutivo), 'warning' (substitui/sobrescreve), 'default'.
// Quando não declarado, é inferido da classe do botão que disparou a ação.
//
// A mensagem aceita marcadores {campo}, trocados pelo valor atual do campo do
// formulário com esse name (em <select>, pelo texto da opção escolhida).
//
// Programaticamente: await confirmAction({ title, message, tone }) -> boolean

const ConfirmDialog = (() => {
    const TONES = ['default', 'warning', 'danger'];
    const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

    let elements = null;
    let pending = null;
    let lastFocused = null;

    const build = () => {
        if (elements) return elements;

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay modal-overlay-confirm';
        overlay.setAttribute('data-confirm-dialog', '');
        overlay.setAttribute('aria-hidden', 'true');

        const dialog = document.createElement('div');
        dialog.className = 'modal modal-confirm';
        dialog.setAttribute('role', 'alertdialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.setAttribute('aria-labelledby', 'confirm-dialog-title');
        dialog.setAttribute('aria-describedby', 'confirm-dialog-message');

        const head = document.createElement('div');
        head.className = 'confirm-dialog-head';

        const icon = document.createElement('span');
        icon.className = 'confirm-dialog-icon';
        icon.setAttribute('aria-hidden', 'true');

        const copy = document.createElement('div');
        copy.className = 'confirm-dialog-copy';

        const title = document.createElement('h2');
        title.className = 'confirm-dialog-title';
        title.id = 'confirm-dialog-title';

        const message = document.createElement('p');
        message.className = 'confirm-dialog-message';
        message.id = 'confirm-dialog-message';

        copy.appendChild(title);
        copy.appendChild(message);
        head.appendChild(icon);
        head.appendChild(copy);

        const actions = document.createElement('div');
        actions.className = 'confirm-dialog-actions';

        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'btn btn-secondary confirm-dialog-cancel';

        const accept = document.createElement('button');
        accept.type = 'button';
        accept.className = 'btn confirm-dialog-accept';

        actions.appendChild(cancel);
        actions.appendChild(accept);
        dialog.appendChild(head);
        dialog.appendChild(actions);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        cancel.addEventListener('click', () => settle(false));
        accept.addEventListener('click', () => settle(true));
        overlay.addEventListener('mousedown', (event) => {
            if (event.target === overlay) settle(false);
        });
        dialog.addEventListener('keydown', trapFocus);

        elements = { overlay, dialog, icon, title, message, cancel, accept };
        return elements;
    };

    const trapFocus = (event) => {
        if (event.key === 'Tab') {
            const focusables = Array.from(elements.dialog.querySelectorAll(FOCUSABLE));
            if (!focusables.length) return;
            const first = focusables[0];
            const last = focusables[focusables.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    };

    const onKeydown = (event) => {
        if (!pending) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();
            settle(false);
        }
    };

    const settle = (result) => {
        if (!pending) return;
        const resolve = pending;
        pending = null;

        document.removeEventListener('keydown', onKeydown, true);
        elements.overlay.classList.remove('active');
        elements.overlay.setAttribute('aria-hidden', 'true');
        // Fechado, o diálogo continua no DOM (só com opacity/pointer-events zerados):
        // desabilitar os botões o tira da ordem de tabulação e do alcance do leitor.
        elements.accept.disabled = true;
        elements.cancel.disabled = true;

        if (lastFocused && typeof lastFocused.focus === 'function' && document.contains(lastFocused)) {
            lastFocused.focus();
        }
        lastFocused = null;
        resolve(Boolean(result));
    };

    const open = (options = {}) => {
        const ui = build();

        // Uma confirmação por vez: a anterior é encerrada como "cancelar".
        settle(false);

        const tone = TONES.includes(options.tone) ? options.tone : 'default';
        const defaultTitle = tone === 'danger' ? 'Confirmar remoção' : 'Confirmar ação';

        ui.title.textContent = options.title || defaultTitle;
        ui.message.textContent = options.message || 'Deseja continuar?';
        ui.cancel.textContent = options.cancelLabel || 'Cancelar';
        ui.accept.textContent = options.confirmLabel || 'Confirmar';
        ui.icon.textContent = tone === 'danger' ? '!' : tone === 'warning' ? '⚠' : '?';

        TONES.forEach((name) => {
            ui.dialog.classList.toggle(`tone-${name}`, name === tone);
        });
        ui.accept.classList.remove('btn-primary', 'btn-danger');
        ui.accept.classList.add(tone === 'danger' ? 'btn-danger' : 'btn-primary');
        ui.accept.disabled = false;
        ui.cancel.disabled = false;

        lastFocused = document.activeElement;
        ui.overlay.removeAttribute('aria-hidden');
        ui.overlay.classList.add('active');
        document.addEventListener('keydown', onKeydown, true);

        return new Promise((resolve) => {
            pending = resolve;
            requestAnimationFrame(() => {
                // Em ações destrutivas o foco começa na saída segura.
                (tone === 'danger' ? ui.cancel : ui.accept).focus();
            });
        });
    };

    return { open };
})();

function confirmAction(options) {
    return ConfirmDialog.open(options);
}

(() => {
    const interpolate = (message, form) => {
        if (!form || !message.includes('{')) return message;
        return message.replace(/\{([A-Za-z_][\w-]*)\}/g, (match, name) => {
            const field = form.elements ? form.elements[name] : null;
            if (!field) return match;
            if (field instanceof HTMLSelectElement) {
                const option = field.options[field.selectedIndex];
                return (option ? option.text : field.value).trim();
            }
            const value = field.value;
            return typeof value === 'string' ? value.trim() : match;
        });
    };

    const inferTone = (element, trigger) => {
        const declared = element.getAttribute('data-confirm-tone');
        if (declared) return declared;
        const source = trigger || element;
        if (source.classList && source.classList.contains('btn-danger')) return 'danger';
        return 'default';
    };

    const optionsFor = (element, trigger, form) => ({
        title: element.getAttribute('data-confirm-title') || undefined,
        message: interpolate(element.getAttribute('data-confirm') || '', form),
        confirmLabel: element.getAttribute('data-confirm-label') || undefined,
        cancelLabel: element.getAttribute('data-confirm-cancel-label') || undefined,
        tone: inferTone(element, trigger),
    });

    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-confirm')) return;

        if (form.dataset.confirmResolved === 'true') {
            delete form.dataset.confirmResolved;
            return;
        }

        event.preventDefault();
        event.stopImmediatePropagation();

        const submitter = event.submitter && form.contains(event.submitter) ? event.submitter : null;
        ConfirmDialog.open(optionsFor(form, submitter, form)).then((confirmed) => {
            if (!confirmed) return;
            form.dataset.confirmResolved = 'true';
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit(submitter || undefined);
            } else {
                delete form.dataset.confirmResolved;
                form.submit();
            }
        });
    }, true);

    document.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-confirm]');
        if (!trigger || trigger instanceof HTMLFormElement) return;
        // Submits são tratados no evento 'submit' do formulário (valida antes de perguntar).
        if (trigger.matches('button[type="submit"], input[type="submit"]')) return;
        if (trigger.dataset.confirmResolved === 'true') {
            delete trigger.dataset.confirmResolved;
            return;
        }

        event.preventDefault();
        event.stopImmediatePropagation();

        const form = trigger.closest('form');
        ConfirmDialog.open(optionsFor(trigger, trigger, form)).then((confirmed) => {
            if (!confirmed) return;
            if (trigger instanceof HTMLAnchorElement && trigger.href) {
                window.location.href = trigger.href;
                return;
            }
            trigger.dataset.confirmResolved = 'true';
            trigger.click();
        });
    }, true);
})();
