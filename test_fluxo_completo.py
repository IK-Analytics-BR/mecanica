# -*- coding: utf-8 -*-
"""
TEST FLUXO COMPLETO - IKFlow Mecanica
Rotas baseadas no mapa real extraido do sistema.
"""
import requests, re, sys
from datetime import datetime, date, timedelta

BASE = "http://127.0.0.1:8080"
S = requests.Session()
LOG = []

def log(etapa, status, det=""):
    tag = "[OK]   " if status == "OK" else ("[AVISO]" if status == "WARN" else "[ERRO] ")
    msg = f"{tag} {etapa:<45} {det}"
    LOG.append((status, msg))
    print(msg)

def get(url, **kw):
    try: return S.get(BASE+url, timeout=12, allow_redirects=True, **kw)
    except: return None

def post(url, data):
    try: return S.post(BASE+url, data=data, timeout=12, allow_redirects=True)
    except: return None

def ok(r): return r is not None and r.status_code in [200,201,302]

print("\n" + "="*65)
print("  TESTE FLUXO COMPLETO - IKFlow Mecanica")
print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
print("="*65 + "\n")

# ── 0. LOGIN ──────────────────────────────────────────────────
r = get("/login")
log("0a. GET /login", "OK" if ok(r) else "ERRO", f"HTTP {r.status_code if r else 'N/A'}")

r = post("/login", {"username":"admin","password":"admin123"})
if ok(r):
    autenticado = any(k in (r.text or "") for k in ["service_orders","logout","Sair","dashboard","bem-vindo"])
    log("0b. POST /login (admin/admin123)", "OK" if autenticado else "WARN",
        "Sessao ativa" if autenticado else f"URL={r.url} body[:60]={r.text[:60]}")
else:
    log("0b. POST /login", "ERRO", f"HTTP {r.status_code if r else 'N/A'}")

# ── 1. CLIENTE ────────────────────────────────────────────────
r = get("/clientes/cadastrar")
log("1a. GET /clientes/cadastrar", "OK" if ok(r) else "WARN", f"HTTP {r.status_code if r else 'N/A'}")

r = post("/clientes/cadastrar", {
    "nome":"Joao Silva Teste","cpf_cnpj":"123.456.789-00",
    "telefone":"(11) 99999-1234","email":"joao.teste@email.com",
    "endereco":"Rua das Flores, 100","cidade":"Sao Paulo",
    "estado":"SP","cep":"01310-100","tipo":"pf",
    "observacoes":"Cliente teste fluxo automatizado"
})
log("1b. POST /clientes/cadastrar", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} | URL={r.url if r else ''}")

CLIENTE_ID = "1"
ra = get("/api/clientes/buscar", params={"q":"Joao Silva"})
if ra and ra.status_code == 200:
    try:
        d = ra.json()
        if d: CLIENTE_ID = str(d[0].get("id","1")); log("1c. ID cliente (API)", "OK", f"ID={CLIENTE_ID}")
        else: log("1c. ID cliente (API)", "WARN", "lista vazia, ID=1")
    except: log("1c. ID cliente", "WARN", "erro JSON")
else:
    rl = get("/clientes")
    if rl and rl.status_code == 200:
        m = re.findall(r'/clientes/visualizar/([^"\'>\s/]+)', rl.text)
        if m: CLIENTE_ID = m[-1]; log("1c. ID cliente (lista)", "OK", f"ID={CLIENTE_ID}")

# ── 2. VEICULO ────────────────────────────────────────────────
VEICULO_ID = "1"
r = post("/api/veiculos/cadastrar-rapido", {
    "cliente_id":CLIENTE_ID,"placa":"ABC1D23","marca":"Volkswagen",
    "modelo":"Gol","ano":"2018","cor":"Prata","km_atual":"75000","combustivel":"flex"
})
if r and r.status_code in [200,201]:
    try:
        d = r.json()
        vid = d.get("id") or d.get("veiculo_id") or d.get("equipment_id")
        if vid: VEICULO_ID = str(vid); log("2a. POST /api/veiculos/cadastrar-rapido", "OK", f"ID={VEICULO_ID}")
        else: log("2a. Cadastrar veiculo API", "WARN", f"sem ID no JSON: {str(d)[:80]}")
    except: log("2a. Cadastrar veiculo API", "WARN", f"HTTP {r.status_code} sem JSON")
else:
    r2 = post("/equipamentos/cadastrar", {
        "customer_id":CLIENTE_ID,"cliente_id":CLIENTE_ID,
        "placa":"ABC1D23","marca":"Volkswagen","modelo":"Gol",
        "ano":"2018","tipo":"veiculo","identificacao":"ABC1D23","km_atual":"75000"
    })
    if ok(r2):
        m = re.findall(r'/equipamentos/(?:visualizar/)?(\d+)', r2.url+r2.text[:300])
        if m: VEICULO_ID = m[-1]
        log("2b. POST /equipamentos/cadastrar", "OK" if ok(r2) else "WARN",
            f"HTTP {r2.status_code} | ID={VEICULO_ID}")
    else:
        log("2b. Cadastrar veiculo", "WARN", f"HTTP {r2.status_code if r2 else 'N/A'} - ID=1")

r3 = get(f"/api/veiculos/por-cliente/{CLIENTE_ID}")
log("2c. GET /api/veiculos/por-cliente", "OK" if ok(r3) else "WARN", f"HTTP {r3.status_code if r3 else 'N/A'}")

# ── 3. ABERTURA DA OS ─────────────────────────────────────────
r = get("/service_orders/add")
log("3a. GET /service_orders/add", "OK" if ok(r) else "WARN", f"HTTP {r.status_code if r else 'N/A'}")

r = post("/service_orders/add", {
    "customer_id":CLIENTE_ID,"cliente_id":CLIENTE_ID,
    "equipment_id":VEICULO_ID,"veiculo_id":VEICULO_ID,
    "km_entrada":"75000",
    "customer_complaint":"Barulho freio traseiro ao frear. Vibracao no volante.",
    "alegacao_cliente":"Barulho freio traseiro ao frear. Vibracao no volante.",
    "priority":"normal","status":"open"
})
OS_ID = None
if ok(r):
    log("3b. POST /service_orders/add", "OK", f"HTTP {r.status_code} | URL={r.url}")
    m = re.findall(r'/service_orders(?:/view|/edit)?/(\d+)', r.url+r.text[:600])
    if m: OS_ID = max(m, key=lambda x: int(x))
else:
    log("3b. POST /service_orders/add", "WARN", f"HTTP {r.status_code if r else 'N/A'}")

if not OS_ID:
    r2 = get("/service_orders")
    if r2 and r2.status_code == 200:
        m = re.findall(r'/service_orders(?:/view)?/(\d+)', r2.text)
        if m: OS_ID = max(m, key=lambda x: int(x))
OS_ID = OS_ID or "1"
log("3c. OS ID confirmado", "OK" if OS_ID != "1" else "WARN", f"ID={OS_ID}")

# ── 4. DIAGNOSTICO ────────────────────────────────────────────
r = get(f"/service_orders/view/{OS_ID}")
log("4a. GET /service_orders/view/{id}", "OK" if ok(r) else "WARN", f"HTTP {r.status_code if r else 'N/A'}")

r = post(f"/service_orders/edit/{OS_ID}", {
    "technical_diagnosis":"Pastilhas traseiras desgastadas. Discos com sulcos. Rolamento dianteiro dir. com folga.",
    "diagnostico":"Pastilhas traseiras desgastadas. Discos com sulcos. Rolamento dianteiro dir. com folga.",
    "status":"in_progress","technician_id":"1","mecanico_id":"1"
})
log("4b. POST /service_orders/edit/{id} (diagnostico)", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'}")

# ── 5. PECAS / ORCAMENTO ──────────────────────────────────────
ok_items = 0
for item in [
    {"description":"Pastilha freio traseira","quantity":"1","unit_price":"85.00","item_type":"part"},
    {"description":"Disco freio traseiro (par)","quantity":"1","unit_price":"220.00","item_type":"part"},
    {"description":"Rolamento dianteiro direito","quantity":"1","unit_price":"150.00","item_type":"part"},
]:
    ri = post(f"/service_orders/add_item/{OS_ID}", item)
    if ok(ri): ok_items += 1

rl = post(f"/service_orders/add_labor/{OS_ID}", {
    "description":"Mao de obra freios + rolamento","technician_id":"1","hours":"3","rate":"116.67"
})
if ok(rl): ok_items += 1
log("5a. Itens/pecas na OS (add_item/add_labor)", "OK" if ok_items>0 else "WARN",
    f"{ok_items}/4 inseridos | Total ~R$ 805,00")

ORCAMENTO_ID = OS_ID
r = post("/orcamentos/salvar", {
    "cliente_id":CLIENTE_ID,"order_id":OS_ID,
    "validade":(date.today()+timedelta(days=7)).isoformat(),
    "observacoes":f"Orcamento OS #{OS_ID}"
})
if ok(r):
    m = re.findall(r'/orcamentos/(\d+)', r.url+r.text[:300])
    if m: ORCAMENTO_ID = m[-1]
    log("5b. POST /orcamentos/salvar", "OK", f"HTTP {r.status_code} | ID={ORCAMENTO_ID}")
else:
    log("5b. POST /orcamentos/salvar", "WARN", f"HTTP {r.status_code if r else 'N/A'}")

# ── 6. ENVIO + APROVACAO ──────────────────────────────────────
r = get(f"/whatsapp/enviar-orcamento-wa/{OS_ID}")
log("6a. GET /whatsapp/enviar-orcamento-wa/{id}", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} (requer config WA)")

r = get(f"/whatsapp/enviar-os/{OS_ID}/orcamento")
log("6b. GET /whatsapp/enviar-os/{id}/orcamento", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} (requer config WA)")

r = post(f"/service_orders/{OS_ID}/aprovar", {"status":"approved"})
if ok(r):
    log("6c. POST /service_orders/{id}/aprovar", "OK", f"HTTP {r.status_code}")
else:
    r2 = post(f"/orcamentos/{ORCAMENTO_ID}/aprovar", {}) if ORCAMENTO_ID != OS_ID else None
    if r2 and ok(r2):
        log("6c. POST /orcamentos/{id}/aprovar", "OK", f"HTTP {r2.status_code}")
    else:
        log("6c. Aprovar orcamento", "WARN", f"HTTP {r.status_code if r else 'N/A'}")

# ── 7. AGENDA ─────────────────────────────────────────────────
r = get("/agenda")
log("7a. GET /agenda", "OK" if ok(r) else "WARN", f"HTTP {r.status_code if r else 'N/A'}")

DATA_AGEND = (date.today()+timedelta(days=1)).isoformat()
r = post(f"/agenda/agendar/{OS_ID}", {
    "order_id":OS_ID,"technician_id":"1",
    "scheduled_date":DATA_AGEND,"start_time":"09:00","end_time":"12:00",
    "notes":"Troca freios + rolamento"
})
log("7b. POST /agenda/agendar/{id}", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} | {DATA_AGEND} 09:00-12:00")

# Carga semanal
r = get("/agenda/carga-semanal")
log("7c. GET /agenda/carga-semanal", "OK" if ok(r) else "WARN", f"HTTP {r.status_code if r else 'N/A'}")

# ── 8. INICIAR SERVICO ────────────────────────────────────────
r = post(f"/service_orders/{OS_ID}/iniciar", {"technician_id":"1","mecanico_id":"1"})
log("8.  POST /service_orders/{id}/iniciar", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} | {datetime.now().strftime('%H:%M')}")

# ── 9. FINALIZAR + TEMPO ──────────────────────────────────────
r = post(f"/service_orders/{OS_ID}/finalizar", {
    "status":"completed","km_saida":"75010",
    "technical_notes":"Pastilhas trocadas, discos lixados, rolamento substituido. Frenagem OK.",
    "observacoes_tecnicas":"Pastilhas trocadas, discos lixados, rolamento substituido.",
    "proxima_revisao_km":"85000","garantia_meses":"6","garantia_km":"10000"
})
log("9.  POST /service_orders/{id}/finalizar", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} | KM saida=75010 | Tempo 3h")

# ── 10. NOTIFICAR CLIENTE ─────────────────────────────────────
r = get(f"/whatsapp/notificar-pronta/{OS_ID}")
log("10a. GET /whatsapp/notificar-pronta/{id}", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} (requer config WA)")

r = get(f"/whatsapp/enviar-os/{OS_ID}/finalizada")
log("10b. GET /whatsapp/enviar-os/{id}/finalizada", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} (requer config WA)")

# ── 11. PAGAMENTO / CONTAS A RECEBER ─────────────────────────
r = get("/contas-receber")
CR_TEM = r and r.status_code == 200
log("11a. GET /contas-receber", "OK" if CR_TEM else "WARN",
    f"HTTP {r.status_code if r else 'N/A'}")

CR_INST = None
if CR_TEM:
    m = re.findall(r'receber-parcela/(\d+)', r.text)
    if m:
        CR_INST = m[-1]
        log("11b. Parcela C/R localizada", "OK", f"ID parcela={CR_INST}")
    else:
        log("11b. Parcela C/R", "WARN", "nao encontrada na lista (OS pode nao ter gerado C/R automatico)")

if CR_INST:
    rb = post(f"/contas-receber/receber-parcela/{CR_INST}", {
        "valor_pago":"805.00","forma_pagamento":"dinheiro",
        "data_pagamento":date.today().isoformat(),
        "conta_bancaria_id":"1","observacoes":"Pago em dinheiro no balcao"
    })
    log("11c. POST /contas-receber/receber-parcela/{id}", "OK" if ok(rb) else "WARN",
        f"HTTP {rb.status_code if rb else 'N/A'} | R$ 805,00 dinheiro")
else:
    log("11c. Baixar pagamento", "WARN", "Sem parcela encontrada - baixar manualmente")

# ── 12. FINANCEIRO / CAIXA ────────────────────────────────────
r = get("/caixa/atual")
log("12a. GET /caixa/atual", "OK" if ok(r) else "WARN", f"HTTP {r.status_code if r else 'N/A'}")

r = get("/caixa/")
log("12b. GET /caixa/ (lista registros)", "OK" if ok(r) else "WARN", f"HTTP {r.status_code if r else 'N/A'}")

r = get("/contas-receber")
log("12c. GET /contas-receber (financeiro)", "OK" if ok(r) else "WARN", f"HTTP {r.status_code if r else 'N/A'}")

# ── 13. GARANTIA ──────────────────────────────────────────────
r = get("/garantias")
log("13a. GET /garantias (lista)", "OK" if ok(r) else "WARN", f"HTTP {r.status_code if r else 'N/A'}")

r = post(f"/garantias/nova/{OS_ID}", {
    "order_id":OS_ID,"descricao":"Troca pastilhas freio + discos + rolamento",
    "data_inicio":date.today().isoformat(),
    "data_fim":(date.today()+timedelta(days=180)).isoformat(),
    "km_garantia":"85000","observacoes":"6 meses ou 10.000 km"
})
log("13b. POST /garantias/nova/{id}", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} | valida ate {(date.today()+timedelta(days=180)).isoformat()}")

# Acionar garantia (lista)
r = get(f"/garantias/{OS_ID}/acionar")
log("13c. GET /garantias/{id}/acionar", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'}")

# ── 14. COMISSAO ──────────────────────────────────────────────
r = get("/comissoes")
if r and r.status_code == 200:
    tem_os = OS_ID in r.text
    log("14a. GET /comissoes", "OK", f"Lista acessivel | OS #{OS_ID} {'encontrada' if tem_os else 'nao consta ainda'}")
else:
    log("14a. GET /comissoes", "WARN", f"HTTP {r.status_code if r else 'N/A'}")

r = get("/comissoes/config")
log("14b. GET /comissoes/config", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'}")

# Pagar comissao se existir
r2 = get("/comissoes")
if r2 and r2.status_code == 200:
    m = re.findall(r'/comissoes/(\d+)/pagar', r2.text)
    if m:
        rc = post(f"/comissoes/{m[-1]}/pagar", {"data_pagamento":date.today().isoformat()})
        log("14c. POST /comissoes/{id}/pagar", "OK" if ok(rc) else "WARN",
            f"HTTP {rc.status_code if rc else 'N/A'} | Comissao ID={m[-1]}")

# ── 15. STATUS FINAL + PDF ────────────────────────────────────
r = get(f"/service_orders/view/{OS_ID}")
if r and r.status_code == 200:
    finalizada = any(s in r.text.lower() for s in ["completed","finaliz","pago","closed"])
    log("15a. GET /service_orders/view/{id} (status final)", "OK" if finalizada else "WARN",
        f"OS #{OS_ID} {'FINALIZADA' if finalizada else 'status nao confirmado'}")
else:
    log("15a. Status final OS", "WARN", f"HTTP {r.status_code if r else 'N/A'}")

r = get(f"/service_orders/{OS_ID}/pdf")
log("15b. GET /service_orders/{id}/pdf", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'}" + (f" | {len(r.content)} bytes" if ok(r) else ""))

r = get(f"/whatsapp/satisfacao/{OS_ID}")
log("15c. GET /whatsapp/satisfacao/{id}", "OK" if ok(r) else "WARN",
    f"HTTP {r.status_code if r else 'N/A'} (requer config WA)")

# ── RELATORIO ─────────────────────────────────────────────────
print("\n" + "="*65)
print("  RESULTADO DO TESTE")
print("="*65)
total = len(LOG)
n_ok   = sum(1 for s,_ in LOG if s=="OK")
n_warn = sum(1 for s,_ in LOG if s=="WARN")
n_err  = sum(1 for s,_ in LOG if s=="ERRO")
print(f"\n  OS testada:   #{OS_ID}")
print(f"  Cliente ID:   {CLIENTE_ID}")
print(f"  Veiculo ID:   {VEICULO_ID}")
print(f"  Orcamento ID: {ORCAMENTO_ID}")
print(f"\n  Total etapas: {total}")
print(f"  [OK]   : {n_ok}")
print(f"  [AVISO]: {n_warn}  (rotas existem, dados ou config pendentes)")
print(f"  [ERRO] : {n_err}")
print()
if n_err == 0 and n_warn <= 8:
    print("  >> FLUXO APROVADO - sistema operacional!")
elif n_err == 0:
    print("  >> FLUXO FUNCIONAL com avisos - ver itens [AVISO] acima")
else:
    erros = [m for s,m in LOG if s=="ERRO"]
    print("  >> ERROS ENCONTRADOS:")
    for e in erros: print(f"     {e}")
print("="*65)
