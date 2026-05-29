"""
Rotas para gerenciamento de estoque.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import datetime
import json

from database import get_db
from utils.auth import login_required

# Helper Kardex
try:
    from utils.estoque_helper import registrar_movimentacao
except ImportError:
    registrar_movimentacao = None

# Criar o blueprint
inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/estoque')
@login_required
def inventory_list():
    """Lista todos os produtos em estoque."""
    db = get_db()
    
    # Filtros
    category_id = request.args.get('category_id')
    location_id = request.args.get('location_id', '1')  # Default para o estoque principal
    status = request.args.get('status', 'all')
    
    # Construir a consulta base (usa products.stock_quantity como fonte única)
    query = """
        SELECT p.id as product_id, COALESCE(p.stock_quantity, 0) as quantity,
               p.name as product_name, p.internal_code as code, p.barcode as sku, 
               p.unit_measure as unit, p.cost_price as purchase_price,
               p.price as sale_price, p.category_id as category_id, c.name as category_name, 
               COALESCE(l.name, 'Principal') as location_name,
               COALESCE(cs.min_stock, 0) as min_stock, COALESCE(cs.max_stock, 0) as max_stock
        FROM products p
        LEFT JOIN product_categories c ON p.category_id = c.id
        LEFT JOIN current_stock cs ON cs.product_id = p.id AND cs.location_id = 1
        LEFT JOIN stock_locations l ON cs.location_id = l.id
        WHERE p.active = TRUE
    """
    params = []
    
    # Adicionar filtros
    if category_id:
        query += " AND p.category_id = %s"
        params.append(category_id)
    
    if location_id:
        query += " AND cs.location_id = %s"
        params.append(location_id)
    
    if status == 'low':
        query += " AND COALESCE(p.stock_quantity, 0) <= COALESCE(cs.min_stock, 0) AND COALESCE(cs.min_stock, 0) > 0"
    elif status == 'high':
        query += " AND COALESCE(p.stock_quantity, 0) >= COALESCE(cs.max_stock, 0) AND COALESCE(cs.max_stock, 0) > 0"
    elif status == 'out':
        query += " AND COALESCE(p.stock_quantity, 0) = 0"
    
    # Ordenação
    query += " ORDER BY p.name"
    
    # Executar a consulta
    stock_items = db.fetch_all(query, tuple(params))
    
    # Buscar categorias para o filtro
    categories = db.fetch_all("""
        SELECT id, name FROM product_categories
        WHERE active = TRUE
        ORDER BY name
    """)
    
    # Buscar locais de estoque para o filtro
    locations = db.fetch_all("""
        SELECT id, name FROM stock_locations
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'inventory_list.html',
        stock_items=stock_items,
        categories=categories,
        locations=locations,
        category_id=category_id,
        location_id=location_id,
        status=status,
        active_page='inventory'
    )

@inventory_bp.route('/estoque/movimentacoes')
@login_required
def inventory_movements():
    """Lista todas as movimentações de estoque."""
    db = get_db()
    
    # Filtros
    product_id = request.args.get('product_id')
    movement_type = request.args.get('movement_type', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Construir a consulta base
    query = """
        SELECT sm.*, p.name AS product_name,
               p.internal_code AS code,
               p.unit_measure AS unit,
               u.username AS created_by_name,
               l.name AS location_name
        FROM stock_movements sm
        JOIN products p ON sm.product_id = p.id
        LEFT JOIN users u ON sm.created_by = u.id
        LEFT JOIN stock_locations l ON sm.location_id = l.id
        WHERE 1=1
    """
    params = []
    
    # Adicionar filtros
    if product_id:
        query += " AND sm.product_id = %s"
        params.append(product_id)
    
    if movement_type != 'all':
        query += " AND sm.movement_type = %s"
        params.append(movement_type)
    
    if start_date:
        query += " AND DATE(sm.created_at) >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND DATE(sm.created_at) <= %s"
        params.append(end_date)
    
    # Ordenação
    query += " ORDER BY sm.created_at DESC"
    
    # Executar a consulta
    movements = db.fetch_all(query, tuple(params))
    
    # Buscar produtos para o filtro
    products = db.fetch_all("""
        SELECT id, name FROM products
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'inventory_movements.html',
        movements=movements,
        products=products,
        product_id=product_id,
        movement_type=movement_type,
        start_date=start_date,
        end_date=end_date,
        active_page='inventory_movements'
    )

@inventory_bp.route('/estoque/buscar-produtos', methods=['GET'])
@login_required
def search_products():
    """Busca produtos por nome, código ou SKU."""
    search_term = request.args.get('term', '')
    location_id = request.args.get('location_id', '1')
    
    if not search_term or len(search_term) < 2:
        return jsonify([]), 200
    
    db = get_db()
    
    # Buscar produtos que correspondem ao termo de busca (usa products.stock_quantity como fonte única)
    products = db.fetch_all("""
        SELECT p.id, p.name, p.internal_code as code, p.barcode as sku, p.unit_measure as unit, 
               p.cost_price as purchase_price, p.price as sale_price,
               COALESCE(p.stock_quantity, 0) as current_stock
        FROM products p
        WHERE p.active = TRUE AND 
              (p.name LIKE %s OR p.internal_code LIKE %s OR p.barcode LIKE %s)
        ORDER BY p.name
        LIMIT 50
    """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
    
    result = []
    for product in products:
        code_display = f"[{product['code']}] " if product['code'] else ""
        sku_display = f" (SKU: {product['sku']})" if product['sku'] else ""
        
        result.append({
            'id': product['id'],
            'text': f"{code_display}{product['name']}{sku_display} - Estoque: {product['current_stock']} {product['unit']}",
            'unit': product['unit'],
            'current_stock': product['current_stock'],
            'stock': product['current_stock'],  # Duplicado para compatibilidade com o Select2
            'name': product['name'],
            'code': product['code'] or '',
            'sku': product['sku'] or ''
        })
    
    return jsonify(result)

@inventory_bp.route('/estoque/produto-estoque', methods=['GET'])
@login_required
def get_product_stock():
    """Retorna o estoque atual de um produto em um local específico."""
    product_id = request.args.get('product_id')
    location_id = request.args.get('location_id', '1')
    
    if not product_id:
        return jsonify({'error': 'Produto não informado'}), 400
    
    db = get_db()
    
    # Buscar informações do produto (usa products.stock_quantity como fonte única)
    product = db.fetch_one("""
        SELECT p.id, p.name, p.internal_code as code, p.barcode as sku, p.unit_measure as unit, 
               p.cost_price as purchase_price, p.price as sale_price, 
               COALESCE(p.stock_quantity, 0) as current_stock
        FROM products p
        WHERE p.id = %s AND p.active = TRUE
    """, (product_id,))
    
    if not product:
        return jsonify({'error': 'Produto não encontrado'}), 404
    
    return jsonify({
        'id': product['id'],
        'name': product['name'],
        'unit': product['unit'],
        'current_stock': product['current_stock'] if product['current_stock'] is not None else 0
    })

@inventory_bp.route('/estoque/ajuste', methods=['GET', 'POST'])
@login_required
def inventory_adjustment():
    """Realiza ajustes de estoque."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        product_id = request.form.get('product_id')
        location_id = request.form.get('location_id', 1)
        quantity = request.form.get('quantity')
        adjustment_type = request.form.get('adjustment_type')
        reason = request.form.get('reason')
        
        # Validar dados
        errors = []
        
        if not product_id:
            errors.append('Produto é obrigatório.')
        
        if not quantity:
            errors.append('Quantidade é obrigatória.')
        else:
            try:
                quantity = float(quantity)
                if quantity <= 0:
                    errors.append('Quantidade deve ser maior que zero.')
            except ValueError:
                errors.append('Quantidade inválida.')
        
        if not adjustment_type:
            errors.append('Tipo de ajuste é obrigatório.')
        
        if not reason:
            errors.append('Motivo do ajuste é obrigatório.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            # Buscar produtos para o formulário (usa products.stock_quantity como fonte única)
            products = db.fetch_all("""
                SELECT p.id, p.name, p.unit_measure as unit, COALESCE(p.stock_quantity, 0) as current_stock
                FROM products p
                WHERE p.active = TRUE
                ORDER BY p.name
            """)
            
            # Buscar locais de estoque para o formulário
            locations = db.fetch_all("""
                SELECT id, name FROM stock_locations
                WHERE active = TRUE
                ORDER BY name
            """)
            
            return render_template(
                'inventory_adjustment.html',
                products=products,
                locations=locations,
                active_page='inventory_adjustment'
            )
        
        # Buscar estoque atual do produto (usa products.stock_quantity como fonte única)
        produto_estoque = db.fetch_one("""
            SELECT stock_quantity FROM products WHERE id = %s
        """, (product_id,))
        
        current_stock = db.fetch_one("""
            SELECT * FROM current_stock
            WHERE product_id = %s AND location_id = %s
        """, (product_id, location_id))
        
        # Converter quantidade para float
        try:
            quantity = float(quantity)
        except (ValueError, TypeError):
            flash('Quantidade inválida.', 'danger')
            return redirect(url_for('inventory.inventory_adjustment'))
        
        # Calcular nova quantidade e DELTA para registrar em stock_movements (usa products.stock_quantity)
        prev = float(produto_estoque['stock_quantity']) if produto_estoque and produto_estoque['stock_quantity'] is not None else 0.0
        if adjustment_type == 'add':
            new_quantity = prev + quantity
            movement_type = 'adjustment_add'
            delta = +abs(float(quantity))
        elif adjustment_type == 'subtract':
            new_quantity = prev - quantity
            if new_quantity < 0:
                quantity = prev  # limitar retirada ao saldo
                new_quantity = 0.0
            movement_type = 'adjustment_subtract'
            delta = -abs(float(quantity))
        else:  # replace
            new_quantity = quantity
            movement_type = 'adjustment_replace'
            delta = float(new_quantity) - prev
            
        # Log para debug
        print(f"Ajuste de estoque - Produto: {product_id}, Local: {location_id}, Tipo: {adjustment_type}, Quantidade: {quantity}, Novo estoque: {new_quantity}")
        
        # Usar Kardex para registrar movimentação
        if registrar_movimentacao:
            tipo_kardex = 'ajuste_positivo' if delta > 0 else 'ajuste_negativo'
            resultado = registrar_movimentacao(
                produto_id=product_id,
                tipo=tipo_kardex,
                quantidade=abs(delta),
                origem_tela='Ajuste Manual',
                referencia_tipo='ajuste',
                referencia_codigo=f'AJT-{product_id}',
                observacao=reason or f'Ajuste de estoque: {adjustment_type}',
                local_id=int(location_id)
            )
            if resultado.get('success'):
                print(f"[AJUSTE] [KARDEX] Estoque: {resultado.get('estoque_anterior')} -> {resultado.get('estoque_posterior')}")
            else:
                print(f"[AJUSTE] [KARDEX] Erro: {resultado.get('error')}")
        else:
            # Fallback: atualização direta
            if current_stock:
                db.update("""
                    UPDATE current_stock
                    SET quantity = %s
                    WHERE product_id = %s AND location_id = %s
                """, (new_quantity, product_id, location_id))
            else:
                db.insert("""
                    INSERT INTO current_stock (product_id, location_id, quantity, min_stock, max_stock)
                    VALUES (%s, %s, %s, %s, %s)
                """, (product_id, location_id, new_quantity, 0, 0))
                
            db.update("""
                UPDATE products
                SET stock_quantity = %s
                WHERE id = %s
            """, (new_quantity, product_id))
            
            # Registrar movimentação legada
            db.insert(
                """
                INSERT INTO stock_movements (
                    product_id, movement_type, quantity, reference_id, reference_type,
                    unit_cost, location_id, notes, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    product_id, movement_type, delta, None, 'adjustment',
                    0, location_id, reason, session.get('user_id', 1)
                )
            )
        
        flash('Ajuste de estoque realizado com sucesso!', 'success')
        return redirect(url_for('inventory.inventory_list'))
    # Buscar produtos para o formulário (usa products.stock_quantity como fonte única)
    location_id = request.args.get('location_id', '1')
    products = db.fetch_all("""
        SELECT p.id, p.name, p.internal_code as code, p.barcode as sku, p.unit_measure as unit,
               COALESCE(p.stock_quantity, 0) as current_stock,
               COALESCE(cs.min_stock, 0) as min_stock,
               COALESCE(cs.max_stock, 0) as max_stock
        FROM products p
        LEFT JOIN current_stock cs ON p.id = cs.product_id AND cs.location_id = %s
        WHERE p.active = TRUE
        ORDER BY p.name
    """, (location_id,))
    
    # Buscar locais de estoque para o formulário
    locations = db.fetch_all("""
        SELECT id, name FROM stock_locations
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'inventory_adjustment.html',
        products=products,
        locations=locations,
        active_page='inventory_adjustment'
    )

@inventory_bp.route('/estoque/transferencia', methods=['GET', 'POST'])
@login_required
def inventory_transfer():
    """Realiza transferências entre locais de estoque."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        product_id = request.form.get('product_id')
        source_location_id = request.form.get('source_location_id')
        target_location_id = request.form.get('target_location_id')
        quantity = request.form.get('quantity')
        notes = request.form.get('notes')
        
        # Validar dados
        errors = []
        
        if not product_id:
            errors.append('Produto é obrigatório.')
        
        if not source_location_id:
            errors.append('Local de origem é obrigatório.')
        
        if not target_location_id:
            errors.append('Local de destino é obrigatório.')
        
        if source_location_id == target_location_id:
            errors.append('Os locais de origem e destino devem ser diferentes.')
        
        if not quantity:
            errors.append('Quantidade é obrigatória.')
        else:
            try:
                quantity = float(quantity)
                if quantity <= 0:
                    errors.append('Quantidade deve ser maior que zero.')
            except ValueError:
                errors.append('Quantidade inválida.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            # Buscar produtos para o formulário
            products = db.fetch_all("""
                SELECT p.id, p.name, p.unit
                FROM products p
                WHERE p.active = TRUE
                ORDER BY p.name
            """)
            
            # Buscar locais de estoque para o formulário
            locations = db.fetch_all("""
                SELECT id, name FROM stock_locations
                WHERE active = TRUE
                ORDER BY name
            """)
            
            return render_template(
                'inventory_transfer.html',
                products=products,
                locations=locations,
                active_page='inventory_transfer'
            )
        
        # Buscar estoque atual do produto no local de origem
        source_stock = db.fetch_one("""
            SELECT * FROM current_stock
            WHERE product_id = %s AND location_id = %s
        """, (product_id, source_location_id))
        
        if not source_stock or source_stock['quantity'] < quantity:
            flash('Estoque insuficiente no local de origem.', 'danger')
            return redirect(url_for('inventory.inventory_transfer'))
        
        # Buscar estoque atual do produto no local de destino
        target_stock = db.fetch_one("""
            SELECT * FROM current_stock
            WHERE product_id = %s AND location_id = %s
        """, (product_id, target_location_id))
        
        # Atualizar estoque no local de origem
        db.update("""
            UPDATE current_stock
            SET quantity = quantity - %s
            WHERE product_id = %s AND location_id = %s
        """, (quantity, product_id, source_location_id))
        
        # Atualizar ou inserir estoque no local de destino
        if target_stock:
            db.update("""
                UPDATE current_stock
                SET quantity = quantity + %s
                WHERE product_id = %s AND location_id = %s
            """, (quantity, product_id, target_location_id))
        else:
            db.insert("""
                INSERT INTO current_stock (product_id, location_id, quantity, min_stock, max_stock)
                VALUES (%s, %s, %s, %s, %s)
            """, (product_id, target_location_id, quantity, 0, 0))
        
        # Registrar movimentação de saída
        db.insert("""
            INSERT INTO stock_movements (
                product_id, movement_type, quantity, reference_id, reference_type,
                unit_cost, location_id, notes, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            product_id, 'transfer_out', quantity, None, 'transfer',
            0, source_location_id, notes, session.get('user_id', 1)  # Usar ID 1 como padrão se não houver user_id na sessão
        ))
        
        # Registrar movimentação de entrada
        db.insert("""
            INSERT INTO stock_movements (
                product_id, movement_type, quantity, reference_id, reference_type,
                unit_cost, location_id, notes, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            product_id, 'transfer_in', quantity, None, 'transfer',
            0, target_location_id, notes, session.get('user_id', 1)  # Usar ID 1 como padrão se não houver user_id na sessão
        ))
        
        flash('Transferência de estoque realizada com sucesso!', 'success')
        return redirect(url_for('inventory.inventory_list'))
    
    # Buscar produtos para o formulário
    products = db.fetch_all("""
        SELECT p.id, p.name, p.unit
        FROM products p
        WHERE p.active = TRUE
        ORDER BY p.name
    """)
    
    # Buscar locais de estoque para o formulário
    locations = db.fetch_all("""
        SELECT id, name FROM stock_locations
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'inventory_transfer.html',
        products=products,
        locations=locations,
        active_page='inventory_transfer'
    )

@inventory_bp.route('/estoque/configurar/<int:product_id>', methods=['GET', 'POST'])
@login_required
def inventory_configure(product_id):
    """Configura parâmetros de estoque para um produto."""
    db = get_db()
    
    # Buscar o produto
    product = db.fetch_one("""
        SELECT * FROM products
        WHERE id = %s AND active = TRUE
    """, (product_id,))
    
    if not product:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('inventory.inventory_list'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        location_id = request.form.get('location_id')
        min_stock = request.form.get('min_stock') or 0
        max_stock = request.form.get('max_stock') or 0
        reorder_point = request.form.get('reorder_point') or 0
        reorder_quantity = request.form.get('reorder_quantity') or 0
        
        # Validar dados
        try:
            min_stock = float(min_stock)
            max_stock = float(max_stock)
            reorder_point = float(reorder_point)
            reorder_quantity = float(reorder_quantity)
        except ValueError:
            flash('Valores inválidos. Use apenas números.', 'danger')
            return redirect(url_for('inventory.inventory_configure', product_id=product_id))
        
        # Buscar estoque atual do produto
        current_stock = db.fetch_one("""
            SELECT * FROM current_stock
            WHERE product_id = %s AND location_id = %s
        """, (product_id, location_id))
        
        # Atualizar ou inserir configurações de estoque
        if current_stock:
            db.update("""
                UPDATE current_stock
                SET min_stock = %s, max_stock = %s, reorder_point = %s, reorder_quantity = %s
                WHERE product_id = %s AND location_id = %s
            """, (min_stock, max_stock, reorder_point, reorder_quantity, product_id, location_id))
        else:
            db.insert("""
                INSERT INTO current_stock (product_id, location_id, quantity, min_stock, max_stock, reorder_point, reorder_quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (product_id, location_id, 0, min_stock, max_stock, reorder_point, reorder_quantity))
        
        flash('Configurações de estoque atualizadas com sucesso!', 'success')
        return redirect(url_for('inventory.inventory_list'))
    
    # Buscar configurações de estoque do produto
    stock_configs = db.fetch_all("""
        SELECT cs.*, l.name as location_name
        FROM current_stock cs
        JOIN stock_locations l ON cs.location_id = l.id
        WHERE cs.product_id = %s
        ORDER BY l.name
    """, (product_id,))
    
    # Buscar locais de estoque para o formulário
    locations = db.fetch_all("""
        SELECT id, name FROM stock_locations
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'inventory_configure.html',
        product=product,
        stock_configs=stock_configs,
        locations=locations,
        active_page='inventory'
    )

@inventory_bp.route('/estoque/relatorio')
@login_required
def inventory_report():
    """Gera relatórios de estoque."""
    db = get_db()
    
    # Filtros
    report_type = request.args.get('report_type', 'current')
    location_id = request.args.get('location_id')
    category_id = request.args.get('category_id')
    
    # Construir a consulta base para o relatório atual (usa products.stock_quantity como fonte única)
    if report_type == 'current':
        query = """
            SELECT p.id as product_id, COALESCE(p.stock_quantity, 0) as quantity,
                   p.name as product_name, p.internal_code as code, p.barcode as sku, 
                   p.unit_measure as unit, p.cost_price as purchase_price,
                   p.price as sale_price, c.name as category_name, 
                   COALESCE(l.name, 'Principal') as location_name,
                   (p.price * COALESCE(p.stock_quantity, 0)) as total_value,
                   COALESCE(cs.min_stock, 0) as min_stock, COALESCE(cs.max_stock, 0) as max_stock
            FROM products p
            LEFT JOIN product_categories c ON p.category_id = c.id
            LEFT JOIN current_stock cs ON cs.product_id = p.id AND cs.location_id = 1
            LEFT JOIN stock_locations l ON cs.location_id = l.id
            WHERE p.active = TRUE AND COALESCE(p.stock_quantity, 0) > 0
        """
        params = []
        
        # Adicionar filtros
        if location_id:
            query += " AND cs.location_id = %s"
            params.append(location_id)
        
        if category_id:
            query += " AND p.category_id = %s"
            params.append(category_id)
        
        # Ordenar por nome do produto
        query += " ORDER BY p.name"
        
        # Executar a consulta
        report_data = db.fetch_all(query, tuple(params))
        
        # Calcular totais
        total_items = len(report_data)
        total_value = sum(item['total_value'] for item in report_data if item['total_value'] is not None)
        
    # Construir a consulta para o relatório de movimentações
    elif report_type == 'movements':
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = """
            SELECT sm.*, p.name AS product_name,
                   p.internal_code AS code,
                   p.unit_measure AS unit,
                   u.username AS created_by_name,
                   l.name AS location_name
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            LEFT JOIN users u ON sm.created_by = u.id
            LEFT JOIN stock_locations l ON sm.location_id = l.id
            WHERE 1=1
        """
        params = []
        
        # Adicionar filtros
        if location_id:
            query += " AND sm.location_id = %s"
            params.append(location_id)
        
        if category_id:
            query += " AND p.category_id = %s"
            params.append(category_id)
        
        if start_date:
            query += " AND DATE(sm.created_at) >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND DATE(sm.created_at) <= %s"
            params.append(end_date)
        
        # Ordenar por data de criação
        query += " ORDER BY sm.created_at DESC"
        
        # Executar a consulta
        report_data = db.fetch_all(query, tuple(params))
        
        # Calcular totais
        total_items = len(report_data)
        total_value = None
    
    # Construir a consulta para o relatório de produtos abaixo do estoque mínimo (usa products.stock_quantity)
    elif report_type == 'low_stock':
        query = """
            SELECT p.id as product_id, COALESCE(p.stock_quantity, 0) as quantity,
                   p.name as product_name, p.internal_code as code, p.barcode as sku, 
                   p.unit_measure as unit, p.cost_price as purchase_price,
                   p.price as sale_price, c.name as category_name, 
                   COALESCE(l.name, 'Principal') as location_name,
                   COALESCE(cs.min_stock, 0) as min_stock, COALESCE(cs.max_stock, 0) as max_stock,
                   (COALESCE(cs.min_stock, 0) - COALESCE(p.stock_quantity, 0)) as missing_quantity
            FROM products p
            LEFT JOIN product_categories c ON p.category_id = c.id
            LEFT JOIN current_stock cs ON cs.product_id = p.id AND cs.location_id = 1
            LEFT JOIN stock_locations l ON cs.location_id = l.id
            WHERE p.active = TRUE
            AND COALESCE(p.stock_quantity, 0) < COALESCE(cs.min_stock, 0)
            AND COALESCE(cs.min_stock, 0) > 0
        """
        params = []
        
        # Adicionar filtros
        if location_id:
            query += " AND cs.location_id = %s"
            params.append(location_id)
        
        if category_id:
            query += " AND p.category_id = %s"
            params.append(category_id)
        
        # Ordenar por quantidade faltante (decrescente)
        query += " ORDER BY missing_quantity DESC"
        
        # Executar a consulta
        report_data = db.fetch_all(query, tuple(params))
        
        # Calcular totais
        total_items = len(report_data)
        total_value = sum(item['missing_quantity'] * item['purchase_price'] for item in report_data if item['missing_quantity'] is not None and item['purchase_price'] is not None)
    
    # Buscar categorias para o filtro
    categories = db.fetch_all("""
        SELECT id, name FROM product_categories
        WHERE active = TRUE
        ORDER BY name
    """)
    
    # Buscar locais de estoque para o filtro
    locations = db.fetch_all("""
        SELECT id, name FROM stock_locations
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'inventory_report.html',
        report_data=report_data,
        report_type=report_type,
        categories=categories,
        locations=locations,
        category_id=category_id,
        location_id=location_id,
        total_items=total_items,
        total_value=total_value,
        start_date=request.args.get('start_date'),
        end_date=request.args.get('end_date'),
        active_page='inventory_report'
    )

@inventory_bp.route('/api/produto/<int:product_id>/estoque')
@login_required
def api_product_stock(product_id):
    """API para buscar estoque de um produto."""
    db = get_db()
    
    location_id = request.args.get('location_id')
    
    # Construir a consulta base
    query = """
        SELECT cs.*, l.name as location_name
        FROM current_stock cs
        JOIN stock_locations l ON cs.location_id = l.id
        WHERE cs.product_id = %s
    """
    params = [product_id]
    
    # Adicionar filtro de local
    if location_id:
        query += " AND cs.location_id = %s"
        params.append(location_id)
    
    # Executar a consulta
    stock = db.fetch_all(query, tuple(params))
    
    return jsonify(stock)
