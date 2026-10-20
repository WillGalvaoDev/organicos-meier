"""Operação de teste das chamadas ao provedor (E07-04), registrada só nos testes.

`criar_cobranca_de_teste` chama `provedor.criar_cobranca` com a chave gravada na chamada e guarda
o `id_externo` devolvido numa tabela de apoio: prova a repetição com a mesma chave antes de a
E08 existir. O gancho `falhou` guarda o código da recusa.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.pagamentos.chamadas import OPERACOES, Operacao, registrar_operacao
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pagamentos.provedor import NovaCobranca, Provedor
from tests.apoio.models import CobrancaDeTeste, FalhaDeTeste

NOME = "criar_cobranca_de_teste"


def _executar(provedor: Provedor, chamada: ChamadaAoProvedor) -> Any:
    nova = NovaCobranca(
        chave_idempotencia=chamada.chave_idempotencia,
        referencia_externa=chamada.alvo,
        valor=Decimal(chamada.parametros["valor"]),
        descricao="Cobrança de teste",
        expira_em=datetime.fromisoformat(chamada.parametros["expira_em"]),
    )
    return provedor.criar_cobranca(nova)


def _concluir(chamada: ChamadaAoProvedor, resultado: Any) -> None:
    CobrancaDeTeste.objects.create(id_externo=resultado.pagamento.id_externo)


def _falhou(chamada: ChamadaAoProvedor, erro: Exception) -> None:
    FalhaDeTeste.objects.create(codigo=getattr(erro, "codigo", type(erro).__name__))


@contextmanager
def operacao_de_teste() -> Iterator[None]:
    """Registra `criar_cobranca_de_teste` durante o bloco."""
    registrar_operacao(NOME, Operacao(_executar, _concluir, _falhou))
    try:
        yield
    finally:
        OPERACOES.pop(NOME, None)
