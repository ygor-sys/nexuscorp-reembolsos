"""Solicitações de reembolso: solicitante, gestor e financeiro."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlmodel import Session

from .. import services
from ..database import get_session
from ..deps import UsuarioLogado, exigir_perfil
from ..enums import Categoria, Perfil, Situacao
from ..models import Usuario
from ..schemas import (
    AprovacaoIn,
    HistoricoOut,
    RecusaIn,
    ReembolsoAtualizar,
    ReembolsoCriar,
    ReembolsoOut,
)

router = APIRouter(
    prefix="/reembolsos",
    responses={401: {"description": "Não autenticado"}},
)

Sessao = Annotated[Session, Depends(get_session)]
Gestor = Annotated[Usuario, Depends(exigir_perfil(Perfil.GESTOR))]
Financeiro = Annotated[Usuario, Depends(exigir_perfil(Perfil.FINANCEIRO))]
IdReembolso = Annotated[int, Path(ge=1, description="Identificador da solicitação")]

R404 = {404: {"description": "Solicitação inexistente ou fora do seu escopo"}}
R409 = {409: {"description": "Operação incompatível com a situação atual / regra de negócio"}}
R403 = {403: {"description": "Perfil sem permissão, outro departamento (RN03) ou própria autoria (RN09)"}}


# ----------------------------------------------------------------------- solicitante
@router.post(
    "",
    tags=["Reembolsos"],
    response_model=ReembolsoOut,
    status_code=201,
    summary="Registra uma solicitação (nasce em rascunho)",
    responses={**R409, 422: {"description": "Dados inválidos (RN04, RN06, campos extras...)"}},
)
def registrar(dados: ReembolsoCriar, usuario: UsuarioLogado, session: Sessao):
    return services.para_saida(session, services.criar(session, usuario, dados))


@router.get(
    "",
    tags=["Reembolsos"],
    response_model=list[ReembolsoOut],
    summary="Lista as solicitações que o usuário pode ver (com filtros)",
)
def listar(
    usuario: UsuarioLogado,
    session: Sessao,
    departamento_id: Optional[int] = Query(default=None, ge=1),
    situacao: Optional[Situacao] = None,
    categoria: Optional[Categoria] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """Colaborador: só as suas. Gestor: as do seu departamento já enviadas, mais as suas.
    Financeiro: as encaminhadas pelos gestores, mais as suas. Os filtros apenas restringem
    esse escopo; nunca o ampliam."""
    registros = services.listar(session, usuario, departamento_id, situacao, categoria, skip, limit)
    return [services.para_saida(session, r) for r in registros]


@router.get("/{reembolso_id}",
    tags=["Reembolsos"], response_model=ReembolsoOut, summary="Detalhes de uma solicitação", responses=R404)
def detalhar(reembolso_id: IdReembolso, usuario: UsuarioLogado, session: Sessao):
    return services.para_saida(session, services.obter_visivel(session, usuario, reembolso_id))


@router.get(
    "/{reembolso_id}/historico",
    tags=["Reembolsos"],
    response_model=list[HistoricoOut],
    summary="Histórico de decisões de uma solicitação",
    responses=R404,
)
def historico(reembolso_id: IdReembolso, usuario: UsuarioLogado, session: Sessao):
    return services.listar_historico(session, usuario, reembolso_id)


@router.patch(
    "/{reembolso_id}",
    tags=["Reembolsos"],
    response_model=ReembolsoOut,
    summary="Altera uma solicitação (somente rascunho, somente o autor)",
    responses={**R404, **R409},
)
def atualizar(reembolso_id: IdReembolso, dados: ReembolsoAtualizar, usuario: UsuarioLogado, session: Sessao):
    return services.para_saida(session, services.atualizar(session, usuario, reembolso_id, dados))


@router.delete(
    "/{reembolso_id}",
    tags=["Reembolsos"],
    status_code=204,
    summary="Exclui uma solicitação (somente rascunho, somente o autor)",
    responses={**R404, **R409},
)
def excluir(reembolso_id: IdReembolso, usuario: UsuarioLogado, session: Sessao):
    services.excluir(session, usuario, reembolso_id)
    return Response(status_code=204)


@router.post(
    "/{reembolso_id}/enviar",
    tags=["Reembolsos"],
    response_model=ReembolsoOut,
    summary="Encaminha o rascunho para análise do gestor",
    responses={**R404, **R409},
)
def enviar(reembolso_id: IdReembolso, usuario: UsuarioLogado, session: Sessao):
    return services.para_saida(session, services.enviar(session, usuario, reembolso_id))


# --------------------------------------------------------------------------- gestor
@router.post(
    "/{reembolso_id}/gestor/aprovar",
    response_model=ReembolsoOut,
    tags=["Gestor"],
    summary="Gestor aprova e encaminha ao financeiro",
    responses={**R403, **R404, **R409},
)
def gestor_aprovar(
    reembolso_id: IdReembolso, usuario: Gestor, session: Sessao, dados: Optional[AprovacaoIn] = None
):
    obs = dados.observacao if dados else None
    return services.para_saida(session, services.decidir_como_gestor(session, usuario, reembolso_id, True, obs))


@router.post(
    "/{reembolso_id}/gestor/recusar",
    response_model=ReembolsoOut,
    tags=["Gestor"],
    summary="Gestor recusa (justificativa obrigatória)",
    responses={**R403, **R404, **R409},
)
def gestor_recusar(reembolso_id: IdReembolso, dados: RecusaIn, usuario: Gestor, session: Sessao):
    return services.para_saida(
        session, services.decidir_como_gestor(session, usuario, reembolso_id, False, dados.observacao)
    )


# ------------------------------------------------------------------------ financeiro
@router.post(
    "/{reembolso_id}/financeiro/aprovar",
    response_model=ReembolsoOut,
    tags=["Financeiro"],
    summary="Financeiro aprova a análise final",
    responses={**R403, **R404, **R409},
)
def financeiro_aprovar(
    reembolso_id: IdReembolso, usuario: Financeiro, session: Sessao, dados: Optional[AprovacaoIn] = None
):
    obs = dados.observacao if dados else None
    return services.para_saida(
        session, services.decidir_como_financeiro(session, usuario, reembolso_id, True, obs)
    )


@router.post(
    "/{reembolso_id}/financeiro/recusar",
    response_model=ReembolsoOut,
    tags=["Financeiro"],
    summary="Financeiro recusa (justificativa obrigatória)",
    responses={**R403, **R404, **R409},
)
def financeiro_recusar(reembolso_id: IdReembolso, dados: RecusaIn, usuario: Financeiro, session: Sessao):
    return services.para_saida(
        session, services.decidir_como_financeiro(session, usuario, reembolso_id, False, dados.observacao)
    )


@router.post(
    "/{reembolso_id}/financeiro/pagar",
    response_model=ReembolsoOut,
    tags=["Financeiro"],
    summary="Financeiro registra o pagamento (somente solicitações aprovadas)",
    responses={**R403, **R404, **R409},
)
def financeiro_pagar(
    reembolso_id: IdReembolso, usuario: Financeiro, session: Sessao, dados: Optional[AprovacaoIn] = None
):
    obs = dados.observacao if dados else None
    return services.para_saida(session, services.registrar_pagamento(session, usuario, reembolso_id, obs))
