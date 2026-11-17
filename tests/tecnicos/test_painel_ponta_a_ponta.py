"""E15-07: ponta a ponta, painel e alertas operacionais (acceptance A-1 a A-15), com o simulador de
pagamentos, as tarefas chamadas como o worker as chama, as telas do administrador e o relógio
controlado. Sem código de produção novo.

Desvios documentados no review.md: um só administrador (ADM1), a chamada que falhou de vez e a
consulta divergente criadas direto (o simulador não tem recusa definitiva de cancelamento nem
valor divergente), e o arranjo de A-8 e A-10 sobre o `consultar_pagamento`.
"""

import re
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core import mail
from django.test import Client

from apps.financeiro.models import AlertaFinanceiro
from apps.pagamentos.chamadas import processar_chamadas
from apps.pedidos.models import Pedido
from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.apuracao import H
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.entrega import arranjo_ae, descartar, receber_tudo, registrar_endereco
from tests.apoio.operacao import INSTANTE, MIN, concluir_todas, notificacoes
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
L = T0 + 72 * H
URL = "/administracao/"
CINCO_DE_UM_MINUTO = (
    "processar_envios_pendentes",
    "processar_chamadas_ao_provedor",
    "encerrar_fechamentos_vencidos",
    "bloquear_tentativas_vencidas",
    "enviar_pedidos_formais",
)


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


class Painel:
    """ADM1 autenticado por passkey; lê o painel e o histórico em qualquer instante."""

    def __init__(self, client: Client, relogio: RelogioControlado) -> None:
        self.client = client
        self.relogio = relogio
        relogio.congelar(T0)
        self.admin, self.credencial = administrador_com_passkey(client)

    def entrar(self, instante: Any = None) -> None:
        if instante is not None:
            self.relogio.congelar(instante)
        entrar_de_novo(self.client, self.credencial, self.admin)

    def pagina(self, instante: Any = None, url: str = URL) -> Any:
        self.entrar(instante)
        return self.client.get(url)

    def post(self, url: str, campos: dict[str, Any] | None = None, **opcoes: Any) -> Any:
        self.entrar()
        return self.client.post(url, campos or {}, **opcoes)


@pytest.fixture
def painel(client: Client, relogio: RelogioControlado) -> Painel:
    return Painel(client, relogio)


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _secoes(resposta: Any) -> dict[str, str]:
    html = resposta.content.decode()
    achados = re.split(r"<h2[^>]*>(.*?)</h2>", html, flags=re.DOTALL)
    return {
        " ".join(achados[i].split()): " ".join(re.sub(r"<[^>]+>", " ", achados[i + 1]).split())
        for i in range(1, len(achados) - 1, 2)
    }


def _acoes(painel: Painel, instante: Any = None) -> str:
    return _secoes(painel.pagina(instante))["Ações necessárias"]


def _invariante_ok() -> None:
    from apps.financeiro.invariante import verificar_invariante_agora

    verificar_invariante_agora()
    assert not AlertaFinanceiro.objects.filter(
        tipo="invariante_violado", resolvido_em__isnull=True
    ).exists()


def _um_aberto_por_par() -> None:
    abertos = AlertaFinanceiro.objects.filter(resolvido_em__isnull=True)
    pares = [(a.tipo, a.chave) for a in abertos]
    assert len(pares) == len(set(pares))


def _verificar() -> None:
    from apps.operacao.tarefas import verificar_operacao

    verificar_operacao(timestamp=0)


def _rota(a: Any, sufixo: str) -> str:
    rodada = getattr(a, "rodada", a)
    return f"/administracao/rodadas/{rodada.pk}/{sufixo}/"


# --- cenário 1: a rodada inteira pelo painel ----------------------------------------------------


def _ap_i2() -> Any:
    from apps.fornecedores.models import Fornecedor
    from tests.apoio.interesses import cenario, reservada

    rodada, produto, _estoque = cenario(limite="30", nome="Q", preco=D("10.00"), multiplo=D("12"))
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(
        nome="G", minimo=D("100.00"), email_pedido="pedidos@g.example"
    )
    comprador = ContaFactory.create(nome="Compradora Gê")
    reservada(comprador, produto, 18)
    return rodada


def _pagar(sim: Any, pedido: Pedido) -> None:
    from tests.apoio.pedidos import tentativa_criada

    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    from apps.nucleo.tempo import agora

    sim.aprovar(id_externo, em=agora())
    sim.entregar_avisos()
    processar_chamadas()


def test_da_primeira_a_ultima_etapa_ate_a_aprovacao(painel: Painel, sim: Any) -> None:  # A-1 e A-2
    from apps.rodadas.fechamento import encerrar_fechamentos_vencidos, prazo_do_fechamento

    rodada = _ap_i2()
    sim.definir_liberacao("pix", horas=0)
    assert "Mínimo atingido: o fechamento pode ser iniciado." in _acoes(painel, T0)
    assert painel.post(_rota(rodada, "fechamento/iniciar")).status_code == 302
    resposta = painel.pagina()
    assert "Mínimo atingido" not in _secoes(resposta)["Ações necessárias"]
    assert "Fecha em" in _secoes(resposta)["Rodadas"]
    prazo = prazo_do_fechamento(rodada)
    assert prazo is not None
    painel.relogio.congelar(prazo + MIN)
    assert encerrar_fechamentos_vencidos() == 1
    assert "Fechamento encerrado: aguarda a abertura do pagamento." in _acoes(painel)
    t1 = prazo + MIN
    resposta = painel.post(
        f"/administracao/rodadas/{rodada.pk}/pagamento/abrir/", {"frete": "22,00"}
    )
    assert resposta.status_code == 302
    pedido = Pedido.objects.get()
    assert "Pagamento até" in _secoes(painel.pagina(t1 + H))["Rodadas"]
    _pagar(sim, pedido)
    tarde = painel.pagina(t1 + 48 * H)
    assert "Apta para a apuração final desde" in _secoes(tarde)["Ações necessárias"]
    base = f"/administracao/rodadas/{rodada.pk}/apuracao"
    assert painel.post(f"{base}/iniciar/").status_code == 302
    assert "Apuração feita: aguarda a aprovação do resultado." in _acoes(painel)
    assert painel.post(f"{base}/aprovar/").status_code == 302
    secoes = _secoes(painel.pagina())
    assert "Aguardando fornecedor" in secoes["Rodadas"]
    assert "Recebimento:" in secoes["Ações necessárias"]
    _invariante_ok()
    _um_aberto_por_par()


def test_pedido_formal_com_falhas_e_reenvio(painel: Painel, sim: Any, settings: Any) -> None:  # A-3
    from apps.pedidos.models import PedidoFormal
    from tests.apoio.pedido_formal import EMAIL_DO_PEDIDO, FALHA, LOCMEM, PRAZO, processar

    settings.EMAIL_BACKEND = FALHA
    a, _x, _y, _pf = _ae(painel, sim, endereco=False)
    for instante in (PRAZO, PRAZO + 5 * MIN, PRAZO + 35 * MIN):
        processar(painel.relogio, instante)
    settings.EMAIL_BACKEND = LOCMEM
    assert "não foi enviado depois das três tentativas: reenvie." in _acoes(painel)
    pagina = painel.pagina(url=_rota(a, "pedido-formal")).content.decode()
    achado = re.search(r'name="token" value="([^"]+)"', pagina)
    assert achado
    resposta = painel.post(_rota(a, "pedido-formal/reenviar"), {"token": achado.group(1)})
    assert resposta.status_code == 302
    assert "não foi enviado depois" not in _acoes(painel)
    assert PedidoFormal.objects.get().fornecedor.email_pedido == EMAIL_DO_PEDIDO
    _invariante_ok()


def _ae(painel: Painel, sim: Any, *, endereco: bool = True, **opcoes: Any) -> Any:
    """O AE com o administrador do painel (o arranjo aproveita a conta dele)."""
    a, x, y, pf = arranjo_ae(painel.relogio, sim, **opcoes)
    if endereco:
        registrar_endereco(a.admin)
    return a, x, y, pf


def test_repasse_e_frete_pelo_painel(painel: Painel, sim: Any) -> None:  # A-4
    a, _x, _y, _pf = _ae(painel, sim, liberacao_horas=0)
    acoes = _acoes(painel)
    assert "Repasse ao fornecedor liberado: R$ 170,00." in acoes
    assert "Pagamento do frete liberado: R$ 22,00." in acoes
    id_repasse = sim.registrar_saida(D("170.00"), descricao="repasse")
    resposta = painel.post(
        _rota(a, "saidas/repasse"),
        {"valor": "170,00", "identificacao": id_repasse, "justificativa": "Pix"},
    )
    assert resposta.status_code == 302
    resposta = painel.post(
        _rota(a, "saidas/frete"),
        {"valor": "22,00", "identificacao": "frete-1", "justificativa": "Frete"},
    )
    assert resposta.status_code == 302
    depois = _acoes(painel)
    assert "Repasse ao fornecedor liberado" not in depois
    assert "Pagamento do frete liberado" not in depois
    _invariante_ok()


def _ids(item: Any) -> dict[str, Any]:
    return {"acionamento": str(uuid.uuid4()), "item": item.pk}


def test_recebimento_liberacao_e_descarte_pelo_painel(painel: Painel, sim: Any) -> None:  # A-5
    from apps.pedidos.models import ItemDoPedido
    from apps.pedidos.ocorrencias import saldo_do_item

    a, _x, _y, pf = _ae(painel, sim, liberacao_horas=0, endereco=False)
    for linha in pf.linhas.order_by("pk"):
        resposta = painel.post(
            _rota(a, "recebimento/registrar"),
            {
                "produto": linha.produto_id,
                "quantidade": str(linha.quantidade).replace(".", ","),
                "acionamento": str(uuid.uuid4()),
            },
        )
        assert resposta.status_code == 302
    sem = _acoes(painel)
    assert "Recebimento resolvido: a retirada pode ser liberada. Registre antes o endereço" in sem
    registrar_endereco(a.admin)
    com = _acoes(painel)
    assert "Recebimento resolvido: a retirada pode ser liberada." in com
    assert "Registre antes" not in com
    painel.relogio.congelar(L)
    resposta = painel.post(_rota(a, "retirada/liberar"), {"acionamento": str(uuid.uuid4())})
    assert resposta.status_code == 302
    assert "Retirada até" in _secoes(painel.pagina())["Rodadas"]
    tarde = painel.pagina(L + timedelta(days=8))
    assert "Prazo de retirada encerrado: 4 item(ns)" in _secoes(tarde)["Ações necessárias"]
    assert "retirada encerrada em" in _secoes(tarde)["Prazos encerrados"]
    for item in ItemDoPedido.objects.filter(pedido__abertura__rodada=a.rodada):
        campos = {**_ids(item), "quantidade": str(saldo_do_item(item)).replace(".", ",")}
        assert painel.post(_rota(a, "descartes/registrar"), campos).status_code == 302
    final = _secoes(painel.pagina())
    assert "Nenhuma rodada em andamento." in final["Rodadas"]
    assert "Prazo de retirada" not in final["Ações necessárias"]
    _invariante_ok()


# --- cenário 2: worker parado e retomado --------------------------------------------------------


def _worker_parado(painel: Painel) -> Any:
    painel.relogio.congelar(INSTANTE)
    concluir_todas(INSTANTE)
    painel.relogio.congelar(INSTANTE + 6 * MIN)
    concluir_todas(INSTANTE + 6 * MIN, exceto=CINCO_DE_UM_MINUTO)
    _verificar()
    return painel.admin


def test_worker_parado_abre_e_painel_mostra(painel: Painel) -> None:  # A-6
    admin = _worker_parado(painel)
    abertos = AlertaFinanceiro.objects.filter(tipo="tarefa_atrasada", resolvido_em__isnull=True)
    assert sorted(a.chave for a in abertos) == sorted(CINCO_DE_UM_MINUTO)
    avisos = [n for n in notificacoes(admin) if n.titulo == "Tarefa atrasada"]
    assert len(avisos) == 5
    resposta = painel.pagina(INSTANTE + 6 * MIN)
    secoes = _secoes(resposta)
    assert secoes["Alertas abertos"].count("Tarefa atrasada") == 5
    assert secoes["Tarefas periódicas"].count("Atrasada desde") == 5
    _um_aberto_por_par()


def test_worker_retomado_resolve(painel: Painel) -> None:  # A-7
    from apps.notificacoes.processamento import processar_envios
    from apps.notificacoes.tarefas import processar_envios_pendentes
    from apps.pagamentos.tarefas import processar_chamadas_ao_provedor
    from apps.pedidos.tarefas import bloquear_tentativas_vencidas, enviar_pedidos_formais
    from apps.rodadas.tarefas import encerrar_fechamentos_vencidos_agora

    _worker_parado(painel)
    mail.outbox.clear()
    for tarefa in (
        processar_envios_pendentes,
        processar_chamadas_ao_provedor,
        encerrar_fechamentos_vencidos_agora,
        bloquear_tentativas_vencidas,
        enviar_pedidos_formais,
    ):
        tarefa(timestamp=0)
    _verificar()
    assert not AlertaFinanceiro.objects.filter(
        tipo="tarefa_atrasada", resolvido_em__isnull=True
    ).exists()
    processar_envios()
    assert any("Tarefa atrasada" in m.subject for m in mail.outbox)
    secoes = _secoes(painel.pagina(INSTANTE + 6 * MIN))
    assert "Nenhum alerta aberto." in secoes["Alertas abertos"]
    assert "Atrasada desde" not in secoes["Tarefas periódicas"]
    assert "Em dia" in secoes["Tarefas periódicas"]


# --- cenário 3: provedor com problemas ----------------------------------------------------------


def _chamada_que_falha_de_vez(painel: Painel) -> None:
    """Uma consulta a um pagamento que o provedor não conhece: depois de 24 h vira `falhou`."""
    from apps.pagamentos.chamadas import agendar_chamada
    from apps.pagamentos.models import ChamadaAoProvedor

    painel.relogio.congelar(T0)
    agendar_chamada("consultar_pagamento", "sim-999")
    instante = T0
    for _ in range(60):
        painel.relogio.congelar(instante)
        processar_chamadas()
        chamada = ChamadaAoProvedor.objects.get(operacao="consultar_pagamento", alvo="sim-999")
        if chamada.situacao == "falhou":
            return
        instante += timedelta(hours=1)
    raise AssertionError("a chamada não falhou de vez")


def test_chamada_que_falhou_e_a_ciencia_pelo_painel(painel: Painel, sim: Any) -> None:  # A-8, A-9
    from apps.nucleo.auditoria import EntradaAuditoria

    _chamada_que_falha_de_vez(painel)
    concluir_todas(_agora())
    _verificar()
    alerta = AlertaFinanceiro.objects.get(tipo="chamada_ao_provedor_falhou")
    secao = painel.pagina().content.decode()
    assert f'action="/administracao/alertas/{alerta.pk}/ciencia/"' in secao
    resposta = painel.post(f"/administracao/alertas/{alerta.pk}/ciencia/", follow=True)
    assert "Ciência registrada." in resposta.content.decode()
    alerta.refresh_from_db()
    assert alerta.resolvido_em is not None
    assert "Chamada ao provedor falhou" not in _secoes(painel.pagina())["Alertas abertos"]
    historico = painel.pagina(url="/administracao/historico/?acao=alerta.ciencia")
    assert "alerta.ciencia" in historico.content.decode()
    assert EntradaAuditoria.objects.filter(acao="alerta.ciencia", autor_id=str(painel.admin.pk))


def _agora() -> Any:
    from apps.nucleo.tempo import agora

    return agora()


def test_consulta_divergente_nao_abre_duas_vezes(painel: Painel, sim: Any) -> None:  # A-10
    from apps.pagamentos.models import ConsultaDoPagamento, PagamentoNoProvedor

    painel.relogio.congelar(T0)
    pagamento = PagamentoNoProvedor.objects.create(
        provedor="simulador",
        ambiente="teste",
        id_externo="pg-div",
        referencia_externa="ref-div",
        valor=D("45.90"),
        situacao="aprovado",
        criado_no_provedor_em=T0 - 3 * H,
        expira_em=T0 + 24 * H,
        aprovado_no_provedor_em=T0 - 2 * H,
    )

    def consultar(quando: Any) -> None:
        ConsultaDoPagamento.objects.create(
            pagamento=pagamento,
            origem="tarefa",
            situacao="aprovado",
            referencia_externa="ref-div",
            valor=D("45.90"),
            consultado_em=quando,
            aplicada=True,
            divergencia="valor",
        )

    consultar(T0)
    concluir_todas(T0)
    _verificar()
    assert AlertaFinanceiro.objects.filter(tipo="consulta_com_divergencia").count() == 1
    painel.relogio.congelar(T0 + 10 * MIN)
    consultar(T0 + 10 * MIN)
    concluir_todas(T0 + 11 * MIN)
    painel.relogio.congelar(T0 + 11 * MIN)
    _verificar()
    assert AlertaFinanceiro.objects.filter(tipo="consulta_com_divergencia").count() == 1


def test_avisos_recusados_em_sequencia(painel: Painel, sim: Any) -> None:  # A-11
    from apps.pagamentos.provedor import NovaCobranca, obter_provedor
    from apps.simulador_pagamentos.controle import corpo_e_cabecalhos
    from apps.simulador_pagamentos.models import AvisoSimulado

    painel.relogio.congelar(T0)
    anonimo = Client()
    for _ in range(5):
        resposta = anonimo.post(
            "/pagamentos/avisos/", data=b'{"x": 1}', content_type="application/json"
        )
        assert resposta.status_code == 401
    concluir_todas(T0)
    _verificar()
    assert AlertaFinanceiro.objects.filter(
        tipo="avisos_recusados_em_sequencia", resolvido_em__isnull=True
    ).exists()
    nova = NovaCobranca("kv", "ref-v", D("45.90"), "Pedido", T0 + 24 * H)
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    sim.aprovar(id_externo, em=T0)
    corpo, cabecalhos = corpo_e_cabecalhos(AvisoSimulado.objects.get(id_externo=id_externo))
    aceito = anonimo.post(
        "/pagamentos/avisos/", data=corpo, content_type="application/json", headers=cabecalhos
    )
    assert aceito.status_code == 200
    _verificar()
    assert not AlertaFinanceiro.objects.filter(
        tipo="avisos_recusados_em_sequencia", resolvido_em__isnull=True
    ).exists()


# --- cenário 4: mensagens falhando --------------------------------------------------------------


def test_email_que_falha_abre_o_alerta_e_o_site_continua(
    painel: Painel, settings: Any
) -> None:  # A-12
    from django.db import transaction

    from apps.financeiro.models import MovimentoFinanceiro
    from apps.notificacoes.emissao import emitir_evento
    from apps.notificacoes.eventos import Evento
    from apps.notificacoes.models import Envio, Notificacao
    from apps.notificacoes.processamento import processar_envios

    painel.relogio.congelar(T0)
    comprador = ContaFactory.create(nome="Compradora")
    settings.EMAIL_BACKEND = "tests.apoio.email_falho.BackendQueFalha"
    movimentos = MovimentoFinanceiro.objects.count()
    with transaction.atomic():
        emitir_evento(
            Evento.PAGAMENTO_CONFIRMADO,
            comprador,
            titulo="Pagamento confirmado",
            corpo="Seu pagamento foi confirmado.",
            chave="e15-07:pagamento",
        )
    instante = T0
    envio = Envio.objects.get(conta=comprador, canal="email")
    for _ in range(20):
        instante += timedelta(days=1)
        painel.relogio.congelar(instante)
        processar_envios()
        envio.refresh_from_db()
        if envio.situacao == "falhou":
            break
    assert envio.situacao == "falhou"
    concluir_todas(instante)
    _verificar()
    assert AlertaFinanceiro.objects.filter(
        tipo="falha_de_mensagem", resolvido_em__isnull=True
    ).exists()
    cliente = Client()
    cliente.force_login(comprador)
    central = _texto(cliente.get("/notificacoes/"))
    assert "Pagamento confirmado" in central
    assert Notificacao.objects.filter(conta=comprador, evento="pagamento_confirmado").count() == 1
    assert MovimentoFinanceiro.objects.count() == movimentos


# --- cenário 5: histórico -----------------------------------------------------------------------


def test_o_historico_reflete_as_acoes_do_administrador(painel: Painel, sim: Any) -> None:  # A-13
    from apps.nucleo.auditoria import EntradaAuditoria
    from apps.pedidos.models import ItemDoPedido
    from apps.pedidos.ocorrencias import saldo_do_item

    a, _x, _y, pf = _ae(painel, sim, liberacao_horas=0, endereco=False)
    receber_tudo(a, pf)
    registrar_endereco(a.admin)
    painel.relogio.congelar(L)
    painel.post(_rota(a, "retirada/liberar"), {"acionamento": str(uuid.uuid4())})
    painel.relogio.congelar(L + timedelta(days=8))
    for item in ItemDoPedido.objects.filter(pedido__abertura__rodada=a.rodada):
        descartar(a.admin, item, saldo_do_item(item))
    esperado = list(
        EntradaAuditoria.objects.filter(autor_id=str(painel.admin.pk))
        .order_by("-momento", "-pk")
        .values_list("acao", flat=True)
    )
    assert "recebimento.registrar" in esperado
    assert "descarte.registrar" in esperado
    lidas: list[str] = []
    pagina = 1
    while True:
        html = painel.pagina(
            url=f"/administracao/historico/?autor={painel.admin.pk}&pagina={pagina}"
        )
        lidas += re.findall(r'<td class="acao">(.*?)</td>', html.content.decode())
        if f"Página {pagina} de" not in _texto(html) or "Próxima" not in _texto(html):
            break
        pagina += 1
    assert lidas == esperado


# --- cenário 6: isolamento ----------------------------------------------------------------------


def test_comprador_e_fornecedor_ficam_de_fora(painel: Painel, sim: Any) -> None:  # A-14
    a, _x, _y, _pf = _ae(painel, sim, liberacao_horas=0)
    _worker_parado(painel)
    alerta = AlertaFinanceiro.objects.filter(tipo="tarefa_atrasada").first()
    assert alerta is not None
    conta_f = ContaFactory.create(nome="Conta de F", fornecedor=True)
    for conta in (a.a, conta_f):
        cliente = Client()
        cliente.force_login(conta)
        assert cliente.get(URL).status_code == 403
        assert cliente.get("/administracao/historico/").status_code == 403
        assert cliente.post(f"/administracao/alertas/{alerta.pk}/ciencia/").status_code == 403
        assert notificacoes(conta) == []
    alerta.refresh_from_db()
    assert alerta.resolvido_em is None


# --- invariantes --------------------------------------------------------------------------------


def _foto() -> tuple[Any, ...]:
    from apps.financeiro.models import MovimentoFinanceiro
    from apps.notificacoes.models import Envio
    from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor
    from apps.rodadas.models import Rodada

    dominio = tuple(
        (m.__name__, tuple(sorted(str(linha) for linha in m.objects.values())))
        for m in (Rodada, Pedido, PagamentoNoProvedor, ChamadaAoProvedor, MovimentoFinanceiro)
    )
    envios = tuple(Envio.objects.order_by("pk").values_list("pk", "situacao", "tentativas"))
    return (*dominio, envios)


def test_as_verificacoes_so_leem(painel: Painel, sim: Any) -> None:  # A-15
    a, _x, _y, _pf = _ae(painel, sim, liberacao_horas=0)
    _chamada_que_falha_de_vez(painel)
    painel.relogio.congelar(INSTANTE + 6 * MIN)
    concluir_todas(INSTANTE, exceto=CINCO_DE_UM_MINUTO)
    antes = _foto()
    ultimo_envio = max(
        (pk for (pk, _s, _t) in antes[-1]),
        default=0,
    )
    _verificar()
    depois = _foto()
    assert depois[:-1] == antes[:-1]
    assert tuple(e for e in depois[-1] if e[0] <= ultimo_envio) == antes[-1]
    _invariante_ok()
    _um_aberto_por_par()
    assert a.rodada.pk


def test_a_retomada_longa_nao_acusa_a_verificacao(painel: Painel) -> None:  # A-16 (E15-R01)
    from apps.financeiro import tarefas as financeiro
    from apps.notificacoes.processamento import processar_envios
    from apps.notificacoes.tarefas import processar_envios_pendentes
    from apps.operacao.catalogo import TAREFAS_MONITORADAS
    from apps.pagamentos.tarefas import processar_chamadas_ao_provedor
    from apps.pedidos import tarefas as pedidos
    from apps.rodadas.tarefas import encerrar_fechamentos_vencidos_agora

    painel.relogio.congelar(INSTANTE)
    admin = painel.admin
    concluir_todas(INSTANTE)
    retomada = INSTANTE + 20 * MIN
    antes = _secoes(painel.pagina(retomada))["Tarefas periódicas"]
    # aos 20 min: as cinco de 1 minuto e a verificação (tolerância de 15 min); as demais em dia
    assert antes.count("Atrasada desde") == 6
    assert "Verificação operacional" in antes
    painel.relogio.congelar(retomada)
    for tarefa in (
        financeiro.registrar_tarifas_pendentes,
        financeiro.verificar_invariante,
        financeiro.conciliar_dias_pendentes,
        processar_envios_pendentes,
        processar_chamadas_ao_provedor,
        pedidos.bloquear_tentativas_vencidas,
        pedidos.reconsultar_pagamentos_da_margem,
        pedidos.autorizar_devolucoes_do_cancelamento,
        pedidos.enviar_pedidos_formais,
        encerrar_fechamentos_vencidos_agora,
    ):
        tarefa(timestamp=0)
    _verificar()
    processar_envios()
    assert not AlertaFinanceiro.objects.filter(tipo="tarefa_atrasada", chave="verificar_operacao")
    assert not AlertaFinanceiro.objects.filter(
        tipo="tarefa_atrasada", resolvido_em__isnull=True
    ).exists()
    assert notificacoes(admin) == []
    depois = _secoes(painel.pagina(retomada))["Tarefas periódicas"]
    assert depois.count("Em dia") == len(TAREFAS_MONITORADAS)
    assert "Atrasada desde" not in depois
