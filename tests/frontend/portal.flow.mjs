// Fluxo de interface da Fase 6 e das correções L1/L5 em DOM simulado contra a API real: portal sem
// IDs digitados, agenda nas consultas novas, alertas do portal visíveis no prontuário e no painel,
// sem alert(), e visão Administração financeira.
//
// Pré-requisitos: servidor com dados de demonstração em banco descartável (o teste grava um
// agendamento, uma nota/evolução e um alerta). Uso: npm run flow   (HEALTHOS_URL altera o endereço)
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { installDom } from "./dom.mjs";

const BASE = process.env.HEALTHOS_URL || "http://127.0.0.1:8000";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const nodeFetch = globalThis.fetch;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const api = async p => (await nodeFetch(`${BASE}/api/v1${p}`)).json();
let failures = 0;
let instance = 0;

function check(label, ok, detail = "") {
    if (!ok) failures++;
    console.log(`${ok ? "OK   " : "FALHA"} ${label.padEnd(52)} ${detail}`);
}

async function waitFor(predicate, timeout = 10000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
        const value = await predicate();
        if (value) return value;
        await sleep(150);
    }
    return null;
}

async function openPage(file, url, profile) {
    const html = readFileSync(path.join(ROOT, file), "utf-8").replace(/<script[^>]*src="[^"]*"[^>]*><\/script>/g, "");
    const env = installDom(html, { url: BASE + url });
    globalThis.fetch = env.window.fetch = (input, init) => nodeFetch(new URL(input, BASE), init);
    process.removeAllListeners("unhandledRejection");
    process.on("unhandledRejection", e => env.errors.push(`promise: ${e?.message || e}`));
    if (profile) env.window.localStorage.setItem("healthos.profile", JSON.stringify(profile));
    return {
        ...env,
        text: () => env.document.body.textContent.replace(/\s+/g, " "),
        async load(module) {
            const href = pathToFileURL(path.join(ROOT, "static", "js", module)).href;
            await import(`${href}?instance=${instance++}`);
        },
    };
}

/** Digita no seletor e escolhe a opção do paciente, como faria a pessoa. */
async function pickPatient(page, inputId, patient) {
    const input = page.document.getElementById(inputId);
    input.focus();
    input.value = patient.full_name;
    input.dispatchEvent(new page.window.Event("input", { bubbles: true }));
    const option = await waitFor(() => [...page.document.querySelectorAll(`#${input.getAttribute("aria-controls")} [role="option"]`)]
        .find(li => li.textContent.includes(patient.full_name)));
    option?.dispatchEvent(new page.window.MouseEvent("mousedown", { bubbles: true }));
    return Boolean(option);
}

// showResult() usa innerText, que o jsdom guarda como propriedade sem gerar texto no documento.
const message = (page, id) => page.document.getElementById(id).innerText || page.document.getElementById(id).textContent || "";

try {
    await nodeFetch(`${BASE}/health`);
} catch {
    console.error(`Servidor indisponível em ${BASE}. Suba a aplicação antes de rodar este teste.`);
    process.exit(2);
}

const patient = (await api("/patients?limit=1")).items[0];
const doctor = (await api("/professionals?professional_type=MEDICO&status=ATIVO&limit=1")).items[0];
if (!patient || !doctor) {
    console.error("Sem paciente ou médico: suba o servidor com SEED_DEMO_DATA=True.");
    process.exit(2);
}

// --------------------------------------------- sem paciente escolhido (setor)
const empty = await openPage("index.html", "/", { audience: "SETOR", sector: "RECEPCAO", label: "Recepção" });
await empty.load("pages/portal.js");
empty.document.querySelector('[data-action="fetch-consultations"]').click();
const warned = await waitFor(() => message(empty, "res-consultas").includes("Escolha o paciente"));
check("portal › sem paciente, aviso no formulário", Boolean(warned));
check("portal › nenhum campo pede ID digitado",
      !empty.document.querySelector('input[placeholder*="ID"]') && empty.document.querySelectorAll("[data-portal-patient]").length === 8);

// ---------------------------------------------------- visão Paciente (busca)
const portal = await openPage("index.html", "/", { audience: "SETOR", sector: "RECEPCAO", label: "Recepção" });
await portal.load("pages/portal.js");
const doc = portal.document;
check("portal › paciente escolhido pelo nome", await pickPatient(portal, "p-consult-patient", patient), patient.full_name);
check("portal › escolha vale para todos os formulários",
      [...doc.querySelectorAll("[data-portal-patient]")].every(input => input.value === patient.full_name));

doc.querySelector('[data-action="fetch-consultations"]').click();
const consultations = await waitFor(() => {
    const div = doc.getElementById("res-consultas");
    return !div.className.includes("red") && div.children.length > 0 && div;
});
check("portal › Minhas consultas", Boolean(consultations), consultations ? `${consultations.children.length} item(ns)` : "sem resposta");

doc.querySelector('[data-action="fetch-billing"]').click();
const billing = await waitFor(() => {
    const div = doc.getElementById("res-fatura");
    return !div.className.includes("red") && div.children.length > 0 && div;
});
check("portal › Minhas faturas", Boolean(billing));

const auditTotal = async () => (await api(`/audit-events?patient_id=${patient.id}&event_type=CONSULTA_AGENDADA&limit=1`)).total;
const bookedBefore = await auditTotal();
const agendaDoctor = doc.getElementById("p-agenda-doctor");
let slotDoctor = null;
let slot = null;
for (const option of await waitFor(() => {
    const options = [...agendaDoctor.querySelectorAll("option[value]:not([value=''])")];
    return options.length && options;
})) {
    agendaDoctor.value = option.value;
    agendaDoctor.dispatchEvent(new portal.window.Event("change", { bubbles: true }));
    slot = await waitFor(() => doc.querySelector("#p-slot-id option[value]:not([value=''])"), 5000);
    if (slot) { slotDoctor = option.value; break; }
}
if (slot) {
    doc.getElementById("p-slot-id").value = slot.value;
    doc.getElementById("p-agenda-reason").value = "Retorno pelo portal";
    doc.getElementById("form-agenda").requestSubmit();
    const booked = await waitFor(() => message(portal, "res-agenda").includes("Sucesso"));
    const created = (await api(`/appointments?patient_id=${patient.id}&limit=100`)).items
        .find(a => a.professional_id === slotDoctor && new Date(a.start_time).getTime() === new Date(slot.value).getTime());
    check("agenda › reserva vira consulta nova (/appointments)", Boolean(booked) && Boolean(created), message(portal, "res-agenda"));
    check("agenda › auditoria CONSULTA_AGENDADA", await auditTotal() === bookedBefore + 1);
    const upcoming = (await api(`/dashboards/patient/${patient.id}`)).upcoming_appointments;
    check("agenda › aparece no painel do paciente", Boolean(created) && upcoming.some(a => a.id === created.id));
    doc.querySelector('[data-action="fetch-consultations"]').click();
    const listed = await waitFor(() => doc.getElementById("res-consultas").textContent.includes("Retorno pelo portal"));
    check("Minhas consultas › mostra a consulta nova", Boolean(listed));
} else {
    console.log("PULADO agenda: nenhum médico com horário livre em 7 dias");
}

// ------------------------------------------------------ visão Médico (nota)
doc.querySelector('[data-view="doctor"]').click();
const doctorOption = await waitFor(() => doc.querySelector(`#d-note-doctor option[value="${doctor.id}"]`));
check("portal › médico escolhido na lista", Boolean(doctorOption));
doc.getElementById("d-note-doctor").value = doctor.id;
const note = `Nota do portal sem IDs ${Date.now()}: paciente fictício estável.`;
doc.getElementById("d-note-content").value = note;
doc.getElementById("form-doc-new").requestSubmit();
await waitFor(() => message(portal, "res-doc-new").includes("Sucesso"));
const evolution = (await api(`/patients/${patient.id}/evolutions`)).find(e => e.content === note);
check("portal › nota com médico da lista vira evolução", evolution?.professional_id === doctor.id,
      evolution ? evolution.status : message(portal, "res-doc-new"));

doc.querySelector('[data-action="fetch-history"]').click();
const history = await waitFor(() => doc.getElementById("res-doc-history").textContent.includes(note));
check("portal › histórico mostra a nota", Boolean(history));

const description = `Alerta do portal ${Date.now()}`;
doc.getElementById("d-alert-msg").value = description;
doc.getElementById("form-doc-alerts").requestSubmit();
await waitFor(() => message(portal, "res-doc-alerts").includes("Sucesso"));
const alerts = await api(`/admin/alerts/patient/${patient.id}/active`);
check("portal › alerta criado para o paciente escolhido", alerts.some(a => a.description === description),
      message(portal, "res-doc-alerts"));
// L5: o alerta do portal aparece no resumo do prontuário e no painel do paciente.
const record = await openPage("static/pages/prontuario.html", `/app/prontuario?patient=${patient.id}`,
                              { audience: "SETOR", sector: "ADMINISTRACAO", label: "Administração" });
await record.load("pages/medical-record.js");
const inSummary = await waitFor(() => record.text().includes("Alertas do paciente") && record.text().includes(description));
check("alertas › alerta do portal no resumo do prontuário", Boolean(inSummary));
const patientBoard = await openPage("static/pages/painel.html", "/app/painel",
                                    { audience: "PACIENTE", recipient_id: patient.id, label: patient.full_name });
await patientBoard.load("pages/dashboard.js");
const inBoard = await waitFor(() => patientBoard.text().includes(description));
check("alertas › alerta do portal no painel do paciente", Boolean(inBoard));
check("alertas › prontuário e painel sem erros", !record.errors.length && !patientBoard.errors.length,
      [...record.errors, ...patientBoard.errors].join(" | "));
check("portal › sem alert() nem erros de execução", !portal.errors.length && !empty.errors.length,
      [...portal.errors, ...empty.errors].join(" | "));

// ---------------------------------------------------------------- perfis
const asPatient = await openPage("index.html", "/", { audience: "PACIENTE", recipient_id: patient.id, label: patient.full_name });
await asPatient.load("pages/portal.js");
const prefilled = await waitFor(() => asPatient.document.getElementById("p-bill-patient").value === patient.full_name);
check("perfil paciente › paciente já vem escolhido", Boolean(prefilled)
      && !asPatient.document.getElementById("grid-patient").classList.contains("hidden"));
check("perfil paciente › nada salvo além do perfil", asPatient.window.localStorage.getItem("healthos.patientId") === null);
// Trocar para um perfil que não é de paciente limpa a escolha (revisão de código, R2).
asPatient.window.localStorage.setItem("healthos.profile", JSON.stringify({
    audience: "PROFISSIONAL", recipient_id: doctor.id, label: doctor.full_name, professional_type: "MEDICO" }));
asPatient.window.dispatchEvent(new asPatient.window.CustomEvent("healthos:profile"));
const cleared = await waitFor(() => [...asPatient.document.querySelectorAll("[data-portal-patient]")].every(input => input.value === ""));
check("troca de perfil › paciente anterior deixa de estar escolhido", Boolean(cleared));

const asDoctor = await openPage("index.html", "/", {
    audience: "PROFISSIONAL", recipient_id: doctor.id, label: doctor.full_name, professional_type: "MEDICO" });
await asDoctor.load("pages/portal.js");
const doctorDefault = await waitFor(() => asDoctor.document.getElementById("d-note-doctor").value === doctor.id);
check("perfil médico › visão Médico e médico já escolhido", Boolean(doctorDefault)
      && !asDoctor.document.getElementById("grid-doctor").classList.contains("hidden"));

// ------------------------------------------------------- visão Administração
const board = await openPage("static/pages/painel.html", "/app/painel", { audience: "SETOR", sector: "ADMINISTRACAO", label: "Administração" });
await board.load("pages/dashboard.js");
const admin = await waitFor(() => board.text().includes("A receber"));
const summary = await api("/billing/summary");
check("administração › indicadores financeiros", Boolean(admin) && board.text().includes("Vencido")
      && board.text().includes(`${summary.overdue_count} fatura(s) em atraso`));
check("administração › atalhos", ["/app/consultas", "/app/financeiro", "/app/relatorios", "/app/profissionais"]
      .every(href => board.document.querySelector(`#board nav a[href="${href}"]`)));
check("administração › sem indicadores clínicos", !board.text().includes("Health Score") && !board.text().includes("Exames por situação"));
check("administração › sem erros de execução", !board.errors.length, board.errors.join(" | "));

console.log(failures ? `RESULTADO: ${failures} problema(s)` : "RESULTADO: fluxo do portal e da administração OK");
process.exit(failures ? 1 : 0);
