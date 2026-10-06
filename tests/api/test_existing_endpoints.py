"""Regressão dos endpoints que já existiam antes da expansão.

Estes testes garantem a regra de compatibilidade: cada novo módulo deve manter
estes fluxos respondendo exatamente como antes.
"""
import uuid

import pytest

API = "/api/v1"


@pytest.fixture(scope="module")
def patient_id(client):
    response = client.post(f"{API}/admin/patients/", json={
        "full_name": "Maria Silva (fictícia)", "cpf": "39053344705",
        "birth_date": "1990-01-01", "gender": "Feminino",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_portal_and_docs_are_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_patient_crud(client, patient_id):
    duplicated = client.post(f"{API}/admin/patients/", json={
        "full_name": "Maria Silva (fictícia)", "cpf": "39053344705",
        "birth_date": "1990-01-01", "gender": "Feminino",
    })
    assert duplicated.status_code == 400

    assert any(p["id"] == patient_id for p in client.get(f"{API}/admin/patients/").json())
    updated = client.patch(f"{API}/admin/patients/{patient_id}", json={"phone": "(91) 90000-0000"})
    assert updated.status_code == 200
    assert updated.json()["phone"] == "(91) 90000-0000"
    assert client.get(f"{API}/admin/patients/{uuid.uuid4()}").status_code == 404


def test_patient_rejects_invalid_cpf(client):
    response = client.post(f"{API}/admin/patients/", json={
        "full_name": "CPF Inválido", "cpf": "11111111111", "birth_date": "1990-01-01", "gender": "Outro",
    })
    assert response.status_code == 400


def test_list_users_includes_demo_doctor(client):
    response = client.get(f"{API}/admin/users/")
    assert response.status_code == 200
    assert any(u["email"] == "medico.demo@healthos.local" for u in response.json())


def test_booking_flow(client, patient_id):
    slots = client.get(f"{API}/clinical/availability").json()
    assert slots, "o startup deve criar horários de demonstração"
    slot_id = slots[0]["id"]

    booked = client.post(f"{API}/clinical/schedule", json={"slot_id": slot_id, "patient_id": patient_id})
    assert booked.status_code == 201
    assert booked.json()["status"] == "BOOKED"

    again = client.post(f"{API}/clinical/schedule", json={"slot_id": slot_id, "patient_id": patient_id})
    assert again.status_code == 400

    appointments = client.get(f"{API}/clinical/patients/{patient_id}/appointments").json()
    assert [a["id"] for a in appointments] == [slot_id]


def test_clinical_note_becomes_immutable(client, patient_id):
    doctor_id = client.get(f"{API}/clinical/availability").json()[0]["doctor_id"]
    note = client.post(f"{API}/clinical/notes", json={
        "patient_id": patient_id, "doctor_id": doctor_id, "content": "Evolução fictícia de teste.",
    })
    assert note.status_code == 201
    note_id = note.json()["id"]

    edited = client.patch(f"{API}/clinical/notes/{note_id}", json={"content": "Evolução fictícia revisada."})
    assert edited.json()["version"] == 2
    assert client.patch(f"{API}/clinical/notes/{note_id}/finalize").json()["status"] == "FINALIZED"
    assert client.patch(f"{API}/clinical/notes/{note_id}", json={"content": "Edição proibida aqui."}).status_code == 400

    history = client.get(f"{API}/clinical/patients/{patient_id}/history").json()
    assert note_id in [n["id"] for n in history]


def test_patient_alerts(client, patient_id):
    created = client.post(f"{API}/admin/alerts/", json={
        "patient_id": patient_id, "alert_type": "ALLERGY", "severity": "HIGH", "description": "Alergia fictícia",
    })
    assert created.status_code == 201
    active = client.get(f"{API}/admin/alerts/patient/{patient_id}/active").json()
    assert created.json()["id"] in [a["id"] for a in active]


def test_pharmacy_stock_and_dispense(client):
    med = client.post(f"{API}/pharmacy/medications", json={
        "name": "Medicamento Demo", "generic_name": "Genérico Demo", "dosage": "500mg", "unit": "COMPRIMIDO",
    })
    assert med.status_code == 201
    med_id = med.json()["id"]

    assert client.post(f"{API}/pharmacy/inventory/{med_id}/FARMACIA", json={"quantity": 12}).status_code == 201
    assert client.post(f"{API}/pharmacy/inventory/{med_id}/FARMACIA", json={"quantity": 3}).json()["quantity"] == 15
    dispensed = client.post(f"{API}/pharmacy/dispense/{med_id}/FARMACIA", json={"quantity": 6})
    assert dispensed.status_code == 200
    assert dispensed.json()["quantity"] == 9

    too_much = client.post(f"{API}/pharmacy/dispense/{med_id}/FARMACIA", json={"quantity": 100})
    assert too_much.status_code == 400

    critical = client.get(f"{API}/pharmacy/critical-stock").json()
    assert med_id in [item["medication_id"] for item in critical]


def test_billing_flow(client, patient_id):
    invoice = client.post(f"{API}/billing/invoices", json={
        "patient_id": patient_id, "invoice_number": "INV-TEST-1", "insurance_coverage": "80",
    })
    assert invoice.status_code == 201
    invoice_id = invoice.json()["id"]

    assert client.post(f"{API}/billing/invoices/{invoice_id}/finalize").status_code == 400  # sem itens
    charge = client.post(f"{API}/billing/invoices/{invoice_id}/charges", json={
        "description": "Consulta", "billing_type": "CONSULTA", "quantity": "1", "unit_price": "200",
    })
    assert charge.status_code == 200
    assert client.post(f"{API}/billing/invoices/{invoice_id}/finalize").json()["status"] == "PENDENTE"

    summary = client.get(f"{API}/billing/patients/{patient_id}/summary").json()
    assert float(summary[0]["patient_share"]) == pytest.approx(40.0)


def test_notifications(client, patient_id):
    sent = client.post(f"{API}/notifications/send", json={
        "patient_id": patient_id, "type": "LEMBRETE_CONSULTA", "title": "Lembrete", "message": "Consulta amanhã",
    })
    assert sent.status_code == 201
    notification_id = sent.json()["id"]
    assert notification_id in [n["id"] for n in client.get(f"{API}/notifications/me", params={"patient_id": patient_id}).json()]

    assert client.patch(f"{API}/notifications/{notification_id}/read").status_code == 200
    assert client.get(f"{API}/notifications/me", params={"patient_id": patient_id}).json() == []

    no_recipient = client.post(f"{API}/notifications/send", json={"type": "LEMBRETE_CONSULTA", "title": "x", "message": "y"})
    assert no_recipient.status_code == 400
