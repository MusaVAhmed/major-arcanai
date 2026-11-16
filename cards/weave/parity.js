/* parity.js — dev-only check that weave.js and train.py agree token for
   token. Loads the exported weights exactly as the page does, decodes the
   saved greedy case from parity.json (through the real headerIds path, by
   inverting the ids — which also proves the id layout both sides assume),
   and compares. Run from cards/weave: node parity.js out-whisper
   Greedy agreement has a shelf life — python float32 and JS float64
   part company at near-ties — so the contract is "first 48 characters
   identical", reported honestly either way. */
'use strict';
const fs = require('fs');
const path = require('path');

const dir = process.argv[2] || 'out-whisper';
global.window = {};
global.fetch = async (u) => {
  const buf = fs.readFileSync(u);
  return {
    json: async () => JSON.parse(buf.toString()),
    arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength),
  };
};
require('./weave.js');
const W = global.window.ARCANAI_WEAVE;

(async () => {
  const ok = await W.boot(dir + '/');
  if (!ok) { console.log('BOOT FAIL'); process.exit(1); }
  const meta = JSON.parse(fs.readFileSync(path.join(dir, 'meta.json')));
  const tok = meta.tok;
  const base = {
    cards: 256,
    seats: 256 + tok.cards.length,
    faces: 256 + tok.cards.length + tok.seats.length,
    doms: 256 + tok.cards.length + tok.seats.length + tok.faces.length,
  };
  const par = JSON.parse(fs.readFileSync(path.join(dir, 'parity.json')));
  const ids = par.header;
  const dom = tok.domains[ids[0] - base.doms];
  const cards = [];
  for (let i = 1; i < ids.length - 1; i += 3) {
    cards.push({
      seat: tok.seats[ids[i] - base.seats],
      rev: ids[i + 1] - base.faces === 1,
      i: ids[i + 2] - base.cards,
    });
  }
  const got = W.reading({ dom, cards });
  const want = par.greedy;
  const n = 48;
  const a = got.slice(0, n), b = want.slice(0, n);
  console.log('js :', JSON.stringify(a));
  console.log('py :', JSON.stringify(b));
  console.log(a === b && a.length >= Math.min(n, Math.min(got.length, want.length))
    ? 'PARITY PASS' : 'PARITY FAIL');
  process.exit(a === b ? 0 : 2);
})();
