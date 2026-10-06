// Assistente educacional: funções pontuais sobre o prontuário e chat com histórico.
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDateTime, renderEmpty, renderLoading, toast } from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { renderPagination } from '../components/pagination.js';
import { createPatientPicker } from '../components/patient-picker.js';
import {
    aiResponseCard, answerText, factsUsed, providerBadge, urgentNotice,
} from '../components/ai-response.js';

const PAGE_SIZE = 10;
const $ = id => document.getElementById(id);
const state = { patient: null, conversation: null, convOffset: 0, sending: false };

// ---------------------------------------------------------------- paciente

function setPatient(patient) {
    state.patient = patient;
    state.conversation = null;
    state.convOffset = 0;
    history.replaceState(null, '', patient ? `?patient=${encodeURIComponent(patient.id)}` : window.location.pathname);
    $('patient-info').textContent = patient
        ? `${patient.full_name} · ${patient.age} anos. As respostas usam só primeiro nome, idade e registros clínicos.`
        : 'Nenhum paciente selecionado: perguntas gerais.';
    $('btn-summary').disabled = $('btn-insights').disabled = !patient;
    $('btn-clear-patient').classList.toggle('hidden', !patient);
    $('ai-result').classList.add('hidden');
    renderConversation();
    loadConversations();
}

async function preselect(patientId) {
    try {
        const record = await apiCall(`/patients/${encodeURIComponent(patientId)}/record`);
        $('patient-search').value = record.patient.full_name;
        setPatient({ id: record.patient.id, full_name: record.patient.full_name, age: record.age });
    } catch (err) {
        toast(err.message, 'error');
        setPatient(null);
    }
}

// ------------------------------------------------------- funções pontuais

async function runFeature(button, request, { needsPatient = true } = {}) {
    const target = $('ai-result');
    target.classList.remove('hidden');
    renderLoading(target, 'Consultando o assistente...');
    button.disabled = true;
    try {
        target.innerHTML = aiResponseCard(await request());
    } catch (err) {
        renderEmpty(target, `Erro: ${err.message}`);
    } finally {
        button.disabled = needsPatient && !state.patient;
    }
}

// --------------------------------------------------------------- conversas

async function loadConversations() {
    const list = $('conversations');
    renderLoading(list);
    const params = new URLSearchParams({ status: $('conv-status').value, limit: PAGE_SIZE, offset: state.convOffset });
    if (state.patient) params.set('patient_id', state.patient.id);
    try {
        const page = await apiCall(`/conversations?${params}`);
        if (!page.items.length) renderEmpty(list, 'Nenhuma conversa.');
        else list.innerHTML = page.items.map(c => `
            <li><button data-conversation="${escapeHtml(c.id)}"
                class="w-full text-left px-2 py-2 rounded-lg hover:bg-blue-50 ${c.id === state.conversation?.id ? 'bg-blue-50' : ''}">
                <div class="text-sm font-medium text-slate-800 truncate">${escapeHtml(c.title)}</div>
                <div class="text-xs text-slate-500">${formatDateTime(c.updated_at || c.created_at)}</div>
            </button></li>`).join('');
        renderPagination($('conv-pagination'), page, offset => { state.convOffset = offset; loadConversations(); });
    } catch (err) {
        renderEmpty(list, `Erro: ${err.message}`);
    }
}

async function openConversation(id) {
    renderLoading($('messages'));
    try {
        state.conversation = await apiCall(`/conversations/${id}`);
        renderConversation();
        loadConversations();
    } catch (err) {
        renderEmpty($('messages'), `Erro: ${err.message}`);
    }
}

function bubble(message) {
    if (message.role === 'USUARIO') {
        return `<div class="flex justify-end"><div class="max-w-[85%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2 text-sm whitespace-pre-line">${escapeHtml(message.content)}</div></div>`;
    }
    return `<div class="flex justify-start"><div class="max-w-[85%] bg-white border rounded-2xl rounded-bl-sm px-4 py-3 space-y-2">
        ${message.urgent ? urgentNotice() : ''}
        ${answerText(message.content)}
        ${factsUsed(message.facts_used)}
        <div class="text-[11px] text-slate-500">${escapeHtml(message.provider || '')} · ${formatDateTime(message.created_at)}</div>
    </div></div>`;
}

function renderConversation() {
    const conversation = state.conversation;
    const archived = conversation?.status === 'ARQUIVADA';
    $('chat-title').textContent = conversation ? conversation.title : 'Nova conversa';
    $('btn-archive').classList.toggle('hidden', !conversation || archived);
    $('message').disabled = $('btn-send').disabled = archived || state.sending;
    $('message').placeholder = archived ? 'Conversa arquivada: somente leitura.' : 'Pergunte sobre exames, medicamentos, sinais vitais...';

    const messages = conversation?.messages || [];
    if (!messages.length) {
        renderEmpty($('messages'), state.patient
            ? `Pergunte sobre os registros de ${state.patient.full_name.split(' ')[0]}.`
            : 'Selecione um paciente para perguntas sobre o prontuário, ou faça uma pergunta geral.');
    } else {
        $('messages').innerHTML = messages.map(bubble).join('');
        $('messages').scrollTop = $('messages').scrollHeight;
    }
    const last = messages[messages.length - 1];
    const suggestions = !archived && last?.role === 'ASSISTENTE' ? last.suggestions : [];
    $('suggestions').innerHTML = suggestions.map(s => `
        <button data-suggestion="${escapeHtml(s)}" class="px-3 py-1 rounded-full border text-xs text-blue-700 bg-blue-50 hover:bg-blue-100">${escapeHtml(s)}</button>`).join('');
}

async function sendMessage(content) {
    const text = content.trim();
    if (!text || state.sending) return;
    state.sending = true;
    try {
        if (!state.conversation) {
            state.conversation = await apiCall('/conversations', 'POST', { patient_id: state.patient?.id || null });
        }
        state.conversation.messages.push({ role: 'USUARIO', content: text });
        renderConversation();
        $('messages').insertAdjacentHTML('beforeend',
            '<p id="typing" class="text-sm text-slate-500"><i class="fas fa-ellipsis fa-fade" aria-hidden="true"></i> Assistente respondendo...</p>');
        const exchange = await apiCall(`/conversations/${state.conversation.id}/messages`, 'POST', { content: text });
        state.conversation.messages.splice(-1, 1, exchange.user_message, exchange.assistant_message);
        if (state.conversation.messages.length === 2) state.conversation.title = exchange.user_message.content.slice(0, 80);
        $('message').value = '';
        loadConversations();
    } catch (err) {
        state.conversation?.messages.pop();  // a pergunta não foi registrada
        toast(err.message, 'error');
    } finally {
        state.sending = false;
        renderConversation();
        $('message').focus();
    }
}

// ------------------------------------------------------------------ início

renderNav('assistente');
renderDemoBanner();
createPatientPicker($('patient-search'), { onSelect: setPatient });

apiCall('/ai/status').then(status => {
    $('provider').innerHTML = providerBadge(status);
    $('disclaimer').innerHTML = `<i class="fas fa-circle-info" aria-hidden="true"></i> ${escapeHtml(status.disclaimer)}`;
}).catch(err => toast(err.message, 'error'));

$('btn-summary').addEventListener('click', event =>
    runFeature(event.currentTarget, () => apiCall(`/ai/patients/${state.patient.id}/summary`, 'POST')));
$('btn-insights').addEventListener('click', event =>
    runFeature(event.currentTarget, () => apiCall(`/ai/patients/${state.patient.id}/insights`, 'POST')));
$('btn-clear-patient').addEventListener('click', () => { $('patient-search').value = ''; setPatient(null); });
$('form-symptoms').addEventListener('submit', event => {
    event.preventDefault();
    runFeature(event.currentTarget.querySelector('button'), () => apiCall('/ai/symptoms', 'POST', {
        description: $('symptoms').value.trim(), patient_id: state.patient?.id || null,
    }), { needsPatient: false });
});

$('btn-new').addEventListener('click', () => { state.conversation = null; renderConversation(); loadConversations(); $('message').focus(); });
$('conv-status').addEventListener('change', () => { state.convOffset = 0; loadConversations(); });
$('btn-archive').addEventListener('click', async () => {
    try {
        state.conversation = { ...await apiCall(`/conversations/${state.conversation.id}/archive`, 'POST'),
                               messages: state.conversation.messages };
        toast('Conversa arquivada.', 'success');
        renderConversation();
        loadConversations();
    } catch (err) {
        toast(err.message, 'error');
    }
});

$('form-message').addEventListener('submit', event => { event.preventDefault(); sendMessage($('message').value); });
$('message').addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage($('message').value); }
});
document.addEventListener('click', event => {
    const conversation = event.target.closest('[data-conversation]');
    if (conversation) return openConversation(conversation.dataset.conversation);
    const suggestion = event.target.closest('[data-suggestion]');
    if (suggestion) sendMessage(suggestion.dataset.suggestion);
});

const preselected = new URLSearchParams(window.location.search).get('patient');
if (preselected) preselect(preselected);
else setPatient(null);
