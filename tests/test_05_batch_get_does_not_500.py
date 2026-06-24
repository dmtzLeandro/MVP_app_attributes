def test_batch_get_does_not_500(client, store_id, admin_headers):
    client.post("/admin/attributes/seed", headers=admin_headers)

    payload = {"mode": "get", "product_ids": ["p1", "p2"]}
    r = client.post(
        "/admin/products/attributes/batch",
        json=payload,
        headers=admin_headers,
    )

    assert r.status_code != 500
