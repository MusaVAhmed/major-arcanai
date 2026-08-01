#!/usr/bin/env python3
"""Composite Roman numeral cartouche + name banner onto generated card art."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

CARDS_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(CARDS_DIR, 'Cinzel.ttf')
OUT_DIR = os.path.join(CARDS_DIR, 'lettered')
os.makedirs(OUT_DIR, exist_ok=True)

INK = (26, 26, 26, 255)
PAPER = (255, 255, 255, 255)


def font(size, weight=700):
    f = ImageFont.truetype(FONT_PATH, size)
    f.set_variation_by_axes([weight])
    return f


def text_w(draw, s, f, tracking):
    return sum(draw.textlength(c, font=f) for c in s) + tracking * (len(s) - 1)


def draw_tracked(draw, xy, s, f, tracking, fill):
    x, y = xy
    for c in s:
        draw.text((x, y), c, font=f, fill=fill)
        x += draw.textlength(c, font=f) + tracking


def diamond(draw, cx, cy, r, fill):
    draw.polygon([(cx - r, cy), (cx, cy - r), (cx + r, cy), (cx, cy + r)], fill=fill)


def star4(draw, cx, cy, r, fill):
    s = r * 0.28
    draw.polygon([(cx, cy - r), (cx + s, cy - s), (cx + r, cy), (cx + s, cy + s),
                  (cx, cy + r), (cx - s, cy + s), (cx - r, cy), (cx - s, cy - s)], fill=fill)


def letter_card(src, num, name):
    im = Image.open(src).convert('RGBA')
    W, H = im.size
    d = ImageDraw.Draw(im)
    scale = W / 848.0

    # ---- top cartouche (pill on the frame band) ----
    nf = font(int(44 * scale))
    tracking = int(3 * scale)
    nw = text_w(d, num, nf, tracking)
    star_r = int(9 * scale)
    gap = int(16 * scale)
    pad = int(26 * scale)
    pill_w = nw + 2 * (star_r * 2 + gap) + 2 * pad
    pill_h = int(64 * scale)
    cx, cy = W // 2, int(46 * scale)
    box = [cx - pill_w // 2, cy - pill_h // 2, cx + pill_w // 2, cy + pill_h // 2]
    d.rounded_rectangle(box, radius=pill_h // 2, fill=PAPER, outline=INK, width=int(5 * scale))
    inset = int(9 * scale)
    d.rounded_rectangle([box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset],
                        radius=(pill_h - 2 * inset) // 2, outline=INK, width=int(2 * scale))
    bb = d.textbbox((0, 0), num, font=nf)
    ty = cy - (bb[1] + bb[3]) / 2
    draw_tracked(d, (cx - nw / 2, ty), num, nf, tracking, INK)
    star4(d, box[0] + pad + star_r, cy, star_r, INK)
    star4(d, box[2] - pad - star_r, cy, star_r, INK)

    # ---- bottom banner ----
    banner_h = int(92 * scale)
    bcy = H - int(74 * scale)
    max_text_w = W * 0.66
    size = int(46 * scale)
    while size > int(22 * scale):
        bf = font(size)
        tr = int(size * 0.10)
        tw = text_w(d, name, bf, tr)
        if tw <= max_text_w:
            break
        size -= 2
    dia_r = int(7 * scale)
    pad = int(30 * scale)
    ban_w = min(int(tw + 2 * (dia_r * 2 + int(14 * scale)) + 2 * pad), int(W * 0.88))
    bx = [W // 2 - ban_w // 2, bcy - banner_h // 2, W // 2 + ban_w // 2, bcy + banner_h // 2]
    d.rounded_rectangle(bx, radius=int(14 * scale), fill=PAPER, outline=INK, width=int(5 * scale))
    inset = int(9 * scale)
    d.rounded_rectangle([bx[0] + inset, bx[1] + inset, bx[2] - inset, bx[3] - inset],
                        radius=int(8 * scale), outline=INK, width=int(2 * scale))
    bb = d.textbbox((0, 0), name, font=bf)
    ty = bcy - (bb[1] + bb[3]) / 2
    draw_tracked(d, (W / 2 - tw / 2, ty), name, bf, tr, INK)
    diamond(d, bx[0] + pad + dia_r, bcy, dia_r, INK)
    diamond(d, bx[2] - pad - dia_r, bcy, dia_r, INK)

    return im.convert('RGB')


def main():
    manifest = json.load(open(os.path.join(CARDS_DIR, 'manifest.json')))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    idx = {c['slug']: (i, c) for i, c in enumerate(manifest['cards'])}
    for slug, (i, c) in idx.items():
        if only and slug != only:
            continue
        src = os.path.join(CARDS_DIR, f"{i:02d}_{slug}.png")
        out = os.path.join(OUT_DIR, f"{i:02d}_{slug}.png")
        im = letter_card(src, c['num'], c['name'].upper())
        im.save(out)
        print('lettered', out)


if __name__ == '__main__':
    main()
