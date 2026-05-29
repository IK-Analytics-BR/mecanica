"""
Rotas para gerenciamento de técnicos.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import datetime

from database import get_db
from utils.auth import login_required

# Criar o blueprint
technician_bp = Blueprint('technician', __name__)


@technician_bp.route('/tecnicos')
@login_required
def technicians_list():
    """Lista todos os técnicos."""
    db = get_db()
    
    # Buscar todos os técnicos ativos
    technicians = db.fetch_all("""
        SELECT * FROM technicians
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'technician_list.html',
        technicians=technicians,
        active_page='technicians'
    )

@technician_bp.route('/tecnicos/cadastrar', methods=['GET', 'POST'])
@login_required
def technician_create():
    """Cadastra um novo técnico."""
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        registration_number = request.form.get('registration_number')
        specialty = request.form.get('specialty')
        phone = request.form.get('phone')
        email = request.form.get('email')
        document_number = request.form.get('document_number')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip_code')
        notes = request.form.get('notes')
        status = request.form.get('status')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome do técnico é obrigatório.')
        
        if not registration_number:
            errors.append('Número de registro é obrigatório.')
        
        # Verificar se o número de registro já existe
        db = get_db()
        existing_technician = db.fetch_one("""
            SELECT id FROM technicians
            WHERE registration_number = %s AND active = TRUE
        """, (registration_number,))
        
        if existing_technician:
            errors.append('Número de registro já cadastrado.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('technician.technician_create'))
        
        # Inserir técnico no banco de dados
        technician_id = db.insert("""
            INSERT INTO technicians (name, registration_number, specialty, phone, email, document_number, address, city, state, zip_code, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, registration_number, specialty, phone, email, document_number, address, city, state, zip_code, notes, status))
        
        if technician_id:
            flash('Técnico cadastrado com sucesso!', 'success')
            return redirect(url_for('technician.technicians_list'))
        else:
            flash('Erro ao cadastrar técnico.', 'danger')
    
    return render_template(
        'technician_form.html',
        technician=None,
        active_page='technicians'
    )

@technician_bp.route('/tecnicos/editar/<int:technician_id>', methods=['GET', 'POST'])
@login_required
def technician_edit(technician_id):
    """Edita um técnico existente."""
    db = get_db()
    
    # Buscar o técnico
    technician = db.fetch_one("""
        SELECT * FROM technicians
        WHERE id = %s AND active = TRUE
    """, (technician_id,))
    
    if not technician:
        flash('Técnico não encontrado.', 'danger')
        return redirect(url_for('technician.technicians_list'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        registration_number = request.form.get('registration_number')
        specialty = request.form.get('specialty')
        phone = request.form.get('phone')
        email = request.form.get('email')
        document_number = request.form.get('document_number')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip_code')
        notes = request.form.get('notes')
        status = request.form.get('status')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome do técnico é obrigatório.')
        
        if not registration_number:
            errors.append('Número de registro é obrigatório.')
        
        # Verificar se o número de registro já existe (exceto para o próprio técnico)
        existing_technician = db.fetch_one("""
            SELECT id FROM technicians
            WHERE registration_number = %s AND id != %s AND active = TRUE
        """, (registration_number, technician_id))
        
        if existing_technician:
            errors.append('Número de registro já cadastrado para outro técnico.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('technician.technician_edit', technician_id=technician_id))
        
        # Atualizar técnico no banco de dados
        affected_rows = db.update("""
            UPDATE technicians
            SET name = %s, registration_number = %s, specialty = %s, phone = %s, email = %s, 
                document_number = %s, address = %s, city = %s, state = %s, zip_code = %s, 
                notes = %s, status = %s
            WHERE id = %s
        """, (name, registration_number, specialty, phone, email, document_number, address, city, state, zip_code, notes, status, technician_id))
        
        if affected_rows > 0:
            flash('Técnico atualizado com sucesso!', 'success')
            return redirect(url_for('technician.technicians_list'))
        else:
            flash('Erro ao atualizar técnico.', 'danger')
    
    return render_template(
        'technician_form.html',
        technician=technician,
        active_page='technicians'
    )

@technician_bp.route('/tecnicos/visualizar/<int:technician_id>')
@login_required
def technician_view(technician_id):
    """Visualiza detalhes de um técnico."""
    db = get_db()
    
    # Buscar o técnico
    technician = db.fetch_one("""
        SELECT * FROM technicians
        WHERE id = %s AND active = TRUE
    """, (technician_id,))
    
    if not technician:
        flash('Técnico não encontrado.', 'danger')
        return redirect(url_for('technician.technicians_list'))
    
    # Buscar ordens de serviço associadas ao técnico (se existirem)
    service_orders = []
    try:
        service_orders = db.fetch_all("""
            SELECT * FROM service_orders
            WHERE technician_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (technician_id,))
    except:
        # A tabela de ordens de serviço pode não existir ainda
        pass
    
    return render_template(
        'technician_view.html',
        technician=technician,
        service_orders=service_orders,
        active_page='technicians'
    )

@technician_bp.route('/tecnicos/excluir/<int:technician_id>', methods=['POST'])
@login_required
def technician_delete(technician_id):
    """Exclui um técnico (exclusão lógica)."""
    db = get_db()
    
    # Verificar se o técnico existe
    technician = db.fetch_one("""
        SELECT * FROM technicians
        WHERE id = %s AND active = TRUE
    """, (technician_id,))
    
    if not technician:
        flash('Técnico não encontrado.', 'danger')
        return redirect(url_for('technician.technicians_list'))
    
    # Verificar se o técnico está associado a ordens de serviço
    try:
        service_orders = db.fetch_one("""
            SELECT COUNT(*) as count FROM service_orders
            WHERE technician_id = %s
        """, (technician_id,))
        
        if service_orders and service_orders['count'] > 0:
            flash('Não é possível excluir um técnico associado a ordens de serviço.', 'danger')
            return redirect(url_for('technician.technician_view', technician_id=technician_id))
    except:
        # A tabela de ordens de serviço pode não existir ainda
        pass
    
    # Excluir técnico (exclusão lógica)
    affected_rows = db.update("""
        UPDATE technicians
        SET active = FALSE
        WHERE id = %s
    """, (technician_id,))
    
    if affected_rows > 0:
        flash('Técnico excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir técnico.', 'danger')
    
    return redirect(url_for('technician.technicians_list'))

@technician_bp.route('/api/tecnicos')
@login_required
def api_technicians():
    """API para listar técnicos (para uso em selects dinâmicos)."""
    db = get_db()
    
    # Buscar todos os técnicos ativos
    technicians = db.fetch_all("""
        SELECT id, name, specialty, registration_number
        FROM technicians
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    return {'technicians': technicians}
