"""A matriz de rastreabilidade da fase 1 (E16-07): cenário (§16) e teste técnico -> testes.

Cada entrada tem as afirmações verificáveis do texto-base (até 140 caracteres) e, para cada uma,
os testes que a provam: `caminho/do/arquivo.py::nome_do_teste` (ou `::Classe::nome`), relativo à
raiz, sem parâmetros. O mesmo teste pode servir a afirmações diferentes. `test_matriz.py` confere
a estrutura e a existência, a coleta e a ausência de pulo; o documento
`docs/rastreabilidade-fase1.md` é gerado daqui (`python -m tests.rastreabilidade.gerar`).
"""

CENARIOS: dict[int, dict[str, list[str]]] = {
    1: {
        "Convite com mais de 24h, já consumido ou usado com outro e-mail não cadastra usuário": [
            "tests/tecnicos/test_convites_cadastro.py::test_convite_consumido_nao_pode_ser_reutilizado",
            "tests/tecnicos/test_contas_google_cadastro.py::test_google_com_outro_email_nao_cadastra_pelo_convite",
            "tests/tecnicos/test_convites_cadastro.py::test_fronteira_de_24h_no_post",
            "tests/tecnicos/test_convites_cadastro.py::test_cadastro_cria_conta_email_verificado_e_sessao",
        ],
        "Convite de fornecedor não permite escolher outro fornecedor": [
            "tests/tecnicos/test_convites_cadastro.py::test_convite_consumido_nao_pode_ser_reutilizado",
            "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_fornecedor",
            "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_comprador",
            "tests/tecnicos/test_contas_google_cadastro.py::test_google_com_outro_email_nao_cadastra_pelo_convite",
        ],
    },
    2: {
        "Google sem conta e sem convite não cria conta nem abre sessão": [
            "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada",
        ],
        "Link sem conta não recebe e-mail nem abre sessão": [
            "tests/tecnicos/test_contas_link_de_acesso.py::test_email_sem_conta_tem_a_mesma_resposta_e_nao_envia",
        ],
        "Google com conta suspensa abre a sessão, mas a suspensão continua: sem adição de interesse": [
            "tests/aceitacao/test_cenario_02_login_nao_contorna_suspensao.py::test_google_de_conta_suspensa_entra_mas_nao_adiciona_interesse",
            "tests/tecnicos/test_contas_google_login.py::test_conta_suspensa_entra_pelo_google",
        ],
        "Link com conta suspensa abre a sessão, mas a suspensão continua: sem adição de interesse": [
            "tests/aceitacao/test_cenario_02_login_nao_contorna_suspensao.py::test_link_de_conta_suspensa_entra_mas_nao_adiciona_interesse",
            "tests/tecnicos/test_contas_link_de_acesso.py::test_suspensao_depois_do_pedido_nao_bloqueia",
        ],
        "Google com conta banida ou removida não abre a sessão": [
            "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
        ],
        "Link com conta banida ou removida não recebe link e não abre a sessão": [
            "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link",
            "tests/tecnicos/test_contas_link_de_acesso.py::test_banimento_ou_remocao_depois_do_pedido_bloqueia_o_uso",
        ],
    },
    3: {
        "Duas reservas simultâneas para a última unidade não podem ambas ser aceitas": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_ultima_unidade_disputada_so_uma_vence",
        ],
    },
    4: {
        "Interesse abaixo do mínimo permanece aberto indefinidamente": [
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_atingir_o_minimo_nao_inicia_nada_sozinho",
            "tests/tecnicos/test_interesses_progresso.py::test_atingir_o_minimo_nao_muda_a_etapa_nem_grava",
        ],
        "Atingir mínimo não inicia fechamento sozinho": [
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_atingir_o_minimo_nao_inicia_nada_sozinho",
            "tests/tecnicos/test_interesses_progresso.py::test_atingir_o_minimo_nao_muda_a_etapa_nem_grava",
        ],
    },
    5: {
        "Administrador inicia fechamento e o término ocorre 24h depois": [
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_inicio_registra_ciclo_prazo_de_24_horas_e_auditoria",
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_a_queda_e_a_recuperacao_do_minimo_nao_mexem_no_prazo",
        ],
        "Queda temporária do mínimo não reinicia nem estende o relógio": [
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_a_queda_e_a_recuperacao_do_minimo_nao_mexem_no_prazo",
            "tests/tecnicos/test_rodadas_fechamento_prorrogacao.py::test_a_queda_do_minimo_nao_prorroga",
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_inicio_registra_ciclo_prazo_de_24_horas_e_auditoria",
        ],
    },
    6: {
        "Produto de R$ 10,00, múltiplo 12 e 18 unidades gera R$ 120,00 elegíveis, não R$ 180,00": [
            "tests/tecnicos/test_interesses_progresso.py::test_dezoito_unidades_com_multiplo_doze",
        ],
    },
    7: {
        "Comprador A adiciona 8 unidades;": [
            "tests/tecnicos/test_interesses_carrinho.py::test_caixas_so_com_as_unidades_do_proprio_comprador",
            "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_as_ultimas_adicoes_perdem_o_excedente",
            "tests/tecnicos/test_interesses_progresso.py::test_caixa_formada_pela_ordem_de_adicao",
        ],
        "B adiciona 10: primeira caixa contém 8 de A e 4 de B;": [
            "tests/tecnicos/test_interesses_carrinho.py::test_caixas_so_com_as_unidades_do_proprio_comprador",
            "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_as_ultimas_adicoes_perdem_o_excedente",
            "tests/tecnicos/test_interesses_progresso.py::test_caixa_formada_pela_ordem_de_adicao",
        ],
        "B vê 6 excedentes": [
            "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_as_ultimas_adicoes_perdem_o_excedente",
            "tests/tecnicos/test_interesses_progresso.py::test_caixa_formada_pela_ordem_de_adicao",
            "tests/tecnicos/test_interesses_carrinho.py::test_caixas_so_com_as_unidades_do_proprio_comprador",
        ],
        "No fim do fechamento, essas 6 são removidas": [
            "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_as_ultimas_adicoes_perdem_o_excedente",
        ],
    },
    8: {
        "A aumenta posteriormente sua quantidade: o acréscimo fica depois das adições anteriores de B": [
            "tests/tecnicos/test_interesses_servicos.py::test_acrescimo_posterior_vai_para_o_fim_da_fila",
        ],
        "Redução de A remove primeiro seu acréscimo mais recente": [
            "tests/tecnicos/test_interesses_servicos.py::test_acrescimo_posterior_vai_para_o_fim_da_fila",
        ],
    },
    9: {
        "Fechamento encerrado com mínimo insuficiente volta para interesse": [
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_nao_atingido_volta_para_interesse",
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_atingido_aguarda_o_pagamento",
        ],
        "Com mínimo suficiente, fica bloqueado aguardando autorização de pagamento": [
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_atingido_aguarda_o_pagamento",
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_nao_atingido_volta_para_interesse",
        ],
    },
    10: {
        "Produtos de R$ 100,00 e R$ 300,00, frete de R$ 40,00: compradores pagam respectivamente R$ 115,00 e R$ 345,00, incluindo serviço e frete": [
            "tests/tecnicos/test_pedidos_calculo.py::test_cobranca_rateia_o_frete_pelos_produtos",
        ],
    },
    11: {
        "Na etapa de pagamento, nenhuma alteração de carrinho, novo comprador ou preço de catálogo modifica pedidos congelados": [
            "tests/tecnicos/test_pedidos_abertura.py::test_abertura_congela_um_pedido_por_comprador",
            "tests/tecnicos/test_pedidos_abertura.py::test_composicao_fica_congelada_apos_a_abertura",
        ],
    },
    12: {
        "Com pagamento aberto em `T0`, tentativas são aceitas antes de `T0 + 24h` e recusadas a partir de `T0 + 24h`, mesmo que a tarefa agendada...": [
            "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre",
            "tests/tecnicos/test_pedidos_prazos.py::test_com_o_bloqueio_parado_o_servidor_recusa_a_tentativa",
        ],
        "Durante a margem operacional não é possível comprar, alterar pedidos nem criar cobranças": [
            "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento",
            "tests/tecnicos/test_pedidos_prazos.py::test_depois_de_48_horas_nada_acontece_sozinho",
        ],
        "A rodada aguarda `T0 + 48h` e decisão administrativa": [
            "tests/tecnicos/test_pedidos_prazos.py::test_depois_de_48_horas_nada_acontece_sozinho",
        ],
    },
    13: {
        "Inadimplência em uma caixa invalida a caixa inteira; compradores pagos nela recebem estorno proporcional sem realocação para outra caixa": [
            "tests/tecnicos/test_apuracao_viavel.py::test_estorno_proporcional_das_unidades_em_caixa_invalidada",
        ],
    },
    14: {
        "Se produtos válidos pagos mantêm o mínimo, a diferença de frete de inadimplentes fica com o administrador e não altera cobranças concluídas": [
            "tests/tecnicos/test_apuracao_telas.py::test_aprovar_mostra_o_frete_e_esconde_o_botao",
            "tests/tecnicos/test_apuracao_aprovacao.py::test_aprovar_leva_a_apuracao_ao_livro_e_avanca_a_rodada",
        ],
    },
    15: {
        "Se produtos válidos pagos ficam abaixo do mínimo, a rodada retorna para interesse; pagos mantêm interesses e têm estornos autorizáveis...": [
            "tests/tecnicos/test_apuracao_telas.py::test_minimo_nao_atendido_devolve_a_rodada_e_mostra_o_estorno_integral",
        ],
    },
    16: {
        "Novo fechamento pode começar com estorno antigo pendente, sem misturar cobranças ou duplicar estoque": [
            "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente",
        ],
    },
    17: {
        "Webhook repetido não duplica pagamento, pedido, mensagem formal ou estorno": [
            "tests/tecnicos/test_notificacoes_emissao.py::test_emissao_repetida_nao_duplica",
        ],
    },
    18: {
        "Falta de R$ 25,00 em pedido de R$ 100,00 de produtos, R$ 5,00 de serviço e R$ 20,00 de frete gera R$ 31,25 de estorno": [
            "tests/tecnicos/test_ocorrencias.py::test_cenario_18_servico_e_frete_proporcionais",
            "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenario_18_reembolso_pontual_com_servico_e_frete_proporcionais",
        ],
    },
    19: {
        "Suspensão esvazia interesses e cancela pedidos não pagos; pedidos pagos continuam disponíveis para retirada": [
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_19_o_suspenso_retira",
            "tests/tecnicos/test_pedidos_moderacao.py::test_suspensao_cancela_o_pedido_nao_pago",
            "tests/tecnicos/test_interesses_suspensao.py::test_suspensao_esvazia_os_interesses_e_a_reversao_nao_restaura",
        ],
        "Reversão não restaura automaticamente interesses antigos sem regra específica": [
            "tests/tecnicos/test_interesses_suspensao.py::test_suspensao_esvazia_os_interesses_e_a_reversao_nao_restaura",
        ],
    },
    20: {
        "Remoção bloqueia acesso e novo cadastro com o e-mail, mas mantém histórico e pedidos pagos para controle administrativo": [
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_preserva_conta_historico_e_convite",
            "tests/tecnicos/test_interesses_suspensao.py::test_remocao_preserva_em_pedido_e_nao_apaga_parcelas",
        ],
    },
    21: {
        "Fornecedor não consegue consultar compradores ou dados de outro fornecedor, inclusive por acesso direto à API": [
            "tests/tecnicos/test_portal_do_fornecedor.py::test_rodada_de_outro_fornecedor_ou_inexistente_da_o_mesmo_404",
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_comprador_nao_entra_no_portal",
        ],
    },
    22: {
        "Liberação de retirada permite nova rodada imediatamente": [
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_22_nova_rodada_e_retirada_antiga",
            "tests/tecnicos/test_retirada.py::test_cenario_22_retirada_depois_do_prazo",
            "tests/tecnicos/test_liberacao_da_retirada.py::test_cenario_22_a_nova_rodada_nao_herda_a_reserva",
        ],
        "Retiradas antigas continuam registráveis por item": [
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_22_nova_rodada_e_retirada_antiga",
        ],
    },
    23: {
        "Após sete dias, itens restantes aparecem como pendentes de decisão/descarte; somente ação administrativa registra descarte efetivo": [
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_23_prazo_e_descarte",
            "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_cenario_23_pelas_telas",
            "tests/tecnicos/test_retirada_comprador.py::test_depois_do_prazo_sem_descarte",
            "tests/tecnicos/test_retirada.py::test_cenario_23_o_tempo_nao_descarta",
        ],
    },
    24: {
        "Falha no WhatsApp não desfaz pagamento nem impede que a notificação e o estado correto apareçam no site": [
            "tests/tecnicos/test_pedidos_quitacao.py::test_falha_do_whatsapp_nao_desfaz_a_quitacao",
            "tests/tecnicos/test_pedidos_abertura.py::test_falha_do_whatsapp_nao_desfaz_a_abertura",
            "tests/tecnicos/test_notificacoes_falha_isolada.py::test_falha_no_whatsapp_nao_desfaz_o_fato_nem_a_notificacao",
            "tests/tecnicos/test_notificacoes_falha_isolada.py::test_nada_e_tentado_antes_da_confirmacao_da_transacao",
        ],
    },
    25: {
        "Pagamento iniciado antes de `T0 + 24h` e aprovado pelo provedor em `T0 + 30h` quita o pedido, mesmo que a notificação chegue depois de...": [
            "tests/tecnicos/test_pedidos_quitacao.py::test_aprovacao_no_prazo_quita_o_pedido",
        ],
    },
    26: {
        "Pagamento aprovado depois de `T0 + 48h` não quita o pedido e gera obrigação de devolução integral, pela plataforma ou pela devolução...": [
            "tests/tecnicos/test_apuracao_inicio.py::test_reconsulta_registra_o_pagamento_aprovado_depois_de_48_horas",
            "tests/tecnicos/test_pedidos_quitacao.py::test_aprovacao_depois_da_margem_gera_devolucao",
        ],
    },
    27: {
        "A apuração final não começa antes de `T0 + 48h`, mesmo com todos os pedidos pagos": [
            "tests/tecnicos/test_pedidos_prazos.py::test_a_apuracao_so_pode_comecar_em_48_horas",
        ],
        "A partir de `T0 + 48h`, só começa com autorização do administrador": [
            "tests/tecnicos/test_pedidos_prazos.py::test_a_apuracao_so_pode_comecar_em_48_horas",
        ],
    },
    28: {
        "O administrador não consegue prorrogar o prazo de pagamento nem a margem operacional": [
            "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos",
            "tests/tecnicos/test_rodadas_fechamento_prorrogacao.py::test_prorrogacao_estende_o_prazo_e_audita",
        ],
        "Continua podendo prorrogar o fechamento conforme as regras existentes": [
            "tests/tecnicos/test_rodadas_fechamento_prorrogacao.py::test_prorrogacao_estende_o_prazo_e_audita",
        ],
    },
    29: {
        "O aporte inicial de R$ 1.000,00 entra na reserva e não altera a receita de serviço nem outra destinação": [
            "tests/aceitacao/test_cenario_29_aporte.py::test_o_aporte_inicial_vai_so_para_a_reserva",
        ],
    },
    30: {
        "A tarifa do provedor sobre um pagamento é registrada como despesa coberta pela receita de serviço, sem alterar obrigações com...": [
            "tests/aceitacao/test_cenario_30_tarifa.py::test_a_tarifa_e_registrada_como_despesa_e_nao_chega_ao_comprador",
        ],
    },
    31: {
        "Déficit de frete por inadimplência ou devolução é registrado separadamente (frete arrecadado, frete efetivo, déficit) e coberto pela...": [
            "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre",
            "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_frete_devolvido_depois_do_pagamento_do_frete_tambem_conta_como_coberto",
        ],
    },
    32: {
        "Recursos do fornecedor A nunca cobrem tarifa, déficit, prejuízo ou obrigação do fornecedor B, mesmo com saldo único no provedor": [
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b",
        ],
        "Movimentação com esse efeito é recusada": [
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
        ],
    },
    33: {
        "Devolução devida antes do repasse é financiada pelos recursos da própria rodada": [
            "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_antes_do_repasse_a_devolucao_sai_dos_recursos_da_propria_rodada",
            "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_depois_do_repasse_o_que_falta_fica_sem_cobertura_ate_o_administrador_escolher",
        ],
        "Devolução depois do repasse é coberta pela taxa de serviço, pela reserva ou por novo aporte": [
            "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_depois_do_repasse_o_que_falta_fica_sem_cobertura_ate_o_administrador_escolher",
            "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_antes_do_repasse_a_devolucao_sai_dos_recursos_da_propria_rodada",
        ],
    },
    34: {
        "Com reserva insuficiente, a obrigação permanece integralmente registrada e o sistema alerta": [
            "tests/aceitacao/test_cenario_34_reserva_insuficiente.py::test_reserva_que_nao_cobre_alerta_e_o_aporte_do_administrador_resolve",
        ],
        "Depois de novo aporte, a devolução é concluída sem duplicidade": [
            "tests/aceitacao/test_cenario_34_reserva_insuficiente.py::test_reserva_que_nao_cobre_alerta_e_o_aporte_do_administrador_resolve",
        ],
    },
    35: {
        "Quando a devolução pela plataforma é comprovadamente inviável, o administrador devolve diretamente ao comprador, e a plataforma registra...": [
            "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional",
        ],
        "Até a confirmação, a obrigação permanece integral": [
            "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional",
        ],
    },
    36: {
        "A confirmação de devolução excepcional é recusada enquanto houver devolução pendente na plataforma para a mesma parcela, e não pode ser...": [
            "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_36_recusas_da_confirmacao",
            "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_36_pela_tela",
        ],
    },
    37: {
        "Não existe forma de registrar pagamento de comprador recebido fora da plataforma integrada": [
            "tests/tecnicos/test_pagamentos_fronteiras.py::test_nenhuma_rota_comando_ou_admin_registra_pagamento",
            "tests/tecnicos/test_pagamentos_fronteiras.py::test_so_a_sincronizacao_escreve_nos_registros_de_pagamento",
        ],
    },
    38: {
        "A aplicação não inicia em produção com o simulador de pagamentos habilitado": [
            "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_com_o_simulador_nao_carrega",
            "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_sem_provedor_configurado_nao_recebe_o_simulador",
        ],
    },
    39: {
        "Pedido com dois pagamentos aceitos: apenas um quita o pedido, e o outro gera obrigação de devolução integral": [
            "tests/tecnicos/test_pedidos_quitacao.py::test_dois_pagamentos_aceitos_so_um_quita",
            "tests/tecnicos/test_financeiro_concorrencia.py::test_dois_pagamentos_do_mesmo_pedido_ao_mesmo_tempo",
        ],
    },
    40: {
        "O repasse manual ao fornecedor continua registrável e consome apenas a obrigação com aquele fornecedor": [
            "tests/tecnicos/test_repasse.py::test_o_repasse_so_baixa_a_obrigacao_com_o_fornecedor",
        ],
    },
    41: {
        "O cancelamento administrativo afeta todos os compradores da rodada": [
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_nova_rodada_depois_do_cancelamento",
            "tests/tecnicos/test_cancelamento_da_rodada.py::test_cancela_a_rodada_em_interesse_e_zera_as_reservas",
            "tests/tecnicos/test_cancelamento_com_pedidos.py::test_cancela_o_nao_pago_e_preserva_o_pago",
        ],
        "Não existe forma de cancelar a rodada para compradores selecionados": [
            "tests/tecnicos/test_cancelamento_com_pedidos.py::test_cancela_o_nao_pago_e_preserva_o_pago",
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_nova_rodada_depois_do_cancelamento",
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_com_reembolso_durante_a_margem",
            "tests/tecnicos/test_cancelamento_da_rodada.py::test_cancela_a_rodada_em_interesse_e_zera_as_reservas",
        ],
    },
    42: {
        "Somente o administrador consegue cancelar a rodada; compradores e fornecedores são recusados, inclusive por acesso direto à API": [
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http",
            "tests/tecnicos/test_cancelamento_da_rodada.py::test_so_o_administrador_ativo_cancela",
        ],
        "O cancelamento é aceito sem motivo e sem informação sobre o fornecedor": [
            "tests/tecnicos/test_cancelamento_telas.py::test_comprador_e_fornecedor_nao_cancelam",
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http",
            "tests/tecnicos/test_cancelamento_da_rodada.py::test_so_o_administrador_ativo_cancela",
        ],
    },
    43: {
        "Cancelamento com reembolso: cada comprador que pagou recebe devolução integral (produtos, serviço e frete), descontado o que já foi...": [
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_reembolso_integral_do_pedido_pago",
            "tests/tecnicos/test_cancelamento_aviso.py::test_aviso_com_reembolso_e_mensagem",
            "tests/tecnicos/test_cancelamento_telas.py::test_cancelar_com_reembolso_pela_tela",
        ],
        "O total devolvido nunca ultrapassa o valor pago, e quem não pagou não recebe devolução": [
            "tests/tecnicos/test_cancelamento_aviso.py::test_aviso_com_reembolso_e_mensagem",
        ],
    },
    44: {
        "Cancelamento sem reembolso não gera nenhuma devolução nova": [
            "tests/tecnicos/test_cancelamento_telas.py::test_cancelar_sem_reembolso_pela_tela",
            "tests/tecnicos/test_cancelamento_com_pedidos.py::test_pagamento_em_duplicidade_continua_como_estava",
            "tests/tecnicos/test_cancelamento_aviso.py::test_aviso_sem_reembolso_e_sem_mensagem",
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente",
        ],
        "Uma obrigação de devolução já existente (por exemplo, pagamento aprovado depois de `T0 + 48h`) continua pendente até ser liquidada": [
            "tests/tecnicos/test_cancelamento_com_pedidos.py::test_pagamento_em_duplicidade_continua_como_estava",
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente",
        ],
    },
    45: {
        "Depois do cancelamento, pagamentos, repasses, devoluções e demais registros financeiros anteriores continuam consultáveis e inalterados": [
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_depois_da_aprovacao_do_resultado",
        ],
    },
    46: {
        "Reembolsos do cancelamento usam a plataforma de pagamentos e, se ela for comprovadamente inviável, a devolução excepcional confirmada...": [
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_falha_definitiva_segue_para_a_devolucao_excepcional",
        ],
    },
    47: {
        "A partir da abertura do pagamento, nenhuma tela ou rota permite a comprador ou administrador adicionar, remover ou alterar produtos ou...": [
            "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409",
        ],
    },
    48: {
        "Ocorrência de 2 unidades faltantes de um produto de R$ 10,00 em pedido de R$ 100,00 de produtos, R$ 5,00 de serviço e R$ 20,00 de frete...": [
            "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_registrar_a_ocorrencia",
            "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual",
            "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenarios_48_e_52_a_ocorrencia_nao_muda_pedido_nem_rodada",
        ],
        "O pedido original continua igual, e ocorrência e reembolso ficam registrados à parte": [
            "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_registrar_a_ocorrencia",
            "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual",
        ],
    },
    49: {
        "A soma das ocorrências de um item não pode ultrapassar a quantidade paga desse item": [
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_t18_duas_ocorrencias_ao_mesmo_tempo_pela_rota",
            "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_ocorrencia_acima_do_saldo",
            "tests/tecnicos/test_ocorrencias.py::test_cenario_49_a_soma_nao_passa_da_quantidade_paga",
            "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenario_49_a_soma_das_ocorrencias_nao_passa_da_quantidade_paga",
        ],
        "Uma ocorrência que ultrapasse é recusada": [
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_t18_duas_ocorrencias_ao_mesmo_tempo_pela_rota",
            "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_ocorrencia_acima_do_saldo",
            "tests/tecnicos/test_ocorrencias.py::test_cenario_49_a_soma_nao_passa_da_quantidade_paga",
            "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenario_49_a_soma_das_ocorrencias_nao_passa_da_quantidade_paga",
        ],
    },
    50: {
        "O comprador não consegue registrar falta nem pedir substituição alterando o pedido": [
            "tests/tecnicos/test_retirada_comprador.py::test_as_rotas_do_comprador_nao_criam_ocorrencia",
            "tests/tecnicos/test_retirada_comprador.py::test_o_comprador_nao_alcanca_escrita_da_e14",
        ],
    },
    51: {
        "Pagamento comunicado pelo provedor depois da apuração ou do cancelamento é registrado e tratado financeiramente com auditoria, sem...": [
            "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta",
            "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta",
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_pagamento_aprovado_junto_do_cancelamento_gera_devolucao_e_alerta",
        ],
    },
    52: {
        "Registrar uma ocorrência de entrega não cancela a rodada, e cancelar a rodada não registra ocorrências": [
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_52_cancelamento_com_ocorrencia_anterior",
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_a_rodada_liberada_nao_e_cancelada_pela_tela",
            "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenarios_48_e_52_a_ocorrencia_nao_muda_pedido_nem_rodada",
        ],
    },
    53: {
        "Caixa invalidada por inadimplência de B: as unidades que A pagou nessa caixa recebem estorno proporcional e voltam ao interesse com a...": [
            "tests/tecnicos/test_apuracao_viavel.py::test_estorno_proporcional_das_unidades_em_caixa_invalidada",
            "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila",
            "tests/tecnicos/test_apuracao_viavel.py::test_a_restauracao_nao_espera_a_autorizacao_da_devolucao",
        ],
        "Os itens válidos de A no ciclo não mudam": [
            "tests/tecnicos/test_apuracao_viavel.py::test_so_a_parte_da_caixa_invalidada_e_estornada_e_restaurada",
            "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila",
        ],
    },
    54: {
        "O inadimplente B perde todos os itens daquele fornecedor no carrinho, inclusive reservas e posições na fila": [
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor",
        ],
        "Itens de B de outros fornecedores não são afetados": [
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai",
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_parcelas_de_outro_fornecedor_nao_mudam",
        ],
    },
    55: {
        "A restauração processada duas vezes, ou em paralelo com novas adições, não duplica parcela, reserva ou posição": [
            "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre",
        ],
        "Uma parcela adicionada depois da adição original da parcela restaurada fica atrás dela": [
            "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre",
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
        ],
    },
    56: {
        "Rodada que volta para interesse por insuficiência de pagamentos mantém o estoque cadastrado": [
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
        ],
        "Reservas de quem pagou continuam com a ordem original, e as dos inadimplentes são liberadas e ficam disponíveis": [
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
        ],
        "Estornos pendentes não impedem novas adições nem novo fechamento": [
            "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente",
        ],
    },
    57: {
        "Depois do retorno ao interesse, o total reservado de cada produto nunca passa do estoque, e nenhuma reserva aparece duplicada": [
            "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada",
        ],
    },
    58: {
        "E-mail de conta removida é recusado no login por senha, por link e pelo Google, e um novo convite para esse e-mail não permite cadastro": [
            "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite",
            "tests/tecnicos/test_contas_login_senha.py::test_login_de_email_banido_e_recusado_com_a_mensagem_generica",
            "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
            "tests/tecnicos/test_perfil_concorrencia.py::test_remocao_depois_da_leitura_recusa_o_perfil_e_nao_grava_avatar",
        ],
        "O histórico, inclusive financeiro, continua consultável pelo administrador": [
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_preserva_conta_historico_e_convite",
        ],
    },
    59: {
        "O banimento vale para o mesmo endereço escrito com maiúsculas diferentes, mas não para aliases (por exemplo, com `+` ou pontos)": [
            "tests/tecnicos/test_contas_login_senha.py::test_login_de_alias_nao_e_afetado_pelo_banimento_do_endereco_base",
        ],
        "IP, dispositivo e telefone não são bloqueados": [
            "tests/aceitacao/test_cenario_59_banimento_so_do_endereco.py::test_cenario_59_ip_dispositivo_e_telefone_nao_sao_bloqueados",
        ],
    },
    60: {
        "Suspensão continua reversível e não bane o e-mail": [
            "tests/tecnicos/test_moderacao_servicos.py::test_suspender_pela_tela_nao_encerra_a_sessao_nem_bane",
            "tests/tecnicos/test_moderacao_servicos.py::test_reativar_volta_a_ativa_sem_restaurar_nada",
        ],
    },
    61: {
        "Pessoa com conta de comprador e conta de fornecedor: cada login vê só as permissões e os dados da sua conta": [
            "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
            "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa",
            "tests/tecnicos/test_convites_cadastro.py::test_comprador_e_fornecedor_com_emails_diferentes_sao_contas_independentes",
            "tests/aceitacao/test_cenario_61_contas_independentes.py::test_cada_sessao_ve_so_a_propria_conta",
            "tests/aceitacao/test_cenario_61_contas_independentes.py::test_conta_de_fornecedor_nao_compra_e_comprador_nao_acessa_a_area_do_fornecedor",
        ],
        "A conta de fornecedor é recusada ao tentar comprar, inclusive pela API": [
            "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
        ],
    },
    62: {
        "Conta de fornecedor só é criada por convite de fornecedor, e conta de comprador não é convertida em conta de fornecedor nem ganha esse...": [
            "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_comprador",
            "tests/aceitacao/test_cenario_62_papel_imutavel.py::test_banco_recusa_trocar_o_papel_mesmo_com_fornecedor_preenchido",
        ],
    },
    63: {
        "Produto por peso a R$ 12,00/kg com incremento de 0,5 kg: 1,5 kg é aceito por R$ 18,00, e 1,2 kg é recusado pelo servidor, inclusive pela API": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_interesses_servicos.py::test_entradas_invalidas_nao_gravam",
        ],
    },
    64: {
        "Produto por peso a R$ 12,99/kg com incremento de 0,05 kg: 0,35 kg resulta em R$ 4,5465, arredondado uma única vez para R$ 4,55 (seção 9)": [
            "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_e_arredondado_uma_vez_so",
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_12_99_vezes_0_35",
        ],
    },
    65: {
        "Quantidade e preço de produto por peso ficam congelados na abertura do pagamento, sem ajuste posterior por pesagem": [
            "tests/tecnicos/test_pedidos_abertura.py::test_produto_por_peso_guarda_o_subtotal_arredondado",
        ],
    },
    66: {
        "Cadastro de produto por peso com múltiplo de compra que não seja múltiplo do incremento é recusado": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
            "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_recusa",
        ],
    },
    67: {
        "O fornecedor vê seus produtos, quantidades, preços unitários, valores totais dos produtos, andamento, pedido formal e previsão de entrega": [
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_portal_nao_expoe_dado_da_e14",
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_do_resultado_aprovado_ao_pedido_aceito",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_ajuste_da_previsao_pela_tela_e_reenvio_com_o_conteudo_original",
        ],
        "Consulta ou exportação de pagamentos individuais, dados de compradores, taxa de serviço, reserva ou dados de outro fornecedor é recusada...": [
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
            "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal",
            "tests/tecnicos/test_portal_do_fornecedor.py::test_rodada_de_outro_fornecedor_ou_inexistente_da_o_mesmo_404",
        ],
    },
    68: {
        "Envio do pedido formal falha na primeira tentativa e funciona na segunda: duas tentativas registradas, um envio, sem aviso ao administrador": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_do_resultado_aprovado_ao_pedido_aceito",
            "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha",
        ],
    },
    69: {
        "Três tentativas falham: não há quarta tentativa automática, o administrador é notificado e o botão **Reenviar pedido** fica disponível": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
            "tests/tecnicos/test_pedido_formal_telas.py::test_depois_das_tres_falhas_o_formulario_aparece",
            "tests/tecnicos/test_pedido_formal_envio.py::test_exatamente_tres_tentativas_automaticas",
        ],
        "O reenvio usa o mesmo pedido formal, com os mesmos produtos, quantidades e valores": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
        ],
    },
    70: {
        "Duplo clique em **Reenviar pedido** gera um único envio": [
            "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_gera_um_so_envio",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_post_durante_a_tentativa_automatica_e_recusado_sem_esperar",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_um_token_novo_faz_uma_tentativa_nova",
        ],
        "Um novo clique feito depois gera uma nova tentativa registrada, e nenhum dos dois cria um pedido novo": [
            "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_um_token_novo_faz_uma_tentativa_nova",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_gera_um_so_envio",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
        ],
    },
    71: {
        "Na fase de interesse, o administrador altera mínimo, múltiplo e estoque": [
            "tests/tecnicos/test_rodadas_minimo.py::test_altera_o_minimo_em_interesse_e_audita",
            "tests/tecnicos/test_rodadas_estoque.py::test_sem_limite_nao_pode_ir_abaixo_do_reservado",
            "tests/tecnicos/test_rodadas_estoque.py::test_reducao_ate_o_reservado_e_aceita",
            "tests/tecnicos/test_rodadas_estoque.py::test_reducao_abaixo_do_reservado_e_recusada",
        ],
        "Uma redução de estoque abaixo da quantidade reservada é recusada": [
            "tests/tecnicos/test_rodadas_estoque.py::test_reducao_abaixo_do_reservado_e_recusada",
            "tests/tecnicos/test_rodadas_estoque.py::test_sem_limite_nao_pode_ir_abaixo_do_reservado",
            "tests/tecnicos/test_rodadas_estoque.py::test_reducao_ate_o_reservado_e_aceita",
        ],
    },
    72: {
        "Do início do fechamento em diante, alterar mínimo, múltiplo ou estoque é recusado, inclusive para o administrador e pela API": [
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
            "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pelo_servico",
            "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pela_rota",
            "tests/tecnicos/test_rodadas_minimo.py::test_minimo_congelado_pelo_servico",
        ],
        "Alterar preço continua permitido no fechamento e atinge os interesses (seção 5.1)": [
            "tests/tecnicos/test_catalogo_condicoes.py::test_preco_muda_em_qualquer_etapa",
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
            "tests/tecnicos/test_interesses_preco.py::test_preco_alterado_no_fechamento_atinge_o_carrinho",
        ],
    },
    73: {
        "Quando a rodada volta para interesse, as condições voltam a ser editáveis, e os registros do ciclo anterior continuam com os valores...": [
            "tests/tecnicos/test_rodadas_ciclos.py::test_cenario_73_ciclos_anteriores_nao_mudam",
            "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_depois_do_retorno_as_condicoes_voltam_a_ser_editaveis",
            "tests/tecnicos/test_rodadas_ciclos.py::test_condicoes_voltam_a_ser_editaveis_na_volta_para_interesse",
        ],
    },
    74: {
        "Caixa invalidada por inadimplência em rodada que segue viável: as unidades pagas por A nessa caixa vão para a fila de interesses...": [
            "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila",
            "tests/tecnicos/test_apuracao_viavel.py::test_a_fila_nao_reserva_na_rodada_apurada",
        ],
        "O pedido congelado e os itens válidos de A não mudam": [
            "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila",
            "tests/tecnicos/test_apuracao_viavel.py::test_a_fila_nao_reserva_na_rodada_apurada",
        ],
    },
    75: {
        "Na próxima rodada em interesse, com estoque de 10 unidades e pendentes A (6 unidades, posição mais antiga) e C (8 unidades): A recebe 6...": [
            "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
        ],
        "O total reservado é 10": [
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_do_produto_atende_a_fila_pela_sequencia_original",
            "tests/tecnicos/test_interesses_parcela_modelo.py::test_atualizacoes_validas_do_cenario_75",
            "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
        ],
    },
    76: {
        "Na mesma rodada, D adiciona 3 unidades depois da abertura, sem estoque livre: a adição é recusada ou fica limitada, conforme a seção 5": [
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_adicao_sem_estoque_e_recusada_e_o_aumento_atende_c_antes_de_d",
        ],
        "Se depois for liberado ou aumentado estoque, as 4 unidades pendentes de C são atendidas antes de qualquer nova reserva de D": [
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_adicao_sem_estoque_e_recusada_e_o_aumento_atende_c_antes_de_d",
        ],
    },
    77: {
        "Unidades pendentes sem reserva não contam para o mínimo e não entram em pedido quando a rodada abre pagamento": [
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
            "tests/tecnicos/test_pedido_formal.py::test_as_quantidades_pendentes_nao_entram",
        ],
        "Continuam na fila para a rodada seguinte": [
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
        ],
    },
    78: {
        "Apuração reexecutada, ou tentativa de reserva da fila executada duas vezes ou em paralelo com novas adições, não duplica parcela...": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem",
        ],
        "O total reservado nunca passa do estoque, e a ordem segue a posição original": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro",
        ],
    },
    79: {
        "O inadimplente B não tem nenhuma unidade daquele fornecedor na fila de pendentes": [
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor",
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai",
        ],
    },
    80: {
        "Convite ou cadastro para um e-mail já usado por outra conta, de qualquer papel, é recusado, inclusive quando escrito com maiúsculas ou...": [
            "tests/tecnicos/test_convites_emissao.py::test_emissao_recusa_email_ja_em_uso_por_qualquer_conta",
            "tests/tecnicos/test_contas_modelo.py::test_conta_recusa_email_em_uso_com_variacao_de_caixa_e_espacos",
        ],
    },
    81: {
        "A mesma pessoa tem conta de comprador com `ana@exemplo.com` e conta de fornecedor com `ana.fornecedor@exemplo.com`: as duas funcionam de...": [
            "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa",
            "tests/tecnicos/test_convites_cadastro.py::test_comprador_e_fornecedor_com_emails_diferentes_sao_contas_independentes",
        ],
        "Banir `ana@exemplo.com` não bloqueia `ana.fornecedor@exemplo.com`": [
            "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa",
            "tests/tecnicos/test_convites_cadastro.py::test_comprador_e_fornecedor_com_emails_diferentes_sao_contas_independentes",
        ],
    },
    82: {
        "Login com Google cujo e-mail normalizado pertence a uma conta acessa somente essa conta e nunca cria uma segunda": [
            "tests/tecnicos/test_contas_google_login.py::test_segundo_login_com_o_mesmo_uid_entra_na_mesma_conta",
            "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social",
        ],
        "Google com e-mail sem conta nem convite válido não cria conta": [
            "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada",
            "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social",
        ],
    },
    83: {
        "Banimento de um e-mail com duas sessões abertas: as duas são invalidadas e a próxima requisição de cada uma é recusada": [
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes",
            "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou",
        ],
        "Novo login por qualquer método é recusado": [
            "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite",
            "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
            "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link",
        ],
        "Históricos são preservados": [
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_preserva_conta_historico_e_convite",
        ],
    },
    84: {
        "`usuario@gmail.com` e `usuario+teste@gmail.com` podem pertencer a contas distintas": [
            "tests/tecnicos/test_contas_emails.py::test_normalizar_email_nao_altera_aliases",
            "tests/tecnicos/test_contas_emails.py::test_normalizar_email_propriedade_alias_continua_distinto",
        ],
        "Banir um não afeta o outro": [
            "tests/tecnicos/test_moderacao_remocao.py::test_remocao_afeta_so_o_endereco_exato",
        ],
    },
    85: {
        "Produto em litros com incremento de 0,5 L: 1,5 L é aceito e 1,2 L é recusado": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_interesses_servicos.py::test_entradas_invalidas_nao_gravam",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_aceitas",
        ],
        "Produto em unidades com incremento 1: 2 é aceito e 2,5 é recusado": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_interesses_servicos.py::test_entradas_invalidas_nao_gravam",
            "tests/tecnicos/test_interesses_carrinho.py::test_quantidade_recusada_volta_no_formulario_do_produto",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
        ],
        "Produto em kg com incremento de 0,25 kg: 0,75 kg é aceito": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_aceitas",
            "tests/tecnicos/test_interesses_servicos.py::test_entradas_invalidas_nao_gravam",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
        ],
        "Todas as validações ocorrem no servidor, inclusive pela API": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_aceitas",
        ],
    },
    86: {
        "Incremento igual a zero ou negativo é recusado no cadastro do produto": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela",
            "tests/tecnicos/test_catalogo_quantidades.py::test_criar_produto_recusa_incremento_float_ou_int",
        ],
    },
    87: {
        "Múltiplo de 1 kg com incremento de 0,25 kg é aceito, e múltiplo de 1 kg com incremento de 0,3 kg é recusado": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
            "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_recusa",
        ],
        "Na fase de interesse, uma alteração que torne o múltiplo incompatível (por exemplo, 0,9 kg com incremento de 0,25 kg) é recusada": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
            "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_invalido_em_interesse",
            "tests/tecnicos/test_catalogo_condicoes.py::test_alterar_e_remover_o_multiplo_em_interesse",
            "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_recusa",
        ],
        "A partir do fechamento, qualquer alteração de múltiplo é recusada (seção 4.4)": [
            "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico",
        ],
    },
    88: {
        "R$ 7,99/kg × 0,25 kg = R$ 1,9975, e o subtotal cobrado é R$ 2,00": [
            "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_7_99_vezes_0_25",
        ],
    },
    89: {
        "Meio centavo: R$ 2,50/kg × 0,25 kg = R$ 0,625, arredondado para R$ 0,63": [
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_2_50_vezes_0_25",
            "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
            "tests/tecnicos/test_interesses_progresso.py::test_arredondamento_por_comprador",
            "tests/tecnicos/test_pedidos_calculo.py::test_produtos_soma_os_subtotais_ja_arredondados",
        ],
        "Dois itens de R$ 0,625 cada somam `P` = R$ 1,26 (soma dos subtotais arredondados), não R$ 1,25": [
            "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
            "tests/tecnicos/test_pedidos_calculo.py::test_produtos_soma_os_subtotais_ja_arredondados",
            "tests/tecnicos/test_interesses_progresso.py::test_arredondamento_por_comprador",
        ],
    },
    90: {
        "Depois de cobrar R$ 2,00 por 0,25 kg a R$ 7,99/kg, o preço do produto muda para R$ 8,99/kg": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
        ],
        "Uma ocorrência da quantidade inteira desse item reembolsa R$ 2,00 de produtos, mais serviço e frete proporcionais sobre os valores...": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
        ],
    },
    91: {
        "A devolução integral de um cancelamento com reembolso soma exatamente os valores cobrados registrados (produtos, serviço e frete)...": [
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_depois_da_aprovacao_do_resultado",
        ],
    },
    92: {
        "Depois de um envio bem-sucedido do pedido formal, o botão **Reenviar pedido** está disponível": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico",
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso",
        ],
        "O acionamento gera uma única tentativa, com o mesmo pedido formal e o mesmo conteúdo, sem tentativas automáticas adicionais": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico",
        ],
    },
    93: {
        "Reenvio manual que falha: a falha é registrada, nenhuma tentativa automática é iniciada e o botão continua disponível": [
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_que_falha_e_registrado_e_o_botao_continua",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenvio_que_falha_continua_com_o_botao",
        ],
    },
    94: {
        "Enquanto o ciclo automático não termina (depois da primeira falha e antes da terceira), o reenvio manual é recusado": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado",
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenvio_durante_o_ciclo_e_recusado_com_409",
        ],
    },
    95: {
        "Dois acionamentos concorrentes da mesma solicitação de reenvio geram um único envio": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_post_durante_a_tentativa_automatica_e_recusado_sem_esperar",
        ],
        "Dois acionamentos distintos geram duas tentativas registradas": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
        ],
        "Em nenhum caso há segundo pedido formal ou mudança no conteúdo original": [
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_em_paralelo_envia_uma_vez",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_post_durante_a_tentativa_automatica_e_recusado_sem_esperar",
        ],
    },
    96: {
        "Comprador A tem 6 unidades reservadas e 4 pendentes de um produto": [
            "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero",
        ],
        'O carrinho e o histórico mostram separadamente "reservado: 6" e "pendente: 4", inclusive quando o estoque do produto está zerado': [
            "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero",
        ],
    },
    97: {
        "A remove 2 das 4 unidades pendentes: a pendência cai para 2, e as reservas de A e de outros compradores, as posições FIFO de outras...": [
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
            "tests/tecnicos/test_interesses_carrinho.py::test_remover_pendentes_pela_rota",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno",
        ],
        "Ao remover as 2 restantes, a pendência zera e a parcela sai da fila": [
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
            "tests/tecnicos/test_interesses_carrinho.py::test_remover_pendentes_pela_rota",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno",
        ],
    },
    98: {
        "Remoção de quantidade pendente maior que a existente, ou fora do incremento do produto, é recusada sem alteração": [
            "tests/tecnicos/test_interesses_carrinho.py::test_remocao_de_pendentes_recusada_e_campos_extras_ignorados",
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remocoes_invalidas_sao_recusadas_sem_escrita",
        ],
    },
    99: {
        "Tentativa de usar a remoção de pendentes sobre item de pedido congelado (por exemplo, enviando o identificador do item do pedido) é...": [
            "tests/tecnicos/test_interesses_carrinho.py::test_remocao_de_pendentes_recusada_e_campos_extras_ignorados",
            "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido",
        ],
        "Pedido e registros financeiros não mudam": [
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido",
            "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao",
        ],
    },
    100: {
        "Remoção de pendentes em paralelo com a alocação da fila: ao final, reservado + pendente nunca passa da quantidade original da parcela...": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remocao_de_pendentes_em_paralelo_com_a_inclusao",
            "tests/tecnicos/test_interesses_concorrencia.py::test_atendimento_da_fila_e_suspensao_se_serializam",
        ],
    },
    101: {
        "D remove 3 unidades reservadas e há pendente de C com 4 unidades: C recebe as 3 antes de qualquer nova reserva": [
            "tests/tecnicos/test_interesses_fila.py::test_liberacao_vai_para_a_fila_na_mesma_transacao",
            "tests/tecnicos/test_interesses_concorrencia.py::test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_reducao_em_paralelo_com_adicao_atende_c_antes_de_e",
        ],
        "Um interesse novo de E feito ao mesmo tempo recebe só o que sobrar": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_reducao_em_paralelo_com_adicao_atende_c_antes_de_e",
        ],
    },
    102: {
        "Pendentes do fornecedor X nunca são alocados em rodada do fornecedor Y": [
            "tests/tecnicos/test_interesses_fila.py::test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_outro_fornecedor_nao_recebe_as_pendentes_de_f",
        ],
    },
    103: {
        "Rodada que volta para interesse por insuficiência de pagamentos: as reservas dos adimplentes ficam na própria rodada e não passam pela...": [
            "tests/tecnicos/test_apuracao_retorno.py::test_unidades_de_caixa_invalidada_ficam_reservadas_sem_passar_pela_fila",
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
        ],
    },
    104: {
        "Produto de R$ 10,00, mínimo de R$ 100,00, A com 8 unidades reservadas e C com 5 pendentes sem reserva: o progresso elegível é R$ 80,00...": [
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_minimo_nao_conta_pendentes",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_pendentes_de_c_ficam_fora_do_progresso_e_do_fechamento",
        ],
        "Se a rodada chegar ao pagamento, as pendentes de C não entram em pedido nem cobrança e continuam na fila": [
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
        ],
    },
    105: {
        "Na fase de interesse, produto com incremento de 0,5 kg, parcelas reservadas de 1,0 kg e 1,5 kg, pendente de 2,0 kg e múltiplo de 3 kg: a...": [
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_compativel_e_aceito",
        ],
    },
    106: {
        "No mesmo produto, a alteração para 1 kg é recusada (1,5 kg reservado deixa de ser múltiplo), e a alteração para 2 kg é recusada (o...": [
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_o_multiplo_e_recusado",
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado",
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_para_2_no_cenario_106_e_recusado",
        ],
        "Em ambos os casos, nada é alterado": [
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_para_2_no_cenario_106_e_recusado",
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado",
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_o_multiplo_e_recusado",
        ],
    },
    107: {
        "A partir do início do fechamento, qualquer alteração de incremento é recusada, inclusive para o administrador e pela API": [
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_congelado",
        ],
        "A alteração de preço continua permitida (seção 5.1)": [
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
            "tests/tecnicos/test_catalogo_incremento.py::test_preco_continua_editavel_no_fechamento",
        ],
    },
    108: {
        "Alteração de incremento em paralelo com uma adição de interesse no mesmo produto: ou a adição é validada contra o novo incremento, ou a...": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam",
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_suspensao_ou_remocao_se_serializam",
        ],
        "Nunca fica parcela fora do incremento vigente": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam",
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_suspensao_ou_remocao_se_serializam",
        ],
    },
    109: {
        "Ovos (unidade, incremento 1): 12 é aceito e 12,5 é recusado": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_interesses_servicos.py::test_entradas_invalidas_nao_gravam",
            "tests/tecnicos/test_interesses_carrinho.py::test_quantidade_recusada_volta_no_formulario_do_produto",
        ],
        "Maçãs (unidade, incremento 2): 4 é aceito e 3 é recusado": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_interesses_carrinho.py::test_quantidade_recusada_volta_no_formulario_do_produto",
        ],
        "Banana (kg, 0,25): 1,25 é aceito": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_aceitas",
        ],
        "Leite (litro, 0,5): 2,5 é aceito": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_aceitas",
        ],
        "Caixa de produtos (caixa, 1): 3 é aceito e 1,5 é recusado": [
            "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
            "tests/tecnicos/test_interesses_servicos.py::test_entradas_invalidas_nao_gravam",
            "tests/tecnicos/test_interesses_carrinho.py::test_quantidade_recusada_volta_no_formulario_do_produto",
        ],
    },
    110: {
        "Incrementos 0, -1 e 0,0001 são recusados": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_invalidos_no_servico",
            "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela",
            "tests/tecnicos/test_catalogo_quantidades.py::test_criar_produto_recusa_incremento_float_ou_int",
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos",
        ],
        "Incrementos 0,001 e 2 são aceitos": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos",
        ],
    },
    111: {
        "Maçãs com incremento 2 e múltiplo 12 são aceitas": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
            "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_aceita_e_aceita_vazio",
        ],
        "Com múltiplo 5, a configuração é recusada": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_recusa",
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
        ],
    },
    112: {
        "Item de 1,000 kg a R$ 7,99/kg, com subtotal registrado de R$ 7,99": [
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_112_parcial_usa_o_valor_registrado",
        ],
        "Ocorrência de 0,25 kg: o reembolso de produtos é R$ 7,99 × 0,25 = R$ 1,9975, arredondado para R$ 2,00": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
        ],
        "Uma mudança posterior do preço do produto para R$ 9,99/kg não altera o valor": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
        ],
    },
    113: {
        "No mesmo item, três ocorrências de 0,25 kg reembolsam R$ 2,00 cada": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_113_quatro_parciais_somam_o_pago",
        ],
        "A quarta, que completa a quantidade, reembolsa R$ 1,99 (R$ 7,99 − R$ 6,00)": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
        ],
        "A soma é exatamente R$ 7,99": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_113_quatro_parciais_somam_o_pago",
        ],
    },
    114: {
        "Depois de uma ocorrência parcial de R$ 2,00 no item de R$ 7,99, o cancelamento da rodada com reembolso devolve, para esse item...": [
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago",
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_integral_depois_de_parcial_completa_exatamente",
            "tests/tecnicos/test_ocorrencias.py::test_o_cancelamento_devolve_so_o_saldo_restante",
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_114_integral_depois_do_parcial_completa_exatamente",
        ],
    },
    115: {
        "Item de 0,6 kg a R$ 0,15/kg, subtotal de R$ 0,09 e incremento de 0,1 kg": [
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_115_centavos_nao_passam_do_pago",
        ],
        "Cada ocorrência de 0,1 kg calcula R$ 0,015, arredondado para R$ 0,02": [
            "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago",
        ],
        "A quinta é limitada a R$ 0,01, o saldo restante, e a sexta reembolsa R$ 0,00": [
            "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago",
        ],
        "A soma nunca passa de R$ 0,09, e uma ocorrência acima da quantidade paga é recusada": [
            "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago",
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_115_centavos_nao_passam_do_pago",
        ],
    },
    116: {
        "Pedido com R$ 100,00 de produtos, R$ 5,00 de serviço e R$ 20,00 de frete: um reembolso parcial de R$ 2,00 de produtos devolve também R$...": [
            "tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py::test_cenario_116_numeros_do_cenario",
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_116_servico_e_frete_proporcionais",
        ],
    },
    117: {
        "Cada reembolso parcial é registrado separadamente, com item, quantidade e valores": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_117_cada_devolucao_e_registrada_separadamente",
        ],
        "O pedido congelado continua com a composição original": [
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_117_cada_devolucao_e_registrada_separadamente",
        ],
    },
    118: {
        "Uma tentativa automática em execução e um acionamento manual simultâneo: o manual é recusado e nenhuma tentativa a mais é feita": [
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_post_durante_a_tentativa_automatica_e_recusado_sem_esperar",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
        ],
    },
    119: {
        "Depois de concluído o ciclo automático, dois acionamentos manuais com solicitações distintas feitos ao mesmo tempo são executados um...": [
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
        ],
    },
}

TECNICOS: dict[str, dict[str, list[str]]] = {
    "T-1": {
        "Tentativa criada em `T0 + 24h − 1 ms` é aceita": [
            "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento",
            "tests/tecnicos/test_pedidos_prazos.py::test_com_o_bloqueio_parado_o_servidor_recusa_a_tentativa",
        ],
        "Em `T0 + 24h` e `T0 + 24h + 1 ms` é recusada, com a tarefa de bloqueio parada": [
            "tests/tecnicos/test_pedidos_prazos.py::test_com_o_bloqueio_parado_o_servidor_recusa_a_tentativa",
        ],
    },
    "T-2": {
        "`date_approved = T0 + 48h` é aceito. `T0 + 48h + 1 ms` gera obrigação de devolução": [
            "tests/tecnicos/test_pedidos_quitacao.py::test_fronteira_de_48_horas_da_margem",
        ],
    },
    "T-3": {
        "Aprovação em `T0 + 47h59` com webhook chegando em `T0 + 50h` quita o pedido, se a apuração ainda não ocorreu": [
            "tests/tecnicos/test_pedidos_quitacao.py::test_aviso_atrasado_nao_muda_o_horario_de_aprovacao",
        ],
    },
    "T-4": {
        "Apuração recusada em `T0 + 48h − 1 ms`, mesmo com 100% pago": [
            "tests/tecnicos/test_apuracao_telas.py::test_antes_de_48_horas_a_pagina_so_informa_o_horario",
            "tests/tecnicos/test_apuracao_inicio.py::test_antes_de_48_horas_e_recusada_sem_consulta_nem_escrita",
            "tests/tecnicos/test_pedidos_prazos.py::test_a_apuracao_so_pode_comecar_em_48_horas",
            "tests/tecnicos/test_apuracao_inicio.py::test_em_48_horas_exatas_a_apuracao_e_aceita",
        ],
        "Em `T0 + 48h` exige autorização": [
            "tests/tecnicos/test_pedidos_prazos.py::test_a_apuracao_so_pode_comecar_em_48_horas",
            "tests/tecnicos/test_apuracao_telas.py::test_antes_de_48_horas_a_pagina_so_informa_o_horario",
            "tests/tecnicos/test_apuracao_inicio.py::test_em_48_horas_exatas_a_apuracao_e_aceita",
        ],
    },
    "T-5": {
        "Nenhuma rota permite alterar `T0` ou o prazo de pagamento, nem com perfil de admin": [
            "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos",
            "tests/tecnicos/test_pedidos_prazos.py::test_o_t0_nao_muda_nem_por_sql",
        ],
    },
    "T-6": {
        "Webhook repetido 5 vezes, em paralelo, reconhece o pagamento uma única vez": [
            "tests/tecnicos/test_pagamentos_concorrencia.py::test_mesmo_aviso_cinco_vezes_em_paralelo_reconhece_o_pagamento_uma_vez",
            "tests/tecnicos/test_pagamentos_concorrencia.py::test_cinco_avisos_diferentes_do_mesmo_pagamento",
        ],
    },
    "T-7": {
        "Webhook, bloqueio de `T0 + 24h` e apuração concorrendo sobre o mesmo pedido produzem o mesmo resultado em qualquer ordem": [
            "tests/tecnicos/test_pedidos_concorrencia.py::test_bloqueio_e_aviso_de_outra_mudanca_ao_mesmo_tempo",
            "tests/tecnicos/test_apuracao_inicio.py::test_aviso_espera_a_apuracao_que_ja_cancelou_y",
            "tests/tecnicos/test_apuracao_inicio.py::test_aviso_antes_da_apuracao_quita_y",
            "tests/tecnicos/test_apuracao_inicio.py::test_apuracao_espera_o_aviso_que_trava_a_situacao_de_y",
        ],
    },
    "T-8": {
        "Devolução com falha temporária repetida reaproveita a chave de idempotência e não devolve duas vezes": [
            "tests/tecnicos/test_devolucoes_execucao.py::test_falha_depois_de_executar_repete_a_mesma_chave",
            "tests/tecnicos/test_devolucoes_execucao.py::test_tres_falhas_abrem_o_alerta_e_a_quarta_conclui",
            "tests/tecnicos/test_simulador_estornos.py::test_falha_depois_de_executar_deixa_o_estorno_gravado",
        ],
    },
    "T-9": {
        "Confirmação de devolução excepcional recusada enquanto houver devolução em processamento no provedor": [
            "tests/tecnicos/test_devolucoes_excepcional.py::test_estorno_em_processamento_no_provedor_recusa_e_agenda_a_verificacao",
            "tests/tecnicos/test_devolucoes_excepcional.py::test_sem_parcela_e_parcela_concluida_sao_recusadas",
            "tests/tecnicos/test_devolucoes_excepcional.py::test_falha_definitiva_ainda_nao_comprovada_bloqueia",
            "tests/tecnicos/test_devolucoes_excepcional.py::test_depois_da_confirmacao_o_provedor_nao_e_mais_chamado",
        ],
        "Nova tentativa no provedor recusada depois da confirmação": [
            "tests/tecnicos/test_devolucoes_excepcional.py::test_depois_da_confirmacao_o_provedor_nao_e_mais_chamado",
            "tests/tecnicos/test_devolucoes_excepcional.py::test_sem_parcela_e_parcela_concluida_sao_recusadas",
            "tests/tecnicos/test_devolucoes_excepcional.py::test_estorno_em_processamento_no_provedor_recusa_e_agenda_a_verificacao",
            "tests/tecnicos/test_devolucoes_excepcional.py::test_falha_definitiva_ainda_nao_comprovada_bloqueia",
        ],
        "Segunda confirmação da mesma parcela recusada": [
            "tests/tecnicos/test_devolucoes_excepcional.py::test_sem_parcela_e_parcela_concluida_sao_recusadas",
            "tests/tecnicos/test_devolucoes_excepcional.py::test_falha_definitiva_ainda_nao_comprovada_bloqueia",
            "tests/tecnicos/test_devolucoes_excepcional.py::test_estorno_em_processamento_no_provedor_recusa_e_agenda_a_verificacao",
            "tests/tecnicos/test_devolucoes_excepcional.py::test_nao_vale_duas_vezes",
        ],
    },
    "T-10": {
        "Utilização da reserva acima do saldo livre recusada": [
            "tests/tecnicos/test_financeiro_reserva.py::test_uso_acima_do_livre_e_recusado_inteiro",
            "tests/tecnicos/test_financeiro_telas.py::test_designar_acima_do_livre_responde_409_com_a_mensagem",
            "tests/tecnicos/test_financeiro_concorrencia.py::test_designacao_e_utilizacao_ao_mesmo_tempo",
            "tests/tecnicos/test_financeiro_reserva.py::test_obrigacoes_sem_cobertura_acima_do_livre_abrem_o_alerta",
        ],
        "Obrigação sem cobertura mantida integral, com alerta de insuficiência": [
            "tests/tecnicos/test_financeiro_reserva.py::test_obrigacoes_sem_cobertura_acima_do_livre_abrem_o_alerta",
            "tests/tecnicos/test_financeiro_reserva.py::test_uso_acima_do_livre_e_recusado_inteiro",
        ],
    },
    "T-11": {
        "Lançamento que use recursos do fornecedor A para tarifa, déficit ou obrigação do fornecedor B recusado": [
            "tests/tecnicos/test_financeiro_concorrencia.py::test_dois_repasses_que_juntos_passam_do_liberado",
        ],
        "Repasse a A limitado ao valor liberado de A": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_repasse_limitado_ao_liberado_e_conciliado",
            "tests/tecnicos/test_financeiro_concorrencia.py::test_dois_repasses_que_juntos_passam_do_liberado",
            "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b",
            "tests/tecnicos/test_repasse.py::test_o_repasse_nao_passa_do_liberado",
        ],
    },
    "T-12": {
        "Aplicação configurada com o simulador em produção encerra na inicialização": [
            "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_sem_provedor_configurado_nao_recebe_o_simulador",
            "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_com_o_simulador_nao_carrega",
            "tests/tecnicos/test_configuracao_pagamentos.py::test_nem_a_web_nem_o_worker_sobem_em_producao_com_o_simulador",
        ],
    },
    "T-13": {
        "Cancelamento com reembolso executado duas vezes em paralelo: um é recusado e nenhuma devolução é duplicada": [
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_dois_cancelamentos_em_paralelo_geram_um_estorno_por_pagamento",
            "tests/tecnicos/test_cancelamento_da_rodada.py::test_cancelar_de_novo_e_recusado",
        ],
    },
    "T-14": {
        "Cancelamento com reembolso com devolução parcial pendente: a nova obrigação cobre só o saldo restante, e o total nunca passa do valor pago": [
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago",
            "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido",
        ],
    },
    "T-15": {
        "Cancelamento sem reembolso com obrigação existente: nenhuma obrigação nova, e a existente continua pendente e não é baixada": [
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente",
            "tests/tecnicos/test_cancelamento_com_pedidos.py::test_pagamento_em_duplicidade_continua_como_estava",
        ],
    },
    "T-16": {
        "Rota de cancelamento recusa lista de compradores e aceita requisição sem motivo": [
            "tests/tecnicos/test_cancelamento_da_rodada.py::test_a_assinatura_nao_aceita_lista_de_compradores_nem_motivo",
            "tests/tecnicos/test_cancelamento_telas.py::test_a_rota_recusa_campos_fora_da_indicacao",
        ],
        "Comprador e fornecedor recebem recusa": [
            "tests/tecnicos/test_cancelamento_telas.py::test_comprador_e_fornecedor_nao_cancelam",
            "tests/tecnicos/test_cancelamento_telas.py::test_a_rota_recusa_campos_fora_da_indicacao",
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http",
        ],
    },
    "T-17": {
        "`UPDATE` ou `DELETE` direto no banco sobre item de pedido congelado é recusado pela trigger": [
            "tests/tecnicos/test_pedidos_abertura.py::test_composicao_do_pedido_nao_muda_nem_some",
        ],
        "Nenhuma rota permite edição": [
            "tests/tecnicos/test_pedidos_abertura_tela.py::test_nenhuma_rota_altera_pedido_item_t0_ou_frete",
        ],
    },
    "T-18": {
        "Ocorrências concorrentes sobre o mesmo item não ultrapassam a quantidade paga": [
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_t18_duas_ocorrencias_ao_mesmo_tempo_pela_rota",
            "tests/tecnicos/test_ocorrencias.py::test_o_mesmo_acionamento_em_paralelo",
            "tests/tecnicos/test_ocorrencias.py::test_duas_ocorrencias_no_mesmo_item_t18",
        ],
        "Cada ocorrência gera um único reembolso, com o valor de §9.2": [
            "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_t18_duas_ocorrencias_ao_mesmo_tempo_pela_rota",
            "tests/tecnicos/test_ocorrencias.py::test_o_mesmo_acionamento_em_paralelo",
            "tests/tecnicos/test_ocorrencias.py::test_duas_ocorrencias_no_mesmo_item_t18",
        ],
    },
    "T-19": {
        "Pagamento informado pelo provedor depois da apuração ou do cancelamento fica registrado com alerta e não altera o pedido": [
            "tests/tecnicos/test_apuracao_inicio.py::test_aviso_espera_a_apuracao_que_ja_cancelou_y",
            "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta",
            "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta",
            "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_pagamento_aprovado_junto_do_cancelamento_gera_devolucao_e_alerta",
        ],
    },
    "T-20": {
        "Apuração com caixa invalidada executada duas vezes: parcelas restauradas uma única vez, mesmo número de sequência, sem reserva duplicada": [
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
        ],
    },
    "T-21": {
        "Restauração concorrendo com adição de outro comprador ao mesmo produto: ordem FIFO pela sequência original e total reservado ≤ estoque": [
            "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre",
        ],
    },
    "T-22": {
        "Retorno ao interesse com inadimplentes e pagantes: estoque cadastrado inalterado, reservas de inadimplentes liberadas, reservas de...": [
            "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
            "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada",
        ],
    },
    "T-23": {
        "Alteração de mínimo, múltiplo e estoque recusada pelo servidor em fechamento, pagamento, margem e etapas seguintes, inclusive pelo admin": [
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
            "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pelo_servico",
            "tests/tecnicos/test_rodadas_minimo.py::test_minimo_congelado_pelo_servico",
            "tests/tecnicos/test_rodadas_fechamento_concorrencia.py::test_alteracao_de_minimo_depois_do_inicio_e_recusada",
        ],
        "Preço aceito no fechamento": [
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
            "tests/tecnicos/test_rodadas_fechamento_concorrencia.py::test_alteracao_de_minimo_depois_do_inicio_e_recusada",
            "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_preco_muda_nas_quatro_etapas_ativas",
        ],
        "Redução de estoque abaixo do reservado recusada": [
            "tests/tecnicos/test_rodadas_estoque.py::test_reducao_abaixo_do_reservado_e_recusada",
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
            "tests/tecnicos/test_rodadas_fechamento_concorrencia.py::test_alteracao_de_minimo_depois_do_inicio_e_recusada",
        ],
    },
    "T-24": {
        "Login por senha, link e Google com e-mail banido (variando maiúsculas e espaços) recusado": [
            "tests/tecnicos/test_contas_login_senha.py::test_login_de_email_banido_e_recusado_com_a_mensagem_generica",
            "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
        ],
        "Alias com `+` não bloqueado": [
            "tests/tecnicos/test_contas_login_senha.py::test_login_de_alias_nao_e_afetado_pelo_banimento_do_endereco_base",
            "tests/tecnicos/test_contas_link_de_acesso.py::test_banimento_ou_remocao_depois_do_pedido_bloqueia_o_uso",
        ],
        "Sessão aberta encerrada no banimento": [
            "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou",
        ],
    },
    "T-25": {
        "Conta de fornecedor chamando rotas de carrinho e pagamento recebe recusa": [
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_e_recusado_nas_rotas_da_e14",
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_compra",
            "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_portal_nao_expoe_dado_da_e14",
        ],
        "Conta de comprador chamando rotas de fornecedor recebe recusa": [
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_e_recusado_nas_rotas_da_e14",
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_compra",
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_comprador_nao_entra_no_portal",
            "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
        ],
    },
    "T-26": {
        "Quantidade fora do incremento recusada pela API. `0,35 × 12,99` resulta em 455 centavos": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_de_455_centavos",
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_12_99_vezes_0_35",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
        ],
        "Múltiplo que não é múltiplo do incremento recusado no cadastro": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_recusa",
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
        ],
    },
    "T-27": {
        "Fornecedor consultando por identificador direto pagamentos, compradores, taxa de serviço, reserva ou produto de outro fornecedor recebe...": [
            "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
        ],
        "A exportação só contém campos permitidos": [
            "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal",
        ],
    },
    "T-28": {
        "SES simulado falhando três vezes: exatamente três tentativas, alerta ao admin e botão disponível": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
            "tests/tecnicos/test_pedido_formal_telas.py::test_depois_das_tres_falhas_o_formulario_aparece",
            "tests/tecnicos/test_pedido_formal_envio.py::test_exatamente_tres_tentativas_automaticas",
        ],
        "Falha seguida de sucesso: nenhuma tentativa a mais": [
            "tests/tecnicos/test_pedido_formal_telas.py::test_depois_das_tres_falhas_o_formulario_aparece",
            "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
            "tests/tecnicos/test_pedido_formal_envio.py::test_exatamente_tres_tentativas_automaticas",
        ],
    },
    "T-29": {
        "Duas requisições de reenvio com o mesmo token geram um envio": [
            "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_gera_um_so_envio",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_em_pedidos_diferentes_envia_um_so_email",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_um_token_novo_faz_uma_tentativa_nova",
        ],
        "Tokens distintos geram duas tentativas registradas": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
            "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_um_token_novo_faz_uma_tentativa_nova",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_gera_um_so_envio",
        ],
        "O conteúdo enviado é idêntico ao snapshot": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
        ],
    },
    "T-30": {
        "`alocar_pendentes` com estoque menor que o total pendente: reserva por ordem de sequência, a última parcela atendida parcialmente, o...": [
            "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_do_produto_atende_a_fila_pela_sequencia_original",
        ],
    },
    "T-31": {
        "`alocar_pendentes` executada em paralelo com a adição de um interesse novo no mesmo produto: pendentes atendidos primeiro, nenhuma...": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro",
            "tests/tecnicos/test_interesses_concorrencia.py::test_suspensao_confirmada_antes_barra_a_adicao",
        ],
    },
    "T-32": {
        "Apuração reexecutada sobre a mesma caixa invalidada: a chave (parcela, caixa) impede segunda restauração, sem nova parcela nem nova...": [
            "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
        ],
    },
    "T-33": {
        "Parcela pendente sem reserva fora de mínimo, caixas e pedido na abertura do pagamento": [
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor",
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_minimo_nao_conta_pendentes",
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
        ],
        "Continua pendente na rodada seguinte": [
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_minimo_nao_conta_pendentes",
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
        ],
        "Inadimplente sem parcelas pendentes": [
            "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
            "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_minimo_nao_conta_pendentes",
            "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
        ],
    },
    "T-34": {
        "Dois cadastros simultâneos com o mesmo e-mail normalizado (`Ana@x.com` e ` ana@x.com `), um por convite de comprador e outro de...": [
            "tests/tecnicos/test_convites_cadastro_concorrencia.py::test_dois_convites_com_mesmo_email_normalizado_em_paralelo",
        ],
    },
    "T-35": {
        "Login com Google com e-mail igual ao de uma conta, mas com maiúsculas diferentes: entra nessa conta e não cria outra": [
            "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social",
        ],
        "Google com e-mail sem conta e sem convite: nada criado": [
            "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada",
            "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social",
        ],
    },
    "T-36": {
        "Banimento com sessões ativas em dois navegadores: sessões apagadas e a próxima requisição de cada uma é recusada pelo middleware": [
            "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou",
            "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_conta_com_email_banido_mesmo_ativa",
        ],
        "A outra conta da mesma pessoa, com outro e-mail, continua acessível": [
            "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa",
        ],
    },
    "T-37": {
        "`normalizar_email` usado em todos os pontos de comparação (cadastro, convite, login, unicidade, banimento): teste de propriedade com...": [
            "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos",
        ],
        "Aliases com `+` continuam distintos": [
            "tests/tecnicos/test_contas_emails.py::test_normalizar_email_propriedade_alias_continua_distinto",
            "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos",
        ],
    },
    "T-38": {
        "Quantidades em L, kg e unidade validadas contra o incremento do produto": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_aceitas",
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
        ],
        "Incremento zero, negativo ou com mais de 3 casas recusado": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_criar_produto_recusa_incremento_float_ou_int",
            "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_recusa",
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
            "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
        ],
        "Múltiplo incompatível recusado no cadastro e na alteração em interesse": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_validar_multiplo_recusa",
            "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
            "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
        ],
    },
    "T-39": {
        "Tabela de arredondamento: 7,99 × 0,25 = 2,00;": [
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_7_99_vezes_0_25",
            "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_2_50_vezes_0_25",
        ],
        "2,50 × 0,25 = 0,63;": [
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_2_50_vezes_0_25",
            "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
            "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_7_99_vezes_0_25",
        ],
        "12,99 × 0,35 = 4,55. `P` é a soma dos subtotais arredondados": [
            "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
        ],
        "A verificação estática não encontra `float` em código monetário": [
            "tests/tecnicos/test_varredura_float.py::test_modulos_de_dinheiro_nao_usam_float",
            "tests/tecnicos/test_varredura_float.py::test_a_varredura_acusa_float_com_arquivo_e_linha",
        ],
    },
    "T-40": {
        "Reembolso do item inteiro depois de mudar o preço no catálogo usa o subtotal do snapshot": [
            "tests/aceitacao/test_t40_reembolso_do_item_inteiro.py::test_t40_reembolso_do_item_inteiro_depois_de_mudar_o_preco",
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
        ],
        "A soma da devolução integral bate com os valores cobrados registrados": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
            "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenarios_90_e_91_integral_devolve_exatamente_o_cobrado",
        ],
    },
    "T-41": {
        "Reenvio manual: recusado durante o ciclo automático, aceito depois da terceira falha e depois de sucesso, uma tentativa por acionamento...": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico",
        ],
    },
    "T-42": {
        "Consulta do comprador devolve reservado e pendente em campos separados, inclusive com estoque zero": [
            "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero",
        ],
        "Outro comprador não vê essas parcelas": [
            "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado",
        ],
    },
    "T-43": {
        "`remover_pendente` parcial e total: só a quantidade pendente muda, sequências e reservas inalteradas, parcelas mais recentes reduzidas...": [
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno",
        ],
        "Quantidade fora do incremento ou acima do pendente recusada sem escrita": [
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remocoes_invalidas_sao_recusadas_sem_escrita",
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
            "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava",
        ],
    },
    "T-44": {
        '`remover_pendente` com identificador de item de pedido congelado ou de parcela "em pedido" recusada': [
            "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido",
        ],
        "Pedido, trigger e registros financeiros inalterados": [
            "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido",
        ],
    },
    "T-45": {
        "`remover_pendente` em paralelo com `alocar_pendentes` sobre o mesmo produto: em qualquer ordem, reservado + pendente ≤ original, total...": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remocao_de_pendentes_em_paralelo_com_a_inclusao",
            "tests/tecnicos/test_interesses_concorrencia.py::test_atendimento_da_fila_e_suspensao_se_serializam",
        ],
    },
    "T-46": {
        "Liberação de estoque em paralelo com nova reserva: pendentes atendidos primeiro pela sequência": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado",
            "tests/tecnicos/test_interesses_concorrencia.py::test_dez_adicoes_de_dois_com_limite_dez",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_reducao_em_paralelo_com_adicao_atende_c_antes_de_e",
            "tests/tecnicos/test_interesses_fila.py::test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele",
        ],
        "Pendentes do fornecedor X nunca alocados em rodada do fornecedor Y": [
            "tests/tecnicos/test_interesses_fila.py::test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele",
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_outro_fornecedor_nao_recebe_as_pendentes_de_f",
        ],
    },
    "T-47": {
        "Cálculo do mínimo, formação de caixas, abertura de pagamento, pedido formal e cobrança ignoram quantidade pendente": [
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
            "tests/tecnicos/test_pedido_formal.py::test_as_quantidades_pendentes_nao_entram",
        ],
        "A quantidade pendente continua na fila depois da abertura do pagamento": [
            "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
            "tests/tecnicos/test_pedido_formal.py::test_as_quantidades_pendentes_nao_entram",
        ],
    },
    "T-48": {
        "`alterar_incremento`: valor compatível aceito na fase de interesse; incompatível com reservado, pendente ou múltiplo recusado sem...": [
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_o_multiplo_e_recusado",
            "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado",
        ],
    },
    "T-49": {
        "`alterar_incremento` em paralelo com adição de interesse no mesmo produto: operações serializadas pela trava do produto, nenhuma parcela...": [
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam",
            "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_suspensao_ou_remocao_se_serializam",
        ],
    },
    "T-50": {
        "Validação R-8 com a tabela da especificação (1, 2, 0,25, 0,5, 1) e inválidos (0, -1, 0,0001)": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_invalidos_no_servico",
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos",
            "tests/tecnicos/test_interesses_servicos.py::test_entradas_invalidas_nao_gravam",
            "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela",
        ],
        "Quantidades inteiras e fracionárias validadas com `Decimal`": [
            "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos",
        ],
        "Número em ponto flutuante na API recusado": [
            "tests/tecnicos/test_nucleo_valores.py::test_conversao_recusa_float",
            "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_recusa_float_e_int",
        ],
    },
    "T-51": {
        "`reembolso_parcial`: 7,99 × 0,25/1 = 2,00; sequência 2,00 / 2,00 / 2,00 / 1,99; caso de R$ 0,09 com limite ao saldo": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
            "tests/tecnicos/test_devolucoes_reembolso.py::test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo",
        ],
        "Mudança do preço de catálogo não altera nenhum valor": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
        ],
    },
    "T-52": {
        "Reembolso acima da quantidade paga recusado": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_quantidade_invalida_e_recusada",
            "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
            "tests/tecnicos/test_devolucoes_reembolso.py::test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo",
        ],
        "Devolução integral depois de parciais completa exatamente o saldo": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
        ],
        "Acumulado de serviço e frete nunca passa do registrado": [
            "tests/tecnicos/test_devolucoes_reembolso.py::test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo",
            "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
        ],
    },
    "T-53": {
        "Dois `reembolso_parcial` concorrentes sobre o mesmo item: serializados pela trava, soma ≤ subtotal, nenhum registro duplicado": [
            "tests/tecnicos/test_devolucoes_concorrencia.py::test_dois_parciais_do_mesmo_item_nunca_passam_do_pago",
            "tests/tecnicos/test_devolucoes_concorrencia.py::test_tres_parciais_ao_mesmo_tempo_respeitam_o_pago",
        ],
    },
    "T-54": {
        "Reenvio manual recusado com tentativa automática agendada ou em execução": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
            "tests/tecnicos/test_pedido_formal_telas.py::test_reenvio_durante_o_ciclo_e_recusado_com_409",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_antes_da_primeira_tentativa_automatica_o_reenvio_e_recusado",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado",
        ],
        "Aceito depois do sucesso e depois da terceira falha, com uma tentativa por acionamento": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
        ],
    },
    "T-55": {
        "Tentativa automática e acionamento manual concorrentes: o manual é recusado": [
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_post_durante_a_tentativa_automatica_e_recusado_sem_esperar",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
        ],
        "Dois manuais distintos depois do ciclo: executados em sequência, nunca ao mesmo tempo": [
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
            "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
        ],
        "Snapshot inalterado": [
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
            "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
        ],
    },
}
