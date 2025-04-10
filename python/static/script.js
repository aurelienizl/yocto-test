$(document).ready(function() {
    function refreshTasks() {
      $.getJSON('/tasks', function(data) {
        var currentTask = null, queueTasks = [], finishedTasks = [];
        var logSelectOptions = '<option value="">Select a task</option>';
        $.each(data, function(i, task) {
          if(task.status === "running") {
            currentTask = task;
          } else if(task.status === "queued") {
            queueTasks.push(task);
          } else if(task.status === "finished" || task.status === "failed" || task.status === "canceled") {
            finishedTasks.push(task);
          }
          logSelectOptions += '<option value="'+ task.id +'">'+ task.git_uri +' ('+ task.status +')</option>';
        });
        
        // Update current task display.
        if(currentTask) {
          $('#currentTaskInfo').html(
            '<p><strong>ID:</strong> ' + currentTask.id + '<br>' +
            '<strong>Repo:</strong> ' + currentTask.git_uri + '<br>' +
            '<strong>Started:</strong> ' + currentTask.started_at + '</p>'
          );
          $('#killTaskBtn').show();
        } else {
          $('#currentTaskInfo').html('<p>No task is currently running.</p>');
          $('#killTaskBtn').hide();
        }
        
        // Update pending tasks table.
        var queueHtml = '';
        $.each(queueTasks, function(i, task) {
          queueHtml += '<tr>' +
                       '<td>' + task.id + '</td>' +
                       '<td>' + task.git_uri + '</td>' +
                       '<td>' + task.created_at + '</td>' +
                       '<td><button class="removeTask" data-taskid="'+task.id+'">Remove</button></td>' +
                       '</tr>';
        });
        $('#queueTable tbody').html(queueHtml);
        
        // Update finished tasks table.
        var finishedHtml = '';
        $.each(finishedTasks, function(i, task) {
          finishedHtml += '<tr>' +
                          '<td>' + task.id + '</td>' +
                          '<td>' + task.git_uri + '</td>' +
                          '<td>' + task.status + '</td>' +
                          '<td>' + (task.started_at || '-') + '</td>' +
                          '<td>' + (task.finished_at || '-') + '</td>' +
                          '<td><a href="/logs/'+ task.id +'" target="_blank">View</a></td>' +
                          '</tr>';
        });
        $('#finishedTable tbody').html(finishedHtml);
        
        $('#logTaskSelect').html(logSelectOptions);
      });
    }
    
    refreshTasks();
    setInterval(refreshTasks, 5000);
    
    // Enqueue repository.
    $('#enqueueForm').submit(function(e) {
      e.preventDefault();
      $.post('/enqueue', $(this).serialize(), function(response) {
        alert(response.message);
        refreshTasks();
      }).fail(function(xhr) {
        alert(xhr.responseJSON.error);
      });
    });
    
    // Remove a queued task.
    $(document).on('click', '.removeTask', function() {
      var taskId = $(this).data('taskid');
      $.post('/remove', { task_id: taskId }, function(response) {
        alert(response.message);
        refreshTasks();
      }).fail(function(xhr) {
        alert(xhr.responseJSON.error);
      });
    });
    
    // Kill the current task.
    $('#killTaskBtn').click(function() {
      if(confirm("Are you sure you want to kill the running task?")) {
        $.post('/kill', function(response) {
          alert(response.message);
          refreshTasks();
        }).fail(function(xhr) {
          alert(xhr.responseJSON.error);
        });
      }
    });
    
    // Stream logs for the selected task.
    $('#logTaskSelect').change(function() {
      var taskId = $(this).val();
      if(window.logEventSource) {
        window.logEventSource.close();
      }
      if(!taskId) {
        $('#logs').html('');
        return;
      }
      window.logEventSource = new EventSource('/stream_logs/' + taskId);
      window.logEventSource.onmessage = function(event) {
        $('#logs').append(event.data + '<br>');
        $('#logs').scrollTop($('#logs')[0].scrollHeight);
      };
      window.logEventSource.onerror = function(error) {
        console.error("Error in log stream", error);
      
        // Optionally, close and attempt to re-establish the connection after a delay
        window.logEventSource.close();
        
        setTimeout(function() {
          // Recreate the EventSource connection if a task is selected
          var taskId = $('#logTaskSelect').val();
          if(taskId) {
            window.logEventSource = new EventSource('/stream_logs/' + taskId);
            window.logEventSource.onmessage = function(event) {
              $('#logs').append(event.data + '<br>');
              $('#logs').scrollTop($('#logs')[0].scrollHeight);
            };
            window.logEventSource.onerror = arguments.callee; // reassign this error handler
          }
        }, 5000); // reconnect after 5 seconds
      };      
    });
  });
  