from datetime import date, datetime, timedelta

import pytest

API = "/api/v1"
ALL_DAY = [{"weekday": d, "start_time": "00:00", "end_time": "23:59"} for d in range(7)]


@pytest.fixture(scope="module")
def actors(client):
    patient = client.post(f"{API}/admin/patients/", json={
        "full_name": "Paciente Eventos (fictício)", "cpf": "61238419020", "birth_date": "1988-08-08", "gender": "Outro"})
    assert patient.status_code == 201, patient.text
    doctor = client.post(f"{API}/professionals", json={
        "full_name": "Dr. Eventos", "professional_type": "MEDICO", "registry_number": "CRM-EV 1",
        "working_hours": ALL_DAY}).json()
    return {"patient": patient.json(), "doctor": doctor}


def inbox(client, **params):
    return client.get(f"{API}/inbox", params=params).json()


def test_patient_creation_is_audited(client, actors):
    page = client.get(f"{API}/audit-events", params={"patient_id": actors["patient"]["id"],
                                                     "event_type": "PACIENTE_CRIADO"}).json()
    assert page["total"] == 1 and "Paciente Eventos" in page["items"][0]["summary"]


def test_booking_notifies_patient_and_professional(client, actors):
    tomorrow = datetime.combine(date.today() + timedelta(days=1), datetime.min.time()).replace(hour=10)
    booked = client.post(f"{API}/appointments", json={
        "patient_id": actors["patient"]["id"], "professional_id": actors["doctor"]["id"],
        "start_time": tomorrow.isoformat()})
    assert booked.status_code == 201

    patient_inbox = inbox(client, audience="PACIENTE", recipient_id=actors["patient"]["id"])
    assert patient_inbox["items"][0]["title"] == "Consulta agendada"
    assert "Dr. Eventos" in patient_inbox["items"][0]["message"]
    doctor_inbox = inbox(client, audience="PROFISSIONAL", recipient_id=actors["doctor"]["id"])
    assert doctor_inbox["items"][0]["link"] == "/app/consultas"

    audit = client.get(f"{API}/audit-events", params={"entity_id": booked.json()["id"]}).json()
    assert [e["event_type"] for e in audit["items"]] == ["CONSULTA_AGENDADA"]


def test_exam_release_notifies_patient_and_requester(client, actors):
    tsh = next(t for t in client.get(f"{API}/exam-types").json() if t["code"] == "TSH")
    exam = client.post(f"{API}/exam-requests", json={
        "patient_id": actors["patient"]["id"], "exam_type_id": tsh["id"], "requested_by": actors["doctor"]["id"],
        "priority": "URGENTE"}).json()
    lab_inbox = inbox(client, audience="SETOR", sector="LABORATORIO")
    assert any(n["title"] == "Novo exame solicitado" and n["priority"] == "ALTA" for n in lab_inbox["items"])

    for step, body in (("collect", None), ("start-processing", None), ("results", {"values": {"TSH": 9.5}}),
                       ("validate", {"professional_id": actors["doctor"]["id"]}), ("release", None)):
        assert client.post(f"{API}/exam-requests/{exam['id']}/{step}", json=body).status_code == 200, step

    doctor_inbox = inbox(client, audience="PROFISSIONAL", recipient_id=actors["doctor"]["id"], category="EXAME")
    released = doctor_inbox["items"][0]
    assert released["priority"] == "ALTA" and "Fora da referência" in released["message"]
    assert inbox(client, audience="PACIENTE", recipient_id=actors["patient"]["id"],
                 category="EXAME")["items"][0]["title"] == "Resultado de exame disponível"


def test_inbox_actions_and_counts(client, actors):
    params = {"audience": "PACIENTE", "recipient_id": actors["patient"]["id"]}
    counts = client.get(f"{API}/inbox/counts", params=params).json()
    assert counts["unread"] >= 2 and counts["read"] == 0

    first = inbox(client, **params)["items"][0]["id"]
    assert client.post(f"{API}/inbox/{first}/read").json()["status"] == "LIDA"
    assert client.post(f"{API}/inbox/{first}/read").status_code == 409
    assert client.post(f"{API}/inbox/{first}/archive").json()["status"] == "ARQUIVADA"
    assert client.post(f"{API}/inbox/{first}/explode").status_code == 422

    updated = client.post(f"{API}/inbox/mark-all-read", params=params).json()["updated"]
    after = client.get(f"{API}/inbox/counts", params=params).json()
    assert after == {"unread": 0, "read": counts["unread"] - 1, "archived": 1} and updated == counts["unread"] - 1
    assert client.get(f"{API}/inbox", params={"audience": "SETOR"}).status_code == 400  # setor obrigatório


def test_alert_endpoints(client):
    rules = client.get(f"{API}/alerts/rules").json()
    assert {r["code"] for r in rules} >= {"ESTOQUE_BAIXO", "LOTE_VENCENDO", "EXAME_FORA_REFERENCIA",
                                         "SINAL_VITAL_CRITICO", "PACIENTE_SEM_ACOMPANHAMENTO"}
    report = client.post(f"{API}/alerts/evaluate").json()
    assert report["opened"] >= 1  # pelo menos o TSH fora da referência liberado acima
    assert client.post(f"{API}/alerts/evaluate", json={"rules": ["NAO_EXISTE"]}).status_code == 400

    page = client.get(f"{API}/alerts", params={"rule_code": "EXAME_FORA_REFERENCIA", "status": "ATIVO"}).json()
    alert = page["items"][0]
    assert client.post(f"{API}/alerts/{alert['id']}/acknowledge", json={"by": "Coordenação"}).json()["status"] == "RECONHECIDO"
    assert client.post(f"{API}/alerts/{alert['id']}/resolve", json={"note": "ok"}).status_code == 422
    resolved = client.post(f"{API}/alerts/{alert['id']}/resolve", json={"note": "Paciente contatado (fictício)"}).json()
    assert resolved["status"] == "RESOLVIDO"
    summary = client.get(f"{API}/alerts/summary").json()
    assert set(summary) == {"by_category", "by_level"}
    assert client.get(f"{API}/audit-events/counts").json()["ALERTA_RESOLVIDO"] >= 1
