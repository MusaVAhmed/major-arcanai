#!/usr/bin/env python3
"""eval_c.py — phase C acceptance: does a sentence stay on its card?

Phase B shipped a voice that recites the approved lines on the right
cards. Phase C is judged on the failure the demo hands found: fresh
multi-card hands whose greedy run wanders into a neighbouring
memorisation. The instrument is the same content-word attribution the
weaving gate uses, pointed at the model instead of at me.

  python3 eval_c.py out-voice-c            # trajectory on fresh hands
  python3 eval_c.py out-voice-b out-voice-c  # side by side

Checks, in order of hardness:
  1. TRAJECTORY: share of emitted sentences that attribute (>=2 clear
     content-word matches) to a card actually dealt in that hand.
  2. HELD-OUT WEAVINGS: the 12 weavings kept out of training; the
     metric is not string equality with the gold line — it is whether
     the model produces ANY in-hand connected reading, measured by 1
     plus a novelty share (exact known training strings emitted).
  3. SEAT ORDER: among hands with >=2 attributed sentences, do they
     arrive in canonical seat order?
"""
import argparse
import json
import os
import random
import re

import numpy as np

import corpus as C
from gate_c import bag, STOPW, sents
from tok import Tok
from train import load_export, sample

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = re.compile(r"[a-z']+")


def attr(sentence, sent_pool, min_overlap=2):
    """Nearest face to a sentence, content words only; None when unclear."""
    sc = bag(sentence) - STOPW
    best, bestn, second = None, 0, 0
    for k, pc in sent_pool.items():
        n = len(sc & (pc - STOPW))
        if n > bestn:
            best, second = k, bestn
            bestn = n
        else:
            second = max(second, n)
    return best if bestn >= min_overlap and bestn > second else None


def fresh_hands(seed, n=24):
    rng = random.Random(seed)
    deck = C.load_deck()
    seats = C.load_seats()
    out = []
    for _ in range(n):
        n_cards = 3 if rng.random() < 0.5 else 5
        hand = C.make_hand(rng, deck, seats, n_cards)
        mode = str(n_cards)
        by_seat = {c[1]: c for c in hand}
        canon = [(card["index"], face) for sname in [s["name"] for s in seats[mode]]
                 if sname in by_seat
                 for card, _s, face in [by_seat[sname]]]
        dom = rng.choice(["work", "love", "kin", "loss", "change", "self", "none"])
        out.append((dom, canon))
    return out


def run(a):
    deck = C.load_deck()
    tok = Tok([c["name"] for c in deck])
    rng = np.random.default_rng(0)
    sent_pool = {(i, f): bag(" ".join(C.pool_for(c, f)))
                 for i, c in enumerate(deck) for f in ("up", "rev")}
    known = set()
    for fn in ("voicings.json",):
        d = json.load(open(os.path.join(HERE, fn)))
        for face_map in d.values():
            for lines in face_map.values():
                known.update(lines)
    ev = []
    with open(os.path.join(HERE, "weavings_eval.tsv")) as f:
        for line in f:
            if not line.strip():
                continue
            dom, spec, text = line.rstrip("\n").split("\t", 2)
            hand = [(int(t.split(":")[0]),
                     "up" if t.split(":")[1].startswith("u") else "rev")
                    for t in spec.split("|")]
            ev.append((dom, hand, text))

    for out_dir in a.out_dirs:
        model = load_export(out_dir, tok, np.random.default_rng(0))
        hands = fresh_hands(7)
        n_sent = n_attr = n_parrot = 0
        order_ok = order_n = 0
        per_line = []
        for dom, canon in hands:
            hdr = tok.header(dom, [(deck[i]["name"],
                                    C.load_seats()[str(len(canon))][k]["name"], f)
                                   for k, (i, f) in enumerate(canon)])
            text = sample(model, tok, hdr, max_new=200)
            got = [attr(sn, sent_pool) for sn in sents(text)]
            n_sent += len(got)
            n_attr += sum(1 for r in got if r in canon)
            n_parrot += int(text in known)
            seq = [r for r in got if r in canon]
            if len(seq) >= 2:
                order_n += 1
                order_ok += int(seq == [c for c in canon if c in seq])
            per_line.append((dom, [deck[i]["name"] + ("" if f == "up" else " rev")
                                   for i, f in canon], text))
        held_attr = held_sent = held_parrot = 0
        for dom, hand, _gold in ev:
            n = len(hand)
            seat_names = [s["name"] for s in C.load_seats()[str(n)]]
            hdr = tok.header(dom, [(deck[i]["name"], seat_names[k], f)
                                   for k, (i, f) in enumerate(hand)])
            text = sample(model, tok, hdr, max_new=200)
            got = [attr(sn, sent_pool) for sn in sents(text)]
            held_sent += len(got)
            held_attr += sum(1 for r in got if r in hand)
            held_parrot += int(text in known)

        print(f"\n==== {out_dir} ====")
        print(f"fresh hands : trajectory {n_attr}/{max(n_sent,1)} attributed "
              f"sentences on-card; parrots {n_parrot}/{len(hands)}")
        print(f"seat order  : {order_ok}/{order_n} hands with >=2 attributed "
              f"sentences in canonical order")
        print(f"held-out    : trajectory {held_attr}/{max(held_sent,1)}; "
              f"exact training strings {held_parrot}/{len(ev)}")
        if a.verbose:
            for dom, names, text in per_line[:8]:
                print(f"  [{dom}] {', '.join(names)}\n      {text[:180]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dirs", nargs="+")
    ap.add_argument("-v", "--verbose", action="store_true")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
