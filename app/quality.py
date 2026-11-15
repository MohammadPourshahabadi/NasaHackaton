"""Optional, local PNG/JPEG export checks for the review workflow."""

from pathlib import Path


MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 24_000_000
PREVIEW_SIZE = (256, 256)


def inspect_image(path):
    """Report decoding and simple brightness statistics. This is not scan interpretation."""
    result = {"width": None, "height": None, "mean": None, "contrast": None, "flags": []}
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return {**result, "status": "error", "detail": "The optional local image decoder is unavailable."}

    try:
        with Path(path).open("rb") as stream:
            stream.seek(0, 2)
            if stream.tell() > MAX_BYTES:
                return {**result, "status": "error", "detail": "Choose a PNG or JPEG export under 8 MB."}
            stream.seek(0)
            with Image.open(stream, formats=("PNG", "JPEG")) as image:
                width, height = image.size
                if width * height > MAX_PIXELS:
                    return {**result, "status": "error", "detail": "Choose an export under 24 megapixels."}
                image.thumbnail(PREVIEW_SIZE)
                stats = ImageStat.Stat(image.convert("L"))
    except (OSError, ValueError, TypeError, Image.DecompressionBombError):
        return {**result, "status": "error", "detail": "Could not decode this PNG or JPEG export."}

    mean = stats.mean[0]
    contrast = stats.stddev[0]
    flags = []
    if min(width, height) < 160:
        flags.append("Small export")
    if mean < 20:
        flags.append("Mostly dark pixels")
    elif mean > 235:
        flags.append("Mostly light pixels")
    if contrast < 12:
        flags.append("Low overall tonal variation")

    return {
        "status": "review" if flags else "ok",
        "detail": "Decoded locally. Export statistics only. A trained reviewer evaluates the scan.",
        "width": width, "height": height, "mean": round(mean, 1),
        "contrast": round(contrast, 1), "flags": flags,
    }
