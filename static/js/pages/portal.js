// Portal do Paciente / Médico (página inicial).
import { apiCall } from '../core/api.js';
import {
    escapeHtml, isValidUuid, formatMoney, openModal, enableModalDismiss, showResult, renderEmpty,
} from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';

const PATIENT_ID_KEY = 'healthos.patientId';
const ACTIVE_TAB = 'px-4 py-2 rounded-lg text-sm font-bold transition-all bg-blue-600 text-white';
const INACTIVE_TAB = 'px-4 py-2 rounded-lg text-sm font-bold transition-all text-slate-600 hover:bg-slate-100';

const $ = id => document.getElementById(id);

function rememberPatientId(patientId) {
    try { localStorage.setItem(PATIENT_ID_KEY, patientId); } catch { /* armazenamento indisponível */ }
    ['p-id-agenda', 'p-consult-id', 'p-bill-id'].forEach(id => {
        const input = $(id);
        if (input) input.value = patientId;
    });
}

function restorePatientId() {
    try {
        const saved = localStorage.getItem(PATIENT_ID_KEY);
        if (saved) rememberPatientId(saved);
    } catch { /* armazenamento indisponível */ }
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
    rememberPatientId(res.id);
    return `Sucesso! Seu ID de Paciente é: ${res.id}`;
});

async function fetchConsultations() {
    const pid = $('p-consult-id').value.trim();
    const resDiv = $('res-consultas');
    resDiv.innerHTML = '';
    if (!isValidUuid(pid)) return alert('Informe o ID UUID recebido ao cadastrar o paciente.');
    try {
        const res = await apiCall(`/clinical/patients/${pid}/appointments`);
        resDiv.classList.remove('hidden');
        if (res.length === 0) return renderEmpty(resDiv, 'Nenhuma consulta agendada.');
        res.forEach(app => {
            const item = document.createElement('div');
            item.className = 'p-3 border rounded-lg bg-white flex flex-col gap-1';
            item.innerHTML = `
                <div class="flex justify-between items-center">
                    <span class="font-bold text-slate-800">Consulta Agendada</span>
                    <span class="text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded-full">${escapeHtml(app.status)}</span>
                </div>
                <div class="text-sm text-slate-600">
                    <i class="fas fa-calendar"></i> ${new Date(app.start_time).toLocaleString()}
                </div>`;
            resDiv.appendChild(item);
        });
    } catch (err) {
        alert(`Erro: ${err.message}`);
    }
}

async function fetchAvailableSlots() {
    const select = $('p-slot-id');
    select.innerHTML = '<option value="">Carregando horários...</option>';
    try {
        const slots = await apiCall('/clinical/availability');
        select.innerHTML = '<option value="">Selecione um horário</option>';
        const periods = [
            { label: 'Manhã (antes das 12h)', test: hour => hour < 12 },
            { label: 'Tarde (12h às 18h)', test: hour => hour >= 12 && hour < 18 },
            { label: 'Noite (a partir das 18h)', test: hour => hour >= 18 },
        ];
        const groups = periods.map(period => {
            const group = document.createElement('optgroup');
            group.label = period.label;
            select.appendChild(group);
            return { ...period, group };
        });
        slots.forEach(slot => {
            const startsAt = new Date(slot.start_time);
            const option = document.createElement('option');
            option.value = slot.id;
            option.textContent = `${startsAt.toLocaleDateString('pt-BR')} às ${startsAt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })} — ${slot.duration_minutes} min`;
            groups.find(period => period.test(startsAt.getHours())).group.appendChild(option);
        });
        groups.forEach(({ group }) => { if (!group.children.length) group.remove(); });
        if (!slots.length) select.innerHTML = '<option value="">Sem horários futuros disponíveis</option>';
    } catch (err) {
        select.innerHTML = '<option value="">Erro ao carregar horários</option>';
        alert(`Erro: ${err.message}`);
    }
}

bindForm('form-agenda', 'res-agenda', async () => {
    const patientId = $('p-id-agenda').value.trim();
    if (!isValidUuid(patientId)) throw new Error('Cadastre o paciente e use o ID UUID retornado para reservar a consulta.');
    await apiCall('/clinical/schedule', 'POST', { slot_id: $('p-slot-id').value, patient_id: patientId });
    return 'Sucesso! Consulta agendada.';
});

async function fetchBilling() {
    const pid = $('p-bill-id').value.trim();
    const resDiv = $('res-fatura');
    resDiv.innerHTML = '';
    if (!isValidUuid(pid)) return alert('Informe o ID UUID recebido ao cadastrar o paciente.');
    try {
        const res = await apiCall(`/billing/patients/${pid}/summary`);
        resDiv.classList.remove('hidden');
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
        alert(`Erro: ${err.message}`);
    }
}

// ------------------------------------------------------------------ Médico

async function fetchClinicalHistory() {
    const pid = $('d-patient-id').value.trim();
    const resDiv = $('res-doc-history');
    resDiv.innerHTML = '';
    try {
        const res = await apiCall(`/clinical/patients/${pid}/history`);
        resDiv.classList.remove('hidden');
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
        alert(`Erro: ${err.message}`);
    }
}

bindForm('form-doc-new', 'res-doc-new', async () => {
    await apiCall('/clinical/notes', 'POST', {
        patient_id: $('d-note-patient-id').value,
        doctor_id: $('d-note-doctor-id').value,
        content: $('d-note-content').value,
    });
    return 'Sucesso! Nota salva.';
});

bindForm('form-doc-alerts', 'res-doc-alerts', async () => {
    await apiCall('/admin/alerts', 'POST', {
        patient_id: $('d-alert-patient-id').value,
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

enableModalDismiss();
renderNav('portal');
renderDemoBanner();
restorePatientId();
