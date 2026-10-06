// Alertas por regra: resumo, filtros, reconhecer/resolver e avaliação sob demanda.
import { apiCall } from '../core/api.js';
import {
    closeModal, enableModalDismiss, escapeHtml, formatDateTime, openModal, renderEmpty, renderLoading, toast,
} from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';
import { fillSelect } from '../core/labels.js';
import { renderPagination } from '../components/pagination.js';
import { getProfile } from '../components/profile.js';

const PAGE_SIZE = 20;
const $ = id => document.getElementById(id);
const CATEGORIES = { CLINICO: 'Clínico', LABORATORIAL: 'Laboratorial', MEDICAMENTO: 'Medicamento', CONSULTA: 'Consulta',
                     ESTOQUE: 'Estoque', ADMINISTRATIVO: 'Administrativo', SISTEMA: 'Sistema' };
const STATUSES = { ABERTOS: 'Abertos (ativos e reconhecidos)', ATIVO: 'Ativos', RECONHECIDO: 'Reconhecidos', RESOLVIDO: 'Resolvidos' };
// Nível sempre com ícone + texto (cor de status nunca sozinha).
const LEVELS = {
    CRITICO: { label: 'Crítico', icon: 'fa-triangle-exclamation', css: 'flag-critical' },
    ATENCAO: { label: 'Atenção', icon: 'fa-circle-exclamation', css: 'flag-attention' },
    INFO: { label: 'Informativo', icon: 'fa-circle-info', css: 'flag-normal' },
};
const state = { offset: 0, resolving: null };

const levelBadge = level => {
    const info = LEVELS[level];
    return `<span class="flag ${info.css}"><i class="fas ${info.icon}" aria-hidden="true"></i>${info.label}</span>`;
};

async function loadSummary() {
    const summary = await apiCall('/alerts/summary');
    $('tiles').innerHTML = Object.entries(LEVELS).map(([level, info]) => `
        <div class="glass-card rounded-2xl p-5">
            <div class="text-xs uppercase tracking-wide text-slate-500 mb-1"><i class="fas ${info.icon}" aria-hidden="true"></i> ${info.label}</div>
            <div class="text-3xl font-semibold text-slate-900">${summary.by_level[level] || 0}</div>
            <div class="text-xs text-slate-500">alertas abertos</div>
        </div>`).join('');
}

async function loadList() {
    const list = $('list');
    renderLoading(list);
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset: state.offset });
    const status = $('f-status').value;
    if (status === 'ABERTOS') { params.append('status', 'ATIVO'); params.append('status', 'RECONHECIDO'); }
    else if (status) params.set('status', status);
    if ($('f-category').value) params.set('category', $('f-category').value);
    if ($('f-level').value) params.set('level', $('f-level').value);
    try {
        const page = await apiCall(`/alerts?${params}`);
        if (!page.items.length) renderEmpty(list, 'Nenhum alerta com esses filtros.');
        else list.innerHTML = page.items.map(a => `
            <article class="glass-card rounded-2xl p-4">
                <div class="flex flex-wrap justify-between items-start gap-2">
                    <div class="min-w-0">
                        <div class="flex flex-wrap items-center gap-2">${levelBadge(a.level)}
                            <span class="text-xs text-slate-500">${escapeHtml(CATEGORIES[a.category] || a.category)} · ${escapeHtml(a.rule_code)}</span></div>
                        <h2 class="font-bold text-slate-800 mt-1">${escapeHtml(a.title)}</h2>
                        <p class="text-sm text-slate-600">${escapeHtml(a.message)}</p>
                        <p class="text-xs text-slate-500 mt-1">Detectado em ${formatDateTime(a.first_detected_at)} · última verificação ${formatDateTime(a.last_detected_at)}
                            ${a.acknowledged_by ? ` · reconhecido por ${escapeHtml(a.acknowledged_by)}` : ''}</p>
                        ${a.resolution_note ? `<p class="text-xs text-emerald-700 mt-1">${escapeHtml(a.resolution_note)}</p>` : ''}
                    </div>
                    <div class="flex flex-wrap gap-2">
                        ${a.link ? `<a href="${escapeHtml(a.link)}" class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">Abrir</a>` : ''}
                        ${a.status === 'ATIVO' ? `<button data-ack="${escapeHtml(a.id)}" class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">Reconhecer</button>` : ''}
                        ${a.status !== 'RESOLVIDO' ? `<button data-resolve="${escapeHtml(a.id)}" class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">Resolver</button>` : ''}
                    </div>
                </div>
            </article>`).join('');
        renderPagination($('pagination'), page, offset => { state.offset = offset; loadList(); });
    } catch (err) {
        renderEmpty(list, `Erro: ${err.message}`);
    }
}

const refresh = () => Promise.all([loadSummary(), loadList()]);

async function init() {
    renderNav('alertas');
    renderDemoBanner();
    enableModalDismiss();
    fillSelect($('f-status'), STATUSES);
    fillSelect($('f-category'), CATEGORIES, 'Todas');
    fillSelect($('f-level'), Object.fromEntries(Object.entries(LEVELS).map(([k, v]) => [k, v.label])), 'Todos');
    $('filters').addEventListener('change', () => { state.offset = 0; loadList(); });

    const rules = await apiCall('/alerts/rules');
    $('rules').innerHTML = rules.map(r => `<li><strong>${escapeHtml(r.code)}</strong> · ${escapeHtml(CATEGORIES[r.category])}
        → ${escapeHtml(r.sector)}<br><span class="text-slate-600">${escapeHtml(r.description)}</span></li>`).join('');

    $('evaluate').addEventListener('click', async () => {
        try {
            const report = await apiCall('/alerts/evaluate', 'POST');
            toast(`Avaliação concluída: ${report.opened} novo(s), ${report.auto_resolved} resolvido(s) automaticamente.`, 'success');
            window.dispatchEvent(new Event('healthos:inbox-changed'));
            refresh();
        } catch (err) {
            toast(err.message, 'error');
        }
    });
    document.addEventListener('click', async event => {
        const ack = event.target.closest('[data-ack]');
        if (ack) {
            try {
                await apiCall(`/alerts/${ack.dataset.ack}/acknowledge`, 'POST', { by: getProfile().label });
                refresh();
            } catch (err) {
                toast(err.message, 'error');
            }
        }
        const resolve = event.target.closest('[data-resolve]');
        if (resolve) {
            state.resolving = resolve.dataset.resolve;
            $('resolve-note').value = '';
            openModal('modal-resolve');
        }
    });
    $('form-resolve').addEventListener('submit', async event => {
        event.preventDefault();
        try {
            await apiCall(`/alerts/${state.resolving}/resolve`, 'POST', { note: $('resolve-note').value });
            closeModal('modal-resolve');
            toast('Alerta resolvido.', 'success');
            refresh();
        } catch (err) {
            toast(err.message, 'error');
        }
    });
    await refresh();
}

init().catch(err => toast(err.message, 'error'));
