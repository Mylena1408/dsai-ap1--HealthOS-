from datetime import datetime, timedelta
import uuid

import pytest

API = "/api/v1"


@pytest.fixture(scope="module")
def patient(client):
    response = client.post(f"{API}/admin/patients/", json={
        "full_name": "Paciente Exames (fictício)", "cpf": "28625587887", "birth_date": "1975-05-05", "gender": "Outro"})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="module")
def validator(client):
    return client.post(f"{API}/professionals", json={
        "full_name": "Biomédico Validador (fictício)", "professional_type": "OUTRO",
        "registry_number": "CRBM-T 77"}).json()


def test_catalog_is_available_at_startup(client):
    exam_types = client.get(f"{API}/exam-types").json()
    codes = {t["code"] for t in exam_types}
    assert {"HEMO", "GLI", "LIPID", "TG", "CREA", "UREIA", "TSH", "T4L", "VITD"} <= codes
    hemo = next(t for t in exam_types if t["code"] == "HEMO")
    assert [a["code"] for a in hemo["analytes"]] == ["HB", "HT", "LEUCO", "PLAQ"]
    assert hemo["analytes"][0]["reference"] == "12–16 g/dL"
    assert len(client.get(f"{API}/laboratories").json()) == 2


def test_vital_signs_over_http(client, patient):
    pid = patient["id"]
    yesterday = (datetime.now() - timedelta(days=1)).isoformat(timespec="minutes")
    first = client.post(f"{API}/patients/{pid}/vital-signs", json={
        "recorded_at": yesterday, "height_cm": 160, "weight_kg": 64, "temperature": 36.6})
    assert first.status_code == 201 and first.json()["bmi"] == 25.0
    second = client.post(f"{API}/patients/{pid}/vital-signs", json={"oxygen_saturation": 89, "heart_rate": 110})
    assert second.json()["flags"] == {"heart_rate": "ALTO", "oxygen_saturation": "CRITICO_BAIXO"}

    assert client.post(f"{API}/patients/{pid}/vital-signs", json={}).status_code == 400
    assert client.post(f"{API}/patients/{pid}/vital-signs", json={"heart_rate": "rápido"}).status_code == 422
    assert client.get(f"{API}/patients/{pid}/vital-signs").json()["total"] == 2

    summary = client.get(f"{API}/patients/{pid}/vital-signs/summary").json()
    assert summary["records"] == 2 and "educacionais" in summary["disclaimer"]
    assert {m["metric"] for m in summary["metrics"]} >= {"bmi", "temperature", "oxygen_saturation"}


def test_exam_lifecycle_over_http(client, patient, validator):
    tsh = next(t for t in client.get(f"{API}/exam-types").json() if t["code"] == "TSH")
    exam = client.post(f"{API}/exam-requests", json={"patient_id": patient["id"], "exam_type_id": tsh["id"]})
    assert exam.status_code == 201
    eid = exam.json()["id"]

    assert client.post(f"{API}/exam-requests/{eid}/start-processing").status_code == 409
    tomorrow = (datetime.now() + timedelta(days=1)).isoformat(timespec="minutes")
    assert client.post(f"{API}/exam-requests/{eid}/schedule", json={"scheduled_for": tomorrow}).json()["status"] == "AGENDADO"
    assert client.post(f"{API}/exam-requests/{eid}/collect").json()["sample_code"].startswith("AM")
    client.post(f"{API}/exam-requests/{eid}/start-processing")
    assert client.post(f"{API}/exam-requests/{eid}/results", json={"values": {"TSH": 9999}}).status_code == 400
    resulted = client.post(f"{API}/exam-requests/{eid}/results", json={"values": {"TSH": 6.25}}).json()
    assert resulted["results"][0]["flag"] == "ALTO"
    client.post(f"{API}/exam-requests/{eid}/validate", json={"professional_id": validator["id"]})
    released = client.post(f"{API}/exam-requests/{eid}/release").json()
    assert released["status"] == "LIBERADO" and released["allowed_transitions"] == []
    assert client.post(f"{API}/exam-requests/{eid}/cancel", json={"reason": "tarde demais"}).status_code == 409

    history = client.get(f"{API}/patients/{patient['id']}/exams/analytes/TSH/history").json()
    assert [p[1] for p in history["points"]] == [6.25]

    listed = client.get(f"{API}/exam-requests", params={"patient_id": patient["id"], "status": "LIBERADO"}).json()
    assert listed["total"] == 1 and listed["items"][0]["exam_code"] == "TSH"


def test_laboratory_not_found_and_validation(client, patient):
    assert client.get(f"{API}/exam-requests/{uuid.uuid4()}").status_code == 404
    assert client.post(f"{API}/exam-requests", json={
        "patient_id": patient["id"], "exam_type_id": str(uuid.uuid4())}).status_code == 404
    assert client.get(f"{API}/exam-requests", params={"status": "PERDIDO"}).status_code == 422


def test_vitals_and_exams_appear_in_the_timeline(client, patient):
    events = client.get(f"{API}/patients/{patient['id']}/timeline", params={"types": ["SINAIS_VITAIS", "EXAME"]}).json()
    titles = [e["title"] for e in events["items"]]
    assert "Resultado liberado: TSH" in titles and "Exame solicitado: TSH" in titles
    released = next(e for e in events["items"] if e["title"] == "Resultado liberado: TSH")
    assert released["status"] == "ALTERADO" and "TSH: 6.25" in released["description"]
    vitals = [e for e in events["items"] if e["event_type"] == "SINAIS_VITAIS"]
    # IMC 25,0 já é sobrepeso e SpO₂ 89% é crítica: os dois registros aparecem como alterados.
    assert [v["status"] for v in vitals] == ["ALTERADO", "ALTERADO"]
    assert any("SpO₂ 89 %" in v["description"] for v in vitals)
