# E16-04 — Registro do implementador

Agente 2.

## Red (observado antes do código de produção)

- `uv run pytest -q tests/tecnicos/test_backup_externo.py`: erro de coleta, `ImportError: cannot import name 'BackupExterno' from 'apps.operacao.models'` (modelo, rotina, tarefa e comando não existiam; cobre A-1 a A-12 e A-14).
- `uv run pytest -q tests/tecnicos/test_backup_externo_ferramentas.py tests/ambiente/test_homologacao.py tests/tecnicos/test_painel_administrativo.py`: **7 failed, 51 passed, 1 skipped**. Falharam A-13 (cinco casos: as quatro variáveis não eram exigidas e a chave `age1` não era validada) e A-16/A-17 (sem a linha do backup no painel). O A-15 **pulou** na máquina de desenvolvimento (Windows, sem `pg_dump`, `age` nem `pg_restore`).

## Green

- `BackupExterno` (`apps/operacao/models.py`, migração `0002`): só inserção por trigger, chave única, `tamanho_bytes > 0` e `sha256` com 64 hexadecimais por restrição do banco.
- `apps/operacao/backup.py`: `fazer_backup_externo(instante)` em quatro etapas (`pg_dump` custom, `age --encrypt --recipient`, envio com `sha256` em metadado e `head_object` conferindo o tamanho); `BackupFalhou(etapa, causa)` com `despejo`, `cifragem`, `envio`, `conferencia` e `configuracao`; diretório temporário `0700` apagado sempre; objeto com tamanho divergente é apagado; a senha só vai em `PGPASSWORD`; nenhum log com segredo ou saída das ferramentas. `executar_ferramenta` é o ponto substituível das ferramentas externas.
- Tarefa `backup_diario` (`0 6 * * *`, `queueing_lock`) em `apps/operacao/tarefas.py`, no catálogo (1.440/1.560 min) e em `MONITORES_EXTERNOS` (120/60); comando `backup_externo`; variáveis de `prod.py` (`R2_BUCKET_BACKUPS`, credencial própria, `BACKUP_CHAVE_PUBLICA_AGE` com `age1`); linha "Último backup externo" no painel; no CI, o job `verificacoes` instala `postgresql-client-17` e `age` e define `EXIGIR_FERRAMENTAS_DE_BACKUP=1`.

## Evidência do A-15 (ferramentas reais)

Não roda na máquina do desenvolvedor. Foi executado dentro da imagem construída pela E16-01 (que tem `pg_dump` 17.12, `pg_restore`, `age` 1.1.1 e `age-keygen`), com o repositório montado e o Postgres do host:

`docker run ... -e EXIGIR_FERRAMENTAS_DE_BACKUP=1 organicos-meier:local sh -c "uv sync --locked && uv run pytest -q tests/tecnicos/test_backup_externo_ferramentas.py"` → **1 passed**. O teste gera um par `age-keygen`, grava uma `Rodada` e uma `EntradaAuditoria` (com `transaction=True`), faz o backup real, baixa o objeto do `moto`, decifra, confirma que o texto da auditoria não está no arquivo cifrado e que `pg_restore --list` contém `rodadas_rodada` e `nucleo_entradaauditoria`. Em outro banco de testes (`organicos_a15`), porque o `test_organicos` do host estava ocupado por uma sessão de execuções anteriores. O resultado do job no CI fica para o registro do revisor.

## Decisões e desvios

1. **Pontos de substituição dos testes** (a spec não os fixa): `apps.operacao.backup.executar_ferramenta(args, env, timeout)` para `pg_dump` e `age`; o R2 é o `moto`. Os erros do `pg_dump` (código 1) e da cifragem (`TimeoutExpired`) viram `BackupFalhou` com causa `1` e `TimeoutExpired`.
2. **Senha única nos testes:** a senha do banco de teste (`organicos`) coincide com o texto da chave do objeto e de um diretório; os testes A-2 e A-8 trocam `settings_dict["PASSWORD"]` por um valor único para que a conferência de vazamento valha. O diretório temporário usa o prefixo `bkp-`.
3. **A-4/A-5, forma da falha:** o `ClientError` no envio e o tamanho divergente são provocados em `botocore.client.BaseClient._make_api_call` (`PutObject`/`HeadObject`), contra o backend S3 simulado.
4. **Linha do painel:** `_data` usa Brasília; o tamanho é `tamanho/1.000.000` com uma casa e vírgula; a chave não aparece.
5. **Testes que mexeram com Sentry** passaram a restaurar o estado com `sentry_sdk.get_global_scope().set_client(None)`: `sentry_sdk.init(dsn=None)` deixava um cliente ativo e quebrava o A-3 da E16-03 conforme a ordem dos testes.
6. **Prefixo `test_backup_externo`** em `PREFIXOS_COM_SIMULADOR`; `_AMBIENTE_MINIMO` ganhou as quatro variáveis do backup.
7. **Catálogo com 12 tarefas:** os testes da E15 que usam `concluir_todas` e `len(TAREFAS_MONITORADAS)` seguem verdes.

## Verificação

`uv run pytest -q` em `test_backup_externo.py`, `tests/ambiente`, `test_painel_administrativo.py`, `test_observabilidade.py`, `test_execucao_das_tarefas.py`, `test_painel_ponta_a_ponta.py`: verde (118 passed, 1 skipped = A-15, que passou no contêiner). `ruff` e `mypy` (544 arquivos) limpos; `makemigrations --check` sem mudanças. Suíte completa no fim da E16. Sem push, PR nem merge.


---

## Revisão independente — agente 3 — 2026-11-17

Base avaliada: `52f8745870ebfa007ad6a94edf7f968ae472d04e`, branch
`e16-especificacoes`, diff contra `02f8e91`. Requisitos lidos antes do código:
AGENTS.md, especificação funcional v1.7, infraestrutura v1.8 e as oito specs e
acceptances da E16. Registros do implementador acima preservados integralmente.
A evidência global de execução está no parecer da E16-08 abaixo.

**Veredito da fatia: REPROVADO.**

### E16-R03 — Importante — repetição sobrescreve backup já confirmado

Referências: E16-04 regras 1, 2, 4 e invariantes; AGENTS.md §6 (integridade,
idempotência e recuperação); `apps/operacao/backup.py:188` e `:207`.
A chave tem resolução de segundos e o upload substitui o objeto antes de tentar
inserir o registro com chave única. A restrição do banco age tarde demais.
Uma execução manual e a periódica no mesmo segundo podem colidir; o comando manual
não participa do `queueing_lock` do worker.

Reprodução independente com os fixtures `ab` e `ferramentas` de
`tests/tecnicos/test_backup_externo.py`, no banco isolado do revisor:

```python
from tests.tecnicos import test_backup_externo as apoio
primeiro = apoio._fazer()  # instante I fixo, objeto e registro confirmados
monkeypatch.setattr(apoio, "CONTEUDO_CIFRADO", b"OUTRO-BACKUP-CIFRADO")
with pytest.raises(IntegrityError), transaction.atomic():
    apoio._fazer()  # mesmo I/chave: upload acontece, INSERT falha
atual = ab.get_object(Bucket=apoio.BUCKET, Key=primeiro.chave)["Body"].read()
assert hashlib.sha256(atual).hexdigest() == primeiro.sha256
```

Resultado: falha na última asserção. Hash do registro começa `2f75b302`; hash do
objeto agora começa `c6679d53`. O registro imutável deixa de descrever o objeto que
aponta. Variar os bytes simula duas cifragens distintas. Não se trata de exigir
um formato novo de chave: é necessário impedir que uma colisão substitua um backup
confirmado, inclusive concorrente, mantendo o contrato aprovado.

Retorno: proteger a identidade e o objeto antes do envio, definir a resposta segura
à repetição e testar chamadas concorrentes/manual-periódica, sem perder o objeto
anterior. A correção não deve se limitar a capturar o IntegrityError posterior.

A-1 a A-14/A-16/A-17: conferidos rotina, modelo/trigger, falhas, limpeza, tarefa,
comando, configuração e painel. A-15: o teste local é pulado por falta de ferramentas;
registro do implementador em contêiner preservado, mas não foi revalidado nesta
revisão e o build atual falha em R01. Não confundir `pg_restore --list` desse critério
com o teste de restauração operacional completo da E16-08.
