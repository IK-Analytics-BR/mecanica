"""
whatsapp_routes.py — Módulo WhatsApp Business para IKFlow Mecânica
Provedores suportados:
  - UazAPI       (uazapi.com — CONFIGURADO)
  - UZapi        (uzapi.com)
  - Z-API        (z-api.io)
  - WPPConnect   (wppconnect-server)
  - Evolution API v2 (evolution-api.com)
  - Meta Cloud API  (graph.facebook.com)
"""
import json
import os
import requests
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db

whatsapp_bp = Blueprint('whatsapp', __name__)

# ─────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────

def _get_config(db):
    cfg = db.fetch_one("SELECT * FROM whatsapp_config WHERE ativo = 1 LIMIT 1")
    return cfg or {}


def _enviar_mensagem(cfg: dict, telefone: str, mensagem: str) -> dict:
    """Dispara mensagem de texto via o provedor configurado."""
    telefone = ''.join(c for c in telefone if c.isdigit())
    if not telefone.startswith('55'):
        telefone = '55' + telefone

    provider  = cfg.get('provider', 'uzapi')
    api_url   = (cfg.get('api_url') or '').rstrip('/')
    api_key   = cfg.get('api_key') or ''
    token     = cfg.get('token') or cfg.get('api_key') or ''
    instance  = cfg.get('instance_name') or cfg.get('instance') or 'mecanica'
    session_n = cfg.get('session_name') or instance

    try:
        if provider == 'uazapi':
            # UazAPI — https://uazapi.com
            # POST /send/text
            # Header: token: <instance_token>   (NAO Authorization Bearer)
            # Body: { number, text, delay }
            url = f"{api_url}/send/text"
            headers = {'Content-Type': 'application/json',
                       'Accept': 'application/json',
                       'token': token}
            payload = {'number': telefone, 'text': mensagem, 'delay': 1500}

        elif provider == 'uzapi':
            # UZapi — https://uzapi.com/docs
            # POST /message/sendText/{instance}
            # Header: apikey
            url = f"{api_url}/message/sendText/{instance}"
            headers = {'Content-Type': 'application/json', 'apikey': api_key}
            payload = {'number': telefone, 'text': mensagem}

        elif provider == 'zapi':
            # Z-API — https://developer.z-api.io
            # POST /instances/{instance}/token/{token}/send-text
            # Header: Client-Token
            client_token = cfg.get('client_token') or token
            url = f"{api_url}/instances/{instance}/token/{token}/send-text"
            headers = {'Content-Type': 'application/json', 'Client-Token': client_token}
            payload = {'phone': telefone, 'message': mensagem}

        elif provider == 'wppconnect':
            # WPPConnect Server — https://wppconnect.io
            # POST /api/{session}/send-message
            url = f"{api_url}/api/{session_n}/send-message"
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
            payload = {'phone': telefone, 'message': mensagem, 'isGroup': False}

        elif provider == 'evolution':
            # Evolution API v2 — https://evolution-api.com
            url = f"{api_url}/message/sendText/{instance}"
            headers = {'Content-Type': 'application/json', 'apikey': api_key}
            payload = {'number': telefone, 'text': mensagem}

        elif provider == 'meta':
            # Meta Cloud API (WhatsApp Business Platform)
            phone_number_id = cfg.get('phone_number_id') or ''
            url = f'https://graph.facebook.com/v19.0/{phone_number_id}/messages'
            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
            payload = {
                'messaging_product': 'whatsapp',
                'to': telefone,
                'type': 'text',
                'text': {'body': mensagem}
            }

        else:
            return {'ok': False, 'status': 0, 'body': f'Provedor desconhecido: {provider}'}

        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return {'ok': r.status_code in (200, 201), 'status': r.status_code, 'body': r.text}

    except Exception as e:
        return {'ok': False, 'status': 0, 'body': str(e)}


def _registrar_log(db, tipo: str, telefone: str, mensagem: str, os_id, status: str, resposta: str):
    try:
        db.insert("""
            INSERT INTO whatsapp_logs
            (tipo, telefone, mensagem, service_order_id, status, resposta, enviado_em)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (tipo, telefone, mensagem, os_id, status, (resposta or '')[:500]))
    except Exception as e:
        print(f'[WA] Log error: {e}')


def _get_template_mensagem(db, tipo: str) -> str:
    """Busca mensagem do banco (whatsapp_templates). Fallback para texto genérico."""
    try:
        row = db.fetch_one(
            "SELECT mensagem FROM whatsapp_templates WHERE tipo=%s AND ativo=1 LIMIT 1",
            (tipo,)
        )
        if row and row.get('mensagem'):
            return row['mensagem']
    except Exception:
        pass
    # Fallback mínimo
    defaults = {
        'orcamento':       "Ola {nome}, seu orcamento {os_numero} para o veiculo {placa} esta pronto. Total: R$ {total}. Aguardamos aprovacao.",
        'aprovado':        "Ola {nome}, o orcamento {os_numero} foi aprovado! Iniciamos o servico no seu {placa}.",
        'concluido':       "Ola {nome}, seu veiculo {placa} esta pronto para retirada! OS: {os_numero} | Total: R$ {total}.",
        'lembrete_revisao':"Ola {nome}, o veiculo {placa} esta proximo do prazo de revisao. Agende agora!",
        'cobranca':        "Ola {nome}, ha um valor em aberto referente ao servico {os_numero}. Total: R$ {total}. Entre em contato.",
    }
    return defaults.get(tipo, "Mensagem do IKFlow Mecanica.")


# ─────────────────────────────────────────────────────────────
# Rotas
# ─────────────────────────────────────────────────────────────

@whatsapp_bp.route('/whatsapp')
def whatsapp_painel():
    db = get_db()
    cfg = _get_config(db)
    try:
        logs = db.fetch_all("""
            SELECT wl.*, so.order_number, c.name as customer_name
            FROM whatsapp_logs wl
            LEFT JOIN service_orders so ON so.id = wl.service_order_id
            LEFT JOIN customers c ON c.id = so.customer_id
            ORDER BY wl.enviado_em DESC LIMIT 100
        """)
        kpis = db.fetch_one("""
            SELECT COUNT(*) as total,
                   SUM(status='enviado') as enviados,
                   SUM(status='erro') as erros,
                   SUM(tipo='orcamento') as orcamentos,
                   SUM(tipo='concluido') as concluidos,
                   SUM(tipo='cobranca') as cobranças
            FROM whatsapp_logs
        """) or {}
    except Exception:
        logs, kpis = [], {}
    return render_template('whatsapp/painel.html', cfg=cfg, logs=logs, kpis=kpis)


@whatsapp_bp.route('/whatsapp/configurar', methods=['GET', 'POST'])
def whatsapp_config():
    db = get_db()
    cfg = _get_config(db)

    if request.method == 'POST':
        provider         = request.form.get('provider', 'uazapi')
        api_url          = request.form.get('api_url', '').rstrip('/')
        api_key          = request.form.get('api_key', '')
        token            = request.form.get('token', '')
        client_token     = request.form.get('client_token', '')
        instance         = request.form.get('instance_name', '')
        session_name     = request.form.get('session_name', '')
        phone_id         = request.form.get('phone_number_id', '')
        numero_wa        = request.form.get('numero_whatsapp', '')
        dias_lembrete    = int(request.form.get('dias_lembrete', 7))
        telefone_teste   = request.form.get('telefone_teste', '').strip()
        telefones_admin  = request.form.get('telefones_admin', '').strip()
        disparos_ativos  = 1 if request.form.get('disparos_ativos') else 0

        try:
            if cfg:
                db.execute_query("""
                    UPDATE whatsapp_config
                    SET provider=%s, api_url=%s, api_key=%s, token=%s,
                        client_token=%s, instance_name=%s, session_name=%s,
                        phone_number_id=%s, numero_whatsapp=%s,
                        dias_lembrete=%s, telefone_teste=%s,
                        telefones_admin=%s, disparos_ativos=%s, ativo=1
                    WHERE id=%s
                """, (provider, api_url, api_key, token, client_token,
                      instance, session_name, phone_id, numero_wa,
                      dias_lembrete, telefone_teste, telefones_admin,
                      disparos_ativos, cfg['id']))
            else:
                db.insert("""
                    INSERT INTO whatsapp_config
                    (provider, api_url, api_key, token, client_token,
                     instance_name, session_name, phone_number_id, numero_whatsapp,
                     dias_lembrete, telefone_teste, telefones_admin, disparos_ativos, ativo)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
                """, (provider, api_url, api_key, token, client_token,
                      instance, session_name, phone_id, numero_wa,
                      dias_lembrete, telefone_teste, telefones_admin, disparos_ativos))
            flash('Configuração salva com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro ao salvar: {e}', 'danger')

        return redirect(url_for('whatsapp.whatsapp_config'))

    try:
        templates_editaveis = db.fetch_all("SELECT * FROM whatsapp_templates ORDER BY tipo")
    except Exception:
        templates_editaveis = []

    return render_template('whatsapp/config.html', cfg=cfg,
                           templates_editaveis=templates_editaveis)


@whatsapp_bp.route('/whatsapp/salvar-template/<int:template_id>', methods=['POST'])
def whatsapp_salvar_template(template_id):
    db = get_db()
    mensagem = request.form.get('mensagem', '').strip()
    titulo   = request.form.get('titulo', '').strip()
    if mensagem:
        try:
            db.update(
                "UPDATE whatsapp_templates SET mensagem=%s, titulo=%s WHERE id=%s",
                (mensagem, titulo, template_id)
            )
            flash('Template atualizado!', 'success')
        except Exception as e:
            flash(f'Erro: {e}', 'danger')
    return redirect(url_for('whatsapp.whatsapp_config'))


@whatsapp_bp.route('/whatsapp/testar', methods=['POST'])
def whatsapp_testar():
    db = get_db()
    cfg = _get_config(db)
    if not cfg:
        flash('Configure o WhatsApp primeiro.', 'danger')
        return redirect(url_for('whatsapp.whatsapp_config'))
    telefone = request.form.get('telefone', '')
    mensagem = request.form.get('mensagem', 'Teste de conexao — IKFlow Mecanica')
    resultado = _enviar_mensagem(cfg, telefone, mensagem)
    if resultado['ok']:
        flash(f'Mensagem enviada para {telefone}!', 'success')
        _registrar_log(db, 'teste', telefone, mensagem, None, 'enviado', resultado['body'])
    else:
        flash(f'Erro ao enviar: {resultado["body"][:200]}', 'danger')
        _registrar_log(db, 'teste', telefone, mensagem, None, 'erro', resultado['body'])
    return redirect(url_for('whatsapp.whatsapp_config'))


@whatsapp_bp.route('/whatsapp/enviar-os/<int:order_id>/<tipo>', methods=['POST'])
def whatsapp_enviar_os(order_id, tipo):
    """Envia mensagem WhatsApp para o cliente da OS."""
    db = get_db()
    cfg = _get_config(db)
    if not cfg:
        flash('Configure o WhatsApp antes de enviar.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    order = db.fetch_one("""
        SELECT so.*, c.name as customer_name, c.phone as customer_phone,
               e.serial_number as placa
        FROM service_orders so
        LEFT JOIN customers c ON c.id = so.customer_id
        LEFT JOIN equipment e ON e.id = so.equipment_id
        WHERE so.id = %s
    """, (order_id,))

    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))

    telefone = order.get('customer_phone', '')
    if not telefone:
        flash('Cliente sem telefone cadastrado.', 'warning')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    template = _get_template_mensagem(db, tipo)
    mensagem = template.format(
        nome=order.get('customer_name', 'Cliente'),
        os_numero=order.get('order_number', ''),
        placa=order.get('placa', 'veiculo'),
        total=f"{float(order.get('total_geral') or 0):.2f}".replace('.', ','),
    )

    resultado = _enviar_mensagem(cfg, telefone, mensagem)
    status = 'enviado' if resultado['ok'] else 'erro'
    _registrar_log(db, tipo, telefone, mensagem, order_id, status, resultado['body'])

    if resultado['ok']:
        try:
            db.update("UPDATE service_orders SET phone_notificado=NOW() WHERE id=%s", (order_id,))
        except Exception:
            pass
        flash(f'WhatsApp "{tipo}" enviado para {telefone}!', 'success')
    else:
        flash(f'Falha ao enviar WhatsApp: {resultado["body"][:150]}', 'danger')

    return redirect(url_for('service_order.service_order_view', order_id=order_id))


@whatsapp_bp.route('/whatsapp/enviar-orcamento-wa/<int:order_id>', methods=['POST'])
@login_required
def enviar_orcamento_wa(order_id):
    """Envia orçamento ao cliente via WA e marca status_orcamento='enviado'."""
    db = get_db()
    cfg = _get_config(db)
    if not cfg:
        flash('Configure o WhatsApp antes de enviar.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    order = db.fetch_one("""
        SELECT so.*, c.name as customer_name, c.phone as customer_phone,
               e.serial_number as placa
        FROM service_orders so
        LEFT JOIN customers c ON c.id = so.customer_id
        LEFT JOIN equipment e ON e.id = so.equipment_id
        WHERE so.id = %s
    """, (order_id,))

    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))

    telefone = (order.get('customer_phone') or '').strip()
    if not telefone:
        flash('Cliente sem telefone cadastrado. Cadastre o telefone antes de enviar.', 'warning')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    template = _get_template_mensagem(db, 'orcamento')
    mensagem = template.format(
        nome=order.get('customer_name', 'Cliente'),
        os_numero=order.get('order_number', ''),
        placa=order.get('placa') or 'veículo',
        total=f"{float(order.get('total_geral') or 0):.2f}".replace('.', ','),
    )

    resultado = _enviar_mensagem(cfg, telefone, mensagem)
    status_log = 'enviado' if resultado['ok'] else 'erro'
    _registrar_log(db, 'orcamento', telefone, mensagem, order_id, status_log, resultado['body'])

    if resultado['ok']:
        try:
            db.execute_query(
                "UPDATE service_orders SET status_orcamento='enviado', phone_notificado=NOW() WHERE id=%s",
                (order_id,)
            )
        except Exception:
            pass
        flash(f'Orçamento enviado via WhatsApp para {telefone}!', 'success')
    else:
        flash(f'Falha ao enviar WhatsApp: {resultado["body"][:150]}', 'danger')

    return redirect(url_for('service_order.service_order_view', order_id=order_id))


@whatsapp_bp.route('/whatsapp/notificar-pronta/<int:order_id>', methods=['POST'])
@login_required
def notificar_os_pronta(order_id):
    """Notifica cliente que o veículo está pronto para retirada."""
    db = get_db()
    cfg = _get_config(db)
    if not cfg:
        flash('Configure o WhatsApp antes de enviar.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    order = db.fetch_one("""
        SELECT so.*, c.name as customer_name, c.phone as customer_phone,
               e.serial_number as placa
        FROM service_orders so
        LEFT JOIN customers c ON c.id = so.customer_id
        LEFT JOIN equipment e ON e.id = so.equipment_id
        WHERE so.id = %s
    """, (order_id,))

    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))

    telefone = (order.get('customer_phone') or '').strip()
    if not telefone:
        flash('Cliente sem telefone cadastrado.', 'warning')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    template = _get_template_mensagem(db, 'concluido')
    mensagem = template.format(
        nome=order.get('customer_name', 'Cliente'),
        os_numero=order.get('order_number', ''),
        placa=order.get('placa') or 'veículo',
        total=f"{float(order.get('total_geral') or 0):.2f}".replace('.', ','),
    )

    resultado = _enviar_mensagem(cfg, telefone, mensagem)
    status_log = 'enviado' if resultado['ok'] else 'erro'
    _registrar_log(db, 'concluido', telefone, mensagem, order_id, status_log, resultado['body'])

    if resultado['ok']:
        try:
            db.execute_query("UPDATE service_orders SET phone_notificado=NOW() WHERE id=%s", (order_id,))
        except Exception:
            pass
        flash(f'Notificação "pronto para retirada" enviada para {telefone}!', 'success')
    else:
        flash(f'Falha ao enviar WhatsApp: {resultado["body"][:150]}', 'danger')

    return redirect(url_for('service_order.service_order_view', order_id=order_id))


@whatsapp_bp.route('/whatsapp/disparar-lembretes')
def disparar_lembretes_revisao():
    """
    Job chamado por cron (ou manualmente).
    Busca veículos com km próximo de revisão e envia WA.
    Usa dias_lembrete da config e disparos_ativos=1.
    """
    db = get_db()
    cfg = _get_config(db)
    if not cfg or not cfg.get('disparos_ativos'):
        return jsonify({'ok': False, 'msg': 'Disparos desativados ou WhatsApp não configurado.'})

    dias = int(cfg.get('dias_lembrete') or 7)
    enviados, erros = 0, 0

    try:
        veiculos = db.fetch_all("""
            SELECT e.id, e.serial_number as placa, e.next_maintenance_date,
                   c.name as customer_name, c.phone as customer_phone
            FROM equipment e
            LEFT JOIN customers c ON c.id = e.customer_id
            WHERE e.active = 1
              AND e.next_maintenance_date IS NOT NULL
              AND e.next_maintenance_date <= DATE_ADD(CURDATE(), INTERVAL %s DAY)
              AND e.next_maintenance_date >= CURDATE()
            ORDER BY e.next_maintenance_date ASC
        """, (dias,))
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'Erro na consulta: {e}'})

    for v in veiculos:
        telefone = (v.get('customer_phone') or '').strip()
        if not telefone:
            continue
        template = _get_template_mensagem(db, 'lembrete_revisao')
        mensagem = template.format(
            nome=v.get('customer_name', 'Cliente'),
            placa=v.get('placa') or 'veículo',
            os_numero='',
            total='',
        )
        resultado = _enviar_mensagem(cfg, telefone, mensagem)
        status_log = 'enviado' if resultado['ok'] else 'erro'
        _registrar_log(db, 'lembrete_revisao', telefone, mensagem, None, status_log, resultado['body'])
        if resultado['ok']:
            enviados += 1
        else:
            erros += 1

    return jsonify({'ok': True, 'enviados': enviados, 'erros': erros, 'total': len(veiculos)})


@whatsapp_bp.route('/whatsapp/alerta-urgente/<int:order_id>', methods=['POST'])
@login_required
def alerta_os_urgente(order_id):
    """Notifica admins sobre OS urgente."""
    db = get_db()
    cfg = _get_config(db)
    if not cfg:
        return  # silencioso

    order = db.fetch_one("""
        SELECT so.order_number, c.name as customer_name, e.serial_number as placa
        FROM service_orders so
        LEFT JOIN customers c ON c.id = so.customer_id
        LEFT JOIN equipment e ON e.id = so.equipment_id
        WHERE so.id = %s
    """, (order_id,))
    if not order:
        return

    telefones_admin = (cfg.get('telefones_admin') or '').strip()
    if not telefones_admin:
        return

    mensagem = (
        f"⚠️ OS URGENTE: {order.get('order_number')} | "
        f"Cliente: {order.get('customer_name')} | "
        f"Veículo: {order.get('placa')} | "
        f"Ação imediata necessária."
    )
    for tel in [t.strip() for t in telefones_admin.split(',') if t.strip()]:
        resultado = _enviar_mensagem(cfg, tel, mensagem)
        status_log = 'enviado' if resultado['ok'] else 'erro'
        _registrar_log(db, 'urgente', tel, mensagem, order_id, status_log, resultado['body'])


def _disparar_wa_automatico(order_id: int, tipo: str):
    """
    Helper público chamado internamente ao mudar status da OS.
    Não redireciona — só envia e registra log.
    tipo: 'concluido' | 'orcamento' | 'urgente'
    """
    try:
        from database import get_db as _get_db
        db = _get_db()
        cfg = _get_config(db)
        if not cfg or not cfg.get('disparos_ativos'):
            return

        order = db.fetch_one("""
            SELECT so.*, c.name as customer_name, c.phone as customer_phone,
                   e.serial_number as placa
            FROM service_orders so
            LEFT JOIN customers c ON c.id = so.customer_id
            LEFT JOIN equipment e ON e.id = so.equipment_id
            WHERE so.id = %s
        """, (order_id,))
        if not order:
            return

        telefone = (order.get('customer_phone') or '').strip()
        if not telefone:
            return

        template = _get_template_mensagem(db, tipo)
        mensagem = template.format(
            nome=order.get('customer_name', 'Cliente'),
            os_numero=order.get('order_number', ''),
            placa=order.get('placa') or 'veículo',
            total=f"{float(order.get('total_geral') or 0):.2f}".replace('.', ','),
        )
        resultado = _enviar_mensagem(cfg, telefone, mensagem)
        status_log = 'enviado' if resultado['ok'] else 'erro'
        _registrar_log(db, tipo, telefone, mensagem, order_id, status_log, resultado['body'])
        if resultado['ok']:
            try:
                db.execute_query("UPDATE service_orders SET phone_notificado=NOW() WHERE id=%s", (order_id,))
            except Exception:
                pass
    except Exception as e:
        print(f'[WA AUTO] Erro ao disparar {tipo} para OS {order_id}: {e}')


@whatsapp_bp.route('/whatsapp/status-instancia')
def whatsapp_status():
    """Verifica status da instância (suporta UZapi, Evolution, WPPConnect)."""
    db = get_db()
    cfg = _get_config(db)
    if not cfg:
        return jsonify({'status': 'not_configured'})

    provider = cfg.get('provider', 'uzapi')
    api_url  = (cfg.get('api_url') or '').rstrip('/')
    api_key  = cfg.get('api_key') or ''
    instance = cfg.get('instance_name') or 'mecanica'
    token    = cfg.get('token') or api_key

    try:
        if provider == 'uazapi':
            url = f"{api_url}/instance/status"
            r = requests.get(url, headers={'token': token, 'Accept': 'application/json'}, timeout=5)
        elif provider in ('uzapi', 'evolution'):
            url = f"{api_url}/instance/connectionState/{instance}"
            r = requests.get(url, headers={'apikey': api_key}, timeout=5)
        elif provider == 'wppconnect':
            url = f"{api_url}/api/{instance}/status-session"
            r = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=5)
        elif provider == 'zapi':
            r_tok = cfg.get('token') or ''
            url = f"{api_url}/instances/{instance}/token/{r_tok}/status"
            r = requests.get(url, timeout=5)
        else:
            return jsonify({'status': 'unsupported_provider'})
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
