// Centralized API endpoints
const API = {
  tasks:    '/tasks',
  current:  '/current',
  enqueue:  '/enqueue',
  kill:     '/kill',
  remove:   '/remove',
  logsJson: (id, after_id=0) => `/logs_json/${id}?after_id=${after_id}`,
  download: id => `/tasks/${id}/download`,
  metrics: {
    cpu:    '/metrics/cpu',
    memory: '/metrics/memory',
    disk:   '/metrics/disk'
  }
};

// Status badge helper
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

// Update job status widget
function updateCurrentStatus() {
  $.getJSON(API.current, data => {
    $('#currentStatus').text(
      data.id ? `Running (${data.git_uri})` : 'Idle'
    );
  }).fail(() => {
    $('#currentStatus').text('Unknown');
  });
}

// Poll and display system metrics
function loadMetrics() {
  $.getJSON(API.metrics.cpu, data => {
    $('#cpuUsage').text(data.cpu_percent.toFixed(1) + '%');
  });
  $.getJSON(API.metrics.memory, data => {
    $('#memUsage').text(data.percent.toFixed(1) + '%');
  });
  $.getJSON(API.metrics.disk, data => {
    $('#diskUsage').text(data.percent.toFixed(1) + '%');
  });
}

// Shared log‐polling
let logPollInterval = null;
let lastLogId = 0;

function startLogPolling(taskId) {
  const $pre = $('#logPre');
  lastLogId = 0;
  $pre.text('Loading logs…');
  $('#logModal').modal('show');

  logPollInterval = setInterval(() => {
    $.getJSON(API.logsJson(taskId, lastLogId), rows => {
      if (rows.length && $pre.text().startsWith('Loading')) {
        $pre.text('');
      }
      rows.forEach(r => {
        $pre.append(`[${r.timestamp}] ${r.line}\n`);
        lastLogId = r.id;
      });
      $pre[0].scrollTop = $pre[0].scrollHeight;
    });
  }, 1000);
}

function stopLogPolling() {
  if (logPollInterval) {
    clearInterval(logPollInterval);
    logPollInterval = null;
  }
}

// Initialize shared bits
$(document).ready(function() {
  updateCurrentStatus();
  setInterval(updateCurrentStatus, 2000);

  loadMetrics();
  setInterval(loadMetrics, 5000);

  $('#logModal').on('hidden.bs.modal', stopLogPolling);
});
