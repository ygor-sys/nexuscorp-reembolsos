"""Contratos de entrada e saída da API (validação dos dados recebidos)."""
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import Categoria, Decisao, Etapa, Perfil, Situacao
from .utils import hoje

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Estrito(BaseModel):
    """Base dos contratos de entrada: campos desconhecidos são rejeitados (RN15)."""

    model_config = ConfigDict(extra="forbid")


def _limpar(valor):
    return valor.strip() if isinstance(valor, str) else valor


def _senha_forte(senha: str) -> str:
    if not (any(c.isalpha() for c in senha) and any(c.isdigit() for c in senha)):
        raise ValueError("A senha deve conter ao menos uma letra e um número.")
    return senha


def _email_valido(email: str) -> str:
    if not _EMAIL.match(email):
        raise ValueError("E-mail inválido.")
    return email


# ----------------------------------------------------------------- autenticação / usuários
class CadastroIn(Estrito):
    """Autocadastro: sempre cria um COLABORADOR. 'perfil' e demais campos extras são rejeitados."""

    nome: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254)
    senha: str = Field(min_length=8, max_length=128)
    departamento_id: int = Field(ge=1)

    @field_validator("nome", mode="before")
    @classmethod
    def _nome(cls, v):
        return _limpar(v)

    @field_validator("email", mode="before")
    @classmethod
    def _email_antes(cls, v):
        return _limpar(v).lower() if isinstance(v, str) else v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return _email_valido(v)

    @field_validator("senha")
    @classmethod
    def _senha(cls, v):
        return _senha_forte(v)


class LoginIn(Estrito):
    email: str = Field(min_length=1, max_length=254)
    senha: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _email_antes(cls, v):
        return _limpar(v).lower() if isinstance(v, str) else v


class UsuarioAtualizar(Estrito):
    """Atualização do próprio cadastro. Perfil, departamento e situação NÃO são aceitos (RN15)."""

    nome: Optional[str] = Field(default=None, min_length=2, max_length=120)
    email: Optional[str] = Field(default=None, max_length=254)
    senha_atual: Optional[str] = Field(default=None, min_length=1, max_length=128)
    nova_senha: Optional[str] = Field(default=None, min_length=8, max_length=128)

    @field_validator("nome", mode="before")
    @classmethod
    def _nome(cls, v):
        return _limpar(v)

    @field_validator("email", mode="before")
    @classmethod
    def _email_antes(cls, v):
        return _limpar(v).lower() if isinstance(v, str) else v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return None if v is None else _email_valido(v)

    @field_validator("nova_senha")
    @classmethod
    def _senha(cls, v):
        return None if v is None else _senha_forte(v)

    @model_validator(mode="after")
    def _consistencia(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        nulos = [c for c in self.model_fields_set if getattr(self, c) is None]
        if nulos:
            raise ValueError(f"Valores nulos não são aceitos: {', '.join(sorted(nulos))}.")
        if self.nova_senha and not self.senha_atual:
            raise ValueError("Para trocar a senha, informe 'senha_atual'.")
        if self.senha_atual and not self.nova_senha:
            raise ValueError("'senha_atual' só é usada junto com 'nova_senha'.")
        return self


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Validade do token, em segundos.")


class UsuarioOut(BaseModel):
    """Nunca inclui credenciais (RN13)."""

    id: int
    nome: str
    email: str
    perfil: Perfil
    departamento_id: int


class DepartamentoOut(BaseModel):
    id: int
    nome: str


def usuario_saida(u) -> UsuarioOut:
    return UsuarioOut(id=u.id, nome=u.nome, email=u.email, perfil=u.perfil, departamento_id=u.departamento_id)


# ------------------------------------------------------------------------------- reembolsos
class ReembolsoCriar(Estrito):
    """Solicitante, departamento e situação são definidos pelo servidor, nunca pelo cliente."""

    categoria: Categoria
    valor: Decimal = Field(gt=0, max_digits=10, decimal_places=2, description="RN04: maior que zero, em reais.")
    data_despesa: date
    justificativa: str = Field(min_length=5, max_length=500)
    comprovante_ref: str = Field(min_length=3, max_length=100)

    @field_validator("justificativa", "comprovante_ref", mode="before")
    @classmethod
    def _limpar_textos(cls, v):
        return _limpar(v)

    @field_validator("data_despesa")
    @classmethod
    def _sem_data_futura(cls, v):
        if v > hoje():
            raise ValueError("RN06: a data da despesa não pode estar no futuro.")
        return v


class ReembolsoAtualizar(Estrito):
    categoria: Optional[Categoria] = None
    valor: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    data_despesa: Optional[date] = None
    justificativa: Optional[str] = Field(default=None, min_length=5, max_length=500)
    comprovante_ref: Optional[str] = Field(default=None, min_length=3, max_length=100)

    @field_validator("justificativa", "comprovante_ref", mode="before")
    @classmethod
    def _limpar_textos(cls, v):
        return _limpar(v)

    @field_validator("data_despesa")
    @classmethod
    def _sem_data_futura(cls, v):
        if v is not None and v > hoje():
            raise ValueError("RN06: a data da despesa não pode estar no futuro.")
        return v

    @model_validator(mode="after")
    def _consistencia(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        nulos = [c for c in self.model_fields_set if getattr(self, c) is None]
        if nulos:
            raise ValueError(f"Valores nulos não são aceitos: {', '.join(sorted(nulos))}.")
        return self


class AprovacaoIn(Estrito):
    observacao: Optional[str] = Field(default=None, max_length=500)

    @field_validator("observacao", mode="before")
    @classmethod
    def _limpar_obs(cls, v):
        v = _limpar(v)
        return v or None


class RecusaIn(Estrito):
    observacao: str = Field(min_length=5, max_length=500, description="RN11: justificativa obrigatória.")

    @field_validator("observacao", mode="before")
    @classmethod
    def _limpar_obs(cls, v):
        return _limpar(v)


class ReembolsoOut(BaseModel):
    id: int
    solicitante_id: int
    solicitante_nome: str
    departamento_id: int
    categoria: Categoria
    valor: float
    data_despesa: date
    justificativa: str
    comprovante_ref: str
    situacao: Situacao
    criado_em: datetime
    atualizado_em: datetime


class HistoricoOut(BaseModel):
    id: int
    reembolso_id: int
    responsavel_id: int
    responsavel_nome: str
    responsavel_perfil: Perfil
    etapa: Etapa
    decisao: Decisao
    observacao: Optional[str]
    data_hora: datetime
