# E16-04 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo AB:**
  - instante `I = 2026-11-20 06:00:00 UTC`;
  - `AMBIENTE = "homologacao"`;
  - bucket `backups-teste` no `moto`;
  - `BACKUP_CHAVE_PUBLICA_AGE` de teste.
- **Etapas substituíveis:** as três etapas externas (despejo, cifragem e envio) atrás de interfaces. Os testes de A-1 a A-13 usam substitutos que gravam o que receberam ou falham sob comando. O A-15 usa as ferramentas reais.
- **Ferramentas reais:** o A-15 exige `pg_dump` 17, `pg_restore`, `age` e `age-keygen`. No CI, a variável `EXIGIR_FERRAMENTAS_DE_BACKUP=1` faz a ausência delas falhar o teste. Fora do CI, a ausência pula o teste com o motivo.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 1 | positivo | AB com substitutos que funcionam | `fazer_backup_externo(I)` | um `BackupExterno` com a chave `banco/homologacao/2026/11/organicos-homologacao-20261120T060000Z.dump.age`, o tamanho e o `sha256` do arquivo cifrado, `iniciado_em` e `concluido_em`; o objeto no bucket com o metadado `sha256`. **Red esperado:** a função não existe |
| A-2 | Regra 1 | positivo | AB | ler o que o despejo recebeu | argumentos com `--format=custom`, `--no-owner` e `--no-privileges`; a senha do banco ausente dos argumentos e presente só em `PGPASSWORD` no ambiente do processo |
| A-3 | Regra 1 | positivo | AB | ler o que a cifragem recebeu | `--encrypt` e `--recipient` com a chave pública; o arquivo de entrada é o despejo |
| A-4 | Regras 2 e 3 | negativo | AB com o despejo saindo com código 1; depois com a cifragem esgotando o tempo; depois com `ClientError` no envio | `fazer_backup_externo(I)` em cada caso | `BackupFalhou` com etapa `despejo` e causa `1`; `cifragem` e `TimeoutExpired`; `envio` e `ClientError`; nenhum `BackupExterno`; nenhum objeto no bucket; o diretório temporário vazio ou apagado nos três |
| A-5 | Regra 2 | negativo | AB com o `head_object` devolvendo um tamanho diferente | `fazer_backup_externo(I)` | `BackupFalhou("conferencia", ...)`; o objeto apagado do bucket; nenhum `BackupExterno` |
| A-6 | Regra 3 | positivo | AB, sucesso | listar o diretório temporário usado | nada sobrou; o diretório foi criado com permissão só do dono (em sistemas POSIX) |
| A-7 | Regra 4 | negativo | um `BackupExterno` gravado | `update()` e `delete()` nele; outro com a mesma chave; outro com `tamanho_bytes = 0`; outro com `sha256` de 63 caracteres | recusados pelo banco nos cinco casos |
| A-8 | Regra 5 | negativo | o A-1 e os casos do A-4, com logs capturados; os substitutos com stderr contendo `ana@exemplo.com` | ler os logs | o `INFO` com a chave, o tamanho e a duração; os `ERROR` com a etapa e a causa; nenhum log contém a senha do banco, `DATABASE_URL`, as credenciais do R2 nem `ana@exemplo.com` |
| A-9 | Regra 6 | positivo | — | ler as tarefas periódicas do Procrastinate e o catálogo da E15-01 | `backup_diario` com `0 6 * * *` e `queueing_lock`; no catálogo, "Backup externo diário", 1.440 e 1.560 minutos |
| A-10 | Regra 6 | positivo | AB com substitutos que funcionam | `backup_diario(timestamp=0)` | um `BackupExterno`; o `ExecucaoDaTarefa` da tarefa com a conclusão |
| A-11 | Regra 6 | negativo | AB com o envio falhando | `backup_diario(timestamp=0)` | `BackupFalhou` repassado; o `ExecucaoDaTarefa` com a falha `BackupFalhou`; nenhum `BackupExterno` |
| A-12 | Regra 7 | positivo e negativo | AB | `call_command("backup_externo")` com sucesso; depois com o despejo falhando | a chave e o tamanho na saída; na falha, "Backup falhou na etapa despejo." e saída com código 1 |
| A-13 | Regra 8 | negativo | AF da E16-01 sem cada uma das quatro variáveis; com `BACKUP_CHAVE_PUBLICA_AGE=chave-invalida` | carregar `config.settings.prod` em subprocesso | falha nos quatro; a mensagem da regra 8 no último |
| A-14 | Regra 6, E16-03 | positivo | o transporte em memória da E16-03 | `backup_diario(timestamp=0)` com sucesso | check-ins `in_progress` e `ok` com o slug `backup-diario` e o `monitor_config` da tabela da E16-03 (`0 6 * * *`, margem de 120 e duração máxima de 60) |
| A-15 | Regras 1 e 3, ponta a ponta | positivo | ferramentas reais; um par de chaves gerado por `age-keygen` no teste; o banco de testes com uma `Rodada` e uma `EntradaAuditoria` conhecidas; bucket no `moto` | `fazer_backup_externo(agora())`; baixar o objeto; decifrar com a chave privada; `pg_restore --list` | a decifragem funciona; a lista do `pg_restore` contém as tabelas da rodada e da auditoria; o conteúdo cifrado não contém o texto da `EntradaAuditoria`. **Red esperado:** a função não existe |
| A-16 | Regra 9 | positivo | um `BackupExterno` concluído em `I` com 12.345.678 bytes | `GET /administracao/` como o administrador | "Último backup externo: 20/11/2026 03:00 (12,3 MB)"; a chave do objeto ausente do HTML |
| A-17 | Regra 9 | positivo | nenhum `BackupExterno` | `GET /administracao/` | "Nenhum backup externo registrado." |
| A-18 | Regra 1-A (E16-R03) | negativo | AB; `fazer_backup_externo(I)` concluído; os substitutos passam a produzir outro conteúdo cifrado (`OUTRO-BACKUP-CIFRADO`) | `fazer_backup_externo(I)` de novo | `BackupFalhou("reserva", "ChaveExistente")`; despejo e cifragem não chamados; o SHA-256 do objeto no bucket igual ao do registro; um único `BackupExterno`. **Red esperado:** `IntegrityError` com o objeto já substituído (reprodução do revisor) |
| A-19 | Regra 1-A (E16-R03) | negativo | AB; um objeto já no bucket com a chave de `I`, sem `BackupExterno` | `fazer_backup_externo(I)` | `BackupFalhou("reserva", "ChaveExistente")`; o objeto com os mesmos bytes; nenhum `BackupExterno`; nenhuma ferramenta chamada |
| A-20 | Regra 1-A (E16-R03) | negativo | AB; outra conexão do banco segurando a trava do backup | `fazer_backup_externo(I)` | `BackupFalhou("reserva", "EmAndamento")`; nenhuma ferramenta chamada; nenhum objeto; nenhum `BackupExterno` |
| A-21 | Regra 1-A, concorrência (E16-R03) | negativo | AB; duas threads com conexões próprias chamando `fazer_backup_externo(I)` (teste com transações reais e marca `concorrencia`); o despejo substituto da primeira espera até a segunda tentar a reserva | as duas chamadas | exatamente uma conclui; a outra levanta `BackupFalhou("reserva", ...)` com `EmAndamento` ou `ChaveExistente`; um único `BackupExterno`; o SHA-256 do objeto igual ao do registro |
| A-22 | Regra 1-A (E16-R03) | positivo | AB; uma execução que falha no envio; depois uma bem-sucedida | `fazer_backup_externo(I)` de novo depois da falha; depois `fazer_backup_externo(I + 1h)` | a segunda chamada conclui (a falha no envio não deixou objeto nem trava); a terceira conclui; ao fim de cada chamada, nenhuma trava consultiva do backup em `pg_locks` |
| A-23 | Regra 1-A (E16-R03) | negativo | AB; o `head_object` da reserva levantando `ClientError` com código 403 | `fazer_backup_externo(I)` | `BackupFalhou("reserva", "ClientError")`; nenhuma ferramenta chamada; o log `ERROR` com a etapa `reserva` |
| A-24 | Regra 1-A.4 (E16-R03) | negativo | AB; o despejo substituto grava no bucket um objeto com a chave de `I` antes de terminar (simula outra escrita durante o despejo) | `fazer_backup_externo(I)` | `BackupFalhou("reserva", "ChaveExistente")`; o objeto gravado pelo substituto intacto; nenhum envio da rotina; nenhum `BackupExterno` |
| A-25 | Regras 6 e 7 (E16-R03) | negativo | AB com a trava ocupada; depois com a chave existente | `call_command("backup_externo")`; depois `backup_diario(timestamp=0)` com a chave existente | a mensagem da etapa e a segunda linha da regra 7 em cada caso, com código 1; na tarefa, `BackupFalhou` repassado e o `ExecucaoDaTarefa` com a falha |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-12 e A-14 | `tests/tecnicos/test_backup_externo.py` |
| A-13 | `tests/ambiente/test_homologacao.py` |
| A-15 | `tests/tecnicos/test_backup_externo_ferramentas.py`; o job `verificacoes` do CI instala o `postgresql-client-17` e o `age` e define `EXIGIR_FERRAMENTAS_DE_BACKUP=1` |
| A-16 e A-17 | `tests/tecnicos/test_painel_administrativo.py` |
| A-18 a A-25 | `tests/tecnicos/test_backup_externo.py` (A-21 com transações reais) |
