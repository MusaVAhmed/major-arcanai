#!/usr/bin/env python3
"""Build the draw-page masthead in the deck's own visual language.

Harvests the ornate corners + thorn-vine edges from the card back, letters
"THE MAJOR / ARCANAI" with the same Cinzel + cartouche idiom as letter.py,
and emits two variants into the release assets:
  masthead.png       bone linework, AI in gold        (classic, dark page)
  masthead-foil.png  flat gold linework, AI in pale   (foil, dark page)
"""
import os
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

CARDS = os.path.dirname(os.path.abspath(__file__))
REL_ASSETS = os.path.join(os.path.dirname(CARDS), 'release', 'major-arcanai', 'assets')
FONT_PATH = os.path.join(CARDS, 'Cinzel.ttf')

W, H = 1500, 600
CORNER = 250                    # corner crop size from the back art
RULES = [(37, 44), (54, 58), (67, 74)]   # triple border rules, offsets from edge

BONE = (233, 227, 211)
GOLD = (204, 151, 57)           # foil.py's flat gold (hsv .106/.72/.80)
GOLD_AI = (212, 169, 78)        # AI accent on the classic masthead
PALE = (255, 233, 168)          # AI accent on the foil masthead


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


def star4(draw, cx, cy, r, fill):
    s = r * 0.28
    draw.polygon([(cx, cy - r), (cx + s, cy - s), (cx + r, cy), (cx + s, cy + s),
                  (cx, cy + r), (cx - s, cy + s), (cx - r, cy), (cx - s, cy - s)], fill=fill)


def diamond(draw, cx, cy, r, fill):
    draw.polygon([(cx - r, cy), (cx, cy - r), (cx + r, cy), (cx, cy + r)], fill=fill)


def crescent(mask, cx, cy, r, flip=False):
    """Waning/waxing crescent: a disc with an offset bite taken out."""
    d = ImageDraw.Draw(mask)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    off = int(r * 0.62) * (-1 if flip else 1)
    bite = ImageDraw.Draw(mask)
    bite.ellipse([cx - r + off, cy - r, cx + r + off, cy + r], fill=0)


def build_frame_mask():
    """Ink mask (255 = line) for the ornate frame, from the card back."""
    back = Image.open(os.path.join(CARDS, 'back.png')).convert('L')
    ink = ImageOps.invert(back)          # lines -> bright
    frame = Image.new('L', (W, H), 0)

    tl = ink.crop((0, 0, CORNER, CORNER))
    tr = tl.transpose(Image.FLIP_LEFT_RIGHT)
    bl = tl.transpose(Image.FLIP_TOP_BOTTOM)
    br = tl.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)
    frame.paste(tl, (0, 0))
    frame.paste(tr, (W - CORNER, 0))
    frame.paste(bl, (0, H - CORNER))
    frame.paste(br, (W - CORNER, H - CORNER))

    # thorn-vine strip along top/bottom between the corners, mirrored tiles
    strip = ink.crop((CORNER, 0, 518, 150))          # 268 wide
    span = W - 2 * CORNER
    x = CORNER
    i = 0
    while x < W - CORNER:
        t = strip.transpose(Image.FLIP_LEFT_RIGHT) if i % 2 else strip
        w = min(strip.width, W - CORNER - x)
        frame.paste(t.crop((0, 0, w, 150)), (x, 0))
        frame.paste(t.crop((0, 0, w, 150)).transpose(Image.FLIP_TOP_BOTTOM), (x, H - 150))
        x += w
        i += 1

    # vine strips down the side gaps between the corners
    side = ink.crop((0, CORNER, 150, 518))
    y = CORNER
    i = 0
    while y < H - CORNER:
        t = side.transpose(Image.FLIP_TOP_BOTTOM) if i % 2 else side
        h = min(side.height, H - CORNER - y)
        frame.paste(t.crop((0, 0, 150, h)), (0, y))
        frame.paste(t.crop((0, 0, 150, h)).transpose(Image.FLIP_LEFT_RIGHT), (W - 150, y))
        y += h
        i += 1
    return frame


def build_text_masks():
    """(main_mask, ai_mask): lettering + cartouche; AI kept separate."""
    main = Image.new('L', (W, H), 0)
    ai = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(main)
    cx = W // 2

    # ---- cartouche pill: THE MAJOR (the cards' numeral-pill idiom) ----
    ef = font(40)
    tr = 14
    s = 'THE MAJOR'
    ew = text_w(d, s, ef, tr)
    star_r = 9
    gap = 16
    pad = 26
    pill_w = int(ew + 2 * (star_r * 2 + gap) + 2 * pad)
    pill_h = 66
    pcy = 215
    box = [cx - pill_w // 2, pcy - pill_h // 2, cx + pill_w // 2, pcy + pill_h // 2]
    d.rounded_rectangle(box, radius=pill_h // 2, outline=255, width=5)
    inset = 9
    d.rounded_rectangle([box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset],
                        radius=(pill_h - 2 * inset) // 2, outline=255, width=2)
    bb = d.textbbox((0, 0), s, font=ef)
    draw_tracked(d, (cx - ew / 2, pcy - (bb[1] + bb[3]) / 2), s, ef, tr, 255)
    star4(d, box[0] + pad + star_r, pcy, star_r, 255)
    star4(d, box[2] - pad - star_r, pcy, star_r, 255)

    # ---- the word: ARCAN (main) + AI (accent) ----
    bf = font(176, weight=800)
    trk = 6
    word_w = text_w(d, 'ARCANAI', bf, trk)
    x0 = cx - word_w / 2
    bb = d.textbbox((0, 0), 'ARCANAI', font=bf)
    wy = 360 - (bb[1] + bb[3]) / 2
    draw_tracked(d, (x0, wy), 'ARCAN', bf, trk, 255)
    ai_x = x0 + text_w(d, 'ARCAN', bf, trk) + trk
    draw_tracked(ImageDraw.Draw(ai), (ai_x, wy), 'AI', bf, trk, 255)

    return main, ai


def colorize(frame, main, ai, line_rgb, ai_rgb):
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    solid_line = Image.new('RGBA', (W, H), line_rgb + (255,))
    solid_ai = Image.new('RGBA', (W, H), ai_rgb + (255,))
    both = frame.point(lambda v: v)  # copy
    both.paste(main, (0, 0), main)
    img.paste(solid_line, (0, 0), both)
    img.paste(solid_ai, (0, 0), ai)
    return img


def main():
    os.makedirs(REL_ASSETS, exist_ok=True)
    frame = build_frame_mask()
    text, ai = build_text_masks()
    # engraver's halo: clear the frame behind the lettering so type sits IN
    # the ornament rather than fighting it
    halo = Image.new('L', (W, H), 0)
    halo.paste(text, (0, 0), text)
    halo.paste(ai, (0, 0), ai)
    halo = halo.filter(ImageFilter.MaxFilter(25))
    frame = ImageChops.subtract(frame, halo)
    colorize(frame, text, ai, BONE, GOLD_AI).save(os.path.join(REL_ASSETS, 'masthead.png'))
    colorize(frame, text, ai, GOLD, PALE).save(os.path.join(REL_ASSETS, 'masthead-foil.png'))
    print('wrote masthead.png + masthead-foil.png', (W, H))


if __name__ == '__main__':
    main()
