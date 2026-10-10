// Fluxos de interface das Fases 3 e 4 em DOM simulado contra a API real: cria, edita e assina uma
// evolução pela aba "Evolução", confere a linha do tempo, a área "Médicos disponíveis" do
// Painel, o aviso de prescrição para quem não é médico e a visão "Enfermagem" do Painel.
//
// Pré-requisitos: servidor com dados de demonstração em banco descartável (o teste grava uma
// evolução), por exemplo SEED_DEMO_DATA=True e DATABASE_URL apontando para um arquivo temporário.
// Uso: npm run flow   (HEALTHOS_URL altera o endereço; padrão http://127.0.0.1:8000)
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
    console.log(`${ok ? "OK   " : "FALHA"} ${label.padEnd(48)} ${detail}`);
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
    env.window.localStorage.setItem("healthos.profile", JSON.stringify(profile));
    return {
        ...env,
        text: () => env.document.body.textContent.replace(/\s+/g, " "),
        async load(module) {
            const href = pathToFileURL(path.join(ROOT, "static", "js", module)).href;
            await import(`${href}?instance=${instance++}`);
        },
    };
}

try {
    await nodeFetch(`${BASE}/health`);
} catch {
    console.error(`Servidor indisponível em ${BASE}. Suba a aplicação antes de rodar este teste.`);
    process.exit(2);
}

const doctor = (await api("/professionals?professional_type=MEDICO&status=ATIVO&limit=1")).items[0];
const nurse = (await api("/professionals?professional_type=ENFERMEIRO&status=ATIVO&limit=1")).items[0];
const patient = (await api("/patients?limit=1")).items[0];
if (!doctor || !nurse || !patient) {
    console.error("Sem médico, enfermeiro ou paciente: suba o servidor com SEED_DEMO_DATA=True.");
    process.exit(2);
}
const asProfile = p => ({ audience: "PROFISSIONAL", recipient_id: p.id, label: p.full_name, professional_type: p.professional_type });
const marker = `Evolução de teste de interface ${Date.now()}`;
const evolutionsOf = () => api(`/patients/${patient.id}/evolutions`);
const mine = async () => (await evolutionsOf()).find(e => e.content.startsWith(marker));

// ------------------------------------------------- aba Evolução (perfil médico)
const record = await openPage("static/pages/prontuario.html", `/app/prontuario?patient=${patient.id}`, asProfile(doctor));
await record.load("pages/medical-record.js");
const doc = record.document;
const tab = await waitFor(() => doc.querySelector('[data-tab="evolucao"]'));
tab?.click();
const select = await waitFor(() => doc.querySelector("#evo-professional option[value]:not([value=''])") && doc.getElementById("evo-professional"));
check("evolução › médico do perfil já vem escolhido", select?.value === doctor.id, select?.value || "sem seletor");

doc.getElementById("evo-content").value = `${marker}: paciente fictício estável.`;
doc.getElementById("form-evolution").requestSubmit();
const draft = await waitFor(mine);
check("evolução › rascunho criado pela interface", draft?.status === "RASCUNHO" && draft?.professional_id === doctor.id,
      draft ? `${draft.status}, versão ${draft.version}` : "não gravou");

const item = draft && await waitFor(() => doc.querySelector(`[data-evolution="${draft.id}"] [data-evo-act="edit"]`));
item?.click();
const editor = draft && await waitFor(() => doc.getElementById(`evo-edit-${draft.id}`));
if (editor) {
    editor.value = `${marker}: paciente fictício estável, sem queixas.`;
    editor.closest("form").requestSubmit();
}
const edited = await waitFor(async () => (await mine())?.version === 2 && mine());
check("evolução › rascunho editado (versão 2)", Boolean(edited), edited ? edited.content.slice(marker.length) : "não editou");

record.window.confirm = () => true;
const sign = draft && await waitFor(() => doc.querySelector(`[data-evolution="${draft.id}"] [data-evo-act="sign"]`));
sign?.click();
const signed = await waitFor(async () => (await mine())?.status === "ASSINADA" && mine());
check("evolução › assinada com confirmação", Boolean(signed), signed ? `assinada em ${signed.signed_at}` : "não assinou");
const locked = await waitFor(() => {
    const row = doc.querySelector(`[data-evolution="${draft?.id}"]`);
    return row && !row.querySelector("[data-evo-act]") && row.textContent.includes("Assinada");
});
check("evolução › assinada não mostra Editar/Assinar", Boolean(locked));

doc.querySelector('[data-tab="timeline"]')?.click();
const inTimeline = await waitFor(() => record.text().includes(`Evolução clínica — ${doctor.full_name}`));
check("linha do tempo › mostra a evolução", Boolean(inTimeline));
check("prontuário (médico) › sem erros de execução", !record.errors.length, record.errors.join(" | "));

// ------------------------------------------- Painel › Profissional (médico)
const board = await openPage("static/pages/painel.html", "/app/painel", asProfile(doctor));
let copied = null;
Object.defineProperty(board.window.navigator, "clipboard", {
    value: { writeText: async text => { copied = text; } }, configurable: true,
});
// O Node 18 não tem `navigator` global; no navegador, ele é o da janela.
Object.defineProperty(globalThis, "navigator", { value: board.window.navigator, configurable: true });
await board.load("pages/dashboard.js");
const copyButton = await waitFor(() => board.document.querySelector(`[data-copy-id="${doctor.id}"]`));
check("painel › área 'Médicos disponíveis' com o ID", Boolean(copyButton) && board.text().includes("Médicos disponíveis"));
copyButton?.click();
// toast() usa innerText, que o jsdom guarda como propriedade sem gerar texto no documento.
const toast = await waitFor(() => [...board.document.querySelectorAll("#toast-container [role='status']")]
    .some(item => item.innerText === "ID copiado."));
check("painel › Copiar ID copia o ID certo", Boolean(toast) && copied === doctor.id, copied || "nada copiado");
check("painel (médico) › sem erros de execução", !board.errors.length, board.errors.join(" | "));

// --------------------------------------- perfil de enfermagem (não é médico)
const nurseBoard = await openPage("static/pages/painel.html", "/app/painel", asProfile(nurse));
await nurseBoard.load("pages/dashboard.js");
const nursingView = await waitFor(() => nurseBoard.text().includes("Pacientes do dia"));
const selectedTab = nurseBoard.document.querySelector('[data-view="nursing"]')?.getAttribute("aria-selected");
check("painel (enfermagem) › abre na visão Enfermagem", Boolean(nursingView) && selectedTab === "true");
const tiles = ["Consultas hoje", "Sinais vitais críticos", "Prescrições ativas", "Avisos não lidos"];
check("painel (enfermagem) › quatro indicadores", tiles.every(label => nurseBoard.text().includes(label)));
const patientIds = new Set((await api("/patients?limit=100")).items.map(p => p.id));
const links = [...nurseBoard.document.querySelectorAll('#board a[href^="/app/prontuario?patient="]')];
const linked = links.map(a => new URL(a.href).searchParams.get("patient"));
check("painel (enfermagem) › links levam a prontuários existentes",
      links.length > 0 && linked.every(id => patientIds.has(id)), `${links.length} link(s)`);
check("painel (enfermagem) › sem a área de IDs dos médicos", !nurseBoard.text().includes("Médicos disponíveis"));

const nurseRecord = await openPage("static/pages/prontuario.html", `/app/prontuario?patient=${patient.id}`, asProfile(nurse));
await nurseRecord.load("pages/medical-record.js");
(await waitFor(() => nurseRecord.document.querySelector('[data-tab="medicamentos"]')))?.click();
const notice = await waitFor(() => nurseRecord.text().includes("Apenas médicos(as) prescrevem"));
check("medicamentos (enfermagem) › aviso de prescrição", Boolean(notice));
(await waitFor(() => nurseRecord.document.querySelector('[data-tab="sinais"]')))?.click();
const author = await waitFor(() => nurseRecord.document.querySelector("#v-author option[value]:not([value=''])")
                                   && nurseRecord.document.getElementById("v-author"));
check("sinais vitais › 'Registrado por' sugere o perfil", author?.value === nurse.id, author?.value || "sem seletor");
check("enfermagem › sem erros de execução", !nurseBoard.errors.length && !nurseRecord.errors.length,
      [...nurseBoard.errors, ...nurseRecord.errors].join(" | "));

console.log(failures ? `RESULTADO: ${failures} problema(s)` : "RESULTADO: fluxo da evolução e área do médico OK");
process.exit(failures ? 1 : 0);
