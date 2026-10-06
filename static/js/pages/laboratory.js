// Fila do laboratório: etapas, filtros e ações permitidas para cada exame.
import { apiCall } from '../core/api.js';
import {
    closeModal, enableModalDismiss, escapeHtml, formatDateTime, openModal, renderEmpty, renderLoading, toast,
} from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { EXAM_PRIORITY, EXAM_STATUS, badge, fillSelect, flagBadge } from '../core/labels.js';
import { renderPagination } from '../components/pagination.js';

const PAGE_SIZE = 15;
const $ = id => document.getElementById(id);
const state = { stage: 'EM_PROCESSAMENTO', offset: 0, byId: {}, examTypes: {}, validators: {}, pending: null };
const fmt = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 2 });

// Ação da interface para cada status de destino. Quando a mesma transição significa coisas
// diferentes (EM_PROCESSAMENTO = iniciar ou devolver), decide-se pelo status atual.
function actionsFor(exam) {
    return exam.allowed_transitions.map(target => {
        if (target === 'AGENDADO') return { key: 'schedule', label: exam.status === 'AGENDADO' ? 'Reagendar' : 'Agendar coleta', icon: 'fa-calendar' };
        if (target === 'COLETADO') return { key: 'collect', label: 'Registrar coleta', icon: 'fa-vial' };
        if (target === 'EM_PROCESSAMENTO') return exam.status === 'RESULTADO_REGISTRADO'
            ? { key: 'return', label: 'Devolver p/ correção', icon: 'fa-rotate-left' }
            : { key: 'start-processing', label: 'Iniciar processamento', icon: 'fa-flask' };
        if (target === 'RESULTADO_REGISTRADO') return { key: 'results', label: 'Registrar resultados', icon: 'fa-keyboard' };
        if (target === 'VALIDADO') return { key: 'validate', label: 'Validar', icon: 'fa-user-check' };
        if (target === 'LIBERADO') return { key: 'release', label: 'Liberar ao paciente', icon: 'fa-paper-plane' };
        return { key: 'cancel', label: 'Cancelar', icon: 'fa-ban' };
    });
}

function examCard(e) {
    const buttons = [...actionsFor(e), { key: 'history', label: 'Histórico', icon: 'fa-clock-rotate-left' }]
        .map(a => `<button data-act="${a.key}" data-id="${escapeHtml(e.id)}" class="px-3 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">
            <i class="fas ${a.icon}" aria-hidden="true"></i> ${a.label}</button>`).join('');
    const results = e.results.length ? `
        <div class="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-sm">${e.results.map(r => `
            <span>${escapeHtml(r.analyte_name)}: <strong class="tabular-nums">${fmt(r.value)}</strong> ${escapeHtml(r.unit)} ${flagBadge(r.flag)}</span>`).join('')}
        </div>` : '';
    return `
        <article class="glass-card rounded-2xl p-4">
            <div class="flex flex-wrap justify-between items-start gap-2">
                <div>
                    <div class="font-bold text-slate-800">${escapeHtml(e.exam_name)} <span class="text-slate-400 font-normal">· ${escapeHtml(e.patient_name || '')}</span></div>
                    <div class="text-xs text-slate-500">Solicitado ${formatDateTime(e.requested_at)}
                        ${e.scheduled_for && e.status === 'AGENDADO' ? ` · coleta prevista ${formatDateTime(e.scheduled_for)}` : ''}
                        ${e.sample_code ? ` · amostra ${escapeHtml(e.sample_code)}` : ''}
                        ${e.expected_by && !['LIBERADO', 'VALIDADO'].includes(e.status) ? ` · prazo ${formatDateTime(e.expected_by)}` : ''}
                        ${e.laboratory_name ? ` · ${escapeHtml(e.laboratory_name)}` : ''}</div>
                </div>
                <div class="flex gap-2 items-center">${e.priority === 'URGENTE' ? '<span class="text-xs font-semibold text-red-700"><i class="fas fa-bolt" aria-hidden="true"></i> Urgente</span>' : ''}${badge(EXAM_STATUS, e.status)}</div>
            </div>
            ${results}
            <div class="flex flex-wrap gap-2 mt-3">${buttons}</div>
        </article>`;
}

async function loadStages() {
    // Uma contagem por etapa (consulta leve: limit=1, só o total interessa).
    const counts = await Promise.all(Object.keys(EXAM_STATUS).map(async status =>
        [status, (await apiCall(`/exam-requests?status=${status}&limit=1`)).total]));
    $('stages').innerHTML = counts.map(([status, total]) => `
        <button data-stage="${status}" aria-pressed="${status === state.stage}"
            class="px-3 py-2 rounded-xl text-sm font-semibold border ${status === state.stage ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-700 hover:bg-slate-50'}">
            ${escapeHtml(EXAM_STATUS[status].label)} <span class="ml-1 tabular-nums opacity-80">${total}</span></button>`).join('');
}

async function loadList() {
    const list = $('list');
    renderLoading(list);
    const params = new URLSearchParams({ status: state.stage, limit: PAGE_SIZE, offset: state.offset,
                                         newest_first: String(['LIBERADO', 'CANCELADO'].includes(state.stage)) });
    if ($('f-type').value) params.set('exam_type_id', $('f-type').value);
    if ($('f-priority').value) params.set('priority', $('f-priority').value);
    if ($('f-abnormal').checked) params.set('only_abnormal', 'true');
    try {
        const page = await apiCall(`/exam-requests?${params}`);
        page.items.forEach(e => { state.byId[e.id] = e; });
        if (!page.items.length) renderEmpty(list, 'Nenhum exame nesta etapa.');
        else list.innerHTML = page.items.map(examCard).join('');
        renderPagination($('pagination'), page, offset => { state.offset = offset; loadList(); });
    } catch (err) {
        renderEmpty(list, `Erro: ${err.message}`);
    }
}

async function refresh(message) {
    if (message) toast(message, 'success');
    await Promise.all([loadStages(), loadList()]);
}

// --------------------------------------------------------------- ações

function ask(title, fieldsHtml, submit) {
    $('action-title').innerText = title;
    $('action-fields').innerHTML = fieldsHtml;
    state.pending = submit;
    openModal('modal-action');
}

function localInputValue(date) {
    const pad = n => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

async function post(id, path, body = null, message = 'Exame atualizado.') {
    try {
        await apiCall(`/exam-requests/${id}/${path}`, 'POST', body);
        closeModal('modal-action');
        await refresh(message);
    } catch (err) {
        toast(err.message, 'error');
    }
}

function handle(key, id) {
    const exam = state.byId[id];
    const reason = (label) => `<label class="text-sm text-slate-600">${label}
        <textarea id="a-reason" required minlength="3" maxlength="500" class="w-full p-2 border rounded-lg h-24 mt-1"></textarea></label>`;
    switch (key) {
    case 'schedule': {
        const tomorrow = new Date(Date.now() + 86400000);
        tomorrow.setHours(8, 0, 0, 0);
        return ask('Agendar coleta', `<label class="text-sm text-slate-600">Data e hora
            <input id="a-date" type="datetime-local" required value="${localInputValue(tomorrow)}" class="w-full p-2 border rounded-lg mt-1"></label>`,
            () => post(id, 'schedule', { scheduled_for: $('a-date').value }, 'Coleta agendada.'));
    }
    case 'results': {
        const type = state.examTypes[exam.exam_type_id];
        return ask(`Resultados — ${exam.exam_name}`, type.analytes.map(a => `
            <label class="text-sm text-slate-600 block">${escapeHtml(a.name)} <span class="text-slate-400">(${escapeHtml(a.unit)} · ref. ${escapeHtml(a.reference)})</span>
                <input data-analyte="${escapeHtml(a.code)}" type="number" step="any" required class="w-full p-2 border rounded-lg mt-1"></label>`).join('') +
            '<label class="text-sm text-slate-600 block">Observações<input id="a-notes" maxlength="2000" class="w-full p-2 border rounded-lg mt-1"></label>' +
            '<p class="text-xs text-amber-700">Valores fictícios para demonstração.</p>',
            () => post(id, 'results', {
                values: Object.fromEntries([...document.querySelectorAll('#action-fields [data-analyte]')]
                    .map(input => [input.dataset.analyte, Number(input.value)])),
                notes: $('a-notes').value || null,
            }, 'Resultados registrados; aguardando validação.'));
    }
    case 'validate':
        ask('Validar laudo', `<label class="text-sm text-slate-600">Profissional responsável
            <select id="a-validator" required class="w-full p-2 border rounded-lg mt-1"></select></label>`,
            () => post(id, 'validate', { professional_id: $('a-validator').value }, 'Laudo validado.'));
        return fillSelect($('a-validator'), state.validators, 'Selecione');
    case 'return':
        return ask('Devolver para correção', reason('Motivo'), () => post(id, 'return', { reason: $('a-reason').value }, 'Laudo devolvido para correção.'));
    case 'cancel':
        return ask('Cancelar exame', reason('Motivo do cancelamento'), () => post(id, 'cancel', { reason: $('a-reason').value }, 'Exame cancelado.'));
    case 'history':
        $('history-body').innerHTML = exam.history.map(h => `
            <li class="text-sm"><div class="text-xs text-slate-500">${formatDateTime(h.changed_at)}</div>
                ${badge(EXAM_STATUS, h.to_status)}${h.note ? ` <span class="text-slate-600">${escapeHtml(h.note)}</span>` : ''}</li>`).join('');
        return openModal('modal-history');
    default: // collect, start-processing, release: sem dados adicionais
        return post(id, key, null);
    }
}

async function init() {
    renderNav('laboratorio');
    renderDemoBanner();
    enableModalDismiss();

    const [types, professionals] = await Promise.all([apiCall('/exam-types'), apiCall('/professionals?status=ATIVO&limit=100')]);
    state.examTypes = Object.fromEntries(types.map(t => [t.id, t]));
    state.validators = Object.fromEntries(professionals.items.map(p => [p.id, p.full_name]));
    fillSelect($('f-type'), Object.fromEntries(types.map(t => [t.id, t.name])), 'Todos');
    fillSelect($('f-priority'), EXAM_PRIORITY, 'Todas');

    $('filters').addEventListener('change', () => { state.offset = 0; loadList(); });
    $('form-action').addEventListener('submit', event => { event.preventDefault(); state.pending?.(); });
    document.addEventListener('click', event => {
        const stage = event.target.closest('[data-stage]');
        if (stage) { state.stage = stage.dataset.stage; state.offset = 0; return refresh(); }
        const action = event.target.closest('[data-act]');
        if (action) handle(action.dataset.act, action.dataset.id);
    });
    await refresh();
}

init().catch(err => toast(err.message, 'error'));
