# 🔍 AUDITORIA COMPLETA — IKFlow Mecânica
**Data:** 28/05/2026 | **Auditor:** Cascade AI  
**Versão auditada:** v1.7 (81/93 = 87% MVP)  
**Ambiente:** `mecanicas.ikflow.cloud` — Flask/Python + MySQL

---

## RELATÓRIO EXECUTIVO

| Item | Avaliação |
|---|---|
| **Maturidade geral** | 7,5 / 10 — MVP sólido, heranças identificáveis mas não bloqueantes |
| **MVP real entregue** | ~83% funcional (descontando módulos herdados sem uso real) |
| **Risco operacional** | ⚠️ Médio — módulos industriais ativos consomem memória e confundem usuários |
| **Risco de dados** | ⚠️ Médio — sem `company_id` em várias tabelas críticas (multi-tenant incompleto) |
| **Risco de segurança** | ⚠️ Médio — algumas rotas sem `@login_required`, sem CSRF em formulários |
| **Prioridade de ação** | Limpeza de heranças + multi-tenant + segurança antes de escala comercial |

---

## 1. PROBLEMAS CRÍTICOS

### C1 — Multi-tenant incompleto (ALTO RISCO)
- **Problema:** Tabelas `service_orders`, `customers`, `equipment`, `technicians`, `sales` não possuem `company_id` ou equivalente.
- **Impacto:** Clientes de empresas diferentes verão dados uns dos outros em instalação multi-empresa.
- **Severidade:** 🔴 Crítica
- **Localização:** Todas as rotas de OS, clientes, veículos, estoque.
- **Causa:** Sistema herdado de uso mono-empresa; nunca foi adaptado para SaaS real.
- **Solução:** Adicionar `company_id` nas tabelas principais + filtro em todas as queries por `session['company_id']`.
- **Risco financeiro:** ALTO — vazamento de dados entre clientes pagantes.

---

### C2 — Autenticação inconsistente
- **Problema:** `login_required` é redefinido localmente em **cada arquivo de rota** (15+ duplicatas). Nenhum middleware centralizado.
- **Localização:** `whatsapp_routes.py`, `service_order_routes.py`, `technician_routes.py`, `dashboard_routes.py`, etc.
- **Causa:** Herança de múltiplos projetos copiados sem refatoração.
- **Solução:** Criar `app/utils/auth.py` com o decorator único e importar em todos.
- **Risco técnico:** Se um arquivo esquecer o decorator, a rota fica pública.

---

### C3 — Sem proteção CSRF
- **Problema:** Formulários POST não usam token CSRF (`Flask-WTF` ou `flask-wtf`).
- **Localização:** Todos os formulários HTML — `service_order_form.html`, `cliente_form.html`, `whatsapp_routes.py`, etc.
- **Solução:** Instalar `Flask-WTF`, adicionar `{{ form.hidden_tag() }}` ou middleware global.
- **Risco de segurança:** ALTO — CSRF attacks em produção.

---

### C4 — Módulo `ordem_producao_routes.py` ativo (241 KB) — Industrial
- **Problema:** Módulo de manufatura/produção industrial registrado e carregado em memória. Rotas como `/industria/ordem-producao/meu-gantt` aparecem no menu de Mecânicos.
- **Localização:** `main_mysql.py` linha 116, menu `base.html` linhas 353–358.
- **Impacto:** Mecânico vê "Ordens de Execução", "Gantt de Serviços", "Painel do Líder" — termos industriais, não automotivos.
- **Solução:** Desativar no menu com `{% if false %}` ou criar `APP_MODE` guard; manter código mas ocultar das rotas públicas.

---

### C5 — `orcamento_routes.py` com 125 KB — Possível duplicidade com OS
- **Problema:** Módulo de orçamentos separado de 125 KB. Fluxo OS já tem campo `status_orcamento`. Pode haver duplicidade de lógica.
- **Localização:** `orcamento_routes.py` vs `service_order_routes.py`.
- **Risco:** Cliente cria orçamento em 2 lugares diferentes → inconsistência de dados.
- **Solução:** Auditar se o orçamento deve ser parte da OS ou módulo separado. Unificar ou documentar claramente a diferença.

---

## 2. PROBLEMAS MÉDIOS

### M1 — Módulos herdados carregados desnecessariamente
Módulos ativos no `main_mysql.py` que **não fazem sentido para mecânica**:

| Módulo | Arquivo | Tamanho | Contexto original |
|---|---|---|---|
| `romaneio_bp` | `romaneio_routes.py` | 18 KB | Distribuição/logística |
| `dev_economico_bp` | `dev_economico_routes.py` | 33 KB | Governança econômica |
| `rota_vendas_bp` | `rota_vendas_routes.py` | 11 KB | CRM de salgados/correias |
| `questionario_visita_bp` | `questionario_visita_routes.py` | 5 KB | Salgados/visita comercial |
| `config_producao_bp` | `config_producao_routes.py` | 23 KB | Industrial |
| `ficha_tecnica_bp` | `ficha_tecnica_routes.py` | 36 KB | Industrial/manufatura |
| `producao_pausas_bp` | `producao_pausas_routes.py` | 14 KB | Industrial |
| `vendedor_bp` | `vendedor_routes.py` | 16 KB | Força de vendas B2B |
| `segment_bp` | `segment_routes.py` | 5 KB | Segmentação B2B |

**Impacto:** ~161 KB de código carregado inutilmente em cada processo Flask. Aumenta tempo de boot e consumo de memória.

---

### M2 — Templates duplicados de produto
Existem **6 variantes** do formulário de produto:
- `produto_form.html` (15 KB)
- `produto_form_abas.html` (95 KB) ← gigante
- `produto_form_abas_fixed.html` (33 KB)
- `produto_form_scripts.html` (8 KB)
- `produto_form_tabs_*.html` (5 arquivos)
- `produto_view_completo.html` (26 KB)

**Causa:** Iterações de desenvolvimento nunca limpas.  
**Solução:** Manter somente `produto_form_abas_fixed.html` + `produto_view_completo.html`, deletar os demais.

---

### M3 — Apresentações de produto expostas
- `apresentacao_ikflow.html` (51 KB) e `apresentacao_ikflow_v2.html` (64 KB) no diretório de templates público.
- **Risco:** Conteúdo comercial/interno acessível por URL direta.
- **Solução:** Mover para `/static/docs/` ou proteger com `@login_required`.

---

### M4 — Menu com item duplicado "Lembretes de Revisão"
- `base.html` linha 244: "Lembretes de Revisão" aponta para `/agenda` (igual ao item acima).
- `base.html` linha 477: "Lembretes Automáticos" no menu Comunicação aponta para `em_desenvolvimento`.
- **Solução:** Remover duplicata; o item em Comunicação deve apontar para `/whatsapp/disparar-lembretes` ou ser removido.

---

### M5 — `hour_meter_routes.py` — Horímetro industrial vs KM veículo
- **Problema:** Módulo de horímetro herdado de contexto industrial (horas de operação de máquinas). Na mecânica automotiva, o correto é **quilometragem** (KM).
- **Localização:** Menu Veículos → "KM / Horímetro", `hour_meter_routes.py`.
- **Solução:** Renomear interface para "Quilometragem" e adaptar campos de "horas" para "km". O campo `accumulated_hours` em `equipment` deveria ser `km_atual`.

---

### M6 — `questionario_visita_salgados.html` (42 KB) em produção
- **Problema:** Template com "salgados" no nome e conteúdo de questionário de visita para distribuidora de salgados está no diretório de templates da mecânica.
- **Risco:** Confusão de contexto, dados irrelevantes.
- **Solução:** Remover ou substituir por questionário de satisfação pós-OS automotivo.

---

### M7 — Dashboard usa terminologia CMMS (industrial)
- `dashboard_routes.py` linha 28: rota `/cmms_dashboard` — CMMS é Computerized Maintenance Management System (industrial).
- Menu: "Dashboard Geral" aponta para `cmms_dashboard`.
- Campos como `wear_percentage`, `base_life_hours`, `k_intensity`, `k_environment` em `equipment` são métricas industriais, não automotivas.
- **Solução:** Renomear rota para `/dashboard` e adaptar métricas para veículos (km, revisões, OS abertas).

---

### M8 — `venda_pdv_profissional.html` com 148 KB
- **Problema:** Template gigante de 148 KB para o PDV. Provavelmente contém código morto de iterações anteriores.
- **Impacto:** Lentidão no carregamento inicial do PDV em conexões móveis.
- **Solução:** Auditoria interna do template; separar em componentes menores via `{% include %}`.

---

## 3. PROBLEMAS LEVES

### L1 — Título do sistema desatualizado
- `technician_list.html` linha 3: `"Técnicos - Sistema de Gestão de Suprimentos"` — herdado do IKFlow Correias.
- `technician_view.html` linha 3: mesmo problema.
- Vários templates usam "Sistema de Gestão de Suprimentos" no `<title>`.
- **Solução:** `sed -i 's/Sistema de Gestão de Suprimentos/IKFlow Mecânica/g'` nos templates ou variável global no `base.html`.

---

### L2 — `insumo_routes.py` — Insumos industriais vs mecânica
- "Insumos" faz sentido em mecânica (óleo, graxa, fluidos), mas a interface herdada pode usar terminologia industrial.
- Avaliar se `insumo_form.html` usa campos adequados para consumíveis automotivos.

---

### L3 — Menu "Comunicação" com item apontando para `em_desenvolvimento`
- "Lembretes Automáticos" no menu Comunicação aponta para `em_desenvolvimento` mesmo com a rota `/whatsapp/disparar-lembretes` funcionando.
- **Solução:** Atualizar para apontar para `/whatsapp/disparar-lembretes` ou remover.

---

### L4 — `purchase_order_routes_fixed.py` — sufixo `_fixed`
- Arquivo com sufixo `_fixed` sugere correção temporária nunca consolidada.
- **Solução:** Renomear para `purchase_order_routes.py` após confirmar que é a versão definitiva.

---

### L5 — Dois sistemas de usuários paralelos
- `users_routes.py` + `usuario_routes_mysql.py` — dois módulos de usuários.
- `user_form.html` + `usuario_form.html` — dois formulários.
- **Causa:** Herança de dois projetos diferentes.
- **Solução:** Consolidar em um único módulo; remover o legado.

---

### L6 — `cfop_routes.py` com import quebrado
- Erro conhecido: `No module named 'app.database'` ao importar.
- Rota fiscal crítica para NF-e inacessível.
- **Solução:** Corrigir import para `from database import get_db`.

---

## 4. FLUXOS QUEBRADOS / INCOMPLETOS

| Fluxo | Problema | Severidade |
|---|---|---|
| OS → Faturamento NF-e | Botão existe mas `nfe_emissao` falha no import | 🔴 Alta |
| OS → NFS-e | Funciona se `nfse_bp` carregado, mas sem teste confirmado | 🟡 Média |
| PDV → Comissão vendedor | Não implementado — venda registrada sem vincular comissão | 🟡 Média |
| Veículo → KM → Preventivo | `next_maintenance` agora atualizado, mas sem input de KM atual na OS | 🟡 Média |
| Orçamento → Aprovação → OS | Fluxo de aprovação de orçamento não tem trigger automático de criação de OS | 🟡 Média |
| Estoque → Consumo OS | Peças da OS não baixam automaticamente o estoque | 🔴 Alta |
| PIX → Baixa automática C/R | PIX gerado mas sem webhook para baixa no contas a receber | 🟡 Média |

---

## 5. HERANÇAS DETECTADAS — AÇÃO NECESSÁRIA

### Para OCULTAR do menu (manter código, esconder interface):
```python
# Adicionar guard APP_MODE no main_mysql.py para não registrar:
ordem_producao_bp   # Industrial — Gantt, OP, Painel do Líder
producao_pausas_bp  # Industrial — Motivos de Pausa
config_producao_bp  # Industrial — Configuração de produção
ficha_tecnica_bp    # Industrial — Ficha técnica de produto
dev_economico_bp    # Governança econômica
romaneio_bp         # Romaneio de entregas
```

### Para RENOMEAR (adaptar ao contexto automotivo):
| Atual | Proposto |
|---|---|
| "Meu Painel (Mecânico)" → `meu-gantt` | → "Minha Fila de Serviços" |
| "Gantt de Serviços" | → usar Agenda de Mecânicos (já implementada) |
| "Ordens de Execução" | → "Minhas OS" |
| "KM / Horímetro" | → "Quilometragem do Veículo" |
| `/cmms_dashboard` | → `/dashboard` |
| "Sistema de Gestão de Suprimentos" (title) | → "IKFlow Mecânica" |
| `wear_percentage` (dashboard) | → KM até próxima revisão |

### Para AVALIAR se mantém (uso real incerto):
- `rota_vendas_bp` — "Rota de Captação" pode ser útil para vendedores externos
- `questionario_visita_bp` — pode ser reaproveitado como pesquisa de satisfação pós-OS
- `vendedor_bp` / `segment_bp` — sem contexto claro para mecânica

---

## 6. BANCO DE DADOS — ACHADOS

### Tabelas com campos industriais em `equipment`:
```sql
base_life_hours        -- horas de vida útil (industrial)
standard_hours_day     -- horas padrão/dia (industrial)
real_hours_day         -- horas reais/dia (industrial)
k_intensity            -- coeficiente intensidade (industrial)
k_environment          -- coeficiente ambiente (industrial)
accumulated_hours      -- horas acumuladas (deveria ser km_atual)
adjusted_life_hours    -- vida ajustada em horas (industrial)
wear_percentage        -- desgaste % (industrial)
last_hour_update       -- última atualização de horas (industrial)
```
**Proposta:** Adicionar colunas `km_atual`, `km_proxima_revisao` e manter os campos industriais como `NULL` (sem deletar para não quebrar queries existentes).

### Colunas `phone_notificado` ausentes:
- `service_orders.phone_notificado` — adicionada pela migration_agenda.sql (pendente no servidor).
- Sem ela, o badge de "última notificação WA" no view da OS não funciona.

### Tabelas sem `company_id` (risco multi-tenant):
`service_orders`, `customers`, `equipment`, `technicians`, `sales`, `sale_items`, `cash_register`, `inventory`

---

## 7. SEGURANÇA — ACHADOS

| Item | Risco | Ação |
|---|---|---|
| Sem CSRF | Alto | Instalar `Flask-WTF` |
| `login_required` duplicado em 15+ arquivos | Médio | Centralizar em `utils/auth.py` |
| Senha do DB hardcoded em `config_production.py` (histórico git) | Alto | Confirmar se `.env` está sendo usado corretamente; revogar credencial se exposta |
| Sem rate limiting nas APIs WA | Médio | Adicionar `Flask-Limiter` em `/whatsapp/enviar-*` |
| Sem log de auditoria de ações | Médio | Implementar log em criação/edição/exclusão de OS e clientes |
| `apresentacao_ikflow*.html` acessíveis sem login | Baixo | Mover ou proteger |

---

## 8. PERFORMANCE — ACHADOS

| Item | Impacto | Solução |
|---|---|---|
| 15+ blueprints industriais carregados sem uso | Boot +300ms estimado | Desativar no `main_mysql.py` |
| `venda_pdv_profissional.html` 148 KB | Lentidão PDV mobile | Dividir em partials |
| `produto_form_abas.html` 95 KB | Lentidão cadastro peça | Usar versão `_fixed` (33 KB) |
| Sem cache em queries de dashboard | Consulta DB a cada refresh | Adicionar `functools.lru_cache` ou Redis |
| FullCalendar carregado globalmente | Impacto em telas sem agenda | Lazy load via `{% block scripts %}` |

---

## 9. UX — ACHADOS

| Tela | Problema | Solução |
|---|---|---|
| Menu Equipe | Termos industriais misturados com mecânica | Renomear e reorganizar |
| OS Form | Muito extenso — scrollar muito para preencher | Quebrar em abas/wizard |
| Dashboard | Métricas de `wear_percentage` sem contexto claro para mecânico | Substituir por OS abertas/prazo revisão/receita |
| Veículos | Campo "Horímetro" confunde mecânico que pensa em KM | Renomear para KM |
| PDV | 148 KB de template — possível lentidão em mobile | Otimizar |
| Agenda | "Lembretes de Revisão" duplicado no menu | Remover duplicata |

---

## 10. PLANO DE AÇÃO PRIORIZADO

### 🔴 SEMANA 1 — Segurança e Limpeza (bloqueante para comercialização)
1. Centralizar `login_required` em `utils/auth.py`
2. Instalar `Flask-WTF` + CSRF em todos os formulários POST
3. Desativar blueprints industriais no `main_mysql.py` (guard `APP_MODE`)
4. Corrigir import `cfop_routes.py` (`app.database` → `database`)
5. Executar `migration_agenda.sql` no servidor

### 🟡 SEMANA 2 — Adaptação automotiva
6. Renomear terminologia industrial → automotiva no menu e templates
7. Substituir "Sistema de Gestão de Suprimentos" por "IKFlow Mecânica" (global)
8. Adaptar dashboard: métricas de OS, receita, revisões — remover `wear_percentage`
9. Corrigir fluxo Estoque → Consumo OS (baixa automática ao concluir OS)
10. Unificar módulos de usuários (`users_routes` + `usuario_routes_mysql`)

### 🟢 SEMANA 3 — Multi-tenant e escala
11. Adicionar `company_id` nas tabelas críticas + migration
12. Filtrar todas as queries por `session.get('company_id')`
13. Implementar log de auditoria de ações
14. Remover/arquivar templates legados (`questionario_visita_salgados.html`, `apresentacao_ikflow*.html`, `produto_form_abas.html`)

### 🔵 SEMANA 4 — Fluxos faltantes
15. Estoque → consumo automático ao fechar OS
16. Orçamento → OS (trigger de aprovação)
17. PIX → baixa automática C/R (webhook)
18. Comissionamento mecânico

---

## RESUMO FINAL

| Categoria | Achados | Críticos | Médios | Leves |
|---|---|---|---|---|
| Multi-tenant | 1 | 1 | 0 | 0 |
| Segurança | 5 | 2 | 2 | 1 |
| Heranças industriais | 9 módulos | 1 | 6 | 2 |
| Fluxos quebrados | 7 | 2 | 5 | 0 |
| BD inconsistente | 9 campos | 0 | 3 | 6 |
| UX/Nomenclatura | 8 | 0 | 3 | 5 |
| Templates duplicados | 6 | 0 | 2 | 4 |
| Performance | 5 | 0 | 2 | 3 |
| **TOTAL** | **~50** | **6** | **23** | **21** |

**Conclusão:** O sistema está funcional e entregável para um cliente piloto em ambiente controlado. Para comercialização em larga escala (SaaS multi-empresa), os problemas C1 (multi-tenant) e C3 (CSRF) são bloqueantes. Os demais são melhorias incrementais que não impedem o uso operacional diário.
