// Verificação do assistente (harness): resultado dos casos fixos de SPEC/2026-10-19-harness-assistente.md.
// Entradas e respostas são sempre escapadas.
import { escapeHtml, formatDateTime } from '../core/dom.js';

const STATUS = {
    APROVADO: { css: 'flag-normal', icon: 'fa-circle-check', label: 'Aprovado' },
    REPROVADO: { css: 'flag-critical', icon: 'fa-circle-xmark', label: 'Reprovado' },
    PULADO: { css: 'flag-attention', icon: 'fa-forward', label: 'Pulado' },
};

const GROUPS = { SEGURANCA: 'Segurança', COMPORTAMENTO: 'Comportamento' };

const statusFlag = status => {
    const s = STATUS[status] || STATUS.PULADO;
    return `<span class="flag ${s.css}"><i class="fas ${s.icon}" aria-hidden="true"></i>${s.label}</span>`;
};

const executed = report => report.total - report.skipped;

/** Selo curto ao lado do selo do provedor: resultado da última execução. */
export function harnessBadge(report) {
    const css = report.failed ? 'flag-critical' : 'flag-normal';
    const icon = report.failed ? 'fa-circle-xmark' : 'fa-shield-halved';
    return `<a href="#harness" class="flag ${css}" title="Resultado da verificação do assistente">
        <i class="fas ${icon}" aria-hidden="true"></i>Verificação: ${report.passed} de ${executed(report)}</a>`;
}

function checksList(checks) {
    if (!checks.length) return '';
    return `<ul class="mt-1 space-y-0.5">${checks.map(c => `
        <li class="${c.passed ? 'text-slate-600' : 'text-red-700 font-semibold'}">
            <i class="fas ${c.passed ? 'fa-check' : 'fa-xmark'}" aria-hidden="true"></i>
            <span class="sr-only">${c.passed ? 'ok:' : 'falhou:'}</span> ${escapeHtml(c.name)}</li>`).join('')}</ul>`;
}

/** Resumo e tabela com cada caso: código, entrada, esperado, obtido e situação. */
export function harnessReport(report) {
    const summary = report.failed
        ? `${report.failed} verificação(ões) reprovada(s); ${report.passed} de ${executed(report)} aprovadas`
        : `${report.passed} de ${executed(report)} verificações aprovadas`;
    const skipped = report.skipped
        ? `<p class="text-xs text-amber-700">${report.skipped} caso(s) pulado(s): com provedor real, os casos que chamam a IA não rodam, para evitar custo e envio de dados.</p>`
        : '';
    return `<div class="space-y-3" data-harness-report>
        <div class="flex flex-wrap items-center justify-between gap-2">
            <strong class="text-slate-800" role="status">${escapeHtml(summary)}</strong>
            <span class="text-xs text-slate-500">${escapeHtml(report.provider)} · ${escapeHtml(report.model)} · ${formatDateTime(report.ran_at)}</span>
        </div>
        ${skipped}
        <div class="overflow-x-auto">
            <table class="w-full text-sm text-left">
                <caption class="sr-only">Casos de verificação do assistente</caption>
                <thead class="text-xs text-slate-500 uppercase border-b">
                    <tr><th scope="col" class="py-2 pr-3">Caso</th><th scope="col" class="py-2 pr-3">Entrada</th>
                        <th scope="col" class="py-2 pr-3">Esperado</th><th scope="col" class="py-2 pr-3">Obtido</th>
                        <th scope="col" class="py-2">Situação</th></tr>
                </thead>
                <tbody class="divide-y">${report.cases.map(c => `
                    <tr class="align-top">
                        <td class="py-2 pr-3 whitespace-nowrap"><div class="font-semibold text-slate-800">${escapeHtml(c.code)}</div>
                            <div class="text-xs text-slate-500">${escapeHtml(GROUPS[c.group] || c.group)}</div></td>
                        <td class="py-2 pr-3 text-slate-700">${escapeHtml(c.input)}</td>
                        <td class="py-2 pr-3 text-slate-700">${escapeHtml(c.expected)}</td>
                        <td class="py-2 pr-3 text-slate-700">${escapeHtml(c.obtained)}
                            <details class="text-xs mt-1"><summary class="cursor-pointer text-slate-500">Verificações (${c.checks.length})</summary>
                                ${checksList(c.checks)}</details></td>
                        <td class="py-2">${statusFlag(c.status)}</td>
                    </tr>`).join('')}</tbody>
            </table>
        </div>
    </div>`;
}
