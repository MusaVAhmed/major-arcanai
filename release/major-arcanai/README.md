# The Major ArcanAI — digital release v1.3

A 40-card humorous oracle deck of sarcastic skeletons in ornate black-and-white
line art. Twelve classic major arcana (The Lovers, Death, The Tower, …) anchor a
deck of cards life actually deals you (The Two of Deez, The Breast Pump, The
Zoom Meeting).

## What's in the box

| Path | Contents |
|---|---|
| `index.html` | Interactive card-draw page (1 / 3 / 5-card spreads, flip animation). Works offline from a double-click, or host the folder on any static site |
| `cards/` | All 40 cards + card back, 800×1280 px grayscale PNG (5:8 tarot ratio) |
| `cards-web/` | Same set at 500×800 px for web/app use |
| `cards-foil/` · `cards-foil-web/` | **Foil edition**: gold-foil-on-black cards — metallic gold luster linework with glow, same two sizes. Toggle with the ✦ Foil button on the draw page |
| `deck.json` | Machine-readable deck: numeral, name, meaning, image paths per card |
| `GUIDEBOOK.md` | The "little white book" — how to read, plus every card's meaning |

## Using the deck

- **Apps / websites**: load `deck.json`, render images from the `web` paths.
  Filenames are zero-padded by card index so alphabetical order = deck order.
- **Sharing**: `cards-web/` images are sized for social posts and messaging.
- **Print**: these files are screen-resolution. For physical printing, upscale
  from the source art (see the project repo) to 300+ DPI at 70×120 mm plus bleed.

## Credits

Card art generated with Google Gemini from an original card list and per-card
art direction; lettered in Cinzel (SIL Open Font License). Deck concept, card
names, and meanings by the deck's author. Review Google Gemini's terms of
service regarding commercial use of generated images before selling this deck.

v1.0 — August 2026
