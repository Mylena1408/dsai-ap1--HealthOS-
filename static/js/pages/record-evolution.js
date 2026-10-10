// Aba "Evolução" do prontuário: rascunho, edição e assinatura. Assinar é só mudar a situação
// do registro (sem senha — ADR-002); depois disso, a evolução não pode ser alterada.
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDateTime, toast, whileBusy } from '../core/dom.js';
import { EVOLUTION_STATUS, PROFESSIONAL_TYPES, badge } from '../core/labels.js';
import { activeProfessionals, fillAuthorSelect } from '../components/author-select.js';

const $ = id => document.getElementById(id);
const card = (title, body) => `<div class="glass-card rounded-2xl p-5"><h3 class="font-bold text-slate-800 mb-3">${title}</h3>${body}</div>`;
const smallButton = 'px-3 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100 disabled:opacity-50';
const textarea = (id, value = '') => `<textarea id="${id}" required minlength="10" maxlength="10000" rows="5"
    class="w-full p-2 border rounded-lg mt-1">${escapeHtml(value)}</textarea>`;

function evolutionItem(e) {
    const type = PROFESSIONAL_TYPES[e.professional_type] || '';
    return `<li class="py-3" data-evolution="${escapeHtml(e.id)}">
        <div class="flex flex-wrap justify-between items-center gap-2 text-sm">
            <span><strong>${escapeHtml(e.professional_name || 'Profissional')}</strong>${type ? ` <span class="text-slate-500">· ${escapeHtml(type)}</span>` : ''}
                <span class="text-slate-500">· ${formatDateTime(e.created_at)} · versão ${e.version}${e.signed_at ? ` · assinada em ${formatDateTime(e.signed_at)}` : ''}</span></span>
            ${badge(EVOLUTION_STATUS, e.status)}
        </div>
        <div data-evolution-body>
            <p class="text-sm text-slate-700 whitespace-pre-line mt-1">${escapeHtml(e.content)}</p>
            ${e.status === 'RASCUNHO' ? `<div class="flex gap-2 mt-2">
                <button type="button" data-evo-act="edit" class="${smallButton}">Editar</button>
                <button type="button" data-evo-act="sign" class="${smallButton} text-emerald-700">Assinar</button></div>` : ''}
        </div>
    </li>`;
}

export async function renderEvolutionTab(container, { patientId, onChange }) {
    const [evolutions, professionals] = await Promise.all([
        apiCall(`/patients/${patientId}/evolutions`), activeProfessionals(),
    ]);
    const path = id => `/patients/${patientId}/evolutions${id ? `/${id}` : ''}`;

    container.innerHTML = card('Nova evolução', `
            <form id="form-evolution" class="space-y-3">
                <label class="text-sm text-slate-600 block">Profissional responsável
                    <select id="evo-professional" required class="w-full p-2 border rounded-lg mt-1"></select></label>
                <label class="text-sm text-slate-600 block">Texto da evolução (mínimo de 10 caracteres)${textarea('evo-content')}</label>
                <p class="text-xs text-slate-600">O rascunho pode ser editado. Depois de assinada, a evolução não muda.</p>
                <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700 disabled:opacity-50">Salvar rascunho</button>
            </form>`)
        + card(`Evoluções <span class="text-sm font-normal text-slate-500">(${evolutions.length})</span>`, evolutions.length
            ? `<ul class="divide-y">${evolutions.map(evolutionItem).join('')}</ul>`
            : '<p class="text-sm text-slate-500">Nenhuma evolução registrada.</p>');

    fillAuthorSelect($('evo-professional'), professionals, { placeholder: 'Selecione' });

    $('form-evolution').addEventListener('submit', async event => {
        event.preventDefault();
        await whileBusy(event.submitter || event.target.querySelector('[type="submit"]'), async () => {
            try {
                await apiCall(path(), 'POST', { professional_id: $('evo-professional').value, content: $('evo-content').value });
                await onChange('Evolução salva como rascunho.');
            } catch (err) {
                toast(err.message, 'error');
            }
        });
    });

    container.querySelectorAll('[data-evo-act]').forEach(button => button.addEventListener('click', async () => {
        const item = button.closest('[data-evolution]');
        const evolution = evolutions.find(e => e.id === item.dataset.evolution);
        if (button.dataset.evoAct === 'edit') return openEditor(item, evolution);
        if (!window.confirm('Assinar esta evolução? Depois de assinada, ela não poderá ser alterada.')) return;
        await whileBusy(button, async () => {
            try {
                await apiCall(`${path(evolution.id)}/sign`, 'POST');
                await onChange('Evolução assinada.');
            } catch (err) {
                toast(err.message, 'error');
            }
        });
    }));

    function openEditor(item, evolution) {
        const editorId = `evo-edit-${evolution.id}`;
        item.querySelector('[data-evolution-body]').innerHTML = `
            <form data-evo-edit class="mt-2 space-y-2">
                <label class="text-xs text-slate-600 block">Editar texto${textarea(editorId, evolution.content)}</label>
                <div class="flex gap-2">
                    <button type="submit" class="${smallButton} text-blue-700">Salvar alterações</button>
                    <button type="button" data-evo-cancel class="${smallButton}">Cancelar</button></div>
            </form>`;
        const form = item.querySelector('[data-evo-edit]');
        $(editorId).focus();
        form.querySelector('[data-evo-cancel]').addEventListener('click', () => onChange());
        form.addEventListener('submit', async event => {
            event.preventDefault();
            await whileBusy(form.querySelector('[type="submit"]'), async () => {
                try {
                    await apiCall(path(evolution.id), 'PATCH', { content: $(editorId).value });
                    await onChange('Rascunho atualizado.');
                } catch (err) {
                    toast(err.message, 'error');
                }
            });
        });
    }
}
