"""E04-01: catálogo de eventos e canais (acceptance A-1)."""

from apps.contas.models import Papel
from apps.notificacoes.eventos import CANAIS_POR_EVENTO, DESTINATARIO_POR_EVENTO, Canal, Evento

S, E, W = Canal.SITE, Canal.EMAIL, Canal.WHATSAPP

# transcrição da matriz da spec E04-01 (evento, destinatário, canais)
MATRIZ = [
    ("preco_alterado", Papel.COMPRADOR, {S}),
    ("fechamento_iniciado", Papel.COMPRADOR, {S, E, W}),
    ("excedentes_removidos", Papel.COMPRADOR, {S, E}),
    ("pagamento_aberto", Papel.COMPRADOR, {S, E, W}),
    ("pagamento_confirmado", Papel.COMPRADOR, {S, E}),
    ("itens_cancelados", Papel.COMPRADOR, {S, E}),
    ("retorno_para_interesse", Papel.COMPRADOR, {S, E}),
    ("estorno", Papel.COMPRADOR, {S, E}),
    ("previsao_de_entrega_alterada", Papel.COMPRADOR, {S, E}),
    ("retirada_liberada", Papel.COMPRADOR, {S, E, W}),
    ("rodada_cancelada", Papel.COMPRADOR, {S, E, W}),
    ("comunicado", Papel.COMPRADOR, {S, E, W}),
    ("falha_no_pedido_formal", Papel.ADMINISTRADOR, {S, E}),
    ("alerta_financeiro", Papel.ADMINISTRADOR, {S, E}),  # E09-03
]


def test_a_matriz_de_canais_e_a_da_especificacao() -> None:  # A-1
    assert {e.value for e in Evento} == {nome for nome, _, _ in MATRIZ}
    assert set(CANAIS_POR_EVENTO) == set(Evento)
    assert set(DESTINATARIO_POR_EVENTO) == set(Evento)
    for nome, papel, canais in MATRIZ:
        assert CANAIS_POR_EVENTO[Evento(nome)] == frozenset(canais), nome
        assert DESTINATARIO_POR_EVENTO[Evento(nome)] == papel, nome


def test_site_em_todos_whatsapp_em_cinco_e_email_ausente_so_no_preco() -> None:  # A-1
    assert all(Canal.SITE in canais for canais in CANAIS_POR_EVENTO.values())
    com_whatsapp = {e.value for e, c in CANAIS_POR_EVENTO.items() if Canal.WHATSAPP in c}
    assert com_whatsapp == {
        "fechamento_iniciado",
        "pagamento_aberto",
        "retirada_liberada",
        "rodada_cancelada",
        "comunicado",
    }
    sem_email = {e.value for e, c in CANAIS_POR_EVENTO.items() if Canal.EMAIL not in c}
    assert sem_email == {"preco_alterado"}
