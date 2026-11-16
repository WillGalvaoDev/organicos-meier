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


## Revisão independente — agente 3 — 2026-11-16

Referência auditada: `2f5958c`, branch `e15-especificacoes`, sobre `8b1739f` (E14). Foram lidos os documentos-base (funcional v1.7 e infraestrutura v1.8), as sete especificações e matrizes E15 e os registros Red/Green, antes da comparação com código e testes. Este parecer acrescenta-se ao registro do implementador, preservado integralmente. Evidências globais e código das reproduções estão em [E15-07/review.md](../E15-07/review.md).

**Veredito da fatia: REPROVADO por R03**, compartilhado com E15-05. A-1 a A-16 confrontados: margens estritas, dias em Brasília, chaves, resolução e ausência de escrita no domínio estão cobertos; A-14 cobre congelamento, mas não a segunda metade da regra 5.

### R03 — importante — falta a contagem atual dos atrasos no painel

- Requisito: spec.md, regra 5: dados do alerta aberto ficam congelados, mas “A contagem atual aparece no painel (E15-05)”.
- Código: `apps/operacao/painel.py:376` monta o corpo exclusivamente de `alerta.dados`; o contexto não acrescenta contagem atual de chamadas/envios atrasados.
- Reprodução: abrir alerta geral com uma chamada atrasada; criar outra chamada igualmente atrasada; verificar novamente e carregar `contexto_do_painel`. O alerta corretamente conserva `quantidade=1`, mas o painel informa “1 chamada(s)” e não apresenta o total atual 2 em outra seção.
- Impacto: o painel subestima ou superestima o acúmulo enquanto a condição continua aberta. Corrigir a leitura do painel preservando os dados e a notificação originais, sem abrir alerta duplicado. Cobrir aumento e redução da contagem ainda positiva; o mesmo caminho atende os envios.

TDD: Red `9d5ebe1`, Green `4ba1d7a` e ajuste de tipos `821c83e`; registro de 12 falhas e quatro guardas passando. Não reexecutado Red histórico.

## Correção R03 (implementador, 2026-11-16)

Ver E15-05: o painel remonta o corpo dos alertas `chamadas_ao_provedor_atrasadas` e `envios_atrasados` com a contagem atual (A-26 a A-30). Nenhum dado, notificação ou alerta é alterado.
