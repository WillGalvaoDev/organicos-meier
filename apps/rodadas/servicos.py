"""Abertura de rodada (E03-02)."""

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.nucleo.auditoria import registrar_auditoria
from apps.rodadas.models import ETAPAS_ATIVAS, Etapa, Rodada
from apps.rodadas.sinais import rodada_aberta


class RodadaAtivaExistente(Exception):
    """O fornecedor já tem uma rodada ativa."""

    def __init__(self) -> None:
        super().__init__("Este fornecedor já tem uma rodada ativa.")


def abrir_rodada(autor: Conta, fornecedor: Fornecedor) -> Rodada:
    """Abre uma rodada em `interesse` para o fornecedor, se ele não tiver outra ativa.

    A linha do fornecedor é travada antes da checagem, então duas aberturas simultâneas ficam em
    série (a segunda vê a rodada da primeira); o índice parcial do banco é a defesa final. O
    sinal `rodada_aberta` é enviado dentro da transação: um receptor que falha desfaz tudo.
    """
    if getattr(autor, "papel", None) != Papel.ADMINISTRADOR:
        raise PermissionDenied
    with transaction.atomic():
        Fornecedor.objects.select_for_update().get(pk=fornecedor.pk)
        if Rodada.objects.filter(fornecedor_id=fornecedor.pk, etapa__in=ETAPAS_ATIVAS).exists():
            raise RodadaAtivaExistente
        rodada = Rodada.objects.create(
            fornecedor_id=fornecedor.pk, etapa=Etapa.INTERESSE, aberta_por=autor
        )
        rodada_aberta.send(sender=Rodada, rodada=rodada)
        registrar_auditoria(
            autor,
            "rodada.abrir",
            rodada,
            {"rodada": rodada.pk, "fornecedor": fornecedor.pk},
        )
    return rodada
