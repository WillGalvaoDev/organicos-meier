"""Sequência e triggers da parcela de interesse (E03-04), no estilo da E02-10.

A sequência do banco define a ordem FIFO. A trigger de inserção sempre a atribui (valor
informado é ignorado, inclusive por SQL direto); as demais protegem as colunas imutáveis e
proíbem exclusão (parcela removida fica como histórico).
"""

from django.db import migrations

_TABELA = "interesses_parcela"
_SEQUENCIA = "interesses_parcela_sequencia"


def criar_sequencia() -> migrations.RunSQL:
    return migrations.RunSQL(
        sql=f"CREATE SEQUENCE {_SEQUENCIA};", reverse_sql=f"DROP SEQUENCE IF EXISTS {_SEQUENCIA};"
    )


def instalar_gatilhos() -> migrations.RunSQL:
    funcao_sequencia = f"""
        CREATE OR REPLACE FUNCTION interesses_atribuir_sequencia() RETURNS trigger AS $$
        BEGIN
            NEW.sequencia := nextval('{_SEQUENCIA}');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """
    funcao_imutavel = """
        CREATE OR REPLACE FUNCTION interesses_recusar_troca_de_coluna_imutavel()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'sequência, comprador, produto e quantidade original da parcela '
                'não podem ser alterados'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    funcao_exclusao = """
        CREATE OR REPLACE FUNCTION interesses_recusar_exclusao_de_parcela() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'a parcela não pode ser excluída'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    trigger_sequencia = f"""
        CREATE TRIGGER "{_TABELA}_sequencia_do_banco" BEFORE INSERT ON "{_TABELA}"
        FOR EACH ROW EXECUTE FUNCTION interesses_atribuir_sequencia();
    """
    trigger_imutavel = f"""
        CREATE TRIGGER "{_TABELA}_colunas_imutaveis"
        BEFORE UPDATE OF sequencia, comprador_id, produto_id, quantidade_original
        ON "{_TABELA}"
        FOR EACH ROW WHEN (
            OLD.sequencia IS DISTINCT FROM NEW.sequencia
            OR OLD.comprador_id IS DISTINCT FROM NEW.comprador_id
            OR OLD.produto_id IS DISTINCT FROM NEW.produto_id
            OR OLD.quantidade_original IS DISTINCT FROM NEW.quantidade_original
        )
        EXECUTE FUNCTION interesses_recusar_troca_de_coluna_imutavel();
    """
    trigger_exclusao = f"""
        CREATE TRIGGER "{_TABELA}_sem_exclusao" BEFORE DELETE ON "{_TABELA}"
        FOR EACH ROW EXECUTE FUNCTION interesses_recusar_exclusao_de_parcela();
    """
    return migrations.RunSQL(
        sql=[
            funcao_sequencia,
            funcao_imutavel,
            funcao_exclusao,
            trigger_sequencia,
            trigger_imutavel,
            trigger_exclusao,
        ],
        reverse_sql=[
            f'DROP TRIGGER IF EXISTS "{_TABELA}_sem_exclusao" ON "{_TABELA}";',
            f'DROP TRIGGER IF EXISTS "{_TABELA}_colunas_imutaveis" ON "{_TABELA}";',
            f'DROP TRIGGER IF EXISTS "{_TABELA}_sequencia_do_banco" ON "{_TABELA}";',
        ],
    )
