"""Guest suggestions: private only, and spoofed X-Forwarded-For cannot dodge the rate limit."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.client_ip import client_address

PATH = "/api/suggestions/anonymous"
HEADERS = {"X-Anonymous-Submit": "1"}


def test_guest_cannot_publish_but_signed_in_student_can(app, clients):
    guest = TestClient(app)
    body = {"category": "lecture", "content": "공개 시도"}
    r = guest.post(PATH, json={**body, "is_public": True}, headers=HEADERS)
    assert r.status_code == 403 and r.json()["error"] == "guest_public_forbidden"
    assert clients["s1"].get("/api/suggestions/public").json() == []
    assert guest.post(PATH, json=body, headers=HEADERS).status_code == 201
    assert clients["s1"].post("/api/suggestions", json={**body, "is_public": True}).status_code == 201
    board = clients["s1"].get("/api/suggestions/public").json()
    assert [row["content"] for row in board] == ["공개 시도"]


def test_spoofed_forwarded_for_shares_the_proxy_appended_bucket(app):
    guest = TestClient(app)
    body = {"category": "other", "content": "도배 시도"}
    for i in range(10):
        spoof = {**HEADERS, "X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}
        assert guest.post(PATH, json=body, headers=spoof).status_code == 201
    spoof = {**HEADERS, "X-Forwarded-For": "10.9.9.9, 203.0.113.7"}
    assert guest.post(PATH, json=body, headers=spoof).status_code == 429
    other_client = {**HEADERS, "X-Forwarded-For": "10.9.9.9, 198.51.100.4"}
    assert guest.post(PATH, json=body, headers=other_client).status_code == 201


class _Req:
    def __init__(self, xff=None, host="1.2.3.4"):
        self.headers = {"x-forwarded-for": xff} if xff is not None else {}
        self.client = type("C", (), {"host": host})()


def test_client_address_uses_right_most_trusted_entries():
    assert client_address(_Req("evil, 203.0.113.7"), 1) == "203.0.113.7"
    assert client_address(_Req("evil, 203.0.113.7, 10.0.0.2"), 2) == "203.0.113.7"
    assert client_address(_Req("203.0.113.7"), 2) == "1.2.3.4"  # fewer hops than trusted: socket peer
    assert client_address(_Req(None), 1) == "1.2.3.4"
    assert client_address(_Req("evil, 203.0.113.7"), 0) == "1.2.3.4"
