// Utilitários de interface compartilhados pelas páginas.

// Todo dado vindo da API deve passar por aqui antes de entrar em innerHTML (evita XSS).
export function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
    ));
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
    const colors = { info: 'bg-slate-800', success: 'bg-emerald-600', error: 'bg-red-600' };
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
    element.innerHTML = `<p class="text-slate-500 text-center text-sm py-4">${escapeHtml(label)}</p>`;
}
