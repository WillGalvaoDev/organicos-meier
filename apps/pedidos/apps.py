from django.apps import AppConfig


class PedidosConfig(AppConfig):
    name = "apps.pedidos"
    label = "pedidos"

    def ready(self) -> None:
        from apps.contas.moderacao import conta_removida, conta_suspensa
        from apps.pagamentos.sinais import situacao_do_pagamento_mudou
        from apps.pedidos.operacoes import registrar_operacoes
        from apps.pedidos.receptores import (
            cancelar_pedidos_na_remocao,
            cancelar_pedidos_na_suspensao,
            decidir_destino_do_pagamento_aprovado,
        )

        registrar_operacoes()
        situacao_do_pagamento_mudou.connect(
            decidir_destino_do_pagamento_aprovado, dispatch_uid="pedidos.quitacao"
        )
        # depois dos receptores de interesses (E05-07): `apps.interesses` vem antes na lista
        conta_suspensa.connect(cancelar_pedidos_na_suspensao, dispatch_uid="pedidos.suspensao")
        conta_removida.connect(cancelar_pedidos_na_remocao, dispatch_uid="pedidos.remocao")
