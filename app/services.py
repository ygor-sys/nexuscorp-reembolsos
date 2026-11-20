"""Regras de negócio da gestão de reembolsos (RN02 a RN12)."""
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, and_, col, or_, select

from . import workflow
from .enums import Acao, Categoria, Decisao, Etapa, Perfil, Situacao
from .models import HistoricoAnalise, Reembolso, Usuario
from .schemas import HistoricoOut, ReembolsoAtualizar, ReembolsoCriar, ReembolsoOut
from .utils import agora

NAO_ENCONTRADA = "Solicitação não encontrada."


def _erro(codigo: int, mensagem: str) -> HTTPException:
    return HTTPException(status_code=codigo, detail=mensagem)


def para_centavos(valor: Decimal) -> int:
    return int((valor * 100).to_integral_value())


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise _erro(409, "RN05: já existe uma solicitação sua com esta referência de comprovante.") from None


# ------------------------------------------------------------------------------ saídas
def para_saida(session: Session, r: Reembolso) -> ReembolsoOut:
    solicitante = session.get(Usuario, r.solicitante_id)
    return ReembolsoOut(
        id=r.id,
        solicitante_id=r.solicitante_id,
        solicitante_nome=solicitante.nome if solicitante else "",
        departamento_id=r.departamento_id,
        categoria=r.categoria,
        valor=r.valor_centavos / 100,
        data_despesa=r.data_despesa,
        justificativa=r.justificativa,
        comprovante_ref=r.comprovante_ref,
        situacao=r.situacao,
        criado_em=r.criado_em,
        atualizado_em=r.atualizado_em,
    )


# ------------------------------------------------------------------- escopo de visibilidade
def condicao_escopo(usuario: Usuario):
    """Define o que cada usuário pode LER (RN02, RN03). Rascunhos são privados do autor."""
    propria = col(Reembolso.solicitante_id) == usuario.id
    if usuario.perfil == Perfil.GESTOR:
        do_departamento = and_(
            col(Reembolso.departamento_id) == usuario.departamento_id,
            col(Reembolso.situacao) != Situacao.RASCUNHO,
        )
        return or_(propria, do_departamento)
    if usuario.perfil == Perfil.FINANCEIRO:
        liberadas = col(Reembolso.situacao).in_(
            [Situacao.AGUARDANDO_FINANCEIRO, Situacao.APROVADA, Situacao.PAGA]
        )
        recusadas_pelo_financeiro = and_(
            col(Reembolso.situacao) == Situacao.RECUSADA,
            col(Reembolso.id).in_(
                select(HistoricoAnalise.reembolso_id).where(
                    HistoricoAnalise.etapa == Etapa.FINANCEIRO,
                    HistoricoAnalise.decisao == Decisao.RECUSADA,
                )
            ),
        )
        return or_(propria, liberadas, recusadas_pelo_financeiro)
    return propria


def listar(
    session: Session,
    usuario: Usuario,
    departamento_id: Optional[int],
    situacao: Optional[Situacao],
    categoria: Optional[Categoria],
    skip: int,
    limit: int,
) -> list[Reembolso]:
    stmt = select(Reembolso).where(condicao_escopo(usuario))
    if departamento_id is not None:
        stmt = stmt.where(Reembolso.departamento_id == departamento_id)
    if situacao is not None:
        stmt = stmt.where(Reembolso.situacao == situacao)
    if categoria is not None:
        stmt = stmt.where(Reembolso.categoria == categoria)
    stmt = stmt.order_by(col(Reembolso.id).desc()).offset(skip).limit(limit)
    return list(session.exec(stmt).all())


def obter_visivel(session: Session, usuario: Usuario, reembolso_id: int) -> Reembolso:
    """Fora do escopo = 404, idêntico ao de um id inexistente (não revela que o registro existe)."""
    r = session.exec(select(Reembolso).where(Reembolso.id == reembolso_id, condicao_escopo(usuario))).first()
    if r is None:
        raise _erro(404, NAO_ENCONTRADA)
    return r


def listar_historico(session: Session, usuario: Usuario, reembolso_id: int) -> list[HistoricoOut]:
    obter_visivel(session, usuario, reembolso_id)
    registros = session.exec(
        select(HistoricoAnalise)
        .where(HistoricoAnalise.reembolso_id == reembolso_id)
        .order_by(col(HistoricoAnalise.id))
    ).all()
    saida = []
    for h in registros:
        responsavel = session.get(Usuario, h.responsavel_id)
        saida.append(
            HistoricoOut(
                id=h.id,
                reembolso_id=h.reembolso_id,
                responsavel_id=h.responsavel_id,
                responsavel_nome=responsavel.nome,
                responsavel_perfil=responsavel.perfil,
                etapa=h.etapa,
                decisao=h.decisao,
                observacao=h.observacao,
                data_hora=h.data_hora,
            )
        )
    return saida


# --------------------------------------------------------------- operações do solicitante
def _checar_duplicidade(session: Session, solicitante_id: int, ref: str, ignorar_id: Optional[int] = None) -> None:
    stmt = select(Reembolso.id).where(
        Reembolso.solicitante_id == solicitante_id,
        Reembolso.comprovante_chave == ref.casefold(),
    )
    if ignorar_id is not None:
        stmt = stmt.where(Reembolso.id != ignorar_id)
    if session.exec(stmt).first() is not None:
        raise _erro(409, "RN05: já existe uma solicitação sua com esta referência de comprovante.")


def obter_proprio(session: Session, usuario: Usuario, reembolso_id: int) -> Reembolso:
    r = session.get(Reembolso, reembolso_id)
    if r is None or r.solicitante_id != usuario.id:
        raise _erro(404, NAO_ENCONTRADA)
    return r


def _exigir_rascunho(r: Reembolso, acao: str) -> None:
    if r.situacao != Situacao.RASCUNHO:
        detalhe = (
            f"RN07: uma solicitação na situação '{r.situacao.value}' não pode ser {acao}; "
            "isso só é possível enquanto ela estiver em rascunho."
        )
        if r.situacao in workflow.SITUACOES_ENCERRADAS:
            detalhe += " Solicitações encerradas são imutáveis."
        raise _erro(409, detalhe)


def criar(session: Session, usuario: Usuario, dados: ReembolsoCriar) -> Reembolso:
    _checar_duplicidade(session, usuario.id, dados.comprovante_ref)
    r = Reembolso(
        solicitante_id=usuario.id,
        departamento_id=usuario.departamento_id,
        categoria=dados.categoria,
        valor_centavos=para_centavos(dados.valor),
        data_despesa=dados.data_despesa,
        justificativa=dados.justificativa,
        comprovante_ref=dados.comprovante_ref,
        comprovante_chave=dados.comprovante_ref.casefold(),
    )
    session.add(r)
    _commit(session)
    session.refresh(r)
    return r


def atualizar(session: Session, usuario: Usuario, reembolso_id: int, dados: ReembolsoAtualizar) -> Reembolso:
    r = obter_proprio(session, usuario, reembolso_id)
    _exigir_rascunho(r, "alterada")
    campos = dados.model_dump(exclude_unset=True)
    if "valor" in campos:
        r.valor_centavos = para_centavos(campos.pop("valor"))
    if "comprovante_ref" in campos:
        ref = campos.pop("comprovante_ref")
        _checar_duplicidade(session, usuario.id, ref, ignorar_id=r.id)
        r.comprovante_ref = ref
        r.comprovante_chave = ref.casefold()
    for campo, valor in campos.items():
        setattr(r, campo, valor)
    r.atualizado_em = agora()
    session.add(r)
    _commit(session)
    session.refresh(r)
    return r


def excluir(session: Session, usuario: Usuario, reembolso_id: int) -> None:
    r = obter_proprio(session, usuario, reembolso_id)
    _exigir_rascunho(r, "excluída")
    session.delete(r)
    session.commit()


def enviar(session: Session, usuario: Usuario, reembolso_id: int) -> Reembolso:
    r = obter_proprio(session, usuario, reembolso_id)
    return _transicionar(session, r, Acao.ENVIAR, usuario, Etapa.SUBMISSAO, Decisao.ENVIADA, None)


# ------------------------------------------------------- análise do gestor e do financeiro
def _transicionar(
    session: Session,
    r: Reembolso,
    acao: Acao,
    usuario: Usuario,
    etapa: Etapa,
    decisao: Decisao,
    observacao: Optional[str],
) -> Reembolso:
    """Muda a situação e grava o histórico na MESMA transação (RN12): ou os dois, ou nenhum."""
    try:
        nova = workflow.proxima_situacao(r.situacao, acao)
    except workflow.TransicaoInvalida as exc:
        raise _erro(409, str(exc)) from None
    r.situacao = nova
    r.atualizado_em = agora()
    session.add(r)
    session.add(
        HistoricoAnalise(
            reembolso_id=r.id,
            responsavel_id=usuario.id,
            etapa=etapa,
            decisao=decisao,
            observacao=observacao,
        )
    )
    session.commit()
    session.refresh(r)
    return r


def _carregar_para_decisao(session: Session, usuario: Usuario, reembolso_id: int) -> Reembolso:
    r = session.get(Reembolso, reembolso_id)
    # Rascunho alheio é invisível para todos, exceto o autor.
    if r is None or (r.situacao == Situacao.RASCUNHO and r.solicitante_id != usuario.id):
        raise _erro(404, NAO_ENCONTRADA)
    return r


def _vedar_autoanalise(r: Reembolso, usuario: Usuario) -> None:
    if r.solicitante_id == usuario.id:  # RN09
        raise _erro(403, "RN09: você não pode analisar ou pagar uma solicitação de sua própria autoria.")


def _observacao(texto: Optional[str], obrigatoria: bool) -> Optional[str]:
    texto = texto.strip() if texto else None
    if obrigatoria and not texto:  # RN11 (defesa em profundidade; o schema já exige)
        raise _erro(422, "RN11: toda recusa exige uma justificativa.")
    return texto or None


def decidir_como_gestor(
    session: Session, usuario: Usuario, reembolso_id: int, aprovar: bool, observacao: Optional[str]
) -> Reembolso:
    r = _carregar_para_decisao(session, usuario, reembolso_id)
    if r.departamento_id != usuario.departamento_id:  # RN03
        raise _erro(403, "RN03: esta solicitação pertence a outro departamento; você não é o responsável por ela.")
    _vedar_autoanalise(r, usuario)
    obs = _observacao(observacao, obrigatoria=not aprovar)
    return _transicionar(
        session,
        r,
        Acao.GESTOR_APROVAR if aprovar else Acao.GESTOR_RECUSAR,
        usuario,
        Etapa.GESTOR,
        Decisao.APROVADA if aprovar else Decisao.RECUSADA,
        obs,
    )


def decidir_como_financeiro(
    session: Session, usuario: Usuario, reembolso_id: int, aprovar: bool, observacao: Optional[str]
) -> Reembolso:
    r = _carregar_para_decisao(session, usuario, reembolso_id)
    _vedar_autoanalise(r, usuario)
    obs = _observacao(observacao, obrigatoria=not aprovar)
    return _transicionar(
        session,
        r,
        Acao.FINANCEIRO_APROVAR if aprovar else Acao.FINANCEIRO_RECUSAR,
        usuario,
        Etapa.FINANCEIRO,
        Decisao.APROVADA if aprovar else Decisao.RECUSADA,
        obs,
    )


def registrar_pagamento(session: Session, usuario: Usuario, reembolso_id: int, observacao: Optional[str]) -> Reembolso:
    r = _carregar_para_decisao(session, usuario, reembolso_id)
    _vedar_autoanalise(r, usuario)
    return _transicionar(
        session, r, Acao.PAGAR, usuario, Etapa.PAGAMENTO, Decisao.PAGA, _observacao(observacao, obrigatoria=False)
    )
