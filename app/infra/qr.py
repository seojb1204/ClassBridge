"""Pixel-aligned PNG QR images with an opaque white quiet zone."""
from io import BytesIO

import qrcode
from qrcode.image.pil import PilImage


def png_qr(url: str) -> bytes:
    image = qrcode.make(url, image_factory=PilImage, box_size=16, border=4)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
