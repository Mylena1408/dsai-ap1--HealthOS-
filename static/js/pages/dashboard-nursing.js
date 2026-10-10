// Visão "Enfermagem" do Painel: pacientes do dia, sinais vitais críticos e prescrições ativas,
// montada só com rotas existentes (Fase 4, decisão D3). Os registros são feitos no prontuário.
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDateTime } from '../core/dom.js';
import { statusBadge } from '../core/labels.js';

const DAY_STATUSES = ['AGENDADA', 'CONFIRMADA', 'EM_ANDAMENTO', 'FINALIZADA'];
const OPEN_ALERTS = ['ATIVO', 'RECONHECIDO'];
const ACTIVE_PRESCRIPTIONS = ['ATIVA', 'PARCIALMENTE_DISPENSADA'];
const LIST_LIMIT = 10;

const query = (base, repeated) => {
    const params = new URLSearchParams(base);
    Object.entries(repeated).forEach(([key, values]) => values.forEach(value => params.append(key, value)));
    return params;
};
const localDate = (date = new Date()) =>
    `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const time = value => new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
const recordLink = (patientId, name) => patientId ? `<a href="/app/prontuario?patient=${encodeURIComponent(patientId)}"
    class="text-xs font-semibold text-blue-700 hover:underline whitespace-nowrap">Abrir prontuário<span class="sr-only"> de ${escapeHtml(name || 'paciente')}</span></a>` : '';
const empty = text => `<p class="text-sm text-slate-500">${escapeHtml(text)}</p>`;
const levelFlag = level => level === 'CRITICO'
    ? '<span class="flag flag-critical"><i class="fas fa-triangle-exclamation" aria-hidden="true"></i>Crítico</span>'
    : '<span class="flag flag-attention"><i class="fas fa-circle-exclamation" aria-hidden="true"></i>Atenção</span>';

export async function renderNursingBoard(board, { card, tile }) {
    const today = localDate();
    const [appointments, alerts, prescriptions, inbox] = await Promise.all([
        apiCall(`/appointments?${query({ date_from: today, date_to: today, limit: 200 }, { status: DAY_STATUSES })}`),
        apiCall(`/alerts?${query({ rule_code: 'SINAL_VITAL_CRITICO', limit: LIST_LIMIT }, { status: OPEN_ALERTS })}`),
        apiCall(`/prescriptions?${query({ limit: LIST_LIMIT }, { status: ACTIVE_PRESCRIPTIONS })}`),
        apiCall('/inbox/counts?audience=SETOR&sector=ENFERMAGEM'),
    ]);
    const day = [...appointments.items].sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

    board.innerHTML = `
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            ${tile('Consultas hoje', String(appointments.total))}
            ${tile('Sinais vitais críticos', String(alerts.total), 'alertas em aberto')}
            ${tile('Prescrições ativas', String(prescriptions.total))}
            ${tile('Avisos não lidos', String(inbox.unread), '<a href="/app/notificacoes" class="text-blue-700 hover:underline">ver notificações</a>')}
        </div>
        ${card(`Pacientes do dia <span class="text-sm font-normal text-slate-500">(${day.length})</span>`, day.length ? `<ul class="divide-y">${day.map(a => `
            <li class="py-2 flex flex-wrap justify-between items-center gap-2 text-sm">
                <span>${time(a.start_time)} · <strong>${escapeHtml(a.patient_name || '')}</strong>
                    <span class="text-slate-500">· ${escapeHtml(a.professional_name || '')}</span></span>
                <span class="flex items-center gap-2">${statusBadge(a.status)}${recordLink(a.patient_id, a.patient_name)}</span>
            </li>`).join('')}</ul>` : empty('Nenhuma consulta hoje.'))}
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            ${card('Sinais vitais críticos', alerts.items.length ? `<ul class="divide-y">${alerts.items.map(a => `
                <li class="py-2 text-sm space-y-1">
                    <div class="flex flex-wrap justify-between items-center gap-2">${levelFlag(a.level)}${recordLink(a.patient_id)}</div>
                    <div class="font-medium text-slate-800">${escapeHtml(a.title)}</div>
                    <div class="text-slate-600">${escapeHtml(a.message)}</div>
                    <div class="text-xs text-slate-500">Detectado em ${formatDateTime(a.last_detected_at)}${a.status === 'RECONHECIDO' ? ' · reconhecido' : ''}</div>
                </li>`).join('')}</ul>` : empty('Nenhum sinal vital crítico em aberto.'))}
            ${card('Prescrições ativas', (prescriptions.items.length ? `<ul class="divide-y">${prescriptions.items.map(p => `
                <li class="py-2 text-sm space-y-1">
                    <div class="flex flex-wrap justify-between items-center gap-2">
                        <span><strong>${escapeHtml(p.patient_name || '')}</strong>
                            <span class="text-slate-500">· ${escapeHtml(p.prescriber_name || '')} · ${formatDateTime(p.issued_at)}</span></span>
                        ${recordLink(p.patient_id, p.patient_name)}</div>
                    <ul class="text-slate-600 list-disc pl-5">${p.items.map(i => `
                        <li>${escapeHtml(i.medication_name || '')} — ${escapeHtml(i.dose)}, ${escapeHtml(i.frequency)}</li>`).join('')}</ul>
                </li>`).join('')}</ul>` : empty('Nenhuma prescrição ativa.'))
                + '<p class="text-xs text-slate-600 mt-3">Somente consulta: a administração de medicamentos não é registrada neste sistema.</p>')}
        </div>`;
}
