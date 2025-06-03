//--------------------------------------------------------
//  Compute base-path once from <body data-base="…">
//--------------------------------------------------------
const BASE = document.body.dataset.base || '';

function api(path) {
  // join BASE + /path, collapse duplicate slashes
  return `${BASE}/${path}`.replace(/\/+/g, '/').replace(/\/\?/, '?');
}

//--------------------------------------------------------
//  Centralized API map  (EVERY entry via api())
//--------------------------------------------------------
const API = {
  // list tasks for all repos or a single repo_id
  tasks:        repoId => api(repoId ? `tasks?repo_id=${repoId}` : 'tasks'),
  repositories: api('repositories'),
  current:      api('current'),
  enqueue:      api('enqueue'),
  kill:         api('kill'),
  remove:       api('remove'),
  logsJson:     (id, afterId = 0) => api(`logs_json/${id}?after_id=${afterId}`),
  download:     id => api(`tasks/${id}/download`),
  metrics: {
    cpu:    api('metrics/cpu'),
    memory: api('metrics/memory'),
    disk:   api('metrics/disk')
  }
};

//--------------------------------------------------------
//  UI helpers
//--------------------------------------------------------
function getBadgeClass(status) {
  switch (status) {
    case 'queued':   return 'badge-secondary';
    case 'running':  return 'badge-warning';
    case 'finished': return 'badge-success';
    case 'failed':   return 'badge-danger';
    case 'canceled': return 'badge-dark';
    default:         return 'badge-info';
  }
}

//--------------------------------------------------------
//  Live system status widgets
//--------------------------------------------------------
function updateCurrentStatus() {
  $.getJSON(API.current, data => {
    if (data && data.id) {
      const label = data.git_uri || data.repo_id || data.id;
      $('#currentStatus').text(`Running (${label})`);
    } else {
      $('#currentStatus').text('Idle');
    }
  }).fail(() => {
    $('#currentStatus').text('Unknown');
  });
}

function loadMetrics() {
  $.getJSON(API.metrics.cpu,    d => $('#cpuUsage').text(d.cpu_percent.toFixed(0) + '%'));
  $.getJSON(API.metrics.memory, d => $('#memUsage').text(d.percent.toFixed(0) + '%'));
  $.getJSON(API.metrics.disk,   d => $('#diskUsage').text(d.percent.toFixed(0) + '%'));
}

//--------------------------------------------------------
//  Shared log polling
//--------------------------------------------------------
let logPollInterval = null;
let lastLogId = 0;

function startLogPolling(taskId) {
  stopLogPolling();
  lastLogId = 0;
  $('#logPre').text('Loading logs…');
  $('#logModal').modal('show');

  logPollInterval = setInterval(() => {
    $.getJSON(API.logsJson(taskId, lastLogId), rows => {
      if (rows.length && $('#logPre').text().startsWith('Loading')) {
        $('#logPre').text('');
      }
      rows.forEach(r => {
        $('#logPre').append(`[${r.timestamp}] ${r.line}\n`);
        lastLogId = r.id;
      });
      $('#logPre')[0].scrollTop = $('#logPre')[0].scrollHeight;
    });
  }, 1000);
}

function stopLogPolling() {
  if (logPollInterval) {
    clearInterval(logPollInterval);
    logPollInterval = null;
  }
}

//--------------------------------------------------------
//  Global bootstrap
//--------------------------------------------------------
$(document).ready(() => {
  $('#logModal').on('hidden.bs.modal', stopLogPolling);

  updateCurrentStatus();
  setInterval(updateCurrentStatus, 2000);

  loadMetrics();
  setInterval(loadMetrics, 5000);
});
