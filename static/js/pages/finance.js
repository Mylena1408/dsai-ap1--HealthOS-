// Financeiro: indicadores do período, faturas, pagamentos e faturamento de atendimentos.
import { apiCall } from '../core/api.js';
import {
    enableModalDismiss, escapeHtml, formatDate, formatDateTime, formatMoney, openModal, renderEmpty,
    renderLoading, toast,
} from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { INVOICE_STATUS, PAYMENT_METHODS, badge, fillSelect } from '../core/labels.js';
import { renderBarChart } from '../components/bar-chart.js';
import { renderLineChart } from '../components/line-chart.js';
import { renderPagination } from '../components/pagination.js';
import { createPatientPicker } from '../components/patient-picker.js';

const PAGE_SIZE = 15;
const $ = id => document.getElementById(id);
const state = { offset: 0, invoice: null, billPatient: null, unbilled: [] };
// Data local no formato AAAA-MM-DD (toISOString usaria UTC e poderia mudar o dia).
const isoDate = date => [date.getFullYear(), date.getMonth() + 1, date.getDate()].map(n => String(n).padStart(2, '0')).join('-');
const monthLabel = ym => new Date(`${ym}-01T00:00`).toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' });
const tile = (label, value, hint = '', tone = '') => `<div class="glass-card rounded-2xl p-4">
    <div class="text-xs uppercase tracking-wide text-slate-500">${label}</div>
    <div class="text-2xl font-bold tabular-nums ${tone || 'text-slate-900'}">${value}</div>
    <div class="text-xs text-slate-500 mt-1">${hint}</div></div>`;

// ------------------------------------------------------------ indicadores

async function loadSummary() {
    const params = new URLSearchParams({ start: $('p-start').value, end: $('p-end').value });
    renderLoading($('kpis'));
    try {
        const s = await apiCall(`/billing/summary?${params}`);
        $('kpis').innerHTML = [
            tile('Faturado no período', formatMoney(s.invoiced), 'faturas emitidas, sem as canceladas'),
            tile('Recebido no período', formatMoney(s.received), 'pagamentos registrados'),
            tile('A receber', formatMoney(s.receivable), `${s.open_count} fatura(s) em aberto, de qualquer data`),
            tile('Em atraso', formatMoney(s.overdue),
                 `<i class="fas fa-triangle-exclamation" aria-hidden="true"></i> ${s.overdue_count} fatura(s) vencida(s)`,
                 s.overdue_count ? 'text-red-700' : ''),
        ].join('');

        const point = (m, key) => ({ t: new Date(`${m.month}-15T00:00`), v: Number(m[key]), note: monthLabel(m.month) });
        renderLineChart($('chart-monthly'), [
            { name: 'Faturado', color: 'var(--series-1)', points: s.monthly.map(m => point(m, 'invoiced')) },
            { name: 'Recebido', color: 'var(--series-2)', points: s.monthly.map(m => point(m, 'received')) },
        ], { format: formatMoney, ariaLabel: 'Faturado e recebido nos últimos seis meses' });
        $('table-monthly').innerHTML = `<table class="w-full text-sm"><thead><tr class="text-left text-slate-500 border-b">
                <th class="py-1 pr-3 font-medium">Mês</th><th class="py-1 pr-3 font-medium text-right">Faturado</th>
                <th class="py-1 font-medium text-right">Recebido</th></tr></thead>
            <tbody>${s.monthly.map(m => `<tr class="border-b last:border-0"><td class="py-1 pr-3">${escapeHtml(monthLabel(m.month))}</td>
                <td class="py-1 pr-3 text-right tabular-nums">${formatMoney(m.invoiced)}</td>
                <td class="py-1 text-right tabular-nums">${formatMoney(m.received)}</td></tr>`).join('')}</tbody></table>`;
        renderBarChart($('chart-methods'), s.received_by_method.map(i => ({ label: PAYMENT_METHODS[i.label] || i.label, value: Number(i.value) })),
                       { format: formatMoney, ariaLabel: 'Recebido por forma de pagamento' });
        renderBarChart($('chart-payers'), s.invoiced_by_payer.map(i => ({ label: i.label, value: Number(i.value) })),
                       { color: 'var(--series-2)', format: formatMoney, ariaLabel: 'Faturado por pagador' });
    } catch (err) {
        renderEmpty($('kpis'), `Erro: ${err.message}`);
    }
}

// ----------------------------------------------------------------- faturas

async function loadInvoices() {
    const body = $('invoices');
    body.innerHTML = '<tr><td colspan="7" class="py-4 text-center text-slate-500 text-sm">Carregando...</td></tr>';
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset: state.offset });
    if ($('f-status').value) params.set('status', $('f-status').value);
    if ($('f-number').value.trim()) params.set('number', $('f-number').value.trim());
    try {
        const page = await apiCall(`/billing/invoices?${params}`);
        body.innerHTML = page.items.length ? page.items.map(i => `
            <tr class="border-b last:border-0 hover:bg-slate-50">
                <td class="py-2 pr-3"><button data-invoice="${escapeHtml(i.id)}" class="font-semibold text-blue-700 hover:underline">${escapeHtml(i.number)}</button></td>
                <td class="py-2 pr-3">${escapeHtml(i.patient_name)}</td>
                <td class="py-2 pr-3 whitespace-nowrap">${formatDate(i.issue_date)}</td>
                <td class="py-2 pr-3 whitespace-nowrap">${formatDate(i.due_date)}</td>
                <td class="py-2 pr-3 text-right tabular-nums">${formatMoney(i.gross_total)}</td>
                <td class="py-2 pr-3 text-right tabular-nums">${formatMoney(i.balance)}</td>
                <td class="py-2">${badge(INVOICE_STATUS, i.status)}</td></tr>`).join('')
            : '<tr><td colspan="7" class="py-4 text-center text-slate-500 text-sm">Nenhuma fatura encontrada.</td></tr>';
        renderPagination($('pagination'), page, offset => { state.offset = offset; loadInvoices(); });
    } catch (err) {
        body.innerHTML = `<tr><td colspan="7" class="py-4 text-center text-red-700 text-sm">Erro: ${escapeHtml(err.message)}</td></tr>`;
    }
}

function renderInvoice() {
    const i = state.invoice;
    const row = (label, value, strong = false) => `<div class="flex justify-between gap-4 ${strong ? 'font-bold' : ''}">
        <span class="text-slate-600">${label}</span><span class="tabular-nums">${value}</span></div>`;
    const can = action => i.allowed_actions.includes(action);
    $('invoice-detail').innerHTML = `
        <div class="flex flex-wrap items-center gap-3 mb-1 pr-8">
            <h3 id="invoice-title" class="text-xl font-bold text-slate-800">Fatura ${escapeHtml(i.number)}</h3>${badge(INVOICE_STATUS, i.status)}
        </div>
        <p class="text-sm text-slate-600 mb-4">${escapeHtml(i.patient_name)} · emissão ${formatDate(i.issue_date)} · vencimento ${formatDate(i.due_date)}
            ${i.insurance_provider ? ` · ${escapeHtml(i.insurance_provider)} (${Number(i.coverage_percentage)}%)` : ' · particular'}</p>
        <table class="w-full text-sm mb-4"><thead><tr class="text-left text-slate-500 border-b">
            <th class="py-1 pr-3 font-medium">Item</th><th class="py-1 pr-3 font-medium text-right">Qtd.</th>
            <th class="py-1 font-medium text-right">Total</th></tr></thead>
            <tbody>${i.items.map(it => `<tr class="border-b last:border-0"><td class="py-1 pr-3">${escapeHtml(it.description)}</td>
                <td class="py-1 pr-3 text-right tabular-nums">${Number(it.quantity)}</td>
                <td class="py-1 text-right tabular-nums">${formatMoney(it.total)}</td></tr>`).join('')}</tbody></table>
        <div class="grid sm:grid-cols-2 gap-4">
            <div class="space-y-1 text-sm">
                ${row('Total bruto', formatMoney(i.gross_total), true)}
                ${row('Parte do convênio', formatMoney(i.insurance_share))}
                ${row('Parte do paciente', formatMoney(i.patient_share))}
                ${row('Pago', formatMoney(i.amount_paid))}
                ${row('Saldo', formatMoney(i.balance), true)}
            </div>
            <div class="text-sm">
                <div class="font-semibold text-slate-700 mb-1">Pagamentos</div>
                ${i.payments.length ? `<ul class="space-y-1">${i.payments.map(p => `<li class="flex justify-between gap-2">
                    <span>${formatDateTime(p.paid_at)} · ${escapeHtml(PAYMENT_METHODS[p.method] || p.method)}${p.note ? ` · ${escapeHtml(p.note)}` : ''}</span>
                    <span class="tabular-nums">${formatMoney(p.amount)}</span></li>`).join('')}</ul>`
                    : '<p class="text-slate-500">Nenhum pagamento.</p>'}
                ${i.cancellation_reason ? `<p class="mt-2 text-slate-600">Cancelada em ${formatDateTime(i.cancelled_at)}: ${escapeHtml(i.cancellation_reason)}</p>` : ''}
            </div>
        </div>
        ${can('emitir') ? `<button data-act="issue" class="mt-5 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700">Emitir fatura</button>` : ''}
        ${can('pagar') ? `<form id="form-payment" class="mt-5 grid grid-cols-1 sm:grid-cols-4 gap-2 items-end">
            <label class="text-sm text-slate-600">Valor (R$)<input id="pay-amount" type="number" min="0.01" step="0.01" max="${escapeHtml(i.balance)}"
                value="${escapeHtml(i.balance)}" required class="w-full p-2 border rounded-lg mt-1"></label>
            <label class="text-sm text-slate-600">Forma<select id="pay-method" class="w-full p-2 border rounded-lg mt-1"></select></label>
            <label class="text-sm text-slate-600">Observação<input id="pay-note" maxlength="255" class="w-full p-2 border rounded-lg mt-1"></label>
            <button type="submit" class="bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-emerald-700">Registrar pagamento</button>
        </form>` : ''}
        ${can('cancelar') ? `<form id="form-cancel" class="mt-3 flex flex-wrap gap-2 items-end">
            <label class="text-sm text-slate-600 flex-1 min-w-[12rem]">Motivo do cancelamento<input id="cancel-reason" required minlength="3" maxlength="500" class="w-full p-2 border rounded-lg mt-1"></label>
            <button type="submit" class="border border-red-300 text-red-700 px-4 py-2 rounded-lg text-sm font-bold hover:bg-red-50">Cancelar fatura</button>
        </form>` : ''}`;
    if (can('pagar')) {
        // "Não informado" existe só para pagamentos antigos; aqui a forma é obrigatória.
        fillSelect($('pay-method'), Object.fromEntries(Object.entries(PAYMENT_METHODS).filter(([code]) => code !== 'NAO_INFORMADO')));
    }
}

async function openInvoice(id) {
    renderLoading($('invoice-detail'));
    openModal('modal-invoice');
    try {
        state.invoice = await apiCall(`/billing/invoices/${id}`);
        renderInvoice();
    } catch (err) {
        renderEmpty($('invoice-detail'), `Erro: ${err.message}`);
    }
}

async function invoiceAction(request, message) {
    try {
        state.invoice = await request();
        renderInvoice();
        toast(message, 'success');
        loadInvoices();
        loadSummary();
    } catch (err) {
        toast(err.message, 'error');
    }
}

// ------------------------------------------------------ faturar atendimentos

async function selectBillPatient(patient) {
    state.billPatient = patient;
    $('b-insurer').value = patient.insurance_provider || '';
    $('b-coverage').value = patient.insurance_provider ? 80 : 0;
    $('form-bill').classList.remove('hidden');
    renderLoading($('unbilled'));
    try {
        state.unbilled = await apiCall(`/billing/patients/${patient.id}/unbilled`);
        $('unbilled').innerHTML = state.unbilled.length ? state.unbilled.map((s, index) => `
            <label class="flex items-center gap-3 text-sm py-1">
                <input type="checkbox" data-service="${index}" checked>
                <span class="flex-1">${escapeHtml(s.description)} <span class="text-slate-500">· ${formatDate(s.performed_at)}</span></span>
                <span class="tabular-nums">${formatMoney(s.price)}</span></label>`).join('')
            : '<p class="text-sm text-slate-500">Nenhum atendimento a faturar para este paciente.</p>';
        updateBillTotal();
    } catch (err) {
        renderEmpty($('unbilled'), `Erro: ${err.message}`);
    }
}

function selectedServices() {
    return [...document.querySelectorAll('[data-service]:checked')].map(box => state.unbilled[Number(box.dataset.service)]);
}

function updateBillTotal() {
    const services = selectedServices();
    const total = services.reduce((sum, s) => sum + Number(s.price), 0);
    $('b-total').textContent = services.length ? `${services.length} atendimento(s) · total ${formatMoney(total)}` : 'Nenhum atendimento selecionado.';
}

async function submitBill(event) {
    event.preventDefault();
    const services = selectedServices();
    if (!services.length) return toast('Selecione ao menos um atendimento.', 'error');
    try {
        const invoice = await apiCall(`/billing/patients/${state.billPatient.id}/invoices`, 'POST', {
            services: services.map(s => ({ source_type: s.source_type, source_id: s.source_id })),
            insurance_provider: $('b-insurer').value.trim() || null, insurance_policy_number: $('b-policy').value.trim() || null,
            coverage_percentage: $('b-coverage').value || '0', issue: $('b-issue').checked,
        });
        toast(`Fatura ${invoice.number} gerada.`, 'success');
        await selectBillPatient(state.billPatient);
        loadInvoices();
        loadSummary();
        state.invoice = invoice;
        openModal('modal-invoice');
        renderInvoice();
    } catch (err) {
        toast(err.message, 'error');
    }
}

// ------------------------------------------------------------------ início

renderNav('financeiro');
renderDemoBanner();
enableModalDismiss();
const today = new Date();
$('p-end').value = isoDate(today);
$('p-start').value = isoDate(new Date(today.getFullYear(), today.getMonth(), 1));
fillSelect($('f-status'), INVOICE_STATUS, 'Todas');
createPatientPicker($('bill-patient'), { onSelect: selectBillPatient });

$('form-period').addEventListener('submit', event => { event.preventDefault(); loadSummary(); });
$('toggle-table').addEventListener('click', event => {
    const showTable = $('table-monthly').classList.toggle('hidden') === false;
    $('chart-monthly').classList.toggle('hidden', showTable);
    event.currentTarget.textContent = showTable ? 'Ver gráfico' : 'Ver tabela';
    event.currentTarget.setAttribute('aria-pressed', String(showTable));
});
$('f-status').addEventListener('change', () => { state.offset = 0; loadInvoices(); });
let numberDebounce;
$('f-number').addEventListener('input', () => {
    clearTimeout(numberDebounce);
    numberDebounce = setTimeout(() => { state.offset = 0; loadInvoices(); }, 300);
});
$('form-bill').addEventListener('change', event => { if (event.target.matches('[data-service]')) updateBillTotal(); });
$('form-bill').addEventListener('submit', submitBill);

document.addEventListener('click', event => {
    const invoice = event.target.closest('[data-invoice]');
    if (invoice) return openInvoice(invoice.dataset.invoice);
    if (event.target.closest('[data-act="issue"]')) {
        invoiceAction(() => apiCall(`/billing/invoices/${state.invoice.id}/issue`, 'POST'), 'Fatura emitida.');
    }
});
document.addEventListener('submit', event => {
    if (event.target.id === 'form-payment') {
        event.preventDefault();
        invoiceAction(() => apiCall(`/billing/invoices/${state.invoice.id}/payments`, 'POST', {
            amount: $('pay-amount').value, method: $('pay-method').value, note: $('pay-note').value.trim() || null,
        }), 'Pagamento registrado.');
    } else if (event.target.id === 'form-cancel') {
        event.preventDefault();
        invoiceAction(() => apiCall(`/billing/invoices/${state.invoice.id}/cancel`, 'POST', {
            reason: $('cancel-reason').value.trim(),
        }), 'Fatura cancelada.');
    }
});

loadSummary();
loadInvoices();
// Vindo da busca global: /app/financeiro?invoice=<id> abre a fatura.
const requestedInvoice = new URLSearchParams(window.location.search).get('invoice');
if (requestedInvoice) openInvoice(requestedInvoice);
