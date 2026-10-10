// Prontuário eletrônico: busca de pacientes, resumo clínico, linha do tempo e registros estruturados.
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDate, formatDateTime, renderEmpty, renderLoading, toast } from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { renderExamsTab, renderVitalsTab } from './record-monitoring.js';
import { renderMedicationsTab } from './record-medications.js';
import { renderEvolutionTab } from './record-evolution.js';
import {
    ALLERGY_CATEGORIES, ALLERGY_SEVERITY, APPOINTMENT_TYPES, BLOOD_TYPES, CONDITION_STATUS, DIAGNOSIS_CERTAINTY,
    TIMELINE_TYPES, badge, fillSelect, patientAlertList, statusBadge,
} from '../core/labels.js';

const PAGE_SIZE = 20;
const $ = id => document.getElementById(id);
const state = { offset: 0, patientId: null, record: null, tab: 'resumo', timelineTypes: new Set() };

const TAB_LABELS = {
    resumo: 'Resumo', timeline: 'Linha do tempo', evolucao: 'Evolução', sinais: 'Sinais vitais', exames: 'Exames',
    medicamentos: 'Medicamentos',
    alergias: 'Alergias', condicoes: 'Condições',
    diagnosticos: 'Diagnósticos', procedimentos: 'Procedimentos', perfil: 'Perfil e contatos',
};

const card = (title, body) => `
    <div class="glass-card rounded-2xl p-5">
        <h3 class="font-bold text-slate-800 mb-3">${title}</h3>${body}</div>`;
const empty = text => `<p class="text-sm text-slate-500">${escapeHtml(text)}</p>`;
const input = (id, attrs = '') => `<input id="${id}" ${attrs} class="w-full p-2 border rounded-lg outline-none focus:border-blue-500">`;
const submit = label => `<button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700">${label}</button>`;
const actionButton = (act, id, label) =>
    `<button data-act="${act}" data-id="${escapeHtml(id)}" class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">${label}</button>`;
const api = path => `/patients/${state.patientId}${path}`;

// ------------------------------------------------------------- pacientes

async function loadPatients(append = false) {
    const list = $('patients');
    if (!append) { state.offset = 0; renderLoading(list); }
    try {
        const page = await apiCall(`/patients?${new URLSearchParams({ q: $('search').value.trim(), limit: PAGE_SIZE, offset: state.offset })}`);
        const html = page.items.map(p => `
            <li><button data-patient="${escapeHtml(p.id)}" class="w-full text-left px-2 py-3 hover:bg-blue-50 rounded-lg ${p.id === state.patientId ? 'bg-blue-50' : ''}">
                <div class="font-medium text-slate-800">${escapeHtml(p.full_name)}</div>
                <div class="text-xs text-slate-600">${p.age} anos · ${escapeHtml(p.gender)}${p.insurance_provider ? ` · ${escapeHtml(p.insurance_provider)}` : ''}</div>
            </button></li>`).join('');
        if (append) list.insertAdjacentHTML('beforeend', html);
        else if (!page.items.length) renderEmpty(list, 'Nenhum paciente encontrado.');
        else list.innerHTML = html;
        state.offset += page.items.length;
        $('more').classList.toggle('hidden', state.offset >= page.total);
    } catch (err) {
        renderEmpty(list, `Erro: ${err.message}`);
    }
}

async function openPatient(patientId) {
    state.patientId = patientId;
    history.replaceState(null, '', `?patient=${encodeURIComponent(patientId)}`);
    document.querySelectorAll('[data-patient]').forEach(b => b.classList.toggle('bg-blue-50', b.dataset.patient === patientId));
    renderLoading($('record'), 'Abrindo prontuário...');
    try {
        state.record = await apiCall(api('/record'));
        renderRecord();
    } catch (err) {
        renderEmpty($('record'), `Erro: ${err.message}`);
    }
}

// --------------------------------------------------------------- cabeçalho

function renderRecord() {
    const r = state.record;
    const p = r.patient;
    const allergyChips = r.active_allergies.length
        ? r.active_allergies.map(a => `<span class="text-xs font-semibold px-2 py-1 rounded-full ${ALLERGY_SEVERITY[a.severity].color}">
                <i class="fas fa-triangle-exclamation"></i> ${escapeHtml(a.substance)}</span>`).join(' ')
        : '<span class="text-xs text-slate-500">Nenhuma alergia ativa registrada</span>';

    $('record').innerHTML = `
        <div class="glass-card rounded-2xl p-5">
            <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 class="text-2xl font-bold text-slate-900">${escapeHtml(p.full_name)}</h2>
                    <p class="text-sm text-slate-600">${r.age} anos · ${escapeHtml(p.gender)} · nascimento ${formatDate(p.birth_date + 'T00:00')} · CPF ${escapeHtml(p.cpf)}</p>
                    <p class="text-sm text-slate-600">${escapeHtml(p.insurance_provider || 'Particular')}${p.phone ? ` · ${escapeHtml(p.phone)}` : ''}</p>
                </div>
                <div class="flex items-center gap-3">
                    <a href="/app/assistente?patient=${encodeURIComponent(p.id)}" class="px-3 py-2 rounded-lg border text-sm font-semibold text-blue-700 hover:bg-blue-50">
                        <i class="fas fa-robot" aria-hidden="true"></i> Assistente</a>
                    <div class="text-center bg-red-50 text-red-700 rounded-xl px-4 py-2">
                        <div class="text-xs uppercase">Tipo sanguíneo</div>
                        <div class="text-xl font-bold">${escapeHtml(BLOOD_TYPES[r.profile.blood_type])}</div>
                    </div>
                </div>
            </div>
            <div class="mt-3 flex flex-wrap gap-2 items-center"><span class="text-sm font-medium text-slate-700">Alergias:</span> ${allergyChips}</div>
            <p class="text-xs text-amber-700 mt-3"><i class="fas fa-circle-info"></i> ${escapeHtml(r.disclaimer)}</p>
        </div>
        <div class="bg-white p-1 rounded-xl border border-slate-200 flex flex-wrap gap-1" role="tablist">
            ${Object.entries(TAB_LABELS).map(([id, label]) => `
                <button data-tab="${id}" role="tab" aria-selected="${id === state.tab}"
                    class="px-3 py-2 rounded-lg text-sm font-bold ${id === state.tab ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}">${label}</button>`).join('')}
        </div>
        <div id="tab-content" class="space-y-4"></div>`;
    renderTab();
}

async function renderTab() {
    const container = $('tab-content');
    renderLoading(container);
    try {
        await TABS[state.tab](container);
    } catch (err) {
        renderEmpty(container, `Erro: ${err.message}`);
    }
}

async function refresh(message) {
    if (message) toast(message, 'success');
    state.record = await apiCall(api('/record'));
    renderRecord();
}

/** Liga um formulário renderizado dinamicamente a um envio para a API. */
function bindForm(formId, buildRequest, successMessage) {
    $(formId).addEventListener('submit', async event => {
        event.preventDefault();
        try {
            const [path, method, body] = buildRequest();
            await apiCall(api(path), method, body);
            await refresh(successMessage);
        } catch (err) {
            toast(err.message, 'error');
        }
    });
}

// ------------------------------------------------------------------- abas

const TABS = {
    async resumo(container) {
        const r = state.record;
        // Alertas criados pelo portal (/admin/alerts): só apareciam na linha do tempo (L5).
        const patientAlerts = await apiCall(`/admin/alerts/patient/${state.patientId}/active`).catch(() => null);
        const appointment = a => `<li class="py-2 flex flex-wrap justify-between gap-2 text-sm">
            <span>${formatDateTime(a.start_time)} · ${escapeHtml(a.professional_name || '')} · ${escapeHtml(APPOINTMENT_TYPES[a.appointment_type] || '')}</span>
            ${statusBadge(a.status)}</li>`;
        container.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                ${card('Alertas do paciente', patientAlerts === null ? empty('Não foi possível carregar os alertas.')
                    : patientAlerts.length ? patientAlertList(patientAlerts) : empty('Nenhum alerta ativo.'))}
                ${card('Próximas consultas', r.upcoming_appointments.length
                    ? `<ul class="divide-y">${r.upcoming_appointments.map(appointment).join('')}</ul>` : empty('Nenhuma consulta futura.'))}
                ${card('Última consulta realizada', r.last_appointment
                    ? `<ul>${appointment(r.last_appointment)}</ul>${r.last_appointment.notes ? `<p class="text-sm text-slate-600 mt-2">${escapeHtml(r.last_appointment.notes)}</p>` : ''}`
                    : empty('Nenhuma consulta finalizada.'))}
                ${card('Problemas ativos', r.active_conditions.length
                    ? `<ul class="space-y-2">${r.active_conditions.map(c => `<li class="flex justify-between gap-2 text-sm">
                        <span>${escapeHtml(c.name)}${c.code ? ` <span class="text-slate-500">(${escapeHtml(c.code)})</span>` : ''}</span>${badge(CONDITION_STATUS, c.status)}</li>`).join('')}</ul>`
                    : empty('Nenhuma condição ativa.'))}
                ${card('Diagnósticos recentes', r.recent_diagnoses.length
                    ? `<ul class="space-y-2">${r.recent_diagnoses.map(d => `<li class="flex justify-between gap-2 text-sm">
                        <span>${escapeHtml(d.description)} <span class="text-slate-500">${formatDate(d.diagnosed_at)}</span></span>${badge(DIAGNOSIS_CERTAINTY, d.certainty)}</li>`).join('')}</ul>`
                    : empty('Nenhum diagnóstico registrado.'))}
            </div>`;
    },

    async timeline(container) {
        const params = new URLSearchParams({ limit: 200 });
        state.timelineTypes.forEach(type => params.append('types', type));
        const page = await apiCall(api(`/timeline?${params}`));
        const filters = Object.entries(TIMELINE_TYPES).map(([type, info]) => `
            <label class="text-xs flex items-center gap-1 border rounded-full px-2 py-1 cursor-pointer">
                <input type="checkbox" data-timeline-type="${type}" ${state.timelineTypes.has(type) ? 'checked' : ''}> ${info.label}</label>`).join('');
        const items = page.items.map(e => {
            const info = TIMELINE_TYPES[e.event_type];
            return `<li class="relative pl-10 pb-5">
                <span class="absolute left-0 top-0 w-7 h-7 rounded-full ${info.color} text-white flex items-center justify-center text-xs" aria-hidden="true"><i class="fas ${info.icon}"></i></span>
                <div class="text-xs text-slate-500">${formatDateTime(e.occurred_at)} · ${info.label}${e.status ? ` · ${escapeHtml(e.status)}` : ''}</div>
                <div class="font-medium text-slate-800">${escapeHtml(e.title)}</div>
                ${e.description ? `<div class="text-sm text-slate-600 whitespace-pre-line">${escapeHtml(e.description)}</div>` : ''}
            </li>`;
        }).join('');
        container.innerHTML = card(`Linha do tempo <span class="text-sm font-normal text-slate-500">(${page.total} eventos)</span>`, `
            <div class="flex flex-wrap gap-2 mb-4">${filters}</div>
            ${items ? `<ol class="border-l-2 border-slate-100 ml-3 pl-0">${items}</ol>` : empty('Nenhum evento para os filtros escolhidos.')}`);
    },

    evolucao: container => renderEvolutionTab(container, { patientId: state.patientId, onChange: refresh }),

    sinais: container => renderVitalsTab(container, { patientId: state.patientId, onChange: refresh }),

    exames: container => renderExamsTab(container, { patientId: state.patientId, onChange: refresh }),

    medicamentos: container => renderMedicationsTab(container, { patientId: state.patientId, onChange: refresh }),

    async alergias(container) {
        const allergies = await apiCall(api('/allergies'));
        container.innerHTML = card('Alergias', allergies.length ? `<ul class="divide-y">${allergies.map(a => `
                <li class="py-2 flex flex-wrap justify-between items-center gap-2 text-sm">
                    <span><strong>${escapeHtml(a.substance)}</strong> · ${escapeHtml(ALLERGY_CATEGORIES[a.category])}
                        ${a.reaction ? `· ${escapeHtml(a.reaction)}` : ''}</span>
                    <span class="flex gap-2 items-center">${badge(ALLERGY_SEVERITY, a.severity)}
                        ${a.status === 'ATIVA' ? actionButton('resolve-allergy', a.id, 'Marcar resolvida') : '<span class="text-xs text-slate-500">Resolvida</span>'}</span>
                </li>`).join('')}</ul>` : empty('Nenhuma alergia registrada.')) + card('Registrar alergia', `
            <form id="form-allergy" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                ${input('a-substance', 'required minlength="2" placeholder="Substância"')}
                ${input('a-reaction', 'placeholder="Reação (opcional)"')}
                <select id="a-category" class="p-2 border rounded-lg"></select>
                <select id="a-severity" class="p-2 border rounded-lg"></select>
                <div>${submit('Registrar')}</div>
            </form>`);
        fillSelect($('a-category'), ALLERGY_CATEGORIES);
        fillSelect($('a-severity'), ALLERGY_SEVERITY);
        bindForm('form-allergy', () => ['/allergies', 'POST', {
            substance: $('a-substance').value, category: $('a-category').value,
            severity: $('a-severity').value, reaction: $('a-reaction').value || null,
        }], 'Alergia registrada.');
    },

    async condicoes(container) {
        const conditions = await apiCall(api('/conditions'));
        const nextStatus = { ATIVA: ['CONTROLADA', 'RESOLVIDA'], CONTROLADA: ['ATIVA', 'RESOLVIDA'], RESOLVIDA: ['ATIVA'] };
        container.innerHTML = card('Condições clínicas', conditions.length ? `<ul class="divide-y">${conditions.map(c => `
                <li class="py-2 flex flex-wrap justify-between items-center gap-2 text-sm">
                    <span><strong>${escapeHtml(c.name)}</strong>${c.code ? ` (${escapeHtml(c.code)})` : ''}
                        <span class="text-slate-500">· desde ${c.onset_date ? formatDate(c.onset_date + 'T00:00') : '—'}</span></span>
                    <span class="flex flex-wrap gap-2 items-center">${badge(CONDITION_STATUS, c.status)}
                        ${nextStatus[c.status].map(s => actionButton(`condition-${s}`, c.id, CONDITION_STATUS[s].label)).join('')}</span>
                </li>`).join('')}</ul>` : empty('Nenhuma condição registrada.')) + card('Registrar condição', `
            <form id="form-condition" class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                ${input('c-name', 'required minlength="3" placeholder="Condição"')}
                ${input('c-code', 'placeholder="Código (opcional)"')}
                ${input('c-onset', 'type="date" aria-label="Data de início"')}
                <div>${submit('Registrar')}</div>
            </form>`);
        $('c-onset').max = new Date().toISOString().slice(0, 10);
        bindForm('form-condition', () => ['/conditions', 'POST', {
            name: $('c-name').value, code: $('c-code').value || null, onset_date: $('c-onset').value || null,
        }], 'Condição registrada.');
    },

    async diagnosticos(container) {
        const diagnoses = await apiCall(api('/diagnoses'));
        container.innerHTML = card('Diagnósticos', diagnoses.length ? `<ul class="divide-y">${diagnoses.map(d => `
                <li class="py-2 flex flex-wrap justify-between items-center gap-2 text-sm">
                    <span><strong>${escapeHtml(d.description)}</strong>${d.code ? ` (${escapeHtml(d.code)})` : ''}
                        <span class="text-slate-500">· ${formatDate(d.diagnosed_at)}${d.professional_name ? ` · ${escapeHtml(d.professional_name)}` : ''}</span></span>
                    <span class="flex gap-2 items-center">${badge(DIAGNOSIS_CERTAINTY, d.certainty)}
                        ${d.certainty === 'SUSPEITA' ? actionButton('confirm-diagnosis', d.id, 'Confirmar') + actionButton('rule-out-diagnosis', d.id, 'Descartar') : ''}</span>
                </li>`).join('')}</ul>` : empty('Nenhum diagnóstico registrado.')) + card('Registrar hipótese diagnóstica', `
            <form id="form-diagnosis" class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div class="sm:col-span-2">${input('d-description', 'required minlength="3" placeholder="Descrição (fictícia)"')}</div>
                ${input('d-code', 'placeholder="Código (opcional)"')}
                <div>${submit('Registrar')}</div>
            </form>`);
        bindForm('form-diagnosis', () => ['/diagnoses', 'POST', {
            description: $('d-description').value, code: $('d-code').value || null,
        }], 'Diagnóstico registrado como suspeita.');
    },

    async procedimentos(container) {
        const procedures = await apiCall(api('/procedures'));
        container.innerHTML = card('Procedimentos realizados', procedures.length ? `<ul class="divide-y">${procedures.map(p => `
                <li class="py-2 text-sm"><strong>${escapeHtml(p.name)}</strong>
                    <span class="text-slate-500">· ${formatDateTime(p.performed_at)}${p.professional_name ? ` · ${escapeHtml(p.professional_name)}` : ''}</span>
                    ${p.notes ? `<div class="text-slate-600">${escapeHtml(p.notes)}</div>` : ''}</li>`).join('')}</ul>`
            : empty('Nenhum procedimento registrado.')) + card('Registrar procedimento', `
            <form id="form-procedure" class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                ${input('p-name', 'required minlength="3" placeholder="Procedimento"')}
                ${input('p-date', 'type="datetime-local" required aria-label="Data e hora"')}
                ${input('p-notes', 'placeholder="Observações (opcional)"')}
                <div>${submit('Registrar')}</div>
            </form>`);
        bindForm('form-procedure', () => ['/procedures', 'POST', {
            name: $('p-name').value, performed_at: $('p-date').value, notes: $('p-notes').value || null,
        }], 'Procedimento registrado.');
    },

    async perfil(container) {
        const profile = state.record.profile;
        container.innerHTML = card('Dados clínicos complementares', `
            <form id="form-profile" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label class="text-sm text-slate-600">Tipo sanguíneo <select id="pf-blood" class="w-full p-2 border rounded-lg mt-1"></select></label>
                <label class="text-sm text-slate-600">Ocupação ${input('pf-occupation', 'maxlength="120"')}</label>
                <label class="text-sm text-slate-600 sm:col-span-2">Observações
                    <textarea id="pf-notes" maxlength="2000" class="w-full p-2 border rounded-lg h-24 mt-1"></textarea></label>
                <div>${submit('Salvar')}</div>
            </form>`) + card('Contatos de emergência', `
            ${profile.emergency_contacts.length ? `<ul class="divide-y mb-4">${profile.emergency_contacts.map(c => `
                <li class="py-2 flex flex-wrap justify-between items-center gap-2 text-sm">
                    <span><strong>${escapeHtml(c.full_name)}</strong> · ${escapeHtml(c.relationship)} · ${escapeHtml(c.phone)}
                        ${c.is_primary ? '<span class="text-xs text-blue-700 font-semibold ml-1">Principal</span>' : ''}</span>
                    ${actionButton('remove-contact', c.id, 'Remover')}
                </li>`).join('')}</ul>` : empty('Nenhum contato cadastrado (máximo de 3).')}
            <form id="form-contact" class="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
                ${input('ct-name', 'required minlength="3" placeholder="Nome"')}
                ${input('ct-relationship', 'required minlength="2" placeholder="Parentesco"')}
                ${input('ct-phone', 'required minlength="10" placeholder="Telefone"')}
                <label class="text-sm flex items-center gap-2"><input id="ct-primary" type="checkbox"> Contato principal</label>
                <div>${submit('Adicionar')}</div>
            </form>`);
        fillSelect($('pf-blood'), BLOOD_TYPES);
        $('pf-blood').value = profile.blood_type;
        $('pf-occupation').value = profile.occupation || '';
        $('pf-notes').value = profile.notes || '';
        bindForm('form-profile', () => ['/profile', 'PUT', {
            blood_type: $('pf-blood').value, occupation: $('pf-occupation').value || null, notes: $('pf-notes').value || null,
        }], 'Perfil atualizado.');
        bindForm('form-contact', () => ['/emergency-contacts', 'POST', {
            full_name: $('ct-name').value, relationship: $('ct-relationship').value,
            phone: $('ct-phone').value, is_primary: $('ct-primary').checked,
        }], 'Contato adicionado.');
    },
};

// Ações dos botões dentro das abas: [método, caminho, corpo, mensagem]
const ACTIONS = {
    'resolve-allergy': id => ['POST', `/allergies/${id}/resolve`, null, 'Alergia marcada como resolvida.'],
    'confirm-diagnosis': id => ['POST', `/diagnoses/${id}/confirm`, null, 'Diagnóstico confirmado.'],
    'rule-out-diagnosis': id => ['POST', `/diagnoses/${id}/rule-out`, null, 'Diagnóstico descartado.'],
    'remove-contact': id => ['DELETE', `/emergency-contacts/${id}`, null, 'Contato removido.'],
    ...Object.fromEntries(Object.keys(CONDITION_STATUS).map(status => [
        `condition-${status}`, id => ['PATCH', `/conditions/${id}/status`, { status }, 'Situação da condição atualizada.'],
    ])),
};

// ------------------------------------------------------------------ eventos

document.addEventListener('click', async event => {
    const patient = event.target.closest('[data-patient]');
    if (patient) return openPatient(patient.dataset.patient);

    const tab = event.target.closest('[data-tab]');
    if (tab) { state.tab = tab.dataset.tab; return renderRecord(); }

    const action = event.target.closest('[data-act]');
    if (action && ACTIONS[action.dataset.act]) {
        const [method, path, body, message] = ACTIONS[action.dataset.act](action.dataset.id);
        try {
            await apiCall(api(path), method, body);
            await refresh(message);
        } catch (err) {
            toast(err.message, 'error');
        }
    }
});

document.addEventListener('change', event => {
    const type = event.target.dataset?.timelineType;
    if (!type) return;
    if (event.target.checked) state.timelineTypes.add(type);
    else state.timelineTypes.delete(type);
    renderTab();
});

let debounce;
$('search').addEventListener('input', () => { clearTimeout(debounce); debounce = setTimeout(() => loadPatients(), 300); });
$('more').addEventListener('click', () => loadPatients(true));

renderNav('prontuario');
renderDemoBanner();
renderEmpty($('record'), 'Selecione um paciente na lista para abrir o prontuário.');
loadPatients();
const preselected = new URLSearchParams(window.location.search).get('patient');
if (preselected) openPatient(preselected);
