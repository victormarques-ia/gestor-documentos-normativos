"""Configuração do pytest: torna o pacote `app` (em backend/) importável."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "backend"))
