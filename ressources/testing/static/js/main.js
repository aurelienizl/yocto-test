document.addEventListener('alpine:init', () => {
    Alpine.data('fileManager', () => ({
  
      // ── State ──
      path: '',
      items: [],
      history: [],
      future: [],
      toasts: [],
      uploads: [],
      clipboard: null,            // holds the last-copied item
      contextMenu: { visible:false, x:0, y:0, item:null },
  
      // ── Lifecycle ──
      init() {
        this.load();
        setInterval(() => this.load(), 1000);
      },
  
      // ── Toast helpers ──
      toast(msg, type='info') {
        const id = Date.now() + Math.random();
        this.toasts.push({ msg, type, id });
        setTimeout(() => this.toasts = this.toasts.filter(t => t.id !== id), 4000);
      },
      removeToast(id) {
        this.toasts = this.toasts.filter(t => t.id !== id);
      },
  
      // ── Fetch helper ──
      fetchJSON(url, opts={}) {
        const ctl = new AbortController();
        opts.signal = ctl.signal;
        return Promise.race([
          fetch(url, opts),
          new Promise((_, rj) => setTimeout(() => ctl.abort(), 5000))
        ]).then(r => r.json());
      },
  
      // ── Load directory ──
      load() {
        this.fetchJSON(`/api/list?path=${encodeURIComponent(this.path)}`)
          .then(r => {
            if (r.status === 'success') {
              this.items = r.data.map(it => ({
                ...it,
                relativePath: this.path ? `${this.path}/${it.name}` : it.name
              }));
            } else {
              this.toast(r.message,'error');
            }
          })
          .catch(() => this.toast('Server timeout','error'));
      },
  
      // ── Navigation ──
      navigate(p) {
        this.history.push(this.path);
        this.future = [];
        this.path = p;
        this.hideMenu();
        this.load();
      },
      back() {
        if (!this.history.length) return;
        this.future.push(this.path);
        this.path = this.history.pop();
        this.load();
      },
      forward() {
        if (!this.future.length) return;
        this.history.push(this.path);
        this.path = this.future.pop();
        this.load();
      },
  
      // ── CRUD ──
      createFolder() {
        const n = prompt('New folder name:'); if (!n) return;
        this.fetchJSON('/api/create-folder',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ path:this.path, name:n })
        }).then(r => {
          r.status==='success'
            ? (this.toast(r.message,'success'),this.load())
            : this.toast(r.message,'error');
        });
      },
      deleteItem(it) {
        if (!confirm(`Delete "${it.name}"?`)) return;
        this.fetchJSON('/api/delete',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ path:this.path, name:it.name })
        }).then(r => {
          r.status==='success'
            ? (this.toast(r.message,'success'),this.load())
            : this.toast(r.message,'error');
        });
      },
      renameItem(it) {
        const nn = prompt('Rename to:',it.name); if (!nn||nn===it.name) return;
        this.fetchJSON('/api/rename',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ path:this.path, old:it.name, new:nn })
        }).then(r => {
          r.status==='success'
            ? (this.toast(r.message,'success'),this.load())
            : this.toast(r.message,'error');
        });
      },
      download(it) {
        window.location = `/api/download?path=${encodeURIComponent(this.path)}&name=${encodeURIComponent(it.name)}`;
      },
      moveItem(it) {
        const tgt = prompt('Target folder path:',this.path); if(tgt===null) return;
        this.fetchJSON('/api/move',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ path:this.path, name:it.name, target:tgt.trim() })
        }).then(r => {
          r.status==='success'
            ? (this.toast(r.message,'success'),this.load())
            : this.toast(r.message,'error');
        });
      },
  
      // ── Copy / Paste ──
      copyItem(it) {
        this.clipboard = it;
        this.toast(`Copied "${it.name}"`,'info');
      },
      pasteItem() {
        if (!this.clipboard) {
          this.toast('Nothing to paste','error');
          return;
        }
        const srcDir = this.clipboard.relativePath.split('/').slice(0,-1).join('/');
        this.fetchJSON('/api/copy',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({
            path: srcDir,
            name: this.clipboard.name,
            target: this.path
          })
        }).then(r => {
          r.status==='success'
            ? (this.toast(r.message,'success'),this.load())
            : this.toast(r.message,'error');
        });
        this.clipboard = null;
      },
  
      // ── Context Menu ──
      showMenu(evt,it) {
        this.contextMenu = {
          visible: true,
          x: evt.clientX,
          y: evt.clientY,
          item: it
        };
      },
      hideMenu() {
        this.contextMenu.visible = false;
        this.contextMenu.item = null;
      },
  
      // ── Drag & Drop Upload ──
      onDragOver(e){ e.dataTransfer.dropEffect='copy'; },
      onDrop(e){ Array.from(e.dataTransfer.files).forEach(f=>this.uploadFile(f)); },
      uploadFile(file) {
        const id = Date.now()+'-'+file.name;
        this.uploads.push({ id,name:file.name,progress:0 });
        const xhr=new XMLHttpRequest();
        xhr.open('POST','/api/upload');
        xhr.upload.onprogress=ev=>{
          const u=this.uploads.find(x=>x.id===id);
          if(u&&ev.lengthComputable) u.progress=Math.round(ev.loaded/ev.total*100);
        };
        xhr.onload=()=>{
          this.uploads=this.uploads.filter(x=>x.id!==id);
          this.load();
          try{const r=JSON.parse(xhr.response);this.toast(r.message,r.status==='success'?'success':'error');}
          catch{this.toast('Upload failed','error');}
        };
        xhr.onerror=()=>this.toast('Upload error','error');
        const fd=new FormData();
        fd.append('path',this.path);
        fd.append('file',file);
        xhr.send(fd);
      },
  
      // ── Formatters ──
      fmtSize(b){return(b/1024).toFixed(2)+' KB';},
      fmtTime(ts){return new Date(ts*1000).toLocaleString();}
  
    }));
  });
  