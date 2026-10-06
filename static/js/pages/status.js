// Página de status: consome /status e /metrics.
import { apiCall } from '../core/api.js';
import { escapeHtml, renderEmpty, toast } from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';

const REFRESH_MS = 15000;
const RECORD_LABELS = {
    patients: 'Pacientes', users: 'Usuários', schedules: 'Horários', medications: 'Medicamentos', invoices: 'Faturas',
};

function formatUptime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return h ? `${h}h ${m}min` : `${m}min ${Math.floor(seconds % 60)}s`;
}

function tile(label, value, tone = 'slate') {
    const tones = { slate: 'text-slate-800', ok: 'text-emerald-600', bad: 'text-red-600' };
    return `<div class="glass-card rounded-2xl p-5">
        <div class="text-xs uppercase tracking-wide text-slate-500 mb-1">${escapeHtml(label)}</div>
        <div class="text-2xl font-bold ${tones[tone]}">${escapeHtml(value)}</div>
    </div>`;
}

async function load() {
    const tiles = document.getElementById('status-tiles');
    let status;
    try {
        status = await apiCall('/status', 'GET', null, { root: true });
    } catch (err) {
        // /status responde 503 quando o banco está indisponível.
        tiles.innerHTML = tile('Aplicação', 'Indisponível', 'bad');
        toast(err.message, 'error');
        return;
    }
    const metrics = await apiCall('/metrics', 'GET', null, { root: true });
    const dbOk = status.database.status === 'ok';

    tiles.innerHTML = [
        tile('Aplicação', status.status === 'ok' ? 'Operacional' : 'Degradada', status.status === 'ok' ? 'ok' : 'bad'),
        tile('Banco de dados', dbOk ? `${status.database.dialect} · ${status.database.latency_ms} ms` : 'Erro', dbOk ? 'ok' : 'bad'),
        tile('Tempo no ar', formatUptime(status.uptime_seconds)),
        tile('Taxa de erro', `${(metrics.error_rate * 100).toFixed(1)}%`, metrics.errors_total ? 'bad' : 'ok'),
    ].join('');

    const records = status.database.records || {};
    document.getElementById('db-records').innerHTML = Object.entries(records).map(([key, total]) => `
        <div class="bg-slate-50 rounded-xl p-3 text-center">
            <div class="text-xl font-bold text-slate-800">${Number(total)}</div>
            <div class="text-xs text-slate-500">${escapeHtml(RECORD_LABELS[key] || key)}</div>
        </div>`).join('');

    const body = document.getElementById('routes-body');
    const routes = Object.entries(metrics.routes).sort((a, b) => b[1].count - a[1].count);
    if (!routes.length) {
        body.innerHTML = '<tr><td colspan="5"></td></tr>';
        renderEmpty(body.querySelector('td'), 'Nenhuma requisição registrada ainda.');
        return;
    }
    body.innerHTML = routes.map(([route, stats]) => `
        <tr class="border-b last:border-0">
            <td class="py-2 pr-4 font-mono text-xs text-slate-700">${escapeHtml(route)}</td>
            <td class="py-2 pr-4 text-right tabular-nums">${stats.count}</td>
            <td class="py-2 pr-4 text-right tabular-nums ${stats.errors ? 'text-red-600 font-bold' : ''}">${stats.errors}</td>
            <td class="py-2 pr-4 text-right tabular-nums">${stats.avg_ms}</td>
            <td class="py-2 text-right tabular-nums">${stats.max_ms}</td>
        </tr>`).join('');
}

renderNav('status');
renderDemoBanner();
document.getElementById('btn-refresh').addEventListener('click', load);
load();
setInterval(load, REFRESH_MS);
