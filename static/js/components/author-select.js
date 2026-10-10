// Seletor do profissional responsável por um registro, sugerido pelo perfil de demonstração
// (R3 da modernização). A sugestão pode ser trocada; não há senha nem bloqueio (ADR-002).
import { apiCall } from '../core/api.js';
import { escapeHtml } from '../core/dom.js';
import { PROFESSIONAL_TYPES } from '../core/labels.js';
import { getProfile } from './profile.js';

let cached = null;

/** Profissionais ativos, buscados uma vez por página. */
export function activeProfessionals() {
    cached ??= apiCall('/professionals?status=ATIVO&limit=100')
        .then(page => page.items)
        .catch(err => { cached = null; throw err; });
    return cached;
}

/** ID do profissional do perfil atual (ou null se o perfil for setor ou paciente). */
export function profileProfessionalId() {
    const profile = getProfile();
    return profile.audience === 'PROFISSIONAL' ? profile.recipient_id : null;
}

/** Preenche o <select> agrupando por tipo e já escolhe o profissional do perfil, se estiver na lista. */
export function fillAuthorSelect(select, professionals, { placeholder = 'Não informado' } = {}) {
    const groups = Object.entries(PROFESSIONAL_TYPES).map(([type, label]) => {
        const options = professionals.filter(p => p.professional_type === type)
            .map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.full_name)}</option>`).join('');
        return options && `<optgroup label="${escapeHtml(label)}">${options}</optgroup>`;
    }).join('');
    select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>${groups}`;
    const mine = profileProfessionalId();
    if (mine && professionals.some(p => p.id === mine)) select.value = mine;
}

/** Desativa o botão enquanto a requisição corre, evitando registros duplicados. */
export async function whileBusy(button, action) {
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    try {
        return await action();
    } finally {
        button.disabled = false;
        button.removeAttribute('aria-busy');
    }
}
