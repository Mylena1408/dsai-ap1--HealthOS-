// Trilha de auditoria didática: filtros por tipo e período, paginação.
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDateTime, toast } from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { fillSelect } from '../core/labels.js';
import { renderPagination } from '../components/pagination.js';

const PAGE_SIZE = 25;
const $ = id => document.getElementById(id);
const state = { offset: 0 };
// Rótulo legível a partir do código (ex.: CONSULTA_AGENDADA -> "Consulta agendada").
const label = code => code.charAt(0) + code.slice(1).toLowerCase().replaceAll('_', ' ');

async function loadCounts() {
    const counts = await apiCall('/audit-events/counts');
    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    fillSelect($('f-type'), Object.fromEntries(entries.map(([code]) => [code, label(code)])), 'Todos');
    $('counts').innerHTML = entries.map(([code, total]) => `
        <button data-type="${escapeHtml(code)}" class="px-3 py-1 rounded-full border bg-white text-xs text-slate-700 hover:bg-slate-50">
            ${escapeHtml(label(code))} <strong class="tabular-nums">${total}</strong></button>`).join('');
}

async function load() {
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset: state.offset });
    if ($('f-type').value) params.set('event_type', $('f-type').value);
    if ($('f-from').value) params.set('date_from', $('f-from').value);
    if ($('f-to').value) params.set('date_to', $('f-to').value);
    const rows = $('rows');
    try {
        const page = await apiCall(`/audit-events?${params}`);
        rows.innerHTML = page.items.length ? page.items.map(e => `
            <tr class="border-b last:border-0 align-top">
                <td class="py-2 pr-3 whitespace-nowrap">${formatDateTime(e.occurred_at)}</td>
                <td class="py-2 pr-3 whitespace-nowrap font-medium">${escapeHtml(label(e.event_type))}</td>
                <td class="py-2 pr-3 text-slate-600">${escapeHtml(e.entity_type)}
                    ${e.patient_id ? `<a href="/app/prontuario?patient=${encodeURIComponent(e.patient_id)}" class="block text-xs text-blue-700 hover:underline">prontuário</a>` : ''}</td>
                <td class="py-2 text-slate-700">${escapeHtml(e.summary)}</td>
            </tr>`).join('') : '<tr><td colspan="4" class="py-4 text-center text-slate-500">Nenhum evento para os filtros escolhidos.</td></tr>';
        renderPagination($('pagination'), page, offset => { state.offset = offset; load(); });
    } catch (err) {
        toast(err.message, 'error');
    }
}

renderNav('auditoria');
renderDemoBanner();
$('filters').addEventListener('change', () => { state.offset = 0; load(); });
$('counts').addEventListener('click', event => {
    const chip = event.target.closest('[data-type]');
    if (!chip) return;
    $('f-type').value = chip.dataset.type;
    state.offset = 0;
    load();
});
loadCounts().then(load).catch(err => toast(err.message, 'error'));
