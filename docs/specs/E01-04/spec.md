# E01-04 — Registros só de inserção e trilha de auditoria

Fatia 4 de 5 da milestone **E01 — Fundação de engenharia**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Livro-razão, devoluções, ocorrências de entrega, tentativas de envio e auditoria precisam ser registros que só aceitam inserção, protegidos também no banco. Esta fatia cria:

- o mecanismo reutilizável de registro que só aceita inserção, com proteção na aplicação e no Postgres;
- a trilha de auditoria comum, que as etapas seguintes usarão para registrar ações relevantes.

As tabelas de negócio que usarão o mecanismo ficam nas suas etapas.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §14 (Auditoria) | Autor, ação, momento, motivo quando exigido e alterações relevantes. |
| Especificação §7 | Toda intervenção deve ser auditada. Nenhuma intervenção reescreve pagamentos, apaga histórico ou cobra valor adicional. |
| Especificação §15 | Histórico financeiro imutável ou auditável. Remoção de conta não apaga fatos operacionais. Dados pessoais mínimos. |
| Infraestrutura 5 | Histórico financeiro, livro-razão e auditoria só aceitam inserção. |
| Infraestrutura 4.9 | Proteção de imutabilidade por trigger no Postgres, além da ausência de rotas de edição. |
| AGENTS.md §6 | Lançamentos auditáveis e imutáveis. Toda ação financeira relevante deve ser auditável. |

## Escopo

**Dentro:**

- Base abstrata de modelo "só inserção":
  - a aplicação recusa atualização, exclusão, `update()` e `delete()` em lote e `bulk_update`;
  - inserção normal e `bulk_create` continuam permitidas.
- Utilitário de migração que instala, numa tabela, uma trigger do Postgres que recusa `UPDATE` e `DELETE`. Ele é reutilizável pelas tabelas das etapas seguintes.
- Modelo de auditoria que só aceita inserção, com a trigger instalada.
- Função de serviço para registrar uma entrada de auditoria.

**Fora:**

- Tabelas de negócio (livro-razão, devoluções, ocorrências, itens de pedido congelado), que usarão o mecanismo nas suas etapas.
- Telas de consulta da auditoria (E15).
- Retenção e expurgo de auditoria (não definidos nos documentos-base).

## Regras

**Registro só de inserção (aplicação):**

- Salvar um objeto novo funciona.
- Salvar de novo um objeto já gravado levanta uma exceção própria (`RegistroImutavel`).
- `delete()` de instância, `QuerySet.update()`, `QuerySet.delete()` e `bulk_update()` levantam a mesma exceção.

**Registro só de inserção (banco):**

- A trigger recusa `UPDATE` e `DELETE` mesmo por SQL direto.
- A recusa gera um erro do banco, que aparece na aplicação como erro de integridade ou de banco e não é silenciado.

**Auditoria:**

Cada entrada registra:

- **autor:** usuário ou "sistema", nunca vazio;
- **ação:** identificador textual estável, por exemplo `rodada.cancelar`;
- **momento:** obtido da fonte de tempo da E01-03;
- **motivo:** opcional, porque algumas ações não exigem (por exemplo, o cancelamento de rodada, especificação §7.2);
- **alterações relevantes:** estrutura de chave e valor;
- **referência ao objeto afetado:** tipo e identificador.

Regras de conteúdo:

Representação (decisão técnica desta fatia):

- O autor é gravado como tipo (`usuario` ou `sistema`) mais o identificador do usuário quando o tipo é `usuario`. O identificador não é chave estrangeira. Assim, remover a conta não apaga a entrada nem precisa de cascata, a entrada não depende do modelo de usuário que a E02 vai definir, e nenhum dado pessoal (nome, e-mail) é copiado.
- O objeto afetado é gravado como rótulo do modelo (`app_label.model`) mais o identificador em texto, também sem chave estrangeira.
- Banco: tipo do autor restrito a `usuario` ou `sistema`; identificador obrigatório quando o tipo é `usuario` e ausente quando é `sistema`. As duas regras são garantidas por *constraint*.

- `registrar_auditoria(...)` grava a entrada na transação corrente. Se a transação for desfeita, a entrada também é desfeita, para nunca auditar uma ação que não aconteceu.
- **Dados mínimos:** as alterações registram identificadores e valores de negócio, nunca senhas, tokens, chaves de API ou comprovantes. A função recusa uma chave que contenha um dos termos reservados para segredos (`senha`, `password`, `token`, `secret`, `chave_api`). A comparação:
  - ignora maiúsculas e minúsculas;
  - procura o termo dentro da chave, então `senha_hash` e `Token_Pagamento` também são recusadas;
  - percorre dicionários e listas aninhados.
- **Autor removido:** a entrada de auditoria continua existindo depois da remoção da conta do autor. A referência ao autor não pode ser apagada em cascata.

## Interfaces

Módulos em `apps/nucleo` (nomes ajustáveis pelo implementador, se mantidos o comportamento e os testes):

- `RegistroSoInsercao` (modelo abstrato) e `RegistroImutavel(Exception)`.
- `instalar_protecao_so_insercao(nome_tabela)`, operação de migração reutilizável.
- `EntradaAuditoria` (modelo) e `registrar_auditoria(autor, acao, objeto, alteracoes, motivo=None)`, em que `autor` é uma instância de usuário ou a constante `SISTEMA`, exportada pelo mesmo módulo.

## Invariantes

- Nenhuma entrada de auditoria pode ser alterada ou apagada, nem pela aplicação nem por SQL direto.
- Toda tabela que herdar de `RegistroSoInsercao` e instalar a proteção tem o mesmo comportamento.
- A auditoria nunca contém segredos.

## Casos-limite e concorrência

- `bulk_create` de várias entradas funciona.
- Remoção do usuário autor não remove as entradas, e a referência fica preservada.
- Transação desfeita depois de `registrar_auditoria`: a entrada não existe.
- Duas transações gravando auditoria ao mesmo tempo não interferem entre si. Não exige teste de concorrência específico, porque são inserções independentes.

## Dependências e decisões em aberto

- Depende de E01-01 (CI) e E01-03 (momento da auditoria).
- O modelo de teste de A-1 a A-5 fica no app só de testes `tests/apoio` (definido na spec da E01-02).
- Sem decisões em aberto.
