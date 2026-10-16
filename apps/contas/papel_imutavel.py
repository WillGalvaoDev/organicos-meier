"""Operação de migração que torna o papel da conta imutável no Postgres (E02-10, cenário 62)."""

from django.db import migrations

_FUNCAO = "contas_recusar_troca_de_papel"


def instalar_papel_imutavel(nome_tabela: str = "contas_conta") -> migrations.RunSQL:
    """Instala a trigger que recusa qualquer `UPDATE` que mude a coluna `papel`.

    A condição `OLD.papel IS DISTINCT FROM NEW.papel` deixa passar as gravações comuns do ORM,
    que reenviam a coluna com o mesmo valor.
    """
    trigger = f"{nome_tabela}_papel_imutavel"
    criar_funcao = f"""
        CREATE OR REPLACE FUNCTION {_FUNCAO}() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'o papel da conta não pode ser alterado'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    criar_trigger = f"""
        CREATE TRIGGER "{trigger}" BEFORE UPDATE OF papel ON "{nome_tabela}"
        FOR EACH ROW WHEN (OLD.papel IS DISTINCT FROM NEW.papel)
        EXECUTE FUNCTION {_FUNCAO}();
    """
    return migrations.RunSQL(
        sql=[criar_funcao, criar_trigger],
        reverse_sql=[f'DROP TRIGGER IF EXISTS "{trigger}" ON "{nome_tabela}";'],
    )
