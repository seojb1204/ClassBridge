"""Client address for abuse limits behind reverse proxies.

uvicorn's ``--forwarded-allow-ips='*'`` takes the *left-most* X-Forwarded-For entry,
which the client itself can write. Render appends to (and does not reset) that header,
so only the right-most ``trusted_proxy_hops`` entries are proxy-written. This helper
reads the raw header and uses the entry the nearest trusted proxy appended.
The value is used only as an in-memory rate-limit key (HMAC'd), never stored.
"""
from __future__ import annotations

from starlette.requests import Request


def client_address(request: Request, trusted_hops: int) -> str:
    if trusted_hops > 0:
        raw = request.headers.get("x-forwarded-for", "")
        hosts = [part.strip() for part in raw.split(",") if part.strip()]
        if len(hosts) >= trusted_hops:
            return hosts[-trusted_hops]
    return request.client.host if request.client else "unknown"
