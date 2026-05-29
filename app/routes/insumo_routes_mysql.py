from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required

# Criar um Blueprint para as rotas de insumo
insumo_bp = Blueprint('insumo', __name__)


# Rota para listar todos os insumos
@insumo_bp.route('/insumos')
@login_required
def insumos():
    # Buscar insumos ativos no banco de dados
    db = get_db()
    insumos = db.fetch_all("""
        SELECT s.*, sup.name as supplier_name 
        FROM supplies s
        LEFT JOIN suppliers sup ON s.supplier_id = sup.id
        WHERE s.active = TRUE
    """)
    return render_template('insumo_list.html', insumos=insumos)

# Rota para cadastrar um novo insumo
@insumo_bp.route('/insumos/cadastrar', methods=['GET', 'POST'])
@login_required
def insumo_cadastrar():
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form['name']
        description = request.form['description']
        stock = request.form['stock']
        min_stock = request.form['min_stock']
        price = request.form['price']
        supplier_id = request.form['supplier_id'] if request.form['supplier_id'] else None
        
        # Inserir insumo no banco de dados
        db = get_db()
        query = """
            INSERT INTO supplies (name, description, stock, min_stock, price, supplier_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (name, description, stock, min_stock, price, supplier_id)
        
        insumo_id = db.insert(query, params)
        
        if insumo_id:
            flash('Insumo cadastrado com sucesso!', 'success')
            return redirect(url_for('insumo.insumos'))
        else:
            flash('Erro ao cadastrar insumo.', 'danger')
    
    # Buscar fornecedores para o formulário
    db = get_db()
    fornecedores = db.fetch_all("SELECT id, name FROM suppliers WHERE active = TRUE")
    
    # Renderizar o formulário de cadastro de insumo
    return render_template('insumo_form.html', insumo=None, fornecedores=fornecedores)

# Rota para editar um insumo existente
@insumo_bp.route('/insumos/editar/<id>', methods=['GET', 'POST'])
@login_required
def insumo_editar(id):
    # Buscar o insumo pelo ID
    db = get_db()
    insumo = db.fetch_one("SELECT * FROM supplies WHERE id = %s", (id,))
    
    if not insumo:
        flash('Insumo não encontrado.', 'danger')
        return redirect(url_for('insumo.insumos'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form['name']
        description = request.form['description']
        stock = request.form['stock']
        min_stock = request.form['min_stock']
        price = request.form['price']
        supplier_id = request.form['supplier_id'] if request.form['supplier_id'] else None
        
        # Atualizar insumo no banco de dados
        query = """
            UPDATE supplies
            SET name = %s, description = %s, stock = %s, min_stock = %s, price = %s, supplier_id = %s
            WHERE id = %s
        """
        params = (name, description, stock, min_stock, price, supplier_id, id)
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Insumo atualizado com sucesso!', 'success')
            return redirect(url_for('insumo.insumos'))
        else:
            flash('Erro ao atualizar insumo.', 'danger')
    
    # Buscar fornecedores para o formulário
    fornecedores = db.fetch_all("SELECT id, name FROM suppliers WHERE active = TRUE")
    
    # Renderizar o formulário de edição de insumo
    return render_template('insumo_form.html', insumo=insumo, fornecedores=fornecedores)

# Rota para visualizar um insumo
@insumo_bp.route('/insumos/visualizar/<id>')
@login_required
def insumo_visualizar(id):
    # Buscar o insumo pelo ID
    db = get_db()
    insumo = db.fetch_one("""
        SELECT s.*, sup.name as supplier_name 
        FROM supplies s
        LEFT JOIN suppliers sup ON s.supplier_id = sup.id
        WHERE s.id = %s
    """, (id,))
    
    if not insumo:
        flash('Insumo não encontrado.', 'danger')
        return redirect(url_for('insumo.insumos'))
    
    # Buscar fornecedor do insumo
    fornecedor = None
    if insumo['supplier_id']:
        fornecedor = db.fetch_one("SELECT * FROM suppliers WHERE id = %s", (insumo['supplier_id'],))
    
    # Buscar equipamentos que usam este insumo
    equipamentos = db.fetch_all("""
        SELECT e.*, c.name as customer_name 
        FROM equipment e
        JOIN installed_supplies ins ON e.id = ins.equipment_id
        JOIN customers c ON e.customer_id = c.id
        WHERE ins.supply_id = %s AND e.active = TRUE
        GROUP BY e.id
    """, (id,))
    
    # Renderizar a visualização do insumo
    return render_template('insumo_view.html', insumo=insumo, fornecedor=fornecedor, equipamentos=equipamentos)

# Rota para excluir um insumo
@insumo_bp.route('/insumos/excluir/<id>')
@login_required
def insumo_excluir(id):
    # Buscar o insumo pelo ID
    db = get_db()
    insumo = db.fetch_one("SELECT * FROM supplies WHERE id = %s", (id,))
    
    if insumo:
        # Verificar se o insumo está instalado em algum equipamento
        instalados = db.fetch_one("""
            SELECT COUNT(*) as count FROM installed_supplies 
            WHERE supply_id = %s
        """, (id,))
        
        if instalados and instalados['count'] > 0:
            flash('Não é possível excluir o insumo pois ele está instalado em equipamentos.', 'danger')
            return redirect(url_for('insumo.insumos'))
        
        # Marcar o insumo como inativo (exclusão lógica)
        affected_rows = db.update("""
            UPDATE supplies SET active = FALSE WHERE id = %s
        """, (id,))
        
        if affected_rows > 0:
            flash('Insumo excluído com sucesso!', 'success')
        else:
            flash('Erro ao excluir insumo.', 'danger')
    else:
        flash('Insumo não encontrado.', 'danger')
    
    # Redirecionar para a lista de insumos
    return redirect(url_for('insumo.insumos'))
