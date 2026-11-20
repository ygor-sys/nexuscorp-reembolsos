"""Máquina de estados do ciclo de vida de uma solicitação (seção 6 do enunciado).

Módulo puro (sem banco nem HTTP): é a única fonte de verdade sobre quais transições
são permitidas. Qualquer par (situação, ação) fora da tabela é rejeitado.
"""
from .enums import Acao, Situacao

TRANSICOES: dict[tuple[Situacao, Acao], Situacao] = {
    (Situacao.RASCUNHO, Acao.ENVIAR): Situacao.AGUARDANDO_GESTOR,
    (Situacao.AGUARDANDO_GESTOR, Acao.GESTOR_APROVAR): Situacao.AGUARDANDO_FINANCEIRO,
    (Situacao.AGUARDANDO_GESTOR, Acao.GESTOR_RECUSAR): Situacao.RECUSADA,
    (Situacao.AGUARDANDO_FINANCEIRO, Acao.FINANCEIRO_APROVAR): Situacao.APROVADA,
    (Situacao.AGUARDANDO_FINANCEIRO, Acao.FINANCEIRO_RECUSAR): Situacao.RECUSADA,
    (Situacao.APROVADA, Acao.PAGAR): Situacao.PAGA,
}

SITUACOES_ENCERRADAS = (Situacao.PAGA, Situacao.RECUSADA)

_MOTIVOS: dict[Situacao, str] = {
    Situacao.RASCUNHO: "A solicitação ainda é um rascunho e não foi enviada para análise.",
    Situacao.AGUARDANDO_GESTOR: "A solicitação ainda aguarda a análise do gestor (RN08).",
    Situacao.AGUARDANDO_FINANCEIRO: "A solicitação já foi aprovada pelo gestor e aguarda a análise do financeiro.",
    Situacao.APROVADA: "A solicitação já foi aprovada pelo financeiro e aguarda o registro do pagamento.",
    Situacao.PAGA: "Solicitação encerrada (paga); não admite novas operações.",
    Situacao.RECUSADA: "Solicitação encerrada (recusada); não admite novas operações.",
}


class TransicaoInvalida(Exception):
    """A ação solicitada é incompatível com a situação atual da solicitação."""


def proxima_situacao(atual: Situacao, acao: Acao) -> Situacao:
    try:
        return TRANSICOES[(atual, acao)]
    except KeyError:
        motivo = _MOTIVOS[atual]
        if acao is Acao.PAGAR and atual not in SITUACOES_ENCERRADAS:
            motivo += " O pagamento só é permitido após a aprovação financeira (RN10)."
        raise TransicaoInvalida(
            f"Operação '{acao.value}' incompatível com a situação '{atual.value}'. {motivo}"
        ) from None
