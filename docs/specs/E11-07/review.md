# E11-07 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Comandos com os arquivos de teste inteiros, sem `-k`: `uv run pytest tests/tecnicos/test_apuracao_telas.py tests/tecnicos/test_pedidos_apuracao_do_comprador.py`.

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-12 e A-17 (administrador) e A-13 a A-16 (comprador) | `2e5c00c` | **Red: 16 failed, 1 passed.** Sem o bloco "Apuração final" na página da rodada; as duas rotas respondem 404 (`404 == 409/503/302/405`); o painel da margem mostra "Não pago" e não "Cancelado (falta de pagamento)"; o pedido do comprador não traz "Cancelado por falta de pagamento" nem as frases da caixa incompleta e do retorno. **A-16 passou** (regressão: o comprador não vê dado de outro nem o mínimo; a recusa do pedido de outro comprador já existia) |
| `bloco_da_apuracao` e `efeitos_da_apuracao_no_pedido` (`apps/pedidos/apuracao_tela.py`), rotas `apuracao/iniciar/` e `apuracao/aprovar/` (`exige_reautenticacao_por_passkey`, só POST), `inadimplencia` no painel, textos do pedido | commit da fatia | **17 passed** |

## Decisões técnicas

- **Qual apuração o bloco mostra.** A do último ciclo da rodada que tem abertura de pagamento. Isso mantém o bloco com a rodada de volta em `interesse` e o faz sumir quando um novo pagamento é aberto (o novo ciclo ainda não tem apuração e, em `pagamento`, mostra o horário ou o botão).
- **Rótulos no singular** dos grupos da lista de devoluções em `ROTULO_DO_GRUPO_NO_SINGULAR` (`devolucoes_views.py`), para o estorno aparecer como "Pendente de autorização".
- **503 na aprovação.** A spec fixa a mensagem do início; para a aprovação usei "Não foi possível consultar o provedor; o resultado não foi aprovado. Tente de novo." (a mesma ideia, sem dizer que nada foi apurado).
- A página mantém o HTML simples das demais telas do administrador; sem estilo novo.

## Riscos remanescentes e limites de verificação

- A aprovação com a consulta ao provedor bloqueada não tem critério de tela na spec; coberta pelo serviço (E11-06 A-5).


## Parecer independente — agente 3 — 2026-10-31

Base auditada: `1a36495`, branch `e11-implementacao`, comparada à base E10 integrada `1b9bf07`. Leitura dos documentos-base (funcional v1.7 e infraestrutura v1.8), spec/acceptance das oito fatias, implementação, testes e registros de TDD. O conteúdo anterior deste arquivo foi preservado integralmente. Evidências e reproduções completas no [parecer consolidado da E11-08](../E11-08/review.md).

**Sem achado próprio nos cenários A-1 a A-17; aprovação da etapa não concedida.** Conferidas as rotas POST, autorização administrativa e nova autenticação por passkey, 409/503, disponibilidade por prazo, apresentação do resultado, links de devolução, situação do comprador e isolamento de dados. As mensagens de fila/reservas não correspondem ao estado real nos casos R01/R02, originados nas fatias de restauração; devem ser revalidadas junto dessas correções.

A mensagem específica de 503 na aprovação evita afirmar que nada foi apurado depois de já existir apuração: adaptação técnica coerente, sem mudar a regra de bloqueio. TDD: `2e5c00c → 33c0cd2`, registros conferidos. Não foi feita inspeção visual em navegador; evidência de tela nesta revisão é leitura de templates/rotas e testes HTTP da suíte.

## Correções da revisão (textos ao comprador) — agente 2 — 2026-11-01

Comando: `uv run pytest tests/tecnicos/test_pedidos_apuracao_do_comprador.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-18 a A-21 | `be1b362` | **Red: 4 failed.** A-18: o texto afirma interesses reservados; A-19 e A-20: `Reservado: 6` e `Pendente: 4` ausentes do carrinho (parcela `removida`); A-21: "fila de pendentes" presente sem restauração |
| `efeitos_da_apuracao_no_pedido` lê o registro da apuração: `RestauracaoDeCaixa` para a frase da fila e a auditoria `removidas_por_conta_impedida` para a frase dos interesses reservados | `ee1a720` | 8 passed no arquivo |

A tela não deduz nada da situação atual da conta.


## Revalidação independente das correções — agente 3 — 2026-11-01

Base auditada: `0af24ad`, branch `e11-implementacao`; correções desde o parecer `3aa8858` sobre `1a36495`. Requisitos corrigidos em `732b7bb`, código, testes e registros Red/Green confrontados. Conteúdo anterior preservado. Evidências e prova residual no [parecer consolidado E11-08](../E11-08/review.md).

**REPROVADO — manifestação de R02 residual (importante), sem novo número de achado.** A-18 passa no arranjo com parcelas ainda `em_pedido`, mas não cobre a conta cujas parcelas já foram removidas pela suspensão. Nesse caso, `_conta_impedida_no_retorno` lê uma lista vazia e `efeitos_da_apuracao_no_pedido` retorna `interesses_reservados=True`, embora a reserva seja zero, contrariando o adendo R02 desta spec. A prova parametrizada no consolidado reproduz tela e aviso. Correções de R01 e da mensagem de caixa sem restauração validadas. Sem inspeção visual em navegador; evidência de tela por código e testes.
