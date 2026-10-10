// Fluxo de interface das visões Enfermagem e Psicologia do portal (spec
// 2026-10-10-portal-enfermagem-psicologia), em DOM simulado contra a API real.
//
// Pré-requisitos: servidor com dados de demonstração em banco descartável (o teste grava sinais
// vitais, procedimento, evoluções, sessão e condição). Uso: npm run flow
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
    console.log(`${ok ? "OK   " : "FALHA"} ${label.padEnd(56)} ${detail}`);
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

async function openPortal(profile) {
    const html = readFileSync(path.join(ROOT, "index.html"), "utf-8").replace(/<script[^>]*src="[^"]*"[^>]*><\/script>/g, "");
    const env = installDom(html, { url: `${BASE}/` });
    globalThis.fetch = env.window.fetch = (input, init) => nodeFetch(new URL(input, BASE), init);
    process.removeAllListeners("unhandledRejection");
    process.on("unhandledRejection", e => env.errors.push(`promise: ${e?.message || e}`));
    env.window.localStorage.setItem("healthos.profile", JSON.stringify(profile));
    const href = pathToFileURL(path.join(ROOT, "static", "js", "pages", "portal.js")).href;
    await import(`${href}?instance=${instance++}`);
    return { ...env, text: () => env.document.body.textContent.replace(/\s+/g, " ") };
}

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
const message = (page, id) => page.document.getElementById(id).innerText || "";
const localDateTime = date => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
const asProfile = p => ({ audience: "PROFISSIONAL", recipient_id: p.id, label: p.full_name, professional_type: p.professional_type });

try {
    await nodeFetch(`${BASE}/health`);
} catch {
    console.error(`Servidor indisponível em ${BASE}. Suba a aplicação antes de rodar este teste.`);
    process.exit(2);
}

const patient = (await api("/patients?limit=1")).items[0];
const nurse = (await api("/professionals?professional_type=ENFERMEIRO&status=ATIVO&limit=1")).items[0];
const psychologists = (await api("/professionals?professional_type=PSICOLOGO&status=ATIVO&limit=10")).items;
if (!patient || !nurse || !psychologists.length) {
    console.error("Sem paciente, enfermeiro ou psicólogo: suba o servidor com SEED_DEMO_DATA=True.");
    process.exit(2);
}
const stamp = Date.now();

// ------------------------------------------------------------------ Enfermagem
const nursing = await openPortal(asProfile(nurse));
const doc = nursing.document;
const opened = await waitFor(() => !doc.getElementById("grid-nursing").classList.contains("hidden")
                                   && doc.getElementById("n-author").value === nurse.id);
check("enfermagem › perfil abre a visão e sugere o profissional", Boolean(opened)
      && doc.getElementById("btn-view-nursing").getAttribute("aria-pressed") === "true");
check("enfermagem › paciente escolhido pelo nome", await pickPatient(nursing, "n-patient", patient), patient.full_name);
const day = await waitFor(() => doc.getElementById("n-day").children.length > 0);
check("enfermagem › pacientes do dia carregados", Boolean(day) && !doc.getElementById("n-day").textContent.includes("Erro"));

doc.getElementById("n-spo2").value = "97";
doc.getElementById("n-hr").value = "82";
doc.getElementById("form-n-vitals").requestSubmit();
await waitFor(() => message(nursing, "res-n-vitals").includes("Medição registrada"));
const vitals = (await api(`/patients/${patient.id}/vital-signs?limit=1`)).items[0];
check("enfermagem › sinais vitais gravados com o autor", vitals?.professional_id === nurse.id && vitals?.oxygen_saturation === 97,
      message(nursing, "res-n-vitals"));

const procedureName = `Curativo simples (teste ${stamp})`;
doc.getElementById("n-procedure-name").value = procedureName;
doc.getElementById("n-procedure-date").value = localDateTime(new Date(Date.now() - 3600000));
doc.getElementById("form-n-procedure").requestSubmit();
await waitFor(() => message(nursing, "res-n-procedure").includes("Procedimento registrado"));
const procedure = (await api(`/patients/${patient.id}/procedures`)).find(p => p.name === procedureName);
check("enfermagem › procedimento gravado com o autor", procedure?.professional_id === nurse.id, message(nursing, "res-n-procedure"));

const nursingNote = `Evolução de enfermagem ${stamp}: paciente fictício estável.`;
doc.getElementById("n-evolution-content").value = nursingNote;
doc.getElementById("form-n-evolution").requestSubmit();
await waitFor(() => message(nursing, "res-n-evolution").includes("rascunho"));
const nursingEvolution = (await api(`/patients/${patient.id}/evolutions`)).find(e => e.content === nursingNote);
check("enfermagem › evolução de enfermagem em rascunho", nursingEvolution?.professional_type === "ENFERMEIRO"
      && nursingEvolution?.status === "RASCUNHO");

doc.querySelector('[data-care-action="nursing-meds"]').click();
const meds = await waitFor(() => doc.getElementById("n-meds").children.length > 0);
check("enfermagem › medicamentos em uso consultados", Boolean(meds) && !doc.getElementById("n-meds").textContent.includes("Erro"));
const audit = new Set((await api(`/audit-events?patient_id=${patient.id}&limit=200`)).items.map(e => e.event_type));
check("enfermagem › auditoria e linha do tempo", audit.has("SINAIS_VITAIS_REGISTRADOS")
      && (await api(`/patients/${patient.id}/timeline?types=PROCEDIMENTO&limit=200`)).items.some(e => e.title.includes(procedureName)));
check("enfermagem › sem erros de execução", !nursing.errors.length, nursing.errors.join(" | "));

// ------------------------------------------------------------------- Psicologia
// Psicólogo com sessão que já pode ser iniciada (até 30 min antes), se houver; senão o primeiro.
let startable = null;
for (const psy of psychologists) {
    const page = await api(`/appointments?professional_id=${psy.id}&limit=100`);
    startable = page.items.find(a => a.allowed_transitions.includes("EM_ANDAMENTO"));
    if (startable) break;
}
const psychologist = psychologists.find(p => p.id === startable?.professional_id) || psychologists[0];
const psy = await openPortal(asProfile(psychologist));
const pdoc = psy.document;
const psyOpened = await waitFor(() => !pdoc.getElementById("grid-psychology").classList.contains("hidden")
                                      && pdoc.getElementById("ps-professional").value === psychologist.id);
check("psicologia › perfil abre a visão e sugere o profissional", Boolean(psyOpened));
check("psicologia › aviso didático de sigilo, sem bloqueio", psy.text().includes("Registro didático")
      && !pdoc.querySelector('#grid-psychology input[type="password"]'));
check("psicologia › paciente escolhido pelo nome", await pickPatient(psy, "ps-patient", patient));

const slot = await waitFor(() => pdoc.querySelector("#ps-slot option[value]:not([value=''])"));
// D14: nenhum horário oferecido coincide com consulta ativa do paciente (o servidor recusaria).
const busy = (await api(`/appointments?patient_id=${patient.id}&status=AGENDADA&status=CONFIRMADA&status=EM_ANDAMENTO&limit=200`)).items
    .map(a => [new Date(a.start_time).getTime(), new Date(a.end_time).getTime()]);
const offered = [...pdoc.querySelectorAll("#ps-slot option[value]:not([value=''])")].map(o => new Date(o.value).getTime());
check("psicologia › horários oferecidos sem conflito com o paciente",
      offered.every(t => !busy.some(([start, end]) => t >= start && t < end)), `${offered.length} horário(s), ${busy.length} consulta(s) do paciente`);
if (slot) {
    pdoc.getElementById("ps-slot").value = slot.value;
    pdoc.getElementById("ps-type").value = "TELECONSULTA";
    pdoc.getElementById("ps-reason").value = `Sessão de teste ${stamp}`;
    pdoc.getElementById("form-ps-schedule").requestSubmit();
    await waitFor(() => message(psy, "res-ps-schedule").includes("Sessão agendada"));
    const session = (await api(`/appointments?patient_id=${patient.id}&professional_id=${psychologist.id}&limit=100`)).items
        .find(a => a.reason === `Sessão de teste ${stamp}`);
    check("psicologia › sessão agendada (teleconsulta)", session?.appointment_type === "TELECONSULTA", message(psy, "res-ps-schedule"));
    const inAgenda = await waitFor(() => pdoc.getElementById("ps-agenda").textContent.includes(`Sessão de teste ${stamp}`));
    check("psicologia › sessão aparece na agenda", Boolean(inAgenda));
} else {
    console.log("PULADO psicologia › agendar: sem horário livre em 7 dias");
}

if (startable) {
    const row = await waitFor(() => pdoc.querySelector(`[data-appointment="${startable.id}"] [data-appointment-action="start"]`));
    row?.click();
    const started = await waitFor(async () => (await api(`/appointments/${startable.id}`)).status === "EM_ANDAMENTO");
    const complete = await waitFor(() => pdoc.querySelector(`[data-appointment="${startable.id}"] [data-appointment-action="complete"]`));
    complete?.click();
    const done = await waitFor(async () => (await api(`/appointments/${startable.id}`)).status === "FINALIZADA");
    const unbilled = await api(`/billing/patients/${startable.patient_id}/unbilled`);
    check("psicologia › iniciar e finalizar sessão pela agenda", Boolean(started) && Boolean(done));
    check("psicologia › sessão finalizada vai para 'não faturado'", unbilled.some(u => u.source_id === startable.id));
} else {
    console.log("PULADO psicologia › iniciar/finalizar: nenhuma sessão na janela de início");
}

const psyNote = `Evolução da sessão ${stamp}: paciente fictício colaborativo.`;
pdoc.getElementById("ps-evolution-content").value = psyNote;
pdoc.getElementById("form-ps-evolution").requestSubmit();
const draft = await waitFor(async () => (await api(`/patients/${patient.id}/evolutions`)).find(e => e.content === psyNote));
psy.window.confirm = () => true;
const sign = draft && await waitFor(() => pdoc.querySelector(`[data-evolution="${draft.id}"] [data-evolution-sign]`));
sign?.click();
const signed = draft && await waitFor(async () => (await api(`/patients/${patient.id}/evolutions`)).find(e => e.id === draft.id)?.status === "ASSINADA");
check("psicologia › evolução registrada e assinada", draft?.professional_type === "PSICOLOGO" && Boolean(signed));
const timeline = await api(`/patients/${patient.id}/timeline?types=EVOLUCAO&limit=200`);
check("psicologia › evolução na linha do tempo", draft && timeline.items.some(e => e.source_id === draft.id));

const conditionName = `Ansiedade (fictícia ${stamp})`;
pdoc.getElementById("ps-condition-name").value = conditionName;
pdoc.getElementById("form-ps-condition").requestSubmit();
await waitFor(() => message(psy, "res-ps-condition").includes("Condição registrada"));
const condition = (await api(`/patients/${patient.id}/conditions`)).find(c => c.name === conditionName);
check("psicologia › queixa registrada no prontuário", Boolean(condition));
const history = await waitFor(() => pdoc.getElementById("ps-history").textContent.includes(conditionName));
check("psicologia › histórico mostra evolução e condição", Boolean(history) && pdoc.getElementById("ps-history").textContent.includes(psyNote));
check("psicologia › sem erros de execução", !psy.errors.length, psy.errors.join(" | "));

console.log(failures ? `RESULTADO: ${failures} problema(s)` : "RESULTADO: visões de enfermagem e psicologia OK");
process.exit(failures ? 1 : 0);
