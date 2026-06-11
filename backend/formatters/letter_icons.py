"""Tiny cobalt contact icons for the cover-letter letterhead.

Drawn once at runtime with Pillow (already a dependency via pdfplumber) and cached
as PNG bytes - so there are no asset files to ship or path issues on Render. Each
call returns a fresh BytesIO because python-docx's add_picture consumes the stream.
If Pillow is unavailable for any reason, icon_png returns None and the caller falls
back to a short text label, so the letter always renders.
"""
from io import BytesIO

COBALT = (0, 71, 171, 255)
WHITE = (255, 255, 255, 255)
_SZ = 64
_cache: dict = {}


def _new():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (_SZ, _SZ), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _phone():
    img, d = _new()
    d.rounded_rectangle([20, 6, 44, 58], radius=8, outline=COBALT, width=6)
    d.ellipse([28, 49, 36, 57], fill=COBALT)
    return img


def _email():
    img, d = _new()
    d.rounded_rectangle([8, 16, 56, 48], radius=4, outline=COBALT, width=6)
    d.line([11, 20, 32, 36], fill=COBALT, width=6)
    d.line([53, 20, 32, 36], fill=COBALT, width=6)
    return img


def _location():
    img, d = _new()
    d.ellipse([18, 8, 46, 36], fill=COBALT)
    d.polygon([(20, 30), (44, 30), (32, 58)], fill=COBALT)
    d.ellipse([27, 16, 37, 26], fill=WHITE)
    return img


def _linkedin():
    img, d = _new()
    d.rounded_rectangle([6, 6, 58, 58], radius=10, fill=COBALT)
    d.ellipse([15, 16, 24, 25], fill=WHITE)           # i dot
    d.rectangle([16, 29, 23, 48], fill=WHITE)         # i stem
    d.rectangle([29, 29, 36, 48], fill=WHITE)         # n left stem
    d.rectangle([29, 29, 49, 36], fill=WHITE)         # n top
    d.rectangle([43, 33, 50, 48], fill=WHITE)         # n right stem
    return img


_DRAW = {"phone": _phone, "email": _email, "location": _location, "linkedin": _linkedin}


def icon_png(kind: str):
    """Return a BytesIO PNG of the cobalt icon, or None if it can't be drawn."""
    if kind not in _cache:
        fn = _DRAW.get(kind)
        if not fn:
            return None
        try:
            buf = BytesIO()
            fn().save(buf, format="PNG")
            _cache[kind] = buf.getvalue()
        except Exception:
            return None
    return BytesIO(_cache[kind])
