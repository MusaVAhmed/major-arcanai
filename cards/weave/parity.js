/* parity.js — dev-only check that weave.js and train.py agree token for
   token. Loads the exported weights exactly as the page does, decodes the
   saved greedy case from parity.json (through the real headerIds path, by
   inverting the ids — which also proves the id layout both sides assume),
   and compares. Run from cards/weave: node parity.js out-whisper
   Greedy agreement has a shelf life — python float32 and JS float64
   part company at near-ties — so the contract is margin-aware: identical
   strings, or a first divergence where the saved python top-2 margin was
   < 0.05 logits. A divergence at a fat margin fails loudly. */
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
  const gaps = par.gaps || [];
  // Contract: identical output, or the first divergence happens where the
  // PYTHON margin between first and second choice was < 0.05 logits — a
  // documented float-path tie, not a forward-pass disagreement. A
  // divergence at a large margin is a real bug and fails loudly.
  let i = 0;
  const n = Math.min(got.length, want.length);
  while (i < n && got[i] === want[i]) i++;
  const prefixOk = i === n && n >= 16;
  const tieOk = i < n && i < gaps.length && gaps[i] < 0.05;
  console.log('js :', JSON.stringify(got.slice(0, 48)));
  console.log('py :', JSON.stringify(want.slice(0, 48)));
  console.log(`agree to char ${i} of ${n}` + (i < n ? ` (python gap there: ${gaps[i] !== undefined ? gaps[i].toFixed(3) : 'n/a'})` : ''));
  console.log(prefixOk || tieOk ? (tieOk ? 'PARITY PASS (near-tie divergence)' : 'PARITY PASS') : 'PARITY FAIL');
  process.exit(prefixOk || tieOk ? 0 : 2);
})();
