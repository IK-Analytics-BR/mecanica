from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required

# Criar um Blueprint para as rotas de grupo de produto
product_group_bp = Blueprint('product_group', __name__)


# Rota para listar todos os grupos de produtos
@product_group_bp.route('/produtos/grupos')
@login_required
def grupos():
    # Verificar se há parâmetros de busca
    search_term = request.args.get('search_term', '')
    
    # Buscar grupos ativos no banco de dados
    db = get_db()
    
    if search_term:
        # Buscar grupos que correspondem ao termo de busca
        query = "SELECT * FROM product_groups WHERE active = TRUE AND name LIKE %s"
        params = (f'%{search_term}%',)
        grupos = db.fetch_all(query, params)
    else:
        # Buscar todos os grupos ativos
        grupos = db.fetch_all("SELECT * FROM product_groups WHERE active = TRUE")
    
    return render_template('product_group_list.html', grupos=grupos, search_term=search_term)

# Rota para cadastrar um novo grupo de produto
@product_group_bp.route('/produtos/grupos/cadastrar', methods=['GET', 'POST'])
@login_required
def grupo_cadastrar():
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        
        # Verificar se já existe grupo com o mesmo nome
        db = get_db()
        grupo_existente = db.fetch_one("SELECT * FROM product_groups WHERE name = %s AND active = TRUE", (name,))
        
        if grupo_existente:
            flash(f'Já existe um grupo com o nome "{name}".', 'warning')
            return render_template('product_group_form.html')
        
        # Inserir grupo no banco de dados
        query = "INSERT INTO product_groups (name, description) VALUES (%s, %s)"
        params = (name, description)
        
        result = db.insert(query, params)
        
        if result:
            flash('Grupo cadastrado com sucesso!', 'success')
            return redirect(url_for('product_group.grupos'))
        else:
            flash('Erro ao cadastrar grupo.', 'danger')
    
    return render_template('product_group_form.html')

# Rota para editar um grupo de produto
@product_group_bp.route('/produtos/grupos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def grupo_editar(id):
    # Buscar o grupo pelo ID
    db = get_db()
    grupo = db.fetch_one("SELECT * FROM product_groups WHERE id = %s", (id,))
    
    if not grupo:
        flash('Grupo não encontrado.', 'danger')
        return redirect(url_for('product_group.grupos'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        
        # Verificar se já existe outro grupo com o mesmo nome
        grupo_existente = db.fetch_one("SELECT * FROM product_groups WHERE name = %s AND id != %s AND active = TRUE", (name, id))
        
        if grupo_existente:
            flash(f'Já existe outro grupo com o nome "{name}".', 'warning')
            return render_template('product_group_form.html', grupo=grupo)
        
        # Atualizar grupo no banco de dados
        query = "UPDATE product_groups SET name = %s, description = %s WHERE id = %s"
        params = (name, description, id)
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Grupo atualizado com sucesso!', 'success')
            return redirect(url_for('product_group.grupos'))
        else:
            flash('Erro ao atualizar grupo.', 'danger')
    
    return render_template('product_group_form.html', grupo=grupo)

# Rota para visualizar um grupo de produto
@product_group_bp.route('/produtos/grupos/visualizar/<int:id>')
@login_required
def grupo_visualizar(id):
    # Buscar o grupo pelo ID
    db = get_db()
    grupo = db.fetch_one("SELECT * FROM product_groups WHERE id = %s", (id,))
    
    if not grupo:
        flash('Grupo não encontrado.', 'danger')
        return redirect(url_for('product_group.grupos'))
    
    # Buscar subgrupos associados a este grupo
    subgrupos = db.fetch_all("SELECT * FROM product_subgroups WHERE group_id = %s AND active = TRUE", (id,))
    
    # Buscar produtos associados a este grupo
    produtos = db.fetch_all("SELECT * FROM products WHERE group_id = %s AND active = TRUE", (id,))
    
    return render_template('product_group_view.html', grupo=grupo, subgrupos=subgrupos, produtos=produtos)

# Rota para excluir um grupo de produto
@product_group_bp.route('/produtos/grupos/excluir/<int:id>')
@login_required
def grupo_excluir(id):
    # Buscar o grupo pelo ID
    db = get_db()
    grupo = db.fetch_one("SELECT * FROM product_groups WHERE id = %s", (id,))
    
    if not grupo:
        flash('Grupo não encontrado.', 'danger')
        return redirect(url_for('product_group.grupos'))
    
    # Verificar se existem subgrupos associados a este grupo
    subgrupos = db.fetch_all("SELECT * FROM product_subgroups WHERE group_id = %s AND active = TRUE", (id,))
    
    if subgrupos:
        flash('Não é possível excluir este grupo, pois existem subgrupos associados a ele.', 'warning')
        return redirect(url_for('product_group.grupos'))
    
    # Verificar se existem produtos associados a este grupo
    produtos = db.fetch_all("SELECT * FROM products WHERE group_id = %s AND active = TRUE", (id,))
    
    if produtos:
        flash('Não é possível excluir este grupo, pois existem produtos associados a ele.', 'warning')
        return redirect(url_for('product_group.grupos'))
    
    # Excluir grupo do banco de dados (exclusão lógica)
    query = "UPDATE product_groups SET active = FALSE WHERE id = %s"
    params = (id,)
    
    affected_rows = db.update(query, params)
    
    if affected_rows > 0:
        flash('Grupo excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir grupo.', 'danger')
    
    return redirect(url_for('product_group.grupos'))
