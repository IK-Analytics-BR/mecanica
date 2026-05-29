"""
Rotas para dashboards e relatórios do CMMS.

Antes da solicitação: caso já tenha na versão atual, avance para a próxima.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import calendar
import json

from database import get_db
from utils.auth import login_required

# Criar o blueprint
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@dashboard_bp.route('/cmms_dashboard')
@login_required
def cmms_dashboard():
    """Dashboard geral da mecânica."""
    db = get_db()

    # KPI: Veículos cadastrados
    try:
        equipment_stats = db.fetch_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN next_maintenance IS NOT NULL AND next_maintenance <= CURDATE() THEN 1 ELSE 0 END) as critical_count,
                SUM(CASE WHEN next_maintenance IS NOT NULL AND next_maintenance BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as warning_count,
                SUM(CASE WHEN next_maintenance IS NULL OR next_maintenance > DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as normal_count
            FROM equipment
            WHERE active = TRUE
        """)
    except Exception:
        equipment_stats = {'total': 0, 'critical_count': 0, 'warning_count': 0, 'normal_count': 0}

    # Estatísticas de ordens de serviço
    try:
        service_order_stats = db.fetch_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_count,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
                SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END) as canceled_count
            FROM service_orders
            WHERE active = TRUE
        """)
    except Exception:
        service_order_stats = {'total': 0, 'open_count': 0, 'in_progress_count': 0, 'completed_count': 0, 'canceled_count': 0}

    alert_stats = {'total': 0, 'active_count': 0, 'acknowledged_count': 0, 'resolved_count': 0, 'critical_count': 0, 'high_count': 0}
    maintenance_plan_stats = {'total': 0, 'preventive_count': 0, 'corrective_count': 0, 'predictive_count': 0}

    # OS por mês (últimos 12 meses)
    current_month = datetime.now().month
    current_year = datetime.now().year
    months_data = []
    for i in range(12):
        month = ((current_month - i - 1) % 12) + 1
        year = current_year if month <= current_month else current_year - 1
        month_name = calendar.month_name[month]
        try:
            month_orders = db.fetch_one("""
                SELECT COUNT(*) as count FROM service_orders
                WHERE MONTH(open_date) = %s AND YEAR(open_date) = %s
            """, (month, year))
        except Exception:
            month_orders = None
        months_data.append({'month': month_name, 'count': month_orders['count'] if month_orders else 0})
    months_data.reverse()

    # Top 5 veículos com mais OS
    try:
        top_equipment = db.fetch_all("""
            SELECT e.name as equipment_name, e.name as label, COUNT(so.id) as count
            FROM service_orders so
            JOIN equipment e ON so.equipment_id = e.id
            GROUP BY e.id, e.name
            ORDER BY count DESC
            LIMIT 5
        """)
    except Exception:
        top_equipment = []

    # Top 5 mecânicos com mais OS concluídas
    try:
        top_technicians = db.fetch_all("""
            SELECT t.name as technician_name, COUNT(so.id) as count
            FROM service_orders so
            JOIN technicians t ON so.technician_id = t.id
            WHERE so.technician_id IS NOT NULL AND so.status = 'completed'
            GROUP BY t.id, t.name
            ORDER BY count DESC
            LIMIT 5
        """)
    except Exception:
        top_technicians = []

    # KPI: Receita do mês atual
    try:
        receita_mes = db.fetch_one("""
            SELECT COALESCE(SUM(total_geral), 0) as receita
            FROM service_orders
            WHERE status = 'completed'
              AND MONTH(completion_date) = MONTH(CURDATE())
              AND YEAR(completion_date) = YEAR(CURDATE())
        """)
    except Exception:
        receita_mes = {'receita': 0}

    # KPI: Técnicos ativos
    try:
        tecnicos_ativos = db.fetch_one("SELECT COUNT(*) as total FROM technicians WHERE status = 'active'")
    except Exception:
        tecnicos_ativos = {'total': 0}

    # OS recentes
    try:
        recent_orders = db.fetch_all("""
            SELECT so.*, c.name as customer_name, e.name as equipment_name
            FROM service_orders so
            JOIN customers c ON so.customer_id = c.id
            JOIN equipment e ON so.equipment_id = e.id
            WHERE so.active = TRUE
            ORDER BY so.open_date DESC
            LIMIT 5
        """)
    except Exception:
        recent_orders = []

    recent_alerts = []
    upcoming_maintenance = []
    alert_types = {}

    return render_template(
        'cmms_dashboard.html',
        equipment_stats=equipment_stats,
        service_order_stats=service_order_stats,
        alert_stats=alert_stats,
        maintenance_plan_stats=maintenance_plan_stats,
        months_data=months_data,
        top_equipment=top_equipment,
        top_technicians=top_technicians,
        recent_orders=recent_orders,
        recent_alerts=recent_alerts,
        upcoming_maintenance=upcoming_maintenance,
        alert_types=alert_types,
        receita_mes=receita_mes,
        tecnicos_ativos=tecnicos_ativos,
        active_page='cmms_dashboard'
    )


@dashboard_bp.route('/maintenance_report')
@login_required
def maintenance_report():
    """Relatório de manutenções."""
    db = get_db()

    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    customer_id = request.args.get('customer_id')
    equipment_id = request.args.get('equipment_id')
    technician_id = request.args.get('technician_id')
    status = request.args.get('status')

    query = """
        SELECT so.*, c.name as customer_name, e.name as equipment_name,
               t.name as technician_name
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN technicians t ON so.technician_id = t.id
        WHERE so.active = TRUE
          AND so.open_date BETWEEN %s AND %s
    """
    params = [start_date, end_date]

    if customer_id:
        query += " AND so.customer_id = %s"
        params.append(customer_id)
    if equipment_id:
        query += " AND so.equipment_id = %s"
        params.append(equipment_id)
    if technician_id:
        query += " AND so.technician_id = %s"
        params.append(technician_id)
    if status:
        query += " AND so.status = %s"
        params.append(status)

    query += " ORDER BY so.open_date DESC"

    try:
        orders = db.fetch_all(query, tuple(params))
    except Exception:
        orders = []

    total_orders = len(orders)
    total_cost = 0
    total_downtime = 0

    for order in orders:
        try:
            items = db.fetch_all("""
                SELECT si.*, p.name as supply_name,
                       si.quantity * si.unit_price as subtotal
                FROM service_order_items si
                LEFT JOIN products p ON si.product_id = p.id
                WHERE si.service_order_id = %s
            """, (order['id'],))
        except Exception:
            items = []

        items_cost = sum((i.get('subtotal') or 0) for i in items)
        order_cost = items_cost + (order.get('labor_cost') or 0)

        order['order_items'] = items
        order['items_cost'] = items_cost
        order['labor'] = []
        order['labor_cost'] = order.get('labor_cost') or 0
        order['total_cost'] = order_cost
        order['maintenance_plan_task'] = None

        total_cost += order_cost
        total_downtime += order.get('downtime_minutes') or 0

    try:
        customers = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE ORDER BY name")
    except Exception:
        customers = []
    try:
        equipments = db.fetch_all("SELECT id, name, customer_id FROM equipment WHERE active = TRUE ORDER BY name")
    except Exception:
        equipments = []
    try:
        technicians = db.fetch_all("SELECT id, name FROM technicians ORDER BY name")
    except Exception:
        technicians = []

    return render_template(
        'maintenance_report.html',
        orders=orders,
        total_orders=total_orders,
        total_cost=total_cost,
        total_downtime=total_downtime,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        equipment_id=equipment_id,
        technician_id=technician_id,
        status=status,
        customers=customers,
        equipments=equipments,
        technicians=technicians,
        active_page='maintenance_report'
    )


@dashboard_bp.route('/cost_report')
@login_required
def cost_report():
    """Relatório de custos."""
    db = get_db()

    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    customer_id = request.args.get('customer_id')
    equipment_id = request.args.get('equipment_id')
    group_by = request.args.get('group_by', 'equipment')

    if group_by == 'customer':
        group_field = 'c.name'
        group_label = 'Cliente'
    elif group_by == 'type':
        group_field = 'so.status'
        group_label = 'Status'
    else:
        group_field = 'e.name'
        group_label = 'Equipamento'

    params = [start_date, end_date]
    extra = ""
    if customer_id:
        extra += " AND so.customer_id = %s"
        params.append(customer_id)
    if equipment_id:
        extra += " AND so.equipment_id = %s"
        params.append(equipment_id)

    try:
        costs_list = db.fetch_all(f"""
            SELECT {group_field} as group_name,
                   COALESCE(SUM(so.total_geral), 0) as total_cost,
                   0 as items_cost,
                   0 as labor_cost
            FROM service_orders so
            JOIN customers c ON so.customer_id = c.id
            JOIN equipment e ON so.equipment_id = e.id
            WHERE so.active = TRUE
              AND so.open_date BETWEEN %s AND %s
              {extra}
            GROUP BY {group_field}
            ORDER BY total_cost DESC
        """, tuple(params))
    except Exception:
        costs_list = []

    total_cost = sum(r.get('total_cost') or 0 for r in costs_list)
    total_items_cost = 0
    total_labor_cost = 0

    try:
        customers = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE ORDER BY name")
    except Exception:
        customers = []
    try:
        equipments = db.fetch_all("SELECT id, name, customer_id FROM equipment WHERE active = TRUE ORDER BY name")
    except Exception:
        equipments = []

    return render_template(
        'cost_report.html',
        costs=costs_list,
        total_items_cost=total_items_cost,
        total_labor_cost=total_labor_cost,
        total_cost=total_cost,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        equipment_id=equipment_id,
        group_by=group_by,
        group_label=group_label,
        customers=customers,
        equipments=equipments,
        active_page='cost_report'
    )


@dashboard_bp.route('/performance_report')
@login_required
def performance_report():
    """Relatório de desempenho dos mecânicos."""
    db = get_db()

    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    customer_id = request.args.get('customer_id')
    equipment_id = request.args.get('equipment_id')

    params = [start_date, end_date]
    extra = ""
    if customer_id:
        extra += " AND so.customer_id = %s"
        params.append(customer_id)
    if equipment_id:
        extra += " AND so.equipment_id = %s"
        params.append(equipment_id)

    try:
        performance_list = db.fetch_all(f"""
            SELECT e.name as equipment_name,
                   COUNT(so.id) as repair_count,
                   AVG(TIMESTAMPDIFF(HOUR, so.open_date, so.completion_date)) as mttr,
                   NULL as mtbf,
                   COUNT(so.id) as failure_count,
                   COALESCE(SUM(so.total_geral), 0) as total_cost,
                   0 as total_downtime_minutes,
                   100.0 as availability
            FROM service_orders so
            JOIN customers c ON so.customer_id = c.id
            JOIN equipment e ON so.equipment_id = e.id
            WHERE so.active = TRUE
              AND so.open_date BETWEEN %s AND %s
              AND so.status = 'completed'
              {extra}
            GROUP BY e.id, e.name
            ORDER BY repair_count DESC
        """, tuple(params))
    except Exception:
        performance_list = []

    try:
        customers = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE ORDER BY name")
    except Exception:
        customers = []
    try:
        equipments = db.fetch_all("SELECT id, name, customer_id FROM equipment WHERE active = TRUE ORDER BY name")
    except Exception:
        equipments = []

    return render_template(
        'performance_report.html',
        performance_data=performance_list,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        equipment_id=equipment_id,
        customers=customers,
        equipments=equipments,
        active_page='performance_report'
    )


@dashboard_bp.route('/export_report/<report_type>')
@login_required
def export_report(report_type):
    """Exporta um relatório em formato CSV."""
    if report_type == 'maintenance':
        return redirect(url_for('dashboard.maintenance_report', export=True))
    elif report_type == 'cost':
        return redirect(url_for('dashboard.cost_report', export=True))
    elif report_type == 'performance':
        return redirect(url_for('dashboard.performance_report', export=True))
    else:
        flash('Tipo de relatório inválido.', 'danger')
        return redirect(url_for('dashboard.cmms_dashboard'))
