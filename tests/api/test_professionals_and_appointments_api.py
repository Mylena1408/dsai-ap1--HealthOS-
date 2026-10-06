from datetime import date, datetime, timedelta
import uuid

import pytest

API = "/api/v1"
ALL_DAY = [{"weekday": d, "start_time": "00:00", "end_time": "23:59"} for d in range(7)]


@pytest.fixture(scope="module")
def setup(client):
    department = client.post(f"{API}/departments", json={"name": "Pediatria (teste API)"}).json()
    specialty = client.post(f"{API}/specialties", json={"name": "Pediatria Geral (teste API)",
                                                         "default_duration_minutes": 20}).json()
    professional = client.post(f"{API}/professionals", json={
        "full_name": "Dra. Ana Teste (fictícia)", "professional_type": "MEDICO",
        "registry_number": "CRM-PA 99001", "department_id": department["id"],
        "specialty_id": specialty["id"], "email": "ana.teste@example.com", "working_hours": ALL_DAY,
    })
    assert professional.status_code == 201, professional.text
    patient = client.post(f"{API}/admin/patients/", json={
        "full_name": "Paciente API (fictício)", "cpf": "11144477735", "birth_date": "2015-03-03", "gender": "Outro",
    }).json()
    return {"department": department, "specialty": specialty, "professional": professional.json(), "patient": patient}


def tomorrow_at(hour: int, minute: int = 0) -> str:
    return datetime.combine(date.today() + timedelta(days=1), datetime.min.time()).replace(
        hour=hour, minute=minute).isoformat()


def test_professional_registration_and_search(client, setup):
    prof = setup["professional"]
    assert prof["department_name"] == "Pediatria (teste API)"
    assert prof["specialty_name"] == "Pediatria Geral (teste API)"
    assert len(prof["working_hours"]) == 7

    page = client.get(f"{API}/professionals", params={"q": "ana teste", "professional_type": "MEDICO"}).json()
    assert page["total"] == 1 and page["items"][0]["id"] == prof["id"]
    assert client.get(f"{API}/professionals", params={"status": "AFASTADO", "q": "ana teste"}).json()["total"] == 0

    duplicated = client.post(f"{API}/professionals", json={
        "full_name": "Outra", "professional_type": "MEDICO", "registry_number": "CRM-PA 99001"})
    assert duplicated.status_code == 409
    assert client.get(f"{API}/professionals/{uuid.uuid4()}").status_code == 404
    assert client.post(f"{API}/professionals", json={
        "full_name": "Tipo inválido", "professional_type": "ASTRONAUTA", "registry_number": "X-1"}).status_code == 422


def test_working_hours_validation(client, setup):
    prof_id = setup["professional"]["id"]
    overlapping = [{"weekday": 0, "start_time": "08:00", "end_time": "12:00"},
                   {"weekday": 0, "start_time": "11:00", "end_time": "13:00"}]
    assert client.put(f"{API}/professionals/{prof_id}/working-hours", json=overlapping).status_code == 400
    assert client.put(f"{API}/professionals/{prof_id}/working-hours", json=ALL_DAY).status_code == 200


def test_appointment_lifecycle_over_http(client, setup):
    body = {"patient_id": setup["patient"]["id"], "professional_id": setup["professional"]["id"],
            "start_time": tomorrow_at(9), "appointment_type": "PRIMEIRA_CONSULTA", "reason": "Rotina"}
    created = client.post(f"{API}/appointments", json=body)
    assert created.status_code == 201, created.text
    appt = created.json()
    assert appt["duration_minutes"] == 20
    assert appt["allowed_transitions"] == ["CONFIRMADA", "CANCELADA"]

    assert client.post(f"{API}/appointments", json={**body, "start_time": tomorrow_at(9, 10)}).status_code == 409
    assert client.post(f"{API}/appointments/{appt['id']}/no-show").status_code == 400  # ainda não chegou a hora
    assert client.post(f"{API}/appointments/{appt['id']}/start").status_code == 409    # precisa confirmar antes

    confirmed = client.post(f"{API}/appointments/{appt['id']}/confirm").json()
    assert confirmed["status"] == "CONFIRMADA"
    assert client.post(f"{API}/appointments/{appt['id']}/start").status_code == 400    # cedo demais
    assert client.post(f"{API}/appointments/{appt['id']}/confirm").status_code == 409

    moved = client.post(f"{API}/appointments/{appt['id']}/reschedule", json={"start_time": tomorrow_at(15)}).json()
    assert moved["status"] == "AGENDADA" and moved["start_time"].startswith(tomorrow_at(15)[:16])

    assert client.post(f"{API}/appointments/{appt['id']}/cancel", json={"reason": ""}).status_code == 422
    cancelled = client.post(f"{API}/appointments/{appt['id']}/cancel", json={"reason": "Imprevisto fictício"}).json()
    assert cancelled["status"] == "CANCELADA"
    assert cancelled["allowed_transitions"] == []
    assert [h["to_status"] for h in cancelled["history"]] == ["AGENDADA", "CONFIRMADA", "AGENDADA", "CANCELADA"]

    assert client.post(f"{API}/appointments/{appt['id']}/start").status_code == 409  # Cancelada -> Em andamento


def test_listing_filters_and_availability(client, setup):
    prof_id = setup["professional"]["id"]
    client.post(f"{API}/appointments", json={"patient_id": setup["patient"]["id"], "professional_id": prof_id,
                                             "start_time": tomorrow_at(10)})

    page = client.get(f"{API}/appointments", params={"professional_id": prof_id, "status": ["AGENDADA", "CONFIRMADA"]}).json()
    assert page["total"] == 1 and page["items"][0]["patient_name"] == "Paciente API (fictício)"
    assert client.get(f"{API}/appointments", params={"status": "INVALIDO"}).status_code == 422

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    slots = client.get(f"{API}/professionals/{prof_id}/availability",
                       params={"date_from": tomorrow, "days": 1, "duration_minutes": 30}).json()
    starts = {s["start_time"][11:16] for s in slots}
    assert "10:00" not in starts and "10:30" in starts
    assert client.get(f"{API}/professionals/{prof_id}/availability", params={"days": 40}).status_code == 422


def test_booking_unknown_patient_returns_404(client, setup):
    response = client.post(f"{API}/appointments", json={
        "patient_id": str(uuid.uuid4()), "professional_id": setup["professional"]["id"], "start_time": tomorrow_at(11)})
    assert response.status_code == 404
