"""
Rotas para gerenciamento de romaneios de vendas.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import datetime

from database import get_db
from utils.auth import login_required

# Criar o blueprint
romaneio_bp = Blueprint('romaneio', __name__)


@romaneio_bp.route('/romaneios')
@login_required
def romaneio_list():
    """Lista todos os romaneios de vendas."""
    db = get_db()
    
    # Buscar todos os romaneios ativos
    romaneios = db.fetch_all("""
        SELECT m.*, s.name as seller_name, r.name as route_name
        FROM sales_manifests m
        JOIN sellers s ON m.seller_id = s.id
        JOIN sales_routes r ON m.route_id = r.id
        WHERE m.active = TRUE
        ORDER BY m.date DESC
    """)
    
    return render_template(
        'romaneio_list.html',
        romaneios=romaneios,
        active_page='romaneios'
    )

@romaneio_bp.route('/romaneios/cadastrar', methods=['GET', 'POST'])
@login_required
def romaneio_cadastrar():
    """Cadastra um novo romaneio de vendas."""
    if request.method == 'POST':
        # Obter dados do formulário
        date = request.form.get('date')
        seller_id = request.form.get('seller_id')
        route_id = request.form.get('route_id')
        notes = request.form.get('notes')
        
        # Validar dados
        errors = []
        
        if not date:
            errors.append('Data é obrigatória.')
        
        if not seller_id:
            errors.append('Vendedor é obrigatório.')
        
        if not route_id:
            errors.append('Rota é obrigatória.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('romaneio.romaneio_cadastrar'))
        
        # Gerar número do romaneio (formato: RM-YYYYMMDD-XXX)
        db = get_db()
        today = datetime.datetime.now().strftime('%Y%m%d')
        
        # Buscar último número de romaneio para gerar o próximo
        last_manifest = db.fetch_one("""
            SELECT manifest_number FROM sales_manifests
            WHERE manifest_number LIKE %s
            ORDER BY id DESC LIMIT 1
        """, (f'RM-{today}-%',))
        
        if last_manifest:
            last_number = int(last_manifest['manifest_number'].split('-')[-1])
            manifest_number = f'RM-{today}-{last_number + 1:03d}'
        else:
            manifest_number = f'RM-{today}-001'
        
        # Inserir romaneio no banco de dados
        manifest_id = db.insert("""
            INSERT INTO sales_manifests (manifest_number, date, seller_id, route_id, notes, status)
            VALUES (%s, %s, %s, %s, %s, 'draft')
        """, (manifest_number, date, seller_id, route_id, notes))
        
        if manifest_id:
            flash('Romaneio cadastrado com sucesso!', 'success')
            
            # Buscar clientes da rota
            clientes = db.fetch_all("""
                SELECT customer_id, visit_order FROM route_customer
                WHERE route_id = %s
                ORDER BY visit_order
            """, (route_id,))
            
            # Criar visitas para cada cliente da rota
            for cliente in clientes:
                db.insert("""
                    INSERT INTO manifest_visits (manifest_id, customer_id, visit_order, visit_status)
                    VALUES (%s, %s, %s, 'pending')
                """, (manifest_id, cliente['customer_id'], cliente['visit_order']))
            
            return redirect(url_for('romaneio.romaneio_view', manifest_id=manifest_id))
        else:
            flash('Erro ao cadastrar romaneio.', 'danger')
    
    # Buscar vendedores para o formulário
    db = get_db()
    vendedores = db.fetch_all("""
        SELECT id, name FROM sellers
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    # Buscar rotas para o formulário
    rotas = db.fetch_all("""
        SELECT r.id, r.name, r.seller_id, s.name as seller_name
        FROM sales_routes r
        JOIN sellers s ON r.seller_id = s.id
        WHERE r.active = TRUE
        ORDER BY r.name
    """)
    
    return render_template(
        'romaneio_form.html',
        romaneio=None,
        vendedores=vendedores,
        rotas=rotas,
        active_page='romaneios'
    )

@romaneio_bp.route('/romaneios/editar/<int:manifest_id>', methods=['GET', 'POST'])
@login_required
def romaneio_editar(manifest_id):
    """Edita um romaneio de vendas existente."""
    db = get_db()
    
    # Buscar o romaneio
    romaneio = db.fetch_one("""
        SELECT * FROM sales_manifests
        WHERE id = %s AND active = TRUE
    """, (manifest_id,))
    
    if not romaneio:
        flash('Romaneio não encontrado.', 'danger')
        return redirect(url_for('romaneio.romaneio_list'))
    
    # Verificar se o romaneio pode ser editado
    if romaneio['status'] in ['completed', 'canceled']:
        flash('Não é possível editar um romaneio concluído ou cancelado.', 'danger')
        return redirect(url_for('romaneio.romaneio_view', manifest_id=manifest_id))
    
    if request.method == 'POST':
        # Obter dados do formulário
        date = request.form.get('date')
        seller_id = request.form.get('seller_id')
        route_id = request.form.get('route_id')
        notes = request.form.get('notes')
        status = request.form.get('status')
        
        # Validar dados
        errors = []
        
        if not date:
            errors.append('Data é obrigatória.')
        
        if not seller_id:
            errors.append('Vendedor é obrigatório.')
        
        if not route_id:
            errors.append('Rota é obrigatória.')
        
        if not status:
            errors.append('Status é obrigatório.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('romaneio.romaneio_editar', manifest_id=manifest_id))
        
        # Atualizar romaneio no banco de dados
        affected_rows = db.update("""
            UPDATE sales_manifests
            SET date = %s, seller_id = %s, route_id = %s, notes = %s, status = %s
            WHERE id = %s
        """, (date, seller_id, route_id, notes, status, manifest_id))
        
        if affected_rows > 0:
            flash('Romaneio atualizado com sucesso!', 'success')
            return redirect(url_for('romaneio.romaneio_view', manifest_id=manifest_id))
        else:
            flash('Erro ao atualizar romaneio.', 'danger')
    
    # Buscar vendedores para o formulário
    vendedores = db.fetch_all("""
        SELECT id, name FROM sellers
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    # Buscar rotas para o formulário
    rotas = db.fetch_all("""
        SELECT r.id, r.name, r.seller_id, s.name as seller_name
        FROM sales_routes r
        JOIN sellers s ON r.seller_id = s.id
        WHERE r.active = TRUE
        ORDER BY r.name
    """)
    
    return render_template(
        'romaneio_form.html',
        romaneio=romaneio,
        manifest_id=manifest_id,
        vendedores=vendedores,
        rotas=rotas,
        active_page='romaneios'
    )

@romaneio_bp.route('/romaneios/visualizar/<int:manifest_id>')
@login_required
def romaneio_view(manifest_id):
    """Visualiza detalhes de um romaneio de vendas."""
    db = get_db()
    
    # Buscar o romaneio
    romaneio = db.fetch_one("""
        SELECT m.*, s.name as seller_name, r.name as route_name
        FROM sales_manifests m
        JOIN sellers s ON m.seller_id = s.id
        JOIN sales_routes r ON m.route_id = r.id
        WHERE m.id = %s AND m.active = TRUE
    """, (manifest_id,))
    
    if not romaneio:
        flash('Romaneio não encontrado.', 'danger')
        return redirect(url_for('romaneio.romaneio_list'))
    
    # Buscar visitas do romaneio
    visitas = db.fetch_all("""
        SELECT v.*, c.name as customer_name, c.address, c.number, c.complement, c.neighborhood, c.city, c.state, c.phone
        FROM manifest_visits v
        JOIN customers c ON v.customer_id = c.id
        WHERE v.manifest_id = %s
        ORDER BY v.visit_order
    """, (manifest_id,))
    
    # Buscar pedidos do romaneio
    pedidos = db.fetch_all("""
        SELECT o.*, c.name as customer_name
        FROM manifest_orders o
        JOIN manifest_visits v ON o.visit_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE v.manifest_id = %s
        ORDER BY v.visit_order
    """, (manifest_id,))
    
    # Calcular totais
    total_pedidos = sum(pedido['total_amount'] for pedido in pedidos)
    total_clientes = len(visitas)
    clientes_visitados = sum(1 for visita in visitas if visita['visit_status'] == 'visited')
    
    return render_template(
        'romaneio_view.html',
        romaneio=romaneio,
        visitas=visitas,
        pedidos=pedidos,
        total_pedidos=total_pedidos,
        total_clientes=total_clientes,
        clientes_visitados=clientes_visitados,
        active_page='romaneios'
    )

@romaneio_bp.route('/romaneios/excluir/<int:manifest_id>', methods=['POST'])
@login_required
def romaneio_excluir(manifest_id):
    """Exclui um romaneio de vendas (exclusão lógica)."""
    db = get_db()
    
    # Verificar se o romaneio existe
    romaneio = db.fetch_one("""
        SELECT * FROM sales_manifests
        WHERE id = %s AND active = TRUE
    """, (manifest_id,))
    
    if not romaneio:
        flash('Romaneio não encontrado.', 'danger')
        return redirect(url_for('romaneio.romaneio_list'))
    
    # Verificar se o romaneio pode ser excluído
    if romaneio['status'] in ['in_progress', 'completed']:
        flash('Não é possível excluir um romaneio em andamento ou concluído.', 'danger')
        return redirect(url_for('romaneio.romaneio_view', manifest_id=manifest_id))
    
    # Excluir romaneio (exclusão lógica)
    affected_rows = db.update("""
        UPDATE sales_manifests
        SET active = FALSE, status = 'canceled'
        WHERE id = %s
    """, (manifest_id,))
    
    if affected_rows > 0:
        flash('Romaneio excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir romaneio.', 'danger')
    
    return redirect(url_for('romaneio.romaneio_list'))

@romaneio_bp.route('/romaneios/visita/<int:visit_id>', methods=['POST'])
@login_required
def romaneio_visita_update(visit_id):
    """Atualiza o status de uma visita."""
    db = get_db()
    
    # Buscar a visita
    visita = db.fetch_one("""
        SELECT v.*, m.status as manifest_status
        FROM manifest_visits v
        JOIN sales_manifests m ON v.manifest_id = m.id
        WHERE v.id = %s
    """, (visit_id,))
    
    if not visita:
        flash('Visita não encontrada.', 'danger')
        return redirect(url_for('romaneio.romaneio_list'))
    
    # Verificar se o romaneio permite atualização de visitas
    if visita['manifest_status'] in ['completed', 'canceled']:
        flash('Não é possível atualizar visitas de um romaneio concluído ou cancelado.', 'danger')
        return redirect(url_for('romaneio.romaneio_view', manifest_id=visita['manifest_id']))
    
    # Obter dados do formulário
    status = request.form.get('status')
    notes = request.form.get('notes')
    
    # Validar dados
    if not status:
        flash('Status é obrigatório.', 'danger')
        return redirect(url_for('romaneio.romaneio_view', manifest_id=visita['manifest_id']))
    
    # Atualizar visita
    visit_time = datetime.datetime.now() if status == 'visited' else None
    
    affected_rows = db.update("""
        UPDATE manifest_visits
        SET visit_status = %s, notes = %s, visit_time = %s
        WHERE id = %s
    """, (status, notes, visit_time, visit_id))
    
    if affected_rows > 0:
        flash('Visita atualizada com sucesso!', 'success')
    else:
        flash('Erro ao atualizar visita.', 'danger')
    
    return redirect(url_for('romaneio.romaneio_view', manifest_id=visita['manifest_id']))

@romaneio_bp.route('/romaneios/pedido/<int:visit_id>', methods=['POST'])
@login_required
def romaneio_pedido_add(visit_id):
    """Adiciona um pedido a uma visita."""
    db = get_db()
    
    # Buscar a visita
    visita = db.fetch_one("""
        SELECT v.*, m.status as manifest_status
        FROM manifest_visits v
        JOIN sales_manifests m ON v.manifest_id = m.id
        WHERE v.id = %s
    """, (visit_id,))
    
    if not visita:
        flash('Visita não encontrada.', 'danger')
        return redirect(url_for('romaneio.romaneio_list'))
    
    # Verificar se o romaneio permite adicionar pedidos
    if visita['manifest_status'] in ['completed', 'canceled']:
        flash('Não é possível adicionar pedidos a um romaneio concluído ou cancelado.', 'danger')
        return redirect(url_for('romaneio.romaneio_view', manifest_id=visita['manifest_id']))
    
    # Obter dados do formulário
    payment_method = request.form.get('payment_method')
    payment_terms = request.form.get('payment_terms')
    notes = request.form.get('notes')
    
    # Validar dados
    if not payment_method:
        flash('Forma de pagamento é obrigatória.', 'danger')
        return redirect(url_for('romaneio.romaneio_view', manifest_id=visita['manifest_id']))
    
    # Gerar número do pedido (formato: PD-YYYYMMDD-XXX)
    today = datetime.datetime.now().strftime('%Y%m%d')
    
    # Buscar último número de pedido para gerar o próximo
    last_order = db.fetch_one("""
        SELECT order_number FROM manifest_orders
        WHERE order_number LIKE %s
        ORDER BY id DESC LIMIT 1
    """, (f'PD-{today}-%',))
    
    if last_order:
        last_number = int(last_order['order_number'].split('-')[-1])
        order_number = f'PD-{today}-{last_number + 1:03d}'
    else:
        order_number = f'PD-{today}-001'
    
    # Inserir pedido
    order_id = db.insert("""
        INSERT INTO manifest_orders (visit_id, order_number, payment_method, payment_terms, notes)
        VALUES (%s, %s, %s, %s, %s)
    """, (visit_id, order_number, payment_method, payment_terms, notes))
    
    if order_id:
        flash('Pedido adicionado com sucesso!', 'success')
        
        # Atualizar status da visita para visitada
        db.update("""
            UPDATE manifest_visits
            SET visit_status = 'visited', visit_time = NOW()
            WHERE id = %s
        """, (visit_id,))
        
        # Adicionar itens do pedido
        produtos = request.form.getlist('produtos[]')
        quantidades = request.form.getlist('quantidades[]')
        precos = request.form.getlist('precos[]')
        
        total_amount = 0
        
        for i in range(len(produtos)):
            if produtos[i] and quantidades[i] and precos[i]:
                produto_id = produtos[i]
                quantidade = int(quantidades[i])
                preco = float(precos[i])
                total = quantidade * preco
                
                db.insert("""
                    INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (order_id, produto_id, quantidade, preco, total))
                
                total_amount += total
        
        # Atualizar o valor total do pedido
        db.update("""
            UPDATE manifest_orders
            SET total_amount = %s
            WHERE id = %s
        """, (total_amount, order_id))
    else:
        flash('Erro ao adicionar pedido.', 'danger')
    
    return redirect(url_for('romaneio.romaneio_view', manifest_id=visita['manifest_id']))

@romaneio_bp.route('/romaneios/finalizar/<int:manifest_id>', methods=['POST'])
@login_required
def romaneio_finalizar(manifest_id):
    """Finaliza um romaneio de vendas."""
    db = get_db()
    
    # Verificar se o romaneio existe
    romaneio = db.fetch_one("""
        SELECT * FROM sales_manifests
        WHERE id = %s AND active = TRUE
    """, (manifest_id,))
    
    if not romaneio:
        flash('Romaneio não encontrado.', 'danger')
        return redirect(url_for('romaneio.romaneio_list'))
    
    # Verificar se o romaneio pode ser finalizado
    if romaneio['status'] in ['completed', 'canceled']:
        flash('Este romaneio já está finalizado ou cancelado.', 'warning')
        return redirect(url_for('romaneio.romaneio_view', manifest_id=manifest_id))
    
    # Finalizar romaneio
    affected_rows = db.update("""
        UPDATE sales_manifests
        SET status = 'completed'
        WHERE id = %s
    """, (manifest_id,))
    
    if affected_rows > 0:
        flash('Romaneio finalizado com sucesso!', 'success')
    else:
        flash('Erro ao finalizar romaneio.', 'danger')
    
    return redirect(url_for('romaneio.romaneio_view', manifest_id=manifest_id))

@romaneio_bp.route('/romaneios/cancelar/<int:manifest_id>', methods=['POST'])
@login_required
def romaneio_cancelar(manifest_id):
    """Cancela um romaneio de vendas."""
    db = get_db()
    
    # Verificar se o romaneio existe
    romaneio = db.fetch_one("""
        SELECT * FROM sales_manifests
        WHERE id = %s AND active = TRUE
    """, (manifest_id,))
    
    if not romaneio:
        flash('Romaneio não encontrado.', 'danger')
        return redirect(url_for('romaneio.romaneio_list'))
    
    # Verificar se o romaneio pode ser cancelado
    if romaneio['status'] == 'completed':
        flash('Não é possível cancelar um romaneio já concluído.', 'danger')
        return redirect(url_for('romaneio.romaneio_view', manifest_id=manifest_id))
    
    if romaneio['status'] == 'canceled':
        flash('Este romaneio já está cancelado.', 'warning')
        return redirect(url_for('romaneio.romaneio_view', manifest_id=manifest_id))
    
    # Cancelar romaneio
    affected_rows = db.update("""
        UPDATE sales_manifests
        SET status = 'canceled'
        WHERE id = %s
    """, (manifest_id,))
    
    if affected_rows > 0:
        flash('Romaneio cancelado com sucesso!', 'success')
    else:
        flash('Erro ao cancelar romaneio.', 'danger')
    
    return redirect(url_for('romaneio.romaneio_view', manifest_id=manifest_id))
