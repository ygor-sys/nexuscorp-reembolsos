"""Consulta de departamentos (necessária para o autocadastro)."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from ..database import get_session
from ..models import Departamento
from ..schemas import DepartamentoOut

router = APIRouter(prefix="/departamentos", tags=["Departamentos"])


@router.get("", response_model=list[DepartamentoOut], summary="Lista departamentos (id e nome; público)")
def listar_departamentos(session: Annotated[Session, Depends(get_session)]):
    departamentos = session.exec(select(Departamento).order_by(col(Departamento.nome))).all()
    return [DepartamentoOut(id=d.id, nome=d.nome) for d in departamentos]
