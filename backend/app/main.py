"""
CIN0143 — Sistemas Distribuídos | Equipe 08 — Gestor de Documentos Normativos

Servidor FastAPI: evolução do servidor de sockets TCP para um framework web.
Sobe em PORTA FIXA (uvicorn), aceita MÚLTIPLAS CONEXÕES e expõe os comandos do
protocolo original (DIR/GET/PUT) como endpoints REST, com SWAGGER em /docs.

Como rodar:
    uvicorn app.main:app --reload --port 8000   (a partir de backend/)
    ou: python -m app.main
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import HOST, PORT
from .routes import files
from .storage import Storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: monta o estado central em memória varrendo a pasta física.
    app.state.storage = Storage()
    yield
    # SHUTDOWN: estado é em memória/disco, nada a liberar.


app = FastAPI(
    title="Gestor de Documentos Normativos — Equipe 08",
    description=(
        "Sistema cliente-servidor para upload, download e listagem de documentos "
        "de texto. Evolução da atividade de sockets TCP para FastAPI.\n\n"
        "**Protocolo:** `DIR` → `GET /api/files` · `GET <nome>` → `GET /api/files/{nome}` "
        "· `PUT <nome>` → `PUT /api/files/{nome}`."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

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
