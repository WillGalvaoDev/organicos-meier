# E01-02 — Valores monetários e quantidades decimais

Fatia 2 de 5 da milestone **E01 — Fundação de engenharia**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Preços, subtotais, reembolsos e quantidades fracionárias dependem de aritmética decimal exata e de um único arredondamento determinístico. Esta fatia cria as primitivas comuns que as etapas de catálogo, cobrança e devoluções vão usar: conversão segura de entrada, arredondamento a centavos, verificação de múltiplo exato e campos de modelo padronizados.

Não inclui regras de negócio específicas (cálculo de pedido, frete, serviço, reembolso). Elas pertencem às etapas E03, E08 e E10 e usarão estas primitivas.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §4.2 | Aritmética decimal exata, sem ponto flutuante binário, validação no servidor. Incremento com até três casas. |
| Especificação §9 (arredondamento) | Preços com duas casas. Subtotal arredondado uma única vez a duas casas, com `ROUND_HALF_UP`. |
| Especificação §16 | Cenários 64, 88 e 89 (valores de referência do arredondamento). |
| Infraestrutura 4.12 | Quantidade `NUMERIC(12,3)`, preço `NUMERIC(12,2)`, `quantize(Decimal("0.01"), ROUND_HALF_UP)`, entrada como texto decimal, ponto flutuante recusado. |
| Infraestrutura 4.12 e testes T-26, T-39, T-50 | `0,35 × 12,99 = 4,55`; `7,99 × 0,25 = 2,00`; `2,50 × 0,25 = 0,63`; ponto flutuante na API recusado. |
| AGENTS.md §6 | Dinheiro em representação decimal exata. |

## Escopo

**Dentro:**

- App de núcleo técnico `apps/nucleo`, sem modelos de negócio. Quem criar o app primeiro (E01-02, E01-03 ou E01-04) o registra em `INSTALLED_APPS`, e as outras fatias reaproveitam.
- App só de testes `tests/apoio` (ver "Modelos de teste").
- Conversão de entrada para dinheiro e para quantidade, com validação.
- Arredondamento a centavos com `ROUND_HALF_UP`.
- Verificação de múltiplo exato entre dois decimais.
- Campos de modelo para dinheiro e quantidade, com precisão fixa.
- Anotações de tipo das funções públicas, sem `float` nas assinaturas, verificadas pelo mypy strict que já roda no CI.

**Fora:**

- Formatação para exibição em pt-BR (vírgula, "R$"), que fica nas telas.
- Leitura de formulários localizados com vírgula, que fica nas fatias de tela.
- Regras de incremento, múltiplo de produto e subtotal de pedido (E03 e E08).

## Regras

**Dinheiro:**

- Representado como `Decimal` com exatamente duas casas.
- A conversão de entrada aceita texto decimal com ponto como separador (`"7.99"`) ou um `Decimal`.
- Recusa: `float`, `bool`, `int` (para evitar conversões implícitas, use texto ou `Decimal`), texto vazio, texto não numérico, `NaN`, infinito, mais de duas casas decimais (`"7.999"`), separador de milhar.
- O texto `"8"` vira `8.00`.
- O sinal não é validado aqui: quem chama decide se aceita valores negativos.

**Quantidade:**

- Representada como `Decimal` com até três casas.
- A conversão segue as mesmas recusas, com limite de três casas (`"0.0001"` é recusado).

**Arredondamento:**

- `arredondar_centavos(valor)` devolve o valor quantizado em `0.01` com `ROUND_HALF_UP`.
- Aceita só `Decimal`. Qualquer outro tipo é recusado.
- Exemplos obrigatórios (valores não negativos, os únicos usados pelo negócio):
  - `7.99 × 0.25 = 1.9975 → 2.00`
  - `2.50 × 0.25 = 0.625 → 0.63`
  - `12.99 × 0.35 = 4.5465 → 4.55`
  - `0.015 → 0.02`

**Múltiplo exato:**

- `eh_multiplo(valor, passo)` é verdadeiro quando `valor` é múltiplo inteiro de `passo`, por aritmética `Decimal` exata.
- `passo` precisa ser maior que zero. Caso contrário, a função recusa.
- Exemplos:
  - `1.25` de `0.25`: verdadeiro;
  - `1.2` de `0.5`: falso;
  - `0` de `0.25`: verdadeiro;
  - `4` de `2`: verdadeiro;
  - `3` de `2`: falso.

**Campos de modelo:**

- Campo de dinheiro: `NUMERIC(12,2)`.
- Campo de quantidade: `NUMERIC(12,3)`.
- Ambos recusam `float` na validação (`full_clean`), com erro de validação do Django. O `DecimalField` padrão aceita `float`, então a recusa é comportamento próprio destes campos.

**Modelos de teste:**

- Os modelos usados só nos testes (nesta fatia e em E01-03, E01-04 e E01-05) ficam no app `tests/apoio`, com rótulo `apoio_testes` e migrações próprias.
- O app é registrado apenas em `config/settings/test.py`, e nunca entra em `base.py` nem em `prod.py`.
- Quem criar o app primeiro faz o registro e acrescenta `tests/apoio/` à seção "Estrutura" do `README.md`. As outras fatias acrescentam seus modelos e migrações.

**Erro:**

- Toda recusa levanta uma exceção própria do núcleo (por exemplo, `ValorInvalido`), com mensagem que identifica o motivo, sem expor dados pessoais.

## Interfaces

Módulo `apps/nucleo/valores.py` (nomes podem ser ajustados pelo implementador, se mantidos o comportamento e os testes):

- `dinheiro(entrada: str | Decimal) -> Decimal`
- `quantidade(entrada: str | Decimal) -> Decimal`
- `arredondar_centavos(valor: Decimal) -> Decimal`
- `eh_multiplo(valor: Decimal, passo: Decimal) -> bool`
- `ValorInvalido(Exception)`
- Campos `CampoDinheiro` e `CampoQuantidade` (subclasses de `DecimalField`).

## Invariantes

- Nenhuma função desta fatia aceita ou devolve `float`.
- `arredondar_centavos` é idempotente: arredondar de novo não muda o valor.
- Valores gravados e relidos do Postgres preservam exatamente as casas definidas.

## Casos-limite e concorrência

- Valores no limite da precisão: `9999999999.99` (dinheiro) e `999999999.999` (quantidade) gravam e relêem sem perda. Um valor acima do limite é recusado na validação.
- Zero é válido para dinheiro e quantidade, e o sinal fica a cargo de quem chama.
- `Decimal` com expoente (`Decimal("1E+2")`) é aceito e normalizado para `100.00`.
- Sem concorrência nesta fatia.

## Dependências e decisões em aberto

- Depende de E01-01 (CI) para a evidência de verificação.
- Sem decisões em aberto.
