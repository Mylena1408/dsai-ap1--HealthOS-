API = "/api/v1"


def test_catalog(client):
    catalog = {r["key"]: r for r in client.get(f"{API}/reports").json()}
    assert set(catalog) == {"consultas", "exames", "dispensacoes", "estoque", "faturas", "auditoria"}
    assert catalog["estoque"]["uses_period"] is False
    assert "ATRASADO" in catalog["faturas"]["status_options"]
    assert catalog["faturas"]["status_labels"]["ATRASADO"] == "Em atraso"
    assert catalog["faturas"]["columns"][5] == {"key": "gross_total", "label": "Total", "kind": "moeda"}


def test_formats_over_http(client):
    params = {"start": "2026-01-01", "end": "2026-12-31"}
    report = client.get(f"{API}/reports/auditoria", params=params).json()
    assert report["start"] == "2026-01-01" and report["end"] == "2026-12-31" and not report["truncated"]
    assert "fictícios" in report["disclaimer"]

    csv = client.get(f"{API}/reports/auditoria", params={**params, "format": "csv"})
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert csv.headers["content-disposition"] == 'attachment; filename="healthos_auditoria_20260101-20261231.csv"'
    assert csv.content.decode("utf-8-sig").startswith("Data;Evento;Entidade;Resumo")

    pdf = client.get(f"{API}/reports/estoque", params={"format": "pdf"})
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")

    # Cada exportação fica na trilha de auditoria.
    exported = client.get(f"{API}/audit-events", params={"event_type": "RELATORIO_EXPORTADO", "limit": 5}).json()
    assert {e["data"]["format"] for e in exported["items"]} >= {"csv", "pdf"}


def test_report_errors(client):
    assert client.get(f"{API}/reports/inexistente").status_code == 404
    assert client.get(f"{API}/reports/consultas", params={"format": "xlsx"}).status_code == 422
    assert client.get(f"{API}/reports/consultas", params={"start": "2026-13-01"}).status_code == 422
    assert client.get(f"{API}/reports/consultas", params={"start": "2026-10-02", "end": "2026-10-01"}).status_code == 400
    assert client.get(f"{API}/reports/consultas", params={"start": "2024-01-01", "end": "2026-01-01"}).status_code == 400
    assert client.get(f"{API}/reports/consultas", params={"status": "PAGO"}).status_code == 400
