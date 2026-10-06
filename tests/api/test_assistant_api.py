import uuid

import pytest

API = "/api/v1"


@pytest.fixture(scope="module")
def patient(client):
    response = client.post(f"{API}/admin/patients/", json={
        "full_name": "Paciente Assistente (fictício)", "cpf": "51724638017", "birth_date": "1970-03-03",
        "gender": "Outro"})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="module")
def released_exam(client, patient):
    """Exame de TSH percorrendo o fluxo real do laboratório até a liberação."""
    tsh = next(t for t in client.get(f"{API}/exam-types").json() if t["code"] == "TSH")
    validator = client.post(f"{API}/professionals", json={
        "full_name": "Validador Assistente (fictício)", "professional_type": "OUTRO",
        "registry_number": "CRBM-IA 1"}).json()
    eid = client.post(f"{API}/exam-requests", json={"patient_id": patient["id"], "exam_type_id": tsh["id"]}).json()["id"]
    client.post(f"{API}/exam-requests/{eid}/collect")
    client.post(f"{API}/exam-requests/{eid}/start-processing")
    client.post(f"{API}/exam-requests/{eid}/results", json={"values": {"TSH": 6.25}})
    client.post(f"{API}/exam-requests/{eid}/validate", json={"professional_id": validator["id"]})
    assert client.post(f"{API}/exam-requests/{eid}/release").json()["status"] == "LIBERADO"
    return eid


def test_status_reports_demo_mode(client):
    status = client.get(f"{API}/ai/status").json()
    assert (status["provider"], status["model"], status["demo_mode"]) == ("demo", "regras-deterministicas", True)
    assert "As informações apresentadas são educacionais e não substituem avaliação profissional." in status["disclaimer"]


def test_summary_insights_and_exam_analysis(client, patient, released_exam):
    summary = client.post(f"{API}/ai/patients/{patient['id']}/summary")
    assert summary.status_code == 200 and summary.json()["feature"] == "RESUMO_PRONTUARIO"
    assert "Paciente" in summary.json()["text"] and summary.json()["disclaimer"].startswith("As informações")
    assert client.post(f"{API}/ai/patients/{patient['id']}/insights").json()["feature"] == "OBSERVACOES"

    analysis = client.post(f"{API}/ai/exams/{released_exam}/analysis").json()
    assert "TSH" in analysis["text"] and "fora da faixa" in analysis["text"]

    tsh = next(t for t in client.get(f"{API}/exam-types").json() if t["code"] == "TSH")
    pending = client.post(f"{API}/exam-requests", json={"patient_id": patient["id"], "exam_type_id": tsh["id"]}).json()
    assert client.post(f"{API}/ai/exams/{pending['id']}/analysis").status_code == 400  # só exames liberados

    assert client.post(f"{API}/ai/patients/{uuid.uuid4()}/summary").status_code == 404
    assert client.post(f"{API}/ai/exams/{uuid.uuid4()}/analysis").status_code == 404


def test_symptoms_orientation(client, patient):
    calm = client.post(f"{API}/ai/symptoms", json={"description": "Tosse há dois dias", "patient_id": patient["id"]})
    assert calm.status_code == 200 and calm.json()["urgent"] is False
    urgent = client.post(f"{API}/ai/symptoms", json={"description": "Dor no peito forte agora"}).json()
    assert urgent["urgent"] is True and "192" in urgent["text"]
    assert client.post(f"{API}/ai/symptoms", json={"description": "x"}).status_code == 422
    assert client.post(f"{API}/ai/symptoms", json={"description": "y" * 2001}).status_code == 422


def test_conversation_lifecycle(client, patient):
    created = client.post(f"{API}/conversations", json={"patient_id": patient["id"]})
    assert created.status_code == 201 and created.json()["status"] == "ATIVA"
    cid = created.json()["id"]

    exchange = client.post(f"{API}/conversations/{cid}/messages", json={"content": "Quais exames foram feitos?"})
    assert exchange.status_code == 201
    body = exchange.json()
    assert body["user_message"]["role"] == "USUARIO" and body["assistant_message"]["role"] == "ASSISTENTE"
    assert body["assistant_message"]["provider"] == "demo:regras-deterministicas"

    stored = client.get(f"{API}/conversations/{cid}").json()
    assert stored["title"] == "Quais exames foram feitos?" and len(stored["messages"]) == 2
    listed = client.get(f"{API}/conversations", params={"patient_id": patient["id"]}).json()
    assert listed["total"] == 1 and listed["items"][0]["messages"] == []

    assert client.post(f"{API}/conversations/{cid}/messages", json={"content": ""}).status_code == 422
    assert client.post(f"{API}/conversations/{cid}/archive").json()["status"] == "ARQUIVADA"
    assert client.post(f"{API}/conversations/{cid}/messages", json={"content": "Mais uma"}).status_code == 409
    archived = client.get(f"{API}/conversations", params={"patient_id": patient["id"], "status": "ARQUIVADA"}).json()
    assert archived["total"] == 1

    assert client.get(f"{API}/conversations/{uuid.uuid4()}").status_code == 404
    assert client.post(f"{API}/conversations", json={"patient_id": str(uuid.uuid4())}).status_code == 404
