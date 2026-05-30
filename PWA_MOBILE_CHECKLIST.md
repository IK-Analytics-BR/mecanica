# PWA Mobile — Checklist de Adaptação de Telas

> Estratégia: todas as telas herdam de `base.html` que já tem o bottom nav e drawer.
> O ajuste em cada tela é CSS local: tabelas → cards, formulários → stack vertical, botões → full width.
> ✅ = Concluído | 🔄 = Em progresso | ⬜ = Pendente

---

## 🔴 PRIORIDADE ALTA — Telas do Bottom Nav (uso diário)

| # | Tela | Template | Status |
|---|------|----------|--------|
| 1 | Dashboard / Início | `bem_vindo.html` | ✅ |
| 2 | Lista de OS | `service_order_list.html` | ✅ |
| 3 | Nova OS (form) | `service_order_form.html` | ✅ |
| 4 | Visualizar OS | `service_order_view.html` | ✅ |
| 5 | Lista de Clientes | `cliente_list.html` | ✅ |
| 6 | Form Cliente | `cliente_form.html` | ✅ |
| 7 | Visualizar Cliente | `cliente_view.html` | ✅ |
| 8 | Lista Estoque | `inventory_list.html` | ✅ |
| 9 | Ajuste de Estoque | `inventory_adjustment.html` | ✅ |
| 10 | Transferência Estoque | `inventory_transfer.html` | ✅ |

---

## 🟡 PRIORIDADE MÉDIA — Acessadas pelo Menu Drawer

| # | Tela | Template | Status |
|---|------|----------|--------|
| 11 | Dashboard OS | `service_order_dashboard.html` | ✅ |
| 12 | OS Avulsa | `service_order_avulso.html` | ✅ |
| 13 | Editar OS | `service_order_edit.html` | ✅ |
| 14 | Relatório Mecânicos | `relatorio_mecanicos.html` | ✅ |
| 15 | Relatório Serviços | `relatorio_servicos.html` | ✅ |
| 16 | Lista Técnicos | `technician_list.html` | ✅ |
| 17 | Form Técnico | `technician_form.html` | ✅ |
| 18 | Movimentações Estoque | `inventory_movements.html` | ✅ |
| 19 | Relatório Estoque | `inventory_report.html` | ✅ |
| 20 | C/R Lista | `accounts_receivable_list.html` | ✅ |
| 21 | C/R Form | `accounts_receivable_form.html` | ✅ |
| 22 | C/P Lista | `accounts_payable_list.html` | ✅ |
| 23 | Fluxo de Caixa | `cash_flow_dashboard.html` | ✅ |
| 24 | Fornecedor Lista | `fornecedor_list.html` | ✅ |
| 25 | Fornecedor Form | `fornecedor_form.html` | ✅ |
| 26 | Produto Lista | `produto_list.html` | ✅ |
| 27 | Produto Form | `produto_form_abas.html` | ✅ |
| 28 | Agenda Mecânico | `agenda_mecanico.html` | ✅ |
| 29 | Perfil Usuário | `user_profile.html` | ✅ |
| 30 | Login | `auth/login.html` | ✅ |

---

## 🟢 PRIORIDADE BAIXA — Admin / Relatórios complexos

| # | Tela | Template | Status |
|---|------|----------|--------|
| 31 | Usuários Lista | `users_list.html` | ✅ |
| 32 | Usuário Form | `user_form.html` | ✅ |
| 33 | Permissões | `admin/permissoes_lista.html` | ✅ |
| 34 | Relatório Financeiro | `financial_report.html` | ✅ |
| 35 | Relatório Compras | `purchase_report.html` | ✅ |
| 36 | Relatório Consolidado | `consolidated_report.html` | ✅ |
| 37 | Pedido Compra Lista | `purchase_order_list.html` | ✅ |
| 38 | Pedido Compra Form | `purchase_order_form_fixed.html` | ⬜ |
| 39 | NF-e / NFS-e | `nfe/ nfse/` | ⬜ |
| 40 | Configurações Empresa | `company_settings.html` | ✅ |

---

## Padrão de adaptação aplicado em cada tela

```css
/* Tabelas → scroll horizontal ou cards */
/* Botões de ação → 44px altura mínima */
/* Formulários → 1 coluna, labels acima */
/* Cards com border-radius: 12px */
/* Fontes: labels 13px, valores 15px */
/* Padding interno: 16px */
```
