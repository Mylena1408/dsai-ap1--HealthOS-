// Testes dos componentes de gráfico (rodam sem servidor): npm test
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { installDom } from "./dom.mjs";

let env;
beforeEach(() => { env = installDom(); });

const { renderLineChart } = await import("../../static/js/components/line-chart.js");
const { renderBarChart } = await import("../../static/js/components/bar-chart.js");
const day = i => new Date(2026, 9, 1 + i, 12);
const container = () => env.document.body.appendChild(env.document.createElement("div"));

test("linha: duas séries, faixa de referência, legenda e rótulo final", () => {
    const el = container();
    renderLineChart(el, [
        { name: "Sistólica", color: "var(--series-1)", points: [0, 1, 2, 3].map(i => ({ t: day(i), v: 120 + i * 5 })) },
        { name: "Diastólica", color: "var(--series-2)", points: [0, 1, 2, 3].map(i => ({ t: day(i), v: 80 + i })) },
    ], { unit: "mmHg", reference: { min: 90, max: 129 } });
    assert.equal(el.querySelectorAll("svg path").length, 2);
    assert.equal(el.querySelectorAll("svg circle").length, 8);
    assert.equal(el.querySelectorAll(".viz-band").length, 1);
    assert.equal(el.querySelectorAll(".viz-legend > span").length, 2);
    assert.deepEqual([...el.querySelectorAll(".viz-end-label")].map(t => t.textContent), ["135 mmHg", "83 mmHg"]);
    assert.doesNotMatch(el.innerHTML, /NaN/);
});

test("linha: tooltip por teclado percorre as medições", () => {
    const el = container();
    renderLineChart(el, [{ name: "FC", color: "red", points: [0, 1, 2].map(i => ({ t: day(i), v: 70 + i })) }],
                    { unit: "bpm" });
    const overlay = el.querySelector("rect[tabindex]");
    overlay.dispatchEvent(new env.window.FocusEvent("focus"));
    const tooltip = el.querySelector(".viz-tooltip");
    assert.equal(tooltip.hidden, false);
    assert.match(tooltip.textContent, /72 bpm/);  // começa na última medição
    overlay.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "ArrowLeft" }));
    assert.match(tooltip.textContent, /71 bpm/);
});

test("linha: casos-limite não geram coordenadas inválidas e série única não tem legenda", () => {
    const flat = container();
    renderLineChart(flat, [{ name: "Zero", color: "red", points: [0, 1, 2].map(i => ({ t: day(i), v: 0 })) }]);
    const single = container();
    renderLineChart(single, [{ name: "Um", color: "red", points: [{ t: day(0), v: 5 }] }]);
    for (const el of [flat, single]) assert.doesNotMatch(el.innerHTML, /NaN/);
    assert.equal(flat.querySelectorAll(".viz-legend").length, 0);
});

test("barras: valor na ponta, tooltip no foco e estado vazio", () => {
    const el = container();
    renderBarChart(el, [{ label: "Finalizada", value: 12 }, { label: "Cancelada", value: 3 }, { label: "Zero", value: 0 }],
                   { unit: "un." });
    assert.deepEqual([...el.querySelectorAll(".viz-end-label")].map(t => t.textContent), ["12 un.", "3 un.", "0 un."]);
    el.querySelectorAll("path")[1].dispatchEvent(new env.window.FocusEvent("focus"));
    assert.match(el.querySelector(".viz-tooltip").textContent, /3 un\.Cancelada/);
    assert.doesNotMatch(el.innerHTML, /NaN/);

    const empty = container();
    renderBarChart(empty, []);
    assert.match(empty.textContent, /Sem dados/);
});

test("escapeHtml neutraliza marcação vinda da API", async () => {
    const { escapeHtml } = await import("../../static/js/core/dom.js");
    assert.equal(escapeHtml('<img src=x onerror="alert(1)">'), "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
    assert.equal(escapeHtml(null), "");
});

test("resposta da IA: texto escapado, alerta de urgência, registros e aviso", async () => {
    const { aiResponseCard, providerBadge } = await import("../../static/js/components/ai-response.js");
    const html = aiResponseCard({
        feature: "ORIENTACAO_SINTOMAS", text: "Linha 1\n<img src=x onerror=alert(1)>", provider: "demo",
        model: "regras", urgent: true, facts_used: [{ category: "Alergia", text: "Dipirona" }],
        disclaimer: "As informações apresentadas são educacionais e não substituem avaliação profissional.",
    });
    const box = document.createElement("div");
    box.innerHTML = html;
    assert.equal(box.querySelector("img"), null);
    assert.match(box.textContent, /Orientação sobre sintomas/);
    assert.match(box.querySelector("[role=alert]").textContent, /192/);
    assert.match(box.querySelector("details").textContent, /Registros consultados \(1\)/);
    assert.match(box.textContent, /não substituem avaliação profissional/);
    assert.match(providerBadge({ demo_mode: true, model: "x" }), /Modo demonstração/);
});

test("destaque da busca não injeta HTML e não quebra entidades", async () => {
    const { highlightTerm } = await import("../../static/js/core/dom.js");
    assert.equal(highlightTerm("Maria & <b>Ana</b>", "ana"),
                 'Maria &amp; &lt;b&gt;<mark class="bg-amber-100 rounded px-0.5">Ana</mark>&lt;/b&gt;');
    assert.equal(highlightTerm("A & B", "amp"), "A &amp; B");  // o termo não casa dentro de &amp;
    assert.equal(highlightTerm("custo (R$)", "(R$"), 'custo <mark class="bg-amber-100 rounded px-0.5">(R$</mark>)');
    assert.equal(highlightTerm("texto", "  "), "texto");
});
