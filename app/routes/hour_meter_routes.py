"""
Rotas para gerenciamento de horímetro de equipamentos.

Antes da solicitação: caso já tenha na versão atual, avance para a próxima.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from datetime import datetime

from database import get_db
from utils.auth import login_required
from services.wear_service import WearService

# Criar o blueprint
hour_meter_bp = Blueprint('hour_meter', __name__)


@hour_meter_bp.route('/hour_meter')
@login_required
def hour_meter_list():
    """Lista todas as leituras de horímetro."""
    db = get_db()
    
    # Buscar as leituras de horímetro
    readings = db.fetch_all("""
        SELECT r.*, e.name as equipment_name, u.name as user_name
        FROM hour_meter_readings r
        JOIN equipment e ON r.equipment_id = e.id
        LEFT JOIN users u ON r.user_id = u.id
        ORDER BY r.reading_date DESC, r.id DESC
    """)
    
    # Buscar equipamentos ativos para o formulário de nova leitura
    equipments = db.fetch_all("""
        SELECT id, name FROM equipment
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'hour_meter_list.html',
        readings=readings,
        equipments=equipments,
        active_page='hour_meter'
    )

@hour_meter_bp.route('/hour_meter/add', methods=['GET', 'POST'])
@login_required
def hour_meter_add():
    """Adiciona uma nova leitura de horímetro."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        equipment_id = request.form.get('equipment_id')
        hours = request.form.get('hours')
        reading_date = request.form.get('reading_date') or datetime.now().strftime('%Y-%m-%d')
        reading_type = 'manual'
        user_id = session.get('user_id')
        
        # Validar dados
        if not equipment_id or not hours:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return redirect(url_for('hour_meter.hour_meter_add'))
        
        try:
            hours = int(hours)
            if hours < 0:
                raise ValueError("Horas devem ser um número positivo")
        except ValueError:
            flash('O valor de horas deve ser um número inteiro positivo.', 'danger')
            return redirect(url_for('hour_meter.hour_meter_add'))
        
        # Registrar a leitura e atualizar o desgaste
        success = WearService.update_hour_meter(
            int(equipment_id),
            hours,
            reading_date,
            user_id,
            reading_type
        )
        
        if success:
            flash('Leitura de horímetro registrada com sucesso!', 'success')
            return redirect(url_for('hour_meter.hour_meter_list'))
        else:
            flash('Erro ao registrar leitura de horímetro.', 'danger')
    
    # Buscar equipamentos ativos para o formulário
    equipments = db.fetch_all("""
        SELECT id, name FROM equipment
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'hour_meter_form.html',
        equipments=equipments,
        reading=None,
        active_page='hour_meter'
    )

@hour_meter_bp.route('/hour_meter/equipment/<int:equipment_id>')
@login_required
def hour_meter_by_equipment(equipment_id):
    """Lista as leituras de horímetro de um equipamento específico."""
    db = get_db()
    
    # Buscar o equipamento
    equipment = db.fetch_one("""
        SELECT * FROM equipment
        WHERE id = %s
    """, (equipment_id,))
    
    if not equipment:
        flash('Equipamento não encontrado.', 'danger')
        return redirect(url_for('hour_meter.hour_meter_list'))
    
    # Buscar as leituras de horímetro do equipamento
    readings = db.fetch_all("""
        SELECT r.*, u.name as user_name
        FROM hour_meter_readings r
        LEFT JOIN users u ON r.user_id = u.id
        WHERE r.equipment_id = %s
        ORDER BY r.reading_date DESC, r.id DESC
    """, (equipment_id,))
    
    return render_template(
        'hour_meter_equipment.html',
        equipment=equipment,
        readings=readings,
        active_page='hour_meter'
    )

@hour_meter_bp.route('/hour_meter/delete/<int:reading_id>', methods=['POST'])
@login_required
def hour_meter_delete(reading_id):
    """Exclui uma leitura de horímetro."""
    # Verificar se o usuário é administrador
    if session.get('role') != 'admin':
        flash('Você não tem permissão para excluir leituras de horímetro.', 'danger')
        return redirect(url_for('hour_meter.hour_meter_list'))
    
    db = get_db()
    
    # Buscar a leitura
    reading = db.fetch_one("""
        SELECT * FROM hour_meter_readings
        WHERE id = %s
    """, (reading_id,))
    
    if not reading:
        flash('Leitura não encontrada.', 'danger')
        return redirect(url_for('hour_meter.hour_meter_list'))
    
    # Excluir a leitura
    affected_rows = db.delete("""
        DELETE FROM hour_meter_readings
        WHERE id = %s
    """, (reading_id,))
    
    if affected_rows > 0:
        flash('Leitura de horímetro excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir leitura de horímetro.', 'danger')
    
    return redirect(url_for('hour_meter.hour_meter_list'))
