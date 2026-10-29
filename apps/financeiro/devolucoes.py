"""Devolução pela plataforma (E10-04): parcela, autorização, estados, tentativa e liquidação.

Uma obrigação com comprador vira dinheiro devolvido em passos: o administrador autoriza, o sistema
grava a parcela com a chave de idempotência e agenda o estorno, a tarefa chama o provedor e aplica
cada resposta, e a conclusão liquida a obrigação no livro-razão. Na falha definitiva, o sistema
reconsulta o provedor antes de declarar a parcela elegível para a devolução excepcional (E10-06).

Ordem das travas: pagamento, situação do pedido (se houver), parcela e, por fim, as contas do
livro-razão. Autorização não é dinheiro devolvido: só a conclusão do estorno liquida.
"""

import logging
import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction

from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.alertas import abrir_alerta, resolver_alerta
from apps.financeiro.estornos import avisar_o_comprador
from apps.financeiro.livro import conta_da_obrigacao, saldo, travar_contas
from apps.financeiro.models import (
    ConfirmacaoDeDevolucaoExcepcional,
    HistoricoDaDevolucao,
    MeioDaDevolucaoExcepcional,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
    Reembolso,
    SituacaoDaParcela,
    TipoDeAlerta,
)
from apps.financeiro.obrigacoes import (
    _designacoes_ativas,
    _liquidado,
    liquidar_obrigacao,
    liquidar_obrigacao_fora_do_provedor,
)
from apps.financeiro.reserva import sem_cobertura_da_obrigacao
from apps.nucleo.auditoria import SISTEMA, _Sistema, registrar_auditoria
from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import (
    FalhaDefinitiva,
    FalhaTemporaria,
    Operacao,
    agendar_chamada,
    nao_encontrado,
    registrar_operacao,
)
from apps.pagamentos.consulta import consultar_antes_de_decidir, travar_pagamento
from apps.pagamentos.models import ChamadaAoProvedor, SituacaoDaChamada
from apps.pagamentos.provedor import (
    EstornoConsultado,
    NovoEstorno,
    PagamentoNaoEncontrado,
    Provedor,
    SaldoInsuficienteParaEstorno,
    SituacaoDoEstorno,
    obter_provedor,
)
from apps.pedidos.models import DestinoDoPagamento, SituacaoDoPedido

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
S = SituacaoDaParcela
FINAIS = (S.CONCLUIDA, S.CONCLUIDA_FORA_DA_PLATAFORMA)
ABERTAS = (S.SOLICITADA, S.FALHA_TEMPORARIA, S.EM_PROCESSAMENTO)
TENTATIVAS_PARA_ALERTAR = 3

TRANSICOES: dict[str, tuple[str, ...]] = {
    S.SOLICITADA: (S.FALHA_TEMPORARIA, S.EM_PROCESSAMENTO, S.CONCLUIDA, S.FALHA_DEFINITIVA),
    S.FALHA_TEMPORARIA: (S.FALHA_TEMPORARIA, S.EM_PROCESSAMENTO, S.CONCLUIDA, S.FALHA_DEFINITIVA),
    S.EM_PROCESSAMENTO: (S.CONCLUIDA, S.FALHA_DEFINITIVA),
    S.FALHA_DEFINITIVA: (S.ELEGIVEL_EXCEPCIONAL, S.EM_PROCESSAMENTO, S.CONCLUIDA),
    S.ELEGIVEL_EXCEPCIONAL: (S.CONCLUIDA_FORA_DA_PLATAFORMA, S.CONCLUIDA),
    S.CONCLUIDA: (),
    S.CONCLUIDA_FORA_DA_PLATAFORMA: (),
}


class DevolucaoRecusada(Exception):
    """A ação não pode ser feita agora; a mensagem diz o motivo."""


# --- leitura -----------------------------------------------------------------------------------


def pagamento_da_obrigacao(obrigacao: ObrigacaoComComprador) -> Any:
    """O pagamento que a devolução estorna: o que quitou o pedido do reembolso, ou o pagamento
    que não quitou (duplicidade, fora do prazo, sem pedido...). Outra origem: `ValueError`."""
    if obrigacao.origem_tipo == Reembolso._meta.label_lower:
        reembolso = Reembolso.objects.select_related("pedido__estado__quitado_por").get(
            pk=obrigacao.origem_id
        )
        quitado_por = reembolso.pedido.estado.quitado_por
        if quitado_por is None:
            raise ValueError("o pedido do reembolso não tem pagamento que o quitou")
        return quitado_por
    if obrigacao.origem_tipo == DestinoDoPagamento._meta.label_lower:
        return (
            DestinoDoPagamento.objects.select_related("pagamento")
            .get(pk=obrigacao.origem_id)
            .pagamento
        )
    raise ValueError("a origem da obrigação não é executável pela plataforma")


def situacao_da_devolucao(obrigacao: ObrigacaoComComprador) -> str:
    """`devida`, se não há parcela; senão, a situação da parcela."""
    parcela = ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).first()
    return "devida" if parcela is None else str(parcela.situacao)


# --- autor, travas e histórico ---------------------------------------------------------------


def _exigir_autor(autor: object, *, aceita_sistema: bool) -> Conta | None:
    if aceita_sistema and autor is SISTEMA:
        return None
    if (
        isinstance(autor, Conta)
        and autor.pk is not None
        and autor.papel == Papel.ADMINISTRADOR
        and autor.situacao == Situacao.ATIVA
    ):
        return autor
    raise PermissionDenied("só o administrador mexe nas devoluções")


def _travar_cadeia(parcela_pk: int) -> ParcelaDeDevolucao:
    """Pagamento, situação do pedido (se houver) e parcela, nessa ordem, e a parcela relida."""
    base = ParcelaDeDevolucao.objects.select_related("obrigacao").get(pk=parcela_pk)
    travar_pagamento(base.pagamento_id)
    if base.obrigacao.pedido_id is not None:
        SituacaoDoPedido.objects.select_for_update().get(pedido_id=base.obrigacao.pedido_id)
    return (
        ParcelaDeDevolucao.objects.select_for_update(of=("self",))
        .select_related("obrigacao", "pagamento")
        .get(pk=parcela_pk)
    )


def _historico(
    parcela: ParcelaDeDevolucao, autor: Conta | None, dados: dict[str, Any] | None = None
) -> None:
    HistoricoDaDevolucao.objects.create(
        parcela=parcela, situacao=parcela.situacao, autor=autor, dados=dados or {}
    )


def transicionar(
    parcela: ParcelaDeDevolucao,
    nova: str,
    *,
    autor: Conta | _Sistema,
    dados: dict[str, Any] | None = None,
) -> ParcelaDeDevolucao:
    """Muda a situação da parcela (já travada) e grava o histórico. Fora da tabela de transições:
    `DevolucaoRecusada`."""
    if nova not in TRANSICOES.get(parcela.situacao, ()):
        raise DevolucaoRecusada(f"transição inválida: {parcela.situacao} para {nova}")
    parcela.situacao = nova
    campos = ["situacao"]
    if nova in FINAIS:
        parcela.concluida_em = agora()
        campos.append("concluida_em")
    parcela.save(update_fields=campos)
    _historico(parcela, autor if isinstance(autor, Conta) else None, dados)
    return parcela


def _chave_do_alerta(parcela: ParcelaDeDevolucao) -> str:
    return f"parcela:{parcela.pk}"


def _dados_do_alerta(parcela: ParcelaDeDevolucao, **extra: Any) -> dict[str, Any]:
    return {
        "parcela": parcela.pk,
        "obrigacao": parcela.obrigacao_id,
        "valor": parcela.valor,
        "situacao": parcela.situacao,
        **extra,
    }


def _resolver(parcela: ParcelaDeDevolucao, tipo: str, motivo: str) -> None:
    resolver_alerta(tipo, _chave_do_alerta(parcela), motivo=motivo)


# --- autorização ------------------------------------------------------------------------------


def autorizar_devolucao(
    obrigacao: ObrigacaoComComprador, *, autor: Conta | _Sistema
) -> ParcelaDeDevolucao:
    """Autoriza a devolução: grava a parcela `solicitada`, com a chave de idempotência, e agenda o
    estorno. Repetir devolve a parcela existente. A reconsulta ao provedor vem antes da
    transação."""
    autor_conta = _exigir_autor(autor, aceita_sistema=True)
    pagamento = pagamento_da_obrigacao(obrigacao)
    consultar_antes_de_decidir(pagamento.referencia_externa)  # ConsultaAoProvedorFalhou
    with transaction.atomic():
        pagamento = travar_pagamento(pagamento.pk)
        if obrigacao.pedido_id is not None:
            SituacaoDoPedido.objects.select_for_update().get(pedido_id=obrigacao.pedido_id)
        existente = ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).first()
        if existente is not None:
            return existente
        destino = conta_da_obrigacao(obrigacao)
        travar_contas(destino)
        valor = obrigacao.devido - _liquidado(destino)
        if valor <= 0:
            raise DevolucaoRecusada("não há nada a devolver nesta obrigação")
        if pagamento.situacao != "aprovado":
            raise DevolucaoRecusada("o pagamento não está aprovado no provedor")
        if sem_cobertura_da_obrigacao(obrigacao) > 0:
            raise DevolucaoRecusada(
                "a obrigação não está coberta: é preciso cobrir antes, por designação da reserva, "
                "receita de serviço ou aporte"
            )
        ja_devolvido = sum(
            (p.valor for p in ParcelaDeDevolucao.objects.filter(pagamento_id=pagamento.pk)),
            valor * 0,
        )
        if ja_devolvido + valor > pagamento.valor:
            raise DevolucaoRecusada("a devolução passaria do valor do pagamento")
        parcela = ParcelaDeDevolucao.objects.create(
            obrigacao=obrigacao,
            pagamento=pagamento,
            valor=valor,
            situacao=S.SOLICITADA,
            chave_idempotencia=uuid.uuid4().hex,
            autorizada_por=autor_conta,
        )
        _historico(parcela, autor_conta, {"valor": valor})
        registrar_auditoria(
            autor,
            "financeiro.devolucao_autorizada",
            parcela,
            {"obrigacao": obrigacao.pk, "valor": valor, "pagamento": pagamento.pk},
        )
        agendar_chamada(
            "estornar", f"parcela:{parcela.pk}", chave_idempotencia=parcela.chave_idempotencia
        )
        avisar_o_comprador(parcela, S.SOLICITADA)
        return parcela


# --- nova tentativa ---------------------------------------------------------------------------


def tentar_devolucao_de_novo(
    parcela: ParcelaDeDevolucao, *, autor: Conta | _Sistema
) -> ParcelaDeDevolucao:
    """Antecipa a próxima tentativa de uma parcela em falha temporária, com a mesma chave."""
    autor_conta = _exigir_autor(autor, aceita_sistema=False)
    atual = ParcelaDeDevolucao.objects.select_related("pagamento").get(pk=parcela.pk)
    if atual.situacao != S.FALHA_TEMPORARIA:
        raise DevolucaoRecusada("só uma devolução com falha temporária pode ser tentada de novo")
    consultar_antes_de_decidir(atual.pagamento.referencia_externa)
    with transaction.atomic():
        travada = _travar_cadeia(parcela.pk)
        if travada.situacao != S.FALHA_TEMPORARIA:
            raise DevolucaoRecusada(
                "só uma devolução com falha temporária pode ser tentada de novo"
            )
        chamada = (
            ChamadaAoProvedor.objects.select_for_update()
            .filter(
                operacao="estornar",
                alvo=f"parcela:{travada.pk}",
                situacao=SituacaoDaChamada.PENDENTE,
            )
            .first()
        )
        if chamada is None:
            raise DevolucaoRecusada("não há tentativa pendente para esta devolução")
        chamada.proxima_em = agora()
        chamada.save(update_fields=["proxima_em"])
        _historico(travada, autor_conta, {"acao": "nova_tentativa"})
        return travada


# --- aplicação das respostas do provedor ------------------------------------------------------


def _pk_da_parcela(chamada: ChamadaAoProvedor) -> int:
    return int(chamada.alvo.split(":", 1)[1])


def _concluir_parcela(parcela: ParcelaDeDevolucao, estorno: EstornoConsultado) -> None:
    """O provedor concluiu o estorno: a parcela conclui e a obrigação é liquidada no livro."""
    parcela.id_estorno = estorno.id_estorno
    parcela.save(update_fields=["id_estorno"])
    transicionar(parcela, S.CONCLUIDA, autor=SISTEMA, dados={"id_estorno": estorno.id_estorno})
    avisar_o_comprador(parcela, S.CONCLUIDA)
    liquidar_obrigacao(parcela.obrigacao, parcela.valor, referencia=estorno.id_estorno)
    motivo = "devolução concluída"
    _resolver(parcela, TipoDeAlerta.DEVOLUCAO_COM_FALHA, motivo)
    _resolver(parcela, TipoDeAlerta.DEVOLUCAO_EM_FALHA_DEFINITIVA, motivo)


def _declarar_falha_definitiva(parcela: ParcelaDeDevolucao, codigo: str) -> None:
    """A recusa definitiva: guarda a evidência, alerta e agenda a reconsulta."""
    if parcela.situacao not in ABERTAS:
        return
    parcela.codigo_da_falha = codigo[:40]
    parcela.evidencia = {**parcela.evidencia, "recusa": {"codigo": codigo, "em": agora()}}
    parcela.save(update_fields=["codigo_da_falha", "evidencia"])
    transicionar(parcela, S.FALHA_DEFINITIVA, autor=SISTEMA, dados={"codigo": codigo})
    _resolver(parcela, TipoDeAlerta.DEVOLUCAO_COM_FALHA, "falha definitiva")
    abrir_alerta(
        TipoDeAlerta.DEVOLUCAO_EM_FALHA_DEFINITIVA,
        _chave_do_alerta(parcela),
        _dados_do_alerta(parcela, codigo=codigo),
    )
    agendar_chamada("verificar_estornos", f"parcela:{parcela.pk}")


def _aplicar_estorno(parcela_pk: int, estorno: EstornoConsultado | None) -> None:
    if estorno is None:
        return
    parcela = _travar_cadeia(parcela_pk)
    if parcela.situacao in FINAIS or parcela.situacao == S.ELEGIVEL_EXCEPCIONAL:
        return
    if estorno.situacao == SituacaoDoEstorno.CONCLUIDO:
        _concluir_parcela(parcela, estorno)
    elif estorno.situacao == SituacaoDoEstorno.EM_PROCESSAMENTO:
        if parcela.situacao in (S.SOLICITADA, S.FALHA_TEMPORARIA):
            parcela.id_estorno = estorno.id_estorno
            parcela.save(update_fields=["id_estorno"])
            transicionar(
                parcela,
                S.EM_PROCESSAMENTO,
                autor=SISTEMA,
                dados={"id_estorno": estorno.id_estorno},
            )
            agendar_chamada("acompanhar_estorno", f"parcela:{parcela.pk}")
    else:
        _declarar_falha_definitiva(parcela, estorno.codigo or "estorno_recusado")


# --- operação `estornar` ----------------------------------------------------------------------


def _executar_estorno(provedor: Provedor, chamada: ChamadaAoProvedor) -> EstornoConsultado:
    parcela = ParcelaDeDevolucao.objects.select_related("pagamento").get(pk=_pk_da_parcela(chamada))
    if parcela.situacao in FINAIS or parcela.situacao == S.ELEGIVEL_EXCEPCIONAL:
        raise FalhaDefinitiva("parcela_encerrada")
    try:
        return provedor.estornar(
            NovoEstorno(parcela.pagamento.id_externo, parcela.valor, chamada.chave_idempotencia)
        )
    except SaldoInsuficienteParaEstorno:
        raise FalhaTemporaria("saldo_insuficiente") from None
    except PagamentoNaoEncontrado:
        raise nao_encontrado(chamada) from None


def _concluir_estorno(chamada: ChamadaAoProvedor, estorno: EstornoConsultado) -> None:
    _aplicar_estorno(_pk_da_parcela(chamada), estorno)


def _estorno_adiado(chamada: ChamadaAoProvedor, codigo: str) -> None:
    """Falha temporária: a parcela passa a `falha_temporaria`; alerta no saldo insuficiente e a
    partir da terceira tentativa."""
    parcela = _travar_cadeia(_pk_da_parcela(chamada))
    if parcela.situacao not in (S.SOLICITADA, S.FALHA_TEMPORARIA):
        return
    mudou = parcela.situacao != S.FALHA_TEMPORARIA or parcela.codigo_da_falha != codigo
    parcela.codigo_da_falha = codigo
    parcela.save(update_fields=["codigo_da_falha"])
    if mudou:
        transicionar(
            parcela,
            S.FALHA_TEMPORARIA,
            autor=SISTEMA,
            dados={"codigo": codigo, "tentativas": chamada.tentativas},
        )
    if codigo == "saldo_insuficiente" or chamada.tentativas >= TENTATIVAS_PARA_ALERTAR:
        abrir_alerta(
            TipoDeAlerta.DEVOLUCAO_COM_FALHA,
            _chave_do_alerta(parcela),
            _dados_do_alerta(parcela, codigo=codigo, tentativas=chamada.tentativas),
        )


def _estorno_falhou(chamada: ChamadaAoProvedor, erro: Exception) -> None:
    codigo = str(getattr(erro, "codigo", "falha"))
    if codigo == "parcela_encerrada":
        return
    _declarar_falha_definitiva(_travar_cadeia(_pk_da_parcela(chamada)), codigo)


# --- operação `acompanhar_estorno` ------------------------------------------------------------


def _executar_acompanhamento(
    provedor: Provedor, chamada: ChamadaAoProvedor
) -> EstornoConsultado | None:
    parcela = ParcelaDeDevolucao.objects.select_related("pagamento").get(pk=_pk_da_parcela(chamada))
    if parcela.situacao != S.EM_PROCESSAMENTO:
        return None
    try:
        estornos = provedor.consultar_estornos(parcela.pagamento.id_externo)
    except PagamentoNaoEncontrado:
        raise nao_encontrado(chamada) from None
    estorno = next((e for e in estornos if e.id_estorno == parcela.id_estorno), None)
    if estorno is None:
        raise nao_encontrado(chamada)
    if estorno.situacao == SituacaoDoEstorno.EM_PROCESSAMENTO:
        raise FalhaTemporaria("em_processamento")
    return estorno


# --- operação `verificar_estornos` ------------------------------------------------------------


def _executar_verificacao(
    provedor: Provedor, chamada: ChamadaAoProvedor
) -> list[EstornoConsultado]:
    parcela = ParcelaDeDevolucao.objects.select_related("pagamento").get(pk=_pk_da_parcela(chamada))
    try:
        provedor.consultar_pagamento(parcela.pagamento.id_externo)
        return provedor.consultar_estornos(parcela.pagamento.id_externo)
    except PagamentoNaoEncontrado:
        raise nao_encontrado(chamada) from None


def _evidencia_da_reconsulta(estornos: list[EstornoConsultado]) -> dict[str, Any]:
    return {
        "em": agora(),
        "estornos": [
            {
                "id_estorno": e.id_estorno,
                "situacao": e.situacao.value,
                "valor": e.valor,
                "codigo": e.codigo,
            }
            for e in estornos
        ],
    }


def _nao_contabilizados(estornos: list[EstornoConsultado]) -> list[EstornoConsultado]:
    contabilizados = set(
        ParcelaDeDevolucao.objects.exclude(id_estorno=None).values_list("id_estorno", flat=True)
    )
    return [
        e
        for e in estornos
        if e.id_estorno not in contabilizados
        and e.situacao in (SituacaoDoEstorno.EM_PROCESSAMENTO, SituacaoDoEstorno.CONCLUIDO)
    ]


def _adotar_estorno_tardio(parcela: ParcelaDeDevolucao, estornos: list[EstornoConsultado]) -> None:
    """O provedor concluiu tarde um estorno que o sistema dava por inviável (E10-05): se ele tem o
    valor da parcela, a parcela o adota e é liquidada pela via principal."""
    adotado = next(
        (
            e
            for e in _nao_contabilizados(estornos)
            if e.situacao == SituacaoDoEstorno.CONCLUIDO and e.valor == parcela.valor
        ),
        None,
    )
    if adotado is None:
        return
    parcela.evidencia = {**parcela.evidencia, "adocao": _evidencia_da_reconsulta(estornos)}
    parcela.save(update_fields=["evidencia"])
    _concluir_parcela(parcela, adotado)
    motivo = "estorno concluído tardiamente pelo provedor e adotado"
    _resolver(parcela, TipoDeAlerta.DEVOLUCAO_ELEGIVEL_EXCEPCIONAL, motivo)
    resolver_alerta(TipoDeAlerta.DEVOLUCAO_CONCLUIDA_TARDIAMENTE, adotado.id_estorno, motivo=motivo)


def _concluir_verificacao(chamada: ChamadaAoProvedor, estornos: list[EstornoConsultado]) -> None:
    parcela = _travar_cadeia(_pk_da_parcela(chamada))
    if parcela.situacao not in (S.FALHA_DEFINITIVA, S.ELEGIVEL_EXCEPCIONAL):
        return
    if parcela.situacao == S.ELEGIVEL_EXCEPCIONAL:
        _adotar_estorno_tardio(parcela, estornos)
        return
    nao_contabilizados = _nao_contabilizados(estornos)
    parcela.evidencia = {**parcela.evidencia, "reconsulta": _evidencia_da_reconsulta(estornos)}
    outros_valores = [e for e in nao_contabilizados if e.valor != parcela.valor]
    iguais = [e for e in nao_contabilizados if e.valor == parcela.valor]
    if outros_valores:
        parcela.codigo_da_falha = "verificacao_inconclusiva"
        parcela.save(update_fields=["evidencia", "codigo_da_falha"])
        return
    parcela.save(update_fields=["evidencia"])
    if iguais:
        adotado = iguais[0]
        if adotado.situacao == SituacaoDoEstorno.CONCLUIDO:
            _concluir_parcela(parcela, adotado)
            return
        parcela.id_estorno = adotado.id_estorno
        parcela.save(update_fields=["id_estorno"])
        transicionar(
            parcela, S.EM_PROCESSAMENTO, autor=SISTEMA, dados={"id_estorno": adotado.id_estorno}
        )
        _resolver(parcela, TipoDeAlerta.DEVOLUCAO_EM_FALHA_DEFINITIVA, "estorno adotado")
        agendar_chamada("acompanhar_estorno", f"parcela:{parcela.pk}")
        return
    transicionar(parcela, S.ELEGIVEL_EXCEPCIONAL, autor=SISTEMA, dados={"reconsulta": "vazia"})
    avisar_o_comprador(parcela, S.ELEGIVEL_EXCEPCIONAL)
    _resolver(parcela, TipoDeAlerta.DEVOLUCAO_EM_FALHA_DEFINITIVA, "falha definitiva comprovada")
    abrir_alerta(
        TipoDeAlerta.DEVOLUCAO_ELEGIVEL_EXCEPCIONAL,
        _chave_do_alerta(parcela),
        _dados_do_alerta(parcela),
    )


def registrar_operacoes() -> None:
    registrar_operacao(
        "estornar",
        Operacao(_executar_estorno, _concluir_estorno, _estorno_falhou, adiada=_estorno_adiado),
    )
    registrar_operacao(
        "acompanhar_estorno", Operacao(_executar_acompanhamento, _concluir_estorno, _estorno_falhou)
    )
    registrar_operacao("verificar_estornos", Operacao(_executar_verificacao, _concluir_verificacao))


# --- devolução excepcional (E10-06) ---------------------------------------------------------

TAMANHO_MAXIMO_DO_COMPROVANTE = 10 * 1024 * 1024
ASSINATURAS_DO_COMPROVANTE = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
)
MENSAGEM_PENDENTE = "há devolução pendente na plataforma"


def _ler_o_comprovante(comprovante: Any) -> tuple[bytes, str, str]:
    """Os bytes, o tipo e a extensão do comprovante, pelo conteúdo e não pelo nome."""
    if comprovante is None or not hasattr(comprovante, "read"):
        raise ValueError("comprovante obrigatório")
    conteudo = comprovante.read(TAMANHO_MAXIMO_DO_COMPROVANTE + 1)
    if not isinstance(conteudo, bytes) or not conteudo:
        raise ValueError("comprovante vazio")
    if len(conteudo) > TAMANHO_MAXIMO_DO_COMPROVANTE:
        raise ValueError("comprovante acima de 10 MB")
    for assinatura, tipo, extensao in ASSINATURAS_DO_COMPROVANTE:
        if conteudo.startswith(assinatura):
            return conteudo, tipo, extensao
    raise ValueError("comprovante deve ser PDF, JPEG ou PNG")


def _validar_a_confirmacao(
    meio: str, identificacao: str, justificativa: str, comprovante: Any
) -> tuple[bytes, str, str]:
    if meio not in MeioDaDevolucaoExcepcional.values:
        raise ValueError("meio deve ser pix ou transferencia")
    if (
        not isinstance(identificacao, str)
        or not 1 <= len(identificacao.strip()) <= 100
        or len(identificacao) > 100
        or "\x00" in identificacao
    ):
        raise ValueError("identificação da transferência de 1 a 100 caracteres")
    if not isinstance(justificativa, str) or not 1 <= len(justificativa.strip()) <= 1000:
        raise ValueError("justificativa de 1 a 1.000 caracteres")
    return _ler_o_comprovante(comprovante)


def _exigir_elegivel(parcela: ParcelaDeDevolucao) -> None:
    situacao = parcela.situacao
    if situacao == S.ELEGIVEL_EXCEPCIONAL:
        return
    if situacao == S.CONCLUIDA:
        raise DevolucaoRecusada("já devolvida pela plataforma")
    if situacao == S.CONCLUIDA_FORA_DA_PLATAFORMA:
        raise DevolucaoRecusada("já confirmada")
    raise DevolucaoRecusada(MENSAGEM_PENDENTE)


def _cobertura_da_parcela(parcela: ParcelaDeDevolucao) -> bool:
    destino = conta_da_obrigacao(parcela.obrigacao)
    ativas = _designacoes_ativas(parcela.obrigacao)
    disponivel = max(ZERO, saldo(destino)) + sum((resto for _, resto in ativas), ZERO)
    return bool(disponivel >= parcela.valor)


def confirmar_devolucao_excepcional(
    parcela: ParcelaDeDevolucao,
    *,
    autor: Conta,
    meio: str,
    identificacao: str,
    justificativa: str,
    comprovante: Any,
) -> ConfirmacaoDeDevolucaoExcepcional:
    """O administrador confirma que devolveu o dinheiro fora da plataforma. Só vale para a parcela
    `elegivel_excepcional`, uma vez, sem devolução em andamento no provedor. A obrigação é
    liquidada pelo F16 e as novas tentativas pela plataforma ficam bloqueadas."""
    autor_conta = _exigir_autor(autor, aceita_sistema=False)
    conteudo, tipo, extensao = _validar_a_confirmacao(
        meio, identificacao, justificativa, comprovante
    )
    if parcela.pk is None:
        raise DevolucaoRecusada("a devolução pela plataforma não foi tentada")
    atual = ParcelaDeDevolucao.objects.select_related("pagamento", "obrigacao").get(pk=parcela.pk)
    _exigir_elegivel(atual)
    consultar_antes_de_decidir(atual.pagamento.referencia_externa)  # ConsultaAoProvedorFalhou
    _recusar_se_o_provedor_tem_estorno(atual)
    armazenamento = ConfirmacaoDeDevolucaoExcepcional._meta.get_field("comprovante").storage
    gravado: str | None = None
    try:
        with transaction.atomic():
            travada = _travar_cadeia(atual.pk)
            _exigir_elegivel(travada)
            if not _cobertura_da_parcela(travada):
                raise DevolucaoRecusada(
                    "a obrigação não está coberta: é preciso cobrir antes, por designação da "
                    "reserva, receita de serviço ou aporte"
                )
            confirmacao = ConfirmacaoDeDevolucaoExcepcional(
                parcela=travada,
                obrigacao=travada.obrigacao,
                pedido_id=travada.obrigacao.pedido_id,
                comprador_id=travada.obrigacao.comprador_id,
                valor=travada.valor,
                meio=meio,
                identificacao=identificacao,
                justificativa=justificativa.strip(),
                comprovante_nome=str(getattr(comprovante, "name", "") or "comprovante")[-255:],
                comprovante_tipo=tipo,
                comprovante_tamanho=len(conteudo),
                autor=autor_conta,
            )
            gravado = armazenamento.save(
                f"comprovantes/{uuid.uuid4().hex}{extensao}", ContentFile(conteudo)
            )
            confirmacao.comprovante.name = gravado
            confirmacao.save()
            liquidar_obrigacao_fora_do_provedor(
                travada.obrigacao, travada.valor, referencia=f"excepcional:{travada.pk}"
            )
            transicionar(
                travada,
                S.CONCLUIDA_FORA_DA_PLATAFORMA,
                autor=autor,
                dados={"meio": meio, "identificacao": identificacao},
            )
            _resolver(travada, TipoDeAlerta.DEVOLUCAO_ELEGIVEL_EXCEPCIONAL, "devolução excepcional")
            avisar_o_comprador(travada, S.CONCLUIDA_FORA_DA_PLATAFORMA, meio=meio)
            registrar_auditoria(
                autor_conta,
                "financeiro.devolucao_excepcional_confirmada",
                confirmacao,
                {"parcela": travada.pk, "obrigacao": travada.obrigacao_id, "valor": travada.valor},
                motivo=justificativa.strip(),
            )
            return confirmacao
    except BaseException:
        if gravado is not None:  # a transação foi desfeita: o arquivo não fica órfão
            armazenamento.delete(gravado)
        raise


def _recusar_se_o_provedor_tem_estorno(parcela: ParcelaDeDevolucao) -> None:
    """Estorno não contabilizado em processamento ou concluído: a confirmação é recusada e a
    verificação agendada, para a parcela adotá-lo (E10-05)."""
    estornos = obter_provedor().consultar_estornos(parcela.pagamento.id_externo)
    if _nao_contabilizados(estornos):
        with transaction.atomic():
            agendar_chamada("verificar_estornos", f"parcela:{parcela.pk}")
        raise DevolucaoRecusada("há devolução em processamento ou concluída no provedor")
