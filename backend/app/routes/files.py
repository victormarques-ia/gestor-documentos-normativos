"""
Endpoints REST do Gestor de Documentos Normativos.

Evolução do protocolo de sockets para REST:
    DIR              -> GET  /api/files               (implementado)
    PUT <nome> <n>   -> PUT  /api/files/{nome}        (implementado, upload isolado)
    GET <nome>       -> GET  /api/files/{nome}        (documentado, não implementado)

Esta versão cobre o servidor base na porta fixa, a definição do formato
de saída do DIR (com metadados) e a validação do upload isolado via PUT.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..config import ALLOWED_EXTENSIONS
from ..deps import get_storage
from ..models import DirResponse, FileMeta
from ..storage import (
    EmptyContent,
    FileTooLarge,
    InvalidFilename,
    Storage,
    UnsupportedType,
)

router = APIRouter(prefix="/api/files", tags=["documentos"])


@router.get("", response_model=DirResponse, summary="DIR — lista os documentos")
def list_files(storage: Storage = Depends(get_storage)):
    """Lista todos os documentos com seus metadados (nome, tamanho, data, tipo)."""
    files = storage.list_files()
    return DirResponse(count=len(files), files=files)


@router.put(
    "/{filename}",
    response_model=FileMeta,
    status_code=status.HTTP_201_CREATED,
    summary="PUT — envia/atualiza um documento (upload isolado)",
)
async def put_file(filename: str, request: Request, storage: Storage = Depends(get_storage)):
    """
    Faz upload de um documento de texto (envio com `Content-Type: text/plain`).
    O corpo da requisição é o conteúdo do arquivo. PUT é idempotente: reenviar
    sobrescreve. Esta versão valida um upload por vez, sem concorrência.
    """
    content = await request.body()
    try:
        meta = storage.write_file(filename, content)
    except InvalidFilename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "nome de arquivo inválido")
    except EmptyContent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "conteúdo vazio não é permitido")
    except UnsupportedType:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"extensão não permitida — use {sorted(ALLOWED_EXTENSIONS)}",
        )
    except FileTooLarge:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "arquivo excede o tamanho máximo"
        )
    return meta
