# E15-03 — Registro do implementador

Agente 2.

## Red

- Commit `9d5ebe1`: `uv run pytest tests/tecnicos/test_alertas_de_atraso.py` → **12 falhas e 4 passando**. Os quatro que já passavam são recusas por ausência do alerta (A-3 prazo prorrogado, A-6 pedido formal já encerrado, A-9 sem conciliação, A-12 chamada futura): guardas, não Red do comportamento novo.
- `tests/conftest.py` ganhou os prefixos `test_alertas_de_` e `test_painel_` para ligar o banco do simulador (como na E14).

## Green

- `apps/operacao/atrasos.py`: os cinco tipos (`fechamento_nao_encerrado`, `pedido_formal_atrasado`, `conciliacao_atrasada`, `chamadas_ao_provedor_atrasadas`, `envios_atrasados`) e as verificações de condição, registradas pelo `ready()`; novos valores em `TipoDeAlerta` e migração `financeiro/0018`.
- Resultado: `16 passed`.

## Ajustes nos meus testes depois do Red (sem afrouxar o critério)

- **A-4:** o AF já tem e-mails pendentes além da margem, então o administrador recebe também `envios_atrasados`; o teste escolhe a notificação pelo título.
- **A-8:** os e-mails dos primeiros avisos ficam pendentes até o dia seguinte e abrem `envios_atrasados`; o retorno `(1, 1)` deixou de valer, e o teste confere por tipo: o alerta de `dia:2026-11-18` resolvido e o de `dia:2026-11-19` aberto.
- **A-15:** os avisos criam e-mails (`Envio`) novos por natureza; a comparação exige que rodada, conciliações e chamadas fiquem iguais e que os envios que já existiam fiquem iguais.

## Decisões técnicas

- Condição de chamada pendente: `proxima_em` atrasada (estrito, margem de 5 min) **ou** `instante − criada_em > 25 h`.
- `conciliacao_atrasada` olha só o dia seguinte à última conciliação, como a regra 6 descreve.
- Os textos são montados na leitura a partir de `dados`; datas em Brasília.
