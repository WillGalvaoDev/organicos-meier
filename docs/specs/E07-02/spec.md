# E07-02 — Ambiente, provedor configurado e recusa do simulador em produção

Fatia 2 de 6 da milestone **E07 — Simulador de pagamentos e integração**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

A aplicação não pode iniciar em produção com o simulador de pagamentos (A3, cenário 38, T-12). Para isso, a configuração precisa dizer em que ambiente a aplicação roda e qual implementação de pagamento está ativa, e a combinação proibida precisa impedir o processo de subir.

Esta fatia entrega:

- a configuração `AMBIENTE`;
- a configuração `PROVEDOR_PAGAMENTOS`;
- a recusa no carregamento das configurações, que impede a web e o worker de subir;
- uma segunda verificação em `obter_provedor()`.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §15, Integridade | "A aplicação não pode iniciar em produção com o simulador de pagamentos habilitado." |
| Especificação §15, Operação | Ambientes separados de desenvolvimento, testes e produção; pagamentos de teste nunca confundidos com reais. |
| Cenários §16 | 38. |
| Infraestrutura 4.1 | "A verificação de inicialização compara ambiente e implementação de pagamento configurada, e encerra o processo se produção estiver com o simulador." "Cada pagamento registra o provedor e o ambiente." |
| Infraestrutura 5 | Ambientes separados, cada um com credenciais próprias. O simulador nunca é ativado em produção. |
| Infraestrutura 7 | Fase 1: desenvolvimento e homologação, sem operação em produção. |
| Testes técnicos | T-12: "Aplicação configurada com o simulador em produção encerra na inicialização." |
| AGENTS.md §7 | "É proibido iniciar a aplicação em produção com simulador habilitado." |
| E04-04 | Precedente: `CANAL_WHATSAPP` com valores fechados e recusa no carregamento de `prod.py`. |

## Escopo

**Dentro:**

- `AMBIENTE` e `PROVEDOR_PAGAMENTOS` nos arquivos de configuração.
- A recusa no carregamento e a verificação em `obter_provedor()`.
- `SEGREDO_AVISOS_SIMULADOR` em `prod.py`.

**Fora:**

- O provedor real (fase 2a). Na fase 1, `PROVEDOR_PAGAMENTOS` só aceita `simulador`. Por isso, `prod.py` com `AMBIENTE=producao` nunca carrega nesta fase, o que é o comportamento pedido.
- A homologação no Fly.io (E16). Ver "Herança para a E16".

## Decisões técnicas

- **Valores de `AMBIENTE`:**
  - `desenvolvimento` em `dev.py`;
  - `testes` em `test.py`;
  - em `prod.py`, lido da variável de ambiente `AMBIENTE`, obrigatória, com `homologacao` ou `producao`. A homologação usa as configurações de produção (HTTPS, cookies seguros) com dados de teste e o simulador, como pede a fase 1.

  Qualquer outro valor, ou a variável ausente em `prod.py`, levanta `ImproperlyConfigured`.
- **`PROVEDOR_PAGAMENTOS`** é lido do ambiente em `base.py`, com padrão `simulador`. Na fase 1, qualquer valor diferente de `simulador` levanta `ImproperlyConfigured`, em qualquer ambiente, como `CANAL_WHATSAPP`. O valor do Mercado Pago entra na fase 2a, com especificação própria.
- **A recusa fica no carregamento das configurações.** Web, worker e comandos (`manage.py migrate`, `procrastinate worker`) importam as mesmas configurações, então nenhum deles sobe. É o mesmo mecanismo da E04-04, que já é testado em subprocesso (`tests/tecnicos/test_configuracao_producao.py`).
- **Segunda verificação em `obter_provedor()`:** levanta `ImproperlyConfigured` se `AMBIENTE` for `producao` e o provedor for o simulador. Cobre configurações alteradas depois do carregamento, como `override_settings`.
- **`SEGREDO_AVISOS_SIMULADOR` em `prod.py`:** obrigatório quando o provedor é o simulador (homologação), sem valor padrão. Em `dev.py` e `test.py`, há valor fixo de teste.

## Regras

**`prod.py`**, depois de importar `base.py`:

1. `AMBIENTE = env("AMBIENTE")`. Ausente ou fora de `homologacao` e `producao`: `ImproperlyConfigured("AMBIENTE deve ser 'homologacao' ou 'producao'.")`.
2. Com `AMBIENTE == "producao"` e `PROVEDOR_PAGAMENTOS == "simulador"`: `ImproperlyConfigured("O simulador de pagamentos não pode ser usado em produção.")`.
3. Com o simulador, `SEGREDO_AVISOS_SIMULADOR = env("SEGREDO_AVISOS_SIMULADOR")`, sem padrão.

A mensagem de erro não traz segredos nem outras variáveis.

**`obter_provedor()`** (E07-01):

- Com `settings.AMBIENTE == "producao"` e o simulador configurado, levanta `ImproperlyConfigured`, com a mesma mensagem.
- Caso contrário, devolve a implementação de `PROVEDOR_PAGAMENTOS`.

**Registro do ambiente:** a E07-03 e a E07-04 gravam `settings.AMBIENTE` e o nome do provedor em cada pagamento e em cada chamada.

## Ajuste autorizado nos testes existentes

Dois testes carregam `prod.py` e passam a falhar pelo motivo novo, porque `AMBIENTE` fica obrigatório:

- `tests/tecnicos/test_configuracao_producao.py`, em subprocesso, com o dicionário `_AMBIENTE_MINIMO`. O ajuste autorizado é acrescentar `"AMBIENTE": "homologacao"` e `"SEGREDO_AVISOS_SIMULADOR": "segredo-de-teste"` a `_AMBIENTE_MINIMO`.
- `test_app_de_testes_fora_da_producao`, em `tests/tecnicos/test_nucleo_campos_decimais.py`, que importa `config.settings.prod` no próprio processo. O ajuste autorizado é definir as mesmas duas variáveis com `monkeypatch.setenv` antes da importação. Se o módulo já estiver importado, ele é recarregado com `importlib.reload`.

Nenhuma asserção muda, e o diff dos dois arquivos vai para o `review.md`. Qualquer outro teste que falhe com a mensagem de `AMBIENTE` é registrado e devolvido ao especificador, sem ajuste por conta própria.

## Interfaces

- `config/settings/base.py`, `dev.py`, `test.py` e `prod.py`: `AMBIENTE`, `PROVEDOR_PAGAMENTOS` e `SEGREDO_AVISOS_SIMULADOR`.
- `apps/pagamentos/provedor.py`: a verificação em `obter_provedor()`.
- `.env.example`: a linha comentada `# PROVEDOR_PAGAMENTOS=simulador`.

## Invariantes

- Em nenhuma combinação de configuração a aplicação carrega com `AMBIENTE=producao` e o simulador.
- `AMBIENTE` sempre tem um dos quatro valores.

## Casos-limite e concorrência

- **`PROVEDOR_PAGAMENTOS` em maiúsculas ou com espaços** (`" Simulador "`): recusado. O valor precisa ser exato.
- **`AMBIENTE=producao` e `PROVEDOR_PAGAMENTOS` ausente:** o padrão é o simulador, então o carregamento falha. Produção nunca recebe o simulador por omissão.
- **`override_settings(AMBIENTE="producao")` num teste:** `obter_provedor()` recusa.

## Herança para a E16

`prod.py` recusa `CANAL_WHATSAPP=simulado` em qualquer valor de `AMBIENTE` (E04-04). Na homologação, o WhatsApp fica `desligado`, e isso basta para a fase 1. Se a E16 quiser o WhatsApp simulado na homologação, ela especifica a mudança para recusar só com `AMBIENTE=producao`.

## Dependências e decisões em aberto

- Depende de E07-01 e E04-04.
- Sem decisões em aberto.
