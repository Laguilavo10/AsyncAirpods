"""Tray icon images, drawn at runtime so the project ships no binary assets."""

from __future__ import annotations

from enum import Enum

from PIL import Image, ImageDraw

_SIZE = 64


class IconState(Enum):
    ON_PC = "#2E9E5B"
    CONNECTING = "#2F6FD6"
    AWAY = "#8A8F98"
    PAUSED = "#D08A1E"
    ERROR = "#C93C3C"


def draw(state: IconState) -> Image.Image:
    """Two earbud stems on a colored disc."""
    image = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    canvas = ImageDraw.Draw(image)
    canvas.ellipse((2, 2, _SIZE - 2, _SIZE - 2), fill=state.value)
    for x in (20, 38):
        canvas.ellipse((x - 2, 14, x + 8, 26), fill="white")
        canvas.rounded_rectangle((x + 1, 22, x + 6, 48), radius=3, fill="white")
    return image
