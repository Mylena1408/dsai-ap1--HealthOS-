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
    return badge(APPOINTMENT_STATUS, status);
}

/** Preenche um <select> com as opções de um dicionário {valor: rótulo}. */
export function fillSelect(select, options, placeholder = null) {
    select.innerHTML = (placeholder !== null ? `<option value="">${escapeHtml(placeholder)}</option>` : '') +
        Object.entries(options).map(([value, label]) =>
            `<option value="${escapeHtml(value)}">${escapeHtml(typeof label === 'string' ? label : label.label)}</option>`
        ).join('');
}

// ------------------------------------------------------------- prontuário

export const BLOOD_TYPES = {
    'A+': 'A+', 'A-': 'A-', 'B+': 'B+', 'B-': 'B-', 'AB+': 'AB+', 'AB-': 'AB-', 'O+': 'O+', 'O-': 'O-',
    NAO_INFORMADO: 'Não informado',
};
export const ALLERGY_CATEGORIES = { MEDICAMENTO: 'Medicamento', ALIMENTO: 'Alimento', AMBIENTAL: 'Ambiental', OUTRO: 'Outro' };
export const ALLERGY_SEVERITY = {
    LEVE: { label: 'Leve', color: 'bg-yellow-100 text-yellow-800' },
    MODERADA: { label: 'Moderada', color: 'bg-orange-100 text-orange-800' },
    GRAVE: { label: 'Grave', color: 'bg-red-100 text-red-700' },
};
export const CONDITION_STATUS = {
    ATIVA: { label: 'Ativa', color: 'bg-red-100 text-red-700' },
    CONTROLADA: { label: 'Controlada', color: 'bg-blue-100 text-blue-700' },
    RESOLVIDA: { label: 'Resolvida', color: 'bg-emerald-100 text-emerald-700' },
};
export const DIAGNOSIS_CERTAINTY = {
    SUSPEITA: { label: 'Suspeita', color: 'bg-amber-100 text-amber-800' },
    CONFIRMADA: { label: 'Confirmada', color: 'bg-emerald-100 text-emerald-700' },
    DESCARTADA: { label: 'Descartada', color: 'bg-slate-200 text-slate-600' },
};
export const TIMELINE_TYPES = {
    CADASTRO: { label: 'Cadastro', icon: 'fa-id-card', color: 'bg-slate-500' },
    CONSULTA: { label: 'Consulta', icon: 'fa-calendar-check', color: 'bg-blue-500' },
    NOTA_CLINICA: { label: 'Nota clínica', icon: 'fa-file-medical', color: 'bg-emerald-500' },
    ALERTA: { label: 'Alerta', icon: 'fa-triangle-exclamation', color: 'bg-red-500' },
    TRIAGEM: { label: 'Triagem', icon: 'fa-stethoscope', color: 'bg-orange-500' },
    ALERGIA: { label: 'Alergia', icon: 'fa-allergies', color: 'bg-pink-500' },
    CONDICAO: { label: 'Condição', icon: 'fa-notes-medical', color: 'bg-purple-500' },
    DIAGNOSTICO: { label: 'Diagnóstico', icon: 'fa-magnifying-glass', color: 'bg-indigo-500' },
    PROCEDIMENTO: { label: 'Procedimento', icon: 'fa-syringe', color: 'bg-teal-500' },
    SINAIS_VITAIS: { label: 'Sinais vitais', icon: 'fa-heart-pulse', color: 'bg-rose-500' },
    EXAME: { label: 'Exame', icon: 'fa-vial', color: 'bg-cyan-600' },
};

/** Etiqueta colorida para qualquer dicionário {valor: {label, color}}. */
export function badge(dictionary, value) {
    const info = dictionary[value] || { label: value, color: 'bg-slate-100 text-slate-600' };
    return `<span class="text-xs font-semibold px-2 py-1 rounded-full whitespace-nowrap ${info.color}">${escapeHtml(info.label)}</span>`;
}

// ------------------------------------------------- sinais vitais e laboratório

export const RESULT_FLAGS = {
    NORMAL: { label: 'Normal', icon: 'fa-circle-check', css: 'flag-normal' },
    BAIXO: { label: 'Baixo', icon: 'fa-arrow-down', css: 'flag-attention' },
    ALTO: { label: 'Alto', icon: 'fa-arrow-up', css: 'flag-attention' },
    CRITICO_BAIXO: { label: 'Crítico (baixo)', icon: 'fa-triangle-exclamation', css: 'flag-critical' },
    CRITICO_ALTO: { label: 'Crítico (alto)', icon: 'fa-triangle-exclamation', css: 'flag-critical' },
};

/** Etiqueta de classificação: cor + ícone + texto (nunca só cor). */
export function flagBadge(flag) {
    const info = RESULT_FLAGS[flag];
    if (!info) return '';
    return `<span class="flag ${info.css}"><i class="fas ${info.icon}" aria-hidden="true"></i>${escapeHtml(info.label)}</span>`;
}

export const BMI_CATEGORIES = {
    BAIXO_PESO: 'Baixo peso', PESO_ADEQUADO: 'Peso adequado', SOBREPESO: 'Sobrepeso', OBESIDADE: 'Obesidade',
};

export const EXAM_STATUS = {
    SOLICITADO: { label: 'Solicitado', color: 'bg-slate-100 text-slate-700' },
    AGENDADO: { label: 'Agendado', color: 'bg-blue-100 text-blue-700' },
    COLETADO: { label: 'Coletado', color: 'bg-indigo-100 text-indigo-700' },
    EM_PROCESSAMENTO: { label: 'Em processamento', color: 'bg-amber-100 text-amber-800' },
    RESULTADO_REGISTRADO: { label: 'Resultado registrado', color: 'bg-purple-100 text-purple-700' },
    VALIDADO: { label: 'Validado', color: 'bg-teal-100 text-teal-700' },
    LIBERADO: { label: 'Liberado', color: 'bg-emerald-100 text-emerald-700' },
    CANCELADO: { label: 'Cancelado', color: 'bg-slate-200 text-slate-500' },
};

export const EXAM_PRIORITY = { ROTINA: 'Rotina', URGENTE: 'Urgente' };
