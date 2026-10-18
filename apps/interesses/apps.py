from django.apps import AppConfig


class InteressesConfig(AppConfig):
    name = "apps.interesses"
    label = "interesses"

    def ready(self) -> None:
        from apps.catalogo.sinais import preco_alterado
        from apps.contas.moderacao import conta_removida, conta_suspensa
        from apps.interesses.avisos import avisar_preco_alterado
        from apps.interesses.receptores import (
            atender_fila_na_abertura,
            atender_fila_no_aumento_de_estoque,
            remover_interesses_na_remocao,
            remover_interesses_na_suspensao,
        )
        from apps.rodadas.sinais import estoque_alterado, rodada_aberta

        rodada_aberta.connect(atender_fila_na_abertura, dispatch_uid="interesses.fila.abertura")
        preco_alterado.connect(avisar_preco_alterado, dispatch_uid="interesses.aviso.preco")
        estoque_alterado.connect(
            atender_fila_no_aumento_de_estoque, dispatch_uid="interesses.fila.estoque"
        )
        conta_suspensa.connect(remover_interesses_na_suspensao, dispatch_uid="interesses.suspensao")
        conta_removida.connect(remover_interesses_na_remocao, dispatch_uid="interesses.remocao")
