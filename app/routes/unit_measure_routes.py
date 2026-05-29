from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from database import get_db
from utils.auth import login_required


unit_measure_bp = Blueprint('unit_measure', __name__)

# Rota para listar unidades de medida
@unit_measure_bp.route('/unidades')
@login_required
def unidades():
    # Buscar unidades de medida ativas no banco de dados
    db = get_db()
    unidades = db.fetch_all("SELECT * FROM unit_measures WHERE active = TRUE ORDER BY code")
    return render_template('unit_measure_list.html', unidades=unidades)

# Rota para cadastrar uma nova unidade de medida
@unit_measure_bp.route('/unidades/cadastrar', methods=['GET', 'POST'])
@login_required
def unidade_cadastrar():
    if request.method == 'POST':
        # Obter dados do formulário
        code = request.form.get('code', '').strip().upper()
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        # Validar dados
        if not code or not name:
            flash('Código e nome são obrigatórios.', 'danger')
            return render_template('unit_measure_form.html')
        
        # Verificar se o código já existe
        db = get_db()
        existing = db.fetch_one("SELECT id FROM unit_measures WHERE code = %s", (code,))
        if existing:
            flash(f'O código {code} já está em uso.', 'danger')
            return render_template('unit_measure_form.html', unidade={'code': code, 'name': name, 'description': description})
        
        # Inserir unidade de medida no banco de dados
        query = """
            INSERT INTO unit_measures (code, name, description)
            VALUES (%s, %s, %s)
        """
        unidade_id = db.insert(query, (code, name, description))
        
        if unidade_id:
            flash('Unidade de medida cadastrada com sucesso!', 'success')
            return redirect(url_for('unit_measure.unidades'))
        else:
            flash('Erro ao cadastrar unidade de medida.', 'danger')
    
    # Renderizar o formulário de cadastro
    return render_template('unit_measure_form.html', unidade=None)

# Rota para editar uma unidade de medida existente
@unit_measure_bp.route('/unidades/editar/<id>', methods=['GET', 'POST'])
@login_required
def unidade_editar(id):
    # Buscar a unidade de medida pelo ID
    db = get_db()
    unidade = db.fetch_one("SELECT * FROM unit_measures WHERE id = %s", (id,))
    
    if not unidade:
        flash('Unidade de medida não encontrada.', 'danger')
        return redirect(url_for('unit_measure.unidades'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        code = request.form.get('code', '').strip().upper()
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        # Validar dados
        if not code or not name:
            flash('Código e nome são obrigatórios.', 'danger')
            return render_template('unit_measure_form.html', unidade=unidade)
        
        # Verificar se o código já existe (exceto para a própria unidade)
        existing = db.fetch_one("SELECT id FROM unit_measures WHERE code = %s AND id != %s", (code, id))
        if existing:
            flash(f'O código {code} já está em uso.', 'danger')
            return render_template('unit_measure_form.html', unidade={'id': id, 'code': code, 'name': name, 'description': description})
        
        # Atualizar unidade de medida no banco de dados
        query = """
            UPDATE unit_measures
            SET code = %s, name = %s, description = %s
            WHERE id = %s
        """
        affected_rows = db.update(query, (code, name, description, id))
        
        if affected_rows > 0:
            flash('Unidade de medida atualizada com sucesso!', 'success')
            return redirect(url_for('unit_measure.unidades'))
        else:
            flash('Erro ao atualizar unidade de medida.', 'danger')
    
    # Renderizar o formulário de edição
    return render_template('unit_measure_form.html', unidade=unidade)

# Rota para excluir uma unidade de medida
@unit_measure_bp.route('/unidades/excluir/<id>')
@login_required
def unidade_excluir(id):
    # Verificar se a unidade está sendo usada em produtos
    db = get_db()
    produtos = db.fetch_all("SELECT id FROM products WHERE unit_measure = (SELECT code FROM unit_measures WHERE id = %s)", (id,))
    
    if produtos:
        flash('Esta unidade de medida não pode ser excluída pois está sendo usada em produtos.', 'danger')
        return redirect(url_for('unit_measure.unidades'))
    
    # Excluir a unidade de medida (soft delete)
    query = "UPDATE unit_measures SET active = FALSE WHERE id = %s"
    affected_rows = db.update(query, (id,))
    
    if affected_rows > 0:
        flash('Unidade de medida excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir unidade de medida.', 'danger')
    
    return redirect(url_for('unit_measure.unidades'))
