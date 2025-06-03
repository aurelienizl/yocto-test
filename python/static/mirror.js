/************************************************************************
 * BuildOS Mirror Manager – delete-button, global paste, safe copy     *
 ************************************************************************/
import { APPS } from './apps.js';

/* ---------- nav ---------------------------------------------------- */
(function nav(){
  const nav=document.getElementById('nav');
  APPS.forEach(a=>{
    const l=document.createElement('a'); l.href=a.href; l.textContent=a.name;
    if(location.pathname===a.href) l.style.opacity='1';
    nav.appendChild(l);
  });
}());

/* ---------- dom refs ------------------------------------------------ */
const $=s=>document.querySelector(s);
const refs={
  back:$('#backBtn'), fwd:$('#fwdBtn'), up:$('#upBtn'),
  crumbs:$('#crumbs'), newBtn:$('#newBtn'),
  upload:$('#uploadBtn'), fileIn:$('#fileInput'),
  tbody:$('#list tbody'), ctx:$('#ctx'), toasts:$('#toasts')
};

/* ---------- state --------------------------------------------------- */
let path='', items=[], history=[], future=[], clipboard=null,
    okPath='', okItems=[], pollId=null;

/* ---------- helpers ------------------------------------------------- */
const BASE=document.body.dataset.base||'';
const api=p=>`${BASE}/${p}`.replace(/\/+/g,'/').replace(/\/\?/,'?');
const fmt=b=>(b/1024).toFixed(1)+' KB';
const fmtDate=ts=>new Date(ts*1000).toLocaleString();
const post=d=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
function toast(msg,type='info'){ const d=document.createElement('div');d.className=`toast ${type}`;d.textContent=msg;refs.toasts.appendChild(d);setTimeout(()=>d.remove(),4000);d.onclick=()=>d.remove();}
function fetchJSON(url,opts={}){
  const ctl=new AbortController();opts.signal=ctl.signal;
  return Promise.race([fetch(url,opts),new Promise((_,r)=>setTimeout(()=>{ctl.abort();r(new Error('timeout'));},5000))])
    .then(r=>r.json()).catch(e=>({status:'error',message:e.message||'network'}));
}

/* ---------- rendering ----------------------------------------------- */
function render(){
  refs.tbody.innerHTML='';
  items.sort((a,b)=>Number(b.is_dir)-Number(a.is_dir)||a.name.localeCompare(b.name))
    .forEach(it=>{
      const tr=document.createElement('tr');
      tr.dataset.name=it.name; tr.dataset.dir=it.is_dir;
      tr.innerHTML=`<td class="name">${it.is_dir?'📁':'📄'} ${it.name}</td>
                    <td>${it.is_dir?'—':fmt(it.size)}</td>
                    <td>${fmtDate(it.last_modified)}</td>
                    <td><button data-del="1">✕</button></td>`;
      refs.tbody.appendChild(tr);
    });
  refs.crumbs.textContent='/'+path;
  refs.back.disabled=!history.length;
  refs.fwd.disabled=!future.length;
}

/* ---------- directory load (rollback on error) ---------------------- */
function load(showToast,revert){
  fetchJSON(api(`list?path=${encodeURIComponent(path)}`))
    .then(r=>{
      if(r.status==='success'){
        items=r.data.map(it=>({...it,rel:path?`${path}/${it.name}`:it.name}));
        okPath=path; okItems=items; render();
      }else{
        if(showToast) toast(r.message,'error');
        if(revert){ path=okPath; items=okItems; history.pop(); render(); }
      }
    });
}

/* ---------- navigation --------------------------------------------- */
const navTo=p=>{history.push(path);future=[];path=p;load(true,true);};
const back =()=>{if(!history.length)return;future.push(path);path=history.pop();load(true,false);};
const fwd  =()=>{if(!future.length)return;history.push(path);path=future.pop();load(true,false);};
const up   =()=>{if(!path)return;navTo(path.split('/').slice(0,-1).join('/'));};

/* ---------- CRUD ---------------------------------------------------- */
function newFolder(){
  const n=prompt('Folder name:');if(!n)return;
  fetchJSON(api('create-folder'),post({path,name:n})).then(r=>r.status==='success'?(toast(r.message,'success'),load()):toast(r.message,'error'));
}
function del(name){
  if(!confirm(`Delete "${name}"?`))return;
  fetchJSON(api('delete'),post({path,name})).then(r=>r.status==='success'?(toast(r.message,'success'),load()):toast(r.message,'error'));
}
function rename(name){
  const nn=prompt('Rename to:',name);if(!nn||nn===name)return;
  fetchJSON(api('rename'),post({path,old:name,new:nn})).then(r=>r.status==='success'?(toast(r.message,'success'),load()):toast(r.message,'error'));
}
const download=name=>location=api(`download?path=${encodeURIComponent(path)}&name=${encodeURIComponent(name)}`);
function nextCopyName(n){
  const ext=n.includes('.')?'.'+n.split('.').pop():'';
  const base=ext? n.slice(0,-ext.length):n;
  let i=1, candidate; do{candidate=`${base} copy${i>1?' '+i:''}${ext}`; i++;}while(items.some(it=>it.name===candidate)); return candidate;
}
function copy(name){                     // remember dir + name
  clipboard = { dir: path, name };
  toast(`Copied "${name}"`, 'info');
}

function paste(){
  if (!clipboard){ toast('Clipboard empty', 'error'); return; }

  fetchJSON(api('copy'), post({
    path  : clipboard.dir,         // source directory
    name  : clipboard.name,        // item
    target: path                   // destination directory
  })).then(r => {
    if (r.status === 'success'){
      toast(r.message, 'success');
      load();
    } else {
      toast(r.message, 'error');   // “Destination exists”, etc.
    }
  });

  clipboard = null;
}

function upload(files){[...files].forEach(f=>{const fd=new FormData();fd.append('path',path);fd.append('file',f);fetch(api('upload'),{method:'POST',body:fd}).then(r=>r.json()).then(r=>r.status==='success'?(toast(r.message,'success'),load()):toast(r.message,'error'))})}

/* ---------- context menu ------------------------------------------- */
function hideCtx(){refs.ctx.hidden=true;}
function showCtx(e,tr){
  refs.ctx.innerHTML='';
  const name=tr?.dataset.name, isDir=tr?.dataset.dir==='true';
  if(name){
    add('Open',isDir,()=>navTo(path?`${path}/${name}`:name));
    add('Download',!isDir,()=>download(name));
    add('Copy',true,()=>copy(name));
    add('Paste',!!clipboard,paste);
    add('Rename',true,()=>rename(name));
    add('Delete',true,()=>del(name),'del');
  }else{
    add('Paste',!!clipboard,paste);
  }
  refs.ctx.style.left=e.clientX+'px';refs.ctx.style.top=e.clientY+'px';
  refs.ctx.hidden=false; e.preventDefault();
}
function add(label,enabled,fn,extra=''){
  const li=document.createElement('li');li.textContent=label;
  if(enabled)li.onclick=()=>{fn();hideCtx();};else li.className='disabled';
  if(extra)li.classList.add(extra);refs.ctx.appendChild(li);
}
document.addEventListener('click',hideCtx);

/* ---------- table & page events ------------------------------------ */
refs.tbody.ondblclick=e=>{const tr=e.target.closest('tr'); if(tr){const {name,dir}=tr.dataset; dir==='true'?navTo(path?`${path}/${name}`:name):download(name);} };
refs.tbody.onclick=e=>{if('del' in e.target.dataset){const name=e.target.closest('tr').dataset.name;del(name);} };
refs.tbody.oncontextmenu=e=>showCtx(e,e.target.closest('tr'));
document.body.oncontextmenu=e=>{if(!e.target.closest('tr'))showCtx(e,null);} /* blank area */

refs.back.onclick=back; refs.fwd.onclick=fwd; refs.up.onclick=up;
refs.newBtn.onclick=newFolder; refs.upload.onclick=()=>refs.fileIn.click();
refs.fileIn.onchange=e=>upload(e.target.files);
document.body.ondragover=e=>e.preventDefault();
document.body.ondrop=e=>{e.preventDefault();upload(e.dataTransfer.files);};

/* ---------- polling & init ----------------------------------------- */
pollId=setInterval(()=>load(false,false),3000);
load(true,false);
