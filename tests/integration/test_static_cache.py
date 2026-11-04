"""Static assets must revalidate after deployment."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_static_js_and_html_are_revalidated_after_deploy(app):
    client = TestClient(app)
    for path in ("/", "/static/js/main.js", "/static/css/app.css"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["Cache-Control"] == "no-cache, must-revalidate"
