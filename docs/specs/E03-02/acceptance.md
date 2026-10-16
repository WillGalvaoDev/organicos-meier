# E03-02 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Rodadas em etapas posteriores a `interesse` são criadas pela `RodadaFactory`, porque as transições ainda não existem. Os testes de concorrência usam `executar_em_paralelo` (E01-05) e `django_db(transaction=True)`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §4.3 | positivo | um fornecedor sem rodada | o administrador envia `POST .../rodadas/abrir/` | uma rodada em `interesse`, com `aberta_em = agora()` e `aberta_por` = administrador; auditoria `rodada.abrir`; o detalhe mostra a etapa |
| A-2 | Spec §4.3 | negativo | um fornecedor com rodada ativa em cada etapa ativa (`interesse`, `fechamento`, `fechamento_encerrado`, `pagamento`, `aguardando_fornecedor`), um caso por etapa | abro outra rodada | `RodadaAtivaExistente`, com a mensagem; continua uma única rodada ativa |
| A-3 | Spec §4.3 | positivo | um fornecedor cuja última rodada está `disponivel_para_retirada` e outro cuja última está `cancelada` | abro rodada para cada um | aceito nos dois; a rodada antiga não muda |
| A-4 | Spec §4.3 | negativo | o banco | insiro por SQL direto uma segunda rodada `interesse` para um fornecedor que já tem uma rodada `fechamento` | o banco recusa (índice único parcial) |
| A-5 | Spec da fatia | concorrência | um fornecedor sem rodada | duas chamadas de `abrir_rodada` em paralelo, repetidas 10 vezes com fornecedores novos | em todas: exatamente uma rodada ativa; uma chamada com sucesso e a outra com `RodadaAtivaExistente` |
| A-6 | Spec da fatia | negativo | um receptor de `rodada_aberta` que levanta erro | abro rodada | nenhuma rodada criada; nenhuma auditoria |
| A-7 | Spec da fatia | positivo | um receptor de teste de `rodada_aberta` | abro rodada | o receptor é chamado uma vez, com a rodada, dentro da transação (`in_atomic_block` verdadeiro) |
| A-8 | Spec §4.1, §4.4, cenário 71 | positivo | um fornecedor com mínimo R$ 150,00 e rodada em `interesse` | o administrador altera o mínimo para `200,00` | mínimo R$ 200,00; auditoria `fornecedor.alterar_minimo` com `anterior "150.00"` e `novo "200.00"` |
| A-9 | Spec §4.4, cenário 72, T-23 | negativo | o mesmo fornecedor com a rodada ativa em `fechamento`, `fechamento_encerrado`, `pagamento` e `aguardando_fornecedor`, um caso por etapa | o administrador envia o `POST` do mínimo; noutro teste, chamo `alterar_minimo` diretamente | 409 com a mensagem única pela rota; `CondicoesCongeladas` (`fora_de_interesse`) pelo serviço; mínimo inalterado; nenhuma auditoria |
| A-10 | Spec §4.1 | negativo | um fornecedor sem rodada ativa, e outro cuja última rodada está `disponivel_para_retirada` | altero o mínimo | 409 / `CondicoesCongeladas` (`sem_rodada_ativa`); nada gravado |
| A-11 | Spec da fatia | negativo | a rodada em `interesse` | envio mínimo `0`, `0,001` e `abc` | erro de formulário em cada um; nada gravado |
| A-12 | Spec da fatia | positivo | a rodada em `interesse` e mínimo R$ 150,00 | envio `150,00` | redirecionamento; nenhuma auditoria nova |
| A-13 | Spec da fatia | negativo | a rodada ativa em `fechamento` | abro `GET .../minimo/` | 200, com a mensagem única e sem formulário |
| A-14 | Spec §4.4 | concorrência | a rodada em `interesse` | uma thread trava fornecedor e rodada, grava `fechamento` e espera; `alterar_minimo` corre em outra thread; a primeira confirma ao ver a outra conexão esperando por trava (`pg_stat_activity`) | `CondicoesCongeladas`; mínimo inalterado; etapa `fechamento` |
| A-15 | Spec da fatia | concorrência | a rodada em `interesse` e mínimo R$ 150,00 | duas chamadas de `alterar_minimo` em paralelo, para `200,00` e `300,00` | duas auditorias; o `anterior` de uma é `150.00` e o da outra é o valor gravado pela primeira; o valor final é o `novo` da segunda auditoria |
| A-16 | Spec da fatia | negativo | uma chamada de `travar_condicoes` fora de `transaction.atomic()` | executo | `TransactionManagementError` |
| A-17 | Spec §2, §15 | negativo | um comprador e uma conta de fornecedor autenticados; um visitante anônimo | `POST` de abertura de rodada e `GET`/`POST` do mínimo | 403 para os autenticados; anônimo redirecionado para `/entrar/`; nada criado nem alterado |
| A-18 | Spec da fatia | negativo | um comprador como `autor` | chamo `abrir_rodada` e `alterar_minimo` | `PermissionDenied`; nada gravado |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-4, A-6, A-7, A-16 | `tests/tecnicos/test_rodadas_abertura.py` |
| A-8 a A-13, A-18 | `tests/tecnicos/test_rodadas_minimo.py` |
| A-5, A-14, A-15 | `tests/tecnicos/test_rodadas_concorrencia.py` (marcador `concorrencia`) |
| A-17 | `tests/tecnicos/test_rodadas_permissoes.py` |
| A-8 (cenário 71); A-9 (cenário 72, T-23) | também marcados `acceptance` e `tecnico`, com os números no comentário |
