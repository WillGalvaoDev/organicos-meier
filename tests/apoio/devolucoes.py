"""Apoio dos testes das devoluções (E10): pedidos pagos com itens de valores explícitos."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.contas.models import Conta
from apps.financeiro.reembolsos import reembolso_integral_do_pedido, reembolso_parcial
from apps.pedidos.models import ItemDoPedido, Pedido
from tests.apoio.financeiro import chave_nova, pedido_composto
from tests.apoio.pedidos import administrador, marcar_pago
from tests.fabricas import ContaFactory, ProdutoFactory

D = Decimal
H = timedelta(hours=1)


@dataclass(frozen=True)
class Item:
    """Um item do arranjo: subtotal, quantidade e incremento, em texto."""

    subtotal: str
    quantidade: str
    incremento: str


# Os arranjos K, M e N da aceitação da E10-02
K = ("7.99", "0.40", "1.60", [Item("7.99", "1.000", "0.25")])
M = ("0.09", "0.00", "0.00", [Item("0.09", "0.600", "0.1")])
N = ("100.00", "5.00", "20.00", [Item("25.00", "1", "1"), Item("75.00", "3", "1")])


def itens_do_pedido(pedido: Pedido, itens: list[Item]) -> list[ItemDoPedido]:
    """Grava os itens (a composição comercial) do pedido, direto."""
    fornecedor = pedido.abertura.rodada.fornecedor
    criados: list[ItemDoPedido] = []
    for item in itens:
        quantidade = D(item.quantidade)
        produto = ProdutoFactory.create(fornecedor=fornecedor, incremento=D(item.incremento))
        criados.append(
            ItemDoPedido.objects.create(
                pedido=pedido,
                produto=produto,
                nome=produto.nome,
                unidade=produto.unidade,
                incremento=D(item.incremento),
                preco_unitario=(D(item.subtotal) / quantidade).quantize(D("0.01")),
                quantidade=quantidade,
                subtotal=D(item.subtotal),
            )
        )
    return criados


def pedido_pago_com_itens(
    arranjo: tuple[str, str, str, list[Item]], comprador: Conta | None = None
) -> tuple[Pedido, list[ItemDoPedido]]:
    """Um pedido `pago` (direto no banco, sem entradas no livro) com os itens do arranjo."""
    produtos, servico, frete, itens = arranjo
    pedido = pedido_composto(comprador or ContaFactory.create(), produtos, servico, frete)
    marcar_pago(pedido)
    return pedido, itens_do_pedido(pedido, itens)


def parcial(
    item: ItemDoPedido,
    quantidade: str,
    *,
    chave: str | None = None,
    motivo: str = "ocorrencia_de_entrega",
) -> Any:
    """Um `reembolso_parcial` numa transação própria, pelo administrador."""
    with transaction.atomic():
        return reembolso_parcial(
            item, D(quantidade), chave=chave or chave_nova(), motivo=motivo, autor=administrador()
        )


def integral(pedido: Pedido, *, chave: str | None = None) -> Any:
    """Um `reembolso_integral_do_pedido` numa transação própria, pelo administrador."""
    with transaction.atomic():
        return reembolso_integral_do_pedido(
            pedido,
            chave=chave or chave_nova(),
            motivo="cancelamento_da_rodada",
            autor=administrador(),
        )


def componentes(registrado: Any) -> tuple[Decimal, Decimal, Decimal]:
    """Os produtos, o serviço e o frete do reembolso registrado."""
    r = registrado.reembolso
    return r.produtos, r.servico, r.frete


@dataclass
class Arranjo:
    """O arranjo da E10-04: X pago por P1 (125,00, com as entradas na custódia), um aporte de
    1.000,00 no simulador e no livro, e O1, a obrigação do parcial de 1 unidade do item I2 de X
    (31,25)."""

    sim: Any
    relogio: Any
    admin: Conta
    comprador: Conta
    pedido: Pedido
    i1: ItemDoPedido
    i2: ItemDoPedido
    pagamento: Any
    o1: Any


def arranjo_da_devolucao(sim: Any, relogio: Any) -> Arranjo:
    from apps.financeiro.reserva import registrar_aporte
    from apps.pedidos.models import SituacaoDoPedido
    from tests.apoio.pedidos import T0, sincronizar, tentativa_criada

    relogio.congelar(T0 + timedelta(hours=1))
    comprador = ContaFactory.create(nome="Comprador B")
    pedido = pedido_composto(comprador)
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    sim.aprovar(id_externo)
    sincronizar(id_externo)
    i1, i2 = itens_do_pedido(pedido, N[3])
    admin = administrador()
    id_deposito = sim.depositar(D("1000.00"))
    with transaction.atomic():
        registrar_aporte(admin, D("1000.00"), id_deposito, "Aporte")
    relogio.congelar(T0 + timedelta(hours=2))
    pagamento = SituacaoDoPedido.objects.get(pedido=pedido).quitado_por
    o1 = parcial(i2, "1").obrigacao
    return Arranjo(sim, relogio, admin, comprador, pedido, i1, i2, pagamento, o1)


def obrigacao_sem_cobertura(a: Arranjo) -> Any:
    """A custódia do pedido é esvaziada antes do reembolso: a obrigação nasce sem cobertura."""
    from apps.financeiro.livro import saldo
    from apps.financeiro.reserva import sem_cobertura_da_obrigacao
    from tests.apoio.financeiro import chave_nova, custodia, mover, obrigacao_com

    rodada, ciclo = a.pedido.abertura.rodada, a.pedido.abertura.ciclo
    ralo = obrigacao_com(rodada, ciclo, a.comprador, numero=9999)
    for componente in ("produtos", "servico", "frete"):
        conta = custodia(rodada, ciclo, a.comprador, componente)
        mover("financiamento_de_obrigacao", conta, ralo, saldo(conta), chave=chave_nova())
    obrigacao = parcial(a.i1, "1").obrigacao
    assert sem_cobertura_da_obrigacao(obrigacao) == obrigacao.devido
    return obrigacao


def levar_a_elegivel(a: Arranjo, obrigacao: Any = None, pagamento: Any = None) -> Any:
    """Autoriza a obrigação (por padrão, O1) com a recusa definitiva `prazo_vencido` do provedor
    e deixa a reconsulta rodar: a parcela fica `elegivel_excepcional` pelo caminho real."""
    from apps.financeiro.devolucoes import autorizar_devolucao
    from apps.pagamentos.chamadas import processar_chamadas

    alvo = obrigacao or a.o1
    a.sim.recusar_estornos((pagamento or a.pagamento).id_externo, "prazo_vencido")
    parcela = autorizar_devolucao(alvo, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"
    return parcela


def montar_tela(client: Any, sim: Any, relogio: Any) -> tuple[Arranjo, bytes]:
    """O arranjo da E10-04 com o administrador logado por passkey (recente) no `client`."""
    from tests.apoio.admin_fluxos import administrador_com_passkey, entrar_com_passkey_direta
    from tests.apoio.pedidos import T0

    relogio.congelar(T0)
    conta, credencial = administrador_com_passkey(client)
    a = arranjo_da_devolucao(sim, relogio)
    assert a.admin.pk == conta.pk
    entrar_com_passkey_direta(client, credencial, conta)
    return a, credencial


def entrar_de_novo(client: Any, credencial: bytes, conta: Conta) -> None:
    """Um login novo por passkey no instante corrente: a passkey fica recente."""
    from tests.apoio.admin_fluxos import entrar_com_passkey_direta

    client.post("/sair/")
    entrar_com_passkey_direta(client, credencial, conta)


def parcela_de_fabrica(
    a: Arranjo, situacao: str, valor: str = "10.00", *, do_pedido: bool = False
) -> Any:
    """Uma obrigação de teste (com o pedido e o comprador de X, se `do_pedido`) com uma parcela na
    situação dada, gravada direto."""
    from apps.financeiro.models import ObrigacaoComComprador, ParcelaDeDevolucao
    from tests.apoio.financeiro import chave_nova, obrigacao_de_teste

    obrigacao = obrigacao_de_teste(valor)
    if do_pedido:
        obrigacao = ObrigacaoComComprador.objects.create(
            rodada=a.pedido.abertura.rodada,
            ciclo=a.pedido.abertura.ciclo,
            pedido=a.pedido,
            comprador=a.comprador,
            origem_tipo="teste",
            origem_id=chave_nova(),
            motivo="ocorrencia_de_entrega",
            produtos=D(valor),
        )
    return ParcelaDeDevolucao.objects.create(
        obrigacao=obrigacao,
        pagamento=a.pagamento,
        valor=D(valor),
        situacao=situacao,
        chave_idempotencia=chave_nova()[:64],
        codigo_da_falha="indisponivel" if situacao.startswith("falha") else "",
    )


def duplicidade(a: Arranjo) -> Any:
    """Um segundo pagamento aprovado do pedido X (destino `devolucao`, motivo `duplicidade`):
    devolve o destino decidido e a obrigação integral dele."""
    from apps.financeiro.models import ObrigacaoComComprador
    from apps.pagamentos.provedor import NovaCobranca, obter_provedor
    from apps.pedidos.models import DestinoDoPagamento
    from tests.apoio.pedidos import T0, sincronizar

    nova = NovaCobranca("k-dup", a.pedido.referencia_externa, a.pedido.total, "Dup", T0 + 24 * H)
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    a.sim.aprovar(id_externo)
    sincronizar(id_externo)
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=id_externo)
    obrigacao = ObrigacaoComComprador.objects.get(
        origem_tipo="pedidos.destinodopagamento", origem_id=str(destino.pk)
    )
    return destino, obrigacao


def sem_pedido(a: Arranjo) -> Any:
    """Um pagamento aprovado que nenhum pedido tem: devolve o pagamento e a obrigação."""
    from apps.financeiro.models import ObrigacaoComComprador
    from apps.pagamentos.provedor import NovaCobranca, obter_provedor
    from apps.pedidos.models import DestinoDoPagamento
    from tests.apoio.pedidos import T0, sincronizar

    nova = NovaCobranca("k-sp", "ref-desconhecida", D("40.00"), "Sem pedido", T0 + 24 * H)
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    a.sim.aprovar(id_externo)
    sincronizar(id_externo)
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=id_externo)
    return destino.pagamento, ObrigacaoComComprador.objects.get(pedido=None, integral=D("40.00"))
