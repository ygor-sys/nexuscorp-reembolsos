"""Ponto de entrada da API."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .database import criar_tabelas
from .routers import auth, departamentos, reembolsos, usuarios


@asynccontextmanager
async def lifespan(_app: FastAPI):
    criar_tabelas()
    yield


app = FastAPI(
    title="NexusCorp - Plataforma de Gestão de Reembolsos",
    version="1.0.0",
    description=(
        "API REST para centralizar solicitações de reembolso, com autenticação JWT, controle de "
        "acesso por perfil (colaborador, gestor, financeiro), fluxo de aprovação e histórico "
        "rastreável.\n\n"
        "**Como usar no Swagger:** faça `POST /auth/login`, copie o `access_token` e clique em "
        "*Authorize*.\n\n"
        "**Códigos de erro:** 401 identificação · 403 falta de permissão · 404 recurso fora do "
        "escopo · 409 conflito com regra de negócio/situação · 422 dados inválidos."
    ),
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def erro_de_validacao(_request: Request, exc: RequestValidationError):
    """422 enxuto: lista campo, mensagem e tipo, e NÃO devolve o valor recebido
    (evita ecoar senhas ou dados sensíveis na resposta - RN13)."""
    erros = [
        {"campo": ".".join(str(p) for p in e["loc"]), "mensagem": e["msg"], "tipo": e["type"]}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": erros})


app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(departamentos.router)
app.include_router(reembolsos.router)


@app.get("/saude", tags=["Infra"], summary="Verificação de disponibilidade")
def saude():
    return {"status": "ok"}
