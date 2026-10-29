"""Controles do simulador de pagamentos (E07-01): o pagador e o provedor, para os testes.

Reproduzem aprovação, recusa, expiração, avisos atrasados, repetidos, fora de ordem ou perdidos,
falhas, indisponibilidade e atraso de consistência. Os controles de situação não passam pelo
plano de falhas: o plano só afeta as operações da interface.
"""

import json
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from apps.nucleo.tempo import agora, somar_horas
from apps.nucleo.valores import ValorInvalido, dinheiro
from apps.pagamentos.provedor import SituacaoNoProvedor
from apps.simulador_pagamentos import estado
from apps.simulador_pagamentos.models import AvisoSimulado, EstornoSimulado, MovimentoSimulado
from apps.simulador_pagamentos.plano import PLANO
from apps.simulador_pagamentos.roteador import ALIAS

Receptor = Callable[[bytes, dict[str, str]], int]

_APROVAVEIS = (
    SituacaoNoProvedor.PENDENTE,
    SituacaoNoProvedor.CANCELADO,
    SituacaoNoProvedor.EXPIRADO,
)


def _instante(em: datetime | None) -> datetime:
    if em is None:
        return agora()
    somar_horas(em, 0)  # recusa o instante sem fuso
    return em


def aprovar(id_externo: str, *, em: datetime | None = None) -> None:
    """Aprova a partir de pendente, cancelada ou expirada (L-2, L-3).

    `em` anterior à criação, ou cobrança já aprovada ou recusada: `ValueError`. Um `em` no
    passado é uma aprovação que o provedor informa depois.
    """
    instante = _instante(em)
    with transaction.atomic(using=ALIAS):
        cobranca = estado.obter(id_externo, travar=True)
        if cobranca.situacao not in _APROVAVEIS:
            raise ValueError(f"cobrança {cobranca.situacao} não pode ser aprovada")
        if instante < cobranca.criado_em:
            raise ValueError("aprovação anterior à criação da cobrança")
        estado.mudar(cobranca, SituacaoNoProvedor.APROVADO, instante)
    estado.registrar("aprovar", id_externo)


def _encerrar_pendente(id_externo: str, situacao: SituacaoNoProvedor, operacao: str) -> None:
    with transaction.atomic(using=ALIAS):
        cobranca = estado.obter(id_externo, travar=True)
        if cobranca.situacao != SituacaoNoProvedor.PENDENTE:
            raise ValueError(f"só uma cobrança pendente pode ser {situacao.value}")
        estado.mudar(cobranca, situacao)
    estado.registrar(operacao, id_externo)


def recusar(id_externo: str) -> None:
    _encerrar_pendente(id_externo, SituacaoNoProvedor.RECUSADO, "recusar")


def expirar(id_externo: str) -> None:
    _encerrar_pendente(id_externo, SituacaoNoProvedor.EXPIRADO, "expirar")


def aprovar_no_cancelamento(id_externo: str, *, em: datetime | None = None) -> None:
    """O próximo `cancelar_cobranca` dessa cobrança aprova em vez de cancelar: o pagador
    concluiu no mesmo instante do cancelamento (infraestrutura 4.3)."""
    instante = None if em is None else _instante(em)
    cobranca = estado.obter(id_externo)
    if instante is not None and instante < cobranca.criado_em:
        raise ValueError("aprovação anterior à criação da cobrança")
    PLANO.aprovar_no_cancelamento(cobranca.pk, instante)


def reemitir_aviso(id_externo: str) -> AvisoSimulado:
    """Outro aviso para a mesma cobrança, sem mudar a situação (o provedor repetindo o evento)."""
    estado.obter(id_externo)
    estado.registrar("reemitir_aviso", id_externo)
    return estado.novo_aviso(id_externo)


def avisos_pendentes() -> list[AvisoSimulado]:
    return list(AvisoSimulado.objects.filter(entregas=0, descartado=False).order_by("pk"))


def descartar(aviso: AvisoSimulado) -> None:
    """O aviso perdido: nunca será entregue."""
    AvisoSimulado.objects.filter(pk=aviso.pk).update(descartado=True)
    estado.registrar("descartar", aviso.id_externo)


def corpo_e_cabecalhos(aviso: AvisoSimulado) -> tuple[bytes, dict[str, str]]:
    corpo = json.dumps(
        {"id_evento": aviso.id_evento, "tipo": aviso.tipo, "id_externo": aviso.id_externo},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return corpo, {estado.CABECALHO_DA_ASSINATURA: "sha256=" + estado.assinar(corpo)}


def entregar_avisos(
    avisos: Sequence[AvisoSimulado] | None = None,
    *,
    vezes: int = 1,
    receptor: Receptor | None = None,
) -> list[int]:
    """Entrega os avisos na ordem recebida (por padrão, os pendentes), cada um `vezes` vezes.

    Monta o corpo, assina e chama o `receptor` (por padrão, `receber_aviso`, a função que a rota
    de avisos chama; os testes podem injetar outro); devolve os códigos HTTP.

    Atrasado = não entregar ainda; repetido = `vezes`; fora de ordem = a ordem da lista; perdido
    = `descartar`.
    """
    if receptor is None:
        from apps.pagamentos.avisos import receber_aviso  # a função que a rota de avisos chama

        def receptor(corpo: bytes, cabecalhos: dict[str, str]) -> int:
            return receber_aviso(corpo, cabecalhos, {})  # a entrega não tem query string

    codigos: list[int] = []
    for aviso in avisos if avisos is not None else avisos_pendentes():
        for _ in range(vezes):
            corpo, cabecalhos = corpo_e_cabecalhos(aviso)
            codigos.append(receptor(corpo, cabecalhos))
            AvisoSimulado.objects.filter(pk=aviso.pk).update(entregas=F("entregas") + 1)
            estado.registrar("entregar_avisos", aviso.id_externo)
    return codigos


def indisponivel() -> None:
    """Toda operação da interface levanta `ProvedorIndisponivel`, até `normalizar()`."""
    PLANO.indisponivel()


def falhar_proximas(
    n: int, *, operacao: str | None = None, depois_de_executar: bool = False
) -> None:
    """As próximas `n` chamadas (de uma operação, ou de qualquer uma) falham. Com
    `depois_de_executar`, a operação é feita e gravada antes da exceção (tempo esgotado depois
    de o provedor aceitar)."""
    PLANO.falhar_proximas(n, operacao, depois_de_executar)


def atrasar_consistencia(id_externo: str, consultas: int) -> None:
    """As próximas `consultas` consultas e buscas do pagamento veem a situação anterior à última
    mudança (L-6)."""
    PLANO.atrasar(estado.obter(id_externo).pk, consultas)


def normalizar() -> None:
    PLANO.normalizar()


def reiniciar() -> None:
    """Zera os planos (inclusive tarifa e liberação) e apaga os movimentos da conta."""
    PLANO.reiniciar()
    EstornoSimulado.objects.all().delete()
    MovimentoSimulado.objects.all().delete()


def _decimal(valor: object, *, positivo: bool = True) -> Decimal:
    """Dinheiro do controle: `Decimal` com até duas casas; `float` e valor fora da regra viram
    `ValueError`. Com `positivo`, zero e negativos também."""
    if not isinstance(valor, Decimal):
        raise ValueError("o valor deve ser Decimal")
    try:
        convertido = dinheiro(valor)
    except ValorInvalido as erro:
        raise ValueError(str(erro)) from None
    if convertido == 0 or (positivo and convertido < 0):
        raise ValueError("o valor deve ser maior que zero" if positivo else "o valor é zero")
    return convertido


def definir_tarifa(meio: str, *, percentual: Decimal, fixa: Decimal) -> None:
    """A tarifa do meio: `percentual` (em %, por exemplo 0,99) do valor mais a parte `fixa`."""
    if not isinstance(percentual, Decimal) or not isinstance(fixa, Decimal):
        raise ValueError("percentual e parte fixa devem ser Decimal")
    if percentual < 0 or fixa < 0:
        raise ValueError("a tarifa não pode ser negativa")
    PLANO.definir_tarifa(meio, percentual, fixa)


def definir_liberacao(meio: str, *, horas: int) -> None:
    """O prazo, em horas depois da aprovação, em que o dinheiro do meio fica liberado."""
    if isinstance(horas, bool) or not isinstance(horas, int) or horas < 0:
        raise ValueError("as horas devem ser um inteiro não negativo")
    PLANO.definir_liberacao(meio, horas)


def _movimento_avulso(tipo: str, descricao: str, valor: Decimal, em: datetime | None) -> str:
    instante = _instante(em)
    movimento = estado.novo_movimento(tipo, descricao, valor, instante, instante)
    estado.registrar(tipo)
    return movimento.id_movimento


def depositar(valor: Decimal, *, em: datetime | None = None) -> str:
    """Um depósito (aporte) na conta do provedor, liberado no ato."""
    return _movimento_avulso("deposito", "deposito", _decimal(valor), em)


def registrar_saida(valor: Decimal, *, descricao: str, em: datetime | None = None) -> str:
    """Uma saída da conta (repasse, retirada), liberada no ato."""
    return _movimento_avulso("saida", descricao[:50], -_decimal(valor), em)


def ajustar_saldo(valor: Decimal, *, em: datetime | None = None) -> str:
    """Um ajuste que nenhum registro do sistema explica: a divergência de teste da conciliação."""
    return _movimento_avulso("ajuste", "ajuste", _decimal(valor, positivo=False), em)


# --- estornos e contestação (E10-03) -------------------------------------------------------


def estornos_em_processamento(id_externo: str) -> None:
    """Os próximos estornos do pagamento nascem `em_processamento`."""
    PLANO.estornos_em_processamento(estado.obter(id_externo).pk)


def concluir_estorno(id_estorno: str, *, em: datetime | None = None) -> None:
    """O estorno em processamento termina: o débito entra na conta e ele passa a ser visível."""
    instante = _instante(em)
    with transaction.atomic(using=ALIAS):
        estorno = estado.obter_estorno(id_estorno, travar=True)
        if estorno.situacao != "em_processamento":
            raise ValueError("só um estorno em processamento pode ser concluído")
        estado.concluir(estorno, instante)
    estado.registrar("concluir_estorno", estorno.cobranca.id_externo)


def recusar_estorno(id_estorno: str, codigo: str) -> None:
    """O estorno em processamento é recusado, sem movimento."""
    with transaction.atomic(using=ALIAS):
        estorno = estado.obter_estorno(id_estorno, travar=True)
        if estorno.situacao != "em_processamento":
            raise ValueError("só um estorno em processamento pode ser recusado")
        estorno.situacao = "recusado"
        estorno.codigo = codigo
        estorno.visivel = True
        estorno.save(update_fields=["situacao", "codigo", "visivel"])
    estado.registrar("recusar_estorno", estorno.cobranca.id_externo)


def recusar_estornos(id_externo: str, codigo: str) -> None:
    """Os próximos estornos do pagamento são recusados com o código."""
    PLANO.recusar_estornos(estado.obter(id_externo).pk, codigo)


def recusar_mas_processar(id_externo: str, codigo: str) -> None:
    """O próximo estorno é recusado na resposta, mas o provedor o processa: ele fica invisível
    até `concluir_estorno` (o risco residual da infraestrutura 4.7)."""
    PLANO.recusar_mas_processar(estado.obter(id_externo).pk, codigo)


def sem_estorno_parcial(id_externo: str) -> None:
    """O pagamento só aceita estorno do restante inteiro."""
    PLANO.sem_estorno_parcial(estado.obter(id_externo).pk)


def contestar(
    id_externo: str,
    valor: Decimal | None = None,
    *,
    descricao: str = "chargeback",
    em: datetime | None = None,
) -> str:
    """A contestação: um débito `outro` na conta. Nada muda no pagamento nem no sistema."""
    if descricao not in ("chargeback", "med"):
        raise ValueError("a descrição deve ser chargeback ou med")
    cobranca = estado.obter(id_externo)
    if cobranca.situacao != SituacaoNoProvedor.APROVADO:
        raise ValueError("só um pagamento aprovado pode ser contestado")
    debito = cobranca.valor if valor is None else _decimal(valor)
    if debito > cobranca.valor:
        raise ValueError("o valor passa do valor do pagamento")
    instante = _instante(em)
    movimento = estado.novo_movimento("outro", descricao, -debito, instante, instante, cobranca)
    estado.registrar("contestar", id_externo)
    return movimento.id_movimento
