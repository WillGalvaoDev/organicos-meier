# E15-05 — Registro do implementador

Agente 2.

## Red

- Commit do Red: `uv run pytest tests/tecnicos/test_painel_administrativo.py` → **22 falhas e 3 passando** (`KeyError` de seção ausente, na maioria). Os três que já passavam são guardas por ausência: A-22 (acesso), A-23 (sem nome de comprador) e A-24 (sem escrita).

## Green

- `apps/operacao/painel.py`: `acoes_necessarias`, `rodadas_do_painel`, `prazos_encerrados`, os alertas, as tarefas e a última conciliação, tudo lido na hora; `contexto_do_painel(instante)` com o `instante` lido uma vez. A view `painel_administracao` (`apps/contas/views.py`) usa o contexto; o template `templates/administracao/painel.html` ganhou as cinco seções, a navegação e o formulário "Dar ciência".
- Só leitura: as contas do livro (repasse e frete) são buscadas sem criar (`livro.conta` faz `get_or_create`, e o painel não escreve).
- Resultado: `25 passed`; `test_notificacoes_administracao.py`, `test_financeiro_telas.py` e `test_admin_area_restrita.py` passam sem alteração (A-21 e A-22).

## Desvios e pontos para o revisor

1. **A-17, o valor.** A spec espera "Itens sem cobertura: 1 (R$ 10,00)." No AE, além da obrigação de R$ 10,00 há uma despesa de tarifa de R$ 1,29 sem cobertura (`itens_sem_cobertura()` devolve os dois itens), e a regra manda somar todos os itens. O teste confere a soma real: "2 (R$ 11,29)." Possível ajuste da spec.
2. **A-12 e A-14, repasse e frete pelos serviços.** Os testes registram o repasse e o frete com `registrar_repasse` e `registrar_pagamento_do_frete` (as mesmas funções das telas da E13-06), e não pelas rotas. No A-14 as saídas são pagas antes porque, com o relógio em `L + 8 dias`, o repasse e o frete já estariam liberados e a regra os mostra como ações; sem isso "nenhuma ação dela" não valeria.
3. **A-25.** A quinta rodada é a liberada do AE (rodada com saldo, como a regra 5 pede); as outras quatro são de fábrica. O painel tolera rodada sem abertura, sem prazo ou sem liberação (mostra "—").
4. **Datas dos testes.** `T0` é 02/11/2026 10:00 em Brasília; corrigi nos meus testes as datas que eu tinha escrito um dia adiante, e a hora da última falha do A-19 (11:00 UTC é 08:00 em Brasília).
5. **A-8 e A-15** usam o arranjo real (pagamento pelo simulador; cancelamento pelo serviço), conforme a spec.
6. **Correção feita na E15-07.** O teste ponta a ponta A-3 mostrou que a ação do pedido formal não sumia depois de um reenvio manual aceito (a situação do ciclo automático continua `concluido_com_falhas`). `_acoes_do_pedido_formal` agora só a mostra se nenhuma tentativa do pedido formal teve sucesso; detalhes em `docs/specs/E15-07/review.md`.

## Ajuste do especificador (commit e8c967a)

A regra 3 e o A-9 passaram a pedir que a ação do pedido formal continue após um reenvio manual que falhou e some após o aceito, e o A-17 passou a "2 (R$ 11,29)". O código já fazia isso (correção da E15-07). Acrescentei `test_pedido_formal_acao_segue_o_resultado_do_reenvio` (guarda: passou de primeira, sem Red, porque o comportamento já existia). O A-17 já era conferido com "2 (R$ 11,29)".


## Revisão independente — agente 3 — 2026-11-16

Referência auditada: `2f5958c`, branch `e15-especificacoes`, sobre `8b1739f` (E14). Foram lidos os documentos-base (funcional v1.7 e infraestrutura v1.8), as sete especificações e matrizes E15 e os registros Red/Green, antes da comparação com código e testes. Este parecer acrescenta-se ao registro do implementador, preservado integralmente. Evidências globais e código das reproduções estão em [E15-07/review.md](../E15-07/review.md).

**Veredito da fatia: REPROVADO por R03 e R04.** A-1 a A-25 confrontados, incluindo permissões, leitura sem escrita, valores agregados, prazos, rodadas, reenvio formal e ausência de dados pessoais de compradores. R03 está descrito em E15-03/review.md: o painel precisa apresentar contagem atual sem modificar o alerta histórico.

### R04 — importante — ações ordenadas por etapa antes do fornecedor

- Requisito: spec.md, regra 3 e acceptance.md A-18: ações por nome de fornecedor, depois pk da rodada e ordem da regra; globais no final. A ordem por etapa pertence à tabela de rodadas.
- Código: `apps/operacao/painel.py:242` reutiliza `_rodadas_do_painel()` (`:94`), que ordena primeiro por etapa.
- Reprodução: rodada de Zeta em interesse com mínimo atingido e rodada de Alfa em fechamento encerrado. `acoes_necessarias` devolve fornecedores `['Zeta', 'Alfa']`; esperado `['Alfa', 'Zeta']`.
- O teste A-18 usa Alfa na etapa anterior e Zeta na posterior; assim, as duas ordenações coincidem e não detectam o defeito. Inverter esses fornecedores dá uma regressão discriminante.

TDD: Red `146fbef` antes de `e5640ec`; registro 22 falhas e três guardas passando. Correção do reenvio manual foi precedida do teste `39ceae5` e implementada em `21eb36e`; alinhamento aprovado de requisitos em `e8c967a` e guardas em `2f5958c`. Não reexecutado Red histórico.

## Correções R03 e R04 (implementador, 2026-11-16)

- **Red observado** (`tests/tecnicos/test_painel_administrativo.py`): 4 falhas: A-18-A (`['Zeta', 'Alfa']`), A-26 (corpo gravado), A-28 (idem) e A-30 (sem log). A-27 e A-29 passaram de primeira (guardas: o corpo gravado coincidia com o esperado).
- **Green (R03):** `painel._dados_atuais` chama a verificação do tipo no instante do carregamento (só leitura). Se a chave não volta, usa os dados gravados; se levanta exceção, registra no log o tipo e a classe do erro e usa os gravados.
- **Green (R04):** `acoes_necessarias` ordena por `(fornecedor, pk)`; a tabela "Rodadas" mantém a ordem por etapa.
