"""
garantia_routes.py — Controle de Garantia por OS/Peça/Serviço — IKFlow Mecânica
"""
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import get_db
from utils.auth import login_required
from utils.tenant import get_company_id

garantia_bp = Blueprint('garantia', __name__)


def registrar_garantia_os(order_id: int, prazo_dias: int = 90) -> dict:
    """
    Cria garantia padrão ao concluir OS.
    Chamada automaticamente em service_order_routes ao status=completed.
    """
    db = get_db()
    company_id = get_company_id()

    # Evita duplicata
    existe = db.fetch_one("""
        SELECT id FROM garantias
        WHERE service_order_id = %s AND company_id = %s
    """, (order_id, company_id))
    if existe:
        return {'ok': False, 'motivo': 'Garantia já registrada para esta OS'}

    order = db.fetch_one("""
        SELECT id, order_number, observations, diagnostico
        FROM service_orders WHERE id = %s
    """, (order_id,))
    if not order:
        return {'ok': False, 'motivo': 'OS não encontrada'}

    hoje     = date.today()
    data_fim = hoje + timedelta(days=prazo_dias)
    descricao = (
        f"Garantia OS {order['order_number']} — "
        f"{(order.get('diagnostico') or order.get('observations') or 'Serviços executados')[:150]}"
    )

    gid = db.insert("""
        INSERT INTO garantias
          (company_id, service_order_id, tipo, descricao,
           data_inicio, data_fim, prazo_dias)
        VALUES (%s,%s,'servico',%s,%s,%s,%s)
    """, (company_id, order_id, descricao, hoje, data_fim, prazo_dias))

    return {'ok': bool(gid), 'data_fim': str(data_fim), 'prazo_dias': prazo_dias}


@garantia_bp.route('/garantias')
@login_required
def garantia_lista():
    """Lista garantias com filtro de status."""
    db = get_db()
    company_id = get_company_id()
    status = request.args.get('status', 'vigente')

    # Atualiza expiradas automaticamente
    db.execute("""
        UPDATE garantias SET status='expirada'
        WHERE company_id = %s AND status = 'vigente' AND data_fim < CURDATE()
    """, (company_id,))

    query = """
        SELECT g.*, so.order_number,
               c.name as customer_name,
               e.name as equipment_name,
               e.serial_number as placa,
               DATEDIFF(g.data_fim, CURDATE()) as dias_restantes
        FROM garantias g
        JOIN service_orders so ON so.id = g.service_order_id
        LEFT JOIN customers c  ON c.id  = so.customer_id
        LEFT JOIN equipment e  ON e.id  = so.equipment_id
        WHERE g.company_id = %s
    """
    params = [company_id]
    if status and status != 'todos':
        query += " AND g.status = %s"
        params.append(status)
    query += " ORDER BY g.data_fim ASC"

    garantias = db.fetch_all(query, tuple(params)) or []

    kpis = db.fetch_one("""
        SELECT
          SUM(status='vigente')   AS vigentes,
          SUM(status='acionada')  AS acionadas,
          SUM(status='expirada')  AS expiradas,
          SUM(status='vigente' AND data_fim BETWEEN CURDATE() AND DATE_ADD(CURDATE(),INTERVAL 30 DAY)) AS vencendo
        FROM garantias WHERE company_id = %s
    """, (company_id,)) or {}

    return render_template('garantia_lista.html',
        garantias=garantias, kpis=kpis, status=status)


@garantia_bp.route('/garantias/nova/<int:order_id>', methods=['GET', 'POST'])
@login_required
def garantia_nova(order_id):
    """Cria garantia manual para uma OS."""
    db = get_db()
    company_id = get_company_id()

    order = db.fetch_one("""
        SELECT so.id, so.order_number, so.observations,
               c.name as customer_name, e.name as equipment_name
        FROM service_orders so
        LEFT JOIN customers c ON c.id = so.customer_id
        LEFT JOIN equipment e ON e.id = so.equipment_id
        WHERE so.id = %s
    """, (order_id,))

    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('garantia.garantia_lista'))

    if request.method == 'POST':
        tipo       = request.form.get('tipo', 'servico')
        descricao  = request.form.get('descricao', '').strip()
        prazo_dias = int(request.form.get('prazo_dias', 90))
        hoje       = date.today()
        data_fim   = hoje + timedelta(days=prazo_dias)

        if not descricao:
            flash('Descrição obrigatória.', 'danger')
        else:
            db.insert("""
                INSERT INTO garantias
                  (company_id, service_order_id, tipo, descricao,
                   data_inicio, data_fim, prazo_dias)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (company_id, order_id, tipo, descricao, hoje, data_fim, prazo_dias))
            flash(f'Garantia criada até {data_fim.strftime("%d/%m/%Y")}.', 'success')
            return redirect(url_for('garantia.garantia_lista'))

    return render_template('garantia_form.html', order=order)


@garantia_bp.route('/garantias/<int:gid>/acionar', methods=['POST'])
@login_required
def garantia_acionar(gid):
    """Registra acionamento de garantia."""
    db = get_db()
    company_id = get_company_id()
    obs = request.form.get('observacao', '')
    db.update("""
        UPDATE garantias
        SET status='acionada', acionada_em=NOW(), observacao=%s
        WHERE id=%s AND company_id=%s AND status='vigente'
    """, (obs, gid, company_id))
    flash('Garantia acionada com sucesso.', 'warning')
    return redirect(request.referrer or url_for('garantia.garantia_lista'))
