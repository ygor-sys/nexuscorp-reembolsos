"""Enumerações do domínio."""
from enum import Enum


class Perfil(str, Enum):
    COLABORADOR = "colaborador"
    GESTOR = "gestor"
    FINANCEIRO = "financeiro"


class Categoria(str, Enum):
    ALIMENTACAO = "alimentacao"
    TRANSPORTE = "transporte"
    HOSPEDAGEM = "hospedagem"
    MATERIAIS = "materiais"


class Situacao(str, Enum):
    RASCUNHO = "rascunho"
    AGUARDANDO_GESTOR = "aguardando_gestor"
    AGUARDANDO_FINANCEIRO = "aguardando_financeiro"
    APROVADA = "aprovada"
    PAGA = "paga"
    RECUSADA = "recusada"


class Etapa(str, Enum):
    SUBMISSAO = "submissao"
    GESTOR = "gestor"
    FINANCEIRO = "financeiro"
    PAGAMENTO = "pagamento"


class Decisao(str, Enum):
    ENVIADA = "enviada"
    APROVADA = "aprovada"
    RECUSADA = "recusada"
    PAGA = "paga"


class Acao(str, Enum):
    ENVIAR = "enviar"
    GESTOR_APROVAR = "gestor_aprovar"
    GESTOR_RECUSAR = "gestor_recusar"
    FINANCEIRO_APROVAR = "financeiro_aprovar"
    FINANCEIRO_RECUSAR = "financeiro_recusar"
    PAGAR = "pagar"
