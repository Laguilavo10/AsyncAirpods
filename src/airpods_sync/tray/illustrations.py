"""Headphone illustrations for the Nearby AirPods window, drawn at runtime.

Original drawings (no product photos, which are copyrighted), one per family.
Each is drawn at 4x and scaled down, which gives smooth antialiased edges.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

_SCALE = 4
_BASE = 128  # logical size of the drawing grid

_BODY = (250, 250, 251, 255)
_OUTLINE = (176, 182, 191, 255)
_DETAIL = (120, 128, 140, 255)
_TIP = (214, 219, 226, 255)
_MESH = (60, 66, 76, 255)
_DARK_BODY = (54, 58, 66, 255)
_DARK_OUTLINE = (128, 134, 144, 255)
_SHADOW = (0, 0, 0, 70)


class Family(Enum):
    AIRPODS = "airpods"  # long stems: AirPods 1st-4th gen
    AIRPODS_PRO = "airpods_pro"  # short stems and silicone tips
    AIRPODS_MAX = "airpods_max"  # over-ear, Apple
    HEADPHONES = "headphones"  # any other over-ear headset


# Apple product IDs, the same ones the domain knows by name
_FAMILIES: dict[int, Family] = {
    0x2002: Family.AIRPODS,
    0x200F: Family.AIRPODS,
    0x2013: Family.AIRPODS,
    0x200E: Family.AIRPODS_PRO,
    0x2014: Family.AIRPODS_PRO,
    0x2024: Family.AIRPODS_PRO,
    0x2027: Family.AIRPODS_PRO,
    0x200A: Family.AIRPODS_MAX,
}


def family_for(model_id: int | None) -> Family:
    return _FAMILIES.get(model_id, Family.HEADPHONES) if model_id is not None else Family.HEADPHONES


@lru_cache(maxsize=16)
def illustration(family: Family, size: int) -> Image.Image:
    """A square RGBA image of `size` pixels."""
    big = _BASE * _SCALE
    art = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    _DRAWERS[family](art)
    shadow = _shadow_of(art)
    shadow.alpha_composite(art)
    return shadow.resize((size, size), Image.LANCZOS)


def _shadow_of(art: Image.Image) -> Image.Image:
    alpha = art.getchannel("A").point(lambda a: _SHADOW[3] if a else 0)
    shadow = Image.new("RGBA", art.size, _SHADOW[:3] + (0,))
    shadow.putalpha(alpha)
    offset = Image.new("RGBA", art.size, (0, 0, 0, 0))
    offset.paste(shadow, (0, 3 * _SCALE))
    return offset.filter(ImageFilter.GaussianBlur(4 * _SCALE))


def _s(*values: float) -> list[float]:
    return [v * _SCALE for v in values]


def _bud(stem_length: float, pro: bool) -> Image.Image:
    """One left earbud on its own layer, upright, head centered at (40, 30).

    Callers tilt and mirror it.
    """
    layer = Image.new("RGBA", (_BASE * _SCALE, _BASE * _SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    width = 3 * _SCALE
    head_w, head_h = (36, 32) if pro else (32, 30)
    left, top = 40 - head_w / 2, 30 - head_h / 2
    stem_w = 14 if pro else 12
    stem_left = 40 - head_w / 2 + 4  # the stem hangs from the outer half of the head
    if pro:  # silicone tip, on the inner side that goes into the ear
        draw.ellipse(_s(left + head_w - 12, top + 7, left + head_w + 9, top + head_h - 5),
                     fill=_TIP, outline=_OUTLINE, width=width)
    draw.rounded_rectangle(
        _s(stem_left, 30, stem_left + stem_w, 30 + head_h / 2 + stem_length),
        radius=stem_w / 2 * _SCALE, fill=_BODY, outline=_OUTLINE, width=width,
    )
    draw.ellipse(_s(left, top, left + head_w, top + head_h), fill=_BODY, outline=_OUTLINE, width=width)
    # speaker grille, a slim slot on the inner side
    draw.rounded_rectangle(_s(left + head_w - 11, top + 9, left + head_w - 6, top + head_h - 9),
                           radius=2 * _SCALE, fill=_MESH)
    # microphone at the bottom of the stem
    stem_end = 30 + head_h / 2 + stem_length
    draw.rounded_rectangle(_s(stem_left + 3, stem_end - 8, stem_left + stem_w - 3, stem_end - 4),
                           radius=2 * _SCALE, fill=_DETAIL)
    return layer


def _pair_of_buds(art: Image.Image, stem_length: float, pro: bool) -> None:
    left = _bud(stem_length, pro).rotate(-10, resample=Image.BICUBIC, center=_s(40, 30))
    right = left.transpose(Image.FLIP_LEFT_RIGHT)
    top = (_BASE - (30 + 16 + stem_length + 14)) / 2  # center the pair vertically
    art.alpha_composite(left, (-4 * _SCALE, int(top * _SCALE)))
    art.alpha_composite(right, (4 * _SCALE, int(top * _SCALE)))


def _airpods(art: Image.Image) -> None:
    _pair_of_buds(art, stem_length=52, pro=False)


def _airpods_pro(art: Image.Image) -> None:
    _pair_of_buds(art, stem_length=36, pro=True)


def _over_ear(art: Image.Image, body: tuple, outline: tuple, square_cups: bool) -> None:
    draw = ImageDraw.Draw(art)
    width = 3 * _SCALE
    # headband: a thick arc with a lighter inner canopy
    draw.arc(_s(22, 14, 106, 100), start=185, end=355, fill=outline, width=14 * _SCALE)
    draw.arc(_s(24, 16, 104, 98), start=187, end=353, fill=body, width=10 * _SCALE)
    for left in (True, False):
        x0 = 14 if left else 84
        # yoke
        draw.rounded_rectangle(_s(x0 + 10, 50, x0 + 20, 70), radius=3 * _SCALE, fill=_DETAIL)
        if square_cups:
            draw.rounded_rectangle(_s(x0, 62, x0 + 30, 108), radius=12 * _SCALE,
                                   fill=body, outline=outline, width=width)
            cushion = (x0 + 22, 66, x0 + 30, 104) if left else (x0, 66, x0 + 8, 104)
            draw.rounded_rectangle(_s(*cushion), radius=4 * _SCALE, fill=_MESH)
        else:
            draw.ellipse(_s(x0 - 2, 60, x0 + 32, 108), fill=body, outline=outline, width=width)
            cushion = (x0 + 20, 64, x0 + 34, 104) if left else (x0 - 4, 64, x0 + 10, 104)
            draw.ellipse(_s(*cushion), fill=_MESH)


def _airpods_max(art: Image.Image) -> None:
    _over_ear(art, _BODY, _OUTLINE, square_cups=True)


def _headphones(art: Image.Image) -> None:
    _over_ear(art, _DARK_BODY, _DARK_OUTLINE, square_cups=False)


_DRAWERS = {
    Family.AIRPODS: _airpods,
    Family.AIRPODS_PRO: _airpods_pro,
    Family.AIRPODS_MAX: _airpods_max,
    Family.HEADPHONES: _headphones,
}
