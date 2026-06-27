# Entrega 3 — Interface, Testes e Finalização

A Entrega 3 é a fase de **Interface**: o usuário interage com o sistema pela
GUI, não mais pelo terminal. Os requisitos de "feedback visual em tempo real"
e "downloads simultâneos do mesmo arquivo" passam a ser demonstrados pela UI.

---

## Escopo

Requisitos:

- Desenvolver a **interface gráfica** do cliente como explorador visual de manuais técnicos
  (lista de arquivos, botão de upload, botão de download).
- Implementar o **comando `GET` integrado à interface**: clique no arquivo dispara
  download em blocos do servidor, com **barra de progresso visível**.
- Mapear as **travas de leitura paralela concorrente** no servidor: múltiplos
  usuários devem conseguir baixar o mesmo manual simultaneamente sem bloqueio mútuo.
- Incluir **barras de progresso** na tela do cliente para uploads (`PUT`) e downloads (`GET`),
  refletindo o avanço real do fluxo de bytes.
- Atualizar o README com instruções de como abrir a interface, fazer upload de um manual
  e simular downloads simultâneos do mesmo arquivo.

---

## ✅ Itens entregues

| Item | Onde está |
|---|---|
| Interface gráfica do cliente (explorador visual) | [`backend/static/index.html`](../../backend/static/index.html) |
| Lógica Alpine (estado, handlers, SSE) | [`backend/static/app.js`](../../backend/static/app.js) |
| Estilo (dark, responsivo) | [`backend/static/styles.css`](../../backend/static/styles.css) |
| Servida pelo FastAPI em `/ui/` (deploy único) | [`backend/app/main.py`](../../backend/app/main.py) |
| Comando `GET` integrado à UI (clique → download) | [`backend/static/app.js`](../../backend/static/app.js) (função `download`) |
| **Barra de progresso** real para upload (PUT via XHR) | [`backend/static/app.js`](../../backend/static/app.js) (função `upload`) |
| **Barra de progresso** real para download (fetch + stream + Content-Length) | [`backend/static/app.js`](../../backend/static/app.js) (função `download`) |
| Travas de leitura paralela no servidor (downloads simultâneos) | [`backend/app/locks.py`](../../backend/app/locks.py) (RWLock — pronto desde a E2) |
| Reatividade em tempo real entre clientes (SSE) | [`backend/app/routes/files.py`](../../backend/app/routes/files.py) (`/events` + `_broadcast`) |
| Tratamento de erros na interface (toasts) | [`backend/static/app.js`](../../backend/static/app.js) (função `toast`) |
| Validação client-side (extensão, tamanho, vazio) | [`backend/static/app.js`](../../backend/static/app.js) (função `upload`) |
| Testes (15 testes — inclui UI e broadcast SSE) | [`tests/test_api.py`](../../tests/test_api.py) |

---

## Estratégia de reatividade

Dois planos diferentes resolvidos em conjunto, mantendo o deploy único:

| Plano | Mecanismo | Implementação |
|---|---|---|
| **Reatividade local** (mudanças de estado → re-render automático da tela) | Alpine.js 3 via CDN | `x-data`, `x-for`, `@click`, `:disabled`, `x-show` |
| **Reatividade entre clientes** (upload de um usuário → outras abas atualizam) | Server-Sent Events (SSE) | endpoint `/api/files/events` (StreamingResponse) + `EventSource` no browser |

### Como o SSE funciona aqui

1. O navegador abre `new EventSource('/api/files/events')` — uma conexão HTTP
   que fica aberta indefinidamente, com `media_type: text/event-stream`.
2. O servidor mantém uma lista `_subscribers: list[asyncio.Queue]`. Cada
   conexão SSE ganha sua própria `Queue`.
3. Quando um `PUT` é bem-sucedido, `_broadcast("file_updated", filename)`
   distribui o evento para todas as queues.
4. Cada cliente conectado recebe `event: file_updated\ndata: <nome>\n\n`
   e dispara `loadList()` automaticamente.
5. Se a conexão cair, o browser reconecta sozinho — sem código extra.

Latência observada: < 100ms entre o término do PUT e a UI de outras abas
atualizar.

---

## Como abrir a interface

```bash
cd backend
uvicorn app.main:app --port 8000
```

Acesse **http://localhost:8000/ui/** no navegador.

A tela traz:
- Indicador de **status SSE** ("● conectado" / "● offline") no canto direito do header.
- Área de **upload** com input de arquivo + barra de progresso.
- **Lista de manuais** (DIR) com colunas Nome, Tamanho, Modificado e Ações.
- **Botão Baixar** em cada linha + barra de progresso de download.
- **Toasts** auto-dismiss para confirmações e erros.

---

## Verificação

### Fluxo manual na UI

1. Abrir `http://localhost:8000/ui/` — lista vazia + badge "● conectado".
2. Clicar no input de arquivo → selecionar um `.txt` ou `.md` → barra de upload evolui 0% → 100% → toast verde "enviado: ...".
3. Lista re-renderiza com o arquivo aparecendo (instantâneo via SSE).
4. Clicar **Baixar** → barra de download evolui → arquivo baixa no navegador → toast verde "baixado: ...".
5. Testar caminhos de erro:
   - Tentar enviar `binario.exe` → toast vermelho "415: extensão não permitida".
   - Tentar arquivo > 5 MB → toast vermelho "413: ...".
   - Tentar arquivo vazio → toast vermelho "400: conteúdo vazio".

### Reatividade entre abas

1. Abrir **duas abas** em `http://localhost:8000/ui/`.
2. Em uma das abas, fazer um upload.
3. A **outra aba atualiza a lista em < 100ms** — sem nenhum clique do usuário.
4. Nos logs do servidor: `SSE broadcast: file_updated=<nome> (2 subscriber(s))`.

### Downloads simultâneos do mesmo arquivo

1. Abrir **3 abas** em `/ui/`.
2. Em cada aba, clicar **Baixar** no mesmo arquivo em sequência rápida.
3. As 3 barras de progresso evoluem em paralelo (sem uma esperar a outra).
4. Nos logs:
   ```
   gestor.files | GET regulamento.txt — N bytes  (3 vezes próximas em tempo)
   gestor.http  | GET /api/files/regulamento.txt -> 200 (...ms) [cliente=...]  (3x)
   ```
5. O `RWLock` (read-lock) permite os 3 leitores simultaneamente — o servidor
   não trava nem serializa.