# E02-04 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As telas são testadas com o administrador autenticado por passkey (dublê da E02-03). `T` é um instante fixo congelado com a fixture `relogio`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §3.1, §14 | positivo | o relógio em `T` | o administrador emite convite de comprador para `" Bia@X.com"` pela tela | um `Convite` com `bia@x.com`, papel comprador, sem fornecedor, `emitido_em = T`, `expira_em = T + 24h` e não consumido |
| A-2 | Spec §12 | positivo | o convite do A-1 | inspeciono a caixa de saída | um e-mail para `bia@x.com` com um link `/convite/<token>/`, a finalidade "comprador" e a expiração no fuso de America/Sao_Paulo |
| A-3 | Spec §3.1 (token) | positivo | o convite do A-1 e o token extraído do e-mail | consulto o banco | `token_hash == sha256(token)`; o token em texto não aparece em nenhuma coluna de `Convite` nem na auditoria |
| A-4 | Spec §3.1 (token) | positivo | dois convites emitidos | comparo os tokens dos e-mails | diferentes, cada um com pelo menos 43 caracteres |
| A-5 | Spec §3.1, §13 | positivo | um fornecedor `F` | o administrador emite convite de fornecedor vinculado a `F` | o convite tem papel fornecedor e `fornecedor = F`; o e-mail cita o nome de `F` |
| A-6 | Spec §3.1 | negativo | a tela de emissão | envio (a) papel fornecedor sem fornecedor; (b) papel comprador com fornecedor; (c) fornecedor com `id` inexistente; (d) papel `administrador` adulterado no `POST` | recusa em cada caso, nenhum convite e nenhum e-mail |
| A-7 | Spec §3.1, cenário 80 | negativo | uma conta com `ana@exemplo.com`, de qualquer papel, inclusive removida | emito convite para `"  Ana@Exemplo.com "` | recusa `EmailEmUso`; nenhum convite e nenhum e-mail |
| A-8 | Spec §3.1 | negativo | `EmailBanido` com `ana@x.com` | emito convite para `"ANA@x.com"` | recusa por banimento; nenhum convite e nenhum e-mail |
| A-9 | Cenário 59 | positivo | `EmailBanido` com `ana@x.com` | emito convite para `ana+1@x.com` | convite criado |
| A-10 | Spec §3.1 | positivo | um convite pendente para `bia@x.com` | emito outro para o mesmo e-mail | dois convites pendentes, com tokens diferentes |
| A-11 | Spec §2, §15 | negativo | um comprador e um fornecedor autenticados; um visitante anônimo | enviam `GET` e `POST` para `/administracao/convites/` | 403 para os autenticados e redirecionamento para `/entrar/` para o anônimo; nenhum convite |
| A-12 | Spec §2 | negativo | um comprador como `autor` | chamo `emitir_convite` diretamente | `PermissionDenied`; nada gravado |
| A-13 | Infra 4.3 | fronteira | um convite emitido em `T` | consulto a situação em `T + 24h − 1 ms`, em `T + 24h` e em `T + 24h + 1 ms` | `pendente`, `expirado`, `expirado` |
| A-14 | Spec §14 | positivo | um convite com `consumido_em` preenchido, por fábrica | consulto a situação e a lista | `consumido`, com a conta criada exibida |
| A-15 | Spec §13 | positivo | três convites (pendente, expirado e consumido) | o administrador abre a lista | os três aparecem do mais recente para o mais antigo, com e-mail, papel, fornecedor, emissão e expiração em America/Sao_Paulo e situação |
| A-16 | Spec da fatia | negativo | um `Convite` criado por SQL direto com papel `administrador`, e outro com papel fornecedor sem fornecedor | executo os `INSERT` | o banco recusa os dois |
| A-17 | Spec da fatia | positivo | uma emissão válida | consulto a auditoria | uma entrada `convite.emitir` com autor administrador e alterações contendo o `id` do convite, o papel e o fornecedor, sem o e-mail e sem o token |
| A-18 | Spec da fatia | negativo | uma emissão válida dentro de uma transação que depois é desfeita (teste de serviço) | inspeciono a caixa de saída e o banco | nenhum e-mail e nenhum convite |
| A-19 | Spec da fatia | negativo | o backend de e-mail configurado para levantar erro no envio | o administrador emite um convite válido | o convite existe; a tela mostra a mensagem de falha no envio; o log capturado não contém o e-mail nem o token |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-10, A-17 a A-19 | `tests/tecnicos/test_convites_emissao.py` |
| A-11, A-12 | `tests/tecnicos/test_convites_permissoes.py` |
| A-13 a A-15 | `tests/tecnicos/test_convites_consulta.py` |
| A-16 | `tests/tecnicos/test_convites_modelo.py` |
| A-7 (cenário 80, emissão) | também marcado `acceptance`, com o comentário `cenário 80` |
