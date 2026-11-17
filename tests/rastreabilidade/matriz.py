"""A matriz de rastreabilidade da fase 1 (E16-07): cenário (§16) e teste técnico -> testes.

Escrita à mão a partir das colunas "Origem" dos `acceptance.md` e da leitura dos testes. Cada
referência é `caminho/do/arquivo.py::nome_do_teste` (ou `::Classe::nome`), relativa à raiz, sem
parâmetros. `test_matriz.py` confere que todas existem, não estão puladas nem se repetem, e o
documento `docs/rastreabilidade-fase1.md` é gerado daqui (`python -m tests.rastreabilidade.gerar`).
"""

CENARIOS: dict[int, list[str]] = {
    1: [
        "tests/tecnicos/test_contas_google_cadastro.py::test_google_com_outro_email_nao_cadastra_pelo_convite",
        "tests/tecnicos/test_convites_cadastro.py::test_cadastro_cria_conta_email_verificado_e_sessao",
        "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_comprador",
        "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_fornecedor",
        "tests/tecnicos/test_convites_cadastro.py::test_convite_consumido_nao_pode_ser_reutilizado",
        "tests/tecnicos/test_convites_cadastro.py::test_fronteira_de_24h_no_post",
    ],
    2: [
        "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_banimento_ou_remocao_depois_do_pedido_bloqueia_o_uso",
    ],
    3: [
        "tests/tecnicos/test_interesses_concorrencia.py::test_ultima_unidade_disputada_so_uma_vence",
    ],
    4: [
        "tests/tecnicos/test_interesses_progresso.py::test_atingir_o_minimo_nao_muda_a_etapa_nem_grava",
        "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_a_tarefa_nao_mexe_no_que_nao_venceu",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_atingir_o_minimo_nao_inicia_nada_sozinho",
    ],
    5: [
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_inicio_registra_ciclo_prazo_de_24_horas_e_auditoria",
        "tests/tecnicos/test_rodadas_fechamento_prorrogacao.py::test_a_queda_do_minimo_nao_prorroga",
        "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_a_queda_e_a_recuperacao_do_minimo_nao_mexem_no_prazo",
    ],
    6: [
        "tests/tecnicos/test_interesses_progresso.py::test_dezoito_unidades_com_multiplo_doze",
    ],
    7: [
        "tests/tecnicos/test_interesses_carrinho.py::test_caixas_so_com_as_unidades_do_proprio_comprador",
        "tests/tecnicos/test_interesses_progresso.py::test_caixa_formada_pela_ordem_de_adicao",
        "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_as_ultimas_adicoes_perdem_o_excedente",
    ],
    8: [
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_depois_de_um_retorno_ao_interesse",
        "tests/tecnicos/test_interesses_progresso.py::test_acrescimo_posterior_fica_com_o_excedente",
        "tests/tecnicos/test_interesses_servicos.py::test_acrescimo_posterior_vai_para_o_fim_da_fila",
    ],
    9: [
        "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_atingido_aguarda_o_pagamento",
        "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_nao_atingido_volta_para_interesse",
    ],
    10: [
        "tests/tecnicos/test_pedidos_calculo.py::test_cobranca_rateia_o_frete_pelos_produtos",
    ],
    11: [
        "tests/tecnicos/test_pedidos_abertura.py::test_abertura_congela_um_pedido_por_comprador",
        "tests/tecnicos/test_pedidos_abertura.py::test_composicao_fica_congelada_apos_a_abertura",
    ],
    12: [
        "tests/tecnicos/test_pedidos_prazos.py::test_com_o_bloqueio_parado_o_servidor_recusa_a_tentativa",
        "tests/tecnicos/test_pedidos_prazos.py::test_depois_de_48_horas_nada_acontece_sozinho",
        "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre",
        "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento",
    ],
    13: [
        "tests/tecnicos/test_apuracao_resultado.py::test_caixas_com_inadimplente_sao_invalidadas_sem_reorganizar",
        "tests/tecnicos/test_apuracao_resultado.py::test_parcela_que_cruza_caixas_so_perde_a_parte_da_caixa_invalidada",
        "tests/tecnicos/test_apuracao_viavel.py::test_estorno_proporcional_das_unidades_em_caixa_invalidada",
        "tests/tecnicos/test_apuracao_viavel.py::test_so_a_parte_da_caixa_invalidada_e_estornada_e_restaurada",
        "tests/tecnicos/test_apuracao_telas.py::test_apuracao_viavel_mostra_o_resultado_e_o_botao_de_aprovar",
    ],
    14: [
        "tests/tecnicos/test_apuracao_aprovacao.py::test_aprovar_leva_a_apuracao_ao_livro_e_avanca_a_rodada",
        "tests/tecnicos/test_apuracao_aprovacao.py::test_o_pedido_e_o_pagamento_nao_mudam_e_a_custodia_zera",
        "tests/tecnicos/test_apuracao_telas.py::test_aprovar_mostra_o_frete_e_esconde_o_botao",
        "tests/tecnicos/test_apuracao_telas.py::test_apuracao_viavel_mostra_o_resultado_e_o_botao_de_aprovar",
    ],
    15: [
        "tests/tecnicos/test_apuracao_retorno.py::test_devolucao_integral_dos_pedidos_pagos",
        "tests/tecnicos/test_apuracao_retorno.py::test_pagamentos_insuficientes_devolvem_a_rodada_ao_interesse",
        "tests/tecnicos/test_apuracao_telas.py::test_minimo_nao_atendido_devolve_a_rodada_e_mostra_o_estorno_integral",
    ],
    16: [
        "tests/tecnicos/test_apuracao_retorno.py::test_novo_pagamento_cria_pedidos_novos_sem_tocar_o_ciclo_antigo",
        "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente",
    ],
    17: [
        "tests/tecnicos/test_notificacoes_emissao.py::test_emissao_repetida_nao_duplica",
        "tests/tecnicos/test_pagamentos_avisos.py::test_aviso_repetido_nao_repete_efeitos",
        "tests/tecnicos/test_pagamentos_concorrencia.py::test_cinco_avisos_diferentes_do_mesmo_pagamento",
        "tests/tecnicos/test_pagamentos_concorrencia.py::test_cinco_sincronizacoes_do_mesmo_pagamento_aprovado",
        "tests/tecnicos/test_pagamentos_sincronizacao.py::test_consultas_repetidas_nao_repetem_efeitos",
        "tests/tecnicos/test_pagamentos_concorrencia.py::test_mesmo_aviso_cinco_vezes_em_paralelo_reconhece_o_pagamento_uma_vez",
    ],
    18: [
        "tests/tecnicos/test_ocorrencias.py::test_cenario_18_servico_e_frete_proporcionais",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_entrega_parcial_ocorrencia_e_liberacao",
        "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenario_18_reembolso_pontual_com_servico_e_frete_proporcionais",
    ],
    19: [
        "tests/tecnicos/test_interesses_suspensao.py::test_suspensao_esvazia_os_interesses_e_a_reversao_nao_restaura",
        "tests/tecnicos/test_moderacao_servicos.py::test_reativar_volta_a_ativa_sem_restaurar_nada",
        "tests/tecnicos/test_pedidos_moderacao.py::test_suspensao_cancela_o_pedido_nao_pago",
        "tests/tecnicos/test_retirada.py::test_a_retirada_nao_depende_da_situacao_do_comprador",
        "tests/tecnicos/test_retirada_comprador.py::test_o_comprador_suspenso_ve_a_retirada",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_19_o_suspenso_retira",
    ],
    20: [
        "tests/tecnicos/test_interesses_suspensao.py::test_remocao_preserva_em_pedido_e_nao_apaga_parcelas",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_preserva_conta_historico_e_convite",
    ],
    21: [
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_comprador_nao_entra_no_portal",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_portal_nao_expoe_dado_da_e14",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_rodada_de_outro_fornecedor_ou_inexistente_da_o_mesmo_404",
    ],
    22: [
        "tests/tecnicos/test_liberacao_da_retirada.py::test_cenario_22_a_nova_rodada_nao_herda_a_reserva",
        "tests/tecnicos/test_retirada.py::test_cenario_22_retirada_depois_do_prazo",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_22_nova_rodada_e_retirada_antiga",
    ],
    23: [
        "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_cenario_23_pelas_telas",
        "tests/tecnicos/test_retirada.py::test_cenario_23_descarte_antes_do_prazo",
        "tests/tecnicos/test_retirada.py::test_cenario_23_descarte_no_prazo_final",
        "tests/tecnicos/test_retirada.py::test_cenario_23_o_tempo_nao_descarta",
        "tests/tecnicos/test_retirada_comprador.py::test_depois_do_prazo_sem_descarte",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_23_prazo_e_descarte",
    ],
    24: [
        "tests/tecnicos/test_notificacoes_falha_isolada.py::test_falha_no_whatsapp_nao_desfaz_o_fato_nem_a_notificacao",
        "tests/tecnicos/test_notificacoes_falha_isolada.py::test_nada_e_tentado_antes_da_confirmacao_da_transacao",
        "tests/tecnicos/test_notificacoes_processamento.py::test_falha_do_email_nao_altera_a_notificacao",
        "tests/tecnicos/test_pedidos_abertura.py::test_falha_do_whatsapp_nao_desfaz_a_abertura",
        "tests/tecnicos/test_pedidos_quitacao.py::test_falha_do_whatsapp_nao_desfaz_a_quitacao",
    ],
    25: [
        "tests/tecnicos/test_pedidos_quitacao.py::test_aprovacao_no_prazo_quita_o_pedido",
        "tests/tecnicos/test_pedidos_quitacao.py::test_aviso_atrasado_nao_muda_o_horario_de_aprovacao",
    ],
    26: [
        "tests/tecnicos/test_apuracao_inicio.py::test_reconsulta_registra_o_pagamento_aprovado_depois_de_48_horas",
        "tests/tecnicos/test_pedidos_quitacao.py::test_aprovacao_depois_da_margem_gera_devolucao",
    ],
    27: [
        "tests/tecnicos/test_pedidos_prazos.py::test_a_apuracao_so_pode_comecar_em_48_horas",
    ],
    28: [
        "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos",
        "tests/tecnicos/test_rodadas_fechamento_prorrogacao.py::test_prorrogacao_estende_o_prazo_e_audita",
    ],
    29: [
        "tests/aceitacao/test_cenario_29_aporte.py::test_o_aporte_inicial_vai_so_para_a_reserva",
    ],
    30: [
        "tests/aceitacao/test_cenario_30_tarifa.py::test_a_tarifa_e_registrada_como_despesa_e_nao_chega_ao_comprador",
    ],
    31: [
        "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre",
        "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_frete_devolvido_depois_do_pagamento_do_frete_tambem_conta_como_coberto",
    ],
    32: [
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_a_devolucao_devida_antes_do_repasse_e_a_unica_ressalva",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b",
    ],
    33: [
        "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_antes_do_repasse_a_devolucao_sai_dos_recursos_da_propria_rodada",
        "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_depois_do_repasse_o_que_falta_fica_sem_cobertura_ate_o_administrador_escolher",
    ],
    34: [
        "tests/aceitacao/test_cenario_34_reserva_insuficiente.py::test_reserva_que_nao_cobre_alerta_e_o_aporte_do_administrador_resolve",
    ],
    35: [
        "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional",
        "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_pela_tela",
    ],
    36: [
        "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_36_recusas_da_confirmacao",
        "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_36_pela_tela",
    ],
    37: [
        "tests/tecnicos/test_pagamentos_fronteiras.py::test_nenhuma_rota_comando_ou_admin_registra_pagamento",
        "tests/tecnicos/test_pagamentos_fronteiras.py::test_so_a_sincronizacao_escreve_nos_registros_de_pagamento",
        "tests/tecnicos/test_pagamentos_sincronizacao.py::test_a_sincronizacao_grava_a_tarifa_e_a_liberacao",
        "tests/tecnicos/test_pagamentos_sincronizacao.py::test_o_historico_so_aceita_insercao",
    ],
    38: [
        "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_com_o_simulador_nao_carrega",
        "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_sem_provedor_configurado_nao_recebe_o_simulador",
    ],
    39: [
        "tests/tecnicos/test_financeiro_concorrencia.py::test_dois_pagamentos_do_mesmo_pedido_ao_mesmo_tempo",
        "tests/tecnicos/test_pedidos_quitacao.py::test_dois_pagamentos_aceitos_so_um_quita",
    ],
    40: [
        "tests/tecnicos/test_repasse.py::test_o_repasse_so_baixa_a_obrigacao_com_o_fornecedor",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_repasse_limitado_ao_liberado_e_conciliado",
    ],
    41: [
        "tests/tecnicos/test_cancelamento_com_pedidos.py::test_cancela_o_nao_pago_e_preserva_o_pago",
        "tests/tecnicos/test_cancelamento_da_rodada.py::test_cancela_a_rodada_em_interesse_e_zera_as_reservas",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_com_reembolso_durante_a_margem",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_nova_rodada_depois_do_cancelamento",
    ],
    42: [
        "tests/tecnicos/test_cancelamento_da_rodada.py::test_so_o_administrador_ativo_cancela",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http",
        "tests/tecnicos/test_cancelamento_telas.py::test_comprador_e_fornecedor_nao_cancelam",
    ],
    43: [
        "tests/tecnicos/test_cancelamento_aviso.py::test_aviso_com_reembolso_e_mensagem",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_reembolso_integral_do_pedido_pago",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_sem_pagamento_nao_ha_reembolso",
        "tests/tecnicos/test_cancelamento_telas.py::test_cancelar_com_reembolso_pela_tela",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_com_reembolso_durante_a_margem",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_depois_da_aprovacao_do_resultado",
    ],
    44: [
        "tests/tecnicos/test_cancelamento_aviso.py::test_aviso_sem_reembolso_e_sem_mensagem",
        "tests/tecnicos/test_cancelamento_telas.py::test_cancelar_sem_reembolso_pela_tela",
        "tests/tecnicos/test_cancelamento_com_pedidos.py::test_pagamento_em_duplicidade_continua_como_estava",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente",
    ],
    45: [
        "tests/tecnicos/test_cancelamento_da_rodada.py::test_ciclos_condicoes_e_prazos_ficam_como_estavam",
        "tests/tecnicos/test_cancelamento_telas.py::test_pagina_da_rodada_cancelada_so_le",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_nova_rodada_depois_do_cancelamento",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_depois_da_aprovacao_do_resultado",
    ],
    46: [
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_falha_definitiva_segue_para_a_devolucao_excepcional",
    ],
    47: [
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_nenhuma_rota_altera_pedido_item_t0_ou_frete",
        "tests/tecnicos/test_retirada_comprador.py::test_as_rotas_do_comprador_nao_criam_ocorrencia",
    ],
    48: [
        "tests/tecnicos/test_ocorrencias.py::test_a_ocorrencia_nao_muda_o_pedido_nem_a_rodada",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual",
        "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_registrar_a_ocorrencia",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_entrega_parcial_ocorrencia_e_liberacao",
        "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenarios_48_e_52_a_ocorrencia_nao_muda_pedido_nem_rodada",
    ],
    49: [
        "tests/tecnicos/test_ocorrencias.py::test_cenario_49_a_soma_nao_passa_da_quantidade_paga",
        "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_ocorrencia_acima_do_saldo",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_t18_duas_ocorrencias_ao_mesmo_tempo_pela_rota",
        "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenario_49_a_soma_das_ocorrencias_nao_passa_da_quantidade_paga",
    ],
    50: [
        "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_so_o_administrador_acessa",
        "tests/tecnicos/test_retirada_comprador.py::test_a_pagina_nao_tem_formulario_de_falta",
        "tests/tecnicos/test_retirada_comprador.py::test_o_comprador_nao_alcanca_escrita_da_e14",
        "tests/tecnicos/test_retirada_comprador.py::test_as_rotas_do_comprador_nao_criam_ocorrencia",
    ],
    51: [
        "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_pagamento_aprovado_junto_do_cancelamento_gera_devolucao_e_alerta",
        "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta",
    ],
    52: [
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_a_rodada_liberada_nao_e_cancelada_pela_tela",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_52_cancelamento_com_ocorrencia_anterior",
        "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenarios_48_e_52_a_ocorrencia_nao_muda_pedido_nem_rodada",
    ],
    53: [
        "tests/tecnicos/test_apuracao_viavel.py::test_a_restauracao_nao_espera_a_autorizacao_da_devolucao",
    ],
    54: [
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_parcelas_de_outro_fornecedor_nao_mudam",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai",
    ],
    55: [
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
        "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre",
    ],
    56: [
        "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ],
    57: [
        "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada",
    ],
    58: [
        "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_banimento_ou_remocao_depois_do_pedido_bloqueia_o_uso",
        "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_preserva_conta_historico_e_convite",
        "tests/tecnicos/test_perfil_concorrencia.py::test_remocao_depois_da_leitura_recusa_o_perfil_e_nao_grava_avatar",
        "tests/tecnicos/test_contas_login_senha.py::test_login_de_email_banido_e_recusado_com_a_mensagem_generica",
    ],
    59: [
        "tests/tecnicos/test_contas_google_login.py::test_alias_de_email_banido_entra_normalmente",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_alias_de_email_banido_recebe_e_usa_o_link",
        "tests/tecnicos/test_convites_emissao.py::test_emissao_para_alias_de_email_banido_funciona",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_afeta_so_o_endereco_exato",
        "tests/tecnicos/test_contas_login_senha.py::test_login_de_alias_nao_e_afetado_pelo_banimento_do_endereco_base",
    ],
    60: [
        "tests/tecnicos/test_moderacao_servicos.py::test_reativar_volta_a_ativa_sem_restaurar_nada",
        "tests/tecnicos/test_moderacao_servicos.py::test_suspender_pela_tela_nao_encerra_a_sessao_nem_bane",
    ],
    61: [
        "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
    ],
    62: [
        "tests/aceitacao/test_cenario_62_papel_imutavel.py::test_banco_recusa_trocar_o_papel_mesmo_com_fornecedor_preenchido",
        "tests/aceitacao/test_cenario_62_papel_imutavel.py::test_nenhum_formulario_edita_o_papel_da_propria_conta",
        "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_comprador",
    ],
    63: [
        "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_com_um_unico_arredondamento",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
        "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_de_455_centavos",
        "tests/tecnicos/test_interesses_carrinho.py::test_quantidade_recusada_volta_no_formulario_do_produto",
    ],
    64: [
        "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_com_um_unico_arredondamento",
        "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_e_arredondado_uma_vez_so",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_12_99_vezes_0_35",
        "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_de_455_centavos",
    ],
    65: [
        "tests/tecnicos/test_pedidos_abertura.py::test_produto_por_peso_guarda_o_subtotal_arredondado",
    ],
    66: [
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
    ],
    67: [
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_ajuste_da_previsao_pela_tela_e_reenvio_com_o_conteudo_original",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_painel_do_fornecedor",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_do_resultado_aprovado_ao_pedido_aceito",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_comprador_nao_entra_no_portal",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_portal_nao_expoe_dado_da_e14",
    ],
    68: [
        "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_do_resultado_aprovado_ao_pedido_aceito",
    ],
    69: [
        "tests/tecnicos/test_pedido_formal_telas.py::test_depois_das_tres_falhas_o_formulario_aparece",
        "tests/tecnicos/test_pedido_formal_envio.py::test_exatamente_tres_tentativas_automaticas",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
    ],
    70: [
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_gera_um_so_envio",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_um_token_novo_faz_uma_tentativa_nova",
        "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro",
    ],
    71: [
        "tests/tecnicos/test_rodadas_estoque.py::test_reducao_abaixo_do_reservado_e_recusada",
        "tests/tecnicos/test_rodadas_estoque.py::test_reducao_ate_o_reservado_e_aceita",
        "tests/tecnicos/test_rodadas_estoque.py::test_sem_limite_nao_pode_ir_abaixo_do_reservado",
        "tests/tecnicos/test_rodadas_minimo.py::test_altera_o_minimo_em_interesse_e_audita",
    ],
    72: [
        "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico",
        "tests/tecnicos/test_catalogo_condicoes.py::test_preco_muda_em_qualquer_etapa",
        "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_a_fase_prevalece_sobre_o_valor_pela_rota",
        "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_nenhuma_condicao_muda_fora_de_interesse",
        "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_preco_muda_nas_quatro_etapas_ativas",
        "tests/tecnicos/test_interesses_preco.py::test_preco_alterado_no_fechamento_atinge_o_carrinho",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
        "tests/tecnicos/test_rodadas_minimo.py::test_minimo_congelado_pela_rota",
    ],
    73: [
        "tests/tecnicos/test_rodadas_ciclos.py::test_cenario_73_ciclos_anteriores_nao_mudam",
        "tests/tecnicos/test_rodadas_ciclos.py::test_condicoes_voltam_a_ser_editaveis_na_volta_para_interesse",
        "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_depois_do_retorno_as_condicoes_voltam_a_ser_editaveis",
    ],
    74: [
        "tests/tecnicos/test_apuracao_viavel.py::test_a_fila_nao_reserva_na_rodada_apurada",
        "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila",
    ],
    75: [
        "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
        "tests/tecnicos/test_interesses_parcela_modelo.py::test_atualizacoes_validas_do_cenario_75",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_do_produto_atende_a_fila_pela_sequencia_original",
    ],
    76: [
        "tests/tecnicos/test_interesses_fila.py::test_novo_comprador_so_recebe_o_que_sobra_da_fila",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_adicao_sem_estoque_e_recusada_e_o_aumento_atende_c_antes_de_d",
    ],
    77: [
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
        "tests/tecnicos/test_pedido_formal.py::test_as_quantidades_pendentes_nao_entram",
        "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
    ],
    78: [
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_alocar_de_novo_nao_muda_nada",
        "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem",
        "tests/tecnicos/test_interesses_fila.py::test_execucao_repetida_nao_altera_nada",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro",
        "tests/tecnicos/test_interesses_concorrencia.py::test_suspensao_confirmada_antes_barra_a_adicao",
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ],
    79: [
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor",
    ],
    80: [
        "tests/tecnicos/test_contas_modelo.py::test_conta_recusa_email_em_uso_com_variacao_de_caixa_e_espacos",
        "tests/tecnicos/test_convites_cadastro.py::test_email_que_virou_conta_depois_da_emissao_e_recusado",
        "tests/tecnicos/test_convites_emissao.py::test_emissao_recusa_email_ja_em_uso_por_qualquer_conta",
    ],
    81: [
        "tests/tecnicos/test_convites_cadastro.py::test_comprador_e_fornecedor_com_emails_diferentes_sao_contas_independentes",
        "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa",
    ],
    82: [
        "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social",
        "tests/tecnicos/test_contas_google_login.py::test_segundo_login_com_o_mesmo_uid_entra_na_mesma_conta",
        "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada",
    ],
    83: [
        "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes",
        "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_conta_com_email_banido_mesmo_ativa",
    ],
    84: [
        "tests/tecnicos/test_contas_emails.py::test_normalizar_email_nao_altera_aliases",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_afeta_so_o_endereco_exato",
        "tests/tecnicos/test_contas_emails.py::test_normalizar_email_propriedade_alias_continua_distinto",
    ],
    85: [
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
        "tests/tecnicos/test_interesses_carrinho.py::test_quantidade_recusada_volta_no_formulario_do_produto",
    ],
    86: [
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_invalidos_no_servico",
        "tests/tecnicos/test_catalogo_quantidades.py::test_criar_produto_recusa_incremento_float_ou_int",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela",
    ],
    87: [
        "tests/tecnicos/test_catalogo_condicoes.py::test_alterar_e_remover_o_multiplo_em_interesse",
        "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico",
        "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_invalido_em_interesse",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_aceita_e_aceita_vazio",
    ],
    88: [
        "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_7_99_vezes_0_25",
    ],
    89: [
        "tests/tecnicos/test_interesses_progresso.py::test_arredondamento_por_comprador",
        "tests/tecnicos/test_pedidos_calculo.py::test_produtos_soma_os_subtotais_ja_arredondados",
        "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_2_50_vezes_0_25",
    ],
    90: [
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenarios_90_e_91_integral_devolve_exatamente_o_cobrado",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
    ],
    91: [
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_estorno_conclui_e_liquida_a_obrigacao",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_depois_da_aprovacao_do_resultado",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenarios_90_e_91_integral_devolve_exatamente_o_cobrado",
    ],
    92: [
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico",
        "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso",
    ],
    93: [
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_que_falha_e_registrado_e_o_botao_continua",
        "tests/tecnicos/test_pedido_formal_telas.py::test_reenvio_que_falha_continua_com_o_botao",
    ],
    94: [
        "tests/tecnicos/test_pedido_formal_telas.py::test_durante_o_ciclo_a_pagina_explica_e_nao_oferece_o_botao",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado",
        "tests/tecnicos/test_pedido_formal_telas.py::test_reenvio_durante_o_ciclo_e_recusado_com_409",
    ],
    95: [
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_em_paralelo_envia_uma_vez",
    ],
    96: [
        "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero",
    ],
    97: [
        "tests/tecnicos/test_interesses_carrinho.py::test_remover_pendentes_pela_rota",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno",
    ],
    98: [
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remocoes_invalidas_sao_recusadas_sem_escrita",
        "tests/tecnicos/test_interesses_carrinho.py::test_remocao_de_pendentes_recusada_e_campos_extras_ignorados",
    ],
    99: [
        "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido",
        "tests/tecnicos/test_interesses_carrinho.py::test_remocao_de_pendentes_recusada_e_campos_extras_ignorados",
    ],
    100: [
        "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remocao_de_pendentes_em_paralelo_com_a_inclusao",
        "tests/tecnicos/test_interesses_concorrencia.py::test_atendimento_da_fila_e_suspensao_se_serializam",
        "tests/tecnicos/test_interesses_concorrencia.py::test_vinte_insercoes_em_paralelo_recebem_sequencias_distintas",
    ],
    101: [
        "tests/tecnicos/test_interesses_concorrencia.py::test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado",
        "tests/tecnicos/test_interesses_fila.py::test_liberacao_vai_para_a_fila_na_mesma_transacao",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_reducao_em_paralelo_com_adicao_atende_c_antes_de_e",
        "tests/tecnicos/test_interesses_concorrencia.py::test_dez_adicoes_de_dois_com_limite_dez",
    ],
    102: [
        "tests/tecnicos/test_interesses_fila.py::test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_outro_fornecedor_nao_recebe_as_pendentes_de_f",
    ],
    103: [
        "tests/tecnicos/test_apuracao_retorno.py::test_unidades_de_caixa_invalidada_ficam_reservadas_sem_passar_pela_fila",
    ],
    104: [
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_pendentes_de_c_ficam_fora_do_progresso_e_do_fechamento",
        "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_minimo_nao_conta_pendentes",
    ],
    105: [
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_compativel_e_aceito",
    ],
    106: [
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_para_2_no_cenario_106_e_recusado",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_o_multiplo_e_recusado",
    ],
    107: [
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_congelado",
        "tests/tecnicos/test_catalogo_incremento.py::test_preco_continua_editavel_no_fechamento",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
    ],
    108: [
        "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam",
        "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_suspensao_ou_remocao_se_serializam",
    ],
    109: [
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
        "tests/tecnicos/test_interesses_carrinho.py::test_quantidade_recusada_volta_no_formulario_do_produto",
    ],
    110: [
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_invalidos_no_servico",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos",
        "tests/tecnicos/test_catalogo_quantidades.py::test_criar_produto_recusa_incremento_float_ou_int",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela",
    ],
    111: [
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_aceita_e_aceita_vazio",
    ],
    112: [
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_112_parcial_usa_o_valor_registrado",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
    ],
    113: [
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_113_quatro_parciais_somam_o_pago",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
    ],
    114: [
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_integral_depois_de_parcial_completa_exatamente",
        "tests/tecnicos/test_ocorrencias.py::test_o_cancelamento_devolve_so_o_saldo_restante",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_114_integral_depois_do_parcial_completa_exatamente",
    ],
    115: [
        "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_115_centavos_nao_passam_do_pago",
    ],
    116: [
        "tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py::test_cenario_116_numeros_do_cenario",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_116_servico_e_frete_proporcionais",
    ],
    117: [
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_117_cada_devolucao_e_registrada_separadamente",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
    ],
    118: [
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_post_durante_a_tentativa_automatica_e_recusado_sem_esperar",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar",
    ],
    119: [
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia",
    ],
}

TECNICOS: dict[str, list[str]] = {
    "T-1": [
        "tests/tecnicos/test_nucleo_tempo.py::test_fronteira_prazo_encerrado_exclusivo",
        "tests/tecnicos/test_pedidos_prazos.py::test_com_o_bloqueio_parado_o_servidor_recusa_a_tentativa",
        "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento",
    ],
    "T-2": [
        "tests/tecnicos/test_nucleo_tempo.py::test_fronteira_ate_o_limite_inclusivo",
        "tests/tecnicos/test_pedidos_quitacao.py::test_fronteira_de_48_horas_da_margem",
    ],
    "T-3": [
        "tests/tecnicos/test_pedidos_quitacao.py::test_aviso_atrasado_nao_muda_o_horario_de_aprovacao",
    ],
    "T-4": [
        "tests/tecnicos/test_apuracao_inicio.py::test_antes_de_48_horas_e_recusada_sem_consulta_nem_escrita",
        "tests/tecnicos/test_apuracao_inicio.py::test_em_48_horas_exatas_a_apuracao_e_aceita",
        "tests/tecnicos/test_apuracao_telas.py::test_antes_de_48_horas_a_pagina_so_informa_o_horario",
        "tests/tecnicos/test_pedidos_prazos.py::test_a_apuracao_so_pode_comecar_em_48_horas",
    ],
    "T-5": [
        "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos",
        "tests/tecnicos/test_pedidos_prazos.py::test_o_t0_nao_muda_nem_por_sql",
    ],
    "T-6": [
        "tests/tecnicos/test_pagamentos_concorrencia.py::test_cinco_avisos_diferentes_do_mesmo_pagamento",
        "tests/tecnicos/test_pagamentos_concorrencia.py::test_cinco_sincronizacoes_do_mesmo_pagamento_aprovado",
        "tests/tecnicos/test_pagamentos_concorrencia.py::test_mesmo_aviso_cinco_vezes_em_paralelo_reconhece_o_pagamento_uma_vez",
        "tests/tecnicos/test_pedidos_concorrencia.py::test_aviso_e_tarefa_ao_mesmo_tempo_decidem_uma_vez",
    ],
    "T-7": [
        "tests/tecnicos/test_apuracao_inicio.py::test_apuracao_espera_o_aviso_que_trava_a_situacao_de_y",
        "tests/tecnicos/test_apuracao_inicio.py::test_aviso_antes_da_apuracao_quita_y",
        "tests/tecnicos/test_pedidos_concorrencia.py::test_bloqueio_e_aviso_ao_mesmo_tempo_quitam_uma_vez",
        "tests/tecnicos/test_pedidos_concorrencia.py::test_bloqueio_e_aviso_de_outra_mudanca_ao_mesmo_tempo",
        "tests/tecnicos/test_pedidos_concorrencia.py::test_bloqueio_e_aviso_em_qualquer_ordem_quitam_uma_vez",
        "tests/tecnicos/test_pedidos_concorrencia.py::test_cancelamento_em_execucao_nao_trava_a_moderacao",
        "tests/tecnicos/test_pedidos_concorrencia.py::test_dois_pagamentos_ao_mesmo_tempo_um_quita_e_o_outro_duplica",
        "tests/tecnicos/test_pedidos_concorrencia.py::test_duas_aberturas_ao_mesmo_tempo_abrem_uma_so",
    ],
    "T-8": [
        "tests/tecnicos/test_devolucoes_execucao.py::test_falha_depois_de_executar_repete_a_mesma_chave",
        "tests/tecnicos/test_devolucoes_execucao.py::test_tres_falhas_abrem_o_alerta_e_a_quarta_conclui",
        "tests/tecnicos/test_simulador_estornos.py::test_falha_depois_de_executar_deixa_o_estorno_gravado",
        "tests/tecnicos/test_simulador_estornos.py::test_mesma_chave_devolve_o_mesmo_estorno",
    ],
    "T-9": [
        "tests/tecnicos/test_devolucoes_excepcional.py::test_depois_da_confirmacao_o_provedor_nao_e_mais_chamado",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_devolucao_pendente_na_plataforma_bloqueia",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_estorno_em_processamento_no_provedor_recusa_e_agenda_a_verificacao",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_falha_definitiva_ainda_nao_comprovada_bloqueia",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_nao_vale_duas_vezes",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_sem_parcela_e_parcela_concluida_sao_recusadas",
    ],
    "T-10": [
        "tests/tecnicos/test_financeiro_concorrencia.py::test_designacao_e_utilizacao_ao_mesmo_tempo",
        "tests/tecnicos/test_financeiro_concorrencia.py::test_duas_designacoes_que_juntas_passam_do_livre",
        "tests/tecnicos/test_financeiro_reserva.py::test_obrigacoes_sem_cobertura_acima_do_livre_abrem_o_alerta",
        "tests/tecnicos/test_financeiro_reserva.py::test_uso_acima_do_livre_e_recusado_inteiro",
        "tests/tecnicos/test_financeiro_telas.py::test_designar_acima_do_livre_responde_409_com_a_mensagem",
    ],
    "T-11": [
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b",
        "tests/tecnicos/test_financeiro_concorrencia.py::test_dois_repasses_que_juntos_passam_do_liberado",
        "tests/tecnicos/test_financeiro_liquidez_e_saidas.py::test_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b",
        "tests/tecnicos/test_financeiro_liquidez_e_saidas.py::test_repasse_liberado_baixa_so_a_obrigacao_daquele_fornecedor",
        "tests/tecnicos/test_financeiro_livro.py::test_dinheiro_do_fornecedor_nao_vai_para_outra_rodada",
        "tests/tecnicos/test_financeiro_livro.py::test_obrigacao_do_fornecedor_so_vai_para_onde_a_p2_permite",
        "tests/tecnicos/test_financeiro_livro.py::test_tarifa_nao_sai_do_dinheiro_do_fornecedor",
        "tests/tecnicos/test_repasse.py::test_o_liberado_de_outro_fornecedor_nao_paga_este",
    ],
    "T-12": [
        "tests/tecnicos/test_configuracao_pagamentos.py::test_nem_a_web_nem_o_worker_sobem_em_producao_com_o_simulador",
        "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_sem_provedor_configurado_nao_recebe_o_simulador",
        "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_com_o_simulador_nao_carrega",
    ],
    "T-13": [
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_dois_cancelamentos_com_reembolso_gravam_um_por_pedido",
        "tests/tecnicos/test_cancelamento_da_rodada.py::test_cancelar_de_novo_e_recusado",
        "tests/tecnicos/test_cancelamento_da_rodada.py::test_dois_cancelamentos_em_paralelo_gravam_um",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_dois_cancelamentos_em_paralelo_geram_um_estorno_por_pagamento",
    ],
    "T-14": [
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago",
    ],
    "T-15": [
        "tests/tecnicos/test_cancelamento_com_pedidos.py::test_pagamento_em_duplicidade_continua_como_estava",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente",
    ],
    "T-16": [
        "tests/tecnicos/test_cancelamento_da_rodada.py::test_a_assinatura_nao_aceita_lista_de_compradores_nem_motivo",
        "tests/tecnicos/test_cancelamento_telas.py::test_a_rota_recusa_campos_fora_da_indicacao",
        "tests/tecnicos/test_cancelamento_telas.py::test_aceita_so_a_indicacao",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http",
        "tests/tecnicos/test_cancelamento_telas.py::test_comprador_e_fornecedor_nao_cancelam",
    ],
    "T-17": [
        "tests/tecnicos/test_pedidos_abertura.py::test_composicao_do_pedido_nao_muda_nem_some",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_nenhuma_rota_altera_pedido_item_t0_ou_frete",
    ],
    "T-18": [
        "tests/tecnicos/test_ocorrencias.py::test_duas_ocorrencias_no_mesmo_item_t18",
        "tests/tecnicos/test_ocorrencias.py::test_o_mesmo_acionamento_em_paralelo",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_t18_duas_ocorrencias_ao_mesmo_tempo_pela_rota",
    ],
    "T-19": [
        "tests/tecnicos/test_apuracao_inicio.py::test_aviso_repetido_nao_repete_destino_obrigacao_nem_alerta",
        "tests/tecnicos/test_apuracao_inicio.py::test_aviso_espera_a_apuracao_que_ja_cancelou_y",
        "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_pagamento_aprovado_junto_do_cancelamento_gera_devolucao_e_alerta",
        "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta",
    ],
    "T-20": [
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ],
    "T-21": [
        "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre",
    ],
    "T-22": [
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
        "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada",
    ],
    "T-23": [
        "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico",
        "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_a_fase_prevalece_sobre_o_valor_pela_rota",
        "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_nenhuma_condicao_muda_fora_de_interesse",
        "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_preco_muda_nas_quatro_etapas_ativas",
        "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pela_rota",
        "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pelo_servico",
        "tests/tecnicos/test_rodadas_estoque.py::test_reducao_abaixo_do_reservado_e_recusada",
        "tests/tecnicos/test_rodadas_fechamento_concorrencia.py::test_alteracao_de_minimo_depois_do_inicio_e_recusada",
    ],
    "T-24": [
        "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_banimento_ou_remocao_depois_do_pedido_bloqueia_o_uso",
        "tests/tecnicos/test_contas_login_senha.py::test_login_de_alias_nao_e_afetado_pelo_banimento_do_endereco_base",
        "tests/tecnicos/test_contas_login_senha.py::test_login_de_email_banido_e_recusado_com_a_mensagem_generica",
        "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes",
    ],
    "T-25": [
        "tests/tecnicos/test_interesses_carrinho.py::test_quem_pode_ver_e_quem_pode_gravar",
        "tests/tecnicos/test_permissoes_papeis.py::test_comprador_nao_entra_na_area_do_fornecedor",
        "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_comprador_nao_entra_no_portal",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_e_recusado_nas_rotas_da_e14",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_compra",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_portal_nao_expoe_dado_da_e14",
    ],
    "T-26": [
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_aceitas",
        "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_12_99_vezes_0_35",
        "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_com_um_unico_arredondamento",
        "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_de_455_centavos",
        "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_aceita_e_aceita_vazio",
    ],
    "T-27": [
        "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_rodada_de_outro_fornecedor_ou_inexistente_da_o_mesmo_404",
    ],
    "T-28": [
        "tests/tecnicos/test_pedido_formal_envio.py::test_exatamente_tres_tentativas_automaticas",
        "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha",
        "tests/tecnicos/test_pedido_formal_telas.py::test_depois_das_tres_falhas_o_formulario_aparece",
    ],
    "T-29": [
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_em_pedidos_diferentes_envia_um_so_email",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_em_paralelo_envia_uma_vez",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_gera_um_so_envio",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_um_token_novo_faz_uma_tentativa_nova",
        "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro",
    ],
    "T-30": [
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_do_produto_atende_a_fila_pela_sequencia_original",
        "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
    ],
    "T-31": [
        "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro",
        "tests/tecnicos/test_interesses_concorrencia.py::test_suspensao_confirmada_antes_barra_a_adicao",
    ],
    "T-32": [
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ],
    "T-33": [
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_minimo_nao_conta_pendentes",
        "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
    ],
    "T-34": [
        "tests/tecnicos/test_contas_modelo.py::test_conta_corrida_mesmo_email_normalizado_com_papeis_diferentes",
        "tests/tecnicos/test_convites_cadastro_concorrencia.py::test_dois_convites_com_mesmo_email_normalizado_em_paralelo",
    ],
    "T-35": [
        "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social",
        "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada",
    ],
    "T-36": [
        "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes",
        "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa",
        "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_conta_com_email_banido_mesmo_ativa",
    ],
    "T-37": [
        "tests/tecnicos/test_contas_emails.py::test_normalizar_email_propriedade_variacoes_e_idempotencia",
        "tests/tecnicos/test_normalizacao_varredura.py::test_codigo_de_apps_nao_compara_email_sem_normalizar",
        "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos",
        "tests/tecnicos/test_normalizacao_varredura.py::test_varredura_acusa_iexact_em_arquivo_temporario",
        "tests/tecnicos/test_contas_emails.py::test_normalizar_email_propriedade_alias_continua_distinto",
    ],
    "T-38": [
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_invalidos_no_servico",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_aceitas",
        "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
        "tests/tecnicos/test_catalogo_quantidades.py::test_criar_produto_recusa_incremento_float_ou_int",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_aceita_e_aceita_vazio",
    ],
    "T-39": [
        "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
        "tests/tecnicos/test_varredura_float.py::test_a_varredura_acusa_float_com_arquivo_e_linha",
        "tests/tecnicos/test_varredura_float.py::test_a_varredura_cobre_os_modulos_e_ignora_as_migracoes",
        "tests/tecnicos/test_varredura_float.py::test_a_varredura_nao_acusa_inteiros_decimais_nem_anotacoes",
        "tests/tecnicos/test_varredura_float.py::test_modulos_de_dinheiro_nao_usam_float",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_2_50_vezes_0_25",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_7_99_vezes_0_25",
    ],
    "T-40": [
        "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
    ],
    "T-41": [
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado",
    ],
    "T-42": [
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero",
        "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado",
    ],
    "T-43": [
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remocoes_invalidas_sao_recusadas_sem_escrita",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
    ],
    "T-44": [
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao",
    ],
    "T-45": [
        "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remocao_de_pendentes_em_paralelo_com_a_inclusao",
        "tests/tecnicos/test_interesses_concorrencia.py::test_atendimento_da_fila_e_suspensao_se_serializam",
        "tests/tecnicos/test_interesses_concorrencia.py::test_vinte_insercoes_em_paralelo_recebem_sequencias_distintas",
    ],
    "T-46": [
        "tests/tecnicos/test_interesses_concorrencia.py::test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_adicao_sem_estoque_e_recusada_e_o_aumento_atende_c_antes_de_d",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_outro_fornecedor_nao_recebe_as_pendentes_de_f",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_reducao_em_paralelo_com_adicao_atende_c_antes_de_e",
        "tests/tecnicos/test_interesses_concorrencia.py::test_dez_adicoes_de_dois_com_limite_dez",
        "tests/tecnicos/test_interesses_fila.py::test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele",
    ],
    "T-47": [
        "tests/tecnicos/test_pedido_formal.py::test_as_quantidades_pendentes_nao_entram",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
        "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
    ],
    "T-48": [
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_compativel_e_aceito",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_congelado",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_o_multiplo_e_recusado",
    ],
    "T-49": [
        "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam",
        "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_suspensao_ou_remocao_se_serializam",
    ],
    "T-50": [
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos",
        "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_recusa_float_e_int",
        "tests/tecnicos/test_nucleo_campos_decimais.py::test_campos_recusam_float_na_validacao",
        "tests/tecnicos/test_nucleo_valores.py::test_conversao_quantidade_recusa_excesso_de_casas",
        "tests/tecnicos/test_nucleo_valores.py::test_conversao_recusa_float",
        "tests/tecnicos/test_catalogo_quantidades.py::test_criar_produto_recusa_incremento_float_ou_int",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_invalidos_no_servico",
    ],
    "T-51": [
        "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo",
    ],
    "T-52": [
        "tests/tecnicos/test_devolucoes_reembolso.py::test_quantidade_invalida_e_recusada",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
    ],
    "T-53": [
        "tests/tecnicos/test_devolucoes_concorrencia.py::test_dois_parciais_do_mesmo_item_nunca_passam_do_pago",
        "tests/tecnicos/test_devolucoes_concorrencia.py::test_tres_parciais_ao_mesmo_tempo_respeitam_o_pago",
    ],
    "T-54": [
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_antes_da_primeira_tentativa_automatica_o_reenvio_e_recusado",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado",
        "tests/tecnicos/test_pedido_formal_telas.py::test_reenvio_durante_o_ciclo_e_recusado_com_409",
    ],
    "T-55": [
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia",
    ],
}
