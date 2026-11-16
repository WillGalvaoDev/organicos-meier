"""E14-08: ponta a ponta, entrega, ocorrências, liberação, retirada e descarte
(acceptance A-1 a A-12), pelas telas e com o simulador de pagamentos."""

import copy
import re
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.test import Client

from apps.financeiro.livro import conta, saldo
from apps.financeiro.models import (
    AlertaFinanceiro,
    Destinacao,
    ItemReembolsado,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
    Reembolso,
)
from apps.fornecedores.models import Fornecedor
from apps.notificacoes.models import Notificacao
from apps.pagamentos.chamadas import processar_chamadas
from apps.pedidos.models import (
    CancelamentoDaRodada,
    DescarteDeItem,
    ItemDoPedido,
    LinhaDoPedidoFormal,
    OcorrenciaDeEntrega,
    Pedido,
    PedidoFormal,
    RecebimentoDoFornecedor,
    RetiradaDeItem,
)
from apps.rodadas.models import CondicaoDoProdutoNoCiclo
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.entrega import item_de
from tests.apoio.pedido_formal import EMAIL_DO_PEDIDO, PRAZO
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
L = T0 + 72 * H
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)
ENDERECO = "Rua das Hortas, 100 — Méier, Rio de Janeiro/RJ"


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _processar_tudo() -> None:
    while processar_chamadas():
        pass


def _invariante_ok() -> None:
    from apps.financeiro.invariante import verificar_invariante_agora

    verificar_invariante_agora()
    assert not AlertaFinanceiro.objects.filter(
        tipo="invariante_violado", resolvido_em__isnull=True
    ).exists()


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _foto_do_congelado() -> Any:
    return (
        list(PedidoFormal.objects.order_by("pk").values()),
        list(LinhaDoPedidoFormal.objects.order_by("pk").values()),
        list(Pedido.objects.order_by("pk").values()),
        list(ItemDoPedido.objects.order_by("pk").values()),
    )


def _invariantes(inicio: Any) -> None:
    """O A-12: o congelado igual ao do começo, a conta por item e o invariante financeiro."""
    assert _foto_do_congelado() == inicio
    for item in ItemDoPedido.objects.all():
        reembolsado = sum((i.quantidade for i in ItemReembolsado.objects.filter(item=item)), D("0"))
        retirado = sum((r.quantidade for r in RetiradaDeItem.objects.filter(item=item)), D("0"))
        descartado = sum((d.quantidade for d in DescarteDeItem.objects.filter(item=item)), D("0"))
        assert reembolsado + retirado + descartado <= item.quantidade
    _invariante_ok()


def _ae_pela_tela(
    client: Client, relogio: RelogioControlado, sim: Any, *, liberacao_horas: int = 0
) -> tuple[Any, Any, Any, Any, bytes, Any]:
    """O AE com a aprovação pela tela da E11-07 e o endereço registrado pela tela da E14-03. O
    relógio fica em `T0 + 48h`. Devolve o arranjo, X, Y, o pedido formal, a credencial do
    administrador e a foto do que fica congelado."""
    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    sim.definir_liberacao("pix", horas=liberacao_horas)
    a, x, y = arranjo_ap(relogio)
    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(email_pedido=EMAIL_DO_PEDIDO)
    pagar(relogio, sim, x)
    pagar(relogio, sim, y)
    for produto in (a.p1, a.p2):
        CondicaoDoProdutoNoCiclo.objects.get_or_create(
            ciclo=a.ciclo,
            produto=produto,
            defaults={"incremento": produto.incremento, "multiplo": produto.multiplo},
        )
    relogio.congelar(PRAZO)
    entrar_de_novo(client, credencial, a.admin)
    base = f"/administracao/rodadas/{a.rodada.pk}/apuracao"
    assert client.post(f"{base}/iniciar/").status_code == 302
    assert client.post(f"{base}/aprovar/").status_code == 302
    resposta = client.post("/administracao/retirada/endereco/", {"texto": ENDERECO})
    assert resposta.status_code == 302
    pedido_formal = PedidoFormal.objects.get(rodada=a.rodada)
    return a, x, y, pedido_formal, credencial, _foto_do_congelado()


def _rota(a: Any, sufixo: str) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/{sufixo}/"


def _receber(client: Client, a: Any, produto: Any, quantidade: str) -> Any:
    campos = {"produto": produto.pk, "quantidade": quantidade, "acionamento": str(uuid.uuid4())}
    return client.post(_rota(a, "recebimento/registrar"), campos)


def _ocorrencia(client: Client, a: Any, item: Any, tipo: str, quantidade: str) -> Any:
    campos = {
        "item": item.pk,
        "tipo": tipo,
        "quantidade": quantidade,
        "acionamento": str(uuid.uuid4()),
    }
    return client.post(_rota(a, "ocorrencias/registrar"), campos, follow=True)


def _liberar(client: Client, a: Any) -> Any:
    return client.post(_rota(a, "retirada/liberar"), {"acionamento": str(uuid.uuid4())})


def _retirar(client: Client, a: Any, item: Any, quantidade: str) -> Any:
    campos = {"item": item.pk, "quantidade": quantidade, "acionamento": str(uuid.uuid4())}
    return client.post(_rota(a, "retiradas/registrar"), campos)


def _autorizar_pela_tela(client: Client, a: Any, credencial: bytes, obrigacao: Any) -> Any:
    entrar_de_novo(client, credencial, a.admin)
    return client.post(f"/administracao/financeiro/devolucoes/{obrigacao.pk}/autorizar/")


def _concluir_devolucoes(sim: Any) -> None:
    _processar_tudo()
    sim.entregar_avisos()
    _processar_tudo()


def _recebido_e_liberado(
    client: Client, relogio: RelogioControlado, sim: Any, **opcoes: Any
) -> tuple[Any, Any, Any, Any, bytes, Any]:
    """O A-1: recebimento parcial, a liberação recusada, a ocorrência e a liberação em `L`."""
    a, x, y, pf, credencial, inicio = _ae_pela_tela(client, relogio, sim, **opcoes)
    relogio.congelar(T0 + 60 * H)
    entrar_de_novo(client, credencial, a.admin)
    assert _receber(client, a, a.p1, "9").status_code == 302
    assert _receber(client, a, a.p2, "12").status_code == 302
    recusada = _liberar(client, a)
    assert recusada.status_code == 409
    assert "Ainda falta resolver: P1 (2 unidade)." in _texto(recusada)
    resposta = _ocorrencia(client, a, item_de(x, a.p1), "faltante", "2")
    assert "Reembolso de R$ 23,59" in _texto(resposta)
    relogio.congelar(L)
    entrar_de_novo(client, credencial, a.admin)
    assert _liberar(client, a).status_code == 302
    return a, x, y, pf, credencial, inicio


def _comprador(conta_do_comprador: Any) -> Client:
    cliente = Client()
    cliente.force_login(conta_do_comprador)
    return cliente


def _o_comprador_e_o_fornecedor(a: Any, x: Any) -> None:
    """O A-11: o comprador A não alcança as rotas da E14-06 e o fornecedor F só vê o permitido."""
    conta_f = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    modelos = (OcorrenciaDeEntrega, RecebimentoDoFornecedor, RetiradaDeItem, DescarteDeItem)
    antes = [m.objects.count() for m in modelos]
    comprador = _comprador(a.a)
    campos = {
        "item": item_de(x, a.p1).pk,
        "produto": a.p1.pk,
        "tipo": "faltante",
        "quantidade": "1",
        "acionamento": str(uuid.uuid4()),
    }
    for rota in ("recebimento", "ocorrencias", "retiradas"):
        assert comprador.get(_rota(a, rota)).status_code == 403
    for rota in (
        "recebimento/registrar",
        "retirada/liberar",
        "ocorrencias/registrar",
        "retiradas/registrar",
        "descartes/registrar",
    ):
        assert comprador.post(_rota(a, rota), campos).status_code == 403
    assert [m.objects.count() for m in modelos] == antes
    fornecedor = _comprador(conta_f)
    pagina = fornecedor.get(f"/fornecedor/rodadas/{a.rodada.pk}/")
    arquivo = fornecedor.get(f"/fornecedor/rodadas/{a.rodada.pk}/pedido-formal.csv")
    assert pagina.status_code == arquivo.status_code == 200
    texto = _texto(pagina)
    assert "Disponível para retirada" in texto
    for proibido in (a.a.nome, a.b.nome, "Rua das Hortas", "Faltante", "Incorreto", "Descarte"):
        assert proibido not in texto
        assert proibido not in arquivo.content.decode()


# --- A-1 a A-3: a entrega parcial resolvida por ocorrência, antes do repasse --------------


def test_entrega_parcial_ocorrencia_e_liberacao(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, x, _y, _pf, _c, inicio = _recebido_e_liberado(client, relogio, sim)
    avisos = Notificacao.objects.filter(evento="retirada_liberada")
    assert {n.conta_id for n in avisos} == {a.a.pk, a.b.pk}
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo="ocorrencia_de_entrega")
    assert obrigacao.devido == D("23.59")
    _invariantes(inicio)


def test_a_devolucao_da_ocorrencia_pela_tela_da_e10(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    a, x, _y, _pf, credencial, inicio = _recebido_e_liberado(client, relogio, sim)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo="ocorrencia_de_entrega")
    assert _autorizar_pela_tela(client, a, credencial, obrigacao).status_code == 302
    _concluir_devolucoes(sim)
    assert ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao == "concluida"
    assert Notificacao.objects.filter(conta=a.a, evento="estorno").exists()
    assert "Concluída" in _texto(_comprador(a.a).get(f"/pedidos/{x.pk}/"))
    _invariantes(inicio)


def _repasse_pela_tela(client: Client, a: Any, sim: Any, valor: str) -> Any:
    id_saida = sim.registrar_saida(D(valor.replace(",", ".")), descricao="repasse")
    return client.post(
        _rota(a, "saidas/repasse"),
        {"valor": valor, "identificacao": id_saida, "justificativa": "Pix ao fornecedor"},
    )


def test_o_repasse_fica_limitado_ao_que_sobrou_da_obrigacao_com_o_fornecedor(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    a, _x, _y, _pf, credencial, inicio = _recebido_e_liberado(client, relogio, sim)
    entrar_de_novo(client, credencial, a.admin)
    assert _repasse_pela_tela(client, a, sim, "150,00").status_code == 302
    obrigacao_f = conta(
        Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk
    )
    assert saldo(obrigacao_f) == D("0.00")
    recusado = _repasse_pela_tela(client, a, sim, "0,01")
    assert recusado.status_code == 409
    assert saldo(obrigacao_f) == D("0.00")
    _invariantes(inicio)


# --- A-4: ocorrência depois do repasse e da liberação ---------------------------------------


def test_ocorrencia_depois_do_repasse_coberta_pela_reserva(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from apps.financeiro.reserva import (
        designar_reserva,
        registrar_aporte,
        sem_cobertura_da_obrigacao,
    )

    a, x, y, _pf, credencial, inicio = _ae_pela_tela(client, relogio, sim)
    entrar_de_novo(client, credencial, a.admin)
    assert _repasse_pela_tela(client, a, sim, "170,00").status_code == 302
    for produto, quantidade in ((a.p1, "11"), (a.p2, "12")):
        assert _receber(client, a, produto, quantidade).status_code == 302
    relogio.congelar(L)
    entrar_de_novo(client, credencial, a.admin)
    assert _liberar(client, a).status_code == 302
    obrigacao_f = conta(
        Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk
    )
    antes_de_f = saldo(obrigacao_f)
    relogio.congelar(L + timedelta(days=1))
    entrar_de_novo(client, credencial, a.admin)
    resposta = _ocorrencia(client, a, item_de(y, a.p2), "incorreto", "2")
    texto = _texto(resposta)
    assert "Reembolso de R$ 11,79" in texto
    assert "Parte do reembolso ainda não tem cobertura: R$ 10,00." in texto
    ocorrencia = OcorrenciaDeEntrega.objects.get()
    assert ocorrencia.etapa == "disponivel_para_retirada"
    obrigacao = ObrigacaoComComprador.objects.get(pedido=y, motivo="ocorrencia_de_entrega")
    assert sem_cobertura_da_obrigacao(obrigacao) == D("10.00")
    id_deposito = sim.depositar(D("1000.00"))
    with transaction.atomic():
        registrar_aporte(a.admin, D("1000.00"), id_deposito, "Aporte")
        designar_reserva(a.admin, obrigacao, D("10.00"), "Cobrir a parte de produtos")
    assert sem_cobertura_da_obrigacao(obrigacao) == D("0.00")
    assert _autorizar_pela_tela(client, a, credencial, obrigacao).status_code == 302
    _concluir_devolucoes(sim)
    assert ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao == "concluida"
    assert obrigacao.devido == D("11.79")
    assert saldo(obrigacao_f) == antes_de_f
    from apps.pedidos.ocorrencias import saldo_do_item

    assert saldo_do_item(item_de(y, a.p2)) == D("6")
    _invariantes(inicio)
    _o_comprador_e_o_fornecedor(a, x)  # A-11


# --- A-5 e A-6: nova rodada, retirada antiga, prazo e descarte ------------------------------


def _com_nova_rodada(
    client: Client, relogio: RelogioControlado, sim: Any
) -> tuple[Any, Any, Any, bytes, Any, Any, Any]:
    """O A-5: depois da liberação, a nova rodada do fornecedor com o interesse de C, e a retirada
    antiga em `L + 2 dias`. Devolve o arranjo, X, Y, a credencial, a foto, a nova rodada e C."""
    from apps.interesses.consultas import total_reservado
    from apps.rodadas.models import Rodada

    a, x, y, _pf, credencial, inicio = _recebido_e_liberado(client, relogio, sim)
    assert (
        client.post(f"/administracao/fornecedores/{a.fornecedor.pk}/rodadas/abrir/").status_code
        == 302
    )
    nova = Rodada.objects.exclude(pk=a.rodada.pk).get()
    assert nova.etapa == "interesse"
    incluida = client.post(
        f"/administracao/rodadas/{nova.pk}/estoque/incluir/", {"produto": a.p1.pk, "limite": "11"}
    )
    assert incluida.status_code == 302
    c = ContaFactory.create(nome="Comprador C")
    comprador = _comprador(c)
    interesse = comprador.post(
        "/interesses/", {"produto": a.p1.pk, "quantidade": "11", "origem": "carrinho"}
    )
    assert interesse.status_code == 302
    assert total_reservado(a.p1) == D("11")
    relogio.congelar(L + timedelta(days=2))
    entrar_de_novo(client, credencial, a.admin)
    assert _retirar(client, a, item_de(x, a.p1), "4").status_code == 302
    assert RetiradaDeItem.objects.count() == 1
    assert total_reservado(a.p1) == D("11")
    return a, x, y, credencial, inicio, nova, c


def test_cenario_22_nova_rodada_e_retirada_antiga(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, x, _y, _credencial, inicio, nova, _c = _com_nova_rodada(client, relogio, sim)
    assert nova.pk != a.rodada.pk
    assert RetiradaDeItem.objects.get().item.pedido_id == x.pk
    _invariantes(inicio)


def test_cenario_23_prazo_e_descarte(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    a, x, y, credencial, inicio, _nova, _c = _com_nova_rodada(client, relogio, sim)
    relogio.congelar(L + timedelta(days=8))
    entrar_de_novo(client, credencial, a.admin)
    pagina = _texto(client.get(_rota(a, "retiradas")))
    assert "Prazo encerrado — pendentes de decisão" in pagina
    assert not DescarteDeItem.objects.exists()
    reembolsos = Reembolso.objects.count()
    for item, quantidade in ((item_de(x, a.p2), "4"), (item_de(y, a.p1), "5")):
        campos = {"item": item.pk, "quantidade": quantidade, "acionamento": str(uuid.uuid4())}
        assert client.post(_rota(a, "descartes/registrar"), campos).status_code == 302
    assert DescarteDeItem.objects.count() == 2
    assert Reembolso.objects.count() == reembolsos
    assert re.search(r"P2 4 0 0 4 0", _texto(_comprador(a.a).get(f"/pedidos/{x.pk}/")))
    _invariantes(inicio)
    _o_comprador_e_o_fornecedor(a, x)  # A-11


# --- A-7 e A-8: o cancelamento ----------------------------------------------------------------


@pytest.mark.parametrize("reembolso", ["sim", "nao"])
def test_a_rodada_liberada_nao_e_cancelada_pela_tela(
    client: Client, relogio: RelogioControlado, sim: Any, reembolso: str
) -> None:  # A-7
    a, x, _y, _pf, credencial, inicio = _recebido_e_liberado(client, relogio, sim)
    ocorrencias = OcorrenciaDeEntrega.objects.count()
    entrar_de_novo(client, credencial, a.admin)
    resposta = client.post(_rota(a, "cancelar"), {"reembolso": reembolso})
    assert resposta.status_code == 409
    assert "A rodada já foi encerrada e não pode ser cancelada." in _texto(resposta)
    assert not CancelamentoDaRodada.objects.exists()
    assert OcorrenciaDeEntrega.objects.count() == ocorrencias
    from apps.rodadas.models import Rodada

    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "disponivel_para_retirada"
    _invariantes(inicio)
    _o_comprador_e_o_fornecedor(a, x)  # A-11


def test_cenario_52_cancelamento_com_ocorrencia_anterior(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    a, x, _y, _pf, credencial, inicio = _ae_pela_tela(client, relogio, sim)
    resposta = _ocorrencia(client, a, item_de(x, a.p1), "faltante", "2")
    assert "Ocorrência registrada." in _texto(resposta)
    ocorrencia = OcorrenciaDeEntrega.objects.get()
    reembolso_antes = Reembolso.objects.get(pk=ocorrencia.reembolso_id)
    entrar_de_novo(client, credencial, a.admin)
    assert client.post(_rota(a, "cancelar"), {"reembolso": "sim"}).status_code == 302
    _processar_tudo()
    assert OcorrenciaDeEntrega.objects.count() == 1
    assert Reembolso.objects.get(pk=ocorrencia.reembolso_id) == reembolso_antes
    cancelamento = ObrigacaoComComprador.objects.get(pedido=x, motivo="cancelamento_da_rodada")
    assert cancelamento.devido == D("70.76")
    recebimento = _receber(client, a, a.p1, "1")
    assert recebimento.status_code == 409
    assert "O recebimento só é registrado enquanto a rodada aguarda o fornecedor." in _texto(
        recebimento
    )
    nova = _ocorrencia(client, a, item_de(x, a.p1), "faltante", "1")
    assert nova.status_code == 409
    assert OcorrenciaDeEntrega.objects.count() == 1
    _invariantes(inicio)


# --- A-9: concorrência pela rota (T-18) -------------------------------------------------------


def _cookies(client: Client) -> Any:
    return copy.deepcopy(client.cookies)


def _cliente(cookies: Any) -> Client:
    cliente = Client()
    cliente.cookies = copy.deepcopy(cookies)
    return cliente


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_t18_duas_ocorrencias_ao_mesmo_tempo_pela_rota(
    client: Client,
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-9
    from apps.pedidos import ocorrencias as modulo
    from tests.apoio.corrida import Corrida

    a, x, _y, _pf, _credencial, inicio = _ae_pela_tela(client, relogio, simulador_pagamentos)
    item = item_de(x, a.p1)
    cookies = _cookies(client)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")

    def enviar(tipo: str) -> Any:
        campos = {
            "item": item.pk,
            "tipo": tipo,
            "quantidade": "4",
            "acionamento": str(uuid.uuid4()),
        }
        return _cliente(cookies).post(_rota(a, "ocorrencias/registrar"), campos)

    ra, rb = corrida.rodar(
        lambda: enviar("faltante"),
        lambda: enviar("nao_entregue"),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert rb.excecao is None, repr(rb.excecao)
    assert (ra.valor.status_code, rb.valor.status_code) == (302, 409)
    assert "A quantidade passa do saldo deste item (2 unidade)." in _texto(rb.valor)
    assert corrida.b_esperou
    assert (Reembolso.objects.count(), ObrigacaoComComprador.objects.count()) == (1, 1)
    assert sum(o.quantidade for o in OcorrenciaDeEntrega.objects.filter(item=item)) == D("4")
    _invariantes(inicio)


# --- A-10: o comprador suspenso retira --------------------------------------------------------


def test_cenario_19_o_suspenso_retira(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    from apps.contas.models import Conta

    a, x, _y, _pf, credencial, inicio = _recebido_e_liberado(client, relogio, sim)
    Conta.objects.filter(pk=a.a.pk).update(situacao="suspensa")
    a.a.refresh_from_db()
    entrar_de_novo(client, credencial, a.admin)
    assert _retirar(client, a, item_de(x, a.p1), "4").status_code == 302
    assert RetiradaDeItem.objects.count() == 1
    pagina = _comprador(a.a).get(f"/pedidos/{x.pk}/")
    assert pagina.status_code == 200
    assert "Retirada liberada em" in _texto(pagina)
    _invariantes(inicio)
