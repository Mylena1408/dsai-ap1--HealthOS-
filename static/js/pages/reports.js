// Relatórios: catálogo, filtros, pré-visualização e downloads (CSV/PDF gerados pela API).
import { API_BASE, apiCall } from '../core/api.js';
import { escapeHtml, formatDate, formatDateTime, formatMoney, renderEmpty, renderLoading } from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { fillSelect } from '../core/labels.js';

const PREVIEW_ROWS = 200;  // a tela mostra um trecho; os arquivos trazem o relatório inteiro
const $ = id => document.getElementById(id);
const state = { catalog: [], report: null };
const localDate = date => [date.getFullYear(), date.getMonth() + 1, date.getDate()].map(n => String(n).padStart(2, '0')).join('-');
const formatNumber = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 2 });

function cell(value, kind, labels) {
    if (value === null || value === undefined || value === '') return '';
    switch (kind) {
        case 'data': return formatDate(`${value}T00:00`);
        case 'data_hora': return formatDateTime(value);
        case 'moeda': return formatMoney(value);
        case 'numero': return formatNumber(value);
        case 'codigo': return escapeHtml(labels[value] || value);
        default: return escapeHtml(value);
    }
}

function params(format) {
    const query = new URLSearchParams({ format });
    if (state.report.uses_period) {
        if ($('r-start').value) query.set('start', $('r-start').value);
        if ($('r-end').value) query.set('end', $('r-end').value);
    }
    if ($('r-status').value) query.set('status', $('r-status').value);
    return query;
}

function updateDownloads() {
    // Links diretos: o navegador baixa o arquivo com o nome enviado pela API.
    $('download-csv').href = `${API_BASE}/reports/${state.report.key}?${params('csv')}`;
    $('download-pdf').href = `${API_BASE}/reports/${state.report.key}?${params('pdf')}`;
}

function selectReport(key) {
    state.report = state.catalog.find(r => r.key === key);
    document.querySelectorAll('[data-report]').forEach(b => {
        const active = b.dataset.report === key;
        b.classList.toggle('bg-blue-50', active);
        b.classList.toggle('border-blue-300', active);
        b.setAttribute('aria-current', String(active));
    });
    $('report-title').textContent = state.report.title;
    $('report-description').textContent = state.report.description;
    $('form-report').classList.remove('hidden');
    document.querySelectorAll('[data-period]').forEach(field => field.classList.toggle('hidden', !state.report.uses_period));
    $('status-field').classList.toggle('hidden', !state.report.status_options.length);
    fillSelect($('r-status'), state.report.status_labels, 'Todas');
    $('preview').classList.add('hidden');
    updateDownloads();
}

async function preview() {
    const target = $('preview');
    target.classList.remove('hidden');
    renderLoading(target, 'Gerando relatório...');
    try {
        const report = await apiCall(`/reports/${state.report.key}?${params('json')}`);
        const scope = report.start ? `${formatDate(`${report.start}T00:00`)} a ${formatDate(`${report.end}T00:00`)}` : 'posição atual';
        const rows = report.rows.slice(0, PREVIEW_ROWS);
        const numeric = kind => kind === 'moeda' || kind === 'numero';
        target.innerHTML = `
            <div class="flex flex-wrap justify-between gap-2 mb-3 text-sm">
                <span class="text-slate-600">${escapeHtml(scope)} · <strong>${report.total_rows}</strong> linha(s) · gerado em ${formatDateTime(report.generated_at)}</span>
                ${report.truncated ? '<span class="flag flag-attention"><i class="fas fa-triangle-exclamation" aria-hidden="true"></i>Limite de linhas atingido: reduza o período</span>' : ''}
            </div>
            ${rows.length ? `<div class="overflow-x-auto"><table class="w-full text-sm">
                <thead><tr class="text-left text-slate-500 border-b">${report.columns.map(c =>
                    `<th class="py-2 pr-3 font-medium ${numeric(c.kind) ? 'text-right' : ''}">${escapeHtml(c.label)}</th>`).join('')}</tr></thead>
                <tbody>${rows.map(row => `<tr class="border-b last:border-0">${report.columns.map(c =>
                    `<td class="py-1.5 pr-3 ${numeric(c.kind) ? 'text-right tabular-nums' : ''}">${cell(row[c.key], c.kind, report.code_labels)}</td>`).join('')}</tr>`).join('')}</tbody>
            </table></div>` : '<p class="text-sm text-slate-500">Nenhum registro no período.</p>'}
            ${report.rows.length > PREVIEW_ROWS ? `<p class="text-xs text-slate-500 mt-2">Exibindo ${PREVIEW_ROWS} de ${report.total_rows} linhas; os arquivos CSV e PDF trazem todas.</p>` : ''}
            <p class="text-xs text-amber-700 mt-3"><i class="fas fa-circle-info" aria-hidden="true"></i> ${escapeHtml(report.disclaimer)}</p>`;
    } catch (err) {
        renderEmpty(target, `Erro: ${err.message}`);
    }
}

async function init() {
    renderNav('relatorios');
    renderDemoBanner();
    const today = new Date();
    $('r-end').value = localDate(today);
    $('r-start').value = localDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 29));
    try {
        state.catalog = await apiCall('/reports');
        $('catalog').innerHTML = state.catalog.map(r => `
            <li><button data-report="${escapeHtml(r.key)}" class="w-full text-left glass-card rounded-xl p-3 border hover:bg-slate-50">
                <div class="font-semibold text-slate-800 text-sm">${escapeHtml(r.title)}</div>
                <div class="text-xs text-slate-600">${r.uses_period ? 'Por período' : 'Posição atual'}</div>
            </button></li>`).join('');
        const requested = new URLSearchParams(window.location.search).get('report');
        selectReport(state.catalog.some(r => r.key === requested) ? requested : state.catalog[0].key);
    } catch (err) {
        renderEmpty($('catalog'), `Erro: ${err.message}`);
    }
}

document.addEventListener('click', event => {
    const report = event.target.closest('[data-report]');
    if (report) selectReport(report.dataset.report);
});
$('form-report').addEventListener('change', () => { if (state.report) updateDownloads(); });
$('form-report').addEventListener('submit', event => { event.preventDefault(); preview(); });
init();
