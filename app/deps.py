"""Dependências de autenticação e autorização por perfil."""
from dataclasses import dataclass
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from .database import get_session
from .enums import Perfil
from .models import TokenRevogado, Usuario
from .security import decodificar_token

bearer = HTTPBearer(auto_error=False, description="Token JWT obtido em POST /auth/login.")


def _nao_autenticado() -> HTTPException:
    # Mensagem única para qualquer falha de identificação: não revela o motivo.
    return HTTPException(
        status_code=401,
        detail="Não autenticado: token ausente, inválido, expirado ou encerrado.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@dataclass
class SessaoAutenticada:
    usuario: Usuario
    payload: dict


def sessao_atual(
    credenciais: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> SessaoAutenticada:
    """RN01 e RN14: valida assinatura, validade, revogação, versão do token e usuário ativo."""
    if credenciais is None:
        raise _nao_autenticado()
    try:
        payload = decodificar_token(credenciais.credentials)
        usuario_id = int(payload["sub"])
        versao = int(payload.get("tv", -1))
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise _nao_autenticado() from None
    if session.get(TokenRevogado, payload["jti"]) is not None:
        raise _nao_autenticado()
    usuario = session.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo or usuario.token_version != versao:
        raise _nao_autenticado()
    return SessaoAutenticada(usuario=usuario, payload=payload)


def usuario_atual(sessao: Annotated[SessaoAutenticada, Depends(sessao_atual)]) -> Usuario:
    return sessao.usuario


UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]


def exigir_perfil(*perfis: Perfil):
    """Fábrica de dependência: 403 se o perfil do usuário (lido do banco) não for permitido."""

    def _verificar(usuario: UsuarioLogado) -> Usuario:
        if usuario.perfil not in perfis:
            permitidos = ", ".join(p.value for p in perfis)
            raise HTTPException(status_code=403, detail=f"Operação restrita ao(s) perfil(is): {permitidos}.")
        return usuario

    return _verificar
