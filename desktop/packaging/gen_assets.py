# -*- coding: utf-8 -*-
"""Genera los assets de build: icono .ico de la app y bitmaps del instalador.

Requiere Pillow (solo en build, no en runtime). Estilo de la marca: cuadrado
blanco redondeado con "J" negra (como el logo de la landing) sobre fondo negro.
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "ui", "fonts", "Outfit.ttf")


def _rounded(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def make_logo(size, margin_ratio=0.0):
    """Cuadrado blanco redondeado con J negra, canvas transparente."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = int(size * margin_ratio)
    box = (m, m, size - m, size - m)
    _rounded(d, box, radius=int((size - 2 * m) * 0.25), fill=(250, 250, 250, 255))
    inner = size - 2 * m
    try:
        font = ImageFont.truetype(FONT, int(inner * 0.62))
    except Exception:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), "J", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = m + (inner - tw) / 2 - bbox[0]
    y = m + (inner - th) / 2 - bbox[1] - inner * 0.02
    d.text((x, y), "J", font=font, fill=(0, 0, 0, 255))
    return img


def make_ico(path):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = make_logo(256, margin_ratio=0.02)
    base.save(path, format="ICO", sizes=[(s, s) for s in sizes])
    print("icono:", path)


def make_wizard_images(path_big, path_small):
    """BMPs del instalador Inno: lateral 164x314 y cabecera 55x58 (modern usa
    tamanos flexibles; estos son los clasicos que Inno escala)."""
    big = Image.new("RGB", (164, 314), (0, 0, 0))
    d = ImageDraw.Draw(big)
    # grid sutil estilo landing
    for x in range(0, 164, 32):
        d.line([(x, 0), (x, 314)], fill=(10, 10, 10))
    for y in range(0, 314, 32):
        d.line([(0, y), (164, y)], fill=(10, 10, 10))
    logo = make_logo(56)
    big.paste(logo, (54, 96), logo)
    try:
        f = ImageFont.truetype(FONT, 17)
    except Exception:
        f = ImageFont.load_default()
    d.text((82, 170), "JobHunter", font=f, fill=(250, 250, 250), anchor="mm")
    try:
        f2 = ImageFont.truetype(FONT, 10)
    except Exception:
        f2 = ImageFont.load_default()
    d.text((82, 192), "Empleo con IA", font=f2, fill=(120, 120, 120), anchor="mm")
    big.save(path_big, format="BMP")

    small = Image.new("RGB", (55, 58), (0, 0, 0))
    logo2 = make_logo(40)
    small.paste(logo2, (7, 9), logo2)
    small.save(path_small, format="BMP")
    print("wizard:", path_big, path_small)


if __name__ == "__main__":
    make_ico(os.path.join(HERE, "icon.ico"))
    make_wizard_images(os.path.join(HERE, "wizard-side.bmp"),
                       os.path.join(HERE, "wizard-small.bmp"))
