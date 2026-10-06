// Apresentação das respostas do assistente educacional (ADR-021).
// O texto vem do provedor de IA: é sempre escapado e exibido com quebras de linha preservadas.
import { escapeHtml } from '../core/dom.js';

export const FEATURE_LABELS = {
    RESUMO_PRONTUARIO: 'Resumo do prontuário',
    ANALISE_EXAME: 'Explicação de exame',
    ORIENTACAO_SINTOMAS: 'Orientação sobre sintomas',
    OBSERVACOES: 'Observações',
    CHAT: 'Conversa',
};

/** Selo do provedor: deixa claro quando as respostas vêm de regras de demonstração. */
export function providerBadge(status) {
    return status.demo_mode
        ? `<span class="flag flag-attention" title="Respostas geradas por regras fixas, sem modelo de linguagem">
               <i class="fas fa-flask" aria-hidden="true"></i>Modo demonstração</span>`
        : `<span class="flag flag-normal" title="Modelo ${escapeHtml(status.model)}">
               <i class="fas fa-robot" aria-hidden="true"></i>IA: ${escapeHtml(status.model)}</span>`;
}

export const urgentNotice = () => `
    <div class="flex items-start gap-2 bg-red-50 border border-red-200 text-red-800 rounded-xl p-3 text-sm font-semibold" role="alert">
        <i class="fas fa-truck-medical mt-0.5" aria-hidden="true"></i>
        <span>Sinais de alerta identificados: procure atendimento de urgência ou ligue 192 (SAMU).</span></div>`;

/** Lista recolhível dos registros do prontuário que embasaram a resposta. */
export function factsUsed(facts) {
    if (!facts?.length) return '';
    return `<details class="text-xs text-slate-600 mt-2">
        <summary class="cursor-pointer font-semibold">Registros consultados (${facts.length})</summary>
        <ul class="mt-1 space-y-0.5">${facts.map(f => `<li><span class="text-slate-500">${escapeHtml(f.category)}:</span> ${escapeHtml(f.text)}</li>`).join('')}</ul>
    </details>`;
}

export const answerText = text => `<div class="text-sm text-slate-800 whitespace-pre-line">${escapeHtml(text)}</div>`;

export const disclaimerLine = text =>
    `<p class="text-xs text-amber-700 mt-3"><i class="fas fa-circle-info" aria-hidden="true"></i> ${escapeHtml(text)}</p>`;

/** Resposta completa de uma função pontual (resumo, observações, exame, sintomas). */
export function aiResponseCard(response) {
    return `<div class="space-y-2" data-ai-response>
        <div class="flex flex-wrap items-center justify-between gap-2">
            <strong class="text-slate-800">${escapeHtml(FEATURE_LABELS[response.feature] || response.feature)}</strong>
            <span class="text-xs text-slate-500">${escapeHtml(response.provider)} · ${escapeHtml(response.model)}</span>
        </div>
        ${response.urgent ? urgentNotice() : ''}
        ${answerText(response.text)}
        ${factsUsed(response.facts_used)}
        ${disclaimerLine(response.disclaimer)}
    </div>`;
}
