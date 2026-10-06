// Barra de navegação compartilhada. Cada novo módulo com página própria
// acrescenta uma entrada em NAV_ITEMS.
import { mountProfileControls } from '../components/profile.js';

const NAV_ITEMS = [
    { id: 'portal', label: 'Portal', href: '/', icon: 'fa-house-medical' },
    { id: 'painel', label: 'Painel', href: '/app/painel', icon: 'fa-chart-line' },
    { id: 'prontuario', label: 'Prontuário', href: '/app/prontuario', icon: 'fa-notes-medical' },
    { id: 'consultas', label: 'Consultas', href: '/app/consultas', icon: 'fa-calendar-days' },
    { id: 'laboratorio', label: 'Laboratório', href: '/app/laboratorio', icon: 'fa-flask' },
    { id: 'farmacia', label: 'Farmácia', href: '/app/farmacia', icon: 'fa-prescription-bottle-medical' },
    { id: 'financeiro', label: 'Financeiro', href: '/app/financeiro', icon: 'fa-file-invoice-dollar' },
    { id: 'relatorios', label: 'Relatórios', href: '/app/relatorios', icon: 'fa-file-lines' },
    { id: 'assistente', label: 'Assistente', href: '/app/assistente', icon: 'fa-robot' },
    { id: 'alertas', label: 'Alertas', href: '/app/alertas', icon: 'fa-triangle-exclamation' },
    { id: 'profissionais', label: 'Profissionais', href: '/app/profissionais', icon: 'fa-user-doctor' },
    { id: 'auditoria', label: 'Auditoria', href: '/app/auditoria', icon: 'fa-clipboard-list' },
    { id: 'status', label: 'Status', href: '/app/status', icon: 'fa-heart-pulse' },
];

export function renderNav(activeId) {
    const nav = document.getElementById('app-nav');
    if (!nav) return;

    const links = NAV_ITEMS.map(item => {
        const active = item.id === activeId;
        const style = active ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100';
        // Com muitas páginas, o rótulo aparece só em telas largas; o ícone mantém title/aria-label.
        return `<a href="${item.href}" title="${item.label}" aria-label="${item.label}"
                   class="px-2 xl:px-3 py-2 rounded-md text-sm font-medium flex items-center gap-2 shrink-0 ${style}"
                   ${active ? 'aria-current="page"' : ''}><i class="fas ${item.icon}" aria-hidden="true"></i><span class="hidden xl:inline">${item.label}</span></a>`;
    }).join('');

    nav.className = 'bg-white border-b border-slate-200 px-4 sm:px-6 py-4 flex justify-between items-center sticky top-0 z-50 gap-4';
    nav.innerHTML = `
        <a href="/" class="flex items-center gap-2 shrink-0">
            <div class="bg-blue-600 p-2 rounded-lg"><i class="fas fa-hospital-user text-white text-xl"></i></div>
            <span class="text-2xl font-bold text-slate-800 tracking-tight">Health<span class="text-blue-600">OS</span></span>
        </a>
        <div class="flex items-center gap-1 overflow-x-auto min-w-0">
            ${links}
            <a href="/docs" target="_blank" rel="noopener" title="API Docs" class="bg-blue-600 text-white px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 shrink-0">
                <i class="fas fa-book-open" aria-hidden="true"></i><span class="hidden xl:inline">API Docs</span>
            </a>
        </div>
        <form id="nav-search" action="/app/busca" role="search" class="shrink-0 flex items-center">
            <label for="nav-search-input" class="sr-only">Buscar no sistema</label>
            <input id="nav-search-input" name="q" type="search" minlength="2" maxlength="80" placeholder="Buscar ( / )"
                class="hidden md:block w-36 lg:w-44 p-2 border rounded-lg text-sm">
            <a href="/app/busca" class="md:hidden px-2 py-2 text-slate-600" title="Buscar" aria-label="Buscar"><i class="fas fa-magnifying-glass" aria-hidden="true"></i></a>
        </form>
        <div id="nav-profile" class="shrink-0"></div>`;
    mountProfileControls(document.getElementById('nav-profile'));
    enableSearchShortcut();
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
