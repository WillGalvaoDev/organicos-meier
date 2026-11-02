"""Apoio dos testes do cancelamento da rodada (E12): o arranjo CI da E12-01."""

from decimal import Decimal
from typing import Any

from apps.interesses.models import ParcelaDeInteresse
from apps.rodadas.models import Etapa
from tests.apoio.interesses import cenario
from tests.fabricas import ContaFactory, ParcelaFactory

D = Decimal


class Ci:
    """O arranjo CI: P1 com limite 11; C pendente (3), A (6), B (5) e D sem estoque (3)."""

    def __init__(self, *, etapa: str = Etapa.INTERESSE, limite: str = "11", a_pendente: int = 0):
        from apps.contas.models import Conta, Papel

        self.rodada, self.p1, self.estoque = cenario(limite=limite, etapa=etapa)
        self.admin = Conta.objects.get(papel=Papel.ADMINISTRADOR)
        self.a, self.b, self.c, self.d = (ContaFactory.create() for _ in range(4))
        self.pc = ParcelaFactory.create(
            comprador=self.c,
            produto=self.p1,
            quantidade_original=D("3"),
            quantidade_reservada=D("0"),
            quantidade_pendente=D("3"),
            situacao="pendente",
        )
        self.pa = ParcelaFactory.create(
            comprador=self.a,
            produto=self.p1,
            quantidade_original=D(6 + a_pendente),
            quantidade_reservada=D("6"),
            quantidade_pendente=D(a_pendente),
        )
        self.pb = ParcelaFactory.create(
            comprador=self.b,
            produto=self.p1,
            quantidade_original=D("5"),
            quantidade_reservada=D("5"),
        )
        self.pd = ParcelaFactory.create(
            comprador=self.d,
            produto=self.p1,
            quantidade_original=D("3"),
            quantidade_reservada=D("0"),
            quantidade_pendente=D("3"),
        )

    def cancelar(self, **kwargs: Any) -> Any:
        from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

        kwargs.setdefault("com_reembolso", False)
        return cancelar_rodada(self.admin, self.rodada, **kwargs)

    def parcela(self, parcela: ParcelaDeInteresse) -> ParcelaDeInteresse:
        parcela.refresh_from_db()
        return parcela


def arranjo_ap_r(
    relogio: Any, sim: Any, *, segunda_cobranca: bool = False
) -> tuple[Any, Any, str | None]:
    """O arranjo AP-R da correção da revisão (E12-02): X pago no ciclo 1, a apuração em 48h com o
    retorno ao interesse e a devolução de mínimo pendente. Com `segunda_cobranca`, uma segunda
    cobrança de X fica pendente no simulador (prazo em T0 + 24h). Devolve o arranjo, X e o
    `id_externo` da segunda cobrança (ou `None`)."""
    from apps.pagamentos.provedor import NovaCobranca, obter_provedor
    from apps.pedidos.apuracao import iniciar_apuracao
    from tests.apoio.apuracao import H, arranjo_ap, pagar
    from tests.apoio.pedidos import T0

    a, x, _y = arranjo_ap(relogio, minimo="100.00", limites=(11, 12))
    pagar(relogio, sim, x)
    extra = None
    if segunda_cobranca:
        extra = (
            obter_provedor()
            .criar_cobranca(
                NovaCobranca("extra-revisor", x.referencia_externa, x.total, "Pedido", T0 + 24 * H)
            )
            .pagamento.id_externo
        )
    relogio.congelar(T0 + 48 * H)
    iniciar_apuracao(a.admin, a.rodada)
    return a, x, extra
