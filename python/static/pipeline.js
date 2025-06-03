/******************************************************************
 *  BuildOS Pipeline front-end – fixed enqueue / kill / cancel URLs
 ******************************************************************/
import { APPS } from './apps.js';

/* ---------- helpers ---------- */
const API_BASE = document.body.dataset.base || '';       // "/pipeline"
const $  = id => document.getElementById(id);
const $$ = q  => document.querySelectorAll(q);
const api = p => p.startsWith('/') ? p
                                   : `${API_BASE}/${p}`.replace(/\/+/g,'/');
const fetchJSON = (u,o)=>fetch(u,o).then(r=>r.json());

/* ---------- nav ---------- */
function buildNav(nav){
  APPS.forEach(a=>{
    const l=document.createElement('a');
    l.href=a.href;l.textContent=a.name;
    if(location.pathname===a.href) l.style.opacity='1';
    nav.appendChild(l);
  });
}
buildNav($('nav'));

/* ---------- utils ---------- */
const badge = s => `<span class="badge ${s}">${s}</span>`;

/* ---------- API endpoints (fixed) ---------- */
const API = {
  repos:   api('repositories'),
  tasks:   api('tasks'),
  enqueue: api('enqueue'),
  kill:    api('kill'),
  remove:  api('remove'),
  logs:    (id,a=0)=>api(`logs_json/${id}?after_id=${a}`),
  dl:      id=>api(`tasks/${id}/download`),
  metrics: {
    cpu: api('/metrics/cpu'),
    memory: api('/metrics/memory'),
    disk: api('/metrics/disk')
  },
  current: api('current')
};

/* ---------- repositories UI ---------- */
const container = $('reposContainer');

function renderRepos(repos){
  container.innerHTML='';
  repos.forEach(r=>{
    const card=document.createElement('div');
    card.className='repo-card'; card.dataset.repo=r.id;
    card.innerHTML=`
      <div class="repo-head">
        <h2>${r.name||r.id}</h2>
        <button class="run-btn" data-repo="${r.id}">Run</button>
      </div>
      <div class="tasks"><table>
        <thead><tr><th>ID</th><th>Status</th><th>Started</th><th>Actions</th></tr></thead>
        <tbody></tbody>
      </table></div>`;
    container.appendChild(card);
  });
}

container.addEventListener('click',e=>{
  /* run pipeline --------------------------------------------------*/
  if(e.target.classList.contains('run-btn')){
    const repoId=e.target.dataset.repo;
    const fd=new FormData();fd.append('repo_id',repoId);
    fetchJSON(API.enqueue,{method:'POST',body:fd})
      .then(r=>alert(r.message||r.error||'Unknown')); }

  /* actions inside tasks table ------------------------------------*/
  const id=e.target.dataset.id;
  if(!id) return;
  if(e.target.classList.contains('kill')){
    fetchJSON(API.kill,{method:'POST'});
  }else if(e.target.classList.contains('cancel')){
    const fd=new FormData();fd.append('job_id',id);
    fetchJSON(API.remove,{method:'POST',body:fd});
  }else if(e.target.classList.contains('log')){
    openLogs(id);
  }else if(e.target.classList.contains('dl')){
    location=API.dl(id);
  }
});

/* ---------- tasks refresh ---------- */
function loadTasks(){
  fetchJSON(API.tasks).then(all=>{
    const map={}; all.forEach(t=>{
      (map[t.repo_id]=map[t.repo_id]||[]).push(t);
    });
    for(const card of $$('.repo-card')){
      const repoId = card.dataset.repo;
      const tbody  = card.querySelector('tbody');
      tbody.innerHTML='';
      (map[repoId]||[]).forEach(t=>{
        const tr=document.createElement('tr');
        tr.innerHTML=`
          <td>${t.id.slice(0,8)}</td>
          <td>${badge(t.status)}</td>
          <td>${new Date(t.created_at||t.started_at||0).toLocaleString()}</td>
          <td>
            ${t.status==='running' ? `<button class="kill"  data-id="${t.id}">Kill</button>`:''}
            ${t.status==='queued'  ? `<button class="cancel" data-id="${t.id}">Cancel</button>`:''}
            <button class="log" data-id="${t.id}">Logs</button>
            ${t.status==='finished'&&t.has_content ? `<button class="dl" data-id="${t.id}">Download</button>`:''}
          </td>`;
        tbody.appendChild(tr);
      });
    }
  });
}

/* ---------- metrics ---------- */
function loadMetrics(){
  fetchJSON(API.metrics.cpu).then(d=>$('cpuUsage').textContent = d.cpu_percent.toFixed(0)+'%');
  fetchJSON(API.metrics.memory).then(d=>$('memUsage').textContent= d.percent.toFixed(0)+'%');
  fetchJSON(API.metrics.disk).then(d=>$('diskUsage').textContent = d.percent.toFixed(0)+'%');
  fetchJSON(API.current).then(d=>{
    $('currentStatus').textContent = d.id ? `Running ${d.repo_id||''}` : 'Idle';
  });
}

/* ---------- logs dialog ---------- */
let timer=0,last=0;
function openLogs(id){
  clearInterval(timer); last=0;
  $('logPre').textContent='Loading…';
  $('logDlg').showModal();
  timer=setInterval(()=>fetchJSON(API.logs(id,last)).then(rows=>{
    rows.forEach(r=>{
      $('logPre').append(`[${r.timestamp}] ${r.line}\n`);
      last=r.id;
    });
    $('logPre').scrollTop=$('logPre').scrollHeight;
  }),1000);
}
$('closeLogBtn').onclick=()=>{ $('logDlg').close();clearInterval(timer); };

/* ---------- bootstrap ---------- */
fetchJSON(API.repos).then(renderRepos).then(loadTasks);
setInterval(loadTasks,4000);
loadMetrics();setInterval(loadMetrics,5000);
