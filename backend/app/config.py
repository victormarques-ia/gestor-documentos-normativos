import os
import pathlib

# Servidor
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))

# Pasta física dos documentos normativos (a "fonte da verdade").
_DEFAULT_STORAGE = pathlib.Path(__file__).resolve().parent.parent / "storage"
STORAGE_DIR = pathlib.Path(os.environ.get("STORAGE_DIR", _DEFAULT_STORAGE))

# Regras de negócio do domínio (documentos de texto).
ALLOWED_EXTENSIONS = {".txt", ".md", ".rst", ".docx", ".pdf", ".csv", ".json", ".xml"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
