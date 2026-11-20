"""Os nomes reais do banco migrado, para a forma `banco:` do `caminho` (regra 2-K, R05-J7).

Os nomes das triggers são montados em tempo de migração (`f"{tabela}_so_insercao"`), então a
presença do texto nos `.py` não prova o nome. Vale só o nome exato de uma restrição, de um
índice único ou de uma trigger não interna do catálogo do Postgres.
"""

from django.db import connection

_CONSULTA = """
    SELECT conname FROM pg_constraint
    UNION
    SELECT c.relname FROM pg_class c JOIN pg_index i ON i.indexrelid = c.oid WHERE i.indisunique
    UNION
    SELECT tgname FROM pg_trigger WHERE NOT tgisinternal
"""


def nomes_do_banco() -> frozenset[str]:
    with connection.cursor() as cursor:
        cursor.execute(_CONSULTA)
        return frozenset(str(linha[0]) for linha in cursor.fetchall())
