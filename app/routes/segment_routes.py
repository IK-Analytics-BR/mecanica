from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required

# Criar um Blueprint para as rotas de segmento
segment_bp = Blueprint('segment', __name__)


# Rota para listar todos os segmentos
@segment_bp.route('/segmentos')
@login_required
def segmentos():
    # Buscar segmentos ativos no banco de dados
    db = get_db()
    segmentos = db.fetch_all("SELECT * FROM segments WHERE active = TRUE ORDER BY name")
    
    return render_template('segment_list.html', segmentos=segmentos)

# Rota para cadastrar um novo segmento
@segment_bp.route('/segmentos/cadastrar', methods=['GET', 'POST'])
@login_required
def segmento_cadastrar():
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        
        # Inserir segmento no banco de dados
        db = get_db()
        query = "INSERT INTO segments (name, description) VALUES (%s, %s)"
        params = (name, description)
        
        segmento_id = db.insert(query, params)
        
        if segmento_id:
            flash('Segmento cadastrado com sucesso!', 'success')
            return redirect(url_for('segment.segmentos'))
        else:
            flash('Erro ao cadastrar segmento.', 'danger')
    
    # Renderizar o formulário de cadastro de segmento
    return render_template('segment_form.html', segmento=None)

# Rota para editar um segmento existente
@segment_bp.route('/segmentos/editar/<id>', methods=['GET', 'POST'])
@login_required
def segmento_editar(id):
    # Buscar o segmento pelo ID
    db = get_db()
    segmento = db.fetch_one("SELECT * FROM segments WHERE id = %s", (id,))
    
    if not segmento:
        flash('Segmento não encontrado.', 'danger')
        return redirect(url_for('segment.segmentos'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        
        # Atualizar segmento no banco de dados
        query = """
            UPDATE segments
            SET name = %s, description = %s
            WHERE id = %s
        """
        params = (name, description, id)
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Segmento atualizado com sucesso!', 'success')
            return redirect(url_for('segment.segmentos'))
        else:
            flash('Erro ao atualizar segmento.', 'danger')
    
    # Renderizar o formulário de edição de segmento
    return render_template('segment_form.html', segmento=segmento)

# Rota para visualizar um segmento
@segment_bp.route('/segmentos/visualizar/<id>')
@login_required
def segmento_visualizar(id):
    # Buscar o segmento pelo ID
    db = get_db()
    segmento = db.fetch_one("SELECT * FROM segments WHERE id = %s", (id,))
    
    if not segmento:
        flash('Segmento não encontrado.', 'danger')
        return redirect(url_for('segment.segmentos'))
    
    # Buscar clientes e fornecedores deste segmento
    clientes = db.fetch_all("""
        SELECT * FROM customers 
        WHERE segment_id = %s AND active = TRUE
    """, (id,))
    
    fornecedores = db.fetch_all("""
        SELECT * FROM suppliers 
        WHERE segment_id = %s AND active = TRUE
    """, (id,))
    
    # Renderizar a visualização do segmento
    return render_template('segment_view.html', 
                          segmento=segmento, 
                          clientes=clientes, 
                          fornecedores=fornecedores)

# Rota para excluir um segmento
@segment_bp.route('/segmentos/excluir/<id>')
@login_required
def segmento_excluir(id):
    # Buscar o segmento pelo ID
    db = get_db()
    segmento = db.fetch_one("SELECT * FROM segments WHERE id = %s", (id,))
    
    if segmento:
        # Verificar se o segmento está sendo usado por clientes ou fornecedores
        clientes = db.fetch_all("SELECT COUNT(*) as count FROM customers WHERE segment_id = %s AND active = TRUE", (id,))
        fornecedores = db.fetch_all("SELECT COUNT(*) as count FROM suppliers WHERE segment_id = %s AND active = TRUE", (id,))
        
        if (clientes and clientes[0]['count'] > 0) or (fornecedores and fornecedores[0]['count'] > 0):
            flash('Não é possível excluir o segmento pois existem clientes ou fornecedores associados a ele.', 'danger')
            return redirect(url_for('segment.segmentos'))
        
        # Marcar o segmento como inativo (exclusão lógica)
        affected_rows = db.update("""
            UPDATE segments SET active = FALSE WHERE id = %s
        """, (id,))
        
        if affected_rows > 0:
            flash('Segmento excluído com sucesso!', 'success')
        else:
            flash('Erro ao excluir segmento.', 'danger')
    else:
        flash('Segmento não encontrado.', 'danger')
    
    # Redirecionar para a lista de segmentos
    return redirect(url_for('segment.segmentos'))
