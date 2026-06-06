"""Dependências do FastAPI (injeção do estado central)."""
from fastapi import Request

from .storage import Storage


def get_storage(request: Request) -> Storage:
    """Devolve a instância única de Storage criada no startup (app.state)."""
    return request.app.state.storage
