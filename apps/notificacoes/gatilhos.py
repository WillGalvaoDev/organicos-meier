"""Triggers da notificação (E04-01), no estilo da E02-10.

Nada é apagado. O único `UPDATE` aceito muda `lida_em` de nulo para um instante, sem tocar em
nenhuma outra coluna; marcar de novo, desmarcar ou alterar conteúdo é recusado.
"""

from django.db import migrations

_TABELA = "notificacoes_notificacao"


def instalar_gatilhos() -> migrations.RunSQL:
    funcao_exclusao = """
        CREATE OR REPLACE FUNCTION notificacoes_recusar_exclusao() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'a notificação não pode ser excluída'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    funcao_alteracao = """
        CREATE OR REPLACE FUNCTION notificacoes_so_marcar_como_lida() RETURNS trigger AS $$
        BEGIN
            IF OLD.lida_em IS NULL AND NEW.lida_em IS NOT NULL
               AND OLD.id = NEW.id
               AND OLD.conta_id = NEW.conta_id
               AND OLD.evento = NEW.evento
               AND OLD.titulo = NEW.titulo
               AND OLD.corpo = NEW.corpo
               AND OLD.link IS NOT DISTINCT FROM NEW.link
               AND OLD.chave = NEW.chave
               AND OLD.criada_em = NEW.criada_em THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'a notificação só pode ser marcada como lida, uma única vez'
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
    """
    trigger_exclusao = f"""
        CREATE TRIGGER "{_TABELA}_sem_exclusao" BEFORE DELETE ON "{_TABELA}"
        FOR EACH ROW EXECUTE FUNCTION notificacoes_recusar_exclusao();
    """
    trigger_alteracao = f"""
        CREATE TRIGGER "{_TABELA}_so_marcar_como_lida" BEFORE UPDATE ON "{_TABELA}"
        FOR EACH ROW EXECUTE FUNCTION notificacoes_so_marcar_como_lida();
    """
    return migrations.RunSQL(
        sql=[funcao_exclusao, funcao_alteracao, trigger_exclusao, trigger_alteracao],
        reverse_sql=[
            f'DROP TRIGGER IF EXISTS "{_TABELA}_so_marcar_como_lida" ON "{_TABELA}";',
            f'DROP TRIGGER IF EXISTS "{_TABELA}_sem_exclusao" ON "{_TABELA}";',
        ],
    )
