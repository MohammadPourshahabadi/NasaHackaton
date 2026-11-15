"""Stamp a visible 'SI-generated' watermark (Space Apps rule: Super Intelligence) on illustrations that were made with OpenAI Codex (image generation).

AI-generated assets in Aboard: anatomy-atlas.png, activity-frames.png, activity-man.png,
activity-woman-extra.png, activity-man-extra.png, measurement-frames.png and equipment-atlas.png.
Art drawn by code (star field, mood sticker, rating faces, scripted guide animations) is not tagged.
"""
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LABEL = 'SI-generated'


@lru_cache(maxsize=8)
def _font(size):
    for name in ('segoeuib.ttf', 'arialbd.ttf'):
        try:
            return ImageFont.truetype(str(Path('C:/Windows/Fonts') / name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def ai_tag(image, corner='bottom-left'):
    """Return a copy of a PIL image with a small semi-transparent 'SI-generated' pill in one corner."""
    tagged = image.convert('RGBA')
    width, height = tagged.size
    size = max(9, min(16, width // 18))
    face = _font(size)
    overlay = Image.new('RGBA', tagged.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    text_width = draw.textlength(LABEL, font=face)
    pad_x, pad_y, margin = size * .6, size * .3, max(4, size // 2)
    box_w, box_h = text_width + 2 * pad_x, size + 2 * pad_y + 2
    x = margin if corner.endswith('left') else width - margin - box_w
    y = height - margin - box_h if corner.startswith('bottom') else margin
    draw.rounded_rectangle((x, y, x + box_w, y + box_h), radius=box_h / 2, fill=(10, 18, 24, 190),
                           outline=(255, 255, 255, 120), width=1)
    draw.text((x + pad_x, y + pad_y), LABEL, font=face, fill=(255, 255, 255, 235))
    tagged.alpha_composite(overlay)
    return tagged
