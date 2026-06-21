"""
Camada de armazenamento: pasta física + índice de metadados em memória.

ESTADO CENTRAL EM MEMÓRIA
-------------------------
  - files_meta:   dict[str, FileMeta]  -> índice de metadados por nome
  - locks:        LockManager           -> um RWLock por arquivo
  - _meta_guard:  threading.Lock        -> protege o dict files_meta

O filesystem (STORAGE_DIR) é a FONTE DA VERDADE; o índice em memória é
reconstruído no startup (scan da pasta) e atualizado a cada escrita (PUT).

CONCORRÊNCIA
------------
O `RWLock` por arquivo permite N leitores simultâneos (GET no mesmo arquivo
em paralelo) OU 1 escritor exclusivo (PUT bloqueia leitores ativos).
"""
import pathlib
import threading
from datetime import datetime, timezone

from .config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, STORAGE_DIR
from .locks import LockManager
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


class FileNotFoundInStorage(Exception):
    """Documento solicitado não existe."""


class Storage:
    """Encapsula o estado central em memória e as operações sobre os arquivos."""

    def __init__(self, storage_dir: pathlib.Path = STORAGE_DIR):
        self.dir = pathlib.Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.files_meta: dict[str, FileMeta] = {}
        self.locks = LockManager()
        self._meta_guard = threading.Lock()
        self.scan()

    def _safe_path(self, filename: str) -> pathlib.Path:
        """Rejeita nomes com separadores de diretório ou ponto inicial."""
        if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
            raise InvalidFilename(filename)
        return self.dir / filename

    @staticmethod
    def _validate_extension(filename: str) -> None:
        if pathlib.Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise UnsupportedType(filename)

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
        with self._meta_guard:
            self.files_meta = {
                p.name: self._build_meta(p)
                for p in sorted(self.dir.iterdir())
                if p.is_file() and not p.name.startswith(".")
            }

    def list_files(self) -> list[FileMeta]:
        """DIR — devolve os metadados de todos os documentos."""
        with self._meta_guard:
            return sorted(self.files_meta.values(), key=lambda m: m.name)

    def read_file(self, filename: str) -> bytes:
        """GET — leitura sob read-lock (vários leitores em paralelo)."""
        path = self._safe_path(filename)
        if not path.exists():
            raise FileNotFoundInStorage(filename)
        with self.locks.get(filename).read():
            return path.read_bytes()

    def write_file(self, filename: str, content: bytes) -> FileMeta:
        """PUT — gravação sob write-lock (exclusiva). Valida antes de gravar."""
        path = self._safe_path(filename)
        self._validate_extension(filename)
        if not content:
            raise EmptyContent(filename)
        if len(content) > MAX_FILE_SIZE:
            raise FileTooLarge(len(content))

        with self.locks.get(filename).write():
            path.write_bytes(content)

        meta = self._build_meta(path)
        with self._meta_guard:
            self.files_meta[filename] = meta
        return meta
