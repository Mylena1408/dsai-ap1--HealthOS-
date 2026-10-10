// Perfil de demonstração (sem autenticação — ADR-002) e sino de notificações.
// O perfil escolhe qual caixa de entrada é exibida (paciente, profissional ou setor) e as
// sugestões do menu "Para você" (ADR-027). Profissionais guardam também o tipo.
import { apiCall } from '../core/api.js';
import { escapeHtml } from '../core/dom.js';
import { PROFESSIONAL_TYPES } from '../core/labels.js';

const STORAGE_KEY = 'healthos.profile';
export const SECTORS = {
    RECEPCAO: 'Recepção', LABORATORIO: 'Laboratório', FARMACIA: 'Farmácia',
    COORDENACAO_CLINICA: 'Coordenação clínica', ADMINISTRACAO: 'Administração',
};
const DEFAULT_PROFILE = { audience: 'SETOR', sector: 'ADMINISTRACAO', label: 'Administração' };

export function getProfile() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY)) || DEFAULT_PROFILE;
    } catch {
        return DEFAULT_PROFILE;
    }
}

export function setProfile(profile) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile)); } catch { /* armazenamento indisponível */ }
    window.dispatchEvent(new CustomEvent('healthos:profile', { detail: profile }));
}

/** Parâmetros de consulta da caixa de entrada do perfil atual. */
export function inboxParams(profile = getProfile()) {
    const params = new URLSearchParams({ audience: profile.audience });
    if (profile.audience === 'SETOR') params.set('sector', profile.sector);
    else params.set('recipient_id', profile.recipient_id);
    return params;
}

async function refreshBell(button) {
    try {
        const counts = await apiCall(`/inbox/counts?${inboxParams()}`);
        const badge = button.querySelector('[data-unread]');
        badge.textContent = counts.unread > 99 ? '99+' : String(counts.unread);
        badge.classList.toggle('hidden', counts.unread === 0);
        button.setAttribute('aria-label', `Notificações: ${counts.unread} não lida(s)`);
    } catch { /* o sino é auxiliar; falhas não bloqueiam a página */ }
}

function openPicker() {
    let dialog = document.getElementById('profile-picker');
    if (!dialog) {
        dialog = document.createElement('div');
        dialog.id = 'profile-picker';
        dialog.className = 'modal';
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.innerHTML = `
            <div class="bg-white p-6 rounded-2xl w-full max-w-md shadow-2xl relative">
                <button data-close-profile aria-label="Fechar" class="absolute top-4 right-4 text-slate-500 hover:text-slate-600"><i class="fas fa-times"></i></button>
                <h3 class="text-xl font-bold text-slate-800 mb-1">Perfil de demonstração</h3>
                <p class="text-xs text-slate-600 mb-4">Sem senha: o perfil escolhe a caixa de notificações e as
                    sugestões do menu "Para você". Todas as telas continuam acessíveis.</p>
                <div class="space-y-4">
                    <div><span class="text-sm font-medium text-slate-700">Setor</span>
                        <div class="flex flex-wrap gap-2 mt-2">${Object.entries(SECTORS).map(([key, label]) =>
                            `<button data-sector="${key}" class="px-3 py-1 rounded-lg border text-sm hover:bg-blue-50">${label}</button>`).join('')}</div></div>
                    <label class="block text-sm font-medium text-slate-700">Profissional
                        <select data-professional class="w-full p-2 border rounded-lg mt-1"><option value="">Carregando...</option></select></label>
                    <label class="block text-sm font-medium text-slate-700">Paciente
                        <input data-patient-search type="search" placeholder="Buscar por nome" class="w-full p-2 border rounded-lg mt-1"></label>
                    <ul data-patient-results class="divide-y max-h-40 overflow-y-auto"></ul>
                </div>
            </div>`;
        document.body.appendChild(dialog);
        dialog.addEventListener('click', event => {
            if (event.target === dialog || event.target.closest('[data-close-profile]')) dialog.classList.remove('active');
            const sector = event.target.closest('[data-sector]');
            if (sector) choose({ audience: 'SETOR', sector: sector.dataset.sector, label: SECTORS[sector.dataset.sector] });
            const patient = event.target.closest('[data-patient-id]');
            if (patient) choose({ audience: 'PACIENTE', recipient_id: patient.dataset.patientId, label: patient.dataset.label });
        });
        const select = dialog.querySelector('[data-professional]');
        apiCall('/professionals?status=ATIVO&limit=100').then(page => {
            const groups = Object.entries(PROFESSIONAL_TYPES).map(([type, typeLabel]) => {
                const options = page.items.filter(p => p.professional_type === type).map(p =>
                    `<option value="${escapeHtml(p.id)}" data-type="${type}">${escapeHtml(p.full_name)}</option>`).join('');
                return options && `<optgroup label="${escapeHtml(typeLabel)}">${options}</optgroup>`;
            });
            select.innerHTML = '<option value="">Selecione</option>' + groups.join('');
        }).catch(() => { select.innerHTML = '<option value="">Indisponível</option>'; });
        select.addEventListener('change', () => select.value && choose({
            audience: 'PROFISSIONAL', recipient_id: select.value, label: select.selectedOptions[0].textContent,
            professional_type: select.selectedOptions[0].dataset.type }));
        let debounce;
        dialog.querySelector('[data-patient-search]').addEventListener('input', event => {
            clearTimeout(debounce);
            debounce = setTimeout(async () => {
                const page = await apiCall(`/patients?${new URLSearchParams({ q: event.target.value, limit: 6 })}`);
                dialog.querySelector('[data-patient-results]').innerHTML = page.items.map(p => `
                    <li><button data-patient-id="${escapeHtml(p.id)}" data-label="${escapeHtml(p.full_name)}"
                        class="w-full text-left px-2 py-2 text-sm hover:bg-blue-50">${escapeHtml(p.full_name)}</button></li>`).join('');
            }, 250);
        });
    }
    function choose(profile) {
        setProfile(profile);
        dialog.classList.remove('active');
    }
    dialog.classList.add('active');
}

/** Acrescenta seletor de perfil e sino à barra de navegação. */
export function mountProfileControls(container) {
    const wrapper = document.createElement('div');
    wrapper.className = 'flex items-center gap-1 shrink-0';
    wrapper.innerHTML = `
        <button data-profile class="px-2 py-2 rounded-md text-xs sm:text-sm text-slate-600 hover:bg-slate-100 flex items-center gap-1 max-w-[10rem]">
            <i class="fas fa-user-circle" aria-hidden="true"></i><span class="hidden sm:inline md:hidden xl:inline truncate" data-profile-label></span></button>
        <a href="/app/notificacoes" data-bell class="relative px-2 py-2 rounded-md text-slate-600 hover:bg-slate-100">
            <i class="fas fa-bell" aria-hidden="true"></i>
            <span data-unread class="hidden absolute -top-0.5 -right-0.5 bg-red-600 text-white text-[10px] font-bold rounded-full px-1.5 leading-4"></span></a>`;
    container.prepend(wrapper);
    const label = wrapper.querySelector('[data-profile-label]');
    const bell = wrapper.querySelector('[data-bell]');
    const button = wrapper.querySelector('[data-profile]');
    const update = () => {
        const profile = getProfile();
        const type = PROFESSIONAL_TYPES[profile.professional_type];
        label.textContent = profile.label;
        button.setAttribute('aria-label', `Perfil de demonstração: ${profile.label}${type ? `, ${type}` : ''} (trocar)`);
        refreshBell(bell);
    };
    button.addEventListener('click', openPicker);
    window.addEventListener('healthos:profile', update);
    window.addEventListener('healthos:inbox-changed', () => refreshBell(bell));
    update();
}
