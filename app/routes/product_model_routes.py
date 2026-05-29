from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db
from utils.auth import login_required

product_model_bp = Blueprint('product_model', __name__)

# Auth decorator

@product_model_bp.route('/produtos/modelos')
@login_required
def modelos():
    search_term = request.args.get('search_term', '')
    db = get_db()
    if search_term:
        modelos = db.fetch_all("SELECT * FROM product_models WHERE active = TRUE AND name LIKE %s ORDER BY name", (f"%{search_term}%",))
    else:
        modelos = db.fetch_all("SELECT * FROM product_models WHERE active = TRUE ORDER BY name")
    return render_template('product_model_list.html', modelos=modelos, search_term=search_term)

@product_model_bp.route('/produtos/modelos/cadastrar', methods=['GET','POST'])
@login_required
def modelo_cadastrar():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        description = request.form.get('description','').strip()
        if not name:
            flash('Nome é obrigatório.', 'danger')
            return render_template('product_model_form.html')
        db = get_db()
        exists = db.fetch_one("SELECT id FROM product_models WHERE name = %s AND active = TRUE", (name,))
        if exists:
            flash('Já existe um modelo com esse nome.', 'warning')
            return render_template('product_model_form.html', modelo={'name': name, 'description': description})
        db.insert("INSERT INTO product_models (name, description) VALUES (%s,%s)", (name, description))
        flash('Modelo cadastrado com sucesso!', 'success')
        return redirect(url_for('product_model.modelos'))
    return render_template('product_model_form.html')

@product_model_bp.route('/produtos/modelos/editar/<int:id>', methods=['GET','POST'])
@login_required
def modelo_editar(id):
    db = get_db()
    modelo = db.fetch_one("SELECT * FROM product_models WHERE id = %s", (id,))
    if not modelo:
        flash('Modelo não encontrado.', 'danger')
        return redirect(url_for('product_model.modelos'))
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        description = request.form.get('description','').strip()
        dup = db.fetch_one("SELECT id FROM product_models WHERE name = %s AND id != %s AND active = TRUE", (name, id))
        if dup:
            flash('Já existe outro modelo com esse nome.', 'warning')
            return render_template('product_model_form.html', modelo=modelo)
        db.update("UPDATE product_models SET name=%s, description=%s WHERE id=%s", (name, description, id))
        flash('Modelo atualizado!', 'success')
        return redirect(url_for('product_model.modelos'))
    return render_template('product_model_form.html', modelo=modelo)

@product_model_bp.route('/produtos/modelos/visualizar/<int:id>')
@login_required
def modelo_visualizar(id):
    db = get_db()
    modelo = db.fetch_one("SELECT * FROM product_models WHERE id = %s", (id,))
    if not modelo:
        flash('Modelo não encontrado.', 'danger')
        return redirect(url_for('product_model.modelos'))
    produtos = db.fetch_all("SELECT * FROM products WHERE model_id = %s AND active = TRUE", (id,))
    return render_template('product_model_view.html', modelo=modelo, produtos=produtos)

@product_model_bp.route('/produtos/modelos/excluir/<int:id>')
@login_required
def modelo_excluir(id):
    db = get_db()
    modelo = db.fetch_one("SELECT * FROM product_models WHERE id = %s", (id,))
    if not modelo:
        flash('Modelo não encontrado.', 'danger')
        return redirect(url_for('product_model.modelos'))
    produtos = db.fetch_all("SELECT id FROM products WHERE model_id = %s AND active = TRUE", (id,))
    if produtos:
        flash('Não é possível excluir. Existem produtos associados.', 'warning')
        return redirect(url_for('product_model.modelos'))
    db.update("UPDATE product_models SET active = FALSE WHERE id = %s", (id,))
    flash('Modelo excluído com sucesso!', 'success')
    return redirect(url_for('product_model.modelos'))
