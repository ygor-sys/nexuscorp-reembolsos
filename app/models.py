"""Modelo de dados (tabelas) - SQLModel/SQLAlchemy."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .enums import Categoria, Decisao, Etapa, Perfil, Situacao
from .utils import agora


class Departamento(SQLModel, table=True):
    __tablename__ = "departamentos"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(max_length=80, unique=True, index=True)


class Usuario(SQLModel, table=True):
    __tablename__ = "usuarios"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(max_length=120)
    email: str = Field(max_length=254, unique=True, index=True)
    senha_hash: str  # nunca o texto da senha (RN13)
    perfil: Perfil = Field(default=Perfil.COLABORADOR)
    departamento_id: int = Field(foreign_key="departamentos.id", index=True)
    ativo: bool = Field(default=True)
    # Incrementado quando a senha muda: invalida todos os tokens emitidos antes (RN14).
    token_version: int = Field(default=0)
    criado_em: datetime = Field(default_factory=agora)


class Reembolso(SQLModel, table=True):
    __tablename__ = "reembolsos"
    __table_args__ = (
        # RN05: o mesmo colaborador não repete a referência de comprovante.
        UniqueConstraint("solicitante_id", "comprovante_chave", name="uq_solicitante_comprovante"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    solicitante_id: int = Field(foreign_key="usuarios.id", index=True)
    # Departamento do solicitante no momento do registro (base da responsabilidade do gestor, RN03).
    departamento_id: int = Field(foreign_key="departamentos.id", index=True)
    categoria: Categoria = Field(index=True)
    valor_centavos: int  # dinheiro em centavos inteiros: sem erro de arredondamento
    data_despesa: date
    justificativa: str = Field(max_length=500)
    comprovante_ref: str = Field(max_length=100)
    comprovante_chave: str = Field(max_length=100)  # comprovante_ref normalizado (casefold)
    situacao: Situacao = Field(default=Situacao.RASCUNHO, index=True)
    criado_em: datetime = Field(default_factory=agora)
    atualizado_em: datetime = Field(default_factory=agora)


class HistoricoAnalise(SQLModel, table=True):
    __tablename__ = "historico_analises"

    id: Optional[int] = Field(default=None, primary_key=True)
    reembolso_id: int = Field(foreign_key="reembolsos.id", index=True)
    responsavel_id: int = Field(foreign_key="usuarios.id", index=True)
    etapa: Etapa
    decisao: Decisao
    observacao: Optional[str] = Field(default=None, max_length=500)
    data_hora: datetime = Field(default_factory=agora)


class TokenRevogado(SQLModel, table=True):
    """Tokens encerrados por logout (RN14). Linhas expiradas são limpas no próprio logout."""

    __tablename__ = "tokens_revogados"

    jti: str = Field(primary_key=True, max_length=64)
    expira_em: datetime
