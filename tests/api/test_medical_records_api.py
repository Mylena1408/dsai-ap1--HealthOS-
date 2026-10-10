from datetime import datetime, timedelta
import uuid

import pytest

API = "/api/v1"


@pytest.fixture(scope="module")
def patient(client):
    response = client.post(f"{API}/admin/patients/", json={
        "full_name": "Helena Prontuário (fictícia)", "cpf": "71428793860", "birth_date": "1970-07-07",
        "gender": "Feminino", "email": "helena.prontuario@example.com",
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_search_patients_is_paginated(client, patient):
    page = client.get(f"{API}/patients", params={"q": "helena prontu"}).json()
    assert page["total"] == 1 and page["items"][0]["id"] == patient["id"]
    assert page["items"][0]["age"] >= 55
    assert client.get(f"{API}/patients", params={"q": "714.287"}).json()["total"] == 1
    assert client.get(f"{API}/patients", params={"order_by": "invalido"}).status_code == 422
    assert client.get(f"{API}/patients", params={"limit": 1}).json()["limit"] == 1


def test_record_crud_over_http(client, patient):
    pid = patient["id"]
    profile = client.put(f"{API}/patients/{pid}/profile", json={"blood_type": "AB+", "occupation": "Engenheira"})
    assert profile.status_code == 200 and profile.json()["blood_type"] == "AB+"
    assert client.put(f"{API}/patients/{pid}/profile", json={"blood_type": "Z+"}).status_code == 422

    contact = client.post(f"{API}/patients/{pid}/emergency-contacts", json={
        "full_name": "Rui Contato", "relationship": "Esposo", "phone": "(91) 97777-6666"}).json()
    contact_id = contact["emergency_contacts"][0]["id"]
    assert contact["emergency_contacts"][0]["is_primary"] is True

    allergy = client.post(f"{API}/patients/{pid}/allergies", json={
        "substance": "Látex", "category": "AMBIENTAL", "severity": "GRAVE", "reaction": "Urticária (fictícia)"})
    assert allergy.status_code == 201
    assert client.post(f"{API}/patients/{pid}/allergies", json={
        "substance": "látex", "category": "AMBIENTAL", "severity": "LEVE"}).status_code == 409

    condition = client.post(f"{API}/patients/{pid}/conditions", json={"name": "Diabetes tipo 2 (fictícia)",
                                                                       "code": "E11", "onset_date": "2015-01-01"}).json()
    controlled = client.patch(f"{API}/patients/{pid}/conditions/{condition['id']}/status", json={"status": "CONTROLADA"})
    assert controlled.json()["status"] == "CONTROLADA"

    diagnosis = client.post(f"{API}/patients/{pid}/diagnoses", json={"description": "Hipótese fictícia"}).json()
    assert client.post(f"{API}/patients/{pid}/diagnoses/{diagnosis['id']}/rule-out").json()["certainty"] == "DESCARTADA"
    assert client.post(f"{API}/patients/{pid}/diagnoses/{diagnosis['id']}/confirm").status_code == 409

    performed = (datetime.now() - timedelta(days=1)).isoformat()
    assert client.post(f"{API}/patients/{pid}/procedures", json={"name": "Glicemia capilar", "performed_at": performed}).status_code == 201
    future = (datetime.now() + timedelta(days=1)).isoformat()
    assert client.post(f"{API}/patients/{pid}/procedures", json={"name": "No futuro", "performed_at": future}).status_code == 400

    record = client.get(f"{API}/patients/{pid}/record").json()
    assert record["patient"]["full_name"] == "Helena Prontuário (fictícia)"
    assert record["profile"]["occupation"] == "Engenheira"
    assert [a["substance"] for a in record["active_allergies"]] == ["Látex"]
    assert record["active_conditions"][0]["status"] == "CONTROLADA"

    removed = client.delete(f"{API}/patients/{pid}/emergency-contacts/{contact_id}").json()
    assert removed["emergency_contacts"] == []


def test_timeline_over_http(client, patient):
    pid = patient["id"]
    page = client.get(f"{API}/patients/{pid}/timeline").json()
    types = {e["event_type"] for e in page["items"]}
    assert {"CADASTRO", "ALERGIA", "CONDICAO", "DIAGNOSTICO", "PROCEDIMENTO"} <= types

    filtered = client.get(f"{API}/patients/{pid}/timeline", params={"types": ["ALERGIA", "PROCEDIMENTO"]}).json()
    assert {e["event_type"] for e in filtered["items"]} == {"ALERGIA", "PROCEDIMENTO"}
    assert client.get(f"{API}/patients/{pid}/timeline", params={"types": "XYZ"}).status_code == 422
    assert client.get(f"{API}/patients/{pid}/timeline", params={"date_from": "2026-02-01", "date_to": "2026-01-01"}).status_code == 400


def test_unknown_patient_returns_404(client):
    missing = uuid.uuid4()
    for path in ("record", "timeline", "allergies", "conditions", "diagnoses", "procedures", "evolutions"):
        assert client.get(f"{API}/patients/{missing}/{path}").status_code == 404, path


def test_evolutions_over_http(client, patient):
    pid = patient["id"]
    nurse = client.post(f"{API}/professionals", json={
        "full_name": "Enf. Evolução (fictícia)", "professional_type": "ENFERMEIRO", "registry_number": "COREN-EV 1"}).json()
    created = client.post(f"{API}/patients/{pid}/evolutions", json={
        "professional_id": nurse["id"], "content": "Curativo realizado, ferida limpa (fictício)."})
    assert created.status_code == 201, created.text
    evolution = created.json()
    assert evolution["status"] == "RASCUNHO" and evolution["professional_type"] == "ENFERMEIRO"
    eid = evolution["id"]

    assert client.post(f"{API}/patients/{pid}/evolutions", json={
        "professional_id": nurse["id"], "content": "curto"}).status_code == 422
    assert client.post(f"{API}/patients/{pid}/evolutions", json={
        "professional_id": str(uuid.uuid4()), "content": "Profissional que não existe."}).status_code == 404

    edited = client.patch(f"{API}/patients/{pid}/evolutions/{eid}", json={
        "content": "Curativo realizado, ferida limpa e seca (fictício)."}).json()
    assert edited["version"] == 2
    signed = client.post(f"{API}/patients/{pid}/evolutions/{eid}/sign").json()
    assert signed["status"] == "ASSINADA" and signed["signed_at"]
    assert client.patch(f"{API}/patients/{pid}/evolutions/{eid}", json={
        "content": "Tentativa de alterar a evolução."}).status_code == 409
    assert client.post(f"{API}/patients/{pid}/evolutions/{eid}/sign").status_code == 409
    assert client.post(f"{API}/patients/{pid}/evolutions/{uuid.uuid4()}/sign").status_code == 404

    assert [e["id"] for e in client.get(f"{API}/patients/{pid}/evolutions").json()] == [eid]
    timeline = client.get(f"{API}/patients/{pid}/timeline", params={"types": "EVOLUCAO"}).json()
    assert [e["source_id"] for e in timeline["items"]] == [eid]
    assert timeline["items"][0]["title"] == "Evolução clínica — Enf. Evolução (fictícia)"
    audit = client.get(f"{API}/audit-events", params={"patient_id": pid}).json()
    assert "EVOLUCAO_ASSINADA" in {e["event_type"] for e in audit["items"]}
