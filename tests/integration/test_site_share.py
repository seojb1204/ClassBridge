import qrcode
from fastapi.testclient import TestClient


def test_public_site_qr_uses_configured_url_without_account_or_request_host(app, clients, monkeypatch):
    original = qrcode.make
    encoded = []

    def capture(data, **kwargs):
        encoded.append(data)
        return original(data, **kwargs)

    monkeypatch.setattr(qrcode, "make", capture)
    for client in (TestClient(app), clients["s1"], clients["prof"], clients["admin"]):
        response = client.get("/api/site/qr.svg", headers={"Host": "untrusted.example"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/svg+xml")
        assert "classbridge-site-qr.svg" in response.headers["content-disposition"]
        assert "<svg" in response.text
        assert encoded[-1] == app.state.settings.base_url.rstrip("/") + "/"
