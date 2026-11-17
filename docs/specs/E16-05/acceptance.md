# E16-05 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo AR:**
  - relógio em `I = 2026-11-20 15:00 UTC` (12:00 em Brasília);
  - o AE da E14-01 (fornecedor F, compradores A e B, pagos pelo simulador), aprovado, com o repasse de R$ 170,00 registrado;
  - um aporte de R$ 1.000,00;
  - uma `ConciliacaoDiaria` de 19/11/2026;
  - um `BackupExterno` concluído em `I − 9h`.
- **Execução:** `call_command("conferir_restauracao", stdout=..., stderr=...)`, capturando a saída e o código de saída (`SystemExit`).
- **Banco intocado:** a contagem de linhas das tabelas de domínio, de alertas, de auditoria e do Procrastinate é comparada antes e depois do comando.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regras 2 e 3 | positivo | AR coerente | o comando | as sete seções na ordem da regra 2, cada uma com o título e o resultado; "Ponto recuperado" com o instante do último movimento, da última auditoria e de 20/11/2026 03:00 (backup); "Invariante financeiro" `OK` com a diferença; "Estoque" `OK`; "Reconferir com o extrato" `ATENÇÃO` com o repasse de R$ 170,00 e o aporte de R$ 1.000,00, do mais novo para o mais antigo; a linha final com `0 falha(s)`; código de saída 0. **Red esperado:** o comando não existe |
| A-2 | Regra 1 | negativo | o A-1 | comparar o banco | as contagens iguais; nenhum `AlertaFinanceiro` aberto ou resolvido; nenhuma `EntradaAuditoria`; nenhum job do Procrastinate novo |
| A-3 | Regra 1 | negativo | AR; uma conferência de teste registrada que tenta gravar uma `EntradaAuditoria` | o comando | falha com erro de transação somente leitura; nada gravado |
| A-4 | Regra 2.2 | negativo | AR com o saldo do simulador reduzido abaixo das obrigações de terceiros (`ajustar_saldo`, E09) | o comando | "Invariante financeiro" `FALHA`, com a diferença negativa; código de saída 1; nenhum alerta `invariante_violado` aberto |
| A-5 | Regra 2.2 | positivo | AR com o simulador indisponível (`indisponivel()`, E07) | o comando | "Invariante financeiro" `ATENÇÃO` com "Provedor indisponível: conferir depois."; código de saída 0 |
| A-6 | Regra 2.3 | negativo | AR com o total reservado de um produto acima do estoque, gravado diretamente | o comando | "Estoque" `FALHA` com o fornecedor, o produto, o reservado e o estoque; código de saída 1 |
| A-7 | Regra 2.4 | positivo | uma rodada em `fechamento` com o prazo vencido há 2 horas e não encerrada | o comando | "Prazos encerrados" `ATENÇÃO` com a linha do E15-05 e a frase da infraestrutura 6 |
| A-8 | Regra 2.5 | positivo | uma `ChamadaAoProvedor` pendente, uma devolução em processamento e dois `Envio` pendentes | o comando | "Pendências com o provedor" `ATENÇÃO` com 1, 1 e 2 |
| A-9 | Regra 2.6 | positivo | AR com o relógio em `I + 2 dias` e nenhuma conciliação nova | o comando | "Conciliação" `ATENÇÃO` com a última em 19/11/2026 e o número de dias encerrados sem conciliação calculado como na E09-07 |
| A-10 | Regra 5 | positivo | AR com o aporte em `I − 1h` e o repasse em `I − 2h` | `--antes-de 2026-11-20T11:30` (Brasília, `I − 30min`); depois `--antes-de 2026-11-20T10:30` | o aporte e o repasse no primeiro; só o repasse no segundo |
| A-11 | Regra 5 | negativo | AR | `--antes-de ontem` | "Instante inválido: use AAAA-MM-DDTHH:MM."; código de saída 2 |
| A-12 | Regra 4 | negativo | AR com os compradores A e B com nome, e-mail e WhatsApp conhecidos | o comando | nenhum desses valores na saída; nenhuma parte de `DATABASE_URL` na saída |
| A-13 | Regras 6 e 7 | positivo | `docs/operacao/restauracao.md` | ler o arquivo | os dez títulos da regra 6, na ordem; a tabela "Registro dos testes" com as colunas da regra 6.9; os comandos `fly scale count worker=0`, `pg_restore --no-owner --no-privileges` e `python manage.py conferir_restauracao` |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-12 | `tests/tecnicos/test_conferir_restauracao.py` |
| A-13 | `tests/ambiente/test_artefatos_de_implantacao.py` |
