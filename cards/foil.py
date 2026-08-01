#!/usr/bin/env python3
"""Foil edition: dark cards with iridescent linework + glow. Pure PIL, no numpy."""
import os, glob, math, colorsys, sys
from PIL import Image, ImageOps, ImageFilter, ImageChops

CARDS = os.path.dirname(os.path.abspath(__file__))
REL = os.path.join(os.path.dirname(CARDS), 'release', 'major-arcanai')
BG = (10, 9, 8)            # warm near-black stock
GLOW_STRENGTH = 0.45


def palette_luts():
    """Flat metallic gold — no baked-in lighting; the page's dynamic sheen
    is the only light source."""
    r, g, b = [], [], []
    for i in range(256):
        cr, cg, cb = colorsys.hsv_to_rgb(0.106, 0.72, 0.80)
        r.append(int(cr * 255)); g.append(int(cg * 255)); b.append(int(cb * 255))
    return r, g, b


def diagonal_ramp(w, h):
    """0..255 ramp running along the diagonal, with a soft wobble."""
    big = max(w, h) * 2
    ramp = Image.linear_gradient('L').resize((big, big))
    ramp = ramp.rotate(45, resample=Image.BILINEAR)
    left = (big - w) // 2
    top = (big - h) // 2
    ramp = ramp.crop((left, top, left + w, top + h))
    # wobble: blend a perpendicular ramp in softly for an oil-slick bend
    ramp2 = Image.linear_gradient('L').resize((w, h)).rotate(180)
    return ImageOps.autocontrast(Image.blend(ramp, ramp2, 0.18))


def foil(src, out):
    im = Image.open(src).convert('L')
    w, h = im.size
    mask = ImageOps.invert(im)                       # lines -> white
    lut_r, lut_g, lut_b = palette_luts()
    ramp = diagonal_ramp(w, h)
    grad = Image.merge('RGB', (ramp.point(lut_r), ramp.point(lut_g), ramp.point(lut_b)))

    card = Image.new('RGB', (w, h), BG)
    # crisp foil lines only — no glow, like real foil stamping
    card = Image.composite(grad, card, mask)
    card.save(out, optimize=True)


def main():
    jobs = []
    for sub, dark in (('cards', 'cards-foil'), ('cards-web', 'cards-foil-web')):
        os.makedirs(os.path.join(REL, dark), exist_ok=True)
        for f in sorted(glob.glob(os.path.join(REL, sub, '*.png'))):
            jobs.append((f, os.path.join(REL, dark, os.path.basename(f))))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for src, out in jobs:
        if only and only not in os.path.basename(src):
            continue
        foil(src, out)
        print('foiled', out)


if __name__ == '__main__':
    main()
