// Portal do Paciente / Médico (página inicial). O paciente é escolhido por nome ou CPF e o médico
// numa lista, sem IDs digitados (Fase 6); a agenda usa as consultas novas (L1, docs/INTEGRACOES.md).
import { apiCall } from '../core/api.js';
import {
    escapeHtml, formatMoney, openModal, enableModalDismiss, showResult, renderEmpty,
} from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { createPatientPicker } from '../components/patient-picker.js';
import { getProfile } from '../components/profile.js';
import { statusBadge } from '../core/labels.js';

const ACTIVE_TAB = 'px-4 py-2 rounded-lg text-sm font-bold transition-all bg-blue-600 text-white';
const INACTIVE_TAB = 'px-4 py-2 rounded-lg text-sm font-bold transition-all text-slate-600 hover:bg-slate-100';
const NO_PATIENT = 'Escolha o paciente pelo nome ou CPF.';

const $ = id => document.getElementById(id);
// O paciente escolhido vale para todos os formulários e fica só na memória da página (R6).
const state = { patient: null };

function setPatient(patient) {
    state.patient = patient;
    document.querySelectorAll('[data-portal-patient]').forEach(input => { input.value = patient?.full_name || ''; });
}

function requirePatient() {
    if (!state.patient) throw new Error(NO_PATIENT);
    return state.patient.id;
}

function enablePatientFields() {
    document.querySelectorAll('[data-portal-patient]').forEach(input => {
        createPatientPicker(input, { onSelect: patient => setPatient(patient) });
        // Texto alterado sem escolher na lista: a escolha anterior deixa de valer.
        input.addEventListener('input', () => {
            if (state.patient && input.value !== state.patient.full_name) state.patient = null;
        });
    });
}

/** Lista de resultados: mensagem de erro no lugar da lista (sem alert()). */
function listError(element, message) {
    element.className = 'mt-6 text-sm p-3 rounded-lg bg-red-100 text-red-700';
    element.textContent = message;
}

function listReady(element, base) {
    element.className = base;
    element.innerHTML = '';
}

function switchView(view) {
    const isPatient = view === 'patient';
    $('grid-patient').classList.toggle('hidden', !isPatient);
    $('grid-doctor').classList.toggle('hidden', isPatient);
    $('btn-view-patient').className = isPatient ? ACTIVE_TAB : INACTIVE_TAB;
    $('btn-view-doctor').className = isPatient ? INACTIVE_TAB : ACTIVE_TAB;
    $('page-title').innerText = isPatient ? 'Portal do Paciente' : 'Portal do Médico';
    $('page-subtitle').innerText = isPatient
        ? 'Demonstração de serviços integrados para o usuário final.'
        : 'Gestão clínica e acompanhamento de pacientes.';
}

/** Visão e paciente iniciais acompanham o perfil de demonstração. */
function applyProfile() {
    const profile = getProfile();
    switchView(profile.audience === 'PROFISSIONAL' ? 'doctor' : 'patient');
    // Outro perfil não herda o paciente do anterior (evita gravar no paciente errado).
    setPatient(profile.audience === 'PACIENTE' ? { id: profile.recipient_id, full_name: profile.label } : null);
    document.querySelectorAll('[data-doctor-select]').forEach(doctors => {
        if (profile.audience === 'PROFISSIONAL' && [...doctors.options].some(o => o.value === profile.recipient_id)) {
            doctors.value = profile.recipient_id;
        }
    });
}

/** Envia um formulário e mostra o resultado no elemento de feedback. */
function bindForm(formId, resultId, handler) {
    $(formId).addEventListener('submit', async event => {
        event.preventDefault();
        const result = $(resultId);
        try {
            showResult(result, await handler(), true);
        } catch (err) {
            showResult(result, `Erro: ${err.message}`, false);
        }
    });
}

// ---------------------------------------------------------------- Paciente

bindForm('form-cadastro', 'res-cadastro', async () => {
    const data = {
        full_name: $('p-fullname').value,
        cpf: $('p-cpf').value.replace(/\D/g, ''),
        birth_date: $('p-birth').value,
        gender: $('p-gender').value,
    };
    const res = await apiCall('/admin/patients', 'POST', data);
    setPatient({ id: res.id, full_name: res.full_name || data.full_name });
    return `Sucesso! Paciente cadastrado e já escolhido nos formulários do portal. ID: ${res.id}`;
});

const when = value => new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });

async function fetchConsultations() {
    const resDiv = $('res-consultas');
    listReady(resDiv, 'mt-6 space-y-3');
    try {
        const patientId = requirePatient();
        const [page, legacy] = await Promise.all([
            apiCall(`/appointments?${new URLSearchParams({ patient_id: patientId, newest_first: true, limit: 50 })}`),
            apiCall(`/clinical/patients/${patientId}/appointments`).catch(() => []),
        ]);
        resDiv.innerHTML = page.items.length ? page.items.map(a => `
            <div class="p-3 border rounded-lg bg-white flex flex-col gap-1">
                <div class="flex justify-between items-center gap-2">
                    <span class="font-bold text-slate-800">${when(a.start_time)}</span>${statusBadge(a.status)}
                </div>
                <div class="text-sm text-slate-600">${escapeHtml(a.professional_name || '')}${a.reason ? ` · ${escapeHtml(a.reason)}` : ''}</div>
            </div>`).join('') : '<p class="text-slate-500 text-center text-sm py-2">Nenhuma consulta encontrada.</p>';
        if (legacy.length) {
            resDiv.insertAdjacentHTML('beforeend', `
                <div class="pt-2"><p class="text-xs font-semibold uppercase tracking-wide text-slate-600">Reservas da agenda antiga (somente consulta)</p>
                    <ul class="text-sm text-slate-600 mt-1 space-y-1">${legacy.map(r => `<li data-legacy-booking>${when(r.start_time)} · ${escapeHtml(r.status)}</li>`).join('')}</ul></div>`);
        }
    } catch (err) {
        listError(resDiv, `Erro: ${err.message}`);
    }
}

async function fetchAvailableSlots() {
    const select = $('p-slot-id');
    const doctorId = $('p-agenda-doctor').value;
    $('res-agenda').classList.add('hidden');
    if (!doctorId) {
        select.innerHTML = '<option value="">Escolha o médico para ver os horários</option>';
        return;
    }
    select.innerHTML = '<option value="">Carregando horários...</option>';
    try {
        const slots = await apiCall(`/professionals/${encodeURIComponent(doctorId)}/availability?days=7`);
        if (!slots.length) {
            select.innerHTML = '<option value="">Sem horários livres nos próximos 7 dias</option>';
            return;
        }
        const time = value => new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
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
        showResult($('res-agenda'), `Erro: ${err.message}`, false);
    }
}

bindForm('form-agenda', 'res-agenda', async () => {
    const patientId = requirePatient();
    const startTime = $('p-slot-id').value;
    if (!startTime) throw new Error('Escolha o médico e um horário livre.');
    const appointment = await apiCall('/appointments', 'POST', {
        patient_id: patientId, professional_id: $('p-agenda-doctor').value, start_time: startTime,
        reason: $('p-agenda-reason').value.trim() || null,
    });
    fetchAvailableSlots();
    return `Sucesso! Consulta agendada para ${when(appointment.start_time)} com ${appointment.professional_name || 'o(a) médico(a)'}.`;
});

async function fetchBilling() {
    const resDiv = $('res-fatura');
    listReady(resDiv, 'mt-6 space-y-2');
    try {
        const res = await apiCall(`/billing/patients/${requirePatient()}/summary`);
        if (res.length === 0) return renderEmpty(resDiv, 'Nenhum débito pendente encontrado.');
        res.forEach(inv => {
            const card = document.createElement('article');
            card.className = 'p-4 border rounded-lg bg-white space-y-2';
            const due = inv.due_date ? new Date(inv.due_date) : null;
            const overdue = due && due < new Date() && inv.status !== 'PAGO';
            const dueLabel = due ? due.toLocaleDateString('pt-BR') : 'Não informado';
            card.innerHTML = `
                <div class="flex justify-between gap-2">
                    <strong>Débito ${escapeHtml(inv.number)}</strong>
                    <span class="text-xs ${overdue ? 'text-red-600' : 'text-slate-500'}">${overdue ? 'Vencido' : escapeHtml(inv.status)}</span>
                </div>
                <div class="text-sm text-slate-600">Total dos serviços: ${formatMoney(inv.gross_total)}</div>
                <div class="text-sm text-slate-600">Cobertura do convênio: ${formatMoney(inv.insurance_share)}</div>
                <div class="font-bold text-blue-700">Valor devido pelo paciente: ${formatMoney(inv.patient_share)}</div>
                <div class="text-sm ${overdue ? 'text-red-600' : 'text-slate-600'}">Vencimento: ${dueLabel}</div>`;
            resDiv.appendChild(card);
        });
    } catch (err) {
        listError(resDiv, `Erro: ${err.message}`);
    }
}

// ------------------------------------------------------------------ Médico

async function fetchClinicalHistory() {
    const resDiv = $('res-doc-history');
    listReady(resDiv, 'mt-6 space-y-3');
    try {
        const res = await apiCall(`/clinical/patients/${requirePatient()}/history`);
        if (res.length === 0) return renderEmpty(resDiv, 'Sem histórico clínico disponível.');
        res.forEach(note => {
            const item = document.createElement('div');
            item.className = 'p-3 border rounded-lg bg-white flex flex-col gap-2';
            const badge = note.status === 'FINALIZED' ? 'bg-gray-100 text-gray-600' : 'bg-yellow-100 text-yellow-600';
            item.innerHTML = `
                <div class="flex justify-between items-center">
                    <span class="font-bold text-slate-800">Nota de Evolução</span>
                    <span class="text-xs ${badge} px-2 py-1 rounded-full">${escapeHtml(note.status)}</span>
                </div>
                <div class="text-sm text-slate-600 whitespace-pre-line">${escapeHtml(note.content)}</div>
                <div class="text-xs text-slate-500 text-right">${new Date(note.timestamp).toLocaleString('pt-BR')}</div>`;
            resDiv.appendChild(item);
        });
    } catch (err) {
        listError(resDiv, `Erro: ${err.message}`);
    }
}

async function loadDoctors() {
    const selects = document.querySelectorAll('[data-doctor-select]');
    try {
        const page = await apiCall('/professionals?professional_type=MEDICO&status=ATIVO&limit=100');
        const options = '<option value="">Selecione</option>' + page.items.map(d =>
            `<option value="${escapeHtml(d.id)}">${escapeHtml(d.full_name)}${d.specialty_name ? ` — ${escapeHtml(d.specialty_name)}` : ''}</option>`).join('');
        selects.forEach(select => { select.innerHTML = options; });
    } catch {
        selects.forEach(select => { select.innerHTML = '<option value="">Lista de médicos indisponível</option>'; });
    }
}

bindForm('form-doc-new', 'res-doc-new', async () => {
    await apiCall('/clinical/notes', 'POST', {
        patient_id: requirePatient(),
        doctor_id: $('d-note-doctor').value,
        content: $('d-note-content').value,
    });
    return 'Sucesso! Nota salva como evolução em rascunho (assine no prontuário).';
});

bindForm('form-doc-alerts', 'res-doc-alerts', async () => {
    await apiCall('/admin/alerts', 'POST', {
        patient_id: requirePatient(),
        alert_type: $('d-alert-type').value,
        severity: $('d-alert-severity').value,
        description: $('d-alert-msg').value,
    });
    return 'Sucesso! Alerta criado.';
});

// A dispensa é feita em /app/farmacia, com receita e lote (Fase 5); a rota legada segue só na API.

// --------------------------------------------------- Ligação dos controles

const ACTIONS = {
    'fetch-consultations': fetchConsultations,
    'fetch-slots': fetchAvailableSlots,
    'fetch-billing': fetchBilling,
    'fetch-history': fetchClinicalHistory,
};

document.addEventListener('click', event => {
    const target = event.target.closest('[data-open-modal], [data-view], [data-action]');
    if (!target) return;
    if (target.dataset.openModal) openModal(target.dataset.openModal);
    if (target.dataset.view) switchView(target.dataset.view);
    if (target.dataset.action) ACTIONS[target.dataset.action]?.();
});

// Versões anteriores guardavam o ID do paciente no navegador; agora só o perfil fica salvo (R6).
try { localStorage.removeItem('healthos.patientId'); } catch { /* armazenamento indisponível */ }

enableModalDismiss();
renderNav('portal');
renderDemoBanner();
enablePatientFields();
window.addEventListener('healthos:profile', applyProfile);
$('p-agenda-doctor').addEventListener('change', fetchAvailableSlots);
loadDoctors().then(applyProfile);
