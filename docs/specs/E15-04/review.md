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
