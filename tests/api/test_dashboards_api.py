import uuid

API = "/api/v1"


def test_dashboards_respond_over_http(client):
    patient = client.post(f"{API}/admin/patients/", json={
        "full_name": "Paciente Painel (fictício)", "cpf": "84434895002", "birth_date": "1979-09-09",
        "gender": "Outro"}).json()
    score = client.get(f"{API}/patients/{patient['id']}/health-score").json()
    assert [c["key"] for c in score["components"]] == ["consultas", "exames", "medicamentos", "monitoramento",
                                                       "acompanhamento"]
    assert score["components"][0]["applicable"] is False  # sem consultas: não aplicável, não zero
    assert "demonstrativo" in score["disclaimer"]

    board = client.get(f"{API}/dashboards/patient/{patient['id']}").json()
    assert board["patient_name"] == "Paciente Painel (fictício)" and board["health_score"]["score"] == score["score"]

    professional = client.post(f"{API}/professionals", json={
        "full_name": "Dra. Painel", "professional_type": "MEDICO", "registry_number": "CRM-PAINEL 1"}).json()
    assert len(client.get(f"{API}/dashboards/professional/{professional['id']}").json()["daily_30d"]) == 30
    assert "items_below_minimum" in client.get(f"{API}/dashboards/pharmacy").json()
    admin = client.get(f"{API}/dashboards/admin").json()
    assert admin["counts"]["patients"] >= 1 and len(admin["new_patients_monthly"]) == 6

    assert client.get(f"{API}/patients/{uuid.uuid4()}/health-score").status_code == 404
    assert client.get(f"{API}/dashboards/professional/{uuid.uuid4()}").status_code == 404
