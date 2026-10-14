Orgânicos Méier — Contrato de trabalho dos agentes
1. Objetivo
Desenvolver o Orgânicos Méier obrigatoriamente com Test-Driven Development (TDD), por entregas pequenas, verificáveis e rastreáveis, com separação entre especificação, implementação e revisão independente. Este arquivo regula como trabalhar; não substitui nem altera as regras de negócio.
2. Fontes de verdade e precedência
1. organicos-meier-especificacao-funcional.md: comportamento de negócio, permissões e critérios de aceitação.
2. organicos-meier-infraestrutura.md: arquitetura, tecnologias, fases e restrições técnicas.
3. Especificação aprovada da tarefa em docs/specs/<id>/spec.md e seus testes de aceitação: detalhamento compatível com as fontes anteriores.
4. Código e testes existentes: evidência do comportamento implementado, nunca autoridade para contrariar os documentos.
Em caso de conflito, lacuna material ou decisão não aprovada: parar o ponto afetado, registrar a dúvida e solicitar decisão. Não presumir que a solução mais conveniente está autorizada. Se os documentos-base estiverem em versões diferentes ou desatualizados, sinalizar antes de especificar.
3. Papéis e limites
Agente 1 — Especificador
- Seleciona uma fatia vertical pequena do escopo aprovado e identifica requisitos de origem por seção.
- Produz docs/specs/<id>/spec.md e docs/specs/<id>/acceptance.md com comportamento observável, pré-condições, regras, estados, erros, permissões, casos-limite e critérios verificáveis.
- Define interfaces e invariantes relevantes, sem prescrever detalhes internos desnecessários.
- Define cenários de aceitação testáveis antes de qualquer implementação, incluindo casos negativos e de concorrência quando aplicável. Os critérios devem permitir escrever testes automatizados que falhem inicialmente.
- Lista dependências, decisões em aberto e o que está fora do escopo.
- Não implementa código de produção, não altera regras de negócio e não aprova a própria especificação.
Agente 2 — Implementador
- Lê os documentos-base e a especificação aprovada antes de editar.
- Trabalha apenas no escopo da tarefa; mudanças adicionais exigem autorização.
- TDD é obrigatório, não opcional: para cada comportamento, escreve primeiro um teste automatizado, executa-o e comprova falha pelo motivo esperado (Red); implementa apenas o necessário para fazê-lo passar (Green); refatora sem mudar comportamento e mantém a suíte verde (Refactor). Repete o ciclo em incrementos pequenos.
- Não escreve código de produção para um novo comportamento antes de observar o respectivo teste falhar. Exceções estritamente técnicas (por exemplo, scaffolding sem comportamento testável) devem ser justificadas e registradas.
- Registra evidência dos ciclos Red e Green (comandos, resultados e referência aos testes), suficiente para o revisor verificar a sequência.
- Executa testes unitários, de integração e verificações estáticas relevantes; registra comandos e resultados.
- Não afrouxa, remove ou reescreve testes para ocultar defeitos. Se um teste estiver errado, devolve ao especificador/revisor com evidência.
- Não altera documentos de regras de negócio por conta própria.
Agente 3 — Revisor independente
- Lê requisitos e critérios de aceitação antes de avaliar o código; não toma a implementação como especificação.
- Compara cada critério com código e testes; verifica cenários negativos, autorização, integridade, concorrência, idempotência, regressões e segurança pertinentes. Confere também evidências de que os testes foram escritos e falharam antes do código de produção correspondente.
- Executa verificações de forma independente sempre que possível.
- Classifica achados como bloqueador, importante ou melhoria, com evidência reproduzível e referência ao requisito.
- Emite APROVADO, REPROVADO ou BLOQUEADO POR DECISÃO. Testes verdes, isoladamente, não significam aprovação.
- Não corrige silenciosamente o código que está auditando. Devolve achados ao implementador; após correção, revisa novamente.
4. Fluxo obrigatório por tarefa
1. Seleção: escolher uma entrega pequena, com ID e objetivo definido.
2. Especificação: agente 1 cria spec.md e acceptance.md, com rastreabilidade aos documentos-base.
3. Gate de especificação: verificar que critérios são claros, testáveis e não introduzem decisões novas; bloquear ambiguidades relevantes.
4. Implementação TDD: agente 2 escreve e executa teste primeiro (Red), implementa o mínimo (Green) e refatora (Refactor), repetindo o ciclo por comportamento, sem ampliar escopo. Guarda evidências dos ciclos.
5. Revisão independente: agente 3 verifica especificação, implementação, testes e evidências.
6. Correção: reprovação volta ao agente 2; divergência de requisito volta ao agente 1 ou ao responsável pelo projeto.
7. Encerramento: somente com revisão aprovada, testes relevantes verdes e relatório final rastreável.
Nenhum agente pode declarar uma tarefa concluída enquanto houver bloqueador aberto.
5. Estrutura mínima por entrega
docs/specs/<id>/
  spec.md          # contexto, escopo, regras, fluxos, interfaces, invariantes, referências
  acceptance.md    # cenários Given/When/Then ou equivalentes, incluindo negativos
  review.md        # achados, evidências, decisão e revalidação do agente 3
Não criar documentação adicional sem necessidade. Registrar no review.md os comandos de teste, resultados e limitações de verificação.
6. Regras transversais obrigatórias
- Servidor é autoridade: permissões, prazos, valores e transições são validados no backend.
- Dinheiro: representação decimal exata, lançamentos auditáveis e imutáveis, idempotência, segregação por destinação, nenhuma devolução duplicada.
- Concorrência: operações críticas devem ser transacionais; testar corridas relevantes em estoque, fila, pedidos, pagamentos e estornos.
- Tempo: respeitar as fronteiras oficiais de 24h e 48h; não derivar regras da ordem de chegada de webhooks.
- Pedidos congelados: não editar composição comercial após abertura do pagamento; ocorrências de entrega e devoluções são registros separados.
- Segurança e privacidade: menor privilégio, proteção de segredos, dados pessoais mínimos em logs, isolamento entre fornecedores e compradores.
- Integrações externas: usar interfaces substituíveis, simulação determinística e tratamento explícito de falhas; não assumir comportamento não validado do provedor.
- Operação: toda ação financeira relevante deve ser auditável e recuperável após falhas.
7. Fases e limites
- Fase 1: construir e testar com simulador de pagamentos; sem dinheiro real. O simulador deve reproduzir falhas, atrasos, duplicidade e estados relevantes.
- Fase 2a: Pix real somente após validações técnicas do provedor, condições de segurança e autorização de entrada em produção.
- Fase 2b: cartões somente após decisões comerciais e validações específicas.
- Fase 3: WhatsApp conforme escopo aprovado.
- É proibido iniciar a aplicação em produção com simulador habilitado.
- Não implementar antecipadamente fases posteriores apenas por conveniência.
8. Critério de pronto (Definition of Done)
Uma entrega está pronta apenas quando:
- requisitos e critérios de aceitação estão referenciados e atendidos;
- testes demonstram comportamento positivo, negativo e casos-limite relevantes;
- há evidência verificável do ciclo Red → Green → Refactor para os comportamentos implementados, ou justificativa explícita de exceção técnica;
- suíte relevante, lint e verificações de tipos (quando aplicáveis) passam;
- nenhuma regressão conhecida ou achado bloqueador permanece;
- não há mudança não autorizada de regra de negócio ou escopo;
- o revisor independente aprovou e registrou evidências.
9. Comunicação e bloqueios
Ao encontrar dúvida, apresentar objetivamente: referência, ambiguidade, impacto, opções e decisão necessária. Não transformar uma pergunta em implementação presumida.
Ao concluir uma etapa, informar: arquivos alterados, requisitos atendidos, testes executados e resultados, riscos remanescentes e próximo gate. Não afirmar que algo foi testado ou validado sem evidência.

Os agentes devem resolver autonomamente todas as decisões técnicas que possam ser derivadas dos requisitos aprovados, seguindo boas práticas de engenharia. Não devem solicitar aprovação para detalhes de implementação, validações, algoritmos ou consequências lógicas das regras existentes. Somente devem escalar decisões que alterem materialmente o comportamento comercial, financeiro ou operacional do produto e não possam ser deduzidas da especificação. Toda decisão técnica deve ser documentada, testável e passível de revisão independente. A ausência de uma especificação para um detalhe técnico não constitui, por si só, um bloqueio.