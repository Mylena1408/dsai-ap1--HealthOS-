// Revisão em navegador real: acessibilidade (axe, WCAG 2.1 AA), estouro horizontal em 4 larguras,
// erros na tela/console e interações por teclado. Uso (com a API rodando):
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
const WIDTHS = [1440, 1024, 768, 375];
const PAGES = ["/", "/app/painel", "/app/prontuario", "/app/consultas", "/app/laboratorio", "/app/farmacia",
               "/app/financeiro", "/app/relatorios", "/app/busca?q=ro", "/app/assistente", "/app/alertas",
               "/app/notificacoes", "/app/auditoria", "/app/profissionais", "/app/status"];
const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21aa"];
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

// 1. Cada página em quatro larguras.
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
        if (width === WIDTHS[0]) problems.push(...(await axe(page)).map(v => `axe ${v}`));
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
await page.setViewport({ width: 375, height: 800 });
await page.goto(`${BASE}/app/painel`, { waitUntil: "networkidle0" });
await page.click("#nav-toggle");
state = await page.evaluate(() => ({ expanded: document.getElementById("nav-toggle").getAttribute("aria-expanded"),
                                     links: document.querySelectorAll("#nav-mobile a").length }));
check("menu móvel abre com todas as páginas", state.expanded === "true" && state.links >= 12, JSON.stringify(state));

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

await browser.close();
console.log(failures ? `RESULTADO: ${failures} problema(s)` : "RESULTADO: nenhuma violação encontrada");
process.exit(failures ? 1 : 0);
