"""
push_routes.py — Web Push Notifications (VAPID) para IKFlow Mecânica
Endpoints:
  GET  /push/vapid-public-key  → retorna chave pública VAPID
  POST /push/subscribe          → salva subscription do browser
  POST /push/enviar             → envia notificação (admin only)
  POST /push/enviar-os/<id>     → helper interno (trigger por OS)
"""
import json
import os
from flask import Blueprint, request, jsonify, session
from database import get_db
from utils.auth import login_required, admin_required

push_bp = Blueprint('push', __name__)

# ── Chaves VAPID (gere uma vez com: python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.public_key.serialize().decode(), v.private_key.serialize().decode())")
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY  = os.environ.get('VAPID_PUBLIC_KEY',  '')
VAPID_CLAIMS      = {'sub': f"mailto:{os.environ.get('VAPID_EMAIL', 'admin@ikflow.com.br')}"}


def _send_push(subscription_info: dict, payload: dict) -> bool:
    """Envia notificação push. Retorna True se OK."""
    try:
        from pywebpush import webpush, WebPushException
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
        return True
    except Exception as e:
        print(f'[PUSH] Erro ao enviar: {e}')
        return False


# ─────────────────────────────────────────────────────────────
# Retorna chave pública VAPID para o frontend
# ─────────────────────────────────────────────────────────────
@push_bp.route('/push/vapid-public-key')
def vapid_public_key():
    return jsonify({'publicKey': VAPID_PUBLIC_KEY})


# ─────────────────────────────────────────────────────────────
# Salva subscription do browser
# ─────────────────────────────────────────────────────────────
@push_bp.route('/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint    = data.get('endpoint', '')
    p256dh      = (data.get('keys') or {}).get('p256dh', '')
    auth_key    = (data.get('keys') or {}).get('auth', '')
    user_id     = session.get('user_id', 0)
    company_id  = session.get('company_id', 1)

    if not endpoint:
        return jsonify({'ok': False, 'msg': 'endpoint obrigatório'}), 400

    db = get_db()
    try:
        existing = db.fetch_one(
            "SELECT id FROM push_subscriptions WHERE endpoint = %s", (endpoint,)
        )
        if existing:
            db.execute(
                "UPDATE push_subscriptions SET p256dh=%s, auth_key=%s, user_id=%s WHERE endpoint=%s",
                (p256dh, auth_key, user_id, endpoint)
            )
        else:
            db.execute(
                """INSERT INTO push_subscriptions
                   (company_id, user_id, endpoint, p256dh, auth_key)
                   VALUES (%s,%s,%s,%s,%s)""",
                (company_id, user_id, endpoint, p256dh, auth_key)
            )
    except Exception as e:
        print(f'[PUSH] Erro ao salvar subscription: {e}')
        return jsonify({'ok': False, 'msg': str(e)}), 500

    return jsonify({'ok': True})


# ─────────────────────────────────────────────────────────────
# Envio manual (admin)
# ─────────────────────────────────────────────────────────────
@push_bp.route('/push/enviar', methods=['POST'])
@admin_required
def push_enviar():
    data    = request.get_json(silent=True) or {}
    titulo  = data.get('titulo', 'IKFlow Mecânica')
    corpo   = data.get('corpo', '')
    url     = data.get('url', '/')
    user_id = data.get('user_id')          # None = broadcast

    db = get_db()
    company_id = session.get('company_id', 1)

    try:
        if user_id:
            subs = db.fetch_all(
                "SELECT * FROM push_subscriptions WHERE user_id=%s AND ativo=1", (user_id,)
            ) or []
        else:
            subs = db.fetch_all(
                "SELECT * FROM push_subscriptions WHERE company_id=%s AND ativo=1", (company_id,)
            ) or []
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)}), 500

    payload = {'titulo': titulo, 'corpo': corpo, 'url': url}
    ok, fail = 0, 0
    for sub in subs:
        info = {
            'endpoint': sub['endpoint'],
            'keys': {'p256dh': sub['p256dh'], 'auth': sub['auth_key']},
        }
        if _send_push(info, payload):
            ok += 1
        else:
            fail += 1
            # Desativar subscription inválida
            try:
                db.execute(
                    "UPDATE push_subscriptions SET ativo=0 WHERE id=%s", (sub['id'],)
                )
            except Exception:
                pass

    return jsonify({'ok': True, 'enviados': ok, 'falhas': fail})


# ─────────────────────────────────────────────────────────────
# Helper interno: dispara push ao mudar status de OS
# ─────────────────────────────────────────────────────────────
def push_notificar_os(order_id: int, tipo: str):
    """
    Chamado internamente ao concluir/aprovar OS.
    tipo: 'completed' | 'orcamento_enviado'
    """
    if not VAPID_PRIVATE_KEY:
        return

    try:
        db = get_db()
        order = db.fetch_one("""
            SELECT so.order_number, so.total_geral, so.technician_id,
                   c.name as customer_name, e.serial_number as placa
            FROM service_orders so
            LEFT JOIN customers c ON c.id = so.customer_id
            LEFT JOIN equipment e ON e.id = so.equipment_id
            WHERE so.id = %s
        """, (order_id,))
        if not order:
            return

        if tipo == 'completed':
            titulo = '✅ OS Concluída'
            corpo  = f"OS {order['order_number']} — {order.get('placa','veículo')} pronta para retirada."
        else:
            titulo = '📋 Orçamento Enviado'
            corpo  = f"OS {order['order_number']} — aguardando aprovação do cliente."

        # Notifica técnico responsável + admins da empresa
        tech_id    = order.get('technician_id')
        company_id = db.fetch_one("SELECT company_id FROM service_orders WHERE id=%s", (order_id,))
        company_id = (company_id or {}).get('company_id', 1)

        subs = db.fetch_all("""
            SELECT * FROM push_subscriptions
            WHERE company_id = %s AND ativo = 1
        """, (company_id,)) or []

        payload = {'titulo': titulo, 'corpo': corpo, 'url': f'/service_orders/view/{order_id}'}
        for sub in subs:
            info = {
                'endpoint': sub['endpoint'],
                'keys': {'p256dh': sub['p256dh'], 'auth': sub['auth_key']},
            }
            _send_push(info, payload)
    except Exception as e:
        print(f'[PUSH] push_notificar_os erro: {e}')
