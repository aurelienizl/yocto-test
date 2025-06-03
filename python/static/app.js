$(document).ready(function () {
  // Normalize pathname by stripping proxy prefix + trailing slash
  const RAW = window.location.pathname.replace(/\/+$/, '');
  const path = RAW.startsWith(BASE) ? RAW.slice(BASE.length) || '/' : RAW || '/';

  // ------------------------------------------------------------------
  //  DASHBOARD  (/  /tasks)
  // ------------------------------------------------------------------
  function loadTasks() {
    $.when(
      $.getJSON(API.repositories),
      $.getJSON(API.tasks())
    ).done(function ([repos], [tasks]) {
      const repoMap = Object.fromEntries(repos.map(r => [r.id, r]));
      const $tbody = $('#tasksTable tbody').empty();

      tasks.forEach(t => {
        const repo = repoMap[t.repo_id] || { name: t.repo_id };
        const $tr = $('<tr>')
          .append($('<td>').text(t.id.slice(0, 8)))
          .append($('<td>').text(repo.name))
          .append(
            $('<td>').html(`<span class="badge ${getBadgeClass(t.status)}">${t.status}</span>`)
          )
          .append(
            $('<td>').text(new Date(t.created_at).toLocaleString())
          );

        const $actions = $('<td class="text-nowrap">');

        // "Kill" button if running
        if (t.status === 'running') {
          const $killBtn = $(`<button class="btn btn-warning btn-sm kill-btn">Kill</button>`);
          $killBtn.attr('data-job-id', t.id);
          $actions.append($killBtn);
        }

        // "Remove" button if queued
        if (t.status === 'queued') {
          const $removeBtn = $(`<button class="btn btn-danger btn-sm remove-btn">Remove</button>`);
          $removeBtn.attr('data-job-id', t.id);
          $actions.append($removeBtn);
        }

        // "Logs" button always
        {
          const $logBtn = $(`<button class="btn btn-primary btn-sm log-btn">Logs</button>`);
          $logBtn.attr('data-job-id', t.id);
          $actions.append($logBtn);
        }

        // "Download" if finished && has_content
        if (t.status === 'finished' && t.has_content) {
          const $dlBtn = $(`<button class="btn btn-info btn-sm download-btn">Download</button>`);
          $dlBtn.attr('data-job-id', t.id);
          $actions.append($dlBtn);
        }

        $tr.append($actions);
        $tbody.append($tr);
      });
    });
  }

  // ------------------------------------------------------------------
  //  REPOSITORIES PAGE  (/repos)
  // ------------------------------------------------------------------
  function loadRepos() {
    $.getJSON(API.repositories, function (repos) {
      const $container = $('#reposContainer').empty();
      if (!repos.length) {
        $container.append(
          '<p class="text-muted">No repositories configured.</p>'
        );
        return;
      }
      repos.forEach(function (r) {
        const $col = $('<div class="col-sm-6 col-md-4 col-lg-3 d-flex">');
        const $card = $(`
          <div class="card mb-4 flex-fill shadow-sm">
            <div class="card-body d-flex flex-column">
              <h5 class="card-title">${r.name}</h5>
              <p class="card-text small text-truncate">${r.git_uri}</p>
              <div class="mt-auto">
                <button class="btn btn-success btn-sm run-btn" data-repo-id="${r.id}">
                  Run Pipeline
                </button>
                <span class="badge badge-pill badge-info ml-2">${r.task_count} runs</span>
              </div>
            </div>
          </div>`);
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

    // Delegate kill/remove/log/download under #tasksTable
    $('#tasksTable')
      // Kill running job
      .on('click', '.kill-btn', function (e) {
        const jobId = $(this).data('job-id');
        if (!jobId) return;
        $.post(API.kill, {}, loadTasks);
      })
      // Remove queued job
      .on('click', '.remove-btn', function (e) {
        const jobId = $(this).data('job-id');
        if (!jobId) return;
        $.post(API.remove, { job_id: jobId }, loadTasks)
          .fail(function (xhr) {
            alert("Error removing job: " + xhr.responseJSON.error);
            loadTasks();
          });
      })
      // Show logs
      .on('click', '.log-btn', function (e) {
        const jobId = $(this).data('job-id');
        if (!jobId) return;
        startLogPolling(jobId);
      })
      // Download content
      .on('click', '.download-btn', function (e) {
        const jobId = $(this).data('job-id');
        if (!jobId) return;
        window.location = API.download(jobId);
      });
  }
  else if (path === '/repos') {
    loadRepos();

    // Delegate "Run Pipeline" button under #reposContainer
    $('#reposContainer').on('click', '.run-btn', function (e) {
      const repoId = $(this).data('repo-id');
      if (!repoId) return;
      $.post(API.enqueue, { repo_id: repoId })
        .done(function (res) {
          alert(res.message);
          loadRepos(); // refresh run counts
        })
        .fail(function (xhr) {
          const json = xhr.responseJSON || {};
          alert("Error enqueuing: " + (json.error || "Unknown error"));
        });
    });
  }
});
