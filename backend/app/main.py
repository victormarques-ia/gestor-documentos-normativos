"""
CIN0143 — Sistemas Distribuídos | Equipe 08 — Gestor de Documentos Normativos

Servidor FastAPI: evolução do servidor de sockets TCP para um framework web.
Sobe em PORTA FIXA (uvicorn), aceita MÚLTIPLAS CONEXÕES e expõe os comandos
do protocolo (DIR/GET/PUT) como endpoints REST, com SWAGGER em /docs.

Como rodar:
    uvicorn app.main:app --reload --port 8000   (a partir de backend/)
    ou: python -m app.main
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from .config import HOST, PORT
from .routes import files
from .storage import Storage


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gestor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = Storage()
    app.state.storage = storage
    log.info(
        "servidor pronto — storage=%s, documentos indexados=%d",
        storage.dir,
        len(storage.files_meta),
    )
    yield
    log.info("servidor encerrando")


app = FastAPI(
    title="Gestor de Documentos Normativos — Equipe 08",
    description=(
        "Sistema cliente-servidor para upload, download e listagem de documentos "
        "de texto. Evolução da atividade de sockets TCP para FastAPI.\n\n"
        "**Protocolo:** `DIR` → `GET /api/files` · `GET <nome>` → `GET /api/files/{nome}` "
        "· `PUT <nome>` → `PUT /api/files/{nome}`."
    ),
    version="0.2.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    client = f"{request.client.host}:{request.client.port}" if request.client else "?"
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logging.getLogger("gestor.http").info(
        "%s %s -> %d (%.1fms) [cliente=%s]",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        client,
    )
    return response


app.include_router(files.router)


@app.get("/health", tags=["infra"], summary="Health-check")
def health():
    """Confirma que o servidor está no ar (usado em testes de conexão)."""
    return {"status": "ok"}


@app.get("/", tags=["infra"], summary="Informações da API")
def root():
    return {
        "service": "Gestor de Documentos Normativos",
        "equipe": 8,
        "docs": "/docs",
        "endpoints": [
            "GET /api/files",
            "GET /api/files/{nome}",
            "PUT /api/files/{nome}",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
