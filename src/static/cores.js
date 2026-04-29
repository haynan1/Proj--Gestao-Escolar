/**
 * cores.js - gerenciamento de cores para disciplinas e professores.
 */

const CORES_PREDEFINIDAS = [
    { nome: 'Azul', hex: '#2563eb' },
    { nome: 'Verde', hex: '#16a34a' },
    { nome: 'Vermelho', hex: '#dc2626' },
    { nome: 'Roxo', hex: '#9333ea' },
    { nome: 'Laranja', hex: '#ea580c' },
    { nome: 'Ciano', hex: '#0891b2' },
    { nome: 'Indigo', hex: '#4f46e5' },
    { nome: 'Carmim', hex: '#be123c' },
    { nome: 'Teal', hex: '#0d9488' },
    { nome: 'Ouro', hex: '#a16207' },
    { nome: 'Violeta', hex: '#7c3aed' },
    { nome: 'Celeste', hex: '#0284c7' },
    { nome: 'Oliva', hex: '#65a30d' },
    { nome: 'Terracota', hex: '#c2410c' },
    { nome: 'Magenta', hex: '#db2777' },
    { nome: 'Anil', hex: '#4338ca' },
    { nome: 'Esmeralda', hex: '#047857' },
    { nome: 'Rubria', hex: '#b91c1c' },
    { nome: 'Petroleo', hex: '#0369a1' },
    { nome: 'Marrom', hex: '#92400e' },
];

function corTexto(hexBg) {
    const hex = hexBg.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    const luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminancia > 0.5 ? '#0f172a' : '#f1f5f9';
}

function aplicarCorAula(el, cor) {
    el.style.backgroundColor = `${cor}22`;
    el.style.borderLeftColor = cor;
    el.style.color = cor;
}

function initColorPicker(inputId, swatchContainerId) {
    const input = document.getElementById(inputId);
    const container = document.getElementById(swatchContainerId);
    if (!input || !container) return;

    const defaultColor = input.dataset.defaultColor || '#22c55e';
    const customInput = document.getElementById(`${inputId}-custom`);
    const currentControl = document.querySelector(`[data-color-trigger="${inputId}"]`);
    const currentPreview = currentControl?.querySelector('.color-current-preview');

    container.classList.add('color-swatch-grid');
    const shouldBuildPalette = !container.querySelector('button[data-color]:not([data-color-mode="default"])');

    const syncSelected = () => {
        const currentColor = input.value.trim();
        const defaultSelected = currentColor === '';
        container.querySelectorAll('button[data-color]').forEach((btn) => {
            const isDefaultButton = btn.dataset.colorMode === 'default';
            const selected = isDefaultButton
                ? defaultSelected
                : !defaultSelected && btn.dataset.color.toLowerCase() === currentColor.toLowerCase();
            btn.classList.toggle('active', selected);
            btn.setAttribute('aria-pressed', selected ? 'true' : 'false');
        });
        if (customInput && currentColor) {
            customInput.value = currentColor;
        }
        if (currentControl && currentPreview) {
            currentControl.classList.toggle('is-empty', defaultSelected);
            currentPreview.style.backgroundColor = defaultSelected ? '' : currentColor;
        }
    };

    if (!container.querySelector('button[data-color-mode="default"]')) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.title = 'Sem cor';
        btn.className = 'color-swatch color-swatch-empty';
        btn.dataset.color = '';
        btn.dataset.colorMode = 'default';
        btn.setAttribute('aria-label', 'Sem cor, usar padrão do sistema');
        btn.setAttribute('aria-pressed', 'false');
        container.prepend(btn);
    }

    if (shouldBuildPalette) {
        CORES_PREDEFINIDAS.forEach((cor) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.title = cor.nome;
            btn.className = 'color-swatch';
            btn.dataset.color = cor.hex;
            btn.style.backgroundColor = cor.hex;
            btn.setAttribute('aria-label', `Selecionar cor ${cor.nome}`);
            btn.setAttribute('aria-pressed', 'false');
            container.appendChild(btn);
        });
    }

    container.querySelectorAll('button[data-color]').forEach((btn) => {
        btn.type = 'button';
        btn.classList.add('color-swatch');
        btn.setAttribute('aria-pressed', 'false');
        btn.addEventListener('click', () => {
            input.value = btn.dataset.color;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            syncSelected();
        });
    });

    input.addEventListener('input', syncSelected);
    if (currentControl && customInput) {
        currentControl.addEventListener('click', () => {
            customInput.click();
        });
    }
    if (customInput) {
        customInput.addEventListener('input', () => {
            input.value = customInput.value || defaultColor;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            syncSelected();
        });
    }
    syncSelected();
}

document.addEventListener('DOMContentLoaded', () => {
    initColorPicker('cor-disciplina', 'swatches-disciplina');
    initColorPicker('cor-disciplina-edit', 'swatches-disciplina-edit');
    initColorPicker('cor-professor', 'swatches-professor');
    initColorPicker('cor-professor-edit', 'swatches-professor-edit');
});
