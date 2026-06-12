// recall web UI — vanilla JS, no framework.

const $ = (s) => document.querySelector(s);
const q = $('#q');
const list = $('#results');
const empty = $('#empty');
const count = $('#count');
const stats = $('#stats');

let results = [];
let active = -1;
let currentQ = '';
let inflight = null;

async function loadStats() {
  try {
    const r = await fetch('/api/status');
    const s = await r.json();
    const live = (s.live_sources || []).join(' · ');
    stats.textContent = `${s.total.toLocaleString()} items · ${live}`;
  } catch (e) {
    stats.textContent = 'offline';
  }
}

async function search() {
  const v = q.value.trim();
  currentQ = v;
  if (!v) {
    results = [];
    render();
    return;
  }
  if (inflight) inflight.abort();
  inflight = new AbortController();
  const t0 = performance.now();
  try {
    const r = await fetch(`/api/search?q=${encodeURIComponent(v)}&limit=50`, { signal: inflight.signal });
    const data = await r.json();
    const dt = (performance.now() - t0).toFixed(0);
    results = data.results || [];
    count.textContent = `${data.count} result${data.count === 1 ? '' : 's'} in ${dt}ms`;
    active = results.length ? 0 : -1;
    render();
  } catch (e) {
    if (e.name !== 'AbortError') {
      console.error(e);
    }
  }
}

function render() {
  if (!results.length) {
    list.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';
  const html = results.map((r, i) => `
    <li class="result ${i === active ? 'active' : ''}" data-idx="${i}">
      <div class="row1">
        <span class="source ${r.source}">${r.source}</span>
        ${r.app && r.app !== r.source ? `<span class="source">${escapeHTML(r.app)}</span>` : ''}
        <span class="age">${escapeHTML(r.age)}</span>
      </div>
      ${r.title ? `<div class="title">${highlight(r.title)}</div>` : ''}
      ${r.snippet && r.snippet !== r.title ? `<div class="snippet">${highlight(r.snippet)}</div>` : ''}
      ${r.url ? `<a class="url" href="${escapeAttr(r.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${escapeHTML(r.url)}</a>` : ''}
    </li>
  `).join('');
  list.innerHTML = html;

  // active item into view
  const a = list.querySelector('.result.active');
  if (a) a.scrollIntoView({ block: 'nearest' });
}

function highlight(s) {
  if (!s) return '';
  const safe = escapeHTML(s);
  if (!currentQ) return safe;
  const terms = currentQ.split(/\s+/).filter(Boolean).map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (!terms.length) return safe;
  const re = new RegExp(`(${terms.join('|')})`, 'gi');
  return safe.replace(re, '<mark>$1</mark>');
}

function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function escapeAttr(s) { return escapeHTML(s); }

function open(i) {
  const r = results[i];
  if (!r) return;
  // prefer the URL (open in browser)
  if (r.url) {
    window.open(r.url, '_blank', 'noopener');
    return;
  }
  // fall back to opening the source app
  const app = (r.app || r.source || '').toLowerCase();
  const url = `recall://open?id=${encodeURIComponent(r.id)}`;
  // We don't have a registered protocol, so just copy the title/snippet to clipboard.
  navigator.clipboard.writeText(`${r.title}\n${r.snippet}`).then(() => {
    count.textContent = `copied: ${r.title?.slice(0, 50)}`;
    setTimeout(() => { count.textContent = `${results.length} result(s)`; }, 1500);
  });
}

function move(delta) {
  if (!results.length) return;
  active = Math.max(0, Math.min(results.length - 1, active + delta));
  render();
}

// events
q.addEventListener('input', debounce(search, 80));

// prefill from ?q=...
const _u = new URL(location.href);
const _initQ = _u.searchParams.get('q');
if (_initQ) { q.value = _initQ; search(); }
q.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
  else if (e.key === 'Enter') { e.preventDefault(); open(active); }
  else if (e.key === 'Escape') { q.value = ''; search(); q.blur(); }
});
q.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'c' && results[active]) {
    navigator.clipboard.writeText(results[active].snippet || results[active].title || '');
  }
});
list.addEventListener('click', (e) => {
  const li = e.target.closest('.result');
  if (!li) return;
  if (e.target.tagName === 'A') return; // let the link open
  open(parseInt(li.dataset.idx, 10));
});
list.addEventListener('mousemove', (e) => {
  const li = e.target.closest('.result');
  if (!li) return;
  const i = parseInt(li.dataset.idx, 10);
  if (i !== active) { active = i; render(); }
});
empty.addEventListener('click', (e) => {
  const a = e.target.closest('a[data-q]');
  if (!a) return;
  e.preventDefault();
  q.value = a.dataset.q;
  search();
});
$('#reindex').addEventListener('click', async (e) => {
  e.preventDefault();
  count.textContent = 're-indexing…';
  try {
    const r = await fetch('/api/reindex');
    const data = await r.json();
    const total = Object.values(data.added || {}).reduce((a,b)=>a+b, 0);
    count.textContent = `+${total} new`;
    setTimeout(() => loadStats(), 200);
  } catch (e) {
    count.textContent = 're-index failed';
  }
});

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// global hotkey: ⌘K or ⌘. focuses search
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === '.')) {
    e.preventDefault();
    q.focus();
    q.select();
  }
});

loadStats();
