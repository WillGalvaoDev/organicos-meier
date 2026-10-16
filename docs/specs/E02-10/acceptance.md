# E02-10 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As rotas `/teste/...` existem só nas configurações de teste.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | T-25, cenário 61 | negativo | um fornecedor autenticado | chama `GET` e `POST /teste/carrinho/` e `POST /teste/pagamento/`, também com o cabeçalho `HX-Request: true` | 403 em todos; a view não executa (contador da rota de teste igual a zero) |
| A-2 | T-25 | negativo | um comprador autenticado | chama `GET /teste/fornecedor/painel/` | 403 |
| A-3 | Spec §2 | positivo | um comprador ativo | chama `/teste/carrinho/`, `/teste/pagamento/` e `/teste/meus-pedidos/` | 200 nos três |
| A-4 | Spec §2 | negativo | um comprador suspenso | chama `/teste/carrinho/` e `/teste/pagamento/`; depois `/teste/meus-pedidos/` | 403 nos dois primeiros; 200 no terceiro |
| A-5 | Spec §2 | positivo | um fornecedor vinculado a `F` | chama `/teste/fornecedor/painel/` | 200 com o `id` de `F` |
| A-6 | Spec §15 | negativo | o administrador (com passkey) | chama as rotas de comprador e de fornecedor de teste | 403 em todas |
| A-7 | Spec §15 | negativo | um visitante anônimo | chama cada rota de teste | redirecionamento para `/entrar/` em todas; a view não executa |
| A-8 | Cenário 61 | positivo | a mesma pessoa com conta comprador `ana@exemplo.com` e conta fornecedor `ana.fornecedor@exemplo.com`, com sessões em dois clientes | cada cliente abre `/inicio/` e `/perfil/` | cada resposta contém só o nome, o e-mail e o papel da conta da própria sessão |
| A-9 | Spec da fatia | negativo | um objeto de conta em memória com papel fornecedor e sem fornecedor | passa pelo decorador `exige_fornecedor` (teste unitário com `RequestFactory`) | 403 |
| A-10 | Spec da fatia | positivo | o projeto com as rotas da E02 | rodo o teste de varredura | nenhuma rota sem política; cada entrada de `POLITICAS_DE_TERCEIROS` corresponde a uma rota existente |
| A-11 | Spec da fatia | negativo | uma rota sem política acrescentada temporariamente pelo teste (via `urlpatterns` de teste ou `override_settings(ROOT_URLCONF=...)`) | rodo a função de varredura | falha citando o nome ou caminho da rota |
| A-12 | Cenário 62 | negativo | uma conta comprador | atualizo `papel` por SQL direto para `fornecedor` (com `fornecedor_id` preenchido no mesmo `UPDATE`) | o banco recusa |
| A-13 | Cenário 62 | negativo | todos os formulários (`Form` e `ModelForm`) de `apps/` | inspeciono os campos | nenhum tem campo `papel` editável para a própria conta; o único campo de papel do projeto é o da emissão de convite (E02-04) |
| A-14 | T-37 | propriedade | e-mails gerados com variações de maiúsculas e espaços, mais um alias `+` do mesmo usuário | executo cada fluxo listado na spec com a variação | cada fluxo trata a variação como o mesmo endereço; o alias é tratado como outro endereço em todos |
| A-15 | T-37 | estático | o código-fonte de `apps/` | rodo o teste AST | nenhuma ocorrência de `email__iexact`, `email_normalizado__iexact`, nem de `.lower()`/`.casefold()` sobre nomes contendo `email` fora de `apps/contas/emails.py` |
| A-16 | T-37 | negativo | um arquivo temporário com `Conta.objects.filter(email_normalizado__iexact=x)` analisado pela mesma função do teste AST | rodo a função sobre ele | a função acusa a ocorrência |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-7, A-9 | `tests/tecnicos/test_permissoes_papeis.py` (A-1 e A-2 marcados `tecnico`, com o comentário `T-25`) |
| A-8 | `tests/aceitacao/test_cenario_61_contas_independentes.py` (marcador `acceptance`) |
| A-10, A-11 | `tests/tecnicos/test_permissoes_politica_rotas.py` |
| A-12, A-13 | `tests/aceitacao/test_cenario_62_papel_imutavel.py` (marcador `acceptance`) |
| A-14 a A-16 | `tests/tecnicos/test_normalizacao_varredura.py` (marcador `tecnico`, com o comentário `T-37`) |
