# E11-05 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Comandos com o arquivo de teste inteiro, sem `-k`: `uv run pytest tests/tecnicos/test_apuracao_retorno.py`.

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-17 (apoio `limites=(11, 12)`) | `67e5bd2` | **Red: 15 failed, 2 passed.** A rodada continua em `pagamento`; parcelas `em_pedido`/`pendente` em vez de `ativa`; nenhum `Reembolso` integral; sem aviso; `DID NOT RAISE RuntimeError` (A-10); `InteressesBloqueados`/`CondicoesCongeladas` nos A-11 a A-14; `_restaurar_as_reservas_dos_pagantes` inexistente (A-15). **A-6 e A-16 passaram** (regressões: nada é apurado no livro; os motivos da E06 continuam exigindo o fechamento encerrado) |
| `voltar_para_interesse` aceita `pagamentos_insuficientes` a partir de `pagamento` (e só com ele); `_restaurar_as_reservas_dos_pagantes`, `_conferir_o_estoque`, `_devolver_integralmente`, `_avisar_o_retorno`, auditoria `retorno` | commit da fatia | **17 passed** |

## Decisões técnicas

- Etapa diferente do motivo gera a recusa `fora_de_pagamento` (mensagem própria); os motivos da E06 mantêm `fora_de_fechamento_encerrado`.
- A conferência do estoque usa `total_reservado` depois da restauração e antes do retorno (que atende a fila), com o estoque já travado pela E11-01.

## Ponto para o especificador (A-3 não é atingível como escrito)

O A-3 espera a parcela de A em P1, depois da apuração, `ativa` com reservado 6 e **pendente 2**. Mas a regra 4 da própria fatia manda `voltar_para_interesse` atender a fila (`alocar_pendentes`), e o inadimplente B libera 5 unidades de P1: o pendente de A, o mais antigo, recebe as 2 (R-5). O resultado, com ou sem limite, é reservado 8 e pendente 0. Implementei as regras e o teste afirma os dois momentos: (1) a restauração, sozinha, deixa a reserva igual à parte congelada (6) com a pendência intacta (2), que é o que o A-3 quer provar do E08-02; (2) o retorno inteiro, ativa com 8 e 0. Peço que o A-3 seja corrigido (por exemplo, afirmar só a restauração).

## Riscos remanescentes e limites de verificação

- **Conta suspensa ou removida (A-17):** a parcela `em_pedido` dela fica `em_pedido`, ainda contada em `total_reservado`, depois de a rodada voltar ao interesse. A spec manda só não restaurar. Um interesse de conta suspensa segurando estoque numa rodada em interesse parece indesejável; não alterei o comportamento. Decisão do especificador.

## Defeito achado depois pela E11-08 (corrigido)

A devolução integral de mais de um pedido pago na mesma apuração tinha o mesmo defeito da E11-04 (`OrdemDeTravasViolada`). Teste: `test_dois_pagantes_recebem_a_devolucao_integral_na_mesma_apuracao` (Red `3066566`). A correção é a mesma: o conjunto das contas de todos os pagantes é travado antes da primeira devolução.
