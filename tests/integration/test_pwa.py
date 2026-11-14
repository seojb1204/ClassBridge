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


def test_notification_worker_links_are_fixed_authenticated_routes(clients):
    worker = clients['prof'].get('/sw.js').text
    assert '"/#/suggestions"' in worker
    assert '"/#/inbox"' in worker
    assert '.includes(payload.url) ? payload.url : "/#/bookings"' in worker
    assert 'config.session !== payload.session' in worker


def test_editorial_icons_and_apple_home_screen(clients):
    client = clients["prof"]
    page = client.get("/").text
    manifest = client.get("/static/manifest.webmanifest").json()
    assert manifest["theme_color"] == manifest["background_color"] == "#f7f3ec"
    assert manifest["id"] == "/"  # Preserve existing installed-app identity.
    assert manifest["name"] == "ClassBridge 교수자"
    assert manifest["short_name"] == "ClassBridge"
    assert all("app-editorial-v1-" in icon["src"] for icon in manifest["icons"])
    assert any(icon["purpose"] == "maskable" for icon in manifest["icons"])
    assert 'rel="apple-touch-icon" sizes="180x180" href="/static/icons/app-editorial-v1-180.png"' in page
    assert 'sizes="32x32" href="/static/icons/app-editorial-v1-32.png"' in page
    for size in (32, 180):
        response = client.get(f"/static/icons/app-editorial-v1-{size}.png")
        assert response.status_code == 200
        assert struct.unpack("!II", response.content[16:24]) == (size, size)
    svg = client.get("/static/icons/app-editorial-v1.svg").text
    assert '#a64419' in svg and '#f7f3ec' in svg
    assert '#3155ef' not in svg
