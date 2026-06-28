"""
Cada classe cobre um requisito explícito da especificação:
  - Protocolo DIR / GET / PUT completo
  - Concorrência de leitura (RWLock: N leitores simultâneos)
  - Isolamento de escrita (escritor exclusivo, sem corrupção)
  - Broadcast SSE em tempo real (PUT dispara evento para todos os clientes)
  - Persistência em disco (arquivos sobrevivem a reinicializações do Storage)
  - Validações de segurança (nome, extensão, tamanho, conteúdo, path traversal)
  - Content-Length no GET (necessário para barra de progresso no cliente)
  - Interface gráfica servida pelo próprio FastAPI (deploy único)
"""
import asyncio
import concurrent.futures
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.deps import get_storage
from app.main import app
from app.storage import (
    EmptyContent,
    FileTooLarge,
    InvalidFilename,
    Storage,
    UnsupportedType,
)

@pytest.fixture
def client(tmp_path):
    storage = Storage(storage_dir=tmp_path)
    app.dependency_overrides[get_storage] = lambda: storage
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def storage_com_arquivos(tmp_path):
    """Storage pré-populado com 3 documentos de tipos e tamanhos variados."""
    s = Storage(storage_dir=tmp_path)
    s.write_file("norma01.txt", b"Norma 01 " * 80)
    s.write_file("manual.md", b"# Manual\n\nConteudo." * 40)
    s.write_file("regulamento.txt", b"Regulamento v1.0 " * 60)
    return s


@pytest.fixture
def client_populado(tmp_path, storage_com_arquivos):
    app.dependency_overrides[get_storage] = lambda: storage_com_arquivos
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

class TestProtocoloDIR:
    """DIR → GET /api/files: lista todos os documentos com metadados."""

    def test_lista_vazia_inicialmente(self, client):
        r = client.get("/api/files")
        assert r.status_code == 200
        assert r.json() == {"count": 0, "files": []}

    def test_reflete_arquivos_enviados(self, client):
        client.put("/api/files/a.txt", content=b"conteudo A")
        client.put("/api/files/b.md", content=b"conteudo B")
        body = client.get("/api/files").json()
        assert body["count"] == 2
        nomes = {f["name"] for f in body["files"]}
        assert nomes == {"a.txt", "b.md"}

    def test_metadados_completos(self, client):
        client.put("/api/files/doc.txt", content=b"A" * 512)
        meta = client.get("/api/files").json()["files"][0]
        assert meta["name"] == "doc.txt"
        assert meta["size_bytes"] == 512
        assert "modified_at" in meta
        assert meta["content_type"] == "text/plain"

    def test_md_tem_content_type_correto(self, client):
        client.put("/api/files/readme.md", content=b"# titulo")
        meta = client.get("/api/files").json()["files"][0]
        assert meta["content_type"] == "text/markdown"

    def test_sobrescrita_nao_duplica_entrada(self, client):
        client.put("/api/files/manual.txt", content=b"v1")
        client.put("/api/files/manual.txt", content=b"v2 atualizado")
        body = client.get("/api/files").json()
        assert body["count"] == 1

    def test_tamanho_atualizado_apos_sobrescrita(self, client):
        client.put("/api/files/doc.txt", content=b"curto")
        client.put("/api/files/doc.txt", content=b"muito mais longo que antes")
        meta = client.get("/api/files").json()["files"][0]
        assert meta["size_bytes"] == len(b"muito mais longo que antes")

    def test_varios_arquivos_retornados(self, client_populado):
        body = client_populado.get("/api/files").json()
        assert body["count"] == 3
        nomes = {f["name"] for f in body["files"]}
        assert nomes == {"norma01.txt", "manual.md", "regulamento.txt"}

class TestProtocoloGET:
    """GET /api/files/{nome}: download do documento com progresso real."""

    def test_conteudo_integro(self, client):
        conteudo = b"Regulamento Interno v3.1 - texto com acentuacao."
        client.put("/api/files/reg.txt", content=conteudo)
        r = client.get("/api/files/reg.txt")
        assert r.status_code == 200
        assert r.content == conteudo

    def test_content_length_presente(self, client):
        """Content-Length obrigatório: sem ele o cliente não consegue calcular progresso."""
        conteudo = b"X" * 2048
        client.put("/api/files/grande.txt", content=conteudo)
        r = client.get("/api/files/grande.txt")
        assert "content-length" in r.headers
        assert int(r.headers["content-length"]) == len(conteudo)

    def test_content_disposition_forca_download(self, client):
        """Content-Disposition: attachment impede o browser de exibir inline."""
        client.put("/api/files/manual.txt", content=b"conteudo")
        r = client.get("/api/files/manual.txt")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "manual.txt" in cd

    def test_404_arquivo_inexistente(self, client):
        assert client.get("/api/files/nao_existe.txt").status_code == 404

    def test_reflete_sobrescrita(self, client):
        client.put("/api/files/doc.txt", content=b"versao 1")
        client.put("/api/files/doc.txt", content=b"versao 2 atualizada")
        r = client.get("/api/files/doc.txt")
        assert r.content == b"versao 2 atualizada"

    def test_multiplos_arquivos_independentes(self, client_populado):
        """Cada GET retorna exatamente o conteúdo do arquivo correto."""
        r_norma = client_populado.get("/api/files/norma01.txt")
        r_manual = client_populado.get("/api/files/manual.md")
        assert r_norma.status_code == 200
        assert r_manual.status_code == 200
        assert r_norma.content != r_manual.content

class TestProtocoloPUT:
    """PUT /api/files/{nome}: upload de documento com validações."""

    def test_retorna_201_com_metadados(self, client):
        r = client.put("/api/files/norma.txt", content=b"conteudo valido")
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "norma.txt"
        assert body["size_bytes"] == len(b"conteudo valido")
        assert "modified_at" in body

    def test_aceita_txt_e_md(self, client):
        assert client.put("/api/files/doc.txt", content=b"texto").status_code == 201
        assert client.put("/api/files/readme.md", content=b"# titulo").status_code == 201

    def test_rejeita_extensao_desconhecida_415(self, client):
        assert client.put("/api/files/mal.exe", content=b"x").status_code == 415

    def test_rejeita_pdf_415(self, client):
        assert client.put("/api/files/contrato.pdf", content=b"%PDF").status_code == 415

    def test_rejeita_conteudo_vazio_400(self, client):
        assert client.put("/api/files/vazio.txt", content=b"").status_code == 400

    def test_rejeita_nome_oculto_400(self, client):
        assert client.put("/api/files/.oculto.txt", content=b"x").status_code == 400

    def test_aceita_arquivo_proximo_ao_limite(self, client):
        """4,9 MB deve ser aceito (limite é 5 MB)."""
        conteudo = b"A" * (4 * 1024 * 1024 + 900 * 1024)
        assert client.put("/api/files/grande.txt", content=conteudo).status_code == 201

    def test_rejeita_arquivo_acima_do_limite_413(self, client):
        conteudo = b"B" * (5 * 1024 * 1024 + 1)
        assert client.put("/api/files/enorme.txt", content=conteudo).status_code == 413


# ─── Requisito: Validações de Segurança ──────────────────────────────────────

class TestValidacoesSeguranca:
    """Validações na camada de storage que protegem contra nomes maliciosos."""

    def test_rejeita_path_traversal_com_barra(self, tmp_path):
        """Nomes com '/' são rejeitados no Storage — proteção anti path-traversal."""
        storage = Storage(storage_dir=tmp_path)
        with pytest.raises(InvalidFilename):
            storage.write_file("../secreto.txt", b"invasao")

    def test_rejeita_path_traversal_com_barra_invertida(self, tmp_path):
        storage = Storage(storage_dir=tmp_path)
        with pytest.raises(InvalidFilename):
            storage.write_file("subdir\\secreto.txt", b"invasao")

    def test_rejeita_nome_vazio(self, tmp_path):
        storage = Storage(storage_dir=tmp_path)
        with pytest.raises(InvalidFilename):
            storage.write_file("", b"conteudo")

    def test_rejeita_extensao_nao_permitida(self, tmp_path):
        storage = Storage(storage_dir=tmp_path)
        with pytest.raises(UnsupportedType):
            storage.write_file("binario.exe", b"x")

    def test_rejeita_conteudo_vazio(self, tmp_path):
        storage = Storage(storage_dir=tmp_path)
        with pytest.raises(EmptyContent):
            storage.write_file("vazio.txt", b"")

    def test_rejeita_arquivo_muito_grande(self, tmp_path):
        storage = Storage(storage_dir=tmp_path)
        with pytest.raises(FileTooLarge):
            storage.write_file("enorme.txt", b"X" * (5 * 1024 * 1024 + 1))

    def test_arquivo_fica_dentro_do_storage_dir(self, tmp_path):
        """Arquivo gravado não pode escapar para fora do storage_dir."""
        storage = Storage(storage_dir=tmp_path)
        storage.write_file("norma.txt", b"conteudo")
        arquivo = tmp_path / "norma.txt"
        assert arquivo.exists()
        # nenhum arquivo foi criado fora do tmp_path
        parent_files = list(tmp_path.parent.glob("norma.txt"))
        assert parent_files == []

class TestFluxoCompleto:
    """Simula o fluxo de um usuário real: enviar → listar → baixar."""

    def test_ciclo_upload_listagem_download(self, client):
        conteudo = b"Manual de Procedimentos Operacionais - Revisao 5\n" * 20
        nome = "procedimentos.txt"

        r_put = client.put(f"/api/files/{nome}", content=conteudo)
        assert r_put.status_code == 201

        nomes_na_lista = [f["name"] for f in client.get("/api/files").json()["files"]]
        assert nome in nomes_na_lista

        r_get = client.get(f"/api/files/{nome}")
        assert r_get.status_code == 200
        assert r_get.content == conteudo

    def test_multiplos_arquivos_isolados(self, client):
        """Cada arquivo preserva seu conteúdo independentemente dos outros."""
        arquivos = {
            "norma-a.txt": b"Norma A " * 10,
            "norma-b.txt": b"Norma B " * 20,
            "manual.md": b"# Manual\n" * 5,
        }
        for nome, conteudo in arquivos.items():
            assert client.put(f"/api/files/{nome}", content=conteudo).status_code == 201

        assert client.get("/api/files").json()["count"] == 3

        for nome, conteudo_esperado in arquivos.items():
            r = client.get(f"/api/files/{nome}")
            assert r.content == conteudo_esperado, f"conteudo corrompido: {nome}"

    def test_sobrescrita_preserva_conteudo_correto(self, client):
        client.put("/api/files/doc.txt", content=b"versao 1 - antiga")
        client.put("/api/files/doc.txt", content=b"versao 2 - nova e definitiva")
        assert client.get("/api/files/doc.txt").content == b"versao 2 - nova e definitiva"

    def test_erro_nao_compromete_arquivos_validos(self, client):
        """Uma requisição inválida não afeta arquivos já gravados."""
        client.put("/api/files/valido.txt", content=b"conteudo valido")
        client.put("/api/files/invalido.exe", content=b"x")  # 415 - deve falhar

        r = client.get("/api/files/valido.txt")
        assert r.status_code == 200
        assert r.content == b"conteudo valido"

class TestConcorrenciaLeitura:
    """N leitores simultâneos no mesmo arquivo sem bloqueio mútuo."""

    def test_leitores_paralelos_nao_bloqueiam_uns_aos_outros(self, tmp_path):
        """8 leitores simultâneos retornam conteúdo íntegro e sem deadlock."""
        storage = Storage(storage_dir=tmp_path)
        conteudo = (b"A" * 512 + b"B" * 512) * 8
        storage.write_file("manual_grande.txt", conteudo)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            resultados = list(ex.map(lambda _: storage.read_file("manual_grande.txt"), range(8)))

        assert all(r == conteudo for r in resultados), "conteudo divergiu entre leitores"

    def test_leituras_concorrentes_via_http(self, tmp_path):
        """5 clientes HTTP simultâneos baixam o mesmo arquivo sem bloqueio."""
        storage = Storage(storage_dir=tmp_path)
        conteudo = b"Regulamento " * 512
        storage.write_file("regulamento.txt", conteudo)
        app.dependency_overrides[get_storage] = lambda: storage

        barrier = threading.Barrier(5)
        resultados = []
        resultado_lock = threading.Lock()

        def baixar():
            with TestClient(app) as c:
                barrier.wait()
                r = c.get("/api/files/regulamento.txt")
                with resultado_lock:
                    resultados.append(r.content)

        threads = [threading.Thread(target=baixar) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        app.dependency_overrides.clear()

        assert len(resultados) == 5
        assert all(r == conteudo for r in resultados), "conteudo corrompido em download simultaneo"

    def test_escrita_nao_corrompe_leitores_concorrentes(self, tmp_path):
        """Escritor e leitores simultâneos: conteúdo jamais corrompido."""
        storage = Storage(storage_dir=tmp_path)
        v1 = b"versao-A " * 200
        v2 = b"versao-B " * 200
        storage.write_file("doc.txt", v1)
        erros = []

        def leitor():
            try:
                conteudo = storage.read_file("doc.txt")
                if conteudo not in (v1, v2):
                    erros.append(f"conteudo inesperado: {conteudo[:20]}")
            except Exception as e:
                erros.append(str(e))

        def escritor():
            storage.write_file("doc.txt", v2)

        threads = (
            [threading.Thread(target=leitor) for _ in range(5)]
            + [threading.Thread(target=escritor)]
            + [threading.Thread(target=leitor) for _ in range(5)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert erros == [], f"leitura corrompida durante escrita: {erros}"

    def test_rwlock_leitores_rodam_em_paralelo(self, tmp_path):
        """Dois leitores com sleep artificial completam mais rápido que 2× o sleep."""
        from app.locks import RWLock

        lock = RWLock()
        tempos = []

        def leitor_lento():
            with lock.read():
                start = time.perf_counter()
                time.sleep(0.1)
                tempos.append(time.perf_counter() - start)

        t1 = threading.Thread(target=leitor_lento)
        t2 = threading.Thread(target=leitor_lento)
        inicio = time.perf_counter()
        t1.start(); t2.start()
        t1.join(); t2.join()
        total = time.perf_counter() - inicio

        # Se rodassem serialmente: ~0,2s. Em paralelo: ~0,1s + overhead.
        assert total < 0.18, f"leitores rodaram sequencialmente (total={total:.3f}s)"


class TestSSEReatividade:
    """PUT de um cliente → lista de outro cliente atualiza em < 100ms via SSE."""

    def test_broadcast_entrega_a_todos_os_subscribers(self):
        """Todos os subscribers ativos recebem o evento simultaneamente."""
        from app.routes.files import _broadcast, _subscribers

        queues = [asyncio.Queue() for _ in range(3)]
        for q in queues:
            _subscribers.append(q)
        try:
            _broadcast("file_updated", "norma.txt")
            for q in queues:
                assert q.qsize() == 1
                event, data = q.get_nowait()
                assert event == "file_updated"
                assert data == "norma.txt"
        finally:
            for q in queues:
                if q in _subscribers:
                    _subscribers.remove(q)

    def test_put_bem_sucedido_emite_evento_sse(self, client):
        """PUT → subscriber recebe (event='file_updated', data=<nome do arquivo>)."""
        from app.routes.files import _subscribers

        q = asyncio.Queue()
        _subscribers.append(q)
        try:
            r = client.put("/api/files/novo.txt", content=b"conteudo")
            assert r.status_code == 201
            assert q.qsize() == 1
            event, data = q.get_nowait()
            assert event == "file_updated"
            assert data == "novo.txt"
        finally:
            if q in _subscribers:
                _subscribers.remove(q)

    def test_put_invalido_nao_emite_sse(self, client):
        """Requisições que falham na validação não disparam broadcast SSE."""
        from app.routes.files import _subscribers

        q = asyncio.Queue()
        _subscribers.append(q)
        try:
            client.put("/api/files/invalido.exe", content=b"x")  # 415
            client.put("/api/files/vazio.txt", content=b"")       # 400
            assert q.qsize() == 0, "broadcast emitido apos PUT invalido"
        finally:
            if q in _subscribers:
                _subscribers.remove(q)

    def test_multiplos_puts_emitem_multiplos_eventos(self, client):
        """Cada PUT bem-sucedido emite exatamente um evento para cada subscriber."""
        from app.routes.files import _subscribers

        q = asyncio.Queue()
        _subscribers.append(q)
        try:
            client.put("/api/files/doc1.txt", content=b"a")
            client.put("/api/files/doc2.txt", content=b"b")
            client.put("/api/files/doc3.txt", content=b"c")
            assert q.qsize() == 3
            nomes = {q.get_nowait()[1] for _ in range(3)}
            assert nomes == {"doc1.txt", "doc2.txt", "doc3.txt"}
        finally:
            if q in _subscribers:
                _subscribers.remove(q)

    def test_sse_endpoint_responde_com_media_type_correto(self, client):
        """O endpoint /api/files/events retorna StreamingResponse com media-type SSE."""
        from fastapi.responses import StreamingResponse

        from app.routes.files import _subscribers, events

        before = len(_subscribers)
        response = asyncio.run(events())
        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"

        # events() registra um subscriber; limpamos para não vazar estado global.
        if len(_subscribers) > before:
            del _subscribers[before:]


class TestPersistencia:
    """Documentos sobrevivem a reinicializações — filesystem é fonte da verdade."""

    def test_arquivo_existe_fisicamente_no_disco(self, tmp_path):
        storage = Storage(storage_dir=tmp_path)
        storage.write_file("persistente.txt", b"conteudo persistido")
        assert (tmp_path / "persistente.txt").exists()
        assert (tmp_path / "persistente.txt").read_bytes() == b"conteudo persistido"

    def test_nova_instancia_indexa_arquivos_existentes(self, tmp_path):
        """Nova instância do Storage escaneia o disco e reconstrói o índice."""
        (tmp_path / "pre_existente.txt").write_bytes(b"arquivo anterior")
        storage2 = Storage(storage_dir=tmp_path)
        nomes = [f.name for f in storage2.list_files()]
        assert "pre_existente.txt" in nomes

    def test_conteudo_sobrescrito_correto_no_disco(self, tmp_path):
        storage = Storage(storage_dir=tmp_path)
        storage.write_file("doc.txt", b"versao 1")
        storage.write_file("doc.txt", b"versao 2 - final")
        assert (tmp_path / "doc.txt").read_bytes() == b"versao 2 - final"

    def test_multiplos_arquivos_persistem_independentemente(self, tmp_path):
        storage = Storage(storage_dir=tmp_path)
        arquivos = {"a.txt": b"AAA", "b.txt": b"BBB", "c.md": b"CCC"}
        for nome, conteudo in arquivos.items():
            storage.write_file(nome, conteudo)

        storage2 = Storage(storage_dir=tmp_path)
        for nome, conteudo_esperado in arquivos.items():
            assert storage2.read_file(nome) == conteudo_esperado

class TestInterfaceGrafica:
    """UI servida pelo próprio servidor"""

    def test_raiz_retorna_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_ui_contem_marcador_do_projeto(self, client):
        """Confirma que é nossa UI, não uma página genérica."""
        r = client.get("/")
        assert "gestor de documentos" in r.text.lower()

    def test_css_e_js_servidos_na_raiz(self, client):
        """Assets do frontend servidos pelo mesmo servidor que a API."""
        assert client.get("/styles.css").status_code == 200
        assert client.get("/app.js").status_code == 200

    def test_swagger_disponivel_para_demo(self, client):
        """/docs exposto para exercitar a API diretamente durante a apresentação."""
        assert client.get("/docs").status_code == 200

    def test_health_coexiste_com_ui(self, client):
        """/health e / convivem: o mount estático não engole as rotas da API."""
        assert client.get("/health").json() == {"status": "ok"}

    def test_api_coexiste_com_ui(self, client):
        """GET /api/files funciona mesmo com mount estático na raiz."""
        assert client.get("/api/files").status_code == 200
