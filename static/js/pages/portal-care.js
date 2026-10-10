// Visões Enfermagem e Psicologia do portal, ligadas só às rotas existentes
// (spec 2026-10-10-portal-enfermagem-psicologia). Sem senha nem bloqueio (ADR-002).
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDate, formatDateTime, renderEmpty, showResult, whileBusy } from '../core/dom.js';
import { CONDITION_STATUS, EVOLUTION_STATUS, ROUTES, badge, statusBadge } from '../core/labels.js';
import { activeProfessionals } from '../core/professionals.js';
import { getProfile } from '../components/profile.js';

const $ = id => document.getElementById(id);
const DAY_STATUSES = ['AGENDADA', 'CONFIRMADA', 'EM_ANDAMENTO', 'FINALIZADA'];
const APPOINTMENT_ACTIONS = { CONFIRMADA: ['confirm', 'Confirmar'], EM_ANDAMENTO: ['start', 'Iniciar'], FINALIZADA: ['complete', 'Finalizar'] };

const localDate = (date = new Date()) =>
    `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const addDays = days => new Date(Date.now() + days * 864e5);
const time = value => new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
const recordLink = (patientId, name) => patientId ? `<a href="/app/prontuario?patient=${encodeURIComponent(patientId)}"
    class="text-xs font-semibold text-blue-700 hover:underline whitespace-nowrap">Abrir prontuário<span class="sr-only"> de ${escapeHtml(name || 'paciente')}</span></a>` : '';
const numberOf = id => ($(id).value === '' ? null : Number($(id).value));
const query = (base, repeated = {}) => {
    const params = new URLSearchParams(base);
    Object.entries(repeated).forEach(([key, values]) => values.forEach(value => params.append(key, value)));
    return params;
};

const ACTIVE_STATUSES = ['AGENDADA', 'CONFIRMADA', 'EM_ANDAMENTO'];

/**
 * Tira dos horários livres do profissional os que coincidem com uma consulta ativa do paciente
 * (o servidor recusaria a sobreposição). Sem paciente, devolve todos.
 */
export async function freeSlotsForPatient(slots, patientId) {
    if (!patientId || !slots.length) return slots;
    const page = await apiCall(`/appointments?${query({ patient_id: patientId, limit: 200 }, { status: ACTIVE_STATUSES })}`);
    const busy = page.items.map(a => [new Date(a.start_time).getTime(), new Date(a.end_time).getTime()]);
    return slots.filter(slot => {
        const start = new Date(slot.start_time).getTime();
        const end = new Date(slot.end_time).getTime();
        return !busy.some(([busyStart, busyEnd]) => start < busyEnd && end > busyStart);
    });
}

let requirePatient = () => { throw new Error('Escolha o paciente pelo nome ou CPF.'); };
let currentPatient = () => null;

/** Formulário com envio único e resultado junto da operação. */
function bindCareForm(formId, resultId, handler) {
    $(formId).addEventListener('submit', async event => {
        event.preventDefault();
        await whileBusy(event.target.querySelector('[type="submit"]'), async () => {
            try {
                showResult($(resultId), await handler(), true);
            } catch (err) {
                showResult($(resultId), `Erro: ${err.message}`, false);
            }
        });
    });
}

/** Seletor de profissionais de um tipo, já escolhido pelo perfil quando ele é desse tipo. */
async function fillTypedSelect(select) {
    try {
        const professionals = (await activeProfessionals()).filter(p => p.professional_type === select.dataset.careType);
        select.innerHTML = '<option value="">Selecione</option>' + professionals.map(p =>
            `<option value="${escapeHtml(p.id)}">${escapeHtml(p.full_name)}${p.specialty_name ? ` — ${escapeHtml(p.specialty_name)}` : ''}</option>`).join('');
        const profile = getProfile();
        if (profile.audience === 'PROFISSIONAL' && professionals.some(p => p.id === profile.recipient_id)) select.value = profile.recipient_id;
    } catch {
        select.innerHTML = '<option value="">Lista indisponível</option>';
    }
}

// ----------------------------------------------------------------- Enfermagem

async function loadNursingDay() {
    const list = $('n-day');
    try {
        const today = localDate();
        const page = await apiCall(`/appointments?${query({ date_from: today, date_to: today, limit: 200 }, { status: DAY_STATUSES })}`);
        const items = [...page.items].sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
        if (!items.length) return renderEmpty(list, 'Nenhuma consulta hoje.');
        list.innerHTML = items.map(a => `<li class="py-2 flex flex-wrap justify-between items-center gap-2">
            <span>${time(a.start_time)} · <strong>${escapeHtml(a.patient_name || '')}</strong>
                <span class="text-slate-600">· ${escapeHtml(a.professional_name || '')}</span></span>
            <span class="flex items-center gap-2">${statusBadge(a.status)}${recordLink(a.patient_id, a.patient_name)}</span></li>`).join('');
    } catch (err) {
        renderEmpty(list, `Erro: ${err.message}`);
    }
}

async function loadNursingAlerts() {
    const list = $('n-alerts');
    try {
        const page = await apiCall(`/alerts?${query({ rule_code: 'SINAL_VITAL_CRITICO', limit: 10 }, { status: ['ATIVO', 'RECONHECIDO'] })}`);
        if (!page.items.length) return renderEmpty(list, 'Nenhum sinal vital crítico em aberto.');
        list.innerHTML = page.items.map(a => `<li class="py-2 space-y-1">
            <div class="flex flex-wrap justify-between items-center gap-2">
                <span class="flag ${a.level === 'CRITICO' ? 'flag-critical' : 'flag-attention'}"><i class="fas ${a.level === 'CRITICO' ? 'fa-triangle-exclamation' : 'fa-circle-exclamation'}" aria-hidden="true"></i>${a.level === 'CRITICO' ? 'Crítico' : 'Atenção'}</span>
                ${recordLink(a.patient_id)}</div>
            <div class="text-slate-800">${escapeHtml(a.message)}</div></li>`).join('');
    } catch (err) {
        renderEmpty(list, `Erro: ${err.message}`);
    }
}

async function loadNursingMeds() {
    const list = $('n-meds');
    try {
        const meds = await apiCall(`/patients/${requirePatient()}/medications`);
        const inUse = meds.filter(m => m.status === 'EM_USO');
        if (!inUse.length) return renderEmpty(list, 'Nenhum medicamento em uso.');
        list.innerHTML = inUse.map(m => `<li class="py-2"><strong>${escapeHtml(m.medication_name || '')}</strong>
            · ${escapeHtml(m.dose)}, ${escapeHtml(m.frequency)} · ${escapeHtml(ROUTES[m.route] || m.route)}</li>`).join('');
    } catch (err) {
        renderEmpty(list, `Erro: ${err.message}`);
    }
}

function bindNursingForms() {
    bindCareForm('form-n-vitals', 'res-n-vitals', async () => {
        const body = {
            systolic: numberOf('n-sys'), diastolic: numberOf('n-dia'), heart_rate: numberOf('n-hr'),
            respiratory_rate: numberOf('n-rr'), temperature: numberOf('n-temp'), oxygen_saturation: numberOf('n-spo2'),
            glucose_mg_dl: numberOf('n-glucose'), professional_id: $('n-author').value || null,
        };
        await apiCall(`/patients/${requirePatient()}/vital-signs`, 'POST', body);
        loadNursingAlerts();
        return 'Medição registrada. Ela aparece no prontuário (Sinais vitais) e na linha do tempo.';
    });
    bindCareForm('form-n-procedure', 'res-n-procedure', async () => {
        await apiCall(`/patients/${requirePatient()}/procedures`, 'POST', {
            name: $('n-procedure-name').value, performed_at: $('n-procedure-date').value,
            notes: $('n-procedure-notes').value || null, professional_id: $('n-author').value || null,
        });
        return 'Procedimento registrado no prontuário.';
    });
    bindCareForm('form-n-evolution', 'res-n-evolution', async () => {
        if (!$('n-author').value) throw new Error('Escolha o profissional de enfermagem.');
        await apiCall(`/patients/${requirePatient()}/evolutions`, 'POST', {
            professional_id: $('n-author').value, content: $('n-evolution-content').value,
        });
        return 'Evolução salva como rascunho. Assine no prontuário, aba Evolução.';
    });
}

// ------------------------------------------------------------------ Psicologia

async function loadPsychologyAgenda() {
    const list = $('ps-agenda');
    const professionalId = $('ps-professional').value;
    if (!professionalId) return renderEmpty(list, 'Escolha o(a) psicólogo(a).');
    try {
        const page = await apiCall(`/appointments?${query({
            professional_id: professionalId, date_from: localDate(), date_to: localDate(addDays(7)), limit: 100 })}`);
        const items = [...page.items].sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
        if (!items.length) return renderEmpty(list, 'Nenhuma sessão nos próximos 7 dias.');
        list.innerHTML = items.map(a => `<li class="py-2 flex flex-wrap justify-between items-center gap-2" data-appointment="${escapeHtml(a.id)}">
            <span>${formatDateTime(a.start_time)} · <strong>${escapeHtml(a.patient_name || '')}</strong>${a.reason ? ` <span class="text-slate-600">· ${escapeHtml(a.reason)}</span>` : ''}</span>
            <span class="flex flex-wrap items-center gap-2">${statusBadge(a.status)}
                ${a.allowed_transitions.filter(s => APPOINTMENT_ACTIONS[s]).map(s => `<button type="button" data-appointment-action="${APPOINTMENT_ACTIONS[s][0]}"
                    class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">${APPOINTMENT_ACTIONS[s][1]}</button>`).join('')}
                ${recordLink(a.patient_id, a.patient_name)}</span></li>`).join('');
    } catch (err) {
        renderEmpty(list, `Erro: ${err.message}`);
    }
}

async function loadPsychologySlots() {
    const select = $('ps-slot');
    const professionalId = $('ps-professional').value;
    if (!professionalId) {
        select.innerHTML = '<option value="">Escolha o(a) psicólogo(a)</option>';
        return;
    }
    select.innerHTML = '<option value="">Carregando horários...</option>';
    try {
        const all = await apiCall(`/professionals/${encodeURIComponent(professionalId)}/availability?days=7`);
        const slots = await freeSlotsForPatient(all, currentPatient()?.id);
        if (!slots.length) {
            select.innerHTML = `<option value="">${all.length ? 'Sem horários livres para este paciente nos próximos 7 dias'
                : 'Sem horários livres nos próximos 7 dias'}</option>`;
            return;
        }
        const days = new Map();
        slots.forEach(slot => {
            const day = new Date(slot.start_time).toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: '2-digit' });
            if (!days.has(day)) days.set(day, []);
            days.get(day).push(`<option value="${escapeHtml(slot.start_time)}">${time(slot.start_time)} às ${time(slot.end_time)}</option>`);
        });
        select.innerHTML = '<option value="">Selecione um horário</option>'
            + [...days].map(([day, options]) => `<optgroup label="${escapeHtml(day)}">${options.join('')}</optgroup>`).join('');
    } catch (err) {
        select.innerHTML = '<option value="">Erro ao carregar horários</option>';
    }
}

async function loadPsychologyHistory() {
    const box = $('ps-history');
    const patient = currentPatient();
    if (!patient) return renderEmpty(box, 'Escolha o paciente pelo nome ou CPF.');
    try {
        const [evolutions, conditions] = await Promise.all([
            apiCall(`/patients/${patient.id}/evolutions`), apiCall(`/patients/${patient.id}/conditions`),
        ]);
        box.innerHTML = `
            <div><h3 class="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-1">Evoluções</h3>
                ${evolutions.length ? `<ul class="divide-y">${evolutions.map(e => `<li class="py-2" data-evolution="${escapeHtml(e.id)}">
                    <div class="flex flex-wrap justify-between items-center gap-2">
                        <span class="text-slate-600">${formatDateTime(e.created_at)} · ${escapeHtml(e.professional_name || '')}</span>
                        <span class="flex items-center gap-2">${badge(EVOLUTION_STATUS, e.status)}
                            ${e.status === 'RASCUNHO' ? '<button type="button" data-evolution-sign class="px-2 py-1 rounded-lg border text-xs font-semibold text-emerald-700 hover:bg-slate-100">Assinar</button>' : ''}</span>
                    </div>
                    <p class="text-slate-800 whitespace-pre-line mt-1">${escapeHtml(e.content)}</p></li>`).join('')}</ul>`
                    : '<p class="text-slate-500">Nenhuma evolução.</p>'}</div>
            <div><h3 class="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-1">Queixas e condições</h3>
                ${conditions.length ? `<ul class="space-y-1">${conditions.map(c => `<li class="flex flex-wrap justify-between gap-2">
                    <span>${escapeHtml(c.name)}${c.onset_date ? ` <span class="text-slate-600">· desde ${formatDate(`${c.onset_date}T12:00`)}</span>` : ''}</span>
                    ${badge(CONDITION_STATUS, c.status)}</li>`).join('')}</ul>` : '<p class="text-slate-500">Nenhuma condição registrada.</p>'}</div>`;
    } catch (err) {
        renderEmpty(box, `Erro: ${err.message}`);
    }
}

function bindPsychologyForms() {
    bindCareForm('form-ps-schedule', 'res-ps-schedule', async () => {
        const patientId = requirePatient();
        if (!$('ps-professional').value || !$('ps-slot').value) throw new Error('Escolha o(a) psicólogo(a) e um horário livre.');
        const appointment = await apiCall('/appointments', 'POST', {
            patient_id: patientId, professional_id: $('ps-professional').value, start_time: $('ps-slot').value,
            appointment_type: $('ps-type').value, reason: $('ps-reason').value.trim() || null,
        });
        loadPsychologySlots();
        loadPsychologyAgenda();
        return `Sessão agendada para ${formatDateTime(appointment.start_time)}.`;
    });
    bindCareForm('form-ps-evolution', 'res-ps-evolution', async () => {
        if (!$('ps-professional').value) throw new Error('Escolha o(a) psicólogo(a).');
        await apiCall(`/patients/${requirePatient()}/evolutions`, 'POST', {
            professional_id: $('ps-professional').value, content: $('ps-evolution-content').value,
        });
        loadPsychologyHistory();
        return 'Evolução salva como rascunho. Assine no histórico ao lado.';
    });
    bindCareForm('form-ps-condition', 'res-ps-condition', async () => {
        await apiCall(`/patients/${requirePatient()}/conditions`, 'POST', {
            name: $('ps-condition-name').value, onset_date: $('ps-condition-onset').value || null,
        });
        loadPsychologyHistory();
        return 'Condição registrada no prontuário.';
    });
    $('ps-condition-onset').max = localDate();

    $('ps-agenda').addEventListener('click', async event => {
        const button = event.target.closest('[data-appointment-action]');
        if (!button) return;
        const id = button.closest('[data-appointment]').dataset.appointment;
        await whileBusy(button, async () => {
            try {
                await apiCall(`/appointments/${id}/${button.dataset.appointmentAction}`, 'POST', {});
            } catch (err) {
                showResult($('res-ps-schedule'), `Erro: ${err.message}`, false);
            }
        });
        loadPsychologyAgenda();
    });
    $('ps-history').addEventListener('click', async event => {
        const button = event.target.closest('[data-evolution-sign]');
        const patient = currentPatient();
        if (!button || !patient) return;
        if (!window.confirm('Assinar esta evolução? Depois de assinada, ela não poderá ser alterada.')) return;
        const id = button.closest('[data-evolution]').dataset.evolution;
        await whileBusy(button, async () => {
            try {
                await apiCall(`/patients/${patient.id}/evolutions/${id}/sign`, 'POST');
            } catch (err) {
                showResult($('res-ps-evolution'), `Erro: ${err.message}`, false);
            }
        });
        loadPsychologyHistory();
    });
    $('ps-professional').addEventListener('change', () => { loadPsychologySlots(); loadPsychologyAgenda(); });
}

// ------------------------------------------------------------------ ligação

const ACTIONS = {
    'nursing-day': loadNursingDay, 'nursing-alerts': loadNursingAlerts, 'nursing-meds': loadNursingMeds,
    'psy-agenda': loadPsychologyAgenda, 'psy-history': loadPsychologyHistory,
};

/** Carrega o conteúdo de uma visão quando ela é aberta. */
export function onCareViewShown(view) {
    if (view === 'nursing') { loadNursingDay(); loadNursingAlerts(); }
    if (view === 'psychology') { loadPsychologyAgenda(); loadPsychologySlots(); loadPsychologyHistory(); }
}

/** `requirePatient`/`getPatient` vêm do portal: o paciente escolhido vale para todas as visões. */
export async function initCareViews({ requirePatient: require, getPatient }) {
    requirePatient = require;
    currentPatient = getPatient;
    bindNursingForms();
    bindPsychologyForms();
    document.addEventListener('click', event => {
        const action = event.target.closest('[data-care-action]');
        if (action) ACTIONS[action.dataset.careAction]?.();
    });
    document.addEventListener('portal:patient', () => {
        if (!$('grid-psychology').classList.contains('hidden')) { loadPsychologyHistory(); loadPsychologySlots(); }
        $('n-meds').innerHTML = '';
    });
    await Promise.all([...document.querySelectorAll('[data-care-type]')].map(fillTypedSelect));
}
