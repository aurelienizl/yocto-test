$(document).ready(function() {
  // Maps a task status to a Bootstrap badge class.
  function getBadgeClass(status) {
    switch (status) {
      case 'queued':
        return 'badge-secondary';
      case 'running':
        return 'badge-warning';
      case 'finished':
        return 'badge-success';
      case 'failed':
        return 'badge-danger';
      case 'canceled':
        return 'badge-dark';
      default:
        return 'badge-info';
    }
  }

  // Function to load tasks from the server
  function loadTasks() {
    $.getJSON('/tasks', function(data) {
      var tableBody = $('#tasksTable tbody');
      tableBody.empty();
      $.each(data, function(index, task) {
        var tr = $('<tr>');
        // Shorten the task id for display purposes
        tr.append($('<td>').text(task.id.substring(0, 8)));
        tr.append($('<td>').text(task.git_uri));
        // Use the getBadgeClass() to assign a color class to the badge.
        tr.append($('<td>').html('<span class="badge ' + getBadgeClass(task.status) + '">' + task.status + '</span>'));
        tr.append($('<td>').text(new Date(task.created_at).toLocaleString()));
        
        var actions = $('<td>');
        // Display "Kill" button for running tasks
        if (task.status === 'running') {
          actions.append('<button class="btn btn-warning btn-sm mr-1 kill-btn" data-id="' + task.id + '">Kill</button>');
        }
        // Display "Remove" button for queued tasks
        if (task.status === 'queued') {
          actions.append('<button class="btn btn-danger btn-sm mr-1 remove-btn" data-id="' + task.id + '">Remove</button>');
        }
        // Log button available for any task
        actions.append('<button class="btn btn-primary btn-sm log-btn" data-id="' + task.id + '">Logs</button>');
        tr.append(actions);
        tableBody.append(tr);
      });
    });
  }

  // Function to update the status displayed in the navbar.
  function updateCurrentStatus() {
    $.getJSON('/current', function(data) {
      // If the returned JSON contains an "id", a job is running.
      if (data.hasOwnProperty("id")) {
        $('#currentStatus').text("Running (" + data.git_uri + ")");
      } else {
        $('#currentStatus').text("Idle");
      }
    }).fail(function() {
      $('#currentStatus').text("Unknown");
    });
  }

  // Initial load of tasks and current status.
  loadTasks();
  updateCurrentStatus();

  // Refresh tasks list every 5 seconds.
  setInterval(loadTasks, 5000);
  // Refresh current status every 2 seconds.
  setInterval(updateCurrentStatus, 2000);

  // Handle task submission.
  $('#taskForm').submit(function(e) {
    e.preventDefault();
    var gitUri = $('#gitUri').val();
    $.post('/enqueue', { git_uri: gitUri }, function(response) {
      alert(response.message);
      $('#gitUri').val('');
      loadTasks();
    }).fail(function(xhr) {
      alert(xhr.responseJSON ? xhr.responseJSON.error : 'An error occurred while enqueuing the task.');
    });
  });

  // Kill task action.
  $('#tasksTable').on('click', '.kill-btn', function() {
    var taskId = $(this).data('id');
    $.post('/kill', { task_id: taskId }, function(response) {
      alert(response.message);
      loadTasks();
    }).fail(function(xhr) {
      alert(xhr.responseJSON ? xhr.responseJSON.error : 'An error occurred while killing the task.');
    });
  });

  // Remove task action.
  $('#tasksTable').on('click', '.remove-btn', function() {
    var taskId = $(this).data('id');
    $.post('/remove', { job_id: taskId }, function(response) {
      alert(response.message);
      loadTasks();
    }).fail(function(xhr) {
      alert(xhr.responseJSON ? xhr.responseJSON.error : 'An error occurred while removing the task.');
    });
  });

  // Open log modal to display logs.
  $('#tasksTable').on('click', '.log-btn', function() {
    var taskId = $(this).data('id');
    $('#logPre').text("Loading logs...");
    $('#logModal').modal('show');
    $.get('/logs/' + taskId)
      .done(function(data) {
        $('#logPre').text(data);
      })
      .fail(function(jqXHR, textStatus, errorThrown) {
        console.log('Log fetch failed:', textStatus, errorThrown);
        $('#logPre').text("No logs available or an error occurred while retrieving logs.");
      });
  });

  // Manual close action for modal.
  $('#logModal .close, #logModal .btn-secondary').on('click', function() {
    console.log('Close button clicked');
    $('#logModal').modal('hide');
  });
});
