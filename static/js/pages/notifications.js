// Caixa de notificações do perfil de demonstração atual.
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDateTime, renderEmpty, renderLoading, toast } from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { fillSelect } from '../core/labels.js';
import { renderPagination } from '../components/pagination.js';
import { getProfile, inboxParams } from '../components/profile.js';

const PAGE_SIZE = 20;
const $ = id => document.getElementById(id);
const TABS = { NAO_LIDA: 'Não lidas', LIDA: 'Lidas', ARQUIVADA: 'Arquivadas' };
const CATEGORIES = { CONSULTA: 'Consulta', EXAME: 'Exame', MEDICAMENTO: 'Medicamento', ALERTA: 'Alerta',
                     FINANCEIRO: 'Financeiro', ADMINISTRATIVO: 'Administrativo' };
const ICONS = { CONSULTA: 'fa-calendar-check', EXAME: 'fa-vial', MEDICAMENTO: 'fa-pills', ALERTA: 'fa-triangle-exclamation',
                FINANCEIRO: 'fa-receipt', ADMINISTRATIVO: 'fa-building' };
const state = { status: 'NAO_LIDA', offset: 0 };

function actions(n) {
    const button = (action, label, icon) => `<button data-act="${action}" data-id="${escapeHtml(n.id)}"
        class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100"><i class="fas ${icon}" aria-hidden="true"></i> ${label}</button>`;
    if (n.status === 'NAO_LIDA') return button('read', 'Marcar como lida', 'fa-envelope-open') + button('archive', 'Arquivar', 'fa-box-archive');
    if (n.status === 'LIDA') return button('unread', 'Marcar como não lida', 'fa-envelope') + button('archive', 'Arquivar', 'fa-box-archive');
    return button('unarchive', 'Desarquivar', 'fa-box-open');
}

async function load() {
    const list = $('list');
    renderLoading(list);
    $('profile-name').textContent = getProfile().label;
    $('tabs').innerHTML = Object.entries(TABS).map(([status, label]) => `
        <button data-status="${status}" role="tab" aria-selected="${status === state.status}"
            class="px-3 py-2 rounded-lg text-sm font-bold ${status === state.status ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}">${label}</button>`).join('');
    const params = inboxParams();
    params.set('status', state.status);
    params.set('limit', PAGE_SIZE);
    params.set('offset', state.offset);
    if ($('category').value) params.set('category', $('category').value);
    try {
        const page = await apiCall(`/inbox?${params}`);
        if (!page.items.length) renderEmpty(list, 'Nenhuma notificação aqui.');
        else list.innerHTML = page.items.map(n => `
            <article class="glass-card rounded-2xl p-4 ${n.status === 'NAO_LIDA' ? 'border-l-4 border-l-blue-500' : ''}">
                <div class="flex items-start gap-3">
                    <i class="fas ${ICONS[n.category] || 'fa-bell'} text-slate-500 mt-1" aria-hidden="true"></i>
                    <div class="flex-1 min-w-0">
                        <div class="flex flex-wrap justify-between gap-2">
                            <strong class="text-slate-800">${escapeHtml(n.title)}</strong>
                            <span class="text-xs text-slate-500">${formatDateTime(n.created_at)}</span>
                        </div>
                        <p class="text-sm text-slate-600 mt-1">${escapeHtml(n.message)}</p>
                        <div class="flex flex-wrap items-center gap-2 mt-2">
                            <span class="text-xs text-slate-500">${escapeHtml(CATEGORIES[n.category] || n.category)}</span>
                            ${n.priority === 'ALTA' ? '<span class="flag flag-critical"><i class="fas fa-circle-exclamation" aria-hidden="true"></i>Prioridade alta</span>' : ''}
                            ${n.link ? `<a href="${escapeHtml(n.link)}" class="text-xs text-blue-700 font-semibold hover:underline">Abrir</a>` : ''}
                            <span class="flex gap-2 ml-auto">${actions(n)}</span>
                        </div>
                    </div>
                </div>
            </article>`).join('');
        renderPagination($('pagination'), page, offset => { state.offset = offset; load(); });
    } catch (err) {
        renderEmpty(list, `Erro: ${err.message}`);
    }
}

async function act(action, id) {
    try {
        await apiCall(`/inbox/${id}/${action}`, 'POST');
        window.dispatchEvent(new Event('healthos:inbox-changed'));
        load();
    } catch (err) {
        toast(err.message, 'error');
    }
}

renderNav('notificacoes');
renderDemoBanner();
fillSelect($('category'), CATEGORIES, 'Todas');
$('category').addEventListener('change', () => { state.offset = 0; load(); });
$('mark-all').addEventListener('click', async () => {
    try {
        const { updated } = await apiCall(`/inbox/mark-all-read?${inboxParams()}`, 'POST');
        toast(`${updated} notificação(ões) marcada(s) como lida(s).`, 'success');
        window.dispatchEvent(new Event('healthos:inbox-changed'));
        load();
    } catch (err) {
        toast(err.message, 'error');
    }
});
document.addEventListener('click', event => {
    const tab = event.target.closest('[data-status]');
    if (tab) { state.status = tab.dataset.status; state.offset = 0; return load(); }
    const action = event.target.closest('[data-act]');
    if (action) act(action.dataset.act, action.dataset.id);
});
window.addEventListener('healthos:profile', () => { state.offset = 0; load(); });
load();
