def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_admin_catalog_requires_token(client):
    assert client.get("/api/v1/catalog/niches").status_code == 401


def test_catalog_and_dashboard_api(client, admin_headers):
    created = client.post(
        "/api/v1/catalog/niches",
        headers=admin_headers,
        json={"name": "Demo", "slug": "demo", "active": True, "sort_order": 0},
    )
    assert created.status_code == 201, created.text
    listed = client.get("/api/v1/catalog/niches", headers=admin_headers)
    assert [x["slug"] for x in listed.json()] == ["demo"]
    dashboard = client.get("/api/v1/dashboard/summary", headers=admin_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["niches"] == 1
