# E10-07 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

| Etapa | Commit | Comando | Resultado |
|---|---|---|---|
| Testes A-1 a A-20 (telas, avisos, seção do comprador) | `E10-07: testes A-1 a A-20` | `uv run pytest tests/tecnicos/test_devolucoes_telas.py tests/tecnicos/test_devolucoes_avisos.py tests/tecnicos/test_pedidos_estornos_do_comprador.py` | **Red: 24 failed, 2 passed.** Passam o A-14 (o outro comprador já recebia 404) e a variante do A-4 de rota inexistente para o anônimo/403 que o 404 não distingue; ambos são regressão |
| `estornos.py` (textos, aviso, seção), `devolucoes_views.py`, 5 rotas, 3 templates, link no menu, avisos nos serviços da E10-04 e E10-06 | `E10-07: avisos de estorno...` | os mesmos arquivos | **26 passed** |
| Cenários 35 e 36 pelo fluxo da tela | mesmo commit | `tests/aceitacao/test_cenarios_35_36_excepcional.py` | 4 passed |

**Correção de teste (declarada).** O A-16 foi escrito com `falhar_proximas(1, operacao="estornar")` antes de `levar_a_elegivel`, o que deixaria a parcela em `falha_temporaria` e nunca chegaria a elegível. O erro era do teste, e não do código; a linha foi removida, e o caminho real já passa pela falha definitiva (que também não avisa). Nenhuma asserção foi afrouxada.

## Decisões técnicas

- Os avisos são emitidos dentro dos serviços, na transação do fato, com a chave `estorno:<parcela>:<situação>:<conta>`. No `concluir`, o aviso vem antes da liquidação; se a liquidação levanta, a transação do `concluir` se desfaz, e o aviso também (A-20).
- As rotas ficam sob `administracao/financeiro/devolucoes/` (o prefixo do menu financeiro da E09-08).
- A lista mostra seis seções (`pendentes`, `solicitadas`, `em-processamento`, `falhas`, `elegiveis`, `concluidas`), paginadas por obrigação.
- Recusa do serviço: 409; provedor fora do ar: 503; campo ou comprovante inválido na confirmação: 400 com o formulário.

## Verificações executadas (E10 inteira, sobre o último commit)

```
uv run pytest                                 # 2600 passed in 280.09s, sem filtro
uv run ruff check . --no-cache                # All checks passed
uv run ruff format --check .                  # 347 files already formatted
uv run mypy .                                 # Success: no issues found in 415 source files
uv run python manage.py makemigrations --check --dry-run   # No changes detected
```

Antes da E10 a suíte tinha 2433 testes; a E10 acrescentou 167.

## Riscos remanescentes e limites de verificação

- A trava de cada operação (pedido, parcela, confirmação) foi escrita junto com o código funcional, sem Red da corrida (E10-04 e E10-06); só mutação, que não substitui Red.
- `verificar_estornos` com falha definitiva do provedor não é reagendada.
- A leitura da cobertura na autorização não trava a reserva.
- O armazenamento do comprovante é o do Django em desenvolvimento e teste; o R2 é da E16.
- O README (Parte 1) só será atualizado no PR para a `main`, depois da aprovação.

## Revisão (agente 3)

| Achado | Classificação (bloqueador, importante, melhoria) | Evidência | Requisito |
|---|---|---|---|
| | | | |

**Decisão:** pendente

## Revalidação

—
