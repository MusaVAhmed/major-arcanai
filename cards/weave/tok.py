"""Byte-level tokenizer for weave, plus the entity vocabulary.

The text side is raw UTF-8 bytes: zero vocab file, zero parity surface,
the same letter-by-letter contract TINY 2.1 ships. Entity tokens
(cards, seats, faces, domains) live above the bytes and appear in the
deal header only — a generated line never contains one, so every emitted
id under 256 is text and nothing else. Vocab and ids are exported to
meta.json so weave.js reads these numbers, never re-derives them.

Header grammar (the whole conditioning, in order):
    <dom:...> (<seat:...> <up|rev> <card-name>){n} <deal_end>
then the reading's bytes, then <eos>. Loss is computed on the text+eos
span only; the header is context, not target.
"""

SEATS = [
    "<noseat>",
    "Past", "Present", "Future",
    "The Situation", "The Obstacle", "The Advice", "The Vibe", "The Outcome",
    "What Crosses You", "The Root", "The Recent Past", "The Crown",
    "The Near Future", "The Self", "The House", "Hopes and Fears",
]
FACES = ["up", "rev"]
DOMAINS = ["none", "work", "love", "kin", "loss", "change", "self"]


class Tok:
    def __init__(self, card_names):
        self.card_names = list(card_names)
        self.n_bytes = 256
        id = self.n_bytes
        self.card_id = {}
        for name in self.card_names:
            self.card_id[name] = id; id += 1
        self.seat_id = {s: id + i for i, s in enumerate(SEATS)}
        id += len(SEATS)
        self.face_id = {f: id + i for i, f in enumerate(FACES)}
        id += len(FACES)
        self.dom_id = {d: id + i for i, d in enumerate(DOMAINS)}
        id += len(DOMAINS)
        self.deal_end = id; id += 1
        self.eos = id; id += 1
        self.vocab_size = id
        self.n_special_text = 0  # no special may ever be emitted in a line

    def header(self, dom, cards):
        """cards: list of (name, seat, face). Returns token ids."""
        out = [self.dom_id.get(dom, self.dom_id["none"])]
        for name, seat, face in cards:
            out.append(self.seat_id[seat])
            out.append(self.face_id[face])
            out.append(self.card_id[name])
        out.append(self.deal_end)
        return out

    def encode_text(self, s):
        return [c for c in s.encode("utf-8")]

    def decode_text(self, ids):
        end = next((i for i, v in enumerate(ids) if v >= self.n_bytes), len(ids))
        return bytes(ids[:end]).decode("utf-8", errors="replace")

    def meta(self):
        return {
            "n_bytes": self.n_bytes,
            "cards": self.card_names,
            "seats": SEATS, "faces": FACES, "domains": DOMAINS,
            "deal_end": self.deal_end, "eos": self.eos,
            "vocab_size": self.vocab_size,
        }
