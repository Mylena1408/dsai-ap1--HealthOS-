// Seletor do profissional responsável por um registro, sugerido pelo perfil de demonstração
// (R3 da modernização). A sugestão pode ser trocada; não há senha nem bloqueio (ADR-002).
import { activeProfessionals, groupedProfessionalOptions } from '../core/professionals.js';
import { escapeHtml } from '../core/dom.js';
import { getProfile } from './profile.js';

export { activeProfessionals };

/** ID do profissional do perfil atual (ou null se o perfil for setor ou paciente). */
export function profileProfessionalId() {
    const profile = getProfile();
    return profile.audience === 'PROFISSIONAL' ? profile.recipient_id : null;
}

/** Preenche o <select> agrupando por tipo e já escolhe o profissional do perfil, se estiver na lista. */
export function fillAuthorSelect(select, professionals, { placeholder = 'Não informado' } = {}) {
    select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>${groupedProfessionalOptions(professionals)}`;
    const mine = profileProfessionalId();
    if (mine && professionals.some(p => p.id === mine)) select.value = mine;
}
