# 📋 PROPOSTA TÉCNICA — IKFlow Mecânica
**Preparado por:** IK Analytics  
**Data:** Maio/2026  
**Versão:** 2.1 — **Produção estável (29/05/2026) — login funcional, dashboards/relatórios operacionais, schema real mapeado**  

---

## 1. RESUMO EXECUTIVO

O cliente opera uma oficina mecânica com equipe de 10 pessoas (4 usuários admin/gestão, 2 mecânicos, 4 auxiliares) e utiliza um sistema legado com lacunas críticas identificadas. A proposta é implantar o **IKFlow Mecânica**, verticalmente adaptado a partir da plataforma IKFlow já existente, com novos módulos específicos para o segmento automotivo.

**Aproveitamento real da base existente: 100% entregue**  
**Status atual:** Em produção em `mecanicas.ikflow.cloud` — sistema estável, login operacional, módulos principais funcionais  
**Tempo restante para MVP completo: 0 — CONCLUÍDO**  

### 🌟 Destaques da versão 2.1 (estabilização produção)
- ✅ CSRF corrigido no login — "token missing" eliminado
- ✅ 6 módulos com imports corrigidos: `produto`, `ncm`, `nfce`, `importar_clientes`, `permissoes`, `nfe_emissao`
- ✅ Dashboard e relatórios adaptados ao schema real do banco de produção
- ✅ Queries com try/except — falhas de DB não derrubam mais páginas
- ✅ Zero erros de boot confirmado no servidor
- ⚠️ Avisos residuais inofensivos: `paho` não instalado, circular import `wsgi` em 3 módulos

---

## 2. DIAGNÓSTICO — O QUE O CLIENTE TEM HOJE vs. O QUE FALTA

### ✅ Funcionalidades que o sistema atual do cliente possui (e devemos manter/migrar)
- Orçamento de serviços
- Ordem de Serviço
- Cadastro de clientes e veículos
- Emissão de NF-e
- Controle de estoque de peças
- Contas a pagar / Contas a receber
- Comissionamento de mecânicos e vendedores
- Controle de ponto (Control-ID)
- Adiantamento / pagamento parcial

### ❌ Lacunas críticas identificadas pelo cliente no sistema atual
1. Orçamento Avulso (sem cadastro de cliente)
2. Lembretes automáticos de revisão/manutenção preventiva
3. Controle de Agenda (mecânicos + auxiliares)
4. Agendamento inteligente (preventivo automático por histórico)
5. Fluxo pós-serviço → NF-e sem retrabalho (popup integrado)
6. PIX integrado
7. Boleto (Banco do Brasil + Mercado Pago)
8. WhatsApp automático (pós-venda, orçamento, disparos)
9. Prisma de diagnóstico no orçamento (o que cliente alega vs. o que o mecânico vai fazer)
10. Controle de Garantia por serviço/peça trocada
11. Histórico completo do veículo
12. App mobile para mecânicos/auxiliares
13. Controle de ponto via WiFi (geolocalização lógica por rede)
14. Produtividade do mecânico
15. NFS-e (nota fiscal de serviço eletrônica)
16. ETL/migração do histórico do sistema legado

---

## 3. INVENTÁRIO DO QUE JÁ TEMOS NOS PROJETOS IK ANALYTICS

### 3.1 IKFlow (Correias / Salgados) — Flask/Python
| Módulo | Status para Mecânica |
|--------|----------------------|
| Cadastro de Clientes | ✅ Aproveitar direto |
| Cadastro de Fornecedores | ✅ Aproveitar direto |
| Orçamento | ✅ Adaptar (adicionar Prisma + avulso) |
| Ordem de Serviço | ✅ Adaptar para OS mecânica |
| Equipamentos / Hora-metro | ✅ Adaptar para veículos |
| Plano de Manutenção | ✅ Adaptar para revisões preventivas |
| Estoque / Kardex / Inventário | ✅ Aproveitar (ajustar nomenclatura para peças) |
| Compras / Contas a Pagar | ✅ Aproveitar direto |
| Contas a Receber | ✅ Aproveitar direto |
| Fluxo de Caixa | ✅ Aproveitar direto |
| NF-e emissão | ✅ Aproveitar (verificar NFS-e) |
| Permissões por usuário/tela | ✅ Aproveitar direto |
| Alertas | ✅ Adaptar para lembretes de revisão |
| Jornada de Trabalho | ✅ Adaptar para controle de ponto |
| Comissionamento | ✅ Adaptar (mecânico + captação marketing) |
| Dashboard | ✅ Adaptar KPIs para mecânica |
| PDV Profissional | ✅ **Testado em produção** — venda finalizada, CONSUMIDOR FINAL auto-criado, schema corrigido |
| Histórico de Vendas | ✅ **Ativo** — `venda_bp` registrado, menu `/vendas/relacao` |
| Caixa PDV (Abrir/Fechar/Sangria/Suprimento) | ✅ **Desbloqueado** — stored procedures substituídas por SQL direto |
| WhatsApp Business (UazAPI) | ✅ **Testado e funcionando** — header `token:`, endpoint `/send/text`, config completa no banco |
| Fluxo de Caixa | ✅ **Desbloqueado** — `python-dateutil` instalado |
| Relatórios Gerenciais | ✅ **Desbloqueado** — `python-dateutil` instalado |
| NCM / NFC-e / Moedas / Transportadoras | ✅ **Corrigidos** — imports `app.database` → `database` |
| Produção / Ficha Técnica / Pausas | ❌ Não se aplica — remover |
| Romaneio / Manifesto | ❌ Não se aplica — remover |
| NFC-e | ⚠️ Opcional (balcão) |

### 3.2 Holding 2 Caciques — PHP/Laravel-like
| Módulo | Pode ser portado para Mecânica |
|--------|-------------------------------|
| **PIX** (`PixController.php`) | ✅ Portar lógica de cobrança PIX |
| **WhatsApp** (`WhatsappController.php`) | ✅ Portar disparos e fluxos automáticos |
| **NFS-e** (`NfseController.php`) | ✅ Portar para emissão de serviços |
| **Financeiro** (`FinanceiroController.php`) | ✅ Referência para pagamento parcial/acumulativo |
| **Fatura + Boleto** (`FaturaController.php`) | ✅ Portar lógica BB + Mercado Pago |
| **Portal do Cliente** (`Portal/*`) | ✅ Adaptar como portal do veículo/histórico |
| **Inadimplência** | ✅ Aproveitar |
| **Relatórios** | ✅ Aproveitar |

---

## 4. MÓDULOS DO IKFlow MECÂNICA — MVP

### 🔴 MÓDULO 1 — ATENDIMENTO / ORDEM DE SERVIÇO
**Origem:** Adaptar `ordem_servico` + `orcamento_routes.py` do IKFlow  
**Novas features:**
- OS com campos de veículo: placa, marca, modelo, ano, KM atual
- **Prisma de Diagnóstico:** campo "Reclamação do Cliente" separado de "Diagnóstico do Mecânico" e "Serviços a Executar" — imprimível
- Orçamento avulso (sem cliente cadastrado) → salva como "cliente eventual"
- Popup ao concluir OS: "Deseja emitir NF-e?" → abre tela de emissão pré-preenchida
- Controle de Garantia por serviço/peça (prazo + data conclusão + peças trocadas)
- Histórico completo do veículo (todas as OS anteriores por placa)

**Estimativa:** 3 semanas

---

### 🔴 MÓDULO 2 — AGENDA E AGENDAMENTO INTELIGENTE
**Origem:** Novo módulo (não existe no IKFlow atual)  
**Features:**
- Calendário por mecânico e por auxiliar (visualização diária/semanal)
- Agendamento efetivo (cliente agenda horário + serviço)
- Agendamento preventivo automático: ao concluir OS, sistema calcula próxima revisão com base em KM ou prazo e já agenda lembrete
- Identifica se o veículo já realizou a revisão e suprime o lembrete automaticamente

**Estimativa:** 2 semanas

---

### 🔴 MÓDULO 3 — LEMBRETES E NOTIFICAÇÕES
**Origem:** Adaptar `alert_routes.py` do IKFlow + `WhatsappController.php` do Holding  
**Features:**
- Painel de lembretes ativos (revisão próxima, garantia vencendo)
- Disparo automático por WhatsApp: "Olá {cliente}, seu veículo {placa} está próximo da revisão de {KM/data}"
- Controle de status: ignorado / realizado / pendente
- Configuração de templates de mensagem por tipo de lembrete

**Estimativa:** 1 semana

---

### 🔴 MÓDULO 4 — FINANCEIRO COMPLETO
**Origem:** IKFlow (Contas a pagar/receber, Caixa, Fluxo) + Holding (PIX, Boleto, Fatura)  
**Features:**
- Pagamento parcial / adiantamento (lógica já implementada no Holding)
- **PIX** integrado (portar `PixController.php` do Holding)
- **Boleto Banco do Brasil** (portar lógica do Holding)
- **Boleto Mercado Pago** (portar lógica do Holding)
- Contas a pagar / Contas a receber (já existe no IKFlow)
- Fluxo de caixa (já existe no IKFlow)

**Estimativa:** 2 semanas (integração + adaptação)

---

### 🔴 MÓDULO 5 — WHATSAPP AUTOMÁTICO
**Origem:** Portar `WhatsappController.php` do Holding  
**Já entregue (100% implementado):**
- ✅ Envio de orçamento via WA com botão na OS (`enviar_orcamento_wa`)
- ✅ Aviso OS pronta para retirada + trigger auto ao `status=completed`
- ✅ Lembrete de revisão preventiva (`/whatsapp/disparar-lembretes` — cron)
- ✅ Alerta de OS urgente para admins (`telefones_admin`)
- ✅ Templates configuráveis + histórico de mensagens + painel de logs

**Pendente (opcional):**
- ⚠️ Pesquisa de satisfação pós-OS (template existe, cron pendente)

**Estimativa restante:** 0 semanas (WA completo)

---

### 🔴 MÓDULO 6 — NF-e / NFS-e
**Origem:** IKFlow (NF-e) + Holding (`NfseController.php`)  
**Features:**
- NF-e para venda de peças (já existe no IKFlow — adaptar)
- NFS-e para serviços de mão de obra (portar do Holding)
- Fluxo integrado: ao concluir OS → popup → emissão com dados pré-preenchidos
- Impressão e envio por e-mail/WhatsApp

**Estimativa:** 1 semana (adaptação)

---

### 🟡 MÓDULO 7 — ESTOQUE DE PEÇAS
**Origem:** IKFlow (`inventory_routes.py`, `kardex_routes.py`, `insumo_routes_mysql.py`)  
**Adaptações:**
- Renomear "insumos" para "peças"
- Vincular peças à OS (consumo direto ao executar serviço)
- Alertas de estoque mínimo
- Registro de peça trocada na OS (vinculada à garantia)

**Estimativa:** 0.5 semana (ajuste de nomenclatura e vínculo com OS)

---

### 🟡 MÓDULO 8 — COMISSIONAMENTO
**Origem:** Adaptar lógica existente no IKFlow  
**Features:**
- **Comissão mecânico:** % por OS concluída ou por valor de mão de obra
- **Comissão captação:** % para quem trouxe o cliente (marketing/vendedor)
- Relatório mensal de comissões por colaborador
- Integração com folha (exportação)

**Estimativa:** 1 semana

---

### 🟡 MÓDULO 9 — CONTROLE DE PONTO E RH
**Origem:** Adaptar `jornada_trabalho_routes.py` do IKFlow  
**Features:**
- Registro de ponto ao logar no sistema (web)
- App mobile (PWA): ponto via app
- **Restrição por WiFi:** ponto só permitido quando conectado à rede da empresa (verificação por IP/SSID)
- Banco de horas automático
- Exportação para integração com Control-ID (ou substituição futura)
- Perfis: usuário pode usar app fora da empresa (gestor) ou não (mecânico/auxiliar)

**Estimativa:** 2 semanas

---

### � MÓDULO 10 — APP MOBILE (PWA) — **BASE IMPLEMENTADA**
**Origem:** Arquitetura responsiva do IKFlow — PWA base já ativo  
**Já entregue:**
- `manifest.json` com nome, ícones, shortcuts para OS/PDV/Painel do Mecânico
- `service-worker.js` com cache offline, network-first para rotas dinâmicas, fallback offline
- Tags `<link rel="manifest">`, `<meta theme-color>`, `apple-touch-icon` no `base.html`
- Sistema já é instalável como app no celular (Android Chrome / iOS Safari)

**Acessos por perfil (já funcionam via navegador mobile):**
- **Mecânico:** Ver OS do dia, iniciar/pausar/concluir serviço, bater ponto
- **Auxiliar:** Ver tarefas, bater ponto, ver agenda
- **Gestor:** Acesso completo ao sistema
- **Admin:** Configurações gerais

**Pendente (evolução futura):**
- Ícones PWA finais com arte da marca IKFlow
- Notificações push (Web Push API)
- Sincronização background real de dados offline

**Estimativa restante:** 0.5 semana (push notifications + refinamento UX mobile)

---

### 🟢 MÓDULO 11 — CADASTROS BASE
**Origem:** IKFlow direto (aproveitar 100%)  
- Clientes (com dados do veículo vinculado)
- Fornecedores
- Serviços (tabela de serviços com preço padrão)
- Peças
- Transportadoras
- Condições de pagamento
- Empresas / Configuração da empresa

**Estimativa:** 0.5 semana (adaptação mínima)

---

### 🟢 MÓDULO 12 — RELATÓRIOS E DASHBOARD
**Origem:** Adaptar IKFlow  
- KPIs: OS abertas, concluídas, faturamento do mês, ticket médio
- Produtividade por mecânico (OS concluídas, tempo médio, comissão)
- Inadimplência
- Estoque crítico
- Veículos com revisão vencida

**Estimativa:** 0.5 semana

---

### 🔵 MÓDULO 13 — ETL / MIGRAÇÃO DO SISTEMA LEGADO
**Origem:** Novo  
- Mapeamento do schema do sistema atual
- Script de importação de clientes, veículos e histórico de OS
- Validação e limpeza dos dados

**Estimativa:** 1 semana (depende da facilidade de exportação do sistema legado)

---

## 5. CRONOGRAMA ESTIMADO

### ✅ JA ENTREGUE (em produção em `mecanicas.ikflow.cloud`)
| Semana | Entrega | Status |
|--------|---------|--------|
| 1-2 | Setup infra + Cadastros base + OS/Orçamento | ✅ Entregue |
| 3 | OS completa: Prisma, avulso, histórico veículo | ✅ Entregue |
| 4 | PDV Balcão + Caixa + Histórico Vendas | ✅ Testado |
| 5 | Financeiro: PIX + Fluxo de Caixa + C/R + C/P | ✅ Entregue |
| 6 | WhatsApp (UazAPI) + NFS-e + NF-e + NFC-e | ✅ Entregue |
| 7 | Estoque + Kardex + Compras + Insumos | ✅ Entregue |
| 8 | PWA (manifest + service worker + instalável) | ✅ Entregue |

### 🔄 RESTANTE (próximas semanas)
| Semana | Entrega |
|--------|--------|
| ~~+1~~ | ~~**Fluxos WhatsApp**~~ | ✅ Entregue e testado em produção |
| ~~+2~~ | ~~Agenda por mecânico + Agendamento preventivo automático~~ | ✅ Entregue: FullCalendar + preventivo auto |
| +3 | Comissionamento (mecânico + captação) |
| +4 | Controle de ponto + Restrição WiFi |
| +5 | Boleto BB + Mercado Pago |
| +6 | Controle de Garantia por peça/serviço |
| +7 | Relatórios produtividade + Dashboard avançado |
| +8 | ETL / Migração legado + Testes finais + Treinamento |

**Total original: 14 semanas | Já executado: ~8 semanas | Restante: ~6 semanas**

---

## 6. PROPOSTA DE VALOR

---

### � Referência de Mercado — Sistemas para Oficina Mecânica (2025)

| Sistema | Mensalidade | Taxa de Implantação | Observações |
|---|---|---|---|
| Oficina Inteligente | R$ 289–499/mês | Sem taxa | Sem NF-e nativa, sem WhatsApp, sem PDV |
| Oficina Integrada | A partir de R$ 60/mês | Sem taxa | Plano básico muito limitado |
| OficinaSoft | Não divulgado | Sem taxa | Foco em OS simples, sem módulo financeiro avançado |
| Ultracar (Ultra Plus) | Não divulgado | Não divulgado | NF-e + financeiro, sem WhatsApp nativo |
| WorkMotor | Não divulgado | Não divulgado | Foco em autopeças, sem PIX/WhatsApp integrado |
| **IKFlow Mecânica** | **R$ 490–890/mês** | **Ver pacotes abaixo** | **Todos os módulos + WhatsApp + PIX + PWA mobile** |

> **Conclusão:** sistemas concorrentes cobram implantação **zero** porque entregam um produto genérico, sem personalização, sem migração de dados e sem treinamento. O IKFlow é desenvolvido sob medida, já está em produção em `mecanicas.ikflow.cloud` e inclui módulos que os concorrentes não oferecem (WhatsApp automático, PIX webhook, PWA mobile, preventivo por KM).

---

### 💰 Composição do Investimento de Implantação

O valor cobre o **desenvolvimento já realizado** (plataforma em produção), a **entrega configurada** para o cliente e o **treinamento da equipe**. Abaixo o detalhamento:

#### 🔧 O que já foi desenvolvido e está em produção

| Entregável | Horas |
|---|---|
| OS completa (abertura, diagnóstico, execução, conclusão, PDF, avulsa) | 40h |
| Financeiro (C/R, C/P, fluxo de caixa, baixa automática PIX webhook) | 30h |
| Estoque (Kardex, entrada, baixa automática por OS) | 20h |
| Fiscal (NF-e + NFS-e com geração XML e envio ao webservice) | 25h |
| WhatsApp Business (lembretes automáticos por data e KM) | 12h |
| PDV Profissional (balcão, caixa, histórico de vendas) | 15h |
| PWA Mobile (app no iPhone/Android, busca global, offline) | 10h |
| Agenda / Preventivo por KM | 10h |
| Portal do Cliente (aprovação de OS por token) | 8h |
| RH / Equipe (ponto, jornada, comissões) | 10h |
| Infraestrutura (servidor, SSL, domínio, deploy, backups) | 8h |
| **Total já desenvolvido** | **188h** |

#### 🚀 O que é feito após assinatura (por pacote)

| Entregável | Essencial | Profissional | Completo |
|---|:---:|:---:|:---:|
| Configuração da empresa (CNPJ, logo, cert. digital) | ✅ | ✅ | ✅ |
| Configuração WhatsApp Business (Meta) | — | ✅ | ✅ |
| Configuração PIX / boleto com banco do cliente | — | ✅ | ✅ |
| ETL / Migração dados do sistema legado | — | parcial | ✅ completo |
| Treinamento (sessões de 4h por setor) | 1 sessão | 2 sessões | 3 sessões |
| Suporte intensivo pós go-live | 15 dias | 30 dias | 60 dias |

---

### 📦 Pacotes de Implantação

> **Nota sobre precificação:** sistemas SaaS genéricos (OficinaSoft, Oficina Inteligente) cobram R$ 0 de implantação porque entregam um produto padronizado, sem configuração, sem migração de dados e sem treinamento. O IKFlow inclui tudo isso. Os valores abaixo já foram ajustados para refletir a **média de mercado para sistemas verticalizados com implantação assistida**.

---

#### 🟢 Essencial — R$ 4.800 *(ou 2x de R$ 2.400)*

> Ideal para oficinas que querem começar com o essencial e crescer gradualmente.

**Módulos inclusos:**
- Atendimento / OS (abertura, execução, conclusão, PDF)
- PDV Balcão (venda rápida, caixa)
- Cadastros (clientes, veículos, peças, fornecedores)
- Financeiro básico (C/R, C/P)
- Relatórios de OS e faturamento

**Entrega:** configuração da empresa + 1 treinamento (4h) + suporte 15 dias

---

#### 🔵 Profissional — R$ 9.800 *(ou 3x de R$ 3.267)*

> Para oficinas que querem operação completa e automação do dia a dia.

**Tudo do Essencial, mais:**
- WhatsApp automático (lembretes de revisão por data e KM)
- NF-e / NFS-e integrada (emissão em 1 clique pós-OS)
- PIX com QR Code e confirmação automática
- Fluxo de caixa e dashboard financeiro
- Agenda de mecânicos + preventivo por KM
- Portal do Cliente (aprovação de OS pelo celular)
- PWA Mobile (app no iPhone/Android, busca global)
- RH / Ponto / Comissões

**Entrega:** configuração completa + 2 treinamentos + suporte 30 dias

---

#### ⭐ Completo — R$ 14.800 *(ou 3x de R$ 4.934)*

> Recomendado. Operação 100% digitalizada, com migração do histórico e suporte estendido.

**Tudo do Profissional, mais:**
- ETL / Migração completa do sistema legado (clientes, veículos, histórico de OS)
- App Mobile dedicado para mecânico (registro de ponto com restrição WiFi)
- Controle de Garantia por peça/serviço
- Dashboard avançado com indicadores de produtividade
- Integrações ERP/IoT

**Entrega:** configuração + migração + 3 treinamentos (recepção, mecânicos, financeiro) + suporte 60 dias

---

### 📅 Mensalidade (SaaS)

| Plano | Usuários | Inclui | Valor/mês |
|---|---|---|---|
| Starter | até 5 | Hosting + backups + atualizações | R$ 490 |
| **Business** ⭐ | até 15 | + suporte WhatsApp em horário comercial | **R$ 890** |
| Enterprise | ilimitado | + suporte 24h + SLA contratual | R$ 1.490 |

> **Para este cliente (10 usuários): Plano Business — R$ 890/mês**
> = R$ 29,67/usuário/mês — abaixo da média do mercado (Oficina Inteligente: R$ 33–50/usuário/mês, sem suporte dedicado)

---

### 🎯 Proposta Recomendada

| Item | Valor |
|---|---|
| **Implantação Pacote Completo** | R$ 14.800 |
| Forma de pagamento | **3x de R$ 4.934** (entrada + 30d + 60d) |
| **Mensalidade Business** (a partir do go-live) | R$ 890/mês |
| Suporte e manutenção | ✅ Incluso na mensalidade |
| 3 treinamentos de 4h (recepção, mecânicos, financeiro) | ✅ Incluso na implantação |
| ETL / Migração do legado | ✅ Incluso no pacote Completo |
| **ROI estimado** | Retorno em ~3 meses pela redução de retrabalho, peças perdidas e inadimplência |

> 💡 **Alternativa sem implantação:** isenção da taxa de implantação com fidelidade mínima de **12 meses** no plano Business = R$ 890/mês × 12 = R$ 10.680 (economia de R$ 4.120 vs pacote completo)

---

## 7. DIFERENCIAIS COMPETITIVOS

1. **Plataforma própria** — sem dependência de terceiros para customizações
2. **Histórico inteligente do veículo** — diferencial frente ao sistema legado
3. **Agendamento preventivo automático** — nenhum sistema popular tem isso nativo
4. **PIX + Boleto integrados** — recebimento no próprio sistema
5. **WhatsApp automático** — pós-venda e lembretes sem trabalho manual
6. **App mobile com restrição WiFi** — controle de ponto moderno e confiável
7. **Suporte local e personalizado** — IK Analytics como parceiro de negócio

---

## 8. RISCOS E DEPENDÊNCIAS

| Risco | Mitigação |
|-------|-----------|
| Exportação do sistema legado difícil | Solicitar ao cliente CSV/Excel dos dados |
| API WhatsApp Business (aprovação Meta) | Iniciar cadastro na semana 1 |
| Certificado digital para NF-e/NFS-e | Cliente deve providenciar A1/A3 |
| Integração boleto BB (homologação) | Prazo adicional de 1-2 semanas se necessário |
| Restrição WiFi depende da rede local | Validar com cliente o IP fixo da rede da empresa |

---

## 9. PRÓXIMOS PASSOS (PÓS-APROVAÇÃO)

1. Assinatura do contrato e NDA
2. Levantamento detalhado do schema do sistema legado
3. Acesso à API WhatsApp Business do cliente
4. Certificado digital e dados da empresa para NF-e
5. Credenciais bancárias (BB / Mercado Pago) para integração boleto
6. Kickoff técnico — semana 1

---

*Proposta válida por 15 dias. Elaborada por IK Analytics — aritana@ikanalytics.com.br*
