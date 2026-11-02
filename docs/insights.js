// Insights page: charts built with Chart.js, following one-axis / thin-mark / legend rules.
(() => {
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => n == null ? '' : Math.abs(n) >= 1e6 ? (n/1e6).toFixed(1).replace(/\.0$/,'')+'M' : Math.abs(n) >= 1e4 ? (n/1e3).toFixed(1).replace(/\.0$/,'')+'K' : Number.isInteger(n) ? n.toLocaleString('en-US') : String(n);
const pct = (a, b) => b ? Math.round((a / b - 1) * 100) : 0;
const p100 = r => Math.round(r * 100);
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const MONTHS_LONG = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const DAYS_LONG = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
const HOURS = Array.from({length: 25}, (_, h) => h === 24 || h === 0 ? 'midnight' : h === 12 ? 'noon' : `${h % 12}${h < 12 ? 'am' : 'pm'}`);
const HOURS_AX = Array.from({length: 24}, (_, h) => `${h % 12 || 12}${h < 12 ? 'am' : 'pm'}`);
const METRIC = {hit10: 'Reached 10+ points', mean: 'Avg points', median: 'Median points', n: 'Launches'};
const pfmt = p => p < 0.001 ? 'p < 0.001' : `p = ${p < 0.01 ? p.toFixed(3) : p.toFixed(2)}`;
const sub = (G, best, rest) => G ? (G.p < 0.05 ? `${best}: ${Math.round(G.best_hits / G.best_n * 100)}% of launches reached 10 points, vs ${Math.round(G.rest_hits / G.rest_n * 100)}% ${rest} (${pfmt(G.p)}).` : `${best} looks best, ${Math.round(G.best_hits / G.best_n * 100)}% vs ${Math.round(G.rest_hits / G.rest_n * 100)}% reaching 10 points, but that's within chance (${pfmt(G.p)}).`) : '';
let S = null, chartjs = null, charts = [];

const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const theme = () => ({ series: [1,2,3,4,5,6,7,8].map(i => cssv(`--c${i}`)), gray: cssv('--cgray'), grid: cssv('--grid'), axis: cssv('--axis'), muted: cssv('--muted'),
  ink: cssv('--fg'), ink2: cssv('--gray'), surface: cssv('--panel') });
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

function loadChartJs() {
  if (window.Chart) return Promise.resolve(window.Chart);
  return chartjs || (chartjs = new Promise((res, rej) => {
    const s = document.createElement('script'); s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js';
    s.onload = () => res(window.Chart); s.onerror = () => { chartjs = null; s.remove(); rej(new Error('chart.js')); }; document.head.appendChild(s);
  }));
}
function loadStats() {
  if (S) return Promise.resolve(S);
  return fetch('data/stats.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(s => (S = s));
}

// crosshair for line charts: a hairline that snaps to the hovered x
const crosshair = { id: 'crosshair', afterDatasetsDraw(c) {
  const a = c.tooltip?.getActiveElements?.(); if (!a || !a.length || c.config.type !== 'line') return;
  const x = a[0].element.x, {ctx, chartArea: {top, bottom}} = c; ctx.save(); ctx.strokeStyle = theme().axis; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke(); ctx.restore(); } };
// vertical markers with a label (product releases etc.)
const marks = { id: 'marks', afterDatasetsDraw(c) {
  const ms = c.options.plugins.marks; if (!ms || !ms.length) return;
  const t = theme(), {ctx, chartArea: {top, bottom, left, right}} = c, xs = c.scales.x; ctx.save();
  ctx.font = '600 12px -apple-system, system-ui, sans-serif'; ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
  ms.forEach((m, i) => {
    if (m.index < 0) return;
    const x = xs.getPixelForValue(m.index), y = top + i * 20, w = ctx.measureText(m.label).width + 14, h = 17;
    ctx.strokeStyle = t.ink2; ctx.lineWidth = 1; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke(); ctx.setLineDash([]);
    const cx = Math.min(Math.max(x, left + w / 2), right - w / 2);   // keep the chip inside the plot
    ctx.fillStyle = t.surface; ctx.strokeStyle = t.axis; ctx.beginPath(); ctx.roundRect(cx - w / 2, y, w, h, 6); ctx.fill(); ctx.stroke();
    ctx.fillStyle = t.ink; ctx.fillText(m.label, cx, y + h / 2 + .5);
  });
  ctx.restore(); } };

const vfmt = (v, percent) => v == null ? '' : percent ? (+v).toFixed(1) + '%' : fmt(Math.round(v * 10) / 10);
function baseOptions(t, {percent = false, horizontal = false, stacked = false} = {}) {
  const val = { grid: {color: t.grid, drawTicks: false}, border: {display: false}, ticks: {color: t.muted, font: {size: 12}, callback: v => percent ? v + '%' : fmt(v), maxTicksLimit: 6, padding: 6}, stacked, beginAtZero: true, max: percent && stacked ? 100 : undefined };
  const cat = { grid: {display: false}, border: {display: false}, ticks: {color: t.muted, font: {size: 12}, maxRotation: 0, autoSkipPadding: 12}, stacked };
  return { responsive: true, maintainAspectRatio: false, animation: reduced() ? false : {duration: 380, easing: 'easeOutQuart'},
    interaction: {mode: 'index', intersect: false, axis: horizontal ? 'y' : 'x'}, indexAxis: horizontal ? 'y' : 'x',
    layout: {padding: {top: 8, right: 8}}, scales: horizontal ? {x: val, y: cat} : {x: cat, y: val},
    plugins: { legend: {display: false}, tooltip: {
      backgroundColor: t.surface, titleColor: t.ink, bodyColor: t.ink, borderColor: t.grid, borderWidth: 1, cornerRadius: 10, padding: 10, boxWidth: 10, boxHeight: 2, boxPadding: 6,
      titleFont: {weight: '600', size: 13}, bodyFont: {size: 13}, usePointStyle: false,
      callbacks: { label: ctx => { const v = ctx.parsed[horizontal ? 'x' : 'y']; const extra = ctx.dataset.extra?.[ctx.dataIndex]; return ` ${vfmt(v, percent)}  ${ctx.dataset.label}${extra ? ' · ' + extra : ''}`; } } } },
    _percent: percent };
}
const barStyle = (color, {top = true, horizontal = false, gapTop = false, surface} = {}) => ({ backgroundColor: color, maxBarThickness: 24, barPercentage: 0.72, categoryPercentage: 0.8,
  borderRadius: top ? (horizontal ? {topRight: 4, bottomRight: 4} : {topLeft: 4, topRight: 4}) : 0, borderSkipped: horizontal ? 'left' : 'bottom',
  ...(gapTop ? {borderColor: surface, borderWidth: horizontal ? {right: 2} : {top: 2}} : {}) });

function card(id, title, sub, {controls = '', height = 280} = {}) {
  return `<section class="card" id="${id}" aria-labelledby="${id}-t"><div class="card-h"><div><h3 id="${id}-t">${title}</h3><p>${sub}</p></div>${controls ? `<div class="toggles">${controls}</div>` : ''}</div>
    <div class="plot" style="height:${height}px"><canvas role="img"></canvas></div><div class="legend"></div></section>`;
}
function seg(name, label, opts, cur) {
  return `<div class="seg small" role="group" aria-label="${esc(label)}" data-toggle="${name}">${opts.map(k => `<button data-v="${k}" class="${k === cur ? 'on' : ''}" aria-pressed="${k === cur}">${METRIC[k] || k}</button>`).join('')}</div>`;
}
function toggles(el, render, first) {
  el.querySelectorAll('[data-v]').forEach(b => b.onclick = () => {
    el.querySelectorAll('[data-v]').forEach(x => { const on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-pressed', on); });
    render(b.dataset.v);
  });
  render(first);
}

function draw(el, type, labels, datasets, opts, {keys = 'rect'} = {}) {
  const canvas = el.querySelector('canvas'), old = charts.find(c => c.canvas === canvas);
  if (old) { old.destroy(); charts = charts.filter(c => c !== old); }
  canvas.setAttribute('aria-label', `${el.querySelector('h3').textContent}. ${datasets.map(d => d.label).join(', ')}.`);
  charts.push(new Chart(canvas, {type, data: {labels, datasets}, options: opts, plugins: [crosshair, marks]}));
  const lg = el.querySelector('.legend'); lg.innerHTML = '';
  if (datasets.length > 1) datasets.forEach(d => { const i = document.createElement('span'), k = document.createElement('i'); k.className = keys; k.style.background = type === 'line' ? d.borderColor : (Array.isArray(d.backgroundColor) ? d.backgroundColor[0] : d.backgroundColor); i.appendChild(k); i.appendChild(document.createTextNode(d.label)); lg.appendChild(i); });
}
function tile(label, value, delta, vs, upGood = true, unit = '%') {
  const cls = delta == null ? '' : (delta >= 0) === upGood ? 'good' : 'bad';
  return `<div class="tile"><span>${label}</span><b>${value}</b>${delta == null ? '' : `<em class="${cls}">${delta > 0 ? '+' : ''}${delta}${unit} <small>vs ${vs}</small></em>`}</div>`;
}

window.leaveInsights = () => { charts.forEach(c => c.destroy()); charts = []; };
window.renderInsights = async function(main, alive = () => true) {
  try { await Promise.all([loadStats(), loadChartJs()]); }
  catch {
    if (!alive()) return;
    main.innerHTML = `<h1>Insights</h1><p class="sub">The charts didn't load. Check your connection and <a href="" class="lnk" id="iretry">try again</a>.</p>`;
    document.getElementById('iretry').onclick = e => { e.preventDefault(); window.renderInsights(main, alive); };
    return;
  }
  if (!alive()) return;
  window.leaveInsights();
  const Y = S.years, n = Y.length, cur = S.partial_year, li = Y.indexOf(cur - 1), pi = li - 1, l3 = Math.max(0, li - 3);
  const yix = y => Math.max(0, Y.indexOf(Math.max(y, Y[0])));
  const tot = Y.map((_, i) => S.mentions.submissions[i] + S.mentions.comments[i]);
  const sh = S.show_hn, ai = S.ai_first_seen.map((v, i) => S.first_seen[i] ? v / S.first_seen[i] * 100 : 0);
  const prevPeak = Math.max(...tot.slice(0, n - 1)), peakYear = Y[tot.indexOf(prevPeak)];
  const monthName = MONTHS_LONG[new Date(S.generated * 1000).getUTCMonth()];
  const h1 = tot[n-1] > prevPeak ? `${cur} is already the busiest year for app mentions on HN` : peakYear === Y[li] ? `${Y[li]} was the busiest year yet for app mentions on HN` : `App mentions peaked in ${peakYear}, and ${Y[li]} was ${Math.abs(pct(tot[li], prevPeak))}% lower`;
  const s1 = tot[n-1] > prevPeak ? `${fmt(tot[n-1])} mentions by ${monthName}, already past the ${peakYear} record of ${fmt(prevPeak)}.` : `${fmt(tot[li])} mentions in ${Y[li]}.`;
  const win = sh.best_window;
  const cp = [...S.category_points].sort((a, b) => b.hit10 - a.hit10), topC = cp[0], lowC = cp[cp.length - 1];
  const catShare = yr => S.categories.map(c => { const s = S.categories.reduce((a, d) => a + d.values[yr], 0); return s ? c.values[yr] / s * 100 : 0; });
  const base = yix(2013), gain = S.categories.map((c, k) => ({name: c.name, d: catShare(li)[k] - catShare(base)[k]})).filter(c => c.name !== 'Other').sort((a, b) => b.d - a.d);
  const iosShare = i => (S.platform.ios[i] + S.platform.android[i]) ? S.platform.ios[i] / (S.platform.ios[i] + S.platform.android[i]) * 100 : 0;
  const mo = sh.monthly, iGPT = mo.months.indexOf('2022-11'), iCC = mo.months.indexOf('2025-02');
  const avg = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
  const preGPT = avg(mo.launches.slice(Math.max(0, iGPT - 12), iGPT)), last12 = avg(mo.launches.slice(-12));
  const launchX = sh.by_year[li].n && sh.by_year[l3].n ? (sh.by_year[li].n / sh.by_year[l3].n).toFixed(1) : null;
  const SG = S.significance || {};
  const pr = sh.by_year[l3].mean ? sh.by_year[li].mean / sh.by_year[l3].mean : 1, ptsWord = pr < 0.9 ? 'fewer points' : pr > 1.1 ? 'more points' : 'about the same points';

  main.className = 'wrap view';
  main.innerHTML = `
    <h1>Insights</h1>
    <p class="sub">What ${fmt(S.total_mentions)} app mentions and ${sh.total.toLocaleString('en-US')} Show HN app launches since ${S.since} say about launching an app on Hacker News. All times are US Eastern.</p>
    <div class="tiles">
      ${tile(`App mentions, ${Y[li]}`, fmt(tot[li]), pct(tot[li], tot[pi]), Y[pi])}
      ${tile(`Show HN app launches, ${Y[li]}`, fmt(sh.by_year[li].n), pct(sh.by_year[li].n, sh.by_year[pi].n), Y[pi])}
      ${tile(`Avg points per launch, ${Y[li]}`, sh.by_year[li].mean, pct(sh.by_year[li].mean, sh.by_year[pi].mean), Y[pi])}
      ${tile(`New apps with “AI” in the name, ${Y[li]}`, ai[li].toFixed(0) + '%', +(ai[li] - ai[pi]).toFixed(1), Y[pi], true, ' pts')}
    </div>
    ${card('c-monthly', `${(last12 / preGPT).toFixed(1)}× as many launches as before ChatGPT`, `Show HN app launches per month: ${Math.round(preGPT)} a month in the year before ChatGPT, ${Math.round(last12)} a month over the last 12. Complete months only.`, {height: 260})}
    ${card('c-ai', `${ai[li].toFixed(0)}% of apps first linked in ${Y[li]} have “AI” in the name`, `${ai[li] >= ai[l3] ? 'Up' : 'Down'} from ${ai[l3].toFixed(0)}% in ${Y[l3]}. Apps are grouped by the year they were first linked on HN.`, {height: 220})}
    ${card('c-launch', launchX ? `Launches are ${launchX >= 1 ? `up ${launchX}×` : `down to ${launchX}×`} since ${Y[l3]}, and each one gets ${ptsWord}` : 'Show HN launches by year', `Show HN posts that link to an app. Average points per launch: ${sh.by_year[li].mean} in ${Y[li]}, ${sh.by_year[l3].mean} in ${Y[l3]}.`, {height: 220})}
    ${card('c-launch-pts', 'Average points per Show HN launch', 'Mean points by launch year. Tooltips show the median and the share that reached 10 points.', {height: 220})}
    ${card('c-cats', `${gain[0].name} gained the most share since ${Y[base]}`, `Share of mentions by store category. ${gain[0].name} +${gain[0].d.toFixed(0)} points, ${gain[gain.length-1].name} ${gain[gain.length-1].d > 0 ? '+' : ''}${gain[gain.length-1].d.toFixed(0)}. Only apps still on a store.`, {controls: seg('cs', 'Show as', ['Share', 'Count'], 'Share'), height: 300})}
    ${card('c-cat-pts', SG.category && SG.category.p < 0.05 ? `${cp.find((c, k) => S.category_points.indexOf(c) === SG.category.best)?.name || topC.name} launches reach 10 points most often` : 'No category clearly does better', sub(SG.category, S.category_points[SG.category?.best]?.name, 'in other categories'), {controls: seg('c', 'Metric', ['hit10', 'mean', 'median'], 'hit10'), height: 30 * cp.length + 40})}
    ${card('c-mentions', h1, s1 + ` Comments and submissions that link to an App Store or Google Play page. ${cur} is year to date.`)}
    ${((G) => card('c-month', G && G.p < 0.05 ? `${MONTHS_LONG[G.best]} launches reach 10 points most often` : 'Launch month barely matters', sub(G, MONTHS_LONG[G?.best], 'in other months'), {controls: seg('m', 'Metric', ['hit10', 'mean', 'n'], 'hit10'), height: 240}))(SG.month)}
    ${((G) => card('c-wday', G && G.p < 0.05 ? `${DAYS_LONG[G.best]} launches do a little better` : 'Launch day barely matters', sub(G, DAYS_LONG[G?.best], 'on other days'), {controls: seg('d', 'Metric', ['hit10', 'mean', 'n'], 'hit10'), height: 240}))(SG.weekday)}
    ${((G) => card('c-hour', G && G.p < 0.05 ? `Launches at ${HOURS[G.best]} Eastern do a little better` : 'Launch hour barely matters', sub(G, `${HOURS[G?.best]} Eastern`, 'at other hours'), {controls: seg('h', 'Metric', ['hit10', 'mean', 'n'], 'hit10'), height: 240}))(SG.hour)}
    ${card('c-plat', `iOS is ${iosShare(li).toFixed(0)}% of app links in ${Y[li]}`, `Share of store links by platform. It was ${iosShare(yix(2015)).toFixed(0)}% in ${Y[yix(2015)]}.`, {height: 220})}
    <p class="note">A mention is a link to an App Store or Google Play page in an HN comment or submission, going back to ${S.since}. Points are the submission's HN score. Comment upvotes aren't public, so they aren't counted. p is a chi-square test across all groups. Under 0.05 means the gap is unlikely to be chance.</p>`;

  const yl = Y.map(y => y === cur ? `${y}*` : String(y)), T = theme();
  { const o = baseOptions(T); o.scales.x.ticks.callback = (v, i) => mo.months[i].endsWith('-01') ? mo.months[i].slice(0, 4) : ''; o.scales.x.ticks.autoSkip = false; o.scales.x.ticks.maxTicksLimit = 40;
    o.plugins.marks = [{index: iGPT, label: 'ChatGPT'}, {index: iCC, label: 'Claude Code'}]; o.layout.padding.top = 48; o.layout.padding.right = 44;
    o.plugins.tooltip.callbacks.title = items => { const [y, m] = mo.months[items[0].dataIndex].split('-'); return `${MONTHS_LONG[+m - 1]} ${y}`; };
    draw(document.getElementById('c-monthly'), 'line', mo.months.map(m => { const [y, mm] = m.split('-'); return `${MONTHS[+mm - 1]} ${y}`; }), [{label: 'Launches', data: mo.launches, borderColor: T.series[0], backgroundColor: T.series[0] + '1a', fill: true, borderWidth: 2, tension: 0.25, pointRadius: 0, pointHoverRadius: 5, pointBackgroundColor: T.series[0], pointBorderColor: T.surface, pointBorderWidth: 2}], o); }
  draw(document.getElementById('c-mentions'), 'bar', yl, [
    {label: 'Submissions', data: S.mentions.submissions, ...barStyle(T.series[0], {top: false})},
    {label: 'Comments', data: S.mentions.comments, ...barStyle(T.series[1], {gapTop: true, surface: T.surface})},
  ], baseOptions(T, {stacked: true}));
  draw(document.getElementById('c-launch'), 'bar', yl, [{label: 'Launches', data: sh.by_year.map(b => b.n), ...barStyle(T.series[0])}], baseOptions(T));
  draw(document.getElementById('c-launch-pts'), 'bar', yl, [{label: 'Avg points', data: sh.by_year.map(b => b.mean), extra: sh.by_year.map(b => `median ${b.median}, ${p100(b.hit10)}% reached 10+, n=${b.n}`), ...barStyle(T.series[0])}], baseOptions(T));
  const timing = (id, labels, rows, dim) => {
    const el = document.getElementById(id);
    toggles(el, metric => {
      const vals = rows.map(b => metric === 'hit10' ? b.hit10 * 100 : b[metric]);
      const colors = rows.map(b => dim && b.n < 120 ? T.gray : T.series[0]);
      draw(el, 'bar', labels, [{label: METRIC[metric], data: vals, extra: rows.map(b => `n=${b.n}, median ${b.median}`), ...barStyle(colors)}], baseOptions(T, {percent: metric === 'hit10'}));
    }, 'hit10');
  };
  timing('c-month', MONTHS, sh.by_month); timing('c-wday', DAYS, sh.by_weekday); timing('c-hour', HOURS_AX, sh.by_hour, true);
  { const el = document.getElementById('c-cat-pts');
    toggles(el, metric => { const rows = [...cp].sort((a, b) => b[metric] - a[metric]);
      draw(el, 'bar', rows.map(r => r.name), [{label: METRIC[metric], data: rows.map(r => metric === 'hit10' ? r.hit10 * 100 : r[metric]), extra: rows.map(r => `n=${r.n}`), ...barStyle(T.series[0], {horizontal: true})}], baseOptions(T, {horizontal: true, percent: metric === 'hit10'})); }, 'hit10'); }
  { const el = document.getElementById('c-cats'), from = yix(2012);
    toggles(el, mode => {
      const ds = S.categories.map((c, k) => { const last = k === S.categories.length - 1; const data = Y.slice(from).map((_, j) => { const i = from + j; return mode === 'Share' ? catShare(i)[k] : c.values[i]; });
        return {label: c.name, data, ...barStyle(c.name === 'Other' ? T.gray : T.series[k], {top: last, gapTop: k > 0, surface: T.surface})}; });
      draw(el, 'bar', yl.slice(from), ds, baseOptions(T, {stacked: true, percent: mode === 'Share'})); }, 'Share'); }
  { const from = yix(2015); draw(document.getElementById('c-ai'), 'line', yl.slice(from), [{label: 'Apps with “AI” in the name', data: ai.slice(from).map(v => Math.round(v * 10) / 10), extra: S.ai_first_seen.slice(from).map((v, j) => `${v} of ${S.first_seen[from + j]} apps`),
      borderColor: T.series[0], backgroundColor: T.series[0] + '1a', fill: true, borderWidth: 2, tension: 0.3, pointRadius: 4, pointHoverRadius: 6, pointBackgroundColor: T.series[0], pointBorderColor: T.surface, pointBorderWidth: 2}], baseOptions(T, {percent: true})); }
  { const from = yix(2010); draw(document.getElementById('c-plat'), 'bar', yl.slice(from), [
      {label: 'iOS', data: Y.slice(from).map((_, j) => iosShare(from + j)), ...barStyle(T.series[0], {top: false})},
      {label: 'Android', data: Y.slice(from).map((_, j) => 100 - iosShare(from + j)), ...barStyle(T.series[1], {gapTop: true, surface: T.surface})}], baseOptions(T, {stacked: true, percent: true})); }
  window.scrollTo(0, 0);
};
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (/^#\/insights\/?$/.test(location.hash)) window.renderInsights(document.getElementById('main'), () => /^#\/insights\/?$/.test(location.hash)); });
})();
