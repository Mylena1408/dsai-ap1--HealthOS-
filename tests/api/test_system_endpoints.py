def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_status_reports_database(client):
    body = client.get("/status").json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"
    assert body["database"]["dialect"] == "sqlite"
    assert body["database"]["records"]["users"] >= 1  # médico de demonstração


def test_metrics_use_route_templates(client):
    client.get("/api/v1/admin/patients/00000000-0000-4000-8000-000000000000")
    routes = client.get("/metrics").json()["routes"]
    key = "GET /api/v1/admin/patients/{patient_id}"
    assert key in routes
    assert routes[key]["status_codes"].get("404", 0) >= 1
    # Nenhuma métrica deve ser criada com o UUID literal na chave.
    assert not any("00000000-0000" in route for route in routes)


def test_frontend_pages_and_static_files(client):
    assert client.get("/app/status").status_code == 200
    assert client.get("/app/inexistente").status_code == 404
    assert client.get("/app/..%2Fmain").status_code in (404, 422)
    script = client.get("/static/js/pages/portal.js")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]


def test_portal_has_no_inline_handlers(client):
    html = client.get("/").text
    assert "onclick=" not in html
    assert '/static/js/pages/portal.js' in html


def test_legacy_routes_are_marked_in_swagger(client):
    paths = client.get("/openapi.json").json()["paths"]
    legacy = [
        ("/api/v1/billing/invoices", "post"), ("/api/v1/billing/invoices/{invoice_id}/charges", "post"),
        ("/api/v1/billing/invoices/{invoice_id}/finalize", "post"), ("/api/v1/billing/invoices/{invoice_id}/pay", "post"),
        ("/api/v1/pharmacy/dispense/{medication_id}/{location_id}", "post"), ("/api/v1/notifications/send", "post"),
        ("/api/v1/notifications/me", "get"), ("/api/v1/notifications/{notification_id}/read", "patch"),
    ]
    for path, method in legacy:
        assert paths[path][method]["description"].startswith("Legado:"), (path, method)
    # A listagem nova do Financeiro, no mesmo caminho, não é legado.
    assert not paths["/api/v1/billing/invoices"]["get"].get("description", "").startswith("Legado:")
