"""Public QR containing only the configured site URL, never account data."""
import qrcode
from fastapi import APIRouter, Request
from fastapi.responses import Response
from qrcode.image.svg import SvgPathFillImage

router = APIRouter(prefix="/api/site", tags=["site"])


@router.get("/qr.svg")
def site_qr(request: Request):
    url = request.app.state.settings.base_url.rstrip("/") + "/"
    image = qrcode.make(url, image_factory=SvgPathFillImage, border=4)
    return Response(image.to_string(), media_type="image/svg+xml",
                    headers={"Content-Disposition": 'inline; filename="classbridge-site-qr.svg"'})
