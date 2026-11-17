# E16-04 — Backup externo diário, cifrado, no R2

Fatia 4 de 8 da milestone **E16 — Homologação e encerramento da fase 1**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E16-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E16-01.

## Contexto e objetivo

A infraestrutura 6 define três camadas de recuperação:
- a restauração a qualquer momento do Neon;
- um `pg_dump` diário cifrado no Cloudflare R2, com perda máxima de 24 horas;
- a conciliação com o provedor.

A segunda camada protege contra a perda do próprio Neon (conta, projeto ou região) e precisa ficar num provedor diferente do banco. Esta fatia cria o backup diário: o despejo do banco, a cifragem e o envio ao R2, com registro de cada backup concluído e o monitoramento já existente das tarefas.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 6 | Externa: `pg_dump` diário criptografado no Cloudflare R2; RPO de 24 horas. |
| Infraestrutura 2 | R2 para arquivos e `pg_dump` diário criptografado, num provedor diferente do banco. |
| Infraestrutura 5 | Segredos só em variáveis do provedor; nenhum dado pessoal em logs. |
| Especificação §15, Operação | Backup e restauração verificável, com proposta de objetivos de recuperação. |
| E15-01 e E15-02 | Catálogo de tarefas monitoradas, `execucao_monitorada` e o alerta `tarefa_atrasada`. |
| E16-03 | `MONITORES_EXTERNOS`, com a linha `backup_diario`. |

## Escopo

**Dentro:**
- a rotina de backup e a tarefa periódica `backup_diario`;
- o comando `backup_externo`, para execução manual;
- o registro `BackupExterno`;
- a linha do último backup no painel (E15-05, regra 10);
- as variáveis de ambiente;
- o teste de ponta a ponta com as ferramentas reais.

**Fora:**
- a restauração e a conferência depois dela (E16-05);
- a criação do bucket, da chave do `age` e da regra de retenção no R2 (E16-08);
- o backup dos arquivos enviados: os comprovantes e avatares já ficam no R2, fora do provedor do banco (E16-02).

## Regras

### Rotina

1. **`fazer_backup_externo(instante) -> BackupExterno`**, em quatro etapas, sem transação longa aberta durante o despejo:
   1. **Despejo:** `pg_dump --format=custom --no-owner --no-privileges` do banco `default` para um arquivo temporário. Os dados de conexão vão por variáveis de ambiente do processo (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGSSLMODE`), derivadas de `DATABASES["default"]`. A senha nunca vai na linha de comando.
   2. **Cifragem:** `age --encrypt --recipient <BACKUP_CHAVE_PUBLICA_AGE>` do despejo para um segundo arquivo temporário. A aplicação só conhece a chave pública: a privada nunca fica no Fly.io.
   3. **Envio:** o arquivo cifrado vai para o bucket `R2_BUCKET_BACKUPS`, com a chave `banco/<AMBIENTE>/<AAAA>/<MM>/organicos-<AMBIENTE>-<AAAAMMDD>T<HHMMSS>Z.dump.age` (instante em UTC) e o metadado `sha256` do arquivo cifrado.
   4. **Conferência:** um `head_object` confirma que o tamanho no bucket é igual ao do arquivo local.

   Depois das quatro etapas, a rotina grava o `BackupExterno` (regra 4). Cada ferramenta tem tempo-limite de 30 minutos.
2. **Falhas:**
   - se qualquer etapa falhar (código de saída diferente de zero, tempo esgotado, erro do R2 ou tamanho divergente), a rotina levanta `BackupFalhou(etapa, causa)`, em que `etapa` é `despejo`, `cifragem`, `envio` ou `conferencia` e `causa` é a classe do erro ou o código de saída;
   - nenhum `BackupExterno` é gravado;
   - na conferência com tamanho divergente, o objeto enviado é apagado;
   - num envio interrompido em partes (multipart), o envio é abortado.
3. **Arquivos temporários:**
   - criados num diretório temporário próprio, com permissão só para o dono;
   - apagados no fim, com sucesso ou falha;
   - o despejo sem cifra nunca sai da máquina.
4. **`BackupExterno`** (só inserção, como os registros de auditoria):
   - `iniciado_em`, `concluido_em`, `ambiente`, `chave` (única), `tamanho_bytes` (inteiro positivo) e `sha256` (64 caracteres hexadecimais);
   - nenhum dado de conexão nem caminho local.
5. **Logs:**
   - no sucesso, `INFO` com a chave, o tamanho e a duração;
   - na falha, `ERROR` com a etapa e a causa;
   - nunca a senha, a URL do banco, as credenciais do R2 ou a saída de erro das ferramentas. A saída de erro pode citar dados, por isso não vai para o log.

### Tarefa e comando

6. **Tarefa periódica:** `backup_diario`, com `cron="0 6 * * *"` (03:00 em Brasília) e `queueing_lock`.
   - Ela é envolvida por `execucao_monitorada` e entra no catálogo da E15-01 com a descrição "Backup externo diário", intervalo de 1.440 minutos e tolerância de 1.560 minutos (26 horas).
   - Ela entra também em `MONITORES_EXTERNOS` (E16-03).
   - A falha é repassada: a E15-01 registra a falha, e o Sentry recebe o erro e o check-in `error`.
7. **Comando:** `python manage.py backup_externo` roda a mesma rotina na hora. Ele imprime a chave e o tamanho no sucesso. Na falha, imprime "Backup falhou na etapa <etapa>." e sai com código 1.

### Configuração

8. **Variáveis** obrigatórias em `prod.py`:
   - `R2_BUCKET_BACKUPS`;
   - `R2_BACKUP_ACCESS_KEY_ID` e `R2_BACKUP_SECRET_ACCESS_KEY`, credencial própria e diferente da dos arquivos (E16-02);
   - `BACKUP_CHAVE_PUBLICA_AGE`, que precisa começar com `age1`. Senão: `ImproperlyConfigured("BACKUP_CHAVE_PUBLICA_AGE deve ser uma chave pública do age (age1...).")`.

   O endpoint é o `R2_ENDPOINT` da E16-02. Em `dev.py` e `test.py`, as variáveis são opcionais. Sem elas, a tarefa levanta `BackupFalhou("configuracao", "ImproperlyConfigured")`, o que deixa o problema visível sem quebrar o worker.

### Painel

9. **Linha no painel:** na seção "Tarefas periódicas" (E15-05, regra 10), depois da linha da última conciliação, entra "Último backup externo: <concluido_em em Brasília, dd/mm/aaaa hh:mm> (<tamanho em MB, com uma casa decimal; 1 MB = 1.000.000 bytes>)". Sem nenhum registro, a linha é "Nenhum backup externo registrado.". A chave do objeto não aparece.

## Decisões técnicas

- **`age` com chave pública.** Um servidor comprometido não consegue ler os backups antigos, porque a chave privada fica só com o responsável (E16-05). O `age` é uma ferramenta pequena, sem configuração, e entra na imagem (E16-01). Sem dependência Python nova: o `boto3` já vem com a E16-02.
- **Despejo no worker, como tarefa do Procrastinate.** Reaproveita o monitoramento da E15 e o monitor externo da E16-03, sem outra máquina nem agendador. O banco é pequeno (infraestrutura 1), então o despejo diário leva pouco tempo.
- **Retenção pelo próprio R2.** A regra de ciclo de vida do bucket apaga os objetos com mais de 35 dias (configurada na E16-08). A aplicação não lista nem apaga backups antigos. Sobre o bucket de backups, a credencial dela grava, confere o tamanho e apaga só o objeto que ela acabou de enviar com defeito.
- **Despejo completo, incluindo o esquema do simulador.** Na fase 1 o simulador grava no mesmo banco (E07-R03) e faz parte do estado a recuperar.

## Invariantes

- Nenhum backup sem cifra sai da máquina.
- Um `BackupExterno` só existe para um objeto conferido no bucket.
- Nenhum segredo ou dado do banco nos logs.

## Dependências e decisões em aberto

- Depende das E16-01 (imagem com `pg_dump` 17 e `age`), E16-02 (`boto3`, `R2_ENDPOINT`), E16-03 (`MONITORES_EXTERNOS`), E15-01, E15-02 e E15-05.
- Nenhuma dependência Python nova.
- Nenhuma decisão em aberto.
