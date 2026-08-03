#!/usr/bin/env python3
"""Dump the embedding corpus the way the page hands it to attune.js.

Reads MEANINGS / REVERSED / SITUATIONS / SITUATIONS_REV out of a package.py
(by AST, so nothing imports PIL) and card names out of manifest.json, and
writes the short-key `DECK` shape the runtime actually sees:
    {slug, name, meaning, r, sit, sitr}

Slugs present in package.py but not yet in manifest.json (a proposed card with
no art) get their name from NEW_NAMES below, so a copy pass can be
dilution-checked before a single image exists.

Usage: python3 deck_dump.py [package.py] [manifest.json] > deck.json
"""
import ast, json, os, sys

CARDS = os.path.dirname(os.path.abspath(__file__))

# Proposed cards, keyed by slug, that exist in package.py's copy dicts but not
# yet in manifest.json. Fill this in to dilution-check a copy pass before any
# art exists; empty it again once the cards land in the manifest.
NEW_NAMES = {}

WANT = ("MEANINGS", "REVERSED", "SITUATIONS", "SITUATIONS_REV")


def dicts(path):
    tree = ast.parse(open(path).read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            n = node.targets[0].id
            if n in WANT:
                out[n] = ast.literal_eval(node.value)
    return out


def main():
    pkg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(CARDS, 'package.py')
    man = sys.argv[2] if len(sys.argv) > 2 else os.path.join(CARDS, 'manifest.json')
    d = dicts(pkg)
    names = {c['slug']: c['name'] for c in json.load(open(man))['cards']}
    deck = []
    for slug in d['MEANINGS']:
        deck.append({
            "slug": slug,
            "name": names.get(slug) or NEW_NAMES[slug],
            "meaning": d['MEANINGS'][slug],
            "r": d['REVERSED'][slug],
            "sit": d['SITUATIONS'][slug],
            "sitr": d['SITUATIONS_REV'][slug],
        })
    json.dump(deck, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
