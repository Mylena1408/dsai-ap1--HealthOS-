// Barra de navegação compartilhada. Cada novo módulo com página própria
// acrescenta uma entrada em NAV_GROUPS (ou um link direto em NAV_LINKS).
// O menu "Para você" só sugere telas pelo perfil; os grupos continuam com todas (ADR-027).
import { getProfile, mountProfileControls } from '../components/profile.js';
import { escapeHtml } from './dom.js';
import { pagesForProfile } from './role-nav.js';

const NAV_LINKS = [
    { id: 'painel', label: 'Painel', href: '/app/painel', icon: 'fa-chart-line' },
];

// Menus agrupados (padrão "disclosure"): cabem em qualquer largura, ao contrário de 16 links soltos.
const NAV_GROUPS = [
    { id: 'atendimento', label: 'Atendimento', icon: 'fa-stethoscope', items: [
        { id: 'prontuario', label: 'Prontuário', href: '/app/prontuario', icon: 'fa-notes-medical' },
        { id: 'consultas', label: 'Consultas', href: '/app/consultas', icon: 'fa-calendar-days' },
        { id: 'laboratorio', label: 'Laboratório', href: '/app/laboratorio', icon: 'fa-flask' },
        { id: 'farmacia', label: 'Farmácia', href: '/app/farmacia', icon: 'fa-prescription-bottle-medical' },
        { id: 'assistente', label: 'Assistente educacional', href: '/app/assistente', icon: 'fa-robot' },
    ] },
    { id: 'gestao', label: 'Gestão', icon: 'fa-briefcase', items: [
        { id: 'financeiro', label: 'Financeiro', href: '/app/financeiro', icon: 'fa-file-invoice-dollar' },
        { id: 'relatorios', label: 'Relatórios', href: '/app/relatorios', icon: 'fa-file-lines' },
        { id: 'alertas', label: 'Alertas', href: '/app/alertas', icon: 'fa-triangle-exclamation' },
        { id: 'profissionais', label: 'Profissionais', href: '/app/profissionais', icon: 'fa-user-doctor' },
        { id: 'auditoria', label: 'Auditoria', href: '/app/auditoria', icon: 'fa-clipboard-list' },
        { id: 'status', label: 'Status do sistema', href: '/app/status', icon: 'fa-heart-pulse' },
        { id: 'docs', label: 'Documentação da API', href: '/docs', icon: 'fa-book-open', external: true },
    ] },
];

// Páginas fora dos menus (sino e busca no topo) que o menu "Para você" pode sugerir.
const EXTRA_PAGES = [
    { id: 'notificacoes', label: 'Notificações', href: '/app/notificacoes', icon: 'fa-bell' },
    { id: 'busca', label: 'Busca', href: '/app/busca', icon: 'fa-magnifying-glass' },
];

const PAGE_CATALOG = new Map([...NAV_LINKS, ...NAV_GROUPS.flatMap(group => group.items), ...EXTRA_PAGES]
    .map(item => [item.id, item]));

const FOR_YOU = { id: 'para-voce', label: 'Para você', icon: 'fa-user-check' };
const FOR_YOU_HINT = 'Sugestões do perfil de demonstração. Todas as telas continuam em Atendimento e Gestão.';

const linkClass = active => (active ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-100');

// `markCurrent: false` nas sugestões: a página atual é anunciada só uma vez, nos menus com todas as telas.
function itemLink(item, activeId, { markCurrent = true } = {}) {
    const active = item.id === activeId;
    const external = item.external ? ' target="_blank" rel="noopener"' : '';
    return `<a href="${item.href}" class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${linkClass(active)}"
               ${active && markCurrent ? 'aria-current="page"' : ''}${external}>
               <i class="fas ${item.icon} w-4 text-center" aria-hidden="true"></i>${item.label}${item.external
                   ? '<span class="sr-only"> (abre em nova aba)</span>' : ''}</a>`;
}

function forYouLinks(activeId) {
    return pagesForProfile(getProfile())
        .map(id => PAGE_CATALOG.get(id)).filter(Boolean)
        .map(item => itemLink(item, activeId, { markCurrent: false })).join('');
}

function forYouLabel() {
    return `Perfil: ${escapeHtml(getProfile().label)}`;
}

function groupMenu(group, active, content) {
    return `<div class="relative" data-nav-group>
            <button type="button" aria-expanded="false" aria-controls="nav-menu-${group.id}"
                class="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium ${linkClass(active)}">
                <i class="fas ${group.icon}" aria-hidden="true"></i>${group.label}
                <i class="fas fa-chevron-down text-xs" aria-hidden="true"></i></button>
            <div id="nav-menu-${group.id}" hidden
                class="absolute left-0 mt-2 w-64 bg-white border border-slate-200 rounded-xl shadow-lg p-2 z-[60]">
                ${content}
            </div>
        </div>`;
}

function desktopNav(activeId) {
    const links = NAV_LINKS.map(item => itemLink(item, activeId)).join('');
    const forYou = groupMenu(FOR_YOU, false, `
        <p class="px-3 pt-1 pb-2 text-xs text-slate-600"><span data-for-you-label>${forYouLabel()}</span>.
            ${FOR_YOU_HINT}</p>
        <div data-for-you>${forYouLinks(activeId)}</div>`);
    const groups = NAV_GROUPS.map(group => groupMenu(group, group.items.some(item => item.id === activeId),
        group.items.map(item => itemLink(item, activeId)).join(''))).join('');
    return `<div class="hidden lg:flex items-center gap-1">${links}${forYou}${groups}</div>`;
}

function mobilePanel(activeId) {
    const heading = label => `<p class="px-3 pt-3 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">${label}</p>`;
    const groups = NAV_GROUPS.map(group => `
        <div>${heading(group.label)}
            <div class="space-y-1">${group.items.map(item => itemLink(item, activeId)).join('')}</div></div>`).join('');
    return `<div id="nav-mobile" hidden
        class="lg:hidden absolute left-0 right-0 top-full bg-white border-b border-slate-200 shadow-lg px-4 pb-4 max-h-[calc(100vh-4.5rem)] overflow-y-auto">
        <form action="/app/busca" role="search" class="pt-3">
            <label for="nav-mobile-search" class="sr-only">Buscar no sistema</label>
            <input id="nav-mobile-search" name="q" type="search" minlength="2" maxlength="80"
                placeholder="Buscar pacientes, faturas..." class="w-full p-2 border rounded-lg text-sm">
        </form>
        <div class="space-y-1 pt-3">${NAV_LINKS.map(item => itemLink(item, activeId)).join('')}</div>
        <div>${heading(FOR_YOU.label)}
            <p class="px-3 pb-1 text-xs text-slate-600"><span data-for-you-label>${forYouLabel()}</span>. ${FOR_YOU_HINT}</p>
            <div class="space-y-1" data-for-you>${forYouLinks(activeId)}</div></div>
        ${groups}
    </div>`;
}

/** Refaz as sugestões (barra e menu móvel) quando o perfil muda, sem recarregar a página. */
function refreshForYou(nav, activeId) {
    nav.querySelectorAll('[data-for-you]').forEach(list => { list.innerHTML = forYouLinks(activeId); });
    nav.querySelectorAll('[data-for-you-label]').forEach(label => { label.textContent = `Perfil: ${getProfile().label}`; });
}

export function renderNav(activeId) {
    const nav = document.getElementById('app-nav');
    if (!nav) return;

    nav.className = 'bg-white border-b border-slate-200 px-4 sm:px-6 py-3 flex justify-between items-center sticky top-0 z-50 gap-3';
    nav.setAttribute('aria-label', 'Navegação principal');
    nav.innerHTML = `
        <div class="flex items-center gap-2 min-w-0">
            <button type="button" id="nav-toggle" aria-expanded="false" aria-controls="nav-mobile"
                class="lg:hidden px-2 py-2 rounded-md text-slate-700 hover:bg-slate-100">
                <i class="fas fa-bars" aria-hidden="true"></i><span class="sr-only">Abrir menu</span></button>
            <a href="/" class="flex items-center gap-2 shrink-0" aria-label="HealthOS: página inicial (portal)">
                <div class="bg-blue-600 p-2 rounded-lg"><i class="fas fa-hospital-user text-white text-xl" aria-hidden="true"></i></div>
                <span class="hidden sm:inline lg:hidden xl:inline text-2xl font-bold text-slate-800 tracking-tight">Health<span class="text-blue-600">OS</span></span>
            </a>
        </div>
        ${desktopNav(activeId)}
        <div class="flex items-center gap-2 shrink-0">
            <form id="nav-search" action="/app/busca" role="search" class="hidden md:flex items-center">
                <label for="nav-search-input" class="sr-only">Buscar no sistema</label>
                <input id="nav-search-input" name="q" type="search" minlength="2" maxlength="80" placeholder="Buscar ( / )"
                    class="w-32 xl:w-56 p-2 border rounded-lg text-sm">
            </form>
            <div id="nav-profile"></div>
        </div>
        ${mobilePanel(activeId)}`;
    mountProfileControls(document.getElementById('nav-profile'));
    window.addEventListener('healthos:profile', () => refreshForYou(nav, activeId));
    enableMenus(nav);
    enableSearchShortcut();
}

/** Abre/fecha os menus: clique no botão, Esc, clique fora ou foco saindo do menu. */
function enableMenus(nav) {
    const toggles = [...nav.querySelectorAll('button[aria-controls]')];
    const setOpen = (button, open) => {
        button.setAttribute('aria-expanded', String(open));
        document.getElementById(button.getAttribute('aria-controls')).hidden = !open;
    };
    const closeAll = except => toggles.forEach(b => { if (b !== except) setOpen(b, false); });

    toggles.forEach(button => button.addEventListener('click', () => {
        const open = button.getAttribute('aria-expanded') !== 'true';
        closeAll(button);
        setOpen(button, open);
    }));
    nav.querySelectorAll('[data-nav-group]').forEach(group => group.addEventListener('focusout', event => {
        if (event.relatedTarget && !group.contains(event.relatedTarget)) setOpen(group.querySelector('button'), false);
    }));
    document.addEventListener('click', event => { if (!nav.contains(event.target)) closeAll(); });
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        const open = toggles.find(b => b.getAttribute('aria-expanded') === 'true');
        if (open) { setOpen(open, false); open.focus(); }
    });
}

let searchShortcutEnabled = false;

/** Tecla "/" leva ao campo de busca (exceto quando já se está digitando em um campo). */
function enableSearchShortcut() {
    if (searchShortcutEnabled) return;
    searchShortcutEnabled = true;
    document.addEventListener('keydown', event => {
        const typing = event.target.closest?.('input, textarea, select, [contenteditable="true"]');
        const input = document.getElementById('nav-search-input');
        if (event.key !== '/' || typing || !input || input.offsetParent === null) return;
        event.preventDefault();
        input.focus();
    });
}

/** Faixa que lembra, em todas as páginas, que o sistema é demonstrativo. */
export function renderDemoBanner() {
    if (document.getElementById('demo-banner')) return;
    const banner = document.createElement('div');
    banner.id = 'demo-banner';
    banner.className = 'bg-amber-50 border-b border-amber-200 text-amber-800 text-xs text-center px-4 py-2';
    banner.innerText = 'Ambiente didático: todos os dados são fictícios e nada aqui substitui avaliação profissional.';
    document.getElementById('app-nav')?.after(banner);
}
