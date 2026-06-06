"""
Configurações centrais do servidor.

Tudo pode ser sobrescrito por variável de ambiente (útil para testes e deploy),
mas os padrões já atendem ao requisito de "porta fixa" da Entrega 1.
"""
import os
import pathlib

# Servidor
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))

# Pasta física dos documentos normativos (a "fonte da verdade").
_DEFAULT_STORAGE = pathlib.Path(__file__).resolve().parent.parent / "storage"
STORAGE_DIR = pathlib.Path(os.environ.get("STORAGE_DIR", _DEFAULT_STORAGE))

# Regras de negócio do domínio (documentos de texto).
ALLOWED_EXTENSIONS = {".txt", ".md"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
