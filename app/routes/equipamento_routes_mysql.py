from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required
from datetime import datetime
from utils.permissoes_helper import tem_permissao
from utils.tenant import get_company_id, inject_company_id

# Criar um Blueprint para as rotas de equipamento
equipamento_bp = Blueprint('equipamento', __name__)


# Decorators para permissões granulares
def equipamento_visualizar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('manutencao.equipamentos', 'visualizar'):
            flash('Você não tem permissão para visualizar equipamentos.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function

def equipamento_criar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('manutencao.equipamentos', 'criar'):
            flash('Você não tem permissão para cadastrar equipamentos.', 'danger')
            return redirect(url_for('equipamento.equipamentos'))
        return f(*args, **kwargs)
    return decorated_function

def equipamento_editar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('manutencao.equipamentos', 'editar'):
            flash('Você não tem permissão para editar equipamentos.', 'danger')
            return redirect(url_for('equipamento.equipamentos'))
        return f(*args, **kwargs)
    return decorated_function

def equipamento_excluir_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('manutencao.equipamentos', 'excluir'):
            flash('Você não tem permissão para excluir equipamentos.', 'danger')
            return redirect(url_for('equipamento.equipamentos'))
        return f(*args, **kwargs)
    return decorated_function

# Rota para listar todos os equipamentos
@equipamento_bp.route('/equipamentos')
@equipamento_visualizar_required
def equipamentos():
    # Buscar equipamentos ativos no banco de dados
    db = get_db()
    company_id = get_company_id()
    equipamentos = db.fetch_all("""
        SELECT e.*, c.name as customer_name
        FROM equipment e
        LEFT JOIN customers c ON e.customer_id = c.id
        WHERE e.active = TRUE AND e.company_id = %s
    """, (company_id,))
    return render_template('equipamento_list.html', equipamentos=equipamentos)

# Rota para cadastrar um novo equipamento
@equipamento_bp.route('/equipamentos/cadastrar', methods=['GET', 'POST'])
@equipamento_criar_required
def equipamento_cadastrar():
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form['name']
        customer_id = request.form.get('customer_id') or None
        installation_date = request.form['installation_date']
        next_maintenance = request.form.get('next_maintenance') or None
        notes = request.form.get('notes', '')
        serial_number = request.form.get('serial_number', '')
        manufacturer = request.form.get('manufacturer', '')
        model = request.form.get('model', '')
        
        # Inserir equipamento no banco de dados
        db = get_db()
        query = """
            INSERT INTO equipment (name, customer_id, installation_date, next_maintenance, notes, serial_number, manufacturer, model)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (name, customer_id, installation_date, next_maintenance, notes, serial_number, manufacturer, model)
        
        equipamento_id = db.insert(query, params)
        
        if equipamento_id:
            flash('Equipamento cadastrado com sucesso!', 'success')
            return redirect(url_for('equipamento.equipamentos'))
        else:
            flash('Erro ao cadastrar equipamento.', 'danger')
    
    # Buscar clientes para o formulário
    db = get_db()
    clientes = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE")
    
    # Renderizar o formulário de cadastro de equipamento
    return render_template('equipamento_form.html', equipamento=None, clientes=clientes)

# Rota para editar um equipamento existente
@equipamento_bp.route('/equipamentos/editar/<id>', methods=['GET', 'POST'])
@equipamento_editar_required
def equipamento_editar(id):
    # Buscar o equipamento pelo ID
    db = get_db()
    equipamento = db.fetch_one("SELECT * FROM equipment WHERE id = %s", (id,))
    
    if not equipamento:
        flash('Equipamento não encontrado.', 'danger')
        return redirect(url_for('equipamento.equipamentos'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form['name']
        customer_id = request.form.get('customer_id') or None
        installation_date = request.form['installation_date']
        next_maintenance = request.form.get('next_maintenance') or None
        notes = request.form.get('notes', '')
        serial_number = request.form.get('serial_number', '')
        manufacturer = request.form.get('manufacturer', '')
        model = request.form.get('model', '')
        
        # Atualizar equipamento no banco de dados
        query = """
            UPDATE equipment
            SET name = %s, customer_id = %s, installation_date = %s, next_maintenance = %s,
                notes = %s, serial_number = %s, manufacturer = %s, model = %s
            WHERE id = %s
        """
        params = (name, customer_id, installation_date, next_maintenance, notes, serial_number, manufacturer, model, id)
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Equipamento atualizado com sucesso!', 'success')
            return redirect(url_for('equipamento.equipamentos'))
        else:
            flash('Erro ao atualizar equipamento.', 'danger')
    
    # Buscar clientes para o formulário
    clientes = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE")
    
    # Renderizar o formulário de edição de equipamento
    return render_template('equipamento_form.html', equipamento=equipamento, clientes=clientes)

# Rota para visualizar um equipamento
@equipamento_bp.route('/equipamentos/visualizar/<id>')
@login_required
def equipamento_visualizar(id):
    # Buscar o equipamento pelo ID
    db = get_db()
    equipamento = db.fetch_one("""
        SELECT e.*, c.name as customer_name 
        FROM equipment e
        LEFT JOIN customers c ON e.customer_id = c.id
        WHERE e.id = %s
    """, (id,))
    
    if not equipamento:
        flash('Equipamento não encontrado.', 'danger')
        return redirect(url_for('equipamento.equipamentos'))
    
    # Buscar cliente do equipamento
    cliente = None
    if equipamento['customer_id']:
        cliente = db.fetch_one("SELECT * FROM customers WHERE id = %s", (equipamento['customer_id'],))
    
    # Buscar insumos instalados neste equipamento
    insumos_instalados = db.fetch_all("""
        SELECT ins.*, s.name as supply_name 
        FROM installed_supplies ins
        JOIN supplies s ON ins.supply_id = s.id
        WHERE ins.equipment_id = %s AND ins.active = TRUE
    """, (id,))
    
    # Renderizar a visualização do equipamento
    return render_template('equipamento_view.html', equipamento=equipamento, cliente=cliente, insumos_instalados=insumos_instalados)

# Rota para excluir um equipamento
@equipamento_bp.route('/equipamentos/excluir/<id>')
@equipamento_excluir_required
def equipamento_excluir(id):
    # Buscar o equipamento pelo ID
    db = get_db()
    equipamento = db.fetch_one("SELECT * FROM equipment WHERE id = %s", (id,))
    
    if equipamento:
        # Verificar se o equipamento possui insumos instalados
        insumos = db.fetch_one("""
            SELECT COUNT(*) as count FROM installed_supplies 
            WHERE equipment_id = %s AND active = TRUE
        """, (id,))
        
        if insumos and insumos['count'] > 0:
            # Marcar insumos instalados como inativos
            db.update("""
                UPDATE installed_supplies SET active = FALSE 
                WHERE equipment_id = %s
            """, (id,))
        
        # Marcar o equipamento como inativo (exclusão lógica)
        affected_rows = db.update("""
            UPDATE equipment SET active = FALSE WHERE id = %s
        """, (id,))
        
        if affected_rows > 0:
            flash('Equipamento excluído com sucesso!', 'success')
        else:
            flash('Erro ao excluir equipamento.', 'danger')
    else:
        flash('Equipamento não encontrado.', 'danger')
    
    # Redirecionar para a lista de equipamentos
    return redirect(url_for('equipamento.equipamentos'))
