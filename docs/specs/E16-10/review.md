# E16-10 — Parecer independente

## Gate de especificação — 2026-11-18 — 696a378

**APROVADO para execução da fatia documental.** Escopo: `spec.md`, A-1 a A-5 de `acceptance.md` e as redações propostas para E08-02 A-12/A-21 e E09-08 A-3. M-3 e M-8 ainda não estão encerradas por este gate.

Conferidos: funcional §5.1; E05-06 (aviso de preço); política `comprador_ativo` e ordem das verificações da E02-10; regra de entrada sem separador de milhar da E09-08; M-3/M-8 e decisão do responsável registrada em `docs/melhorias.md`; regra 10 da E16-08. As correções alinham critérios com regras superiores, sem mudar permissão, notificação ou comportamento financeiro.

- **A-1:** distingue a recusa por etapa do comprador da recusa por papel do administrador. Também distingue preço alterado antes do congelamento, com avisos devidos, do preço alterado depois, sem mudar pedidos nem avisar as parcelas congeladas. Texto anterior preservado.
- **A-2:** troca apenas a entrada `1.000,00` por `1000,00`; apresentação monetária pode continuar com separador de milhar. Negativos do formulário permanecem exigidos, e o texto anterior está preservado.
- **A-3:** exige leitura das asserções e execução dos três arquivos indicados. Os corpos dos testes de ordem de preço contêm os destinatários A/B antes e ausência de avisos depois; o teste de aporte usa `1000,00`. O teste de recusa do administrador aceita status 302/403; essa tolerância não altera o contrato da política, que exige 403 para outro papel autenticado. O implementador deve conferir também a política e as provas existentes pertinentes, conforme a regra 2, sem declarar que esse assert isolado demonstra toda a redação. Se faltar prova exigida, deve registrar a lacuna e devolver, como a própria fatia determina; não afrouxar a regra nem reescrever teste silenciosamente.
- **A-4:** conferir o diff atribuído à fatia E16-10. `696a378` reúne também E16-07/E16-09 e encaminhamento de R07; esses arquivos têm outros escopos declarados e não são mudanças de produção ocultas da E16-10. Registrar a base e os caminhos examinados, sem afirmar que o commit agregado inteiro contém apenas os arquivos da E16-10.
- **A-5:** mover M-3/M-8 para encerradas somente após a revisão de conclusão da entrega, com execução registrada e referência ao commit. A aprovação da especificação não antecipa esse encerramento.

A exceção de TDD é adequada ao escopo exclusivamente documental: nenhum comportamento novo, nenhum teste a alterar. O implementador ainda deve executar os testes e registrar a correspondência exigida; o gate não substitui essa evidência.

Verificações realizadas: leitura das fontes, dos critérios alterados, dos corpos de testes citados e do diff de `b4d2a64..696a378`; nenhum teste executado neste gate. Não foram modificadas especificações, testes ou produção pelo revisor. Nenhum achado impeditivo de especificação. Próximo passo: registro da verificação e execução pelo implementador, seguido de revisão independente de conclusão e encerramento das melhorias. R07 depende ainda das demais evidências operacionais da E16-08.
