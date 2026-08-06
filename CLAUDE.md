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
   to `deck.json`, and copies `cards/seats.js` (the positions), `cards/attune.js`
   (the semantic shuffle) and `cards/voice.js` (the ears) into the release. All
   three files in `cards/` are the source of truth; never edit the copies under
   `release/`. A new sibling script needs three edits, not one: create it in
   `cards/`, add its `shutil.copy`, add its `<script>` tag.
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
  `pick.lens` rides along the same way and for the same reason: a card dealt
  outside a spread (clarifier, jumper, Card of the Day) simply has no lens and
  reads exactly as it did before seats existed. Both persist through
  `saveSpread`/`restoreSpread`, or a tab switch would silently reframe a
  reading.
- **`seats.js` is the one definition of the positions**, read by two consumers
  with opposite needs. `prose` is matching text: long, plain, embedded by
  `attune.js` to decide which card belongs in which seat, and never displayed.
  `lens` is display text: short, lowercase, ends in a colon, printed in front
  of the card's meaning so the same card reads differently depending on where
  it landed — "what's in the way: Keep going. You're closer than you think."
  `label` exists only because the matching prose wants "Hopes and Fears" (an
  ampersand embeds like punctuation) and the page wants "Hopes & Fears".
  Editing `prose` changes `corpusSig` and rebuilds every cached vector on every
  device; editing `lens` costs nothing. The extraction out of `attune.js` was
  proven hash-neutral by diffing the derived `posText` before and after — do
  the same if you ever reshape it. Both consumers degrade rather than throw if
  the file is missing: the page falls back to bare labels, `attune.js` warns
  and disables seating with selection untouched.
- The draw page's CSS is **mobile-first**: base rules are phone portrait, and
  only `min-width` queries (640 / 1024) add desktop behaviour, plus one
  `(orientation: landscape) and (max-height: 560px)` block that sizes cards off
  `dvh` because height is the scarce axis there. Don't reintroduce `max-width`
  queries — they fight the base layer.
- `#table` carries `--n` (card count, set in `draw()`, `idle()`, and after a
  clarifier). From 640px up, `.slot` width is `min(clamp(...), (100% - gaps)/--n)`
  so a five-card spread stays on one row. Any new code that appends a slot must
  update `--n` — **except when the table is laid out**, where `--n` is the row's
  column count and must stay at the dealt count so a clarifier wraps to a second
  row instead of squeezing the spread.
- **Laid out vs the stack** (`#table.laid` + `.celtic`/`.row`, `laidPref`,
  `swapView`). "Laid out" is the Cross's way of reading — every card small and on
  the table at once, its caption suppressed and pulled into `#ccap` by
  `selectSlot`, a second tap on a selected card opening the box. `.laid` carries
  all of that; `.celtic` and `.row` are only the two shapes it comes in. The
  Cross is always laid out, on every screen. Three and Five are laid out **on
  touch only, and only by preference**: `laidPref`
  (`localStorage['arcanai-spreadview']`, grid by default) picks between the row
  and the swipeable stack, and `#vswap` swaps them mid-reading.
  - The swap goes out through `saveSpread` and back through `draw`'s restore
    path — the same road a tab switch travels — so the cards, the faces, which
    are turned over, the clarifiers and the reading's `rid` all survive it, and
    nothing re-deals. Both views index `revealed` into `CUR`, which is what makes
    the two halves of that round trip compatible; keep it that way. A clarifier
    comes back at the end of the row rather than beside its parent, exactly as it
    already did on a tab switch.
  - `.row` sets `min-height:0`: `#table`'s 280px floor exists to stop the idle
    pile jumping, and under one row of 60px cards it is a hole above the reading.
  - The swap is offered only where both views exist — touch, more than one card,
    fewer than ten (`body.canswap`). Desktop never sees it and never gets `.laid`
    outside the Cross.
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
  and are appended to the embedded documents by `attune.js`. They are written
  for matching and stay out of the caption and the guidebook, where they would
  flatten copy meant to land in one line. Two places print them, both
  deliberate and both behind a deliberate second action: `openCardBox` shows
  the showing face's expansion under the caption, and the gallery lightbox
  shows both faces' because it is the reference view. Nowhere else. The card
  box is reachable from every spread — a second tap on a card you already
  turned over, which means `tapTop` in stack mode, a second tap on an already
  selected card when the spread is laid out, and a second click on the slot on
  desktop. Card
  meanings are aphorisms; the expansions are the concrete circumstances people
  actually type. Rules, learned the hard way: all 46 or none (a partial pass
  makes expanded cards quieter on unrelated questions and hands the rest an
  unearned edge — the number is "every card in the deck", not literally 46),
  roughly 14 words each and never more than ~20 (a long draft
  knocked Strength from rank 4 to 17 by dragging a well-placed short vector off
  target), and re-run the dilution check after editing any of them — every card
  must still rank first when queried with its own meaning.
- **The dilution check is a script now**, not a ritual: `cards/deck_dump.py`
  (AST-reads the four dicts out of `package.py`, so it never imports PIL) piped
  into `cards/dilution_check.mjs` (node + `@huggingface/transformers@3.3.3`,
  same model and dtype as the page, `upText`/`revText` copied byte-for-byte from
  `attune.js`). Give it a baseline to diff ranks against:
  `python3 deck_dump.py > /tmp/new.json && git show HEAD:cards/package.py >
  /tmp/base.py && python3 deck_dump.py /tmp/base.py > /tmp/base.json && EMB1=1
  node dilution_check.mjs /tmp/new.json /tmp/base.json`. It also prints nearest
  neighbours, new-vs-new collisions, and `QFILE=` real questions.
- **Always pass `EMB1=1` before believing a rank change.** The page embeds the
  whole corpus in one call and q8 pads every sequence to the longest in the
  batch, so *adding* a long card perturbs unrelated vectors by 0.003–0.008 —
  enough to swap two cards sitting 0.005 apart and look exactly like dilution.
  Adding the six new cards "moved" Perseverance from rank 1 to 2 this way; at
  batch-of-one the rank diff was exactly zero. Any change under ~0.01 is noise
  until re-checked one text per forward pass. Do not rewrite copy over it.
- Editing an expansion changes the corpus hash, so every cached vector on every
  device silently rebuilds on next load. That is intended; no version bump.
- `corpusSig` in `attune.js` joins its inputs on **literal NUL bytes** — four
  of them, committed, all on the `const s = MODEL + …` line. (The `posText` /
  `ancText` line below it looks identical in an editor but carries ordinary
  `\u0000` escape *text*; only the first line has real NULs. This note used to
  say six, which is the two lines' escapes added together.) Harmless as a hash
  delimiter and valid in a JS string, but it makes `grep` call the file binary
  and makes exact-match edits on that line bounce. Any tool that strips NULs
  silently changes the hash and rebuilds every cached vector on every device —
  which is only ever a cost, never a bug. `tr -dc '\000' < cards/attune.js |
  wc -c` should print 4.
- **Resonance** (`resonanceOf` / `backgroundStats` in `attune.js`): how the
  cards actually dealt relate to each other, which replaces counting theme
  tags. Every pair of showing faces is cosined and **z-scored against a
  background distribution** computed once at vector-build time and cached in
  the `LS_KEY` blob (hence v3). Measured, and the numbers are the whole point:
  - The background is every pair of faces belonging to *different* cards —
    3120 pairs, mean **0.196**, sd **0.096**, range −0.10 to 0.63. A card's own
    two faces are excluded because they are each other's nearest neighbours by
    a mile and can never be dealt together; including them inflates the mean
    and flattens every z the deck would ever report.
  - Over 200 seeded three-card draws (`cards/resonance_bench.html`, seed
    20260803): pair z runs p10 −0.92, p50 0.27, p90 1.62, max 4.52. Strongest
    pair ≥ 1.0 in **56.5%** of spreads, tensest ≤ −1.0 in **23.5%**. Those two
    plus a reversal clause and a cohesion fallback are what gets the fire rate
    over 80% without any single line dominating.
  - With three cards `revShare` is quantized to thirds, so ≥0.34, ≥0.5 and
    ≥0.67 are the *same* 41.5% of spreads. Phrase reversal rules in counts
    ("two of the three"), never in shares.
  - **The verdict must not depend on `dom`.** On twelve colloquial questions
    the anchor gate returned no domain for six of them. `domMin` was tuned on
    27 questions written in-repo; real phrasing clears it about half the time.
    Domain is a bonus clause when present, never a driver.
- `resonanceOf` takes DECK indices and returns positions in the *drawn* array
  (`i`, `j`, `loudest`, `quietest`), because callers want the seat and the
  label, not the card number.
- **The verdict** (`RESONANT` / `resonantVerdict` / `tagVerdict` in
  `build_draw_page.py`). Eight rules over the resonance numbers, three lines
  each. Where several fire the deck takes the one **furthest past its own
  threshold**, not the first in priority order — priority let the commonest
  rule win every time. Measured on the bench, 200 seeded three-card draws at 46
  cards: fire rate **95.5%**, commonest single line **9.9%** of firings, **24 of
  24** lines used, nothing falling through to the tag counter. (The older 94% /
  13.3% / 22-of-24 figures in this file were measured at 40 cards and before the
  `haunt` rule existed; both bench runs since the deck grew agree on the numbers
  above.)
  - `GAPSCALE` (5) converts the odd-one-out / loudest-card cosine gaps into the
    z-scores' units so they can be compared. It was 8 and that overcorrected:
    `loud` took a third of all firings and the commonest line hit 14.9% against
    a 15% ceiling — a pass on one seed and a fail on the next. At 5 those two
    behave as the floor they are meant to be.
  - `COHGAIN` (2.5) is why `chorus` and `scatter` ever win. Cohesion is a
    *mean* of pair z-scores, so when a whole spread agrees some pair inside it
    always agrees harder and `twin` took the line every time — at gain 1
    `chorus` won once in 200 draws and two of its three variants had never been
    seen. The gain applies to both tails of the same statistic; treating them
    differently would be arbitrary. It is what lets a whole-spread observation
    outrank a two-card one.
  - The odd/loud rules are gated at a 0.08 cosine gap because the median gap is
    0.10 — ungated, the deck calls a card "the least related" on a coin toss,
    and it looks broken when the card is obviously on topic. The Last Straw
    came up as least-related to "should I quit my job" during tuning.
  - Line variants are chosen by `xmur3` over the card names, never `rng`: a
    restored spread has to say what it said before the tab switch. `xmur3`'s
    tap returns a **uint32**, not a float — `% bank.length`, never `* len`.
  - `QV` (the question vector, kept from the deal) is what gates the whole
    resonant path; without it `showVerdict` falls back to the nine tag strings,
    unchanged. `draw()` restores `QV` on a restored spread too, via `vecFor`,
    which refuses to boot the model on its own — so an unattuned deal still
    never awaits.
  - Verdict copy carrying a count must use the `{n}`, `{nOthers}` or `{revN}`
    slots. A line that says "three" reads wrong the moment a Cross is dealt.
- **Recurring-card memory was removed** (was `CARDLOG_KEY` / `logCard` /
  `priorSightings` / the `haunt` verdict / the "Forget cards" Back Room row).
  The deck logged every card it revealed so it could remark when one kept
  coming back. It read as nagging rather than as noticing, and the owner asked
  for it gone. Do not reintroduce it without asking.
  - `boot()` now sweeps `arcanai-cardlog` so the old log does not sit in
    localStorage forever on devices that used it. That one line is all that
    remains of the feature; it can go once the deck has no returning users on
    an old build, which is never, so leave it.
  - `RID` went with it — its only consumer was tying card-log entries to a
    reading. `saveSpread` no longer persists `rid`; an old stored spread simply
    carries a field nothing reads.
  - The bench used to report 24 of 27 templates because it could never populate
    a card log and so could never fire the three `haunt` lines. It now reports
    **24 of 24**, with fire rate and distribution unchanged (95.5%, commonest
    9.9%) — verified before and after, since `haunt` never won a bench spread.
- Bumping `LS_KEY` orphans the previous ~320 KB blob on every device inside a
  5 MB origin budget, so `boot()` sweeps any `arcanai-cardvecs-*` key that is
  not the current one. Bump the key freely; the sweep is what makes it cheap.
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
  tarot is strict about. The two end-of-reading paths pass `true` (the again
  button and the popstate off a spread). A spread-type switch passes **`SPENT`**,
  which is the whole subtlety, and it is a two-sided rule — both sides were
  reported as bugs:
  - Typed a question and changed your mind about One versus Cross *before*
    drawing? It survives. Losing what you typed for that is infuriating.
  - Already *drew* with it? It is wiped, exactly as finishing would. `.ask` is
    `display:none` for the whole reading, so a question that outlives its own
    spread is one you cannot see and will not remember typing, and it gets
    silently attached to the next reading — which reads as the deck having
    asked on your behalf.
  - `SPENT` is set in `draw()` from the question it actually used, so
    `silentQ` deals (Card of the Day, the jumper) do **not** spend a question
    the seeker typed and never asked.
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
  relaunch of the same process in one command. Bit me three times this way —
  `pgrep -af "http.server 864" | xargs kill` is the same mistake wearing a
  different hat.
- `cards/resonance_bench.html` (not shipped) drives the **real** draw page in
  an iframe rather than reimplementing selection — a harness with its own copy
  of `weightedOrder` stops measuring the deck the moment either drifts. The
  page's top-level bindings are `const`, so they are invisible as
  `frame.contentWindow.X` but *are* in scope for `contentWindow.eval`, which is
  how every probe reaches them. Serve the repo root, open
  `/cards/resonance_bench.html`, press Run. Fixed `SEED`, so two runs of the
  same build produce the same 200 spreads.
- `cards/reader_bench.html` (not shipped) is the **WP4 model bake-off**. One
  candidate at a time through a fixed set of card/seat/question cases chosen for
  contradiction *risk*, reporting download size, load time, tok/s, and every
  line so voice can be hand-judged. Cases are read live from the built page's
  `DECK` and from `seats.js`, so they cannot drift from what ships. Notes:
  - **Inference runs in a Worker.** Not a nicety: 135M on the wasm backend
    froze the tab so hard it stopped answering CDP. Same reason `speak.js` will
    need one.
  - The sanity gate (echo / arithmetic / counting) is **necessary but not
    sufficient** — SmolLM2-135M-Instruct q4 passed 3/3 and then failed the card
    task completely, echoing the prompt back and looping. Judge the lines, not
    the gate.
  - **The handoff's 300 MB download cap was lifted on 2026-08-03**, because it
    left only SmolLM2 standing and the small models are the ones that cannot
    hold the voice. Size is reported and weighed, never capped. D5 is untouched:
    it is a consent rule, not a size cap, so the download size must still be
    shown before the first byte. The real ceiling is now phone RAM and WebGPU's
    `maxStorageBufferBindingSize`, not policy.
  - **D1 compliance and voice trade off against each other**, measured on Gemini
    Nano across 12 cases picked for contradiction risk. The handoff's prompt let
    the model answer the *question* instead of re-voicing the *card* (3/12 D1
    failures, e.g. The Lovers reversed on "is he cheating on me" returned "you're
    drifting, not cheating" — the deck adjudicating an affair it never mentioned).
    Forbidding that fixed all three and flattened the voice: avg words 14.6 → 8.3,
    two near-verbatim copies, "Stop. Literally. A nap is the practical solution."
    became "Consider stillness. A pause unlocks potential." Both prompts ship in
    the bench; the question is which model needs the least leash.
  - The `count` check is deliberately tolerant of list formatting; an
    intolerant regex disqualified a model whose arithmetic was fine.
  - **TTFT is real now.** It was not: the hand-rolled streamer's first `put`
    fired during prompt processing. It is a `TextStreamer` with `skip_prompt`,
    verified against the 3.3.3 bundle — `put()` returns early on the prompt
    batch *before* calling `token_callback_function`, so the first callback is
    the first generated token. The same callback counts tokens exactly, which
    also retired the old `chars/4` estimate: that silently compared one
    tokenizer's characters-per-token against another's and called the ratio
    throughput. If a future build drops `token_callback_function` the bench
    falls back to the estimate and *says so* rather than reporting it as
    measured.
  - **The A/B result was confounded and there is now an A20 arm.** A and B
    differed in two things, not one: B forbids answering the question *and*
    caps at 20 words where A caps at 25. "Honesty costs voice" was therefore
    entangled with losing a fifth of the line. A20 is A verbatim at B's cap:
    A vs A20 isolates the cap, A20 vs B isolates the leash. Do not draw a
    criterion-5 conclusion from A vs B alone.
  - **Qwen3 candidates think unless told not to.** Qwen3-0.6B/1.7B are hybrid
    reasoning models that emit `<think>` blocks by default; the switch is
    `enable_thinking`, which lives in the *chat template*, not in the
    generation options, so there is nowhere to pass it when messages go
    straight into the pipeline. The bench templates by hand and passes it
    there — verified safe because 3.3.3's `apply_chat_template` collects
    unknown kwargs into a rest object and spreads them into the render context,
    so a template that ignores the variable is unaffected. Output is also
    stripped of `<think>` blocks and flagged `THINK-BLOCK` as belt and braces.
  - **`max_new_tokens` is 80, not 48.** A 25-word line is ~35-40 tokens, so 48
    truncated long lines mid-sentence and they read as terse — with no flag
    distinguishing a cut-off model from a clean one. Hitting the ceiling now
    flags `TRUNCATED`.
  - **The D1 pre-screen is a sort order, not a verdict.** MiniLM q8 (the page's
    own model) embeds each produced line and cosines it against the card meaning
    and against the question; `sim q > sim m` flags `ANSWERS-QUESTION?` and
    sorts that row to the top. It exists because hand-judging 12 cases × 9
    models × 3 prompts × 2 dtypes is how careful reading becomes skimming.
    Embeds **one text per forward pass** — the EMB1 rule applies here more than
    anywhere, since the whole comparison is between two cosines a few
    hundredths apart and batching would manufacture the signal.
  - **Seat text is an arm.** The handoff specifies `prose`, but per the seats
    rule above `prose` is matching text — written flat for a cosine, never
    displayed — while `lens` carries the register. Feeding a model text
    optimised to embed is a candidate cause of output that reads flat, so the
    bench can send either. Every seat used in `CASES` has both, checked.
  - Cases are built **before** the model loads, so a missing or unbuilt
    `release/major-arcanai/index.html` fails immediately instead of after
    downloading up to 1.3 GB onto a phone.
  - **The library version is an arm too** (`lib` selector: 3.7.6 / 4.2.0),
    because on mobile WebGPU it decides whether a usable configuration exists
    at all. 3.x is squeezed from both sides — q4f16 hits the fp16 overflow, and
    q4 needs ~2x the device memory and takes the tab with it on an 8 GB
    handset. v4 rewrote the WebGPU runtime in C++ and is the way out if it
    fixes q4f16, since that restores the fp16 footprint with correct numerics.
    Verified API-compatible with everything the bench uses, including `put()`'s
    skip-prompt ordering (TTFT stays honest) and `apply_chat_template`'s kwarg
    spread (`enable_thinking` still reaches Qwen3), and confirmed working:
    sanity 3/3 with byte accounting identical to 3.7.6 on the same model. The
    **D1 screener stays pinned to 3.7.6 regardless** — its cosines are compared
    across runs and must not move under the comparison.
  - **Corruption has TWO signatures and the gate must catch both.** Repetitive
    garbage (`!!!!!!!!`) is the easy one. The other is **token salad**: fluent-
    looking fragments from every script the tokenizer knows, spliced at random.
    Llama-3.2-3B q4f16 under WebLLM produced twelve rows of it **and the first
    version of this gate passed it as "numerics sound"**, which is precisely the
    failure the handoff built the gate to prevent. Never accept "it emitted
    English-looking characters" as evidence. Two discriminators, both cheap and
    both verified against 16 real strings from this bake-off with no false
    positives: English prose is a third to a half **function words** and salad
    has almost none (<8% disqualifies, only applied at >=8 words so short
    correct answers are untouched), and real output stays in **one script**
    while salad mixes Cyrillic, CJK, Thai, Arabic, Devanagari and Hangul in a
    single line (>=3 distinct non-Latin scripts disqualifies).
  - **The gate distinguishes GARBAGE from WRONG, and the difference decides
    whether a candidate lives.** Corrupted numerics emit one repeated token
    (Qwen2.5-0.5B q4f16/WebGPU answered all three checks `!!!!!!!!`). A model
    that answers "2" to 2+2 in fluent English has sound numerics and weak
    arithmetic — a different fact, and not disqualifying. Qwen3-0.6B does
    exactly that, **because this bench disables thinking** to keep `<think>`
    out of the word cap, and Qwen3's non-thinking mode is markedly weaker at
    reasoning. Failing it there would reject a candidate for a limitation the
    harness itself imposed. Only `numerics CORRUPT` blocks the card lines now;
    coherent-but-wrong warns and proceeds.
  - **Measured 2026-08-05, model/runtime compatibility is not uniform:**
    `onnx-community/Qwen2.5-0.5B-Instruct` **cannot be loaded by lib 4.2.0 at
    all** — ORT 1.24.3 fails at session creation in `graph_utils`
    `GetIndexFromName`, on *wasm* as well as WebGPU, while 3.7.6 loads it fine.
    `Qwen3-0.6B-ONNX` (a newer export) loads on 4.2.0 and passes with sound
    numerics. So lib version and model export are coupled, and the arm matrix
    is not free: check a new model loads before drawing conclusions about its
    voice.
  - **Probe configurations with Sanity only.** It answers "does this
    model/dtype/backend/library combination produce valid numerics at all"
    without paying for 12 generations, and that is the question a new
    configuration is actually asking.
  - **Dispose before terminating.** `worker.terminate()` alone does not
    reliably hand back ORT's GPU buffers, and a bench session on a phone is
    many load/kill cycles of several hundred MB each — which is how a page that
    ran fine for two models starts crashing the tab on the fourth. The worker
    takes a `free` command that awaits `pipeline.dispose()`, and the page races
    it against a 3 s timeout before killing the thread so a wedged worker
    cannot hang teardown.
  - **SCOPE CORRECTION (2026-08-05, same day): the binding-cap rule below is a
    fact about ONNX Runtime Web, NOT about the handset.** It was recorded as
    though the phone could not run these models. The phone can. WebLLM/MLC runs
    Llama-3.2 1B/3B in Chrome for Android 121+ under the *same* 128 MB cap,
    because MLC/TVM shards weights across many smaller buffers where ORT
    materialises the embedding/lm_head as a single binding (mlc-ai/web-llm#209
    is the identical 128 MB wall on a Pixel 7, since solved on their side; TVM
    carries explicit mobile fallbacks). See also gpuweb#4533 on `adapter.limits`
    under-reporting true GPU capability. So the rule predicts ORT's behaviour
    exactly and says nothing about what is possible — **the bench now has a
    WebLLM engine arm to tell the two apart**, and WP4 Tier 2 is not dead, it
    may simply have the wrong runtime.
  - **THE BINDING-CAP RULE, and it decides the bake-off.** On the S24 Ultra
    (adreno-7xx, `maxStorageBufferBindingSize` = 128 MB, the WebGPU spec floor)
    a model runs under WebGPU at q4f16 only if its embedding/lm_head tensor
    fits one binding at fp16 — i.e. **vocab x hidden < 67.1M elements**.
    Perfect discrimination on every model actually tried:
    | model | emb @ fp16 | observed |
    |---|---|---|
    | SmolLM2-135M (49152 x 576) | 54 MB | ran |
    | SmolLM2-360M (49152 x 960) | 90 MB | ran, full 3-arm bake-off |
    | Qwen2.5-0.5B (151936 x 896) | 260 MB | failed |
    | Qwen3-0.6B (151936 x 1024) | 297 MB | failed |
    It is **not** architecture (SmolLM2-360M uses GQA too and runs), not lib
    version (Qwen2.5 fails on both), not dtype (q4 fails on memory instead).
    It is **vocabulary**: Qwen's 151936 tokens is 3x SmolLM2's, so its
    embedding is huge at a fraction of the parameters. Every untried candidate
    is over: gemma-3-1b 576 MB, Llama-3.2-1B 501 MB, Qwen2.5-1.5B 445 MB,
    Qwen3-1.7B 594 MB, **and SmolLM2-1.7B 192 MB**.
    **CONFIRMED 2026-08-05 with a control.** SmolLM2-1.7B (192 MB, first over
    the line) loaded fine — 1059 MB, 54 s — and then generated *nothing*: three
    empty outputs, sanity 0/3, caught as corrupt by the garbage classifier. In
    the **same session immediately after**, SmolLM2-360M scored 3/3 with sound
    numerics, so the device was healthy and the failure was the model, not a
    lost GPU context. Five data points, perfect discrimination, and the cap
    falls between 90 MB (works) and 192 MB (fails) with family, vocabulary,
    architecture and library held constant across the boundary.
    **Consequence for WP4: the largest model that runs under WebGPU on this
    handset is SmolLM2-360M, and SmolLM2-360M is not good enough** (best arm
    5/12 mechanically clean, and it produced the grief line). Tier 2 has no
    viable WebGPU candidate on this device. Stop spending phone bandwidth on
    larger models; they are all further over the line.
    Older caveats, kept: the mechanism (ORT materialising that tensor at fp16 in
    the mechanism (ORT materialising that tensor at fp16 in one binding) is
    inferred rather than observed. **SmolLM2-1.7B is the decisive test** — same
    family, same vocab, same architecture, the only variable being 192 MB
    against the cap. If it fails, the ceiling is characterised and Tier 2 has
    no candidate on this handset that is also good enough. If it runs, the rule
    is wrong and there is a capable model that works.
  - **Measured ceiling on the test handset (S24 Ultra, adreno-7xx):
    `maxStorageBufferBindingSize` is 128 MB — the WebGPU spec's required
    minimum, i.e. no headroom above baseline**, while `maxBufferSize` is
    2048 MB. So the binding cap, not total RAM, is the constraint that bites,
    and fp32 compute inflates exactly the tensors that hit it: same weights,
    twice the unpacked width. This is why q4f16 loads on this device and q4
    takes the tab. It also prunes the candidate list — the cap scales against
    model width and refuses rather than slows, so the 1 GB+ candidates
    (Llama-3.2-1B, SmolLM2-1.7B, Qwen2.5-1.5B, Qwen3-1.7B) should be treated as
    unlikely on this adapter regardless of phone RAM. Do not spend gigabytes
    confirming that one at a time. The exact cutoff depends on how ORT splits
    tensors and has not been measured.
  - **q4 costs more memory than q4f16, not just more bytes.** It is fp32
    compute, so activations are fp32 too. On a phone the fp16-overflow
    workaround therefore buys correctness with headroom, and the two
    constraints pull against each other: the dtype that works is the dtype that
    fits least.
  - **q4f16 is not the default dtype to reach for on WebGPU.** It is 4-bit
    weights with fp16 *compute*, and ONNX Runtime Web overflows fp16 on the
    WebGPU backend for some architectures, emitting one repeated token —
    id 0, which prints as `!` in Qwen's tokenizer
    (microsoft/onnxruntime#26732, which also names gemma-3). Measured
    2026-08-05 on an adreno-7xx: `Qwen2.5-0.5B-Instruct` q4f16 scored
    **sanity 0/3, output nothing but `!`**, while the *same model, dtype and
    export* scored **3/3 on the wasm backend**. So it is the backend's
    numerics, not the model, not the conversion, and not the size. Use **q4**
    (4-bit weights, fp32 compute) on WebGPU for anything that fails the gate
    and accept the larger download — q4 ran ~1.5× the q4f16 bytes on
    SmolLM2-135M (176 MB vs 114 MB). This is the single best argument for the
    sanity gate existing: the failure is fluent-looking garbage that no amount
    of reading card lines would have diagnosed.
  - **tok/s is generation throughput, measured first-token-to-last.** It used
    to divide by the whole call, folding prompt processing into the rate, which
    penalises short outputs hardest — the fixed prompt cost amortised over
    fewer tokens. On the SmolLM2-360M run prompt B read 11.1 tok/s against
    prompt A's 20.7 purely because B's lines are shorter; corrected, the arms
    are close. It would have been read as a speed difference when comparing
    models. `genMs` is reported alongside `totalMs` now.
  - **Best configuration found: Qwen3-1.7B-q4f16_1-MLC under WebLLM, prompt B,
    seat `lens`, `/no_think`.** 7/12 mechanically clean, 12.2 avg words, **2/12
    D1 suspicions**, 406 ms TTFT, 56.6 tok/s, sanity 3/3. Beats every
    Llama-3.2-1B arm (best 6/12 clean, 5/12 suspicions) and writes the first
    lines with actual voice: "Enjoyment is allowed." for *You deserve
    enjoyment*; "The outcome is quiet, the roommates are back to being
    roommates." for The Lovers reversed on *is he cheating on me* — the case
    every other model answered by adjudicating him.
  - **THE CRASH IS FIXED, confirmed on the device that had it.**
    `CreateWebWorkerMLCEngine` completed all 12 cases on the S24 Ultra. Every
    previous WebLLM run there died on the first long generation with
    "Failed to execute 'mapAsync' on 'GPUBuffer'". The hand-rolled worker
    boundary WAS the bug — importing web-llm into your own worker and carrying
    your own postMessage protocol means owning the GPU buffer lifecycle across
    that boundary, and MLC's own worker path owns it correctly. **Do not
    hand-roll what the library already provides.**
  - **Greedy is deterministic on a device, NOT across devices — desktop numbers
    do not transfer.** Same code, same model (Qwen3-0.6B), same prompt B/lens,
    `temperature: 0`: on the RTX 500 Ada `/no_think` suppressed thinking
    completely (0 think blocks, 13.6 avg words, sanity 3/3); on the adreno-7xx
    it half-applied (6/12 rows with full reasoning, 33.3 avg words, sanity 1/3).
    `temperature: 0` takes the argmax, the two chips' floating point differs
    slightly, and where the model sits on a knife-edge between emitting
    `<think>` and not, they land on opposite sides — after which the whole
    generation diverges. **Every pneumatic number in this file is indicative,
    not predictive, of the handset.** The bench's own header always said desktop
    numbers do not transfer; this is what that means in practice.
  - **Thinking ON is rejected on the handset, decisively.** Qwen3-0.6B,
    1024-token budget, on the adreno: **79.8 avg words, 0/12 clean, 11-54
    SECONDS per case**. The failure is bimodal, which is worse than uniformly
    bad. When a block closed, the conclusions were reasonable — "Being in a
    situation where you feel sorry, but it's not an apology, it's an exit"
    (sim 0.83/0.12). When it did not, you get `"Position: The Obstacle"` (3
    words) or an **821-word loop**: "Wait, that's the same. But maybe the user
    wants it in the position's context. Wait, maybe I need to take the original
    meaning and assign it to the position…" ten times over, 54 seconds, then the
    cap. A 0.6B does not have the capacity to reason productively; the block is
    a liability, not an asset. Latency disqualifies it independently — a seeker
    taps a card and waits the better part of a minute.
  - **So the on-device answer is: suppress thinking, keep the stripper, accept
    that `/no_think` only half-works on this adapter.** Fighting it costs
    something; letting it run costs far more.
  - **Measured on the phone (the numbers that actually count for WP4):**
    Qwen3-0.6B q4f16, WebLLM worker engine, prompt B, seat lens — loads (320 MB
    download), runs all 12, **TTFT 1208 ms** (criterion 4 missed by 3x, against
    141 ms on the RTX), **22.7 tok/s** (vs 78.9), 3/12 clean, 33.3 avg words,
    **0/12 D1 suspicions**. The faithfulness holds up on-device; the speed and
    the thinking suppression do not.
  - **Few-shot does not help, and the way it fails twice is the lesson.**
    - **Attempt 1, examples in the system prompt as prose with a `-> ` marker:
      Qwen3-0.6B scored 10/12 clean — the highest of the bake-off — by copying
      the third exemplar verbatim onto NINE of twelve cards.** A copied exemplar
      is mechanically perfect, so every flag passed it. Qwen3-1.7B emitted the
      literal `-> ` on three lines. Hence the `EXEMPLAR-ECHO` flag: nothing else
      catches "right shape, wrong provenance".
    - **Attempt 2, examples as proper alternating user/assistant turns** (which
      is the correct way to few-shot a chat API — the message list *is* the
      structure): 0.6B **1/12**, 1.7B **5/12**, against 6/12 and 7/12 zero-shot.
      Worse, both times.
    - **Few-shot turns break `/no_think` on Qwen3.** With assistant turns in the
      history, 0.6B resumed emitting `<think>` on 11/12 rows and never closed
      the block inside the token budget. The two features do not compose.
    - 1.7B stopped echoing verbatim but absorbed the exemplars' *cadence* —
      "Not everything was meant to be saved" turned up on the grief card. Small
      models take the wording, not the method.
    - **So the best configuration stays zero-shot: prompt B, seat `lens`,
      `/no_think`.**
  - **Qwen3-0.6B is the phone-shaped candidate, and it trades voice for
    fidelity.** 1403 MB, **141 ms TTFT** (criterion 4 met outright), 78.9 tok/s,
    **1/12 D1 suspicions** — the most faithful arm measured — 6/12 clean, sanity
    3/3, no preamble. It is also the only model to handle the grief case
    correctly: "You could have left the queue an hour ago. Procrastinating and
    calling it waiting." But its sim-to-meaning runs 0.73-0.81 because it
    **copies rather than rewrites**, and it leaks the seat name into the line
    ("You're in the Obstacle.", "You're in the Vibe."), plus occasional
    grammatical failure ("stuck in something meaningful"). So the choice is
    real: **0.6B is faithful and voiceless at 1403 MB and 141 ms; 1.7B has the
    voice and invents, at 2037 MB and 406 ms.**
  - **gemma3-1b: the system-role hypothesis was WRONG.** Gemma has no system
    turn, so the harness merges system into the user message for that family —
    a correct fix on its own terms — and it changed nothing: 11/12 lines still
    open "Okay, here's a rewrite of that line in the context of…", 49 avg
    words, 9/12 suspicions. The model genuinely narrates the task rather than
    performing it. The merge is kept because it is right regardless; the verdict
    on gemma3-1b for THIS task stands on its own.
  - **Newer is not the axis; size and instruction-tuning style are.**
    `gemma3-1b-it` is newer than Llama-3.2-1B and far worse: ten of twelve lines
    open "Okay, here's a rewrite of the meaning for…", explaining the task
    instead of doing it, 52 avg words, 8/12 suspicions. Qwen3-1.7B won by being
    bigger and better tuned, not by being new.
  - **Thinking ON is worse for this task, measured.** Qwen3 with reasoning
    enabled and a 512-token budget: 269.8 avg words, 0/12 clean, and **D1
    unchanged at 2/12**. The reasoning does not finish inside 512 tokens on
    these prompts, so most rows never close `</think>` and the block survives as
    output. More budget buys latency, not faithfulness. Qwen3's advantage here
    is base competence, not reasoning.
  - **Qwen3's thinking switch: `enable_thinking: false` is accepted by WebLLM
    and ignored by the model.** `/no_think` appended to the user message does
    work — and its documented behaviour is to emit an **empty** `<think></think>`
    then answer. A THINK-BLOCK flag that fires on the tag rather than on its
    contents therefore marks every row and zeroes the clean count on the best
    model in the bake-off, which is exactly what happened here. The evidence was
    in the numbers all along: avg words fell 63.1 → 12.2 when `/no_think` was
    added. Flag content, never tags.
  - **`logit_bias` is the one prompt-adjacent intervention that worked.**
    Banning six first-person tokens took first-person lines from ~4 to 1 with
    clean rate, word count, D1 suspicion and throughput all unmoved. Token-level
    bans fix token-level problems; nothing about them helps with "don't invent
    facts", which is not expressible as a token set.
  - **Two newer models failed on configuration, not capability, and both would
    have been recorded as model failures.** `gemma3-1b` throws
    `WindowSizeConfigurationError` (WebLLM's default chat config vs the model's
    own record), and fixing that with `context_window_size: -1` then throws
    `AttentionSinkSizeError` — it needs `attention_sink_size` too. Always read
    the error before concluding a model does not work.
  - **"The grief will never ease off" is a robust attractor, not a model
    defect.** SmolLM2-360M produced it and so did Qwen3-1.7B — different family,
    5x the parameters, best-scoring configuration, still that line for *will the
    grief ever ease off*. No model tested has avoided it. Treat it as a property
    of the question-plus-card combination.
  - **Structured output (`response_format` + json_object schema) is the wrong
    tool for voice-sensitive prose, measured.** Llama-3.2-1B, prompt B, seat
    lens, against the identical free-text arm:
    | | free | schema@160ch | schema@120ch |
    |---|---|---|---|
    | clean | **6/12** | 5/12 | 5/12 |
    | avg words | **9.3** | 14.0 | 12.6 |
    | tok/s | 90.2 | 92 | 90.8 |
    - **It does do its job on shape**: wrapping quotes, stray quotes, markdown
      and multiline all went to zero. Those are shapes a schema makes
      impossible rather than merely discourages.
    - **And it is free** — 92 vs 90 tok/s. Constrained sampling costs nothing
      measurable here, contrary to the usual warnings.
    - **But a schema licenses as much as it forbids.** `maxLength` is in
      CHARACTERS. At 8 chars/word a 20-word cap became 160 characters and the
      model filled it (OVER20 1→4). At 6 chars/word it still produced 25-26
      word lines, because this model's words average ~4.8 characters. Word caps
      do not map cleanly onto character bounds; either bound characters
      honestly or leave length to the prompt.
    - **The register shifts, and this is the finding worth keeping.** Asked for
      `{"line": "..."}` instead of a bare line, the model stopped writing
      oracle lines and started writing *titles* ("The Shadow", "The Weight of
      Waiting"), *first-person dialogue* ("I'm not sure I'm ready to forgive
      you yet"), and duplicate text across different seats. Completing a JSON
      string value is not the same task, to the model, as writing a line — the
      field name and schema shape prime what belongs there. Use structured
      output for machine-consumed data; do not use it for text whose voice
      matters, at least not without testing the field naming.
  - **The decisive run, 2026-08-05: Llama-3.2-1B q4f16 under WebLLM/MLC on an
    RTX 500 Ada, four arms, `resetChat` on, D1 screen on.**
    | arm | clean | avg words | D1 susp | TTFT | tok/s |
    |---|---|---|---|---|---|
    | B-prose | 5/12 | 11.4 | 5/12 | 279 ms | 78 |
    | **B-lens** | **6/12** | **9.3** | 5/12 | 285 ms | 88.6 |
    | A20-prose | 4/12 | 10.7 | 7/12 | 184 ms | 89.6 |
    | A-prose | 4/12 | 14.1 | 6/12 | 188 ms | 89.2 |
    - **`lens` beats `prose`** — more clean, two words shorter, and it killed
      the worst invention of the whole bake-off: on "how do I say no to my
      sister without a row" the prose arm produced *"You're stuck in a
      relationship that's toxic to you"*, and the lens arm produced bland
      filler instead. The long descriptive seat text was feeding elaboration.
      It bought blandness, not fidelity.
    - **The leash cuts D1 suspicion** (A20 7/12 → B 5/12); **the cap only
      shortens** (A 14.1 → A20 10.7 words, clean unchanged at 4/12). Same
      decomposition the SmolLM2 arms showed, now on a model that can do the task.
    - **Criterion 4 is met on desktop-class hardware and missed on the phone**:
      184-285 ms TTFT on the RTX against 1107 ms for the same model on the
      adreno. Whether that counts depends on which device the criterion is about.
    - **Criterion 1 still fails in roughly half the cases, and fluently.** Under
      the *best* arm it answers "am I the problem" with "I'm not the problem"
      (sim 0.21/0.55), tells a seeker moving city that "you'll find your new
      home, but it's a disaster waiting to happen" (0.13/0.46), and twice
      asserts what "he" is feeling. All under the prompt that forbids answering
      the question and forbids predicting.
    - **A contaminated run scored 9/12 clean and the honest number is 5/12.**
      Without `resetChat` the cases riff on each other's phrasing and come out
      mechanically tidier. Never quote a clean rate from a run without it.
    - The D1 screen caught the two worst by wide margins and **missed The Lovers
      reversed at 0.36/0.33** — a real failure inside the noise. It is a sort
      order, not a gate, and this is what that means in practice.
  - **First real phone run, 2026-08-05: SmolLM2-360M-Instruct q4f16 / WebGPU /
    seat prose, on an S24 Ultra (adreno-7xx, shader-f16 yes).** Rejected, and
    the arms decided something:
    - A (cap 25) 43.3 avg words, 1/12 clean · A20 (cap 20) 35.1, 2/12 ·
      B (cap 20) 28.6, 5/12. So of the 14.7-word fall from A to B, **~56% is
      the word cap and ~44% is the leash — but the leash does nearly all of
      the *cleaning*** (clean 1→2 on the cap, 2→5 on the leash). They are not
      the same knob, and the A-vs-B tradeoff is milder than it looked.
    - The model completes the prompt instead of answering it under A/A20
      (`Card:`, `Position:`, `They asked:` echoed verbatim) and degenerates
      into repetition under B. A capability failure, not a prompt failure.
    - **It echoes `seats.js` prose verbatim** — "The obstacle, the thing that
      stands in the way" is the matching text, sitting in the prompt inviting
      exactly this. Strong argument for the `lens` arm.
    - **Under prompt B it answered "will the grief ever ease off" with "The
      grief will never ease off."** (meaning: "You could have left the queue an
      hour ago. Stalling isn't waiting."; sim **0.06/0.73**, the widest q>m gap
      in the run, correctly sorted to the top by the D1 screen). The
      anti-invention prompt did not prevent it. Treat this as a gate: no model
      ships that produces this line. It also bears on F5 — "no crisis
      interception" was decided when every word was authored at build time.
    - **Every arm fails criterion 4** (TTFT 905 / 965 / 1420 ms against ~400).
      The best of them came from the model that cannot do the task, and larger
      candidates will be slower. Criterion 4 may need amending rather than
      meeting; that is a Commander call.
    - Chrome Prompt API is **absent on Android**, confirming Tier 1 is desktop
      only and Tier 2 is the tier that reaches phones.
  - **Download progress is throttled, and must stay throttled.** Measured: a
    260 MB model fires **6014** `progress_callback` events (~190/s), one per
    ~43 KB chunk, and a 1.3 GB candidate fires roughly five times that.
    Forwarding each one from the worker is a `postMessage` plus a main-thread
    DOM write; once the main thread cannot drain the queue as fast as the
    worker fills it the backlog compounds, and the download appears to slow and
    then freeze partway. The worker posts at most one update per 100 ms (status
    changes always post, so `done`/`ready` are never swallowed) and the page
    coalesces to one DOM write per frame with `requestAnimationFrame`. A 467 MB
    uncached load went from thousands of writes to **3**. Byte accounting still
    sees every event — only the reporting is throttled. The point is that the
    message rate is now bounded by *time*, not by chunk count, so a fast
    connection cannot outrun the display.
  - **The bench is pinned to transformers.js 3.7.6, deliberately ahead of
    `attune.js`'s 3.3.3.** 3.3.3 bundles onnxruntime-web 1.20.1; Chrome now
    ships a native `Float16Array`, ORT maps the float16 dtype onto it, and
    1.20.1 rejects the `Uint16Array` transformers.js actually passes —
    `a float16 tensor's data must be type of function Float16Array()` — killing
    **every q4f16 and fp16 run at load**. ORT 1.21.0 accepts it again
    (microsoft/onnxruntime#23827); 3.5.0 is the first release carrying that and
    3.7.6 is the last of the 3.x line. Three things worth knowing:
    - **It is WebGPU-only.** q4f16 loads fine on the wasm backend even on
      3.3.3, so this cannot be reproduced on a machine with no GPU adapter and
      it did not show up in a full q4 bake-off run. Do not conclude from a
      clean wasm run that a float16 path works.
    - **q4 is unaffected** either way — it has no float16 tensors.
    - **`attune.js` was NOT bumped with it**, and should not be casually.
      MiniLM at q8 has no float16 tensors, so the shipped page cannot hit this,
      and every measured number here (reversal rate, lean stops, resonance
      background, dilution ranks) was taken on 3.3.3. Bumping the page is a
      re-measuring job, not an edit. `speak.js` forces the decision if it wants
      q4f16: either the page carries two library versions or the deck gets
      re-measured on a newer one.
- **Build hygiene**: after any change, run `build_draw_page.py` twice and
  confirm `git diff` on `release/` shows only what you meant and nothing on the
  second run. Catches the failure mode of having edited the generated
  `release/major-arcanai/index.html` instead of the Python string it comes from.
- **Missing-sibling check**: each of `seats.js`, `attune.js`, `voice.js` must be
  removable without breaking the page. Serve a copy of `release/major-arcanai/`
  with one of them deleted (symlink the image dirs, copy the rest) and confirm
  a draw still completes — with `seats.js` gone the page falls back to bare
  position labels and `attune.js` logs "seating disabled".
