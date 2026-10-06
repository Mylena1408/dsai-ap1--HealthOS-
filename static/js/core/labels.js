// Rótulos em português e cores dos valores enumerados da API.
import { escapeHtml } from './dom.js';

export const PROFESSIONAL_TYPES = {
    MEDICO: 'Médico(a)', ENFERMEIRO: 'Enfermeiro(a)', FARMACEUTICO: 'Farmacêutico(a)',
    NUTRICIONISTA: 'Nutricionista', FISIOTERAPEUTA: 'Fisioterapeuta', PSICOLOGO: 'Psicólogo(a)', OUTRO: 'Outro',
};

export const PROFESSIONAL_STATUS = { ATIVO: 'Ativo', AFASTADO: 'Afastado', INATIVO: 'Inativo' };

export const APPOINTMENT_TYPES = {
    PRIMEIRA_CONSULTA: 'Primeira consulta', RETORNO: 'Retorno', URGENCIA: 'Urgência', TELECONSULTA: 'Teleconsulta',
};

export const APPOINTMENT_STATUS = {
    AGENDADA: { label: 'Agendada', color: 'bg-blue-100 text-blue-700' },
    CONFIRMADA: { label: 'Confirmada', color: 'bg-indigo-100 text-indigo-700' },
    EM_ANDAMENTO: { label: 'Em andamento', color: 'bg-amber-100 text-amber-800' },
    FINALIZADA: { label: 'Finalizada', color: 'bg-emerald-100 text-emerald-700' },
    CANCELADA: { label: 'Cancelada', color: 'bg-slate-200 text-slate-600' },
    NAO_COMPARECEU: { label: 'Não compareceu', color: 'bg-red-100 text-red-700' },
};

// Ação da API correspondente a cada status de destino.
export const TRANSITION_ACTIONS = {
    CONFIRMADA: { path: 'confirm', label: 'Confirmar', icon: 'fa-check' },
    EM_ANDAMENTO: { path: 'start', label: 'Iniciar', icon: 'fa-play' },
    FINALIZADA: { path: 'complete', label: 'Finalizar', icon: 'fa-flag-checkered' },
    CANCELADA: { path: 'cancel', label: 'Cancelar', icon: 'fa-ban', needsReason: true },
    NAO_COMPARECEU: { path: 'no-show', label: 'Não compareceu', icon: 'fa-user-xmark' },
};

export const WEEKDAYS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];

export function statusBadge(status) {
    const info = APPOINTMENT_STATUS[status] || { label: status, color: 'bg-slate-100 text-slate-600' };
    return `<span class="text-xs font-semibold px-2 py-1 rounded-full whitespace-nowrap ${info.color}">${escapeHtml(info.label)}</span>`;
}

/** Preenche um <select> com as opções de um dicionário {valor: rótulo}. */
export function fillSelect(select, options, placeholder = null) {
    select.innerHTML = (placeholder !== null ? `<option value="">${escapeHtml(placeholder)}</option>` : '') +
        Object.entries(options).map(([value, label]) =>
            `<option value="${escapeHtml(value)}">${escapeHtml(typeof label === 'string' ? label : label.label)}</option>`
        ).join('');
}
