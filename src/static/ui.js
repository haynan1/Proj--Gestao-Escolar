function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('active');
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('active');
}

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach((modal) => modal.classList.remove('active'));
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
