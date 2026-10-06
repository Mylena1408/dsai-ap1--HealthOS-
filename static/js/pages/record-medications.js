// Aba "Medicamentos" do prontuário: medicamentos em uso/suspensos e nova prescrição.
import { apiCall } from '../core/api.js';
import { escapeHtml, formatDate, formatDateTime, toast } from '../core/dom.js';
import { ITEM_STATUS, PRESCRIPTION_STATUS, ROUTES, badge, fillSelect } from '../core/labels.js';

const $ = id => document.getElementById(id);
const card = (title, body) => `<div class="glass-card rounded-2xl p-5"><h3 class="font-bold text-slate-800 mb-3">${title}</h3>${body}</div>`;
const fmt = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 2 });

function itemRow(index, medications) {
    return `<div class="grid grid-cols-2 sm:grid-cols-6 gap-2 items-end border rounded-lg p-2" data-item="${index}">
        <label class="text-xs text-slate-600 col-span-2">Medicamento<select data-field="medication_id" required class="w-full p-2 border rounded-lg mt-1">
            <option value="">Selecione</option>${medications}</select></label>
        <label class="text-xs text-slate-600">Dose<input data-field="dose" required value="1 comprimido" class="w-full p-2 border rounded-lg mt-1"></label>
        <label class="text-xs text-slate-600">Frequência<input data-field="frequency" required value="de 8 em 8 horas" class="w-full p-2 border rounded-lg mt-1"></label>
        <label class="text-xs text-slate-600">Dias<input data-field="duration_days" type="number" min="1" max="365" required value="7" class="w-full p-2 border rounded-lg mt-1"></label>
        <label class="text-xs text-slate-600">Quantidade<input data-field="quantity" type="number" min="1" step="any" required value="21" class="w-full p-2 border rounded-lg mt-1"></label>
    </div>`;
}

export async function renderMedicationsTab(container, { patientId, onChange }) {
    const [medications, prescriptions, stock, doctors] = await Promise.all([
        apiCall(`/patients/${patientId}/medications`),
        apiCall(`/prescriptions?patient_id=${patientId}&limit=20`),
        apiCall('/medications/stock'),
        apiCall('/professionals?professional_type=MEDICO&status=ATIVO&limit=100'),
    ]);
    const grouped = { EM_USO: [], SUSPENSO: [], CONCLUIDO: [] };
    medications.forEach(m => grouped[m.status].push(m));
    const medicationOptions = stock.filter(s => s.catalog_status === 'ATIVO')
        .map(s => `<option value="${escapeHtml(s.medication_id)}">${escapeHtml(`${s.name} ${s.dosage}`)}${s.is_controlled ? ' (controlado)' : ''}</option>`).join('');

    const list = items => items.length ? `<ul class="divide-y">${items.map(m => `
        <li class="py-2 flex flex-wrap justify-between items-center gap-2 text-sm">
            <span><strong>${escapeHtml(m.medication_name || '')}</strong> · ${escapeHtml(m.dose)}, ${escapeHtml(m.frequency)}
                · ${escapeHtml(ROUTES[m.route] || m.route)}
                <span class="text-slate-500">· prescrito em ${formatDate(m.issued_at)}${m.prescriber_name ? ` por ${escapeHtml(m.prescriber_name)}` : ''}
                · dispensado ${fmt(m.dispensed_quantity)}/${fmt(m.quantity)}</span>
                ${m.status_reason ? `<div class="text-xs text-slate-500">Motivo: ${escapeHtml(m.status_reason)}</div>` : ''}</span>
            <span class="flex gap-2 items-center">${badge(ITEM_STATUS, m.status)}
                ${m.status === 'EM_USO' ? `<button data-med-act="suspend" data-rx="${m.prescription_id}" data-item="${m.item_id}" class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">Suspender</button>
                    <button data-med-act="complete" data-rx="${m.prescription_id}" data-item="${m.item_id}" class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">Concluir</button>` : ''}
                ${m.status === 'SUSPENSO' ? `<button data-med-act="resume" data-rx="${m.prescription_id}" data-item="${m.item_id}" class="px-2 py-1 rounded-lg border text-xs font-semibold hover:bg-slate-100">Retomar</button>` : ''}
            </span></li>`).join('')}</ul>` : '<p class="text-sm text-slate-500">Nenhum.</p>';

    container.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${card(`Em uso <span class="text-sm font-normal text-slate-500">(${grouped.EM_USO.length})</span>`, list(grouped.EM_USO))}
            ${card(`Suspensos <span class="text-sm font-normal text-slate-500">(${grouped.SUSPENSO.length})</span>`, list(grouped.SUSPENSO))}
        </div>
        ${card('Prescrições', prescriptions.items.length ? `<ul class="divide-y">${prescriptions.items.map(p => `
            <li class="py-2 text-sm flex flex-wrap justify-between gap-2">
                <span>${formatDateTime(p.issued_at)} · ${escapeHtml(p.prescriber_name || '')} · ${p.items.length} item(ns)
                    ${p.special_control ? '<span class="text-xs font-semibold text-purple-700 ml-1">Controle especial</span>' : ''}
                    <span class="text-xs text-slate-500">· válida até ${formatDate(p.valid_until)}</span></span>
                <span class="flex gap-2 items-center">${p.is_expired && ['ATIVA', 'PARCIALMENTE_DISPENSADA'].includes(p.status) ? '<span class="text-xs text-red-700">Vencida</span>' : ''}${badge(PRESCRIPTION_STATUS, p.status)}</span>
            </li>`).join('')}</ul>` : '<p class="text-sm text-slate-500">Nenhuma prescrição.</p>')}
        ${card('Nova prescrição', `
            <form id="form-rx" class="space-y-3">
                <label class="text-sm text-slate-600 block">Médico(a) prescritor(a)<select id="rx-doctor" required class="w-full p-2 border rounded-lg mt-1"></select></label>
                <div id="rx-items" class="space-y-2">${itemRow(0, medicationOptions)}</div>
                <button type="button" id="rx-add" class="text-sm text-blue-700 font-semibold"><i class="fas fa-plus"></i> Adicionar item</button>
                <div id="rx-override" class="hidden">
                    <label class="text-sm text-red-700 block">Alergia registrada — justificativa obrigatória para prosseguir
                        <textarea id="rx-override-reason" minlength="10" maxlength="500" class="w-full p-2 border border-red-300 rounded-lg mt-1 h-20"></textarea></label>
                </div>
                <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700">Prescrever</button>
            </form>`)}`;

    fillSelect($('rx-doctor'), Object.fromEntries(doctors.items.map(d => [d.id, d.full_name])), 'Selecione');
    let rows = 1;
    $('rx-add').addEventListener('click', () => $('rx-items').insertAdjacentHTML('beforeend', itemRow(rows++, medicationOptions)));

    $('form-rx').addEventListener('submit', async event => {
        event.preventDefault();
        const items = [...document.querySelectorAll('#rx-items [data-item]')].map(row => {
            const value = field => row.querySelector(`[data-field="${field}"]`).value;
            return { medication_id: value('medication_id'), dose: value('dose'), frequency: value('frequency'),
                     duration_days: Number(value('duration_days')), quantity: Number(value('quantity')) };
        });
        try {
            await apiCall('/prescriptions', 'POST', {
                patient_id: patientId, prescriber_id: $('rx-doctor').value, items,
                allergy_override_reason: $('rx-override-reason').value.trim() || null,
            });
            await onChange('Prescrição emitida.');
        } catch (err) {
            if (err.message.startsWith('Alergia registrada')) $('rx-override').classList.remove('hidden');
            toast(err.message, 'error');
        }
    });

    container.querySelectorAll('[data-med-act]').forEach(button => button.addEventListener('click', async () => {
        const action = button.dataset.medAct;
        let body = null;
        if (action === 'suspend') {
            const reason = window.prompt('Motivo da suspensão:');
            if (!reason) return;
            body = { reason };
        }
        try {
            await apiCall(`/prescriptions/${button.dataset.rx}/items/${button.dataset.item}/${action}`, 'POST', body);
            await onChange('Medicamento atualizado.');
        } catch (err) {
            toast(err.message, 'error');
        }
    }));
}
