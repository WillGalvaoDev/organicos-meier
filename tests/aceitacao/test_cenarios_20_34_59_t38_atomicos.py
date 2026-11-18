"""Cenários 20, 34 e 59 e T-38 (E16-07, regras 2-E e 5: caracterização contra o simulador).

A segunda revalidação da matriz mostrou afirmações compostas provadas só em parte. Cada teste daqui
executa a ação de uma afirmação atômica e confere o resultado dela por inteiro. O comportamento já
existia, então os testes passaram na primeira execução.
"""

import re
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.test import Client

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import IncrementoInvalido
from apps.catalogo.servicos import criar_produto
from apps.contas.convites import emitir_convite
from apps.contas.models import Conta, EmailEmUso
from apps.contas.moderacao import remover
from apps.financeiro.devolucoes import autorizar_devolucao
from apps.financeiro.livro import conta_da_obrigacao, saldo
from apps.financeiro.models import AlertaFinanceiro, MovimentoFinanceiro, ParcelaDeDevolucao
from apps.financeiro.reserva import (
    ReservaInsuficiente,
    avaliar_reserva,
    designar_reserva,
    registrar_aporte,
    situacao_da_reserva,
)
from apps.pagamentos.chamadas import processar_chamadas
from apps.pedidos.models import Pedido, SituacaoDoPedido
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.devolucoes import arranjo_da_devolucao, entrar_de_novo, obrigacao_sem_cobertura
from tests.apoio.financeiro import obrigacao_de_teste
from tests.apoio.pedidos import pedido_aberto, sincronizar, tentativa_criada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, FornecedorFactory

pytestmark = pytest.mark.django_db

D = Decimal
SENHA = "senha-forte-9271!"


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


# --- cenário 20: a remoção mantém o pedido pago e o histórico ---


def _remocao_com_pedido_pago(
    client: Client, relogio: RelogioControlado, sim: Any
) -> tuple[Any, Any, Any, bytes]:
    admin, credencial = administrador_com_passkey(client)
    arranjo, x = pedido_aberto(relogio)
    id_externo = tentativa_criada(x).id_externo
    assert id_externo is not None
    sim.aprovar(id_externo)
    sincronizar(id_externo)
    remover(admin, arranjo.a)
    return arranjo, x, admin, credencial


def test_cenario_20_o_pedido_pago_da_conta_removida_continua_pago(
    client: Client, relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    arranjo, x, _admin, _credencial = _remocao_com_pedido_pago(
        client, relogio, simulador_pagamentos
    )
    arranjo.a.refresh_from_db()
    assert arranjo.a.situacao == "removida"
    situacao = SituacaoDoPedido.objects.get(pedido=x)
    assert situacao.situacao == "pago"
    assert situacao.quitado_por is not None
    assert Pedido.objects.filter(pk=x.pk).exists()


def test_cenario_20_o_administrador_consulta_o_historico_financeiro_do_removido(
    client: Client, relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    _arranjo, _x, admin, credencial = _remocao_com_pedido_pago(
        client, relogio, simulador_pagamentos
    )
    entrar_de_novo(client, credencial, admin)
    resposta = client.get("/administracao/historico/")
    assert resposta.status_code == 200
    acoes = re.findall(r'<td class="acao">(.*?)</td>', resposta.content.decode(), flags=re.DOTALL)
    assert "pedido.quitar" in acoes
    assert "conta.remover" in acoes


# --- cenário 34: depois do novo aporte, a devolução é concluída, sem duplicidade ---


def test_cenario_34_depois_do_aporte_a_devolucao_e_concluida_sem_duplicidade(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    obrigacao = obrigacao_sem_cobertura(a)
    with transaction.atomic():
        designar_reserva(a.admin, obrigacao_de_teste("990.00"), D("990.00"), "consumo da reserva")
    with pytest.raises(ReservaInsuficiente), transaction.atomic():
        designar_reserva(a.admin, obrigacao, obrigacao.devido, "devolução")
    avaliar_reserva()
    assert (
        AlertaFinanceiro.objects.filter(tipo="reserva_insuficiente", resolvido_em=None).count() == 1
    )
    id_deposito = simulador_pagamentos.depositar(D("40.00"))
    with transaction.atomic():
        registrar_aporte(a.admin, D("40.00"), id_deposito, "Novo aporte")
    assert (
        AlertaFinanceiro.objects.filter(tipo="reserva_insuficiente", resolvido_em=None).count() == 0
    )
    with transaction.atomic():
        designar_reserva(a.admin, obrigacao, obrigacao.devido, "devolução")
    autorizar_devolucao(obrigacao, autor=a.admin)
    processar_chamadas()
    assert EstornoSimulado.objects.filter(situacao="concluido").count() == 1
    assert ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao == "concluida"
    assert saldo(conta_da_obrigacao(obrigacao)) == D("0.00")
    movimentos = MovimentoFinanceiro.objects.count()
    reserva = situacao_da_reserva()
    autorizar_devolucao(obrigacao, autor=a.admin)
    processar_chamadas()
    assert EstornoSimulado.objects.filter(situacao="concluido").count() == 1
    assert ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).count() == 1
    assert MovimentoFinanceiro.objects.count() == movimentos
    assert situacao_da_reserva() == reserva


# --- cenário 59: o banimento vale só para o endereço, com caixa e espaços normalizados ---


def _banida_e_aliases() -> Any:
    admin = ContaFactory.create(administrador=True)
    ana = ContaFactory.create(email_normalizado="ana@x.com")
    ana.set_password(SENHA)
    ana.save()
    remover(admin, ana)
    return admin


def test_cenario_59_o_endereco_banido_com_outras_maiusculas_e_recusado_no_login() -> None:
    _banida_e_aliases()
    for escrito in ("ANA@x.com", "  Ana@X.com "):
        cliente = Client()
        cliente.post("/entrar/", {"login": escrito, "password": SENHA})
        assert "_auth_user_id" not in cliente.session, escrito


def test_cenario_59_o_endereco_banido_com_outras_maiusculas_e_recusado_no_novo_cadastro() -> None:
    admin = _banida_e_aliases()
    contas = Conta.objects.count()
    for escrito in ("ANA@x.com", "  Ana@X.com "):
        with pytest.raises(EmailEmUso):
            emitir_convite(admin, escrito, "comprador")
    assert Conta.objects.count() == contas


def test_cenario_59_o_alias_com_pontos_nao_e_afetado() -> None:
    _banida_e_aliases()
    alias = ContaFactory.create(email_normalizado="a.na@x.com")
    alias.set_password(SENHA)
    alias.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": "a.na@x.com", "password": SENHA})
    assert "_auth_user_id" in cliente.session


# --- T-38: incremento recusado com zero, negativo e mais de 3 casas (entrada Decimal) ---


def _incremento_recusado(incremento: Decimal) -> None:
    admin = ContaFactory.create(administrador=True)
    fornecedor = FornecedorFactory.create()
    with pytest.raises(IncrementoInvalido):
        criar_produto(
            admin, fornecedor, nome="X", unidade="kg", incremento=incremento, preco=D("1.00")
        )
    assert Produto.objects.count() == 0


def test_t38_incremento_zero_e_recusado_e_o_produto_nao_e_criado() -> None:
    _incremento_recusado(D("0"))


def test_t38_incremento_negativo_e_recusado_e_o_produto_nao_e_criado() -> None:
    _incremento_recusado(D("-1"))


def test_t38_incremento_com_mais_de_3_casas_e_recusado_e_o_produto_nao_e_criado() -> None:
    _incremento_recusado(D("0.0001"))
