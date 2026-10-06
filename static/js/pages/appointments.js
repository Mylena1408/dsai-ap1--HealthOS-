// Página de consultas: lista filtrável, calendário semanal, agendamento e transições de estado.
import { apiCall } from '../core/api.js';
import {
    closeModal, enableModalDismiss, escapeHtml, formatDateTime, openModal, renderEmpty, renderLoading, showResult, toast,
} from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import {
    APPOINTMENT_STATUS, APPOINTMENT_TYPES, TRANSITION_ACTIONS, WEEKDAYS, fillSelect, statusBadge,
} from '../core/labels.js';
import { renderPagination } from '../components/pagination.js';
import { createPatientPicker } from '../components/patient-picker.js';

const PAGE_SIZE = 15;
const RESCHEDULABLE = ['AGENDADA', 'CONFIRMADA'];
const $ = id => document.getElementById(id);
const state = { tab: 'list', offset: 0, weekStart: mondayOf(new Date()), byId: {}, pendingAction: null, rescheduleId: null };

// ------------------------------------------------------------------ datas

function mondayOf(date) {
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return d;
}
function addDays(date, days) { const d = new Date(date); d.setDate(d.getDate() + days); return d; }
// Data local no formato AAAA-MM-DD (toISOString usaria UTC e poderia mudar o dia).
function isoDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
const timeOf = value => new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

// --------------------------------------------------------------- renderização

function actionButtons(a) {
    const buttons = a.allowed_transitions.map(target => {
        const action = TRANSITION_ACTIONS[target];
        return `<button data-act="${action.path}" data-id="${escapeHtml(a.id)}" class="px-3 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">
            <i class="fas ${action.icon}"></i> ${action.label}</button>`;
    });
    if (RESCHEDULABLE.includes(a.status)) {
        buttons.push(`<button data-act="reschedule" data-id="${escapeHtml(a.id)}" class="px-3 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">
            <i class="fas fa-calendar-plus"></i> Remarcar</button>`);
    }
    buttons.push(`<button data-act="history" data-id="${escapeHtml(a.id)}" class="px-3 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">
        <i class="fas fa-clock-rotate-left"></i> Histórico</button>`);
    return buttons.join('');
}

function listItem(a) {
    return `
        <article class="glass-card rounded-2xl p-4 flex flex-col md:flex-row md:items-center gap-3">
            <div class="md:w-40 shrink-0">
                <div class="font-bold text-slate-800">${new Date(a.start_time).toLocaleDateString('pt-BR')}</div>
                <div class="text-sm text-slate-500">${timeOf(a.start_time)} – ${timeOf(a.end_time)}</div>
            </div>
            <div class="flex-1 min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                    <span class="font-semibold text-slate-800">${escapeHtml(a.patient_name || a.patient_id)}</span>
                    ${statusBadge(a.status)}
                </div>
                <div class="text-sm text-slate-600 truncate">${escapeHtml(a.professional_name || '')} · ${escapeHtml(APPOINTMENT_TYPES[a.appointment_type] || a.appointment_type)}
                    ${a.reason ? ` · ${escapeHtml(a.reason)}` : ''}</div>
            </div>
            <div class="flex flex-wrap gap-2">${actionButtons(a)}</div>
        </article>`;
}

async function loadList() {
    const list = $('list');
    renderLoading(list);
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset: state.offset, newest_first: 'false' });
    if ($('f-professional').value) params.set('professional_id', $('f-professional').value);
    if ($('f-status').value) params.set('status', $('f-status').value);
    if ($('f-from').value) params.set('date_from', $('f-from').value);
    if ($('f-to').value) params.set('date_to', $('f-to').value);
    try {
        const page = await apiCall(`/appointments?${params}`);
        remember(page.items);
        if (!page.items.length) renderEmpty(list, 'Nenhuma consulta encontrada para os filtros escolhidos.');
        else list.innerHTML = page.items.map(listItem).join('');
        renderPagination($('pagination'), page, offset => { state.offset = offset; loadList(); });
    } catch (err) {
        renderEmpty(list, `Erro ao carregar: ${err.message}`);
    }
}

async function loadCalendar() {
    const calendar = $('calendar');
    const professionalId = $('f-professional').value;
    const weekEnd = addDays(state.weekStart, 6);
    $('week-label').innerText = `${state.weekStart.toLocaleDateString('pt-BR')} – ${weekEnd.toLocaleDateString('pt-BR')}`;
    if (!professionalId) {
        calendar.innerHTML = '<div class="md:col-span-7"></div>';
        return renderEmpty(calendar.firstChild, 'Selecione um profissional para ver o calendário.');
    }
    renderLoading(calendar);
    try {
        const page = await apiCall(`/appointments?${new URLSearchParams({
            professional_id: professionalId, date_from: isoDate(state.weekStart), date_to: isoDate(weekEnd), limit: 200,
        })}`);
        remember(page.items);
        const today = isoDate(new Date());
        calendar.innerHTML = WEEKDAYS.map((day, index) => {
            const date = addDays(state.weekStart, index);
            const items = page.items.filter(a => a.start_time.slice(0, 10) === isoDate(date));
            const isToday = isoDate(date) === today;
            return `
                <div class="glass-card rounded-2xl p-3 min-h-[8rem] ${isToday ? 'ring-2 ring-blue-400' : ''}">
                    <div class="text-xs uppercase tracking-wide text-slate-500">${day}</div>
                    <div class="font-bold text-slate-800 mb-2">${date.getDate()}/${date.getMonth() + 1}</div>
                    <div class="space-y-2">
                        ${items.map(a => `
                            <button data-act="history" data-id="${escapeHtml(a.id)}" class="w-full text-left rounded-lg p-2 text-xs ${APPOINTMENT_STATUS[a.status]?.color || ''}">
                                <div class="font-bold">${timeOf(a.start_time)}</div>
                                <div class="truncate">${escapeHtml(a.patient_name || '')}</div>
                            </button>`).join('') || '<p class="text-xs text-slate-500">Sem consultas</p>'}
                    </div>
                </div>`;
        }).join('');
    } catch (err) {
        renderEmpty(calendar, `Erro ao carregar: ${err.message}`);
    }
}

function reload() { return state.tab === 'list' ? loadList() : loadCalendar(); }

function remember(items) { items.forEach(a => { state.byId[a.id] = a; }); }

function switchTab(tab) {
    state.tab = tab;
    document.querySelectorAll('[data-tab]').forEach(button => {
        const active = button.dataset.tab === tab;
        button.className = `tab px-4 py-2 rounded-lg text-sm font-bold transition-all ${active ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`;
        button.setAttribute('aria-selected', active);
    });
    $('view-list').classList.toggle('hidden', tab !== 'list');
    $('view-calendar').classList.toggle('hidden', tab !== 'calendar');
    document.querySelectorAll('.list-only').forEach(el => el.classList.toggle('hidden', tab !== 'list'));
    reload();
}

// ------------------------------------------------------------- horários livres

/** Mostra os horários livres como botões; `onPick(slot)` é chamado no clique. */
async function renderSlots(container, professionalId, date, onPick) {
    if (!professionalId || !date) return renderEmpty(container, 'Escolha profissional e data.');
    renderLoading(container, 'Buscando horários...');
    try {
        const slots = await apiCall(`/professionals/${professionalId}/availability?${new URLSearchParams({ date_from: date, days: 1 })}`);
        if (!slots.length) return renderEmpty(container, 'Sem horários livres nesta data.');
        container.innerHTML = slots.map((slot, index) => `
            <button type="button" data-slot="${index}" class="px-3 py-1 rounded-lg border text-sm hover:bg-blue-50">${timeOf(slot.start_time)}</button>`).join('');
        container.querySelectorAll('[data-slot]').forEach(button => button.addEventListener('click', () => {
            container.querySelectorAll('[data-slot]').forEach(b => b.classList.remove('bg-blue-600', 'text-white'));
            button.classList.add('bg-blue-600', 'text-white');
            onPick(slots[Number(button.dataset.slot)]);
        }));
    } catch (err) {
        renderEmpty(container, `Erro: ${err.message}`);
    }
}

// ------------------------------------------------------------------- ações

async function runAction(id, path, body = null) {
    try {
        const updated = await apiCall(`/appointments/${id}/${path}`, 'POST', body);
        toast(`Consulta: ${APPOINTMENT_STATUS[updated.status]?.label || updated.status}.`, 'success');
        reload();
    } catch (err) {
        toast(err.message, 'error');
    }
}

function askText(title, placeholder, required, onSubmit) {
    $('text-title').innerText = title;
    $('t-value').value = '';
    $('t-value').placeholder = placeholder;
    $('t-value').required = required;
    $('t-value').minLength = required ? 3 : 0;
    state.pendingAction = onSubmit;
    openModal('modal-text');
}

function showHistory(a) {
    $('history-body').innerHTML = a.history.map(h => `
        <li class="ml-4 relative">
            <span class="absolute -left-[1.4rem] top-1 w-3 h-3 rounded-full bg-blue-500" aria-hidden="true"></span>
            <div class="text-xs text-slate-500">${formatDateTime(h.changed_at)}</div>
            <div class="text-sm">${h.from_status ? `${statusBadge(h.from_status)} <i class="fas fa-arrow-right text-slate-500 mx-1"></i>` : ''}${statusBadge(h.to_status)}</div>
            ${h.note ? `<div class="text-sm text-slate-600 mt-1">${escapeHtml(h.note)}</div>` : ''}
        </li>`).join('') +
        `<li class="ml-4 text-sm text-slate-600 pt-2 border-t">${escapeHtml(a.patient_name || '')} com ${escapeHtml(a.professional_name || '')}
            em ${formatDateTime(a.start_time)}${a.notes ? `<br><span class="text-slate-500">Notas: ${escapeHtml(a.notes)}</span>` : ''}</li>`;
    openModal('modal-history');
}

function handleAction(path, id) {
    const appointment = state.byId[id];
    if (path === 'history') return showHistory(appointment);
    if (path === 'reschedule') {
        state.rescheduleId = id;
        $('r-date').value = appointment.start_time.slice(0, 10);
        openModal('modal-reschedule');
        return loadRescheduleSlots();
    }
    if (path === 'cancel') {
        return askText('Motivo do cancelamento', 'Ex.: paciente solicitou remarcação', true,
            reason => runAction(id, 'cancel', { reason }));
    }
    if (path === 'complete') {
        return askText('Finalizar atendimento', 'Notas do atendimento (opcional, fictícias)', false,
            notes => runAction(id, 'complete', notes ? { notes } : null));
    }
    runAction(id, path);
}

function loadRescheduleSlots() {
    const appointment = state.byId[state.rescheduleId];
    renderSlots($('r-slots'), appointment.professional_id, $('r-date').value, async slot => {
        closeModal('modal-reschedule');
        await runAction(appointment.id, 'reschedule', { start_time: slot.start_time });
    });
}

// --------------------------------------------------------------- formulários

let pickedSlot = null;

function refreshNewSlots() {
    pickedSlot = null;
    renderSlots($('n-slots'), $('n-professional').value, $('n-date').value, slot => { pickedSlot = slot; });
}

async function setupNewForm(professionals) {
    const patientPicker = createPatientPicker($('n-patient'));
    fillSelect($('n-professional'), professionals, 'Selecione o profissional');
    fillSelect($('n-type'), APPOINTMENT_TYPES);
    $('n-date').min = isoDate(new Date());
    $('n-date').value = isoDate(addDays(new Date(), 1));
    $('n-professional').addEventListener('change', refreshNewSlots);
    $('n-date').addEventListener('change', refreshNewSlots);

    $('btn-new').addEventListener('click', async () => {
        if ($('f-professional').value) $('n-professional').value = $('f-professional').value;
        openModal('modal-new');
        refreshNewSlots();
    });

    $('form-new').addEventListener('submit', async event => {
        event.preventDefault();
        if (!patientPicker.value) return showResult($('res-new'), 'Selecione um paciente da lista de sugestões.', false);
        if (!pickedSlot) return showResult($('res-new'), 'Escolha um dos horários livres.', false);
        try {
            const created = await apiCall('/appointments', 'POST', {
                patient_id: patientPicker.value.id, professional_id: $('n-professional').value,
                start_time: pickedSlot.start_time, appointment_type: $('n-type').value,
                reason: $('n-reason').value.trim() || null,
            });
            showResult($('res-new'), `Consulta agendada para ${formatDateTime(created.start_time)}.`);
            toast('Consulta agendada.', 'success');
            refreshNewSlots();
            reload();
        } catch (err) {
            showResult($('res-new'), `Erro: ${err.message}`, false);
        }
    });
}

async function init() {
    renderNav('consultas');
    renderDemoBanner();
    enableModalDismiss();

    fillSelect($('f-status'), APPOINTMENT_STATUS, 'Todas');
    const page = await apiCall('/professionals?limit=100&status=ATIVO');
    const professionals = Object.fromEntries(page.items.map(p => [p.id, `${p.full_name}${p.specialty_name ? ` — ${p.specialty_name}` : ''}`]));
    fillSelect($('f-professional'), professionals, 'Todos os profissionais');
    await setupNewForm(professionals);

    $('filters').addEventListener('change', () => { state.offset = 0; reload(); });
    $('filters').addEventListener('submit', event => event.preventDefault());
    $('week-prev').addEventListener('click', () => { state.weekStart = addDays(state.weekStart, -7); loadCalendar(); });
    $('week-next').addEventListener('click', () => { state.weekStart = addDays(state.weekStart, 7); loadCalendar(); });
    $('r-date').addEventListener('change', loadRescheduleSlots);
    $('form-text').addEventListener('submit', event => {
        event.preventDefault();
        closeModal('modal-text');
        state.pendingAction?.($('t-value').value.trim());
    });
    document.addEventListener('click', event => {
        const tab = event.target.closest('[data-tab]');
        if (tab) switchTab(tab.dataset.tab);
        const action = event.target.closest('[data-act]');
        if (action) handleAction(action.dataset.act, action.dataset.id);
    });

    // /app/consultas?professional=<id> abre direto o calendário daquele profissional.
    const preselected = new URLSearchParams(window.location.search).get('professional');
    if (preselected && professionals[preselected]) {
        $('f-professional').value = preselected;
        switchTab('calendar');
    } else {
        switchTab('list');
    }
}

init().catch(err => toast(err.message, 'error'));
