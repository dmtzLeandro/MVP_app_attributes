def test_batch_get_does_not_500(client, store_id):
    # seed defs para evitar FK si algo intenta escribir (no debería en get, pero es seguro)
    client.post("/admin/attributes/seed")

    payload = {"mode": "get", "store_id": store_id, "product_ids": ["p1", "p2"]}
    r = client.post("/admin/products/attributes/batch", json=payload)

    # Lo mínimo: no debe explotar en 500
    assert r.status_code != 500
