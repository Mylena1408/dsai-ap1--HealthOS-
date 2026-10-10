// Abas de sinais vitais e exames do prontuário.
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDateTime, toast, whileBusy } from '../core/dom.js';
import {
    BMI_CATEGORIES, EXAM_PRIORITY, EXAM_STATUS, RESULT_FLAGS, badge, fillSelect, flagBadge,
} from '../core/labels.js';
import { aiResponseCard } from '../components/ai-response.js';
import { activeProfessionals, fillAuthorSelect } from '../components/author-select.js';
import { renderLineChart } from '../components/line-chart.js';

const $ = id => document.getElementById(id);
const card = (title, body, extra = '') => `
    <div class="glass-card rounded-2xl p-5 ${extra}">
        <h3 class="font-bold text-slate-800 mb-3">${title}</h3>${body}</div>`;
const TREND = {
    SUBINDO: '<i class="fas fa-arrow-trend-up" aria-hidden="true"></i> subindo',
    DESCENDO: '<i class="fas fa-arrow-trend-down" aria-hidden="true"></i> descendo',
    ESTAVEL: '<i class="fas fa-equals" aria-hidden="true"></i> estável',
};
const fmt = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
// Gráficos individuais (cada métrica tem escala própria: nunca dois eixos no mesmo gráfico).
const CHARTS = [
    { id: 'pressure', title: 'Pressão arterial', metrics: ['systolic', 'diastolic'] },
    { id: 'heart_rate', title: 'Frequência cardíaca', metrics: ['heart_rate'] },
    { id: 'temperature', title: 'Temperatura', metrics: ['temperature'] },
    { id: 'oxygen_saturation', title: 'Saturação de O₂', metrics: ['oxygen_saturation'] },
    { id: 'weight_kg', title: 'Peso', metrics: ['weight_kg'] },
    { id: 'bmi', title: 'IMC', metrics: ['bmi'] },
    { id: 'glucose_mg_dl', title: 'Glicemia capilar', metrics: ['glucose_mg_dl'] },
];
const SERIES_COLORS = ['var(--series-1)', 'var(--series-2)'];

// ------------------------------------------------------------------ sinais vitais

export async function renderVitalsTab(container, { patientId, onChange }) {
    const [summary, page, professionals] = await Promise.all([
        apiCall(`/patients/${patientId}/vital-signs/summary`),
        apiCall(`/patients/${patientId}/vital-signs?limit=20`),
        activeProfessionals(),
    ]);
    const metrics = Object.fromEntries(summary.metrics.map(m => [m.metric, m]));
    const tiles = summary.metrics.filter(m => m.metric !== 'height_cm').map(m => `
        <div class="glass-card rounded-2xl p-4">
            <div class="text-xs text-slate-500">${escapeHtml(m.label)}</div>
            <div class="text-2xl font-semibold text-slate-900">${fmt(m.latest)} <span class="text-sm font-normal text-slate-500">${escapeHtml(m.unit)}</span></div>
            <div class="flex flex-wrap items-center gap-2 mt-1 text-xs text-slate-600">
                ${m.flag ? flagBadge(m.flag) : ''}${m.trend ? `<span>${TREND[m.trend]}</span>` : ''}
            </div>
            ${m.reference ? `<div class="text-xs text-slate-500 mt-1">Referência: ${escapeHtml(m.reference)}</div>` : ''}
        </div>`).join('');
    const charts = CHARTS.filter(c => c.metrics.some(m => metrics[m]));

    const rows = page.items.map(v => {
        const flagged = Object.entries(v.flags).filter(([, flag]) => flag !== 'NORMAL');
        return `<tr class="border-b last:border-0 align-top">
            <td class="py-2 pr-3 whitespace-nowrap">${formatDateTime(v.recorded_at)}</td>
            <td class="py-2 pr-3 tabular-nums">${v.systolic ? `${v.systolic}/${v.diastolic}` : '—'}</td>
            <td class="py-2 pr-3 tabular-nums">${v.heart_rate ?? '—'}</td>
            <td class="py-2 pr-3 tabular-nums">${v.temperature != null ? fmt(v.temperature) : '—'}</td>
            <td class="py-2 pr-3 tabular-nums">${v.oxygen_saturation ?? '—'}</td>
            <td class="py-2 pr-3 tabular-nums">${v.weight_kg != null ? fmt(v.weight_kg) : '—'}</td>
            <td class="py-2 pr-3 tabular-nums">${v.bmi != null ? `${fmt(v.bmi)} <span class="text-xs text-slate-500">${escapeHtml(BMI_CATEGORIES[v.bmi_category] || '')}</span>` : '—'}</td>
            <td class="py-2">${flagged.length ? flagged.map(([metric, flag]) => `<div class="mb-1"><span class="text-xs text-slate-500">${escapeHtml(metrics[metric]?.label || metric)}</span> ${flagBadge(flag)}</div>`).join('') : flagBadge('NORMAL')}</td>
        </tr>`;
    }).join('');

    container.innerHTML = `
        ${summary.metrics.length ? `<div class="grid grid-cols-2 md:grid-cols-4 gap-3">${tiles}</div>` : ''}
        ${charts.length ? `<div class="grid grid-cols-1 md:grid-cols-2 gap-4">${charts.map(c => card(c.title, `<div id="chart-${c.id}"></div>`)).join('')}</div>` : ''}
        ${card('Registrar medição', `
            <form id="form-vitals" class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                ${[['v-sys', 'Sistólica (mmHg)'], ['v-dia', 'Diastólica (mmHg)'], ['v-hr', 'FC (bpm)'], ['v-rr', 'FR (irpm)'],
                   ['v-temp', 'Temperatura (°C)', '0.1'], ['v-spo2', 'SpO₂ (%)'], ['v-weight', 'Peso (kg)', '0.1'],
                   ['v-height', 'Altura (cm)', '0.1'], ['v-glucose', 'Glicemia (mg/dL)']].map(([id, label, step]) => `
                    <label class="text-xs text-slate-600">${label}
                        <input id="${id}" type="number" ${step ? `step="${step}"` : ''} class="w-full p-2 border rounded-lg mt-1"></label>`).join('')}
                <label class="text-xs text-slate-600 col-span-2">Registrado por
                    <select id="v-author" class="w-full p-2 border rounded-lg mt-1"></select></label>
                <div class="col-span-2 sm:col-span-4"><button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700">Registrar</button></div>
            </form>`)}
        ${card(`Histórico <span class="text-sm font-normal text-slate-500">(${page.total} registros)</span>`, page.items.length ? `
            <div class="relative overflow-x-auto" tabindex="0" role="region" aria-label="Histórico de sinais vitais (tabela)"><table class="w-full text-sm">
                <thead><tr class="text-left text-slate-500 border-b">
                    <th class="py-2 pr-3 font-medium">Data</th><th class="py-2 pr-3 font-medium">PA</th><th class="py-2 pr-3 font-medium">FC</th>
                    <th class="py-2 pr-3 font-medium">Temp</th><th class="py-2 pr-3 font-medium">SpO₂</th><th class="py-2 pr-3 font-medium">Peso</th>
                    <th class="py-2 pr-3 font-medium">IMC</th><th class="py-2 font-medium">Classificação</th></tr></thead>
                <tbody>${rows}</tbody></table></div>` : '<p class="text-sm text-slate-500">Nenhuma medição registrada.</p>')}
        <p class="text-xs text-amber-700"><i class="fas fa-circle-info"></i> ${escapeHtml(summary.disclaimer)}</p>`;

    charts.forEach(c => {
        const series = c.metrics.filter(m => metrics[m]).map((m, i) => ({
            name: metrics[m].label, color: SERIES_COLORS[i],
            points: metrics[m].series.map(([t, v]) => ({ t: new Date(t), v })),
        }));
        // Faixa de referência apenas em gráficos de uma série (na pressão, cada série tem a sua).
        const only = c.metrics.length === 1 ? metrics[c.metrics[0]] : null;
        renderLineChart($(`chart-${c.id}`), series, {
            unit: metrics[c.metrics[0]].unit, ariaLabel: c.title,
            reference: only && (only.normal_min != null || only.normal_max != null)
                ? { min: only.normal_min, max: only.normal_max } : null,
        });
    });

    fillAuthorSelect($('v-author'), professionals);
    $('form-vitals').addEventListener('submit', async event => {
        event.preventDefault();
        const number = id => ($(id).value === '' ? null : Number($(id).value));
        await whileBusy(event.target.querySelector('[type="submit"]'), async () => {
            try {
                await apiCall(`/patients/${patientId}/vital-signs`, 'POST', {
                    systolic: number('v-sys'), diastolic: number('v-dia'), heart_rate: number('v-hr'),
                    respiratory_rate: number('v-rr'), temperature: number('v-temp'), oxygen_saturation: number('v-spo2'),
                    weight_kg: number('v-weight'), height_cm: number('v-height'), glucose_mg_dl: number('v-glucose'),
                    professional_id: $('v-author').value || null,
                });
                await onChange('Medição registrada.');
            } catch (err) {
                toast(err.message, 'error');
            }
        });
    });
}

// -------------------------------------------------------------------- exames

function resultsTable(exam) {
    return `<table class="w-full text-sm mt-2">
        <thead><tr class="text-left text-slate-500 border-b"><th class="py-1 pr-3 font-medium">Analito</th>
            <th class="py-1 pr-3 font-medium text-right">Resultado</th><th class="py-1 pr-3 font-medium">Referência</th>
            <th class="py-1 font-medium">Classificação</th></tr></thead>
        <tbody>${exam.results.map(r => `<tr class="border-b last:border-0">
            <td class="py-1 pr-3"><button data-analyte="${escapeHtml(r.analyte_code)}" class="text-blue-700 hover:underline"
                title="Ver evolução">${escapeHtml(r.analyte_name)}</button></td>
            <td class="py-1 pr-3 text-right tabular-nums font-semibold">${fmt(r.value)} <span class="font-normal text-slate-500">${escapeHtml(r.unit)}</span></td>
            <td class="py-1 pr-3 text-slate-500">${escapeHtml(r.reference_text)}</td>
            <td class="py-1">${flagBadge(r.flag)}</td></tr>`).join('')}</tbody></table>`;
}

export async function renderExamsTab(container, { patientId, onChange }) {
    const [page, examTypes, professionals] = await Promise.all([
        apiCall(`/exam-requests?patient_id=${patientId}&limit=50`),
        apiCall('/exam-types'),
        activeProfessionals(),
    ]);
    const items = page.items.map(e => `
        <li class="py-3">
            <div class="flex flex-wrap justify-between items-center gap-2">
                <span><strong>${escapeHtml(e.exam_name)}</strong>
                    <span class="text-sm text-slate-500">· solicitado em ${formatDateTime(e.requested_at)}${e.requested_by_name ? ` por ${escapeHtml(e.requested_by_name)}` : ''}</span></span>
                <span class="flex gap-2 items-center">${e.priority === 'URGENTE' ? '<span class="text-xs font-semibold text-red-700">URGENTE</span>' : ''}${badge(EXAM_STATUS, e.status)}</span>
            </div>
            ${e.status === 'LIBERADO' ? resultsTable(e) + `
                <button data-explain="${escapeHtml(e.id)}" class="mt-2 px-3 py-1 rounded-lg border text-xs font-semibold text-blue-700 hover:bg-blue-50">
                    <i class="fas fa-robot" aria-hidden="true"></i> Explicar resultado (IA)</button>
                <div data-explanation="${escapeHtml(e.id)}" class="hidden mt-2 bg-slate-50 border rounded-xl p-3" aria-live="polite"></div>`
                : `<p class="text-xs text-slate-500 mt-1">${e.status === 'CANCELADO' ? `Cancelado: ${escapeHtml(e.cancellation_reason || '')}`
                    : 'Resultados disponíveis após validação e liberação pelo laboratório.'}</p>`}
        </li>`).join('');

    container.innerHTML = `
        <div id="analyte-chart-card" class="hidden"></div>
        ${card(`Exames <span class="text-sm font-normal text-slate-500">(${page.total})</span>`,
            items ? `<ul class="divide-y">${items}</ul>` : '<p class="text-sm text-slate-500">Nenhum exame solicitado.</p>')}
        ${card('Solicitar exame', `
            <form id="form-exam" class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <select id="e-type" required class="p-2 border rounded-lg"></select>
                <select id="e-priority" class="p-2 border rounded-lg"></select>
                <input id="e-indication" maxlength="500" placeholder="Indicação clínica (opcional)" aria-label="Indicação clínica (opcional)" class="p-2 border rounded-lg">
                <label class="text-xs text-slate-600 sm:col-span-2">Solicitado por
                    <select id="e-author" class="w-full p-2 border rounded-lg mt-1"></select></label>
                <div><button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700">Solicitar</button></div>
            </form>`)}`;

    fillSelect($('e-type'), Object.fromEntries(examTypes.map(t => [t.id, t.name])), 'Tipo de exame');
    fillSelect($('e-priority'), EXAM_PRIORITY);
    fillAuthorSelect($('e-author'), professionals);
    $('form-exam').addEventListener('submit', async event => {
        event.preventDefault();
        await whileBusy(event.target.querySelector('[type="submit"]'), async () => {
            try {
                await apiCall('/exam-requests', 'POST', {
                    patient_id: patientId, exam_type_id: $('e-type').value, priority: $('e-priority').value,
                    clinical_indication: $('e-indication').value || null, requested_by: $('e-author').value || null,
                });
                await onChange('Exame solicitado. Acompanhe o andamento em Laboratório.');
            } catch (err) {
                toast(err.message, 'error');
            }
        });
    });

    container.querySelectorAll('[data-explain]').forEach(button => button.addEventListener('click', async () => {
        const target = container.querySelector(`[data-explanation="${button.dataset.explain}"]`);
        target.classList.remove('hidden');
        target.innerHTML = '<p class="text-sm text-slate-500"><i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Consultando o assistente...</p>';
        button.disabled = true;
        try {
            target.innerHTML = aiResponseCard(await apiCall(`/ai/exams/${button.dataset.explain}/analysis`, 'POST'));
        } catch (err) {
            target.innerHTML = `<p class="text-sm text-red-700">${escapeHtml(err.message)}</p>`;
        } finally {
            button.disabled = false;
        }
    }));

    container.querySelectorAll('[data-analyte]').forEach(button => button.addEventListener('click', async () => {
        const history = await apiCall(`/patients/${patientId}/exams/analytes/${encodeURIComponent(button.dataset.analyte)}/history`);
        const target = $('analyte-chart-card');
        target.className = '';
        target.innerHTML = card(`Evolução: ${escapeHtml(history.analyte_name || button.dataset.analyte)}
            <span class="text-sm font-normal text-slate-500">(referência ${escapeHtml(history.reference_text || '—')})</span>`,
            '<div id="analyte-chart"></div>');
        const exam = page.items.flatMap(e => e.results).find(r => r.analyte_code === button.dataset.analyte);
        const type = examTypes.flatMap(t => t.analytes).find(a => a.code === button.dataset.analyte);
        renderLineChart($('analyte-chart'), [{
            name: history.analyte_name, color: 'var(--series-1)',
            points: history.points.map(([t, v, flag]) => ({ t: new Date(t), v, note: RESULT_FLAGS[flag]?.label })),
        }], { unit: history.unit || exam?.unit || '', ariaLabel: `Evolução de ${history.analyte_name}`,
              reference: type ? { min: type.normal_min, max: type.normal_max } : null });
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }));
}
