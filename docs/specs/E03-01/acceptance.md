# E03-01 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As telas são testadas com o administrador autenticado por passkey (dublê da E02-03).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §4.1 | positivo | o administrador | cadastra `nome=" Sítio Boa Terra "`, `email_pedido=" Pedidos@BoaTerra.com "`, `minimo="150,00"`, `prazo_entrega_dias=7` e `informacoes_frete="Entrega às terças"` | redirecionamento para o detalhe; gravados `"Sítio Boa Terra"`, `"pedidos@boaterra.com"`, `Decimal("150.00")`, `7` e o texto do frete |
| A-2 | Spec da fatia | positivo | o mesmo formulário | envio `minimo="150.00"` | aceito, com o mesmo valor do A-1 |
| A-3 | Spec §1, §4.1 | negativo | o formulário de cadastro | envio, um por vez, `minimo` igual a `0`, `-1`, `0,001`, `abc` e `1.000,00` | erro no campo `minimo` em cada caso; nenhum fornecedor criado |
| A-4 | Spec da fatia | negativo | o formulário de cadastro | envio, um por vez: nome vazio, nome com 151 caracteres, e-mail `nao-e-email`, prazo `0`, prazo `366`, prazo `2,5`, frete com 1001 caracteres | erro no campo correspondente em cada caso; nada criado |
| A-5 | Spec da fatia | positivo | o formulário de cadastro | envio prazo `1` e, noutro caso, `365`, e frete vazio | aceito nos dois; frete gravado como texto vazio |
| A-6 | Infra 4.12 | negativo | o serviço `criar_fornecedor` | chamo com `minimo=150.0` (`float`) | `ValidationError` ou `ValorInvalido`; nada criado |
| A-7 | Spec da fatia | negativo | o banco | `UPDATE` direto de `minimo` para `0`, e de `prazo_entrega_dias` para `0` | o banco recusa os dois (`CHECK`) |
| A-8 | Spec §4.1 | positivo | um fornecedor | o administrador edita nome, e-mail, prazo e frete | gravados; auditoria `fornecedor.editar` com `campos` listando os quatro nomes, sem valores |
| A-9 | Spec da fatia | negativo | um fornecedor com mínimo R$ 150,00 | `POST` de edição com `minimo=10` além de campos válidos | os campos válidos são gravados; `minimo` continua R$ 150,00; `"minimo"` não aparece em `campos` |
| A-10 | Spec da fatia | positivo | um fornecedor | `POST` de edição com os mesmos valores atuais | redirecionamento; nenhuma auditoria nova |
| A-11 | Spec §14 | positivo | o cadastro do A-1 | consulto a auditoria | uma entrada `fornecedor.criar` com autor administrador e `{"fornecedor": <id>}`; o e-mail do fornecedor não aparece em `alteracoes` |
| A-12 | Spec §2, §15 | negativo | um comprador e uma conta de fornecedor autenticados; um visitante anônimo | `GET` e `POST` em cada rota desta fatia | 403 para os autenticados; anônimo redirecionado para `/entrar/`; nada criado nem alterado |
| A-13 | Spec §2 | negativo | um comprador como `autor` | chamo `criar_fornecedor` e `editar_fornecedor` | `PermissionDenied`; nada gravado |
| A-14 | Spec §4.1, §13 | positivo | um fornecedor `F` com duas contas de fornecedor vinculadas (uma ativa e uma removida) e outro fornecedor `G` com uma conta | abro o detalhe de `F` | aparecem as duas contas de `F` com nome, e-mail e situação; a conta de `G` não aparece |
| A-15 | Spec da fatia | positivo | fornecedores `"Zeta"`, `"Alfa"` e `"Meio"` | abro a lista | ordem `Alfa`, `Meio`, `Zeta`, com mínimo e prazo de cada um |
| A-16 | Spec da fatia | negativo | o detalhe e a edição | acesso com um id inexistente | 404 |
| A-17 | E02-10 | positivo | as rotas desta fatia | rodo o teste de varredura de políticas da E02-10 | todas têm política declarada |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-7, A-11, A-13 | `tests/tecnicos/test_fornecedores_cadastro.py` |
| A-8 a A-10, A-14 a A-16 | `tests/tecnicos/test_fornecedores_tela.py` |
| A-12 | `tests/tecnicos/test_fornecedores_permissoes.py` |
| A-17 | coberto pelo teste existente `tests/tecnicos/test_permissoes_politica_rotas.py` |
