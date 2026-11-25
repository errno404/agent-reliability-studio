"""Section-3 API hardening: request ids, caching, body limits, admin brute force, error defaults, paths, untrusted annotation."""

from __future__ import annotations

import pytest
from app import config
from app.config import REPO_ROOT
from app.main import create_app
from app.security import admin_fail_limiter
from fastapi.testclient import TestClient


@pytest.fixture
def api(seeded_db):
    return TestClient(create_app(), raise_server_exceptions=False)


def test_request_id_is_validated_not_echoed(api):
    ok = api.get("/health", headers={"x-request-id": "abc-123_X.9"})
    assert ok.headers["x-request-id"] == "abc-123_X.9"
    for bad in ["x" * 65, "has space", "a\tb", "<script>", "é" * 3]:
        try:
            r = api.get("/health", headers={"x-request-id": bad})
        except Exception:  # some clients refuse to even send it
            continue
        assert r.headers["x-request-id"] != bad and len(r.headers["x-request-id"]) <= 64


def test_only_successful_anonymous_gets_are_publicly_cacheable(api):
    assert "public" in api.get("/api/runs").headers["cache-control"]
    assert api.get("/api/runs/does-not-exist").headers["cache-control"] == "no-store"  # error
    assert api.get("/api/runs", headers={"x-admin-token": "t"}).headers["cache-control"] == "no-store"  # admin traffic
    assert api.post("/api/runs", json={}).headers["cache-control"] == "no-store"


def test_body_limit_rejects_declared_and_streamed_oversize(api):
    big = "x" * (config.get_settings().max_body_bytes + 10)
    r = api.post("/api/annotation", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413

    def chunks():
        for _ in range(40):
            yield b"y" * 4096  # chunked body, no Content-Length

    r2 = api.post("/api/annotation", content=chunks(), headers={"content-type": "application/json"})
    assert r2.status_code == 413


def test_small_bodies_still_work(api):
    r = api.post("/api/annotation", json={"item_id": "nope", "annotator": "alice", "label": True})
    assert r.status_code in (404, 422)  # reaches the handler


def test_admin_brute_force_is_rate_limited(seeded_db, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("ADMIN_TOKEN", "right-token")
    config.get_settings.cache_clear()
    admin_fail_limiter._hits.clear()
    c = TestClient(create_app())
    codes = [c.post("/api/runs", json={}, headers={"x-admin-token": f"guess{i}"}).status_code for i in range(14)]
    assert codes[:10] == [401] * 10 and 429 in codes[10:]
    # even the right token is refused while the failure window is full: no oracle for the attacker
    assert c.post("/api/runs", json={}, headers={"x-admin-token": "right-token"}).status_code == 429
    admin_fail_limiter._hits.clear()
    config.get_settings.cache_clear()


def test_production_is_the_default_and_hides_error_details(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    config.get_settings.cache_clear()
    assert config.Settings().environment == "production"
    app = create_app()

    @app.get("/boom")
    def boom():  # type: ignore[no-untyped-def]
        raise RuntimeError("secret internal detail /Users/x/db.sqlite")

    r = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500 and "secret" not in r.text and "/Users" not in r.text
    config.get_settings.cache_clear()


def test_no_absolute_filesystem_path_in_any_get_response(api):
    paths = [
        "/api/meta", "/api/agents", "/api/datasets", "/api/datasets/research-live-heldout/v1", "/api/runs", "/api/candidates",
        "/api/overview", "/api/comparisons", "/api/gates", "/api/judges", "/api/policies", "/api/traces",
    ]  # fmt: skip
    for p in paths:
        r = api.get(p)
        assert r.status_code == 200, p
        assert str(REPO_ROOT) not in r.text and "/Users/" not in r.text and "/private/" not in r.text, p


def test_list_endpoints_are_bounded(api):
    for p in ("/api/agents", "/api/datasets", "/api/candidates", "/api/comparisons", "/api/gates", "/api/judges"):
        assert api.get(p, params={"limit": 0}).status_code == 422, p
        assert api.get(p, params={"limit": 10_000}).status_code == 422, p
        assert api.get(p, params={"limit": 1}).status_code == 200, p
    assert len(api.get("/api/agents", params={"limit": 2}).json()) == 2


def test_public_annotation_is_untrusted_and_cannot_adjudicate(api, seeded_db):
    from app.db import session_scope
    from app.models import CalibrationItem, HumanAnnotation
    from sqlalchemy import select

    with session_scope() as s:
        item = s.scalars(select(CalibrationItem.item_id)).first()
    r = api.post("/api/annotation", json={"item_id": item, "annotator": "visitor-1", "label": True})
    assert r.status_code == 200
    r = api.post("/api/annotation/adjudicate", json={"item_id": item, "adjudicator": "visitor-1", "label": False})
    assert r.status_code == 200
    with session_scope() as s:
        rows = list(s.scalars(select(HumanAnnotation).where(HumanAnnotation.annotator.like("%public:visitor-1"))))
        assert rows and all(x.source == "public_untrusted" and not x.adjudicated for x in rows)
    summary = api.get("/api/annotation/summary").json()
    assert "public:visitor-1" in summary["untrusted_annotators"]
    # untrusted labels are reported separately and never enter agreement statistics
    assert (
        "public:visitor-1" not in summary["annotators"] and summary["untrusted_label_counts"]["public:visitor-1"] == 1
    )
    # authenticated (trusted) workflows are admin-only, and disabled outright in the public demo
    for u, body in (
        ("/api/annotation/trusted", {"item_id": item, "annotator": "alice", "label": True}),
        ("/api/annotation/trusted/adjudicate", {"item_id": item, "adjudicator": "alice", "label": True}),
    ):
        assert api.post(u, json=body).status_code in (401, 403)
