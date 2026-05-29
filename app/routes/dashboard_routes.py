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
    """Dashboard geral do CMMS."""
    db = get_db()
    
    # KPI: Veículos cadastrados
    equipment_stats = db.fetch_one("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN next_maintenance IS NOT NULL AND next_maintenance <= CURDATE() THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN next_maintenance IS NOT NULL AND next_maintenance BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as warning_count,
            SUM(CASE WHEN next_maintenance IS NULL OR next_maintenance > DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as normal_count
        FROM equipment
        WHERE active = TRUE
    """)
    
    # Estatísticas de ordens de serviço
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
    
    # Estatísticas de alertas
    alert_stats = db.fetch_one("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_count,
            SUM(CASE WHEN status = 'acknowledged' THEN 1 ELSE 0 END) as acknowledged_count,
            SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved_count,
            SUM(CASE WHEN priority = 'critical' THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN priority = 'high' THEN 1 ELSE 0 END) as high_count
        FROM alerts
    """)
    
    # Estatísticas de planos de manutenção
    maintenance_plan_stats = db.fetch_one("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN type = 'preventive' THEN 1 ELSE 0 END) as preventive_count,
            SUM(CASE WHEN type = 'corrective' THEN 1 ELSE 0 END) as corrective_count,
            SUM(CASE WHEN type = 'predictive' THEN 1 ELSE 0 END) as predictive_count
        FROM maintenance_plans
        WHERE active = TRUE
    """)
    
    # Ordens de serviço por mês (últimos 12 meses)
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    months_data = []
    for i in range(12):
        month = ((current_month - i - 1) % 12) + 1
        year = current_year if month <= current_month else current_year - 1
        
        month_name = calendar.month_name[month]
        
        # Contar ordens de serviço para este mês
        month_orders = db.fetch_one("""
            SELECT COUNT(*) as count
            FROM service_orders
            WHERE MONTH(open_date) = %s AND YEAR(open_date) = %s
        """, (month, year))
        
        months_data.append({
            'month': month_name,
            'count': month_orders['count'] if month_orders else 0
        })
    
    # Inverter para ordem cronológica
    months_data.reverse()
    
    # Top 5 veículos com mais OS
    top_equipment = db.fetch_all("""
        SELECT e.name as equipment_name,
               e.name as label,
               COUNT(so.id) as count
        FROM service_orders so
        JOIN equipment e ON so.equipment_id = e.id
        GROUP BY e.id, e.name
        ORDER BY count DESC
        LIMIT 5
    """)

    # Top 5 mecânicos com mais OS concluídas
    top_technicians = db.fetch_all("""
        SELECT t.name as technician_name, COUNT(so.id) as count
        FROM service_orders so
        JOIN technicians t ON so.technician_id = t.id
        WHERE so.technician_id IS NOT NULL
          AND so.status = 'completed'
        GROUP BY t.id, t.name
        ORDER BY count DESC
        LIMIT 5
    """)

    # KPI: Receita do mês atual (OS concluídas)
    receita_mes = db.fetch_one("""
        SELECT COALESCE(SUM(total_cost), 0) as receita
        FROM service_orders
        WHERE status = 'completed'
          AND MONTH(completion_date) = MONTH(CURDATE())
          AND YEAR(completion_date)  = YEAR(CURDATE())
    """)

    # KPI: Técnicos ativos
    tecnicos_ativos = db.fetch_one("""
        SELECT COUNT(*) as total FROM technicians WHERE status = 'active'
    """)
    
    # Ordens de serviço recentes
    recent_orders = db.fetch_all("""
        SELECT so.*, c.name as customer_name, e.name as equipment_name, 
               u.name as technician_name
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN users u ON so.technician_id = u.id
        WHERE so.active = TRUE
        ORDER BY so.open_date DESC
        LIMIT 5
    """)
    
    # Alertas recentes
    recent_alerts = db.fetch_all("""
        SELECT a.*, e.name as equipment_name, s.name as supply_name
        FROM alerts a
        JOIN equipment e ON a.equipment_id = e.id
        LEFT JOIN supplies s ON a.supply_id = s.id
        ORDER BY a.created_at DESC
        LIMIT 5
    """)
    
    # Próximas manutenções programadas
    upcoming_maintenance = db.fetch_all("""
        SELECT mp.*, e.name as equipment_name, s.name as supply_name,
               MAX(so.completion_date) as last_maintenance
        FROM maintenance_plans mp
        JOIN equipment e ON mp.equipment_id = e.id
        LEFT JOIN supplies s ON mp.supply_id = s.id
        LEFT JOIN service_orders so ON mp.id = so.maintenance_plan_id AND so.status = 'completed'
        WHERE mp.active = TRUE AND mp.trigger_type = 'time'
        GROUP BY mp.id, e.name, s.name
        ORDER BY last_maintenance
        LIMIT 5
    """)
    
    # Calcular próximas datas de manutenção
    today = datetime.now().date()
    for plan in upcoming_maintenance:
        last_date = plan['last_maintenance'].date() if plan['last_maintenance'] else today - timedelta(days=plan['trigger_value'])
        next_date = last_date + timedelta(days=plan['trigger_value'])
        days_remaining = (next_date - today).days
        
        plan['next_date'] = next_date
        plan['days_remaining'] = days_remaining
        
        if days_remaining <= 0:
            plan['status'] = 'overdue'
        elif days_remaining <= 7:
            plan['status'] = 'warning'
        else:
            plan['status'] = 'normal'
    
    # Tipos de alerta para exibição
    alert_types = {
        'wear_80': 'Desgaste 80%',
        'wear_100': 'Desgaste 100%',
        'stock_low': 'Estoque Baixo',
        'maintenance_due': 'Manutenção Programada',
        'os_created': 'OS Criada',
        'os_assigned': 'OS Atribuída',
        'os_completed': 'OS Concluída'
    }
    
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
    
    # Filtros
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    customer_id = request.args.get('customer_id')
    equipment_id = request.args.get('equipment_id')
    technician_id = request.args.get('technician_id')
    status = request.args.get('status')
    
    # Construir a consulta SQL
    query = """
        SELECT so.*, c.name as customer_name, e.name as equipment_name, 
               s.name as supply_name, u.name as technician_name,
               mp.task as maintenance_plan_task
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN supplies s ON so.supply_id = s.id
        LEFT JOIN users u ON so.technician_id = u.id
        LEFT JOIN maintenance_plans mp ON so.maintenance_plan_id = mp.id
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
    
    # Executar a consulta
    orders = db.fetch_all(query, tuple(params))
    
    # Calcular estatísticas
    total_orders = len(orders)
    total_cost = 0
    total_downtime = 0
    
    for order in orders:
        # Buscar itens da ordem de serviço
        items = db.fetch_all("""
            SELECT i.*, s.name as supply_name
            FROM service_order_items i
            JOIN supplies s ON i.supply_id = s.id
            WHERE i.service_order_id = %s
        """, (order['id'],))
        
        # Buscar horas trabalhadas
        labor = db.fetch_all("""
            SELECT l.*, u.name as technician_name
            FROM service_order_labor l
            JOIN users u ON l.technician_id = u.id
            WHERE l.service_order_id = %s
        """, (order['id'],))
        
        # Calcular custos
        items_cost = sum(item['quantity'] * item['unit_cost'] for item in items)
        labor_cost = sum(l['hours_worked'] * l['hourly_rate'] for l in labor)
        order_cost = items_cost + labor_cost
        
        order['order_items'] = items
        order['labor'] = labor
        order['items_cost'] = items_cost
        order['labor_cost'] = labor_cost
        order['total_cost'] = order_cost
        
        total_cost += order_cost
        total_downtime += order['downtime_minutes'] or 0
    
    # Buscar clientes, equipamentos e técnicos para filtros
    customers = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    equipments = db.fetch_all("""
        SELECT id, name, customer_id FROM equipment
        WHERE active = TRUE
        ORDER BY name
    """)
    
    technicians = db.fetch_all("""
        SELECT id, name FROM users
        WHERE role = 'user' AND specialty IS NOT NULL
        ORDER BY name
    """)
    
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
    
    # Filtros
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    customer_id = request.args.get('customer_id')
    equipment_id = request.args.get('equipment_id')
    group_by = request.args.get('group_by', 'equipment')
    
    # Construir a consulta SQL base
    base_query = """
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN service_order_items soi ON so.id = soi.service_order_id
        LEFT JOIN service_order_labor sol ON so.id = sol.service_order_id
        WHERE so.active = TRUE
          AND so.open_date BETWEEN %s AND %s
    """
    
    params = [start_date, end_date]
    
    if customer_id:
        base_query += " AND so.customer_id = %s"
        params.append(customer_id)
    
    if equipment_id:
        base_query += " AND so.equipment_id = %s"
        params.append(equipment_id)
    
    # Agrupar por cliente, equipamento ou tipo de manutenção
    if group_by == 'customer':
        group_field = 'c.name'
        group_label = 'Cliente'
    elif group_by == 'equipment':
        group_field = 'e.name'
        group_label = 'Equipamento'
    elif group_by == 'type':
        group_field = 'so.type'
        group_label = 'Tipo'
    else:
        group_field = 'e.name'
        group_label = 'Equipamento'
    
    # Consulta para custos de peças
    items_query = f"""
        SELECT {group_field} as group_name,
               SUM(soi.quantity * soi.unit_cost) as items_cost
        {base_query}
        GROUP BY {group_field}
    """
    
    # Consulta para custos de mão de obra
    labor_query = f"""
        SELECT {group_field} as group_name,
               SUM(sol.hours_worked * sol.hourly_rate) as labor_cost
        {base_query}
        GROUP BY {group_field}
    """
    
    # Executar as consultas
    items_costs = db.fetch_all(items_query, tuple(params))
    labor_costs = db.fetch_all(labor_query, tuple(params))
    
    # Combinar os resultados
    costs_by_group = {}
    
    for item in items_costs:
        group_name = item['group_name']
        if group_name not in costs_by_group:
            costs_by_group[group_name] = {'items_cost': 0, 'labor_cost': 0}
        costs_by_group[group_name]['items_cost'] = item['items_cost'] or 0
    
    for labor in labor_costs:
        group_name = labor['group_name']
        if group_name not in costs_by_group:
            costs_by_group[group_name] = {'items_cost': 0, 'labor_cost': 0}
        costs_by_group[group_name]['labor_cost'] = labor['labor_cost'] or 0
    
    # Calcular totais
    for group_name, costs in costs_by_group.items():
        costs['total_cost'] = costs['items_cost'] + costs['labor_cost']
    
    # Converter para lista e ordenar por custo total
    costs_list = [{'group_name': k, **v} for k, v in costs_by_group.items()]
    costs_list.sort(key=lambda x: x['total_cost'], reverse=True)
    
    # Calcular totais gerais
    total_items_cost = sum(item['items_cost'] for item in costs_list)
    total_labor_cost = sum(item['labor_cost'] for item in costs_list)
    total_cost = total_items_cost + total_labor_cost
    
    # Buscar clientes e equipamentos para filtros
    customers = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    equipments = db.fetch_all("""
        SELECT id, name, customer_id FROM equipment
        WHERE active = TRUE
        ORDER BY name
    """)
    
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
    """Relatório de desempenho."""
    db = get_db()
    
    # Filtros
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    customer_id = request.args.get('customer_id')
    equipment_id = request.args.get('equipment_id')
    
    # Construir a consulta SQL base
    base_query = """
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        JOIN equipment e ON so.equipment_id = e.id
        WHERE so.active = TRUE
          AND so.open_date BETWEEN %s AND %s
          AND so.status = 'completed'
    """
    
    params = [start_date, end_date]
    
    if customer_id:
        base_query += " AND so.customer_id = %s"
        params.append(customer_id)
    
    if equipment_id:
        base_query += " AND so.equipment_id = %s"
        params.append(equipment_id)
    
    # Consulta para MTBF (Mean Time Between Failures)
    # LAG() não pode ser usado diretamente no mesmo SELECT que tem GROUP BY;
    # usamos uma subquery para calcular os intervalos primeiro.
    mtbf_query = f"""
        SELECT equipment_name,
               COUNT(*) as failure_count,
               SUM(total_downtime_h) as total_downtime,
               AVG(time_since_last_h) as mtbf
        FROM (
            SELECT e.name as equipment_name,
                   TIMESTAMPDIFF(HOUR, so.open_date, so.completion_date) as total_downtime_h,
                   TIMESTAMPDIFF(HOUR,
                       LAG(so.completion_date) OVER (PARTITION BY so.equipment_id ORDER BY so.open_date),
                       so.open_date) as time_since_last_h
            {base_query}
            AND so.type = 'corrective'
        ) sub
        WHERE time_since_last_h IS NOT NULL
        GROUP BY equipment_name
        HAVING COUNT(*) > 1
    """
    
    # Consulta para MTTR (Mean Time To Repair)
    mttr_query = f"""
        SELECT e.name as equipment_name,
               COUNT(so.id) as repair_count,
               AVG(TIMESTAMPDIFF(HOUR, so.open_date, so.completion_date)) as mttr
        {base_query}
        GROUP BY e.name
    """
    
    # Consulta para disponibilidade
    availability_query = f"""
        SELECT e.name as equipment_name,
               SUM(so.downtime_minutes) as total_downtime_minutes,
               TIMESTAMPDIFF(MINUTE, %s, %s) as total_period_minutes
        {base_query}
        GROUP BY e.name
    """
    
    availability_params = [start_date, end_date] + params[2:] if len(params) > 2 else [start_date, end_date]
    
    # Executar as consultas
    mtbf_data = db.fetch_all(mtbf_query, tuple(params))
    mttr_data = db.fetch_all(mttr_query, tuple(params))
    availability_data = db.fetch_all(availability_query, tuple(availability_params))
    
    # Combinar os resultados
    performance_data = {}
    
    for item in mtbf_data:
        equipment_name = item['equipment_name']
        if equipment_name not in performance_data:
            performance_data[equipment_name] = {}
        performance_data[equipment_name]['mtbf'] = item['mtbf']
        performance_data[equipment_name]['failure_count'] = item['failure_count']
    
    for item in mttr_data:
        equipment_name = item['equipment_name']
        if equipment_name not in performance_data:
            performance_data[equipment_name] = {}
        performance_data[equipment_name]['mttr'] = item['mttr']
        performance_data[equipment_name]['repair_count'] = item['repair_count']
    
    for item in availability_data:
        equipment_name = item['equipment_name']
        if equipment_name not in performance_data:
            performance_data[equipment_name] = {}
        
        total_downtime_minutes = item['total_downtime_minutes'] or 0
        total_period_minutes = item['total_period_minutes'] or 1  # Evitar divisão por zero
        
        availability = 1 - (total_downtime_minutes / total_period_minutes)
        performance_data[equipment_name]['availability'] = availability
        performance_data[equipment_name]['total_downtime_minutes'] = total_downtime_minutes
    
    # Converter para lista
    performance_list = [{'equipment_name': k, **v} for k, v in performance_data.items()]
    
    # Buscar clientes e equipamentos para filtros
    customers = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    equipments = db.fetch_all("""
        SELECT id, name, customer_id FROM equipment
        WHERE active = TRUE
        ORDER BY name
    """)
    
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
