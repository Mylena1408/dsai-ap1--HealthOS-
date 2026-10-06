// Página de profissionais: listagem com filtros, detalhes e cadastro.
import { apiCall } from '../core/api.js';
import {
    escapeHtml, enableModalDismiss, formatDateTime, openModal, renderEmpty, renderLoading, showResult, toast,
} from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { PROFESSIONAL_STATUS, PROFESSIONAL_TYPES, WEEKDAYS, fillSelect } from '../core/labels.js';
import { renderPagination } from '../components/pagination.js';

const PAGE_SIZE = 12;
const $ = id => document.getElementById(id);
const state = { offset: 0, specialties: [], departments: [], byId: {} };

const hhmm = value => String(value).slice(0, 5);

function card(p) {
    const statusColor = p.status === 'ATIVO' ? 'text-emerald-700' : 'text-amber-700';
    return `
        <button type="button" data-id="${escapeHtml(p.id)}" class="glass-card rounded-2xl p-5 text-left hover:border-blue-500 transition-all">
            <div class="flex items-start justify-between gap-2 mb-2">
                <h2 class="font-bold text-slate-800">${escapeHtml(p.full_name)}</h2>
                <span class="text-xs font-semibold ${statusColor}">${escapeHtml(PROFESSIONAL_STATUS[p.status] || p.status)}</span>
            </div>
            <p class="text-sm text-slate-600">${escapeHtml(PROFESSIONAL_TYPES[p.professional_type] || p.professional_type)}
                ${p.specialty_name ? `· ${escapeHtml(p.specialty_name)}` : ''}</p>
            <p class="text-xs text-slate-500 mt-1">${escapeHtml(p.registry_number)}${p.department_name ? ` · ${escapeHtml(p.department_name)}` : ''}</p>
            <p class="text-xs text-slate-500 mt-3"><i class="far fa-clock"></i>
                ${p.working_hours.length ? `${new Set(p.working_hours.map(h => h.weekday)).size} dia(s) de atendimento` : 'Sem grade cadastrada'}</p>
        </button>`;
}

async function load() {
    const list = $('list');
    renderLoading(list);
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset: state.offset });
    const filters = { q: $('f-q').value.trim(), professional_type: $('f-type').value,
                      specialty_id: $('f-specialty').value, status: $('f-status').value };
    Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));

    try {
        const page = await apiCall(`/professionals?${params}`);
        if (!page.items.length) renderEmpty(list, 'Nenhum profissional encontrado com esses filtros.');
        else list.innerHTML = page.items.map(card).join('');
        state.byId = Object.fromEntries(page.items.map(p => [p.id, p]));
        renderPagination($('pagination'), page, offset => { state.offset = offset; load(); });
    } catch (err) {
        renderEmpty(list, `Erro ao carregar: ${err.message}`);
    }
}

function showDetail(p) {
    const byDay = WEEKDAYS.map((day, index) => {
        const windows = p.working_hours.filter(h => h.weekday === index);
        return `<tr class="border-b last:border-0"><td class="py-1 pr-4 text-slate-600">${day}</td>
            <td class="py-1">${windows.length ? windows.map(h => `${hhmm(h.start_time)}–${hhmm(h.end_time)}`).join(', ') : '<span class="text-slate-500">—</span>'}</td></tr>`;
    }).join('');
    $('detail-body').innerHTML = `
        <h3 id="detail-title" class="text-2xl font-bold text-slate-800">${escapeHtml(p.full_name)}</h3>
        <p class="text-slate-600 mb-4">${escapeHtml(PROFESSIONAL_TYPES[p.professional_type] || '')}
            ${p.specialty_name ? `· ${escapeHtml(p.specialty_name)}` : ''}</p>
        <dl class="grid grid-cols-2 gap-2 text-sm mb-4">
            <dt class="text-slate-500">Registro</dt><dd>${escapeHtml(p.registry_number)}</dd>
            <dt class="text-slate-500">Departamento</dt><dd>${escapeHtml(p.department_name || '—')}</dd>
            <dt class="text-slate-500">Situação</dt><dd>${escapeHtml(PROFESSIONAL_STATUS[p.status] || p.status)}</dd>
            <dt class="text-slate-500">E-mail</dt><dd class="break-all">${escapeHtml(p.email || '—')}</dd>
        </dl>
        <h4 class="font-semibold text-slate-700 mb-2">Grade semanal</h4>
        <table class="w-full text-sm mb-6"><tbody>${byDay}</tbody></table>
        <h4 class="font-semibold text-slate-700 mb-2">Histórico de atividades</h4>
        <div id="detail-activity" class="mb-6" aria-live="polite"></div>
        <a href="/app/consultas?professional=${encodeURIComponent(p.id)}" class="block text-center w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700">
            <i class="fas fa-calendar-days"></i> Ver agenda</a>`;
    openModal('modal-detail');
    loadActivity(p.id);
}

const ACTIVITY = {
    CONSULTA: { label: 'Consultas', icon: 'fa-calendar-check' },
    SINAIS_VITAIS: { label: 'Sinais vitais', icon: 'fa-heart-pulse' },
    PRESCRICAO: { label: 'Prescrições', icon: 'fa-prescription' },
    DISPENSACAO: { label: 'Dispensações', icon: 'fa-pills' },
    EXAME_SOLICITADO: { label: 'Exames solicitados', icon: 'fa-vial' },
    EXAME_VALIDADO: { label: 'Exames validados', icon: 'fa-check-double' },
};

async function loadActivity(professionalId) {
    const target = $('detail-activity');
    renderLoading(target);
    try {
        const data = await apiCall(`/professionals/${professionalId}/activity?limit=15`);
        const totals = Object.entries(data.totals);
        if (!totals.length) return renderEmpty(target, 'Nenhuma atividade registrada por este profissional.');
        target.innerHTML = `
            <div class="flex flex-wrap gap-2 mb-3">${totals.map(([kind, total]) => `
                <span class="text-xs font-semibold px-2 py-1 rounded-full bg-slate-100 text-slate-700">
                    <i class="fas ${ACTIVITY[kind]?.icon || 'fa-circle'}" aria-hidden="true"></i>
                    ${escapeHtml(ACTIVITY[kind]?.label || kind)}: <span class="tabular-nums">${total}</span></span>`).join('')}</div>
            <ul class="divide-y text-sm max-h-72 overflow-y-auto">${data.items.map(item => `
                <li class="py-2">
                    <div class="flex justify-between gap-2"><span class="text-slate-800">${escapeHtml(item.description)}</span>
                        <span class="text-xs text-slate-500 whitespace-nowrap">${formatDateTime(item.occurred_at)}</span></div>
                    ${item.patient_id ? `<a href="/app/prontuario?patient=${encodeURIComponent(item.patient_id)}"
                        class="text-xs text-blue-700 hover:underline">${escapeHtml(item.patient_name || 'Paciente')}</a>` : ''}
                </li>`).join('')}</ul>`;
    } catch (err) {
        renderEmpty(target, `Erro: ${err.message}`);
    }
}

async function loadCatalogs() {
    [state.departments, state.specialties] = await Promise.all([apiCall('/departments'), apiCall('/specialties')]);
    const specialtyOptions = Object.fromEntries(state.specialties.map(s => [s.id, s.name]));
    fillSelect($('f-specialty'), specialtyOptions, 'Todas as especialidades');
    fillSelect($('n-specialty'), specialtyOptions, 'Especialidade (opcional)');
    fillSelect($('n-department'), Object.fromEntries(state.departments.map(d => [d.id, d.name])), 'Departamento (opcional)');
}

function setupForm() {
    fillSelect($('n-type'), PROFESSIONAL_TYPES);
    $('n-weekdays').innerHTML = WEEKDAYS.map((day, index) => `
        <label class="text-sm flex items-center gap-1 border rounded-lg px-2 py-1">
            <input type="checkbox" value="${index}" ${index < 5 ? 'checked' : ''}> ${day.slice(0, 3)}</label>`).join('');

    $('form-new').addEventListener('submit', async event => {
        event.preventDefault();
        const weekdays = [...$('n-weekdays').querySelectorAll('input:checked')].map(input => Number(input.value));
        const body = {
            full_name: $('n-name').value.trim(),
            professional_type: $('n-type').value,
            registry_number: $('n-registry').value.trim(),
            department_id: $('n-department').value || null,
            specialty_id: $('n-specialty').value || null,
            email: $('n-email').value.trim() || null,
            working_hours: weekdays.map(weekday => ({ weekday, start_time: $('n-start').value, end_time: $('n-end').value })),
        };
        try {
            const created = await apiCall('/professionals', 'POST', body);
            showResult($('res-new'), `Profissional cadastrado: ${created.full_name}`);
            toast('Profissional cadastrado.', 'success');
            event.target.reset();
            state.offset = 0;
            load();
        } catch (err) {
            showResult($('res-new'), `Erro: ${err.message}`, false);
        }
    });
}

function setupFilters() {
    fillSelect($('f-type'), PROFESSIONAL_TYPES, 'Todos os tipos');
    fillSelect($('f-status'), PROFESSIONAL_STATUS, 'Qualquer situação');
    let debounce;
    $('filters').addEventListener('input', () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => { state.offset = 0; load(); }, 300);
    });
    $('filters').addEventListener('submit', event => event.preventDefault());
}

renderNav('profissionais');
renderDemoBanner();
enableModalDismiss();
document.addEventListener('click', event => {
    const opener = event.target.closest('[data-open-modal]');
    if (opener) openModal(opener.dataset.openModal);
    const cardButton = event.target.closest('#list [data-id]');
    if (cardButton) showDetail(state.byId[cardButton.dataset.id]);
});
setupFilters();
setupForm();
loadCatalogs().catch(err => toast(err.message, 'error'));
load();
