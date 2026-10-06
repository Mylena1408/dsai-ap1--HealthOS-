// Ambiente de DOM simulado compartilhado pelos testes do frontend.
import { JSDOM, VirtualConsole } from "jsdom";

let current = null;

/** Cria um DOM e expõe window/document etc. como globais, como os módulos do site esperam. */
export function installDom(html = "<!doctype html><body></body>", { url = "http://localhost/", width = 800 } = {}) {
    const errors = [];
    const virtualConsole = new VirtualConsole();
    virtualConsole.on("jsdomError", e => errors.push(e.message));
    // Fechar a janela anterior encerra seus timers, como uma navegação real no navegador.
    current?.close();
    const dom = new JSDOM(html, { url, pretendToBeVisual: true, virtualConsole });
    const w = current = dom.window;
    // Timers periódicos das páginas pertencem à janela (e morrem com ela), não ao processo Node.
    globalThis.setInterval = w.setInterval.bind(w);
    globalThis.clearInterval = w.clearInterval.bind(w);
    w.ResizeObserver = class { observe() {} };
    w.alert = message => errors.push(`alert: ${message}`);
    Object.defineProperty(w.HTMLElement.prototype, "clientWidth", { get() { return width; }, configurable: true });
    globalThis.window = w;
    for (const key of ["document", "localStorage", "CustomEvent", "Event", "HTMLElement", "URLSearchParams",
                       "ResizeObserver", "history", "Node", "FocusEvent", "KeyboardEvent"]) {
        globalThis[key] = w[key];
    }
    return { window: w, document: w.document, errors };
}
