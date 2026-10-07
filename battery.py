"""Render a small battery with true per-pixel transparency."""
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 64, 28


def render_battery(remaining=None, stale=False, scale=1, light=False):
    factor = 4 * scale
    image = Image.new('RGBA', (WIDTH * factor, HEIGHT * factor))
    draw = ImageDraw.Draw(image)

    def box(points):
        return tuple(round(x * factor) for x in points)

    tone = (25, 25, 25) if light else (255, 255, 255)
    outline = (*tone, 205) if not stale else (140, 140, 140, 190)
    # A faint dark edge remains visible against light desktop backgrounds.
    draw.rounded_rectangle(box((2, 3, 58, 25)), radius=5 * factor,
                           fill=(128, 128, 128, 28), outline=(128, 128, 128, 100), width=3 * factor)
    draw.rounded_rectangle(box((2, 3, 58, 25)), radius=5 * factor,
                           outline=outline, width=round(1.5 * factor))
    draw.rounded_rectangle(box((60, 10, 62, 18)), radius=factor, fill=outline)
    if remaining is not None and remaining > 0:
        percent = max(0, min(100, remaining))
        color = (*tone, 245) if percent > 20 else (255, 69, 58, 245)
        if stale:
            color = (160, 160, 160, 160)
        fill = Image.new('RGBA', image.size)
        ImageDraw.Draw(fill).rounded_rectangle(box((6, 7, 54, 21)), radius=2 * factor, fill=color)
        mask = Image.new('L', image.size)
        ImageDraw.Draw(mask).rectangle(box((6, 7, 6 + 48 * percent / 100, 21)), fill=255)
        image.alpha_composite(Image.composite(fill, Image.new('RGBA', image.size), mask))
    if remaining is None or stale:
        # Unavailable/stale is visibly different from an actual empty quota.
        draw = ImageDraw.Draw(image)
        draw.ellipse(box((29, 11, 32, 14)), fill=outline)
        draw.ellipse(box((30, 17, 31.5, 18.5)), fill=outline)
    return image.resize((WIDTH * scale, HEIGHT * scale), Image.Resampling.LANCZOS)
