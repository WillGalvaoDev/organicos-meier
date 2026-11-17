# Relatório da fase 1

Relatório final da fase 1 (E16-08). **Versão provisória:** a homologação ainda não foi executada, então o critério de saída da fase 1 **não** pode ser declarado atingido (regra 12 da E16-08). Cada seção diz o que já existe e o que falta.

## Resumo

O critério de saída da fase 1 **ainda não foi atingido**: a implantação na homologação, o roteiro funcional, o teste de restauração cronometrado e a revisão das melhorias com o responsável não foram executados, porque dependem das contas da fase 0 e de decisões do responsável (ver "Pendências para a fase 2a" e `docs/specs/E16-08/review.md`).

## Critério de saída

Itens da infraestrutura 7 para a fase 1:

| Item | Resultado | Evidência |
|---|---|---|
| Cenários 1–119 passando contra o simulador | Matriz pronta (E16-07): todos os cenários têm teste. A execução da suíte no commit final da `main` está pendente. | `docs/rastreabilidade-fase1.md` e o CI |
| T-1–T-55 passando, com evidência Red → Green | Matriz pronta (E16-07). As evidências Red e Green estão nos `review.md` de cada fatia; o registro do commit final está pendente. | `docs/rastreabilidade-fase1.md` e `docs/specs/*/review.md` |
| Teste de restauração realizado | **Não realizado.** O comando `conferir_restauracao` e o procedimento existem (E16-05). | `docs/operacao/restauracao.md` |

## Etapas entregues

| Etapa | PR | Reprovações | Observação |
|---|---|---|---|
| E01 a E04 | a consolidar | a consolidar | pareceres nos `review.md` de cada fatia |
| E05 | #65 a #69 | a consolidar | correções R01 a R05 |
| E06 | #70 a #77 | a consolidar | |
| E07 | #78 | a consolidar | |
| E08 | #79 | a consolidar | |
| E09 | #81 | a consolidar | |
| E10 | #83 | 2 | |
| E11 | #84 | 2 | |
| E12 | #85 | 1 | |
| E13 | #86 | 1 | |
| E14 | #87 | 1 | |
| E15 | #88 | 2 | aprovada com a exceção de TDD autorizada pelo responsável |
| E16 | em andamento | — | E16-01 a E16-07 implementadas; E16-08 bloqueada |

As contagens de reprovação das E01 a E09 não foram consolidadas neste rascunho: o levantamento nos pareceres entra na versão final.

## Homologação

Não executada. O que existe: o `Dockerfile`, o `fly.toml`, a rota `/saude/`, o armazenamento no R2, o Sentry, o backup externo cifrado e o procedimento de restauração (E16-01 a E16-05). O documento de operação é `docs/operacao/homologacao.md`. Faltam: as verificações de implantação (regra 3), o roteiro funcional pelas telas com o simulador (regra 4) e o isolamento entre compradores e fornecedores (regra 5), todos com evidência no `review.md` da E16-08.

## Recuperação

- **RPO:** minutos pela restauração do Neon e até 24 horas pelo backup externo (infraestrutura 6).
- **RTO:** a definir depois do primeiro teste cronometrado (`docs/operacao/restauracao.md`).
- **Próximo teste trimestral:** a definir depois do primeiro teste.

## Melhorias

A revisão das melhorias pendentes com o responsável (regra 10) não foi feita. As pendentes estão em `docs/melhorias.md`; o especificador apresenta cada uma com uma recomendação e o responsável decide.

## Exceções e limitações

- **Exceções de processo aprovadas:** a exceção de TDD da E15 (aprovada pelo responsável, commit `7181c67`).
- **L-13** da infraestrutura (limitação registrada na seção 9.2).
- **Lacunas do simulador:** M-12 (recusa definitiva de cancelamento e consulta com valor divergente).
- **Limites da fase 1:** só o simulador de pagamentos, sem dinheiro real e sem produção; o WhatsApp fica desligado.

## Pendências para a fase 2a

- Limitações L-1 a L-4 e L-6 a L-11 (infraestrutura 9.2) e as verificações registradas na milestone 16.
- Saída do sandbox do SES.
- Domínio próprio, Cloudflare e limite de requisições nas rotas de login e convite (E16-01).
- Procedimentos de suporte e de incidentes (especificação §15).
- Avaliação de LGPD dos fluxos para fora do país (infraestrutura 5): SES, Sentry e Cloudflare/R2, com o que é enviado a cada um.
- Orientação do contador e aporte inicial.
- Executar a E16-08: implantação, roteiro, teste de restauração cronometrado (caminhos A e B), suíte no branch de testes do Neon e revisão das melhorias.

## Custos

Os custos observados serão registrados depois da implantação, na seção "Custos observados" de `docs/operacao/homologacao.md`, e comparados com a estimativa de US$ 8–15 por mês da infraestrutura 10.
