// Revisão em navegador real: acessibilidade (axe, WCAG 2.0/2.1/2.2 A e AA) e estouro horizontal em
// 6 larguras, erros na tela/console, estados por perfil e interações por teclado. Uso (com a API
// rodando sobre um banco descartável — a revisão grava um rascunho de evolução):
//   HEALTHOS_URL=http://127.0.0.1:8000 npm run a11y
// Variáveis: BROWSER_PATH (Edge/Chrome instalado), SCREENSHOTS=<pasta> para salvar capturas.
import fs from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer-core";

const BASE = process.env.HEALTHOS_URL || "http://127.0.0.1:8000";
const BROWSER = process.env.BROWSER_PATH || [
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].find(candidate => fs.existsSync(candidate));
const SHOTS = process.env.SCREENSHOTS;
const WIDTHS = [1440, 1024, 768, 390, 375, 360];
const STATE_WIDTHS = [1440, 768, 360];
const PAGES = ["/", "/app/painel", "/app/prontuario", "/app/consultas", "/app/laboratorio", "/app/farmacia",
               "/app/financeiro", "/app/relatorios", "/app/busca?q=ro", "/app/assistente", "/app/alertas",
               "/app/notificacoes", "/app/auditoria", "/app/profissionais", "/app/status"];
const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const axeSource = fs.readFileSync(new URL("./node_modules/axe-core/axe.min.js", import.meta.url), "utf8");
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

if (!BROWSER) {
    console.error("Nenhum navegador encontrado: defina BROWSER_PATH com o caminho do Edge ou do Chrome.");
    process.exit(2);
}
if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });

let failures = 0;
function check(name, ok, detail = "") {
    if (!ok) failures++;
    console.log(`${ok ? "OK   " : "FALHA"} ${name}${detail ? `: ${detail}` : ""}`);
}

async function axe(page) {
    if (!(await page.evaluate(() => Boolean(window.axe)))) await page.addScriptTag({ content: axeSource });
    const violations = await page.evaluate(async tags => (await window.axe.run(document, { runOnly: { type: "tag", values: tags } }))
        .violations.map(v => `${v.id} x${v.nodes.length} (${v.nodes.slice(0, 2).map(n => n.target.join(" ")).join(" ; ")})`), AXE_TAGS);
    return violations;
}

const browser = await puppeteer.launch({ executablePath: BROWSER, headless: true });
const page = await browser.newPage();
const pageErrors = [];
page.on("pageerror", error => pageErrors.push(error.message));
page.on("console", message => { if (message.type() === "error") pageErrors.push(message.text()); });

// 1. Cada página em seis larguras.
for (const url of PAGES) {
    for (const width of WIDTHS) {
        pageErrors.length = 0;
        await page.setViewport({ width, height: 900 });
        await page.goto(BASE + url, { waitUntil: "networkidle0" });
        await sleep(400);
        const state = await page.evaluate(() => ({
            overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            shownErrors: [...document.body.innerText.matchAll(/Erro: [^\n]{0,80}/g)].map(m => m[0]),
        }));
        const problems = [...pageErrors, ...state.shownErrors];
        if (state.overflow > 1) problems.push(`rolagem horizontal de ${state.overflow}px`);
        problems.push(...(await axe(page)).map(v => `axe ${v}`));
        check(`${url} @${width}px`, !problems.length, problems.join(" | "));
        if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${url.replace(/\W+/g, "_") || "portal"}_${width}.png`) });
    }
}

// 2. Menus da navegação pelo teclado.
await page.setViewport({ width: 1280, height: 800 });
await page.goto(`${BASE}/app/financeiro`, { waitUntil: "networkidle0" });
await page.focus('button[aria-controls="nav-menu-gestao"]');
await page.keyboard.press("Enter");
let state = await page.evaluate(() => ({
    expanded: document.querySelector('button[aria-controls="nav-menu-gestao"]').getAttribute("aria-expanded"),
    current: document.querySelector('#nav-menu-gestao [aria-current="page"]')?.textContent.trim(),
}));
check("menu Gestão abre com Enter e marca a página atual", state.expanded === "true" && state.current === "Financeiro", JSON.stringify(state));
const menuViolations = await axe(page);
check("axe com o menu aberto", !menuViolations.length, menuViolations.join(" | "));
await page.keyboard.press("Tab");
check("Tab entra no menu", await page.evaluate(() => Boolean(document.activeElement.closest("#nav-menu-gestao"))));
await page.keyboard.press("Escape");
state = await page.evaluate(() => ({ hidden: document.getElementById("nav-menu-gestao").hidden,
                                     focus: document.activeElement.getAttribute("aria-controls") }));
check("Esc fecha o menu e devolve o foco", state.hidden && state.focus === "nav-menu-gestao", JSON.stringify(state));

// 3. Menu móvel.
for (const width of [375, 360]) {
    await page.setViewport({ width, height: 800 });
    await page.goto(`${BASE}/app/painel`, { waitUntil: "networkidle0" });
    await page.click("#nav-toggle");
    state = await page.evaluate(() => ({ expanded: document.getElementById("nav-toggle").getAttribute("aria-expanded"),
                                         links: document.querySelectorAll("#nav-mobile a").length }));
    check(`menu móvel abre com todas as páginas @${width}px`, state.expanded === "true" && state.links >= 12, JSON.stringify(state));
}

// 4. Seletor de paciente só com teclado.
await page.setViewport({ width: 1280, height: 800 });
await page.goto(`${BASE}/app/assistente`, { waitUntil: "networkidle0" });
await page.focus("#patient-search");
await page.keyboard.type("a");
await sleep(900);
await page.keyboard.press("ArrowDown");
state = await page.evaluate(() => document.getElementById("patient-search").getAttribute("aria-activedescendant"));
check("setas percorrem as opções do seletor de paciente", Boolean(state), String(state));
await page.keyboard.press("Enter");
await sleep(1000);
check("Enter escolhe o paciente", await page.evaluate(() => !document.getElementById("btn-summary").disabled));

// 5. Modal aberto e atalho de busca.
await page.goto(`${BASE}/app/financeiro`, { waitUntil: "networkidle0" });
await page.click("[data-invoice]");
await sleep(1000);
const modalViolations = await axe(page);
check("axe com o modal de fatura aberto", !modalViolations.length, modalViolations.join(" | "));
await page.goto(`${BASE}/app/painel`, { waitUntil: "networkidle0" });
await page.keyboard.press("/");
check("tecla / leva à busca", await page.evaluate(() => document.activeElement.id === "nav-search-input"));

// 6. Estados das Fases 3 a 6 (perfis, aba Evolução, modal de dispensa, seletor do portal).
const api = async (p, init) => (await fetch(`${BASE}/api/v1${p}`, init)).json();
const first = async query => (await api(query)).items[0];
const patient = await first("/patients?limit=1");
const doctor = await first("/professionals?professional_type=MEDICO&status=ATIVO&limit=1");
const nurse = await first("/professionals?professional_type=ENFERMEIRO&status=ATIVO&limit=1");
const asProfessional = p => ({ audience: "PROFISSIONAL", recipient_id: p.id, label: p.full_name, professional_type: p.professional_type });
// Rascunho para auditar o editor da aba Evolução (grava no banco em uso: use um banco descartável).
const draft = await api(`/patients/${patient.id}/evolutions`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ professional_id: doctor.id, content: "Rascunho da revisão de acessibilidade." }),
});

async function withProfile(profile) {
    await page.goto(`${BASE}/health`);
    await page.evaluate(value => {
        if (value) localStorage.setItem("healthos.profile", JSON.stringify(value));
        else localStorage.removeItem("healthos.profile");
    }, profile);
}

const STATES = [
    ["painel › visão Enfermagem", asProfessional(nurse), async () => {
        await page.goto(`${BASE}/app/painel`, { waitUntil: "networkidle0" });
        await page.waitForFunction(() => document.body.innerText.includes("Pacientes do dia"), { timeout: 10000 });
    }],
    ["painel › médico com 'Médicos disponíveis'", asProfessional(doctor), async () => {
        await page.goto(`${BASE}/app/painel`, { waitUntil: "networkidle0" });
        await page.waitForSelector("[data-copy-id]", { timeout: 10000 });
    }],
    ["painel › paciente", { audience: "PACIENTE", recipient_id: patient.id, label: patient.full_name }, async () => {
        await page.goto(`${BASE}/app/painel`, { waitUntil: "networkidle0" });
        await page.waitForFunction(() => document.body.innerText.includes("Alertas abertos"), { timeout: 10000 });
    }],
    ["prontuário › Evolução com editor aberto", asProfessional(doctor), async () => {
        await page.goto(`${BASE}/app/prontuario?patient=${patient.id}`, { waitUntil: "networkidle0" });
        await page.click('[data-tab="evolucao"]');
        await page.waitForSelector(`[data-evolution="${draft.id}"] [data-evo-act="edit"]`, { timeout: 10000 });
        await page.click(`[data-evolution="${draft.id}"] [data-evo-act="edit"]`);
        await page.waitForSelector("[data-evo-edit]", { timeout: 5000 });
    }],
    ["farmácia › modal de dispensa aberto", null, async () => {
        await page.goto(`${BASE}/app/farmacia`, { waitUntil: "networkidle0" });
        await page.waitForSelector("[data-dispense]", { timeout: 10000 });
        await page.click("[data-dispense]");
        await page.waitForSelector("#modal-dispense.active", { timeout: 5000 });
    }],
    ["portal › seletor de paciente aberto no modal", null, async () => {
        await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
        await page.click('[data-open-modal="modal-consultas"]');
        await page.focus("#p-consult-patient");
        await page.keyboard.type("a");
        await page.waitForSelector('[role="listbox"]:not(.hidden) [role="option"]', { timeout: 5000 });
    }],
];

for (const [name, profile, prepare] of STATES) {
    for (const width of STATE_WIDTHS) {
        pageErrors.length = 0;
        await page.setViewport({ width, height: 900 });
        await withProfile(profile);
        try {
            await prepare();
            await sleep(400);
        } catch (error) {
            check(`${name} @${width}px`, false, `estado não preparado: ${error.message}`);
            continue;
        }
        const layout = await page.evaluate(() => ({
            overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            shownErrors: [...document.body.innerText.matchAll(/Erro: [^\n]{0,80}/g)].map(m => m[0]),
        }));
        const problems = [...pageErrors, ...layout.shownErrors, ...(await axe(page)).map(v => `axe ${v}`)];
        if (layout.overflow > 1) problems.push(`rolagem horizontal de ${layout.overflow}px`);
        check(`${name} @${width}px`, !problems.length, problems.join(" | "));
        if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `estado_${name.replace(/\W+/g, "_")}_${width}.png`) });
    }
}
await withProfile(null);

// 7. Teclado: menu "Para você" e seletor de paciente dentro de um modal do portal.
await page.setViewport({ width: 1280, height: 800 });
await page.goto(`${BASE}/app/painel`, { waitUntil: "networkidle0" });
await page.focus('button[aria-controls="nav-menu-para-voce"]');
await page.keyboard.press("Enter");
state = await page.evaluate(() => document.querySelector('button[aria-controls="nav-menu-para-voce"]').getAttribute("aria-expanded"));
check("menu 'Para você' abre com Enter", state === "true", String(state));
await page.keyboard.press("Tab");
check("Tab entra no menu 'Para você'", await page.evaluate(() => Boolean(document.activeElement.closest("#nav-menu-para-voce"))));
await page.keyboard.press("Escape");
state = await page.evaluate(() => ({ hidden: document.getElementById("nav-menu-para-voce").hidden,
                                     focus: document.activeElement.getAttribute("aria-controls") }));
check("Esc fecha 'Para você' e devolve o foco", state.hidden && state.focus === "nav-menu-para-voce", JSON.stringify(state));

await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
await page.click('[data-open-modal="modal-consultas"]');
await page.focus("#p-consult-patient");
await page.keyboard.type("a");
await sleep(900);
await page.keyboard.press("ArrowDown");
state = await page.evaluate(() => document.getElementById("p-consult-patient").getAttribute("aria-activedescendant"));
check("portal: setas percorrem o seletor dentro do modal", Boolean(state), String(state));
await page.keyboard.press("Enter");
await sleep(300);
state = await page.evaluate(() => ({ value: document.getElementById("p-consult-patient").value,
                                     modal: document.getElementById("modal-consultas").classList.contains("active") }));
check("portal: Enter escolhe o paciente sem fechar o modal", Boolean(state.value) && state.modal, JSON.stringify(state));
await page.keyboard.type("o");
await sleep(900);
await page.keyboard.press("Escape");
await sleep(200);
state = await page.evaluate(() => ({
    list: !document.querySelector("#modal-consultas [role='listbox']").classList.contains("hidden"),
    modal: document.getElementById("modal-consultas").classList.contains("active"),
}));
check("portal: Esc fecha só a lista do seletor (modal continua aberto)", !state.list && state.modal, JSON.stringify(state));

await browser.close();
console.log(failures ? `RESULTADO: ${failures} problema(s)` : "RESULTADO: nenhuma violação encontrada");
process.exit(failures ? 1 : 0);
