// Utilitários de interface compartilhados pelas páginas.

// Todo dado vindo da API deve passar por aqui antes de entrar em innerHTML (evita XSS).
export function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
    ));
}

/** Destaca o termo buscado: divide o texto original e escapa cada pedaço (o termo nunca vira HTML). */
export function highlightTerm(text, term) {
    const needle = term.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (!needle) return escapeHtml(text);
    return String(text).split(new RegExp(`(${needle})`, 'gi'))
        .map((piece, index) => index % 2 ? `<mark class="bg-amber-100 rounded px-0.5">${escapeHtml(piece)}</mark>` : escapeHtml(piece))
        .join('');
}

export function isValidUuid(value) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value).trim());
}

export const formatMoney = value =>
    new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value || 0));

export const formatDateTime = value => value ? new Date(value).toLocaleString('pt-BR') : '—';

export const formatDate = value => value ? new Date(value).toLocaleDateString('pt-BR') : '—';

export function openModal(id) { document.getElementById(id)?.classList.add('active'); }
export function closeModal(id) { document.getElementById(id)?.classList.remove('active'); }

/** Fecha modais por botão [data-close-modal], clique no fundo escurecido ou tecla Esc. */
export function enableModalDismiss() {
    document.addEventListener('click', event => {
        const closer = event.target.closest('[data-close-modal]');
        if (closer) closeModal(closer.dataset.closeModal);
        else if (event.target.classList.contains('modal')) event.target.classList.remove('active');
    });
    document.addEventListener('keydown', event => {
        // A tecla já tratada por um componente (ex.: Esc fechando a lista do seletor) não fecha o modal.
        if (event.key === 'Escape' && !event.defaultPrevented) {
            document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
        }
    });
}

/** Mostra uma mensagem de resultado (sucesso/erro) em um elemento de feedback. */
export function showResult(element, message, ok = true) {
    element.classList.remove('hidden', 'bg-green-100', 'text-green-700', 'bg-red-100', 'text-red-700');
    element.classList.add(...(ok ? ['bg-green-100', 'text-green-700'] : ['bg-red-100', 'text-red-700']));
    element.innerText = message;
}

/** Notificação flutuante temporária. */
export function toast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-4 right-4 z-[200] flex flex-col gap-2 max-w-sm';
        document.body.appendChild(container);
    }
    const colors = { info: 'bg-slate-800', success: 'bg-emerald-700', error: 'bg-red-600' };
    const item = document.createElement('div');
    item.className = `${colors[type] || colors.info} text-white text-sm px-4 py-3 rounded-lg shadow-lg`;
    item.setAttribute('role', 'status');
    item.innerText = message;
    container.appendChild(item);
    setTimeout(() => item.remove(), 4000);
}

/** Estado de carregamento padronizado para um contêiner. */
export function renderLoading(element, label = 'Carregando...') {
    element.innerHTML = `<p class="text-slate-500 text-center text-sm py-4"><i class="fas fa-spinner fa-spin mr-2"></i>${escapeHtml(label)}</p>`;
}

export function renderEmpty(element, label) {
    // Em listas, a mensagem precisa ser um item (<li>) para a marcação continuar válida.
    const tag = ['UL', 'OL'].includes(element.tagName) ? 'li' : 'p';
    element.innerHTML = `<${tag} class="text-slate-500 text-center text-sm py-4">${escapeHtml(label)}</${tag}>`;
}

/** Desativa o botão enquanto a ação corre, evitando envios duplicados. */
export async function whileBusy(button, action) {
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    try {
        return await action();
    } finally {
        button.disabled = false;
        button.removeAttribute('aria-busy');
    }
}
