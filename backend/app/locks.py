"""
Controle de concorrência: lock leitor-escritor (RWLock) por arquivo.

Portado da versão em sockets (atv-socket-tcp/server.py). Preserva a semântica
"N leitores simultâneos OU 1 escritor exclusivo".

No FastAPI, os endpoints que tocam o disco rodam no threadpool do Starlette
(funções `def` ou via `run_in_threadpool`); por isso o lock baseado em threads
continua sendo o mecanismo correto — exatamente como no servidor de sockets.
"""
import threading
from contextlib import contextmanager


class RWLock:
    """Permite múltiplos leitores simultâneos ou um único escritor por vez."""

    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers = 0

    def acquire_read(self):
        with self._cond:
            self._readers += 1

    def release_read(self):
        with self._cond:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def acquire_write(self):
        # Adquire o lock interno e aguarda até não haver leitores ativos.
        self._cond.acquire()
        while self._readers > 0:
            self._cond.wait()

    def release_write(self):
        self._cond.release()

    @contextmanager
    def read(self):
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()

    @contextmanager
    def write(self):
        self.acquire_write()
        try:
            yield
        finally:
            self.release_write()


class LockManager:
    """Mantém um RWLock por arquivo, criado sob demanda de forma thread-safe."""

    def __init__(self):
        self._locks: dict[str, RWLock] = {}
        self._meta_lock = threading.Lock()  # protege o dicionário de locks

    def get(self, filename: str) -> RWLock:
        with self._meta_lock:
            if filename not in self._locks:
                self._locks[filename] = RWLock()
            return self._locks[filename]
