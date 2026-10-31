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
