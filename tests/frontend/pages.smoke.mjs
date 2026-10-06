// Teste de fumaça das páginas: executa cada página em DOM simulado contra a API real,
// percorre as abas do prontuário e as visões do painel e relata erros de execução.
//
// Pré-requisitos: servidor rodando com dados de demonstração, por exemplo
//   python -m scripts.seed_demo && uvicorn main:app
// Uso: npm run smoke   (HEALTHOS_URL altera o endereço; padrão http://127.0.0.1:8000)
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { installDom } from "./dom.mjs";

const BASE = process.env.HEALTHOS_URL || "http://127.0.0.1:8000";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const nodeFetch = globalThis.fetch;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let failures = 0;
let instance = 0;

async function openPage(file, url, setup = () => {}) {
    const html = readFileSync(path.join(ROOT, file), "utf-8").replace(/<script[^>]*src="[^"]*"[^>]*><\/script>/g, "");
    const env = installDom(html, { url: BASE + url });
    globalThis.fetch = env.window.fetch = (input, init) => nodeFetch(new URL(input, BASE), init);
    process.removeAllListeners("unhandledRejection");
    process.on("unhandledRejection", e => env.errors.push(`promise: ${e?.message || e}`));
    setup(env.window);
    return {
        ...env,
        async load(module) {
            // Query string única: cada página recebe uma instância nova dos módulos.
            const href = pathToFileURL(path.join(ROOT, "static", "js", module)).href;
            await import(`${href}?instance=${instance++}`);
            await sleep(2500);
        },
    };
}

function check(label, env, extra = "") {
    const text = env.document.body.textContent.replace(/\s+/g, " ");
    const shown = [...text.matchAll(/Erro: [^.]{0,80}/g)].map(m => m[0]);
    const ok = !env.errors.length && !shown.length && env.document.querySelectorAll("#app-nav a").length > 0;
    if (!ok) failures++;
    console.log(`${ok ? "OK   " : "FALHA"} ${label.padEnd(34)} ${extra}`
        + (env.errors.length ? `\n      erros: ${env.errors.join(" | ")}` : "")
        + (shown.length ? `\n      mensagens: ${shown.join(" | ")}` : ""));
}

const PAGES = [
    ["index.html", "/", "pages/portal.js"],
    ["static/pages/painel.html", "/app/painel", "pages/dashboard.js"],
    ["static/pages/prontuario.html", "/app/prontuario", "pages/medical-record.js"],
    ["static/pages/consultas.html", "/app/consultas", "pages/appointments.js"],
    ["static/pages/laboratorio.html", "/app/laboratorio", "pages/laboratory.js"],
    ["static/pages/farmacia.html", "/app/farmacia", "pages/pharmacy.js"],
    ["static/pages/alertas.html", "/app/alertas", "pages/alerts.js"],
    ["static/pages/notificacoes.html", "/app/notificacoes", "pages/notifications.js"],
    ["static/pages/auditoria.html", "/app/auditoria", "pages/audit.js"],
    ["static/pages/profissionais.html", "/app/profissionais", "pages/professionals.js"],
    ["static/pages/status.html", "/app/status", "pages/status.js"],
];

try {
    await nodeFetch(`${BASE}/health`);
} catch {
    console.error(`Servidor indisponível em ${BASE}. Suba a aplicação antes de rodar o teste de fumaça.`);
    process.exit(2);
}

for (const [file, url, module] of PAGES) {
    const page = await openPage(file, url);
    await page.load(module);
    check(url, page, `svg=${page.document.querySelectorAll("svg").length}`);
}

// Interações: abas do prontuário e visões do painel.
const api = async p => (await nodeFetch(`${BASE}/api/v1${p}`)).json();
const patients = (await api("/patients?limit=50")).items;
let patient = patients[0];
for (const candidate of patients) {
    if ((await api(`/patients/${candidate.id}/vital-signs?limit=1`)).total) { patient = candidate; break; }
}
if (patient) {
    const record = await openPage("static/pages/prontuario.html", `/app/prontuario?patient=${patient.id}`);
    await record.load("pages/medical-record.js");
    for (const tab of [...record.document.querySelectorAll("[data-tab]")].map(b => b.dataset.tab)) {
        record.document.querySelector(`[data-tab="${tab}"]`).click();
        await sleep(1500);
        check(`prontuário › ${tab}`, record, `svg=${record.document.getElementById("tab-content").querySelectorAll("svg").length}`);
    }
    const doctor = (await api("/professionals?professional_type=MEDICO&limit=1")).items[0];
    const profiles = [
        ["paciente", { audience: "PACIENTE", recipient_id: patient.id, label: patient.full_name }],
        ...(doctor ? [["profissional", { audience: "PROFISSIONAL", recipient_id: doctor.id, label: doctor.full_name }]] : []),
        ["farmácia", { audience: "SETOR", sector: "FARMACIA", label: "Farmácia" }],
        ["administração", { audience: "SETOR", sector: "ADMINISTRACAO", label: "Administração" }],
    ];
    for (const [label, profile] of profiles) {
        const board = await openPage("static/pages/painel.html", "/app/painel",
                                     w => w.localStorage.setItem("healthos.profile", JSON.stringify(profile)));
        await board.load("pages/dashboard.js");
        check(`painel › ${label}`, board, `svg=${board.document.querySelectorAll("#board svg").length}`);
    }
}

console.log(failures ? `RESULTADO: ${failures} problema(s)` : "RESULTADO: todas as páginas e interações OK");
process.exit(failures ? 1 : 0);
