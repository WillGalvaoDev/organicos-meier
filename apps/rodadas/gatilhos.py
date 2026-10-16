"""Triggers do estoque da rodada (E03-05), no estilo da E02-10.

O produto de um estoque tem de ser do mesmo fornecedor da rodada (isolamento entre
fornecedores), `rodada_id` e `produto_id` nunca mudam e nenhum estoque é excluído.
"""

from django.db import migrations

_TABELA = "rodadas_estoque"


def instalar_gatilhos_do_estoque() -> migrations.RunSQL:
    funcao_fornecedor = """
        CREATE OR REPLACE FUNCTION rodadas_exigir_mesmo_fornecedor() RETURNS trigger AS $$
        BEGIN
            IF (SELECT fornecedor_id FROM rodadas_rodada WHERE id = NEW.rodada_id)
               IS DISTINCT FROM
               (SELECT fornecedor_id FROM catalogo_produto WHERE id = NEW.produto_id) THEN
                RAISE EXCEPTION 'o produto é de outro fornecedor que o da rodada'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """
    funcao_imutavel = """
        CREATE OR REPLACE FUNCTION rodadas_recusar_troca_de_rodada_ou_produto()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'a rodada e o produto do estoque não podem ser alterados'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    funcao_exclusao = """
        CREATE OR REPLACE FUNCTION rodadas_recusar_exclusao_de_estoque() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'o estoque da rodada não pode ser excluído'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    trigger_fornecedor = f"""
        CREATE TRIGGER "{_TABELA}_mesmo_fornecedor" BEFORE INSERT OR UPDATE ON "{_TABELA}"
        FOR EACH ROW EXECUTE FUNCTION rodadas_exigir_mesmo_fornecedor();
    """
    trigger_imutavel = f"""
        CREATE TRIGGER "{_TABELA}_rodada_produto_imutaveis"
        BEFORE UPDATE OF rodada_id, produto_id ON "{_TABELA}"
        FOR EACH ROW WHEN (
            OLD.rodada_id IS DISTINCT FROM NEW.rodada_id
            OR OLD.produto_id IS DISTINCT FROM NEW.produto_id
        )
        EXECUTE FUNCTION rodadas_recusar_troca_de_rodada_ou_produto();
    """
    trigger_exclusao = f"""
        CREATE TRIGGER "{_TABELA}_sem_exclusao" BEFORE DELETE ON "{_TABELA}"
        FOR EACH ROW EXECUTE FUNCTION rodadas_recusar_exclusao_de_estoque();
    """
    return migrations.RunSQL(
        sql=[
            funcao_fornecedor,
            funcao_imutavel,
            funcao_exclusao,
            trigger_fornecedor,
            trigger_imutavel,
            trigger_exclusao,
        ],
        reverse_sql=[
            f'DROP TRIGGER IF EXISTS "{_TABELA}_sem_exclusao" ON "{_TABELA}";',
            f'DROP TRIGGER IF EXISTS "{_TABELA}_rodada_produto_imutaveis" ON "{_TABELA}";',
            f'DROP TRIGGER IF EXISTS "{_TABELA}_mesmo_fornecedor" ON "{_TABELA}";',
        ],
    )
