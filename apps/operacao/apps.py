from django.apps import AppConfig


class OperacaoConfig(AppConfig):
    name = "apps.operacao"
    label = "operacao"

    def ready(self) -> None:
        # registra os tipos de alerta e as verificações (a ordem é a ordem de execução)
        from apps.operacao import atraso_de_tarefa  # noqa: F401
