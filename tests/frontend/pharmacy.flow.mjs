// Fluxo de interface da Fase 5 em DOM simulado contra a API real: dispensa com confirmação,
// envio único (duplo clique não duplica), saldo validado na tela, descarte confirmado e portal
// sem a dispensa legada.
//
// Pré-requisitos: servidor com dados de demonstração em banco descartável (o teste registra um
// lote e uma dispensação). Uso: npm run flow   (HEALTHOS_URL altera o endereço)
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { installDom } from "./dom.mjs";

const BASE = process.env.HEALTHOS_URL || "http://127.0.0.1:8000";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const LOCATION = "FARMACIA_CENTRAL";
const nodeFetch = globalThis.fetch;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const api = async (p, init) => (await nodeFetch(`${BASE}/api/v1${p}`, init)).json();
const post = (p, body) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
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

const pharmacist = (await api("/professionals?professional_type=FARMACEUTICO&status=ATIVO&limit=1")).items[0];
// Mesma consulta da primeira página da fila, para a prescrição aparecer na tela.
const queue = await api("/prescriptions?limit=15&offset=0&status=ATIVA&status=PARCIALMENTE_DISPENSADA");
const prescription = queue.items.find(p => !p.is_expired && p.items.some(i => i.status === "EM_USO" && i.remaining_quantity >= 2));
if (!pharmacist || !prescription) {
    console.error("Sem farmacêutico ou prescrição ativa com saldo: suba o servidor com SEED_DEMO_DATA=True.");
    process.exit(2);
}
const item = prescription.items.find(i => i.status === "EM_USO" && i.remaining_quantity >= 2);
// Garante estoque do medicamento no local da dispensa (lote fictício, válido por um ano).
const expiration = new Date(Date.now() + 365 * 864e5).toISOString().slice(0, 10);
await post("/stock/lots", { medication_id: item.medication_id, lot_number: `UI-${Date.now()}`, location: LOCATION,
                            expiration_date: expiration, quantity: 100 });
const dispensations = async () => (await api(`/dispensations?prescription_id=${prescription.id}`)).total;
const before = await dispensations();

// ------------------------------------------------------------------ dispensa
const page = await openPage("static/pages/farmacia.html", "/app/farmacia", {
    audience: "PROFISSIONAL", recipient_id: pharmacist.id, label: pharmacist.full_name, professional_type: "FARMACEUTICO",
});
await page.load("pages/pharmacy.js");
const doc = page.document;
const select = await waitFor(() => doc.querySelector("#d-pharmacist option[value]:not([value=''])") && doc.getElementById("d-pharmacist"));
check("dispensa › farmacêutico do perfil já vem escolhido", select?.value === pharmacist.id, select?.value || "sem seletor");

(await waitFor(() => doc.querySelector(`[data-dispense="${prescription.id}"]`)))?.click();
const inputs = await waitFor(() => {
    const found = [...doc.querySelectorAll("#d-items [data-item]")];
    return found.length && found;
});
const target = inputs && inputs.find(input => input.dataset.item === item.id);
const form = doc.getElementById("form-dispense");
const setQuantity = value => inputs.forEach(input => { input.value = input === target ? String(value) : "0"; });
let confirms = 0;

page.window.confirm = () => { confirms++; return false; };
setQuantity(1);
form.requestSubmit();
await sleep(1500);
check("dispensa › cancelar a confirmação não dispensa", confirms === 1 && await dispensations() === before);

// O campo tem max = saldo: a validação nativa do formulário barra o envio antes do código
// (no navegador, a mensagem aparece junto ao campo); a checagem em submitDispense é a segunda barreira.
setQuantity(item.remaining_quantity + 5);
let submits = 0;
const countSubmit = () => { submits++; };
form.addEventListener("submit", countSubmit);
form.requestSubmit();
await sleep(1000);
form.removeEventListener("submit", countSubmit);
check("dispensa › quantidade acima do saldo barrada na tela",
      target.validity.rangeOverflow && submits === 0 && confirms === 1 && await dispensations() === before,
      `inválido=${target.validity.rangeOverflow}, envios=${submits}`);

page.window.confirm = () => { confirms++; return true; };
setQuantity(1);
form.requestSubmit();
form.requestSubmit();
form.querySelector('[type="submit"]').click();
const once = await waitFor(async () => await dispensations() === before + 1);
await sleep(2000);
const after = await dispensations();
check("dispensa › duplo clique gera uma única dispensação", Boolean(once) && after === before + 1,
      `antes ${before}, depois ${after}, confirmações ${confirms - 1}`);
const button = form.querySelector('[type="submit"]');
const locked = await waitFor(() => button.disabled && button.textContent === "Dispensado"
                                   && [...form.querySelectorAll("input, select")].every(field => field.disabled));
check("dispensa › formulário bloqueado depois do sucesso", Boolean(locked));
form.requestSubmit();
await sleep(1000);
check("dispensa › novo envio com o formulário bloqueado não dispensa", await dispensations() === before + 1);
check("dispensa › sem erros de execução", !page.errors.length, page.errors.join(" | "));

// --------------------------------------------------------- descarte de lote
(await waitFor(() => doc.querySelector('[data-tab="expiry"]')))?.click();
const discard = await waitFor(() => doc.querySelector("[data-discard]"), 6000);
if (discard) {
    const lotId = discard.dataset.discard;
    const lotsBefore = (await api("/stock/lots?expiring_within_days=60&limit=200")).items.find(l => l.id === lotId);
    page.window.confirm = () => false;
    discard.click();
    await sleep(1500);
    const lotsAfter = (await api("/stock/lots?expiring_within_days=60&limit=200")).items.find(l => l.id === lotId);
    check("descarte › cancelar a confirmação mantém o lote", lotsAfter && lotsAfter.quantity === lotsBefore.quantity,
          `lote ${discard.dataset.lotNumber}`);
} else {
    console.log("PULADO descarte › nenhum lote vencido nos dados de demonstração");
}

// -------------------------------------------------------------------- portal
const portal = await openPage("index.html", "/");
await portal.load("pages/portal.js");
await sleep(500);
const grid = portal.document.getElementById("grid-doctor");
const hrefs = [...grid.querySelectorAll("a")].map(a => a.getAttribute("href"));
check("portal › sem o formulário de dispensa legada",
      !portal.document.getElementById("form-doc-pharmacy") && !portal.document.querySelector('[data-open-modal="modal-doc-pharmacy"]'));
check("portal › card leva ao prontuário e à Farmácia", hrefs.includes("/app/prontuario") && hrefs.includes("/app/farmacia"), hrefs.join(", "));
check("portal › sem erros de execução", !portal.errors.length, portal.errors.join(" | "));

console.log(failures ? `RESULTADO: ${failures} problema(s)` : "RESULTADO: fluxo da farmácia OK");
process.exit(failures ? 1 : 0);
