"""
Rotas para gerenciamento de planos de manutenção.

Antes da solicitação: caso já tenha na versão atual, avance para a próxima.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from datetime import datetime, timedelta

from database import get_db
from utils.auth import login_required

# Criar o blueprint
maintenance_plan_bp = Blueprint('maintenance_plan', __name__)


@maintenance_plan_bp.route('/maintenance_plans')
@login_required
def maintenance_plan_list():
    """Lista todos os planos de manutenção."""
    db = get_db()
    
    # Buscar os planos de manutenção
    plans = db.fetch_all("""
        SELECT p.*, c.name as customer_name, e.name as equipment_name, s.name as supply_name
        FROM maintenance_plans p
        JOIN customers c ON p.customer_id = c.id
        JOIN equipment e ON p.equipment_id = e.id
        LEFT JOIN supplies s ON p.supply_id = s.id
        WHERE p.active = TRUE
        ORDER BY p.customer_id, p.equipment_id
    """)
    
    return render_template(
        'maintenance_plan_list.html',
        plans=plans,
        active_page='maintenance_plans'
    )

@maintenance_plan_bp.route('/maintenance_plans/add', methods=['GET', 'POST'])
@login_required
def maintenance_plan_add():
    """Adiciona um novo plano de manutenção."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        customer_id = request.form.get('customer_id')
        equipment_id = request.form.get('equipment_id')
        supply_id = request.form.get('supply_id') or None
        plan_type = request.form.get('type')
        trigger_type = request.form.get('trigger_type')
        trigger_value = request.form.get('trigger_value')
        task = request.form.get('task')
        instructions = request.form.get('instructions')
        standard_execution_time = request.form.get('standard_execution_time') or 60
        
        # Validar dados
        if not customer_id or not equipment_id or not plan_type or not trigger_type or not trigger_value or not task:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return redirect(url_for('maintenance_plan.maintenance_plan_add'))
        
        try:
            trigger_value = int(trigger_value)
            standard_execution_time = int(standard_execution_time)
            if trigger_value <= 0 or standard_execution_time <= 0:
                raise ValueError("Valores devem ser positivos")
        except ValueError:
            flash('Os valores de gatilho e tempo de execução devem ser números inteiros positivos.', 'danger')
            return redirect(url_for('maintenance_plan.maintenance_plan_add'))
        
        # Inserir plano de manutenção no banco de dados
        query = """
            INSERT INTO maintenance_plans (
                customer_id, equipment_id, supply_id, type, trigger_type, 
                trigger_value, task, instructions, standard_execution_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            customer_id, equipment_id, supply_id, plan_type, trigger_type,
            trigger_value, task, instructions, standard_execution_time
        )
        
        plan_id = db.insert(query, params)
        
        if plan_id:
            flash('Plano de manutenção cadastrado com sucesso!', 'success')
            return redirect(url_for('maintenance_plan.maintenance_plan_list'))
        else:
            flash('Erro ao cadastrar plano de manutenção.', 'danger')
    
    # Buscar clientes, equipamentos e insumos para o formulário
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
    
    supplies = db.fetch_all("""
        SELECT id, name FROM supplies
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'maintenance_plan_form.html',
        customers=customers,
        equipments=equipments,
        supplies=supplies,
        plan=None,
        active_page='maintenance_plans'
    )

@maintenance_plan_bp.route('/maintenance_plans/edit/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def maintenance_plan_edit(plan_id):
    """Edita um plano de manutenção existente."""
    db = get_db()
    
    # Buscar o plano de manutenção
    plan = db.fetch_one("""
        SELECT * FROM maintenance_plans
        WHERE id = %s
    """, (plan_id,))
    
    if not plan:
        flash('Plano de manutenção não encontrado.', 'danger')
        return redirect(url_for('maintenance_plan.maintenance_plan_list'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        customer_id = request.form.get('customer_id')
        equipment_id = request.form.get('equipment_id')
        supply_id = request.form.get('supply_id') or None
        plan_type = request.form.get('type')
        trigger_type = request.form.get('trigger_type')
        trigger_value = request.form.get('trigger_value')
        task = request.form.get('task')
        instructions = request.form.get('instructions')
        standard_execution_time = request.form.get('standard_execution_time') or 60
        
        # Validar dados
        if not customer_id or not equipment_id or not plan_type or not trigger_type or not trigger_value or not task:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return redirect(url_for('maintenance_plan.maintenance_plan_edit', plan_id=plan_id))
        
        try:
            trigger_value = int(trigger_value)
            standard_execution_time = int(standard_execution_time)
            if trigger_value <= 0 or standard_execution_time <= 0:
                raise ValueError("Valores devem ser positivos")
        except ValueError:
            flash('Os valores de gatilho e tempo de execução devem ser números inteiros positivos.', 'danger')
            return redirect(url_for('maintenance_plan.maintenance_plan_edit', plan_id=plan_id))
        
        # Atualizar plano de manutenção no banco de dados
        query = """
            UPDATE maintenance_plans
            SET customer_id = %s, equipment_id = %s, supply_id = %s, type = %s, 
                trigger_type = %s, trigger_value = %s, task = %s, 
                instructions = %s, standard_execution_time = %s
            WHERE id = %s
        """
        params = (
            customer_id, equipment_id, supply_id, plan_type, trigger_type,
            trigger_value, task, instructions, standard_execution_time, plan_id
        )
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Plano de manutenção atualizado com sucesso!', 'success')
            return redirect(url_for('maintenance_plan.maintenance_plan_list'))
        else:
            flash('Erro ao atualizar plano de manutenção.', 'danger')
    
    # Buscar clientes, equipamentos e insumos para o formulário
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
    
    supplies = db.fetch_all("""
        SELECT id, name FROM supplies
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'maintenance_plan_form.html',
        customers=customers,
        equipments=equipments,
        supplies=supplies,
        plan=plan,
        active_page='maintenance_plans'
    )

@maintenance_plan_bp.route('/maintenance_plans/view/<int:plan_id>')
@login_required
def maintenance_plan_view(plan_id):
    """Visualiza um plano de manutenção."""
    db = get_db()
    
    # Buscar o plano de manutenção
    plan = db.fetch_one("""
        SELECT p.*, c.name as customer_name, e.name as equipment_name, s.name as supply_name
        FROM maintenance_plans p
        JOIN customers c ON p.customer_id = c.id
        JOIN equipment e ON p.equipment_id = e.id
        LEFT JOIN supplies s ON p.supply_id = s.id
        WHERE p.id = %s
    """, (plan_id,))
    
    if not plan:
        flash('Plano de manutenção não encontrado.', 'danger')
        return redirect(url_for('maintenance_plan.maintenance_plan_list'))
    
    # Buscar ordens de serviço relacionadas a este plano
    service_orders = db.fetch_all("""
        SELECT so.*, u.name as technician_name
        FROM service_orders so
        LEFT JOIN users u ON so.technician_id = u.id
        WHERE so.maintenance_plan_id = %s
        ORDER BY so.open_date DESC
    """, (plan_id,))
    
    # Calcular próxima manutenção com base no tipo de gatilho
    next_maintenance = None
    if plan['trigger_type'] == 'time':
        # Gatilho baseado em tempo (dias)
        last_maintenance = db.fetch_one("""
            SELECT MAX(completion_date) as last_date
            FROM service_orders
            WHERE maintenance_plan_id = %s AND status = 'completed'
        """, (plan_id,))
        
        if last_maintenance and last_maintenance['last_date']:
            next_date = last_maintenance['last_date'] + timedelta(days=plan['trigger_value'])
            next_maintenance = {
                'date': next_date,
                'remaining': (next_date - datetime.now()).days
            }
    
    elif plan['trigger_type'] == 'hours':
        # Gatilho baseado em horas de operação
        equipment = db.fetch_one("""
            SELECT accumulated_hours
            FROM equipment
            WHERE id = %s
        """, (plan['equipment_id'],))
        
        if equipment and equipment['accumulated_hours'] is not None:
            last_maintenance = db.fetch_one("""
                SELECT MAX(so.completion_date) as last_date, MAX(e.accumulated_hours) as hours_at_maintenance
                FROM service_orders so
                JOIN equipment e ON so.equipment_id = e.id
                WHERE so.maintenance_plan_id = %s AND so.status = 'completed'
            """, (plan_id,))
            
            hours_at_maintenance = 0
            if last_maintenance and last_maintenance['hours_at_maintenance']:
                hours_at_maintenance = last_maintenance['hours_at_maintenance']
            
            next_hours = hours_at_maintenance + plan['trigger_value']
            next_maintenance = {
                'hours': next_hours,
                'remaining': next_hours - equipment['accumulated_hours']
            }
    
    return render_template(
        'maintenance_plan_view.html',
        plan=plan,
        service_orders=service_orders,
        next_maintenance=next_maintenance,
        active_page='maintenance_plans'
    )

@maintenance_plan_bp.route('/maintenance_plans/delete/<int:plan_id>', methods=['POST'])
@login_required
def maintenance_plan_delete(plan_id):
    """Exclui um plano de manutenção."""
    db = get_db()
    
    # Verificar se existem ordens de serviço associadas a este plano
    service_orders = db.fetch_one("""
        SELECT COUNT(*) as count
        FROM service_orders
        WHERE maintenance_plan_id = %s
    """, (plan_id,))
    
    if service_orders and service_orders['count'] > 0:
        flash('Não é possível excluir o plano de manutenção pois existem ordens de serviço associadas a ele.', 'danger')
        return redirect(url_for('maintenance_plan.maintenance_plan_list'))
    
    # Excluir o plano de manutenção (exclusão lógica)
    affected_rows = db.update("""
        UPDATE maintenance_plans
        SET active = FALSE
        WHERE id = %s
    """, (plan_id,))
    
    if affected_rows > 0:
        flash('Plano de manutenção excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir plano de manutenção.', 'danger')
    
    return redirect(url_for('maintenance_plan.maintenance_plan_list'))

@maintenance_plan_bp.route('/maintenance_plans/calendar')
@login_required
def maintenance_plan_calendar():
    """Exibe o calendário de manutenções."""
    db = get_db()
    
    # Buscar os planos de manutenção baseados em tempo
    time_plans = db.fetch_all("""
        SELECT p.*, c.name as customer_name, e.name as equipment_name, s.name as supply_name,
               MAX(so.completion_date) as last_maintenance
        FROM maintenance_plans p
        JOIN customers c ON p.customer_id = c.id
        JOIN equipment e ON p.equipment_id = e.id
        LEFT JOIN supplies s ON p.supply_id = s.id
        LEFT JOIN service_orders so ON p.id = so.maintenance_plan_id AND so.status = 'completed'
        WHERE p.active = TRUE AND p.trigger_type = 'time'
        GROUP BY p.id, c.name, e.name, s.name
        ORDER BY last_maintenance
    """)
    
    # Calcular próximas manutenções para planos baseados em tempo
    calendar_events = []
    today = datetime.now().date()
    
    for plan in time_plans:
        last_date = plan['last_maintenance'].date() if plan['last_maintenance'] else today - timedelta(days=plan['trigger_value'])
        next_date = last_date + timedelta(days=plan['trigger_value'])
        days_remaining = (next_date - today).days
        
        status = 'normal'
        if days_remaining <= 0:
            status = 'overdue'
        elif days_remaining <= 7:
            status = 'warning'
        
        calendar_events.append({
            'plan_id': plan['id'],
            'customer': plan['customer_name'],
            'equipment': plan['equipment_name'],
            'supply': plan['supply_name'],
            'task': plan['task'],
            'last_date': last_date,
            'next_date': next_date,
            'days_remaining': days_remaining,
            'status': status
        })
    
    # Ordenar eventos por data da próxima manutenção
    calendar_events.sort(key=lambda x: x['next_date'])
    
    return render_template(
        'maintenance_plan_calendar.html',
        calendar_events=calendar_events,
        active_page='maintenance_plans'
    )
