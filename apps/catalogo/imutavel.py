"""Triggers que protegem o produto no Postgres (E03-03), no estilo da E02-10.

`fornecedor_id` e `unidade` nunca mudam e o produto nunca é excluído: quantidades de parcelas,
pedidos e snapshots dependem da unidade e do histórico do produto.
"""

from django.db import migrations

_TABELA = "catalogo_produto"


def instalar_produto_imutavel() -> migrations.RunSQL:
    funcao_troca = """
        CREATE OR REPLACE FUNCTION catalogo_recusar_troca_de_unidade_ou_fornecedor()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'a unidade e o fornecedor do produto não podem ser alterados'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    funcao_exclusao = """
        CREATE OR REPLACE FUNCTION catalogo_recusar_exclusao_de_produto()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'o produto não pode ser excluído'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    trigger_troca = f"""
        CREATE TRIGGER "{_TABELA}_unidade_fornecedor_imutaveis"
        BEFORE UPDATE OF unidade, fornecedor_id ON "{_TABELA}"
        FOR EACH ROW WHEN (
            OLD.unidade IS DISTINCT FROM NEW.unidade
            OR OLD.fornecedor_id IS DISTINCT FROM NEW.fornecedor_id
        )
        EXECUTE FUNCTION catalogo_recusar_troca_de_unidade_ou_fornecedor();
    """
    trigger_exclusao = f"""
        CREATE TRIGGER "{_TABELA}_sem_exclusao" BEFORE DELETE ON "{_TABELA}"
        FOR EACH ROW EXECUTE FUNCTION catalogo_recusar_exclusao_de_produto();
    """
    return migrations.RunSQL(
        sql=[funcao_troca, funcao_exclusao, trigger_troca, trigger_exclusao],
        reverse_sql=[
            f'DROP TRIGGER IF EXISTS "{_TABELA}_sem_exclusao" ON "{_TABELA}";',
            f'DROP TRIGGER IF EXISTS "{_TABELA}_unidade_fornecedor_imutaveis" ON "{_TABELA}";',
        ],
    )
