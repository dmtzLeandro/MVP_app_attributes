def test_seed_attribute_definitions(client, admin_headers):
    r = client.post("/admin/attributes/seed", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "ancho_cm" in data.get("seeded", [])
    assert "composicion" in data.get("seeded", [])
