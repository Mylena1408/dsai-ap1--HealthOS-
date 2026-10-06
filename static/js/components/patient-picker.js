// Campo de busca de pacientes com sugestões (usa GET /api/v1/patients?q=).
import { apiCall } from '../core/api.js';
import { escapeHtml } from '../core/dom.js';

const MAX_SUGGESTIONS = 8;

/**
 * Transforma um <input> em seletor de paciente.
 * Retorna { get value(), clear() }; `onSelect(patient)` é chamado na escolha.
 */
export function createPatientPicker(input, { onSelect = () => {} } = {}) {
    const list = document.createElement('ul');
    list.className = 'absolute z-[150] mt-1 w-full bg-white border rounded-lg shadow-lg max-h-64 overflow-y-auto hidden';
    list.setAttribute('role', 'listbox');
    input.parentElement.classList.add('relative');
    input.after(list);
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('role', 'combobox');

    let selected = null;
    let items = [];
    let debounce;
    let lastQuery = null;

    async function search() {
        const query = input.value.trim();
        if (query === lastQuery) return;
        lastQuery = query;
        try {
            const page = await apiCall(`/patients?${new URLSearchParams({ q: query, limit: MAX_SUGGESTIONS })}`);
            if (query !== input.value.trim()) return;  // resposta antiga
            list.innerHTML = page.items.length
                ? page.items.map((p, i) => `
                    <li role="option" data-index="${i}" class="px-3 py-2 cursor-pointer hover:bg-blue-50 text-sm">
                        <div class="font-medium text-slate-800">${escapeHtml(p.full_name)}</div>
                        <div class="text-xs text-slate-500">${p.age} anos · CPF ${escapeHtml(p.cpf)}</div>
                    </li>`).join('')
                : '<li class="px-3 py-2 text-sm text-slate-500">Nenhum paciente encontrado.</li>';
            items = page.items;
            list.classList.remove('hidden');
        } catch (err) {
            list.innerHTML = `<li class="px-3 py-2 text-sm text-red-600">${escapeHtml(err.message)}</li>`;
            list.classList.remove('hidden');
        }
    }

    input.addEventListener('input', () => {
        selected = null;
        clearTimeout(debounce);
        debounce = setTimeout(search, 250);
    });
    input.addEventListener('focus', () => { lastQuery = null; search(); });
    list.addEventListener('mousedown', event => {
        const option = event.target.closest('[data-index]');
        if (!option) return;
        selected = items[Number(option.dataset.index)];
        input.value = selected.full_name;
        list.classList.add('hidden');
        onSelect(selected);
    });
    input.addEventListener('blur', () => setTimeout(() => list.classList.add('hidden'), 150));

    return {
        get value() { return selected; },
        clear() { selected = null; input.value = ''; lastQuery = null; },
    };
}
