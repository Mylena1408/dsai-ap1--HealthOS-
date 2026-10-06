// Controles de paginação para respostas no formato Page {items, total, limit, offset}.

export function renderPagination(container, page, onChange) {
    const { total, limit, offset } = page;
    const current = Math.floor(offset / limit) + 1;
    const pages = Math.max(1, Math.ceil(total / limit));
    const first = total ? offset + 1 : 0;
    const last = Math.min(offset + limit, total);

    container.innerHTML = `
        <span class="text-sm text-slate-500">${first}–${last} de ${total}</span>
        <div class="flex gap-2">
            <button type="button" data-page="prev" class="px-3 py-1 rounded-lg border text-sm disabled:opacity-40" ${current <= 1 ? 'disabled' : ''}>
                <i class="fas fa-chevron-left"></i><span class="sr-only">Anterior</span></button>
            <span class="text-sm text-slate-600 self-center">Página ${current} de ${pages}</span>
            <button type="button" data-page="next" class="px-3 py-1 rounded-lg border text-sm disabled:opacity-40" ${current >= pages ? 'disabled' : ''}>
                <i class="fas fa-chevron-right"></i><span class="sr-only">Próxima</span></button>
        </div>`;
    container.className = 'flex flex-wrap items-center justify-between gap-3 mt-4';
    container.querySelector('[data-page="prev"]').onclick = () => onChange(Math.max(0, offset - limit));
    container.querySelector('[data-page="next"]').onclick = () => onChange(offset + limit);
}
