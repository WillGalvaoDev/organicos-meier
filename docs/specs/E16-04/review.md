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

## Correção E16-R03 — a reserva da chave (implementador, 2026-11-17)

- **Red observado** (`tests/tecnicos/test_backup_externo.py`): 7 falhas e 2 erros — A-18 reproduziu o `IntegrityError` do revisor com o objeto já substituído; A-19, A-23, A-24 e A-25 não levantavam `BackupFalhou("reserva", ...)`; A-20, A-21 e A-25 (comando) dependiam da trava inexistente (`CHAVE_DA_TRAVA_DO_BACKUP`).
- **Green** (`apps/operacao/backup.py`): antes do despejo, `pg_try_advisory_lock` (constante `CHAVE_DA_TRAVA_DO_BACKUP`, sem transação aberta; liberada no fim com sucesso ou falha) e conferência de que a chave não existe em `BackupExterno` nem no bucket (`head_object`, 404 = livre; outro erro do R2 = `BackupFalhou("reserva", classe)`); nova conferência no bucket logo antes do envio. Respostas: `EmAndamento` e `ChaveExistente`, sem rodar ferramenta, sem enviar e sem apagar nada; só se apaga o objeto que a própria execução enviou com tamanho divergente. O comando imprime a segunda linha da regra 7. Sem escrita condicional no R2 (decisão da spec).
- O A-21 usa duas threads com conexões próprias e transações reais: exatamente uma conclui, a outra recebe `EmAndamento` ou `ChaveExistente`, e o SHA-256 do objeto é o do registro. O A-22 confere em `pg_locks` que nenhuma trava sobra.
- **Ajustes de arranjo (nenhuma asserção removida):** os testes A-8 (logs) e A-12 (comando) repetiam o backup com o mesmo instante; com a reserva isso passou a ser recusado por desenho, então a segunda tentativa usa outro instante. O fixture `ab` deixou de trocar a senha do banco (o que quebrava conexões novas): a senha única vive em `senha_unica`, só nos testes A-2 e A-8.
- A-15 (ferramentas reais) reexecutado dentro da imagem do commit `281d191`: 1 passed (ver E16-01).
- Sem push, PR nem merge. Código corrigido no commit `281d191` (os commits seguintes só mudam documentos).


## Revalidação independente — 2026-11-18 — commit 5f12d21

**REPROVADO; R03 permanece importante, com reprodução residual.** A repetição normal e a concorrência com conexão viva estão corrigidas (A-18 a A-25 verdes). Porém a regra 1-A.4 e a invariante de nunca substituir um backup confirmado não estão garantidas: `_reservar(..., so_o_bucket=True)` faz HEAD, seguido de `upload_file` incondicional. Se a sessão da trava cair durante o despejo, duas execuções podem observar a chave livre antes de uma delas terminar.

Reprodução independente: duas threads com conexões PostgreSQL reais e bucket moto, mesmo instante I. Na thread A, fechar `connections['default']` durante o pg_dump simulado libera a trava de sessão. Depois do segundo HEAD de A, uma barreira permite B executar e confirmar seu backup. A retoma, substitui o objeto por seus bytes e falha com IntegrityError na chave única. Resultado: **1 failed em 19,50s**, na asserção de que o hash do objeto corresponde ao registro confirmado por B. Registro: `df7e70e5021544f4834bbee64a9e3789febc4be81470df629cad6ddb03320a5c`; objeto: `559aead08264d5795d3909718cdd05abd49572e84fe55590eef31a88a08fdffd`. Nenhum banco operacional ou bucket externo foi usado.

A nova especificação prescreve HEAD como proteção contra perda da trava, mas essa consequência não é verdadeira. Devolver o ponto ao especificador e implementador: manter a invariante, com coordenação que permaneça válida até o envio ou aborto seguro após perder a sessão; não presumir suporte de escrita condicional do R2. A-24 cobre objeto que já apareceu antes do HEAD, não esta janela entre HEAD e upload. Teste reproduzível abaixo; arquivo temporário do revisor removido após a execução. O A-15 real passou dentro da imagem atual (ver E16-01); não resolve esta corrida.

```python
import hashlib
import threading
from pathlib import Path
import pytest
from django.db import connections
from apps.operacao import backup
from apps.operacao.models import BackupExterno
from tests.tecnicos.test_backup_externo import ab, I, BUCKET, CHAVE_DO_OBJETO

@pytest.mark.django_db(transaction=True)
def test_perda_da_sessao_nao_substitui_backup_confirmado(ab, monkeypatch):
    livre = threading.Event()
    concluido = threading.Event()
    resultados = {}
    original = backup._reservar
    def ferramenta(args, env, timeout):
        if args[0] == 'pg_dump':
            if threading.current_thread().name == 'A':
                connections['default'].close()
            Path(next(a for a in args if a.startswith('--file=')).split('=', 1)[1]).write_bytes(b'dump')
        else:
            Path(args[args.index('--output') + 1]).write_bytes(threading.current_thread().name.encode())
    def reservar(*args, **kwargs):
        original(*args, **kwargs)
        if threading.current_thread().name == 'A' and kwargs.get('so_o_bucket'):
            livre.set()
            assert concluido.wait(20)
    def executar(nome):
        try:
            if nome == 'B':
                assert livre.wait(20)
            resultados[nome] = backup.fazer_backup_externo(I)
        except Exception as erro:
            resultados[nome] = erro
        finally:
            connections.close_all()
            if nome == 'B':
                concluido.set()
    monkeypatch.setattr(backup, 'executar_ferramenta', ferramenta)
    monkeypatch.setattr(backup, '_reservar', reservar)
    threads = [threading.Thread(target=executar, args=(n,), name=n) for n in ('A', 'B')]
    for t in threads: t.start()
    for t in threads: t.join(30)
    assert all(not t.is_alive() for t in threads)
    assert isinstance(resultados['B'], BackupExterno), resultados
    objeto = ab.get_object(Bucket=BUCKET, Key=CHAVE_DO_OBJETO)['Body'].read()
    assert hashlib.sha256(objeto).hexdigest() == resultados['B'].sha256, (resultados, objeto)
```


## Correção residual R03 — implementador (2026-11-18)

Regra 1-B: a chave do objeto passou a levar um identificador de execução de 128 bits (`secrets.token_hex(16)`), `...Z-<EXECUCAO>.dump.age`. A invariante não depende mais da trava nem do `head_object`; os dois ficam como defesa.

- **Red:** testes A-1 (regex), A-18, A-26 (reprodução do revisor, sem forçar o identificador), A-27 e A-28 escritos primeiro. 1ª execução: `ImportError` (função inexistente). Para observar falha de comportamento, acrescentei só a função `identificador_da_execucao()` sem usá-la na chave: **11 failed, 29 passed** (inclui A-26 e A-28). O passo intermediário (função sem uso) é declarado.
- **Green:** chave com identificador gerado antes da reserva; `docs/operacao/restauracao.md` atualizado (formato e ordenação). `tests/tecnicos/test_backup_externo.py` + `tests/ambiente`: **66 passed, 2 xfailed** (os dois xfail são da E16-08, bloqueados por contas da fase 0).
- Arranjo dos testes antigos: a fixture `ab` força o identificador para as chaves ficarem previsíveis; A-1, A-18, A-26 e A-27 o soltam. Nenhuma asserção foi removida ou afrouxada; o A-18 antigo (mesma chave recusada) virou "mesmo instante gera outra chave" + identificador repetido recusado, conforme a spec.
- Commit: `9da84a7`. Suíte completa: ver E16-07/review.md.


## Nova revalidação independente — 2026-11-18 — commit 9f4163b

**APROVADO no escopo local corrigido. E16-R03 encerrado.** Confrontados a regra 1-B e A-1/A-18/A-19/A-24/A-25/A-26/A-27/A-28 corrigidos com o código, testes e roteiro de restauração. A alteração usa `secrets.token_hex(16)` antes da reserva e inclui o identificador na chave; nenhuma coordenação entre objetos de execuções distintas depende da sessão perdida. A repetição do instante produz outro backup; colisão forçada já existente continua recusada antes das ferramentas. Aceita a solução técnica prevista na especificação, com identificadores aleatórios de 128 bits; isso não é uma demonstração matemática de impossibilidade de colisão aleatória.

Executados os testes de backup e ambiente junto da validação da matriz (resultado global em E16-08). A reprodução A-26 fecha a conexão PostgreSQL de A durante o despejo, libera a trava, deixa B concluir entre o segundo HEAD e o envio de A e confere os objetos por suas respectivas chaves: **passou**. A-18 e A-27 também passaram. Os fixtures soltam o identificador fixo nesses casos, preservando o gerador real; A-19/A-24 mantêm colisões controladas. O roteiro mostra o sufixo novo, e o painel continua sem expor a chave.

Registro TDD conferido: ImportError inicial, função substituível ainda sem uso para obter falha comportamental, 11 falhas registradas e correção posterior da chave. A mudança do A-18 corresponde à especificação anterior ao código, não oculta a repetição de uma chave forçada. Não foi alterado código pelo revisor. O teste com ferramentas reais/build da revisão de 5f12d21 não foi repetido nesta rodada, cuja alteração de produção se restringe à identidade do objeto; restauração operacional e RTO continuam pendentes na E16-08.
