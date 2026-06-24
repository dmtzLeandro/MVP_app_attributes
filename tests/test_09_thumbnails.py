import asyncio
import hashlib
import hmac
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.testclient import TestClient

from app.admin_api import routes_products
from app.core import thumb_sign
from app.db.deps import get_db
from app.services import thumbnails


@pytest.fixture(scope="session", autouse=True)
def _migrate_db() -> None:
    """Thumbnail unit tests do not require the shared PostgreSQL fixture."""


@pytest.fixture()
def signing_secret(monkeypatch):
    monkeypatch.setattr(
        thumb_sign.settings,
        "THUMB_SIGNING_SECRET",
        "thumbnail-test-secret",
    )


def test_v1_signature_is_stable_and_bound_to_all_parameters(signing_secret):
    params = {
        "store_id": "store-1",
        "product_id": "product-1",
        "v": "image-version",
        "size": 96,
    }

    signature = thumb_sign.sign_thumb(**params)

    assert signature == thumb_sign.sign_thumb(**params)
    assert signature.startswith("v1.")
    assert thumb_sign.verify_thumb_sig(**params, sig=signature) is True
    assert (
        thumb_sign.verify_thumb_sig(
            **{**params, "product_id": "product-2"}, sig=signature
        )
        is False
    )
    assert (
        thumb_sign.verify_thumb_sig(**{**params, "v": "other"}, sig=signature)
        is False
    )
    assert (
        thumb_sign.verify_thumb_sig(**{**params, "size": 128}, sig=signature)
        is False
    )


def test_legacy_signature_is_accepted_until_expiration(signing_secret, monkeypatch):
    now = 1_700_000_000
    expires_at = now + 60
    params = {
        "store_id": "store-1",
        "product_id": "product-1",
        "v": "image-version",
        "size": 96,
    }
    message = (
        f"{params['store_id']}:{params['product_id']}:"
        f"{params['v']}:{params['size']}:{expires_at}"
    ).encode("utf-8")
    digest = hmac.new(
        b"thumbnail-test-secret", message, hashlib.sha256
    ).hexdigest()
    signature = f"{expires_at}.{digest}"

    monkeypatch.setattr(thumb_sign.time, "time", lambda: now)
    assert thumb_sign.verify_thumb_sig(**params, sig=signature) is True

    monkeypatch.setattr(thumb_sign.time, "time", lambda: expires_at + 1)
    assert thumb_sign.verify_thumb_sig(**params, sig=signature) is False


def test_thumb_path_changes_with_image_version_and_size(monkeypatch, tmp_path):
    monkeypatch.setattr(thumbnails.settings, "THUMB_CACHE_DIR", str(tmp_path))

    first = thumbnails.thumb_path("store-1", "product-1", "version-1", 96)
    same = thumbnails.thumb_path("store-1", "product-1", "version-1", 96)
    other_version = thumbnails.thumb_path(
        "store-1", "product-1", "version-2", 96
    )
    other_size = thumbnails.thumb_path("store-1", "product-1", "version-1", 128)

    assert first == same
    assert first != other_version
    assert first != other_size


class _FakeDb:
    def __init__(self, product):
        self.product = product

    def get(self, _model, _key):
        return self.product


def _product(**overrides):
    values = {
        "is_active": True,
        "image_src": "https://cdn.example.test/product.jpg",
        "image_src_hash": "current-version",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _call_thumbnail(monkeypatch, product, **overrides):
    monkeypatch.setattr(routes_products, "verify_thumb_sig", lambda **_kwargs: True)
    params = {
        "store_id": "store-1",
        "product_id": "product-1",
        "size": 96,
        "v": "current-version",
        "sig": "v1.valid",
        "db": _FakeDb(product),
    }
    params.update(overrides)
    return asyncio.run(routes_products.product_thumbnail(**params))


@pytest.mark.parametrize(
    ("product", "version"),
    [
        (None, "current-version"),
        (_product(is_active=False), "current-version"),
        (_product(image_src=None), "current-version"),
        (_product(image_src_hash=None), "current-version"),
        (_product(), "stale-version"),
    ],
)
def test_thumbnail_rejects_unavailable_or_stale_product(
    monkeypatch, product, version
):
    response = _call_thumbnail(monkeypatch, product, v=version)

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_thumbnail_rejects_invalid_signature_without_cache(monkeypatch):
    monkeypatch.setattr(routes_products, "verify_thumb_sig", lambda **_kwargs: False)

    response = asyncio.run(
        routes_products.product_thumbnail(
            store_id="store-1",
            product_id="product-1",
            size=96,
            v="current-version",
            sig="invalid",
            db=_FakeDb(_product()),
        )
    )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_current_thumbnail_file_uses_immutable_cache(monkeypatch, tmp_path):
    thumbnail_file = tmp_path / "thumbnail.webp"
    thumbnail_file.write_bytes(b"webp")
    monkeypatch.setattr(routes_products, "thumb_path", lambda *_args: thumbnail_file)

    response = _call_thumbnail(monkeypatch, _product())

    assert isinstance(response, FileResponse)
    assert response.headers["cache-control"] == routes_products.THUMB_IMMUTABLE_CACHE


def test_generation_fallback_uses_short_public_cache(monkeypatch, tmp_path):
    missing_file = tmp_path / "missing.webp"
    monkeypatch.setattr(routes_products, "thumb_path", lambda *_args: missing_file)

    async def no_generated_thumbnail(**_kwargs):
        return None

    monkeypatch.setattr(
        routes_products,
        "ensure_thumbnail",
        no_generated_thumbnail,
    )

    response = _call_thumbnail(monkeypatch, _product())

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 307
    assert response.headers["cache-control"] == routes_products.THUMB_FALLBACK_CACHE


def test_thumbnail_size_is_bounded_before_endpoint_execution():
    test_app = FastAPI()
    test_app.include_router(routes_products.router)
    test_app.dependency_overrides[get_db] = lambda: _FakeDb(_product())

    with TestClient(test_app) as client:
        response = client.get(
            "/admin/products/product-1/thumbnail",
            params={
                "store_id": "store-1",
                "size": 1024,
                "v": "current-version",
                "sig": "invalid",
            },
        )

    assert response.status_code == 422
