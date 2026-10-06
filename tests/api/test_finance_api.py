import uuid

import pytest

API = "/api/v1"


@pytest.fixture(scope="module")
def patient(client):
    response = client.post(f"{API}/admin/patients/", json={
        "full_name": "Paciente Financeiro (fictício)", "cpf": "62840195720", "birth_date": "1985-02-02",
        "gender": "Outro", "insurance_provider": "Convênio Fictício API"})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="module")
def released_exam(client, patient):
    glicemia = next(t for t in client.get(f"{API}/exam-types").json() if t["code"] == "GLI")
    validator = client.post(f"{API}/professionals", json={
        "full_name": "Validador Financeiro (fictício)", "professional_type": "OUTRO",
        "registry_number": "CRBM-FIN 1"}).json()
    eid = client.post(f"{API}/exam-requests", json={"patient_id": patient["id"], "exam_type_id": glicemia["id"]}).json()["id"]
    client.post(f"{API}/exam-requests/{eid}/collect")
    client.post(f"{API}/exam-requests/{eid}/start-processing")
    client.post(f"{API}/exam-requests/{eid}/results", json={"values": {"GLI": 92}})
    client.post(f"{API}/exam-requests/{eid}/validate", json={"professional_id": validator["id"]})
    assert client.post(f"{API}/exam-requests/{eid}/release").json()["status"] == "LIBERADO"
    return eid


def test_price_table(client):
    prices = {p["code"]: p for p in client.get(f"{API}/billing/prices").json()}
    assert prices["EXAME-GLI"]["price"] == "15.00" and prices["CONSULTA-RETORNO"]["billing_type"] == "CONSULTA"


def test_invoice_from_services_payments_and_listing(client, patient, released_exam):
    pid = patient["id"]
    unbilled = client.get(f"{API}/billing/patients/{pid}/unbilled").json()
    assert [(s["source_type"], s["source_id"], s["price"]) for s in unbilled] == [("EXAME", released_exam, "15.00")]

    ref = [{"source_type": "EXAME", "source_id": released_exam}]
    created = client.post(f"{API}/billing/patients/{pid}/invoices", json={
        "services": ref, "insurance_provider": "Convênio Fictício API", "coverage_percentage": "60", "issue": False})
    assert created.status_code == 201, created.text
    invoice = created.json()
    assert invoice["status"] == "RASCUNHO" and invoice["allowed_actions"] == ["emitir", "cancelar"]
    assert (invoice["insurance_share"], invoice["patient_share"]) == ("9.00", "6.00")
    assert client.post(f"{API}/billing/patients/{pid}/invoices", json={"services": ref}).status_code == 409
    assert client.get(f"{API}/billing/patients/{pid}/unbilled").json() == []

    iid = invoice["id"]
    assert client.post(f"{API}/billing/invoices/{iid}/payments", json={"amount": "1", "method": "PIX"}).status_code == 409
    issued = client.post(f"{API}/billing/invoices/{iid}/issue").json()
    assert issued["status"] == "PENDENTE" and issued["due_date"]

    payment = client.post(f"{API}/billing/invoices/{iid}/payments", json={"amount": "9.00", "method": "CONVENIO"})
    assert payment.status_code == 201 and payment.json()["status"] == "PARCIALMENTE_PAGO"
    assert client.post(f"{API}/billing/invoices/{iid}/payments", json={"amount": "7", "method": "PIX"}).status_code == 400
    assert client.post(f"{API}/billing/invoices/{iid}/payments", json={"amount": "-1", "method": "PIX"}).status_code == 422
    assert client.post(f"{API}/billing/invoices/{iid}/payments",
                       json={"amount": "6", "method": "NAO_INFORMADO"}).status_code == 422
    assert client.post(f"{API}/billing/invoices/{iid}/cancel", json={"reason": "tarde"}).status_code == 400
    paid = client.post(f"{API}/billing/invoices/{iid}/payments", json={"amount": "6.00", "method": "PIX"}).json()
    assert paid["status"] == "PAGO" and paid["balance"] == "0.00" and len(paid["payments"]) == 2

    listed = client.get(f"{API}/billing/invoices", params={"patient_id": pid}).json()
    assert listed["total"] == 1 and listed["items"][0]["number"] == invoice["number"]
    assert client.get(f"{API}/billing/invoices", params={"patient_id": pid, "status": "PENDENTE"}).json()["total"] == 0
    assert client.get(f"{API}/billing/invoices", params={"number": invoice["number"][-6:]}).json()["total"] == 1
    assert client.get(f"{API}/billing/invoices", params={"start": "2026-10-02", "end": "2026-10-01"}).status_code == 400

    # O resumo antigo (portal) continua mostrando só faturas com valor a receber.
    assert client.get(f"{API}/billing/patients/{pid}/summary").json() == []


def test_cancel_and_not_found(client):
    other = client.post(f"{API}/admin/patients/", json={
        "full_name": "Paciente Cancelamento (fictício)", "cpf": "73159628400", "birth_date": "1990-01-01",
        "gender": "Outro"}).json()
    legacy = client.post(f"{API}/billing/invoices", json={"patient_id": other["id"], "invoice_number": "INV-API-CANCEL"}).json()
    client.post(f"{API}/billing/invoices/{legacy['id']}/charges", json={
        "description": "Consulta", "billing_type": "CONSULTA", "quantity": "1", "unit_price": "100"})
    assert client.post(f"{API}/billing/invoices/{legacy['id']}/cancel", json={"reason": ""}).status_code == 422
    cancelled = client.post(f"{API}/billing/invoices/{legacy['id']}/cancel", json={"reason": "Lançamento de teste"}).json()
    assert cancelled["status"] == "CANCELADO" and cancelled["cancellation_reason"] == "Lançamento de teste"
    assert client.post(f"{API}/billing/invoices/{legacy['id']}/issue").status_code == 409

    assert client.get(f"{API}/billing/invoices/{uuid.uuid4()}").status_code == 404
    assert client.get(f"{API}/billing/patients/{uuid.uuid4()}/unbilled").status_code == 404


def test_summary_over_http(client):
    summary = client.get(f"{API}/billing/summary").json()
    assert {"invoiced", "received", "receivable", "overdue", "monthly"} <= summary.keys()
    assert len(summary["monthly"]) == 6 and "fictícios" in summary["disclaimer"]
    assert client.get(f"{API}/billing/summary", params={"start": "2026-10-05", "end": "2026-10-01"}).status_code == 400
