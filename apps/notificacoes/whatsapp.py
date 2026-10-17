"""Canal de WhatsApp atrás de uma interface substituível (E04-04).

Na fase 1 só existe o simulador determinístico, que nunca fala com a Meta; o canal real chega na
fase 3, com especificação própria. `CANAL_WHATSAPP` vale `desligado` ou `simulado`, e a produção
recusa o simulador (config/settings/prod.py). Nada aqui registra número nem texto em log.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from django.conf import settings

from apps.nucleo.tempo import agora

logger = logging.getLogger(__name__)


class FalhaNoCanalExterno(Exception):
    """O canal externo recusou ou não aceitou a mensagem."""


class CanalWhatsApp(Protocol):
    """`envio_id` só serve para o log do simulador, que nunca registra número nem texto."""

    def enviar(self, numero_e164: str, texto: str, *, envio_id: int | None = None) -> None: ...


@dataclass(frozen=True)
class MensagemAceita:
    numero: str
    texto: str
    instante: datetime


class CanalWhatsAppDesligado:
    """Canal desligado: nenhum envio é criado, então na prática não é chamado."""

    def enviar(self, numero_e164: str, texto: str, *, envio_id: int | None = None) -> None:
        raise FalhaNoCanalExterno("canal desligado")


@dataclass
class CanalWhatsAppSimulado:
    """Simulador determinístico: sem aleatoriedade e sem rede.

    Guarda no processo as mensagens aceitas e um plano de falhas que os testes configuram.
    """

    mensagens: list[MensagemAceita] = field(default_factory=list)
    _sempre: bool = False
    _proximas: int = 0
    _trava: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def enviar(self, numero_e164: str, texto: str, *, envio_id: int | None = None) -> None:
        with self._trava:
            if self._sempre or self._proximas > 0:
                if not self._sempre:
                    self._proximas -= 1
                raise FalhaNoCanalExterno("falha simulada")
            self.mensagens.append(MensagemAceita(numero_e164, texto, agora()))
        logger.info("WhatsApp simulado: envio %s aceito", envio_id)

    def falhar_sempre(self) -> None:
        with self._trava:
            self._sempre = True

    def falhar_proximas(self, n: int) -> None:
        with self._trava:
            self._sempre = False
            self._proximas = n

    def normalizar(self) -> None:
        with self._trava:
            self._sempre = False
            self._proximas = 0

    def reiniciar(self) -> None:
        self.normalizar()
        with self._trava:
            self.mensagens.clear()


SIMULADOR = CanalWhatsAppSimulado()
_DESLIGADO = CanalWhatsAppDesligado()


def obter_canal_whatsapp() -> CanalWhatsApp:
    """A implementação conforme `CANAL_WHATSAPP`; quem envia nunca importa uma delas."""
    return SIMULADOR if settings.CANAL_WHATSAPP == "simulado" else _DESLIGADO
