# ✅ CHECKLIST DE STATUS — IKFlow Mecânica
**Última atualização:** 28/05/2026 (revisão 2 — Deploy Hostinger + menu completo + fluxos WhatsApp priorizados)  
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
| 1.16 | Agendamento preventivo automático | ❌ | Não implementado |
| 1.17 | Controle de Garantia por peça/serviço | ❌ | Não implementado |
| 1.18 | Popup pós-OS "Emitir NF-e?" | ❌ | Não implementado |

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
| 4.10 | Agenda por mecânico (calendário) | ❌ | Não implementado |

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
| 6.1 | PDV Profissional (tela de venda) | ⚠️ | Rota ativa; depende de caixa aberto; teste real pendente |
| 6.2 | Abrir Caixa | ✅ | `/caixa/abrir` — sem stored procedure |
| 6.3 | Caixa Atual (painel) | ✅ | `/caixa/atual` → detalhe |
| 6.4 | Fechar Caixa | ✅ | `/caixa/fechar/<id>` — sem stored procedure |
| 6.5 | Sangria | ✅ | `/caixa/sangria/<id>` — formulário próprio |
| 6.6 | Suprimento | ✅ | `/caixa/suprimento/<id>` — formulário próprio |
| 6.7 | Histórico de Caixas | ✅ | `/caixa/` |
| 6.8 | Configurações do PDV | ✅ | `/vendas/pdv/configuracoes` |
| 6.9 | Novo PDV (cadastro) | ✅ | `/vendas/pdv/novo` |
| 6.10 | Histórico de Vendas | ⚠️ | Depende de `venda_routes.py` registrado |
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
| 9.1 | WhatsApp Business | ✅ | `whatsapp_routes.py` — **UazAPI testado** (`token:` header, `/send/text`) |
| 9.2 | **Envio de orçamento para aprovação (WA)** | ❌ | Botão na OS → envia link/PDF por WA para cliente aprovar |
| 9.3 | **Aviso OS pronta para retirada (WA)** | ❌ | Trigger automático ao finalizar OS |
| 9.4 | **Lembrete de revisão preventiva (WA)** | ❌ | Disparo automático por KM/data (`disparos_ativos`) |
| 9.5 | **Pesquisa de satisfação pós-OS (WA)** | ❌ | Mensagem automática 1h após entrega |
| 9.6 | **Alerta de OS urgente para admin (WA)** | ❌ | Notifica `telefones_admin` ao abrir OS urgente |
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
| Equipe / Mecânicos | 10 | 7 | 0 | 3 |
| Peças e Estoque | 8 | 8 | 0 | 0 |
| Balcão / PDV | 11 | 8 | 3 | 0 |
| Financeiro | 7 | 6 | 0 | 1 |
| Fiscal / NF | 5 | 4 | 1 | 0 |
| Comunicação | 8 | 1 | 1 | 6 |
| PWA / Mobile | 6 | 3 | 2 | 2 (push/offline) |
| Administrativo | 9 | 8 | 0 | 1 |
| **TOTAL** | **93** | **71 (76%)** | **8 (9%)** | **14 (15%)** |

---

## PRÓXIMAS PRIORIDADES SUGERIDAS

### 🔴 Alta — Fluxos WhatsApp (alto impacto no cliente)
1. **Envio de orçamento para aprovação via WA**
   - Botão "Enviar orçamento" na OS → monta mensagem com valor, peças e link PDF
   - Atualiza `status_orcamento` para `enviado` após confirmação de envio
   - Rota: `POST /service_orders/<id>/enviar-orcamento-wa`
2. **Aviso de OS pronta para retirada**
   - Trigger automático ao mudar status OS para `concluida`
   - Mensagem: "Seu veículo [placa] está pronto! Valor: R$ XX. Venha retirar."
   - Rota: `POST /service_orders/<id>/notificar-pronta`
3. **Lembrete de revisão preventiva**
   - Job diário: busca veículos com revisão vencendo em `dias_lembrete` dias
   - Usa `disparos_ativos` da config WA para habilitar/desabilitar
   - Rota: `GET /whatsapp/disparar-lembretes` (chamada por cron)
4. **Pesquisa de satisfação pós-OS**
   - Enviada automaticamente 1h após status `concluida`
   - Mensagem curta: "Como foi o atendimento? Responda: 1-Ótimo 2-Bom 3-Regular"
5. **Alerta de OS urgente para admin**
   - Ao criar OS com prioridade `urgente` → notifica todos os `telefones_admin`

### 🟠 Média — Desbloqueiam módulos quebrados
6. **Instalar `python-dateutil`** → habilita Fluxo de Caixa + Relatórios
7. **Corrigir imports `app.database`** em NF-e, NFC-e, NCM, Transportadoras, Moedas → 5 módulos em 1 fix
8. **Teste real do PDV** — venda completa com caixa aberto

### � Baixa — Pós-MVP
9. **Agenda por mecânico** (calendário diário)
10. **Controle de Garantia** (prazo por peça/serviço)
11. **Comissões** (mecânico + captação)
12. **Portal do Cliente**
13. **Push Notifications** (Web Push API)
14. **Boleto Bancário**
15. **ETL / Migração do legado**
