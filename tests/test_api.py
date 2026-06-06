"""
CIN0143 — Sistemas Distribuídos | Equipe 08 — Gestor de Documentos Normativos

Testes da API REST. Cobrem:
  - /health (servidor na porta fixa)
  - DIR (formato de saída + metadados)
  - PUT isolado (upload validado, sem concorrência)
  - Validações (nome, extensão, tamanho, conteúdo vazio)

Execução (a partir da raiz do projeto):
    pytest -v
"""
import pytest
from fastapi.testclient import TestClient

from app.deps import get_storage
from app.main import app
from app.storage import Storage


@pytest.fixture
def client(tmp_path):
    """Cliente de teste com um Storage isolado em pasta temporária."""
    storage = Storage(storage_dir=tmp_path)
    app.dependency_overrides[get_storage] = lambda: storage
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --- infra ---------------------------------------------------------------- #

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


# --- DIR ------------------------------------------------------------------ #

def test_dir_vazio(client):
    r = client.get("/api/files")
    assert r.status_code == 200
    assert r.json() == {"count": 0, "files": []}


def test_dir_lista_apos_put(client):
    client.put("/api/files/norma02.txt", content="Norma 02.")
    nomes = [f["name"] for f in client.get("/api/files").json()["files"]]
    assert "norma02.txt" in nomes


def test_dir_traz_metadados(client):
    client.put("/api/files/manual.md", content="# título")
    meta = client.get("/api/files").json()["files"][0]
    assert set(meta) == {"name", "size_bytes", "modified_at", "content_type"}
    assert meta["content_type"] == "text/markdown"


# --- PUT ------------------------------------------------------------------ #

def test_put_novo_arquivo(client):
    r = client.put("/api/files/norma01.txt", content="Conteúdo da Norma 01.")
    assert r.status_code == 201
    assert r.json()["name"] == "norma01.txt"
    assert r.json()["size_bytes"] > 0


def test_put_sobrescreve(client):
    client.put("/api/files/manual.txt", content="versão 1")
    client.put("/api/files/manual.txt", content="versão 2")
    # confirma via DIR que o tamanho refletiu a segunda versão
    meta = {f["name"]: f for f in client.get("/api/files").json()["files"]}
    assert meta["manual.txt"]["size_bytes"] == len("versão 2".encode("utf-8"))


def test_put_nome_invalido_400(client):
    # nome iniciado com ponto é rejeitado (proteção anti path-traversal)
    assert client.put("/api/files/.oculto.txt", content="abc").status_code == 400


def test_put_extensao_nao_permitida_415(client):
    assert client.put("/api/files/binario.exe", content="x").status_code == 415


def test_put_conteudo_vazio_400(client):
    assert client.put("/api/files/vazio.txt", content=b"").status_code == 400
