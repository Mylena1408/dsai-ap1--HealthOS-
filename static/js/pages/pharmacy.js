// Farmácia: fila de dispensação, estoque, validade e movimentações.
import { apiCall } from '../core/api.js';
import {
    enableModalDismiss, escapeHtml, formatDate, formatDateTime, openModal, renderEmpty, renderLoading, toast,
} from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { MOVEMENT_TYPES, PRESCRIPTION_STATUS, badge, fillSelect } from '../core/labels.js';
import { renderPagination } from '../components/pagination.js';
import { profileProfessionalId, whileBusy } from '../components/author-select.js';

const $ = id => document.getElementById(id);
const state = {
    tab: 'queue', offset: 0, prescriptions: {}, pharmacists: {}, medications: [], current: null, dispensing: false,
};
const fmt = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
const card = (title, body) => `<div class="glass-card rounded-2xl p-5"><h3 class="font-bold text-slate-800 mb-3">${title}</h3>${body}</div>`;
const table = (headers, rows) => `<div class="relative overflow-x-auto" tabindex="0" role="region"
    aria-label="Tabela: ${headers.filter(Boolean).join(', ')}"><table class="w-full text-sm">
    <thead><tr class="text-left text-slate-500 border-b">${headers.map(h => `<th class="py-2 pr-3 font-medium">${h}</th>`).join('')}</tr></thead>
    <tbody>${rows}</tbody></table></div>`;
const PAGE_SIZE = 15;

// ------------------------------------------------------------------- abas

const TABS = {
    async queue(container) {
        const page = await apiCall(`/prescriptions?${new URLSearchParams({ limit: PAGE_SIZE, offset: state.offset })}&status=ATIVA&status=PARCIALMENTE_DISPENSADA`);
        page.items.forEach(p => { state.prescriptions[p.id] = p; });
        container.innerHTML = page.items.length ? page.items.map(p => `
            <article class="glass-card rounded-2xl p-4">
                <div class="flex flex-wrap justify-between gap-2">
                    <div><strong>${escapeHtml(p.patient_name || '')}</strong>
                        <span class="text-sm text-slate-500">· ${formatDateTime(p.issued_at)} · ${escapeHtml(p.prescriber_name || '')}</span>
                        ${p.special_control ? '<span class="text-xs font-semibold text-purple-700 ml-1">Controle especial</span>' : ''}</div>
                    <div class="flex gap-2 items-center">${p.is_expired ? '<span class="text-xs font-semibold text-red-700"><i class="fas fa-calendar-xmark" aria-hidden="true"></i> Vencida</span>' : `<span class="text-xs text-slate-500">válida até ${formatDate(p.valid_until)}</span>`}
                        ${badge(PRESCRIPTION_STATUS, p.status)}</div>
                </div>
                <ul class="text-sm mt-2 space-y-1">${p.items.map(i => `<li>${escapeHtml(i.medication_name || '')} — ${escapeHtml(i.dose)}, ${escapeHtml(i.frequency)}
                    <span class="text-slate-500">· saldo ${fmt(i.remaining_quantity)} de ${fmt(i.quantity)}${i.status !== 'EM_USO' ? ` · ${escapeHtml(i.status)}` : ''}</span></li>`).join('')}</ul>
                ${p.allergy_override_reason ? `<p class="text-xs text-red-700 mt-1"><i class="fas fa-triangle-exclamation" aria-hidden="true"></i> Prescrita apesar de alergia: ${escapeHtml(p.allergy_override_reason)}</p>` : ''}
                ${p.is_expired ? '' : `<button data-dispense="${escapeHtml(p.id)}" class="mt-3 px-3 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100"><i class="fas fa-pills" aria-hidden="true"></i> Dispensar</button>`}
            </article>`).join('') : card('Fila vazia', '<p class="text-sm text-slate-500">Nenhuma prescrição aguardando dispensação.</p>');
        renderPagination($('pagination'), page, offset => { state.offset = offset; render(); });
    },

    async stock(container) {
        const rows = await apiCall('/medications/stock');
        state.medications = rows;
        container.innerHTML = card('Posição de estoque', table(
            ['Medicamento', 'Categoria', 'Total', 'Em lotes', 'Sem lote', 'Validade mais próxima', 'Situação'],
            rows.map(r => `<tr class="border-b last:border-0">
                <td class="py-2 pr-3"><strong>${escapeHtml(r.name)}</strong> <span class="text-slate-500">${escapeHtml(r.dosage)}</span>${r.is_controlled ? ' <span class="text-xs text-purple-700">controlado</span>' : ''}</td>
                <td class="py-2 pr-3 text-slate-600">${escapeHtml(r.category_name || '—')}</td>
                <td class="py-2 pr-3 tabular-nums font-semibold">${fmt(r.total_quantity)}</td>
                <td class="py-2 pr-3 tabular-nums">${fmt(r.lotted_quantity)}</td>
                <td class="py-2 pr-3 tabular-nums">${fmt(r.unlotted_quantity)}</td>
                <td class="py-2 pr-3">${r.nearest_expiration ? formatDate(`${r.nearest_expiration}T00:00`) : '—'}</td>
                <td class="py-2">${r.below_minimum_locations ? `<span class="flag flag-attention"><i class="fas fa-arrow-down" aria-hidden="true"></i>Abaixo do mínimo em ${r.below_minimum_locations} local(is)</span>` : '<span class="flag flag-normal"><i class="fas fa-circle-check" aria-hidden="true"></i>Adequado</span>'}</td>
            </tr>`).join(''))) + card('Receber lote', `
            <form id="form-lot" class="grid grid-cols-1 sm:grid-cols-5 gap-3">
                <select id="l-medication" required class="p-2 border rounded-lg sm:col-span-2"></select>
                <input id="l-number" required maxlength="40" placeholder="Número do lote" class="p-2 border rounded-lg">
                <input id="l-expiration" type="date" required aria-label="Validade" class="p-2 border rounded-lg">
                <input id="l-quantity" type="number" min="1" step="any" required placeholder="Quantidade" class="p-2 border rounded-lg">
                <input id="l-location" required value="FARMACIA_CENTRAL" aria-label="Local" class="p-2 border rounded-lg sm:col-span-2">
                <div><button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700">Registrar entrada</button></div>
            </form>`);
        fillSelect($('l-medication'), Object.fromEntries(rows.map(r => [r.medication_id, `${r.name} ${r.dosage}`])), 'Medicamento');
        $('form-lot').addEventListener('submit', async event => {
            event.preventDefault();
            await whileBusy(event.target.querySelector('[type="submit"]'), async () => {
                try {
                    await apiCall('/stock/lots', 'POST', {
                        medication_id: $('l-medication').value, lot_number: $('l-number').value, location: $('l-location').value,
                        expiration_date: $('l-expiration').value, quantity: Number($('l-quantity').value),
                    });
                    toast('Lote recebido.', 'success');
                    render();
                } catch (err) {
                    toast(err.message, 'error');
                }
            });
        });
        $('pagination').innerHTML = '';
    },

    async expiry(container) {
        const page = await apiCall(`/stock/lots?expiring_within_days=60&limit=200`);
        container.innerHTML = card(`Lotes vencidos ou vencendo em até 60 dias <span class="text-sm font-normal text-slate-500">(${page.total})</span>`,
            page.items.length ? table(['Medicamento', 'Lote', 'Local', 'Validade', 'Saldo', ''], page.items.map(l => `
                <tr class="border-b last:border-0">
                    <td class="py-2 pr-3">${escapeHtml(l.medication_name || '')}</td>
                    <td class="py-2 pr-3 font-mono text-xs">${escapeHtml(l.lot_number)}</td>
                    <td class="py-2 pr-3 text-slate-600">${escapeHtml(l.location)}</td>
                    <td class="py-2 pr-3">${formatDate(`${l.expiration_date}T00:00`)}
                        ${l.is_expired ? '<span class="flag flag-critical ml-1"><i class="fas fa-triangle-exclamation" aria-hidden="true"></i>Vencido</span>'
                            : `<span class="flag flag-attention ml-1"><i class="fas fa-hourglass-half" aria-hidden="true"></i>${l.days_to_expire} dia(s)</span>`}</td>
                    <td class="py-2 pr-3 tabular-nums">${fmt(l.quantity)}</td>
                    <td class="py-2">${l.is_expired ? `<button data-discard="${escapeHtml(l.id)}" data-lot-number="${escapeHtml(l.lot_number)}" class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">Descartar</button>` : ''}</td>
                </tr>`).join('')) : '<p class="text-sm text-slate-500">Nenhum lote nesta situação.</p>');
        $('pagination').innerHTML = '';
    },

    async movements(container) {
        const page = await apiCall(`/stock/movements?${new URLSearchParams({ limit: PAGE_SIZE, offset: state.offset })}`);
        container.innerHTML = card('Movimentações de estoque', table(
            ['Data', 'Tipo', 'Medicamento', 'Local', 'Quantidade', 'Saldo após', 'Observação'],
            page.items.map(m => `<tr class="border-b last:border-0">
                <td class="py-2 pr-3 whitespace-nowrap">${formatDateTime(m.occurred_at)}</td>
                <td class="py-2 pr-3">${badge(MOVEMENT_TYPES, m.movement_type)}</td>
                <td class="py-2 pr-3">${escapeHtml(m.medication_name || '')}</td>
                <td class="py-2 pr-3 text-slate-600">${escapeHtml(m.location)}</td>
                <td class="py-2 pr-3 tabular-nums">${m.movement_type === 'ENTRADA' ? '+' : '−'}${fmt(m.quantity)}</td>
                <td class="py-2 pr-3 tabular-nums">${fmt(m.balance_after)}</td>
                <td class="py-2 text-slate-500 text-xs">${escapeHtml(m.reason || '')}</td></tr>`).join('')));
        renderPagination($('pagination'), page, offset => { state.offset = offset; render(); });
    },
};

async function render() {
    const container = $('content');
    renderLoading(container);
    try {
        await TABS[state.tab](container);
    } catch (err) {
        renderEmpty(container, `Erro: ${err.message}`);
    }
}

function switchTab(tab) {
    state.tab = tab;
    state.offset = 0;
    document.querySelectorAll('[data-tab]').forEach(button => {
        const active = button.dataset.tab === tab;
        button.className = `tab px-4 py-2 rounded-lg text-sm font-bold ${active ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`;
        button.setAttribute('aria-selected', active);
    });
    render();
}

// --------------------------------------------------------------- dispensação

function openDispense(prescriptionId) {
    const p = state.prescriptions[prescriptionId];
    state.current = p;
    $('d-result').classList.add('hidden');
    $('d-items').innerHTML = p.items.filter(i => i.status === 'EM_USO' && i.remaining_quantity > 0).map(i => `
        <label class="text-sm text-slate-600 flex items-center justify-between gap-3 border rounded-lg p-2">
            <span>${escapeHtml(i.medication_name || '')} <span class="text-slate-500">(saldo ${fmt(i.remaining_quantity)})</span></span>
            <input data-item="${escapeHtml(i.id)}" data-name="${escapeHtml(i.medication_name || '')}" type="number" min="0"
                max="${i.remaining_quantity}" step="any" value="${i.remaining_quantity}" class="w-24 p-2 border rounded-lg text-right"></label>`).join('');
    setDispenseLocked(false);
    openModal('modal-dispense');
}

/** Depois do sucesso o formulário fica travado: outra dispensação exige fechar e abrir de novo. */
function setDispenseLocked(locked) {
    const form = $('form-dispense');
    form.dataset.done = locked ? 'true' : '';
    form.querySelectorAll('input, select').forEach(field => { field.disabled = locked; });
    const button = form.querySelector('[type="submit"]');
    button.disabled = locked;
    button.textContent = locked ? 'Dispensado' : 'Dispensar';
}

function showDispenseResult(ok, html) {
    const result = $('d-result');
    result.className = `mt-4 text-sm rounded-lg p-3 ${ok ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-700'}`;
    result.innerHTML = html;
}

async function submitDispense(event) {
    event.preventDefault();
    const form = $('form-dispense');
    if (state.dispensing || form.dataset.done) return;  // envio em andamento ou já concluído
    const inputs = [...document.querySelectorAll('#d-items [data-item]')];
    const over = inputs.find(input => Number(input.value) > Number(input.max));
    const items = inputs.filter(input => Number(input.value) > 0)
        .map(input => ({ prescription_item_id: input.dataset.item, quantity: Number(input.value), name: input.dataset.name }));
    if (over) return showDispenseResult(false, `Erro: a quantidade de ${escapeHtml(over.dataset.name)} passa do saldo (${fmt(over.max)}).`);
    if (!items.length) return showDispenseResult(false, 'Erro: informe a quantidade de pelo menos um item.');

    const pharmacist = $('d-pharmacist').selectedOptions[0]?.textContent || '';
    const summary = items.map(i => `• ${i.name}: ${fmt(i.quantity)}`).join('\n');
    if (!window.confirm(`Confirmar a dispensação?\n\n${summary}\n\nFarmacêutico(a): ${pharmacist}\nLocal: ${$('d-location').value}`)) return;

    state.dispensing = true;
    try {
        const dispensation = await whileBusy(form.querySelector('[type="submit"]'), () => apiCall('/dispensations', 'POST', {
            prescription_id: state.current.id, pharmacist_id: $('d-pharmacist').value, location: $('d-location').value,
            items: items.map(({ prescription_item_id, quantity }) => ({ prescription_item_id, quantity })),
        }));
        setDispenseLocked(true);
        showDispenseResult(true, `<strong>Dispensado.</strong> Lotes utilizados (FEFO):<ul class="mt-1">${dispensation.lines.map(l =>
            `<li>${escapeHtml(l.medication_name || '')}: ${fmt(l.quantity)} — ${l.lot_number ? `lote ${escapeHtml(l.lot_number)}` : 'estoque sem lote'}</li>`).join('')}</ul>
            <p class="mt-1">Para outra dispensação, feche e abra a prescrição novamente.</p>`);
        render();
    } catch (err) {
        showDispenseResult(false, `Erro: ${escapeHtml(err.message)}`);
    } finally {
        state.dispensing = false;
    }
}

async function init() {
    renderNav('farmacia');
    renderDemoBanner();
    enableModalDismiss();
    const pharmacists = await apiCall('/professionals?professional_type=FARMACEUTICO&status=ATIVO&limit=100');
    fillSelect($('d-pharmacist'), Object.fromEntries(pharmacists.items.map(p => [p.id, p.full_name])), 'Selecione');
    const mine = profileProfessionalId();
    if (mine && pharmacists.items.some(p => p.id === mine)) $('d-pharmacist').value = mine;
    $('form-dispense').addEventListener('submit', submitDispense);
    document.addEventListener('click', async event => {
        const tab = event.target.closest('[data-tab]');
        if (tab) return switchTab(tab.dataset.tab);
        const dispense = event.target.closest('[data-dispense]');
        if (dispense) return openDispense(dispense.dataset.dispense);
        const discard = event.target.closest('[data-discard]');
        if (discard && !discard.disabled) {
            const lot = discard.dataset.lotNumber;
            if (!window.confirm(`Descartar o lote ${lot}? O saldo sai do estoque e a ação não pode ser desfeita.`)) return;
            await whileBusy(discard, async () => {
                try {
                    await apiCall(`/stock/lots/${discard.dataset.discard}/discard`, 'POST', {});
                    toast('Lote vencido descartado.', 'success');
                    render();
                } catch (err) {
                    toast(err.message, 'error');
                }
            });
        }
    });
    switchTab('queue');
}

init().catch(err => toast(err.message, 'error'));
