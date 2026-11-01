# E12-06 — Registro da implementação (agente 2, 2026-11-01)

Comandos: `uv run pytest tests/tecnicos/test_cancelamento_telas.py tests/tecnicos/test_cancelamento_do_comprador.py` (arquivos inteiros, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-19 | `7fc01ec` | **Red: 19 failed, 2 passed.** Rota inexistente (404 em vez de 302/400/405/409/503), página sem o bloco, `views.cancelar_rodada` inexistente, devolução sem o texto do cancelamento, pedido do comprador sem as frases. **Passaram de primeira (regressão):** A-17 (outro comprador recebe 404) e A-19 (carrinho sem a rodada cancelada, com o pendente) |
| Rota `rodadas_cancelar`, `cancelamento_tela.py`, blocos em `estoque.html` e `detalhe.html`, texto das devoluções do cancelamento, "Cancelado (rodada cancelada)" | `4a07358` | **21 passed**; suíte completa **2892 passed**; `ruff`, `mypy`, `makemigrations --check` limpos |

## Decisões técnicas
- A rota recusa qualquer campo fora de `reembolso`, `mensagem` e o CSRF, com 400, antes de chamar o serviço.
- Rodada cancelada: o bloco "Pedidos" lista os da abertura mais recente; as devoluções vêm das obrigações de motivo `cancelamento_da_rodada`.
- Devolução do cancelamento sem parcela: "Autorizada pelo cancelamento da rodada · aguardando cobertura" ou "· aguardando o envio ao provedor"; o botão "Autorizar" some, as ações de cobertura (em outras telas) não mudam.
- Pedido de rodada cancelada: o parágrafo "Pague até…" é omitido.

## Ajustes de testes (autorizados pelo conflito entre critérios; sem afrouxar o resto)
- **E03 A-25** (`test_rodadas_estoque.py::test_409_do_servico_e_pagina_so_de_leitura_com_a_etapa_relida`) exigia nenhum formulário na página só de leitura. A E12-06 (regra 4) manda mostrar o formulário de cancelamento em toda etapa cancelável, inclusive `fechamento`. A asserção passou a excluir só as ações com `/cancelar/`. **Ponto para o especificador.**
- Nos testes das telas o administrador entra de novo depois de cada avanço do relógio (padrão da E11-07).
- A-13 usa o prefixo `/administracao/financeiro/devolucoes/`.


## Parecer independente — agente 3 — 2026-11-01

Base auditada: `8e236e5`, branch `e12-implementacao`, comparada à E11 integrada em `d098654`. Funcional v1.7, infraestrutura v1.8, especificações e critérios das sete fatias lidos antes da avaliação da implementação. Conteúdo anterior preservado integralmente. Evidências, veredito da etapa e reproduções no [parecer consolidado E12-07](../E12-07/review.md).

**REPROVADO — R01 (importante).** A-1 a A-19 confrontados com rotas, templates e testes HTTP; controles de acesso, reautenticação, campos extras, isolamento e tratamento de falhas passam. Após retorno ao interesse seguido de cancelamento, a página do pedido renderiza simultaneamente o cancelamento e a frase antiga de que os interesses continuam reservados. A reserva real é zero. A integração de `cancelamento` e `apuracao` precisa distinguir histórico de estado atual, preservando os registros financeiros. Referências: funcional §7/§7.2, E12-01 regra 6 e E12-06 regra 7. Não houve inspeção visual em navegador.
