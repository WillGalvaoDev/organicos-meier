from django.apps import AppConfig


class PedidosConfig(AppConfig):
    name = "apps.pedidos"
    label = "pedidos"

    def ready(self) -> None:
        from apps.pedidos.operacoes import registrar_operacoes

        registrar_operacoes()
