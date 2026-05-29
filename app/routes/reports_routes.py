"""
Rotas para o módulo de Relatórios.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import datetime
import calendar
import json
from dateutil.relativedelta import relativedelta

from database import get_db
from utils.auth import login_required

# Criar o blueprint
reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/relatorios')
@login_required
def reports_dashboard():
    """Dashboard principal de relatórios."""
    return render_template(
        'reports_dashboard.html',
        active_page='reports'
    )

@reports_bp.route('/relatorios/financeiro')
@login_required
def financial_reports():
    """Relatórios financeiros."""
    db = get_db()
    
    # Obter parâmetros
    report_type = request.args.get('type', 'revenue')
    period = request.args.get('period', 'monthly')
    year = int(request.args.get('year', datetime.datetime.now().year))
    month = int(request.args.get('month', datetime.datetime.now().month))
    
    # Definir datas
    if period == 'monthly':
        start_date = datetime.date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime.date(year, month, last_day)
        title = f"Relatório Financeiro - {start_date.strftime('%B/%Y')}"
    elif period == 'quarterly':
        quarter = ((month - 1) // 3) + 1
        start_month = (quarter - 1) * 3 + 1
        start_date = datetime.date(year, start_month, 1)
        end_month = start_month + 2
        last_day = calendar.monthrange(year, end_month)[1]
        end_date = datetime.date(year, end_month, last_day)
        title = f"Relatório Financeiro - {quarter}º Trimestre/{year}"
    elif period == 'yearly':
        start_date = datetime.date(year, 1, 1)
        end_date = datetime.date(year, 12, 31)
        title = f"Relatório Financeiro - {year}"
    else:  # custom
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            title = f"Relatório Financeiro - {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        else:
            start_date = datetime.date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = datetime.date(year, month, last_day)
            title = f"Relatório Financeiro - {start_date.strftime('%B/%Y')}"
    
    # Dados para o relatório
    report_data = {}
    
    # Relatório de Receitas
    if report_type == 'revenue':
        # Contas a receber recebidas no período
        receivables = db.fetch_all("""
            SELECT ar.*, c.name as customer_name
            FROM accounts_receivable ar
            JOIN customers c ON ar.customer_id = c.id
            WHERE ar.payment_date BETWEEN %s AND %s
            AND ar.status = 'paid'
            AND ar.active = TRUE
            ORDER BY ar.payment_date
        """, (start_date, end_date))
        
        # Calcular totais
        total_amount = sum(item['total_amount'] for item in receivables)
        
        # Agrupar por cliente
        customer_data = {}
        for item in receivables:
            customer = item['customer_name']
            if customer in customer_data:
                customer_data[customer] += item['total_amount']
            else:
                customer_data[customer] = item['total_amount']
        
        # Agrupar por data
        date_data = {}
        for item in receivables:
            date_str = item['payment_date'].strftime('%Y-%m-%d')
            if date_str in date_data:
                date_data[date_str] += item['total_amount']
            else:
                date_data[date_str] = item['total_amount']
        
        report_data = {
            'items': receivables,
            'total': total_amount,
            'customer_data': customer_data,
            'date_data': date_data
        }
    
    # Relatório de Despesas
    elif report_type == 'expenses':
        # Contas a pagar pagas no período
        payables = db.fetch_all("""
            SELECT ap.*, s.name as supplier_name
            FROM accounts_payable ap
            JOIN suppliers s ON ap.supplier_id = s.id
            WHERE ap.payment_date BETWEEN %s AND %s
            AND ap.status = 'paid'
            AND ap.active = TRUE
            ORDER BY ap.payment_date
        """, (start_date, end_date))
        
        # Calcular totais
        total_amount = sum(item['total_amount'] for item in payables)
        
        # Agrupar por fornecedor
        supplier_data = {}
        for item in payables:
            supplier = item['supplier_name']
            if supplier in supplier_data:
                supplier_data[supplier] += item['total_amount']
            else:
                supplier_data[supplier] = item['total_amount']
        
        # Agrupar por data
        date_data = {}
        for item in payables:
            date_str = item['payment_date'].strftime('%Y-%m-%d')
            if date_str in date_data:
                date_data[date_str] += item['total_amount']
            else:
                date_data[date_str] = item['total_amount']
        
        report_data = {
            'items': payables,
            'total': total_amount,
            'supplier_data': supplier_data,
            'date_data': date_data
        }
    
    # Relatório de Fluxo de Caixa
    elif report_type == 'cash_flow':
        # Entradas no período
        income = db.fetch_all("""
            SELECT cf.*, ba.name as bank_account_name
            FROM cash_flow cf
            JOIN bank_accounts ba ON cf.bank_account_id = ba.id
            WHERE cf.date BETWEEN %s AND %s
            AND cf.type = 'income'
            ORDER BY cf.date
        """, (start_date, end_date))
        
        # Saídas no período
        expenses = db.fetch_all("""
            SELECT cf.*, ba.name as bank_account_name
            FROM cash_flow cf
            JOIN bank_accounts ba ON cf.bank_account_id = ba.id
            WHERE cf.date BETWEEN %s AND %s
            AND cf.type = 'expense'
            ORDER BY cf.date
        """, (start_date, end_date))
        
        # Calcular totais
        total_income = sum(item['amount'] for item in income)
        total_expenses = sum(item['amount'] for item in expenses)
        balance = total_income - total_expenses
        
        # Agrupar por data
        date_data = {}
        for item in income:
            date_str = item['date'].strftime('%Y-%m-%d')
            if date_str not in date_data:
                date_data[date_str] = {'income': 0, 'expense': 0, 'balance': 0}
            date_data[date_str]['income'] += item['amount']
        
        for item in expenses:
            date_str = item['date'].strftime('%Y-%m-%d')
            if date_str not in date_data:
                date_data[date_str] = {'income': 0, 'expense': 0, 'balance': 0}
            date_data[date_str]['expense'] += item['amount']
        
        # Calcular saldo acumulado
        running_balance = 0
        for date_str in sorted(date_data.keys()):
            running_balance += date_data[date_str]['income'] - date_data[date_str]['expense']
            date_data[date_str]['balance'] = running_balance
        
        report_data = {
            'income': income,
            'expenses': expenses,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'balance': balance,
            'date_data': date_data
        }
    
    return render_template(
        'financial_report.html',
        report_type=report_type,
        period=period,
        year=year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        title=title,
        report_data=report_data,
        active_page='financial_reports'
    )

@reports_bp.route('/relatorios/compras')
@login_required
def purchase_reports():
    """Relatórios de compras."""
    db = get_db()
    
    # Obter parâmetros
    report_type = request.args.get('type', 'orders')
    period = request.args.get('period', 'monthly')
    year = int(request.args.get('year', datetime.datetime.now().year))
    month = int(request.args.get('month', datetime.datetime.now().month))
    supplier_id = request.args.get('supplier_id')
    
    # Definir datas
    if period == 'monthly':
        start_date = datetime.date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime.date(year, month, last_day)
        title = f"Relatório de Compras - {start_date.strftime('%B/%Y')}"
    elif period == 'quarterly':
        quarter = ((month - 1) // 3) + 1
        start_month = (quarter - 1) * 3 + 1
        start_date = datetime.date(year, start_month, 1)
        end_month = start_month + 2
        last_day = calendar.monthrange(year, end_month)[1]
        end_date = datetime.date(year, end_month, last_day)
        title = f"Relatório de Compras - {quarter}º Trimestre/{year}"
    elif period == 'yearly':
        start_date = datetime.date(year, 1, 1)
        end_date = datetime.date(year, 12, 31)
        title = f"Relatório de Compras - {year}"
    else:  # custom
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            title = f"Relatório de Compras - {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        else:
            start_date = datetime.date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = datetime.date(year, month, last_day)
            title = f"Relatório de Compras - {start_date.strftime('%B/%Y')}"
    
    # Construir a consulta base
    query_params = [start_date, end_date]
    
    # Adicionar filtro de fornecedor
    supplier_filter = ""
    if supplier_id:
        supplier_filter = " AND po.supplier_id = %s"
        query_params.append(supplier_id)
    
    # Dados para o relatório
    report_data = {}
    
    # Relatório de Pedidos de Compra
    if report_type == 'orders':
        # Pedidos de compra no período
        orders = db.fetch_all(f"""
            SELECT po.*, s.name as supplier_name
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            WHERE po.order_date BETWEEN %s AND %s
            AND po.active = TRUE
            {supplier_filter}
            ORDER BY po.order_date
        """, tuple(query_params))
        
        # Calcular totais
        total_amount = sum(item['total_amount'] for item in orders if item['total_amount'])
        
        # Agrupar por fornecedor
        supplier_data = {}
        for item in orders:
            supplier = item['supplier_name']
            if supplier in supplier_data:
                supplier_data[supplier] += item['total_amount'] or 0
            else:
                supplier_data[supplier] = item['total_amount'] or 0
        
        # Agrupar por status
        status_data = {
            'draft': 0,
            'sent': 0,
            'confirmed': 0,
            'partially_received': 0,
            'received': 0,
            'canceled': 0
        }
        
        for item in orders:
            status = item['status']
            if status in status_data:
                status_data[status] += 1
        
        report_data = {
            'items': orders,
            'total': total_amount,
            'supplier_data': supplier_data,
            'status_data': status_data
        }
    
    # Relatório de Notas Fiscais
    elif report_type == 'invoices':
        # Notas fiscais no período
        invoices = db.fetch_all(f"""
            SELECT i.*, s.name as supplier_name
            FROM invoices i
            JOIN suppliers s ON i.supplier_id = s.id
            WHERE i.issue_date BETWEEN %s AND %s
            AND i.active = TRUE
            {supplier_filter}
            ORDER BY i.issue_date
        """, tuple(query_params))
        
        # Calcular totais
        total_amount = sum(item['total_amount'] for item in invoices)
        total_tax = sum(item['tax_amount'] for item in invoices)
        
        # Agrupar por fornecedor
        supplier_data = {}
        for item in invoices:
            supplier = item['supplier_name']
            if supplier in supplier_data:
                supplier_data[supplier] += item['total_amount']
            else:
                supplier_data[supplier] = item['total_amount']
        
        # Agrupar por status
        status_data = {
            'pending': 0,
            'verified': 0,
            'processed': 0,
            'canceled': 0
        }
        
        for item in invoices:
            status = item['status']
            if status in status_data:
                status_data[status] += 1
        
        report_data = {
            'items': invoices,
            'total': total_amount,
            'total_tax': total_tax,
            'supplier_data': supplier_data,
            'status_data': status_data
        }
    
    # Buscar fornecedores para o filtro
    suppliers = db.fetch_all("""
        SELECT id, name FROM suppliers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'purchase_report.html',
        report_type=report_type,
        period=period,
        year=year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        title=title,
        report_data=report_data,
        suppliers=suppliers,
        supplier_id=supplier_id,
        active_page='purchase_reports'
    )

@reports_bp.route('/relatorios/estoque')
@login_required
def inventory_reports():
    """Relatórios de estoque."""
    db = get_db()
    
    # Obter parâmetros
    report_type = request.args.get('type', 'current')
    location_id = request.args.get('location_id')
    category_id = request.args.get('category_id')
    
    # Título do relatório
    if report_type == 'current':
        title = "Posição Atual de Estoque"
    elif report_type == 'movements':
        title = "Movimentações de Estoque"
    elif report_type == 'low_stock':
        title = "Produtos Abaixo do Estoque Mínimo"
    else:
        title = "Relatório de Estoque"
    
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
        
        # Ordenação
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
            SELECT sm.*, p.name as product_name, p.code, p.unit, u.name as created_by_name,
                   l.name as location_name
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            JOIN users u ON sm.created_by = u.id
            JOIN stock_locations l ON sm.location_id = l.id
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
        
        # Ordenação
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
        
        # Ordenação
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
        title=title,
        active_page='inventory_reports'
    )

@reports_bp.route('/relatorios/consolidado')
@login_required
def consolidated_report():
    """Relatório consolidado."""
    db = get_db()
    
    # Obter parâmetros
    period = request.args.get('period', 'monthly')
    year = int(request.args.get('year', datetime.datetime.now().year))
    month = int(request.args.get('month', datetime.datetime.now().month))
    
    # Definir datas
    if period == 'monthly':
        start_date = datetime.date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime.date(year, month, last_day)
        title = f"Relatório Consolidado - {start_date.strftime('%B/%Y')}"
    elif period == 'quarterly':
        quarter = ((month - 1) // 3) + 1
        start_month = (quarter - 1) * 3 + 1
        start_date = datetime.date(year, start_month, 1)
        end_month = start_month + 2
        last_day = calendar.monthrange(year, end_month)[1]
        end_date = datetime.date(year, end_month, last_day)
        title = f"Relatório Consolidado - {quarter}º Trimestre/{year}"
    elif period == 'yearly':
        start_date = datetime.date(year, 1, 1)
        end_date = datetime.date(year, 12, 31)
        title = f"Relatório Consolidado - {year}"
    else:  # custom
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            title = f"Relatório Consolidado - {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        else:
            start_date = datetime.date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = datetime.date(year, month, last_day)
            title = f"Relatório Consolidado - {start_date.strftime('%B/%Y')}"
    
    # Dados para o relatório
    report_data = {}
    
    # Resumo financeiro
    # Entradas no período
    income = db.fetch_all("""
        SELECT SUM(amount) as total
        FROM cash_flow
        WHERE date BETWEEN %s AND %s
        AND type = 'income'
    """, (start_date, end_date))
    
    # Saídas no período
    expenses = db.fetch_all("""
        SELECT SUM(amount) as total
        FROM cash_flow
        WHERE date BETWEEN %s AND %s
        AND type = 'expense'
    """, (start_date, end_date))
    
    # Contas a receber no período
    receivables = db.fetch_all("""
        SELECT SUM(total_amount) as total
        FROM accounts_receivable
        WHERE due_date BETWEEN %s AND %s
        AND status = 'pending'
        AND active = TRUE
    """, (start_date, end_date))
    
    # Contas a pagar no período
    payables = db.fetch_all("""
        SELECT SUM(total_amount) as total
        FROM accounts_payable
        WHERE due_date BETWEEN %s AND %s
        AND status = 'pending'
        AND active = TRUE
    """, (start_date, end_date))
    
    # Resumo de compras
    # Pedidos de compra no período
    purchase_orders = db.fetch_all("""
        SELECT COUNT(*) as count, SUM(total_value) as total
        FROM purchase_orders
        WHERE order_date BETWEEN %s AND %s
        AND active = TRUE
    """, (start_date, end_date))
    
    # Notas fiscais no período
    invoices = db.fetch_all("""
        SELECT COUNT(*) as count, SUM(total_amount) as total
        FROM invoices
        WHERE issue_date BETWEEN %s AND %s
        AND active = TRUE
    """, (start_date, end_date))
    
    # Resumo de estoque (usa products.stock_quantity como fonte única)
    # Valor total em estoque
    stock_value = db.fetch_all("""
        SELECT SUM(COALESCE(p.stock_quantity, 0) * p.price) as total
        FROM products p
        WHERE p.active = TRUE
    """)
    
    # Produtos abaixo do estoque mínimo
    low_stock = db.fetch_all("""
        SELECT COUNT(*) as count
        FROM products p
        LEFT JOIN current_stock cs ON cs.product_id = p.id
        WHERE p.active = TRUE
        AND COALESCE(p.stock_quantity, 0) < COALESCE(cs.min_stock, 0)
        AND COALESCE(cs.min_stock, 0) > 0
    """)
    
    # Movimentações de estoque no período
    stock_movements = db.fetch_all("""
        SELECT COUNT(*) as count
        FROM stock_movements
        WHERE DATE(created_at) BETWEEN %s AND %s
    """, (start_date, end_date))
    
    # Montar dados do relatório
    report_data = {
        'financial': {
            'income': income[0]['total'] if income[0]['total'] else 0,
            'expenses': expenses[0]['total'] if expenses[0]['total'] else 0,
            'balance': (income[0]['total'] if income[0]['total'] else 0) - (expenses[0]['total'] if expenses[0]['total'] else 0),
            'receivables': receivables[0]['total'] if receivables[0]['total'] else 0,
            'payables': payables[0]['total'] if payables[0]['total'] else 0
        },
        'purchases': {
            'orders_count': purchase_orders[0]['count'] if purchase_orders[0]['count'] else 0,
            'orders_total': purchase_orders[0]['total'] if purchase_orders[0]['total'] else 0,
            'invoices_count': invoices[0]['count'] if invoices[0]['count'] else 0,
            'invoices_total': invoices[0]['total'] if invoices[0]['total'] else 0
        },
        'inventory': {
            'stock_value': stock_value[0]['total'] if stock_value[0]['total'] else 0,
            'low_stock_count': low_stock[0]['count'] if low_stock[0]['count'] else 0,
            'movements_count': stock_movements[0]['count'] if stock_movements[0]['count'] else 0
        }
    }
    
    return render_template(
        'consolidated_report.html',
        report_data=report_data,
        period=period,
        year=year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        title=title,
        active_page='consolidated_report'
    )


# ─────────────────────────────────────────────────────────────
# Desempenho por Mecânico
# ─────────────────────────────────────────────────────────────
@reports_bp.route('/relatorios/mecanicos')
@login_required
def relatorio_mecanicos():
    """Relatório de desempenho por mecânico com filtro de período."""
    db = get_db()

    mes_ref = request.args.get('mes_ref', datetime.datetime.now().strftime('%Y-%m'))
    try:
        ano, mes = int(mes_ref[:4]), int(mes_ref[5:7])
    except Exception:
        ano, mes = datetime.datetime.now().year, datetime.datetime.now().month

    ultimo_dia = calendar.monthrange(ano, mes)[1]
    data_ini = f"{ano}-{mes:02d}-01"
    data_fim = f"{ano}-{mes:02d}-{ultimo_dia}"

    mecanicos = db.fetch_all("""
        SELECT
            t.id,
            t.name                                                          AS nome,
            t.specialty                                                     AS especialidade,
            COUNT(so.id)                                                    AS total_os,
            SUM(so.status = 'completed')                                    AS os_concluidas,
            SUM(so.status = 'canceled')                                     AS os_canceladas,
            COALESCE(SUM(CASE WHEN so.status='completed' THEN so.total_geral END), 0) AS receita,
            NULL                                                            AS media_horas,
            ROUND(COALESCE(SUM(CASE WHEN so.status='completed' THEN so.total_geral END), 0)
                  / NULLIF(SUM(so.status='completed'), 0), 2)              AS ticket_medio
        FROM technicians t
        LEFT JOIN service_orders so
               ON so.technician_id = t.id
              AND so.open_date BETWEEN %s AND %s
              AND so.active = TRUE
        WHERE t.active = TRUE
        GROUP BY t.id, t.name, t.specialty
        ORDER BY receita DESC
    """, (data_ini, data_fim)) or []

    # KPIs gerais do período
    kpis = db.fetch_one("""
        SELECT
            COUNT(*)                                                          AS total_os,
            SUM(status='completed')                                           AS concluidas,
            COALESCE(SUM(CASE WHEN status='completed' THEN total_geral END), 0) AS receita_total,
            COUNT(DISTINCT technician_id)                                     AS tecnicos_ativos
        FROM service_orders
        WHERE open_date BETWEEN %s AND %s AND active = TRUE
    """, (data_ini, data_fim)) or {}

    return render_template('relatorio_mecanicos.html',
        mecanicos=mecanicos, kpis=kpis,
        mes_ref=mes_ref, data_ini=data_ini, data_fim=data_fim)


# ─────────────────────────────────────────────────────────────
# Ranking de Serviços Mais Executados
# ─────────────────────────────────────────────────────────────
@reports_bp.route('/relatorios/servicos')
@login_required
def relatorio_servicos():
    """Ranking dos serviços mais executados com filtro de período."""
    db = get_db()

    mes_ref = request.args.get('mes_ref', datetime.datetime.now().strftime('%Y-%m'))
    try:
        ano, mes = int(mes_ref[:4]), int(mes_ref[5:7])
    except Exception:
        ano, mes = datetime.datetime.now().year, datetime.datetime.now().month

    ultimo_dia = calendar.monthrange(ano, mes)[1]
    data_ini = f"{ano}-{mes:02d}-01"
    data_fim = f"{ano}-{mes:02d}-{ultimo_dia}"

    # Ranking por tipo de OS (corretiva / preventiva / preditiva)
    por_tipo = db.fetch_all("""
        SELECT
            COALESCE(type, 'corrective')           AS tipo,
            COUNT(*)                               AS total,
            SUM(status='completed')                AS concluidas,
            COALESCE(SUM(CASE WHEN status='completed' THEN total_geral END), 0) AS receita
        FROM service_orders
        WHERE open_date BETWEEN %s AND %s AND active = TRUE
        GROUP BY tipo
        ORDER BY total DESC
    """, (data_ini, data_fim)) or []

    # Itens / peças mais usados nas OS (top 20)
    top_pecas = db.fetch_all("""
        SELECT
            COALESCE(soi.descricao, 'Item sem nome')            AS descricao,
            SUM(COALESCE(soi.quantidade, soi.quantity, 0))      AS qtd_total,
            COUNT(DISTINCT soi.service_order_id)                AS em_os,
            ROUND(AVG(COALESCE(soi.valor_unitario, soi.unit_cost, 0)), 2) AS preco_medio,
            SUM(COALESCE(soi.valor_total, 0))                   AS receita_total
        FROM service_order_items soi
        JOIN service_orders so ON so.id = soi.service_order_id
        WHERE so.open_date BETWEEN %s AND %s
          AND so.active = TRUE AND so.status = 'completed'
        GROUP BY soi.descricao
        ORDER BY qtd_total DESC
        LIMIT 20
    """, (data_ini, data_fim)) or []

    # Clientes que mais geraram receita
    top_clientes = db.fetch_all("""
        SELECT
            c.name                                                        AS cliente,
            COUNT(so.id)                                                  AS total_os,
            COALESCE(SUM(so.total_geral), 0)                              AS receita,
            ROUND(AVG(so.total_geral), 2)                                 AS ticket_medio
        FROM service_orders so
        JOIN customers c ON c.id = so.customer_id
        WHERE so.open_date BETWEEN %s AND %s
          AND so.active = TRUE AND so.status = 'completed'
        GROUP BY c.id, c.name
        ORDER BY receita DESC
        LIMIT 10
    """, (data_ini, data_fim)) or []

    return render_template('relatorio_servicos.html',
        por_tipo=por_tipo, top_pecas=top_pecas, top_clientes=top_clientes,
        mes_ref=mes_ref, data_ini=data_ini, data_fim=data_fim)
