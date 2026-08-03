/* ── dilution_check.mjs · the check CLAUDE.md keeps demanding ──────────
   Rebuilds attune.js's card corpus outside the browser and asks the one
   question the situational-expansion rule is about: does every card still
   rank FIRST when the seeker types that card's own meaning?

   Documents are built EXACTLY as attune.js builds them (see upText/revText
   there); questions go through the same normalisation embedQuestion() uses
   (trim, lowercase, collapse whitespace). Same model, same dtype.

   Setup (node 18+):
     npm i @huggingface/transformers@3.3.3
   then, from cards/:
     python3 deck_dump.py > /tmp/deck_new.json
     git show HEAD:cards/package.py > /tmp/pkg_base.py
     python3 deck_dump.py /tmp/pkg_base.py > /tmp/deck_base.json
     node dilution_check.mjs /tmp/deck_new.json /tmp/deck_base.json

   With two decks it also diffs the ranks, i.e. it shows whether the cards
   added in the first deck pulled any card in the second off its own meaning.
   The module is resolved from $TRANSFORMERS if set, else by bare specifier.
   ─────────────────────────────────────────────────────────────────────── */
import { readFileSync } from 'node:fs';

const MODEL = 'Xenova/all-MiniLM-L6-v2';
const { pipeline, env } = await import(process.env.TRANSFORMERS || '@huggingface/transformers');
env.allowLocalModels = false;

const argv = process.argv.slice(2);
if (!argv.length) { console.error('usage: node dilution_check.mjs deck.json [baseline.json]'); process.exit(1); }
const load = (p) => JSON.parse(readFileSync(p, 'utf8'));

const extractor = await pipeline('feature-extraction', MODEL, { dtype: 'q8' });
/* EMB1=1 embeds one text per forward pass. The browser embeds the whole
   corpus in one call, but a q8 batch pads every sequence to the longest in
   it, and the padding perturbs a vector in the third decimal — enough to
   flip two cards sitting 0.005 apart when a longer card is ADDED to the
   batch, which looks exactly like dilution and is not. Batch of one removes
   the confound; use it whenever a rank change needs to be believed. */
const ONE = process.env.EMB1 === '1';
async function embed(texts) {
  if (ONE) {
    const vecs = [];
    for (const t of texts) {
      const out = await extractor([t], { pooling: 'mean', normalize: true });
      vecs.push(out.data.slice(0, out.dims[1]));
    }
    return vecs;
  }
  const out = await extractor(texts, { pooling: 'mean', normalize: true });
  const [n, d] = out.dims, data = out.data, vecs = [];
  for (let i = 0; i < n; i++) vecs.push(data.slice(i * d, (i + 1) * d));
  return vecs;
}
const dot = (a, b) => { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * b[i]; return s; };
const norm = (q) => q.trim().toLowerCase().replace(/\s+/g, ' ');
const f3 = (x) => x.toFixed(3);

/* byte-for-byte the construction in attune.js */
const upTextOf = (DECK) => DECK.map((c) => `${c.name}. ${c.meaning}${c.sit ? ' ' + c.sit : ''}`);
const revTextOf = (DECK) => DECK.map((c) => `${c.name}, reversed. ${c.r || ''}${c.sitr ? ' ' + c.sitr : ''}`);

async function corpus(DECK) {
  const vUp = await embed(upTextOf(DECK));
  const vRev = await embed(revTextOf(DECK));
  return { DECK, vUp, vRev };
}

/* readFor()'s card score: a card is relevant if EITHER face speaks. */
function rankFor(C, qv) {
  const sims = C.vUp.map((v, i) => Math.max(dot(qv, v), dot(qv, C.vRev[i])));
  const order = sims.map((s, i) => [s, i]).sort((a, b) => b[0] - a[0]);
  return { sims, order };
}

async function selfRanks(C, field) {
  const qs = C.DECK.map((c) => norm(c[field]));
  const qv = await embed(qs);
  return C.DECK.map((c, i) => {
    const { sims, order } = rankFor(C, qv[i]);
    const rank = order.findIndex(([, j]) => j === i) + 1;
    const top = order[0];
    return { slug: c.slug, rank, sim: sims[i], winner: C.DECK[top[1]].slug, winSim: top[0],
             runner: C.DECK[order[1][1]].slug, runnerSim: order[1][0] };
  });
}

const [newDeck, baseDeck] = [load(argv[0]), argv[1] ? load(argv[1]) : null];
const CN = await corpus(newDeck);
const CB = baseDeck ? await corpus(baseDeck) : null;

/* ── 1. self-rank ─────────────────────────────────────────────────── */
const LABELS = { meaning: 'UPRIGHT MEANING', r: 'REVERSED MEANING',
                 sit: 'UPRIGHT SITUATIONS', sitr: 'REVERSED SITUATIONS' };
for (const field of (process.env.FIELDS || 'meaning,r').split(',')) {
  const label = LABELS[field];
  const rn = await selfRanks(CN, field);
  const rb = CB ? await selfRanks(CB, field) : null;
  const bByS = rb ? Object.fromEntries(rb.map((r) => [r.slug, r])) : null;
  const fails = rn.filter((r) => r.rank !== 1);
  console.log(`\n=== SELF-RANK, query = card's own ${label} (${CN.DECK.length} cards) ===`);
  console.log(`first place: ${rn.length - fails.length}/${rn.length}`);
  for (const r of fails)
    console.log(`  MISS  ${r.slug.padEnd(20)} rank ${String(r.rank).padStart(2)}  self ${f3(r.sim)}  beaten by ${r.winner} ${f3(r.winSim)}`);
  if (bByS) {
    const moved = rn.filter((r) => bByS[r.slug] && bByS[r.slug].rank !== r.rank);
    console.log(`rank changes vs baseline (${CB.DECK.length} cards): ${moved.length}`);
    for (const r of moved)
      console.log(`  ${r.slug.padEnd(20)} ${bByS[r.slug].rank} -> ${r.rank}   (self ${f3(bByS[r.slug].sim)} -> ${f3(r.sim)})  now beaten by ${r.rank === 1 ? '-' : r.winner}`);
    const margins = rn.filter((r) => r.rank === 1)
      .map((r) => [r.slug, r.sim - r.runnerSim, r.runner]).sort((a, b) => a[1] - b[1]).slice(0, 8);
    console.log('thinnest winning margins (self - runner-up):');
    for (const [s, m, run] of margins) console.log(`  ${s.padEnd(20)} +${f3(m)}  over ${run}`);
  }
}

/* ── 2. neighbours: every face of a new card vs every face of the old deck ── */
if (CB) {
  const oldSlugs = new Set(CB.DECK.map((c) => c.slug));
  const newIdx = CN.DECK.map((c, i) => [c, i]).filter(([c]) => !oldSlugs.has(c.slug));
  const faces = [];
  CN.DECK.forEach((c, i) => {
    faces.push({ key: c.slug, face: 'up', v: CN.vUp[i], isNew: !oldSlugs.has(c.slug) });
    faces.push({ key: c.slug, face: 'rev', v: CN.vRev[i], isNew: !oldSlugs.has(c.slug) });
  });
  console.log('\n=== NEAREST NEIGHBOURS · new card faces vs existing faces (cosine) ===');
  for (const [c, i] of newIdx) {
    for (const face of ['up', 'rev']) {
      const v = face === 'up' ? CN.vUp[i] : CN.vRev[i];
      const near = faces.filter((f) => !f.isNew).map((f) => [dot(v, f.v), `${f.key}${f.face === 'rev' ? '-rev' : ''}`])
        .sort((a, b) => b[0] - a[0]).slice(0, 5);
      console.log(`${(c.slug + (face === 'rev' ? '-rev' : '')).padEnd(20)} ${near.map(([s, k]) => `${k} ${f3(s)}`).join('   ')}`);
    }
  }
  // new-vs-new too: six cards added at once can collide with each other
  console.log('\n=== new vs new (cosine, faces) ===');
  const nf = faces.filter((f) => f.isNew);
  const pairs = [];
  for (let a = 0; a < nf.length; a++) for (let b = a + 1; b < nf.length; b++)
    if (nf[a].key !== nf[b].key) pairs.push([dot(nf[a].v, nf[b].v), `${nf[a].key}-${nf[a].face} / ${nf[b].key}-${nf[b].face}`]);
  pairs.sort((a, b) => b[0] - a[0]).slice(0, 8).forEach(([s, k]) => console.log(`  ${f3(s)}  ${k}`));
}

/* ── 2b. what the deck actually does with real questions ─────────────── */
if (process.env.QFILE) {
  const qs = readFileSync(process.env.QFILE, 'utf8').split('\n').map((s) => s.trim()).filter(Boolean);
  const qv = await embed(qs.map(norm));
  console.log('\n=== QUESTIONS · top 5 cards (face shown), new deck vs baseline ===');
  const line = (C, v) => {
    const { order } = rankFor(C, v);
    return order.slice(0, 5).map(([s, i]) => {
      const up = dot(v, C.vUp[i]), rev = dot(v, C.vRev[i]);
      return `${C.DECK[i].slug}${rev > up ? '↯' : ''} ${f3(s)}`;
    }).join('  ');
  };
  qs.forEach((q, i) => {
    console.log(`\n"${q}"`);
    console.log(`  new : ${line(CN, qv[i])}`);
    if (CB) console.log(`  base: ${line(CB, qv[i])}`);
  });
}

/* ── 3. named suspicions, if a list is given on stdin as JSON ────────── */
const SUSPECT = process.env.SUSPECT ? JSON.parse(process.env.SUSPECT) : null;
if (SUSPECT && CB) {
  console.log('\n=== named suspicions ===');
  const byFace = {};
  CN.DECK.forEach((c, i) => { byFace[c.slug] = CN.vUp[i]; byFace[c.slug + '-rev'] = CN.vRev[i]; });
  for (const [a, b] of SUSPECT) {
    if (!byFace[a] || !byFace[b]) { console.log(`  ?? ${a} / ${b} (unknown face)`); continue; }
    console.log(`  ${f3(dot(byFace[a], byFace[b]))}  ${a} / ${b}`);
  }
}
