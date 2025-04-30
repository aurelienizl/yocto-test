$(document).ready(function () {
  // Maps a task status to a Bootstrap badge class.
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

  // Load tasks into the table.
  function loadTasks() {
    $.getJSON('/tasks', function (data) {
      var tableBody = $('#tasksTable tbody');
      tableBody.empty();
      $.each(data, function (index, task) {
        var tr = $('<tr>');
        tr.append($('<td>').text(task.id.substring(0, 8)));
        tr.append($('<td>').text(task.git_uri));
        tr.append(
          $('<td>').html(
            '<span class="badge ' +
              getBadgeClass(task.status) +
              '">' +
              task.status +
              '</span>'
          )
        );
        tr.append(
          $('<td>').text(new Date(task.created_at).toLocaleString())
        );

        var actions = $('<td>');
        if (task.status === 'running') {
          actions.append(
            '<button class="btn btn-warning btn-sm mr-1 kill-btn" data-id="' +
              task.id +
              '">Kill</button>'
          );
        }
        if (task.status === 'queued') {
          actions.append(
            '<button class="btn btn-danger btn-sm mr-1 remove-btn" data-id="' +
              task.id +
              '">Remove</button>'
          );
        }
        actions.append(
          '<button class="btn btn-primary btn-sm log-btn" data-id="' +
            task.id +
            '">Logs</button>'
        );
        if (task.status === 'finished' && task.has_content) {
          actions.append(
            '<button class="btn btn-info btn-sm download-btn ml-1" data-id="' +
              task.id +
              '">Download</button>'
          );
        }
        tr.append(actions);
        tableBody.append(tr);
      });
    });
  }

  // Update navbar status.
  function updateCurrentStatus() {
    $.getJSON('/current', function (data) {
      if (data.hasOwnProperty("id")) {
        $('#currentStatus').text("Running (" + data.git_uri + ")");
      } else {
        $('#currentStatus').text("Idle");
      }
    }).fail(function () {
      $('#currentStatus').text("Unknown");
    });
  }

  // Initial load & intervals.
  loadTasks();
  updateCurrentStatus();
  setInterval(loadTasks, 5000);
  setInterval(updateCurrentStatus, 2000);

  // Enqueue form.
  $('#taskForm').submit(function (e) {
    e.preventDefault();
    var gitUri = $('#gitUri').val();
    $.post('/enqueue', { git_uri: gitUri }, function (res) {
      alert(res.message);
      $('#gitUri').val('');
      loadTasks();
    }).fail(function (xhr) {
      alert(xhr.responseJSON?.error || 'Error enqueuing task.');
    });
  });

  // Kill action.
  $('#tasksTable').on('click', '.kill-btn', function () {
    var id = $(this).data('id');
    $.post('/kill', { task_id: id }, function (res) {
      alert(res.message);
      loadTasks();
    }).fail(function (xhr) {
      alert(xhr.responseJSON?.error || 'Error killing task.');
    });
  });

  // Remove action.
  $('#tasksTable').on('click', '.remove-btn', function () {
    var id = $(this).data('id');
    $.post('/remove', { job_id: id }, function (res) {
      alert(res.message);
      loadTasks();
    }).fail(function (xhr) {
      alert(xhr.responseJSON?.error || 'Error removing task.');
    });
  });

  // Download action.
  $('#tasksTable').on('click', '.download-btn', function () {
    var id = $(this).data('id');
    window.location = '/tasks/' + id + '/download';
  });

  // Polling for logs
  let logPollInterval = null;
  let lastLogId = 0;

  $('#tasksTable').on('click', '.log-btn', function () {
    const id = $(this).data('id');
    const $pre = $('#logPre');
    lastLogId = 0;
    $pre.text('Loading logs…');
    $('#logModal').modal('show');

    logPollInterval = setInterval(function () {
      $.getJSON(`/logs_json/${id}?after_id=${lastLogId}`, function (rows) {
        if (rows.length && $pre.text().startsWith('Loading')) {
          $pre.text('');
        }
        rows.forEach(function (r) {
          $pre.append(`[${r.timestamp}] ${r.line}\n`);
          lastLogId = r.id;
        });
        $pre[0].scrollTop = $pre[0].scrollHeight;
      });
    }, 1000);
  });

  // Stop polling when modal closes
  $('#logModal').on('hidden.bs.modal', function () {
    if (logPollInterval) {
      clearInterval(logPollInterval);
      logPollInterval = null;
    }
  });
});
