/**
 * cores.js — Gerenciamento de cores para disciplinas
 */

const CORES_PREDEFINIDAS = [
    { nome: 'Verde', hex: '#22c55e' },
    { nome: 'Azul', hex: '#3b82f6' },
    { nome: 'Roxo', hex: '#a855f7' },
    { nome: 'Laranja', hex: '#f97316' },
    { nome: 'Vermelho', hex: '#ef4444' },
    { nome: 'Amarelo', hex: '#eab308' },
    { nome: 'Rosa', hex: '#ec4899' },
    { nome: 'Ciano', hex: '#06b6d4' },
    { nome: 'Lima', hex: '#84cc16' },
    { nome: 'Índigo', hex: '#6366f1' },
];

/**
 * Retorna a cor de texto (preto ou branco) com base na luminância do fundo.
 */
function corTexto(hexBg) {
    const hex = hexBg.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    const luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminancia > 0.5 ? '#0f172a' : '#f1f5f9';
}

/**
 * Aplica cor de fundo e texto a um elemento de aula.
 */
function aplicarCorAula(el, cor) {
    el.style.backgroundColor = cor + '22'; // 13% opacity
    el.style.borderLeftColor = cor;
    el.style.color = cor;
}

/**
 * Inicializa seletor de cores rápidas em formulários.
 */
function initColorPicker(inputId, swatchContainerId) {
    const input = document.getElementById(inputId);
    const container = document.getElementById(swatchContainerId);
    if (!input || !container) return;

    CORES_PREDEFINIDAS.forEach(c => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.title = c.nome;
        btn.style.cssText = `
      width: 24px; height: 24px; border-radius: 50%;
      background: ${c.hex}; border: 2px solid transparent;
      cursor: pointer; transition: transform 0.15s, border-color 0.15s;
    `;
        btn.addEventListener('click', () => {
            input.value = c.hex;
            // Atualiza borda de seleção
            container.querySelectorAll('button').forEach(b => b.style.borderColor = 'transparent');
            btn.style.borderColor = '#fff';
            btn.style.transform = 'scale(1.2)';
        });
        btn.addEventListener('mouseover', () => { btn.style.transform = 'scale(1.15)'; });
        btn.addEventListener('mouseout', () => {
            if (input.value !== c.hex) btn.style.transform = 'scale(1)';
        });
        container.appendChild(btn);
    });
}

// Inicializa ao carregar
document.addEventListener('DOMContentLoaded', () => {
    initColorPicker('cor-disciplina', 'swatches-disciplina');
    initColorPicker('cor-disciplina-edit', 'swatches-disciplina-edit');
});
