# E02-01 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Testes com banco usam Postgres real.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §2, R-3 | positivo | `"  Ana@Exemplo.com "`, `"ANA@EXEMPLO.COM"`, `"ana@exemplo.com"` | chamo `normalizar_email` | `"ana@exemplo.com"` nos três |
| A-2 | Spec §2, cenário 84 | positivo | `"usuario+teste@gmail.com"` e `"u.suario@gmail.com"` | chamo `normalizar_email` | os valores voltam iguais à entrada, e nenhum é igual a `"usuario@gmail.com"` |
| A-3 | Infra 4.11 | negativo | `""`, `"   "`, `"semarroba"`, `"a@@b.com"`, `"ana @x.com"`, `None`, `123` | chamo `normalizar_email` | `EmailInvalido` em cada caso |
| A-4 | T-37 | propriedade | e-mails válidos gerados pelo hypothesis, com variações aleatórias de maiúsculas e de espaços nas pontas | chamo `normalizar_email` | todas as variações produzem o mesmo valor, e a função é idempotente |
| A-5 | T-37, cenário 84 | propriedade | um e-mail válido `u@d` e o alias `u+x@d`, gerados | normalizo os dois | os resultados são diferentes |
| A-6 | Spec §2, cenário 80 | negativo | uma conta com `ana@exemplo.com` | crio outra conta, de qualquer papel, com `"  Ana@Exemplo.com "` | `EmailEmUso`, e continua existindo uma única conta |
| A-7 | Infra 4.11 | negativo | a tabela de contas | insiro por SQL direto uma conta com `email_normalizado = 'Ana@x.com'` e outra com `' ana@x.com'` | o banco recusa as duas (`conta_email_ja_normalizado`) |
| A-8 | T-34 (banco) | concorrência | nenhuma conta | duas operações em paralelo, com `executar_em_paralelo`, criam uma conta de comprador com `Ana@x.com` e uma de fornecedor com ` ana@x.com `, repetido 10 vezes, com limpeza entre as repetições | em todas as repetições, exatamente uma conta existe e a outra operação recebe erro de integridade ou `EmailEmUso` |
| A-9 | Spec §2, Infra 4.11 | negativo | um fornecedor | crio por SQL direto (a) uma conta de papel `fornecedor` sem fornecedor e (b) uma conta de papel `comprador` com fornecedor | o banco recusa as duas |
| A-10 | Spec §1 | negativo | um administrador existente | insiro por SQL direto um segundo administrador | o banco recusa |
| A-11 | Spec §1, §2 | negativo | o administrador | atualizo por SQL direto a situação dele para `suspensa` e para `removida` | o banco recusa as duas |
| A-12 | Spec §2 | positivo | contas nas situações `ativa`, `suspensa` e `removida` | leio `is_active` | `True`, `True` e `False` |
| A-13 | Spec §14, Infra 4.11 | positivo | `EmailBanido` com `ana@x.com` | chamo `email_banido` com `"  ANA@x.com "`, `"ana+1@x.com"` e `"lixo"` | `True`, `False` e `False` |
| A-14 | Infra 4.11, 5 | negativo | `EmailBanido` com `ana@x.com` | insiro `"ANA@x.com"` normalizado de novo pela aplicação e, por SQL direto, `'Ana@x.com'` | erro de integridade (unicidade) na primeira e recusa pelo `CHECK` na segunda |
| A-15 | Spec §2 (definitivo), E01-04 | negativo | um `EmailBanido` gravado | altero ou apago pela aplicação e por SQL direto | `RegistroImutavel` na aplicação e recusa do banco no SQL |
| A-16 | Spec §1 | positivo | nenhum administrador | rodo `criar_administrador --email " Admin@x.com " --nome "Adm"` | existe um administrador com `admin@x.com`, senha inutilizável e situação ativa, e uma entrada de auditoria `conta.criar_administrador` com autor sistema |
| A-17 | Spec §1, §2 | negativo | (a) um administrador existente; (b) um e-mail em uso por um comprador; (c) um e-mail banido; (d) o e-mail `"lixo"` | rodo `criar_administrador` em cada caso | erro (`CommandError`), código de saída diferente de zero, nada criado e nada auditado |
| A-18 | Infra 2 (menor privilégio) | negativo | as configurações do projeto | inspeciono `INSTALLED_APPS` e resolvo a URL `/admin/` | `django.contrib.admin` não está instalado, e `/admin/` não resolve (404) |
| A-19 | Spec da fatia | positivo | `ContaFactory` | crio um comprador, um fornecedor (*trait*), um administrador e um suspenso | os quatro passam por `full_clean` e respeitam as restrições |
| A-20 | Spec da fatia, compatibilidade | regressão | a suíte da E01 | rodo a suíte completa | todos os testes da E01 passam, e só a criação de usuário de `test_nucleo_auditoria.py` foi trocada, sem alterar asserções |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-5 | `tests/tecnicos/test_contas_emails.py` |
| A-6 a A-12, A-19 | `tests/tecnicos/test_contas_modelo.py` |
| A-13 a A-15 | `tests/tecnicos/test_contas_banimento_modelo.py` |
| A-16, A-17 | `tests/tecnicos/test_contas_criar_administrador.py` |
| A-18 | `tests/tecnicos/test_contas_modelo.py::test_admin_do_django_ausente` |
| A-20 | evidência no `review.md` (suíte completa e diff de `test_nucleo_auditoria.py`) |
