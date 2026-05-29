# Helper Kardex
try:
    from utils.estoque_helper import registrar_movimentacao
except ImportError:
    registrar_movimentacao = None


def _process_invoice(db, invoice_id, user_id=1):
    """Processa a nota fiscal: atualiza status, movimenta estoque e ajusta pedidos relacionados."""
    # Atualizar status da nota para 'processed' e data de processamento
    db.update(
        """
        UPDATE invoices
        SET status = 'processed', processed_date = CURDATE()
        WHERE id = %s
        """,
        (invoice_id,)
    )

    # Atualizar o status dos itens
    db.update(
        """
        UPDATE invoice_items
        SET status = 'processed'
        WHERE invoice_id = %s
        """,
        (invoice_id,)
    )

    # Obter itens para movimentar estoque
    items = db.fetch_all(
        """
        SELECT ii.*, p.name as product_name
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = %s
        """,
        (invoice_id,)
    )

    for item in items or []:
        product_id = item['product_id']
        quantity = item['quantity']

        # Usar Kardex para registrar movimentação
        if registrar_movimentacao:
            resultado = registrar_movimentacao(
                produto_id=product_id,
                tipo='entrada',
                quantidade=quantity,
                origem_tela='Recebimento NF',
                referencia_tipo='invoice',
                referencia_id=invoice_id,
                referencia_codigo=f'NF-{invoice_id}',
                observacao=f'Recebimento da NF #{invoice_id}',
                custo_unitario=item.get('unit_price')
            )
            if resultado.get('success'):
                print(f"[NF RECEBIMENTO] [KARDEX] Produto {product_id}: {resultado.get('estoque_anterior')} -> {resultado.get('estoque_posterior')}")
            else:
                print(f"[NF RECEBIMENTO] [KARDEX] Erro: {resultado.get('error')}")
        else:
            # Fallback: atualização direta
            db.update(
                """
                UPDATE products
                SET stock_quantity = COALESCE(stock_quantity, 0) + %s
                WHERE id = %s
                """,
                (quantity, product_id)
            )
            
            # Sincronizar current_stock
            stock = db.fetch_one(
                """
                SELECT * FROM current_stock
                WHERE product_id = %s AND location_id = 1
                """,
                (product_id,)
            )

            if stock:
                db.update(
                    """
                    UPDATE current_stock
                    SET quantity = quantity + %s, last_purchase_date = CURDATE()
                    WHERE product_id = %s AND location_id = 1
                    """,
                    (quantity, product_id)
                )
            else:
                import datetime
                db.insert(
                    """
                    INSERT INTO current_stock (
                        product_id, location_id, quantity, min_stock, max_stock, last_purchase_date
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (product_id, 1, quantity, 0, 0, datetime.datetime.now().date())
                )

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
                    product_id, 'purchase', quantity, invoice_id, 'invoice',
                    item['unit_price'], 1, f"Recebimento da NF", user_id
                )
            )

    # Se a nota estiver vinculada a um pedido de compra, ajustar status do pedido
    invoice = db.fetch_one("SELECT purchase_order_id FROM invoices WHERE id = %s", (invoice_id,))
    if invoice and invoice.get('purchase_order_id'):
        purchase_order_id = invoice['purchase_order_id']
        po_items = db.fetch_all(
            """
            SELECT status FROM purchase_order_items
            WHERE purchase_order_id = %s
            """,
            (purchase_order_id,)
        )
        if po_items:
            all_received = all(i['status'] == 'received' for i in po_items)
            any_received = any(i['status'] in ['received', 'partially_received'] for i in po_items)
            if all_received:
                db.update(
                    """
                    UPDATE purchase_orders
                    SET status = 'received', received_date = CURDATE()
                    WHERE id = %s
                    """,
                    (purchase_order_id,)
                )
            elif any_received:
                db.update(
                    """
                    UPDATE purchase_orders
                    SET status = 'partially_received'
                    WHERE id = %s
                    """,
                    (purchase_order_id,)
                )
"""
Rotas para gerenciamento de notas fiscais.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import datetime
import os
import xml.etree.ElementTree as ET
import uuid

from database import get_db
from utils.auth import login_required

# Criar o blueprint
invoice_bp = Blueprint('invoice', __name__)


@invoice_bp.route('/notas-fiscais')
@login_required
def invoice_list():
    """Lista todas as notas fiscais."""
    db = get_db()
    
    # Filtros
    status = request.args.get('status', 'all')
    supplier_id = request.args.get('supplier_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Construir a consulta base
    query = """
        SELECT i.*, s.name as supplier_name
        FROM invoices i
        JOIN suppliers s ON i.supplier_id = s.id
        WHERE i.active = TRUE
    """
    params = []
    
    # Adicionar filtros
    if status != 'all':
        query += " AND i.status = %s"
        params.append(status)
    
    if supplier_id:
        query += " AND i.supplier_id = %s"
        params.append(supplier_id)
    
    if start_date:
        query += " AND i.issue_date >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND i.issue_date <= %s"
        params.append(end_date)
    
    # Ordenação
    query += " ORDER BY i.issue_date DESC"
    
    # Executar a consulta
    invoices = db.fetch_all(query, tuple(params))
    
    # Buscar fornecedores para o filtro
    suppliers = db.fetch_all("""
        SELECT id, name FROM suppliers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'invoice_list.html',
        invoices=invoices,
        suppliers=suppliers,
        status=status,
        supplier_id=supplier_id,
        start_date=start_date,
        end_date=end_date,
        active_page='invoices'
    )

@invoice_bp.route('/notas-fiscais/cadastrar', methods=['GET', 'POST'])
@login_required
def invoice_create():
    """Cadastra uma nova nota fiscal."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        supplier_id = request.form.get('supplier_id')
        invoice_number = request.form.get('invoice_number')
        invoice_series = request.form.get('invoice_series')
        issue_date = request.form.get('issue_date')
        total_amount = request.form.get('total_amount').replace('.', '').replace(',', '.')
        tax_amount = request.form.get('tax_amount').replace('.', '').replace(',', '.')
        notes = request.form.get('notes')
        purchase_order_id = request.form.get('purchase_order_id') or None
        import_po_id = request.form.get('import_po_id') or None
        process_on_save = request.form.get('process_on_save') in ('1','on','true','True')
        
        # Validar dados
        errors = []
        
        # Se importar PO e não veio fornecedor, busque do pedido
        if not supplier_id and import_po_id:
            po = db.fetch_one("SELECT supplier_id FROM purchase_orders WHERE id = %s", (import_po_id,))
            if po:
                supplier_id = po['supplier_id']
        if not supplier_id:
            errors.append('Fornecedor é obrigatório.')
        
        if not invoice_number:
            errors.append('Número da nota fiscal é obrigatório.')
        
        if not issue_date:
            errors.append('Data de emissão é obrigatória.')
        
        if not total_amount:
            errors.append('Valor total é obrigatório.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            # Buscar fornecedores para o formulário
            suppliers = db.fetch_all("""
                SELECT id, name FROM suppliers
                WHERE active = TRUE
                ORDER BY name
            """)
            
            # Buscar pedidos de compra para o formulário
            purchase_orders = db.fetch_all("""
                SELECT po.id, po.order_number, s.name as supplier_name
                FROM purchase_orders po
                JOIN suppliers s ON po.supplier_id = s.id
                WHERE po.status IN ('sent', 'confirmed', 'partially_received')
                AND po.active = TRUE
                ORDER BY po.order_date DESC
            """)
            
            return render_template(
                'invoice_form.html',
                invoice=None,
                suppliers=suppliers,
                purchase_orders=purchase_orders,
                active_page='invoices'
            )
        
        # Inserir nota fiscal no banco de dados
        invoice_id = db.insert("""
            INSERT INTO invoices (
                supplier_id, invoice_number, invoice_series, issue_date,
                total_amount, tax_amount, notes, purchase_order_id, status, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            supplier_id, invoice_number, invoice_series, issue_date,
            total_amount, tax_amount, notes, (import_po_id or purchase_order_id), 'pending', session.get('user_id', 1)
        ))
        
        if invoice_id:
            # Se foi solicitado importar um pedido aprovado, inserir itens na nota
            if import_po_id:
                po_items = db.fetch_all(
                    """
                    SELECT poi.product_id, poi.quantity, poi.unit_price
                    FROM purchase_order_items poi
                    WHERE poi.purchase_order_id = %s
                    """,
                    (import_po_id,)
                )
                if po_items:
                    for it in po_items:
                        quantity = float(it['quantity'])
                        unit_price = float(it['unit_price'])
                        total_price = quantity * unit_price
                        db.insert(
                            """
                            INSERT INTO invoice_items (
                                invoice_id, product_id, quantity, unit_price,
                                total_price, tax_percentage, tax_amount, status
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (invoice_id, it['product_id'], quantity, unit_price, total_price, 0, 0, 'active')
                        )
                    # Atualizar totais da nota com base nos itens inseridos
                    db.execute(
                        """
                        UPDATE invoices
                        SET total_amount = COALESCE((SELECT SUM(total_price) FROM invoice_items WHERE invoice_id = %s), 0),
                            tax_amount = COALESCE((SELECT SUM(tax_amount) FROM invoice_items WHERE invoice_id = %s), 0)
                        WHERE id = %s
                        """,
                        (invoice_id, invoice_id, invoice_id)
                    )
            # Processar a nota e dar entrada no estoque, se solicitado
            if process_on_save:
                _process_invoice(db, invoice_id, session.get('user_id', 1))
                flash('Nota fiscal cadastrada e processada com entrada no estoque!', 'success')
            else:
                flash('Nota fiscal cadastrada com sucesso!', 'success')
            return redirect(url_for('invoice.invoice_view', invoice_id=invoice_id))
        else:
            flash('Erro ao cadastrar nota fiscal.', 'danger')
    
    # Buscar fornecedores para o formulário
    suppliers = db.fetch_all("""
        SELECT id, name FROM suppliers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    # Buscar pedidos de compra para o formulário
    purchase_orders = db.fetch_all("""
        SELECT po.id, po.order_number, s.id as supplier_id, s.name as supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.status IN ('approved')
        ORDER BY po.order_date DESC
    """)
    
    return render_template(
        'invoice_form.html',
        invoice=None,
        suppliers=suppliers,
        purchase_orders=purchase_orders,
        active_page='invoices'
    )

@invoice_bp.route('/notas-fiscais/editar/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def invoice_edit(invoice_id):
    """Edita uma nota fiscal existente."""
    db = get_db()
    
    # Buscar a nota fiscal
    invoice = db.fetch_one("""
        SELECT i.*, s.name as supplier_name
        FROM invoices i
        JOIN suppliers s ON i.supplier_id = s.id
        WHERE i.id = %s AND i.active = TRUE
    """, (invoice_id,))
    
    if not invoice:
        flash('Nota fiscal não encontrada.', 'danger')
        return redirect(url_for('invoice.invoice_list'))
    
    # Verificar se a nota fiscal pode ser editada
    if invoice['status'] not in ['pending', 'verified']:
        flash('Não é possível editar uma nota fiscal que já foi processada ou cancelada.', 'danger')
        return redirect(url_for('invoice.invoice_view', invoice_id=invoice_id))
    
    if request.method == 'POST':
        # Obter dados do formulário
        supplier_id = request.form.get('supplier_id')
        invoice_number = request.form.get('invoice_number')
        invoice_series = request.form.get('invoice_series')
        issue_date = request.form.get('issue_date')
        total_amount = request.form.get('total_amount').replace('.', '').replace(',', '.')
        tax_amount = request.form.get('tax_amount').replace('.', '').replace(',', '.')
        notes = request.form.get('notes')
        purchase_order_id = request.form.get('purchase_order_id') or None
        status = request.form.get('status')
        
        # Validar dados
        errors = []
        
        if not supplier_id:
            errors.append('Fornecedor é obrigatório.')
        
        if not invoice_number:
            errors.append('Número da nota fiscal é obrigatório.')
        
        if not issue_date:
            errors.append('Data de emissão é obrigatória.')
        
        if not total_amount:
            errors.append('Valor total é obrigatório.')
        
        if not status:
            errors.append('Status é obrigatório.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('invoice.invoice_edit', invoice_id=invoice_id))
        
        # Atualizar nota fiscal no banco de dados
        affected_rows = db.update("""
            UPDATE invoices
            SET supplier_id = %s, invoice_number = %s, invoice_series = %s, issue_date = %s,
                total_amount = %s, tax_amount = %s, notes = %s, purchase_order_id = %s, status = %s
            WHERE id = %s
        """, (
            supplier_id, invoice_number, invoice_series, issue_date,
            total_amount, tax_amount, notes, purchase_order_id, status, invoice_id
        ))
        
        if affected_rows > 0:
            flash('Nota fiscal atualizada com sucesso!', 'success')
            
            # Se o status foi alterado para 'verified', atualizar a data de verificação
            if status == 'verified' and invoice['status'] != 'verified':
                db.update("""
                    UPDATE invoices
                    SET verified_date = CURDATE()
                    WHERE id = %s
                """, (invoice_id,))
            
            return redirect(url_for('invoice.invoice_view', invoice_id=invoice_id))
        else:
            flash('Erro ao atualizar nota fiscal.', 'danger')
    
    # Buscar fornecedores para o formulário
    suppliers = db.fetch_all("""
        SELECT id, name FROM suppliers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    # Buscar pedidos de compra para o formulário
    purchase_orders = db.fetch_all("""
        SELECT po.id, po.order_number, s.name as supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.status IN ('sent', 'confirmed', 'partially_received')
        AND po.active = TRUE
        ORDER BY po.order_date DESC
    """)
    
    # Buscar itens da nota fiscal
    items = db.fetch_all("""
        SELECT ii.*, p.name as product_name, p.unit as product_unit
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = %s
        ORDER BY ii.id
    """, (invoice_id,))
    
    # Buscar produtos para o formulário
    products = db.fetch_all("""
        SELECT id, name, unit, purchase_price
        FROM products
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'invoice_form.html',
        invoice=invoice,
        suppliers=suppliers,
        purchase_orders=purchase_orders,
        items=items,
        products=products,
        active_page='invoices'
    )

@invoice_bp.route('/notas-fiscais/visualizar/<int:invoice_id>')
@login_required
def invoice_view(invoice_id):
    """Visualiza detalhes de uma nota fiscal."""
    db = get_db()
    
    # Buscar a nota fiscal
    invoice = db.fetch_one("""
        SELECT i.*, s.name as supplier_name, u.name as created_by_name,
               po.order_number as purchase_order_number
        FROM invoices i
        JOIN suppliers s ON i.supplier_id = s.id
        JOIN users u ON i.created_by = u.id
        LEFT JOIN purchase_orders po ON i.purchase_order_id = po.id
        WHERE i.id = %s AND i.active = TRUE
    """, (invoice_id,))
    
    if not invoice:
        flash('Nota fiscal não encontrada.', 'danger')
        return redirect(url_for('invoice.invoice_list'))
    
    # Buscar itens da nota fiscal
    items = db.fetch_all("""
        SELECT ii.*, p.name as product_name, p.unit as product_unit
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = %s
        ORDER BY ii.id
    """, (invoice_id,))
    
    # Calcular totais
    total_items = len(items)
    total_amount = sum(item['total_price'] for item in items) if items else invoice['total_amount']
    
    return render_template(
        'invoice_view.html',
        invoice=invoice,
        items=items,
        total_items=total_items,
        total_amount=total_amount,
        active_page='invoices'
    )

@invoice_bp.route('/notas-fiscais/excluir/<int:invoice_id>', methods=['POST'])
@login_required
def invoice_delete(invoice_id):
    """Exclui uma nota fiscal (exclusão lógica)."""
    db = get_db()
    
    # Verificar se a nota fiscal existe
    invoice = db.fetch_one("""
        SELECT * FROM invoices
        WHERE id = %s AND active = TRUE
    """, (invoice_id,))
    
    if not invoice:
        flash('Nota fiscal não encontrada.', 'danger')
        return redirect(url_for('invoice.invoice_list'))
    
    # Verificar se a nota fiscal pode ser excluída
    if invoice['status'] not in ['pending', 'verified']:
        flash('Não é possível excluir uma nota fiscal que já foi processada.', 'danger')
        return redirect(url_for('invoice.invoice_view', invoice_id=invoice_id))
    
    # Excluir nota fiscal (exclusão lógica)
    affected_rows = db.update("""
        UPDATE invoices
        SET active = FALSE, status = 'canceled'
        WHERE id = %s
    """, (invoice_id,))
    
    # Cancelar itens da nota fiscal
    db.update("""
        UPDATE invoice_items
        SET status = 'canceled'
        WHERE invoice_id = %s
    """, (invoice_id,))
    
    if affected_rows > 0:
        flash('Nota fiscal excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir nota fiscal.', 'danger')
    
    return redirect(url_for('invoice.invoice_list'))

@invoice_bp.route('/notas-fiscais/item/adicionar', methods=['POST'])
@login_required
def invoice_add_item():
    """Adiciona um item à nota fiscal."""
    db = get_db()
    
    # Obter dados do formulário
    invoice_id = request.form.get('invoice_id')
    product_id = request.form.get('product_id')
    quantity = request.form.get('quantity')
    unit_price = request.form.get('unit_price')
    tax_percentage = request.form.get('tax_percentage') or 0
    
    # Validar dados
    errors = []
    
    if not invoice_id:
        errors.append('ID da nota fiscal é obrigatório.')
    
    if not product_id:
        errors.append('Produto é obrigatório.')
    
    if not quantity:
        errors.append('Quantidade é obrigatória.')
    else:
        try:
            quantity = float(quantity)
        except ValueError:
            errors.append('Quantidade inválida.')
    
    if not unit_price:
        errors.append('Preço unitário é obrigatório.')
    else:
        try:
            unit_price = float(unit_price.replace('.', '').replace(',', '.'))
        except ValueError:
            errors.append('Preço unitário inválido.')
    
    # Se houver erros, exibir mensagens e retornar
    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('invoice.invoice_edit', invoice_id=invoice_id))
    
    # Calcular preço total e imposto
    total_price = quantity * unit_price
    tax_amount = total_price * (float(tax_percentage) / 100)
    
    # Inserir item no banco de dados
    item_id = db.insert("""
        INSERT INTO invoice_items (
            invoice_id, product_id, quantity, unit_price,
            total_price, tax_percentage, tax_amount, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        invoice_id, product_id, quantity, unit_price,
        total_price, tax_percentage, tax_amount, 'active'
    ))
    
    if item_id:
        # Atualizar o valor total da nota fiscal
        db.execute("""
            UPDATE invoices
            SET total_amount = (SELECT SUM(total_price) FROM invoice_items WHERE invoice_id = %s),
                tax_amount = (SELECT SUM(tax_amount) FROM invoice_items WHERE invoice_id = %s)
            WHERE id = %s
        """, (invoice_id, invoice_id, invoice_id))
        
        flash('Item adicionado com sucesso!', 'success')
    else:
        flash('Erro ao adicionar item.', 'danger')
    
    return redirect(url_for('invoice.invoice_edit', invoice_id=invoice_id))

@invoice_bp.route('/notas-fiscais/item/excluir/<int:item_id>', methods=['POST'])
@login_required
def invoice_delete_item(item_id):
    """Remove um item da nota fiscal."""
    db = get_db()
    
    # Buscar o item
    item = db.fetch_one("""
        SELECT * FROM invoice_items
        WHERE id = %s
    """, (item_id,))
    
    if not item:
        flash('Item não encontrado.', 'danger')
        return redirect(url_for('invoice.invoice_list'))
    
    # Buscar a nota fiscal
    invoice = db.fetch_one("""
        SELECT * FROM invoices
        WHERE id = %s
    """, (item['invoice_id'],))
    
    if not invoice:
        flash('Nota fiscal não encontrada.', 'danger')
        return redirect(url_for('invoice.invoice_list'))
    
    # Verificar se a nota fiscal pode ser editada
    if invoice['status'] not in ['pending', 'verified']:
        flash('Não é possível editar uma nota fiscal que já foi processada ou cancelada.', 'danger')
        return redirect(url_for('invoice.invoice_view', invoice_id=invoice['id']))
    
    # Excluir o item
    affected_rows = db.delete("""
        DELETE FROM invoice_items
        WHERE id = %s
    """, (item_id,))
    
    if affected_rows > 0:
        # Atualizar o valor total da nota fiscal
        db.execute("""
            UPDATE invoices
            SET total_amount = COALESCE((SELECT SUM(total_price) FROM invoice_items WHERE invoice_id = %s), 0),
                tax_amount = COALESCE((SELECT SUM(tax_amount) FROM invoice_items WHERE invoice_id = %s), 0)
            WHERE id = %s
        """, (invoice['id'], invoice['id'], invoice['id']))
        
        flash('Item removido com sucesso!', 'success')
    else:
        flash('Erro ao remover item.', 'danger')
    
    return redirect(url_for('invoice.invoice_edit', invoice_id=invoice['id']))

@invoice_bp.route('/notas-fiscais/processar/<int:invoice_id>', methods=['POST'])
@login_required
def invoice_process(invoice_id):
    """Processa uma nota fiscal."""
    db = get_db()
    
    # Verificar se a nota fiscal existe
    invoice = db.fetch_one("""
        SELECT * FROM invoices
        WHERE id = %s AND active = TRUE
    """, (invoice_id,))
    
    if not invoice:
        flash('Nota fiscal não encontrada.', 'danger')
        return redirect(url_for('invoice.invoice_list'))
    
    # Verificar se a nota fiscal pode ser processada
    if invoice['status'] != 'verified':
        flash('Apenas notas fiscais verificadas podem ser processadas.', 'danger')
        return redirect(url_for('invoice.invoice_view', invoice_id=invoice_id))
    
    # Processar a nota fiscal
    affected_rows = db.update("""
        UPDATE invoices
        SET status = 'processed', processed_date = CURDATE()
        WHERE id = %s
    """, (invoice_id,))
    
    if affected_rows > 0:
        # Atualizar o status dos itens
        db.update("""
            UPDATE invoice_items
            SET status = 'processed'
            WHERE invoice_id = %s
        """, (invoice_id,))
        
        # Atualizar o estoque
        items = db.fetch_all("""
            SELECT ii.*, p.name as product_name
            FROM invoice_items ii
            JOIN products p ON ii.product_id = p.id
            WHERE ii.invoice_id = %s
        """, (invoice_id,))
        
        for item in items:
            product_id = item['product_id']
            quantity = item['quantity']
            
            # Usar Kardex para registrar movimentação
            if registrar_movimentacao:
                resultado = registrar_movimentacao(
                    produto_id=product_id,
                    tipo='entrada',
                    quantidade=quantity,
                    origem_tela='Recebimento NF',
                    referencia_tipo='invoice',
                    referencia_id=invoice_id,
                    referencia_codigo=f'NF-{invoice_id}',
                    observacao=f'Recebimento da NF #{invoice_id}',
                    custo_unitario=item.get('unit_price')
                )
                if resultado.get('success'):
                    print(f"[NF] [KARDEX] Produto {product_id}: {resultado.get('estoque_anterior')} -> {resultado.get('estoque_posterior')}")
            else:
                # Fallback: atualização direta
                db.update("""
                    UPDATE products
                    SET stock_quantity = COALESCE(stock_quantity, 0) + %s
                    WHERE id = %s
                """, (quantity, product_id))
                
                stock = db.fetch_one("""
                    SELECT * FROM current_stock
                    WHERE product_id = %s AND location_id = 1
                """, (product_id,))
                
                if stock:
                    db.update("""
                        UPDATE current_stock
                        SET quantity = quantity + %s, last_purchase_date = CURDATE()
                        WHERE product_id = %s AND location_id = 1
                    """, (quantity, product_id))
                else:
                    db.insert("""
                        INSERT INTO current_stock (
                            product_id, location_id, quantity, min_stock, max_stock, last_purchase_date
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (product_id, 1, quantity, 0, 0, datetime.datetime.now().date()))
                
                db.insert("""
                    INSERT INTO stock_movements (
                        product_id, movement_type, quantity, reference_id, reference_type,
                        unit_cost, location_id, notes, created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                product_id, 'purchase', quantity, invoice_id, 'invoice',
                item['unit_price'], 1, f"Recebimento da NF {invoice['invoice_number']}", session.get('user_id', 1)  # Usar ID 1 como padrão se não houver user_id na sessão
            ))
        
        # Se a nota fiscal estiver associada a um pedido de compra, atualizar o status do pedido
        if invoice['purchase_order_id']:
            # Verificar se todos os itens do pedido foram recebidos
            purchase_order_id = invoice['purchase_order_id']
            
            # Buscar itens do pedido de compra
            po_items = db.fetch_all("""
                SELECT * FROM purchase_order_items
                WHERE purchase_order_id = %s
            """, (purchase_order_id,))
            
            # Verificar se todos os itens foram recebidos
            all_received = all(item['status'] == 'received' for item in po_items)
            any_received = any(item['status'] in ['received', 'partially_received'] for item in po_items)
            
            # Atualizar o status do pedido
            if all_received:
                db.update("""
                    UPDATE purchase_orders
                    SET status = 'received', received_date = CURDATE()
                    WHERE id = %s
                """, (purchase_order_id,))
            elif any_received:
                db.update("""
                    UPDATE purchase_orders
                    SET status = 'partially_received'
                    WHERE id = %s
                """, (purchase_order_id,))
        
        flash('Nota fiscal processada com sucesso!', 'success')
    else:
        flash('Erro ao processar nota fiscal.', 'danger')
    
    return redirect(url_for('invoice.invoice_view', invoice_id=invoice_id))

@invoice_bp.route('/notas-fiscais/importar-xml', methods=['GET', 'POST'])
@login_required
def invoice_import_xml():
    """Importa uma nota fiscal a partir de um arquivo XML."""
    db = get_db()
    
    if request.method == 'POST':
        # Verificar se o arquivo foi enviado
        if 'xml_file' not in request.files:
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(url_for('invoice.invoice_import_xml'))
        
        xml_file = request.files['xml_file']
        
        # Verificar se o arquivo é válido
        if xml_file.filename == '':
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(url_for('invoice.invoice_import_xml'))
        
        if not xml_file.filename.endswith('.xml'):
            flash('O arquivo deve ser um XML.', 'danger')
            return redirect(url_for('invoice.invoice_import_xml'))
        
        # Salvar o arquivo temporariamente
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_filename = f"{uuid.uuid4()}.xml"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        xml_file.save(temp_path)
        
        try:
            # Processar o arquivo XML
            tree = ET.parse(temp_path)
            root = tree.getroot()
            
            # Extrair dados da nota fiscal
            # Nota: Este é um exemplo simplificado. O formato real do XML da NF-e pode variar.
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
            
            # Extrair dados do emitente (fornecedor)
            emit = root.find('.//nfe:emit', ns)
            cnpj = emit.find('nfe:CNPJ', ns).text
            supplier_name = emit.find('nfe:xNome', ns).text
            
            # Buscar o fornecedor pelo CNPJ
            supplier = db.fetch_one("""
                SELECT id FROM suppliers
                WHERE document_number = %s
            """, (cnpj,))
            
            if not supplier:
                # Criar um novo fornecedor se não existir
                supplier_id = db.insert("""
                    INSERT INTO suppliers (name, document_number, active)
                    VALUES (%s, %s, TRUE)
                """, (supplier_name, cnpj))
            else:
                supplier_id = supplier['id']
            
            # Extrair dados da nota fiscal
            ide = root.find('.//nfe:ide', ns)
            invoice_number = ide.find('nfe:nNF', ns).text
            invoice_series = ide.find('nfe:serie', ns).text
            issue_date_str = ide.find('nfe:dhEmi', ns).text
            issue_date = datetime.datetime.strptime(issue_date_str.split('T')[0], '%Y-%m-%d').date()
            
            # Extrair valores totais
            total = root.find('.//nfe:total/nfe:ICMSTot', ns)
            total_amount = float(total.find('nfe:vNF', ns).text)
            tax_amount = float(total.find('nfe:vTotTrib', ns).text) if total.find('nfe:vTotTrib', ns) is not None else 0
            
            # Inserir a nota fiscal no banco de dados
            invoice_id = db.insert("""
                INSERT INTO invoices (
                    supplier_id, invoice_number, invoice_series, issue_date,
                    total_amount, tax_amount, status, created_by, xml_path
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                supplier_id, invoice_number, invoice_series, issue_date,
                total_amount, tax_amount, 'pending', session.get('user_id', 1), temp_filename  # Usar ID 1 como padrão se não houver user_id na sessão
            ))
            
            if invoice_id:
                # Extrair itens da nota fiscal
                items = root.findall('.//nfe:det', ns)
                
                for item in items:
                    prod = item.find('nfe:prod', ns)
                    product_code = prod.find('nfe:cProd', ns).text
                    product_name = prod.find('nfe:xProd', ns).text
                    quantity = float(prod.find('nfe:qCom', ns).text)
                    unit_price = float(prod.find('nfe:vUnCom', ns).text)
                    total_price = float(prod.find('nfe:vProd', ns).text)
                    
                    # Buscar o produto pelo código
                    product = db.fetch_one("""
                        SELECT id FROM products
                        WHERE code = %s OR sku = %s
                    """, (product_code, product_code))
                    
                    if not product:
                        # Criar um novo produto se não existir
                        product_id = db.insert("""
                            INSERT INTO products (name, code, unit, purchase_price, active)
                            VALUES (%s, %s, %s, %s, TRUE)
                        """, (product_name, product_code, 'UN', unit_price))
                    else:
                        product_id = product['id']
                    
                    # Calcular imposto do item
                    imposto = item.find('nfe:imposto', ns)
                    tax_percentage = 0
                    tax_amount = 0
                    
                    if imposto.find('nfe:ICMS', ns) is not None:
                        icms = imposto.find('nfe:ICMS', ns)
                        icms_item = icms.find('*')
                        if icms_item is not None and icms_item.find('nfe:pICMS', ns) is not None:
                            tax_percentage = float(icms_item.find('nfe:pICMS', ns).text)
                            tax_amount = float(icms_item.find('nfe:vICMS', ns).text)
                    
                    # Inserir o item no banco de dados
                    db.insert("""
                        INSERT INTO invoice_items (
                            invoice_id, product_id, quantity, unit_price,
                            total_price, tax_percentage, tax_amount, status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        invoice_id, product_id, quantity, unit_price,
                        total_price, tax_percentage, tax_amount, 'active'
                    ))
                
                flash('Nota fiscal importada com sucesso!', 'success')
                return redirect(url_for('invoice.invoice_view', invoice_id=invoice_id))
            else:
                flash('Erro ao importar nota fiscal.', 'danger')
        
        except Exception as e:
            flash(f'Erro ao processar o arquivo XML: {str(e)}', 'danger')
        finally:
            # Remover o arquivo temporário se ocorrer um erro
            if os.path.exists(temp_path) and not invoice_id:
                os.remove(temp_path)
    
    return render_template(
        'invoice_import.html',
        active_page='invoices'
    )

@invoice_bp.route('/api/pedido-compra/<int:purchase_order_id>/itens')
@login_required
def api_purchase_order_items(purchase_order_id):
    """API para buscar itens de um pedido de compra."""
    db = get_db()
    
    # Buscar itens do pedido de compra
    items = db.fetch_all("""
        SELECT poi.*, p.name as product_name, p.unit as product_unit
        FROM purchase_order_items poi
        JOIN products p ON poi.product_id = p.id
        WHERE poi.purchase_order_id = %s
        ORDER BY poi.id
    """, (purchase_order_id,))
    
    return jsonify(items)
