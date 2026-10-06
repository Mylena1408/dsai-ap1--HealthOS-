from datetime import date, timedelta
import uuid

import pytest

API = "/api/v1"
LOCATION = "FARMACIA_API"


@pytest.fixture(scope="module")
def setup(client):
    medication = client.post(f"{API}/pharmacy/medications", json={
        "name": "Losartana API", "generic_name": "Losartana potássica", "dosage": "50mg", "unit": "COMPRIMIDO"}).json()
    patient = client.post(f"{API}/admin/patients/", json={
        "full_name": "Paciente Prescrição API", "cpf": "15350946056", "birth_date": "1960-06-06", "gender": "Outro"}).json()
    doctor = client.post(f"{API}/professionals", json={
        "full_name": "Dra. Receita API", "professional_type": "MEDICO", "registry_number": "CRM-RX 1"}).json()
    pharmacist = client.post(f"{API}/professionals", json={
        "full_name": "Farm. API", "professional_type": "FARMACEUTICO", "registry_number": "CRF-RX 1"}).json()
    category = client.post(f"{API}/medication-categories", json={"name": "Anti-hipertensivos (API)"}).json()
    return dict(medication=medication, patient=patient, doctor=doctor, pharmacist=pharmacist, category=category)


def test_stock_lots_and_legacy_endpoints_coexist(client, setup):
    med_id = setup["medication"]["id"]
    expiration = (date.today() + timedelta(days=180)).isoformat()
    lot = client.post(f"{API}/stock/lots", json={"medication_id": med_id, "location": LOCATION,
                                                 "lot_number": "lz-01", "expiration_date": expiration, "quantity": 40})
    assert lot.status_code == 201 and lot.json()["lot_number"] == "LZ-01" and lot.json()["days_to_expire"] == 180

    # Endpoint legado continua funcionando sobre o mesmo total.
    legacy = client.post(f"{API}/pharmacy/dispense/{med_id}/{LOCATION}", json={"quantity": 5})
    assert legacy.status_code == 200 and legacy.json()["quantity"] == 35

    assert client.put(f"{API}/medications/{med_id}/details",
                      json={"category_id": setup["category"]["id"]}).status_code == 200
    overview = next(o for o in client.get(f"{API}/medications/stock", params={"q": "losartana api"}).json())
    assert overview["total_quantity"] == 35 and overview["category_name"] == "Anti-hipertensivos (API)"
    assert client.get(f"{API}/stock/lots", params={"expiring_within_days": 365, "medication_id": med_id}).json()["total"] == 1
    assert client.post(f"{API}/stock/lots", json={"medication_id": med_id, "location": LOCATION, "lot_number": "X",
                                                  "expiration_date": expiration, "quantity": 0}).status_code == 422


def test_prescription_and_dispensation_over_http(client, setup):
    med_id = setup["medication"]["id"]
    created = client.post(f"{API}/prescriptions", json={
        "patient_id": setup["patient"]["id"], "prescriber_id": setup["doctor"]["id"],
        "items": [{"medication_id": med_id, "dose": "1 comprimido", "frequency": "1x ao dia",
                   "duration_days": 30, "quantity": 30}]})
    assert created.status_code == 201, created.text
    prescription = created.json()
    assert prescription["items"][0]["medication_name"] == "Losartana API 50mg"
    item_id = prescription["items"][0]["id"]

    dispensed = client.post(f"{API}/dispensations", json={
        "prescription_id": prescription["id"], "pharmacist_id": setup["pharmacist"]["id"], "location": LOCATION,
        "items": [{"prescription_item_id": item_id, "quantity": 30}]})
    assert dispensed.status_code == 201, dispensed.text
    body = dispensed.json()
    assert body["prescription_status"] == "DISPENSADA" and sum(l["quantity"] for l in body["lines"]) == 30
    # Antes de dispensar, a saída legada de 5 unidades foi reconciliada contra o lote.
    assert client.get(f"{API}/stock/movements", params={"movement_type": "AJUSTE", "medication_id": med_id}).json()["total"] == 1

    insufficient = client.post(f"{API}/prescriptions", json={
        "patient_id": setup["patient"]["id"], "prescriber_id": setup["doctor"]["id"],
        "items": [{"medication_id": med_id, "dose": "1", "frequency": "1x", "duration_days": 5, "quantity": 50}]}).json()
    response = client.post(f"{API}/dispensations", json={
        "prescription_id": insufficient["id"], "pharmacist_id": setup["pharmacist"]["id"], "location": LOCATION,
        "items": [{"prescription_item_id": insufficient["items"][0]["id"], "quantity": 50}]})
    assert response.status_code == 409 and "insuficiente" in response.json()["detail"]

    medications = client.get(f"{API}/patients/{setup['patient']['id']}/medications").json()
    assert len(medications) == 2 and {m["status"] for m in medications} == {"EM_USO"}
    assert client.get(f"{API}/dispensations", params={"patient_id": setup["patient"]["id"]}).json()["total"] == 1


def test_item_actions_and_validation(client, setup):
    prescription = client.post(f"{API}/prescriptions", json={
        "patient_id": setup["patient"]["id"], "prescriber_id": setup["doctor"]["id"],
        "items": [{"medication_id": setup["medication"]["id"], "dose": "1", "frequency": "1x", "duration_days": 5,
                   "quantity": 5}]}).json()
    item_url = f"{API}/prescriptions/{prescription['id']}/items/{prescription['items'][0]['id']}"
    assert client.post(f"{item_url}/suspend", json={"reason": "Pressão baixa (fictício)"}).json()["items"][0]["status"] == "SUSPENSO"
    assert client.post(f"{item_url}/suspend", json={"reason": "De novo"}).status_code == 409
    assert client.post(f"{item_url}/resume").json()["items"][0]["status"] == "EM_USO"
    assert client.post(f"{item_url}/explode").status_code == 422
    assert client.post(f"{API}/prescriptions/{prescription['id']}/cancel", json={"reason": "Troca"}).json()["status"] == "CANCELADA"

    assert client.get(f"{API}/prescriptions/{uuid.uuid4()}").status_code == 404
    assert client.post(f"{API}/prescriptions", json={
        "patient_id": setup["patient"]["id"], "prescriber_id": setup["pharmacist"]["id"],
        "items": [{"medication_id": setup["medication"]["id"], "dose": "1", "frequency": "1x", "duration_days": 1,
                   "quantity": 1}]}).status_code == 400
    assert client.post(f"{API}/prescriptions", json={
        "patient_id": setup["patient"]["id"], "prescriber_id": setup["doctor"]["id"], "items": []}).status_code == 422


def test_prescriptions_and_dispensations_appear_in_the_timeline(client, setup):
    events = client.get(f"{API}/patients/{setup['patient']['id']}/timeline",
                        params={"types": ["PRESCRICAO", "DISPENSACAO"]}).json()["items"]
    dispensed = [e for e in events if e["event_type"] == "DISPENSACAO"]
    assert len(dispensed) == 1 and dispensed[0]["description"] == "Losartana API: 30"
    assert any("Losartana API — 1 comprimido, 1x ao dia" in e["description"] for e in events
               if e["event_type"] == "PRESCRICAO")
