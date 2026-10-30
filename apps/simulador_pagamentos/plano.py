"""Plano de falhas do simulador (E07-01), guardado no processo: só os testes o usam.

O que o plano guarda não precisa ser visto por outro processo: indisponibilidade, falhas das
próximas chamadas, atraso de consistência e a aprovação que coincide com o cancelamento são
controles dos testes. O estado das cobranças e dos avisos fica no banco.
"""

import threading
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from apps.pagamentos.provedor import ProvedorIndisponivel


@dataclass
class _FalhaProgramada:
    restantes: int
    operacao: str | None
    depois_de_executar: bool


@dataclass(frozen=True)
class Anterior:
    """A situação da cobrança antes da última mudança (o que um provedor atrasado ainda vê)."""

    situacao: str
    aprovado_em: datetime | None


class PlanoDeFalhas:
    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._zerar()

    def _zerar(self) -> None:
        self._indisponivel = False
        self._falha: _FalhaProgramada | None = None
        self._atrasos: dict[int, int] = {}
        self._anteriores: dict[int, Anterior] = {}
        self._aprovacoes_no_cancelamento: dict[int, datetime | None] = {}
        self._tarifas: dict[str, tuple[Decimal, Decimal]] = {}
        self._liberacoes: dict[str, int] = {}
        self._estornos_em_processamento: set[int] = set()
        self._recusas_de_estorno: dict[int, str] = {}
        self._recusas_mas_processa: dict[int, str] = {}
        self._sem_estorno_parcial: set[int] = set()

    def indisponivel(self) -> None:
        with self._trava:
            self._indisponivel = True

    def falhar_proximas(self, n: int, operacao: str | None, depois_de_executar: bool) -> None:
        with self._trava:
            self._falha = _FalhaProgramada(n, operacao, depois_de_executar) if n > 0 else None

    def normalizar(self) -> None:
        with self._trava:
            self._indisponivel = False
            self._falha = None
            self._atrasos.clear()
            self._aprovacoes_no_cancelamento.clear()

    def reiniciar(self) -> None:
        with self._trava:
            self._zerar()

    def consumir(self, operacao: str) -> bool:
        """Aplica o plano a uma chamada da interface.

        Levanta `ProvedorIndisponivel` quando a chamada falha antes de executar. Devolve `True`
        quando a operação deve ser executada e só então falhar.
        """
        with self._trava:
            if self._indisponivel:
                raise ProvedorIndisponivel("provedor simulado indisponível")
            falha = self._falha
            if falha is None or (falha.operacao is not None and falha.operacao != operacao):
                return False
            falha.restantes -= 1
            if falha.restantes <= 0:
                self._falha = None
            if falha.depois_de_executar:
                return True
            raise ProvedorIndisponivel("falha simulada do provedor")

    def registrar_mudanca(self, cobranca_id: int, anterior: Anterior) -> None:
        with self._trava:
            self._anteriores[cobranca_id] = anterior

    def atrasar(self, cobranca_id: int, consultas: int) -> None:
        with self._trava:
            self._atrasos[cobranca_id] = consultas

    def visao_atrasada(self, cobranca_id: int) -> Anterior | None:
        """A situação anterior, enquanto restarem consultas atrasadas para o pagamento."""
        with self._trava:
            restantes = self._atrasos.get(cobranca_id, 0)
            anterior = self._anteriores.get(cobranca_id)
            if restantes <= 0 or anterior is None:
                return None
            self._atrasos[cobranca_id] = restantes - 1
            return anterior

    def definir_tarifa(self, meio: str, percentual: Decimal, fixa: Decimal) -> None:
        with self._trava:
            self._tarifas[meio] = (percentual, fixa)

    def definir_liberacao(self, meio: str, horas: int) -> None:
        with self._trava:
            self._liberacoes[meio] = horas

    def tarifa_do(self, meio: str) -> tuple[Decimal, Decimal]:
        """O percentual (em %) e a parte fixa da tarifa do meio; o padrão é zero."""
        with self._trava:
            return self._tarifas.get(meio, (Decimal(0), Decimal(0)))

    def liberacao_do(self, meio: str) -> int:
        """O prazo de liberação do meio, em horas; o padrão é zero."""
        with self._trava:
            return self._liberacoes.get(meio, 0)

    def estornos_em_processamento(self, cobranca_id: int) -> None:
        with self._trava:
            self._estornos_em_processamento.add(cobranca_id)

    def estorno_em_processamento(self, cobranca_id: int) -> bool:
        with self._trava:
            return cobranca_id in self._estornos_em_processamento

    def recusar_estornos(self, cobranca_id: int, codigo: str) -> None:
        with self._trava:
            self._recusas_de_estorno[cobranca_id] = codigo

    def recusa_de_estorno(self, cobranca_id: int) -> str | None:
        with self._trava:
            return self._recusas_de_estorno.get(cobranca_id)

    def recusar_mas_processar(self, cobranca_id: int, codigo: str) -> None:
        with self._trava:
            self._recusas_mas_processa[cobranca_id] = codigo

    def consumir_recusa_mas_processa(self, cobranca_id: int) -> str | None:
        """O código da recusa programada que o provedor conclui depois, uma só vez."""
        with self._trava:
            return self._recusas_mas_processa.pop(cobranca_id, None)

    def sem_estorno_parcial(self, cobranca_id: int) -> None:
        with self._trava:
            self._sem_estorno_parcial.add(cobranca_id)

    def aceita_estorno_parcial(self, cobranca_id: int) -> bool:
        with self._trava:
            return cobranca_id not in self._sem_estorno_parcial

    def aprovar_no_cancelamento(self, cobranca_id: int, em: datetime | None) -> None:
        with self._trava:
            self._aprovacoes_no_cancelamento[cobranca_id] = em

    def aprovacao_no_cancelamento(self, cobranca_id: int) -> tuple[bool, datetime | None]:
        """Se a cobrança deve ser aprovada no próximo cancelamento, e em que instante."""
        with self._trava:
            if cobranca_id not in self._aprovacoes_no_cancelamento:
                return False, None
            return True, self._aprovacoes_no_cancelamento.pop(cobranca_id)


PLANO = PlanoDeFalhas()
