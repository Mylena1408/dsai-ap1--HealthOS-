// Painéis por perfil: paciente, profissional, enfermagem, farmácia e administração.
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDate, formatDateTime, renderEmpty, renderLoading, toast } from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { APPOINTMENT_STATUS, EXAM_STATUS, flagBadge, statusBadge } from '../core/labels.js';
import { renderBarChart } from '../components/bar-chart.js';
import { renderLineChart } from '../components/line-chart.js';
import { createPatientPicker } from '../components/patient-picker.js';
import { getProfile } from '../components/profile.js';
import { dashboardViewFor } from '../core/role-nav.js';
import { renderNursingBoard } from './dashboard-nursing.js';

const $ = id => document.getElementById(id);
const VIEWS = {
    patient: 'Paciente', professional: 'Profissional', nursing: 'Enfermagem', pharmacy: 'Farmácia', admin: 'Administração',
};
const BANDS = {
    BOM: { label: 'Bom acompanhamento', icon: 'fa-circle-check', meter: 'meter-good' },
    ATENCAO: { label: 'Atenção', icon: 'fa-circle-exclamation', meter: 'meter-attention' },
    INSUFICIENTE: { label: 'Acompanhamento insuficiente', icon: 'fa-triangle-exclamation', meter: 'meter-critical' },
    SEM_DADOS: { label: 'Sem dados', icon: 'fa-circle-question', meter: 'meter-na' },
};
const state = { view: null, patientId: null, professionalId: null, professionals: [] };
const fmt = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
const card = (title, body, extra = '') => `<div class="glass-card rounded-2xl p-5 ${extra}"><h3 class="font-bold text-slate-800 mb-3">${title}</h3>${body}</div>`;
const tile = (label, value, hint = '') => `<div class="glass-card rounded-2xl p-4">
    <div class="text-xs text-slate-500">${escapeHtml(label)}</div>
    <div class="text-2xl font-semibold text-slate-900">${escapeHtml(value)}</div>
    ${hint ? `<div class="text-xs text-slate-500 mt-1">${hint}</div>` : ''}</div>`;
const bandOf = score => score == null ? 'SEM_DADOS' : score >= 80 ? 'BOM' : score >= 60 ? 'ATENCAO' : 'INSUFICIENTE';
const meter = score => `<div class="meter ${BANDS[bandOf(score)].meter}" role="meter" aria-valuemin="0" aria-valuemax="100"
    aria-valuenow="${score ?? 0}"><span style="width:${score ?? 0}%"></span></div>`;
const toItems = counts => Object.entries(counts).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
const labelOf = (dictionary, key) => dictionary[key]?.label || key;

// --------------------------------------------------------------- Health Score

function healthScoreCard(hs) {
    const band = BANDS[hs.band || 'SEM_DADOS'];
    return card('Health Score <span class="text-sm font-normal text-slate-500">(indicador demonstrativo)</span>', `
        <div class="flex flex-wrap items-center gap-6 mb-4">
            <div class="text-5xl font-semibold text-slate-900">${hs.score ?? '—'}<span class="text-lg text-slate-500">/100</span></div>
            <div class="flex-1 min-w-[12rem]">
                ${meter(hs.score)}
                <div class="text-sm text-slate-700 mt-2"><i class="fas ${band.icon}" aria-hidden="true"></i> ${band.label}</div>
            </div>
        </div>
        <ul class="space-y-3">${hs.components.map(c => `
            <li>
                <div class="flex justify-between text-sm"><span class="font-medium text-slate-700">${escapeHtml(c.label)}</span>
                    <span class="tabular-nums text-slate-600">${c.applicable ? c.score : 'não aplicável'}</span></div>
                ${c.applicable ? meter(c.score) : '<div class="meter meter-na"></div>'}
                <div class="text-xs text-slate-500 mt-1">${escapeHtml(c.explanation)}</div>
            </li>`).join('')}</ul>
        <p class="text-xs text-amber-700 mt-4"><i class="fas fa-circle-info" aria-hidden="true"></i> ${escapeHtml(hs.disclaimer)}</p>`);
}

// ----------------------------------------------------------------- visões

const RENDER = {
    async patient(board) {
        if (!state.patientId) return renderEmpty(board, 'Escolha um paciente para ver o painel.');
        const d = await apiCall(`/dashboards/patient/${state.patientId}`);
        board.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                ${tile('Paciente', d.patient_name, `${d.age} anos`)}
                ${tile('Próximas consultas', String(d.upcoming_appointments.length))}
                ${tile('Medicamentos em uso', String(d.medications_in_use.length))}
                ${tile('Notificações não lidas', String(d.unread_notifications))}
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                ${healthScoreCard(d.health_score)}
                <div class="space-y-4">
                    ${card('Próximas consultas', d.upcoming_appointments.length ? `<ul class="divide-y">${d.upcoming_appointments.map(a => `
                        <li class="py-2 flex justify-between gap-2 text-sm"><span>${formatDateTime(a.start_time)} · ${escapeHtml(a.professional_name || '')}</span>${statusBadge(a.status)}</li>`).join('')}</ul>`
                        : '<p class="text-sm text-slate-500">Nenhuma consulta futura.</p>')}
                    ${card('Medicamentos em uso', d.medications_in_use.length ? `<ul class="space-y-1 text-sm">${d.medications_in_use.map(m => `
                        <li>${escapeHtml(m.medication_name || '')} — ${escapeHtml(m.dose)}, ${escapeHtml(m.frequency)}</li>`).join('')}</ul>`
                        : '<p class="text-sm text-slate-500">Nenhum.</p>')}
                    ${card('Alertas abertos', d.open_alerts.length ? `<ul class="space-y-1 text-sm">${d.open_alerts.map(a => `
                        <li><i class="fas fa-triangle-exclamation text-slate-500" aria-hidden="true"></i> ${escapeHtml(a.title)}</li>`).join('')}</ul>`
                        : '<p class="text-sm text-slate-500">Nenhum alerta aberto.</p>')}
                </div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                ${card('Exames recentes', d.recent_exams.length ? `<ul class="divide-y">${d.recent_exams.map(e => `
                    <li class="py-2 text-sm"><div class="flex justify-between gap-2"><strong>${escapeHtml(e.exam_name)}</strong>
                        <span class="text-slate-500">${formatDate(e.released_at)}</span></div>
                        <div class="flex flex-wrap gap-2 mt-1">${e.results.map(r => `<span>${escapeHtml(r.analyte_name)} ${fmt(r.value)} ${escapeHtml(r.unit)} ${flagBadge(r.flag)}</span>`).join('')}</div></li>`).join('')}</ul>`
                    : '<p class="text-sm text-slate-500">Nenhum resultado liberado.</p>')}
                ${card('Sinais vitais (última medida)', d.vitals.length ? `<ul class="grid grid-cols-2 gap-2 text-sm">${d.vitals.filter(v => v.metric !== 'height_cm').map(v => `
                    <li><div class="text-xs text-slate-500">${escapeHtml(v.label)}</div><strong>${fmt(v.latest)}</strong> ${escapeHtml(v.unit)} ${v.flag ? flagBadge(v.flag) : ''}</li>`).join('')}</ul>`
                    : '<p class="text-sm text-slate-500">Sem medições.</p>')}
            </div>
            <a href="/app/prontuario?patient=${encodeURIComponent(d.patient_id)}" class="inline-block text-sm text-blue-700 font-semibold hover:underline">Abrir prontuário completo</a>`;
    },

    async professional(board) {
        if (!state.professionalId) return renderEmpty(board, 'Escolha um profissional para ver o painel.');
        const d = await apiCall(`/dashboards/professional/${state.professionalId}`);
        const rate = d.attendance_rate_30d == null ? '—' : `${Math.round(d.attendance_rate_30d * 100)}%`;
        board.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                ${tile('Consultas hoje', String(d.today.length))}
                ${tile('Próximos 7 dias', String(d.next_7_days), 'agendadas ou confirmadas')}
                ${tile('Pacientes atendidos (30 dias)', String(d.patients_seen_30d))}
                ${tile('Comparecimento (30 dias)', rate, 'finalizadas ÷ (finalizadas + faltas)')}
            </div>
            ${card(`Agenda de hoje — ${escapeHtml(d.professional_name)}`, d.today.length ? `<ul class="divide-y">${d.today.map(a => `
                <li class="py-2 flex flex-wrap justify-between items-center gap-2 text-sm"><span>${new Date(a.start_time).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })} · ${escapeHtml(a.patient_name || '')}</span>
                    <span class="flex items-center gap-2">${statusBadge(a.status)}
                        <a href="/app/prontuario?patient=${encodeURIComponent(a.patient_id)}" class="text-xs font-semibold text-blue-700 hover:underline">Abrir prontuário<span class="sr-only"> de ${escapeHtml(a.patient_name || 'paciente')}</span></a></span></li>`).join('')}</ul>`
                : '<p class="text-sm text-slate-500">Nenhuma consulta hoje.</p>')}
            ${dailyCard('Consultas por dia (últimos 30 dias)', d.daily_30d)}
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                ${card('Exames solicitados por situação', '<div id="chart-exams"></div>')}
                ${card('Resultados recentes fora da referência', d.recent_abnormal_exams.length ? `<ul class="divide-y">${d.recent_abnormal_exams.map(e => `
                    <li class="py-2 text-sm"><strong>${escapeHtml(e.patient_name || '')}</strong> · ${escapeHtml(e.exam_name)}
                        <div class="flex flex-wrap gap-2 mt-1">${e.results.filter(r => r.flag !== 'NORMAL').map(r => `<span>${escapeHtml(r.analyte_name)} ${fmt(r.value)} ${flagBadge(r.flag)}</span>`).join('')}</div></li>`).join('')}</ul>`
                    : '<p class="text-sm text-slate-500">Nenhum.</p>')}
            </div>`;
        const subject = state.professionals.find(p => p.id === state.professionalId);
        if (subject?.professional_type === 'MEDICO') board.insertAdjacentHTML('beforeend', doctorsCard(state.professionals));
        renderDaily(d.daily_30d);
        renderBarChart($('chart-exams'), toItems(d.exams_requested).map(i => ({ ...i, label: labelOf(EXAM_STATUS, i.label) })),
                       { ariaLabel: 'Exames solicitados por situação' });
    },

    nursing: board => renderNursingBoard(board, { card, tile }),

    async pharmacy(board) {
        const d = await apiCall('/dashboards/pharmacy');
        board.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
                ${tile('Itens abaixo do mínimo', String(d.items_below_minimum))}
                ${tile('Itens zerados', String(d.zero_stock))}
                ${tile('Lotes vencendo (30 dias)', String(d.lots_expiring_30d))}
                ${tile('Lotes vencidos com saldo', String(d.lots_expired))}
                ${tile('Receitas na fila', String(d.dispensation_queue))}
            </div>
            ${card(`Unidades dispensadas por dia <span class="text-sm font-normal text-slate-500">(${fmt(d.units_dispensed_30d)} em 30 dias)</span>`, '<div id="chart-dispensed"></div>')}
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                ${card('Mais dispensados (30 dias)', '<div id="chart-top"></div>')}
                ${card('Alertas de estoque e validade', d.open_alerts.length ? `<ul class="space-y-1 text-sm">${d.open_alerts.map(a => `
                    <li>${a.level === 'CRITICO' ? '<span class="flag flag-critical"><i class="fas fa-triangle-exclamation" aria-hidden="true"></i>Crítico</span>' : '<span class="flag flag-attention"><i class="fas fa-circle-exclamation" aria-hidden="true"></i>Atenção</span>'} ${escapeHtml(a.title)}</li>`).join('')}</ul>`
                    : '<p class="text-sm text-slate-500">Nenhum alerta aberto.</p>')}
            </div>
            <a href="/app/farmacia" class="inline-block text-sm text-blue-700 font-semibold hover:underline">Ir para a farmácia</a>`;
        renderLineChart($('chart-dispensed'), [{ name: 'Unidades', color: 'var(--series-1)',
            points: d.daily_30d.map(p => ({ t: new Date(`${p.day}T12:00`), v: p.values.unidades })) }],
            { unit: 'un.', ariaLabel: 'Unidades dispensadas por dia' });
        renderBarChart($('chart-top'), d.top_medications_30d, { unit: 'un.', ariaLabel: 'Medicamentos mais dispensados' });
    },

    async admin(board) {
        const d = await apiCall('/dashboards/admin');
        const distribution = d.health_score_distribution;
        board.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                ${tile('Pacientes', String(d.counts.patients))}
                ${tile('Profissionais ativos', String(d.counts.professionals_active))}
                ${tile('Consultas (30 dias)', String(Object.values(d.appointments_30d).reduce((a, b) => a + b, 0)))}
                ${tile('Health Score médio', d.health_score_average == null ? '—' : fmt(d.health_score_average), 'indicador demonstrativo')}
            </div>
            ${dailyCard('Consultas por dia (últimos 30 dias)', d.daily_appointments_30d)}
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                ${card('Health Score dos pacientes', '<div id="chart-score"></div><p class="text-xs text-slate-500 mt-2">Faixas: bom ≥ 80, atenção 60–79, insuficiente &lt; 60.</p>')}
                ${card('Exames por situação (90 dias)', '<div id="chart-exams"></div>')}
                ${card('Novos pacientes por mês', '<div id="chart-patients"></div>')}
                ${card('Alertas abertos por categoria', '<div id="chart-alerts"></div>')}
            </div>`;
        renderDaily(d.daily_appointments_30d);
        renderBarChart($('chart-score'), Object.entries(distribution).map(([key, value]) => ({ label: BANDS[key].label, value })),
                       { ariaLabel: 'Distribuição do Health Score' });
        renderBarChart($('chart-exams'), toItems(d.exams_90d).map(i => ({ ...i, label: labelOf(EXAM_STATUS, i.label) })),
                       { ariaLabel: 'Exames por situação' });
        renderBarChart($('chart-patients'), d.new_patients_monthly, { ariaLabel: 'Novos pacientes por mês' });
        renderBarChart($('chart-alerts'), toItems(d.alerts_open.by_category), { ariaLabel: 'Alertas abertos por categoria' });
    },
};

// Gráfico diário com 3 séries + visão em tabela (o verde-água tem contraste < 3:1 e exige
// rótulos visíveis ou tabela; ver validação de paleta no ADR-019).
const DAILY_SERIES = [['FINALIZADA', 'var(--series-1)'], ['CANCELADA', 'var(--series-2)'], ['NAO_COMPARECEU', 'var(--series-3)']];

/** Área do médico: médicos ativos com o ID (para formulários que pedem o médico, como o portal). */
function doctorsCard(professionals) {
    const doctors = professionals.filter(p => p.professional_type === 'MEDICO');
    return card(`Médicos disponíveis <span class="text-sm font-normal text-slate-500">(${doctors.length} ativos)</span>`, `
        <p class="text-xs text-slate-600 mb-3">IDs para formulários que pedem o médico, como a evolução do portal. Dados fictícios.</p>
        <div class="overflow-x-auto"><table class="w-full text-sm">
            <thead><tr class="text-left text-slate-500 border-b">
                <th class="py-2 pr-3 font-medium">Médico(a)</th><th class="py-2 pr-3 font-medium">Especialidade</th>
                <th class="py-2 pr-3 font-medium">Registro</th><th class="py-2 pr-3 font-medium">ID</th>
                <th class="py-2 font-medium"><span class="sr-only">Ações</span></th></tr></thead>
            <tbody>${doctors.map(doctor => `<tr class="border-b last:border-0 align-top">
                <td class="py-2 pr-3">${escapeHtml(doctor.full_name)}</td>
                <td class="py-2 pr-3">${escapeHtml(doctor.specialty_name || '—')}</td>
                <td class="py-2 pr-3 whitespace-nowrap">${escapeHtml(doctor.registry_number)}</td>
                <td class="py-2 pr-3"><code class="text-xs break-all">${escapeHtml(doctor.id)}</code></td>
                <td class="py-2"><button type="button" data-copy-id="${escapeHtml(doctor.id)}"
                    aria-label="Copiar ID de ${escapeHtml(doctor.full_name)}"
                    class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100 whitespace-nowrap">Copiar ID</button></td>
            </tr>`).join('')}</tbody></table></div>`);
}

async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch {
        return false;
    }
}

function dailyCard(title, points) {
    const rows = points.filter(p => Object.values(p.values).some(v => v > 0)).map(p => `<tr class="border-b last:border-0">
        <td class="py-1 pr-3">${formatDate(`${p.day}T12:00`)}</td>${DAILY_SERIES.map(([key]) => `<td class="py-1 pr-3 text-right tabular-nums">${p.values[key] || 0}</td>`).join('')}</tr>`).join('');
    return card(title, `<div id="chart-daily"></div>
        <details class="mt-3"><summary class="text-sm text-blue-700 cursor-pointer">Ver como tabela</summary>
            <table class="w-full text-sm mt-2"><thead><tr class="text-left text-slate-500 border-b"><th class="py-1 pr-3 font-medium">Dia</th>
                ${DAILY_SERIES.map(([key]) => `<th class="py-1 pr-3 font-medium text-right">${labelOf(APPOINTMENT_STATUS, key)}</th>`).join('')}</tr></thead>
            <tbody>${rows || '<tr><td colspan="4" class="py-2 text-slate-500">Sem consultas no período.</td></tr>'}</tbody></table></details>`);
}

function renderDaily(points) {
    renderLineChart($('chart-daily'), DAILY_SERIES.map(([key, color]) => ({
        name: labelOf(APPOINTMENT_STATUS, key), color,
        points: points.map(p => ({ t: new Date(`${p.day}T12:00`), v: p.values[key] || 0 })),
    })), { ariaLabel: 'Consultas por dia' });
}

// --------------------------------------------------------- seleção de visão

async function renderSubject() {
    const subject = $('subject');
    if (state.view === 'patient') {
        subject.innerHTML = '<label class="text-sm text-slate-600 block">Paciente<span class="block"><input id="subject-patient" type="search" placeholder="Buscar por nome ou CPF" class="w-full p-2 border rounded-lg mt-1"></span></label>';
        createPatientPicker($('subject-patient'), { onSelect: p => { state.patientId = p.id; render(); } });
    } else if (state.view === 'professional') {
        const page = await apiCall('/professionals?status=ATIVO&limit=100');
        state.professionals = page.items;
        subject.innerHTML = `<label class="text-sm text-slate-600 block">Profissional<select id="subject-professional" class="w-full p-2 border rounded-lg mt-1">
            <option value="">Selecione</option>${page.items.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.full_name)}</option>`).join('')}</select></label>`;
        $('subject-professional').value = state.professionalId || '';
        $('subject-professional').addEventListener('change', event => { state.professionalId = event.target.value || null; render(); });
    } else {
        subject.innerHTML = '';
    }
}

async function render() {
    const board = $('board');
    renderLoading(board);
    try {
        await RENDER[state.view](board);
    } catch (err) {
        renderEmpty(board, `Erro: ${err.message}`);
    }
}

async function switchView(view) {
    state.view = view;
    $('views').innerHTML = Object.entries(VIEWS).map(([key, label]) => `
        <button data-view="${key}" role="tab" aria-selected="${key === view}"
            class="px-3 py-2 rounded-lg text-sm font-bold ${key === view ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}">${label}</button>`).join('');
    await renderSubject();
    render();
}

/** A visão inicial acompanha o perfil de demonstração escolhido no topo. */
function viewFromProfile() {
    const profile = getProfile();
    if (profile.audience === 'PACIENTE') state.patientId = profile.recipient_id;
    if (profile.audience === 'PROFISSIONAL') state.professionalId = profile.recipient_id;
    return dashboardViewFor(profile);
}

renderNav('painel');
renderDemoBanner();
document.addEventListener('click', async event => {
    const view = event.target.closest('[data-view]');
    if (view) switchView(view.dataset.view);
    const copy = event.target.closest('[data-copy-id]');
    if (copy) {
        const ok = await copyText(copy.dataset.copyId);
        toast(ok ? 'ID copiado.' : 'Não foi possível copiar. Selecione o ID na tabela.', ok ? 'success' : 'error');
    }
});
window.addEventListener('healthos:profile', () => switchView(viewFromProfile()));
switchView(viewFromProfile()).catch(err => toast(err.message, 'error'));
