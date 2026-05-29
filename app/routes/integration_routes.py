"""
Rotas para gerenciamento de integrações com ERP e IoT.

Antes da solicitação: caso já tenha na versão atual, avance para a próxima.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import json

from database import get_db
from utils.auth import login_required
from services.erp_integration_service import ERPIntegrationService
from services.iot_integration_service import IoTIntegrationService

# Criar o blueprint
integration_bp = Blueprint('integration', __name__)


# Decorador para verificar se o usuário é administrador
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        
        db = get_db()
        user = db.fetch_one("SELECT role FROM users WHERE username = %s", (session['username'],))
        
        if not user or user['role'] != 'admin':
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

@integration_bp.route('/integrations')
@admin_required
def integrations_dashboard():
    """Dashboard de integrações."""
    erp_service = ERPIntegrationService()
    iot_service = IoTIntegrationService()
    
    erp_status = erp_service.get_erp_status()
    iot_status = iot_service.get_iot_status()
    
    return render_template(
        'integrations_dashboard.html',
        erp_status=erp_status,
        iot_status=iot_status,
        active_page='integrations'
    )

# Rotas para ERP
@integration_bp.route('/integrations/erp')
@admin_required
def erp_config():
    """Configuração da integração com ERP."""
    erp_service = ERPIntegrationService()
    erp_status = erp_service.get_erp_status()
    
    # Buscar clientes para mapeamento
    db = get_db()
    customers = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE ORDER BY name")
    
    return render_template(
        'erp_config.html',
        erp_status=erp_status,
        customers=customers,
        active_page='integrations'
    )

@integration_bp.route('/integrations/erp/update', methods=['POST'])
@admin_required
def erp_update_config():
    """Atualiza a configuração da integração com ERP."""
    config_data = {
        'enabled': request.form.get('enabled') == 'on',
        'erp_type': request.form.get('erp_type'),
        'base_url': request.form.get('base_url'),
        'api_key': request.form.get('api_key'),
        'username': request.form.get('username'),
        'password': request.form.get('password'),
        'sync_interval': int(request.form.get('sync_interval', 3600))
    }
    
    erp_service = ERPIntegrationService()
    result = erp_service.update_config(config_data)
    
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'danger')
    
    return redirect(url_for('integration.erp_config'))

@integration_bp.route('/integrations/erp/test', methods=['POST'])
@admin_required
def erp_test_connection():
    """Testa a conexão com o ERP."""
    erp_service = ERPIntegrationService()
    result = erp_service.test_connection()
    
    return jsonify(result)

@integration_bp.route('/integrations/erp/sync', methods=['POST'])
@admin_required
def erp_sync():
    """Sincroniza dados com o ERP."""
    sync_type = request.form.get('sync_type', 'all')
    direction = request.form.get('direction', 'pull')
    
    erp_service = ERPIntegrationService()
    
    if sync_type == 'all':
        result = erp_service.sync_all()
    elif sync_type == 'equipment':
        result = erp_service.sync_equipment(direction)
    elif sync_type == 'inventory':
        result = erp_service.sync_inventory(direction)
    elif sync_type == 'service_orders':
        result = erp_service.sync_service_orders(direction)
    else:
        result = {'success': False, 'message': 'Tipo de sincronização inválido.'}
    
    return jsonify(result)

# Rotas para IoT
@integration_bp.route('/integrations/iot')
@admin_required
def iot_config():
    """Configuração da integração com IoT."""
    iot_service = IoTIntegrationService()
    iot_status = iot_service.get_iot_status()
    registered_devices = iot_service.get_registered_devices()
    
    # Buscar equipamentos para mapeamento
    db = get_db()
    equipments = db.fetch_all("""
        SELECT e.id, e.name, e.model, e.serial_number, c.name as customer_name
        FROM equipment e
        JOIN customers c ON e.customer_id = c.id
        WHERE e.active = TRUE
        ORDER BY c.name, e.name
    """)
    
    return render_template(
        'iot_config.html',
        iot_status=iot_status,
        registered_devices=registered_devices,
        equipments=equipments,
        active_page='integrations'
    )

@integration_bp.route('/integrations/iot/update', methods=['POST'])
@admin_required
def iot_update_config():
    """Atualiza a configuração da integração com IoT."""
    config_data = {
        'enabled': request.form.get('enabled') == 'on',
        'integration_type': request.form.get('integration_type'),
        'mqtt_broker': request.form.get('mqtt_broker'),
        'mqtt_port': int(request.form.get('mqtt_port', 1883)),
        'mqtt_username': request.form.get('mqtt_username'),
        'mqtt_password': request.form.get('mqtt_password'),
        'mqtt_topic_prefix': request.form.get('mqtt_topic_prefix'),
        'rest_api_url': request.form.get('rest_api_url'),
        'rest_api_key': request.form.get('rest_api_key')
    }
    
    iot_service = IoTIntegrationService()
    result = iot_service.update_config(config_data)
    
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'danger')
    
    return redirect(url_for('integration.iot_config'))

@integration_bp.route('/integrations/iot/test', methods=['POST'])
@admin_required
def iot_test_connection():
    """Testa a conexão com o sistema IoT."""
    iot_service = IoTIntegrationService()
    result = iot_service.test_connection()
    
    return jsonify(result)

@integration_bp.route('/integrations/iot/start', methods=['POST'])
@admin_required
def iot_start_integration():
    """Inicia a integração com IoT."""
    iot_service = IoTIntegrationService()
    result = iot_service.start_integration()
    
    return jsonify(result)

@integration_bp.route('/integrations/iot/stop', methods=['POST'])
@admin_required
def iot_stop_integration():
    """Para a integração com IoT."""
    iot_service = IoTIntegrationService()
    result = iot_service.stop_integration()
    
    return jsonify(result)

@integration_bp.route('/integrations/iot/fetch', methods=['POST'])
@admin_required
def iot_fetch_data():
    """Busca dados da API REST de IoT."""
    iot_service = IoTIntegrationService()
    result = iot_service.fetch_data_from_api()
    
    return jsonify(result)

@integration_bp.route('/integrations/iot/register', methods=['POST'])
@admin_required
def iot_register_device():
    """Registra um dispositivo IoT para um equipamento."""
    device_id = request.form.get('device_id')
    equipment_id = request.form.get('equipment_id')
    
    if not device_id or not equipment_id:
        return jsonify({'success': False, 'message': 'ID do dispositivo e ID do equipamento são obrigatórios.'})
    
    iot_service = IoTIntegrationService()
    result = iot_service.register_device(device_id, int(equipment_id))
    
    return jsonify(result)

@integration_bp.route('/integrations/iot/unregister', methods=['POST'])
@admin_required
def iot_unregister_device():
    """Remove o registro de um dispositivo IoT."""
    device_id = request.form.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'message': 'ID do dispositivo é obrigatório.'})
    
    iot_service = IoTIntegrationService()
    result = iot_service.unregister_device(device_id)
    
    return jsonify(result)

# Rotas para API de integração
@integration_bp.route('/api/iot/data', methods=['POST'])
def iot_api_receive_data():
    """
    Endpoint para receber dados de dispositivos IoT via API REST.
    Esta rota não requer autenticação para facilitar a integração com dispositivos IoT,
    mas utiliza um token de API para validação.
    """
    # Verificar token de API
    api_token = request.headers.get('X-API-Token')
    if not api_token:
        return jsonify({'success': False, 'message': 'Token de API não fornecido.'}), 401
    
    # Validar token (implementação simplificada)
    iot_service = IoTIntegrationService()
    config = iot_service.config
    valid_token = config.get('api_token')
    
    if not valid_token or api_token != valid_token:
        return jsonify({'success': False, 'message': 'Token de API inválido.'}), 401
    
    # Processar dados recebidos
    try:
        data = request.json
        
        if not data:
            return jsonify({'success': False, 'message': 'Nenhum dado recebido.'}), 400
        
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({'success': False, 'message': 'ID do dispositivo não fornecido.'}), 400
        
        # Verificar se o dispositivo está mapeado para um equipamento
        equipment_id = iot_service.device_mappings.get(device_id)
        
        if not equipment_id:
            return jsonify({'success': False, 'message': 'Dispositivo não registrado.'}), 404
        
        # Processar dados
        iot_service._process_equipment_data(equipment_id, data)
        
        return jsonify({'success': True, 'message': 'Dados recebidos e processados com sucesso.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao processar dados: {str(e)}'}), 500
