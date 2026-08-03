#!/usr/bin/env python3
"""Build the two contact sheets — the fastest way to catch a house-style break.

Reading 46 cards one at a time is how a drifting skull, a stray crescent moon or
a card that came back at the wrong aspect goes unnoticed. Side by side in one
grid they are obvious: the eyes on XLIV were caught this way, and so were the
moons that the two "De-moon" commits removed.

    python3 contact_sheet.py              # both sheets
    python3 contact_sheet.py raw          # cards/contact_sheet.jpg only
    python3 contact_sheet.py lettered     # lettered/contact_sheet_lettered.jpg

Sources are the manifest order, so the sheet is always the deck as it actually
is. Cards whose art is missing (status "pending") leave a slot with a cross
through it rather than shifting everything after them.
"""
import json, os, sys
from PIL import Image, ImageDraw

CARDS = os.path.dirname(os.path.abspath(__file__))
SIZE = 2000          # the two committed sheets are 2000x2000; keep it stable
COLS = 8
PAD = 6              # gutter between cards, px
BG = (255, 255, 255)


def sheet(srcdir, out, quality=88):
    manifest = json.load(open(os.path.join(CARDS, 'manifest.json'), encoding='utf-8'))
    cards = manifest['cards']
    rows = -(-len(cards) // COLS)                      # ceil
    cw = (SIZE - PAD * (COLS + 1)) // COLS
    # cards are ~5:8; derive cell height from the first card actually present
    ratio = 1280 / 800
    for i, c in enumerate(cards):
        p = os.path.join(srcdir, f"{i:02d}_{c['slug']}.png")
        if os.path.exists(p):
            w, h = Image.open(p).size
            ratio = h / w
            break
    ch = int(cw * ratio)
    im = Image.new('RGB', (SIZE, PAD + rows * (ch + PAD)), BG)
    d = ImageDraw.Draw(im)
    missing = []
    for i, c in enumerate(cards):
        x = PAD + (i % COLS) * (cw + PAD)
        y = PAD + (i // COLS) * (ch + PAD)
        p = os.path.join(srcdir, f"{i:02d}_{c['slug']}.png")
        if not os.path.exists(p):
            missing.append(c['slug'])
            d.rectangle([x, y, x + cw, y + ch], outline=(200, 200, 200))
            d.line([x, y, x + cw, y + ch], fill=(200, 200, 200))
            d.line([x + cw, y, x, y + ch], fill=(200, 200, 200))
            continue
        card = Image.open(p).convert('RGB').resize((cw, ch), Image.LANCZOS)
        im.paste(card, (x, y))
    im.save(out, quality=quality, optimize=True)
    print(f"wrote {out}  {im.size[0]}x{im.size[1]}  {len(cards) - len(missing)}/{len(cards)} cards"
          + (f"  MISSING: {', '.join(missing)}" if missing else ""))


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'both'
    if which in ('both', 'raw'):
        sheet(CARDS, os.path.join(CARDS, 'contact_sheet.jpg'))
    if which in ('both', 'lettered'):
        sheet(os.path.join(CARDS, 'lettered'),
              os.path.join(CARDS, 'lettered', 'contact_sheet_lettered.jpg'))


if __name__ == '__main__':
    main()
