"""O simulador determinístico do provedor de pagamentos (E07-01): sem rede, sem aleatoriedade.

Os instantes vêm de `agora()` e as cobranças ficam no banco, para que a cobrança criada pela
tarefa (worker) seja vista por outra conexão ou processo. Nada muda de situação sozinho: só os
controles (`controle.py`) e `cancelar_cobranca`.
"""

import hmac
import json
from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Sum

from apps.nucleo.tempo import agora, somar_horas
from apps.pagamentos.provedor import (
    AvisoDoProvedor,
    AvisoInvalido,
    CobrancaCriada,
    MovimentoNoProvedor,
    NovaCobranca,
    PagamentoConsultado,
    ProvedorIndisponivel,
    RecusaDoProvedor,
    SaldoNoProvedor,
    SituacaoNoProvedor,
    TipoDeMovimentoNoProvedor,
)
from apps.simulador_pagamentos import estado
from apps.simulador_pagamentos.models import CobrancaSimulada, MovimentoSimulado
from apps.simulador_pagamentos.plano import PLANO
from apps.simulador_pagamentos.roteador import ALIAS


def _executar[R](operacao: str, funcao: Callable[[], R]) -> R:
    """Aplica o plano de falhas à chamada: falha antes, ou executa e falha depois."""
    falhar_depois = PLANO.consumir(operacao)
    resultado = funcao()
    if falhar_depois:
        raise ProvedorIndisponivel("tempo esgotado simulado")
    return resultado


def _mesmos_dados(cobranca: CobrancaSimulada, nova: NovaCobranca) -> bool:
    return (
        cobranca.referencia_externa == nova.referencia_externa
        and cobranca.valor == nova.valor
        and cobranca.descricao == nova.descricao
        and cobranca.meio == nova.meio
        and cobranca.expira_em == nova.expira_em
    )


def _devolver_existente(existente: CobrancaSimulada, nova: NovaCobranca) -> CobrancaCriada:
    if not _mesmos_dados(existente, nova):
        raise RecusaDoProvedor("chave_reutilizada")
    return _criada(existente)


def _criada(cobranca: CobrancaSimulada) -> CobrancaCriada:
    return CobrancaCriada(
        estado.consultado(cobranca),
        {"pix_copia_e_cola": f"SIMULADO-{cobranca.id_externo}"},
    )


class ProvedorSimulado:
    nome = estado.NOME

    def criar_cobranca(self, nova: NovaCobranca) -> CobrancaCriada:
        def criar() -> CobrancaCriada:
            existente = CobrancaSimulada.objects.filter(
                chave_idempotencia=nova.chave_idempotencia
            ).first()
            if existente is not None:
                return _devolver_existente(existente, nova)
            if nova.expira_em <= agora():
                raise RecusaDoProvedor("expiracao_invalida")
            try:
                with transaction.atomic(using=ALIAS):
                    cobranca = CobrancaSimulada.objects.create(
                        chave_idempotencia=nova.chave_idempotencia,
                        referencia_externa=nova.referencia_externa,
                        valor=nova.valor,
                        descricao=nova.descricao,
                        meio=nova.meio,
                        situacao=SituacaoNoProvedor.PENDENTE.value,
                        criado_em=agora(),
                        expira_em=nova.expira_em,
                    )
            except IntegrityError:
                # outra conexão criou a mesma chave primeiro: a restrição UNIQUE decidiu
                existente = CobrancaSimulada.objects.get(chave_idempotencia=nova.chave_idempotencia)
                return _devolver_existente(existente, nova)
            estado.registrar("criar_cobranca", cobranca.id_externo)
            return _criada(cobranca)

        return _executar("criar_cobranca", criar)

    def consultar_pagamento(self, id_externo: str) -> PagamentoConsultado:
        def consultar() -> PagamentoConsultado:
            cobranca = estado.obter(id_externo)
            estado.registrar("consultar_pagamento", id_externo)
            return estado.consultado(cobranca, atrasavel=True)

        return _executar("consultar_pagamento", consultar)

    def buscar_por_referencia(self, referencia_externa: str) -> list[PagamentoConsultado]:
        def buscar() -> list[PagamentoConsultado]:
            cobrancas = CobrancaSimulada.objects.filter(
                referencia_externa=referencia_externa
            ).order_by("criado_em", "pk")
            estado.registrar("buscar_por_referencia")
            return [estado.consultado(c, atrasavel=True) for c in cobrancas]

        return _executar("buscar_por_referencia", buscar)

    def cancelar_cobranca(self, id_externo: str) -> PagamentoConsultado:
        def cancelar() -> PagamentoConsultado:
            with transaction.atomic(using=ALIAS):
                cobranca = estado.obter(id_externo, travar=True)
                if cobranca.situacao == SituacaoNoProvedor.PENDENTE:
                    aprova, em = PLANO.aprovacao_no_cancelamento(cobranca.pk)
                    if aprova:
                        estado.mudar(cobranca, SituacaoNoProvedor.APROVADO, em or agora())
                    else:
                        estado.mudar(cobranca, SituacaoNoProvedor.CANCELADO)
            estado.registrar("cancelar_cobranca", id_externo)
            return estado.consultado(cobranca)

        return _executar("cancelar_cobranca", cancelar)

    def verificar_aviso(
        self, corpo: bytes, cabecalhos: Mapping[str, str], parametros: Mapping[str, str]
    ) -> AvisoDoProvedor:
        # o simulador confere só a assinatura que já usa e ignora os parâmetros da URL
        def verificar() -> AvisoDoProvedor:
            recebida = next(
                (
                    valor
                    for nome, valor in cabecalhos.items()
                    if nome.lower() == estado.CABECALHO_DA_ASSINATURA.lower()
                ),
                None,
            )
            esperada = "sha256=" + estado.assinar(corpo)
            if recebida is None or not hmac.compare_digest(recebida.encode(), esperada.encode()):
                raise AvisoInvalido("assinatura ausente ou inválida")
            try:
                dados: Any = json.loads(corpo)
            except ValueError:
                raise AvisoInvalido("corpo malformado") from None
            if not isinstance(dados, dict):
                raise AvisoInvalido("corpo malformado")
            return AvisoDoProvedor(
                dados.get("id_evento", ""), dados.get("tipo", ""), dados.get("id_externo", "")
            )

        return _executar("verificar_aviso", verificar)

    def consultar_saldo(self) -> SaldoNoProvedor:
        def consultar() -> SaldoNoProvedor:
            instante = agora()
            movimentos = MovimentoSimulado.objects.all()
            liberado = movimentos.filter(liberado_em__lte=instante).aggregate(s=Sum("valor"))["s"]
            a_liberar = movimentos.filter(liberado_em__gt=instante).aggregate(s=Sum("valor"))["s"]
            estado.registrar("consultar_saldo")
            return SaldoNoProvedor(
                liberado=liberado or Decimal("0.00"),
                a_liberar=a_liberar or Decimal("0.00"),
                referente_a=instante,  # o simulador é em tempo real
                consultado_em=instante,
            )

        return _executar("consultar_saldo", consultar)

    def listar_movimentos(self, desde: datetime, ate: datetime) -> list[MovimentoNoProvedor]:
        somar_horas(desde, 0)  # InstanteSemFuso se não tiver fuso
        somar_horas(ate, 0)
        if desde > ate:
            raise ValueError("desde não pode ser posterior a ate")

        def listar() -> list[MovimentoNoProvedor]:
            movimentos = MovimentoSimulado.objects.filter(
                ocorrido_em__gte=desde, ocorrido_em__lt=ate
            ).order_by("ocorrido_em", "pk")
            estado.registrar("listar_movimentos")
            return [
                MovimentoNoProvedor(
                    id_movimento=m.id_movimento,
                    tipo=TipoDeMovimentoNoProvedor(m.tipo),
                    descricao_no_provedor=m.descricao,
                    valor=m.valor,
                    id_externo=m.id_externo or None,
                    ocorrido_em=m.ocorrido_em,
                    liberado_em=m.liberado_em,
                )
                for m in movimentos
            ]

        return _executar("listar_movimentos", listar)


SIMULADO = ProvedorSimulado()
