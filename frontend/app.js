function gestorApp() {
  return {
    // --- estado ---
    files: [],            // lista atual de documentos (DIR)
    uploading: false,     // upload em andamento
    uploadPct: 0,         // % do upload atual
    downloads: {},        // { nome: % } — downloads ativos
    toasts: [],           // lista de notificações na tela
    online: false,        // conexão SSE viva?
    dragging: false,      // arquivo sendo arrastado sobre a área de drop
    _es: null,            // referência ao EventSource

    connect() {
      this.loadList();
      this._es = new EventSource("/api/files/events");
      this._es.onopen = () => { this.online = true; };
      this._es.onerror = () => { this.online = false; };
      // Atualização silenciosa da lista quando algo muda (este ou outro cliente).
      this._es.addEventListener("file_updated", () => this.loadList());
    },

    // --- DIR ---
    async loadList() {
      try {
        const r = await fetch("/api/files");
        if (!r.ok) throw new Error("lista indisponível");
        this.files = (await r.json()).files;
      } catch (e) {
        this.toast("error", "falha ao listar: " + e.message);
      }
    },

    // --- PUT (XHR para ter progresso real de upload) ---
    onFile(e) {
      const f = e.target.files[0];
      if (f) this.upload(f);
      e.target.value = "";
    },

    onDrop(e) {
      this.dragging = false;
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) this.upload(f);
    },

    upload(file) {
      const ext = "." + file.name.toLowerCase().split(".").pop();
      if (![".txt", ".md", ".rst", ".docx", ".pdf", ".csv", ".json", ".xml"].includes(ext))
        return this.toast("error", "extensão não permitida");
      if (file.size === 0)
        return this.toast("error", "arquivo vazio");
      if (file.size > 5 * 1024 * 1024)
        return this.toast("error", "arquivo > 5 MB");

      this.uploading = true;
      this.uploadPct = 0;

      const xhr = new XMLHttpRequest();
      xhr.upload.onprogress = (ev) => {
        if (ev.lengthComputable) this.uploadPct = (ev.loaded / ev.total) * 100;
      };
      xhr.onload = () => {
        this.uploading = false;
        if (xhr.status >= 200 && xhr.status < 300) {
          this.toast("ok", `enviado: ${file.name}`);
          // SSE vai re-disparar loadList(); este é um fallback otimista.
          this.loadList();
        } else {
          let detail = "falha no upload";
          try { detail = JSON.parse(xhr.responseText).detail || detail; } catch {}
          this.toast("error", `${xhr.status}: ${detail}`);
        }
      };
      xhr.onerror = () => {
        this.uploading = false;
        this.toast("error", "falha de rede no upload");
      };
      xhr.open("PUT", `/api/files/${encodeURIComponent(file.name)}`);
      xhr.setRequestHeader("Content-Type", "text/plain");
      xhr.send(file);
    },

    async download(name) {
      this.downloads = { ...this.downloads, [name]: 0.01 };
      try {
        const r = await fetch(`/api/files/${encodeURIComponent(name)}`);
        if (!r.ok) {
          let detail = "falha no download";
          try { detail = (await r.json()).detail || detail; } catch {}
          throw { status: r.status, detail };
        }
        const total = +r.headers.get("Content-Length") || 0;
        const reader = r.body.getReader();
        const chunks = [];
        let received = 0;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          chunks.push(value);
          received += value.length;
          const pct = total ? (received / total) * 100 : 50;
          this.downloads = { ...this.downloads, [name]: pct };
        }

        const blob = new Blob(chunks, { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = Object.assign(document.createElement("a"), { href: url, download: name });
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        this.toast("ok", `baixado: ${name}`);
      } catch (e) {
        this.toast("error", e.detail ? `${e.status}: ${e.detail}` : "falha no download");
      } finally {
        const next = { ...this.downloads };
        delete next[name];
        this.downloads = next;
      }
    },

    toast(kind, msg) {
      const id = Math.random().toString(36).slice(2);
      this.toasts = [...this.toasts, { id, kind, msg }];
      setTimeout(() => {
        this.toasts = this.toasts.filter((t) => t.id !== id);
      }, 4000);
    },

    // --- formatadores ---
    formatBytes(n) {
      if (n < 1024) return `${n} B`;
      if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
      return `${(n / 1024 / 1024).toFixed(2)} MB`;
    },
    formatDate(iso) {
      try { return new Date(iso).toLocaleString("pt-BR"); }
      catch { return iso; }
    },
  };
}
