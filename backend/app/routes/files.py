import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from ..config import ALLOWED_EXTENSIONS
from ..deps import get_storage
from ..models import DirResponse, FileMeta
from ..storage import (
    EmptyContent,
    FileNotFoundInStorage,
    FileTooLarge,
    InvalidFilename,
    Storage,
    UnsupportedType,
)

log = logging.getLogger("gestor.files")
router = APIRouter(prefix="/api/files", tags=["documentos"])

_subscribers: list[asyncio.Queue] = []


def _broadcast(event: str, data: str) -> None:
    """Envia um evento SSE para todos os clientes conectados."""
    for q in _subscribers:
        q.put_nowait((event, data))
    log.info("SSE broadcast: %s=%s (%d subscriber(s))", event, data, len(_subscribers))



@router.get("", response_model=DirResponse, summary="DIR — lista os documentos")
def list_files(storage: Storage = Depends(get_storage)):
    """Lista todos os documentos com seus metadados (nome, tamanho, data, tipo)."""
    files = storage.list_files()
    log.info("DIR — %d documento(s) listado(s)", len(files))
    return DirResponse(count=len(files), files=files)


@router.get("/events", include_in_schema=False)
async def events():
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.append(queue)
    log.info("SSE: novo subscriber (total=%d)", len(_subscribers))

    async def stream():
        try:
            yield ": connected\n\n"
            while True:
                event, data = await queue.get()
                yield f"event: {event}\ndata: {data}\n\n"
        finally:
            if queue in _subscribers:
                _subscribers.remove(queue)
            log.info("SSE: subscriber desconectado (total=%d)", len(_subscribers))

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get(
    "/{filename}",
    summary="GET — baixa um documento",
    responses={404: {"description": "arquivo não encontrado"}},
)
def get_file(filename: str, storage: Storage = Depends(get_storage)):
    try:
        content = storage.read_file(filename)
    except InvalidFilename:
        log.warning("GET %s — nome inválido", filename)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "nome de arquivo inválido")
    except FileNotFoundInStorage:
        log.warning("GET %s — não encontrado", filename)
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"arquivo não encontrado: {filename}")
    log.info("GET %s — %d bytes", filename, len(content))
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put(
    "/{filename}",
    response_model=FileMeta,
    status_code=status.HTTP_201_CREATED,
    summary="PUT — envia/atualiza um documento",
)
async def put_file(filename: str, request: Request, storage: Storage = Depends(get_storage)):
    content = await request.body()
    try:
        meta = await run_in_threadpool(storage.write_file, filename, content)
    except InvalidFilename:
        log.warning("PUT %s — nome inválido", filename)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "nome de arquivo inválido")
    except EmptyContent:
        log.warning("PUT %s — conteúdo vazio", filename)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "conteúdo vazio não é permitido")
    except UnsupportedType:
        log.warning("PUT %s — extensão não permitida", filename)
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"extensão não permitida — use {sorted(ALLOWED_EXTENSIONS)}",
        )
    except FileTooLarge:
        log.warning("PUT %s — arquivo muito grande (%d bytes)", filename, len(content))
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "arquivo excede o tamanho máximo"
        )
    log.info("PUT %s — %d bytes gravados", filename, meta.size_bytes)
    _broadcast("file_updated", filename)
    return meta
