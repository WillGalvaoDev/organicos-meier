# E15-02 — Registro do implementador

Agente 2.

## Red

- Commit `e207368`: `uv run pytest tests/tecnicos/test_alertas_operacionais.py` → 14 falhas e 1 passando. O A-8 (alerta financeiro como antes) já passava: é guarda de regressão. As demais falham pela ausência de `apps.operacao.verificacao`, do tipo `tarefa_atrasada` e da tarefa `verificar_operacao`.

## Green

- `apps/operacao/tipos.py`: `Natureza`, `Classificacao`, registro dos tipos, `link_do_alerta` e `natureza_do_alerta`.
- `apps/operacao/verificacao.py`: `registrar_verificacao`, `VERIFICACOES`, `verificar_operacao_agora` (uma transação por verificação, registros que faltam criados no começo).
- `apps/operacao/atraso_de_tarefa.py`: o tipo e a verificação de `tarefa_atrasada`; `apps/operacao/tarefas.py`: a tarefa `verificar_operacao` (`*/5 * * * *`, `queueing_lock`), com a entrada "Verificação operacional" (5 e 15 min) no catálogo.
- `apps/financeiro/alertas.py`: `abrir_alerta` aceita os tipos operacionais (gravidade, título, corpo e link da classificação) e emite `Evento.ALERTA_OPERACIONAL`; os financeiros seguem iguais. `apps/financeiro/models.py` (tipo `tarefa_atrasada`) e `apps/notificacoes/eventos.py` (evento só do administrador, site e e-mail); migrações `financeiro` e `notificacoes`.
- Resultado: `15 passed` neste arquivo.

## Desvios e pontos para o revisor

1. **Arranjo AO inviável (especificação).** O AO pede ADM1 e ADM2 ativos e ADM3 suspenso. O banco admite um único administrador e sempre ativo (`conta_administrador_unico` e `conta_administrador_ativo`, `apps/contas/models.py`; funcional §1: "Há um único administrador"). Os testes usam só ADM1 e conferem uma notificação e um e-mail para ele; "nada para ADM3" não tem o que conferir, e "uma notificação por administrador" (A-12) vira uma para ADM1. O A-9 ("sem administrador ativo") roda sem nenhum administrador. **Devolvido ao especificador**: ajustar o AO (ou decidir mudar a regra do administrador único, decisão do responsável). O código percorre todos os administradores ativos e não depende do número.
2. **Teste da E09-03 atualizado.** `test_o_catalogo_do_evento_novo` (A-11 da E09-03) comparava o conjunto de eventos do administrador com dois eventos; a regra 3 desta fatia cria um terceiro, só do administrador. Acrescentei `Evento.ALERTA_OPERACIONAL` ao conjunto esperado, mantendo a igualdade. Mudança exigida pela spec, não afrouxamento.
3. **Corpo do `tarefa_atrasada` e os dados.** A regra 9 tem dois corpos (com e sem conclusão anterior), mas os dados listados não dizem qual vale. Para não acrescentar campo aos dados, `_corpo` consulta o `ExecucaoDaTarefa` (`ultima_conclusao_em` nulo). Se o revisor preferir um campo em `dados`, é uma mudança pequena; sem decisão comercial.
4. **Ponto de pausa do A-12.** O teste pausa depois de `abrir_alerta` chamado pela verificação (`apps.operacao.verificacao.abrir_alerta`). No teste A-6 e A-7 as verificações de teste entram por substituição do dicionário `VERIFICACOES`.
5. **Segundo teste existente atualizado.** `test_a_matriz_de_canais_e_a_da_especificacao` (E04-01) transcreve a matriz de eventos; acrescentei a linha `("alerta_operacional", administrador, {site, e-mail})`, pela regra 3 desta fatia. Nenhuma asserção foi removida.

## Verificação

- Suíte completa antes deste ajuste: 3296 passed e 1 failed (este teste); depois, `tests/tecnicos/test_notificacoes_eventos.py` e `test_financeiro_alertas.py` passam. `mypy .` (513 arquivos) e `ruff` limpos.
6. **Ajuste feito na E15-04.** Com a verificação de notificações atrasadas (E15-03) o `test_a_tarefa_que_para_de_novo_abre_outro_alerta` (A-4) deixou de poder contar o retorno `(1, 0)` nem todas as notificações do administrador: os e-mails dos primeiros avisos ficam pendentes e abrem `envios_atrasados`. O teste passou a conferir só o alerta `tarefa_atrasada` e as notificações com esse título. (A suíte completa acusou a falha; o arquivo isolado passava.)

## Ajuste do especificador (commit e8c967a)

O A-12 pede também um `Envio` de e-mail para ADM1. Acrescentei a asserção ao teste da corrida (guarda: passou de primeira). Os desvios de administrador único e das matrizes de eventos já estavam registrados aqui e agora são regra da spec.


## Revisão independente — agente 3 — 2026-11-16

Referência auditada: `2f5958c`, branch `e15-especificacoes`, sobre `8b1739f` (E14). Foram lidos os documentos-base (funcional v1.7 e infraestrutura v1.8), as sete especificações e matrizes E15 e os registros Red/Green, antes da comparação com código e testes. Este parecer acrescenta-se ao registro do implementador, preservado integralmente. Evidências globais e código das reproduções estão em [E15-07/review.md](../E15-07/review.md).

**Veredito da fatia: REPROVADO.** Matriz A-1 a A-15 confrontada com implementação e testes; unicidade de alerta/notificação/Envio permanece íntegra na corrida reproduzida, mas há dois requisitos não atendidos.

### R01 — importante — a verificação acusa a própria execução

- Requisito: spec.md, regra 10: “A verificação não se acusa”; seu atraso aparece no painel e no monitor externo.
- Código: `apps/operacao/atraso_de_tarefa.py:30` percorre todo o catálogo, incluindo `verificar_operacao`; `apps/operacao/tarefas.py:14` só registra a conclusão depois da verificação.
- Reprodução: concluir todas as tarefas em I; avançar 16 minutos e concluir as outras; executar `verificar_operacao(0)`. Abre alerta `tarefa_atrasada:verificar_operacao` embora a execução termine normalmente. Esperado: nenhum alerta sobre a própria tarefa, mantendo a leitura do atraso no painel.
- Impacto: aviso operacional falso na retomada do monitor. Acrescentar regressão dessa retomada, além do cenário de seis minutos já existente.

### R02 — importante — contagem de aberturas incorreta na concorrência

- Requisito: spec.md, regra 6, retorno de quantos alertas a execução abriu; concorrência de A-12.
- Código: `apps/operacao/verificacao.py:62` lê `ja_aberto` antes da tentativa de abertura e incrementa com base nessa leitura anterior à disputa pelo UNIQUE.
- Reprodução: o mesmo arranjo e pausa de A-12 (`Corrida.depois_de(..., 'abrir_alerta')`), somando os retornos. Duas execuções devolvem `(1, 0)` cada, mas o banco contém um só alerta. Esperado: uma execução contabiliza a abertura e a outra zero.
- Não houve duplicação do alerta ou da notificação: o defeito é o resultado público da verificação. A-12 não verifica esse retorno.

TDD: testes em `e207368`, produção em `088335c`; registro Red 14 falhas e um caso preexistente passando. Cronologia e alterações conferidos; não reexecutado Red histórico.

## Correções R01 e R02 (implementador, 2026-11-16)

- **Red observado** (`uv run pytest tests/tecnicos/test_alertas_operacionais.py`): 5 falhas nos testes A-16 a A-20 (A-16: alerta com a chave `verificar_operacao`; A-17: idem; A-18: o alerta antigo não era resolvido; A-19: as duas execuções devolviam `(1, 0)`; A-20: as duas devolviam 1 resolvido). Os testes e o Green ficaram no mesmo commit.
- **Green (R01):** `atraso_de_tarefa._verificar` ignora `verificar_operacao`; `situacao_das_tarefas` não mudou. O alerta antigo sai pela regra 6 (a chave não volta).
- **Green (R02):** `abrir_alerta_informando_criacao` (E09, `apps/financeiro/alertas.py`) devolve `(alerta, criado)`, e `abrir_alerta` o reaproveita sem mudar a assinatura nem o retorno. `verificacao.abrir_alerta` (função fina, ponto de pausa dos testes) conta só o `criado`. `resolver_alerta` passou a resolver com `UPDATE ... WHERE resolvido_em IS NULL` e devolve `None` se outra execução resolveu antes.
- A-18: o retorno não é conferido (o e-mail pendente do alerta gravado abre `envios_atrasados`); confere-se o alerta, como a spec pede.


## Revalidação independente das correções — agente 3 — 2026-11-16

Código auditado: `f42e08d`, branch `e15-especificacoes`. Delta desde o parecer `2d909d6`: especificação `63285a5`, produção/testes `46e178b`, `812a91a`, `1dfb6e0` e integração/registro `f42e08d`. Os documentos-base e o parecer anterior continuam como referência; os novos requisitos foram lidos antes do delta de código. Registro anterior preservado integralmente. Resultados compartilhados em [E15-07/review.md](../E15-07/review.md).

**APROVADO. R01 e R02 encerrados.** A-1 a A-20 reexecutados, inclusive as provas originais do revisor.

- R01: o detector ignora `verificar_operacao`; a retomada não cria alerta/notificação próprios. A chamada direta conserva o registro atrasado para a leitura do painel. Alerta legado é resolvido pela ausência da chave, com o motivo previsto. A integração de retomada longa também passou.
- R02: a criação informa se houve inserção real; o retorno público de `financeiro.abrir_alerta` permanece o alerta, preservando seus chamadores. A resolução usa UPDATE condicionado a `resolvido_em IS NULL`: quem perde a corrida devolve `None`. As corridas comprovam uma só abertura e uma só resolução contabilizadas; os testes financeiros anteriores também passaram.
- Escopo conferido: notificações e validações continuam na mesma transação, sem duplicação ou alteração de dados financeiros.

TDD: o registro do implementador informa Red antes de Green no mesmo commit `46e178b`. Reapliquei os testes atuais ao código anterior (`2d909d6`) em worktree e bancos isolados: A-16, A-17, A-19 e A-20 falharam pelos motivos esperados; no código atual passaram. A-18 passou também no código anterior: no teste atual, `concluir_todas` deixa a própria verificação em dia antes de verificar. Portanto, esta reprodução comprova quatro falhas, e A-18 funciona como guarda; não confirma a declaração de cinco falhas do registro. Isso não invalida a correção nem a evidência Red dos comportamentos. A reprodução verifica a capacidade discriminante dos testes, não o instante histórico em que o implementador os executou.
