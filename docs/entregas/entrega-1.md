# Entrega 1 — Arquitetura e Escopo

- **Decisão tecnológica documentada** (no [README principal](../../README.md))
- **Repositório organizado** com README mínimo
- **Modelagem do estado central em memória**
- **Protocolo de comunicação definido** (em [`protocolo.md`](../protocolo.md))
- **Esqueleto do servidor base** rodando na porta fixa, com o framework alvo
- **Validações básicas de formato e regras de negócio**

Específicos da Equipe 08 (Gestor de Documentos Normativos):

- Mapear a escuta nativa em porta fixa e definir o **roteamento de endpoints**
  para `GET`, `PUT` e `DIR`.
- Estruturar a **pasta física de manuais** no servidor e as **regras para
  leitura concorrente**.
- Definir o **formato de saída do `DIR`**, incluindo metadados (nome,
  tamanho em bytes, data de modificação).
- **Validar o upload local isolado** de um arquivo de texto simples via `PUT`,
  mesmo sem lógica de concorrência ainda.

---

## ✅ Itens entregues

| Item | Onde está |
|---|---|
| Servidor FastAPI + uvicorn na porta fixa **8000** | [`backend/app/main.py`](../../backend/app/main.py) |
| `/health` (resposta a conexão de teste) | [`backend/app/main.py`](../../backend/app/main.py) |
| `GET /api/files` (DIR) com metadados | [`backend/app/routes/files.py`](../../backend/app/routes/files.py) |
| `PUT /api/files/{nome}` (upload isolado) | [`backend/app/routes/files.py`](../../backend/app/routes/files.py) |
| Modelo Pydantic `FileMeta` / `DirResponse` | [`backend/app/models.py`](../../backend/app/models.py) |
| Estado em memória (`files_meta: dict`) | [`backend/app/storage.py`](../../backend/app/storage.py) |
| Validações (nome, extensão, tamanho, vazio) | [`backend/app/storage.py`](../../backend/app/storage.py) |
| Configuração centralizada (porta, storage, limites) | [`backend/app/config.py`](../../backend/app/config.py) |
| Pasta física dos manuais | [`backend/storage/`](../../backend/storage/) |
| Protocolo REST documentado | [`docs/protocolo.md`](../protocolo.md) |
| Suíte de testes (9 testes, pytest) | [`tests/test_api.py`](../../tests/test_api.py) |

---

## Modelagem do estado central em memória

O **filesystem** (`backend/storage/`) é a **fonte da verdade**; o índice em
memória é construído no *startup* (varredura da pasta) e atualizado a cada `PUT`.

| Estrutura | Tipo | Papel |
|---|---|---|
| `files_meta` | `dict[str, FileMeta]` | índice de metadados por nome (nome, tamanho, data, tipo) |

Implementação em [`backend/app/storage.py`](../../backend/app/storage.py).

---

## Endpoints implementados

### `GET /health`
Health-check.
```bash
$ curl http://localhost:8000/health
{"status":"ok"}
```

### `GET /api/files` — DIR
Lista os documentos com metadados (nome, tamanho em bytes, data de modificação, tipo):
```bash
$ curl http://localhost:8000/api/files
{
  "count": 1,
  "files": [
    {
      "name": "regulamento.txt",
      "size_bytes": 1024,
      "modified_at": "2026-06-06T12:34:56+00:00",
      "content_type": "text/plain"
    }
  ]
}
```

### `PUT /api/files/{nome}` — PUT (upload isolado)
O corpo da requisição é o conteúdo do arquivo. Resposta `201` com os metadados:
```bash
$ curl -X PUT --data-binary @regulamento.txt \
       http://localhost:8000/api/files/regulamento.txt
{"name":"regulamento.txt","size_bytes":1024,"modified_at":"...","content_type":"text/plain"}
```

Especificação completa do contrato REST em [`protocolo.md`](../protocolo.md).

---

## Validações implementadas

| Regra | Status | Quando dispara |
|---|---|---|
| Nome seguro (anti *path traversal*) | `400` | nome vazio, com `/`, `\` ou começando por `.` |
| Conteúdo não vazio | `400` | `PUT` com corpo vazio |
| Tamanho máximo (5 MB) | `413` | upload maior que `MAX_FILE_SIZE` |
| Somente texto (`.txt`, `.md`) | `415` | extensão fora de `ALLOWED_EXTENSIONS` |

---

## Estratégia de concorrência

- **Read-Write Lock por arquivo** (`RWLock`): N leitores simultâneos OR 1
  escritor exclusivo — portado direto do servidor de sockets da atividade
  anterior.
- **`GET` (download) e `DIR`** rodam como funções síncronas (`def`) → o
  Starlette as executa no *threadpool*; vários `GET` baixam o mesmo arquivo
  em paralelo segurando o *read-lock*.
- **`PUT`** permanece `async` para ler o corpo da requisição; a gravação
  bloqueante (*write-lock* + disco) é delegada via `run_in_threadpool`,
  sem travar o *event loop*.

---

## Verificação

### Pelo navegador (Swagger UI)
Subir o servidor e abrir `http://localhost:8000/docs` — usar os botões
*Try it out* para `GET /api/files` e `PUT /api/files/{filename}`.

### Pela linha de comando
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/files

# upload válido (sucesso 201)
curl -X PUT --data-binary @regulamento.txt \
     http://localhost:8000/api/files/regulamento.txt

# caminhos de erro
curl -X PUT --data-binary "x" http://localhost:8000/api/files/binario.exe    # 415
curl -X PUT http://localhost:8000/api/files/vazio.txt                        # 400
```

### Testes automatizados
A partir da raiz do projeto:
```bash
pytest -v
```
Os 9 testes cobrem `/health`, `DIR` (vazio, após PUT, com metadados),
`PUT` (novo, sobrescrita) e as quatro validações.
