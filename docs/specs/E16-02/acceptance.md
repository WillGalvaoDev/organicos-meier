# E16-02 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo R2S:**
  - um bucket `arquivos-teste` simulado pelo `moto` (`mock_aws`);
  - `STORAGES["default"]` sobrescrito no teste com a configuração que `prod.py` monta. A configuração é extraída para uma função ou constante reaproveitável, para que o teste use exatamente a de produção.
- **Contas:** o administrador ADM autenticado com passkey (como na E10), o comprador C e outro comprador D.
- **Ambiente fictício (AF):** o da E16-01.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 1 | positivo | AF com `R2_ENDPOINT`, `R2_BUCKET_ARQUIVOS`, `R2_ACCESS_KEY_ID` e `R2_SECRET_ACCESS_KEY` | carregar `config.settings.prod` em subprocesso | `STORAGES["default"]["BACKEND"]` é o backend S3 do `django-storages`, com o bucket, o endpoint e a região `auto` do ambiente. **Red esperado:** o backend é o do sistema de arquivos |
| A-2 | Regra 1 | negativo | AF sem cada uma das quatro variáveis, uma de cada vez | carregar | falha de configuração nas quatro; a mensagem não contém o valor de nenhuma chave |
| A-3 | Regra 1 | positivo | `config.settings.test` | ler `STORAGES["default"]` | o armazenamento do sistema de arquivos, como antes |
| A-4 | Regras 2 e 3 | positivo | R2S; C envia um avatar pelo perfil | ler o objeto no bucket | a chave começa com `avatares/`; o objeto não tem ACL pública (`get_object_acl` sem concessão a `AllUsers`); `default_acl` é `None` e `querystring_auth` é `True` na configuração |
| A-5 | Regra 4 | positivo | o A-4 | `GET` do avatar como C; como ADM com passkey | 200 com o conteúdo enviado e `Cache-Control: private, no-store` nos dois |
| A-6 | Regra 4 | negativo | o A-4 | `GET` do avatar de C como D; como ADM sem prova de passkey | 404 nos dois |
| A-7 | Regra 3 | positivo | R2S | dois envios de avatar com o mesmo nome de arquivo, por C e por D | duas chaves diferentes no bucket; cada avatar devolve o próprio conteúdo |
| A-8 | Regras 2 a 4 | positivo | R2S; uma devolução excepcional confirmada por ADM com um comprovante PDF chamado `Comprovante Maria.pdf` | `GET` do comprovante como ADM | 200, anexo com o nome `Comprovante Maria.pdf` e o tipo gravado; a chave do objeto começa com `comprovantes/` e não contém "Maria" |
| A-9 | Regra 4 | negativo | o A-8 | `GET` do comprovante como C | 403, como hoje |
| A-10 | Regra 4 | negativo | o A-8 com o objeto apagado do bucket; o A-4 com o objeto apagado | `GET` como ADM | 404 nos dois. **Red esperado:** 500 no comprovante |
| A-11 | Regra 5 | negativo | R2S com o upload forçado a falhar (`ClientError` no `put_object`) | C envia um avatar | 503 com "Não foi possível enviar o arquivo. Tente de novo."; o avatar de C inalterado no banco; nenhum objeto novo |
| A-12 | Regra 5 | negativo | R2S com o upload forçado a falhar; uma obrigação elegível à devolução excepcional | ADM confirma com comprovante | 503 com a mesma mensagem; nenhuma `ConfirmacaoDeDevolucaoExcepcional`, nenhum movimento e a obrigação ainda devida; nenhuma auditoria da confirmação |
| A-13 | Regra 6 | negativo | o A-11 e o A-12 | ler os logs capturados | um log por falha, com a operação e `ClientError`; nenhum contém a chave de acesso, o segredo, uma URL assinada (`X-Amz-Signature`) nem o nome do arquivo |
| A-14 | Regra 2 | negativo | o repositório | procurar `.avatar.url` e `.comprovante.url` nos templates e no código de `apps/` | nenhuma ocorrência |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-3 | `tests/ambiente/test_homologacao.py` |
| A-4 a A-14 | `tests/tecnicos/test_arquivos_no_r2.py` |
