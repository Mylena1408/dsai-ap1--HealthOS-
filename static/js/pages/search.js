// Busca global: resultados agrupados por tipo, cada um com link para a página correspondente.
import { apiCall } from '../core/api.js';
import { escapeHtml, highlightTerm, renderEmpty, renderLoading } from '../core/dom.js';
import { renderNav, renderDemoBanner } from '../core/layout.js';

const PER_GROUP = 8;
const $ = id => document.getElementById(id);
const ICONS = { pacientes: 'fa-user', profissionais: 'fa-user-doctor', medicamentos: 'fa-pills', exames: 'fa-vial',
                faturas: 'fa-file-invoice-dollar', relatorios: 'fa-file-lines' };

async function search(term) {
    const results = $('results');
    if (term.trim().length < 2) return renderEmpty(results, 'Digite ao menos 2 caracteres.');
    history.replaceState(null, '', `?q=${encodeURIComponent(term)}`);
    renderLoading(results, 'Buscando...');
    try {
        const data = await apiCall(`/search?${new URLSearchParams({ q: term, per_group: PER_GROUP })}`);
        if (!data.groups.length) return renderEmpty(results, `Nada encontrado para "${data.query}".`);
        results.innerHTML = data.groups.map(group => `
            <section class="glass-card rounded-2xl p-5" aria-labelledby="group-${escapeHtml(group.key)}">
                <h2 id="group-${escapeHtml(group.key)}" class="font-bold text-slate-800 mb-2">
                    <i class="fas ${ICONS[group.key] || 'fa-circle'} text-slate-400 mr-1" aria-hidden="true"></i>${escapeHtml(group.label)}
                    <span class="text-sm font-normal text-slate-500">(${group.total > group.items.length ? `${group.items.length} de ${group.total}` : group.total})</span>
                </h2>
                <ul class="divide-y">${group.items.map(item => `
                    <li><a href="${escapeHtml(item.link)}" class="block py-2 px-2 -mx-2 rounded-lg hover:bg-blue-50">
                        <div class="font-medium text-slate-800">${highlightTerm(item.title, data.query)}</div>
                        <div class="text-xs text-slate-500">${highlightTerm(item.subtitle, data.query)}</div>
                    </a></li>`).join('')}</ul>
                ${group.total > group.items.length ? '<p class="text-xs text-slate-500 mt-2">Refine o termo para ver os demais.</p>' : ''}
            </section>`).join('');
    } catch (err) {
        renderEmpty(results, `Erro: ${err.message}`);
    }
}

renderNav('busca');
renderDemoBanner();
$('form-search').addEventListener('submit', event => { event.preventDefault(); search($('q').value); });
const initial = new URLSearchParams(window.location.search).get('q') || '';
$('q').value = initial;
if (initial) search(initial);
else $('q').focus();
