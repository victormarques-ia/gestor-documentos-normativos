"""Testes E2E em browser real (Playwright) para a interface web."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest


def _pick_free_port() -> int:
    """Retorna uma porta TCP livre no localhost para subir o servidor E2E."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_for_health(base_url: str, timeout_s: float = 10.0) -> None:
    """Espera o endpoint /health responder 200 para evitar corrida no startup."""
    deadline = time.time() + timeout_s
    health_url = f"{base_url}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=0.8) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"Servidor não ficou pronto em {timeout_s}s: {health_url}")


@pytest.fixture(scope="module")
def pw_module():
    """Importa Playwright sob demanda; se ausente, só os testes de browser são pulados."""
    return pytest.importorskip("playwright.sync_api")


@pytest.fixture
def live_server(tmp_path):
    """Sobe uvicorn em subprocesso apontando STORAGE_DIR para pasta temporária."""
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["STORAGE_DIR"] = str(tmp_path)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--app-dir",
        "backend",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_health(base_url)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


@pytest.fixture
def browser_context(pw_module):
    """Contexto de browser isolado; suporta modo visual via PW_HEADFUL=1."""
    headful = os.environ.get("PW_HEADFUL", "0") == "1"
    slow_mo_ms = int(os.environ.get("PW_SLOWMO_MS", "0"))
    with pw_module.sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful, slow_mo=slow_mo_ms)
        context = browser.new_context(accept_downloads=True)
        try:
            yield context
        finally:
            context.close()
            browser.close()


class TestPlaywrightBrowserE2E:
    """E2E real em browser: upload, SSE entre abas e download com progresso."""

    def test_upload_aparece_na_lista(self, live_server, browser_context):
        page = browser_context.new_page()
        page.goto(live_server, wait_until="domcontentloaded")

        page.set_input_files(
            "input[type='file']",
            {"name": "norma-playwright.txt", "mimeType": "text/plain", "buffer": b"conteudo E2E"},
        )

        page.wait_for_selector("text=enviado: norma-playwright.txt", timeout=6000)
        page.wait_for_selector("code:has-text('norma-playwright.txt')", timeout=6000)
        assert page.locator("tbody tr").count() >= 1

    def test_sse_atualiza_segunda_aba(self, live_server, browser_context):
        page_a = browser_context.new_page()
        page_b = browser_context.new_page()
        page_a.goto(live_server, wait_until="domcontentloaded")
        page_b.goto(live_server, wait_until="domcontentloaded")

        # Garante que o SSE conectou antes de validar atualização cruzada.
        page_b.wait_for_selector("text=● conectado", timeout=6000)

        page_a.set_input_files(
            "input[type='file']",
            {"name": "sse-sync.txt", "mimeType": "text/plain", "buffer": b"sync entre abas"},
        )
        page_a.wait_for_selector("text=enviado: sse-sync.txt", timeout=6000)
        page_b.wait_for_selector("code:has-text('sse-sync.txt')", timeout=6000)

    def test_download_dispara_arquivo_no_browser(self, live_server, browser_context):
        page = browser_context.new_page()
        page.goto(live_server, wait_until="domcontentloaded")

        page.set_input_files(
            "input[type='file']",
            {"name": "download-me.txt", "mimeType": "text/plain", "buffer": b"conteudo para baixar"},
        )
        page.wait_for_selector("code:has-text('download-me.txt')", timeout=6000)

        with page.expect_download(timeout=6000) as dl_info:
            page.locator("tr", has=page.locator("code", has_text="download-me.txt")).get_by_role(
                "button", name="Baixar"
            ).click()

        download = dl_info.value
        assert download.suggested_filename == "download-me.txt"
