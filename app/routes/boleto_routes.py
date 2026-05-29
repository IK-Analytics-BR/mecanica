"""
boleto_routes.py — Boleto Bancário via Mercado Pago — IKFlow Mecânica
Endpoints:
  GET/POST /boleto/gerar/<order_id>   → gera boleto e exibe
  POST     /boleto/webhook            → recebe notificação de pagamento (MP)
  GET      /boleto/<payment_id>       → consulta status do boleto
"""
import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db
from utils.auth import login_required

boleto_bp = Blueprint('boleto', __name__)

MP_ACCESS_TOKEN = os.environ.get('MP_ACCESS_TOKEN', '')


def _mp_sdk():
    try:
        import mercadopago
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        return sdk
    except Exception as e:
        print(f'[BOLETO] SDK erro: {e}')
        return None


# ─────────────────────────────────────────────────────────────
# Gerar boleto
# ─────────────────────────────────────────────────────────────
@boleto_bp.route('/boleto/gerar/<int:order_id>', methods=['GET', 'POST'])
@login_required
def boleto_gerar(order_id):
    db = get_db()
    company_id = session.get('company_id', 1)

    order = db.fetch_one("""
        SELECT so.*, so.total_geral as valor,
               c.name as customer_name, c.cpf, c.cnpj, c.email as customer_email,
               c.phone as customer_phone, c.address, c.city, c.state, c.zip_code
        FROM service_orders so
        LEFT JOIN customers c ON c.id = so.customer_id
        WHERE so.id = %s AND so.company_id = %s
    """, (order_id, company_id))

    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))

    # Boleto já gerado?
    existing = db.fetch_one(
        "SELECT * FROM boletos WHERE service_order_id = %s AND status NOT IN ('cancelled','rejected') ORDER BY id DESC LIMIT 1",
        (order_id,)
    )
    if existing:
        return render_template('boleto/boleto_view.html', order=order, boleto=existing)

    if request.method == 'GET':
        return render_template('boleto/boleto_form.html', order=order)

    # POST — gerar via Mercado Pago
    vencimento = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    valor      = float(order.get('valor') or 0)

    if not MP_ACCESS_TOKEN:
        flash('Token do Mercado Pago não configurado. Defina MP_ACCESS_TOKEN no ambiente.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    sdk = _mp_sdk()
    if not sdk:
        flash('SDK Mercado Pago indisponível.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    # Monta CPF/CNPJ limpo
    _cpf  = ''.join(filter(str.isdigit, order.get('cpf')  or ''))
    _cnpj = ''.join(filter(str.isdigit, order.get('cnpj') or ''))
    if _cnpj:
        cpf_cnpj, doc_type = _cnpj, 'CNPJ'
    elif _cpf:
        cpf_cnpj, doc_type = _cpf, 'CPF'
    else:
        cpf_cnpj, doc_type = '00000000000', 'CPF'

    payload = {
        'transaction_amount': round(valor, 2),
        'description': f'OS {order["order_number"]} — IKFlow Mecânica',
        'payment_method_id': 'bolbradesco',
        'date_of_expiration': f'{vencimento}T23:59:59.000-03:00',
        'payer': {
            'email': order.get('customer_email') or 'cliente@ikflow.com.br',
            'first_name': (order.get('customer_name') or 'Cliente').split()[0],
            'last_name': ' '.join((order.get('customer_name') or 'Cliente').split()[1:]) or 'S/N',
            'identification': {'type': doc_type, 'number': cpf_cnpj or '00000000000'},
            'address': {
                'street_name': order.get('address') or 'Rua não informada',
                'zip_code': ''.join(filter(str.isdigit, order.get('zip_code') or '00000000'))[:8],
            },
        },
        'notification_url': url_for('boleto.boleto_webhook', _external=True),
        'external_reference': str(order_id),
    }

    try:
        result = sdk.payment().create(payload)
        resp   = result.get('response', {})
        status = resp.get('status', 'error')

        if status in ('pending', 'approved'):
            payment_id  = resp.get('id')
            boleto_url  = (resp.get('transaction_details') or {}).get('external_resource_url', '')
            barcode_num = (resp.get('barcode') or {}).get('content', '')

            db.execute("""
                INSERT INTO boletos
                  (company_id, service_order_id, payment_id, status,
                   valor, vencimento, boleto_url, barcode, resposta_mp)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                company_id, order_id, payment_id, status,
                valor, vencimento, boleto_url, barcode_num,
                json.dumps(resp, default=str)[:2000]
            ))

            boleto = db.fetch_one(
                "SELECT * FROM boletos WHERE service_order_id=%s ORDER BY id DESC LIMIT 1",
                (order_id,)
            )
            return render_template('boleto/boleto_view.html', order=order, boleto=boleto)
        else:
            msg = (resp.get('message') or resp.get('cause') or str(resp))[:300]
            flash(f'Erro ao gerar boleto: {msg}', 'danger')
    except Exception as e:
        flash(f'Erro interno ao gerar boleto: {e}', 'danger')

    return redirect(url_for('service_order.service_order_view', order_id=order_id))


# ─────────────────────────────────────────────────────────────
# Consultar status
# ─────────────────────────────────────────────────────────────
@boleto_bp.route('/boleto/status/<int:order_id>')
@login_required
def boleto_status(order_id):
    db = get_db()
    boleto = db.fetch_one(
        "SELECT * FROM boletos WHERE service_order_id=%s ORDER BY id DESC LIMIT 1",
        (order_id,)
    )
    if not boleto or not boleto.get('payment_id'):
        return jsonify({'ok': False, 'msg': 'Boleto não encontrado.'})

    sdk = _mp_sdk()
    if not sdk:
        return jsonify({'ok': False, 'msg': 'SDK indisponível.'})

    try:
        result = sdk.payment().get(boleto['payment_id'])
        resp   = result.get('response', {})
        novo_status = resp.get('status', boleto['status'])
        db.execute(
            "UPDATE boletos SET status=%s WHERE id=%s",
            (novo_status, boleto['id'])
        )
        return jsonify({'ok': True, 'status': novo_status, 'payment_id': boleto['payment_id']})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)})


# ─────────────────────────────────────────────────────────────
# Webhook Mercado Pago
# ─────────────────────────────────────────────────────────────
@boleto_bp.route('/boleto/webhook', methods=['POST'])
def boleto_webhook():
    """Recebe notificação do MP e baixa C/R automaticamente ao pagar."""
    data = request.get_json(silent=True) or request.form.to_dict()
    payment_id = str(data.get('data', {}).get('id') or data.get('id', ''))
    tipo       = data.get('type') or data.get('topic', '')

    if tipo not in ('payment', 'merchant_order') or not payment_id:
        return jsonify({'ok': True}), 200

    sdk = _mp_sdk()
    if not sdk:
        return jsonify({'ok': False}), 500

    try:
        result      = sdk.payment().get(payment_id)
        resp        = result.get('response', {})
        mp_status   = resp.get('status', '')
        order_id    = int(resp.get('external_reference') or 0)

        db = get_db()
        db.execute(
            "UPDATE boletos SET status=%s WHERE payment_id=%s",
            (mp_status, payment_id)
        )

        if mp_status == 'approved' and order_id:
            # Baixa automática em contas a receber
            db.execute("""
                UPDATE accounts_receivable
                   SET status='paid', payment_date=NOW(), payment_method='boleto'
                 WHERE service_order_id=%s AND status='pending'
            """, (order_id,))

    except Exception as e:
        print(f'[BOLETO WEBHOOK] Erro: {e}')

    return jsonify({'ok': True}), 200
