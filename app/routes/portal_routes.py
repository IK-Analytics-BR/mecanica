"""
portal_routes.py — Portal do Cliente — IKFlow Mecânica
Acesso por token único enviado via WhatsApp/e-mail.
Funcionalidades:
  - Ver OS abertas e histórico
  - Aprovar/reprovar orçamento
  - Ver garantias ativas
"""
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db
from utils.auth import login_required

portal_bp = Blueprint('portal', __name__)

TOKEN_EXPIRY_HOURS = 48


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _gerar_token(db, customer_id: int, company_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expira = datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    db.execute(
        "UPDATE portal_tokens SET ativo=0 WHERE customer_id=%s AND ativo=1",
        (customer_id,)
    )
    db.execute(
        """INSERT INTO portal_tokens (company_id, customer_id, token, expira_em)
           VALUES (%s,%s,%s,%s)""",
        (company_id, customer_id, token, expira)
    )
    return token


def _validar_token(db, token: str):
    """Retorna dict do cliente se token válido, None caso contrário."""
    row = db.fetch_one("""
        SELECT pt.*, c.name as customer_name, c.phone, c.email
        FROM portal_tokens pt
        JOIN customers c ON c.id = pt.customer_id
        WHERE pt.token = %s AND pt.ativo = 1 AND pt.expira_em > NOW()
    """, (token,))
    return row


# ─────────────────────────────────────────────────────────────
# Gerar link de acesso (admin envia para o cliente)
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/portal/gerar-link/<int:customer_id>', methods=['POST'])
@login_required
def portal_gerar_link(customer_id):
    db = get_db()
    company_id = session.get('company_id', 1)

    customer = db.fetch_one(
        "SELECT id, name FROM customers WHERE id=%s AND company_id=%s",
        (customer_id, company_id)
    )
    if not customer:
        return jsonify({'ok': False, 'msg': 'Cliente não encontrado.'}), 404

    token = _gerar_token(db, customer_id, company_id)
    link  = url_for('portal.portal_acesso', token=token, _external=True)

    return jsonify({'ok': True, 'token': token, 'link': link,
                    'expira_em': (datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)).strftime('%d/%m/%Y %H:%M')})


# ─────────────────────────────────────────────────────────────
# Acesso do cliente via token
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/portal/<token>')
def portal_acesso(token):
    db  = get_db()
    row = _validar_token(db, token)
    if not row:
        flash('Link inválido ou expirado. Solicite um novo acesso à oficina.', 'danger')
        return render_template('portal/portal_expirado.html'), 403

    # Marcar uso
    db.execute("UPDATE portal_tokens SET usado_em=NOW() WHERE token=%s", (token,))

    customer_id = row['customer_id']
    company_id  = row['company_id']

    # OS abertas e em progresso
    ordens_ativas = db.fetch_all("""
        SELECT so.id, so.order_number, so.status, so.status_orcamento,
               so.total_geral, so.created_at, so.updated_at,
               e.serial_number as placa, e.model as modelo
        FROM service_orders so
        LEFT JOIN equipment e ON e.id = so.equipment_id
        WHERE so.customer_id = %s AND so.company_id = %s
          AND so.status NOT IN ('completed','canceled')
        ORDER BY so.created_at DESC
    """, (customer_id, company_id)) or []

    # Histórico (últimas 20 concluídas)
    historico = db.fetch_all("""
        SELECT so.id, so.order_number, so.status, so.total_geral,
               so.created_at, so.updated_at,
               e.serial_number as placa, e.model as modelo
        FROM service_orders so
        LEFT JOIN equipment e ON e.id = so.equipment_id
        WHERE so.customer_id = %s AND so.company_id = %s
          AND so.status = 'completed'
        ORDER BY so.updated_at DESC LIMIT 20
    """, (customer_id, company_id)) or []

    # Garantias ativas
    garantias = db.fetch_all("""
        SELECT g.id, g.descricao, g.data_inicio, g.data_fim, g.status,
               so.order_number
        FROM garantias g
        JOIN service_orders so ON so.id = g.service_order_id
        WHERE g.customer_id = %s AND g.company_id = %s
          AND g.status = 'ativa'
        ORDER BY g.data_fim ASC
    """, (customer_id, company_id)) or []

    return render_template(
        'portal/portal_cliente.html',
        cliente=row,
        token=token,
        ordens_ativas=ordens_ativas,
        historico=historico,
        garantias=garantias,
    )


# ─────────────────────────────────────────────────────────────
# Aprovar / Reprovar orçamento pelo cliente
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/portal/<token>/orcamento/<int:order_id>/<acao>', methods=['POST'])
def portal_aprovar_orcamento(token, order_id, acao):
    db  = get_db()
    row = _validar_token(db, token)
    if not row:
        return jsonify({'ok': False, 'msg': 'Token inválido ou expirado.'}), 403

    if acao not in ('aprovar', 'reprovar'):
        return jsonify({'ok': False, 'msg': 'Ação inválida.'}), 400

    order = db.fetch_one("""
        SELECT id, status_orcamento FROM service_orders
        WHERE id=%s AND customer_id=%s AND company_id=%s
    """, (order_id, row['customer_id'], row['company_id']))

    if not order:
        return jsonify({'ok': False, 'msg': 'OS não encontrada.'}), 404

    if order['status_orcamento'] not in ('enviado', 'rascunho'):
        return jsonify({'ok': False, 'msg': 'Orçamento já processado.'}), 409

    novo_status = 'aprovado' if acao == 'aprovar' else 'reprovado'
    db.execute(
        "UPDATE service_orders SET status_orcamento=%s WHERE id=%s",
        (novo_status, order_id)
    )

    flash(f'Orçamento {"aprovado" if acao == "aprovar" else "reprovado"} com sucesso!',
          'success' if acao == 'aprovar' else 'warning')
    return redirect(url_for('portal.portal_acesso', token=token))


# ─────────────────────────────────────────────────────────────
# Detalhe de OS pelo cliente
# ─────────────────────────────────────────────────────────────
@portal_bp.route('/portal/<token>/os/<int:order_id>')
def portal_os_detalhe(token, order_id):
    db  = get_db()
    row = _validar_token(db, token)
    if not row:
        flash('Link inválido ou expirado.', 'danger')
        return render_template('portal/portal_expirado.html'), 403

    order = db.fetch_one("""
        SELECT so.*,
               e.serial_number as placa, e.model as modelo, e.brand as marca,
               e.year as ano,
               t.name as tecnico_nome
        FROM service_orders so
        LEFT JOIN equipment e ON e.id = so.equipment_id
        LEFT JOIN technicians t ON t.id = so.technician_id
        WHERE so.id=%s AND so.customer_id=%s AND so.company_id=%s
    """, (order_id, row['customer_id'], row['company_id']))

    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('portal.portal_acesso', token=token))

    itens = db.fetch_all("""
        SELECT soi.descricao, soi.quantidade, soi.valor_unitario, soi.valor_total, soi.tipo
        FROM service_order_items soi
        WHERE soi.service_order_id = %s
        ORDER BY soi.tipo, soi.id
    """, (order_id,)) or []

    return render_template(
        'portal/portal_os_detalhe.html',
        cliente=row,
        token=token,
        order=order,
        itens=itens,
    )
