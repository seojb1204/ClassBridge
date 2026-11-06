from io import BytesIO

import pytest
import qrcode
from fastapi.testclient import TestClient
from PIL import Image


@pytest.mark.parametrize("format", ["svg", "png"])
def test_public_site_qr_uses_configured_url_without_account_or_request_host(app, clients, monkeypatch, format):
    original = qrcode.make
    encoded = []

    def capture(data, **kwargs):
        encoded.append(data)
        return original(data, **kwargs)

    monkeypatch.setattr(qrcode, "make", capture)
    for client in (TestClient(app), clients["s1"], clients["prof"], clients["admin"]):
        response = client.get(f"/api/site/qr.{format}", headers={"Host": "untrusted.example"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/svg+xml" if format == "svg" else "image/png")
        assert f"classbridge-site-qr.{format}" in response.headers["content-disposition"]
        if format == "svg":
            assert "<svg" in response.text
        else:
            image = Image.open(BytesIO(response.content))
            image.load()
            assert image.format == "PNG" and image.width == image.height and image.width >= 400
            assert image.convert("RGB").getpixel((0, 0)) == (255, 255, 255)
        assert encoded[-1] == app.state.settings.base_url.rstrip("/") + "/"
