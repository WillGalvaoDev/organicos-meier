# E02-08 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As telas são testadas com o administrador autenticado por passkey (dublê da E02-03). "Duas sessões" significa dois clientes de teste autenticados na mesma conta.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §2, cenário 60 | positivo | um comprador ativo com uma sessão aberta | o administrador suspende pela tela | situação `suspensa`; nenhum `EmailBanido`; a sessão continua válida (`/inicio/` responde 200); auditoria `conta.suspender` |
| A-2 | Spec §2 | positivo | um receptor de teste conectado a `conta_suspensa` | suspendo um comprador | o receptor é chamado uma vez, com a conta, dentro da transação (`transaction.get_connection().in_atomic_block` verdadeiro no receptor) |
| A-3 | Spec §2 | negativo | um receptor de `conta_suspensa` que levanta erro | suspendo | a suspensão é desfeita: situação continua `ativa` e sem auditoria |
| A-4 | Spec §2, cenário 19, 60 | positivo | um comprador suspenso | o administrador reverte | situação `ativa`; auditoria `conta.reativar`; nenhum outro dado alterado |
| A-5 | Cenário 20, 58, 83, T-24, T-36 | positivo | um comprador ativo com duas sessões abertas | o administrador remove (com confirmação) | situação `removida`; `EmailBanido` do e-mail com autor e momento; os registros do `usersessions` e as linhas de `django_session` da conta apagados; a próxima requisição de cada cliente é tratada como anônima ou recusada; auditoria `conta.remover` |
| A-6 | Cenário 83, T-36 | positivo | o mesmo cenário, com o apagamento de sessões neutralizado no teste (simulando sessão criada na corrida) | cada cliente faz `GET /inicio/` e `POST` em uma rota autenticada | o middleware encerra a sessão: `GET` redireciona para `/entrar/` e `POST` recebe 403; a view não executa (verificado por um contador na rota de teste) |
| A-7 | Cenário 20, 58 | positivo | a conta removida do A-5 | consulto o banco | a conta continua existindo, com histórico de auditoria e convite preservados |
| A-8 | Cenário 58 | negativo | a conta removida do A-5 | tento login por senha, por link (E02-06) e por Google (E02-07), e emito um novo convite para o e-mail com variações de maiúsculas e espaços | recusa em todos; nenhum convite criado |
| A-9 | Cenário 59, 84 | positivo | contas `ana@x.com` e `ana+1@x.com` | removo `ana@x.com` | `ana+1@x.com` continua ativa e entra; um convite para `a.na@x.com` é aceito na emissão |
| A-10 | Cenário 81, T-36 | positivo | a mesma pessoa com conta comprador `ana@exemplo.com` e conta fornecedor `ana.fornecedor@exemplo.com`, ambas com sessão aberta | removo a conta comprador | a sessão da conta fornecedor continua válida; o login dela continua funcionando |
| A-11 | Spec §2 | negativo | o administrador como alvo | chamo `suspender`, `reativar` e `remover` | `ModeracaoInvalida` em todos; nada alterado nem auditado |
| A-12 | Spec da fatia | negativo | (a) suspender um fornecedor; (b) suspender um comprador já suspenso; (c) reativar um comprador ativo; (d) remover uma conta já removida | chamo o serviço em cada caso | `ModeracaoInvalida`; nada alterado nem auditado |
| A-13 | Spec §2, §15 | negativo | um comprador e um fornecedor autenticados; um visitante anônimo | enviam `GET` e `POST` para `/administracao/usuarios/` e para as ações | 403 para os autenticados; anônimo redirecionado para `/entrar/`; nada alterado |
| A-14 | Spec da fatia | negativo | um comprador como `autor` | chamo `remover` diretamente | `PermissionDenied`; nada alterado |
| A-15 | Spec da fatia | concorrência | um comprador ativo | duas chamadas de `remover` em paralelo (`executar_em_paralelo`), repetidas 10 vezes com contas novas | em todas: um `EmailBanido`, uma auditoria `conta.remover`, uma operação com sucesso e outra com `ModeracaoInvalida` |
| A-16 | Spec da fatia | concorrência | um comprador ativo | `suspender` e `remover` em paralelo, repetido 10 vezes | em todas: situação final `removida` com `EmailBanido`; nenhuma exceção não tratada além de `ModeracaoInvalida` |
| A-17 | Spec da fatia | negativo | `encerrar_sessoes` forçado a levantar erro durante `remover` | removo | situação inalterada; nenhum `EmailBanido`; nenhuma auditoria |
| A-18 | Spec §13 | positivo | contas de cada papel e situação | o administrador abre `/administracao/usuarios/` | lista compradores e fornecedores (sem o administrador), com os botões permitidos pela tabela de alvos e nenhum outro |
| A-19 | Spec da fatia | positivo | comprador ativo, comprador suspenso, fornecedor | leio `pode_adicionar_interesse` | `True`, `False`, `False` |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-4, A-11, A-12, A-14, A-19 | `tests/tecnicos/test_moderacao_servicos.py` |
| A-5 a A-10, A-17 | `tests/tecnicos/test_moderacao_remocao.py` |
| A-13, A-18 | `tests/tecnicos/test_moderacao_tela.py` |
| A-15, A-16 | `tests/tecnicos/test_moderacao_concorrencia.py` (marcador `concorrencia`) |
| A-5, A-6 (cenário 83, T-24, T-36); A-7, A-8 (cenários 20 e 58); A-9 (59, 84); A-10 (81, T-36); A-1, A-4 (60, 19) | também marcados `acceptance` ou `tecnico`, com os números no comentário |
