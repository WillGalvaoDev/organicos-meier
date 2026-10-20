from django.apps import AppConfig


class PedidosConfig(AppConfig):
    name = "apps.pedidos"
    label = "pedidos"

    def ready(self) -> None:
        from apps.pagamentos.sinais import situacao_do_pagamento_mudou
        from apps.pedidos.operacoes import registrar_operacoes
        from apps.pedidos.receptores import decidir_destino_do_pagamento_aprovado

        registrar_operacoes()
        situacao_do_pagamento_mudou.connect(
            decidir_destino_do_pagamento_aprovado, dispatch_uid="pedidos.quitacao"
        )
