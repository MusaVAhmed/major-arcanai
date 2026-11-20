#!/usr/bin/env python3
"""Corpus generator for weave — the phase-A oracle.

Builds conditioned deals and their readings from the two shipped sources of
truth: release/major-arcanai/deck.json (cards, read in page order) and
cards/seats.js (spread seats, dumped through node so nothing here is a
second copy). Questions come from questions.txt, the bake-off's bank.

The oracle RE-CITES rather than re-voices: each dealt card contributes one
of its own shipped strings (meaning/sit upright, r/sitr reversed). That is
deliberate — it proves the conditioning grammar, the trainer, the export
and the JS runtime end to end without waiting on the re-voicing pass, and
it doubles as the memorisation floor: 92 facts is two orders of magnitude
under TINY 2.1's 3,500, so a model that cannot recite this cannot do the
task at any size. Phase B (LLM re-voicings, several per face, none equal
to the source text) is what teaches rewriting; the NEAR-COPY and
COPY-EXPANSION flags from reader_bench are phase B's gate, not this
file's.

Domain is sampled but the oracle text does not vary with it; the domain
token earns its place in phase B. The question STRING never appears —
conditioning is the domain token only, which is what makes "copying the
prompt" structurally unavailable rather than discouraged.

Usage:  python3 corpus.py --out weave.jsonl [--n 8000] [--seed 20261115]
"""
import argparse
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def load_deck():
    with open(os.path.join(ROOT, "release", "major-arcanai", "deck.json")) as f:
        deck = json.load(f)
    return deck["cards"]


def load_seats():
    """Dump seats.js through node — the file itself is the parser."""
    js = (
        "global.window={};require(%r);"
        "console.log(JSON.stringify(window.ARCANAI_SEATS.seats))"
        % os.path.join(ROOT, "cards", "seats.js")
    )
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def load_questions():
    qs = []
    with open(os.path.join(HERE, "questions.txt")) as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                dom, q = line.split("\t", 1)
                qs.append((dom, q))
    return qs


def pool_for(card, face):
    # deck.json field names; the page renames these to r/sit/sitr.
    if face == "up":
        return [card["meaning"], card.get("situations")]
    return [card["reversed"], card.get("situations_reversed")]


def make_hand(rng, deck, seats, n_cards):
    mode = str(n_cards) if str(n_cards) in seats else "5"
    # The page's own mapping: 1, 3, 5 map straight; the Cross is mode 10.
    idxs = rng.sample(range(len(deck)), n_cards)
    seats_list = seats[mode]
    order = list(range(n_cards))
    if n_cards > 1:
        rng.shuffle(order)  # which card lands in which seat is the deck's
    hand = []
    for k, i in enumerate(idxs):
        card = deck[i]
        seat = seats_list[order[k]]["name"] if n_cards > 1 else "<noseat>"
        face = "rev" if rng.random() < 0.5 else "up"
        hand.append((card, seat, face))
    return hand


def oracle_text(rng, hand):
    parts = []
    for card, _seat, face in hand:
        pool = [p for p in pool_for(card, face) if p]
        # 70% the shipped meaning, 30% the situational expansion: both are
        # the card's own text; the variety keeps exact recall of one string
        # from being the only solution.
        pick = pool[1] if len(pool) > 1 and rng.random() < 0.3 else pool[0]
        parts.append(pick)
    return " ".join(parts).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "weave.jsonl"))
    ap.add_argument("--n", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=20261115)
    ap.add_argument("--voicings", default=None,
                    help="gate-approved voicings.json: build the phase-B mix "
                         "instead of the pure recitation oracle")
    ap.add_argument("--recites", type=int, default=1500,
                    help="phase-B mode: how many phase-A recites to keep in "
                         "the mix — the recitation floor stays load-bearing "
                         "but must not drown the voice")
    a = ap.parse_args()

    deck = load_deck()
    seats = load_seats()
    questions = load_questions()
    rng = random.Random(a.seed)
    assert questions

    def sample_dom(r):
        return "none" if r.random() < 0.3 else r.choice(
            ["work", "love", "kin", "loss", "change", "self"])

    written = skip = 0
    with open(a.out, "w") as f:
        if a.voicings:
            voicings = json.load(open(a.voicings))
            V = {(int(i), face): lines
                 for i, d in voicings.items() for face, lines in d.items()}

            def emit(hand, dom, text, recite=False):
                nonlocal written, skip
                if len(text.encode("utf-8")) > 480:
                    skip += 1
                    return
                rec = {"dom": dom,
                       "cards": [[c["name"], s, fv] for c, s, fv in hand],
                       "text": text}
                if recite:
                    rec["recite"] = True
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1

            # 1. voice lines: one face, its approved re-voicings, dom sampled
            for (i, face), lines in sorted(V.items()):
                for t in lines:
                    emit([(deck[i], "<noseat>", face)], sample_dom(rng), t)

            # 2. deal lines: real hands, text = the dealt faces' re-voicings
            #    concatenated IN SEAT ORDER — phase A concatenated in draw
            #    order and got away with it because facts are order-free;
            #    phase B teaches the order the page displays.
            for _ in range(a.n):
                r = rng.random()
                n_cards = 1 if r < 0.12 else 3 if r < 0.5 else 5 if r < 0.9 else 10
                hand = make_hand(rng, deck, seats, n_cards)
                mode = str(n_cards) if str(n_cards) in seats else "5"
                # seats are already assigned inside hand (make_hand shuffled
                # them); re-shuffling here invents a second, disagreeing
                # permutation — read them, do not re-derive them
                by_seat = {c[1]: c for c in hand}
                parts = [rng.choice(V[(card["index"], face)])
                         for sname in [s["name"] for s in seats[mode]]
                         if sname in by_seat
                         for card, _s, face in [by_seat[sname]]]
                if not parts:  # 1-card hands seat as <noseat>
                    card, _s, face = hand[0]
                    parts = [rng.choice(V[(card["index"], face)])]
                emit(hand, sample_dom(rng), " ".join(parts).strip())

            # 3. the recitation floor, kept, down-weighted
            oracle_rng = random.Random(a.seed + 1)
            made = 0
            while made < a.recites:
                r = oracle_rng.random()
                n_cards = 1 if r < 0.2 else 3 if r < 0.5 else 5 if r < 0.9 else 10
                hand = make_hand(oracle_rng, deck, seats, n_cards)
                text = oracle_text(oracle_rng, hand)
                if len(text.encode("utf-8")) > 480:
                    continue
                emit(hand, sample_dom(oracle_rng), text, recite=True)
                made += 1
        else:
            for _ in range(a.n):
                r = rng.random()
                n_cards = 1 if r < 0.2 else 3 if r < 0.5 else 5 if r < 0.9 else 10
                hand = make_hand(rng, deck, seats, n_cards)
                text = oracle_text(rng, hand)
                if len(text.encode("utf-8")) > 480:
                    continue  # would not fit the ctx with its header
                emit(hand, sample_dom(rng), text)
    extra = f", {skip} too long skipped" if skip else ""
    print(f"wrote {written} hands -> {a.out}{extra}", file=sys.stderr)


if __name__ == "__main__":
    main()
