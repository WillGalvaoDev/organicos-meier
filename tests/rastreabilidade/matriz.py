"""A matriz de rastreabilidade da fase 1 (E16-07): cenário (§16) e teste técnico -> testes.

Cada entrada tem as afirmações verificáveis do texto-base (até 140 caracteres) e, para cada uma,
as referências dos testes que a provam (`caminho/do/arquivo.py::nome_do_teste`, ou
`::Classe::nome`, relativo à raiz, sem parâmetros), cada uma com a sua prova: um texto de até 200
caracteres que diz o que o teste confere, com pelo menos um trecho copiado, entre crases, de um
`assert` ou `pytest.raises(...)` do corpo do teste (ou de uma função do módulo que ele chama).
`test_matriz.py` confere a estrutura, a existência, a coleta, a ausência de pulo e os trechos das
provas; o documento `docs/rastreabilidade-fase1.md` é gerado daqui
(`python -m tests.rastreabilidade.gerar`).
"""

CENARIOS: dict[int, dict[str, dict[str, str]]] = {
    1: {
        "Convite com mais de 24h não cadastra usuário": {
            "tests/tecnicos/test_convites_cadastro.py::test_fronteira_de_24h_no_post": 'com 24h ou mais o POST dá 410 e nenhuma conta nasce: `resposta.status_code == 410`; `Conta.objects.filter(papel="comprador").count() == 0`',
        },
        "Convite já consumido não cadastra usuário": {
            "tests/tecnicos/test_convites_cadastro.py::test_convite_consumido_nao_pode_ser_reutilizado": 'reuso do convite dá 410 e a conta continua uma só: `Conta.objects.filter(email_normalizado="bia@x.com").count() == 1`; `resposta.status_code == 410`',
        },
        "Convite usado com outro e-mail não cadastra usuário": {
            "tests/tecnicos/test_contas_google_cadastro.py::test_google_com_outro_email_nao_cadastra_pelo_convite": "outro e-mail: nada criado e o convite fica sem consumo: `_contagens() == antes`; `convite.consumido_em is None`",
        },
        "Convite de fornecedor não permite escolher outro fornecedor": {
            "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_fornecedor": "o fornecedor da conta vem do convite: `conta.fornecedor == f1`",
        },
    },
    2: {
        "Google sem conta e sem convite não cria conta nem abre sessão": {
            "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada": "sem sessão e contagens iguais: `not _autenticado(client)`; `_contagens() == antes`",
        },
        "Link sem conta não recebe e-mail nem abre sessão": {
            "tests/tecnicos/test_contas_link_de_acesso.py::test_email_sem_conta_tem_a_mesma_resposta_e_nao_envia": "nenhum link e nenhum e-mail: `LinkDeAcesso.objects.count() == 0`; `len(mail.outbox) == 0`",
        },
        "Google com conta suspensa abre a sessão, mas a suspensão continua: sem adição de interesse": {
            "tests/aceitacao/test_cenario_02_login_nao_contorna_suspensao.py::test_google_de_conta_suspensa_entra_mas_nao_adiciona_interesse": 'entra pelo Google e adicionar interesse dá 403: `"_auth_user_id" in client.session`; `_tentar_adicionar_interesse(client) == 403`',
        },
        "Link com conta suspensa abre a sessão, mas a suspensão continua: sem adição de interesse": {
            "tests/aceitacao/test_cenario_02_login_nao_contorna_suspensao.py::test_link_de_conta_suspensa_entra_mas_nao_adiciona_interesse": 'entra pelo link e adicionar interesse dá 403: `"_auth_user_id" in client.session`; `_tentar_adicionar_interesse(client) == 403`; `not`',
        },
        "Google com conta banida ou removida não abre a sessão": {
            "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google": "nos casos banido e removido não há sessão: `not _autenticado(client)`",
        },
        "Link com conta banida ou removida não recebe link e não abre a sessão": {
            "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link": "nos casos banido e removido não há link nem e-mail: `LinkDeAcesso.objects.count() == 0`; `len(mail.outbox) == 0`",
        },
    },
    3: {
        "Duas reservas simultâneas para a última unidade não podem ambas ser aceitas": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_ultima_unidade_disputada_so_uma_vence": 'a segunda reserva é recusada e o total reservado é 1: `isinstance(resultados[1].excecao, EstoqueInsuficiente)`; `total_reservado(produto) == D("1")`',
        },
    },
    4: {
        "Interesse abaixo do mínimo permanece aberto indefinidamente": {
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_abaixo_do_minimo_a_rodada_fica_aberta_indefinidamente": "5 reservadas (R$ 50,00) com mínimo 100,00 e 30 dias depois: `etapa(rodada) == Etapa.INTERESSE`; `prazo_do_fechamento(rodada) is None`",
        },
        "Atingir mínimo não inicia fechamento sozinho": {
            "tests/tecnicos/test_interesses_progresso.py::test_atingir_o_minimo_nao_muda_a_etapa_nem_grava": "a etapa não muda e nada é gravado: `Rodada.objects.get(pk=rodada.pk).etapa == Etapa.INTERESSE`; `escritas == []`",
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_atingir_o_minimo_nao_inicia_nada_sozinho": "mínimo atingido (R$ 200,00) e 30 dias depois: `etapa(rodada) == Etapa.INTERESSE`; `prazo_do_fechamento(rodada) is None`",
        },
    },
    5: {
        "Administrador inicia fechamento e o término ocorre 24h depois": {
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_inicio_registra_ciclo_prazo_de_24_horas_e_auditoria": "o prazo é o início do ciclo mais 24 h: `prazo.termina_em == ciclo.iniciado_em + timedelta(hours=HORAS_DO_FECHAMENTO)`",
        },
        "Queda temporária do mínimo não reinicia o relógio": {
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_a_queda_e_a_recuperacao_do_minimo_nao_mexem_no_prazo": "o prazo continua o mesmo: `prazo_do_fechamento(rodada) == T`",
        },
        "Queda temporária do mínimo não estende o relógio": {
            "tests/tecnicos/test_rodadas_fechamento_prorrogacao.py::test_a_queda_do_minimo_nao_prorroga": "nenhuma prorrogação é criada: `prazo_do_fechamento(rodada) == T`; `not PrazoDoFechamento.objects.filter(origem=OrigemDoPrazo.PRORROGACAO).exists()`",
        },
    },
    6: {
        "Produto de R$ 10,00, múltiplo 12 e 18 unidades gera R$ 120,00 elegíveis, não R$ 180,00": {
            "tests/tecnicos/test_interesses_progresso.py::test_dezoito_unidades_com_multiplo_doze": 'elegível 120,00 e bruto 180,00: `item.valor_elegivel == D("120.00")`; `item.valor_bruto == D("180.00")`',
        },
    },
    7: {
        "Comprador A adiciona 8 unidades": {
            "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_as_ultimas_adicoes_perdem_o_excedente": 'A fica com 8 reservadas: `reservado(a, p) == D("8")`',
        },
        "B adiciona 10: a primeira caixa contém 8 unidades de A": {
            "tests/tecnicos/test_interesses_progresso.py::test_caixa_formada_pela_ordem_de_adicao": 'A tem 8 reservadas e 8 em caixa: `(para_a.do_comprador.reservado, para_a.do_comprador.em_caixas) == (D("8"), D("8"))`',
        },
        "B adiciona 10: a primeira caixa contém 4 unidades de B": {
            "tests/tecnicos/test_interesses_progresso.py::test_caixa_formada_pela_ordem_de_adicao": 'B tem 10 reservadas e 4 em caixa: `(para_b.do_comprador.reservado, para_b.do_comprador.em_caixas) == (D("10"), D("4"))`',
        },
        "B vê 6 excedentes": {
            "tests/tecnicos/test_interesses_carrinho.py::test_caixas_so_com_as_unidades_do_proprio_comprador": 'a tela de B mostra 6 excedentes: `"Suas unidades excedentes: 6" in html_b`',
        },
        "No fim do fechamento, essas 6 são removidas": {
            "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_as_ultimas_adicoes_perdem_o_excedente": 'removidas 6 e B fica com 4: `resultado.removidas == {p.pk: D("6")}`; `(parcela_b.situacao, parcela_b.quantidade_reservada) == ( SituacaoParcela.ATIVA,`',
        },
    },
    8: {
        "A aumenta depois: o acréscimo fica depois das adições anteriores de B": {
            "tests/tecnicos/test_interesses_servicos.py::test_acrescimo_posterior_vai_para_o_fim_da_fila": "a sequência do acréscimo é maior que a de B: `pa8.sequencia < pb10.sequencia < pa2.sequencia`",
        },
        "Redução de A remove primeiro seu acréscimo mais recente": {
            "tests/tecnicos/test_interesses_servicos.py::test_acrescimo_posterior_vai_para_o_fim_da_fila": "o acréscimo de 2 sai e a parcela de 8 fica: `pa2.situacao == SituacaoParcela.REMOVIDA`; `(pa2.quantidade_reservada, pa2.quantidade_pendente) == (0, 0)`",
        },
    },
    9: {
        "Fechamento encerrado com mínimo insuficiente volta para interesse": {
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_nao_atingido_volta_para_interesse": "a rodada volta à etapa de interesse: `resultado.etapa_final == Etapa.INTERESSE`; `etapa(rodada) == Etapa.INTERESSE`",
        },
        "Com mínimo suficiente, fica bloqueado aguardando autorização de pagamento": {
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_atingido_aguarda_o_pagamento": 'etapa encerrada aguardando pagamento: `etapa(rodada) == Etapa.FECHAMENTO_ENCERRADO`; `entrada.alteracoes["resultado"] == "aguardando_pagamento"`',
        },
    },
    10: {
        "Comprador de R$ 100,00 de produtos paga R$ 115,00 com serviço e frete": {
            "tests/tecnicos/test_pedidos_calculo.py::test_cobranca_rateia_o_frete_pelos_produtos": 'produtos 100, serviço 5, frete 10: `(c1.comprador_id, c1.produtos, c1.servico, c1.frete, c1.total) == ( 1, D("100.00"), D("5.00"), D("10.00"), D("115.00"), )`',
        },
        "Comprador de R$ 300,00 de produtos paga R$ 345,00 com serviço e frete": {
            "tests/tecnicos/test_pedidos_calculo.py::test_cobranca_rateia_o_frete_pelos_produtos": 'produtos 300, serviço 15, frete 30: `(c2.comprador_id, c2.produtos, c2.servico, c2.frete, c2.total) == ( 2, D("300.00"), D("15.00"), D("30.00"), D("345.00"), )`',
        },
    },
    11: {
        "Alterar o carrinho na etapa de pagamento não modifica pedidos congelados": {
            "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409": 'A aumenta (7) e reduz (5) o interesse com pedido aberto: `resposta.status_code == 409`; `list(ItemDoPedido.objects.order_by("pk").values()),`',
        },
        "Novo comprador na etapa de pagamento não modifica pedidos congelados": {
            "tests/tecnicos/test_pedidos_abertura.py::test_composicao_fica_congelada_apos_a_abertura": "o interesse do comprador novo é bloqueado: `pytest.raises(InteressesBloqueados)`",
        },
        "Alterar o preço de catálogo na etapa de pagamento não modifica pedidos congelados": {
            "tests/tecnicos/test_pedidos_abertura.py::test_composicao_fica_congelada_apos_a_abertura": 'com o preço mudado, itens e totais ficam iguais: `list(ItemDoPedido.objects.order_by("pk").values()) == antes`; `list(Pedido.objects.order_by("pk").values("produtos", "servico",`',
        },
    },
    12: {
        "Antes de T0 + 24h a tentativa de pagamento é aceita": {
            "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento": 'a tentativa criada antes do limite cria a cobrança: `len(_tentativas(x)) == 1`; `len(_chamadas("criar_cobranca")) == 1`',
        },
        "A partir de T0 + 24h a tentativa é recusada, mesmo com a tarefa agendada atrasada": {
            "tests/tecnicos/test_pedidos_prazos.py::test_com_o_bloqueio_parado_o_servidor_recusa_a_tentativa": 'com o bloqueio parado, o servidor recusa: `pytest.raises(PagamentoRecusado)`; `erro.value.codigo == "prazo_encerrado"`',
        },
        "Na margem operacional não é possível comprar": {
            "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre": "o interesse na margem é bloqueado: `pytest.raises(InteressesBloqueados)`",
        },
        "Na margem operacional não é possível alterar pedidos": {
            "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre": 'os pedidos ficam iguais: `list(Pedido.objects.order_by("pk").values()) == antes`',
        },
        "Na margem operacional não é possível criar cobranças": {
            "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre": "a tentativa é recusada e nenhuma cobrança nasce: `pytest.raises(PagamentoRecusado)`; `x.tentativas.count() == 0`",
        },
        "A rodada aguarda T0 + 48h": {
            "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre": "em T0+30h as recusas e a etapa: `x.tentativas.count() == 0`; `Rodada.objects.get(pk=arranjo.rodada.pk).etapa == Etapa.PAGAMENTO`",
        },
        "A rodada aguarda a decisão administrativa depois de T0 + 48h": {
            "tests/tecnicos/test_pedidos_prazos.py::test_depois_de_48_horas_nada_acontece_sozinho": 'nenhuma apuração nem cancelamento sozinho: `not [a for a in acoes if a.startswith(("rodada.apurar",`; `_situacao(pedido_de(comprador)).situacao == "aguardando_pagamento"`',
        },
    },
    13: {
        "Inadimplência em uma caixa invalida a caixa inteira": {
            "tests/tecnicos/test_apuracao_viavel.py::test_estorno_proporcional_das_unidades_em_caixa_invalidada": 'o reembolso da caixa é por item invalidado: `reembolso.chave == f"caixa:{apuracao.pk}:{item.pk}"`; `(linha.item_id, linha.quantidade, linha.valor) == (item.pk, D("4.000"),`',
        },
        "Compradores pagos na caixa invalidada recebem estorno proporcional": {
            "tests/tecnicos/test_apuracao_viavel.py::test_estorno_proporcional_das_unidades_em_caixa_invalidada": 'produtos 20, serviço 1 e frete 2,59: `(reembolso.produtos, reembolso.servico, reembolso.frete) == ( D("20.00"),`; `obrigacao.devido == D("23.59")`',
        },
        "Compradores pagos na caixa invalidada não são realocados para outra caixa": {
            "tests/tecnicos/test_apuracao_viavel.py::test_a_fila_nao_reserva_na_rodada_apurada": 'as unidades da caixa invalidada não vão para outra caixa: `total_reservado(a.p2) == D("0.000")`; `alocar_pendentes(a.fornecedor) == D("0.000")`',
        },
    },
    14: {
        "Com produtos válidos pagos mantendo o mínimo, a diferença de frete de inadimplentes fica com o administrador": {
            "tests/tecnicos/test_apuracao_aprovacao.py::test_aprovar_leva_a_apuracao_ao_livro_e_avanca_a_rodada": 'o déficit de frete vira despesa: `deficit.valor == D("14.24")`; `destinos == {"produtos": D("60.00"), "servico": D("3.00"), "frete": D("7.76")}`',
        },
        "A diferença de frete de inadimplentes não altera cobranças concluídas": {
            "tests/tecnicos/test_apuracao_aprovacao.py::test_o_pedido_e_o_pagamento_nao_mudam_e_a_custodia_zera": "pedido e quitação iguais depois da aprovação: `SituacaoDoPedido.objects.get(pedido=x).quitado_por_id,`; `) == antes`",
        },
    },
    15: {
        "Com pagos abaixo do mínimo, a rodada retorna para interesse": {
            "tests/tecnicos/test_apuracao_telas.py::test_minimo_nao_atendido_devolve_a_rodada_e_mostra_o_estorno_integral": 'a rodada volta para interesse: `a.rodada.etapa == "interesse"`; `"Mínimo não atendido: a rodada voltou para interesse" in texto`',
        },
        "Com pagos abaixo do mínimo, os pagos mantêm interesses": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": 'as reservas de quem pagou ficam ativas: `[(p.situacao, p.quantidade_reservada) for p in de_p1] == [("ativa",`; `[(p.situacao, p.quantidade_reservada) for p in de_p2] == [("ativa",`',
        },
        "Com pagos abaixo do mínimo, os pagos têm estornos autorizáveis": {
            "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_15_o_estorno_do_pago_na_rodada_devolvida_e_autorizavel": 'o estorno é autorizado e concluído: `not`; `ParcelaDeDevolucao.objects.get(obrigacao=obrigacao)`; `EstornoSimulado.objects.filter(situacao="concluido"`',
        },
        "Com pagos abaixo do mínimo, os não pagos perdem itens": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": 'as parcelas de B ficam removidas: `{p.situacao for p in ParcelaDeInteresse.objects.filter(comprador=a.b)} == {"removida"}`',
        },
    },
    16: {
        "Novo fechamento pode começar com estorno antigo pendente": {
            "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente": 'o ciclo 2 começa: `a.rodada.etapa == "fechamento"`; `ultimo.numero == 2`',
        },
        "Novo fechamento não mistura cobranças": {
            "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente": "a obrigação do ciclo antigo continua uma só: `ObrigacaoComComprador.objects.filter(pedido=x).count() == 1`",
        },
        "Novo fechamento não duplica estoque": {
            "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada": 'o total reservado cabe no estoque: `total_reservado(a.p1) == D("9.000")`; `total_reservado(a.p2) == D("4.000")`',
        },
    },
    17: {
        "Webhook repetido não duplica o pagamento": {
            "tests/tecnicos/test_pagamentos_avisos.py::test_aviso_repetido_nao_repete_efeitos": 'um aviso, uma chamada e uma auditoria: `AvisoRecebido.objects.count() == 1`; `ChamadaAoProvedor.objects.count() == 1`; `EntradaAuditoria.objects.filter(acao="pagamento.si`',
            "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_nao_duplica_pagamento_pedido_e_mensagem": 'um destino e uma quitação: `DestinoDoPagamento.objects.filter(pagamento__id_externo=c.p).count() == 1`; `EntradaAuditoria.objects.filter(acao="pedido.quitar").count() == 1`',
        },
        "Webhook repetido não cria outro pedido nem muda a situação dele": {
            "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_nao_cria_outro_pedido_nem_muda_a_situacao": 'pedidos e situações iguais: `list(Pedido.objects.order_by("pk").values()) == pedidos`; `list(SituacaoDoPedido.objects.order_by("pk").values()) == situacoes`',
        },
        "Webhook repetido não duplica a mensagem formal (pedido formal por e-mail ao fornecedor)": {
            "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_depois_do_envio_nao_duplica_o_pedido_formal": "um só pedido formal, uma tentativa e um e-mail: `PedidoFormal.objects.filter(rodada`; `(`; `TentativaDeEnvioDoPedidoFormal.obj`; `_emails_do_pedido() == enviados`",
            "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_antes_da_aprovacao_gera_um_so_pedido_formal": 'um pedido formal, um envio, quantidades de um pagamento: `quantidades == {"P1":`; `processar(relogio, PRAZO) == 1`; `TentativaDeEnvioDoPedidoFormal.o`; `_emails_do_pedido() == 1`',
        },
        "Webhook repetido não duplica o estorno": {
            "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_nao_duplica_estorno": 'uma obrigação, uma parcela e um estorno: `ObrigacaoComComprador.objects.filter(pedido=c.x).`; `ParcelaDeDevolucao.objects.filter(obrigacao=obrig`; `EstornoSimulado.objects.filter(situacao="concluid`',
        },
    },
    18: {
        "Falta de R$ 25,00 gera estorno de produtos de R$ 25,00, serviço de R$ 1,25 e frete de R$ 5,00": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_18_servico_e_frete_proporcionais": 'componentes 25,00, 1,25 e 5,00: `_componentes(resultado) == (D("25.00"), D("1.25"), D("5.00"))`',
        },
        "O estorno da falta de R$ 25,00 soma R$ 31,25": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_18_servico_e_frete_proporcionais": 'devido 31,25: `resultado.reembolso.obrigacao.devido == D("31.25")`',
        },
    },
    19: {
        "A suspensão esvazia os interesses": {
            "tests/tecnicos/test_interesses_suspensao.py::test_suspensao_esvazia_os_interesses_e_a_reversao_nao_restaura": "total reservado zero: `total_reservado(p) == 0`; `total_reservado(q) == 0`",
        },
        "A suspensão cancela pedidos não pagos": {
            "tests/tecnicos/test_pedidos_moderacao.py::test_suspensao_cancela_o_pedido_nao_pago": 'o pedido não pago fica cancelado por suspensão: `situacao.situacao == "cancelado"`; `situacao.motivo_do_cancelamento == "suspensao"`',
        },
        "Pedidos pagos continuam disponíveis para retirada": {
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_19_o_suspenso_retira": 'a retirada do suspenso é registrada: `RetiradaDeItem.objects.count() == 1`; `"Retirada liberada em" in _texto(pagina)`',
        },
        "Reversão não restaura automaticamente interesses antigos": {
            "tests/tecnicos/test_interesses_suspensao.py::test_suspensao_esvazia_os_interesses_e_a_reversao_nao_restaura": "nenhuma parcela antiga volta; a nova entra no fim: `not ParcelaDeInteresse.objects.filter( comprador=a,`; `nova.sequencia > max(sequencia for sequencia, _ in antes.values())`",
        },
    },
    20: {
        "Remoção bloqueia o acesso: login por senha, link e Google não abrem sessão": {
            "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite": 'sem sessão: `"_auth_user_id" not in google.session`',
        },
        "Remoção bloqueia novo cadastro com o e-mail": {
            "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite": "novo convite recusado e nenhum convite criado: `pytest.raises(EmailEmUso)`; `Convite.objects.count() == 0`",
        },
        "A remoção mantém o pedido pago": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_20_o_pedido_pago_da_conta_removida_continua_pago": 'o pedido segue pago e quitado: `situacao.situacao == "pago"`; `situacao.quitado_por is not None`',
        },
        "A remoção mantém o histórico consultável pelo administrador": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_20_o_administrador_consulta_o_historico_financeiro_do_removido": 'pedido.quitar e conta.remover aparecem no histórico: `"pedido.quitar" in acoes`; `"conta.remover" in acoes`',
        },
    },
    21: {
        "Fornecedor não consegue consultar dados de compradores": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele": '403 em tudo e nenhum nome de comprador na tela: `[r.status_code for r in recusas] == [403] * 9`; `"Comprador A" not in texto`',
        },
        "Fornecedor não consegue consultar dados de outro fornecedor": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_rodada_de_outro_fornecedor_ou_inexistente_da_o_mesmo_404": "rodada de outro fornecedor dá o mesmo 404: `[r.status_code for r in respostas] == [404, 404, 404]`; `len({r.content for r in respostas}) == 1`",
        },
        "O fornecedor também é recusado por acesso direto à rota": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele": "as chamadas diretas dão 403: `[r.status_code for r in recusas] == [403] * 9`",
        },
    },
    22: {
        "Liberação de retirada permite nova rodada imediatamente": {
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_22_nova_rodada_e_retirada_antiga": 'a nova rodada abre em interesse: `nova.etapa == "interesse"`',
        },
        "A nova rodada não herda a reserva da anterior": {
            "tests/tecnicos/test_liberacao_da_retirada.py::test_cenario_22_a_nova_rodada_nao_herda_a_reserva": 'o resumo reservado é 11 da nova rodada: `resumo.reservado == D("11")`',
        },
        "Retiradas antigas continuam registráveis por item": {
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_22_nova_rodada_e_retirada_antiga": 'a retirada do item da rodada antiga é registrada: `_retirar(client, a, item_de(x, a.p1), "4").status_code == 302`; `RetiradaDeItem.objects.count() == 1`',
        },
    },
    23: {
        "Após sete dias, itens restantes aparecem como pendentes de decisão": {
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_23_prazo_e_descarte": 'a página mostra Prazo encerrado, pendentes de decisão: `"Prazo encerrado — pendentes de decisão" in pagina`',
        },
        "Após sete dias, o tempo sozinho não registra descarte": {
            "tests/tecnicos/test_retirada.py::test_cenario_23_o_tempo_nao_descarta": 'há vencidos e nenhum descarte: `[(v.pedido, v.produto, v.saldo) for v in depois.vencidos] == [ (x.pk, "P1",`; `not _descartes()`',
        },
        "Somente a ação administrativa registra descarte efetivo": {
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_23_prazo_e_descarte": "sem descarte só com o tempo e depois do POST do administrador, 2: `not DescarteDeItem.objects.exists()`; `DescarteDeItem.objects.count() == 2`",
        },
    },
    24: {
        "Falha no WhatsApp não desfaz o pagamento": {
            "tests/tecnicos/test_pedidos_quitacao.py::test_falha_do_whatsapp_nao_desfaz_a_quitacao": 'o pedido segue pago: `_situacao(c.x).situacao == "pago"`',
        },
        "Falha no WhatsApp não impede a notificação no site": {
            "tests/tecnicos/test_pedidos_quitacao.py::test_falha_do_whatsapp_nao_desfaz_a_quitacao": 'Pagamento confirmado aparece nas notificações: `"Pagamento confirmado: F" in cliente.get("/notificacoes/").content.decode()`',
        },
        "Falha no WhatsApp não impede o estado correto no site": {
            "tests/tecnicos/test_pedidos_abertura.py::test_falha_do_whatsapp_nao_desfaz_a_abertura": 'a etapa é pagamento e a página mostra Pagamento aberto: `_etapa(arranjo.rodada) == Etapa.PAGAMENTO`; `"Pagamento aberto: F" in pagina`',
        },
    },
    25: {
        "Pagamento iniciado antes de T0 + 24h e aprovado em T0 + 30h quita o pedido": {
            "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_25_aprovado_em_30h_e_avisado_depois_de_48h_quita_o_pedido": 'destino quita e pedido pago em T0+30 h: `(destino.destino, destino.motivo, destino.pedido) == ("quita", "", c.x)`; `(situacao.situacao, situacao.quitado_em) == ("pago", T0 + 30 * H)`',
        },
        "A quitação vale mesmo que a notificação chegue depois de T0 + 48h": {
            "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_25_aprovado_em_30h_e_avisado_depois_de_48h_quita_o_pedido": "primeiro aviso em T0+50 h e nenhuma obrigação de devolução: `PagamentoNoProvedor.objects.get(id_externo=c.p).primeiro_aviso_em`; `not ObrigacaoComComprador.objects.filter(pedido=c.x).exists()`",
        },
    },
    26: {
        "Pagamento aprovado depois de T0 + 48h não quita o pedido": {
            "tests/tecnicos/test_pedidos_quitacao.py::test_aprovacao_depois_da_margem_gera_devolucao": 'o pedido continua aguardando pagamento: `_situacao(c.x).situacao == "aguardando_pagamento"`',
        },
        "Pagamento aprovado depois de T0 + 48h gera obrigação de devolução integral": {
            "tests/tecnicos/test_apuracao_inicio.py::test_reconsulta_registra_o_pagamento_aprovado_depois_de_48_horas": 'destino devolução e obrigação integral: `_destinos(y) == [("devolucao", "aprovado_apos_a_margem")]`; `obrigacao.integral == y.total`',
        },
        "A devolução do pagamento tardio pode ser feita pela plataforma": {
            "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_nao_duplica_estorno": 'pagamento tardio devolvido no simulador: `EstornoSimulado.objects.filter(situacao="concluido").count() == 1`; `ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).count() == 1`',
        },
        "A devolução do pagamento tardio pode ser feita pela devolução excepcional": {
            "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_26_pagamento_tardio_devolvido_pela_devolucao_excepcional": 'pagamento tardio confirmado fora da plataforma: `parcela.situacao == "concluida_fora_da_plataforma"`; `_liquidado(conta_da_obrigacao(obrigacao)) == obrigacao.devido`',
        },
    },
    27: {
        "A apuração final não começa antes de T0 + 48h": {
            "tests/tecnicos/test_pedidos_prazos.py::test_a_apuracao_so_pode_comecar_em_48_horas": "pode_iniciar_apuracao é falso antes e nada é apurado: `pode_iniciar_apuracao(abertura, MARGEM - MS) is False`; `not`",
        },
        "A apuração não começa antes de T0 + 48h mesmo com todos os pedidos pagos": {
            "tests/tecnicos/test_apuracao_inicio.py::test_antes_de_48_horas_e_recusada_sem_consulta_nem_escrita": 'recusa antes_do_prazo com os pedidos pagos: `pytest.raises(ApuracaoRecusada)`; `recusa.value.codigo == "antes_do_prazo"`',
        },
        "A partir de T0 + 48h a apuração só começa com autorização do administrador": {
            "tests/tecnicos/test_apuracao_inicio.py::test_so_o_administrador_apura": "os outros recebem PermissionDenied e nada muda: `_foto() == antes`; `pytest.raises(PermissionDenied)`",
        },
    },
    28: {
        "O administrador não consegue prorrogar o prazo de pagamento": {
            "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos": "nenhuma rota nem formulário altera o prazo: `suspeitas == []`; `_campos_dos_formularios() & NOMES_DE_PRAZO ==`; `resposta.status_code == 409`",
        },
        "O administrador não consegue prorrogar a margem operacional": {
            "tests/tecnicos/test_pedidos_prazos.py::test_o_t0_nao_muda_nem_por_sql": "T0 e margem não mudam nem por SQL: `pytest.raises(RegistroImutavel)`; `(prazo_de_pagamento(atual), fim_da_margem(atual)) == (PRAZO, MARGEM)`",
        },
        "O administrador continua podendo prorrogar o fechamento": {
            "tests/tecnicos/test_rodadas_fechamento_prorrogacao.py::test_prorrogacao_estende_o_prazo_e_audita": "a prorrogação estende o prazo: `prorrogar_fechamento(admin(), rodada, novo) == novo`; `prazo_do_fechamento(rodada) == novo`",
        },
    },
    29: {
        "O aporte inicial de R$ 1.000,00 entra na reserva": {
            "tests/aceitacao/test_cenario_29_aporte.py::test_o_aporte_inicial_vai_so_para_a_reserva": 'a reserva tem 1.000,00 livres: `saldo(reserva()) == D("1000.00")`; `situacao_da_reserva().livre == D("1000.00")`',
        },
        "O aporte inicial não altera a receita de serviço": {
            "tests/aceitacao/test_cenario_29_aporte.py::test_o_aporte_inicial_vai_so_para_a_reserva": "nenhuma receita tem saldo: `[c for c in receitas if saldo(c) != 0] == []`",
        },
        "O aporte inicial não altera outra destinação": {
            "tests/aceitacao/test_cenario_29_aporte.py::test_o_aporte_inicial_vai_so_para_a_reserva": "nenhuma conta de fornecedor tem saldo: `[c for c in fornecedores if saldo(c) != 0] == []`",
        },
    },
    30: {
        "A tarifa do provedor é registrada como despesa": {
            "tests/aceitacao/test_cenario_30_tarifa.py::test_a_tarifa_e_registrada_como_despesa_e_nao_chega_ao_comprador": 'despesa de tarifa de 1,25 e saldo de despesas: `(despesa.tipo, despesa.valor) == ("tarifa", D("1.25"))`; `saldo(despesas()) == D("-1.25")`',
        },
        "A tarifa é coberta pela receita de serviço": {
            "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_30_a_tarifa_e_coberta_pela_receita_de_servico": 'o pendente da tarifa zera na apuração: `pendente_da_despesa(tarifa) == D("0.00")`; `"Tarifa coberta pela receita de serviço" in cobertura.justificativa`',
        },
        "A tarifa não altera obrigações com fornecedores": {
            "tests/aceitacao/test_cenario_30_tarifa.py::test_a_tarifa_e_registrada_como_despesa_e_nao_chega_ao_comprador": 'a custódia do comprador não muda: `[ saldo(custodia(rodada, ciclo, comprador, componente)) for componente in (Componente.PRODUTOS, Componente.SERVICO, Componente.FRETE) ] == [D("100.00"),`',
        },
        "A tarifa não altera valores cobrados de compradores": {
            "tests/aceitacao/test_cenario_30_tarifa.py::test_a_tarifa_e_registrada_como_despesa_e_nao_chega_ao_comprador": "pedido e itens ficam iguais: `Pedido.objects.filter(pk=pedido.pk).values().get() == valores_do_pedido`; `list(ItemDoPedido.objects.filter(pedido=pedido).values()) == itens`",
        },
    },
    31: {
        "O déficit de frete é registrado separadamente": {
            "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre": 'efetivo 30, arrecadado 20 e déficit 10: `(relatorio.efetivo, relatorio.arrecadado, relatorio.deficit) == ( D("30.00"), D("20.00"), D("10.00"), )`',
        },
        "O déficit de frete é coberto": {
            "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre": 'déficit coberto 10: `frete_do_ciclo(ap.ciclo).deficit_coberto == D("10.00")`',
        },
        "O déficit de frete é coberto pela reserva": {
            "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre": 'a reserva cai de 1.000 para 993,75 depois do déficit: `saldo(reserva()) == D("993.75")`',
        },
        "O déficit de frete não gera cobrança retroativa a compradores": {
            "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre": 'valores cobrados iguais: `list(Pedido.objects.order_by("pk").values("produtos", "servico", "frete")) == ( valores_cobrados )`',
        },
    },
    32: {
        "Recursos do fornecedor A não cobrem tarifa do fornecedor B": {
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso": "cobertura de despesa com dinheiro de A é recusada: `(_saldos(), MovimentoFinanceiro.objects.count()) == antes`; `pytest.raises(MovimentoProibido)`",
        },
        "Recursos do fornecedor A não cobrem déficit nem prejuízo de B": {
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso": "cobertura do frete de B com dinheiro de A é recusada: `(_saldos(), MovimentoFinanceiro.objects.count()) == antes`; `pytest.raises(MovimentoProibido)`",
        },
        "Recursos do fornecedor A não cobrem obrigação do fornecedor B": {
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso": "tentativas de financiar e de repassar da obrigação devida de A para obrigação de B: `pytest.raises(MovimentoProibido)`; `(_saldos(), MovimentoFinanceiro.objects.count()) == antes`",
        },
        "A movimentação com esse efeito é recusada": {
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso": "MovimentoProibido e saldos iguais: `pytest.raises(MovimentoProibido)`; `(_saldos(), MovimentoFinanceiro.objects.count()) == antes`",
        },
    },
    33: {
        "Devolução devida antes do repasse é financiada pelos recursos da própria rodada": {
            "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_antes_do_repasse_a_devolucao_sai_dos_recursos_da_propria_rodada": 'sem sem_cobertura e custódia financia: `resultado.sem_cobertura == D("0.00")`; `[ saldo(custodia(ap.rodada, ap.ciclo, ap.b, componente)) for componente in`',
        },
        "Devolução depois do repasse é coberta pela taxa de serviço": {
            "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_depois_do_repasse_o_que_falta_fica_sem_cobertura_ate_o_administrador_escolher": 'cobertura da receita do que falta: `resultado.sem_cobertura == D("25.00")`',
        },
        "Devolução depois do repasse é coberta pela reserva": {
            "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_depois_do_repasse_o_que_falta_fica_sem_cobertura_ate_o_administrador_escolher": 'nenhuma obrigação sem cobertura depois da designação: `[i for i in itens_sem_cobertura() if i.tipo == "obrigacao"] == []`',
        },
        "Devolução depois do repasse é coberta por novo aporte": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_34_depois_do_aporte_a_devolucao_e_concluida_sem_duplicidade": 'depois do aporte a devolução é concluída: `EstornoSimulado.objects.filter(situacao="concluido").count() == 1`; `ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao == "concluida"`',
        },
    },
    34: {
        "Com reserva insuficiente, a obrigação permanece integralmente registrada": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_34_depois_do_aporte_a_devolucao_e_concluida_sem_duplicidade": "a designação insuficiente é recusada e a obrigação fica sem cobertura: `pytest.raises(ReservaInsuficiente)`",
        },
        "Com reserva insuficiente, o sistema alerta": {
            "tests/aceitacao/test_cenario_34_reserva_insuficiente.py::test_reserva_que_nao_cobre_alerta_e_o_aporte_do_administrador_resolve": 'um alerta de reserva insuficiente aberto: `( AlertaFinanceiro.objects.filter(tipo="reserva_insuficiente", resolvido_em=None).count() == 1 )`',
        },
        "Depois de novo aporte, a devolução é concluída": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_34_depois_do_aporte_a_devolucao_e_concluida_sem_duplicidade": 'o estorno é concluído no simulador e a obrigação fica zerada: `EstornoSimulado.objects.filter(situacao="concluido").count() == 1`; `saldo(conta_da_obrigacao(obrigacao)) == D("0.00")`',
        },
        "Depois de novo aporte, a devolução não é duplicada": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_34_depois_do_aporte_a_devolucao_e_concluida_sem_duplicidade": "repetir não cria outro estorno nem outro débito: `ParcelaDeDevolucao.objects.filter(obrigacao=ob`; `MovimentoFinanceiro.objects.count() ==`; `situacao_da_reserva() == reserva`",
        },
    },
    35: {
        "Quando a devolução pela plataforma é inviável, o administrador devolve diretamente ao comprador": {
            "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional": 'a parcela fica concluída fora da plataforma: `parcela.situacao == "concluida_fora_da_plataforma"`',
        },
        "A plataforma registra a confirmação administrativa do pedido e do comprador": {
            "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional": "a confirmação guarda pedido e comprador: `(confirmacao.pedido_id, confirmacao.comprador_id) == (a.pedido.pk, a.comprador.pk)`",
        },
        "A confirmação baixa a obrigação": {
            "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional": "a obrigação fica liquidada: `_liquidado(conta_da_obrigacao(a.o1)) == a.o1.devido`",
        },
        "Até a confirmação, a obrigação permanece integral": {
            "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional": "nada liquidado antes da confirmação: `a.o1.devido - _liquidado(conta_da_obrigacao(a.o1)) == a.o1.devido`",
        },
    },
    36: {
        "A confirmação é recusada enquanto houver devolução pendente na plataforma": {
            "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_36_pela_tela": '409 há devolução pendente na plataforma: `resposta.status_code == 409`; `"há devolução pendente na plataforma" in resposta.content.decode()`',
        },
        "A confirmação é recusada com falha definitiva ainda não comprovada": {
            "tests/tecnicos/test_devolucoes_excepcional.py::test_falha_definitiva_ainda_nao_comprovada_bloqueia": 'DevolucaoRecusada há devolução pendente: `pytest.raises(DevolucaoRecusada, match="há devolução pendente na plataforma")`',
        },
        "A confirmação não pode ser feita duas vezes para a mesma parcela": {
            "tests/tecnicos/test_devolucoes_excepcional.py::test_nao_vale_duas_vezes": 'a segunda é recusada e nada muda: `pytest.raises(DevolucaoRecusada, match="já confirmada")`; `_contagens() == antes`',
        },
    },
    37: {
        "Não existe forma de registrar pagamento de comprador recebido fora da plataforma integrada": {
            "tests/tecnicos/test_pagamentos_fronteiras.py::test_nenhuma_rota_comando_ou_admin_registra_pagamento": 'nenhuma rota, comando ou admin registra pagamento: `por_app["pagamentos"] == ROTAS_DE_PAGAMENTOS`; `not (APPS / app / "management").exists()`',
        },
        "Só a sincronização com o provedor escreve nos registros de pagamento": {
            "tests/tecnicos/test_pagamentos_fronteiras.py::test_so_a_sincronizacao_escreve_nos_registros_de_pagamento": "nenhum outro módulo escreve: `escrevem == []`",
        },
    },
    38: {
        "A aplicação não inicia em produção com o simulador habilitado": {
            "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_com_o_simulador_nao_carrega": 'a carga em produção falha com ImproperlyConfigured: `resultado.returncode != 0`; `"ImproperlyConfigured" in resultado.stderr`',
        },
    },
    39: {
        "Com dois pagamentos aceitos, apenas um quita o pedido": {
            "tests/tecnicos/test_pedidos_quitacao.py::test_dois_pagamentos_aceitos_so_um_quita": 'um destino quita e o pedido fica pago: `_destino(quem_quita).destino == "quita"`; `situacao.situacao == "pago"`',
        },
        "Com dois pagamentos aceitos, o outro gera obrigação de devolução integral": {
            "tests/tecnicos/test_financeiro_concorrencia.py::test_dois_pagamentos_do_mesmo_pedido_ao_mesmo_tempo": 'a obrigação do pagamento duplicado é integral: `obrigacao.integral == Decimal("125.00")`; `MovimentoFinanceiro.objects.filter(tipo=T.ENTRADA_PARA_DEVOLUCAO).count() == 1`',
        },
        "Dois pagamentos simultâneos geram uma só entrada para devolução": {
            "tests/tecnicos/test_financeiro_concorrencia.py::test_dois_pagamentos_do_mesmo_pedido_ao_mesmo_tempo": 'uma entrada e obrigação integral: `entradas.count() == 1`; `obrigacao.integral == Decimal("125.00")`',
        },
    },
    40: {
        "O repasse manual ao fornecedor continua registrável": {
            "tests/tecnicos/test_repasse.py::test_o_repasse_so_baixa_a_obrigacao_com_o_fornecedor": 'o movimento do tipo repasse baixa a obrigação: `movimento.tipo == "repasse"`; `saldo(obrigacao) == D("90.00")`',
        },
        "O repasse consome apenas a obrigação com aquele fornecedor": {
            "tests/tecnicos/test_repasse.py::test_o_repasse_so_baixa_a_obrigacao_com_o_fornecedor": "os outros saldos ficam iguais: `_saldos(obrigacao) == outros`",
        },
    },
    41: {
        "O cancelamento administrativo afeta todos os compradores da rodada": {
            "tests/tecnicos/test_cancelamento_com_pedidos.py::test_cancela_o_nao_pago_e_preserva_o_pago": 'as parcelas de todos os compradores ficam removidas: `{p.situacao for p in`; `total_reservado(a.p1) == D("0")`',
        },
        "Não existe forma de cancelar a rodada para compradores selecionados": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http": 'a rota recusa a lista de compradores com 400: `_cancelar_pela_tela(client, a, credencial, "sim",`; `Rodada.objects.get(pk=a.rodada.pk).etapa == "pagamento"`',
        },
    },
    42: {
        "Somente o administrador ativo cancela a rodada": {
            "tests/tecnicos/test_cancelamento_da_rodada.py::test_so_o_administrador_ativo_cancela": "os outros recebem PermissionDenied e nada muda: `_foto(ci) == antes`; `pytest.raises(PermissionDenied)`",
        },
        "Comprador e fornecedor são recusados no cancelamento": {
            "tests/tecnicos/test_cancelamento_telas.py::test_comprador_e_fornecedor_nao_cancelam": 'a rodada fica em pagamento e a rota recusa: `_etapa(a) == "pagamento"`; `cliente.post(_rota(a), {"reembolso": "nao"}).status_code in (302, 403)`',
        },
        "A recusa vale também por acesso direto à rota": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http": 'o POST direto dá 302 ou 403: `cliente.post(_rota(a), {"reembolso": "nao"}).status_code in (302, 403)`',
        },
        "O cancelamento é aceito sem motivo": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http": 'cancelar sem reembolso passa e a rodada fica cancelada: `_cancelar_pela_tela(client, a, credencial, "nao").status_code == 302`; `Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"`',
        },
        "O cancelamento é aceito sem informação sobre o fornecedor": {
            "tests/tecnicos/test_cancelamento_da_rodada.py::test_a_assinatura_nao_aceita_lista_de_compradores_nem_motivo": 'a assinatura não tem parâmetro de fornecedor: `parametros == ["autor", "rodada", "com_reembolso", "mensagem"]`',
        },
    },
    43: {
        "Cada comprador que pagou recebe devolução integral de produtos, serviço e frete": {
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_reembolso_integral_do_pedido_pago": 'reembolso integral de 80,00, 4,00 e 10,35: `(reembolso.tipo, reembolso.autor,`; `(reembolso.produtos, reembolso.servico,`; `obrigacao.devido == D("94.35")`',
        },
        "A devolução integral desconta o que já foi devolvido": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago": 'o cancelamento devolve só 5,99 de produtos: `do_cancelamento.produtos == D("5.99")`',
        },
        "A devolução integral desconta o que está pendente": {
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido": 'o cancelamento devolve o restante e o total é 94,35: `(reembolso.produtos, reembolso.servico, reembolso.frete) == (`; `total == D("94.35")`',
        },
        "O total devolvido nunca ultrapassa o valor pago": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago": 'o estornado é igual ao total pago: `_estornado_de(id_externo) == pedido.total == D("9.99")`',
        },
        "Quem não pagou não recebe devolução": {
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_reembolso_integral_do_pedido_pago": "o pedido não pago não tem reembolso: `not Reembolso.objects.filter(pedido=y).exists()`",
        },
    },
    44: {
        "Cancelamento sem reembolso não gera obrigação de cancelamento": {
            "tests/tecnicos/test_cancelamento_telas.py::test_cancelar_sem_reembolso_pela_tela": 'nenhuma obrigação do cancelamento: `not ObrigacaoComComprador.objects.filter(motivo="cancelamento_da_rodada").exists()`',
        },
        "Cancelamento sem reembolso não inicia nenhuma parcela de devolução": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente": 'as obrigações ficam iguais e sem parcela nova: `list(ObrigacaoComComprador.objects.order_by("pk").values()) == antes`; `not ParcelaDeDevolucao.objects.filter(obrigacao=existente).exists()`',
        },
        "Uma obrigação de devolução existente continua pendente": {
            "tests/tecnicos/test_cancelamento_com_pedidos.py::test_pagamento_em_duplicidade_continua_como_estava": "a obrigação por duplicidade e o livro ficam como estavam: `ObrigacaoComComprador.objects.count() == obrigacoes`; `_livro() == antes`",
        },
        "A obrigação existente é liquidada depois": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente": "o estornado chega ao integral: `_estornado_de(id_y) == existente.integral`",
        },
    },
    45: {
        "Depois do cancelamento, os registros financeiros anteriores continuam inalterados": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_depois_da_aprovacao_do_resultado": "as aprovações do resultado ficam iguais: `list(AprovacaoDoResultado.objects.values()) == aprovacoes`",
        },
        "Depois do cancelamento, os registros financeiros anteriores continuam consultáveis": {
            "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_45_os_registros_anteriores_continuam_consultaveis_depois_do_cancelamento": 'o histórico mostra pedido.quitar e rodada.cancelar: `"pedido.quitar" in texto`; `"rodada.cancelar" in texto`',
        },
    },
    46: {
        "Reembolsos do cancelamento usam a plataforma de pagamentos": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_com_reembolso_durante_a_margem": 'o estorno é feito no simulador e a parcela conclui: `_estornado_de(id_x) == D("94.35")`; `ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao ==`',
        },
        "Se a plataforma for inviável, o cancelamento usa a devolução excepcional confirmada": {
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_falha_definitiva_segue_para_a_devolucao_excepcional": 'a parcela fica elegível excepcional: `parcela.situacao == "elegivel_excepcional"`; `pytest.raises(DevolucaoRecusada)`',
        },
        "O cancelamento não duplica devoluções pendentes": {
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido": "a obrigação pendente fica sem parcela nova: `not ParcelaDeDevolucao.objects.filter(obrigacao=de_caixa).exists()`",
        },
    },
    47: {
        "Comprador não consegue adicionar interesse depois da abertura do pagamento": {
            "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409": '409 com a mensagem de interesses bloqueados: `resposta.status_code == 409`; `( "Os interesses deste fornecedor não podem ser alterados nesta etapa."`',
        },
        "Comprador não consegue remover interesse depois da abertura do pagamento": {
            "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409": 'reduzir o interesse dá 409: `resposta.status_code == 409`; `( "Os interesses deste fornecedor não podem ser alterados nesta etapa." in`',
        },
        "Comprador não consegue alterar quantidades depois da abertura do pagamento": {
            "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409": 'aumentar o interesse dá 409: `resposta.status_code == 409`; `( "Os interesses deste fornecedor não podem ser alterados nesta etapa." in`',
        },
        "Administrador não consegue adicionar, remover ou alterar o pedido depois da abertura": {
            "tests/tecnicos/test_pedidos_abertura_tela.py::test_administrador_e_recusado_pela_politica_sem_a_mensagem_da_etapa": "POST do administrador recusado pela política, sem a mensagem da etapa: `resposta.status_code == 403`; `MENSAGEM_INTERESSES not in resposta.content.decode()`",
        },
    },
    48: {
        "A ocorrência de 2 unidades faltantes gera reembolso de produtos de R$ 20,00": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual": 'componentes 20,00, 1,00 e 4,00: `_componentes(resultado) == (D("20.00"), D("1.00"), D("4.00"))`',
        },
        "A ocorrência de 2 unidades faltantes gera reembolso de serviço de R$ 1,00": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual": 'componentes 20,00, 1,00 e 4,00: `_componentes(resultado) == (D("20.00"), D("1.00"), D("4.00"))`',
        },
        "A ocorrência de 2 unidades faltantes gera reembolso de frete de R$ 4,00": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual": 'componentes 20,00, 1,00 e 4,00: `_componentes(resultado) == (D("20.00"), D("1.00"), D("4.00"))`',
        },
        "O reembolso pontual soma R$ 25,00": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual": 'total 25,00 e obrigação de 25,00: `reembolso.total == D("25.00")`; `(obrigacao.devido, obrigacao.comprador_id) == (D("25.00"), a.c.pk)`',
        },
        "O pedido original continua igual": {
            "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenarios_48_e_52_a_ocorrencia_nao_muda_pedido_nem_rodada": "pedido e itens ficam iguais: `(list(Pedido.objects.values()), list(ItemDoPedido.objects.values())) == antes`",
        },
        "Ocorrência e reembolso ficam registrados à parte": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual": 'a ocorrência aponta o reembolso de motivo ocorrência_de_entrega: `reembolso.motivo == "ocorrencia_de_entrega"`; `ocorrencia.reembolso_id == reembolso.pk`',
        },
    },
    49: {
        "A soma das ocorrências de um item não pode ultrapassar a quantidade paga": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_49_a_soma_nao_passa_da_quantidade_paga": 'passa_do_saldo_do_item e nada muda: `pytest.raises(OcorrenciaRecusada)`; `erro.value.codigo == "passa_do_saldo_do_item"`',
        },
        "Uma ocorrência que ultrapasse a quantidade paga é recusada": {
            "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_ocorrencia_acima_do_saldo": '409 a quantidade passa do saldo: `resposta.status_code == 409`; `"A quantidade passa do saldo deste item (4 unidade)." in _texto(resposta)`',
        },
    },
    50: {
        "O comprador não consegue registrar falta": {
            "tests/tecnicos/test_retirada_comprador.py::test_as_rotas_do_comprador_nao_criam_ocorrencia": "a rota dá 405 e nenhum registro nasce: `detalhe.status_code == 405`; `_total_de_registros() == registros`",
        },
        "O comprador não consegue pedir substituição alterando o pedido": {
            "tests/tecnicos/test_retirada_comprador.py::test_as_rotas_do_comprador_nao_criam_ocorrencia": "pedido e itens ficam iguais: `(list(Pedido.objects.values()), list(ItemDoPedido.objects.values())) == antes`",
        },
    },
    51: {
        "Pagamento comunicado depois da apuração é registrado como devolução": {
            "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta": 'destino devolução e obrigação integral: `_destinos(y) == [("devolucao", "pedido_cancelado")]`; `obrigacao.integral == y.total`',
        },
        "Pagamento comunicado depois do cancelamento é registrado como devolução": {
            "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta": 'destino devolução e obrigação integral: `(destino.destino, destino.motivo) == ("devolucao", "pedido_cancelado")`; `obrigacao.integral == D("106.15")`',
        },
        "O pagamento tardio é tratado com auditoria de alerta crítico": {
            "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta": 'alerta crítico com os dados do pagamento: `(alerta.gravidade, alerta.chave) == ("critico", id_y)`; `alerta.dados == { "pagamento": id_y, "pedido": y.pk, "comprador": a.b.pk,`',
        },
        "O pagamento tardio não edita o pedido": {
            "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta": "a composição fica igual: `_composicao() == composicao`",
        },
    },
    52: {
        "Registrar uma ocorrência de entrega não cancela a rodada": {
            "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenarios_48_e_52_a_ocorrencia_nao_muda_pedido_nem_rodada": 'a rodada continua aguardando fornecedor: `Rodada.objects.get(pk=a.rodada.pk).etapa == "aguardando_fornecedor"`',
        },
        "Cancelar a rodada não registra ocorrências": {
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_52_cancelamento_com_ocorrencia_anterior": "continua uma só ocorrência: `OcorrenciaDeEntrega.objects.count() == 1`",
        },
    },
    53: {
        "As unidades que A pagou na caixa invalidada recebem estorno proporcional": {
            "tests/tecnicos/test_apuracao_viavel.py::test_estorno_proporcional_das_unidades_em_caixa_invalidada": 'produtos 20, serviço 1, frete 2,59: `(reembolso.produtos, reembolso.servico, reembolso.frete) == ( D("20.00"),`; `obrigacao.devido == D("23.59")`',
        },
        "As unidades da caixa invalidada voltam ao interesse com a posição original": {
            "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila": "a parcela volta pendente com a posição original: `(parcela.situacao, parcela.quantidade_pendente,`; `(restauracao.parcela_no_pedido_id, restauracao.parcela_id) ==`",
        },
        "As unidades voltam ao interesse antes da conclusão do estorno": {
            "tests/tecnicos/test_apuracao_viavel.py::test_a_restauracao_nao_espera_a_autorizacao_da_devolucao": 'nenhuma devolução e a parcela pendente: `ParcelaDeDevolucao.objects.count() == 0`; `parcela.situacao == "pendente"`',
        },
        "Os itens válidos de A no ciclo não mudam": {
            "tests/tecnicos/test_apuracao_viavel.py::test_so_a_parte_da_caixa_invalidada_e_estornada_e_restaurada": 'a parcela válida segue em pedido sem reembolso: `(primeira.situacao, primeira.quantidade_reservada) == ("em_pedido",`; `_reembolsos(z) == []`',
        },
    },
    54: {
        "O inadimplente B perde as reservas do fornecedor": {
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor": 'as parcelas ficam removidas com reserva zero: `[p.situacao for p in depois] == ["removida"] * 3`; `(nova.quantidade_reservada, nova.quantidade_pendente) == (D("0"), D("0"))`',
        },
        "O inadimplente B perde as posições na fila do fornecedor": {
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai": 'a pendente antiga sai da fila: `(antigo.situacao, antigo.quantidade_pendente) == ("removida", D("0"))`; `not na_fila.exists()`',
        },
        "Itens de B de outros fornecedores não são afetados": {
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_parcelas_de_outro_fornecedor_nao_mudam": "as parcelas do outro fornecedor ficam iguais: `_campos([de_g]) == antes`",
        },
    },
    55: {
        "A restauração repetida não duplica a parcela": {
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo": "uma só restauração: `len(_restauracoes()) == 1`",
        },
        "A restauração repetida não duplica a posição": {
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo": 'pendente 4 e a sequência original: `(depois.quantidade_pendente, depois.sequencia) == (D("4.000"), antes.sequencia)`',
        },
        "A restauração em paralelo com novas adições não duplica a reserva": {
            "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre": 'a reserva cabe no estoque: `(da_c.situacao, da_c.quantidade_reservada) == ("ativa", D("5.000"))`; `total_reservado(a.p1) <= D("11")`',
        },
        "Uma parcela adicionada depois da adição original da parcela restaurada fica atrás dela": {
            "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre": 'a adição de C só recebe o estoque livre: `(da_c.situacao, da_c.quantidade_reservada) == ("ativa", D("5.000"))`',
        },
    },
    56: {
        "Rodada que volta para interesse mantém o estoque cadastrado": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": 'os limites do estoque ficam iguais: `{e.produto_id: e.limite for e in EstoqueDaRodada.objects.filter(rodada=a.rodada)} == { a.p1.pk: D("11.000"), a.p2.pk: D("12.000"), }`',
        },
        "As reservas de quem pagou continuam com a ordem original": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": "as sequências ficam iguais: `{p.pk: p.sequencia for p in ParcelaDeInteresse.objects.all()} == antes`",
        },
        "As reservas dos inadimplentes são liberadas": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": 'as parcelas de B ficam removidas: `{p.situacao for p in ParcelaDeInteresse.objects.filter(comprador=a.b)} == {"removida"}`',
        },
        "As reservas liberadas dos inadimplentes ficam disponíveis": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": 'o total reservado é só o de quem pagou: `total_reservado(a.p1) == D("6.000")`; `total_reservado(a.p2) == D("4.000")`',
        },
        "Estornos pendentes não impedem novas adições": {
            "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_56_o_estorno_pendente_nao_impede_novas_adicoes": "a adição é aceita com a obrigação pendente: `ParcelaDeInteresse.objects.filter(comprador=novo, produto=a.p1).exists()`; `ObrigacaoComComprador.objects.filter(pedido=x).count() == 1`",
        },
        "Estornos pendentes não impedem novo fechamento": {
            "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente": 'o novo fechamento começa sem parcela de devolução: `a.rodada.etapa == "fechamento"`; `ParcelaDeDevolucao.objects.count() == 0`',
        },
    },
    57: {
        "O total reservado de cada produto nunca passa do estoque": {
            "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada": 'totais reservados 9 e 4: `total_reservado(a.p1) == D("9.000")`; `total_reservado(a.p2) == D("4.000")`',
        },
        "Nenhuma reserva aparece duplicada depois do retorno": {
            "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada": "reservada mais pendente cabe no original: `parcela.quantidade_reservada + parcela.quantidade_pendente <= ( parcela.quantidade_original )`",
        },
    },
    58: {
        "E-mail de conta removida é recusado no login por senha": {
            "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite": 'sem sessão: `"_auth_user_id" not in senha.session`',
        },
        "E-mail de conta removida é recusado no login por link": {
            "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link": "caso removido: nenhum link nem e-mail: `LinkDeAcesso.objects.count() == 0`; `len(mail.outbox) == 0`",
        },
        "E-mail de conta removida é recusado no login pelo Google": {
            "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite": 'sem sessão: `"_auth_user_id" not in google.session`',
        },
        "Um novo convite para o e-mail de conta removida não permite cadastro": {
            "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite": "EmailEmUso e nenhum convite: `pytest.raises(EmailEmUso)`; `Convite.objects.count() == 0`",
        },
        "O histórico financeiro continua consultável pelo administrador": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_20_o_administrador_consulta_o_historico_financeiro_do_removido": 'pedido.quitar e conta.remover no histórico: `"pedido.quitar" in acoes`; `"conta.remover" in acoes`',
        },
        "O histórico da conta removida continua consultável pelo administrador": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_20_o_administrador_consulta_o_historico_financeiro_do_removido": 'conta.remover no histórico: `"conta.remover" in acoes`',
        },
    },
    59: {
        "O endereço banido com outras maiúsculas é recusado no login e no novo cadastro": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_59_o_endereco_banido_com_outras_maiusculas_e_recusado_no_login": 'sem sessão com ANA@x.com: `"_auth_user_id" not in cliente.session, escrito`',
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_59_o_endereco_banido_com_outras_maiusculas_e_recusado_no_novo_cadastro": "EmailEmUso e nenhuma conta nova: `Conta.objects.count() == contas`; `pytest.raises(EmailEmUso)`",
        },
        "O banimento não vale para o alias com +": {
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_afeta_so_o_endereco_exato": 'o alias fica ativo e com sessão: `alias.situacao == Situacao.ATIVA`; `"_auth_user_id" in client.session`',
        },
        "O banimento não vale para o alias com pontos": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_59_o_alias_com_pontos_nao_e_afetado": 'a conta com pontos entra: `"_auth_user_id" in cliente.session`',
        },
        "O banimento não bloqueia o IP": {
            "tests/aceitacao/test_cenario_59_banimento_so_do_endereco.py::test_cenario_59_ip_dispositivo_e_telefone_nao_sao_bloqueados": 'outro login do mesmo IP entra: `"_auth_user_id" in dispositivo.session`',
        },
        "O banimento não bloqueia o dispositivo": {
            "tests/aceitacao/test_cenario_59_banimento_so_do_endereco.py::test_cenario_59_ip_dispositivo_e_telefone_nao_sao_bloqueados": 'outro login do mesmo navegador entra: `"_auth_user_id" in dispositivo.session`',
        },
        "O banimento não bloqueia o telefone": {
            "tests/aceitacao/test_cenario_59_banimento_so_do_endereco.py::test_cenario_59_ip_dispositivo_e_telefone_nao_sao_bloqueados": 'outra conta com o mesmo telefone entra: `"_auth_user_id" in dispositivo.session`',
        },
    },
    60: {
        "A suspensão continua reversível": {
            "tests/tecnicos/test_moderacao_servicos.py::test_reativar_volta_a_ativa_sem_restaurar_nada": 'reativar volta a conta a ativa: `depois.pop("situacao") == "ativa"`; `_auditorias("conta.reativar") == 1`',
        },
        "A suspensão não bane o e-mail": {
            "tests/tecnicos/test_moderacao_servicos.py::test_suspender_pela_tela_nao_encerra_a_sessao_nem_bane": "suspensa e nenhum e-mail banido: `_situacao(comprador) == Situacao.SUSPENSA`; `EmailBanido.objects.count() == 0`",
        },
    },
    61: {
        "Cada login de uma pessoa com duas contas vê só os dados da sua conta": {
            "tests/aceitacao/test_cenario_61_contas_independentes.py::test_cada_sessao_ve_so_a_propria_conta": 'a compradora não vê a fornecedora e vice-versa: `"Ana Fornecedora" not in do_comprador`; `"ana.fornecedor@exemplo.com" not in`; `"Ana Compradora" not in do_fornecedor`',
        },
        "Cada login vê só as permissões da sua conta: o fornecedor não compra": {
            "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta": '403 no carrinho e no pagamento: `cliente.get("/teste/carrinho/", **cabecalhos).status_code == 403`; `cliente.post("/teste/pagamento/", **cabecalhos).status_code == 403`',
        },
        "Cada login vê só as permissões da sua conta: o comprador não entra no portal do fornecedor": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_comprador_nao_entra_no_portal": "403 no portal: `[r.status_code for r in recusas] == [403] * 3`",
        },
        "A conta de fornecedor é recusada ao tentar comprar": {
            "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta": '403 e nenhuma view executada: `cliente.get("/teste/carrinho/", **cabecalhos).status_code == 403`; `cliente.post("/teste/pagamento/", **cabecalhos).status_code == 403`',
        },
        "A conta de fornecedor é recusada ao tentar comprar também por chamada direta à API": {
            "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta": 'a chamada direta dá 403: `metodo("/teste/pagamento/", **cabecalhos).status_code == 403`',
        },
    },
    62: {
        "Conta de fornecedor é criada pelo convite de fornecedor": {
            "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_fornecedor": 'o convite de fornecedor cria conta de fornecedor: `conta.papel == "fornecedor"`; `conta.fornecedor == f1`',
        },
        "Conta de comprador não é convertida em conta de fornecedor": {
            "tests/aceitacao/test_cenario_62_papel_imutavel.py::test_banco_recusa_trocar_o_papel_mesmo_com_fornecedor_preenchido": 'o banco recusa trocar o papel: `pytest.raises(DatabaseError, match="papel")`; `comprador.papel == "comprador"`',
        },
        "Conta de comprador não ganha o perfil de fornecedor": {
            "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_comprador": 'o comprador fica sem fornecedor: `conta.papel == "comprador"`; `conta.fornecedor is None`',
        },
    },
    63: {
        "Produto por peso a R$ 12,00/kg com incremento de 0,5 kg: 1,5 kg é aceito": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": 'kg, incremento 0,5: `(Unidade.KG, "0.5", "1.5", True)`; `resumo.reservado == D(entrada)`; `parcela.quantidade_reservada == D(entrada)`',
        },
        "Produto por peso a R$ 12,00/kg: 1,5 kg custa R$ 18,00": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": 'preço 12,00 no preparo; `(Unidade.KG, "0.5", "1.5", True)`: `calcular_subtotal(produto.preco, parcela.quantidade_reservada) == D("18.00")`',
        },
        "Produto por peso com incremento de 0,5 kg: 1,2 kg é recusado pelo servidor": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.KG, "0.5", "1.2", False)`: `pytest.raises(QuantidadeInvalida)`; `parcelas(produto) == []`',
        },
        "A recusa de 1,2 kg vale também pela API": {
            "tests/aceitacao/test_cenario_63_rota_1_2_kg.py::test_cenario_63_rota_recusa_1_2_kg_sem_gravar": 'POST direto com 1,2 kg, sem e com 1,5 reservado: `resposta.status_code == 200`; `"Interesse atualizado" not in resposta.content.decode()`; `total_reservado(produto) == D("1.500")`',
        },
    },
    64: {
        "0,35 kg a R$ 12,99/kg dá subtotal arredondado de R$ 4,55": {
            "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_e_arredondado_uma_vez_so": 'subtotal 4,55 para 0,350: `cobranca.itens[0].subtotal == D("4.55")`; `cobranca.itens[0].quantidade == D("0.350")`',
        },
        "O arredondamento de 12,99 × 0,35 acontece uma única vez": {
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_12_99_vezes_0_35": 'o produto exato vira 4,55: `arredondar_centavos(D("12.99") * D("0.35")) == D("4.55")`',
        },
    },
    65: {
        "A quantidade do produto por peso fica congelada na abertura": {
            "tests/tecnicos/test_pedidos_abertura.py::test_produto_por_peso_guarda_o_subtotal_arredondado": 'quantidade 0,350 e subtotal 4,55: `(item.quantidade, item.subtotal) == (D("0.350"), D("4.55"))`',
        },
        "O preço do produto por peso fica congelado na abertura": {
            "tests/tecnicos/test_pedidos_abertura.py::test_produto_por_peso_guarda_o_subtotal_arredondado": 'preço unitário 12,99 e subtotal 4,55: `(item.preco_unitario, item.subtotal) == (D("12.99"), D("4.55"))`',
        },
        "Não há ajuste posterior por pesagem": {
            "tests/tecnicos/test_pedidos_abertura_tela.py::test_nenhuma_rota_altera_pedido_item_t0_ou_frete": "nenhuma rota altera pedido ou item: `rotas_sem_politica() == []`; `suspeitas == []`",
        },
    },
    66: {
        "Cadastro de produto com múltiplo incompatível com o incremento é recusado pelo serviço": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido": "MultiploInvalido e nenhum produto: `pytest.raises(MultiploInvalido)`; `Produto.objects.count() == 0`",
        },
        "Cadastro de produto com múltiplo incompatível é recusado pela tela": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro": 'erro no formulário e nenhum produto: `"multiplo" in resposta.context["form"].errors`; `Produto.objects.count() == 0`',
        },
    },
    67: {
        "O fornecedor vê seus produtos": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor": 'P1 e P2 aparecem: `"P1" in texto`; `"P2" in texto`',
        },
        "O fornecedor vê as quantidades": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal": 'linhas com 11 e 12: `linhas == [ CABECALHO, "P1;unidade;11;;;10,00;110,00", "P2;unidade;12;6;2;5,00;60,00", ]`',
        },
        "O fornecedor vê os preços unitários": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal": '10,00 e 5,00: `linhas == [ CABECALHO, "P1;unidade;11;;;10,00;110,00", "P2;unidade;12;6;2;5,00;60,00", ]`',
        },
        "O fornecedor vê os valores totais dos produtos": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor": 'R$ 110,00 e total R$ 170,00: `"R$ 110,00" in texto`; `"Total dos produtos: R$ 170,00" in texto`',
        },
        "O fornecedor vê o andamento": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_portal_nao_expoe_dado_da_e14": 'Disponível para retirada: `"Disponível para retirada" in texto`',
        },
        "O fornecedor vê o pedido formal": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor": 'Pedido formal nº: `f"Pedido formal nº {pedido.pk}" in texto`',
        },
        "O fornecedor vê a previsão de entrega": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor": 'Previsão de entrega: `"Previsão de entrega: 11/11/2026" in texto`',
        },
        "Consulta de pagamentos individuais é recusada ao fornecedor": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele": "403 nas rotas de pagamento: `[r.status_code for r in recusas] == [403] * 9`",
        },
        "Consulta de dados de compradores é recusada ao fornecedor": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele": 'nenhum nome de comprador: `"Comprador A" not in texto`',
        },
        "Consulta da taxa de serviço é recusada ao fornecedor": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele": 'nenhum valor de taxa na tela: `"8,50" not in texto`',
        },
        "Consulta da reserva é recusada ao fornecedor": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele": "403 nas rotas de reserva: `[r.status_code for r in recusas] == [403] * 9`",
        },
        "Consulta de dados de outro fornecedor é recusada": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_rodada_de_outro_fornecedor_ou_inexistente_da_o_mesmo_404": "o mesmo 404: `[r.status_code for r in respostas] == [404, 404, 404]`; `len({r.content for r in respostas}) == 1`",
        },
        "A exportação do fornecedor só traz campos permitidos": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal": 'sete colunas permitidas: `linhas == [ CABECALHO, "P1;unidade;11;;;10,00;110,00",`; `len(next(iter(csv.reader(io.StringIO(resposta.content.decode()), delimiter=";"))))`',
        },
    },
    68: {
        "Falha na primeira tentativa e sucesso na segunda: duas tentativas registradas": {
            "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha": 'falha 1 e sucesso 2: `(um.resultado, um.resposta, um.ordem_automatica) == ("falha", "ConnectionError", 1)`; `(dois.resultado, dois.ordem_automatica) == ("sucesso", 2)`',
        },
        "Falha na primeira tentativa e sucesso na segunda: um envio": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_do_resultado_aprovado_ao_pedido_aceito": "um e-mail igual ao snapshot: `len(_emails_iguais_ao_snapshot(pedido)) == 1`",
        },
        "Falha na primeira tentativa e sucesso na segunda: sem aviso ao administrador": {
            "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha": "nenhuma notificação de falha: `not Notificacao.objects.filter(evento=EVENTO).exists()`",
        },
    },
    69: {
        "Três tentativas falham: não há quarta tentativa automática": {
            "tests/tecnicos/test_pedido_formal_envio.py::test_exatamente_tres_tentativas_automaticas": "três automáticas e nada depois: `(envio.situacao, envio.automaticas) ==`; `_processar(relogio, PRAZO + 120 * M) == 0`; `_processar(relogio, PRAZO + timedelta(days=1)) == 0`",
        },
        "Três tentativas falham: o administrador é notificado": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela": "o aviso tem link para o pedido formal: `aviso.link is not None`",
        },
        "Três tentativas falham: o botão Reenviar pedido fica disponível": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_depois_das_tres_falhas_o_formulario_aparece": 'a página traz o formulário com token: `"Envio automático concluído sem sucesso depois de 3 tentativas." in texto`; `\'name="token"\' in resposta.content.decode()`',
        },
        "O reenvio usa o mesmo pedido formal": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas": "o pedido formal fica igual: `_foto_do_pedido(pedido) == antes`",
        },
        "O reenvio usa os mesmos produtos, quantidades e valores": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas": "assunto e corpo iguais ao pedido: `(enviado.subject, enviado.body) == (pedido.assunto, pedido.corpo)`",
        },
    },
    70: {
        "Duplo clique em Reenviar pedido gera um único envio": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro": 'o segundo clique é reconhecido e um só e-mail sai: `"Este reenvio já tinha sido registrado." in _texto(segundo)`; `len([m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]) == 1`',
        },
        "Um novo clique feito depois gera uma nova tentativa registrada": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro": "token novo e dois e-mails ao todo: `novo != token`; `len(enviados) == 2`",
        },
        "O duplo clique não cria pedido novo": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez": "continua um só PedidoFormal do ciclo: `PedidoFormal.objects.filter(ciclo=pedido.ciclo).count() == 1`",
        },
        "O novo clique depois não cria pedido novo": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia": "continua um só PedidoFormal do ciclo: `PedidoFormal.objects.filter(ciclo=pedido.ciclo).count() == 1`",
        },
    },
    71: {
        "Na fase de interesse o administrador altera o mínimo": {
            "tests/tecnicos/test_rodadas_minimo.py::test_altera_o_minimo_em_interesse_e_audita": 'o mínimo vai de 150 para 200: `fornecedor.minimo == Decimal("200.00")`; `entrada.alteracoes == { "fornecedor": fornecedor.pk, "anterior": "150.00",`',
        },
        "Na fase de interesse o administrador altera o múltiplo": {
            "tests/tecnicos/test_catalogo_condicoes.py::test_alterar_e_remover_o_multiplo_em_interesse": 'o múltiplo muda e é removido: `produto.multiplo == D("2.000")`; `produto.multiplo is None`',
        },
        "Na fase de interesse o administrador altera o estoque": {
            "tests/tecnicos/test_rodadas_estoque.py::test_reducao_ate_o_reservado_e_aceita": 'o limite cai até o reservado: `estoque.limite == D("6.000")`; `[(e.alteracoes["anterior"], e.alteracoes["novo"]) for e in entradas] == [`',
        },
        "Redução de estoque abaixo da quantidade reservada é recusada": {
            "tests/tecnicos/test_rodadas_estoque.py::test_reducao_abaixo_do_reservado_e_recusada": 'EstoqueAbaixoDoReservado e limite igual: `pytest.raises(EstoqueAbaixoDoReservado, match="6")`; `estoque.limite == D("10.000")`',
        },
    },
    72: {
        "Do fechamento em diante alterar o mínimo é recusado": {
            "tests/tecnicos/test_rodadas_minimo.py::test_minimo_congelado_pelo_servico": 'CondicoesCongeladas e mínimo igual: `pytest.raises(CondicoesCongeladas, match=MENSAGEM)`; `fornecedor.minimo == Decimal("150.00")`',
        },
        "Do fechamento em diante alterar o múltiplo é recusado": {
            "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico": '409 e múltiplo igual: `resposta.status_code == 409`; `produto.multiplo == D("1.000")`',
        },
        "Do fechamento em diante alterar o estoque é recusado": {
            "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pelo_servico": 'CondicoesCongeladas e limite igual: `pytest.raises(CondicoesCongeladas)`; `estoque.limite == D("10.000")`',
        },
        "A recusa vale para o administrador": {
            "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pela_rota": 'a rota do administrador dá 409 e o limite fica igual: `resposta.status_code == 409`; `estoque.limite == D("10.000")`',
        },
        "A recusa vale pela API": {
            "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico": "a rota HTTP chamada direto recusa: `resposta.status_code == 409`; `MENSAGEM in resposta.content.decode()`",
        },
        "Alterar preço continua permitido no fechamento": {
            "tests/tecnicos/test_catalogo_incremento.py::test_preco_continua_editavel_no_fechamento": 'a alteração para 12,50 passa: `resposta.status_code == 302`; `produto.preco == D("12.50")`',
        },
        "A alteração de preço no fechamento atinge os interesses": {
            "tests/tecnicos/test_interesses_preco.py::test_preco_alterado_no_fechamento_atinge_o_carrinho": 'aviso ao comprador e subtotal novo: `len(avisos_de(a)) == 1`; `"Subtotal: R$ 8,99" in html`',
        },
    },
    73: {
        "Quando a rodada volta para interesse, as condições voltam a ser editáveis": {
            "tests/tecnicos/test_rodadas_ciclos.py::test_condicoes_voltam_a_ser_editaveis_na_volta_para_interesse": 'mínimo, múltiplo e estoque ficam editáveis: `c["fornecedor"].minimo == D("200.00")`; `(c["p"].multiplo, c["p"].incremento) ==`; `c["estoque_p"].limite == D("20.000")`',
        },
        "Os registros do ciclo anterior continuam com os valores originais": {
            "tests/tecnicos/test_rodadas_ciclos.py::test_cenario_73_ciclos_anteriores_nao_mudam": 'o ciclo 1 mantém mínimo e condições: `ciclo1.minimo == D("150.00")`; `_condicoes(ciclo1) == { c["p"].pk: (D("0.500"), D("3.000"), D("10.000")),`',
        },
    },
    74: {
        "As unidades pagas por A na caixa invalidada vão para a fila de pendentes do fornecedor": {
            "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila": 'a parcela fica pendente com 4 unidades: `(parcela.situacao, parcela.quantidade_pendente,`; `restauracao.quantidade == D("4.000")`',
        },
        "As unidades voltam à fila sem reservar estoque da rodada apurada": {
            "tests/tecnicos/test_apuracao_viavel.py::test_a_fila_nao_reserva_na_rodada_apurada": 'reservado zero e alocação zero: `total_reservado(a.p2) == D("0.000")`; `alocar_pendentes(a.fornecedor) == D("0.000")`',
        },
        "As unidades voltam à fila antes da conclusão do estorno": {
            "tests/tecnicos/test_apuracao_viavel.py::test_a_restauracao_nao_espera_a_autorizacao_da_devolucao": 'a parcela fica pendente sem devolução: `ParcelaDeDevolucao.objects.count() == 0`; `parcela.situacao == "pendente"`',
        },
        "O pedido congelado não muda": {
            "tests/tecnicos/test_apuracao_viavel.py::test_o_pedido_congelado_nao_muda": "pedido, itens e parcelas fotografados antes de _iniciar e relidos depois: `depois == antes`",
        },
        "Os itens válidos de A não mudam": {
            "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila": 'a parcela válida segue em pedido com 6: `(de_p1.situacao, de_p1.quantidade_reservada) == ("em_pedido", D("6.000"))`',
        },
    },
    75: {
        "Na próxima rodada, A recebe 6 reservadas": {
            "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original": 'A fica ativa com 6 e sem pendência: `estado(pa) == (SituacaoParcela.ATIVA, D("6"), D("0"))`',
        },
        "Na próxima rodada, C recebe 4 reservadas": {
            "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original": 'C fica ativa com 4: `estado(pc) == (SituacaoParcela.ATIVA, D("4"), D("4"))`',
        },
        "Na próxima rodada, 4 unidades de C continuam pendentes sem reserva": {
            "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original": 'C tem 4 reservadas e 4 pendentes: `estado(pc) == (SituacaoParcela.ATIVA, D("4"), D("4"))`',
        },
        "O total reservado é 10": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_do_produto_atende_a_fila_pela_sequencia_original": 'total reservado 10: `total_reservado(fp.p) == D("10.000")`',
        },
    },
    76: {
        "A adição de D sem estoque livre é recusada": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_adicao_sem_estoque_e_recusada_e_o_aumento_atende_c_antes_de_d": "EstoqueInsuficiente e D sem parcela: `pytest.raises(EstoqueInsuficiente)`; `not ParcelaDeInteresse.objects.filter(comprador=d).exists()`",
        },
        "Liberado ou aumentado o estoque, as 4 pendentes de C são atendidas antes de D": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_adicao_sem_estoque_e_recusada_e_o_aumento_atende_c_antes_de_d": 'C fica com 8 reservadas e o total é 14: `_estado(fp.c, fp.p) == ("ativa", D("8.000"), D("0.000"))`; `total_reservado(fp.p) == D("14.000")`',
        },
    },
    77: {
        "Unidades pendentes sem reserva não contam para o mínimo": {
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo": 'progresso 80 e pendente 5: `resultado.atingido is False`; `(participacao.reservado, participacao.pendente) == (D("0"), D("5"))`',
        },
        "Unidades pendentes sem reserva não entram em pedido quando a rodada abre pagamento": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas": 'o item do pedido tem só as reservadas: `item.quantidade == D("4.000")`',
        },
        "As pendentes continuam na fila para a rodada seguinte": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas": 'a parcela segue pendente com 4: `(parcela.situacao, parcela.quantidade_pendente) == ("pendente", D("4.000"))`',
        },
    },
    78: {
        "A apuração reexecutada não duplica parcela nem restauração": {
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo": "uma restauração e um reembolso: `len(_restauracoes()) == 1`; `len(_reembolsos(x)) == 1`",
        },
        "A reserva da fila em paralelo com novas adições não duplica a reserva": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem": 'a parcela reserva 4 e há uma só: `(pa.quantidade_reservada, pa.quantidade_pendente)`; `total_reservado(produto) == D("4")`; `ParcelaDeInteresse.objects.filter(produto=produto).c`',
        },
        "O total reservado nunca passa do estoque": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem": 'total reservado 4: `total_reservado(produto) == D("4")`',
        },
        "A ordem da fila segue a posição original": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro": 'A e C são atendidos antes de E: `_estado(fp.a, fp.p) == ("ativa", D("6.000"), D("0.000"))`; `_estado(fp.c, fp.p) == ("ativa", D("4.000"), D("4.000"))`',
        },
    },
    79: {
        "O inadimplente B não tem unidade do fornecedor na fila de pendentes": {
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor": 'as parcelas ficam removidas com pendência zero: `[p.situacao for p in depois] == ["removida"] * 3`; `(nova.quantidade_reservada, nova.quantidade_pendente) == (D("0"),`',
        },
        "A pendente antiga do inadimplente também sai da fila": {
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai": 'removida e fora da fila: `(antigo.situacao, antigo.quantidade_pendente) == ("removida", D("0"))`; `not na_fila.exists()`',
        },
    },
    80: {
        "Convite para e-mail já usado por outra conta é recusado": {
            "tests/tecnicos/test_convites_emissao.py::test_emissao_recusa_email_ja_em_uso_por_qualquer_conta": "EmailEmUso e nenhum convite: `pytest.raises(EmailEmUso)`; `Convite.objects.count() == 0`",
        },
        "Cadastro para e-mail já usado por outra conta é recusado": {
            "tests/tecnicos/test_convites_cadastro_concorrencia.py::test_dois_convites_com_mesmo_email_normalizado_em_paralelo": "um só cadastro vence: `len(erros) == 1`; `Conta.objects.filter(email_normalizado=email).count() == 1`",
        },
        "O e-mail escrito com maiúsculas ou espaços diferentes também é recusado": {
            "tests/tecnicos/test_contas_modelo.py::test_conta_recusa_email_em_uso_com_variacao_de_caixa_e_espacos": "EmailEmUso com a variação: `pytest.raises(EmailEmUso)`",
        },
    },
    81: {
        "As contas de comprador e de fornecedor da mesma pessoa funcionam de forma independente": {
            "tests/tecnicos/test_convites_cadastro.py::test_comprador_e_fornecedor_com_emails_diferentes_sao_contas_independentes": 'cada início mostra a própria conta: `"Ana Compradora" in inicio_a`; `"Ana Fornecedora" in inicio_b`',
        },
        "Banir o e-mail do comprador não bloqueia o do fornecedor": {
            "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa": 'o fornecedor entra e o comprador não: `sessao_fornecedor.get("/inicio/").status_code == 200`; `sessao_comprador.get("/inicio/").status_code == 302`',
        },
    },
    82: {
        "Google com e-mail de uma conta acessa somente essa conta": {
            "tests/tecnicos/test_contas_google_login.py::test_segundo_login_com_o_mesmo_uid_entra_na_mesma_conta": 'a sessão é da mesma conta: `outro.session["_auth_user_id"] == str(conta.pk)`',
        },
        "Google com e-mail de uma conta nunca cria uma segunda": {
            "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social": 'a contagem de contas fica igual: `client.session["_auth_user_id"] == str(conta.pk)`; `Conta.objects.count() == antes`',
        },
        "Google com e-mail sem conta nem convite válido não cria conta": {
            "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada": "sem sessão e contagens iguais: `not _autenticado(client)`; `_contagens() == antes`",
        },
    },
    83: {
        "No banimento, as duas sessões abertas são invalidadas": {
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes": "nenhuma sessão da conta resta: `_sessoes_da_conta(conta) == 0`; `UserSession.objects.filter(user=conta).count() == 0`",
        },
        "No banimento, a próxima requisição de cada sessão é recusada": {
            "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou": 'redireciona para entrar e perde a sessão: `resposta.status_code == 302`; `"_auth_user_id" not in cliente.session`',
        },
        "Novo login por senha de conta banida é recusado": {
            "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite": 'sem sessão: `"_auth_user_id" not in senha.session`',
        },
        "Novo login por link de conta banida é recusado": {
            "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link": "caso banido: nenhum link nem e-mail: `LinkDeAcesso.objects.count() == 0`; `len(mail.outbox) == 0`",
        },
        "Novo login pelo Google de conta banida é recusado": {
            "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google": "caso banido: sem sessão: `not _autenticado(client)`",
        },
        "Os históricos são preservados": {
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_preserva_conta_historico_e_convite": 'o convite fica e a auditoria da remoção existe: `Convite.objects.filter(pk=convite.pk).exists()`; `EntradaAuditoria.objects.filter(acao="conta.remover",`',
        },
    },
    84: {
        "usuario@gmail.com e usuario+teste@gmail.com podem pertencer a contas distintas": {
            "tests/aceitacao/test_cenarios_84_aliases_contas_distintas.py::test_cenario_84_aliases_com_mais_sao_contas_distintas": "duas contas pelo cadastro por convite: `[c.email_normalizado for c in contas] == [BASE, ALIAS]`; `contas[0].pk != contas[1].pk`",
        },
        "Banir um endereço não afeta o outro": {
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_afeta_so_o_endereco_exato": 'o alias fica ativo e com sessão: `alias.situacao == Situacao.ATIVA`; `"_auth_user_id" in client.session`',
        },
    },
    85: {
        "Produto em litros com incremento de 0,5 L: 1,5 L é aceito": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.LITRO, "0.5", "1.5", True)`: `resumo.reservado == D(entrada)`; `parcela.quantidade_reservada == D(entrada)`',
        },
        "Produto em litros com incremento de 0,5 L: 1,2 L é recusado": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.LITRO, "0.5", "1.2", False)`: `pytest.raises(QuantidadeInvalida)`; `parcelas(produto) == []`',
        },
        "Produto em unidades com incremento 1: 2 é aceito": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.UNIDADE, "1", "2", True)`: `resumo.reservado == D(entrada)`; `parcela.quantidade_reservada == D(entrada)`',
        },
        "Produto em unidades com incremento 1: 2,5 é recusado": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.UNIDADE, "1", "2.5", False)`: `pytest.raises(QuantidadeInvalida)`; `parcelas(produto) == []`',
        },
        "Produto em kg com incremento de 0,25 kg: 0,75 kg é aceito": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.KG, "0.25", "0.75", True)`: `resumo.reservado == D(entrada)`; `parcela.quantidade_reservada == D(entrada)`',
        },
        "As validações de quantidade ocorrem no servidor, inclusive pela API": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas": "validar_quantidade levanta QuantidadeInvalida: `pytest.raises(QuantidadeInvalida)`",
            "tests/aceitacao/test_cenario_63_rota_1_2_kg.py::test_cenario_63_rota_recusa_1_2_kg_sem_gravar": 'rota HTTP chamada direto com 1,2 kg: `resposta.status_code == 200`; `"Interesse atualizado" not in resposta.content.decode()`; `total_reservado(produto) == D("1.500")`',
        },
    },
    86: {
        "Incremento igual a zero é recusado no cadastro do produto": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela": 'caso `"0"` do `parametrize`: `"incremento" in resposta.context["form"].errors`; `Produto.objects.count() == 0`',
        },
        "Incremento negativo é recusado no cadastro do produto": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela": 'caso `"-1"` do `parametrize`: `"incremento" in resposta.context["form"].errors`; `Produto.objects.count() == 0`',
        },
    },
    87: {
        "Múltiplo de 1 kg com incremento de 0,25 kg é aceito": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro": 'kg do _dados da tela; caso `("0,25", "1")`: `resposta.status_code == 302`; `Produto.objects.get().multiplo == D(multiplo.replace(",", "."))`',
        },
        "Múltiplo de 1 kg com incremento de 0,3 kg é recusado": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido": 'kg no corpo; caso `("0.3", "1")`: `pytest.raises(MultiploInvalido)`; `Produto.objects.count() == 0`',
        },
        "Na fase de interesse, alteração que torne o múltiplo incompatível é recusada": {
            "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_invalido_em_interesse": 'erro no formulário e múltiplo igual: `"multiplo" in resposta.context["form"].errors`; `produto.multiplo == D("1.000")`',
        },
        "A partir do fechamento, qualquer alteração de múltiplo é recusada": {
            "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico": '409 e múltiplo igual: `resposta.status_code == 409`; `produto.multiplo == D("1.000")`',
        },
    },
    88: {
        "7,99/kg × 0,25 kg tem subtotal cobrado de R$ 2,00": {
            "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item": 'subtotais 2,00, 0,63 e 4,55: `[i.subtotal for i in cobranca.itens] == [D("2.00"), D("0.63"), D("4.55")]`',
        },
        "O produto exato 7,99 × 0,25 é arredondado para R$ 2,00": {
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_7_99_vezes_0_25": 'arredondar_centavos dá 2,00: `arredondar_centavos(D("7.99") * D("0.25")) == D("2.00")`',
        },
    },
    89: {
        "2,50/kg × 0,25 kg arredonda para R$ 0,63": {
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_2_50_vezes_0_25": 'arredondar_centavos dá 0,63: `arredondar_centavos(D("2.50") * D("0.25")) == D("0.63")`',
        },
        "Dois itens de R$ 0,625 somam P = R$ 1,26": {
            "tests/tecnicos/test_pedidos_calculo.py::test_produtos_soma_os_subtotais_ja_arredondados": 'produtos 1,26: `cobranca.produtos == D("1.26")`',
        },
        "A soma dos subtotais arredondados não é R$ 1,25": {
            "tests/tecnicos/test_interesses_progresso.py::test_arredondamento_por_comprador": 'elegível 1,26 e bruto 1,25: `item.valor_elegivel == D("1.26")`; `item.valor_bruto == D("1.25")`',
        },
    },
    90: {
        "O preço novo do catálogo não altera o valor registrado de R$ 2,00": {
            "tests/aceitacao/test_cenarios_90_item_inteiro_de_0_25_kg.py::test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado": 'preço do produto 8,99 e item registrado a 7,99: `produto.preco == D("8.99")`; `ItemDoPedido.objects.get(pk=item.pk).preco_unitario == D("7.99")`',
        },
        "A ocorrência da quantidade inteira reembolsa o valor registrado de produtos": {
            "tests/aceitacao/test_cenarios_90_item_inteiro_de_0_25_kg.py::test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado": 'a linha do reembolso é o item inteiro, 0,250 por 2,00: `(linha.item_id, linha.quantidade, linha.valor) == (item.pk, D("0.250"), D("2.00"))`',
        },
        "Serviço e frete do reembolso são proporcionais aos valores registrados": {
            "tests/aceitacao/test_cenarios_90_item_inteiro_de_0_25_kg.py::test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado": 'serviço 0,10 e frete 0,40 sobre os registrados: `componentes(registrado) == (D("2.00"), D("0.10"), D("0.40"))`',
        },
    },
    91: {
        "A devolução integral do cancelamento soma exatamente os valores cobrados registrados": {
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenarios_90_e_91_integral_devolve_exatamente_o_cobrado": 'o acumulado do pedido é 100,00, 5,00 e 20,00: `acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))`',
        },
        "A devolução integral desconta as devoluções já concluídas": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago": 'o estornado total é o pago e o cancelamento devolve 5,99: `_estornado_de(id_externo) == D( "2.50" )`; `do_cancelamento.produtos == D("5.99")`',
        },
        "A devolução integral desconta as devoluções pendentes": {
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido": 'o cancelamento devolve o restante e o total é 94,35: `(reembolso.produtos, reembolso.servico, reembolso.frete) == (`; `total == D("94.35")`',
        },
    },
    92: {
        "Depois de um envio bem-sucedido, o botão Reenviar pedido está disponível": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso": 'a página traz o campo do token: `achado, "a página não traz o campo token"`',
        },
        "O acionamento do reenvio gera uma única tentativa": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso": 'a tentativa manual é uma só: `[t.tipo for t in _tentativas()] == ["automatica", "manual"]`',
        },
        "O reenvio usa o mesmo pedido formal e o mesmo conteúdo": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas": "assunto e corpo iguais e o pedido igual: `(enviado.subject, enviado.body) == (pedido.assunto, pedido.corpo)`; `_foto_do_pedido(pedido) == antes`",
        },
        "O reenvio depois do sucesso não gera tentativas automáticas adicionais": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico": "nada automático e duas tentativas ao todo: `processar(relogio, PRAZO + 24 * 60 * M) == 0`; `len(_tentativas()) == 2`",
        },
    },
    93: {
        "Reenvio manual que falha tem a falha registrada": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_que_falha_e_registrado_e_o_botao_continua": 'tentativa manual com falha ConnectionError: `(registrado.tentativa.tipo, registrado.tentativa.resultado) == ("manual",`; `registrado.tentativa.resposta == "ConnectionError"`',
        },
        "Reenvio manual que falha não inicia tentativa automática": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_que_falha_e_registrado_e_o_botao_continua": 'nada automático depois: `processar(relogio, PRAZO + 24 * 60 * M) == 0`; `[t.tipo for t in _tentativas()] == ["automatica"] * 3 + ["manual"]`',
        },
        "Reenvio manual que falha mantém o botão disponível": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_que_falha_e_registrado_e_o_botao_continua": "pode_reenviar continua verdadeiro: `pode_reenviar(pedido)[0] is True`",
        },
    },
    94: {
        "Durante o ciclo automático o reenvio manual é recusado pelo serviço": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado": 'ciclo_em_andamento e nenhuma consulta: `erro.value.codigo == "ciclo_em_andamento"`; `not consultas`',
        },
        "Durante o ciclo automático o reenvio manual é recusado pela tela": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenvio_durante_o_ciclo_e_recusado_com_409": '409 e só a tentativa automática: `resposta.status_code == 409`; `[t.tipo for t in _tentativas()] == ["automatica"]`',
        },
    },
    95: {
        "Dois acionamentos concorrentes da mesma solicitação geram um único envio": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_em_paralelo_envia_uma_vez": "uma tentativa nova e um e-mail: `(resultados[0].valor.nova,`; `len(_enviados()) == 1`; `len([t for t in _tentativas() if t.tipo ==`",
        },
        "Dois acionamentos distintos geram duas tentativas registradas": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia": "dois e-mails iguais ao snapshot: `len(_emails_iguais_ao_snapshot(pedido)) == 2`",
        },
        "Em nenhum caso há segundo pedido formal": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia": "continua um só PedidoFormal do ciclo: `PedidoFormal.objects.filter(ciclo=pedido.ciclo).count() == 1`",
        },
        "Em nenhum caso há mudança no conteúdo original": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez": "o e-mail enviado tem o assunto e o corpo do pedido: `(enviado.subject, enviado.body) == (pedido.assunto, pedido.corpo)`",
        },
    },
    96: {
        "O carrinho mostra Reservado: 6 e Pendente: 4 de um produto": {
            "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado": 'Reservado: 6 e Pendente: 4: `"Reservado: 6" in html`; `"Pendente: 4" in html`',
        },
        "O carrinho mostra reservado e pendente separados com o estoque do produto zerado": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero": 'Reservado: 4 e Pendente: 4 com livre zero: `"Reservado: 4" in texto`; `"Pendente: 4" in texto`',
        },
        "O histórico (Meus pedidos) mostra Reservado: 6 e Pendente: 4, inclusive com o estoque do produto zerado": {
            "tests/aceitacao/test_cenario_96_historico.py::test_cenario_96_historico_mostra_reservado_e_pendente_com_estoque_zerado": 'A com 6 reservados e 4 pendentes reais, livre zero, em GET /pedidos/: `"Reservado: 6" in secao`; `"Pendente: 4" in secao`; `total_reservado(fp.p) == D("6.000")`',
        },
    },
    97: {
        "Remover 2 das 4 pendentes faz a pendência cair para 2": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia": 'reservado 6 e pendente 2: `(resumo.reservado, resumo.pendente) == (D("6"), D("2"))`; `estado(parcela) == (SituacaoParcela.ATIVA, D("6"), D("2"))`',
        },
        "Remover pendentes não muda as reservas de A": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia": 'a parcela segue ativa com 6 reservadas: `estado(parcela) == (SituacaoParcela.ATIVA, D("6"), D("2"))`',
        },
        "Remover pendentes não muda as reservas de outros compradores": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia": 'a outra parcela fica igual: `estado(outra) == (SituacaoParcela.ATIVA, D("5"), D("0"))`',
        },
        "Remover pendentes não muda as posições FIFO de outras parcelas": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia": "as sequências ficam iguais: `(parcela.sequencia, outra.sequencia) == sequencias`",
        },
        "Remover pendentes não muda o reembolso já devido a A": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno": 'reembolsos e obrigações iguais: `( list( Reembolso.objects.filter(pedido__comprador=fp.c).values_list( "chave",`; `( list( ObrigacaoComComprador.objects.filter(comprador=fp.c).values_list( "pk",`',
        },
        "Ao remover as 2 restantes, a pendência zera": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia": 'reservado 6 e pendente 0: `(resumo.reservado, resumo.pendente) == (D("6"), D("0"))`',
        },
        "Ao remover as 2 restantes, a parcela sai da fila": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia": 'a parcela fica ativa com pendente 0: `estado(parcela) == (SituacaoParcela.ATIVA, D("6"), D("0"))`',
        },
    },
    98: {
        "Remoção de pendente maior que a existente é recusada sem alteração": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava": 'caso `"5"` do `parametrize`: `pytest.raises(RemocaoAcimaDoPendente)`; `auditorias(ACAO) == []`',
        },
        "Remoção de pendente fora do incremento é recusada sem alteração": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava": 'caso `"1.5"` do `parametrize`: `pytest.raises(QuantidadeInvalida)`; `auditorias(ACAO) == []`',
        },
    },
    99: {
        "A remoção de pendentes sobre item de pedido congelado é recusada pelo servidor": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao": "RemocaoAcimaDoPendente com pendente 0: `pytest.raises(RemocaoAcimaDoPendente)`; `erro.value.pendente == 0`",
        },
        "A rota de remoção não alcança o item do pedido congelado": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_com_o_pk_real_do_item_congelado_e_recusada": 'POST com o pk real do item de A em Q: `resposta.status_code in (200, 404, 409)`; `list(ItemDoPedido.objects.order_by("pk").values()), list(Reembolso.objects.order_by("pk").values()),`',
        },
        "Pedido e registros financeiros não mudam": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido": 'itens, reembolsos e obrigações iguais: `( list(ItemDoPedido.objects.order_by("pk").values()), list(Reembolso.objects.order_by("pk").values()), _estado(fp.a, fp.q), ) == antes`',
        },
    },
    100: {
        "Em paralelo com a alocação da fila, reservado mais pendente nunca passa da quantidade original": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam": "reservado mais pendente cabe no original: `parcela.quantidade_reservada + parcela.quantidade_pendente <= parcela.quantidade_original`",
        },
        "Em paralelo com a alocação da fila, nenhuma reserva passa do estoque": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam": 'o total reservado cabe no estoque: `total_reservado(produto) <= D("10")`',
        },
        "A quantidade removida nunca vira reserva": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam": "a remoção concorrente é recusada com pendente 0: `isinstance(resultados[1].excecao, RemocaoAcimaDoPendente)`; `resultados[1].excecao.pendente == 0`",
        },
    },
    101: {
        "Quando D remove 3 reservadas, C recebe as 3 antes de qualquer nova reserva": {
            "tests/tecnicos/test_interesses_fila.py::test_liberacao_vai_para_a_fila_na_mesma_transacao": 'C fica com 3 reservadas e o total é 10: `estado(pc) == (SituacaoParcela.ATIVA, D("3"), D("1"))`; `total_reservado(produto) == D("10")`',
        },
        "Um interesse novo de E feito ao mesmo tempo recebe só o que sobrar": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado": "E é recusado e fica sem parcela: `isinstance(resultados[1].excecao, EstoqueInsuficiente)`; `ParcelaDeInteresse.objects.filter(comprador=e).count() == 0`",
        },
    },
    102: {
        "Pendentes do fornecedor X nunca são alocados em rodada do fornecedor Y": {
            "tests/tecnicos/test_interesses_fila.py::test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele": 'alocação zero e a pendente de X intacta: `alocar(rodada_x.fornecedor) == 0`; `estado(pq) == (SituacaoParcela.PENDENTE, D("0"), D("4"))`',
        },
    },
    103: {
        "As reservas dos adimplentes ficam na própria rodada": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": 'as parcelas de quem pagou ficam ativas: `[(p.situacao, p.quantidade_reservada) for p in de_p1] == [("ativa",`; `[(p.situacao, p.quantidade_reservada) for p in de_p2] == [("ativa",`',
        },
        "As reservas dos adimplentes não passam pela fila de pendentes": {
            "tests/tecnicos/test_apuracao_retorno.py::test_unidades_de_caixa_invalidada_ficam_reservadas_sem_passar_pela_fila": "nenhuma restauração de caixa: `RestauracaoDeCaixa.objects.count() == 0`",
        },
    },
    104: {
        "O progresso elegível é R$ 80,00 com as 5 pendentes de C fora": {
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo": 'elegível 80,00 e faltam 20,00: `resultado.valor_elegivel == D("80.00")`; `resultado.falta == D("20.00")`',
        },
        "O fechamento não pode ser iniciado por causa das pendentes de C": {
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_minimo_nao_conta_pendentes": 'minimo_nao_atingido e a etapa fica em interesse: `erro.value.codigo == "minimo_nao_atingido"`; `etapa(rodada) == Etapa.INTERESSE`',
        },
        "Se a rodada chegar ao pagamento, as pendentes de C não entram em pedido": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas": 'o item do pedido tem só as reservadas: `item.quantidade == D("4.000")`',
        },
        "Se a rodada chegar ao pagamento, as pendentes de C não entram em cobrança": {
            "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_104_a_cobranca_do_pedido_ignora_as_pendentes": 'o pedido cobra só as 4 reservadas: `pedido.produtos == calcular_subtotal(fp.p.preco, D("4.000"))`',
        },
        "As pendentes de C continuam na fila": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas": 'a parcela segue pendente com 4: `(parcela.situacao, parcela.quantidade_pendente) == ("pendente", D("4.000"))`',
        },
    },
    105: {
        "A alteração do incremento para 0,25 kg é aceita": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_compativel_e_aceito": '302 e incremento 0,250: `resposta.status_code == 302`; `produto.incremento == D("0.250")`',
        },
        "A alteração compatível do incremento não muda nenhum interesse": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_compativel_e_aceito": "as parcelas ficam iguais: `_estado_das_parcelas() == antes`",
        },
    },
    106: {
        "A alteração para 1 kg é recusada porque 1,5 kg reservado deixa de ser múltiplo": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado": 'IncrementoIncompativel de quantidade: `pytest.raises(IncrementoIncompativel, match=MSG_QUANTIDADE)`; `erro.value.codigo == "quantidade"`',
        },
        "A alteração para 2 kg é recusada porque o múltiplo de 3 kg não é divisível por 2": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_o_multiplo_e_recusado": 'sem as reservadas, só a pendente de 2,0 em uso: `erro.value.codigo == "multiplo"`; `pytest.raises(IncrementoIncompativel, match=MSG_MULTIPLO)`',
        },
        "Na recusa da alteração para 1 kg, nada é alterado": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado": 'incremento e parcelas iguais: `produto.incremento == D("0.500")`; `_estado_das_parcelas() == antes`',
        },
        "Na recusa da alteração para 2 kg, nada é alterado": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_para_2_no_cenario_106_e_recusado": 'incremento igual e nenhuma auditoria: `produto.incremento == D("0.500")`; `EntradaAuditoria.objects.count() == 0`',
        },
    },
    107: {
        "A partir do fechamento, alterar o incremento é recusado pelo serviço": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_congelado": 'CondicoesCongeladas e incremento igual: `pytest.raises(CondicoesCongeladas)`; `produto.incremento == D("0.500")`',
        },
        "A recusa de alterar o incremento no fechamento vale para o administrador pela rota": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_congelado": "a rota do administrador dá 409: `resposta.status_code == 409`; `MENSAGEM in resposta.content.decode()`",
        },
        "A alteração de preço continua permitida no fechamento": {
            "tests/tecnicos/test_catalogo_incremento.py::test_preco_continua_editavel_no_fechamento": 'a alteração para 12,50 passa: `resposta.status_code == 302`; `produto.preco == D("12.50")`',
        },
    },
    108: {
        "Alteração de incremento e adição em paralelo: ou a adição é validada ou a alteração é recusada": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam": 'a alteração é recusada por IncrementoIncompativel ou a adição por QuantidadeInvalida: `isinstance(resultados[1].excecao,`; `resultados[1].excecao.codigo == "quantidade"`',
        },
        "Nunca fica parcela fora do incremento vigente": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam": "a quantidade reservada é múltipla do incremento: `parcela.quantidade_reservada % incremento == 0`",
        },
    },
    109: {
        "Ovos (unidade, incremento 1): 12 é aceito": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.UNIDADE, "1", "12", True)`: `resumo.reservado == D(entrada)`; `parcela.quantidade_reservada == D(entrada)`',
        },
        "Ovos (unidade, incremento 1): 12,5 é recusado": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.UNIDADE, "1", "12.5", False)`: `pytest.raises(QuantidadeInvalida)`; `parcelas(produto) == []`',
        },
        "Maçãs (unidade, incremento 2): 4 é aceito": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.UNIDADE, "2", "4", True)`: `resumo.reservado == D(entrada)`; `parcela.quantidade_reservada == D(entrada)`',
        },
        "Maçãs (unidade, incremento 2): 3 é recusado": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.UNIDADE, "2", "3", False)`: `pytest.raises(QuantidadeInvalida)`; `parcelas(produto) == []`',
        },
        "Banana (kg, 0,25): 1,25 é aceito": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.KG, "0.25", "1.25", True)`: `resumo.reservado == D(entrada)`; `parcela.quantidade_reservada == D(entrada)`',
        },
        "Leite (litro, 0,5): 2,5 é aceito": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.LITRO, "0.5", "2.5", True)`: `resumo.reservado == D(entrada)`; `parcela.quantidade_reservada == D(entrada)`',
        },
        "Caixa de produtos (caixa, 1): 3 é aceito": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.CAIXA, "1", "3", True)`: `resumo.reservado == D(entrada)`; `parcela.quantidade_reservada == D(entrada)`',
        },
        "Caixa de produtos (caixa, 1): 1,5 é recusado": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": '`(Unidade.CAIXA, "1", "1.5", False)`: `pytest.raises(QuantidadeInvalida)`; `parcelas(produto) == []`',
        },
    },
    110: {
        "O incremento 0 é recusado": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_zero_e_recusado_e_o_produto_nao_e_criado": "IncrementoInvalido e nenhum produto: `pytest.raises(IncrementoInvalido)`; `Produto.objects.count() == 0`",
        },
        "O incremento -1 é recusado": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_negativo_e_recusado_e_o_produto_nao_e_criado": "IncrementoInvalido e nenhum produto: `pytest.raises(IncrementoInvalido)`; `Produto.objects.count() == 0`",
        },
        "O incremento 0,0001 é recusado": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_com_mais_de_3_casas_e_recusado_e_o_produto_nao_e_criado": "IncrementoInvalido e nenhum produto: `pytest.raises(IncrementoInvalido)`; `Produto.objects.count() == 0`",
        },
        "Os incrementos 0,001 e 2 são aceitos": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos": 'casos `("2", D(2))` e `("0.001", D("0.001"))`: `validar_incremento(entrada) == esperado`',
        },
    },
    111: {
        "Maçãs com incremento 2 e múltiplo 12 são aceitas": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro": 'caso `("2", "12")`: `resposta.status_code == 302`; `Produto.objects.get().multiplo == D(multiplo.replace(",", "."))`',
        },
        "Com múltiplo 5 e incremento 2 a configuração é recusada pelo serviço": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido": 'caso `("2", "5")`: `pytest.raises(MultiploInvalido)`; `Produto.objects.count() == 0`',
        },
        "Com múltiplo 5 e incremento 2 a configuração é recusada pelo formulário": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro": 'caso `("2", "5")`: `"multiplo" in resposta.context["form"].errors`; `Produto.objects.count() == 0`',
        },
    },
    112: {
        "O item de 1,000 kg a R$ 7,99/kg tem subtotal registrado de R$ 7,99": {
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_117_cada_devolucao_e_registrada_separadamente": 'item kg 1,000 a 7,99: `Unidade.KG, D("1.000"), D("7.99")`; `ItemDoPedido.objects.get(pk=item.pk).subtotal == D("7.99")`',
        },
        "A ocorrência de 0,25 kg reembolsa R$ 2,00 de produtos": {
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_112_parcial_usa_o_valor_registrado": 'item kg 1,000 a 7,99: `Unidade.KG, D("1.000"), D("7.99")`; `componentes(parcial(item, "0.25"))[0] == D("2.00")`',
        },
        "Uma mudança posterior do preço não altera o valor": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo": 'reembolso de 2,00 pelo registrado: `registrado.reembolso.produtos == D("2.00")`; `(linha.item_id, linha.quantidade, linha.valor) == (item.pk, D("0.250"),`',
        },
    },
    113: {
        "Três ocorrências de 0,25 kg reembolsam R$ 2,00 cada": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente": 'item kg 1,000 a 7,99, parciais de 0,25: `Unidade.KG, D("1.000"), D("7.99")`; `[p for p, _, _ in feitos] == [D("2.00"), D("2.00"), D("2.00"), D("1.99")]`',
        },
        "A quarta ocorrência reembolsa R$ 1,99": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente": 'a quarta leva 1,99 com serviço 0,10 e frete 0,40: `[p for p, _, _ in feitos] == [D("2.00"), D("2.00"), D("2.00"),`; `feitos[3][1:] == (D("0.10"), D("0.40"))`',
        },
        "A soma dos reembolsos é exatamente R$ 7,99": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente": 'a soma dos produtos é 7,99: `sum((p for p, _, _ in feitos), D("0.00")) == D("7.99")`',
        },
    },
    114: {
        "O cancelamento depois de uma parcial devolve para o item exatamente o saldo de R$ 5,99": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago": 'produtos 5,99 e o total é o pago: `do_cancelamento.produtos == D("5.99")`; `_estornado_de(id_externo) == pedido.total == D("9.99")`',
        },
        "O cancelamento depois da parcial devolve só o saldo restante do pedido": {
            "tests/tecnicos/test_ocorrencias.py::test_o_cancelamento_devolve_so_o_saldo_restante": 'obrigação de 70,76: `obrigacao.devido == D("70.76")`',
        },
    },
    115: {
        "O item de 0,6 kg a R$ 0,15/kg tem subtotal de R$ 0,09": {
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_115_centavos_nao_passam_do_pago": 'item kg 0,600 a 0,15: `Unidade.KG, D("0.600"), D("0.15")`; `sum(produtos, D("0.00")) == D("0.09")`',
        },
        "Cada ocorrência de 0,1 kg calcula R$ 0,015 arredondado para R$ 0,02": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago": 'item kg 0,600 a 0,15 (0,1 x 0,15 = 0,015): `Unidade.KG, D("0.600"), D("0.15")`; `produtos == [D("0.02"), D("0.02"), D("0.02"), D("0.02"), D("0.01"), D("0.00")]`',
        },
        "A quinta ocorrência é limitada a R$ 0,01": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago": 'a quinta reembolsa 0,01: `produtos == [D("0.02"), D("0.02"), D("0.02"), D("0.02"), D("0.01"), D("0.00")]`',
        },
        "A sexta ocorrência reembolsa R$ 0,00": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago": 'a sexta reembolsa 0,00 sem obrigação: `produtos == [D("0.02"), D("0.02"), D("0.02"), D("0.02"), D("0.01"),`; `resultados[5].reembolso.obrigacao is None`',
        },
        "A soma dos reembolsos nunca passa de R$ 0,09": {
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_115_centavos_nao_passam_do_pago": 'a soma é 0,09 e o excesso é recusado: `sum(produtos, D("0.00")) == D("0.09")`; `pytest.raises(ReembolsoRecusado)`',
        },
        "Uma ocorrência acima da quantidade paga é recusada": {
            "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago": 'passa_do_saldo_do_item e nada muda: `_recusa(a.admin, item_m, D("0.1"), "faltante") == "passa_do_saldo_do_item"`; `pytest.raises(OcorrenciaRecusada)`',
        },
    },
    116: {
        "Um reembolso parcial de R$ 2,00 de produtos devolve também R$ 0,10 de serviço": {
            "tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py::test_cenario_116_numeros_do_cenario": 'produtos 2,00, serviço 0,10 e frete 0,40: `componentes(parcial(item, "1")) == (D("2.00"), D("0.10"), D("0.40"))`',
        },
        "Um reembolso parcial de R$ 2,00 de produtos devolve também R$ 0,40 de frete": {
            "tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py::test_cenario_116_numeros_do_cenario": 'produtos 2,00, serviço 0,10 e frete 0,40: `componentes(parcial(item, "1")) == (D("2.00"), D("0.10"), D("0.40"))`',
        },
        "O acumulado de cada componente nunca passa do valor registrado": {
            "tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py::test_cenario_116_numeros_do_cenario": 'o acumulado do pedido depois do parcial e do integral é o registrado: `acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))`',
        },
    },
    117: {
        "Cada reembolso parcial é registrado separadamente": {
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_117_cada_devolucao_e_registrada_separadamente": "um reembolso por devolução: `Reembolso.objects.filter(pedido=pedido).count() == 4`",
        },
        "Cada reembolso parcial guarda item, quantidade e valores": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo": 'item, quantidade 0,250 e valor 2,00: `(linha.item_id, linha.quantidade, linha.valor) == (item.pk, D("0.250"), D("2.00"))`',
        },
        "O pedido congelado continua com a composição original": {
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_117_cada_devolucao_e_registrada_separadamente": 'o item mantém quantidade e subtotal: `ItemDoPedido.objects.get(pk=item.pk).quantidade == D("1.000")`; `ItemDoPedido.objects.get(pk=item.pk).subtotal == D("7.99")`',
        },
    },
    118: {
        "O acionamento manual simultâneo com a tentativa automática é recusado": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar": 'ReenvioRecusado ciclo_em_andamento: `isinstance(resultados[1].excecao, modulo.ReenvioRecusado)`; `resultados[1].excecao.codigo == "ciclo_em_andamento"`',
        },
        "Nenhuma tentativa a mais é feita no acionamento manual simultâneo": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar": 'só as três automáticas: `[t.tipo for t in _tentativas()] == ["automatica"] * 3`',
        },
    },
    119: {
        "Dois manuais distintos feitos ao mesmo tempo são executados um depois do outro": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia": "a quinta começa depois de a quarta concluir: `quinta.iniciada_em >= quarta.concluida_em`",
        },
        "Dois manuais distintos nunca executam ao mesmo tempo": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia": "a segunda começa depois de a primeira concluir: `segunda_t.iniciada_em >= primeira_t.concluida_em`",
        },
        "Cada manual distinto tem uma única tentativa registrada": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia": "tentativas 4 e 5: `(quarta.numero, quinta.numero) == (4, 5)`",
        },
    },
}

TECNICOS: dict[str, dict[str, dict[str, str]]] = {
    "T-1": {
        "Tentativa criada em T0 + 24h − 1 ms é aceita": {
            "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento": 'uma tentativa e uma cobrança criada: `len(_tentativas(x)) == 1`; `len(_chamadas("criar_cobranca")) == 1`',
        },
        "Tentativa em T0 + 24h é recusada com a tarefa de bloqueio parada": {
            "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento": 'em T0+24h exato a tentativa é recusada: `erro.value.codigo == "prazo_encerrado"`; `len(_tentativas(x)) == 1`',
        },
        "Tentativa em T0 + 24h + 1 ms é recusada com a tarefa de bloqueio parada": {
            "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento": 'PagamentoRecusado prazo_encerrado: `pytest.raises(PagamentoRecusado)`; `erro.value.codigo == "prazo_encerrado"`',
        },
    },
    "T-2": {
        "date_approved em T0 + 48h é aceito": {
            "tests/tecnicos/test_pedidos_quitacao.py::test_fronteira_de_48_horas_da_margem": 'o pedido fica pago e o destino quita: `_situacao(pedido).situacao == "pago"`; `_destino(id_externo).destino == "quita"`',
        },
        "date_approved em T0 + 48h + 1 ms gera obrigação de devolução": {
            "tests/tecnicos/test_apuracao_inicio.py::test_reconsulta_registra_o_pagamento_aprovado_depois_de_48_horas": 'aprovado em T0+48h+1 ms: `_destinos(y) == [("devolucao", "aprovado_apos_a_margem")]`; `obrigacao.integral == y.total`',
        },
    },
    "T-3": {
        "Aprovação em T0 + 47h59 com webhook em T0 + 50h quita o pedido se a apuração ainda não ocorreu": {
            "tests/tecnicos/test_pedidos_quitacao.py::test_aviso_atrasado_nao_muda_o_horario_de_aprovacao": 'destino quita e quitado_em é a aprovação: `_destino(c.p).destino == "quita"`; `(situacao.situacao, situacao.quitado_em) == ("pago", aprovado)`',
        },
    },
    "T-4": {
        "Apuração em T0 + 48h − 1 ms é recusada": {
            "tests/tecnicos/test_apuracao_inicio.py::test_antes_de_48_horas_e_recusada_sem_consulta_nem_escrita": 'ApuracaoRecusada antes_do_prazo: `pytest.raises(ApuracaoRecusada)`; `recusa.value.codigo == "antes_do_prazo"`',
        },
        "Apuração em T0 + 48h − 1 ms é recusada mesmo com 100% pago": {
            "tests/tecnicos/test_apuracao_inicio.py::test_antes_de_48_horas_e_recusada_sem_consulta_nem_escrita": 'com X e Y pagos e T0+48h−1 ms a apuração é recusada: `recusa.value.codigo == "antes_do_prazo"`; `consultas == []`',
        },
        "Em T0 + 48h a apuração exige autorização do administrador": {
            "tests/tecnicos/test_apuracao_inicio.py::test_so_o_administrador_apura": "os outros recebem PermissionDenied: `_foto() == antes`; `pytest.raises(PermissionDenied)`",
        },
    },
    "T-5": {
        "Nenhuma rota permite alterar T0": {
            "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos": "varredura das rotas por t0, margem e prazo: `suspeitas == []`; `_campos_dos_formularios() & NOMES_DE_PRAZO == set()`",
        },
        "Nenhuma rota permite alterar o prazo de pagamento": {
            "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos": "nenhuma rota nem formulário altera prazo: `suspeitas == []`; `_campos_dos_formularios() & NOMES_DE_PRAZO == set()`",
        },
        "Nem o perfil de administrador altera T0 ou o prazo": {
            "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos": "a prorrogação do admin dá 409 e T0 fica igual: `resposta.status_code == 409`; `( AberturaDoPagamento.objects.get(pk=x.abertura_id).t0,`",
        },
    },
    "T-6": {
        "Webhook repetido 5 vezes em paralelo reconhece o pagamento uma única vez": {
            "tests/tecnicos/test_pagamentos_concorrencia.py::test_mesmo_aviso_cinco_vezes_em_paralelo_reconhece_o_pagamento_uma_vez": 'um aviso e um pagamento aprovado: `AvisoRecebido.objects.count() == 1`; `[p.situacao for p in pagamentos] == ["aprovado"]`',
        },
    },
    "T-7": {
        "Webhook e bloqueio de T0 + 24h concorrendo dão o mesmo resultado em qualquer ordem": {
            "tests/tecnicos/test_pedidos_concorrencia.py::test_bloqueio_e_aviso_de_outra_mudanca_ao_mesmo_tempo": 'pagamento cancelado e pedido aguardando: `PagamentoNoProvedor.objects.get(id_externo=p).situacao == "cancelado"`; `SituacaoDoPedido.objects.get(pedido=x).situacao == "aguardando_pagamento"`',
            "tests/tecnicos/test_pedidos_concorrencia.py::test_bloqueio_e_aviso_dao_o_mesmo_resultado_nas_duas_ordens": 'nas duas ordens o mesmo resultado: `PagamentoNoProvedor.objects.get(id_externo=p).situacao == "cancelado"`; `DestinoDoPagamento.objects.count() == 0`',
        },
        "Webhook antes da apuração quita o pedido": {
            "tests/tecnicos/test_apuracao_inicio.py::test_aviso_antes_da_apuracao_quita_y": 'Y pago e destino quita: `_situacao(y).situacao == "pago"`; `_destinos(y) == [("quita", "")]`',
        },
        "Apuração que cancelou o pedido antes do webhook dá devolução": {
            "tests/tecnicos/test_apuracao_inicio.py::test_aviso_espera_a_apuracao_que_ja_cancelou_y": 'cancelado por inadimplência e destino devolução: `(cancelado.situacao, cancelado.motivo_do_cancelamento) ==`; `_destinos(y) == [("devolucao", "pedido_cancelado")]`',
        },
        "Apuração concorrente com o webhook espera o aviso que trava a situação": {
            "tests/tecnicos/test_apuracao_inicio.py::test_apuracao_espera_o_aviso_que_trava_a_situacao_de_y": 'Y pago e destino quita: `_situacao(y).situacao == "pago"`; `_destinos(y) == [("quita", "")]`',
        },
    },
    "T-8": {
        "A devolução com falha temporária repetida reaproveita a chave de idempotência": {
            "tests/tecnicos/test_devolucoes_execucao.py::test_falha_depois_de_executar_repete_a_mesma_chave": 'a chamada mantém a chave: `ChamadaAoProvedor.objects.get(operacao="estornar").chave_idempotencia == chave`',
        },
        "A devolução com falha temporária repetida não devolve duas vezes": {
            "tests/tecnicos/test_devolucoes_execucao.py::test_falha_depois_de_executar_repete_a_mesma_chave": 'a parcela conclui com um só estorno: `parcela.situacao == "concluida"`; `len(_estornos_do_simulador()) == 1`',
        },
    },
    "T-9": {
        "A confirmação excepcional é recusada com devolução em processamento no provedor": {
            "tests/tecnicos/test_devolucoes_excepcional.py::test_estorno_em_processamento_no_provedor_recusa_e_agenda_a_verificacao": 'DevolucaoRecusada em processamento: `pytest.raises(DevolucaoRecusada, match="em processamento ou concluída no provedor")`',
        },
        "Nova tentativa no provedor é recusada depois da confirmação": {
            "tests/tecnicos/test_devolucoes_excepcional.py::test_depois_da_confirmacao_o_provedor_nao_e_mais_chamado": 'a chamada pendente falha com parcela_encerrada: `pytest.raises(DevolucaoRecusada)`; `(chamada.situacao, chamada.ultimo_erro) == ("falhou",`',
        },
        "A segunda confirmação da mesma parcela é recusada": {
            "tests/tecnicos/test_devolucoes_excepcional.py::test_nao_vale_duas_vezes": 'DevolucaoRecusada já confirmada: `pytest.raises(DevolucaoRecusada, match="já confirmada")`',
        },
    },
    "T-10": {
        "A utilização da reserva acima do saldo livre é recusada": {
            "tests/tecnicos/test_financeiro_reserva.py::test_uso_acima_do_livre_e_recusado_inteiro": "ReservaInsuficiente e estado igual: `pytest.raises(ReservaInsuficiente)`; `_estado() == antes`",
        },
        "A obrigação sem cobertura é mantida integral": {
            "tests/tecnicos/test_financeiro_reserva.py::test_obrigacoes_sem_cobertura_acima_do_livre_abrem_o_alerta": '52,00 sem cobertura: `obrigacoes_sem_cobertura() == D("52.00")`',
        },
        "A obrigação sem cobertura gera alerta de insuficiência": {
            "tests/tecnicos/test_financeiro_reserva.py::test_obrigacoes_sem_cobertura_acima_do_livre_abrem_o_alerta": 'alerta geral com sem cobertura e livre: `alerta.chave == "geral"`; `(D(alerta.dados["sem_cobertura"]), D(alerta.dados["livre"])) ==`',
        },
    },
    "T-11": {
        "Lançamento com recursos do fornecedor A para tarifa é recusado": {
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso": "cobertura de despesa com dinheiro de A é recusada: `(_saldos(), MovimentoFinanceiro.objects.count()) == antes`; `pytest.raises(MovimentoProibido)`",
        },
        "Lançamento com recursos do fornecedor A para déficit de B é recusado": {
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso": "cobertura do frete de B com dinheiro de A é recusada: `(_saldos(), MovimentoFinanceiro.objects.count()) == antes`; `pytest.raises(MovimentoProibido)`",
        },
        "Lançamento com recursos do fornecedor A para obrigação de B é recusado": {
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso": "tentativas de financiar e de repassar da obrigação devida de A para obrigação de B: `pytest.raises(MovimentoProibido)`; `(_saldos(), MovimentoFinanceiro.objects.count()) == antes`",
        },
        "O repasse a A é limitado ao valor liberado de A": {
            "tests/tecnicos/test_repasse.py::test_o_repasse_nao_passa_do_liberado": "LiquidezInsuficiente e nada muda: `pytest.raises(LiquidezInsuficiente)`; `_foto() == antes`",
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b": "repasse de A acima do liberado de A, sem usar o de B: `pytest.raises(LiquidezInsuficiente)`; `saldo(obrigacao_de(b.fornecedor, b.rodada)) == antes`",
        },
        "O repasse acima do liberado é recusado pela tela": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_repasse_limitado_ao_liberado_e_conciliado": '409 com o liberado: `recusado.status_code == 409`; `"Só R$ 0,00 estão liberados no provedor" in _texto(recusado)`',
        },
    },
    "T-12": {
        "A aplicação com o simulador em produção encerra na inicialização": {
            "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_com_o_simulador_nao_carrega": 'a carga falha com ImproperlyConfigured: `resultado.returncode != 0`; `"ImproperlyConfigured" in resultado.stderr`',
        },
    },
    "T-13": {
        "Dois cancelamentos com reembolso em paralelo: um é recusado": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_dois_cancelamentos_em_paralelo_geram_um_estorno_por_pagamento": 'CancelamentoRecusado ja_cancelada: `isinstance(rb.excecao, CancelamentoRecusado), rb.excecao`; `rb.excecao.codigo == "ja_cancelada"`',
        },
        "Dois cancelamentos com reembolso em paralelo não duplicam devolução": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_dois_cancelamentos_em_paralelo_geram_um_estorno_por_pagamento": 'dois estornos concluídos pelos valores pagos: `EstornoSimulado.objects.filter(situacao="conclu`; `_estornado_de(id_x) == D("94.35")`; `_estornado_de(id_y) == D("106.15")`',
        },
    },
    "T-14": {
        "O cancelamento com parcial pendente cobre só o saldo restante": {
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido": 'a obrigação de caixa pendente segue e o cancelamento cobre o restante: `de_caixa.devido == D("23.59")`; `not ParcelaDeDevolucao.objects.filter(obrigacao=de_caixa).exists()`',
        },
        "O total devolvido com parcial pendente nunca passa do valor pago": {
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido": 'com a parcial pendente o total devolvido é o valor pago: `total == D("94.35")`',
        },
    },
    "T-15": {
        "O cancelamento sem reembolso não gera obrigação nova": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente": 'as obrigações ficam iguais: `list(ObrigacaoComComprador.objects.order_by("pk").values()) == antes`',
        },
        "A obrigação existente continua pendente e não é baixada": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente": "sem parcela e o estornado é o integral: `not ParcelaDeDevolucao.objects.filter(obrigacao=existente).exists()`; `_estornado_de(id_y) == existente.integral`",
        },
    },
    "T-16": {
        "A rota de cancelamento recusa lista de compradores": {
            "tests/tecnicos/test_cancelamento_telas.py::test_a_rota_recusa_campos_fora_da_indicacao": "400 com a mensagem de indicação: `resposta.status_code == 400`; `SO_A_INDICACAO in _texto(resposta)`",
        },
        "A rota de cancelamento aceita requisição sem motivo": {
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http": 'cancelar sem reembolso passa e a rodada fica cancelada: `_cancelar_pela_tela(client, a, credencial, "nao").status_code == 302`; `Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"`',
        },
        "Comprador e fornecedor recebem recusa no cancelamento": {
            "tests/tecnicos/test_cancelamento_telas.py::test_comprador_e_fornecedor_nao_cancelam": '302 ou 403: `cliente.post(_rota(a), {"reembolso": "nao"}).status_code in (302, 403)`; `cliente.get(_pagina(a)).status_code in (302, 403)`',
        },
    },
    "T-17": {
        "UPDATE ou DELETE direto sobre item de pedido congelado é recusado pela trigger": {
            "tests/tecnicos/test_pedidos_abertura.py::test_composicao_do_pedido_nao_muda_nem_some": "RegistroImutavel e DatabaseError: `pytest.raises(RegistroImutavel)`; `pytest.raises(DatabaseError)`",
        },
        "Nenhuma rota permite edição do pedido congelado": {
            "tests/tecnicos/test_pedidos_abertura_tela.py::test_nenhuma_rota_altera_pedido_item_t0_ou_frete": "nenhuma rota sem política nem suspeita: `rotas_sem_politica() == []`; `suspeitas == []`",
        },
    },
    "T-18": {
        "Ocorrências concorrentes sobre o mesmo item não ultrapassam a quantidade paga": {
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_t18_duas_ocorrencias_ao_mesmo_tempo_pela_rota": "a segunda dá 409 e a soma é 4: `(ra.valor.status_code, rb.valor.status_code) == (302, 409)`; `sum(o.quantidade for o in OcorrenciaDeEntrega.objects.filter(item=item)) ==`",
        },
        "Cada ocorrência gera um único reembolso": {
            "tests/tecnicos/test_ocorrencias.py::test_o_mesmo_acionamento_em_paralelo": "o mesmo acionamento gera um só registro: `(ra.valor.nova, rb.valor.nova) == (True, False)`; `_foto_dos_registros() == (1, 1, 1, 1)`",
        },
        "O reembolso da ocorrência tem o valor do §9.2": {
            "tests/tecnicos/test_ocorrencias.py::test_duas_ocorrencias_no_mesmo_item_t18": 'produtos 40,00, serviço 2,00 e frete 5,18: `_componentes(ra.valor) == (D("40.00"), D("2.00"), D("5.18"))`',
        },
    },
    "T-19": {
        "Pagamento informado depois da apuração fica registrado": {
            "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta": 'destino devolução e obrigação integral: `_destinos(y) == [("devolucao", "pedido_cancelado")]`; `obrigacao.integral == y.total`',
        },
        "Pagamento informado depois da apuração gera alerta": {
            "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta": 'alerta crítico: `alerta.gravidade == "critico"`',
        },
        "Pagamento informado depois do cancelamento fica registrado com alerta": {
            "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta": 'devolução e alerta crítico: `(destino.destino, destino.motivo) == ("devolucao", "pedido_cancelado")`; `(alerta.gravidade, alerta.chave) == ("critico", id_y)`',
        },
        "Pagamento tardio não altera o pedido": {
            "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta": "a composição fica igual: `_composicao() == composicao`",
        },
    },
    "T-20": {
        "A apuração repetida restaura as parcelas uma única vez": {
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo": "uma restauração: `len(_restauracoes()) == 1`",
        },
        "A apuração repetida mantém o mesmo número de sequência": {
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo": 'pendente 4 e a mesma sequência: `(depois.quantidade_pendente, depois.sequencia) == (D("4.000"), antes.sequencia)`',
        },
        "A apuração repetida não duplica a reserva": {
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo": "um reembolso e uma obrigação: `len(_reembolsos(x)) == 1`; `ObrigacaoComComprador.objects.filter(pedido=x).count() == 1`",
        },
    },
    "T-21": {
        "A restauração com adição concorrente respeita a ordem FIFO original": {
            "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre": 'a adição de C recebe o estoque livre: `(da_c.situacao, da_c.quantidade_reservada) == ("ativa", D("5.000"))`',
        },
        "A restauração com adição concorrente mantém o total reservado dentro do estoque": {
            "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre": 'o total cabe no estoque: `total_reservado(a.p1) <= D("11")`',
        },
    },
    "T-22": {
        "O retorno ao interesse mantém o estoque cadastrado": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": 'os limites ficam iguais: `{e.produto_id: e.limite for e in EstoqueDaRodada.objects.filter(rodada=a.rodada)} == { a.p1.pk: D("11.000"), a.p2.pk: D("12.000"), }`',
        },
        "O retorno ao interesse libera as reservas dos inadimplentes": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": 'as parcelas de B ficam removidas: `{p.situacao for p in ParcelaDeInteresse.objects.filter(comprador=a.b)} == {"removida"}`',
        },
        "O retorno ao interesse mantém as reservas dos pagantes com a sequência original": {
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem": 'reservas ativas e sequências iguais: `[(p.situacao, p.quantidade_reservada) for p in de_p1] == [("ativa",`; `{p.pk: p.sequencia for p in ParcelaDeInteresse.objects.all()} == antes`',
        },
    },
    "T-23": {
        "Alterar o mínimo é recusado pelo servidor fora de interesse": {
            "tests/tecnicos/test_rodadas_minimo.py::test_minimo_congelado_pelo_servico": 'CondicoesCongeladas e mínimo igual: `pytest.raises(CondicoesCongeladas, match=MENSAGEM)`; `fornecedor.minimo == Decimal("150.00")`',
        },
        "Alterar o múltiplo é recusado pelo servidor fora de interesse": {
            "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_nenhuma_condicao_muda_fora_de_interesse": "CondicoesCongeladas e estado igual: `pytest.raises(CondicoesCongeladas)`; `_estado(contexto) == antes`",
        },
        "Alterar o estoque é recusado pelo servidor fora de interesse": {
            "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pelo_servico": 'CondicoesCongeladas e limite igual: `pytest.raises(CondicoesCongeladas)`; `estoque.limite == D("10.000")`',
        },
        "A recusa vale em fechamento, pagamento, margem e etapas seguintes": {
            "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_nenhuma_condicao_muda_fora_de_interesse": "a rota dá 409 para cada condição e situação: `resposta.status_code == 409, (condicao, situacao, extra)`; `MENSAGEM in resposta.content.decode()`",
        },
        "A recusa vale inclusive para o administrador": {
            "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pela_rota": 'a rota do administrador dá 409: `resposta.status_code == 409`; `estoque.limite == D("10.000")`',
        },
        "O preço é aceito no fechamento": {
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel": 'o preço muda para 12,00: `produto.preco == D("12.00")`',
        },
        "O preço é aceito nas quatro etapas ativas": {
            "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_preco_muda_nas_quatro_etapas_ativas": '302 e preço novo: `resposta.status_code == 302`; `contexto.produto.preco == D("12.50")`',
        },
        "A redução de estoque abaixo do reservado é recusada": {
            "tests/tecnicos/test_rodadas_estoque.py::test_reducao_abaixo_do_reservado_e_recusada": 'EstoqueAbaixoDoReservado e limite igual: `pytest.raises(EstoqueAbaixoDoReservado, match="6")`; `estoque.limite == D("10.000")`',
        },
    },
    "T-24": {
        "O login por senha com e-mail banido é recusado": {
            "tests/tecnicos/test_contas_login_senha.py::test_login_de_email_banido_e_recusado_com_a_mensagem_generica": "sem sessão e mensagem genérica: `not _autenticado(client)`; `GENERICA in resposta.content.decode()`",
        },
        "O login por link com e-mail banido é recusado": {
            "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link": "caso banido: nenhum link nem e-mail: `LinkDeAcesso.objects.count() == 0`; `len(mail.outbox) == 0`",
        },
        "O login pelo Google com e-mail banido é recusado": {
            "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google": "caso banido: sem sessão: `not _autenticado(client)`",
        },
        "O e-mail banido com maiúsculas e espaços variados é recusado": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_59_o_endereco_banido_com_outras_maiusculas_e_recusado_no_login": 'sem sessão com variações: `"_auth_user_id" not in cliente.session, escrito`',
        },
        "O alias com + não é bloqueado": {
            "tests/tecnicos/test_contas_login_senha.py::test_login_de_alias_nao_e_afetado_pelo_banimento_do_endereco_base": "o alias entra: `_autenticado(client)`",
        },
        "A sessão aberta é encerrada no banimento": {
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes": "as 2 sessões abertas passam a 0 na remoção: `_sessoes_da_conta(conta) == 0`; `UserSession.objects.filter(user=conta).count() == 0`",
        },
    },
    "T-25": {
        "A conta de fornecedor é recusada nas rotas de carrinho": {
            "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta": '403 no carrinho: `cliente.get("/teste/carrinho/", **cabecalhos).status_code == 403`; `cliente.post("/teste/carrinho/", **cabecalhos).status_code == 403`',
        },
        "A conta de fornecedor é recusada nas rotas de pagamento": {
            "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta": '403 no pagamento: `cliente.post("/teste/pagamento/", **cabecalhos).status_code == 403`; `metodo("/teste/pagamento/", **cabecalhos).status_code == 403`',
        },
        "A conta de comprador é recusada nas rotas de fornecedor": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_comprador_nao_entra_no_portal": "403 no portal: `[r.status_code for r in recusas] == [403] * 3`",
        },
    },
    "T-26": {
        "A quantidade fora do incremento é recusada pela API": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas": "QuantidadeInvalida: `pytest.raises(QuantidadeInvalida)`",
            "tests/aceitacao/test_cenario_63_rota_1_2_kg.py::test_cenario_63_rota_recusa_1_2_kg_sem_gravar": 'rota HTTP chamada direto com 1,2 kg: `resposta.status_code == 200`; `"Interesse atualizado" not in resposta.content.decode()`; `total_reservado(produto) == D("1.500")`',
        },
        "0,35 × 12,99 resulta em 455 centavos": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_de_455_centavos": '455 centavos: `int(calcular_subtotal(D("12.99"), D("0.35")) * 100) == 455`',
        },
        "O múltiplo que não é múltiplo do incremento é recusado no cadastro": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido": "MultiploInvalido e nenhum produto: `pytest.raises(MultiploInvalido)`; `Produto.objects.count() == 0`",
        },
    },
    "T-27": {
        "O fornecedor consultando por identificador direto dados que não são dele recebe recusa": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele": '403 e nenhum dado de comprador: `[r.status_code for r in recusas] == [403] * 9`; `"Comprador A" not in texto`',
        },
        "A exportação só contém campos permitidos": {
            "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal": 'sete colunas permitidas: `linhas == [ CABECALHO, "P1;unidade;11;;;10,00;110,00",`; `len(next(iter(csv.reader(io.StringIO(resposta.content.decode()), delimiter=";"))))`',
        },
    },
    "T-28": {
        "Com o SES falhando três vezes há exatamente três tentativas": {
            "tests/tecnicos/test_pedido_formal_envio.py::test_exatamente_tres_tentativas_automaticas": 'três falhas e três tentativas: `[(t.ordem_automatica, t.resultado) for t in tentativas] == [ (1, "falha"), (2,`; `len(_tentativas()) == 3`',
        },
        "Com o SES falhando três vezes o administrador recebe alerta": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela": "o aviso leva à página do pedido formal: `aviso.link is not None`",
        },
        "Com o SES falhando três vezes o botão fica disponível": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_depois_das_tres_falhas_o_formulario_aparece": "o formulário com token aparece: `'name=\"token\"' in resposta.content.decode()`",
        },
        "Falha seguida de sucesso não faz nenhuma tentativa a mais": {
            "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha": 'duas tentativas e o envio concluído: `(dois.resultado, dois.ordem_automatica) == ("sucesso", 2)`; `_envio().situacao == "concluido_com_sucesso"`',
        },
    },
    "T-29": {
        "Duas requisições de reenvio com o mesmo token geram um envio": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_gera_um_so_envio": "um só envio: `(primeira.nova, segunda.nova) == (True, False)`; `len(_enviados()) == 1`",
        },
        "Tokens distintos geram duas tentativas registradas": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro": "dois e-mails ao todo: `novo != token`; `len(enviados) == 2`",
        },
        "O conteúdo enviado é idêntico ao snapshot": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez": "o e-mail é igual ao snapshot: `len(_emails_iguais_ao_snapshot(pedido)) == 1`",
        },
    },
    "T-30": {
        "O alocar_pendentes reserva por ordem de sequência": {
            "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original": 'A é atendida antes de C e as sequências ficam: `estado(pa) == (SituacaoParcela.ATIVA, D("6"), D("0"))`; `(pa.sequencia, pc.sequencia) == sequencias`',
        },
        "A última parcela atendida fica parcialmente atendida com o restante pendente": {
            "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original": 'C tem 4 reservadas e 4 pendentes: `estado(pc) == (SituacaoParcela.ATIVA, D("4"), D("4"))`',
        },
        "O total reservado é igual ao estoque": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_do_produto_atende_a_fila_pela_sequencia_original": 'total reservado 10: `total_reservado(fp.p) == D("10.000")`',
        },
    },
    "T-31": {
        "Os pendentes são atendidos primeiro em paralelo com a adição nova": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro": 'A e C atendidos antes de E: `_estado(fp.a, fp.p) == ("ativa", D("6.000"), D("0.000"))`; `_estado(fp.c, fp.p) == ("ativa", D("4.000"), D("4.000"))`',
        },
        "Nenhuma reserva passa do estoque em paralelo com a adição nova": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro": 'total reservado 10: `total_reservado(fp.p) == D("10.000")`',
        },
        "O resultado é idêntico em qualquer ordem": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem": 'o total reservado é 4 nas duas ordens: `(pa.quantidade_reservada, pa.quantidade_pendente) == (D("4"), D("0"))`; `total_reservado(produto) == D("4")`',
        },
    },
    "T-32": {
        "A apuração reexecutada não faz segunda restauração": {
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo": "uma só restauração: `len(_restauracoes()) == 1`",
        },
        "A apuração reexecutada não cria nova parcela nem nova sequência": {
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo": 'a mesma sequência e pendente 4: `(depois.quantidade_pendente, depois.sequencia) == (D("4.000"), antes.sequencia)`',
        },
    },
    "T-33": {
        "A parcela pendente sem reserva fica fora do mínimo": {
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo": 'progresso 80 e pendente 5: `resultado.atingido is False`; `(participacao.reservado, participacao.pendente) == (D("0"), D("5"))`',
        },
        "A parcela pendente sem reserva fica fora das caixas e do pedido na abertura": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas": 'só as reservadas contam: `progresso.valor_elegivel == D("200.00")`; `item.quantidade == D("4.000")`',
            "tests/tecnicos/test_interesses_progresso.py::test_a_formacao_de_caixas_ignora_as_pendentes": 'com múltiplo 10, 7 reservadas e 5 pendentes não se forma caixa: `(resultado.total_reservado, resultado.caixas_completas) == (D("7"), 0)`',
        },
        "A parcela pendente continua pendente na rodada seguinte": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas": 'a parcela segue pendente: `(parcela.situacao, parcela.quantidade_pendente) == ("pendente", D("4.000"))`',
        },
        "O inadimplente fica sem parcelas pendentes": {
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai": 'a pendente antiga de B sai da fila: `(antigo.situacao, antigo.quantidade_pendente) == ("removida", D("0"))`; `not na_fila.exists()`',
        },
    },
    "T-34": {
        "Dois cadastros simultâneos com o mesmo e-mail dão um sucesso": {
            "tests/tecnicos/test_convites_cadastro_concorrencia.py::test_dois_convites_com_mesmo_email_normalizado_em_paralelo": "um sucesso e uma conta: `len([r for r in resultados if r.excecao is None]) == 1`; `Conta.objects.filter(email_normalizado=email).count() == 1`",
        },
        "Dois cadastros simultâneos com o mesmo e-mail dão uma recusa pela restrição UNIQUE": {
            "tests/tecnicos/test_contas_modelo.py::test_banco_recusa_segunda_conta_com_o_mesmo_email_pela_restricao_unique": 'o banco recusa pela restrição unique: `pytest.raises(IntegrityError, match="conta_email_unico")`; `Conta.objects.filter(email_normalizado="ana@x.com").count() == 1`',
        },
    },
    "T-35": {
        "Google com e-mail de uma conta em maiúsculas diferentes entra nessa conta": {
            "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social": 'a sessão é da conta existente: `client.session["_auth_user_id"] == str(conta.pk)`; `social.user == conta`',
        },
        "Google com e-mail de uma conta em maiúsculas diferentes não cria outra": {
            "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social": "a contagem fica igual: `Conta.objects.count() == antes`",
        },
        "Google sem conta e sem convite não cria nada": {
            "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada": "sem sessão e contagens iguais: `not _autenticado(client)`; `_contagens() == antes`",
        },
    },
    "T-36": {
        "Banimento com sessões em dois navegadores apaga as sessões": {
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes": "nenhuma sessão resta: `_sessoes_da_conta(conta) == 0`; `UserSession.objects.filter(user=conta).count() == 0`",
        },
        "A próxima requisição de cada sessão é recusada pelo middleware": {
            "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou": 'redireciona e perde a sessão: `resposta.status_code == 302`; `"_auth_user_id" not in cliente.session`',
        },
        "A outra conta da mesma pessoa continua acessível": {
            "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa": 'o fornecedor entra: `sessao_fornecedor.get("/inicio/").status_code == 200`; `"_auth_user_id" in cliente.session`',
        },
    },
    "T-37": {
        "normalizar_email é usado na unicidade da conta": {
            "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos": "EmailEmUso com variações: `pytest.raises(EmailEmUso)`",
        },
        "normalizar_email é usado no convite": {
            "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos": 'o convite guarda o endereço normalizado: `emitir_convite(admin, alias, "comprador").email_normalizado == alias`',
        },
        "normalizar_email é usado no login": {
            "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos": "a entrada com variação autentica: `_autenticado(entrada)`",
        },
        "normalizar_email é usado no cadastro": {
            "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos": 'ConviteInvalido email_em_uso: `pytest.raises(ConviteInvalido)`; `erro.value.codigo == "email_em_uso"`',
        },
        "normalizar_email é usado no banimento": {
            "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos": "o endereço banido não recebe link: `mail.outbox == []`",
        },
        "Aliases com + continuam distintos": {
            "tests/tecnicos/test_contas_emails.py::test_normalizar_email_propriedade_alias_continua_distinto": "alias e e-mail base diferem: `normalizar_email(alias) != normalizar_email(email)`",
        },
    },
    "T-38": {
        "Quantidades em L são validadas contra o incremento": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": 'L: `(Unidade.LITRO, "0.5", "1.5", True)` aceito e `(Unidade.LITRO, "0.5", "1.2", False)` recusado: `resumo.reservado == D(entrada)`; `pytest.raises(QuantidadeInvalida)`',
        },
        "Quantidades em kg são validadas contra o incremento": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": 'kg: `(Unidade.KG, "0.5", "1.2", False)`: `pytest.raises(QuantidadeInvalida)`; `parcelas(produto) == []`',
        },
        "Quantidades em unidade são validadas contra o incremento": {
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos": 'unidade: `(Unidade.UNIDADE, "1", "2.5", False)`: `pytest.raises(QuantidadeInvalida)`; `parcelas(produto) == []`',
        },
        "Incremento zero é recusado": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_zero_e_recusado_e_o_produto_nao_e_criado": "IncrementoInvalido e nenhum produto: `pytest.raises(IncrementoInvalido)`; `Produto.objects.count() == 0`",
        },
        "Incremento negativo é recusado": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_negativo_e_recusado_e_o_produto_nao_e_criado": "IncrementoInvalido e nenhum produto: `pytest.raises(IncrementoInvalido)`; `Produto.objects.count() == 0`",
        },
        "Incremento com mais de 3 casas é recusado": {
            "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_com_mais_de_3_casas_e_recusado_e_o_produto_nao_e_criado": "IncrementoInvalido e nenhum produto: `pytest.raises(IncrementoInvalido)`; `Produto.objects.count() == 0`",
        },
        "Múltiplo incompatível é recusado no cadastro": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro": 'erro de múltiplo e nenhum produto: `"multiplo" in resposta.context["form"].errors`; `Produto.objects.count() == 0`',
        },
        "Múltiplo incompatível é recusado na alteração em interesse": {
            "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_invalido_em_interesse": 'erro de múltiplo e múltiplo igual: `"multiplo" in resposta.context["form"].errors`; `produto.multiplo == D("1.000")`',
        },
    },
    "T-39": {
        "7,99 × 0,25 arredonda para 2,00": {
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_7_99_vezes_0_25": 'arredondar_centavos dá 2,00: `arredondar_centavos(D("7.99") * D("0.25")) == D("2.00")`',
        },
        "2,50 × 0,25 arredonda para 0,63": {
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_2_50_vezes_0_25": 'arredondar_centavos dá 0,63: `arredondar_centavos(D("2.50") * D("0.25")) == D("0.63")`',
        },
        "12,99 × 0,35 arredonda para 4,55": {
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_12_99_vezes_0_35": 'arredondar_centavos dá 4,55: `arredondar_centavos(D("12.99") * D("0.35")) == D("4.55")`',
        },
        "P é a soma dos subtotais arredondados": {
            "tests/tecnicos/test_pedidos_calculo.py::test_produtos_soma_os_subtotais_ja_arredondados": 'produtos 1,26: `cobranca.produtos == D("1.26")`',
        },
        "A verificação estática não encontra float em código monetário": {
            "tests/tecnicos/test_varredura_float.py::test_modulos_de_dinheiro_nao_usam_float": "nenhum achado: `varrer_modulos_de_dinheiro() == []`",
        },
    },
    "T-40": {
        "O reembolso do item inteiro depois de mudar o preço usa o subtotal do snapshot": {
            "tests/aceitacao/test_t40_reembolso_do_item_inteiro.py::test_t40_reembolso_do_item_inteiro_depois_de_mudar_o_preco": 'difere do preço novo vezes a quantidade: `componentes(registrado)[0] != D("9.99") * item.quantidade`',
        },
        "A soma da devolução integral bate com os valores cobrados registrados": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente": '75,00 3,75 e 15,00 e acumulado 100,00 5,00 20,00: `_componentes(registrado) == (D("75.00"), D("3.75"), D("15.00"))`; `acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))`',
        },
    },
    "T-41": {
        "O reenvio manual é recusado durante o ciclo automático": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado": 'ciclo_em_andamento: `erro.value.codigo == "ciclo_em_andamento"`; `not consultas`',
        },
        "O reenvio manual é aceito depois da terceira falha": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas": 'tentativa manual 4 nova: `registrado.nova is True`; `(tentativa.tipo, tentativa.numero, tentativa.ordem_automatica) == ("manual", 4,`',
        },
        "O reenvio manual é aceito depois de sucesso": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico": 'tentativa 2 com sucesso: `(registrado.tentativa.numero, registrado.tentativa.resultado) == (2, "sucesso")`; `_envio().situacao == "concluido_com_sucesso"`',
        },
        "O reenvio gera uma tentativa por acionamento": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso": 'uma tentativa manual: `[t.tipo for t in _tentativas()] == ["automatica", "manual"]`',
        },
        "O reenvio não inicia novo ciclo automático": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico": "nada automático e duas tentativas: `processar(relogio, PRAZO + 24 * 60 * M) == 0`; `len(_tentativas()) == 2`",
        },
        "O reenvio mantém o snapshot e o identificador do pedido formal": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas": "o e-mail e o pedido ficam iguais: `(enviado.subject, enviado.body) == (pedido.assunto, pedido.corpo)`; `_foto_do_pedido(pedido) == antes`",
        },
    },
    "T-42": {
        "A consulta do comprador devolve reservado e pendente em campos separados": {
            "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado": 'Reservado: 6 e Pendente: 4: `"Reservado: 6" in html`; `"Pendente: 4" in html`',
        },
        "A consulta separa reservado e pendente com estoque zero": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero": 'Reservado: 4 e Pendente: 4: `"Reservado: 4" in texto`; `"Pendente: 4" in texto`',
        },
        "Outro comprador não vê essas parcelas": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero": 'A não vê a pendência de C: `"Pendente: 4" not in texto_de_a`; `"Reservado: 6" in texto_de_a`',
        },
    },
    "T-43": {
        "A remoção parcial e total muda só a quantidade pendente": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia": 'pendente 2 depois 0 e reservado 6: `(resumo.reservado, resumo.pendente) == (D("6"), D("2"))`; `estado(parcela) == (SituacaoParcela.ATIVA, D("6"), D("0"))`',
        },
        "A remoção mantém as sequências inalteradas": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia": "as sequências ficam iguais: `(parcela.sequencia, outra.sequencia) == sequencias`",
        },
        "A remoção mantém as reservas inalteradas": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno": 'A fica igual e as sequências iguais: `_estado(fp.a, fp.p) == ("ativa", D("6.000"), D("0.000"))`; `_sequencias(fp.p) == sequencias`',
        },
        "As parcelas mais recentes são reduzidas primeiro": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_comeca_pela_parcela_mais_recente": 'a mais recente é removida e a antiga fica: `estado(recente) == (SituacaoParcela.REMOVIDA, D("0"), D("0"))`; `estado(antiga) == (SituacaoParcela.PENDENTE, D("0"), D("1"))`',
        },
        "Quantidade fora do incremento é recusada sem escrita": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava": 'caso `"1.5"` do `parametrize`: `pytest.raises(QuantidadeInvalida)`; `auditorias(ACAO) == []`',
        },
        "Quantidade acima do pendente é recusada sem escrita": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava": 'caso `"5"` do `parametrize`: `pytest.raises(RemocaoAcimaDoPendente)`; `auditorias(ACAO) == []`',
        },
    },
    "T-44": {
        "A remoção com item de pedido congelado é recusada": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_com_o_pk_real_do_item_congelado_e_recusada": 'POST da rota com o pk real do item de A em Q: `resposta.status_code in (200, 404, 409)`; `list(ItemDoPedido.objects.order_by("pk").values()), list(Reembolso.objects.order_by("pk").values()),`',
        },
        "A remoção com parcela em pedido é recusada pelo serviço": {
            "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao": 'RemocaoAcimaDoPendente e a parcela fica em pedido: `pytest.raises(RemocaoAcimaDoPendente)`; `estado(parcela) == (SituacaoParcela.EM_PEDIDO, D("4"), D("2"))`',
        },
        "A remoção com parcela em pedido é recusada pela rota": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido": "200, 404 ou 409: `resposta.status_code in (200, 404, 409)`",
        },
        "Pedido, trigger e registros financeiros ficam inalterados": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido": 'itens, reembolsos e obrigações iguais: `( list(ItemDoPedido.objects.order_by("pk").values()), list(Reembolso.objects.order_by("pk").values()), _estado(fp.a, fp.q), ) == antes`',
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_com_o_pk_real_do_item_congelado_e_recusada": 'o pedido, os itens, os reembolsos e as parcelas de A ficam iguais: `list(ItemDoPedido.objects.order_by("pk").values()), list(Reembolso.objects.order_by("pk").values()),`',
        },
    },
    "T-45": {
        "Remoção em paralelo com a alocação: reservado mais pendente não passa do original": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam": "cabe no original: `parcela.quantidade_reservada + parcela.quantidade_pendente <= parcela.quantidade_original`",
        },
        "Remoção em paralelo com a alocação: o total reservado não passa do estoque": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam": 'cabe no estoque: `total_reservado(produto) <= D("10")`',
        },
        "A quantidade removida nunca é reservada": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam": "a remoção concorrente é recusada com pendente 0: `isinstance(resultados[1].excecao, RemocaoAcimaDoPendente)`; `resultados[1].excecao.pendente == 0`",
        },
    },
    "T-46": {
        "A liberação de estoque em paralelo com nova reserva atende os pendentes pela sequência": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado": 'C fica ativa com 3 e 1 e o total é 10: `(pc.situacao, pc.quantidade_reservada, pc.quantidade_pendente) == (`; `total_reservado(produto) == D("10")`',
        },
        "Pendentes do fornecedor X nunca são alocados em rodada do fornecedor Y": {
            "tests/tecnicos/test_interesses_fila.py::test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele": 'alocação zero e a pendente de X intacta: `alocar(rodada_x.fornecedor) == 0`; `estado(pq) == (SituacaoParcela.PENDENTE, D("0"), D("4"))`',
        },
    },
    "T-47": {
        "O cálculo do mínimo ignora a quantidade pendente": {
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo": 'elegível 80 e pendente 5: `resultado.atingido is False`; `(participacao.reservado, participacao.pendente) == (D("0"), D("5"))`',
        },
        "A formação de caixas ignora a quantidade pendente": {
            "tests/tecnicos/test_interesses_progresso.py::test_a_formacao_de_caixas_ignora_as_pendentes": 'múltiplo 10, 7 reservadas e 5 pendentes: `(resultado.total_reservado, resultado.caixas_completas) == (D("7"), 0)`; `resultado.quantidade_elegivel == D("0")`',
        },
        "A abertura do pagamento e o pedido ignoram a quantidade pendente": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas": 'o item do pedido tem só as reservadas: `item.quantidade == D("4.000")`',
        },
        "O pedido formal ignora a quantidade pendente": {
            "tests/tecnicos/test_pedido_formal.py::test_as_quantidades_pendentes_nao_entram": 'o pedido formal traz 11: `_linhas(_pedido_formal())["P1"].quantidade == D("11.000")`',
        },
        "A cobrança ignora a quantidade pendente": {
            "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_104_a_cobranca_do_pedido_ignora_as_pendentes": 'o pedido cobra só as 4 reservadas: `pedido.produtos == calcular_subtotal(fp.p.preco, D("4.000"))`',
        },
        "A quantidade pendente continua na fila depois da abertura do pagamento": {
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas": 'a parcela segue pendente: `(parcela.situacao, parcela.quantidade_pendente) == ("pendente", D("4.000"))`',
        },
    },
    "T-48": {
        "Valor compatível de incremento é aceito na fase de interesse": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_compativel_e_aceito": 'incremento 0,250 e parcelas iguais: `produto.incremento == D("0.250")`; `_estado_das_parcelas() == antes`',
        },
        "Incremento incompatível com o reservado é recusado sem escrita": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado": "IncrementoIncompativel e nada escrito: `pytest.raises(IncrementoIncompativel,`; `_estado_das_parcelas() == antes`; `EntradaAuditoria.objects.count() == 0`",
        },
        "Incremento incompatível com o pendente é recusado sem escrita": {
            "tests/tecnicos/test_catalogo_incremento.py::test_pendente_da_fila_tambem_conta": 'IncrementoIncompativel e incremento igual: `pytest.raises(IncrementoIncompativel)`; `produto.incremento == D("0.250")`',
        },
        "Incremento incompatível com o múltiplo é recusado sem escrita": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_o_multiplo_e_recusado": 'IncrementoIncompativel e nada escrito: `pytest.raises(IncrementoIncompativel,`; `produto.incremento == D("0.500")`; `EntradaAuditoria.objects.count() == 0`',
        },
        "Qualquer valor de incremento é recusado a partir do fechamento": {
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_congelado": 'CondicoesCongeladas e incremento igual: `pytest.raises(CondicoesCongeladas)`; `produto.incremento == D("0.500")`',
        },
    },
    "T-49": {
        "A alteração do incremento e a adição em paralelo são serializadas pela trava do produto": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam": 'uma das duas é recusada: `isinstance(resultados[1].excecao, IncrementoIncompativel)`; `resultados[1].excecao.codigo == "quantidade"`',
        },
        "Nenhuma parcela fica fora do incremento vigente ao final": {
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam": "a quantidade reservada é múltipla do incremento: `parcela.quantidade_reservada % incremento == 0`",
        },
    },
    "T-50": {
        "A tabela de incrementos válidos da especificação é aceita": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos": "validar_incremento devolve o valor: `validar_incremento(entrada) == esperado`",
        },
        "Os incrementos inválidos 0, -1 e 0,0001 são recusados": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_invalidos_no_servico": 'casos `"0"`, `"-1"` e `"0.0001"` do `parametrize`: `pytest.raises(IncrementoInvalido)`',
        },
        "Quantidades inteiras e fracionárias são validadas com Decimal": {
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos": "a entrada Decimal também é aceita: `validar_incremento(D(entrada)) == esperado`",
        },
        "Número em ponto flutuante na API é recusado": {
            "tests/tecnicos/test_nucleo_valores.py::test_conversao_recusa_float": 'ValorInvalido por tipo: `pytest.raises(ValorInvalido, match="tipo")`',
        },
    },
    "T-51": {
        "O reembolso parcial de 7,99 × 0,25 é 2,00": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo": 'produtos 2,00: `registrado.reembolso.produtos == D("2.00")`',
        },
        "A sequência de quatro parciais é 2,00, 2,00, 2,00 e 1,99": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente": '2,00 2,00 2,00 e 1,99: `[p for p, _, _ in feitos] == [D("2.00"), D("2.00"), D("2.00"), D("1.99")]`',
        },
        "O caso de R$ 0,09 tem limite ao saldo": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo": '0,02 quatro vezes, 0,01 e 0,00: `[*valores, sexto.reembolso.produtos] == [ D("0.02"), D("0.02"), D("0.02"),`; `acumulado_do_item(item) == (D("0.600"), D("0.09"))`',
        },
        "A mudança do preço de catálogo não altera nenhum valor": {
            "tests/aceitacao/test_t40_reembolso_do_item_inteiro.py::test_t40_reembolso_do_item_inteiro_depois_de_mudar_o_preco": 'com o catálogo a 9,99 o reembolso é o registrado: `componentes(registrado) == (D("7.99"), D("0.40"), D("1.60"))`; `componentes(registrado)[0] != D("9.99") * item.quantidade`',
        },
    },
    "T-52": {
        "O reembolso acima da quantidade paga é recusado": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo": 'o sétimo parcial passa do pago e é recusado: `pytest.raises(ReembolsoRecusado, match="passa da quantidade paga")`; `_total_de_registros() == antes`',
        },
        "A devolução integral depois de parciais completa exatamente o saldo": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente": '75,00 3,75 15,00 e acumulado igual ao pedido: `_componentes(registrado) == (D("75.00"), D("3.75"), D("15.00"))`; `acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))`',
        },
        "O acumulado de serviço nunca passa do registrado": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente": 'serviço acumulado 5,00: `acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))`',
        },
        "O acumulado de frete nunca passa do registrado": {
            "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente": 'frete acumulado 20,00: `acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))`',
        },
    },
    "T-53": {
        "Dois reembolsos parciais concorrentes são serializados pela trava": {
            "tests/tecnicos/test_devolucoes_concorrencia.py::test_dois_parciais_do_mesmo_item_nunca_passam_do_pago": "um passa e o outro é recusado: `a.excecao is None, a.excecao`; `isinstance(b.excecao, ReembolsoRecusado), b.excecao`",
        },
        "A soma dos reembolsos concorrentes não passa do subtotal": {
            "tests/tecnicos/test_devolucoes_concorrencia.py::test_tres_parciais_ao_mesmo_tempo_respeitam_o_pago": 'quantidade, produtos, serviço e frete dentro do pago: `valor <= D("7.99")`; `produtos <= D("7.99")`; `servico <= D("0.40")`; `frete <= D("1.60")`',
        },
        "Nenhum registro de reembolso é duplicado": {
            "tests/tecnicos/test_devolucoes_concorrencia.py::test_dois_parciais_do_mesmo_item_nunca_passam_do_pago": "um reembolso e uma obrigação: `Reembolso.objects.count() == ItemReembolsado.objects.count() == 1`; `ObrigacaoComComprador.objects.count() == 1`",
        },
    },
    "T-54": {
        "O reenvio manual é recusado com tentativa automática agendada": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_antes_da_primeira_tentativa_automatica_o_reenvio_e_recusado": 'ciclo_em_andamento: `pytest.raises(ReenvioRecusado)`; `erro.value.codigo == "ciclo_em_andamento"`',
        },
        "O reenvio manual é recusado com tentativa automática em execução": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar": 'o manual durante a automática em execução é recusado: `resultados[1].excecao.codigo == "ciclo_em_andamento"`; `[t.tipo for t in _tentativas()] == ["automatica"] * 3`',
        },
        "O reenvio manual é aceito depois do sucesso": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico": 'tentativa 2 com sucesso: `(registrado.tentativa.numero, registrado.tentativa.resultado) == (2, "sucesso")`; `_envio().situacao == "concluido_com_sucesso"`',
        },
        "O reenvio manual é aceito depois da terceira falha": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas": 'tentativa manual 4 nova: `registrado.nova is True`; `(tentativa.tipo, tentativa.numero, tentativa.ordem_automatica) == ("manual", 4,`',
        },
        "O reenvio manual gera uma tentativa por acionamento": {
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso": 'uma tentativa manual: `[t.tipo for t in _tentativas()] == ["automatica", "manual"]`',
        },
    },
    "T-55": {
        "A tentativa automática e o acionamento manual concorrentes recusam o manual": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar": 'ReenvioRecusado ciclo_em_andamento: `isinstance(resultados[1].excecao, modulo.ReenvioRecusado)`; `resultados[1].excecao.codigo == "ciclo_em_andamento"`',
        },
        "Dois manuais distintos depois do ciclo executam em sequência": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia": "a quinta começa depois da quarta: `quinta.iniciada_em >= quarta.concluida_em`",
        },
        "Dois manuais distintos nunca executam ao mesmo tempo": {
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia": "a segunda começa depois da primeira: `segunda_t.iniciada_em >= primeira_t.concluida_em`",
        },
        "O snapshot fica inalterado": {
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia": "os dois e-mails são iguais ao corpo do pedido: `(um.body, dois.body) == (pedido.corpo, pedido.corpo)`",
        },
    },
}
