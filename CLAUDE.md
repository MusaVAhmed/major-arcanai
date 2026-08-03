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
   to `deck.json`, and copies `cards/attune.js` (the semantic shuffle) and
   `cards/voice.js` (the ears) into the release. Both files in `cards/` are the
   source of truth; never edit the copies under `release/`.
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
  keep it that way.
- One question embedding drives three things via `readFor(q, mode)`: **which
  cards** (softmax over `max(simUpright, simReversed)`), **which face** (the
  better-matching side wins outright — the owner chose the hard rule over a
  calibrated coin), and **which seat** (cosine against per-position prose in
  `POSITIONS`, soft-roulette assigned by `seatByAffinity`). Each card face is
  its own document; `vUp`/`vRev` are cached separately in localStorage.
- The hard orientation rule pulls the attuned reversal rate to ~29-45% (vs 50%
  unattuned) because reversed copy is second-person and punchy while upright
  copy is declarative, and questions match declarative text better. Measured,
  known, accepted. Recentring it is a one-line change if it ever grates.
- **Seat temperature is deliberately colder than selection temperature**
  (`LEANS[lean] / 3`). At the selection temp the seating measured a 9% affinity
  lift and near-uniform seats, i.e. it did nothing. A third of it gives ~20%
  lift and puts a card in its best seat about twice as often as chance. Any failure (offline, CDN down, cold model inside the
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
- **Situational expansions** live in `package.py` as `SITUATIONS` /
  `SITUATIONS_REV`, flow through `deck.json` into the page as `sit` / `sitr`,
  and are appended to the embedded documents by `attune.js`. They are
  MATCHING-ONLY and must never be rendered or put in the guidebook. Card
  meanings are aphorisms; the expansions are the concrete circumstances people
  actually type. Rules, learned the hard way: all 40 or none (a partial pass
  makes expanded cards quieter on unrelated questions and hands the rest an
  unearned edge), roughly 14 words each and never more than ~20 (a long draft
  knocked Strength from rank 4 to 17 by dragging a well-placed short vector off
  target), and re-run the dilution check after editing any of them — every card
  must still rank first when queried with its own meaning.
- Editing an expansion changes the corpus hash, so every cached vector on every
  device silently rebuilds on next load. That is intended; no version bump.
- `corpusSig` in `attune.js` joins its inputs on **literal NUL bytes** (six of
  them, committed). Harmless as a hash delimiter and valid in a JS string, but
  it makes `grep` call the file binary and makes exact-match edits on that line
  bounce. Any tool that strips NULs silently changes the hash and rebuilds every
  cached vector on every device — which is only ever a cost, never a bug.
- **Anchors** (`ANCHORS` in `attune.js`): six prose descriptions of what a
  question is *about*, embedded as their own corpus and cosined against the
  question. `domainOf(v)` is synchronous and free — the vector is already in
  hand and the anchors are already in memory, so it costs six dot products.
  Rules, all measured on 27 questions:
  - They are a **separate corpus**, never folded into `upText`/`revText`, so
    the situational-expansion dilution rule does not apply and editing one
    cannot move a card in the rankings.
  - Every anchor must name a **subject, not a disposition**. The first draft
    had `nerve` ("whether to do the frightening thing") and it robbed all five
    others, because wanting to confess is a love question asked by a
    frightened person. Swapping it for `change` took the set from 59% to 89%.
  - Anchors want **breadth**, the opposite of the expansions: a deliberately
    terse variant scored 67% against the shipped set's 89%.
  - `domMin` (0.06) is the daylight the leader needs over the runner-up before
    the deck claims to know. Gated, it lands 17/18. The 27 cases were written
    in-repo, not typed by a seeker, so it is a sanity check and not a
    calibration — tune it from the Readings log like `TELL_CFG`.
  - Nothing in the reading depends on `dom` yet, deliberately. It is logged
    (`dom`, `lead`, `domGap`) and otherwise inert.
- Three knobs are tunable at runtime without a rebuild, on
  `ARCANAI_ATTUNE.config`: `temp` (driven by the Back Room lean), `seatRatio`
  (seat temperature as a fraction of selection temperature, 0.34), and
  `faceMargin` (dead zone on the orientation call; 0 ships the hard rule,
  ~0.04 hands about a third of cards back to the seeded coin). The Back Room
  also exposes Faces and Seats chips so a seeker can take either decision away
  from the deck; both persist in localStorage and default on.
- **Tells** (`TELL_CFG` / `qtSample` / `fireTell`): the deck feels *how* the
  question was written and answers with a vibration, never a word, and never a
  change to the deal. All of it is derived from the `#q` value sampled over
  time, never from key events — swipe keyboards deliver whole words in one
  event and report an `inputType` that describes the keyboard rather than the
  hand, so counting keystrokes on a phone measures the keyboard. The one
  discriminator that matters is autocorrect versus a change of mind, and it is
  **trough duration, not depth**: autocorrect deletes and reinserts inside a
  tick, a person leaves a dip with width (`troughMs`, 400). Measured on the
  harness: an autocorrect-heavy question logs `raw=30, churn=0`.
- Corollary, and the bug it caused once: **churn must be committed when a dip
  closes as a qualifying trough**, not as characters disappear. Counting on the
  way down let autocorrect pile up 30 chars of "rewriting" on a question typed
  straight through and fire the wrong tell. `QT.raw` keeps the uncommitted
  total for the log only — it is the measure of how noisy a given keyboard is.
- `.leanrow` is `display:none` unless `#settings.att` — the lean rows only
  exist when attunement is on. Anything appended to the Back Room that should
  survive attunement being off must use `.srow` instead.
- `?tells` (or `?debug`) appends a Readings panel to the Back Room: a rolling
  60-entry log in localStorage that survives reloads, with Copy / Clear / Forget
  questions. The thresholds in `TELL_CFG` are **guesses pending real thumbs on
  a real phone** — they were set to be tuned from that log, the way the lean
  stops were. `?debug` also adds the gyro overlay bar; `?tells` does not.
- A tell arrives as a vibration, as light, or both (`TELLMODE`, Back Room
  "How it answers"). The default is capability-picked: **iOS has no vibration
  API at all**, so `CAN_BUZZ` false defaults to light. The haptic patterns
  must **not** be translated to light one-for-one — they are pulses 90ms
  apart, which as light is a 10Hz strobe, and WCAG 2.3.1 puts the seizure
  threshold at 3 flashes/second. `#tellglow` re-expresses the same signatures
  as *breaths*, every one under 2Hz, peaking at .26 alpha at the screen edge
  and fully transparent across the middle 40%. It is one static gradient,
  painted once and only ever composited at a different opacity, so no card
  layer is touched and nothing repaints. Reduced motion kills the light and
  keeps the buzz: a vibration is not visual motion.
- `idle(wipe)`: **finishing a reading wipes the question**, because asking the
  deck the same thing again until it says something kinder is the one thing
  tarot is strict about. Only the two end-of-reading paths pass `true` (the
  again button and the popstate off a spread). A spread-type switch also calls
  `idle()` and must NOT wipe — losing what you typed just for changing One to
  Cross is infuriating.
- **A flick is not a shake.** A wrist flick throws as much linear acceleration
  as a deliberate shake, so the card jumper cannot be told apart by force: it
  is gated on rotation being *low* (`|rate| < FLICK_RATE`) as well as force
  being high. It is also disabled entirely in Cross mode, and the idle hint
  drops its "shake it and one may jump" line there, because a seeker who asked
  for ten cards did not ask for one. `SHAKE_MAG` and `FLICK_RATE` still want
  tuning against a real wrist.
- **Ask out loud** (`voice.js`, `Xenova/whisper-tiny.en` q8, ~40 MB, lazy):
  nothing downloads until the dot beside `#q` is tapped, and the model fetch
  starts *while* the seeker is still speaking — the only free time the feature
  gets. Audio is decoded to 16 kHz mono, the mic track is stopped before
  transcription begins, and the clip is discarded; nothing leaves the page.
  `voice.js` injects its own button, so a browser that cannot record never
  grows one, and sets `body.canvoice` so the Back Room row (`.srow voicerow`,
  never `.leanrow` — speaking has nothing to do with attunement) is not a dead
  switch. The toggle sets `body.novoice`, which is what actually hides the dot.
- The mic button keeps a 48px touch target but wears its border on `::before`
  as a 30px hairline ring, so the tap area and the visible control can
  disagree — a 48px bordered circle beside a 35px field looks absurd. Its
  width and `body.canvoice .ask input`'s **symmetric** padding are coupled: the
  padding must exceed the button width or the question runs under the icon,
  and it stays symmetric so the placeholder keeps its optical centre. Measured
  at 360/412/800/1280, 6px clearance. `#vsay` is absolutely positioned so a
  status line never shifts the table, and is shrunk inside the landscape-short
  block where `.ask` gives up the margin it was borrowing.
- **Auto-stop** (`VAD` in `voice.js`, exposed at `ARCANAI_VOICE.config` so it
  can be tuned from a console on the phone, like `ARCANAI_ATTUNE.config`): an
  `AnalyserNode` on the live stream, no extra model. Every level is measured
  against the room — the first `calibMs` is sampled as the noise floor — because
  a quiet bedroom and a kitchen with a fridge are orders of magnitude apart and
  a fixed threshold either never fires in one or fires constantly in the other.
  `startMul` (2.2) sits above `stopMul` (1.5) deliberately: with a single
  threshold the level flaps across it on every syllable boundary and the
  silence timer resets forever. Measured on a synthetic stream: `silenceMs`
  1400 → stops 1383 ms after true silence, 700 → 762 ms, both inside one 50 ms
  tick. `noSpeechMs` gives the tap back after 6 s rather than waiting out the
  20 s cap. Still guesses against a real room.
- **Whisper does not return nothing when given nothing.** Six seconds of a
  silent stream transcribed to "you" — it fills quiet with the pleasantries
  that fill quiet in its training data, and that sailed past the empty-string
  guard and into `#q`. The real defence is the VAD flag: `heard` is tri-state,
  and only `false` (the watcher ran and heard nobody) refuses to transcribe.
  `null` must keep transcribing or the feature dies on any engine where the
  analyser cannot build. `NOISE` is the second line, for audio that cleared the
  level gate on a door slam and still had no words in it.
- A transcript lands in one `input` event, so **a spoken question must not be
  read as typing** — to the sampler it is the most decisive question ever
  written and would fire `resolute` on every voice draw. `voice.js` dispatches
  `arcanai:spoken` after the `input` event; the page resets `QT` and sets
  `QT.spoke`, and `tellFor` returns null for every typing signature. The echo
  tell still fires, correctly: it is about the question, not the hand, and the
  deck can absolutely recognise something you have asked it before out loud.
- The echo tell reuses `ARCANAI_ATTUNE.vecFor()`, which deliberately refuses to
  boot the model on its own, so a page with attunement off never pays 23 MB for
  a side feature. No echo without a reading, which is correct: the deck was not
  listening that closely.
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
  line self-kill the shell (exit 144). Kill by PID from `pgrep -a`. The
  bracket trick (`tellsr[v].py`) only saves you if the *unbracketed* string
  appears nowhere else on that command line — so never put the kill and the
  relaunch of the same process in one command. Bit me twice again this way.
