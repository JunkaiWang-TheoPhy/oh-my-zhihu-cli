from pathlib import Path

from PIL import Image, ImageOps

REFERENCE_DIR = Path(
    "/var/folders/z9/gmbcyfts0239_cqcrfjxwlbh0000gp/T"
)
SOURCE_IMAGES = (
    REFERENCE_DIR / "codex-clipboard-5c7dc1d3-ffb5-4fd9-bbe5-8c4d2636f195.png",
    REFERENCE_DIR / "codex-clipboard-eeef39ac-306b-4da6-8b5b-e589520b52bf.png",
    REFERENCE_DIR / "codex-clipboard-54142b7b-868e-496f-93cb-b25615c81943.png",
    REFERENCE_DIR / "codex-clipboard-7649a22c-1674-422d-8cb1-822359e9e0e5.png",
    REFERENCE_DIR / "codex-clipboard-8b12094c-7428-47b1-83dd-d71004f27567.png",
    REFERENCE_DIR / "codex-clipboard-0686eb7e-33eb-4bb3-9f66-22d6adeee472.png",
)
OUTPUT = Path(__file__).parents[1] / "zhihu_cli" / "assets"
NAMES = (
    "logo_01",
    "logo_02",
    "logo_03",
    "liukanshan_01",
    "liukanshan_02",
    "liukanshan_03",
)


def process() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, source in zip(NAMES, SOURCE_IMAGES, strict=True):
        tile = Image.open(source).convert("RGBA")
        corner = tile.getpixel((0, 0))[:3]
        pixels = tile.load()
        for y in range(tile.height):
            for x in range(tile.width):
                red, green, blue, alpha = pixels[x, y]
                distance = sum((value - reference) ** 2 for value, reference in zip(
                    (red, green, blue), corner, strict=True
                )) ** 0.5
                if distance < 42:
                    pixels[x, y] = (0, 0, 0, 0)
        tile.thumbnail((64, 64), Image.Resampling.LANCZOS)
        alpha = tile.getchannel("A")
        # Keep hard edges: this is intended for nearest-neighbor terminal pixels.
        tile = ImageOps.posterize(tile.convert("RGB"), 3).convert("RGBA")
        tile.putalpha(alpha.point(lambda value: 0 if value < 24 else value))
        tile.save(OUTPUT / f"{name}.png", optimize=True)


if __name__ == "__main__":
    process()
