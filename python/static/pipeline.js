/******************************************************************
 *  BuildOS Pipeline – large unlimited log viewer                 *
 ******************************************************************/
import { APPS } from './apps.js';

/* ─ helpers ─ */
const API_BASE = document.body.dataset.base || '';
const $ = id => document.getElementById(id);
const $$ = s => document.querySelectorAll(s);
const api = p => p.startsWith('/') ? p : `${API_BASE}/${p}`.replace(/\/+/g, '/');
const fetchJSON = (u, o) => fetch(u, o).then(r => r.json());

/* ─ nav ─ */
(function initNav() {
  const nav = $('nav');
  APPS.forEach(a => {
    const l = document.createElement('a');
    l.href = a.href; l.textContent = a.name;
    if (location.pathname === a.href) l.style.opacity = '1';
    nav.appendChild(l);
  });
}());

/* ─ API map ─ */
const API = {
  repos: api('repositories'),
  tasks: api('tasks'),
  enqueue: api('enqueue'),
  kill: api('kill'),
  remove: api('remove'),
  logs: (id, a = 0) => api(`logs_json/${id}?after_id=${a}`),
  dl: id => api(`tasks/${id}/download`),
  metrics: {
    cpu: api('/metrics/cpu'), memory: api('/metrics/memory'), disk: api('/metrics/disk')
  },
  current: api('current')
};

/* ─ repo grid ─ */
const grid = $('reposContainer');
const badge = s => `<span class="badge ${s}">${s}</span>`;

function renderRepos(list) {
  grid.innerHTML = '';
  list.forEach(r => {
    grid.insertAdjacentHTML('beforeend', `
      <div class="repo-card" data-repo="${r.id}">
        <div class="repo-head">
          <h2>${r.name || r.id}</h2>
          <button class="run-btn" data-repo="${r.id}">Run</button>
        </div>
        <div class="tasks">
          <table>
            <thead><tr><th>ID</th><th>Status</th><th>Started</th><th>Actions</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>`);
  });
}

/* ─ task refresh ─ */
function refreshTasks() {
  fetchJSON(API.tasks).then(all => {
    const byRepo = {};
    all.forEach(t => (byRepo[t.repo_id] = byRepo[t.repo_id] || []).push(t));

    for (const card of $$('.repo-card')) {
      const repoId = card.dataset.repo;
      const tb = card.querySelector('tbody'); tb.innerHTML = '';
      (byRepo[repoId] || []).forEach(t => {
        tb.insertAdjacentHTML('beforeend', `
          <tr>
            <td>${t.id.slice(0, 8)}</td>
            <td>${badge(t.status)}</td>
            <td>${new Date(t.created_at || t.started_at || 0).toLocaleString()}</td>
            <td>
              ${t.status === 'running' ? `<button class="kill" data-id="${t.id}">Kill</button>` : ''}
              ${t.status === 'queued' ? `<button class="cancel" data-id="${t.id}">Cancel</button>` : ''}
              <button class="log" data-id="${t.id}">Logs</button>
              ${t.status === 'finished' && t.has_content ? `<button class="dl" data-id="${t.id}">Download</button>` : ''}
            </td>
          </tr>`);
      });
    }
  });
}

/* ─ metrics ─ */
function refreshMetrics() {
  fetchJSON(API.metrics.cpu).then(d => $('cpuUsage').textContent = d.cpu_percent.toFixed(0) + '%');
  fetchJSON(API.metrics.memory).then(d => $('memUsage').textContent = d.percent.toFixed(0) + '%');
  fetchJSON(API.metrics.disk).then(d => $('diskUsage').textContent = d.percent.toFixed(0) + '%');
  fetchJSON(API.current).then(d => $('currentStatus').textContent = d.id ? `Running ${d.repo_id || ''}` : 'Idle');
}

/* ─ card buttons ─ */
grid.addEventListener('click', e => {
  if (e.target.classList.contains('run-btn')) {
    const fd = new FormData(); fd.append('repo_id', e.target.dataset.repo);
    return fetchJSON(API.enqueue, { method: 'POST', body: fd }).then(r => alert(r.message || r.error));
  }
  const id = e.target.dataset.id; if (!id) return;

  if (e.target.classList.contains('kill')) return fetchJSON(API.kill, { method: 'POST' });
  if (e.target.classList.contains('cancel')) {
    const fd = new FormData(); fd.append('job_id', id);
    return fetchJSON(API.remove, { method: 'POST', body: fd });
  }
  if (e.target.classList.contains('log')) return showLogs(id);
  if (e.target.classList.contains('dl')) location = API.dl(id);
});

/* ═════════ LOG VIEWER (unlimited, append-once/second) ══════════ */
const LOG_POLL_MS = 1500;
let logTimer = 0;
let lastId = 0;
let autoBottom = true;      // true ⇒ keep tailing

const pre = $('logPre');

/* if the user scrolls >4 px from the bottom, stop autoscroll */
pre.addEventListener('scroll', () => {
  const atBottom = pre.scrollHeight - pre.clientHeight - pre.scrollTop < 4;
  autoBottom = atBottom;
});

function showLogs(jobId) {
  clearInterval(logTimer);
  lastId = 0;
  autoBottom = true;
  pre.textContent = 'Loading…';
  $('logDlg').showModal();

  logTimer = setInterval(async () => {
    const rows = await fetchJSON(API.logs(jobId, lastId));
    if (!rows.length) return;

    if (pre.textContent.startsWith('Loading')) pre.textContent = '';

    /* build once, append once (oldest → newest) */
    let chunk = '';
    for (let i = 0; i < rows.length; i++) {
      chunk += `[${rows[i].timestamp}] ${rows[i].line}\n`;
      lastId = rows[i].id;
    }
    pre.insertAdjacentText('beforeend', chunk);   // append at bottom

    if (autoBottom) pre.scrollTop = pre.scrollHeight;
  }, LOG_POLL_MS);
}

$('closeLogBtn').onclick = () => {
  $('logDlg').close();
  clearInterval(logTimer);
};

/* ─ start loops ─ */
fetchJSON(API.repos).then(renderRepos).then(refreshTasks);
setInterval(refreshTasks, 4000);
refreshMetrics(); setInterval(refreshMetrics, 5000);
