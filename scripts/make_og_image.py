#!/usr/bin/env python3
"""Draw web/static/og.png, the 1200x630 card shown when a ffext link is unfurled.

Committed as a PNG rather than generated at deploy time: it changes only when
the wordmark or tagline does, and every social scraper that matters refuses SVG.
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "web", "static", "og.png")

W, H = 1200, 630
BG = (22, 24, 31)
BG_GLOW = (36, 30, 62)
FG = (243, 244, 247)
FG_MUTED = (160, 165, 178)
ACCENT = (154, 124, 255)
TRUST_HIGH = (94, 204, 140)


def _font_file(family):
    try:
        return subprocess.run(["fc-match", "-f", "%{file}", family],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def font(size, weight="Bold"):
    """Inter at a specific weight.

    Inter ships as a TrueType *collection*, so the weight is a face index rather
    than a variation axis — the collection is scanned for the requested style
    name instead of trusting fontconfig, which hands back face 0 (Regular) for
    every weight requested.
    """
    path = _font_file("Inter") or _font_file("sans-serif")
    if path:
        for index in range(64):
            try:
                f = ImageFont.truetype(path, size, index=index)
            except OSError:
                break
            if f.getname()[1] == weight:
                return f
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def shield(draw, x, y, size, colour):
    """The favicon's shield outline, scaled into a size x size box."""
    u = size / 24.0
    pts = [(4, 6), (4, 13), (7.2, 19.6), (12, 21.9), (16.8, 19.6), (20, 13), (20, 6),
           (16, 5.2), (12, 2.3), (8, 5.2)]
    draw.polygon([(x + px * u, y + py * u) for px, py in pts], outline=colour, width=max(2, int(2.2 * u)))
    draw.line([(x + 9 * u, y + 12 * u), (x + 11 * u, y + 14 * u), (x + 15 * u, y + 10 * u)],
              fill=colour, width=max(2, int(2.2 * u)), joint="curve")


def main():
    # A soft accent wash bleeding in from the top-left, so the card is not a flat
    # rectangle. Computed at 1/16 scale and upsampled — a per-pixel falloff at
    # full size is slow and, once resized, indistinguishable.
    sw, sh = W // 16, H // 16
    small = Image.new("RGB", (sw, sh))
    px = small.load()
    cx, cy, radius = sw * 0.16, sh * 0.06, sw * 0.78
    for y in range(sh):
        for x in range(sw):
            t = min(1.0, (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / radius)
            k = (1 - t) ** 2
            px[x, y] = tuple(int(BG[c] + (BG_GLOW[c] - BG[c]) * k) for c in range(3))
    img = small.resize((W, H), Image.BICUBIC)

    d = ImageDraw.Draw(img)

    shield(d, 80, 74, 76, ACCENT)
    d.text((176, 82), "ffext", font=font(74), fill=FG)

    d.text((80, 214), "Firefox extensions", font=font(84), fill=FG)
    d.text((80, 306), "you can actually check", font=font(84), fill=ACCENT)

    d.text((80, 432),
           "Open source only, ranked by public source, permission footprint,",
           font=font(30, "Medium"), fill=FG_MUTED)
    d.text((80, 474), "data collection and maintenance — not download counts.",
           font=font(30, "Medium"), fill=FG_MUTED)

    d.line([(80, 552), (1120, 552)], fill=(48, 51, 62), width=2)
    d.text((80, 572), "ffext.iodev.org", font=font(28, "SemiBold"), fill=FG_MUTED)

    label = "addons.mozilla.org, re-ranked"
    f = font(28, "SemiBold")
    d.text((1120 - d.textlength(label, font=f), 572), label, font=f, fill=TRUST_HIGH)

    img.save(OUT, optimize=True)
    print(f"{OUT} ({os.path.getsize(OUT) / 1024:.0f} kB)")


if __name__ == "__main__":
    main()
