# E16-09 — Parecer independente

## Gate de especificação — 2026-11-18 — 696a378

**APROVADO para implementação.** Escopo: `spec.md` e A-1 a A-7 de `acceptance.md`. Não constitui aprovação de produção nem encerramento do cenário 96/R05.

Fontes conferidas: funcional §§2, 5.2, 13 e 16.96; E05-05; E11-08 A-6; E02-10 (política comprador); decisão do responsável de 2026-11-18 registrada na especificação, que escolhe valores atuais da mesma fonte do carrinho, inclusive sem pedidos. A decisão resolve a dúvida material levantada na revisão anterior, sem retirar o histórico do requisito. A seção adicional em “Meus pedidos” preserva o histórico dos pedidos e explicita que os interesses exibidos são atuais.

| Critério | Avaliação |
|---|---|
| A-1 | Estado 6 reservado/4 pendente, estoque livre zero, pendentes reais e consulta HTTP do histórico definidos; falha inicial observável pela ausência da seção. O arranjo da E11-08 deve ser adaptado para obter exatamente 6/4, não apenas reutilizado com seus números originais. |
| A-2 | Compara os valores das duas telas e cobre zero pendente; executar as leituras sem mudança concorrente de estado, conforme a condição “no mesmo instante” da regra 9. Não exige igualdade entre requisições separadas por uma alteração legítima. |
| A-3 | Pendente continua visível sem rodada ativa e com produto indisponível; inclui zero reservado e unidade. |
| A-4 | Consulta do comprador da sessão e tentativa de escolher outro comprador pela URL têm resultado negativo verificável. |
| A-5 | Estados sem pedido e sem interesse definidos independentemente. |
| A-6 | Política preservada e referenciada na E02-10: anônimo redirecionado, outros papéis recebem 403. Comprador suspenso continua autorizado à consulta pela política `comprador`; não trocar por `comprador_ativo`. É regressão, podendo passar antes da produção. |
| A-7 | Exibição sem ação de escrita e link ao carrinho; preservação de parcelas e registros verificável. |

As regras adicionais de título, ordem, nomes, unidade/formatação, fonte única e visibilidade por etapa são obrigatórias mesmo quando o critério da tabela não enumera cada detalhe. “Em qualquer etapa” refere-se às linhas retornadas pela consulta prevista nas regras 2 e 3; não autoriza incluir parcelas `em_pedido` ou mudar a composição do carrinho. A implementação deve manter a lista e os links de pedidos existentes e não introduzir escrita, migração ou nova política.

Conferida a viabilidade da interface pela leitura de `apps/interesses/consultas.py::carrinho_do_comprador`, da view de pedidos e da política especificada, depois dos requisitos. A consulta existente já permite reutilizar os dados sem novo cálculo. Nenhum achado impeditivo de especificação; nenhuma nova decisão comercial necessária.

Verificações: leitura documental e diff do commit; sem testes executados neste gate, sem alteração de produção. Próximo passo: implementador escreve e observa os testes falharem pela ausência do comportamento, implementa a seção e registra Red/Green/Refactor e regressões. A-6 é a exceção de regressão explicitamente prevista. Depois, revisão independente da implementação e ligação do teste aprovado na E16-07 A-44. A aprovação deste documento não basta para fechar C96.

## Registro do implementador — 2026-11-18

Agente 2. Implementação da E16-09 conforme `spec.md` e A-1 a A-7. Nenhuma migração, rota, serviço ou política nova.

### Red (observado antes do código de produção)

Comando: `uv run pytest tests/tecnicos/test_pedidos_historico_interesses.py tests/aceitacao/test_cenario_96_historico.py`.

- **A-1** (`test_cenario_96_historico_mostra_reservado_e_pendente_com_estoque_zerado`): falhou em `assert "Interesses reservados e pendentes" in texto`, depois de o arranjo confirmar 6 reservados e 4 pendentes reais de A e a caixa invalidada. Era o Red esperado (seção ausente).
- **A-2, A-3, A-4, A-5, A-7:** 5 falhas em `assert f"<h2>Interesses reservados e pendentes</h2>" in html` / título ausente do texto. Red esperado.
- **A-6** (`test_a_politica_da_rota_nao_mudou`): passou no Red, como a spec prevê (teste de regressão: a política não muda). Não há Red possível.

### Arranjo do A-1

O arranjo da E11-08 dá 6 reservados e 4 pendentes a C, e não a A, com A e C diferentes de 6/4. Para obter exatamente 6/4 em A, `montar_fp` de `tests/tecnicos/test_fila_ponta_a_ponta.py` ganhou o parâmetro `quantidades_de_p` (padrão `(6, 8, 6)`, igual ao anterior; os 99 testes da área seguem verdes). O teste usa `(10, 4, 6)` e a rodada nova com limite 6: A fica com Reservado 6 e Pendente 4, e `total_reservado(P)` igual ao limite (livre zero). `tests/conftest.py` ganhou o prefixo `test_cenario_96_` em `PREFIXOS_COM_SIMULADOR`, porque o arquivo da spec usa o simulador de pagamentos.

### Green

- `apps/pedidos/views.py::lista`: o contexto ganha `interesses = carrinho_do_comprador(comprador)`.
- `templates/pedidos/lista.html`: depois da lista de pedidos, `<h2>Interesses reservados e pendentes</h2>`, um `<h3>` por fornecedor, uma linha por produto com "Reservado: <x> <unidade>" e "Pendente: <y> <unidade>" (filtro `quantidade_br` e `get_unidade_display`), a mensagem "Você não tem interesses reservados nem pendentes." quando não há linhas e o link "Alterar no carrinho" para `/carrinho/`. Sem formulário, sem botão, sem escrita.

### Resultados

- Testes da fatia: 7 passed (A-1 a A-7).
- Regressão da área (telas do comprador, moderação, carrinho, fila ponta a ponta): 99 passed junto com os da fatia.
- Varredura de rotas e políticas (`test_permissoes_politica_rotas.py`): 15 passed.
- `ruff check`, `ruff format` e `mypy` limpos.

### Refactor

Nenhum necessário: a mudança é uma linha de contexto e o bloco do template.

### Limites

- O A-2 compara os pares (produto, reservado, pendente) lidos do HTML do carrinho e do histórico no mesmo estado do banco, sem alteração entre as leituras (gate: regra 9).
- A afirmação do histórico na matriz (E16-07 A-44) é ligada na correção da matriz, depois deste registro.
- A suíte completa roda ao fim do conjunto de fatias (registro na E16-07).

## Revisão independente da implementação — 2026-11-18 — 3e8b4ff

Revisado `6756ad2` e sua integração à matriz em `3e8b4ff`, contra a especificação aprovada no gate `bbe2775`. Escopo de produção limitado à view de lista e ao bloco de template. Não há alteração de modelo, serviço de escrita, cálculo de interesse, política ou migração.

| Critério | Evidência conferida |
|---|---|
| A-1 | `test_cenario_96_historico_mostra_reservado_e_pendente_com_estoque_zerado` usa apuração real com caixa invalidada e nova rodada de limite 6; confirma 6 reservados/4 pendentes, reembolso da caixa e total reservado 6 antes de GET `/pedidos/`. Verifica os dois valores na seção do histórico. |
| A-2 | Compara os pares extraídos do HTML das duas telas no mesmo estado, incluindo produto de outro fornecedor e zero pendente. Produção chama exatamente `carrinho_do_comprador(comprador)`, sem cálculo paralelo. |
| A-3 | Produto indisponível e fornecedor sem rodada ativa ainda aparecem com zero reservado/4 pendentes e unidade. O template não introduz filtro por estoque/etapa. |
| A-4 | Segundo comprador vê somente sua linha; o parâmetro `comprador` da URL não interfere. A view usa `request.user`; a consulta filtra pelo comprador. |
| A-5 | Sem pedidos, a mensagem anterior permanece; a seção distingue ausência de interesses de presença de pendentes. |
| A-6 | Anônimo redirecionado e fornecedor/administrador recusados com 403. Decorador `exige_comprador` preservado, mantendo também a consulta do comprador suspenso. |
| A-7 | Não há form/button na seção; link ao carrinho correto. Teste compara parcelas, auditorias e notificações antes/depois; a view acrescenta somente consulta e renderização. |

Título, posição depois dos pedidos, nomes de fornecedor/produto, ordenação da fonte, `quantidade_br`, unidade e escape padrão do template conferidos por leitura. Lista e links de pedidos existentes preservados. A troca do parâmetro auxiliar de `montar_fp` mantém o padrão anterior `(6, 8, 6)`; o caso novo usa `(10, 4, 6)` e não altera o arranjo dos testes anteriores. O prefixo do simulador em `conftest.py` é infraestrutura de teste coerente com o novo arquivo de aceitação.

Registro Red/Green confrontado com a versão anterior da view/template, que não tinha a seção: seis falhas relatadas por ausência do título e A-6 como regressão verde; implementação mínima correspondente. Não há necessidade de migração ou nova regra de negócio. O registro é a evidência histórica de ordem; a execução independente desta revisão confirma o comportamento final, sem alegar ter presenciado o Red original.

Nenhum achado novo nesta fatia. A ligação de C96 na E16-07 aponta para o teste efetivo do histórico, distinta das provas do carrinho. Resultados da suíte independente e conclusão final registrados ao término desta rodada, junto ao consolidado da E16-08.


### Conclusão — 2026-11-19

**APROVADO** sobre 3e8b4ff. Confirmados no JUnit os sete testes desta entrega: um em test_cenario_96_historico e seis em test_pedidos_historico_interesses, todos passando. Regressão completa: 3669 passed, 1 skipped, 2 xfailed; verificações estáticas e limites registrados na E16-08. A correção específica de C96 está atendida; a aprovação desta fatia não encerra os demais resíduos de R05 nem a E16.
