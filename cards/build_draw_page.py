#!/usr/bin/env python3
"""Build the interactive draw page (v3: gold foil, swipeable stack, gyro fan)."""
import json, os, shutil

CARDS = os.path.dirname(os.path.abspath(__file__))
REL = os.path.join(os.path.dirname(CARDS), 'release', 'major-arcanai')

deck = json.load(open(os.path.join(REL, 'deck.json')))
os.makedirs(os.path.join(REL, 'assets'), exist_ok=True)
shutil.copy(os.path.join(CARDS, 'Cinzel.ttf'), os.path.join(REL, 'assets', 'Cinzel.ttf'))

deck_js = json.dumps([
    {"n": c['numeral'], "name": c['name'], "meaning": c['meaning'], "r": c['reversed'], "img": c['image']['web']}
    for c in deck['cards']
], indent=None)

html = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#141311">
<title>The Major ArcanAI — Draw a Card</title>
<style>
  @font-face { font-family: 'Cinzel'; src: url('assets/Cinzel.ttf'); font-weight: 400 900; }
  :root { --bone:#e9e3d3; --dim:#9a927f; --ink:#141311; --line:#3b372c;
          --gold1:#b8860b; --gold2:#ffd76a; --gold3:#fff3b0; }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html { overscroll-behavior: none; }
  body {
    margin:0; min-height:100vh; color:var(--bone);
    background: radial-gradient(ellipse 90% 70% at 50% 30%, #23201a 0%, var(--ink) 70%);
    font-family: Georgia, 'Times New Roman', serif; text-align:center;
    padding: max(1.2rem, env(safe-area-inset-top)) 1rem 4rem;
  }
  body.foil { background: radial-gradient(ellipse 90% 70% at 50% 30%, #1a1510 0%, #0a0908 70%); }
  h1 {
    font-family:'Cinzel', Georgia, serif; font-weight:700; letter-spacing:.16em;
    font-size: clamp(1.3rem, 6vw, 2.4rem); margin:.2em 0 .1em; text-transform:uppercase;
  }
  body.foil h1 {
    background: linear-gradient(100deg, var(--gold1), var(--gold2), var(--gold3), var(--gold2), var(--gold1));
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .orn { color:var(--dim); letter-spacing:.5em; user-select:none; margin:.2rem 0 1.2rem; }
  .modes { display:flex; gap:.6rem; justify-content:center; flex-wrap:wrap; margin-bottom:1.6rem; }
  button {
    font-family:'Cinzel', Georgia, serif; font-size:.78rem; letter-spacing:.12em; text-transform:uppercase;
    background:none; color:var(--bone); border:1px solid var(--line); padding:.75rem 1.2rem;
    cursor:pointer; transition: border-color .2s, background .2s; min-height:44px;
  }
  button:hover { border-color: var(--bone); }
  button.active { background: var(--bone); color: var(--ink); border-color: var(--bone); }
  button:focus-visible { outline: 2px solid var(--bone); outline-offset: 2px; }
  #foil.active {
    background: linear-gradient(100deg, var(--gold1), var(--gold2), var(--gold3), var(--gold2), var(--gold1));
    color:#0a0908; border-color:transparent;
  }
  #table { display:flex; gap: clamp(.8rem,2.5vw,2rem); justify-content:center; flex-wrap:wrap; perspective:1600px; min-height:280px; }
  #table.stackmode { display:block; }
  .slot { width: clamp(150px, 26vw, 250px); }
  .poslabel {
    font-family:'Cinzel', Georgia, serif; font-size:.68rem; letter-spacing:.22em; color:var(--dim);
    text-transform:uppercase; margin-bottom:.6rem; min-height:1em;
  }
  .t3d { transform: perspective(900px) rotateY(var(--tiltY, 0deg)) translateX(var(--tiltX, 0px)); }
  .scard .t3d, .deck .t3d { width:100%; height:100%; }
  .deck .t3d { position:relative; z-index:2; }
  .card { aspect-ratio: 5/8; position:relative; transform-style:preserve-3d; height:100%;
          transition: transform .7s cubic-bezier(.4,.1,.2,1); cursor:pointer; }
  .card.flipped { transform: rotateY(180deg); }
  .face { position:absolute; inset:0; backface-visibility:hidden; border-radius:10px; overflow:hidden;
          box-shadow: 0 8px 30px rgba(0,0,0,.55); background:#fff; }
  body.foil .face { background:#0a0908; }
  .face img { width:100%; height:100%; object-fit:cover; display:block; }
  .face.front { transform: rotateY(180deg); }
  .card.rev .face.front { transform: rotateY(180deg) rotate(180deg); }
  .revtag { font-style:italic; letter-spacing:.06em; }
  .sheen { position:absolute; inset:0; overflow:hidden; pointer-events:none; opacity:0; transition:opacity .25s;
           mask-size:cover; -webkit-mask-size:cover; mask-mode:luminance; }
  body.dragging .sheen { opacity:0 !important; }
  .glint { position:absolute; left:-50%; top:-50%; width:200%; height:200%;
           background: radial-gradient(circle, rgba(255,250,230,.85), rgba(255,250,230,.22) 17%, transparent 30%); }
  body.foil.sheen-live .sheen { opacity:1; }
  .tap { font-size:.75rem; font-style:italic; color:var(--dim); margin-top:.6rem; }
  .caption { opacity:0; transition: opacity .5s .2s; margin-top:.8rem; }
  .slot.revealed .caption, .stackwrap.revealed .caption { opacity:1; }
  .slot.revealed .tap { display:none; }
  .caption .cname { font-family:'Cinzel', Georgia, serif; font-size:.9rem; letter-spacing:.12em; text-transform:uppercase; }
  .caption .cnum { color:var(--dim); font-style:italic; font-size:.8rem; }
  .caption .cmean { color:var(--dim); font-size:.85rem; line-height:1.5; margin-top:.4rem; }
  /* idle deck pile */
  .deck { position:relative; cursor:pointer; animation:breathe 2.6s ease-in-out infinite alternate; }
  .deck .pile { position:absolute; inset:0; border-radius:10px; background:#f2ecdd; border:1px solid #b9b19d;
                box-shadow:0 8px 30px rgba(0,0,0,.55); }
  body.foil .deck .pile { background:#161119; border-color:#31281a; }
  .deck .p1 { transform:translate(5px,6px) rotate(1.6deg); }
  .deck .p2 { transform:translate(10px,12px) rotate(3.2deg); }
  @keyframes breathe { from { transform:translateY(0); } to { transform:translateY(-7px); } }
  @keyframes dealIn { from { transform:translateY(34px) scale(.92); opacity:0; } }
  .card.deal { animation:dealIn .45s cubic-bezier(.2,.8,.3,1) backwards; }
  /* swipeable stack (touch, multi-card spreads) */
  .stackwrap { max-width:min(76vw, 330px); margin:0 auto; }
  .stack { position:relative; aspect-ratio:5/8; touch-action:pan-y; }
  .scard { position:absolute; inset:0; transition:transform .3s cubic-bezier(.22,.9,.36,1.05), opacity .25s ease; will-change:transform; }
  .scard .card { width:100%; height:100%; }
  .dots { display:flex; gap:.55rem; justify-content:center; margin-top:1.1rem; }
  .dot { width:8px; height:8px; border-radius:50%; border:1px solid var(--dim); }
  .dot.active { background:var(--bone); border-color:var(--bone); }
  body.foil .dot.active { background:var(--gold2); border-color:var(--gold2); }
  .stackwrap .caption { min-height:5.6rem; }
  #galleryview { display:none; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:1.1rem;
                 max-width:72rem; margin:0 auto; }
  body.gallery #galleryview { display:grid; }
  body.gallery #table, body.gallery .hint, body.gallery #again { display:none !important; }
  .gcell { cursor:pointer; }
  .gcell img { width:100%; border-radius:8px; box-shadow:0 6px 20px rgba(0,0,0,.5); display:block; }
  .gcell .gname { font-family:'Cinzel', Georgia, serif; font-size:.68rem; letter-spacing:.1em;
                  text-transform:uppercase; margin-top:.5rem; }
  .gcell .gnum { color:var(--dim); font-style:italic; font-size:.7rem; }
  #lightbox { display:none; position:fixed; inset:0; background:rgba(8,7,5,.94); z-index:50;
              padding:2rem 1rem; overflow-y:auto; cursor:pointer; }
  #lightbox.open { display:block; }
  #lightbox img { max-width:min(88vw, 380px); border-radius:12px; box-shadow:0 12px 50px rgba(0,0,0,.8); }
  #lightbox .caption { opacity:1; max-width:34rem; margin:1rem auto 0; }
  #again { margin-top:2.2rem; display:none; }
  .hint { color:var(--dim); font-size:.85rem; font-style:italic; margin-top:1.4rem; }
  @media (max-width: 700px) {
    .modes { gap:.45rem; }
    button { font-size:.7rem; padding:.7rem .8rem; letter-spacing:.09em; }
    #table:not(.stackmode) { flex-direction: column; align-items: center; gap: 1.6rem; }
    .slot { width: min(72vw, 320px); }
    .slot.single { width: min(80vw, 340px); }
    .caption .cname { font-size:1rem; }
    .caption .cmean { font-size:.95rem; }
  }
  @media (prefers-reduced-motion: reduce) {
    .card, .scard, .caption { transition:none; }
    .deck { animation:none; }
    .card.deal { animation:none; }
  }
</style>
</head>
<body>
  <h1>The Major ArcanAI</h1>
  <div class="orn">&#9789; &#10022; &#9790;</div>
  <div class="modes" role="group" aria-label="Spread and style">
    <button id="m1" class="active">One</button>
    <button id="m3">Three</button>
    <button id="m5">Five</button>
    <button id="foil" aria-pressed="false">&#10022; Foil</button>
    <button id="gallery">All cards</button>
  </div>
  <div id="table" aria-live="polite"></div>
  <div id="galleryview"></div>
  <div id="lightbox" role="dialog" aria-label="Card detail"></div>
  <p class="hint" id="hint">Tap the deck to draw.</p>
  <button id="again">Shuffle &amp; draw again</button>

<script>
const DECK = __DECK__;
const LABELS = {1:[''],3:['Past','Present','Future'],5:['The Situation','The Obstacle','The Advice','The Vibe','The Outcome']};
const COARSE = matchMedia('(pointer: coarse)').matches || new URLSearchParams(location.search).has('touch');
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
let mode = 1;
let foil = localStorage.getItem('arcanai-foil') === '1';
let TILT = 0;
const table = document.getElementById('table');
const again = document.getElementById('again');
const hint = document.getElementById('hint');
const foilBtn = document.getElementById('foil');
const buzz = ms => { if (navigator.vibrate) navigator.vibrate(ms); };

const skin = p => foil ? p.replace('cards-web/', 'cards-foil-web/') : p;
function applyFoil() {
  document.body.classList.toggle('foil', foil);
  foilBtn.classList.toggle('active', foil);
  foilBtn.setAttribute('aria-pressed', String(foil));
  document.querySelectorAll('img[data-src]').forEach(img => { img.src = skin(img.dataset.src); });
  // glint only where the art is bright: mask each sheen with its own card image
  document.querySelectorAll('.face').forEach(f => {
    const img = f.querySelector('img'), sh = f.querySelector('.sheen');
    if (img && sh) sh.style.maskImage = `url("${img.getAttribute('src')}")`;
  });
  localStorage.setItem('arcanai-foil', foil ? '1' : '0');
}
foilBtn.addEventListener('click', () => { foil = !foil; applyFoil(); buzz(8); });

const galleryBtn = document.getElementById('gallery');
const galleryView = document.getElementById('galleryview');
const lightbox = document.getElementById('lightbox');

for (const n of [1,3,5]) {
  document.getElementById('m'+n).addEventListener('click', () => {
    mode = n;
    for (const k of [1,3,5]) document.getElementById('m'+k).classList.toggle('active', k === n);
    closeGallery();
    idle();
  });
}

function closeGallery() {
  document.body.classList.remove('gallery');
  galleryBtn.classList.remove('active');
}
galleryBtn.addEventListener('click', () => {
  const on = !document.body.classList.contains('gallery');
  document.body.classList.toggle('gallery', on);
  galleryBtn.classList.toggle('active', on);
  if (on && !galleryView.childElementCount) {
    DECK.forEach(c => {
      const cell = document.createElement('div');
      cell.className = 'gcell';
      cell.innerHTML = `<img data-src="${c.img}" alt="${c.name}" loading="lazy">
        <div class="gname">${c.name}</div><div class="gnum">${c.n}</div>`;
      cell.addEventListener('click', () => {
        lightbox.innerHTML = `<img data-src="${c.img}" alt="${c.name}">
          <div class="caption"><div class="cname">${c.name}</div><div class="cnum">${c.n}</div>
          <div class="cmean">${c.meaning}</div>
          <div class="cmean"><span class="revtag">Reversed:</span> ${c.r}</div></div>`;
        lightbox.classList.add('open');
        applyFoil();
      });
      galleryView.appendChild(cell);
    });
  }
  if (on) applyFoil();
});
lightbox.addEventListener('click', () => lightbox.classList.remove('open'));

function cardHTML(frontImg, alt) {
  const front = frontImg ? `<img data-src="${frontImg}" alt="${alt}">` : '';
  return `<div class="t3d"><div class="card"><div class="face back"><img data-src="cards-web/back.png" alt="card back"><span class="sheen"><span class="glint"></span></span></div>
    <div class="face front">${front}<span class="sheen"><span class="glint"></span></span></div></div></div>`;
}
const capHTML = c => `<div class="cname">${c.name}</div>
  <div class="cnum">${c.n}${c.rev ? ' &middot; <span class="revtag">reversed</span>' : ''}</div>
  <div class="cmean">${c.rev ? c.r : c.meaning}</div>`;

function idle() {
  again.style.display = 'none';
  hint.style.display = '';
  table.classList.remove('stackmode');
  table.innerHTML = '';
  const slot = document.createElement('div');
  slot.className = 'slot single';
  slot.innerHTML = `<div class="poslabel"></div>
    <div class="deck"><div class="pile p2"></div><div class="pile p1"></div>` + cardHTML('', '') + `</div>`;
  slot.querySelector('.deck').addEventListener('click', draw);
  slot.querySelector('.deck').setAttribute('title', 'Draw');
  table.appendChild(slot);
  applyFoil();
}

function draw() {
  buzz(8);
  const picks = [...DECK].sort(() => Math.random() - .5).slice(0, mode)
    .map(c => ({...c, rev: Math.random() < .5}));
  hint.style.display = 'none';
  table.innerHTML = '';
  if (COARSE && mode > 1) { buildStack(picks); return; }
  table.classList.remove('stackmode');
  picks.forEach((c, i) => {
    const slot = document.createElement('div');
    slot.className = 'slot' + (mode === 1 ? ' single' : '');
    slot.innerHTML = `<div class="poslabel">${LABELS[mode][i] || ''}</div>` + cardHTML(c.img, c.name) +
      `<div class="tap">tap or flick to reveal</div><div class="caption">${capHTML(c)}</div>`;
    if (c.rev) slot.querySelector('.card').classList.add('rev');
    const flip = () => {
      if (slot.classList.contains('revealed')) return;
      slot.querySelector('.card').classList.add('flipped');
      slot.classList.add('revealed');
      buzz(12);
      if ([...table.children].every(s => s.classList.contains('revealed')))
        again.style.display = 'inline-block';
    };
    slot.querySelector('.card').addEventListener('click', flip);
    const cardEl = slot.querySelector('.card');
    cardEl.classList.add('deal');
    cardEl.style.animationDelay = (i * 120) + 'ms';
    table.appendChild(slot);
    if (!COARSE) {  // desktop: auto-reveal; touch always gets the flip gesture
      slot.querySelector('.tap').style.display = 'none';
      setTimeout(flip, REDUCED ? 0 : 550 + i * 550);
    }
  });
  applyFoil();
}

/* ---- swipeable stack ---- */
const S = { order: [], els: [], picks: [], revealed: new Set(), wrap: null, dragging: false, side: -1 };
const topIdx = () => S.order[0];
const topEl = () => S.els[topIdx()];

function buildStack(picks) {
  table.classList.add('stackmode');
  S.picks = picks; S.order = [...picks.keys()]; S.revealed = new Set();
  const wrap = document.createElement('div');
  wrap.className = 'stackwrap';
  wrap.innerHTML = `<div class="poslabel" id="spos"></div><div class="stack" id="stack"></div>
    <div class="dots" id="dots">${picks.map(() => '<span class="dot"></span>').join('')}</div>
    <div class="tap" id="shint"></div><div class="caption" id="scap"></div>`;
  table.appendChild(wrap);
  S.wrap = wrap;
  const stack = wrap.querySelector('#stack');
  S.els = picks.map(c => {
    const el = document.createElement('div');
    el.className = 'scard';
    el.innerHTML = cardHTML(c.img, c.name);
    if (c.rev) el.querySelector('.card').classList.add('rev');
    stack.appendChild(el);
    return el;
  });
  attachDrag(stack);
  // deal-in: start as one pile, then fan out with a stagger
  if (REDUCED) { layoutStack(); }
  else {
    S.els.forEach(el => { el.style.transition = 'none'; el.style.transform = 'translate(0,0)'; });
    void stack.offsetWidth;
    S.els.forEach(el => { el.style.transition = ''; });
    S.order.forEach((ci, pos) => { S.els[ci].style.transitionDelay = (pos * 70) + 'ms'; });
    requestAnimationFrame(() => layoutStack());
    setTimeout(() => S.els.forEach(el => { el.style.transitionDelay = ''; }), 800);
  }
  updateStackUI(); applyFoil();
}

function layoutStack(dragX = 0, dragY = 0) {
  // fan follows the tilt direction: lean right, cards fan right (hysteresis near flat)
  let dir = Math.max(-1, Math.min(1, TILT * 1.5));
  if (Math.abs(dir) < 0.4) dir = S.side * 0.4;
  else S.side = dir < 0 ? -1 : 1;
  S.order.forEach((ci, pos) => {
    const el = S.els[ci];
    el.style.zIndex = String(100 - pos);
    if (pos === 0) {
      el.style.transform = `translateX(${dragX}px) translateY(${dragY}px) rotate(${dragX / 24}deg)`;
    } else {
      const p = Math.min(pos, 3);
      el.style.transform =
        `translateX(${(14 * dir * p).toFixed(1)}px) translateY(${7 * p}px) rotate(${(4 * dir * p).toFixed(2)}deg) scale(${1 - p * 0.03})`;
    }
  });
}

function updateStackUI() {
  const i = topIdx();
  S.wrap.querySelector('#spos').textContent = LABELS[mode][i] || '';
  S.wrap.querySelectorAll('.dot').forEach((d, k) => d.classList.toggle('active', k === i));
  const seen = S.revealed.has(i);
  S.wrap.classList.toggle('revealed', seen);
  S.wrap.querySelector('#scap').innerHTML = seen ? capHTML(S.picks[i]) : '';
  S.wrap.querySelector('#shint').textContent = seen
    ? (S.revealed.size === S.picks.length ? 'swipe to fidget' : 'swipe for next')
    : 'tap or flick your wrist to reveal · swipe for next';
  again.style.display = S.revealed.size === S.picks.length ? 'inline-block' : 'none';
}

function attachDrag(stack) {
  let x0 = 0, y0 = 0, dragging = false, moved = false;
  let lastX = 0, lastT = 0, vx = 0, raf = null, curDX = 0, curDY = 0;
  const paint = () => { raf = null; layoutStack(curDX, curDY); };
  stack.addEventListener('pointerdown', e => {
    dragging = true; S.dragging = true; moved = false;
    document.body.classList.add('dragging');
    x0 = lastX = e.clientX; y0 = e.clientY; lastT = e.timeStamp; vx = 0;
    stack.setPointerCapture(e.pointerId);
    topEl().style.transition = 'none';
  });
  stack.addEventListener('pointermove', e => {
    if (!dragging) return;
    curDX = e.clientX - x0;
    curDY = (e.clientY - y0) * 0.25;          // a little vertical give, feels held
    const dt = e.timeStamp - lastT;
    if (dt > 0) vx = 0.8 * vx + 0.2 * (e.clientX - lastX) / dt;
    lastX = e.clientX; lastT = e.timeStamp;
    if (Math.abs(curDX) > 6) moved = true;
    if (!raf) raf = requestAnimationFrame(paint);
  });
  const end = e => {
    if (!dragging) return;
    dragging = false; S.dragging = false;
    document.body.classList.remove('dragging');
    if (raf) { cancelAnimationFrame(raf); raf = null; }
    const dx = e.clientX - x0;
    topEl().style.transition = '';
    // distance OR velocity: a quick flick counts even if short
    if (moved && S.picks.length > 1 && (Math.abs(dx) > 70 || Math.abs(vx) > 0.55))
      flingNext(dx !== 0 ? dx : vx, curDY);
    else { layoutStack(0, 0); if (!moved) tapTop(); }
    curDX = curDY = 0;
  };
  stack.addEventListener('pointerup', end);
  stack.addEventListener('pointercancel', () => {
    dragging = false; S.dragging = false; document.body.classList.remove('dragging'); if (raf) { cancelAnimationFrame(raf); raf = null; }
    topEl().style.transition = ''; layoutStack(0, 0); curDX = curDY = 0;
  });
}

function flingNext(dir, dy = 0) {
  const el = topEl();
  buzz(6);
  if (REDUCED) { S.order.push(S.order.shift()); layoutStack(); updateStackUI(); return; }
  const sign = dir > 0 ? 1 : -1;
  const out = Math.max(360, Math.min(innerWidth, 700) * 0.9);
  el.style.transition = 'transform .22s cubic-bezier(.35,.6,.5,1)';
  el.style.transform = `translateX(${sign * out}px) translateY(${dy}px) rotate(${sign * 20}deg)`;
  setTimeout(() => {
    S.order.push(S.order.shift());
    // re-enter at the BACK of the fan: snap there invisibly, then fade in
    el.style.transition = 'none';
    el.style.opacity = '0';
    layoutStack();
    void el.offsetWidth;
    el.style.transition = '';
    el.style.opacity = '1';
    updateStackUI();
  }, 225);
}

function tapTop() {
  const i = topIdx();
  if (S.revealed.has(i)) return;
  topEl().querySelector('.card').classList.add('flipped');
  S.revealed.add(i);
  buzz(12);
  updateStackUI();
}

/* ---- sheen + tilt ---- */
function setSheen(lxPx, lyPx) {
  document.querySelectorAll('.sheen').forEach(s => {
    const r = s.closest('.card').getBoundingClientRect();
    if (!r.width) return;
    const x = Math.max(-.6, Math.min(1.6, (lxPx - r.left) / r.width));
    const y = Math.max(-.6, Math.min(1.6, (lyPx - r.top) / r.height));
    const g = s.firstElementChild;
    const m = (s.closest('.card')?.classList.contains('rev') && s.closest('.face')?.classList.contains('front')) ? -1 : 1;
    if (g) g.style.transform = `translate(${(m * (x - .5) * r.width).toFixed(1)}px, ${(m * (y - .5) * r.height).toFixed(1)}px)`;
  });
}
const DEBUG = new URLSearchParams(location.search).has('debug');
let dbgEl = null;
if (DEBUG) {
  dbgEl = document.createElement('div');
  dbgEl.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:#000c;color:#7f7;font:12px monospace;padding:4px;z-index:999;text-align:left';
  dbgEl.textContent = 'debug: waiting for deviceorientation... secure=' + isSecureContext + ' coarse=' + COARSE;
  document.body.appendChild(dbgEl);
}
if (COARSE && 'DeviceOrientationEvent' in window) {
  let raf = null;
  const onOri = e => {
    if (DEBUG) dbgEl.textContent = 'debug: type=' + e.type +
      ' beta=' + (e.beta === null ? 'null' : e.beta.toFixed(1)) +
      ' gamma=' + (e.gamma === null ? 'null' : e.gamma.toFixed(1)) +
      ' live=' + document.body.classList.contains('sheen-live') +
      ' reduced=' + REDUCED +
      ' tiltY=' + document.documentElement.style.getPropertyValue('--tiltY') +
      ' rate=' + (window.__rate || '0');
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = null;
      if (e.gamma === null && e.beta === null) return;   // no sensor data: keep sheen off
      document.body.classList.add('sheen-live');
      const g = e.gamma || 0;
      TILT = TILT * 0.8 + Math.max(-0.7, Math.min(0.7, g / 45)) * 0.2;   // low-pass: ignore hand tremor
      // sheen wants a deliberate lean: quadratic response on the smoothed tilt
      setSheen(innerWidth * Math.max(-.15, Math.min(1.15, .5 + TILT * Math.abs(TILT) * 1.4)),
               innerHeight * .42);   // vertical locked: only side-to-side tilt moves the light
      document.documentElement.style.setProperty('--tiltY', (TILT * 12).toFixed(2) + 'deg');
      document.documentElement.style.setProperty('--tiltX', (TILT * 14).toFixed(1) + 'px');
      if (table.classList.contains('stackmode') && !S.dragging) layoutStack();
    });
  };
  addEventListener('deviceorientation', onOri);
  addEventListener('deviceorientationabsolute', onOri);
  // wrist flick = rotation-rate spike far above normal tilt play
  let lastFlick = 0;
  addEventListener('devicemotion', e => {
    const rate = (e.rotationRate && e.rotationRate.gamma) || 0;
    if (DEBUG) window.__rate = Math.abs(rate).toFixed(0);
    const now = e.timeStamp;
    if (Math.abs(rate) > 170 && now - lastFlick > 700) {
      lastFlick = now;
      if (table.classList.contains('stackmode')) {
        if (S.dragging) return;
        if (!S.revealed.has(topIdx())) tapTop();
        else if (S.picks.length > 1) flingNext(rate);
      } else {
        const card = [...table.querySelectorAll('.slot')]
          .find(s => !s.classList.contains('revealed') && s.querySelector('.face.front img'))
          ?.querySelector('.card');
        if (card) card.click();
      }
    }
  });
  if (typeof DeviceOrientationEvent.requestPermission === 'function') {
    const ask = () => { DeviceOrientationEvent.requestPermission().catch(() => {}); removeEventListener('click', ask); };
    addEventListener('click', ask);
  }
} else {
  addEventListener('pointermove', e => {
    document.body.classList.add('sheen-live');
    setSheen(e.clientX, e.clientY);
  });
}

again.addEventListener('click', idle);
idle();
</script>
</body>
</html>
"""

html = html.replace('__DECK__', deck_js)
with open(os.path.join(REL, 'index.html'), 'w') as f:
    f.write(html)
print('wrote index.html', len(html), 'bytes')

for c in deck['cards']:
    c['image']['foil_full'] = c['image']['full'].replace('cards/', 'cards-foil/')
    c['image']['foil_web'] = c['image']['web'].replace('cards-web/', 'cards-foil-web/')
deck['back']['foil_full'] = 'cards-foil/back.png'
deck['back']['foil_web'] = 'cards-foil-web/back.png'
with open(os.path.join(REL, 'deck.json'), 'w') as f:
    json.dump(deck, f, indent=2)
print('deck.json updated')
