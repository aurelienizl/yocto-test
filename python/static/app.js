// buildos_web/static/app.js
//--------------------------------------------------------
//  Page-specific UI logic  (depends on core.js having loaded)
//--------------------------------------------------------
$(document).ready(function () {
  // Normalise pathname by stripping proxy prefix + trailing slash
  const RAW = window.location.pathname.replace(/\/+$/, '');
  const path = RAW.startsWith(BASE) ? RAW.slice(BASE.length) || '/' : RAW || '/';

  // ------------------------------------------------------------------
  //  DASHBOARD  (/  /tasks)
  // ------------------------------------------------------------------
  function loadTasks() {
    $.when($.getJSON(API.repositories), $.getJSON(API.tasks()))
      .done(([repos], [tasks]) => {
        const repoMap = Object.fromEntries(repos.map(r => [r.id, r]));
        const $tbody = $('#tasksTable tbody').empty();

        tasks.forEach(t => {
          const repo = repoMap[t.repo_id] || { name: t.repo_id };
          const $tr = $('<tr>')
            .append($('<td>').text(t.id.slice(0, 8)))
            .append($('<td>').text(repo.name))
            .append($('<td>').html(`<span class="badge ${getBadgeClass(t.status)}">${t.status}</span>`))
            .append($('<td>').text(new Date(t.created_at).toLocaleString()));

          const $actions = $('<td class="text-nowrap">');
          if (t.status === 'running')
            $actions.append(`<button class="btn btn-warning btn-sm mr-1 kill-btn">Kill</button>`).children().last().data('id', t.id);
          if (t.status === 'queued')
            $actions.append(`<button class="btn btn-danger btn-sm mr-1 remove-btn">Remove</button>`).children().last().data('id', t.id);
          $actions.append(`<button class="btn btn-primary btn-sm log-btn">Logs</button>`).children().last().data('id', t.id);
          if (t.status === 'finished' && t.has_content)
            $actions.append(`<button class="btn btn-info btn-sm ml-1 download-btn">Download</button>`).children().last().data('id', t.id);

          $tr.append($actions);
          $tbody.append($tr);
        });
      });
  }

  // ------------------------------------------------------------------
  //  REPOSITORIES PAGE  (/repos)
  // ------------------------------------------------------------------
  function loadRepos() {
    $.getJSON(API.repositories, repos => {
      const $container = $('#reposContainer').empty();
      if (!repos.length) {
        $container.append('<p class="text-muted">No repositories configured.</p>');
        return;
      }
      repos.forEach(r => {
        const $col = $('<div class="col-sm-6 col-md-4 col-lg-3 d-flex">');
        const $card = $(`
          <div class="card mb-4 flex-fill shadow-sm">
            <div class="card-body d-flex flex-column">
              <h5 class="card-title">${r.name}</h5>
              <p class="card-text small text-truncate">${r.git_uri}</p>
              <div class="mt-auto">
                <button class="btn btn-success btn-sm run-btn">Run Pipeline</button>
                <span class="badge badge-pill badge-info ml-2">${r.task_count} runs</span>
              </div>
            </div>
          </div>`);
        $card.find('.run-btn').data('id', r.id);
        $col.append($card);
        $container.append($col);
      });
    });
  }

  // ------------------------------------------------------------------
  //  PAGE ROUTING
  // ------------------------------------------------------------------
  if (path === '/' || path === '/tasks' || path === '/index') {
    loadTasks();
    setInterval(loadTasks, 5000);

    $('#tasksTable')
      .on('click', '.kill-btn',     e => $.post(API.kill,   {}, loadTasks))
      .on('click', '.remove-btn',   e => $.post(API.remove, { job_id: $(e.target).data('id') }, loadTasks))
      .on('click', '.log-btn',      e => startLogPolling($(e.target).data('id')))
      .on('click', '.download-btn', e => { window.location = API.download($(e.target).data('id')); });
  }
  else if (path === '/repos') {
    loadRepos();

    $('#reposContainer')
      .on('click', '.run-btn', e => {
        const repoId = $(e.target).data('id');
        $.post(API.enqueue, { repo_id: repoId }, res => {
          alert(res.message);
          loadRepos();               // refresh run counts
        });
      });
  }
});
