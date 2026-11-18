# E16-02 — Registro do implementador

Agente 2.

## Red (observado antes do código de produção dos comportamentos)

1. `uv run pytest -q tests/tecnicos/test_arquivos_no_r2.py tests/ambiente/test_homologacao.py`: **1 erro de coleta** (`ModuleNotFoundError: config.armazenamento`) e, no arquivo de ambiente, **6 falhas** (A-1: o backend era o do sistema de arquivos; A-2: as quatro variáveis do R2 não eram exigidas; A-3, escrito errado, corrigido a seguir).
2. Criada só a configuração do R2 (`config/armazenamento.py` + `prod.py`, regra 1) para observar o Red dos comportamentos: `uv run pytest -q tests/tecnicos/test_arquivos_no_r2.py`: **3 failed, 6 passed** — A-10 (500 no comprovante ausente, `FileNotFoundError`), A-11 (500 no upload do avatar) e A-12 (500 no upload do comprovante), todos `ClientError`/`FileNotFoundError` sem tratamento, como a spec prevê.
3. Guardas que passaram de primeira (a troca de armazenamento já bastava): A-4 a A-9 e A-14.

O A-3 inicial lia `STORAGES` de `config.settings.test` por subprocesso e recebia `None` (o módulo não define `STORAGES`; vale o padrão do Django). O teste foi corrigido para ler `django.conf.settings` (a suíte roda em `config.settings.test`): erro do meu teste, não afrouxamento.

## Green

- `config/armazenamento.py::storage_do_r2`: backend `storages.backends.s3.S3Storage` com endpoint, bucket e credenciais, região `auto`, `default_acl=None`, `querystring_auth=True`, validade de 300 s, `file_overwrite=False`, `s3v4`. `prod.py` a usa com as quatro variáveis obrigatórias (sem padrão).
- `apps/nucleo/armazenamento.py`: `falha_do_armazenamento(operacao)` converte `ClientError`/`BotoCoreError`/`S3UploadFailedError` em `ArmazenamentoIndisponivel` e registra só a operação e a classe do erro (`ClientError`, mesmo quando o boto3 embrulha a falha).
- `atualizar_perfil` (avatar) e `confirmar_devolucao_excepcional` (comprovante) usam o contexto no ponto de gravação; a transação se desfaz e o arquivo não fica órfão. O perfil responde 503 com a mensagem e o formulário; a tela da devolução, 503 com `_detalhe`. A view `comprovante` responde 404 quando o objeto não existe (antes, 500).
- Dependências novas: `django-storages[s3]` (produção) e `moto[s3]` (desenvolvimento).

## Decisões e desvios

1. **Prefixo `test_arquivos_no_`** em `PREFIXOS_COM_SIMULADOR` (`tests/conftest.py`), porque o A-8 a A-12 usam o arranjo da E10 com o simulador (mesmo padrão das E15).
2. **`_AMBIENTE_MINIMO`** ganhou as quatro variáveis do R2 (consequência de serem obrigatórias); `test_nucleo_campos_decimais.py` passou a definir todas as variáveis de `_AMBIENTE_MINIMO` no `monkeypatch` (nenhuma asserção removida).
3. **A-12:** a spec diz "a obrigação ainda devida". A obrigação não tem campo de situação (a baixa é o movimento `devolucao_excepcional`), então o teste confere que não há movimento novo, que a parcela segue `elegivel_excepcional`, que não há confirmação nem auditoria da confirmação.
4. **A-13:** o log é conferido no nível `INFO`; o registro `DEBUG` do próprio `botocore` imprime o cabeçalho de assinatura (com o id da chave de acesso) e não é ligado em produção.
5. **mypy:** `boto3`, `botocore`, `moto` e `storages` entram no override `ignore_missing_imports` (sem stubs). Foi preciso apagar o cache do mypy (`.mypy_cache`, artefato ignorado pelo git) para a mudança de configuração valer.

## Verificação

`uv run pytest -q` nos arquivos da fatia e nos relacionados (avatar, perfil, devolução excepcional, T-09, ambiente): **121 passed**. `ruff` e `mypy` (534 arquivos) limpos. Suíte completa no fim da E16. Sem push, PR nem merge.


---

## Revisão independente — agente 3 — 2026-11-17

Base avaliada: `52f8745870ebfa007ad6a94edf7f968ae472d04e`, branch
`e16-especificacoes`, diff contra `02f8e91`. Requisitos lidos antes do código:
AGENTS.md, especificação funcional v1.7, infraestrutura v1.8 e as oito specs e
acceptances da E16. Registros do implementador acima preservados integralmente.
A evidência global de execução está no parecer da E16-08 abaixo.

**Veredito da fatia: APROVADO no escopo local especificado.** A E16 completa não está aprovada.

Conferidos A-1 a A-14 contra configuração compartilhada do backend S3, código,
testes de ambiente e `test_arquivos_no_r2.py`: bucket privado, assinatura/validade,
chaves independentes do nome pessoal, acesso autenticado e passkey do administrador,
recusa de outro comprador, comprovante restrito, 404 para objeto ausente, rollback
do perfil e da confirmação financeira em falha de upload, mensagem 503 e logs da
aplicação sem credenciais. A procura por `.avatar.url`/`.comprovante.url` está coberta.
A implementação preserva a autorização anterior e usa o backend real com `moto`.

Registros TDD conferidos: configuração ausente, três falhas de comportamento antes
do tratamento, guardas existentes e correção explicitada do teste de STORAGES.
Nenhum achado novo específico desta fatia. A prova contra R2 real é o A-9 da E16-08,
ainda pendente; o build integrado tem R01 e a observabilidade tem R02.


## Revalidação independente — 2026-11-18 — commit 5f12d21

Revalidação de regressão: implementação desta fatia não foi alterada pelas correções; suíte completa passou. Mantido o parecer local anterior, sem novo achado. Integração com R2 real continua dependente da E16-08; não foi executada nesta revisão. Evidências globais na E16-08.
