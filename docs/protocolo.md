# Protocolo de Comunicação — Gestor de Documentos Normativos

Especificação do contrato REST do servidor. Base: HTTP/1.1, payloads JSON
(exceto o corpo de upload/download, que é o conteúdo bruto do documento).

Este documento descreve **o protocolo completo** (DIR, PUT, GET). O status
de cada endpoint indica se está implementado nesta versão do servidor ou
apenas documentado.

## Evolução: sockets TCP → REST

A atividade anterior usava um protocolo textual sobre TCP, delimitado por `\n`:

| Ação | Cliente enviava | Servidor respondia |
|---|---|---|
| Listar | `DIR\n` | `OK <n>\n<nome1>\n...` |
| Upload | `PUT <nome> <bytes>\n<conteúdo>` | `OK\n` |
| Download | `GET <nome>\n` | `OK <bytes>\n<conteúdo>` |
| Erro | — | `ERR <mensagem>\n` |

Na versão FastAPI, cada comando vira um endpoint REST com semântica HTTP:

| Comando | Método + rota | Status |
|---|---|---|
| `DIR` | `GET /api/files` | ✅ implementado |
| `PUT <nome>` | `PUT /api/files/{nome}` | ✅ implementado (upload isolado) |
| `GET <nome>` | `GET /api/files/{nome}` | 📄 documentado |

---

## Endpoints

### `GET /health`
Health-check. Resposta `200`:
```json
{ "status": "ok" }
```

### `GET /api/files` — DIR
Lista todos os documentos com metadados. Resposta `200` (`DirResponse`):
```json
{
  "count": 2,
  "files": [
    { "name": "manual.md",       "size_bytes": 320,  "modified_at": "2026-06-06T12:00:00+00:00", "content_type": "text/markdown" },
    { "name": "regulamento.txt", "size_bytes": 1024, "modified_at": "2026-06-06T12:34:56+00:00", "content_type": "text/plain" }
  ]
}
```
Campos de `FileMeta`:

| Campo | Tipo | Descrição |
|---|---|---|
| `name` | string | nome do arquivo |
| `size_bytes` | int | tamanho em bytes |
| `modified_at` | string (ISO 8601, UTC) | data/hora da última modificação |
| `content_type` | string | `text/plain` ou `text/markdown` |

### `PUT /api/files/{nome}` — PUT *(upload isolado)*
Cria ou sobrescreve um documento. **Corpo da requisição = conteúdo do arquivo**
(`Content-Type: text/plain`).
- `201`: sucesso; corpo = `FileMeta` do arquivo gravado.
- `400`: nome inválido **ou** conteúdo vazio.
- `413`: conteúdo acima do tamanho máximo (5 MB).
- `415`: extensão não permitida (apenas `.txt`, `.md`).

Idempotência: reenviar o mesmo `{nome}` sobrescreve o conteúdo.
O PUT atende uma requisição por vez nesta versão. O controle de concorrência
(escrita exclusiva enquanto leitores ativos terminam) está documentado abaixo
em [Regras de validação](#regras-de-validação).

### `GET /api/files/{nome}` — GET *(documentado, ainda não implementado)*
Baixa o conteúdo do documento.
- `200`: corpo = conteúdo; cabeçalho `Content-Disposition: attachment; filename="<nome>"`; `Content-Type: text/plain; charset=utf-8`.
- `400`: nome inválido. `404`: arquivo não encontrado.

Estratégia desenhada: função síncrona (`def`) executada pelo Starlette no
*threadpool*, permitindo que múltiplos `GET` corram em paralelo no mesmo
arquivo, todos segurando o *read-lock* do `RWLock` desse arquivo.

---

## Erros

Formato padrão do FastAPI:
```json
{ "detail": "mensagem explicativa" }
```

| Status | Quando |
|---|---|
| `400 Bad Request` | nome inseguro (vazio, `/`, `\`, ponto inicial) ou conteúdo vazio |
| `404 Not Found` | `GET` de arquivo inexistente |
| `413 Payload Too Large` | upload acima de 5 MB |
| `415 Unsupported Media Type` | extensão fora de `{.txt, .md}` |

---

## Regras de validação

1. **Nome seguro** — rejeita vazio, separadores de caminho (`/`, `\`) e ponto
   inicial, evitando *path traversal* (ex.: `../../etc/passwd`).
2. **Somente texto** — extensão deve estar em `ALLOWED_EXTENSIONS` (`.txt`, `.md`).
3. **Tamanho** — `0 < tamanho <= 5 MB`.
4. **Concorrência** — leitura compartilhada (vários `GET` simultâneos),
   escrita exclusiva (`PUT` aguarda leitores ativos), via `RWLock` por arquivo.
