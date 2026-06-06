"""Modelos Pydantic do contrato REST (payloads de entrada/saída)."""
from datetime import datetime

from pydantic import BaseModel


class FileMeta(BaseModel):
    """Metadados de um documento — usado na resposta do DIR e do PUT."""
    name: str
    size_bytes: int
    modified_at: datetime          # serializado como ISO 8601
    content_type: str


class DirResponse(BaseModel):
    """Resposta do comando DIR (GET /api/files)."""
    count: int
    files: list[FileMeta]
