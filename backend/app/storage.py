"""
Camada de armazenamento: pasta física + índice de metadados em memória.

ESTADO CENTRAL EM MEMÓRIA
-------------------------
  - files_meta: dict[str, FileMeta]  -> índice de metadados por nome de arquivo

O filesystem (STORAGE_DIR) é a FONTE DA VERDADE; o índice em memória é
reconstruído no startup (scan da pasta) e atualizado a cada escrita (PUT).

Esta versão não inclui controle de concorrência: operações de leitura (DIR)
e escrita (PUT) acessam o índice e o disco diretamente, sem locks.
"""
import pathlib
from datetime import datetime, timezone

from .config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, STORAGE_DIR
from .models import FileMeta


# --- Exceções de domínio (traduzidas para HTTP na camada de rotas) --- #
class InvalidFilename(Exception):
    """Nome inseguro (vazio, com separador de caminho ou ponto inicial)."""


class UnsupportedType(Exception):
    """Extensão fora da lista permitida (somente texto)."""


class FileTooLarge(Exception):
    """Conteúdo maior que MAX_FILE_SIZE."""


class EmptyContent(Exception):
    """Upload sem conteúdo."""


class Storage:
    """Encapsula o estado central em memória e as operações sobre os arquivos."""

    def __init__(self, storage_dir: pathlib.Path = STORAGE_DIR):
        self.dir = pathlib.Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.files_meta: dict[str, FileMeta] = {}
        self.scan()

    # ------------------------------------------------------------------ #
    # Validações (regras de formato e de negócio)                          #
    # ------------------------------------------------------------------ #
    def _safe_path(self, filename: str) -> pathlib.Path:
        """Rejeita nomes com separadores de diretório ou ponto inicial."""
        if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
            raise InvalidFilename(filename)
        return self.dir / filename

    @staticmethod
    def _validate_extension(filename: str) -> None:
        if pathlib.Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise UnsupportedType(filename)

    # ------------------------------------------------------------------ #
    # Metadados                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_meta(path: pathlib.Path) -> FileMeta:
        stat = path.stat()
        return FileMeta(
            name=path.name,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            content_type="text/markdown" if path.suffix.lower() == ".md" else "text/plain",
        )

    def scan(self) -> None:
        """(Re)constrói o índice de metadados a partir da pasta física.

        Ignora arquivos ocultos (ex.: .gitkeep) — coerente com `_safe_path`,
        que não permite documentos com nome iniciado por ponto.
        """
        self.files_meta = {
            p.name: self._build_meta(p)
            for p in sorted(self.dir.iterdir())
            if p.is_file() and not p.name.startswith(".")
        }

    # ------------------------------------------------------------------ #
    # Operações implementadas na Entrega 1 (DIR + PUT isolado)             #
    # ------------------------------------------------------------------ #
    def list_files(self) -> list[FileMeta]:
        """DIR — devolve os metadados de todos os documentos."""
        return sorted(self.files_meta.values(), key=lambda m: m.name)

    def write_file(self, filename: str, content: bytes) -> FileMeta:
        """PUT — gravação isolada, sem controle de concorrência."""
        path = self._safe_path(filename)
        self._validate_extension(filename)
        if not content:
            raise EmptyContent(filename)
        if len(content) > MAX_FILE_SIZE:
            raise FileTooLarge(len(content))

        path.write_bytes(content)

        meta = self._build_meta(path)
        self.files_meta[filename] = meta
        return meta
