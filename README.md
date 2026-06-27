# Equipe 08 — Gestor de Documentos Normativos

**CIN0143 — Introdução aos Sistemas Distribuídos e Redes de Computadores**
Universidade Federal de Pernambuco — Centro de Informática
Docente: David J M Cavalcanti

**Integrantes**
- Gabriel Albertin Vieira
- Ithalo Rannieri Araujo Soares
- Talisson Mendes
- Tiago Ferreira
- Victor Silva Marques de Oliveira

---

## Descrição

Sistema distribuído **cliente-servidor** para **upload, download e listagem de
documentos de texto** (manuais e normas). O servidor escuta em **porta fixa**,
aceita **múltiplas conexões** e suporta **concorrência de leitura**: vários
clientes podem baixar o mesmo documento ao mesmo tempo, enquanto o servidor
segue aceitando novas conexões.

Este projeto é a **evolução** da atividade anterior, feita com **sockets TCP
puros** em Python, agora reimplementada sobre o framework **FastAPI**. Os três
comandos do protocolo original (`DIR`, `GET`, `PUT`) são mapeados para
**endpoints REST**.

## Decisão tecnológica e justificativa

**Framework escolhido: FastAPI (Python) + Uvicorn.**

- **Evolui** a base que já temos: a atividade em sockets foi escrita em Python,
  então reaproveitamos o padrão de validação anti *path-traversal* e a
  organização do `storage/`, em vez de reescrever do zero.
- **Testável de imediato:** o FastAPI gera **Swagger UI** em `/docs`, permitindo
  exercitar os endpoints pelo navegador sem nenhum frontend.
- **Porta fixa e múltiplas conexões** nativas via Uvicorn (servidor ASGI).
- **Concorrência de leitura:** o ASGI roda endpoints síncronos no *threadpool*
  do Starlette, casando bem com o `RWLock` baseado em *threads* portado da
  versão em sockets.

## Estrutura de pastas

```
projeto-sistemas-distribuidos-equipe-8/
├── README.md                    # este arquivo (visão geral, atemporal)
├── requirements.txt
├── conftest.py                  # torna backend/app importável nos testes
├── backend/
│   ├── app/
│   │   ├── main.py              # app FastAPI, /health, logging, startup, mount UI
│   │   ├── config.py            # porta, storage, extensões, tamanho máx.
│   │   ├── storage.py           # estado em memória + operações + validações
│   │   ├── locks.py             # RWLock + LockManager (concorrência por arquivo)
│   │   ├── models.py            # Pydantic: FileMeta, DirResponse
│   │   ├── deps.py              # injeção do Storage
│   │   └── routes/files.py      # endpoints REST + SSE (/api/files/events)
│   ├── static/                  # interface gráfica (Alpine.js, sem build)
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── app.js
│   └── storage/                 # pasta física dos documentos
├── tests/test_api.py            # testes pytest da API
└── docs/
    ├── protocolo.md             # especificação do contrato REST
    └── entregas/                # documentação por entrega
        ├── entrega-1.md
        ├── entrega-2.md
        └── entrega-3.md
```

## Como rodar

Pré-requisito: **Python 3.10+**.

```bash
# 1. Ambiente virtual e dependências
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Subir o servidor (porta fixa 8000)
cd backend
uvicorn app.main:app --reload --port 8000
```

Servidor no ar em `http://localhost:8000`. Endpoints disponíveis:

- **`/ui/`** → **interface gráfica** (explorador visual de manuais, upload/download com barras de progresso, reatividade em tempo real via SSE).
- **`/docs`** → Swagger UI para exercitar a API diretamente.
- **`/api/files`** → contrato REST (DIR / GET / PUT).

## Interface gráfica

Acesse **`http://localhost:8000/ui/`** após subir o servidor. A UI suporta:

- **Listagem** automática dos documentos (DIR) com metadados — atualiza em tempo real via SSE quando outro cliente faz upload.
- **Upload** (PUT) com validação (extensão `.txt`/`.md`, tamanho ≤ 5 MB) e **barra de progresso real**.
- **Download** (GET) com **barra de progresso real** (lê em streaming via `Content-Length`).
- **Tratamento de erros** visual via toasts (400/404/413/415).
- **Indicador de status** do canal SSE no header.

Stack do frontend: HTML + Alpine.js (via CDN) + CSS — sem Node, sem build, sem
deploy separado. Tudo servido pelo próprio FastAPI.

## Como testar

**Pelo navegador:** abra `/ui/` para a interface, ou `/docs` para o Swagger.

**Por linha de comando**:

```bash
# DIR — lista documentos com metadados (nome, tamanho, data, tipo)
curl http://localhost:8000/api/files

# PUT — envia um manual (o corpo da requisição é o conteúdo do arquivo)
curl -X PUT --data-binary @regulamento.txt \
     http://localhost:8000/api/files/regulamento.txt

# GET — baixa o conteúdo do manual
curl http://localhost:8000/api/files/regulamento.txt
```

Exemplos completos no
documento da [Entrega 2](docs/entregas/entrega-2.md#verificação).

**Testes automatizados** (a partir da raiz do projeto):

```bash
pytest -v
```

## Entregas

Cada entrega tem um documento próprio descrevendo escopo, itens entregues e
como verificar. O protocolo REST do servidor está em [`docs/protocolo.md`](docs/protocolo.md).

| # | Documento | Foco |
|---|---|---|
| **1** | [`docs/entregas/entrega-1.md`](docs/entregas/entrega-1.md) | Arquitetura e Escopo |
| **2** | [`docs/entregas/entrega-2.md`](docs/entregas/entrega-2.md) | Comunicação e Core (multicliente + GET + RWLock + logs) |
| **3** | [`docs/entregas/entrega-3.md`](docs/entregas/entrega-3.md) | Interface gráfica (Alpine.js + SSE em tempo real, barras de progresso reais) |
