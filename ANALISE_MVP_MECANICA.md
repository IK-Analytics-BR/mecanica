# 📋 Análise Completa MVP — IKFlow Mecânica
**Atualizado em:** 28/05/2026 (revisão 4 — WhatsApp UazAPI funcionando)  
**Fontes consolidadas:**
- `PROPOSTA_MECANICA_IKFLOW.md` — proposta técnica completa
- Fluxo de negócio descrito pelo cliente em sessão
- Inventário real de rotas em `IKFlow-Mecanica/app/routes/` (65+ módulos)
- Inventário do projeto Holding (`windsurf-project-4`) — WhatsApp, PIX, NFS-e, Fiscal
- Inventário do IKFlow-Correias — módulos reutilizáveis

---

## 🔄 Fluxo de Negócio

```
[1] Cliente chega → Atendente verifica reclamação
[2] Abre OS/Orçamento → Imprime Prisma de Diagnóstico → deixa na prancheta
[3] Mecânico verifica veículo → lança diagnóstico + lista serviços/peças → salva
[4] Compras orça peças → insere produto + valor no orçamento (sem cadastrar produto ainda)
[5] Atendente/Gerente define horas técnicas + nível de complexidade (faixas de valor)
[6] Orçamento enviado ao cliente (WhatsApp ou e-mail)
[7] Cliente aprova → OS entra na fila de serviços
[8] Mecânico vê OS atribuídas → inicia → executa → confirma finalização (controla início/fim)
[9] Sistema envia WhatsApp ao cliente → cliente busca → paga → emite NF-e → lança financeiro
```

---

## ✅ JÁ IMPLEMENTADO — Blueprint registrado e funcionando

### 🔧 Módulo OS / Atendimento
| Função | Rota | Status |
|---|---|---|
| Listagem de OS | `/service_orders` | ✅ |
| **Tela unificada OS + Orçamento** | `/service_orders/add` | ✅ Implementado hoje |
| Diagnóstico do mecânico | campo `diagnostico` na OS | ✅ |
| Complexidade + Horas + Faixas R$/h | Simples/Médio/Complexo | ✅ |
| Peças ad-hoc (sem cadastrar produto) | tabela dinâmica na OS | ✅ |
| Total MO + Peças + Desconto em tempo real | JS na tela | ✅ |
| Status orçamento: Rascunho→Enviado→Aprovado | campo `status_orcamento` | ✅ |
| KM de entrada | campo `km_entrada` | ✅ |
| Edição de OS / atribuição de técnico | `/service_orders/edit/<id>` | ✅ |
| Visualização detalhada da OS | `/service_orders/view/<id>` | ✅ |

### 👥 Clientes
| Função | Status |
|---|---|
| CRUD completo de clientes | ✅ `cliente_routes_mysql.py` |
| Importação de clientes (CSV/Excel) | ✅ `importar_clientes_routes.py` |
| **Clientes em Potencial** (CRM básico) | ✅ `clientes_potenciais_routes.py` |
| Questionário de visita ao cliente | ✅ `questionario_visita_routes.py` |
| Rota de vendas por cliente | ✅ `rota_vendas_routes.py` |

### 🚗 Veículos (equipment)
| Função | Status |
|---|---|
| Listagem com placa, modelo, proprietário | ✅ Adaptado hoje |
| Cadastro: Placa, Fabricante, Modelo, KM | ✅ Adaptado hoje |
| Visualização detalhada | ✅ Adaptado hoje |
| Hora-metro (hodômetro) | ✅ `hour_meter_routes.py` |
| Plano de revisão preventiva | ✅ `maintenance_plan_routes.py` |

### 💰 Financeiro
| Função | Status |
|---|---|
| Contas a Pagar | ✅ |
| Contas a Receber | ✅ |
| Fluxo de Caixa | ✅ |
| Contas Bancárias | ✅ |
| Plano de Contas | ✅ |
| Formas de Pagamento | ✅ 6 opções |
| Condições de Pagamento | ✅ |
| Câmbio / Moedas | ✅ |
| Caixa (PDV) | ✅ `cash_register_routes.py` |
| Alertas financeiros | ✅ |

### 🛒 Compras
| Função | Status |
|---|---|
| Fornecedores | ✅ |
| Pedidos de Compra | ✅ |
| Entrada/Recebimento de produtos | ✅ |
| Faturas de Compra | ✅ `invoice_routes.py` |

### 📦 Estoque / Peças
| Função | Status |
|---|---|
| Produtos / Peças (CRUD) | ✅ `produto_routes_mysql.py` |
| Controle de Estoque | ✅ `inventory_routes.py` |
| Kardex (movimentações) | ✅ `kardex_routes.py` |
| Categorias, Marcas, Grupos, Modelos | ✅ |
| Lista de Preços | ✅ `lista_preco_routes.py` |
| Especificações Técnicas de Produto | ✅ |

### 📄 Fiscal / NF-e
| Função | Arquivo | Status |
|---|---|---|
| Emissão NF-e (saída) | `nfe_emissao_routes.py` (87KB) | ✅ |
| **Importação XML NF-e entrada** | `importar_nfe_entrada.py` | ✅ |
| **Importação XML NF-e upload** | `importar_nfe_upload.py` (40KB) | ✅ |
| **Importação NF-e (consulta)** | `importar_nfe.py` | ✅ |
| NFC-e (cupom fiscal) | `nfce_routes.py` (30KB) | ✅ |
| CFOP, NCM, CST, CNAE | ✅ | ✅ |
| Certificados digitais | tabela `certificados_digitais` | ✅ |
| Email de NF-e | tabela `email_config_nfe` | ✅ |

### 💼 Comercial / Orçamentos
| Função | Status |
|---|---|
| Orçamentos completos (múltiplas versões) | ✅ `orcamento_routes.py` (125KB) |
| Orçamento DNA (modelo avançado) | ✅ `orcamento_dna_routes.py` |
| PDV Profissional (balcão) | ✅ `pdv_profissional_routes.py` — **registrado e no menu** `/vendas/pdv` |
| Vendedores / Comissionamento | ✅ `vendedor_routes.py` |
| Vendas / Histórico | ✅ `venda_routes.py` |

### 👷 RH / Equipe
| Função | Status |
|---|---|
| Técnicos / Mecânicos | ✅ `technician_routes.py` |
| Jornada de Trabalho / Ponto | ✅ `jornada_trabalho_routes.py` |
| Usuários e Permissões | ✅ `users_routes.py` + `permissoes_routes.py` |

### 🏢 Administração
| Função | Status |
|---|---|
| Empresas (multi-empresa) | ✅ `empresa_routes.py` |
| Configurações da empresa | ✅ |
| Transportadoras | ✅ |
| Segmentos | ✅ |
| Moedas | ✅ |
| Alertas / Notificações internas | ✅ `alert_routes.py` |
| Integração (APIs externas) | ✅ `integration_routes.py` |
| Relatórios gerenciais | ✅ `reports_routes.py` |
| Dashboard | ✅ `dashboard_routes.py` |

---

## 🟡 EXISTE NO PROJETO MAS NÃO ESTÁ NO MENU / PRECISA ADAPTAR

| Módulo | Arquivo | Adaptação necessária |
|---|---|---|
| **Clientes em Potencial** | `clientes_potenciais_routes.py` | Adicionar ao menu; renomear para contexto mecânica |
| **Questionário de Visita** | `questionario_visita_routes.py` | Adaptar para "Pesquisa pós-atendimento" |
| **Rota de Visitas** | `rota_vendas_routes.py` | Adaptar para "Rota de captação" |
| **Hora-metro** | `hour_meter_routes.py` | Já útil: registrar KM por atendimento |
| **Lista de Preços** | `lista_preco_routes.py` | Adaptar como "Tabela de serviços (mão de obra)" |
| ~~**PDV Profissional**~~ | ~~`pdv_profissional_routes.py`~~ | ✅ **ATIVADO** — blueprint registrado, menu Balcão/PDV atualizado |
| **Execução de Serviços** | `ordem_producao_routes.py` | Adaptar para controle de execução pelo mecânico |
| **Pausas de Produção** | `producao_pausas_routes.py` | Adaptar para pausas/motivos durante a OS |
| **NFC-e** | `nfce_routes.py` | Opcional para venda de peças no balcão |
| **Insumos** | `insumo_routes_mysql.py` | Renomear para "Peças" nas telas |

---

## 🔴 PRECISA PORTAR DE OUTROS PROJETOS (já existe, só integrar)

### Do Holding (`windsurf-project-4` — PHP)

| Módulo | Arquivo PHP | O que tem | Prioridade |
|---|---|---|---|
| **WhatsApp Business** | `WhatsappController.php` (41KB) | Configuração por empresa, envio de orçamento, aviso OS pronta, pós-atendimento, templates configuráveis, log de envios, webhook, status da instância (QR code) | 🔴 Alta |
| **PIX** | `PixController.php` (37KB) | Gerar cobrança PIX, QR code, webhook de confirmação, baixa automática, histórico, logs, múltiplas chaves por empresa | 🔴 Alta |
| **NFS-e** | `NfseController.php` (41KB) | Emissão nota fiscal de serviços, integração prefeitura, XML, PDF | 🟠 Média |
| **Fiscal / SPED** | `FiscalController.php` (36KB) | SPED Fiscal, blocos completos, assinatura | 🟡 Baixa |
| **Rateio** | `RateioController.php` | Rateio de despesas entre centros de custo | 🟡 Baixa |
| **Portal do Cliente** | `Portal/` | Portal web para cliente ver histórico, orçamentos, faturas | 🟠 Média |
| **IA / Análise** | `IaAnaliseController.php` | Análise com LLM — adaptar para análise de produtividade de mecânicos | 🟡 Baixa |
| **Inadimplência** | `InadimplenciaController.php` | Lista de devedores, régua de cobrança | 🟠 Média |
| **Mercado / Inteligência** | `MercadoController.php` | Inteligência de mercado — adaptar para benchmarking de preços de serviços | 🟡 Baixa |

---

## ✅ IMPLEMENTADOS NESTA SESSÃO (anteriormente "não existe")

| # | Funcionalidade | Status |
|---|---|---|
| 1 | **Impressão PDF do Prisma** | ✅ `service_order_pdf.html` + rota `/service_orders/<id>/pdf` |
| 2 | **Orçamento avulso** | ✅ `service_order_avulso.html` + rota `/service_orders/avulso` |
| 3 | **Controle início/fim do serviço** | ✅ rotas `/iniciar` e `/finalizar` + cronômetro JS |
| 4 | **Histórico completo do veículo** | ✅ `veiculo_historico.html` + rota `/veiculos/<id>/historico` |
| 5 | **Lançamento automático C/R** | ✅ `_lancar_contas_receber()` em aprovar/finalizar |
| 6 | **WhatsApp Business** | ✅ `whatsapp_routes.py` — **UazAPI testado e funcionando** (header `token:`, `/send/text`) |
| 7 | **PIX integrado** | ✅ `pix_routes.py` (PIX estático EMV + QR code) |
| 8 | **NFS-e** | ✅ `nfse_routes.py` (ABRASF 2.03, XML + WebService) |
| 9 | **PDV Profissional no balcão** | ✅ Blueprint registrado, menu ativo em Balcão/PDV |
| 10 | **PWA / App mobile** | ✅ `manifest.json` + `service-worker.js` + tags no `base.html` |
| 11 | **Caixa PDV (Abrir/Fechar/Sangria/Suprimento)** | ✅ Rotas já existiam — stored procedures substituídas por SQL direto; menu ativo |
| 12 | **Menu completo — módulos do MVP** | ✅ `lista_preco`, `rota_vendas`, `questionario_visita`, `producao_pausas`, `cash_register` no menu |
| 13 | **Templates Sangria/Suprimento** | ✅ `cash_register_sangria.html` + `cash_register_suprimento.html` criados |
| 14 | **`pdv_settings` no banco** | ✅ Tabela verificada, config padrão inserida, empresas corrigidas (`usar_no_pdv=1`) |
| 15 | **WhatsApp UazAPI** | ✅ Config salva no banco, header `token:` correto, `/send/text` testado e funcionando |
| 16 | **Configuração WA completa** | ✅ `dias_lembrete`, `telefone_teste`, `telefones_admin`, `disparos_ativos` salvos |

## ❌ AINDA NÃO EXISTE — Desenvolvimento futuro

| # | Funcionalidade | Complexidade | Prioridade |
|---|---|---|---|
| 1 | **Agenda por mecânico** (calendário diário/semanal) | Alta | 🟠 Média |
| 2 | **Agendamento preventivo automático** por KM/prazo pós-OS | Alta | 🟠 Média |
| 3 | **Controle de Garantia** por peça/serviço (prazo + data) | Média | 🟠 Média |
| 4 | **Popup pós-OS** "Deseja emitir NF-e?" com dados pré-preenchidos | Baixa | 🟠 Média |
| 5 | **Restrição WiFi para ponto** (IP/rede da empresa) | Média | 🟡 Baixa |
| 6 | **ETL / Migração do sistema legado** | Alta | 🟡 Baixa |
| 7 | **Boleto Banco do Brasil** | Alta | 🟡 Baixa |
| 8 | **Boleto Mercado Pago** | Média | 🟡 Baixa |
| 9 | **Ícones PWA finais** (substituir placeholder por arte real) | Baixa | 🟡 Baixa |

---

## 🏗️ Priorização para Apresentação (Sexta-feira)

### Implementar ainda hoje/amanhã:
1. 🔧 PDF / Impressão da OS (Prisma de diagnóstico)
2. 🔧 Controle início/fim do serviço na tela de edição da OS
3. 🔧 Histórico do veículo no detalhe do veículo
4. 🔧 Lançamento automático em C/R ao aprovar/concluir OS
5. 🔧 Adicionar "Clientes em Potencial" ao menu mecânica

### Para demonstrar (já funcionando):
- ✅ Cadastro de clientes, veículos, técnicos
- ✅ OS/Orçamento unificado: diagnóstico, complexidade, peças ad-hoc, totais
- ✅ Importação XML NF-e entrada e saída
- ✅ Emissão NF-e
- ✅ Financeiro completo
- ✅ Estoque de peças / Kardex
- ✅ Compras / Pedidos
- ✅ Relatórios / Dashboard
- ✅ Permissões por usuário/tela

---

## 📊 Inventário de Rotas — IKFlow Mecânica (`/app/routes/`)

**Total de módulos disponíveis: 65 arquivos de rota**

| Grupo | Módulos |
|---|---|
| **Atendimento/OS** | service_order, orcamento, orcamento_dna, maintenance_plan |
| **Clientes** | cliente, clientes_potenciais, importar_clientes, questionario_visita |
| **Veículos** | equipamento, hour_meter |
| **Técnicos/RH** | technician, jornada_trabalho, vendedor |
| **Financeiro** | accounts_payable, accounts_receivable, cash_flow, cash_register, bank_account, chart_of_accounts, payment_config |
| **Compras** | purchase_order, invoice, fornecedor |
| **Estoque** | inventory, kardex, insumo, produto (+ category/brand/group/subgroup/model) |
| **Fiscal** | nfe_emissao, nfce, importar_nfe, importar_nfe_entrada, importar_nfe_upload, cfop, ncm |
| **Comercial** | pdv_profissional, pdv_config, venda, lista_preco, transportadora |
| **Produção/Execução** | ordem_producao, producao_pausas, config_producao, ficha_tecnica |
| **Rotas Comerciais** | rota_vendas, romaneio |
| **Administração** | empresa, usuario, users, permissoes, segment, company, currency, condicao_pagamento, unit_measure, alert, dashboard, reports, integration, api |

---

## 📌 Módulos que NÃO se aplicam à mecânica (manter ocultos no menu)

- `ordem_producao_routes.py` — Produção industrial (remover ou adaptar para "Execução de Serviços")
- `romaneio_routes.py` — Romaneio de entrega
- `ficha_tecnica_routes.py` — Ficha técnica industrial
- `producao_pausas_routes.py` — Pode adaptar para "pausas do mecânico"
- `dev_economico_routes.py` — Desenvolvimento econômico (outro projeto)

---

*Documento de referência interno — IK Analytics — aritana@ikanalytics.com.br*
