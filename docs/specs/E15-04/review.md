# E15-04 — Registro do implementador

Agente 2.

## Red

- Commit `636d534`: `uv run pytest tests/tecnicos/test_alertas_de_falha.py` → **25 falhas e 3 passando**. Os três que já passavam são recusas por ausência (A-3 falha antiga, A-13 horário que chega e A-15 quatro recusas: afirmam ausência de alerta): não são Red do comportamento novo. As falhas são `ModuleNotFoundError: apps.operacao.ciencia`, `ImportError: SequenciaDeAvisosRecusados` e tipos de alerta inexistentes.

## Green

- `apps/operacao/falhas.py`: as seis verificações e a classificação dos tipos. Os fatos usam `_sem_alerta_posterior`: um fato volta só se o alerta mais recente do par abriu **antes** do instante dele.
- `apps/pagamentos/models.py`: `SequenciaDeAvisosRecusados` (um registro, `id = 1`, três campos). `apps/pagamentos/avisos.py`: `registrar_recusa` (uma instrução `INSERT ... ON CONFLICT DO UPDATE`, atômica), `zerar_recusas` e `_sem_falhar` (uma falha vai para o log, só a classe do erro, e a resposta não muda). O 401 soma, o 200 zera, o 400 não conta.
- `apps/operacao/ciencia.py` (`dar_ciencia`, `CienciaRecusada`, trava `select_for_update`, auditoria `alerta.ciencia`), `apps/operacao/views.py` e a rota `alertas_ciencia` em `config/urls.py`.
- Migrações `financeiro/0019` e `pagamentos/0005`.
- Resultado: `28 passed` neste arquivo.

## Desvios e pontos para o revisor

1. **Arranjo AO com um administrador só**, como na E15-02 (a spec pede ADM3 suspenso, que o banco não admite). O A-23 usa o comprador, o fornecedor e `None`.
2. **Dados por inserção direta.** Os critérios A-4, A-11 e A-12 pedem o simulador; os testes criam `ChamadaAoProvedor` (`falhou`), `DestinoDoPagamento` e `PagamentoNoProvedor` direto, para isolar a verificação. A chamada `falhou` pelo simulador e a decisão do destino têm cobertura nas etapas E07, E08.
3. **Ajuste depois do Red (A-8 e A-10).** Eu tinha escrito `(0, 0)` como retorno da segunda verificação. Os e-mails dos primeiros avisos ficam pendentes (nenhum `processar_envios` roda) e, onze minutos depois, abrem `envios_atrasados`, então o retorno é `(1, 0)` por causa de outro tipo. Os testes passaram a conferir o que o critério pede: nenhum alerta novo de `consulta_com_divergencia`.
4. **Comparação do fato com o alerta:** "posterior" é implementado como `aberto_em >= instante do fato`; um alerta aberto no mesmo instante do fato o cobre.
5. **A-19 (concorrência):** 10 recusas em 5 threads, cada uma com o próprio cliente e conexão; `recusas_seguidas = 10` confirma o incremento atômico.


## Revisão independente — agente 3 — 2026-11-16

Referência auditada: `2f5958c`, branch `e15-especificacoes`, sobre `8b1739f` (E14). Foram lidos os documentos-base (funcional v1.7 e infraestrutura v1.8), as sete especificações e matrizes E15 e os registros Red/Green, antes da comparação com código e testes. Este parecer acrescenta-se ao registro do implementador, preservado integralmente. Evidências globais e código das reproduções estão em [E15-07/review.md](../E15-07/review.md).

**Veredito da fatia: APROVADO no escopo auditado.** A-1 a A-28 confrontados com detectores, contador de recusas, ciência e rotas. Conferidos isolamento de destinatários, ausência de conteúdo de webhook persistido, incremento SQL atômico, falha de registro sem alterar resposta, autorização no serviço e na rota, resolução auditada única sob concorrência e escape na apresentação.

TDD: Red `636d534` anterior a `6f13b60`; 25 falhas e três guardas preexistentes no registro. A mudança na contagem global dos testes A-8/A-10 é coerente com os novos e-mails atrasados; não elimina a asserção do tipo em análise. O ajuste de especificação `e8c967a` resolve o arranjo de administrador único. Comparação `>=` cobre o fato ocorrido no mesmo instante da abertura. Não reexecutei o Red histórico. Dados inseridos diretamente nos testes unitários não constituem validação de um provedor externo; integração restrita ao simulador da fase 1.
