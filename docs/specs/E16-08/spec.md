# E16-08 — Homologação executada e relatório final da fase 1

Fatia 8 de 8 da milestone **E16 — Homologação e encerramento da fase 1**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E16-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E16-01.

## Contexto e objetivo

As E16-01 a E16-07 deixam a aplicação implantável e observável, com backup, procedimento de restauração e matriz de evidências. Esta fatia executa a homologação e fecha a fase 1:
- implantar no Fly.io com o Neon, o R2, o SES, o Sentry e o Better Stack;
- percorrer o roteiro de homologação com o simulador;
- fazer o teste de restauração cronometrado;
- rodar a suíte inteira;
- revisar as melhorias com o responsável;
- escrever o relatório final, que diz se o critério de saída da fase 1 foi atingido.

É uma fatia de operação e documentação. O código de produção só muda para corrigir um defeito que a homologação revelar, e esse defeito vira achado com especificação própria (regra 9).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 7, fase 1 | Ambientes de desenvolvimento e homologação; critério de saída: cenários 1–119 e T-1–T-55 passando contra o simulador, com evidências; teste de restauração realizado. |
| Infraestrutura 6 | Teste de restauração cronometrado, repetido todo trimestre; RTO definido depois dele. |
| Infraestrutura 9.2 e 9.3 | Limitações L-1 a L-13 e validações sem relação com pagamentos (região do Neon, saída do sandbox do SES), pendentes para a fase 2a. |
| Infraestrutura 5 | Avaliação de LGPD dos dados processados fora do país (SES, Sentry, Cloudflare). |
| Especificação §15, Operação | Procedimentos de suporte, incidentes, atualização e recuperação antes do lançamento; controle de custo. |
| Milestone 16 | Homologação no Fly.io com branch do Neon, Sentry e monitor de disponibilidade, backup diário no R2 e teste de restauração cronometrado, execução completa da suíte e relatório final; revisão das melhorias com o responsável antes do relatório; verificações para a fase 2a. |

## Pré-requisitos operacionais (fase 0)

O responsável fornece, antes da execução:
- as contas no Fly.io, no Neon (projeto em `aws-sa-east-1`), no Cloudflare (R2), na AWS (SES em `sa-east-1`), no Sentry e no Better Stack;
- um cliente OAuth do Google para a homologação, com o endereço de retorno no domínio `*.fly.dev`;
- os endereços de e-mail verificados no SES, que ainda está em modo sandbox, para os testes de envio.

Sem eles, a fatia fica **bloqueada por dependência**, sem decisão comercial: o implementador registra o que falta no `review.md` e não implanta.

## Regras

### Implantação e configuração

1. **`docs/operacao/homologacao.md`**, com estas seções, nesta ordem:
   1. **"Componentes":** o app, a região, os processos e o tamanho das máquinas; o branch do Neon; os dois buckets do R2 (arquivos e backups) e a regra de ciclo de vida de 35 dias no de backups; o domínio de e-mail do SES; o projeto do Sentry; o monitor do Better Stack.
   2. **"Variáveis e segredos":** a lista completa (E16-01 regra 9, E16-02, E16-03 e E16-04), com o significado e a origem de cada uma, sem nenhum valor.
   3. **"Implantar e atualizar":** os comandos `fly deploy`, a migração pelo `release_command` e como voltar para a versão anterior (`fly releases` e a imagem anterior).
   4. **"Monitoramento":**
      - o monitor do Better Stack em `/saude/` a cada 3 minutos;
      - os monitores de cron do Sentry (`verificar-operacao`, `backup-diario`);
      - para quem vai cada aviso: o e-mail do responsável.
   5. **"Credenciais e menor privilégio":**
      - a credencial do bucket de arquivos não lê o de backups, e a de backups não lê o de arquivos;
      - a chave privada do `age` não fica no Fly.io (E16-05).
   6. **"Custos observados":** o custo mensal de cada serviço no período da homologação, comparado com a infraestrutura 10, linha a linha: Fly.io de US$ 8–15; Neon de US$ 5–20; SES, R2, Sentry, Better Stack e Cloudflare de US$ 0–2; e total fixo de US$ 15–35 por mês. A faixa de US$ 8–15 é só a do Fly.io, nunca a do total (correção da revisão de 2026-11-17).
2. **Implantação:** o app de homologação é implantado a partir do commit da `main` que contém as E16-01 a E16-07, com `AMBIENTE=homologacao` e o simulador.
3. **Verificações da implantação**, cada uma com a evidência (comando e saída, ou captura) no `review.md`:
   1. `/saude/` responde 200 por HTTPS, e o monitor do Better Stack está verde;
   2. a página de login carrega com os estáticos (WhiteNoise), sem erro no console;
   3. um erro de teste provocado chega ao Sentry com o ambiente `homologacao` e sem dado pessoal. O evento é aberto e conferido contra a regra 3 da E16-03;
   4. os monitores `verificar-operacao` e `backup-diario` aparecem no Sentry com check-ins `ok`;
   5. `fly scale count worker=0` por 20 minutos gera o aviso do monitor `verificar-operacao` por e-mail. Depois, o worker volta e o monitor normaliza. É a prova do herdado da E15;
   6. um avatar enviado vai para o bucket de arquivos e não abre por URL pública;
   7. o backup diário automático das 03:00 roda pelo menos uma vez: o objeto aparece no bucket de backups e a linha aparece no painel;
   8. um e-mail de convite chega a um endereço verificado no SES.

### Roteiro de homologação

4. **Roteiro funcional** pelas telas da homologação, com o simulador (`administracao/simulador-pagamentos/`) e o relógio real:
   - convite e cadastro de um comprador e de um fornecedor;
   - login por senha, link e Google;
   - produto com múltiplo; interesse de dois compradores; mínimo atingido;
   - fechamento de 24 horas; abertura do pagamento; pagamento pelo simulador (um aprovado e um inadimplente);
   - margem; apuração; aprovação; pedido formal por e-mail; repasse;
   - recebimento; liberação; retirada; uma ocorrência de entrega com devolução;
   - painel, alertas e histórico.

   O roteiro leva vários dias por causa dos prazos reais (24 horas de fechamento, 24 de pagamento e 24 de margem), e cada passo é registrado com data, hora e resultado.
5. **Isolamento:** no roteiro, o comprador e o fornecedor tentam abrir o painel, o histórico, o simulador e o pedido do outro comprador, e recebem recusa.

### Restauração

6. **Teste cronometrado:** o roteiro da E16-05 (regra 7) é executado pelos caminhos A (Neon) e B (backup externo).
   - Cada execução é registrada na tabela "Registro dos testes" de `docs/operacao/restauracao.md`.
   - O RTO é preenchido pela regra 6.10 da E16-05.
   - `conferir_restauracao` sai com código 0 nas duas execuções. Se sair com `FALHA`, é achado.

### Suíte e evidências

7. **Suíte:**
   - a suíte completa roda no CI no commit final da `main`, com o resultado (número de testes, duração) registrado;
   - a suíte roda também uma vez com `DATABASE_URL` apontando para um branch do Neon dedicado a testes, com conexão direta e `sslmode=require`, para confirmar a compatibilidade com o banco gerenciado. Uma falha específica do Neon é achado.
8. **Matriz:** o documento `docs/rastreabilidade-fase1.md` (E16-07) é citado no relatório como a evidência dos cenários e dos testes técnicos.

### Achados

9. **Defeito na homologação:** o implementador registra o achado no `review.md` (passo, esperado, obtido, evidência) e devolve ao especificador. A correção segue o fluxo normal, com especificação e TDD. Nenhuma correção é feita direto no ambiente nem fora do repositório.

### Melhorias

10. **Revisão das melhorias** (decisão do responsável de 2026-10-20):
    - o especificador apresenta ao responsável cada melhoria pendente de `docs/melhorias.md`, com uma recomendação: tratar antes do encerramento, tratar na fase 2a ou descartar;
    - a decisão do responsável é registrada em `docs/melhorias.md`. A descartada vai para "Encerradas" com o motivo, e a adiada fica pendente, com a fase indicada;
    - uma melhoria a tratar antes do encerramento vira fatia própria (E16-09 em diante), especificada e revisada no fluxo normal.

### Relatório final

11. **`docs/relatorio-fase1.md`**, com estas seções, nesta ordem:
    1. **"Resumo":** se o critério de saída da fase 1 foi atingido, em uma frase.
    2. **"Critério de saída":** uma linha por item da infraestrutura 7, com o resultado e a evidência:
       - cenários 1–119: a matriz da E16-07 e o CI;
       - T-1–T-55: a matriz e as evidências Red/Green nos `review.md`;
       - teste de restauração: `restauracao.md`.
    3. **"Etapas entregues":** E01 a E16, com o PR e o número de reprovações de cada uma. As fontes são a nota de entrega de cada milestone e os pareceres nos `review.md`. Uma etapa sem número registrado nessas fontes é marcada como "não registrado", sem estimativa.
    4. **"Homologação":** as verificações da regra 3, o roteiro da regra 4, o isolamento da regra 5 e o endereço de `homologacao.md`.
    5. **"Recuperação":** RPO, RTO medido e a próxima data do teste trimestral.
    6. **"Melhorias":** o resultado da regra 10.
    7. **"Exceções e limitações":**
       - as exceções de processo aprovadas pelo responsável (por exemplo, a exceção TDD da E15);
       - a L-13;
       - as lacunas do simulador (M-12);
       - os limites da fase 1: só simulador e sem produção.
    8. **"Pendências para a fase 2a":**
       - L-1 a L-4 e L-6 a L-11;
       - as verificações registradas na milestone 16;
       - saída do sandbox do SES;
       - domínio próprio, Cloudflare e limite de requisições nas rotas de login e convite (E16-01);
       - os procedimentos de suporte e de incidentes (§15);
       - a avaliação de LGPD dos fluxos para fora do país (infraestrutura 5): SES, Sentry e Cloudflare/R2, com o que é enviado a cada um;
       - a orientação do contador;
       - o aporte inicial.
    9. **"Custos":** os custos observados e a comparação com a infraestrutura 10, com as mesmas faixas da regra 1.6.
12. **Bloqueador aberto:** o relatório só afirma que o critério de saída foi atingido sem bloqueador aberto nem achado importante pendente (AGENTS.md §8). Senão, ele diz o que falta.
13. **README:** o PR desta fatia atualiza a Parte 1 nas duas línguas (AGENTS.md §10). A fase passa a "Fase 1 encerrada", se a regra 12 permitir, e o próximo passo é "Fase 2a (preparação)".

### Correções da revisão de 2026-11-17 (E16-R07)

14. **Testes de pendência:**
    - enquanto a fatia estiver bloqueada por dependência, os testes dos A-3 e A-4 podem ficar como `xfail(strict=True)`, com o motivo citando o pré-requisito que falta;
    - esses testes não contam como critério atendido e não podem estar na matriz da E16-07;
    - antes de a fatia ir para revisão de aprovação, os dois `xfail` são retirados, e os testes passam sem marca.
15. **Ordem do encerramento:**
    - a execução das regras 2 a 7 só começa depois de as correções E16-R01 a E16-R06 estarem aprovadas pelo revisor;
    - a implantação usa o commit que contém essas correções;
    - o relatório e os documentos de operação já escritos são corrigidos nos custos (regras 1.6 e 11.9), mesmo antes da execução.

## Decisões técnicas

- **Roteiro com o relógio real.** O prazo de pagamento é improrrogável e não pode ser alterado por nenhuma rota (T-5). Encurtar prazos na homologação exigiria código só para isso e um caminho que não existe em produção. Os prazos curtos já são exercitados com o relógio controlado nos testes. A homologação verifica a implantação real, as tarefas e os avisos ao longo de dias reais.
- **Suíte num branch do Neon.** O CI usa o Postgres 17 em contêiner. Uma rodada no Neon confirma que travas, `LISTEN/NOTIFY` e triggers se comportam igual no banco gerenciado, sem tornar o CI dependente de um serviço externo.
- **Relatório como documento versionado.** É a evidência pedida pelo critério de saída e fica junto com as especificações que ele cita.

## Invariantes

- Nenhum segredo nos documentos ou no `review.md`.
- O simulador continua recusado em produção; a homologação usa `AMBIENTE=homologacao`.
- O relatório não declara a fase 1 encerrada com bloqueador ou achado importante aberto.

## Dependências e decisões em aberto

- Depende das E16-01 a E16-07 e dos pré-requisitos operacionais acima.
- **Decisões do responsável previstas na própria fatia:** as da revisão das melhorias (regra 10), por decisão de 2026-10-20. Não há decisão comercial em aberto para especificar a fatia.
