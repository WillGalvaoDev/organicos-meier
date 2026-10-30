"""E10-06: devolução excepcional confirmada pelo administrador (acceptance A-1 a A-15 e A-17)."""

# A spec fixa `ValueError` sem mensagem nos campos inválidos; o tipo é o contrato.
# ruff: noqa: PT011

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from apps.financeiro.devolucoes import (
    DevolucaoRecusada,
    autorizar_devolucao,
    confirmar_devolucao_excepcional,
    tentar_devolucao_de_novo,
)
from apps.financeiro.livro import (
    EXTERIOR,
    MovimentoProibido,
    Transferencia,
    conta,
    conta_da_obrigacao,
    lancar,
    saldo,
    saldo_total_esperado,
)
from apps.financeiro.models import (
    AlertaFinanceiro,
    ConfirmacaoDeDevolucaoExcepcional,
    Destinacao,
    HistoricoDaDevolucao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
    TransferenciaFinanceira,
)
from apps.financeiro.obrigacoes import _liquidado, liquidar_obrigacao_fora_do_provedor
from apps.financeiro.reserva import designar_reserva
from apps.nucleo.models import EntradaAuditoria
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pagamentos.provedor import NovaCobranca, obter_provedor
from apps.pedidos.models import DestinoDoPagamento
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.devolucoes import (
    Arranjo,
    arranjo_da_devolucao,
    levar_a_elegivel,
    parcela_de_fabrica,
)
from tests.apoio.financeiro import chave_nova, mover
from tests.apoio.pedidos import T0, sincronizar
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
PDF = b"%PDF-1.4\n%conteudo do comprovante\n"


@pytest.fixture(autouse=True)
def midia(settings: Any, tmp_path: Path) -> Path:
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def a(relogio: RelogioControlado, simulador_pagamentos: Any) -> Arranjo:
    return arranjo_da_devolucao(simulador_pagamentos, relogio)


def _arquivos(midia: Path) -> list[Path]:
    return [p for p in (midia / "comprovantes").glob("*") if p.is_file()]


def _pdf(conteudo: bytes = PDF, nome: str = "comprovante.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, conteudo, content_type="application/pdf")


def _confirmar(a: Arranjo, parcela: ParcelaDeDevolucao, **campos: Any) -> Any:
    argumentos: dict[str, Any] = {
        "autor": a.admin,
        "meio": "pix",
        "identificacao": "E2E-123",
        "justificativa": "Pix feito direto ao comprador",
        "comprovante": _pdf(),
        **campos,
    }
    return confirmar_devolucao_excepcional(parcela, **argumentos)


def _contagens() -> tuple[int, int, int]:
    return (
        ConfirmacaoDeDevolucaoExcepcional.objects.count(),
        MovimentoFinanceiro.objects.filter(tipo="devolucao_excepcional").count(),
        HistoricoDaDevolucao.objects.count(),
    )


def test_confirmacao_da_parcela_elegivel(a: Arranjo, midia: Path) -> None:  # A-1
    parcela = levar_a_elegivel(a)
    antes = saldo_total_esperado()
    confirmacao = _confirmar(a, parcela)
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida_fora_da_plataforma"
    assert (confirmacao.pedido_id, confirmacao.comprador_id) == (a.pedido.pk, a.comprador.pk)
    assert (confirmacao.valor, confirmacao.meio, confirmacao.identificacao) == (
        D("31.25"),
        "pix",
        "E2E-123",
    )
    assert confirmacao.autor_id == a.admin.pk
    assert confirmacao.comprovante_tipo == "application/pdf"
    assert confirmacao.comprovante_tamanho == len(PDF)
    assert confirmacao.comprovante_nome == "comprovante.pdf"
    (arquivo,) = _arquivos(midia)
    assert "comprovante" not in arquivo.name
    assert arquivo.read_bytes() == PDF
    (movimento,) = MovimentoFinanceiro.objects.filter(tipo="devolucao_excepcional")
    (transferencia,) = TransferenciaFinanceira.objects.filter(movimento=movimento)
    assert (transferencia.de, transferencia.valor) == (conta_da_obrigacao(a.o1), D("31.25"))
    assert transferencia.para == conta(Destinacao.RESERVA)
    assert _liquidado(conta_da_obrigacao(a.o1)) == D("31.25")
    assert not AlertaFinanceiro.objects.filter(
        tipo="devolucao_elegivel_excepcional", resolvido_em=None
    )
    assert len(EstornoSimulado.objects.all()) == 0
    assert saldo_total_esperado() == antes


def test_antes_da_confirmacao_a_obrigacao_continua_integral(a: Arranjo) -> None:  # A-2
    levar_a_elegivel(a)
    assert a.o1.devido - _liquidado(conta_da_obrigacao(a.o1)) == D("31.25")


@pytest.mark.parametrize("situacao", ["solicitada", "falha_temporaria", "em_processamento"])
def test_devolucao_pendente_na_plataforma_bloqueia(
    a: Arranjo, midia: Path, situacao: str
) -> None:  # A-3
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    ParcelaDeDevolucao.objects.filter(pk=parcela.pk).update(situacao=situacao)
    parcela.refresh_from_db()
    antes = _contagens()
    with pytest.raises(DevolucaoRecusada, match="há devolução pendente na plataforma"):
        _confirmar(a, parcela)
    assert _contagens() == antes
    assert _arquivos(midia) == []


def test_falha_definitiva_ainda_nao_comprovada_bloqueia(a: Arranjo, midia: Path) -> None:  # A-3
    a.sim.recusar_estornos(a.pagamento.id_externo, "prazo_vencido")
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    parcela.refresh_from_db()
    assert parcela.situacao == "falha_definitiva"
    with pytest.raises(DevolucaoRecusada, match="há devolução pendente na plataforma"):
        _confirmar(a, parcela)
    assert _arquivos(midia) == []


def test_sem_parcela_e_parcela_concluida_sao_recusadas(a: Arranjo) -> None:  # A-3
    sem_parcela = ParcelaDeDevolucao(obrigacao=a.o1)
    with pytest.raises(DevolucaoRecusada, match="não foi tentada"):
        _confirmar(a, sem_parcela)
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    with pytest.raises(DevolucaoRecusada, match="já devolvida pela plataforma"):
        _confirmar(a, parcela)


def test_nao_vale_duas_vezes(a: Arranjo, midia: Path) -> None:  # A-4
    parcela = levar_a_elegivel(a)
    _confirmar(a, parcela)
    antes = _contagens()
    with pytest.raises(DevolucaoRecusada, match="já confirmada"):
        _confirmar(a, parcela)
    assert _contagens() == antes
    assert len(_arquivos(midia)) == 1


def test_depois_da_confirmacao_o_provedor_nao_e_mais_chamado(a: Arranjo) -> None:  # A-5
    parcela = levar_a_elegivel(a)
    _confirmar(a, parcela)
    parcela.refresh_from_db()
    with pytest.raises(DevolucaoRecusada):
        tentar_devolucao_de_novo(parcela, autor=a.admin)
    assert autorizar_devolucao(a.o1, autor=a.admin).pk == parcela.pk
    assert not ChamadaAoProvedor.objects.filter(operacao="estornar", situacao="pendente")
    ChamadaAoProvedor.objects.create(
        operacao="estornar",
        alvo=f"parcela:{parcela.pk}",
        chave_idempotencia="fabrica-estornar",
        provedor="simulador",
        ambiente="testes",
    )
    a.sim.normalizar()
    processar_chamadas()
    chamada = ChamadaAoProvedor.objects.get(chave_idempotencia="fabrica-estornar")
    assert (chamada.situacao, chamada.ultimo_erro) == ("falhou", "parcela_encerrada")
    assert EstornoSimulado.objects.count() == 0


def test_estorno_em_processamento_no_provedor_recusa_e_agenda_a_verificacao(
    a: Arranjo, midia: Path
) -> None:  # A-6
    a.sim.recusar_mas_processar(a.pagamento.id_externo, "meio_nao_permite_estorno")
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"
    # o provedor passa a mostrar o estorno que ainda processa
    assert EstornoSimulado.objects.filter(situacao="em_processamento").update(visivel=True) == 1
    antes = _contagens()
    with pytest.raises(DevolucaoRecusada, match="em processamento ou concluída no provedor"):
        _confirmar(a, parcela)
    assert _contagens() == antes
    assert _arquivos(midia) == []
    assert ChamadaAoProvedor.objects.filter(
        operacao="verificar_estornos", alvo=f"parcela:{parcela.pk}", situacao="pendente"
    ).exists()


def test_provedor_fora_do_ar_bloqueia_a_confirmacao(a: Arranjo, midia: Path) -> None:  # A-7
    parcela = levar_a_elegivel(a)
    a.sim.indisponivel()
    antes = _contagens()
    with pytest.raises(ConsultaAoProvedorFalhou):
        _confirmar(a, parcela)
    assert _contagens() == antes
    assert _arquivos(midia) == []


def test_so_o_administrador_confirma(a: Arranjo, midia: Path) -> None:  # A-8
    parcela = levar_a_elegivel(a)
    fornecedor = ContaFactory.create(fornecedor=True)
    for autor in (a.comprador, fornecedor):
        with pytest.raises(PermissionDenied):
            _confirmar(a, parcela, autor=autor)
    assert _contagens()[0] == 0
    assert _arquivos(midia) == []


def _gif() -> SimpleUploadedFile:
    return SimpleUploadedFile("c.gif", b"GIF89a....", content_type="image/gif")


@pytest.mark.parametrize(
    "campos",
    [
        {"meio": ""},
        {"meio": "dinheiro"},
        {"identificacao": ""},
        {"identificacao": "x" * 101},
        {"identificacao": "ab\x00c"},
        {"justificativa": "  "},
        {"justificativa": "x" * 1001},
        {"comprovante": None},
        {
            "comprovante": SimpleUploadedFile(
                "c.pdf", b"isto e texto", content_type="application/pdf"
            )
        },
        {"comprovante": SimpleUploadedFile("c.pdf", b"%PDF-" + b"0" * (10 * 1024 * 1024 - 4))},
        {"comprovante": _gif()},
    ],
)
def test_campos_invalidos_nao_gravam_nada(
    a: Arranjo, midia: Path, campos: dict[str, Any]
) -> None:  # A-9
    parcela = levar_a_elegivel(a)
    with pytest.raises(ValueError):
        _confirmar(a, parcela, **campos)
    assert _contagens()[0] == 0
    assert _arquivos(midia) == []


def test_formatos_aceitos_sao_reconhecidos_pelo_conteudo(a: Arranjo) -> None:  # A-9
    parcela = levar_a_elegivel(a)
    png = SimpleUploadedFile("qualquer.bin", b"\x89PNG\r\n\x1a\n....")
    confirmacao = _confirmar(a, parcela, comprovante=png)
    assert confirmacao.comprovante_tipo == "image/png"


def test_obrigacao_sem_cobertura_exige_cobrir_antes(a: Arranjo) -> None:  # A-10
    # Depois da E10-R03 a designação de uma obrigação com parcela não final não se desfaz; a
    # parcela elegível sem cobertura vem de fábrica (a asserção é a mesma da versão anterior).
    parcela = parcela_de_fabrica(a, "elegivel_excepcional", "10.00")
    obrigacao = parcela.obrigacao
    with pytest.raises(DevolucaoRecusada, match="cobrir"):
        _confirmar(a, parcela)
    with transaction.atomic():
        designar_reserva(a.admin, obrigacao, obrigacao.devido, "cobertura de novo")
    reserva = conta(Destinacao.RESERVA)
    antes = saldo(reserva)
    _confirmar(a, parcela)
    assert saldo(reserva) == antes
    assert _liquidado(conta_da_obrigacao(obrigacao)) == obrigacao.devido


def test_invariante_e_total_do_livro_nao_mudam(a: Arranjo) -> None:  # A-11
    parcela = levar_a_elegivel(a)
    total = saldo_total_esperado()
    _confirmar(a, parcela)
    assert saldo_total_esperado() == total
    assert (
        AlertaFinanceiro.objects.filter(tipo="invariante_violado", resolvido_em=None).count() == 0
    )


def test_duplicidade_confirmada_resolve_o_alerta(a: Arranjo) -> None:  # A-12
    nova = NovaCobranca(
        "k-dup", a.pedido.referencia_externa, a.pedido.total, "Dup", T0 + timedelta(hours=24)
    )
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    a.sim.aprovar(id_externo)
    sincronizar(id_externo)
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=id_externo)
    obrigacao = ObrigacaoComComprador.objects.get(
        origem_tipo="pedidos.destinodopagamento", origem_id=str(destino.pk)
    )
    parcela = levar_a_elegivel(a, obrigacao, destino.pagamento)
    assert AlertaFinanceiro.objects.filter(tipo="duplicidade", resolvido_em=None).exists()
    confirmacao = _confirmar(a, parcela)
    assert (confirmacao.pedido_id, confirmacao.comprador_id) == (a.pedido.pk, a.comprador.pk)
    assert not AlertaFinanceiro.objects.filter(tipo="duplicidade", resolvido_em=None).exists()


def test_pagamento_sem_pedido_confirma_sem_pedido_nem_comprador(a: Arranjo) -> None:  # A-13
    nova = NovaCobranca(
        "k-sp", "ref-desconhecida", D("40.00"), "Sem pedido", T0 + timedelta(hours=24)
    )
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    a.sim.aprovar(id_externo)
    sincronizar(id_externo)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=None, integral=D("40.00"))
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=id_externo)
    parcela = levar_a_elegivel(a, obrigacao, destino.pagamento)
    confirmacao = _confirmar(a, parcela)
    assert (confirmacao.pedido_id, confirmacao.comprador_id) == (None, None)
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida_fora_da_plataforma"
    assert MovimentoFinanceiro.objects.filter(tipo="devolucao_excepcional").count() == 1


def test_f16_so_existe_para_o_tipo_certo_e_entre_as_contas_certas(a: Arranjo) -> None:  # A-14
    destino = conta_da_obrigacao(a.o1)
    reserva = conta(Destinacao.RESERVA)
    mover("entrada_para_devolucao", EXTERIOR, destino, "5.00", origem=a.o1)
    for tipo in ("devolucao", "financiamento_de_obrigacao"):
        with pytest.raises(MovimentoProibido), transaction.atomic():
            mover(tipo, destino, reserva, "1.00", origem=a.o1)
    receita = conta(Destinacao.RECEITA_SERVICO, rodada=a.pedido.abertura.rodada_id)
    for origem in (receita,):
        with pytest.raises(MovimentoProibido), transaction.atomic():
            mover("devolucao_excepcional", origem, reserva, "1.00")
    with pytest.raises(MovimentoProibido), transaction.atomic():
        lancar(
            tipo="devolucao_excepcional",
            transferencias=[Transferencia(destino, EXTERIOR, D("1.00"))],
            autor=a.admin,
            justificativa="teste",
            origem=a.o1,
            chave=chave_nova(),
        )


def test_liquidacao_fora_do_provedor_e_idempotente(a: Arranjo) -> None:  # A-15
    parcela = levar_a_elegivel(a)
    _confirmar(a, parcela)
    (movimento,) = MovimentoFinanceiro.objects.filter(tipo="devolucao_excepcional")
    with transaction.atomic():
        de_novo = liquidar_obrigacao_fora_do_provedor(
            a.o1, D("31.25"), referencia=f"excepcional:{parcela.pk}"
        )
    assert de_novo.pk == movimento.pk
    assert MovimentoFinanceiro.objects.filter(tipo="devolucao_excepcional").count() == 1


def test_auditoria_e_historico_da_confirmacao(a: Arranjo) -> None:  # A-17
    parcela = levar_a_elegivel(a)
    confirmacao = _confirmar(a, parcela)
    entrada = EntradaAuditoria.objects.get(acao="financeiro.devolucao_excepcional_confirmada")
    assert entrada.autor_id == str(a.admin.pk)
    assert entrada.objeto_id == str(confirmacao.pk) or entrada.objeto_id == str(parcela.pk)
    ultimo = parcela.historico.order_by("pk").last()
    assert ultimo is not None
    assert ultimo.situacao == "concluida_fora_da_plataforma"
    assert ultimo.autor_id == a.admin.pk
