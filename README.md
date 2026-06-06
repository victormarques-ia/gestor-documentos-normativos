# Equipe 08 — Gestor de Documentos Normativos

**CIN0143 — Introdução aos Sistemas Distribuídos e Redes de Computadores**
Universidade Federal de Pernambuco — Centro de Informática
Docente: David J M Cavalcanti

**Integrantes**
- Gabriel Albertin Vieira
- Ithalo Rannieri Araujo Soares
- Talisson Mendes
- Tiago Ferreira
- Victor Silva Marques de Oliveira

---

## Descrição

Sistema distribuído **cliente-servidor** para **upload, download e listagem de
documentos de texto** (manuais e normas). O servidor escuta em **porta fixa**,
aceita **múltiplas conexões** e suporta **concorrência de leitura**: vários
clientes podem baixar o mesmo documento ao mesmo tempo, enquanto o servidor
segue aceitando novas conexões.

Este projeto é a **evolução** da atividade anterior, feita com **sockets TCP
puros** em Python, agora reimplementada sobre o framework **FastAPI**. Os três
comandos do protocolo original (`DIR`, `GET`, `PUT`) são mapeados para
**endpoints REST**.

## Decisão tecnológica e justificativa

**Framework escolhido: FastAPI (Python) + Uvicorn.**

- **Evolui** a base que já temos: a atividade em sockets foi escrita em Python,
  então reaproveitamos o padrão de validação anti *path-traversal* e a
  organização do `storage/`, em vez de reescrever do zero.
- **Testável de imediato:** o FastAPI gera **Swagger UI** em `/docs`, permitindo
  exercitar os endpoints pelo navegador sem nenhum frontend.
- **Porta fixa e múltiplas conexões** nativas via Uvicorn (servidor ASGI).
- **Concorrência de leitura:** o ASGI roda endpoints síncronos no *threadpool*
  do Starlette, casando bem com o `RWLock` baseado em *threads* portado da
  versão em sockets.

## Estrutura de pastas

```
projeto-sistemas-distribuidos-equipe-8/
├── README.md                    # este arquivo (visão geral, atemporal)
├── requirements.txt
├── conftest.py                  # torna backend/app importável nos testes
├── backend/
│   ├── app/
│   │   ├── main.py              # app FastAPI, /health, startup do estado
│   │   ├── config.py            # porta, storage, extensões, tamanho máx.
│   │   ├── storage.py           # estado em memória + operações + validações
│   │   ├── models.py            # Pydantic: FileMeta, DirResponse
│   │   ├── deps.py              # injeção do Storage
│   │   └── routes/files.py      # endpoints REST
│   └── storage/                 # pasta física dos documentos
├── tests/test_api.py            # testes pytest da API
└── docs/
    ├── protocolo.md             # especificação do contrato REST
    └── entregas/                # documentação por entrega
        └── entrega-1.md
```

## Como rodar

Pré-requisito: **Python 3.10+**.

```bash
# 1. Ambiente virtual e dependências
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Subir o servidor (porta fixa 8000)
cd backend
uvicorn app.main:app --reload --port 8000
```

Servidor no ar em `http://localhost:8000`. Abra **`http://localhost:8000/docs`**
para a interface interativa (Swagger).

## Como testar

**Pelo navegador:** acesse `/docs` e use os botões *Try it out* dos endpoints.

**Por linha de comando:** ver os comandos `curl` no [doc da entrega atual](docs/entregas/entrega-1.md#verificação).

**Testes automatizados** (a partir da raiz do projeto):

```bash
pytest -v
```

## Entregas

Cada entrega tem um documento próprio descrevendo escopo, itens entregues e
como verificar. O protocolo REST do servidor está em [`docs/protocolo.md`](docs/protocolo.md).

| # | Documento | Foco |
|---|---|---|
| **1** | [`docs/entregas/entrega-1.md`](docs/entregas/entrega-1.md) | Arquitetura e Escopo |
