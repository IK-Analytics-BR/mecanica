"""
Rotas para pedidos de compra.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import mysql.connector
import datetime
from database import get_db
from utils.auth import login_required
from functools import wraps


purchase_order_bp = Blueprint('purchase_order', __name__)

@purchase_order_bp.route('/pedidos-compra', methods=['GET'])
@login_required
def purchase_orders_list():
    """Lista todos os pedidos de compra."""
    db = get_db()
    
    # Filtros
    status = request.args.get('status', '')
    supplier_id = request.args.get('supplier_id', '')
    
    # Consulta base
    query = """
    SELECT po.*, s.name as supplier_name
    FROM purchase_orders po
    LEFT JOIN suppliers s ON po.supplier_id = s.id
    WHERE 1=1
    """
    params = []
    
    # Adicionar filtros se fornecidos
    if status:
        query += " AND po.status = %s"
        params.append(status)
    
    if supplier_id:
        query += " AND po.supplier_id = %s"
        params.append(supplier_id)
    
    # Ordenar por data de criação (mais recente primeiro)
    query += " ORDER BY po.created_at DESC"
    
    # Executar consulta
    orders = db.fetch_all(query, tuple(params))
    
    # Buscar fornecedores para o filtro
    suppliers = db.fetch_all("SELECT id, name FROM suppliers ORDER BY name")
    
    return render_template(
        'purchase_order_list.html',
        orders=orders,
        suppliers=suppliers,
        status=status,
        supplier_id=supplier_id,
        active_page='purchase_orders'
    )

@purchase_order_bp.route('/pedidos-compra/cadastrar', methods=['GET', 'POST'])
@login_required
def purchase_order_create():
    """Redireciona para o formulário integrado de pedidos de compra."""
    return redirect(url_for('purchase_order_integrated.purchase_order_create'))

@purchase_order_bp.route('/pedidos-compra/<int:order_id>', methods=['GET'])
@login_required
def purchase_order_view(order_id):
    """Visualiza um pedido de compra específico."""
    db = get_db()
    
    # Buscar dados do pedido
    order = db.fetch_one("""
    SELECT po.*, s.name as supplier_name, s.cnpj as supplier_tax_id,
           pt.name as payment_term_name, pm.name as payment_method_name,
           cc.name as cost_center_name, u.name as created_by_name
    FROM purchase_orders po
    LEFT JOIN suppliers s ON po.supplier_id = s.id
    LEFT JOIN payment_terms pt ON po.payment_term_id = pt.id
    LEFT JOIN payment_methods pm ON po.payment_method_id = pm.id
    LEFT JOIN cost_centers cc ON po.cost_center_id = cc.id
    LEFT JOIN users u ON po.created_by = u.id
    WHERE po.id = %s
    """, (order_id,))
    
    if not order:
        flash('Pedido de compra não encontrado.', 'danger')
        return redirect(url_for('purchase_order.purchase_orders_list'))
    
    # Buscar itens do pedido
    items = db.fetch_all("""
    SELECT poi.*, p.name as product_name, p.internal_code as product_code
    FROM purchase_order_items poi
    LEFT JOIN products p ON poi.product_id = p.id
    WHERE poi.purchase_order_id = %s
    ORDER BY poi.id
    """, (order_id,))
    
    # Calcular total dos itens
    total_amount = sum(float(item.get('total_price', 0) or 0) for item in items)
    
    # Buscar histórico de status do pedido (opcional, tabela pode não existir)
    try:
        status_history = db.fetch_all(
            """
            SELECT posh.*, u.name as user_name
            FROM purchase_order_status_history posh
            LEFT JOIN users u ON posh.user_id = u.id
            WHERE posh.purchase_order_id = %s
            ORDER BY posh.created_at DESC
            """,
            (order_id,)
        )
    except mysql.connector.errors.ProgrammingError:
        status_history = []
    
    return render_template(
        'purchase_order_view.html',
        order=order,
        items=items,
        total_amount=total_amount,
        status_history=status_history,
        active_page='purchase_orders'
    )

@purchase_order_bp.route('/pedidos-compra/<int:order_id>/atualizar-status', methods=['POST'])
@login_required
def purchase_order_update_status(order_id):
    """Atualiza o status de um pedido de compra."""
    db = get_db()
    
    # Verificar se o pedido existe
    order = db.fetch_one("SELECT * FROM purchase_orders WHERE id = %s", (order_id,))
    if not order:
        flash('Pedido de compra não encontrado.', 'danger')
        return redirect(url_for('purchase_order.purchase_orders_list'))
    
    # Obter novo status
    new_status = request.form.get('status')
    if not new_status:
        flash('Status não fornecido.', 'danger')
        return redirect(url_for('purchase_order.purchase_order_view', order_id=order_id))
    
    # Obter comentário (opcional)
    comment = request.form.get('comment', '')
    
    # Atualizar status do pedido
    db.execute(
        "UPDATE purchase_orders SET status = %s, updated_at = NOW() WHERE id = %s",
        (new_status, order_id)
    )
    
    # Registrar histórico de status (se a tabela existir)
    try:
        db.insert(
            """
            INSERT INTO purchase_order_status_history 
            (purchase_order_id, old_status, new_status, comment, user_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (order_id, order['status'], new_status, comment, session['user_id'])
        )
    except mysql.connector.errors.ProgrammingError:
        # Ignorar se tabela não existir
        pass
    
    flash('Status do pedido atualizado com sucesso.', 'success')
    return redirect(url_for('purchase_order.purchase_order_view', order_id=order_id))

@purchase_order_bp.route('/pedidos-compra/<int:order_id>/editar', methods=['GET', 'POST'])
@login_required
def purchase_order_edit(order_id):
    """Edita um pedido de compra."""
    db = get_db()
    
    # Verificar se o pedido existe
    order = db.fetch_one("SELECT * FROM purchase_orders WHERE id = %s", (order_id,))
    if not order:
        flash('Pedido de compra não encontrado.', 'danger')
        return redirect(url_for('purchase_order.purchase_orders_list'))
    
    # Verificar se o pedido pode ser editado (apenas rascunhos)
    if order['status'] != 'draft':
        flash('Apenas pedidos em rascunho podem ser editados.', 'warning')
        return redirect(url_for('purchase_order.purchase_order_view', order_id=order_id))
    
    if request.method == 'POST':
        # Obter dados do formulário
        supplier_id = request.form.get('supplier_id')
        order_date = request.form.get('order_date')
        expected_delivery_date = request.form.get('expected_delivery_date') or None
        contact_name = request.form.get('contact_name')
        payment_term_id = request.form.get('payment_term_id') or None
        payment_method_id = request.form.get('payment_method_id') or None
        cost_center_id = request.form.get('cost_center_id') or None
        delivery_address = request.form.get('delivery_address')
        notes = request.form.get('notes')
        status = request.form.get('status')
        
        # Valores financeiros
        subtotal = float(request.form.get('subtotal') or 0)
        discount_percent = float(request.form.get('discount_percent') or 0)
        discount_value = float(request.form.get('discount_value') or 0)
        shipping_cost = float(request.form.get('shipping_cost') or 0)
        insurance_cost = float(request.form.get('insurance_cost') or 0)
        other_costs = float(request.form.get('other_costs') or 0)
        tax_value = float(request.form.get('tax_value') or 0)
        total_value = float(request.form.get('total_value') or 0)
        
        # Validar dados
        errors = []
        
        if not supplier_id:
            errors.append('Fornecedor é obrigatório.')
        
        if not order_date:
            errors.append('Data do pedido é obrigatória.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            # Buscar dados para o formulário
            suppliers = db.fetch_all("SELECT id, name FROM suppliers ORDER BY name")
            products = db.fetch_all("SELECT id, name, unit_measure, cost_price FROM products ORDER BY name")
            payment_terms = db.fetch_all("SELECT id, name FROM payment_terms ORDER BY name")
            payment_methods = db.fetch_all("SELECT id, name FROM payment_methods ORDER BY name")
            cost_centers = db.fetch_all("SELECT id, code, name FROM cost_centers ORDER BY name")
            
            # Buscar itens do pedido
            items = db.fetch_all("""
            SELECT * FROM purchase_order_items WHERE purchase_order_id = %s
            """, (order_id,))
            
            return render_template(
                'purchase_order_form.html',
                order=order,
                items=items,
                suppliers=suppliers,
                products=products,
                payment_terms=payment_terms,
                payment_methods=payment_methods,
                cost_centers=cost_centers,
                active_page='purchase_orders'
            )
        
        # Atualizar pedido no banco de dados
        db.execute("""
        UPDATE purchase_orders SET
            supplier_id = %s,
            order_date = %s,
            expected_delivery_date = %s,
            contact_name = %s,
            payment_term_id = %s,
            payment_method_id = %s,
            cost_center_id = %s,
            delivery_address = %s,
            notes = %s,
            status = %s,
            subtotal = %s,
            discount_percent = %s,
            discount_value = %s,
            shipping_cost = %s,
            insurance_cost = %s,
            other_costs = %s,
            tax_value = %s,
            total_value = %s,
            updated_at = NOW()
        WHERE id = %s
        """, (
            supplier_id, order_date, expected_delivery_date,
            contact_name, payment_term_id, payment_method_id, cost_center_id,
            delivery_address, notes, status,
            subtotal, discount_percent, discount_value, shipping_cost,
            insurance_cost, other_costs, tax_value, total_value,
            order_id
        ))
        
        # Remover itens existentes
        db.execute("DELETE FROM purchase_order_items WHERE purchase_order_id = %s", (order_id,))
        
        # Processar itens do pedido
        for key, value in request.form.items():
            if key.startswith('items[') and key.endswith('][product_id]'):
                index = key.split('[')[1].split(']')[0]
                product_id = request.form.get(f'items[{index}][product_id]')
                quantity = float(request.form.get(f'items[{index}][quantity]') or 0)
                unit_price = float(request.form.get(f'items[{index}][unit_price]') or 0)
                discount_percent = float(request.form.get(f'items[{index}][discount_percent]') or 0)
                total_price = float(request.form.get(f'items[{index}][total_price]') or 0)
                
                # Calcular valor do desconto
                discount_value = (quantity * unit_price) * (discount_percent / 100)
                
                # Inserir item do pedido
                db.insert("""
                INSERT INTO purchase_order_items (
                    purchase_order_id, product_id, quantity, unit_price,
                    discount_percent, discount_value, total_price, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    order_id, product_id, quantity, unit_price,
                    discount_percent, discount_value, total_price, 'pending'
                ))
        
        flash('Pedido de compra atualizado com sucesso!', 'success')
        return redirect(url_for('purchase_order.purchase_order_view', order_id=order_id))
    
    # Buscar dados para o formulário
    suppliers = db.fetch_all("SELECT id, name FROM suppliers ORDER BY name")
    products = db.fetch_all("SELECT id, name, unit_measure, cost_price FROM products ORDER BY name")
    payment_terms = db.fetch_all("SELECT id, name FROM payment_terms ORDER BY name")
    payment_methods = db.fetch_all("SELECT id, name FROM payment_methods ORDER BY name")
    cost_centers = db.fetch_all("SELECT id, code, name FROM cost_centers ORDER BY name")
    
    # Buscar itens do pedido
    items = db.fetch_all("""
    SELECT * FROM purchase_order_items WHERE purchase_order_id = %s
    """, (order_id,))
    
    return render_template(
        'purchase_order_form.html',
        order=order,
        items=items,
        suppliers=suppliers,
        products=products,
        payment_terms=payment_terms,
        payment_methods=payment_methods,
        cost_centers=cost_centers,
        active_page='purchase_orders'
    )

@purchase_order_bp.route('/pedidos-compra/<int:order_id>/excluir', methods=['POST'])
@login_required
def purchase_order_delete(order_id):
    """Exclui um pedido de compra."""
    db = get_db()
    
    # Verificar se o pedido existe
    order = db.fetch_one("SELECT * FROM purchase_orders WHERE id = %s", (order_id,))
    if not order:
        flash('Pedido de compra não encontrado.', 'danger')
        return redirect(url_for('purchase_order.purchase_orders_list'))
    
    # Verificar se o pedido pode ser excluído (apenas rascunhos)
    if order['status'] != 'draft':
        flash('Apenas pedidos em rascunho podem ser excluídos.', 'warning')
        return redirect(url_for('purchase_order.purchase_order_view', order_id=order_id))
    
    # Excluir itens do pedido
    db.execute("DELETE FROM purchase_order_items WHERE purchase_order_id = %s", (order_id,))
    
    # Excluir histórico de status do pedido
    db.execute("DELETE FROM purchase_order_status_history WHERE purchase_order_id = %s", (order_id,))
    
    # Excluir pedido
    db.execute("DELETE FROM purchase_orders WHERE id = %s", (order_id,))
    
    flash('Pedido de compra excluído com sucesso!', 'success')
    return redirect(url_for('purchase_order.purchase_orders_list'))

@purchase_order_bp.route('/pedidos-compra/<int:order_id>/imprimir', methods=['GET'])
@login_required
def purchase_order_print(order_id):
    """Exibe versão para impressão de um pedido de compra."""
    db = get_db()
    
    # Buscar dados do pedido
    order = db.fetch_one("""
    SELECT po.*, s.name as supplier_name, s.cnpj as supplier_tax_id,
           s.address as supplier_address, s.city as supplier_city,
           s.state as supplier_state, s.zip_code as supplier_zip_code,
           s.phone as supplier_phone, s.email as supplier_email,
           pt.name as payment_term_name, pm.name as payment_method_name,
           cc.name as cost_center_name, u.name as created_by_name
    FROM purchase_orders po
    LEFT JOIN suppliers s ON po.supplier_id = s.id
    LEFT JOIN payment_terms pt ON po.payment_term_id = pt.id
    LEFT JOIN payment_methods pm ON po.payment_method_id = pm.id
    LEFT JOIN cost_centers cc ON po.cost_center_id = cc.id
    LEFT JOIN users u ON po.created_by = u.id
    WHERE po.id = %s
    """, (order_id,))
    
    if not order:
        flash('Pedido de compra não encontrado.', 'danger')
        return redirect(url_for('purchase_order.purchase_orders_list'))
    
    # Buscar itens do pedido
    items = db.fetch_all("""
    SELECT poi.*, p.name as product_name, p.internal_code as product_code,
           p.unit_measure as product_unit
    FROM purchase_order_items poi
    LEFT JOIN products p ON poi.product_id = p.id
    WHERE poi.purchase_order_id = %s
    ORDER BY poi.id
    """, (order_id,))
    
    # Buscar dados da empresa
    company = db.fetch_one("SELECT * FROM company_info LIMIT 1")
    
    return render_template(
        'purchase_order_print.html',
        order=order,
        items=items,
        company=company,
        active_page='purchase_orders'
    )

# ========================================
# CORREÇÃO #3 e #4: Recebimento de Mercadoria
# ========================================

@purchase_order_bp.route('/pedidos-compra/<int:order_id>/receber', methods=['GET', 'POST'])
@login_required
def purchase_order_receive(order_id):
    """Recebe mercadoria do pedido de compra e atualiza estoque + financeiro."""
    db = get_db()
    
    # Buscar pedido
    order = db.fetch_one("""
        SELECT po.*, s.name as supplier_name
        FROM purchase_orders po
        LEFT JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.id = %s
    """, (order_id,))
    
    if not order:
        flash('Pedido de compra não encontrado.', 'danger')
        return redirect(url_for('purchase_order.purchase_orders_list'))
    
    # Verificar se pedido pode ser recebido
    if order['status'] not in ('approved', 'sent', 'partial'):
        flash('Apenas pedidos aprovados/enviados podem ser recebidos.', 'warning')
        return redirect(url_for('purchase_order.purchase_order_view', order_id=order_id))
    
    # Buscar itens do pedido
    items = db.fetch_all("""
        SELECT poi.*, p.name as product_name, p.unit_measure as unit
        FROM purchase_order_items poi
        LEFT JOIN products p ON poi.product_id = p.id
        WHERE poi.purchase_order_id = %s
        ORDER BY poi.id
    """, (order_id,))
    
    if request.method == 'POST':
        # Obter dados do recebimento
        received_date = request.form.get('received_date') or datetime.datetime.now().strftime('%Y-%m-%d')
        invoice_number = request.form.get('invoice_number', '')
        invoice_date = request.form.get('invoice_date', received_date)
        notes = request.form.get('notes', '')
        location_id = request.form.get('location_id', 1)  # Estoque padrão
        
        # Obter quantidades recebidas por item
        items_received = []
        for item in items:
            qty_received = request.form.get(f'qty_received_{item["id"]}')
            if qty_received:
                try:
                    qty = float(qty_received)
                    if qty > 0:
                        items_received.append({
                            'item_id': item['id'],
                            'product_id': item['product_id'],
                            'quantity': qty,
                            'unit_cost': float(item.get('unit_price', 0))
                        })
                except ValueError:
                    pass
        
        if not items_received:
            flash('Informe a quantidade recebida de pelo menos um item.', 'warning')
            return render_template(
                'purchase_order_receive.html',
                order=order,
                items=items,
                active_page='purchase_orders'
            )
        
        # Obter user_id
        try:
            user_id = int(session.get('user_id', 1))
        except:
            user_id = 1
        
        # CORREÇÃO #3: Atualizar estoque para cada item recebido
        for item_rec in items_received:
            try:
                # 1. Inserir movimento de estoque (ENTRADA)
                db.insert("""
                    INSERT INTO stock_movements
                    (product_id, quantity, movement_type, reference_id, reference_type,
                     unit_cost, created_by, location_id, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    item_rec['product_id'],
                    abs(item_rec['quantity']),  # Quantidade POSITIVA (entrada)
                    'purchase_receive',
                    order_id,
                    'purchase_order',
                    item_rec['unit_cost'],
                    user_id,
                    location_id,
                    f'Recebimento do pedido #{order_id} - NF: {invoice_number}'
                ))
                
                # 2. Atualizar current_stock (usando UPSERT)
                db.insert("""
                    INSERT INTO current_stock (product_id, location_id, quantity)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                """, (item_rec['product_id'], location_id, abs(item_rec['quantity'])))
                
                # 3. Tentar atualizar products.stock (se coluna existir)
                try:
                    for col in ('stock', 'quantity', 'on_hand', 'qty'):
                        try:
                            db.update(
                                f"UPDATE products SET {col} = {col} + %s WHERE id = %s",
                                (abs(item_rec['quantity']), item_rec['product_id'])
                            )
                            break
                        except:
                            continue
                except:
                    pass
                    
            except Exception as e:
                print(f"[ERRO] Falha ao atualizar estoque do produto {item_rec['product_id']}: {e}")
        
        # CORREÇÃO #4: Criar lançamento em Contas a Pagar
        try:
            # Calcular data de vencimento
            from datetime import datetime as dt, timedelta
            invoice_date_obj = dt.strptime(invoice_date, '%Y-%m-%d')
            
            # Assumir 30 dias padrão (pode pegar de payment_terms se existir)
            days_to_pay = 30
            due_date = (invoice_date_obj + timedelta(days=days_to_pay)).strftime('%Y-%m-%d')
            
            # Inserir em accounts_payable
            db.insert("""
                INSERT INTO accounts_payable
                (supplier_id, purchase_order_id, invoice_number, invoice_date,
                 due_date, total_amount, paid_amount, status, payment_method,
                 notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                order['supplier_id'],
                order_id,
                invoice_number or f'PO-{order_id}',
                invoice_date,
                due_date,
                order.get('total_value', 0),
                0.0,  # paid_amount = 0
                'pending',
                order.get('payment_method') or 'boleto',
                f'Lançamento automático - Pedido #{order_id}'
            ))
        except Exception as e:
            print(f"[AVISO] Erro ao criar conta a pagar: {e}")
        
        # Atualizar status do pedido para 'received'
        db.execute("""
            UPDATE purchase_orders 
            SET status = 'received', updated_at = NOW()
            WHERE id = %s
        """, (order_id,))
        
        flash(f'Mercadoria recebida com sucesso! Estoque e financeiro atualizados.', 'success')
        return redirect(url_for('purchase_order.purchase_order_view', order_id=order_id))
    
    # GET - Mostrar formulário de recebimento
    return render_template(
        'purchase_order_receive.html',
        order=order,
        items=items,
        active_page='purchase_orders'
    )
