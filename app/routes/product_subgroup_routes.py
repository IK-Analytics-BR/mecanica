from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required

# Criar um Blueprint para as rotas de subgrupo de produto
product_subgroup_bp = Blueprint('product_subgroup', __name__)


# Rota para listar todos os subgrupos de produtos
@product_subgroup_bp.route('/produtos/subgrupos')
@login_required
def subgrupos():
    # Verificar se há parâmetros de busca
    search_term = request.args.get('search_term', '')
    group_id = request.args.get('group_id', '')
    
    # Buscar subgrupos ativos no banco de dados
    db = get_db()
    
    if search_term and group_id:
        # Buscar subgrupos que correspondem ao termo de busca e ao grupo
        query = """
            SELECT s.*, g.name as group_name 
            FROM product_subgroups s
            JOIN product_groups g ON s.group_id = g.id
            WHERE s.active = TRUE AND s.name LIKE %s AND s.group_id = %s
        """
        params = (f'%{search_term}%', group_id)
        subgrupos = db.fetch_all(query, params)
    elif search_term:
        # Buscar subgrupos que correspondem ao termo de busca
        query = """
            SELECT s.*, g.name as group_name 
            FROM product_subgroups s
            JOIN product_groups g ON s.group_id = g.id
            WHERE s.active = TRUE AND s.name LIKE %s
        """
        params = (f'%{search_term}%',)
        subgrupos = db.fetch_all(query, params)
    elif group_id:
        # Buscar subgrupos que correspondem ao grupo
        query = """
            SELECT s.*, g.name as group_name 
            FROM product_subgroups s
            JOIN product_groups g ON s.group_id = g.id
            WHERE s.active = TRUE AND s.group_id = %s
        """
        params = (group_id,)
        subgrupos = db.fetch_all(query, params)
    else:
        # Buscar todos os subgrupos ativos
        query = """
            SELECT s.*, g.name as group_name 
            FROM product_subgroups s
            JOIN product_groups g ON s.group_id = g.id
            WHERE s.active = TRUE
        """
        subgrupos = db.fetch_all(query)
    
    # Buscar todos os grupos para o filtro
    grupos = db.fetch_all("SELECT * FROM product_groups WHERE active = TRUE")
    
    return render_template('product_subgroup_list.html', subgrupos=subgrupos, grupos=grupos, search_term=search_term, group_id=group_id)

# Rota para cadastrar um novo subgrupo de produto
@product_subgroup_bp.route('/produtos/subgrupos/cadastrar', methods=['GET', 'POST'])
@login_required
def subgrupo_cadastrar():
    # Buscar todos os grupos para o formulário
    db = get_db()
    grupos = db.fetch_all("SELECT * FROM product_groups WHERE active = TRUE")
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        group_id = request.form.get('group_id', '')
        
        # Verificar se o grupo foi selecionado
        if not group_id:
            flash('Por favor, selecione um grupo.', 'warning')
            return render_template('product_subgroup_form.html', grupos=grupos)
        
        # Verificar se já existe subgrupo com o mesmo nome no mesmo grupo
        subgrupo_existente = db.fetch_one(
            "SELECT * FROM product_subgroups WHERE name = %s AND group_id = %s AND active = TRUE", 
            (name, group_id)
        )
        
        if subgrupo_existente:
            flash(f'Já existe um subgrupo com o nome "{name}" neste grupo.', 'warning')
            return render_template('product_subgroup_form.html', grupos=grupos)
        
        # Inserir subgrupo no banco de dados
        query = "INSERT INTO product_subgroups (name, description, group_id) VALUES (%s, %s, %s)"
        params = (name, description, group_id)
        
        result = db.insert(query, params)
        
        if result:
            flash('Subgrupo cadastrado com sucesso!', 'success')
            return redirect(url_for('product_subgroup.subgrupos'))
        else:
            flash('Erro ao cadastrar subgrupo.', 'danger')
    
    return render_template('product_subgroup_form.html', grupos=grupos)

# Rota para editar um subgrupo de produto
@product_subgroup_bp.route('/produtos/subgrupos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def subgrupo_editar(id):
    # Buscar o subgrupo pelo ID
    db = get_db()
    subgrupo = db.fetch_one("SELECT * FROM product_subgroups WHERE id = %s", (id,))
    
    if not subgrupo:
        flash('Subgrupo não encontrado.', 'danger')
        return redirect(url_for('product_subgroup.subgrupos'))
    
    # Buscar todos os grupos para o formulário
    grupos = db.fetch_all("SELECT * FROM product_groups WHERE active = TRUE")
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        group_id = request.form.get('group_id', '')
        
        # Verificar se o grupo foi selecionado
        if not group_id:
            flash('Por favor, selecione um grupo.', 'warning')
            return render_template('product_subgroup_form.html', subgrupo=subgrupo, grupos=grupos)
        
        # Verificar se já existe outro subgrupo com o mesmo nome no mesmo grupo
        subgrupo_existente = db.fetch_one(
            "SELECT * FROM product_subgroups WHERE name = %s AND group_id = %s AND id != %s AND active = TRUE", 
            (name, group_id, id)
        )
        
        if subgrupo_existente:
            flash(f'Já existe outro subgrupo com o nome "{name}" neste grupo.', 'warning')
            return render_template('product_subgroup_form.html', subgrupo=subgrupo, grupos=grupos)
        
        # Atualizar subgrupo no banco de dados
        query = "UPDATE product_subgroups SET name = %s, description = %s, group_id = %s WHERE id = %s"
        params = (name, description, group_id, id)
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Subgrupo atualizado com sucesso!', 'success')
            return redirect(url_for('product_subgroup.subgrupos'))
        else:
            flash('Erro ao atualizar subgrupo.', 'danger')
    
    return render_template('product_subgroup_form.html', subgrupo=subgrupo, grupos=grupos)

# Rota para visualizar um subgrupo de produto
@product_subgroup_bp.route('/produtos/subgrupos/visualizar/<int:id>')
@login_required
def subgrupo_visualizar(id):
    # Buscar o subgrupo pelo ID
    db = get_db()
    query = """
        SELECT s.*, g.name as group_name 
        FROM product_subgroups s
        JOIN product_groups g ON s.group_id = g.id
        WHERE s.id = %s
    """
    subgrupo = db.fetch_one(query, (id,))
    
    if not subgrupo:
        flash('Subgrupo não encontrado.', 'danger')
        return redirect(url_for('product_subgroup.subgrupos'))
    
    # Buscar produtos associados a este subgrupo
    produtos = db.fetch_all("SELECT * FROM products WHERE subgroup_id = %s AND active = TRUE", (id,))
    
    return render_template('product_subgroup_view.html', subgrupo=subgrupo, produtos=produtos)

# Rota para excluir um subgrupo de produto
@product_subgroup_bp.route('/produtos/subgrupos/excluir/<int:id>')
@login_required
def subgrupo_excluir(id):
    # Buscar o subgrupo pelo ID
    db = get_db()
    subgrupo = db.fetch_one("SELECT * FROM product_subgroups WHERE id = %s", (id,))
    
    if not subgrupo:
        flash('Subgrupo não encontrado.', 'danger')
        return redirect(url_for('product_subgroup.subgrupos'))
    
    # Verificar se existem produtos associados a este subgrupo
    produtos = db.fetch_all("SELECT * FROM products WHERE subgroup_id = %s AND active = TRUE", (id,))
    
    if produtos:
        flash('Não é possível excluir este subgrupo, pois existem produtos associados a ele.', 'warning')
        return redirect(url_for('product_subgroup.subgrupos'))
    
    # Excluir subgrupo do banco de dados (exclusão lógica)
    query = "UPDATE product_subgroups SET active = FALSE WHERE id = %s"
    params = (id,)
    
    affected_rows = db.update(query, params)
    
    if affected_rows > 0:
        flash('Subgrupo excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir subgrupo.', 'danger')
    
    return redirect(url_for('product_subgroup.subgrupos'))
