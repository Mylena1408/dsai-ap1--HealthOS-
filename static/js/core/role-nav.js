// Telas sugeridas por perfil de demonstração (menu "Para você").
// É orientação de uso, não controle de acesso: todas as telas continuam abertas (ADR-002, ADR-027).

const GENERIC_PROFESSIONAL = ['painel', 'prontuario', 'consultas', 'alertas'];

export const PROFILE_PAGES = {
    MEDICO: ['painel', 'prontuario', 'consultas', 'laboratorio', 'alertas', 'assistente'],
    ENFERMEIRO: ['painel', 'prontuario', 'consultas', 'alertas', 'laboratorio'],
    FARMACEUTICO: ['painel', 'farmacia', 'prontuario', 'alertas'],
    PSICOLOGO: GENERIC_PROFESSIONAL,
    NUTRICIONISTA: GENERIC_PROFESSIONAL,
    FISIOTERAPEUTA: GENERIC_PROFESSIONAL,
    OUTRO: GENERIC_PROFESSIONAL,
    'SETOR:FARMACIA': ['painel', 'farmacia', 'prontuario', 'alertas'],
    'SETOR:ENFERMAGEM': ['painel', 'prontuario', 'consultas', 'alertas', 'laboratorio'],
    'SETOR:LABORATORIO': ['laboratorio', 'painel', 'alertas'],
    'SETOR:RECEPCAO': ['consultas', 'busca', 'profissionais'],
    'SETOR:COORDENACAO_CLINICA': ['painel', 'alertas', 'profissionais', 'relatorios', 'auditoria'],
    'SETOR:ADMINISTRACAO': ['painel', 'financeiro', 'relatorios', 'profissionais', 'auditoria', 'status'],
    PACIENTE: ['painel', 'notificacoes', 'assistente'],
};

/** Ids das páginas sugeridas para o perfil (perfis antigos sem tipo recebem a sugestão genérica). */
export function pagesForProfile(profile) {
    if (profile?.audience === 'PACIENTE') return PROFILE_PAGES.PACIENTE;
    if (profile?.audience === 'PROFISSIONAL') return PROFILE_PAGES[profile.professional_type] || GENERIC_PROFESSIONAL;
    return PROFILE_PAGES[`SETOR:${profile?.sector}`] || PROFILE_PAGES['SETOR:ADMINISTRACAO'];
}

/** Visão inicial do Painel para o perfil de demonstração. */
export function dashboardViewFor(profile) {
    if (profile?.audience === 'PACIENTE') return 'patient';
    if (profile?.audience === 'PROFISSIONAL') return profile.professional_type === 'ENFERMEIRO' ? 'nursing' : 'professional';
    return { FARMACIA: 'pharmacy', ENFERMAGEM: 'nursing' }[profile?.sector] || 'admin';
}
