// Barra de navegação compartilhada. Cada novo módulo com página própria
// acrescenta uma entrada em NAV_ITEMS.
const NAV_ITEMS = [
    { id: 'portal', label: 'Portal', href: '/', icon: 'fa-house-medical' },
    { id: 'status', label: 'Status', href: '/app/status', icon: 'fa-heart-pulse' },
];

export function renderNav(activeId) {
    const nav = document.getElementById('app-nav');
    if (!nav) return;

    const links = NAV_ITEMS.map(item => {
        const active = item.id === activeId;
        const style = active ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100';
        return `<a href="${item.href}" class="px-3 py-2 rounded-md text-sm font-medium flex items-center gap-2 ${style}"
                   ${active ? 'aria-current="page"' : ''}><i class="fas ${item.icon}"></i><span class="hidden sm:inline">${item.label}</span></a>`;
    }).join('');

    nav.className = 'bg-white border-b border-slate-200 px-4 sm:px-6 py-4 flex justify-between items-center sticky top-0 z-50 gap-4';
    nav.innerHTML = `
        <a href="/" class="flex items-center gap-2 shrink-0">
            <div class="bg-blue-600 p-2 rounded-lg"><i class="fas fa-hospital-user text-white text-xl"></i></div>
            <span class="text-2xl font-bold text-slate-800 tracking-tight">Health<span class="text-blue-600">OS</span></span>
        </a>
        <div class="flex items-center gap-1 sm:gap-2 overflow-x-auto">
            ${links}
            <a href="/docs" target="_blank" rel="noopener" class="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2">
                <i class="fas fa-book-open"></i><span class="hidden sm:inline">API Docs</span>
            </a>
        </div>`;
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
