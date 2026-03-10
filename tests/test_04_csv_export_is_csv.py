def test_csv_export_is_csv(client, store_id, admin_headers):
    r = client.get(
        "/admin/export/csv", params={"store_id": store_id}, headers=admin_headers
    )
    assert r.status_code == 200
    assert "text/csv" in (r.headers.get("content-type") or "")
