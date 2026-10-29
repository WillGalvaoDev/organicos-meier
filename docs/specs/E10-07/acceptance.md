# E10-07 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:**
- O arranjo da E10-04: X pago por P1 e O1 de 31,25 com o motivo `ocorrencia_de_entrega`.
- O administrador ADM logado, com passkey recente nas ações.
- O comprador B (dono de X) e o comprador C (outro).
- O cliente de testes do Django.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §9.2, §13 | positivo | uma obrigação em cada situação: devida, `solicitada`, `falha_temporaria`, `em_processamento`, `falha_definitiva`, `elegivel_excepcional`, `concluida` e `concluida_fora_da_plataforma` | GET `financeiro/devolucoes/` | cada uma no seu grupo; valor, motivo, pedido e comprador visíveis; nas falhas, o código e as tentativas; o texto "Autorização não é dinheiro devolvido" |
| A-2 | §9.2 | positivo | O1 devida | POST `autorizar/` | redireciona ao detalhe com "Devolução solicitada ao provedor"; parcela `solicitada`; um aviso `estorno` "Estorno solicitado" para B, com o valor 31,25 e "Ocorrência na entrega" |
| A-3 | Infra 4.2 | negativo | ADM sem passkey recente | POST `autorizar/` | redireciona à reautenticação; nada gravado |
| A-4 | Permissão | negativo | B, um fornecedor e um visitante anônimo | cada rota de `financeiro/devolucoes/` | 403 para B e para o fornecedor; o login para o anônimo; nada gravado |
| A-5 | E10-04 A-4 | negativo | `indisponivel()` | POST `autorizar/` | status 503, com a mensagem de tentar de novo; nenhuma parcela |
| A-6 | §9.2 | negativo | O1 com 10,00 sem cobertura (variante depois da apuração) | POST `autorizar/` | status 409, com a mensagem de cobrir antes |
| A-7 | §9.2 | positivo | parcela em `falha_temporaria` | POST `tentar-de-novo/` | a chamada pendente com `proxima_em = agora`; redireciona ao detalhe |
| A-8 | Botões | negativo | parcela `concluida` | POST `tentar-de-novo/` e POST `excepcional/` forjados | 409 nos dois; nada muda |
| A-9 | §16 nº 35, §9.5 | positivo | parcela `elegivel_excepcional` | GET `excepcional/` e POST com meio, identificação, justificativa e um PDF | o formulário aparece; depois do POST, a parcela em `concluida_fora_da_plataforma`, a confirmação gravada e um aviso "Devolução realizada" para B, com "por Pix" e sem a identificação da transferência |
| A-10 | §16 nº 36 | negativo | parcela `em_processamento` | GET e POST `excepcional/` | 409, com "há devolução pendente na plataforma"; nada gravado |
| A-11 | Validação | negativo | parcela `elegivel_excepcional` | POST `excepcional/` com o comprovante ausente ou inválido | status 400, com a mensagem; nada gravado |
| A-12 | Segurança | positivo e negativo | o A-9 feito | GET `comprovante/` como ADM, B e C | ADM recebe o arquivo como anexo, com o tipo gravado; B e C recebem 403 |
| A-13 | §12, §13 | positivo | as obrigações do A-1, todas de pedidos de B, e uma de C | GET `pedidos/<X>/` como B | a seção "Estornos" com uma linha por obrigação de B, com o valor, o motivo e o texto de estado da tabela; nenhum código, evidência ou identificação; nenhuma obrigação de C |
| A-14 | Privacidade | negativo | o A-13 | GET `pedidos/<X>/` como C | 404 (a regra atual do detalhe), sem os estornos de B |
| A-15 | §12 | positivo | O1 autorizada e concluída pelo provedor (`processar_chamadas`) | ler os avisos de B | dois avisos `estorno`: "Estorno solicitado" e "Estorno concluído"; os dois com o link do pedido |
| A-16 | §12 | positivo | O1 levada a `elegivel_excepcional` pelo caminho real (E10-04 A-12) | ler os avisos de B | "Estorno solicitado" e "Estorno em andamento"; nenhum aviso para a falha temporária nem para a falha definitiva |
| A-17 | Idempotência | positivo | O1 | duas autorizações seguidas (duplo envio) | uma parcela e um aviso "Estorno solicitado" |
| A-18 | §12 | positivo | uma obrigação `duplicidade` (E09-04) de B, concluída | ler os avisos de B | "Estorno concluído", com "Pagamento em duplicidade" no corpo |
| A-19 | §12 | negativo | uma obrigação `sem_pedido` autorizada e concluída | ler todos os avisos | nenhum aviso `estorno` |
| A-20 | Atomicidade | negativo | um receptor de teste que levanta exceção depois da emissão do aviso, dentro da conclusão | processar a chamada | nenhum aviso gravado, a parcela não conclui e a chamada continua pendente; na execução seguinte, sem a falha, um aviso só |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-12 | `tests/tecnicos/test_devolucoes_telas.py` |
| A-13 e A-14 | `tests/tecnicos/test_pedidos_estornos_do_comprador.py` |
| A-15 a A-20 | `tests/tecnicos/test_devolucoes_avisos.py` |
| A-2, A-9 e A-10 | também `tests/aceitacao/test_cenarios_35_36_excepcional.py`, pelo fluxo da tela |
