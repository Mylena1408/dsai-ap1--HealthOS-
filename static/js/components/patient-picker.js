// Campo de busca de pacientes com sugestões (usa GET /api/v1/patients?q=).
// Segue o padrão "combobox" da WAI-ARIA: setas percorrem as opções, Enter escolhe, Esc fecha.
import { apiCall } from '../core/api.js';
import { escapeHtml } from '../core/dom.js';

const MAX_SUGGESTIONS = 8;
let pickerCount = 0;

/**
 * Transforma um <input> em seletor de paciente.
 * Retorna { get value(), clear() }; `onSelect(patient)` é chamado na escolha.
 */
export function createPatientPicker(input, { onSelect = () => {} } = {}) {
    const listId = `patient-options-${++pickerCount}`;
    const list = document.createElement('ul');
    list.id = listId;
    list.className = 'absolute z-[150] mt-1 w-full bg-white border rounded-lg shadow-lg max-h-64 overflow-y-auto hidden';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', 'Pacientes encontrados');
    input.parentElement.classList.add('relative');
    input.after(list);
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', listId);
    input.setAttribute('aria-expanded', 'false');

    let selected = null;
    let items = [];
    let active = -1;
    let debounce;
    let lastQuery = null;

    function setOpen(open) {
        list.classList.toggle('hidden', !open);
        input.setAttribute('aria-expanded', String(open));
        if (!open) setActive(-1);
    }

    function setActive(index) {
        active = index;
        list.querySelectorAll('[role="option"]').forEach((option, i) => {
            option.setAttribute('aria-selected', String(i === index));
            option.classList.toggle('bg-blue-50', i === index);
        });
        if (index >= 0) {
            input.setAttribute('aria-activedescendant', `${listId}-${index}`);
            document.getElementById(`${listId}-${index}`)?.scrollIntoView?.({ block: 'nearest' });
        } else {
            input.removeAttribute('aria-activedescendant');
        }
    }

    function choose(index) {
        selected = items[index];
        if (!selected) return;
        input.value = selected.full_name;
        setOpen(false);
        onSelect(selected);
    }

    async function search() {
        const query = input.value.trim();
        if (query === lastQuery) return;
        lastQuery = query;
        try {
            const page = await apiCall(`/patients?${new URLSearchParams({ q: query, limit: MAX_SUGGESTIONS })}`);
            if (query !== input.value.trim()) return;  // resposta antiga
            items = page.items;
            list.innerHTML = items.length
                ? items.map((p, i) => `
                    <li role="option" id="${listId}-${i}" data-index="${i}" aria-selected="false"
                        class="px-3 py-2 cursor-pointer hover:bg-blue-50 text-sm">
                        <div class="font-medium text-slate-800">${escapeHtml(p.full_name)}</div>
                        <div class="text-xs text-slate-600">${p.age} anos · CPF ${escapeHtml(p.cpf)}</div>
                    </li>`).join('')
                : '<li class="px-3 py-2 text-sm text-slate-600">Nenhum paciente encontrado.</li>';
            setOpen(true);
        } catch (err) {
            items = [];
            list.innerHTML = `<li class="px-3 py-2 text-sm text-red-700">${escapeHtml(err.message)}</li>`;
            setOpen(true);
        }
    }

    input.addEventListener('input', () => {
        selected = null;
        clearTimeout(debounce);
        debounce = setTimeout(search, 250);
    });
    input.addEventListener('focus', () => { lastQuery = null; search(); });
    input.addEventListener('keydown', event => {
        const open = input.getAttribute('aria-expanded') === 'true';
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            if (!open) { lastQuery = null; search(); return; }
            if (!items.length) return;
            const step = event.key === 'ArrowDown' ? 1 : -1;
            setActive((active + step + items.length) % items.length);
        } else if (event.key === 'Enter' && open && active >= 0) {
            event.preventDefault();  // não envia o formulário em volta
            choose(active);
        } else if (event.key === 'Escape' && open) {
            event.preventDefault();
            setOpen(false);
        }
    });
    list.addEventListener('mousedown', event => {
        const option = event.target.closest('[data-index]');
        if (option) choose(Number(option.dataset.index));
    });
    input.addEventListener('blur', () => setTimeout(() => setOpen(false), 150));

    return {
        get value() { return selected; },
        clear() { selected = null; input.value = ''; lastQuery = null; },
    };
}
