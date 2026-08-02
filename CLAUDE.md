# The Major ArcanAI — project notes for Claude

40-card humorous skeleton tarot deck ("The Major ArcanAI", formerly "The
Audacity Tarot"). Everything ships from `release/major-arcanai/`; the site
deploys automatically to https://musavahmed.github.io/major-arcanai/ via
`.github/workflows/pages.yml` on every push to `main`.

## Build pipeline (run from `cards/`, in this order)

1. `python3 letter.py [slug]` — composites numeral cartouche + name banner
   (Cinzel bold, `cards/Cinzel.ttf`) onto raw art → `cards/lettered/`.
   Base art must stay text-free; re-letter after any re-roll.
2. `python3 package.py` — crops each lettered card to its ink bbox and
   stretches to a uniform art box (744×1223 in an 800×1280 canvas — uniformity
   beats aspect purity, max ~12% stretch is invisible on this art style) →
   `release/major-arcanai/cards{,-web}/`, plus `deck.json` and `GUIDEBOOK.md`.
3. `python3 foil.py [slug]` — gold-foil edition: FLAT metallic gold on warm
   black stock, crisp lines, no glow, no luster bands — the draw page's
   dynamic sheen is deliberately the only lighting → `cards-foil{,-web}/`.
4. `python3 build_draw_page.py` — regenerates `index.html`, appends foil paths
   to `deck.json`, and copies `cards/attune.js` (the semantic shuffle) into the
   release. `cards/attune.js` is the source of truth; never edit the copy.
5. `python3 masthead.py` — draw-page masthead images (classic + foil) built
   from the card back's ornament + Cinzel lettering → `release/.../assets/`.
   Rerun only if `back.png` or the title design changes.

`cards/manifest.json` is the deck source of truth: numeral, name, scene
(doubles as the Gemini image prompt), meaning lives in `package.py`.

## Hard-won constraints — do not regress

- **Draw page mobile effects**: no `mix-blend-mode` and no repainted gradients
  on card layers — Android's compositor flashes them white during touch-drag
  layer promotion. The foil sheen is a luminance-masked container with a
  GPU-transformed `.glint` child, and it fades out entirely while
  `body.dragging`.
- **Gyro must never call `layoutStack()` during a drag** (`S.dragging` guard)
  — it fights the finger and looks choppy.
- Gyro handling: gamma only (vertical is locked deliberately), low-passed
  0.8/0.2, fan direction hops sides with tilt sign with hysteresis. The same
  smoothed TILT drives a subtle 3D card tilt via the `--tiltY` CSS var on the
  `.t3d` wrappers (±5.6° max, skipped under reduced motion).
- Card XI is *The Audacity* — the deck was renamed, the card was not.
- Deals are seeded (entropy pool + question text + clock → mulberry32), not
  `Math.random` — keep new randomness sources flowing through `stir()`/`makeRng`.
  Card of the Day must stay date-deterministic.
- The idle pile listens to pointer events (tap deals, rub shuffles) — a
  synthetic `el.click()` no longer draws; dispatch pointerdown/up in tests.
- Spread position labels live on the pick objects (`pick.label`), not in
  `LABELS` lookups at render time — clarifiers and jumpers rely on this.
- The draw page's CSS is **mobile-first**: base rules are phone portrait, and
  only `min-width` queries (640 / 1024) add desktop behaviour, plus one
  `(orientation: landscape) and (max-height: 560px)` block that sizes cards off
  `dvh` because height is the scarce axis there. Don't reintroduce `max-width`
  queries — they fight the base layer.
- `#table` carries `--n` (card count, set in `draw()`, `idle()`, and after a
  clarifier). From 640px up, `.slot` width is `min(clamp(...), (100% - gaps)/--n)`
  so a five-card spread stays on one row. Any new code that appends a slot must
  update `--n`.
- **Semantic attuned shuffle** (`attune.js`, transformers.js +
  `Xenova/all-MiniLM-L6-v2`, ~23 MB from the HF CDN, browser-cached): the
  question is embedded and cosine-matched against card text. `draw()` is
  `async` for it, but the ternary short-circuits when there is no question or
  attunement is off, so an ordinary deal never awaits and stays synchronous —
  keep it that way. Any failure (offline, CDN down, cold model inside the
  450 ms budget) resolves to `null` and the keyword `THEME_HINTS` path takes
  over; both set `leaned`, which drives the "the deck leaned in" caption.
- Attunement strength is the Back Room's three-stop lean (Subtle / Attuned /
  Shameless), which writes `ARCANAI_ATTUNE.config.temp` from the page's `LEANS`
  map at draw time — the page is authoritative, `attune.js`'s own default only
  matters if the map is bypassed. The stops were measured, not guessed: 400
  five-card draws per question showed `temp: 0.06` putting one card in 92% of
  draws (reads as stacked), so the stops are 0.30 / 0.15 / 0.07 for roughly
  1.7x / 2.3x / 4x a card's baseline rate. Keep the UI in named stops — a
  softmax temperature slider would break the deck's voice. There is NO reliable gibberish detector — nonsense
  embeds to real points (max cosine for real questions 0.149–0.389 vs 0.066–0.323
  for word salad, fully overlapping), so a nonsense question still leans. Don't
  spend another session trying to gate it on similarity.
- Only the lightbox image (`data-big`) gets a `srcset` onto the 800×1280 set;
  spreads and gallery thumbs stay on the 500×800 web set — full-res everywhere
  would cost a phone megabytes per deal. `applyFoil()` rewrites `src` **and**
  `srcset`.
- `audacity_*.png` and `samples/` were scrubbed from git history on request —
  they are gitignored; never re-add them.

## Testing

- Desktop harness can't reproduce gyro-related bugs; test on a real phone
  (user's device: Samsung S24 Ultra). For quick HTTPS on a phone use
  `cloudflared tunnel --url http://localhost:8642 --protocol http2`
  (QUIC/UDP times out on this network).
- To emulate a phone viewport in Chrome, use a scaled iframe harness
  (window resizing is blocked by the KDE WM). Synthetic pointer events carry
  compressed timestamps that inflate swipe-velocity readings — space dispatched
  moves ≥80 ms apart.
- Careful with `pkill -f`: patterns that appear in the shell's own command
  line self-kill the shell (exit 144). Kill by PID from `pgrep -a`.
