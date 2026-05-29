"""
Rotas para gerenciamento de alertas e notificações.

Antes da solicitação: caso já tenha na versão atual, avance para a próxima.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps

from database import get_db
from utils.auth import login_required
from services.notification_service import NotificationService

# Criar o blueprint
alert_bp = Blueprint('alert', __name__)


@alert_bp.route('/alerts')
@login_required
def alert_list():
    """Lista todos os alertas ativos."""
    # Obter parâmetros de filtro
    equipment_id = request.args.get('equipment_id')
    supply_id = request.args.get('supply_id')
    alert_type = request.args.get('alert_type')
    
    # Converter para inteiro se não for None
    if equipment_id:
        try:
            equipment_id = int(equipment_id)
        except ValueError:
            equipment_id = None
    
    if supply_id:
        try:
            supply_id = int(supply_id)
        except ValueError:
            supply_id = None
    
    # Obter alertas ativos
    alerts = NotificationService.get_active_alerts(
        equipment_id=equipment_id,
        supply_id=supply_id,
        alert_type=alert_type
    )
    
    # Obter equipamentos e componentes para filtros
    db = get_db()
    equipments = db.fetch_all("""
        SELECT id, name FROM equipment
        WHERE active = TRUE
        ORDER BY name
    """)
    
    supplies = db.fetch_all("""
        SELECT id, name FROM supplies
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'alert_list.html',
        alerts=alerts,
        equipments=equipments,
        supplies=supplies,
        alert_types=NotificationService.ALERT_TYPES,
        priority_levels=NotificationService.PRIORITY_LEVELS,
        active_page='alerts'
    )

@alert_bp.route('/alerts/history')
@login_required
def alert_history():
    """Lista o histórico de alertas."""
    # Obter parâmetros de filtro
    equipment_id = request.args.get('equipment_id')
    supply_id = request.args.get('supply_id')
    alert_type = request.args.get('alert_type')
    
    # Converter para inteiro se não for None
    if equipment_id:
        try:
            equipment_id = int(equipment_id)
        except ValueError:
            equipment_id = None
    
    if supply_id:
        try:
            supply_id = int(supply_id)
        except ValueError:
            supply_id = None
    
    # Obter histórico de alertas
    alerts = NotificationService.get_alert_history(
        equipment_id=equipment_id,
        supply_id=supply_id,
        alert_type=alert_type
    )
    
    # Obter equipamentos e componentes para filtros
    db = get_db()
    equipments = db.fetch_all("""
        SELECT id, name FROM equipment
        WHERE active = TRUE
        ORDER BY name
    """)
    
    supplies = db.fetch_all("""
        SELECT id, name FROM supplies
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'alert_history.html',
        alerts=alerts,
        equipments=equipments,
        supplies=supplies,
        alert_types=NotificationService.ALERT_TYPES,
        priority_levels=NotificationService.PRIORITY_LEVELS,
        active_page='alerts'
    )

@alert_bp.route('/alerts/view/<int:alert_id>')
@login_required
def alert_view(alert_id):
    """Visualiza um alerta específico."""
    db = get_db()
    
    # Buscar o alerta
    alert = db.fetch_one("""
        SELECT a.*, e.name as equipment_name, s.name as supply_name,
               u1.name as acknowledged_by_name, u2.name as resolved_by_name
        FROM alerts a
        JOIN equipment e ON a.equipment_id = e.id
        LEFT JOIN supplies s ON a.supply_id = s.id
        LEFT JOIN users u1 ON a.acknowledged_by = u1.id
        LEFT JOIN users u2 ON a.resolved_by = u2.id
        WHERE a.id = %s
    """, (alert_id,))
    
    if not alert:
        flash('Alerta não encontrado.', 'danger')
        return redirect(url_for('alert.alert_list'))
    
    # Buscar informações relacionadas ao alerta
    related_info = {}
    
    # Se for um alerta de desgaste, buscar informações do equipamento/componente
    if alert['alert_type'] in ['wear_80', 'wear_100']:
        if alert['supply_id']:
            # Buscar informações do componente
            supply = db.fetch_one("""
                SELECT s.*, e.name as equipment_name
                FROM supplies s
                JOIN installed_supplies i ON s.id = i.supply_id
                JOIN equipment e ON i.equipment_id = e.id
                WHERE s.id = %s
            """, (alert['supply_id'],))
            
            if supply:
                related_info['supply'] = supply
        else:
            # Buscar informações do equipamento
            equipment = db.fetch_one("""
                SELECT * FROM equipment
                WHERE id = %s
            """, (alert['equipment_id'],))
            
            if equipment:
                related_info['equipment'] = equipment
    
    # Se for um alerta de estoque baixo, buscar informações do estoque
    elif alert['alert_type'] == 'stock_low':
        supply = db.fetch_one("""
            SELECT * FROM supplies
            WHERE id = %s
        """, (alert['supply_id'],))
        
        if supply:
            related_info['supply'] = supply
    
    # Se for um alerta de manutenção programada, buscar informações do plano de manutenção
    elif alert['alert_type'] == 'maintenance_due':
        maintenance_plan = db.fetch_one("""
            SELECT mp.*, e.name as equipment_name, s.name as supply_name
            FROM maintenance_plans mp
            JOIN equipment e ON mp.equipment_id = e.id
            LEFT JOIN supplies s ON mp.supply_id = s.id
            WHERE mp.equipment_id = %s
            ORDER BY mp.id DESC
            LIMIT 1
        """, (alert['equipment_id'],))
        
        if maintenance_plan:
            related_info['maintenance_plan'] = maintenance_plan
    
    # Se for um alerta de OS, buscar informações da OS
    elif alert['alert_type'] in ['os_created', 'os_assigned', 'os_completed']:
        service_order = db.fetch_one("""
            SELECT so.*, e.name as equipment_name, u.name as technician_name
            FROM service_orders so
            JOIN equipment e ON so.equipment_id = e.id
            LEFT JOIN users u ON so.technician_id = u.id
            WHERE so.equipment_id = %s
            ORDER BY so.id DESC
            LIMIT 1
        """, (alert['equipment_id'],))
        
        if service_order:
            related_info['service_order'] = service_order
    
    return render_template(
        'alert_view.html',
        alert=alert,
        related_info=related_info,
        alert_types=NotificationService.ALERT_TYPES,
        priority_levels=NotificationService.PRIORITY_LEVELS,
        active_page='alerts'
    )

@alert_bp.route('/alerts/acknowledge/<int:alert_id>', methods=['POST'])
@login_required
def alert_acknowledge(alert_id):
    """Reconhece um alerta."""
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Usuário não identificado.', 'danger')
        return redirect(url_for('alert.alert_list'))
    
    success = NotificationService.acknowledge_alert(alert_id, user_id)
    
    if success:
        flash('Alerta reconhecido com sucesso!', 'success')
    else:
        flash('Erro ao reconhecer alerta.', 'danger')
    
    return redirect(url_for('alert.alert_view', alert_id=alert_id))

@alert_bp.route('/alerts/resolve/<int:alert_id>', methods=['POST'])
@login_required
def alert_resolve(alert_id):
    """Resolve um alerta."""
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Usuário não identificado.', 'danger')
        return redirect(url_for('alert.alert_list'))
    
    success = NotificationService.resolve_alert(alert_id, user_id)
    
    if success:
        flash('Alerta resolvido com sucesso!', 'success')
    else:
        flash('Erro ao resolver alerta.', 'danger')
    
    return redirect(url_for('alert.alert_view', alert_id=alert_id))

@alert_bp.route('/alerts/create', methods=['GET', 'POST'])
@login_required
def alert_create():
    """Cria um alerta manualmente."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        equipment_id = request.form.get('equipment_id')
        supply_id = request.form.get('supply_id') or None
        alert_type = request.form.get('alert_type')
        message = request.form.get('message')
        priority = request.form.get('priority')
        
        # Validar dados
        if not equipment_id or not alert_type or not priority:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return redirect(url_for('alert.alert_create'))
        
        # Criar o alerta
        alert_id = NotificationService.create_alert(
            equipment_id=int(equipment_id),
            supply_id=int(supply_id) if supply_id else None,
            alert_type=alert_type,
            message=message,
            priority=priority
        )
        
        if alert_id:
            flash('Alerta criado com sucesso!', 'success')
            return redirect(url_for('alert.alert_view', alert_id=alert_id))
        else:
            flash('Erro ao criar alerta.', 'danger')
    
    # Obter equipamentos e componentes para o formulário
    equipments = db.fetch_all("""
        SELECT id, name FROM equipment
        WHERE active = TRUE
        ORDER BY name
    """)
    
    supplies = db.fetch_all("""
        SELECT id, name FROM supplies
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'alert_form.html',
        equipments=equipments,
        supplies=supplies,
        alert_types=NotificationService.ALERT_TYPES,
        priority_levels=NotificationService.PRIORITY_LEVELS,
        active_page='alerts'
    )

@alert_bp.route('/alerts/count', methods=['GET'])
@login_required
def alert_count():
    """Retorna o número de alertas ativos (para notificações em tempo real)."""
    alerts = NotificationService.get_active_alerts()
    
    return jsonify({
        'count': len(alerts),
        'high_priority': sum(1 for a in alerts if a['priority'] in ['high', 'critical'])
    })

@alert_bp.route('/alerts/dashboard')
@login_required
def alert_dashboard():
    """Dashboard de alertas."""
    db = get_db()
    
    # Estatísticas de alertas
    stats = db.fetch_one("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_count,
            SUM(CASE WHEN status = 'acknowledged' THEN 1 ELSE 0 END) as acknowledged_count,
            SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved_count,
            SUM(CASE WHEN priority = 'critical' THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN priority = 'high' THEN 1 ELSE 0 END) as high_count,
            SUM(CASE WHEN priority = 'medium' THEN 1 ELSE 0 END) as medium_count,
            SUM(CASE WHEN priority = 'low' THEN 1 ELSE 0 END) as low_count
        FROM alerts
    """)
    
    # Alertas por tipo
    by_type = db.fetch_all("""
        SELECT alert_type, COUNT(*) as count
        FROM alerts
        GROUP BY alert_type
    """)
    
    # Alertas por equipamento (top 5)
    by_equipment = db.fetch_all("""
        SELECT e.name as equipment_name, COUNT(*) as count
        FROM alerts a
        JOIN equipment e ON a.equipment_id = e.id
        GROUP BY e.name
        ORDER BY count DESC
        LIMIT 5
    """)
    
    # Alertas por mês (últimos 6 meses)
    by_month = db.fetch_all("""
        SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as count
        FROM alerts
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(created_at, '%Y-%m')
        ORDER BY month
    """)
    
    # Alertas recentes
    recent_alerts = db.fetch_all("""
        SELECT a.*, e.name as equipment_name, s.name as supply_name
        FROM alerts a
        JOIN equipment e ON a.equipment_id = e.id
        LEFT JOIN supplies s ON a.supply_id = s.id
        ORDER BY a.created_at DESC
        LIMIT 10
    """)
    
    return render_template(
        'alert_dashboard.html',
        stats=stats,
        by_type=by_type,
        by_equipment=by_equipment,
        by_month=by_month,
        recent_alerts=recent_alerts,
        alert_types=NotificationService.ALERT_TYPES,
        priority_levels=NotificationService.PRIORITY_LEVELS,
        active_page='alerts'
    )

@alert_bp.route('/alerts/config', methods=['GET', 'POST'])
@login_required
def alert_config():
    """Configurações de notificações por e-mail."""
    # Verificar se o usuário é administrador
    if session.get('role') != 'admin':
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('alert.alert_list'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        smtp_server = request.form.get('smtp_server')
        smtp_port = request.form.get('smtp_port')
        username = request.form.get('username')
        password = request.form.get('password')
        from_email = request.form.get('from_email')
        to_email = request.form.get('to_email')
        
        # Validar dados
        if not smtp_server or not smtp_port or not username or not password or not from_email or not to_email:
            flash('Por favor, preencha todos os campos.', 'danger')
            return redirect(url_for('alert.alert_config'))
        
        try:
            smtp_port = int(smtp_port)
        except ValueError:
            flash('A porta SMTP deve ser um número inteiro.', 'danger')
            return redirect(url_for('alert.alert_config'))
        
        # Salvar configurações
        success = NotificationService.create_email_config(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            username=username,
            password=password,
            from_email=from_email,
            to_email=to_email
        )
        
        if success:
            flash('Configurações de e-mail salvas com sucesso!', 'success')
        else:
            flash('Erro ao salvar configurações de e-mail.', 'danger')
    
    return render_template(
        'alert_config.html',
        active_page='alerts'
    )
