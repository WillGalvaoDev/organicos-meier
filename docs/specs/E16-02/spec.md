# E16-02 — Arquivos enviados no Cloudflare R2

Fatia 2 de 8 da milestone **E16 — Homologação e encerramento da fase 1**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E16-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E16-01.

## Contexto e objetivo

Hoje os arquivos enviados ficam em `MEDIA_ROOT`, no disco local. São dois tipos:
- o avatar da conta (`Conta.avatar`, E02);
- o comprovante da devolução excepcional (`ConfirmacaoDeDevolucaoExcepcional.comprovante`, E10).

No Fly.io o disco da máquina é efêmero: um arquivo enviado se perderia na próxima implantação. A infraestrutura 2 põe arquivos e comprovantes no Cloudflare R2, e a seção 5 exige que os comprovantes tenham acesso restrito ao administrador. As views atuais já servem os dois arquivos com controle de acesso, lendo pelo `storage`. Esta fatia troca só o armazenamento, em homologação e produção.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 2 | Cloudflare R2 para avatares, comprovantes de devoluções excepcionais e aportes, e backup externo. |
| Infraestrutura 5 | Comprovantes no R2 com acesso restrito ao admin; segredos só em variáveis do provedor. |
| Especificação §9.5 e §13 | Devolução excepcional com comprovante; perfil com avatar. |
| E02 (avatar) e E10 (comprovante) | Views `avatar` (a própria conta ou o administrador com passkey) e `comprovante` (só administrador), que leem o arquivo e o devolvem com `FileResponse`. |

## Escopo

**Dentro:** o armazenamento padrão (`STORAGES["default"]`) em `prod.py`, apontado para um bucket privado do R2 pela API compatível com S3, e o comportamento das duas views com esse armazenamento.

**Fora:**
- o backup do banco, que usa outro bucket (E16-04);
- a migração de arquivos antigos: não há arquivo em ambiente remoto antes desta fatia;
- a criação do bucket e das credenciais (E16-08).

## Regras

1. **Armazenamento:** em `prod.py`, `STORAGES["default"]` usa o backend S3 do `django-storages` com:
   - `endpoint_url` = `R2_ENDPOINT` (`https://<conta>.r2.cloudflarestorage.com`);
   - `bucket_name` = `R2_BUCKET_ARQUIVOS`;
   - credenciais `R2_ACCESS_KEY_ID` e `R2_SECRET_ACCESS_KEY`;
   - região `auto`.

   As quatro variáveis são obrigatórias em `prod.py`, sem padrão. Em `dev.py` e `test.py`, o armazenamento continua o do sistema de arquivos local.
2. **Privado:**
   - sem ACL pública (`default_acl = None`) e sem URLs públicas;
   - `querystring_auth = True`, para que uma eventual chamada a `.url` gere link assinado com validade de 5 minutos, nunca um link permanente;
   - nenhum template ou view passa a usar `.url` desses campos: os arquivos continuam servidos só pelas views `avatar` e `comprovante`, com o controle de acesso atual.
3. **Nomes:** os prefixos atuais (`avatares/` e `comprovantes/`) são mantidos.
   - `file_overwrite = False`: dois arquivos com o mesmo nome não se sobrescrevem; o segundo recebe um nome único.
   - O nome gravado não contém dado pessoal além do que o fluxo atual já grava. O nome original do comprovante continua no campo `comprovante_nome` e não vai para a chave do objeto.
4. **Leitura:** as views abrem o arquivo pelo `storage`, como hoje. Objeto ausente no bucket resulta em 404, como `FileNotFoundError` hoje no avatar. No comprovante, o mesmo caso passa a dar 404, em vez de erro 500.
5. **Falha do R2 no envio:** se o upload falhar (erro de rede ou de credencial), a ação do usuário não é gravada pela metade.
   - **Avatar:** o perfil não é salvo, e a página mostra "Não foi possível enviar o arquivo. Tente de novo." com 503.
   - **Comprovante:** a confirmação da devolução excepcional não é registrada (a transação é desfeita), e a página responde 503 com a mesma mensagem. Nenhuma baixa de obrigação acontece sem o comprovante gravado (E10).
6. **Logs:** falhas do R2 registram a operação e a classe do erro, sem chave de acesso, URL assinada nem nome do arquivo.

## Decisões técnicas

- **`django-storages` (com `boto3`).** É o backend padrão de Django para S3 e compatíveis. O R2 fala a API S3, e a E16-04 reaproveita o `boto3`. Dependência nova, com necessidade demonstrada.
- **`moto` só nos testes.** Ele simula a API S3 em memória, o que permite testar o backend real sem rede nem credenciais. Dependência só de desenvolvimento.
- **Bucket próprio para arquivos.** Os backups ficam em outro bucket, com outra chave (E16-04). Assim a credencial da aplicação web não lê os backups, e a do backup não lê os comprovantes (menor privilégio).
- **Aportes.** A infraestrutura cita "comprovantes de aportes", mas os aportes (E09) não têm arquivo hoje. Não há o que migrar, e nenhuma regra nova é criada aqui.

## Invariantes

- O acesso aos arquivos continua o de hoje: avatar para a própria conta e para o administrador com passkey; comprovante só para o administrador.
- Nenhum arquivo fica público.
- Uma confirmação de devolução excepcional nunca fica registrada sem o comprovante gravado.

## Dependências e decisões em aberto

- Depende da E16-01 (`prod.py` e imagem), da E02 (avatar) e da E10 (comprovante).
- Novas dependências: `django-storages[s3]` (produção) e `moto[s3]` (desenvolvimento).
- Nenhuma decisão em aberto.
