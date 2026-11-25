# weave — a small voice trained on the deck

WP4 asked whether an **off-the-shelf** small model could re-voice a dealt
card in the deck's voice, on-device. It found, extensively and with
receipts: the models that fit the handset's binding caps cannot rewrite
(SmolLM2-360M), the model that is faithful cannot write (Qwen3-0.6B,
"copying is the size ceiling and it has one shape"), and every lever
tried — penalties, sampling, schemas, four subtractions from the prompt
— redirected the copying instead of removing it. **Subtraction redirects
the copying; it does not create the capability to rewrite.**

weave is the subtraction taken to its limit. The bake-off prompt handed
the model the card's meaning, its expansion, the question and the seat's
prose, and the model parroted whichever it liked. weave's input contains
**no prose at all**:

```
⟨love⟩ ⟨Past⟩⟨up⟩⟦Waiting Room⟧ ⟨Present⟩⟨rev⟩⟦Bottle⟧ ⟨Future⟩⟨up⟩⟦Star⟧ ⟩
You could have left the queue an hour ago. Something is surfacing. Hope returns slowly.
```

Cards, seats and faces are single entity tokens; the question arrives as
one domain token chosen by the MiniLM attunement that already runs. You
cannot copy a 20-token prompt. What is left to learn is the whole job:
**92 facts (46 cards × 2 faces) and the voice**, which is a TINY 2.1
task, not a Qwen task — TINY 2.1 ships 367K parameters that recite 3,500
facts, and its documented failure ("outside those it makes things up
confidently") cannot fire here because there is no outside: the model is
trained, not told, and the logit mask refuses to propose anything but
printable bytes.

## What WP4 buys this design (the receipts it settles cheaply)

| WP4 finding | consequence for weave |
|---|---|
| `vocab × hidden < 128 MB` binding caps kill Qwen on the handset | weave: 330 × 256 × 4 B = **0.34 MB** embedding. The cap stops existing. |
| 320 MB–2 GB downloads; D5 consent gate; progress throttling | weave: **2–6 MB**. The download rule stops applying. |
| TTFT 1.2 s on the adreno at 0.6B; criterion 4 was ~400 ms | weave: ~15-token prefill in pure JS, first byte in tens of ms; no GPU, no runtime, no worker |
| `NEAR-COPY` was models repeating prompt text | weave's prompt has no words to repeat — the flag becomes a **phase-B corpus check**, not a runtime risk |
| D1 screen (MiniLM cosines) sorts failures honestly | keep it verbatim: it is the page's own model and it already ships |
| seat-leak and scaffold-echo flags are capitalisation-sensitive | keep them; weave can leak a seat into prose the same way |
| "the grief will never ease off" is an attractor line | kept as a gate: the phrase appears nowhere in the weave corpus |
| rankings transfer desktop→phone; absolute numbers do not | same rule: judge on the S24, iterate on anything |
| ORT/WebLLM runtime roulette (q4f16 overflow, lib pinning, mapAsync) | weave runs on **no** runtime: one classic script, the TINY 2.1 architecture choice in JS |
| placement closed at chance: the deck's aphorisms carry no seat signal | weave is not asked to seat; it is asked to speak **after** attune.js seats |
| SmolLM2-135M "passed 3/3 sanity then failed the card task" | sanity gates are for runtimes and quantisation; weave's equivalent is the gradcheck and the Python↔JS parity test, both boring by design |

## What is deliberately NOT here yet

- **Card names in output.** v1 lines never name a card (the caption
  already names it); adding names = card tokens join the output mask.
- **Question text.** Conditioning is the domain token only. If the
  corpus says that's too coarse, a question-similarity token against the
  six anchors' *phrasings* (not the question) is the next knob.
- **A KV cache that matters.** The JS runtime caches K/V across tokens
  and costs ~2.4 MFLOP per emitted byte; fine without WASM at whisper
  size.
- **BPE.** v1 is byte-level (TINY 2.1 precedent; one decode line, zero
  vocab file, zero Python↔JS parity surface). Upgrade if and only if
  the re-voicing quality needs it, not before.

## Model

Byte-level + entity vocab (46 card ids, 17 seats, 2 faces, 7 domains,
`deal_end`, `eos`; **ids 256..329**; card tokens are DECK order by
contract). Post-LN GPT, learned positions, tied embeddings, GELU(tanh)
— one definition, `model.py`, mirrored exactly once in `weave.js`.

| tier | d | L | params | int8 export | role |
|---|---|---|---|---|---|
| whisper | 160 | 4 | ~1.4 M | ~1.4 MB | pipeline proof + recitation floor |
| voice | 256 | 6 | ~5 M | ~5 MB | shipping candidate |

Trainer: `train.py`, NumPy Adam, cosine, masked loss on text+`eos` only.
Gradient-checked backward (`python3 model.py`, float64, 1e-4 tolerance).
Zero heavy dependencies — the pipeline ethos of `cards/*.py`, and the
reason it trains anywhere.

## Data: two phases, and only one of them teaches voice

- **Phase A (this repo, today): the oracle re-cites.** Each dealt card
  contributes one of its own shipped strings (`meaning`/`situations`,
  `reversed`/`situations_reversed`). It proves the grammar, the trainer,
  the export, the runtime and parity end to end, and it measures the
  **memorisation floor**: can 1.4 M parameters carry 92 facts? If not,
  nothing else here matters. The oracle's readings are in the deck's
  voice *by construction* — they are the deck's copy — so what they do
  **not** teach is rewriting.
- **Phase B: re-voicing.** ~10 fresh readings per card face from a big
  model few-shot on the deck's own copy, plus multi-card weavings of the
  real deal distribution, hand-vetted. This is where voice lives, and
  the bake-off's flags are the acceptance test at the door: no line may
  be `NEAR-COPY` or `COPY-EXPANSION` (word-bag 0.70) of its source, no
  line ships that answers the question rather than voicing the card, the
  grief sentence is banned, ≤20 words, `sitr` is the style sample.

## Acceptance (inheriting WP4's instruments, not inventing new ones)

1. **Parity**: `node parity.js` — greedy Python vs greedy JS: identical
   strings, or a first divergence only where the saved python top-2
   margin was < 0.05 logits (the bake-off's own float caveat, now a
   measurable one — the smoke run diverged at a margin of 0.018 and
   nowhere else).
2. **Recitation matrix** (oracle model): shown card face, greedy line
   cosines (MiniLM D1 screen, the page's own) above its own meaning's
   background + N sd. A card the model cannot recall is a card the tier
   is too small to hold — measured per card, not as a loss number.
3. **Rewrite matrix** (phase-B model): the same 12 bake-off cases
   through the same flags: D1 suspicion, `NEAR-COPY`/`COPY-EXPANSION`,
   `SEAT-NAME-IN-LINE`, `OVER20`. A clean rate per 12 is comparable to
   the bake-off's tables directly: Qwen3-0.6B's phone best is **3/12**;
   0.6B on RTX **7/12**; the whole bake-off never beat 7/12 honestly.
4. **Grief gate**: "will the grief ever ease off" × Waiting Room rev —
   no model ships that says the grief never eases.
5. **The one thing WP4 never had to check**: does it sound like the
   deck? That is an A/B against the template verdicts and the owner's
   ear. Everything above is a floor, not a ceiling.

## Risks, honestly

- **At 1.4 M, 92 facts may smear** (two cards' meanings trading words).
  Measured by (2) per card, and fixable by size, not by prompting.
- **A phase-B corpus that leans on its sources reproduces the bake-off
  at 5 MB instead of 600 MB.** The word-bag check at corpus-build time
  is the guard — bake-off lesson: the source text is what gets copied,
  so keep it out of the output.
- **Voice is corpus-bounded, world-model-free.** weave will not invent
  an affair, but it also will not notice the seeker's own metaphor; the
  domain token is the whole of its attention. Fine at this altitude.

## Layout

| file | role |
|---|---|
| `tok.py` | vocab contract (ids are the wire format; exported to meta.json) |
| `corpus.py` | phase-A oracle over deck.json + seats.js + questions.txt |
| `model.py` | the model + gradient check (run it: `python3 model.py`) |
| `train.py` | Adam, cosine, sample-eval, int8-row export, parity case |
| `weave.js` | the runtime: boot/reading/readingAsync, null on any failure |
| `parity.js` | node harness: JS greedy vs python greedy |
| `recite.py` | the recitation matrix over the export (word-bag instrument) |
| `weave_demo.html` | four fixed spreads, one script tag, no build step |

## Result, phase A (whisper tier, 8,000 steps, 1.35M params, 1.38 MB)

- **Parity: PASS** — python and JS greedy agree to the whole string, no
  tie divergence at all (the underfit model had diverged at a 0.018
  margin; a converged model's margins are fat, as it should be).
- **Recitation: 91/92.** The memorisation floor exists and 1.4 million
  parameters clear it with room. The single miss — The Slice rev
  bleeding "Stop asking for signs" from High Priestess rev mid-line —
  is exactly the per-card smear the SPEC risk list predicted, and the
  word-bag instrument names the culprit.
- **Speed**: 20 ms boot; a full 5-card Cross read in 479 ms on
  single-threaded node, no GPU, no runtime — and that is the **whole
  line**, which the bake-off never achieved at any latency (their 400 ms
  criterion was first-byte; a phone's were 1.2–3.5 s and still typing).
  Per emitted byte the voice costs ~4 ms.
- The oracle model also **mixes pools between a card's own faces**
  (Hermit rev emitting Hermit up's first line) — a phase-B corpus
  note, not a capacity finding: the fact is in there, it said the
  wrong one of its own two.


Shipped integration, when it happens, is the CLAUDE.md three-edit rule:
`weave.js` + exported weights beside `attune.js`, one `<script>` tag,
and `#verdict` prefers `ARCANAI_WEAVE.reading(deal)` over the template
line when it is non-null — the same null-fallback contract every
sibling script already lives by.

## Result, phase B (voice mix, both tiers, Nov 22)

Both tiers trained on the 4,488-row voice mix: 736 gate-approved
voicings + 2,252 seat-ordered deal lines + 1,500 down-weighted recites
(~1:3 voice:recite — the floor kept, not allowed to drown the voice).
Parity PASS on both tiers, and the JS stop rule (stop at sentence
boundary once 2×cards sentences are out — the measured sentences-per-
voicing in the corpus) keeps greedy from overrunning the memorised edge.

**Rewrite matrix over all 92 faces** (`eval_b.py`, bake-off instruments):

| tier | flagged faces | COPY | OFF-drift | exact known strings |
|---|---|---|---|---|
| whisper-b (1.35M) | 40 | 8 | 6 | 17 |
| voice-b (4.94M, 5.00 MB) | 30 | 29 | **1** | **81** |

How to read voice-b's 29 COPYs: they are not source recitations — every
flagged output is a known approved string; the 0.70 word-bag instrument
cannot tell recite from authored paraphrase, only distance to the
source. The honest summary of greedy voice-b: **it picks among the eight
voicings per face and delivers them flawlessly** — 81/92 exact known
strings, one off-card drift in 92, zero malformed prose, zero invented
facts. That is the rewrite tier doing exactly what phase B asked: the
paraphrase lives in the corpus (mine, gated); the model's contribution
is selection, seat-ordered delivery, and 2.7 s/line on a single thread
beside a 23 MB embedder that takes longer to boot.

The unfinished case is **multi-card weaving**: fresh 5-card hands
sometimes enter a neighbouring memorised trajectory (a Receipts line
wandering into a Tower hand, recovered by the next seat). The answer is
phase C — hand-written weavings of real triples — not more parameters.

## Phase C: parked, with the instruments standing

The voice-c run (weaving mix) was killed at step 2,000/8,000 — by the
owner, for host comfort, which outranks any experiment here. Nothing
was lost that the repo cannot rebuild: the weaving corpus is gated and
committed, the before-baseline is recorded (trajectory 21/108, seat
order 1/7, held-out 5/44), and `train.py` now checkpoints every 500
steps with `--resume`, so the rerun is

  OPENBLAS_NUM_THREADS=4 nice -n 10 python3 train.py --tier voice \
    --corpus weave-c.jsonl --steps 4000 --bs 40 --ctx 448 --out out-voice-c

at roughly half the host impact and half the wall clock. Phase C may
also simply wait for a machine that is not a daily driver; the gate,
the eval, and the baseline make the rerun one command and no
decisions.
