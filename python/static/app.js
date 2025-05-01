$(document).ready(function () {
    const path = window.location.pathname;
  
    // Dashboard: tasks table
    function loadTasks() {
      $.getJSON(API.tasks, data => {
        const $tbody = $('#tasksTable tbody').empty();
        data.forEach(task => {
          const $tr = $('<tr>')
            .append($('<td>').text(task.id.substring(0, 8)))
            .append($('<td>').text(task.git_uri))
            .append($('<td>').html(
              `<span class="badge ${getBadgeClass(task.status)}">${task.status}</span>`
            ))
            .append($('<td>').text(
              new Date(task.created_at).toLocaleString()
            ));
  
          const $actions = $('<td>');
          if (task.status === 'running') {
            $actions.append(
              `<button class="btn btn-warning btn-sm mr-1 kill-btn" data-id="${task.id}">Kill</button>`
            );
          }
          if (task.status === 'queued') {
            $actions.append(
              `<button class="btn btn-danger btn-sm mr-1 remove-btn" data-id="${task.id}">Remove</button>`
            );
          }
          $actions.append(
            `<button class="btn btn-primary btn-sm log-btn" data-id="${task.id}">Logs</button>`
          );
          if (task.status === 'finished' && task.has_content) {
            $actions.append(
              `<button class="btn btn-info btn-sm download-btn ml-1" data-id="${task.id}">Download</button>`
            );
          }
          $tr.append($actions);
          $tbody.append($tr);
        });
      });
    }
  
    // Repositories: cards by repo
    function loadRepos() {
      $.getJSON(API.tasks, data => {
        const $container = $('#reposContainer').empty();
        const groups = {};
        data.forEach(t => (groups[t.git_uri] = groups[t.git_uri] || []).push(t));
  
        Object.entries(groups).forEach(([repo, tasks]) => {
          const $card = $('<div class="card mb-4">')
            .append(`<div class="card-header font-weight-bold">${repo}</div>`);
  
          const $list = $('<ul class="list-group list-group-flush">');
          tasks.forEach(task => {
            const $li = $(`
              <li class="list-group-item d-flex justify-content-between align-items-center">
                <span>
                  ${task.id.substring(0,8)}
                  <span class="badge ${getBadgeClass(task.status)}">${task.status}</span>
                  ${new Date(task.created_at).toLocaleString()}
                </span>
              </li>
            `);
            $li.append(
              `<button class="btn btn-sm btn-outline-primary repo-log-btn ml-2" data-id="${task.id}">Logs</button>`
            );
            if (task.status === 'finished' && task.has_content) {
              $li.append(
                `<button class="btn btn-sm btn-outline-info repo-download-btn ml-2" data-id="${task.id}">Download</button>`
              );
            }
            $list.append($li);
          });
          $card.append($list);
          $container.append($card);
        });
      });
    }
  
    // Initialize page logic
    if (path === '/' || path === '/tasks') {
      loadTasks();
      setInterval(loadTasks, 5000);
  
      $('#tasksTable')
        .on('click', '.kill-btn',    e => $.post(API.kill,   { task_id:    $(e.currentTarget).data('id') }, loadTasks))
        .on('click', '.remove-btn',  e => $.post(API.remove, { job_id:      $(e.currentTarget).data('id') }, loadTasks))
        .on('click', '.log-btn',     e => startLogPolling($(e.currentTarget).data('id')))
        .on('click', '.download-btn',e => window.location = API.download($(e.currentTarget).data('id')));
    }
    else if (path === '/repos') {
      loadRepos();
  
      $('#reposContainer')
        .on('click', '.repo-log-btn',      e => startLogPolling($(e.currentTarget).data('id')))
        .on('click', '.repo-download-btn', e => window.location = API.download($(e.currentTarget).data('id')));
    }
  
    // Enqueue (common)
    $('#taskForm').submit(e => {
      e.preventDefault();
      $.post(API.enqueue, { git_uri: $('#gitUri').val().trim() }, res => {
        alert(res.message);
        $('#gitUri').val('');
        if (path === '/' || path === '/tasks') loadTasks();
      });
    });
  });
  