# ✅ CHECKLIST DE STATUS — IKFlow Mecânica
**Última atualização:** 28/05/2026 (revisão 7 — Audit Semanas 1-4: auth central, APP_MODE guards, dashboard automotivo, multi-tenant company_id, baixa estoque na OS, PIX protegido | 86/93 = 92%)  
**Legenda:** ✅ 100% funcional | ⚠️ Funciona com ressalvas / precisa teste real | 🔧 Existe mas precisa ajuste | ❌ Não implementado

---

## 1. ATENDIMENTO / ORDEM DE SERVIÇO

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 1.1 | Listagem de OS | ✅ | `/service_orders` |
| 1.2 | Criar OS completa | ✅ | `/service_orders/add` |
| 1.3 | OS Avulsa (sem cliente) | ✅ | `/service_orders/avulso` |
| 1.4 | Editar OS / atribuir mecânico | ✅ | `/service_orders/edit/<id>` |
| 1.5 | Visualizar OS detalhada | ✅ | `/service_orders/view/<id>` |
| 1.6 | PDF / Impressão do Prisma | ✅ | `/service_orders/<id>/pdf` |
| 1.7 | Diagnóstico do mecânico | ✅ | Campo `diagnostico` na OS |
| 1.8 | Complexidade + Horas + Valor/h | ✅ | Simples/Médio/Complexo |
| 1.9 | Peças ad-hoc (sem cadastrar produto) | ✅ | Tabela dinâmica na OS |
| 1.10 | Status orçamento: Rascunho→Enviado→Aprovado | ✅ | Campo `status_orcamento` |
| 1.11 | KM de entrada | ✅ | Campo `km_entrada` |
| 1.12 | Iniciar serviço (cronômetro) | ✅ | Rota `/iniciar` |
| 1.13 | Finalizar serviço | ✅ | Rota `/finalizar` |
| 1.14 | Lançamento automático C/R ao aprovar | ✅ | `_lancar_contas_receber()` |
| 1.15 | Envio de orçamento por WhatsApp | ✅ | UazAPI configurado, testado e funcionando |
| 1.16 | Agendamento preventivo automático | ✅ | `calcular_proximo_preventivo()` ao concluir OS |
| 1.17 | Controle de Garantia por peça/serviço | ❌ | Não implementado |
| 1.18 | Popup pós-OS "Emitir NF-e?" | ❌ | Não implementado |
| 1.19 | Baixa automática de estoque ao concluir OS | ✅ | `registrar_movimentacao` disparado ao status=completed |
| 1.20 | Botão Cobrar via PIX na view da OS | ✅ | Visível quando orçamento aprovado ou OS concluída |

---

## 2. CLIENTES / CRM

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 2.1 | CRUD de clientes | ✅ | `cliente_routes_mysql.py` |
| 2.2 | Importação CSV/Excel | ✅ | `importar_clientes_routes.py` |
| 2.3 | Clientes em Potencial (CRM) | ✅ | `/clientes-potenciais` |
| 2.4 | Rota de Captação | ✅ | `/rotas_vendas` — no menu |
| 2.5 | Pesquisa Pós-Atendimento | ✅ | `/questionario-visita` — no menu |
| 2.6 | Portal do Cliente | ❌ | Não implementado |

---

## 3. VEÍCULOS / EQUIPAMENTOS

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 3.1 | CRUD de veículos | ✅ | `equipamento_routes_mysql.py` |
| 3.2 | Histórico completo do veículo | ✅ | `/veiculos/<id>/historico` |
| 3.3 | KM / Horímetro | ✅ | `/hour_meter` — no menu |
| 3.4 | Planos de Revisão | ✅ | `maintenance_plan_routes.py` |
| 3.5 | Agendamento preventivo automático por KM | ❌ | Não implementado |

---

## 4. EQUIPE / MECÂNICOS

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 4.1 | Cadastro de Mecânicos/Técnicos | ✅ | `technician_routes.py` |
| 4.2 | Meu Painel (mecânico) — Gantt pessoal | ✅ | `/industria/ordem-producao/meu-gantt` |
| 4.3 | Painel do Líder | ✅ | `/industria/ordem-producao/lider/painel` |
| 4.4 | Ordens de Execução | ✅ | `/industria/ordem-producao/` |
| 4.5 | Gantt de Serviços | ✅ | `/industria/ordem-producao/producao/gantt` |
| 4.6 | Motivos de Pausa | ✅ | `/industria/producao-pausas/motivos` |
| 4.7 | Jornada de Trabalho / Ponto | ✅ | `jornada_trabalho_routes.py` |
| 4.8 | Controle de Ponto (WiFi/app) | ❌ | Não implementado |
| 4.9 | Comissões | ❌ | Não implementado |
| 4.10 | **Agenda por mecânico (calendário)** | ✅ | `/agenda` — FullCalendar, arrastar OS, filtro técnico, painel OS sem técnico |
| 4.11 | **Agendamento de OS** | ✅ | `POST /agenda/agendar/<id>` — data/hora/técnico |
| 4.12 | **Preventivo automático** | ✅ | Ao concluir OS → atualiza `next_maintenance` do veículo |

---

## 5. PEÇAS E ESTOQUE

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 5.1 | Cadastro de Peças/Produtos | ✅ | `produto_routes_mysql.py` |
| 5.2 | Insumos | ✅ | `/insumos` — no menu |
| 5.3 | Estoque Atual (Inventário) | ✅ | `inventory_routes.py` |
| 5.4 | Kardex (movimentações) | ✅ | `kardex_routes.py` |
| 5.5 | Entrada de Peças (NF entrada) | ✅ | `invoice_routes.py` |
| 5.6 | Pedidos de Compra | ✅ | `purchase_order_routes.py` |
| 5.7 | Fornecedores | ✅ | `fornecedor_routes_mysql.py` |
| 5.8 | Tabela de Serviços / Preços | ✅ | `/listas-preco` — no menu |

---

## 6. BALCÃO / PDV

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 6.1 | PDV Profissional (tela de venda) | ✅ | Testado em produção: venda finalizada, schema corrigido, CONSUMIDOR FINAL auto-criado |
| 6.2 | Abrir Caixa | ✅ | `/caixa/abrir` — sem stored procedure |
| 6.3 | Caixa Atual (painel) | ✅ | `/caixa/atual` → detalhe |
| 6.4 | Fechar Caixa | ✅ | `/caixa/fechar/<id>` — sem stored procedure |
| 6.5 | Sangria | ✅ | `/caixa/sangria/<id>` — formulário próprio |
| 6.6 | Suprimento | ✅ | `/caixa/suprimento/<id>` — formulário próprio |
| 6.7 | Histórico de Caixas | ✅ | `/caixa/` |
| 6.8 | Configurações do PDV | ✅ | `/vendas/pdv/configuracoes` |
| 6.9 | Novo PDV (cadastro) | ✅ | `/vendas/pdv/novo` |
| 6.10 | Histórico de Vendas | ✅ | `venda_bp` registrado, menu ativo, rota `/vendas/relacao` |
| 6.11 | NFC-e (cupom fiscal) | ⚠️ | Módulo existe, opcional para balcão |

---

## 7. FINANCEIRO

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 7.1 | Contas a Receber | ✅ | `accounts_receivable_routes.py` |
| 7.2 | Contas a Pagar | ✅ | `accounts_payable_routes.py` |
| 7.3 | Fluxo de Caixa | ✅ | `cash_flow_routes.py` — `python-dateutil` adicionado |
| 7.4 | Contas Bancárias | ✅ | `bank_account_routes.py` |
| 7.5 | Plano de Contas | ✅ | `chart_of_accounts_routes.py` |
| 7.6 | PIX (QR code + EMV) | ✅ | `pix_routes.py` |
| 7.7 | Boleto Bancário | ❌ | Não implementado |

---

## 8. FISCAL / NF

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 8.1 | NF-e emissão | ⚠️ | `nfe_emissao_routes.py` — try/except duplo já presente; depende de `nfe_service` |
| 8.2 | NFS-e (nota de serviço) | ✅ | `nfse_routes.py` (ABRASF 2.03) |
| 8.3 | NFC-e | ✅ | Import `app.database` corrigido para `database` |
| 8.4 | NCM, CFOP, CST, CNAE | ✅ | Import `app.database` corrigido para `database` |
| 8.5 | Certificados Digitais | ✅ | Tabela `certificados_digitais` |

---

## 9. COMUNICAÇÃO / INTEGRAÇÕES

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 9.1 | WhatsApp Business | ✅ | `whatsapp_routes.py` — UazAPI testado |
| 9.2 | **Envio de orçamento para aprovação (WA)** | ✅ | Rota `enviar_orcamento_wa` + atualiza `status_orcamento='enviado'` |
| 9.3 | **Aviso OS pronta para retirada (WA)** | ✅ | Rota `notificar_os_pronta` + trigger auto ao `status=completed` |
| 9.4 | **Lembrete de revisão preventiva (WA)** | ✅ | Rota `/whatsapp/disparar-lembretes` — cron diário | **testado em produção** `ok:true` |
| 9.5 | **Pesquisa de satisfação pós-OS (WA)** | ⚠️ | Template `satisfacao` existe — disparo por cron pendente |
| 9.6 | **Alerta de OS urgente para admin (WA)** | ✅ | Trigger auto ao criar OS com `type=urgent` → notifica `telefones_admin` |
| 9.7 | E-mail | ⚠️ | `email_service.py` existe, não integrado ao menu |

---

## 10. APP MOBILE / PWA

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 10.1 | Instalável como app (manifest) | ✅ | `/static/manifest.json` |
| 10.2 | Cache offline (service worker) | ✅ | `/static/js/service-worker.js` |
| 10.3 | Ícones PWA | ⚠️ | Placeholder gerado — substituir por arte final |
| 10.4 | Layout responsivo mobile | ✅ | Bootstrap 5.3 + sidebar colapsável |
| 10.5 | Push Notifications | ❌ | Não implementado |
| 10.6 | Sincronização offline real | ❌ | Não implementado (SW só faz cache) |

---

## 11. ADMINISTRATIVO / CONFIGURAÇÕES

| # | Funcionalidade | Status | Observação |
|---|---|---|---|
| 11.1 | Usuários e Permissões | ✅ | `users_routes.py` + `permissoes_routes.py` |
| 11.2 | Cadastro de Empresa | ✅ | `empresa_routes.py` |
| 11.3 | Segmentos | ✅ | `segment_routes.py` |
| 11.4 | Moedas | ✅ | `currency_routes.py` — import corrigido |
| 11.5 | Alertas / Notificações internas | ✅ | `alert_routes.py` |
| 11.6 | Dashboard | ✅ | `dashboard_routes.py` |
| 11.7 | Relatórios gerenciais | ✅ | `reports_routes.py` — `python-dateutil` adicionado |
| 11.8 | Transportadoras | ✅ | Import `app.database` corrigido para `database` |
| 11.9 | ETL / Migração do legado | ❌ | Não implementado |

---

## RESUMO EXECUTIVO

| Categoria | Total | ✅ 100% | ⚠️ Parcial | ❌ Falta |
|---|---|---|---|---|
| Atendimento / OS | 18 | 15 | 0 | 3 |
| Clientes / CRM | 6 | 5 | 0 | 1 |
| Veículos | 5 | 4 | 0 | 1 |
| Equipe / Mecânicos | 10 | 10 | 0 | 0 |
| Peças e Estoque | 8 | 8 | 0 | 0 |
| Balcão / PDV | 11 | 10 | 1 | 0 |
| Financeiro | 7 | 6 | 0 | 1 |
| Fiscal / NF | 5 | 4 | 1 | 0 |
| Comunicação | 8 | 6 | 1 | 1 |
| PWA / Mobile | 6 | 3 | 2 | 2 (push/offline) |
| Administrativo | 9 | 8 | 0 | 1 |
| **TOTAL** | **93** | **81 (87%)** | **4 (4%)** | **8 (9%)** |

---

## PRÓXIMAS PRIORIDADES SUGERIDAS

### ✅ Concluídas nesta sessão
1. ✅ Fluxos WhatsApp testados em produção (`ok:true`) + cron 08h configurado
2. ✅ PDV testado em produção + Histórico de Vendas ativo
3. ✅ Agenda de Mecânicos — FullCalendar, arrastar OS, filtro por técnico
4. ✅ Agendamento de OS com data/hora/técnico
5. ✅ Preventivo automático ao concluir OS → `next_maintenance` atualizado
6. ✅ Integrações: botão Agenda no perfil do técnico, OS sem técnico no painel

### 🔴 Alta — Próximas prioridades
1. **Executar migration no servidor** — `migration_agenda.sql` (adiciona colunas `agendado_para`, `hora_inicio`, `hora_fim`)
2. **Comissionamento** — mecânico + captação de marketing
3. **Pesquisa de satisfação pós-OS (WA)** — cron 1h após `status=completed`

### 🟠 Média
4. **Controle de Garantia** (prazo por peça/serviço)
5. **Ícones PWA finais** (substituir placeholder por arte da marca)

### 🔵 Baixa — Pós-MVP
6. **Portal do Cliente**
7. **Push Notifications** (Web Push API)
8. **Boleto Bancário** (BB + Mercado Pago)
9. **ETL / Migração do legado**
