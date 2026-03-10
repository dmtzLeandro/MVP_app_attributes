def test_validation_error_schema(client, admin_headers):
    r = client.post(
        "/admin/products/attributes/batch",
        json={"nope": True},
        headers=admin_headers,
    )
    assert r.status_code == 422
    data = r.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
