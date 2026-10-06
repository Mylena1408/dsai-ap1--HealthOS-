API = "/api/v1"


def test_global_search_over_http(client):
    patient = client.post(f"{API}/admin/patients/", json={
        "full_name": "Zuleica Busca Global (fictícia)", "cpf": "84621357964", "birth_date": "1977-07-07",
        "gender": "Outro"}).json()

    by_name = client.get(f"{API}/search", params={"q": "zuleica"}).json()
    patients = next(g for g in by_name["groups"] if g["key"] == "pacientes")
    assert patients["total"] == 1 and patients["items"][0]["link"] == f"/app/prontuario?patient={patient['id']}"
    assert "84621357964" not in str(by_name) and "***.213.579-**" in patients["items"][0]["subtitle"]

    by_cpf = client.get(f"{API}/search", params={"q": "213.579"}).json()  # pontuação é ignorada no CPF
    assert any(i["title"].startswith("Zuleica") for g in by_cpf["groups"] for i in g["items"])

    assert client.get(f"{API}/search", params={"q": "%%"}).json()["groups"] == []  # curingas não casam tudo
    reports = client.get(f"{API}/search", params={"q": "auditoria"}).json()
    assert {"key": "relatorios"}.items() <= reports["groups"][-1].items()


def test_search_validation(client):
    assert client.get(f"{API}/search", params={"q": "a"}).status_code == 400
    assert client.get(f"{API}/search").status_code == 422
    assert client.get(f"{API}/search", params={"q": "x" * 81}).status_code == 422
    assert client.get(f"{API}/search", params={"q": "ab", "per_group": 50}).status_code == 422
