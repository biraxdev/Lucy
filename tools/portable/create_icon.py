#!/usr/bin/env python3
"""Generate a stylized 'Lucy' desktop icon (ICO)."""
from __future__ import annotations

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise RuntimeError("Pillow is required to generate the icon: pip install Pillow") from exc

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "lucy.ico"

# Sizes to include in the .ico (Windows picks the best one automatically)
SIZES = [256, 128, 96, 64, 48, 32, 24, 16]


def draw_gradient_circle(draw: ImageDraw.ImageDraw, size: int, color1: tuple[int, int, int], color2: tuple[int, int, int]) -> None:
    """Draw a radial-ish gradient by drawing concentric circles."""
    cx = cy = size // 2
    for r in range(size // 2, 0, -2):
        t = r / (size // 2)
        c = (
            int(color1[0] * t + color2[0] * (1 - t)),
            int(color1[1] * t + color2[1] * (1 - t)),
            int(color1[2] * t + color2[2] * (1 - t)),
        )
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)


def draw_neural_nodes(draw: ImageDraw.ImageDraw, size: int) -> None:
    """Draw subtle connected-node pattern."""
    cx = cy = size // 2
    nodes = []
    for i in range(8):
        angle = (2 * math.pi / 8) * i
        r = size * 0.32
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        nodes.append((x, y))
    # Connections
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i < j and (j - i) % 8 in (1, 2, 7):
                draw.line([a, b], fill=(255, 255, 255, 40), width=max(1, size // 128))
    for x, y in nodes:
        r = max(2, size // 64)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 120))


def draw_letter_l(draw: ImageDraw.ImageDraw, size: int) -> None:
    """Draw a bold white 'L' at the center."""
    cx = cy = size // 2
    scale = size / 256
    bar_w = int(22 * scale)
    bar_h = int(80 * scale)
    gap = int(8 * scale)

    # Vertical + horizontal bar of L
    x1 = cx - bar_w // 2 - int(12 * scale)
    y1 = cy - bar_h // 2
    x2 = x1 + bar_w
    y2 = y1 + bar_h
    draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255, 245))

    hx1 = x1
    hy1 = y2 - bar_w
    hx2 = x1 + int(56 * scale)
    hy2 = y2
    draw.rectangle([hx1, hy1, hx2, hy2], fill=(255, 255, 255, 245))

    # Small dot reminiscent of the film's cerebral/neural motif
    dot_r = int(6 * scale)
    draw.ellipse([hx2 - dot_r, hy2 - dot_r, hx2 + dot_r, hy2 + dot_r], fill=(255, 90, 90, 255))


def create_icon_size(size: int) -> Image.Image:
    """Render one icon size as RGBA."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Deep blue/violet gradient background
    draw_gradient_circle(draw, size, (20, 30, 90), (60, 20, 80))

    # Neural pattern
    draw_neural_nodes(draw, size)

    # Bold L
    draw_letter_l(draw, size)

    return img


def main() -> None:
    images = [create_icon_size(s) for s in SIZES]
    images[0].save(OUTPUT, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[1:])
    print(f"Icon created: {OUTPUT}")


if __name__ == "__main__":
    main()
