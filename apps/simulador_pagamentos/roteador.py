"""Roteador do banco do simulador de pagamentos (E07-R03).

O simulador faz o papel do provedor, que é um serviço externo: o que ele aceitou não se desfaz
com a transação do sistema. Por isso ele usa a conexão `simulador_pagamentos`, que aponta para
o mesmo banco (as tabelas são criadas pelas migrações em `default`), e confirma o que grava na
própria conexão. Não há relação entre os modelos do simulador e os do sistema.
"""

from typing import Any

ALIAS = "simulador_pagamentos"
APP = "simulador_pagamentos"


class RoteadorDoSimulador:
    @staticmethod
    def _do_simulador(model: Any) -> bool:
        return bool(model._meta.app_label == APP)

    def db_for_read(self, model: Any, **hints: Any) -> str | None:
        return ALIAS if self._do_simulador(model) else None

    def db_for_write(self, model: Any, **hints: Any) -> str | None:
        return ALIAS if self._do_simulador(model) else None

    def allow_relation(self, obj1: Any, obj2: Any, **hints: Any) -> bool | None:
        return None

    def allow_migrate(self, db: str, app_label: str, **hints: Any) -> bool | None:
        """As migrações rodam só em `default`; no alias do simulador nenhuma roda."""
        if db == ALIAS:
            return False
        if app_label == APP:
            return db == "default"
        return None
