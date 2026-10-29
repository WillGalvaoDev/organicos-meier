from django.apps import AppConfig


class FinanceiroConfig(AppConfig):
    name = "apps.financeiro"
    label = "financeiro"

    def ready(self) -> None:
        from apps.financeiro.receptores import registrar_no_livro_o_destino_decidido
        from apps.pedidos.sinais import destino_do_pagamento_decidido

        destino_do_pagamento_decidido.connect(
            registrar_no_livro_o_destino_decidido, dispatch_uid="financeiro.entradas"
        )
