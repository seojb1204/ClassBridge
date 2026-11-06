import struct


def test_installation_assets_and_root_worker(clients):
    client = clients["prof"]
    page = client.get("/")
    assert 'rel="manifest"' in page.text
    manifest = client.get("/static/manifest.webmanifest").json()
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/" and manifest["scope"] == "/"
    for icon in manifest["icons"]:
        response = client.get(icon["src"])
        assert response.status_code == 200
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack("!II", response.content[16:24])
        assert icon["sizes"] == f"{width}x{height}"
    worker = client.get("/sw.js")
    assert worker.status_code == 200 and "javascript" in worker.headers["content-type"]
    assert worker.headers["service-worker-allowed"] == "/"
    assert "no-cache" in worker.headers["cache-control"]
    assert client.get("/static/offline.html").status_code == 200


def test_installation_does_not_grant_student_staff_access(clients):
    assert clients["s1"].get("/api/bookings").status_code == 403
    assert clients["s1"].get("/static/manifest.webmanifest").status_code == 200
