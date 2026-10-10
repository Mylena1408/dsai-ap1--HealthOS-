// Testes da navegação orientada por perfil (rodam sem servidor): npm test
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { installDom } from "./dom.mjs";

let env;
beforeEach(() => {
    env = installDom('<!doctype html><body><nav id="app-nav"></nav></body>');
    // Sem servidor: o sino de notificações falha em silêncio, como no site.
    globalThis.fetch = () => Promise.reject(new Error("offline"));
});

// core/api.js lê window.location ao ser importado: o DOM precisa existir antes dos imports.
installDom();
const { dashboardViewFor, pagesForProfile } = await import("../../static/js/core/role-nav.js");
const { renderNav } = await import("../../static/js/core/layout.js");
const { setProfile } = await import("../../static/js/components/profile.js");
const { fillAuthorSelect } = await import("../../static/js/components/author-select.js");

const doctor = { audience: "PROFISSIONAL", recipient_id: "1", label: "Ana Lima", professional_type: "MEDICO" };
const nurse = { audience: "PROFISSIONAL", recipient_id: "2", label: "Rui Costa", professional_type: "ENFERMEIRO" };
const patient = { audience: "PACIENTE", recipient_id: "3", label: "Bia Souza" };
const save = profile => env.window.localStorage.setItem("healthos.profile", JSON.stringify(profile));
const forYouHrefs = (index = 0) => [...env.document.querySelectorAll("[data-for-you]")[index].querySelectorAll("a")]
    .map(a => a.getAttribute("href"));

test("sugestões por perfil cobrem todos os tipos, setores e o paciente", () => {
    assert.deepEqual(pagesForProfile(doctor), ["painel", "prontuario", "consultas", "laboratorio", "alertas", "assistente"]);
    assert.deepEqual(pagesForProfile(nurse), ["portal", "painel", "prontuario", "consultas", "alertas", "laboratorio"]);
    assert.deepEqual(pagesForProfile({ ...doctor, professional_type: "PSICOLOGO" }), ["portal", "consultas", "prontuario", "painel", "alertas"]);
    assert.deepEqual(pagesForProfile({ ...doctor, professional_type: "FARMACEUTICO" }), ["painel", "farmacia", "prontuario", "alertas"]);
    for (const type of ["NUTRICIONISTA", "FISIOTERAPEUTA", "OUTRO", undefined, "DESCONHECIDO"]) {
        assert.deepEqual(pagesForProfile({ ...doctor, professional_type: type }), ["painel", "prontuario", "consultas", "alertas"]);
    }
    const sector = key => pagesForProfile({ audience: "SETOR", sector: key });
    assert.deepEqual(sector("FARMACIA"), ["painel", "farmacia", "prontuario", "alertas"]);
    assert.deepEqual(sector("ENFERMAGEM"), pagesForProfile(nurse));
    assert.deepEqual(sector("LABORATORIO"), ["laboratorio", "painel", "alertas"]);
    assert.deepEqual(sector("RECEPCAO"), ["consultas", "busca", "profissionais"]);
    assert.deepEqual(sector("COORDENACAO_CLINICA"), ["painel", "alertas", "profissionais", "relatorios", "auditoria"]);
    assert.deepEqual(sector("ADMINISTRACAO"), ["painel", "financeiro", "relatorios", "profissionais", "auditoria", "status"]);
    assert.deepEqual(pagesForProfile(patient), ["painel", "notificacoes", "assistente"]);
    assert.deepEqual(pagesForProfile(null), sector("ADMINISTRACAO"));
});

test("'Para você' segue o perfil na barra e no menu móvel, sem repetir aria-current", () => {
    save(doctor);
    renderNav("prontuario");
    const expected = ["/app/painel", "/app/prontuario", "/app/consultas", "/app/laboratorio", "/app/alertas", "/app/assistente"];
    assert.deepEqual(forYouHrefs(0), expected);
    assert.deepEqual(forYouHrefs(1), expected);
    for (const list of env.document.querySelectorAll("[data-for-you]")) {
        assert.equal(list.querySelectorAll("[aria-current]").length, 0);
    }
    assert.match(env.document.getElementById("nav-menu-para-voce").textContent, /Todas as telas continuam/);
    const toggle = env.document.querySelector('button[aria-controls="nav-menu-para-voce"]');
    assert.equal(toggle.getAttribute("aria-expanded"), "false");
});

test("menus com todas as telas não mudam com o perfil", () => {
    const allLinks = () => ["nav-menu-atendimento", "nav-menu-gestao"]
        .flatMap(id => [...env.document.getElementById(id).querySelectorAll("a")].map(a => a.getAttribute("href")));
    save(patient);
    renderNav("painel");
    const forPatient = allLinks();
    assert.equal(forPatient.length, 12);
    env = installDom('<!doctype html><body><nav id="app-nav"></nav></body>');
    save(doctor);
    renderNav("painel");
    assert.deepEqual(allLinks(), forPatient);
});

test("trocar de perfil refaz as sugestões sem recarregar", () => {
    save(doctor);
    renderNav("painel");
    setProfile(nurse);
    assert.deepEqual(forYouHrefs(0), ["/", "/app/painel", "/app/prontuario", "/app/consultas", "/app/alertas", "/app/laboratorio"]);
    assert.equal(env.document.querySelector("[data-for-you-label]").textContent, "Perfil: Rui Costa");
    const button = env.document.querySelector("[data-profile]");
    assert.equal(button.getAttribute("aria-label"), "Perfil de demonstração: Rui Costa, Enfermeiro(a) (trocar)");
});

test("rótulo do perfil é escapado e perfis antigos sem tipo recebem a sugestão genérica", () => {
    save({ audience: "PROFISSIONAL", recipient_id: "9", label: '<img src=x onerror="alert(1)">' });
    renderNav("painel");
    assert.equal(env.document.querySelectorAll("#app-nav img").length, 0);
    assert.match(env.document.querySelector("[data-for-you-label]").textContent, /<img src=x/);
    assert.deepEqual(forYouHrefs(0), ["/app/painel", "/app/prontuario", "/app/consultas", "/app/alertas"]);
});

test("autor do registro é sugerido pelo perfil profissional e agrupado por tipo", () => {
    const professionals = [
        { id: "1", full_name: "Ana Lima", professional_type: "MEDICO" },
        { id: "2", full_name: "Rui Costa", professional_type: "ENFERMEIRO" },
    ];
    const select = () => env.document.body.appendChild(env.document.createElement("select"));
    save(nurse);
    const forNurse = select();
    fillAuthorSelect(forNurse, professionals);
    assert.equal(forNurse.value, "2");
    assert.deepEqual([...forNurse.querySelectorAll("optgroup")].map(g => g.label), ["Médico(a)", "Enfermeiro(a)"]);
    save(patient);
    const forPatient = select();
    fillAuthorSelect(forPatient, professionals, { placeholder: "Selecione" });
    assert.equal(forPatient.value, "");
    assert.equal(forPatient.options[0].textContent, "Selecione");
});

test("visão inicial do Painel acompanha o perfil", () => {
    assert.equal(dashboardViewFor(patient), "patient");
    assert.equal(dashboardViewFor(doctor), "professional");
    assert.equal(dashboardViewFor(nurse), "nursing");
    assert.equal(dashboardViewFor({ ...doctor, professional_type: "PSICOLOGO" }), "professional");
    assert.equal(dashboardViewFor({ ...doctor, professional_type: undefined }), "professional");
    const sector = key => dashboardViewFor({ audience: "SETOR", sector: key });
    assert.equal(sector("ENFERMAGEM"), "nursing");
    assert.equal(sector("FARMACIA"), "pharmacy");
    for (const key of ["RECEPCAO", "LABORATORIO", "COORDENACAO_CLINICA", "ADMINISTRACAO"]) assert.equal(sector(key), "admin");
    assert.equal(dashboardViewFor(null), "admin");
});
