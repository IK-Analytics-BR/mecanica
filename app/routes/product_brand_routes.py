from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required

# Criar um Blueprint para as rotas de marca de produto
product_brand_bp = Blueprint('product_brand', __name__)


# Rota para listar todas as marcas de produtos
@product_brand_bp.route('/produtos/marcas')
@login_required
def marcas():
    # Verificar se há parâmetros de busca
    search_term = request.args.get('search_term', '')
    
    # Buscar marcas ativas no banco de dados
    db = get_db()
    
    if search_term:
        # Buscar marcas que correspondem ao termo de busca
        query = "SELECT * FROM product_brands WHERE active = TRUE AND name LIKE %s"
        params = (f'%{search_term}%',)
        marcas = db.fetch_all(query, params)
    else:
        # Buscar todas as marcas ativas
        marcas = db.fetch_all("SELECT * FROM product_brands WHERE active = TRUE")
    
    return render_template('product_brand_list.html', marcas=marcas, search_term=search_term)

# Rota para cadastrar uma nova marca de produto
@product_brand_bp.route('/produtos/marcas/cadastrar', methods=['GET', 'POST'])
@login_required
def marca_cadastrar():
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        
        # Verificar se já existe marca com o mesmo nome
        db = get_db()
        marca_existente = db.fetch_one("SELECT * FROM product_brands WHERE name = %s AND active = TRUE", (name,))
        
        if marca_existente:
            flash(f'Já existe uma marca com o nome "{name}".', 'warning')
            return render_template('product_brand_form.html')
        
        # Inserir marca no banco de dados
        query = "INSERT INTO product_brands (name, description) VALUES (%s, %s)"
        params = (name, description)
        
        result = db.insert(query, params)
        
        if result:
            flash('Marca cadastrada com sucesso!', 'success')
            return redirect(url_for('product_brand.marcas'))
        else:
            flash('Erro ao cadastrar marca.', 'danger')
    
    return render_template('product_brand_form.html')

# Rota para editar uma marca de produto
@product_brand_bp.route('/produtos/marcas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def marca_editar(id):
    # Buscar a marca pelo ID
    db = get_db()
    marca = db.fetch_one("SELECT * FROM product_brands WHERE id = %s", (id,))
    
    if not marca:
        flash('Marca não encontrada.', 'danger')
        return redirect(url_for('product_brand.marcas'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        
        # Verificar se já existe outra marca com o mesmo nome
        marca_existente = db.fetch_one("SELECT * FROM product_brands WHERE name = %s AND id != %s AND active = TRUE", (name, id))
        
        if marca_existente:
            flash(f'Já existe outra marca com o nome "{name}".', 'warning')
            return render_template('product_brand_form.html', marca=marca)
        
        # Atualizar marca no banco de dados
        query = "UPDATE product_brands SET name = %s, description = %s WHERE id = %s"
        params = (name, description, id)
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Marca atualizada com sucesso!', 'success')
            return redirect(url_for('product_brand.marcas'))
        else:
            flash('Erro ao atualizar marca.', 'danger')
    
    return render_template('product_brand_form.html', marca=marca)

# Rota para visualizar uma marca de produto
@product_brand_bp.route('/produtos/marcas/visualizar/<int:id>')
@login_required
def marca_visualizar(id):
    # Buscar a marca pelo ID
    db = get_db()
    marca = db.fetch_one("SELECT * FROM product_brands WHERE id = %s", (id,))
    
    if not marca:
        flash('Marca não encontrada.', 'danger')
        return redirect(url_for('product_brand.marcas'))
    
    # Buscar produtos associados a esta marca
    produtos = db.fetch_all("SELECT * FROM products WHERE brand_id = %s AND active = TRUE", (id,))
    
    return render_template('product_brand_view.html', marca=marca, produtos=produtos)

# Rota para excluir uma marca de produto
@product_brand_bp.route('/produtos/marcas/excluir/<int:id>')
@login_required
def marca_excluir(id):
    # Buscar a marca pelo ID
    db = get_db()
    marca = db.fetch_one("SELECT * FROM product_brands WHERE id = %s", (id,))
    
    if not marca:
        flash('Marca não encontrada.', 'danger')
        return redirect(url_for('product_brand.marcas'))
    
    # Verificar se existem produtos associados a esta marca
    produtos = db.fetch_all("SELECT * FROM products WHERE brand_id = %s AND active = TRUE", (id,))
    
    if produtos:
        flash('Não é possível excluir esta marca, pois existem produtos associados a ela.', 'warning')
        return redirect(url_for('product_brand.marcas'))
    
    # Excluir marca do banco de dados (exclusão lógica)
    query = "UPDATE product_brands SET active = FALSE WHERE id = %s"
    params = (id,)
    
    affected_rows = db.update(query, params)
    
    if affected_rows > 0:
        flash('Marca excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir marca.', 'danger')
    
    return redirect(url_for('product_brand.marcas'))
