"""Tray icon images, drawn at runtime so the project ships no binary assets."""

from __future__ import annotations

from enum import Enum

from PIL import Image, ImageDraw, ImageOps

_SIZE = 64
_SCALE = 4  # drawn larger and scaled down, so the curves stay smooth at 16 px


class IconState(Enum):
    ON_PC = "#2E9E5B"
    CONNECTING = "#2F6FD6"
    AWAY = "#8A8F98"
    PAUSED = "#D08A1E"
    ERROR = "#C93C3C"


def draw(state: IconState) -> Image.Image:
    """A pair of earbuds, speaker tips facing each other, on a colored disc."""
    size = _SIZE * _SCALE
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((4, 4, size - 4, size - 4), fill=state.value)

    left = _earbud(state.value, size).rotate(8, resample=Image.BICUBIC)
    image.alpha_composite(left, (-16, 0))
    image.alpha_composite(ImageOps.mirror(left), (16, 0))
    return image.resize((_SIZE, _SIZE), Image.LANCZOS)


def _earbud(color: str, size: int) -> Image.Image:
    """The left earbud: a round head with its speaker tip facing right, and a stem."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas = ImageDraw.Draw(layer)
    head_x, head_y, radius = size * 0.33, size * 0.34, size * 0.13
    stem_width = size * 0.09
    canvas.rounded_rectangle(
        (head_x - stem_width / 2, head_y, head_x + stem_width / 2, size * 0.80),
        radius=stem_width / 2,
        fill="white",
    )
    canvas.ellipse((head_x - radius, head_y - radius, head_x + radius, head_y + radius), fill="white")
    # The speaker tip, a dark oval on the inner side of the head
    tip_x, tip_radius = head_x + radius * 0.55, radius * 0.38
    canvas.ellipse(
        (tip_x - tip_radius * 0.75, head_y - tip_radius, tip_x + tip_radius * 0.75, head_y + tip_radius),
        fill=color,
    )
    return layer
