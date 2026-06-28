import concurrent.futures

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


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


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


def test_put_novo_arquivo(client):
    r = client.put("/api/files/norma01.txt", content="Conteúdo da Norma 01.")
    assert r.status_code == 201
    assert r.json()["name"] == "norma01.txt"
    assert r.json()["size_bytes"] > 0


def test_put_sobrescreve(client):
    client.put("/api/files/manual.txt", content="versão 1")
    client.put("/api/files/manual.txt", content="versão 2")
    assert client.get("/api/files/manual.txt").content.decode("utf-8") == "versão 2"


def test_put_nome_invalido_400(client):
    assert client.put("/api/files/.oculto.txt", content="abc").status_code == 400


def test_put_extensao_nao_permitida_415(client):
    assert client.put("/api/files/binario.exe", content="x").status_code == 415


def test_put_conteudo_vazio_400(client):
    assert client.put("/api/files/vazio.txt", content=b"").status_code == 400


def test_get_recupera_conteudo(client):
    conteudo = "Regulamento Interno v1.0 — referência."
    client.put("/api/files/regulamento.txt", content=conteudo.encode("utf-8"))
    r = client.get("/api/files/regulamento.txt")
    assert r.status_code == 200
    assert r.content.decode("utf-8") == conteudo


def test_get_inexistente_404(client):
    assert client.get("/api/files/nao_existe.txt").status_code == 404


def test_ui_servido(client):
    """A interface gráfica é servida pelo próprio FastAPI na raiz (Entrega 3)."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.text.lower()
    assert "<!doctype" in body or "<html" in body
    # marker específico da nossa UI
    assert "gestor de documentos" in body


def test_ui_assets_servidos(client):
    """styles.css e app.js servidos como estáticos da raiz."""
    assert client.get("/styles.css").status_code == 200
    assert client.get("/app.js").status_code == 200


def test_sse_broadcast_alimenta_subscribers():
    """
    O mecanismo de broadcast SSE coloca o evento em todas as queues de subscribers.

    O endpoint /api/files/events em si é um stream HTTP infinito (não fecha até o
    cliente desconectar), então testamos a lógica de pub/sub interna que ele usa.
    A integração HTTP é validada no smoke test manual (ver entrega-3.md).
    """
    import asyncio
    from app.routes.files import _broadcast, _subscribers

    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    try:
        _broadcast("file_updated", "teste.txt")
        assert q.qsize() == 1
        event, data = q.get_nowait()
        assert event == "file_updated"
        assert data == "teste.txt"
    finally:
        _subscribers.remove(q)


def test_put_dispara_broadcast_sse(client):
    """Após um PUT bem-sucedido, um evento file_updated é entregue a um subscriber ativo."""
    import asyncio
    from app.routes.files import _subscribers

    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    try:
        r = client.put("/api/files/notificacao.txt", content="abc")
        assert r.status_code == 201
        # broadcast foi chamado pelo endpoint -> evento na queue
        assert q.qsize() == 1
        event, data = q.get_nowait()
        assert event == "file_updated"
        assert data == "notificacao.txt"
    finally:
        _subscribers.remove(q)


def test_leituras_concorrentes_mesmo_arquivo(tmp_path):
    """8 leitores simultâneos no mesmo arquivo devolvem o conteúdo íntegro."""
    storage = Storage(storage_dir=tmp_path)
    conteudo = (b"A" * 512 + b"B" * 512) * 4  # 4 KB reconhecível
    storage.write_file("manual_grande.txt", conteudo)

    def leitor(_):
        return storage.read_file("manual_grande.txt")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        resultados = list(ex.map(leitor, range(8)))

    assert all(r == conteudo for r in resultados), "conteúdo corrompido em leitura concorrente"
