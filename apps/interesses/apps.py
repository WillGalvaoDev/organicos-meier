from django.apps import AppConfig


class InteressesConfig(AppConfig):
    name = "apps.interesses"
    label = "interesses"

    def ready(self) -> None:
        from apps.interesses.receptores import (
            atender_fila_na_abertura,
            atender_fila_no_aumento_de_estoque,
        )
        from apps.rodadas.sinais import estoque_alterado, rodada_aberta

        rodada_aberta.connect(atender_fila_na_abertura, dispatch_uid="interesses.fila.abertura")
        estoque_alterado.connect(
            atender_fila_no_aumento_de_estoque, dispatch_uid="interesses.fila.estoque"
        )
