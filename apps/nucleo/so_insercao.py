"""Registros que só aceitam inserção (E01-04).

Proteção em duas camadas: a aplicação recusa alterar e apagar (este módulo) e o Postgres
recusa `UPDATE` e `DELETE` por trigger, mesmo por SQL direto (`instalar_protecao_so_insercao`).
"""

import re
from typing import Any

from django.db import migrations, models

_NOME_DE_TABELA = re.compile(r"[a-z_][a-z0-9_]*")
_FUNCAO = "nucleo_recusar_alteracao"


class RegistroImutavel(Exception):
    """Tentativa de alterar ou apagar um registro que só aceita inserção."""


class SoInsercaoQuerySet(models.QuerySet):  # type: ignore[type-arg]
    def update(self, **kwargs: Any) -> int:
        raise RegistroImutavel("registro só aceita inserção: update() em lote recusado")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise RegistroImutavel("registro só aceita inserção: delete() em lote recusado")

    def bulk_update(self, *args: Any, **kwargs: Any) -> int:
        raise RegistroImutavel("registro só aceita inserção: bulk_update() recusado")


class RegistroSoInsercao(models.Model):
    """Base abstrata: salvar só funciona para objeto novo; nunca altera nem apaga."""

    objects = SoInsercaoQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise RegistroImutavel(f"{type(self).__name__} só aceita inserção: save() recusado")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise RegistroImutavel(f"{type(self).__name__} só aceita inserção: delete() recusado")


def instalar_protecao_so_insercao(nome_tabela: str) -> migrations.RunSQL:
    """Operação de migração: instala a trigger que recusa `UPDATE` e `DELETE` na tabela."""
    if not _NOME_DE_TABELA.fullmatch(nome_tabela):
        raise ValueError(f"nome de tabela inválido: {nome_tabela!r}")
    trigger = f"{nome_tabela}_so_insercao"
    criar_funcao = f"""
        CREATE OR REPLACE FUNCTION {_FUNCAO}() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'tabela % só aceita inserção', TG_TABLE_NAME
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    criar_trigger = f"""
        CREATE TRIGGER "{trigger}" BEFORE UPDATE OR DELETE ON "{nome_tabela}"
        FOR EACH ROW EXECUTE FUNCTION {_FUNCAO}();
    """
    return migrations.RunSQL(
        sql=[criar_funcao, criar_trigger],
        reverse_sql=[f'DROP TRIGGER IF EXISTS "{trigger}" ON "{nome_tabela}";'],
    )
