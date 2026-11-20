"""Regra 2-K da E16-07: o `caminho` só com funções e métodos (A-70 e A-71), `rota:` com o texto
igual e view de dependência, e `banco:` pelo catálogo do banco migrado (A-72)."""

from typing import Any

import pytest

from tests.rastreabilidade import auditoria, matriz
from tests.rastreabilidade.catalogo import nomes_do_banco
from tests.rastreabilidade.conferencia import conferir_auditoria
from tests.rastreabilidade.test_matriz import REAL, _auditoria_de, _completa

OCORRENCIA = "apps.pedidos.ocorrencias.registrar_ocorrencia"
CHAVE = (1, "afirmação do cenário 1", REAL)


def _problemas(caminho: str, nomes: frozenset[str]) -> list[str]:
    cenarios, tecnicos = _completa()
    base = _auditoria_de(cenarios, tecnicos)
    troca = {**base, CHAVE: {**base[CHAVE], "caminho": caminho}}
    return conferir_auditoria(troca, cenarios, tecnicos, nomes)


NEGATIVOS_DE_FUNCAO = [
    ("apps.pagamentos.provedor.NovaCobranca", "não é função nem método"),
    ("apps.pedidos.calculo.ItemACobrar", "não é função nem método"),
    ("apps.contas.adaptadores.AdaptadorContaSocial", "não é função nem método"),
    ("apps.pagamentos.models.SITUACOES", "não é função nem método"),
    ("apps.pagamentos.provedor.NovaCobranca.chave_idempotencia", "não é função nem método"),
    ("apps.pedidos.models.ItemDoPedido.save", "não é função nem método"),  # herdado
    (
        f"{OCORRENCIA}; {OCORRENCIA}",
        "repetido",
    ),
    ("rota:GET /", "rota"),
    ("rota:POST /ent", "rota"),
    ("rota:POST /entrar", "rota"),
    ("rota:POST /entrar/link/", "view"),
    ("rota:POST /teste/retorno-google/", "rota"),
    ("rota:GET /administracao/financeiro/", "view"),
]

POSITIVOS_DE_FUNCAO = [
    "apps.contas.adaptadores.AdaptadorContaSocial.pre_social_login",
    "apps.pedidos.ocorrencias.registrar_ocorrencia",
    "config.observabilidade.limpar_evento",
    "rota:POST /entrar/",
    "rota:POST /sair/",
    "rota:POST /recuperar-acesso/",
]


@pytest.mark.parametrize(("caminho", "motivo"), NEGATIVOS_DE_FUNCAO)
def test_a_conferencia_estrita_acusa_os_treze_casos(caminho: str, motivo: str) -> None:  # A-70
    problemas = _problemas(caminho, frozenset())
    assert problemas, caminho
    assert all("caminho inválido" in p and REAL in p for p in problemas), problemas
    assert any(motivo in p for p in problemas), (caminho, problemas)


@pytest.mark.parametrize("caminho", POSITIVOS_DE_FUNCAO)
def test_a_conferencia_estrita_aceita_funcoes_e_rotas_de_dependencia(  # A-71
    caminho: str,
) -> None:
    assert _problemas(caminho, frozenset()) == []


def test_a_auditoria_entregue_passa_pela_conferencia_estrita(nomes_banco: frozenset[str]) -> None:
    assert (
        conferir_auditoria(auditoria.AUDITORIA, matriz.CENARIOS, matriz.TECNICOS, nomes_banco) == []
    )  # A-71


@pytest.mark.django_db
def test_o_catalogo_traz_so_restricao_indice_unico_e_trigger_nao_interna(  # A-72
    django_db_blocker: Any,
) -> None:
    from django.db import connection

    nomes = nomes_do_banco()
    for esperado in (
        "pedidos_itemdopedido_so_insercao",
        "contas_conta_papel_imutavel",
        "conta_email_unico",
    ):
        assert esperado in nomes
    with connection.cursor() as cursor:
        cursor.execute("SELECT tgname FROM pg_trigger WHERE tgisinternal LIMIT 1")
        interna = cursor.fetchone()
    assert interna is not None
    assert interna[0] not in nomes
    assert "pedidos_itemdopedido" not in nomes  # tabela
    assert "nucleo_recusar_alteracao" not in nomes  # função


@pytest.mark.django_db
def test_banco_so_vale_pelo_nome_exato_do_catalogo(nomes_banco: frozenset[str]) -> None:  # A-72
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT tgname FROM pg_trigger WHERE tgisinternal LIMIT 1")
        interna = cursor.fetchone()[0]
    for recusado in (
        "banco:pedidos_itemdopedido",
        "banco:papel_imutavel",
        "banco:nucleo_recusar_alteracao",
        f"banco:{interna}",
        "banco:nome_que_nao_existe",
    ):
        problemas = _problemas(recusado, nomes_banco)
        assert problemas, recusado
        assert all("caminho inválido" in p for p in problemas), recusado
    for aceito in (
        "banco:pedidos_itemdopedido_so_insercao",
        "banco:contas_conta_papel_imutavel",
        "banco:conta_email_unico",
    ):
        assert _problemas(aceito, nomes_banco) == [], aceito


def test_a_conferencia_exige_os_nomes_do_banco_como_argumento() -> None:  # A-72
    cenarios, tecnicos = _completa()
    base = _auditoria_de(cenarios, tecnicos)
    with pytest.raises(TypeError):
        conferir_auditoria(base, cenarios, tecnicos)  # type: ignore[call-arg]
