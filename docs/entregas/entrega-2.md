# Entrega 2 — Comunicação e Core

A Entrega 2 é a fase de **Comunicação e Core**: o servidor multicliente entra
em operação, os comandos principais ficam totalmente funcionais via terminal,
a lógica de negócio central é implementada em memória e o servidor passa a
emitir logs operacionais detalhados.

> ℹ️ Para a descrição geral do projeto, decisão tecnológica, integrantes e
> instruções de execução, ver o [README principal](../../README.md).
> Para o contrato REST completo, ver [`docs/protocolo.md`](../protocolo.md).

---

## Escopo

Requisitos gerais (todas as equipes):

- **Servidor multicliente funcional** rodando ininterruptamente no framework-alvo.
- **Comandos principais implementados via console/terminal** (sem GUI ainda).
- **Lógica de negócio central codificada** em memória.
- **Comunicação concorrente ativa**: HTTP com threads/async respondendo sem bloquear.
- **Logs operacionais** estruturados no console.
- **README atualizado** com instruções de execução e testes.

Específicos da Equipe 08 (Gestor de Documentos Normativos):

- Configurar o motor do framework para operar com **suporte a conexões paralelas**.
- Implementar o endpoint do comando **`PUT`** (salvar fisicamente em disco na estrutura definida na E1).
- Desenvolver a lógica do comando **`DIR`** (listar com nome, tamanho em bytes, data de modificação).
- Exibir **logs operacionais detalhados** no console para cada conexão, upload e listagem.
- Atualizar o README com **instruções de `PUT` e `DIR`** via cliente HTTP.

Também cobrimos nesta entrega (parte do escopo total do PDF principal):

- **`GET`** (download) — comando principal do protocolo do sistema.
- **Concorrência de leitura via `RWLock`** — *"vários clientes podem baixar o
  mesmo manual ao mesmo tempo"* (PDF do projeto).

---

## ✅ Itens entregues

| Item | Onde está |
|---|---|
| Conexões paralelas (async/threadpool do Starlette) | [`backend/app/routes/files.py`](../../backend/app/routes/files.py) |
| Endpoint `PUT /api/files/{nome}` (upload com gravação física) | [`backend/app/routes/files.py`](../../backend/app/routes/files.py) |
| Endpoint `GET /api/files` (DIR com metadados) | [`backend/app/routes/files.py`](../../backend/app/routes/files.py) |
| Endpoint `GET /api/files/{nome}` (download) | [`backend/app/routes/files.py`](../../backend/app/routes/files.py) |
| `RWLock` por arquivo (N leitores OR 1 escritor) | [`backend/app/locks.py`](../../backend/app/locks.py) |
| Gravação no threadpool (`run_in_threadpool`) | [`backend/app/routes/files.py`](../../backend/app/routes/files.py) (PUT) |
| Logs por requisição HTTP (middleware) | [`backend/app/main.py`](../../backend/app/main.py) |
| Logs por operação de negócio (DIR/PUT/GET) | [`backend/app/routes/files.py`](../../backend/app/routes/files.py) |
| Logs de lifecycle (startup/shutdown + storage) | [`backend/app/main.py`](../../backend/app/main.py) |
| Testes (12 testes, inclui leituras concorrentes) | [`tests/test_api.py`](../../tests/test_api.py) |

---

## Concorrência: como ficou

- **`DIR` e `GET`** são funções **síncronas (`def`)** → o Starlette as executa
  no **threadpool**, então vários `GET` no mesmo arquivo correm em paralelo,
  todos segurando o **read-lock** do `RWLock` daquele arquivo.
- **`PUT`** é **`async`** para ler o corpo da requisição; a gravação
  bloqueante (write-lock exclusivo + I/O em disco) é delegada ao threadpool
  via `run_in_threadpool`, sem travar o *event loop*.
- O **`LockManager`** mantém um `RWLock` por nome de arquivo, criado sob
  demanda; o dict `files_meta` em memória é protegido por `_meta_guard`.

---

## Logs operacionais (exemplo real do console)

```
2026-06-20 09:38:39 [INFO] gestor | servidor pronto — storage=backend/storage, documentos indexados=0
2026-06-20 09:38:39 [INFO] gestor.files | PUT regulamento.txt — 49 bytes gravados
2026-06-20 09:38:39 [INFO] gestor.http  | PUT /api/files/regulamento.txt -> 201 (1.5ms) [cliente=127.0.0.1:53278]
2026-06-20 09:38:39 [INFO] gestor.files | DIR — 1 documento(s) listado(s)
2026-06-20 09:38:39 [INFO] gestor.http  | GET /api/files -> 200 (0.7ms) [cliente=127.0.0.1:53279]
2026-06-20 09:38:39 [INFO] gestor.files | GET regulamento.txt — 49 bytes
2026-06-20 09:38:39 [INFO] gestor.http  | GET /api/files/regulamento.txt -> 200 (0.9ms) [cliente=127.0.0.1:53280]
2026-06-20 09:38:39 [WARNING] gestor.files | PUT binario.exe — extensão não permitida
2026-06-20 09:38:39 [INFO] gestor.http  | PUT /api/files/binario.exe -> 415 (0.6ms) [cliente=127.0.0.1:53282]
```

Três loggers diferentes em ação:

| Logger | Origem | Cobre |
|---|---|---|
| `gestor` | [`main.py`](../../backend/app/main.py) | lifecycle do servidor (pronto, encerrando) |
| `gestor.http` | middleware em [`main.py`](../../backend/app/main.py) | cada conexão HTTP (método, path, status, ms, cliente IP:porta) |
| `gestor.files` | [`routes/files.py`](../../backend/app/routes/files.py) | operações de negócio (PUT N bytes, DIR N docs, GET N bytes, erros) |

---

## Endpoints (resumo executivo)

### `PUT /api/files/{nome}` — upload
```bash
$ curl -X PUT --data-binary @regulamento.txt \
       http://localhost:8000/api/files/regulamento.txt
{"name":"regulamento.txt","size_bytes":49,"modified_at":"...","content_type":"text/plain"}
```

### `GET /api/files` — DIR
```bash
$ curl http://localhost:8000/api/files
{"count":1,"files":[{"name":"regulamento.txt","size_bytes":49,"modified_at":"...","content_type":"text/plain"}]}
```

### `GET /api/files/{nome}` — download
```bash
$ curl http://localhost:8000/api/files/regulamento.txt
Regulamento Interno v1.0
Art 1: das disposicoes.
```

Especificação completa em [`protocolo.md`](../protocolo.md).

---

## Verificação

### Servidor multicliente em funcionamento
```bash
cd backend && uvicorn app.main:app --port 8000
# observe no console os logs de startup com timestamps
```

### Comandos via terminal (curl)
```bash
# DIR (lista vazia inicialmente)
curl http://localhost:8000/api/files

# PUT (upload de um manual)
curl -X PUT --data-binary @regulamento.txt http://localhost:8000/api/files/regulamento.txt

# DIR após o PUT (manual aparece com metadados)
curl http://localhost:8000/api/files

# GET (download do conteúdo)
curl http://localhost:8000/api/files/regulamento.txt

# caminhos de erro
curl -X PUT --data-binary "x" http://localhost:8000/api/files/binario.exe   # 415
curl -X PUT http://localhost:8000/api/files/vazio.txt                       # 400
curl http://localhost:8000/api/files/nao_existe.txt                         # 404
```

### Concorrência de leitura (vários GET em paralelo no mesmo arquivo)
```bash
# dispara 8 downloads simultâneos do mesmo arquivo
seq 8 | xargs -P8 -I{} curl -s -o /dev/null -w "req{} HTTP%{http_code}\n" \
       http://localhost:8000/api/files/regulamento.txt
```
No console do servidor, observe que os 8 requests rodam em paralelo (timestamps
sobrepostos) e o `RWLock` permite todos como leitores simultâneos.

### Testes automatizados
A partir da raiz do projeto:
```bash
pytest -v
```
Os 12 testes cobrem `/health`, `DIR`, `PUT` (novo, sobrescrita, validações),
`GET` (sucesso, 404) e **leitura concorrente** (8 threads lendo o mesmo
arquivo via `Storage.read_file` em paralelo).
