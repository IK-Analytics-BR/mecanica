from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required

# Criar um Blueprint para as rotas de categoria de produto
product_category_bp = Blueprint('product_category', __name__)


# Rota para listar todas as categorias de produtos
@product_category_bp.route('/produtos/categorias')
@login_required
def categorias():
    # Verificar se há parâmetros de busca
    search_term = request.args.get('search_term', '')
    
    # Buscar categorias ativas no banco de dados
    db = get_db()
    
    if search_term:
        # Buscar categorias que correspondem ao termo de busca
        query = "SELECT * FROM product_categories WHERE active = TRUE AND name LIKE %s"
        params = (f'%{search_term}%',)
        categorias = db.fetch_all(query, params)
    else:
        # Buscar todas as categorias ativas
        categorias = db.fetch_all("SELECT * FROM product_categories WHERE active = TRUE")
    
    return render_template('product_category_list.html', categorias=categorias, search_term=search_term)

# Rota para cadastrar uma nova categoria de produto
@product_category_bp.route('/produtos/categorias/cadastrar', methods=['GET', 'POST'])
@login_required
def categoria_cadastrar():
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        categoria_fiscal = request.form.get('categoria_fiscal', 'produto_producao')
        
        # Verificar se já existe categoria com o mesmo nome
        db = get_db()
        categoria_existente = db.fetch_one("SELECT * FROM product_categories WHERE name = %s AND active = TRUE", (name,))
        
        if categoria_existente:
            flash(f'Já existe uma categoria com o nome "{name}".', 'warning')
            return render_template('product_category_form.html')
        
        # Inserir categoria no banco de dados
        query = "INSERT INTO product_categories (name, description, categoria_fiscal) VALUES (%s, %s, %s)"
        params = (name, description, categoria_fiscal)
        
        result = db.insert(query, params)
        
        if result:
            flash('Categoria cadastrada com sucesso!', 'success')
            return redirect(url_for('product_category.categorias'))
        else:
            flash('Erro ao cadastrar categoria.', 'danger')
    
    return render_template('product_category_form.html')

# Rota para editar uma categoria de produto
@product_category_bp.route('/produtos/categorias/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def categoria_editar(id):
    # Buscar a categoria pelo ID
    db = get_db()
    categoria = db.fetch_one("SELECT * FROM product_categories WHERE id = %s", (id,))
    
    if not categoria:
        flash('Categoria não encontrada.', 'danger')
        return redirect(url_for('product_category.categorias'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        categoria_fiscal = request.form.get('categoria_fiscal', 'produto_producao')
        
        # Verificar se já existe outra categoria com o mesmo nome
        categoria_existente = db.fetch_one("SELECT * FROM product_categories WHERE name = %s AND id != %s AND active = TRUE", (name, id))
        
        if categoria_existente:
            flash(f'Já existe outra categoria com o nome "{name}".', 'warning')
            return render_template('product_category_form.html', categoria=categoria)
        
        # Atualizar categoria no banco de dados
        query = "UPDATE product_categories SET name = %s, description = %s, categoria_fiscal = %s WHERE id = %s"
        params = (name, description, categoria_fiscal, id)
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Categoria atualizada com sucesso!', 'success')
            return redirect(url_for('product_category.categorias'))
        else:
            flash('Erro ao atualizar categoria.', 'danger')
    
    return render_template('product_category_form.html', categoria=categoria)

# Rota para visualizar uma categoria de produto
@product_category_bp.route('/produtos/categorias/visualizar/<int:id>')
@login_required
def categoria_visualizar(id):
    # Buscar a categoria pelo ID
    db = get_db()
    categoria = db.fetch_one("SELECT * FROM product_categories WHERE id = %s", (id,))
    
    if not categoria:
        flash('Categoria não encontrada.', 'danger')
        return redirect(url_for('product_category.categorias'))
    
    # Buscar produtos associados a esta categoria
    produtos = db.fetch_all("SELECT * FROM products WHERE category_id = %s AND active = TRUE", (id,))
    
    return render_template('product_category_view.html', categoria=categoria, produtos=produtos)

# Rota para excluir uma categoria de produto
@product_category_bp.route('/produtos/categorias/excluir/<int:id>')
@login_required
def categoria_excluir(id):
    # Buscar a categoria pelo ID
    db = get_db()
    categoria = db.fetch_one("SELECT * FROM product_categories WHERE id = %s", (id,))
    
    if not categoria:
        flash('Categoria não encontrada.', 'danger')
        return redirect(url_for('product_category.categorias'))
    
    # Verificar se existem produtos associados a esta categoria
    produtos = db.fetch_all("SELECT * FROM products WHERE category_id = %s AND active = TRUE", (id,))
    
    if produtos:
        flash('Não é possível excluir esta categoria, pois existem produtos associados a ela.', 'warning')
        return redirect(url_for('product_category.categorias'))
    
    # Excluir categoria do banco de dados (exclusão lógica)
    query = "UPDATE product_categories SET active = FALSE WHERE id = %s"
    params = (id,)
    
    affected_rows = db.update(query, params)
    
    if affected_rows > 0:
        flash('Categoria excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir categoria.', 'danger')
    
    return redirect(url_for('product_category.categorias'))
