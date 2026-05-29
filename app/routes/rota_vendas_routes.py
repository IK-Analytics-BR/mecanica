"""
Rotas para gerenciamento de rotas de vendas.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import re

from database import get_db
from utils.auth import login_required

# Criar o blueprint
rota_vendas_bp = Blueprint('rota_vendas', __name__)


@rota_vendas_bp.route('/rotas_vendas')
@login_required
def rotas_vendas_list():
    """Lista todas as rotas de vendas."""
    db = get_db()
    
    # Buscar todas as rotas de vendas ativas
    rotas = db.fetch_all("""
        SELECT r.*, s.name as seller_name
        FROM sales_routes r
        JOIN sellers s ON r.seller_id = s.id
        WHERE r.active = TRUE
        ORDER BY r.name
    """)
    
    return render_template(
        'rota_vendas_list.html',
        rotas=rotas,
        active_page='rotas_vendas'
    )

@rota_vendas_bp.route('/rotas_vendas/cadastrar', methods=['GET', 'POST'])
@login_required
def rota_vendas_cadastrar():
    """Cadastra uma nova rota de vendas."""
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        seller_id = request.form.get('seller_id')
        frequency = request.form.get('frequency')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome da rota é obrigatório.')
        
        if not seller_id:
            errors.append('Vendedor é obrigatório.')
        
        if not frequency:
            errors.append('Frequência é obrigatória.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('rota_vendas.rota_vendas_cadastrar'))
        
        # Gerar código da rota (formato: R-YYYYMMDD-XXX)
        db = get_db()
        import datetime
        today = datetime.datetime.now().strftime('%Y%m%d')
        
        # Buscar último código de rota para gerar o próximo
        last_route = db.fetch_one("""
            SELECT code FROM sales_routes
            WHERE code LIKE %s
            ORDER BY id DESC LIMIT 1
        """, (f'R-{today}-%',))
        
        if last_route:
            last_number = int(last_route['code'].split('-')[-1])
            code = f'R-{today}-{last_number + 1:03d}'
        else:
            code = f'R-{today}-001'
        
        # Inserir rota no banco de dados
        route_id = db.insert("""
            INSERT INTO sales_routes (code, name, seller_id, frequency)
            VALUES (%s, %s, %s, %s)
        """, (code, name, seller_id, frequency))
        
        if route_id:
            flash('Rota de vendas cadastrada com sucesso!', 'success')
            
            # Processar clientes vinculados respeitando a ordem enviada
            order_csv = request.form.get('clientes_order', '')
            if order_csv:
                try:
                    clientes_ids = [cid for cid in order_csv.split(',') if cid]
                except Exception:
                    clientes_ids = request.form.getlist('clientes')
            else:
                clientes_ids = request.form.getlist('clientes')
            if clientes_ids:
                for i, cliente_id in enumerate(clientes_ids, start=1):
                    db.insert("""
                        INSERT INTO route_customer (route_id, customer_id, visit_order)
                        VALUES (%s, %s, %s)
                    """, (route_id, cliente_id, i))
            
            return redirect(url_for('rota_vendas.rota_vendas_view', route_id=route_id))
        else:
            flash('Erro ao cadastrar rota de vendas.', 'danger')
    
    # Buscar vendedores para o formulário
    db = get_db()
    vendedores = db.fetch_all("""
        SELECT id, name FROM sellers
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    # Buscar clientes para o formulário
    clientes = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'rota_vendas_form.html',
        rota=None,
        vendedores=vendedores,
        clientes=clientes,
        active_page='rotas_vendas'
    )

@rota_vendas_bp.route('/rotas_vendas/editar/<int:route_id>', methods=['GET', 'POST'])
@login_required
def rota_vendas_editar(route_id):
    """Edita uma rota de vendas existente."""
    db = get_db()
    
    # Buscar a rota
    rota = db.fetch_one("""
        SELECT * FROM sales_routes
        WHERE id = %s AND active = TRUE
    """, (route_id,))
    
    if not rota:
        flash('Rota de vendas não encontrada.', 'danger')
        return redirect(url_for('rota_vendas.rotas_vendas_list'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        seller_id = request.form.get('seller_id')
        frequency = request.form.get('frequency')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome da rota é obrigatório.')
        
        if not seller_id:
            errors.append('Vendedor é obrigatório.')
        
        if not frequency:
            errors.append('Frequência é obrigatória.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('rota_vendas.rota_vendas_editar', route_id=route_id))
        
        # Atualizar rota no banco de dados (pode retornar 0 se não houve mudança de cabeçalho)
        affected_rows = db.update("""
            UPDATE sales_routes
            SET name = %s, seller_id = %s, frequency = %s
            WHERE id = %s
        """, (name, seller_id, frequency, route_id))
        
        # Mesmo que nenhum campo de cabeçalho mude (affected_rows == 0), ainda assim precisamos atualizar a ordem de visita
        if affected_rows >= 0:
            flash('Rota de vendas atualizada com sucesso!', 'success')
            
            # Atualizar clientes vinculados
            # Primeiro, remover todos os vínculos existentes
            db.execute("""
                DELETE FROM route_customer
                WHERE route_id = %s
            """, (route_id,))
            
            # Depois, adicionar os novos vínculos
            order_csv = request.form.get('clientes_order', '')
            if order_csv:
                try:
                    clientes_ids = [cid for cid in order_csv.split(',') if cid]
                except Exception:
                    clientes_ids = request.form.getlist('clientes')
            else:
                clientes_ids = request.form.getlist('clientes')
            if clientes_ids:
                for i, cliente_id in enumerate(clientes_ids, start=1):
                    db.insert("""
                        INSERT INTO route_customer (route_id, customer_id, visit_order)
                        VALUES (%s, %s, %s)
                    """, (route_id, cliente_id, i))
            
            return redirect(url_for('rota_vendas.rota_vendas_view', route_id=route_id))
        else:
            flash('Erro ao atualizar rota de vendas.', 'danger')
    
    # Buscar vendedores para o formulário
    vendedores = db.fetch_all("""
        SELECT id, name FROM sellers
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    # Buscar clientes para o formulário
    clientes = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    # Buscar clientes vinculados à rota
    clientes_vinculados = db.fetch_all("""
        SELECT rc.customer_id, rc.visit_order FROM route_customer rc
        WHERE rc.route_id = %s
        ORDER BY rc.visit_order
    """, (route_id,))
    
    clientes_ids = [cliente['customer_id'] for cliente in clientes_vinculados]
    
    return render_template(
        'rota_vendas_form.html',
        rota=rota,
        route_id=route_id,
        vendedores=vendedores,
        clientes=clientes,
        clientes_ids=clientes_ids,
        active_page='rotas_vendas'
    )

@rota_vendas_bp.route('/rotas_vendas/visualizar/<int:route_id>')
@login_required
def rota_vendas_view(route_id):
    """Visualiza detalhes de uma rota de vendas."""
    db = get_db()
    
    # Buscar a rota
    rota = db.fetch_one("""
        SELECT r.*, s.name as seller_name
        FROM sales_routes r
        JOIN sellers s ON r.seller_id = s.id
        WHERE r.id = %s AND r.active = TRUE
    """, (route_id,))
    
    if not rota:
        flash('Rota de vendas não encontrada.', 'danger')
        return redirect(url_for('rota_vendas.rotas_vendas_list'))
    
    # Buscar clientes vinculados à rota
    clientes = db.fetch_all("""
        SELECT c.*, rc.visit_order
        FROM customers c
        JOIN route_customer rc ON c.id = rc.customer_id
        WHERE rc.route_id = %s AND c.active = TRUE
        ORDER BY rc.visit_order
    """, (route_id,))
    
    # Buscar romaneios da rota
    romaneios = db.fetch_all("""
        SELECT m.*, s.name as seller_name
        FROM sales_manifests m
        JOIN sellers s ON m.seller_id = s.id
        WHERE m.route_id = %s AND m.active = TRUE
        ORDER BY m.date DESC
        LIMIT 10
    """, (route_id,))
    
    return render_template(
        'rota_vendas_view.html',
        rota=rota,
        clientes=clientes,
        romaneios=romaneios,
        active_page='rotas_vendas'
    )

@rota_vendas_bp.route('/rotas_vendas/excluir/<int:route_id>', methods=['POST'])
@login_required
def rota_vendas_excluir(route_id):
    """Exclui uma rota de vendas (exclusão lógica)."""
    db = get_db()
    
    # Verificar se a rota existe
    rota = db.fetch_one("""
        SELECT * FROM sales_routes
        WHERE id = %s AND active = TRUE
    """, (route_id,))
    
    if not rota:
        flash('Rota de vendas não encontrada.', 'danger')
        return redirect(url_for('rota_vendas.rotas_vendas_list'))
    
    # Verificar se a rota possui romaneios ativos
    romaneios = db.fetch_one("""
        SELECT COUNT(*) as count FROM sales_manifests
        WHERE route_id = %s AND active = TRUE AND status != 'completed' AND status != 'canceled'
    """, (route_id,))
    
    if romaneios and romaneios['count'] > 0:
        flash('Não é possível excluir a rota pois ela possui romaneios ativos.', 'danger')
        return redirect(url_for('rota_vendas.rota_vendas_view', route_id=route_id))
    
    # Excluir rota (exclusão lógica)
    affected_rows = db.update("""
        UPDATE sales_routes
        SET active = FALSE
        WHERE id = %s
    """, (route_id,))
    
    if affected_rows > 0:
        flash('Rota de vendas excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir rota de vendas.', 'danger')
    
    return redirect(url_for('rota_vendas.rotas_vendas_list'))
