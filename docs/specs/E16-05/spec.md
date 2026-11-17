# E16-05 — Restauração: conferência e procedimento com teste cronometrado

Fatia 5 de 8 da milestone **E16 — Homologação e encerramento da fase 1**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E16-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E16-01.

## Contexto e objetivo

A infraestrutura 6 define o que fazer depois de uma restauração:
- congelar as rodadas;
- conciliar pagamentos, devoluções e saldo;
- conferir o livro-razão e o estoque;
- reconferir com o extrato os aportes, repasses, retiradas de receita e devoluções excepcionais posteriores ao ponto recuperado;
- avisar quem foi afetado.

Ela também diz que o RTO só é definido depois de um teste de restauração cronometrado, repetido todo trimestre. O critério de saída da fase 1 (infraestrutura 7) exige esse teste.

Esta fatia entrega duas coisas:
- o comando `conferir_restauracao`, só de leitura, que reúne num relatório o que o operador precisa conferir;
- o procedimento escrito, com os dois caminhos de restauração (Neon e backup do R2) e o roteiro do teste cronometrado.

A execução do teste é da E16-08.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 6 | As três camadas, o procedimento depois de restaurar, prazos vencidos durante a indisponibilidade continuam valendo, RTO só depois do teste cronometrado, repetido todo trimestre. |
| Infraestrutura 7 | Critério de saída da fase 1: teste de restauração realizado. |
| Especificação §15, Operação | Backup e restauração verificável, com proposta de objetivos de recuperação; procedimentos de recuperação definidos antes do lançamento. |
| E09-03 | O invariante: saldo do provedor (liberado + a liberar) maior ou igual às obrigações de terceiros. |
| E15-05 | Os prazos encerrados do painel (regra 8). |
| E16-04 | O backup cifrado no R2, com a chave privada do `age` fora do servidor. |

## Escopo

**Dentro:**
- o comando `conferir_restauracao`;
- o documento `docs/operacao/restauracao.md`.

**Fora:**
- a execução do teste e o registro do RTO (E16-08);
- um modo de manutenção na aplicação (ver "Decisões técnicas");
- a conciliação com o Mercado Pago real (fase 2a).

## Regras

### Comando `conferir_restauracao`

1. **Só leitura:**
   - o comando não grava nada: nenhuma tabela, nenhum alerta, nenhuma auditoria, nenhuma tarefa enfileirada;
   - ele roda inteiro numa transação somente leitura (`SET TRANSACTION READ ONLY`). Uma tentativa de escrita durante a conferência é erro de programação e falha o comando;
   - a consulta de saldo ao provedor (simulador, na fase 1) é a única chamada externa.
2. **Seções do relatório**, nesta ordem, cada uma com o título e um resultado `OK`, `ATENÇÃO` ou `FALHA`:
   1. **"Ponto recuperado":** o instante (em Brasília) do último movimento do livro-razão, da última `EntradaAuditoria` e do último `BackupExterno`. É informativa: sempre `OK`.
   2. **"Invariante financeiro":** o saldo do provedor (liberado + a liberar), as obrigações de terceiros até o instante do saldo e a diferença, pela mesma regra da E09-03, mas sem abrir nem resolver alerta.
      - `OK` com diferença maior ou igual a zero;
      - `FALHA` com diferença negativa;
      - `ATENÇÃO` com "Provedor indisponível: conferir depois." quando a consulta falha.
   3. **"Estoque":** os produtos de rodadas não canceladas cujo total reservado passa do estoque, com o fornecedor, o produto, o reservado e o estoque. `FALHA` se houver algum; `OK` senão.
   4. **"Prazos encerrados":** as linhas da regra 8 da E15-05, no instante do comando. `ATENÇÃO` se houver alguma, com a frase "Prazos vencidos durante a indisponibilidade continuam valendo (infraestrutura 6)."; `OK` senão.
   5. **"Pendências com o provedor":**
      - a quantidade de `ChamadaAoProvedor` pendentes;
      - a de devoluções ainda não concluídas no provedor;
      - a de `Envio` pendentes.

      `ATENÇÃO` se alguma for maior que zero.
   6. **"Conciliação":** a data da última `ConciliacaoDiaria` e o número de dias encerrados ainda sem conciliação (E09-07). `ATENÇÃO` com um ou mais dias; `OK` senão.
   7. **"Reconferir com o extrato":** os últimos 20 movimentos dos tipos `aporte`, `repasse`, `pagamento_do_frete`, `retirada_de_receita` e `devolucao_excepcional`, do mais novo para o mais antigo, com data, tipo e valor. Sempre `ATENÇÃO` quando houver algum, com a frase "Movimentos registrados depois do ponto recuperado não estão aqui: conferir com o extrato e os comprovantes."; `OK` quando não houver nenhum.
3. **Resultado final:** a última linha é "Conferência: <n> falha(s), <m> atenção(ões)."
   - código de saída 1 com alguma `FALHA`;
   - código 0 sem `FALHA`, mesmo com `ATENÇÃO`.
4. **Privacidade:** o relatório não traz nome, e-mail ou WhatsApp de comprador, só identificadores internos, nomes de fornecedor, valores e datas. Ele também não traz segredo nem URL do banco.
5. **Opção `--antes-de <AAAA-MM-DDTHH:MM>`**, instante em Brasília: limita a seção 7 aos movimentos com `momento` anterior ao instante dado, para comparar com o extrato até o ponto escolhido. Instante inválido: "Instante inválido: use AAAA-MM-DDTHH:MM." e código de saída 2.

### Procedimento `docs/operacao/restauracao.md`

6. **Conteúdo mínimo**, nesta ordem:
   1. **Quando restaurar e quem decide:** o responsável.
   2. **Congelar:** o worker vai para zero máquinas (`fly scale count worker=0`) e o tráfego público é bloqueado antes da restauração. Sem o worker não há tarefas, prazos automáticos nem envios. Os prazos continuam valendo e são reconferidos depois.
   3. **Caminho A, Neon:** restauração a um instante, num branch novo, e troca do `DATABASE_URL` da aplicação para o branch restaurado (conexão direta, `sslmode=require`).
   4. **Caminho B, backup externo:**
      - localizar o objeto mais recente no bucket de backups;
      - baixar e decifrar com a chave privada do `age`, guardada pelo responsável fora do Fly.io;
      - criar um banco vazio (branch novo do Neon);
      - `pg_restore --no-owner --no-privileges`;
      - trocar o `DATABASE_URL`.
   5. **Conferir:** `fly ssh console` e `python manage.py conferir_restauracao`, com o que fazer em cada `FALHA` e `ATENÇÃO`.
   6. **Reativar:** o worker volta para uma máquina e o tráfego é liberado. Depois, o painel do administrador (E15-05) e os alertas são acompanhados até as tarefas ficarem "Em dia".
   7. **Avisar os afetados:** por comunicado (E04), quando a indisponibilidade ou a perda atingiu compradores ou fornecedores.
   8. **Guarda da chave privada:** onde fica, quem tem cópia e o que fazer se ela se perder. Nesse caso, os backups antigos ficam ilegíveis: gerar um par novo, trocar `BACKUP_CHAVE_PUBLICA_AGE` e fazer um backup na hora.
   9. **Teste cronometrado:** o roteiro da regra 7 e uma tabela "Registro dos testes" com as colunas data, caminho, ponto recuperado, início, fim, duração, resultado da conferência e observações.
   10. **RTO e RPO:**
       - RPO como na infraestrutura 6 (minutos pelo Neon e 24 horas pelo backup externo);
       - RTO preenchido depois do primeiro teste (E16-08): a maior duração medida, arredondada para cima para a meia hora seguinte;
       - repetição a cada trimestre.
7. **Roteiro do teste cronometrado** (executado em homologação, na E16-08):
   1. registrar um estado conhecido, com uma rodada passando por pagamento pelo simulador e uma devolução;
   2. anotar o instante `R`;
   3. criar depois de `R` um dado que não deve sobreviver (por exemplo, um comunicado);
   4. iniciar o cronômetro;
   5. restaurar pelo caminho A até `R`;
   6. rodar `conferir_restauracao`;
   7. confirmar que o dado posterior a `R` sumiu e que o estado conhecido está presente;
   8. parar o cronômetro quando a aplicação responder com os dados conferidos.

   Depois, repetir pelo caminho B com o backup mais recente.

## Decisões técnicas

- **Congelamento operacional, sem modo de manutenção.** Com o worker em zero máquinas e o tráfego bloqueado, nenhuma tarefa ou ação muda rodadas durante a conferência. Isso atende ao "congelar as rodadas" da infraestrutura 6 sem código novo em todas as views. A restauração é rara e feita pelo responsável com o procedimento à mão.
- **Comando só de leitura, com saída de erro só em `FALHA`.** As seções de `ATENÇÃO` pedem julgamento do operador, como a conciliação pendente ou os movimentos a reconferir. Só invariante violado e estoque estourado indicam estado incoerente que impede reativar.
- **Teste em homologação.** A fase 1 não tem produção (infraestrutura 7). O teste mede o procedimento e as ferramentas, que são os mesmos da fase 2a.

## Invariantes

- `conferir_restauracao` não grava em nenhuma tabela, nem alertas nem auditoria.
- O relatório não contém dados pessoais de compradores nem segredos.

## Dependências e decisões em aberto

- Depende das E09-03, E09-07, E15-05 e E16-04.
- Nenhuma dependência nova.
- Nenhuma decisão em aberto.
