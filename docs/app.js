(() => {
const $ = s => document.querySelector(s);
const main = $('#main');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => n == null ? '' : n >= 1e6 ? (n/1e6).toFixed(1).replace(/\.0$/,'')+'M' : n >= 1e4 ? (n/1e3).toFixed(1).replace(/\.0$/,'')+'K' : Math.round(n).toLocaleString('en-US');
const mon = t => new Date(t*1000).toLocaleDateString('en-US', {month:'short', year:'numeric'});
const day = t => new Date(t*1000).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
const plural = (n, w) => `${n.toLocaleString('en-US')} ${w}${n === 1 ? '' : 's'}`;
const linkify = raw => {                  // match URLs on the raw text, escape every piece separately
  const s = String(raw ?? ''); let out = '', last = 0;
  for (const m of s.matchAll(/https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)\]]/g)) {
    out += esc(s.slice(last, m.index)) + `<a href="${esc(m[0])}" rel="nofollow noopener" target="_blank">${esc(m[0])}</a>`; last = m.index + m[0].length;
  }
  return out + esc(s.slice(last));
};
const stars = r => r ? `<span class="star" aria-hidden="true">★</span><span class="sr">rated </span> ${r.toFixed(1)}` : '';
const icon = (a, lazy) => `<span class="ico">${a.i || a.icon ? `<img class="icon"${lazy ? ' loading="lazy"' : ''} src="${esc(a.i || a.icon)}" alt="">` : `<div class="icon ph" aria-hidden="true">${esc((a.n || a.name || '?')[0])}</div>`}</span>`;
// thumbs icons: Lucide, ISC license (see LICENSE)
const TH = {up: '<svg class="th" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/></svg>',
  down: '<svg class="th" viewBox="0 0 24 24" aria-hidden="true"><path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/></svg>'};
const moodPct = (m, pct) => `<span class="mood ${m}">${TH[m]}<span class="sr">${m === 'up' ? 'positive' : 'negative'} </span>${pct}%</span>`;
const moodWord = m => `<span class="mood ${m}">${TH[m]}${m === 'up' ? 'positive' : 'negative'}</span>`;
const moodOf = a => a.mo === 1 ? 'up' : a.mo === -1 ? 'down' : '';

// ---- periods (week / month / year leaderboards, in UTC days) ----
const DAY = 86400000;
let todayDay = Math.floor(Date.now() / DAY), firstDay = 0, Y0 = 2007, NY = 1;   // set from the data on load
const dUTC = d => new Date(d * DAY);
const dayOf = (y, m, d) => Math.round(Date.UTC(y, m, d) / DAY);
function range(mode, a) {
  const t = dUTC(a), y = t.getUTCFullYear(), m = t.getUTCMonth();
  if (mode === 'year') return [dayOf(y, 0, 1), dayOf(y + 1, 0, 1)];
  if (mode === 'month') return [dayOf(y, m, 1), dayOf(y, m + 1, 1)];
  const s = a - ((t.getUTCDay() + 6) % 7); return [s, s + 7];
}
function label(mode, a) {
  const [s, e] = range(mode, a), t = dUTC(s);
  if (mode === 'year') return String(t.getUTCFullYear());
  if (mode === 'month') return t.toLocaleDateString('en-US', {month: 'long', year: 'numeric', timeZone: 'UTC'});
  const f = d => dUTC(d).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'});
  return `${f(s)} – ${f(e - 1)}, ${dUTC(e - 1).getUTCFullYear()}`;
}
function key(mode, a) {
  const iso = dUTC(range(mode, a)[0]).toISOString().slice(0, 10);
  return mode === 'year' ? iso.slice(0, 4) : mode === 'month' ? iso.slice(0, 7) : iso;
}
function parseKey(mode, k) {               // strict: anything malformed falls back to the latest period
  let m;
  if (!k) return null;
  if (mode === 'year' && (m = /^(\d{4})$/.exec(k))) return dayOf(+m[1], 0, 1);
  if (mode === 'month' && (m = /^(\d{4})-(\d{2})$/.exec(k)) && +m[2] >= 1 && +m[2] <= 12) return dayOf(+m[1], +m[2] - 1, 1);
  if (mode === 'week' && (m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(k))) {
    const d = dayOf(+m[1], +m[2] - 1, +m[3]), t = dUTC(d);
    if (t.getUTCMonth() === +m[2] - 1 && t.getUTCDate() === +m[3]) return d;
  }
  return null;
}
const shift = (mode, a, n) => n > 0 ? range(mode, a)[1] : range(mode, range(mode, a)[0] - 1)[0];
// weeks and months must be complete (the current one is nearly empty); the current year is fine. "Today" is the data's build date.
const limitEnd = mode => mode === 'year' ? todayDay + 1 : range(mode, todayDay)[0];
const latest = mode => mode === 'year' ? todayDay : range(mode, todayDay)[0] - 1;
const earliest = mode => range(mode, firstDay)[0];
const clamp = (mode, a) => range(mode, a)[1] > limitEnd(mode) ? range(mode, latest(mode))[0] : a < earliest(mode) ? earliest(mode) : range(mode, a)[0];
function inPeriod(a, s, e) {               // period mentions, period score (weights + distinct outside users), period submission points
  let n = 0, k = 0, p = 0, x = 0, l = 0; const us = new Set();
  for (let i = 0; i < a.t.length; i++) {
    const d = a.t[i]; if (d >= e) break;
    if (d >= s) { n++; k += a.w[i]; p += a.pt[i]; x |= a.sh[i]; l = d; if (a.uu[i] >= 0) us.add(a.uu[i]); }
  }
  a.pm = n; a.pk = k + us.size; a.ph = p; a.px = x; a.pl = l * 86400 + 43200; return n;   // pl: latest mention in the period, noon UTC of its day
}

// ---- state ----
let DB = null, AD = null, STATS = null, dbP = null, metaP = null;
let navToken = 0, routeKind = '', lastListHash = '#/';
const savedScroll = {};
const state = {plat: 0, mood: 0, sort: 'score', cat: null, q: '', limit: 60, mode: 'all', anchor: todayDay};
const SORTS = {
  score: {label: 'HN score', v: (a, per) => per ? a.pk : a.k, show: (a, per) => Math.round(per ? a.pk : a.k)},
  mentions: {label: 'Most mentioned', v: (a, per) => per ? a.pm : a.m, show: (a, per) => (per ? a.pm : a.m).toLocaleString('en-US')},
  points: {label: 'Most HN points', v: (a, per) => per ? a.ph : a.h, show: (a, per) => fmt(per ? a.ph : a.h)},
  recent: {label: 'Recently mentioned', v: (a, per) => per ? a.pl : a.l, show: (a, per) => `<span class="dt">${mon(per ? a.pl : a.l)}</span>`},
  newest: {label: 'Newest on HN', v: a => a.f, show: a => `<span class="dt">${mon(a.f)}</span>`},
  rating: {label: 'Highest rated', v: a => a.r || 0, show: a => `<span class="dt">${stars(a.r)}</span>`, filter: a => a.c >= 100},
  loved: {label: 'Most loved', v: a => a.pp || 0, show: a => `<span class="dt">${moodPct('up', a.pp)}</span>`, filter: a => a.mo === 1},
};
const periodHash = () => state.mode === 'all' ? '#/' : `#/top/${state.mode}/${key(state.mode, state.anchor)}`;

function loadMeta() {                      // small files every page needs: footer date, sponsor, About numbers
  return metaP || (metaP = Promise.all([
    fetch('data/stats.json').then(r => r.ok ? r.json() : null).catch(() => null),
    fetch('data/sponsor.json').then(r => r.ok ? r.json() : null).catch(() => null),
  ]).then(([st, ad]) => {
    STATS = st; AD = ad;
    const upd = $('#upd'); if (upd && STATS) upd.textContent = `Updated every week. Last update: ${day(STATS.generated)}.`;
    if (AD && AD.contact) { $('#adline').hidden = false; $('#adlink').textContent = AD.contact; $('#adlink').href = 'mailto:' + AD.contact; }
  }));
}
function loadDB() {                        // the 2 MB app index, only for list pages
  return dbP || (dbP = fetch('data/apps.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(db => {
    DB = db; todayDay = Math.floor(db.generated * 1000 / DAY); firstDay = db.first_day;
    Y0 = db.since; NY = dUTC(todayDay).getUTCFullYear() - Y0 + 1;
    return db;
  }).catch(e => { dbP = null; throw e; }));
}

function adRow() {
  if (!AD) return '';
  const ua = navigator.userAgent, href = /iPhone|iPad|iPod/.test(ua) ? AD.ios : /Android/.test(ua) ? AD.android : AD.site;
  const parts = [AD.rating ? `${stars(AD.rating)} (${fmt(AD.ratings)})` : '', esc(AD.cat), 'iOS + Android'].filter(Boolean);
  return `<a class="row ad" href="${esc(href)}" rel="noopener sponsored" target="_blank"><span class="rank">Ad</span>${icon(AD)}
    <span class="meta"><span class="ttl">${esc(AD.name)}</span><span class="st">${esc(AD.tagline)}</span><span class="st2">${parts.map(x => `<span class="it">${x}</span>`).join(' ')}</span></span>
    <span></span><span class="num"></span></a>`;
}

function filtered() {
  const s = SORTS[state.sort], per = state.mode !== 'all';
  let list = DB.apps;
  if (per) { const [ps, pe] = range(state.mode, state.anchor); list = list.filter(a => inPeriod(a, ps, pe) > 0); }
  const total = list.length;
  if (s.filter) list = list.filter(s.filter);
  if (state.plat) list = list.filter(a => a.p & state.plat);
  if (state.mood) list = list.filter(a => a.mo === state.mood);
  if (state.cat) list = list.filter(a => a.g === state.cat);
  if (state.q) { const q = state.q.toLowerCase(); list = list.filter(a => (a.n + ' ' + (a.d || '')).toLowerCase().includes(q)); }
  const tie = (a, b) => (per ? (b.pk - a.pk) || (b.pm - a.pm) || (b.k - a.k) : (b.k - a.k) || (b.m - a.m)) || (a.s < b.s ? -1 : 1);   // same order as the RSS feed
  list = list.slice().sort((a, b) => (s.v(b, per) - s.v(a, per)) || tie(a, b));
  return {list, total};
}

const PLATS = [['All platforms', 0], ['iOS', 1], ['Android', 2]];
const MOODS = [['Any HN mood', 0], ['HN likes', 1], ['HN dislikes', -1]];
function menu(id, label, options, cur, set, extra = '') {
  return `<label class="menu${set ? ' set' : ''}${extra}"><span aria-hidden="true">${esc(label)}</span><select id="${id}" aria-label="${esc(label)}">${options.map(([l, v]) => `<option value="${esc(v)}" ${v === cur ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></label>`;
}
// ---- list updates in place: rows that stay keep their DOM and icons, rows on screen glide to their new rank ----
const keyOf = n => n.nodeType === 1 ? n.id || n.getAttribute('href') || '' : '';
const sig = n => n.nodeType === 1 ? n.nodeName + '.' + (n.getAttribute('class') || '').split(' ')[0] : n.nodeName;
function morph(a, b) {                      // make node a look like b, keeping a's identity
  if (a.nodeType !== 1) { if (a.nodeValue !== b.nodeValue) a.nodeValue = b.nodeValue; return; }
  if (a.tagName === 'IMG' && a.getAttribute('src') === b.getAttribute('src')) return;   // same icon: keep the loaded element as is
  for (const {name} of [...a.attributes]) if (!b.hasAttribute(name)) a.removeAttribute(name);
  for (const {name, value} of b.attributes) if (a.getAttribute(name) !== value) a.setAttribute(name, value);
  patch(a, b);
  if (a.tagName === 'SELECT') a.value = b.value;
}
function patch(a, b) {                      // a's children := b's, reusing a's nodes: same id/href, else the next one of the same tag and class
  const keyed = new Map();
  for (const c of a.children) { const k = keyOf(c); if (k) keyed.set(k, c); }
  let i = 0;
  for (const nb of [...b.childNodes]) {
    const k = keyOf(nb), at = a.childNodes[i];
    let na = k ? keyed.get(k) : null;
    if (!k) for (let c = at; c; c = c.nextSibling) if (!keyOf(c) && sig(c) === sig(nb)) { na = c; break; }
    if (na && sig(na) === sig(nb)) { keyed.delete(k); morph(na, nb); } else na = nb;
    if (na !== at) a.insertBefore(na, at || null);
    i++;
  }
  while (a.childNodes.length > i) a.lastChild.remove();
}
function settle() {                         // icons that aren't loaded yet fade in instead of popping
  for (const im of main.querySelectorAll('img.icon:not(.wait)')) if (!im.complete) {
    const done = () => im.classList.remove('wait');
    im.classList.add('wait'); im.addEventListener('load', done, {once: true}); im.addEventListener('error', done, {once: true});
  }
}
const vtNames = new WeakMap(), vtLift = document.head.appendChild(document.createElement('style')); let vtSeq = 0, vtGen = 0, listRev = 0;
function nameRows() {                       // only rows fully on screen, so a gliding row never crosses the sticky header (or the bar, where it sticks)
  const top = Math.max($('.top').getBoundingClientRect().bottom, main.querySelector('.bar')?.getBoundingClientRect().bottom ?? 0), rows = [...main.querySelectorAll('.list > .row')];
  const on = rows.map(r => { const b = r.getBoundingClientRect(); return b.top >= top && b.bottom <= innerHeight; });   // all reads before any write: one layout
  const names = new Set();
  rows.forEach((r, i) => {
    if (on[i]) { if (!vtNames.has(r)) vtNames.set(r, 'r' + ++vtSeq); r.style.viewTransitionName = vtNames.get(r); names.add(vtNames.get(r)); }
    else if (r.style.viewTransitionName) r.style.viewTransitionName = '';
  });
  return names;
}
function swap(html, glide, done) {
  const rev = listRev, tok = navToken;      // a newer list render or another page makes this update stale before its frame comes
  const apply = () => { if (rev !== listRev || tok !== navToken) return false; const t = document.createElement('template'); t.innerHTML = html; patch(main, t.content); settle(); done(); return true; };
  if (!glide || !document.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) return apply();
  const g = ++vtGen, before = nameRows();
  const vt = document.startViewTransition(() => {
    if (!apply()) return;
    const moving = [...nameRows()].filter(n => before.has(n));   // rows on screen before and after travel above the ones fading
    vtLift.textContent = moving.length ? moving.map(n => `::view-transition-group(${n})`).join(',') + '{z-index:1}' : '';
  });
  vt.ready.catch(() => {});                 // a newer switch skipped this one
  vt.finished.then(() => { if (g === vtGen) main.querySelectorAll('.list > .row[style]').forEach(r => r.removeAttribute('style')); });
}
const warmed = new Set(), idle = window.requestIdleCallback || (f => setTimeout(f, 200));
function warm(mode, anchor) {               // preload the top icons of a list the user is likely to open next
  if (!DB) return;
  const id = [mode, mode === 'all' ? '' : key(mode, anchor), state.sort, state.plat, state.mood, state.cat, state.q].join('|');
  if (warmed.has(id)) return; warmed.add(id);
  const keep = [state.mode, state.anchor]; state.mode = mode; state.anchor = anchor;
  try { for (const a of filtered().list.slice(0, 15)) if (a.i) new Image().src = a.i; } finally { [state.mode, state.anchor] = keep; }
}

function renderList(focusId, glide) {
  listRev++;
  const {list, total} = filtered(), shown = list.slice(0, state.limit), per = state.mode !== 'all';
  const lbl = per ? label(state.mode, state.anchor) : '';
  const heading = per ? `Top apps · ${lbl}` : 'Apps Hacker News talks about';
  const sub = per ? `${plural(total, 'app')} linked on HN in ${lbl}.`
                  : `${fmt(DB.apps.length)} iOS and Android apps linked in ${fmt(DB.listed_mentions)} HN comments and submissions since ${DB.since}.`;
  const [ps, pe] = per ? range(state.mode, state.anchor) : [0, 0];
  const stepper = per ? `<span class="period"><button class="arrow" id="prev" aria-label="Previous ${state.mode}" title="←" ${ps <= earliest(state.mode) ? 'disabled' : ''}>‹</button><button class="arrow" id="next" aria-label="Next ${state.mode}" title="→" ${pe >= limitEnd(state.mode) ? 'disabled' : ''}>›</button></span>` : '';
  const sortLabel = k => per && k === 'score' ? 'Top this ' + state.mode : SORTS[k].label;
  const showAd = AD && state.mood !== -1 && shown.length >= 10;   // a list of ten or more: the ad takes position 10
  const filteredView = state.q || state.plat || state.mood || state.cat || SORTS[state.sort].filter;
  const count = filteredView ? `<p class="count">${plural(list.length, 'app')}${state.q ? ` matching “${esc(state.q)}”` : ''}${state.sort === 'rating' ? ', each with 100+ store ratings' : ''}${state.sort === 'loved' && !state.mood ? ' HN likes' : ''}</p>` : '';
  const empty = per && !total ? `No apps were linked on HN in ${lbl}.` : 'No apps found.';
  const html = `
    <h1${per ? ' class="lb"' : ''}>${heading}${stepper}</h1><p class="sub">${sub}</p>
    <div class="bar">
      ${menu('plat', PLATS.find(x => x[1] === state.plat)[0], PLATS, state.plat, !!state.plat)}
      ${menu('mood', MOODS.find(x => x[1] === state.mood)[0], MOODS, state.mood, !!state.mood)}
      ${menu('cat', state.cat || 'All categories', [['All categories', ''], ...DB.cats.filter(c => c[0] !== 'Other').map(c => [c[0], c[0]])], state.cat || '', !!state.cat)}
      ${menu('sort', sortLabel(state.sort), Object.keys(SORTS).map(k => [sortLabel(k), k]), state.sort, false, ' sort')}
    </div>
    ${count}
    <div class="list">${shown.length ? shown.map((a, i) => row(a, i + 1, per) + (i === 8 && showAd ? adRow() : '')).join('') : `<p class="empty">${empty}</p>`}</div>
    ${list.length > state.limit ? `<button class="more" id="more">More</button>` : ''}`;
  const wire = () => {
    const pv = $('#prev'), nx = $('#next');
    if (pv) pv.onclick = () => step(-1);
    if (nx) nx.onclick = () => step(1);
    $('#plat').onchange = e => { state.plat = +e.target.value; state.limit = 60; renderList('plat', true); };
    $('#mood').onchange = e => { state.mood = +e.target.value; state.limit = 60; renderList('mood', true); };
    $('#cat').onchange = e => { state.cat = e.target.value || null; state.limit = 60; renderList('cat', true); };
    $('#sort').onchange = e => { state.sort = e.target.value; state.limit = 60; renderList('sort', true); };
    const m = $('#more');
    if (m) m.onclick = () => {
      const before = state.limit; state.limit += 60; renderList();
      const first = main.querySelectorAll('.list .row:not(.ad)')[before]; if (first) first.focus({preventScroll: true});
    };
    if (focusId && !main.contains(document.activeElement)) { const f = $('#' + focusId); if (f) f.focus({preventScroll: true}); }   // only if the update lost it
  };
  if (main.querySelector(':scope > .list')) swap(html, glide, wire);
  else { fadeIn(); main.innerHTML = html; settle(); wire(); }   // arriving from another page: fade the whole view in once
  setNav();
  if (per) idle(() => { const [s, e] = range(state.mode, state.anchor); if (s > earliest(state.mode)) warm(state.mode, s - 1); if (e < limitEnd(state.mode)) warm(state.mode, e); });
}
function step(dir) {
  const [s, e] = range(state.mode, state.anchor);
  if (dir < 0 && s <= earliest(state.mode)) return;
  if (dir > 0 && e >= limitEnd(state.mode)) return;
  state.anchor = shift(state.mode, state.anchor, dir); location.hash = periodHash();
}

function spark(a, hi) {
  const b = new Array(NY).fill(0);
  for (const d of a.t) { const i = dUTC(d).getUTCFullYear() - Y0; if (i >= 0 && i < NY) b[i]++; }
  if (b.filter(Boolean).length < 2) return '<span class="spark"></span>';   // one year of history is not a chart
  const max = Math.max(...b), W = 4, G = 1, H = 16, TW = NY * (W + G) - G;
  return `<svg class="spark" width="${TW}" height="${H}" viewBox="0 0 ${TW} ${H}" role="img" aria-label="HN mentions per year, ${Y0} to ${Y0 + NY - 1}"><rect class="ax" x="0" y="${H - .5}" width="${TW}" height=".5"/>` + b.map((v, i) => {
    if (!v) return ''; const h = +Math.max(3, Math.sqrt(v / max) * H).toFixed(1);
    return `<rect x="${i*(W+G)}" y="${(H-h).toFixed(1)}" width="${W}" height="${h}" rx=".5"${Y0+i === hi ? ' class="hi"' : ''}/>`; }).join('') + '</svg>';
}
function row(a, rank, per) {
  const mood = moodOf(a), s = SORTS[state.sort];
  const hn = [
    per ? `${plural(a.pm, 'mention')} this ${state.mode}` : `${plural(a.m, 'mention')} by ${plural(a.u, 'HNer')}`,
    per ? `${a.m.toLocaleString('en-US')} all time` : '',
    (per ? a.px : a.x) ? '<span class="hn">Show HN</span>' : '',
  ].filter(Boolean);
  const store = [a.r ? stars(a.r) : '', a.g !== 'Other' ? esc(a.g) : '', [a.p & 1 ? 'iOS' : '', a.p & 2 ? 'Android' : ''].filter(Boolean).join(' + ')].filter(Boolean);
  const moodLine = mood && state.sort !== 'loved' ? moodPct(mood, mood === 'up' ? a.pp : a.pq) : '';
  if (moodLine) hn.push(moodLine);
  const hi = per ? dUTC(range(state.mode, state.anchor)[0]).getUTCFullYear() : 0;
  return `<a class="row" href="#/app/${a.s}"><span class="rank">${rank}</span>${icon(a, rank > 12)}
    <span class="meta"><span class="ttl">${esc(a.n)}</span><span class="st">${hn.map(x => `<span class="it">${x}</span>`).join(' ')}</span><span class="st2">${store.map(x => `<span class="it">${x}</span>`).join(' ')}</span></span>
    ${spark(a, hi)}<span class="num"><b>${s.show(a, per)}</b>${moodLine}</span></a>`;
}

function setNav(k) {
  if (k === undefined) k = state.mode !== 'all' ? state.mode : '';
  document.querySelectorAll('#nav a[data-nav]').forEach(a => {
    const on = a.dataset.nav === k; a.classList.toggle('on', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
}
function fadeIn() { main.className = 'wrap view'; main.style.animation = 'none'; void main.offsetWidth; main.style.animation = ''; }

function notFound(msg = 'There is no app at this address. It may have been renamed, or merged with its listing on the other store.') {
  document.title = 'Not found · HN Apps'; fadeIn();
  main.innerHTML = `<a class="back" href="${esc(lastListHash)}">‹ Back</a><h1>App not found</h1><p class="sub">${esc(msg)}</p><p><a class="lnk" href="#/">See all apps</a></p>`;
}
async function renderApp(raw, token) {
  let slug = null;
  try { slug = decodeURIComponent(raw); } catch { slug = null; }
  if (!slug || !/^[a-z0-9-]{1,80}$/.test(slug)) return notFound();
  main.innerHTML = '<p class="empty">Loading…</p>';
  let a;
  try { const r = await fetch(`data/app/${slug}.json`); if (!r.ok) throw new Error(r.status); a = await r.json(); }
  catch { if (token === navToken) notFound(); return; }
  if (token !== navToken) return;
  const shots = (a.ios?.screens?.length ? a.ios.screens : a.android?.screens) || [];
  const desc = a.ios?.desc || a.android?.desc || '';
  const store = a.ios || a.android || {};
  const rate = [a.ios, a.android].filter(b => b && b.rating).map(b => `<span>${stars(b.rating)} (${fmt(b.ratings)} on ${b === a.ios ? 'App Store' : 'Google Play'})</span>`).join('');
  const price = [a.ios?.price, a.android?.price].filter(Boolean).filter((v, i, s) => s.indexOf(v) === i).join(' / ');
  const y1 = new Date(a.first * 1000).getFullYear(), y2 = new Date(a.last * 1000).getFullYear();
  const facts = [plural(a.threads, 'thread'),
    a.submissions ? `${fmt(a.hn_points)} points and ${fmt(a.hn_comments)} comments on ${plural(a.submissions, 'submission')}` : '',
    a.self_n ? `${plural(a.self_n, 'post')} by the developer` : '',
    a.n_lab ? `mood from ${plural(a.n_lab, 'mention')} by others` : '',
    y1 === y2 && mon(a.first) === mon(a.last) ? `seen ${mon(a.first)}` : `first seen ${mon(a.first)}, last ${mon(a.last)}`].filter(Boolean);
  document.title = `${a.name} · HN Apps`; fadeIn();
  main.innerHTML = `
    <a class="back" href="${esc(lastListHash)}">‹ Back</a>
    <div class="hero">${icon(a)}
      <div class="hmeta"><h1>${esc(a.name)}</h1><span class="dev">${esc(a.dev || '')}</span>
        <div class="hfacts">${rate}${store.genre ? `<span>${esc(store.genre)}</span>` : ''}${price ? `<span>${esc(price)}</span>` : ''}${a.android?.installs ? `<span>${esc(a.android.installs)} installs</span>` : ''}</div>
        <div class="get">${a.ios ? `<a class="btn" href="${esc(a.ios.url)}" rel="noopener" target="_blank">App Store</a>` : ''}${a.android ? `<a class="btn ${a.ios ? 'alt' : ''}" href="${esc(a.android.url)}" rel="noopener" target="_blank">Google Play</a>` : ''}</div>
      </div></div>
    <div class="strip">
      <div class="stat"><span>HN score</span><b class="k">${Math.round(a.hn_score)}</b></div>
      <div class="stat"><span>Mentions</span><b>${a.mentions.toLocaleString('en-US')}</b></div>
      <div class="stat"><span>HNers</span><b>${a.users.toLocaleString('en-US')}</b></div>
      <div class="stat"><span>${a.mood === 'down' ? 'Negative' : a.mood === 'up' ? 'Positive' : 'HN mood'}</span><b class="${a.mood ? 'grad ' + a.mood : ''}">${a.mood ? moodPct(a.mood, a.mood === 'down' ? a.neg_pct : a.pos_pct) : '–'}</b></div>
      <div class="stat"><span>Show HN</span><b>${a.show_hn ? `<a href="https://news.ycombinator.com/item?id=${a.show_hn.id}" rel="noopener" target="_blank">${a.show_hn.points} pts</a>` : '–'}</b></div>
      <div class="stat"><span>On HN</span><b>${y1}${y1 !== y2 ? '–' + String(y2).slice(2) : ''}</b></div>
    </div>
    <p class="facts">${facts.join(' · ')}.</p>
    <h2>On Hacker News<small>best threads first</small></h2>
    ${a.quotes.map(quote).join('')}
    ${shots.length ? `<h2>Screenshots</h2><div class="shots">${shots.map(u => `<img loading="lazy" src="${esc(u)}" alt="Screenshot of ${esc(a.name)}">`).join('')}</div>` : ''}
    ${desc ? `<h2>About</h2><div class="desc" id="desc">${esc(desc)}</div><button class="lnk" id="descmore">Read more</button>` : ''}`;
  const d = $('#desc'), dm = $('#descmore');
  if (dm) {
    if (d.scrollHeight <= d.clientHeight + 4) { dm.remove(); d.classList.add('open'); }
    else { d.classList.add('clip'); dm.onclick = () => { d.classList.toggle('open'); dm.textContent = d.classList.contains('open') ? 'Show less' : 'Read more'; }; }
  }
  main.querySelectorAll('.txt').forEach(t => { if (t.scrollHeight > t.clientHeight + 4) { const b = document.createElement('button'); b.className = 'lnk'; b.textContent = 'Read more'; b.onclick = () => { t.classList.add('open'); b.remove(); }; t.after(b); } });
  window.scrollTo(0, 0);
}

function quote(q) {
  const item = `https://news.ycombinator.com/item?id=${q.id}`, isStory = q.type !== 'comment';
  const body = isStory ? `<b>${esc(q.title || '')}</b>${q.text ? '\n' + linkify(q.text) : ''}` : linkify(q.text);
  const tag = q.self ? '<span class="tagq">developer</span>' : q.s === 'pos' ? moodWord('up') : q.s === 'neg' ? moodWord('down') : '';
  return `<div class="quote">
    <div class="who"><a href="https://news.ycombinator.com/user?id=${encodeURIComponent(q.by || '')}" rel="noopener" target="_blank">${esc(q.by || '[deleted]')}</a>${tag}<span>${day(q.time)}</span>${isStory && q.story_score ? `<span class="pts">${plural(q.story_score, 'point')}</span>` : ''}<a class="open" href="${item}" rel="noopener" target="_blank">on HN ↗</a></div>
    <div class="txt">${body || '<i>(no text)</i>'}</div>
    ${!isStory && q.story_title ? `<div class="thr">in <a href="https://news.ycombinator.com/item?id=${q.story_id}" rel="noopener" target="_blank">${esc(q.story_title)}</a>${q.story_score ? ` · ${plural(q.story_score, 'point')}` : ''}</div>` : ''}
  </div>`;
}

async function renderAbout(token) {
  document.title = 'About · HN Apps';
  await loadMeta();
  if (token !== navToken) return;
  const S = STATS || {}, since = S.list_since || S.since || 2009;
  const all = S.total_mentions ? fmt(S.total_mentions) : 'all', listed = S.listed_mentions ? fmt(S.listed_mentions) : 'most';
  fadeIn();
  main.innerHTML = `<div class="about">
    <h1>About</h1>
    <p>HN Apps is an app store you can only get into by being linked on Hacker News. It has every iOS and Android app anyone has linked in an HN comment or submission since ${since}, ranked by how much HN talked about it.</p>
    <h2>How it works</h2>
    <p>A script goes through every HN comment and story looking for App Store and Google Play links, then looks each one up on the store. When the iOS and Android listings come from the same developer and have matching names, or are linked together in the same HN post and their names or developer match, they become one entry. Apps that are no longer on either store are left out of the lists.</p>
    <h2>The score</h2>
    <p>Each mention adds to an app's score:</p>
    <ul class="rules">
      <li><b>A comment linking the app:</b> 1.</li>
      <li><b>A submission linking the app</b> (a Show HN, for example): 1 + log<sub>2</sub>(points + 1) + log<sub>2</sub>(comments + 1). A 100-point post with 50 comments adds about 13. A 2-point post with no comments adds about 2.6.</li>
      <li><b>Each different HNer</b> who mentioned the app: 1.</li>
      <li><b>The developer's own posts</b> add only what other people gave them: the log of their points and comments. A developer mentioning their app in twenty threads earns nothing for it.</li>
    </ul>
    <p>The logs are there so one viral launch can't beat an app that thirty people bring up on their own. A big thread still counts for more than a quiet one. Comment upvotes aren't public, so they don't count. The week, month and year lists use the same rules, counting only mentions from that period.</p>
    <p>For example, say an app was linked in 12 comments by 9 different people, and in one Show HN by someone else that got 40 points and 12 comments. Its score is 12 + (1 + 5.4 + 3.7) + 10 ≈ 32.</p>
    <p>The other sorts are simpler. Most mentioned counts mentions. Most HN points adds up the points of submissions that linked straight to the app. Highest rated uses store ratings, for apps with at least 100 of them. Most loved ranks the apps HN likes by their share of positive mentions. The Show HN tag means a launch post linked straight to the store.</p>
    <p>A mention isn't a recommendation. Some links are complaints, and some are developers posting their own app. Read the thread before you judge.</p>
    <h2>HN mood</h2>
    <p>Every mention of a listed app is labeled positive, neutral or negative toward the app by a language model, and posts by the app's own developer are marked and left out. An app gets a thumb when at least three people other than the developer take a side and the mentions lean clearly one way: the positive ones outnumber the negative ones by at least 40% of all labeled mentions, or the other way round. The labels are automatic and will be wrong sometimes, so the thread is always one click away.</p>
    <h2>Updates</h2>
    <p>The data is rebuilt every week from the latest HN comments and submissions, so new launches show up within days. Follow along with the <a href="feed.xml">weekly RSS feed</a>.</p>
    <h2>Sponsorship</h2>
    <p>One row in lists of ten or more apps is a paid slot, marked Ad, so the rankings stay honest.${AD && AD.contact ? ` To book it, email <a href="mailto:${esc(AD.contact)}">${esc(AD.contact)}</a>.` : ''}</p>
    <h2>Data</h2>
    <p>HN data comes from the public HN dump and the <a href="https://hn.algolia.com/api" rel="noopener">Algolia HN API</a>. Store details come from the iTunes Lookup API and Google Play. All ${all} mentions are in <a href="data/mentions.jsonl.gz">data/mentions.jsonl.gz</a> (CC BY 4.0, schema in <a href="data/DATA.md">DATA.md</a>). ${listed} of them point to apps still on a store, and those carry sentiment labels and make up the lists. Per-app files are in <code>data/app/*.json</code>.</p>
    <p>Keyboard: <kbd>/</kbd> to search, <kbd>←</kbd> <kbd>→</kbd> to step through weeks, months or years.</p>
    <h2>Source</h2>
    <p>The code is on <a href="https://github.com/vladimirsvsv77/HN-Apps" rel="noopener">GitHub</a>. Found a bug or have an idea? Open an <a href="https://github.com/vladimirsvsv77/HN-Apps/issues" rel="noopener">issue</a> or a <a href="https://github.com/vladimirsvsv77/HN-Apps/pulls" rel="noopener">pull request</a>.</p>
    <p>Inspired by <a href="https://hackertube.org" rel="noopener">HackerTube</a> and <a href="https://hackerbooks.org" rel="noopener">HackerBooks</a>.</p>
  </div>`;
  window.scrollTo(0, 0);
}

async function route() {
  const token = ++navToken, h = location.hash || '#/', prevKind = routeKind;
  if (prevKind === 'list') savedScroll[lastListHash] = window.scrollY;
  if (window.leaveInsights && !h.startsWith('#/insights')) window.leaveInsights();
  const m = h.match(/^#\/app\/(.*)$/);
  if (m) { routeKind = 'app'; setNav('none'); return renderApp(m[1], token); }
  if (/^#\/about\/?$/.test(h)) { routeKind = 'about'; setNav('about'); return renderAbout(token); }
  if (/^#\/insights\/?$/.test(h)) {
    routeKind = 'insights'; setNav('insights'); document.title = 'Insights · HN Apps'; fadeIn();
    main.innerHTML = '<h1>Insights</h1><p class="sub">Loading…</p>';
    return window.renderInsights(main, () => token === navToken);
  }
  routeKind = 'list';
  const top = h.match(/^#\/top\/(year|month|week)(?:\/([^/]*))?\/?$/);
  if (!top && h !== '#/' && h !== '#' && h !== '') history.replaceState(null, '', '#/');
  if (!DB) main.innerHTML = '<h1>Apps Hacker News talks about</h1><p class="sub">Loading…</p>' + '<div class="skel"><i class="a"></i><span style="flex:1"><i class="b"></i><i class="c"></i></span></div>'.repeat(8);
  try { await Promise.all([loadDB(), loadMeta()]); }
  catch { if (token === navToken) { main.innerHTML = '<h1>Apps Hacker News talks about</h1><p class="sub">The app list didn\'t load. Check your connection and <a href="" class="lnk" id="retry">try again</a>.</p>'; $('#retry').onclick = e => { e.preventDefault(); route(); }; } return; }
  if (token !== navToken) return;
  if (top) {
    state.mode = top[1];
    state.anchor = clamp(top[1], parseKey(top[1], top[2]) ?? latest(top[1]));
    const canon = periodHash(); if (location.hash !== canon) history.replaceState(null, '', canon);
  } else state.mode = 'all';
  lastListHash = location.hash || '#/';
  document.title = 'HN Apps · Apps Hacker News talks about';
  renderList(null, true);
  window.scrollTo({top: prevKind === 'app' && savedScroll[lastListHash] != null ? savedScroll[lastListHash] : prevKind === 'list' ? window.scrollY : 0, behavior: 'instant'});
}

let qt; $('#q').addEventListener('input', e => {
  clearTimeout(qt);
  qt = setTimeout(() => { state.q = e.target.value.trim(); state.limit = 60; if (routeKind !== 'list') location.hash = '#/'; else if (DB) renderList(); else route(); }, 120);
});
window.addEventListener('hashchange', route);
$('#nav').addEventListener('pointerover', e => { const k = e.target.closest('a')?.dataset.nav; if (k === '') warm('all', 0); else if (k === 'week' || k === 'month' || k === 'year') warm(k, latest(k)); });
document.addEventListener('keydown', e => {
  if (e.altKey || e.ctrlKey || e.metaKey) return;
  const typing = /input|select|textarea/i.test(e.target.tagName);
  if (e.key === '/' && !typing) { e.preventDefault(); $('#q').focus(); return; }
  if (e.key === 'Escape' && e.target === $('#q')) { $('#q').value = ''; state.q = ''; $('#q').blur(); if (routeKind === 'list' && DB) renderList(); return; }
  if (!typing && !e.shiftKey && routeKind === 'list' && state.mode !== 'all' && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) step(e.key === 'ArrowRight' ? 1 : -1);
});
loadMeta();
route();
})();
