"""Build the vector book/play mark and matching Windows icons, without external fonts."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "packaging" / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)
INK, PAPER, MINT, AMBER = "#142E2D", "#EFF4E6", "#A8DCC2", "#E8BB71"
LEFT = [(27, 32), (59, 40), (59, 96), (27, 87)]
RIGHT = [(66, 40), (101, 30), (101, 85), (66, 96)]
PLAY = [(77, 50), (77, 75), (92, 62)]
BOOKMARK = [(37, 29), (44, 31), (44, 53), (40.5, 49), (37, 51)]


def svg():
    points = lambda values: " ".join(f"{x},{y}" for x, y in values)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" fill="none">
  <rect x="4" y="4" width="120" height="120" rx="31" fill="{INK}"/>
  <rect x="4.5" y="4.5" width="119" height="119" rx="30.5" stroke="{MINT}" stroke-opacity=".18"/>
  <polygon points="{points(LEFT)}" fill="{PAPER}"/>
  <polygon points="{points(RIGHT)}" fill="{MINT}"/>
  <polygon points="{points(BOOKMARK)}" fill="{AMBER}"/>
  <polygon points="{points(PLAY)}" fill="{INK}" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>
</svg>
'''


def render():
    scale = 24
    image = Image.new("RGBA", (128 * scale, 128 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(tuple(v * scale for v in (4, 4, 124, 124)), radius=31 * scale,
                           fill=INK, outline="#35554A", width=scale)
    for shape, color in ((LEFT, PAPER), (RIGHT, MINT), (BOOKMARK, AMBER), (PLAY, INK)):
        draw.polygon([(round(x * scale), round(y * scale)) for x, y in shape], fill=color)
    return image.resize((1024, 1024), Image.Resampling.LANCZOS)


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    for path in (ASSETS / "logo.svg", ROOT / "frontend/public/favicon.svg"):
        path.write_text(svg(), encoding="utf-8")
    image = render()
    image.save(ASSETS / "logo.png")
    image.save(ASSETS / "app.ico", format="ICO", sizes=[(size, size) for size in SIZES])
    preview = Image.new("RGBA", (1120, 360), "#F3F5F2")
    for x, size in [(32, 256), (336, 128), (512, 64), (624, 48), (720, 32), (800, 24), (872, 16)]:
        preview.alpha_composite(image.resize((size, size), Image.Resampling.LANCZOS),
                                (x, 52 + (256 - size) // 2))
    preview.convert("RGB").save(ASSETS / "logo_preview.png")
    print("Generated SVG, PNG and Windows icon sizes 16–256")


if __name__ == "__main__":
    main()
