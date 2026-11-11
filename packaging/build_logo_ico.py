"""生成「分刷酱」图标：对角“分”开的两色圆角方块（两个平台合一）+ 白色对勾（刷完）+ 星光。

输出到 packaging/assets/：logo.svg、logo.png(1024)、app.ico、logo_preview.png。
同时同步 gui_dist/favicon.svg 与 frontend/public/favicon.svg。
用法：python packaging/build_logo_ico.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSETS = HERE / "assets"
CANVAS, SCALE = 1024, 4
SIZES = (16, 24, 32, 48, 64, 128, 256)
BLUE, TEAL, WHITE, PINK = "#3730A3", "#14B8A6", "#FFFFFF", "#FDE68A"
RECT = (48, 48, 976, 976)
RADIUS = 220
# 对角线：左下半 BLUE（右上半 TEAL），线从右上角到左下角附近
SPLIT = [(976, 48), (976, 976), (48, 976)]  # 右下三角（用 TEAL 覆盖）
CHECK = [(268, 540), (452, 724), (780, 340)]
STAR = [(770, 130), (803, 226), (899, 259), (803, 292), (770, 388), (737, 292), (641, 259), (737, 226)]
CHECK_W = 96


def s(pts):
    return [(x * SCALE, y * SCALE) for x, y in pts]


def render():
    n = CANVAS * SCALE
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle([v * SCALE for v in RECT], radius=RADIUS * SCALE, fill=255)
    base = Image.new("RGBA", (n, n), BLUE)
    ImageDraw.Draw(base).polygon(s(SPLIT), fill=TEAL)
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    img.paste(base, mask=mask)
    d = ImageDraw.Draw(img)
    d.line(s(CHECK), fill=WHITE, width=CHECK_W * SCALE, joint="curve")
    r = CHECK_W * SCALE // 2
    for x, y in (CHECK[0], CHECK[-1]):
        d.ellipse((x * SCALE - r, y * SCALE - r, x * SCALE + r, y * SCALE + r), fill=WHITE)
    d.polygon(s(STAR), fill=PINK)
    return img.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)


def svg():
    pts = lambda p: " ".join(f"{x},{y}" for x, y in p)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs><clipPath id="c"><rect x="48" y="48" width="928" height="928" rx="{RADIUS}"/></clipPath></defs>
  <g clip-path="url(#c)">
    <rect width="1024" height="1024" fill="{BLUE}"/>
    <polygon points="{pts(SPLIT)}" fill="{TEAL}"/>
  </g>
  <polyline points="{pts(CHECK)}" fill="none" stroke="{WHITE}" stroke-width="{CHECK_W}" stroke-linecap="round" stroke-linejoin="round"/>
  <polygon points="{pts(STAR)}" fill="{PINK}"/>
</svg>
'''


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    text = svg()
    (ASSETS / "logo.svg").write_text(text, encoding="utf-8")
    for p in (ROOT / "gui_dist" / "favicon.svg", ROOT / "frontend" / "public" / "favicon.svg"):
        if p.parent.exists():
            p.write_text(text, encoding="utf-8")
    image = render()
    image.save(ASSETS / "logo.png")
    image.save(ASSETS / "app.ico", format="ICO", sizes=[(z, z) for z in SIZES])
    preview = Image.new("RGBA", (1120, 360), "#F7F2FA")
    for x, size in [(32, 256), (336, 128), (512, 64), (624, 48), (720, 32), (800, 24), (872, 16)]:
        preview.alpha_composite(image.resize((size, size), Image.Resampling.LANCZOS), (x, 52 + (256 - size) // 2))
    preview.convert("RGB").save(ASSETS / "logo_preview.png")
    print("done")


if __name__ == "__main__":
    main()
