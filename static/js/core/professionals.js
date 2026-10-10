// Lista de profissionais ativos (uma busca por página) e opções agrupadas por tipo, usadas pelo
// seletor de perfil e pelo seletor de autor dos registros.
import { apiCall } from './api.js';
import { escapeHtml } from './dom.js';
import { PROFESSIONAL_TYPES } from './labels.js';

let cached = null;

/** Profissionais ativos, buscados uma vez por página. */
export function activeProfessionals() {
    cached ??= apiCall('/professionals?status=ATIVO&limit=100')
        .then(page => page.items)
        .catch(err => { cached = null; throw err; });
    return cached;
}

/** `<optgroup>` por tipo; `withType` acrescenta data-type em cada opção (seletor de perfil). */
export function groupedProfessionalOptions(professionals, { withType = false } = {}) {
    return Object.entries(PROFESSIONAL_TYPES).map(([type, label]) => {
        const options = professionals.filter(p => p.professional_type === type)
            .map(p => `<option value="${escapeHtml(p.id)}"${withType ? ` data-type="${type}"` : ''}>${escapeHtml(p.full_name)}</option>`)
            .join('');
        return options && `<optgroup label="${escapeHtml(label)}">${options}</optgroup>`;
    }).join('');
}
