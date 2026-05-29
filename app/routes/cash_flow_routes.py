"""
Rotas para gerenciamento de fluxo de caixa.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import datetime
import calendar
from dateutil.relativedelta import relativedelta

from database import get_db
from utils.auth import login_required

# Criar o blueprint
cash_flow_bp = Blueprint('cash_flow', __name__)


@cash_flow_bp.route('/fluxo-caixa')
@login_required
def cash_flow_dashboard():
    """Dashboard principal do fluxo de caixa."""
    db = get_db()
    
    # Obter parâmetros de filtro
    period = request.args.get('period', 'month')
    date_str = request.args.get('date')
    bank_account_id = request.args.get('bank_account_id')
    company_id = request.args.get('company_id')
    
    # Definir datas de início e fim com base no período
    today = datetime.datetime.now().date()
    
    if date_str:
        try:
            # Se uma data específica foi fornecida, usá-la como base
            base_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            base_date = today
    else:
        base_date = today
    
    if period == 'day':
        start_date = base_date
        end_date = base_date
        title = f"Fluxo de Caixa - {start_date.strftime('%d/%m/%Y')}"
        prev_date = (base_date - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        next_date = (base_date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    elif period == 'week':
        # Início da semana (segunda-feira)
        start_date = base_date - datetime.timedelta(days=base_date.weekday())
        # Fim da semana (domingo)
        end_date = start_date + datetime.timedelta(days=6)
        title = f"Fluxo de Caixa - Semana {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        prev_date = (start_date - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        next_date = (start_date + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    else:  # month
        # Início do mês
        start_date = base_date.replace(day=1)
        # Fim do mês
        last_day = calendar.monthrange(base_date.year, base_date.month)[1]
        end_date = base_date.replace(day=last_day)
        title = f"Fluxo de Caixa - {start_date.strftime('%B/%Y')}"
        prev_date = (start_date - relativedelta(months=1)).strftime('%Y-%m-%d')
        next_date = (start_date + relativedelta(months=1)).strftime('%Y-%m-%d')
    
    # Construir a consulta base para o fluxo de caixa
    query = """
        SELECT 
            cf.*, 
            ba.name AS bank_account_name,
            e.nome_fantasia AS company_name
        FROM cash_flow cf
        JOIN bank_accounts ba ON cf.bank_account_id = ba.id
        LEFT JOIN empresas e ON cf.company_id = e.id
        WHERE cf.date BETWEEN %s AND %s
    """
    params = [start_date, end_date]
    
    # Adicionar filtro de conta bancária, se fornecido
    if bank_account_id:
        query += " AND cf.bank_account_id = %s"
        params.append(bank_account_id)

    # Adicionar filtro de empresa, se fornecido
    if company_id:
        query += " AND cf.company_id = %s"
        params.append(company_id)
    
    # Ordenação
    query += " ORDER BY cf.date, cf.id"
    
    # Executar a consulta
    cash_flow_items = db.fetch_all(query, tuple(params))
    
    # Calcular saldos
    income_total = sum(item['amount'] for item in cash_flow_items if item['type'] == 'income')
    expense_total = sum(item['amount'] for item in cash_flow_items if item['type'] == 'expense')
    balance = income_total - expense_total
    
    # Buscar contas bancárias para o filtro
    bank_accounts = db.fetch_all("""
        SELECT id, name FROM bank_accounts
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    # Preparar dados para o gráfico diário
    daily_data = {}
    for item in cash_flow_items:
        date_str = item['date'].strftime('%Y-%m-%d')
        if date_str not in daily_data:
            daily_data[date_str] = {'income': 0, 'expense': 0, 'balance': 0}
        
        if item['type'] == 'income':
            daily_data[date_str]['income'] += item['amount']
        else:
            daily_data[date_str]['expense'] += item['amount']
    
    # Calcular saldo acumulado
    running_balance = 0
    for date_str in sorted(daily_data.keys()):
        running_balance += daily_data[date_str]['income'] - daily_data[date_str]['expense']
        daily_data[date_str]['balance'] = running_balance
    
    # Buscar contas a pagar vencendo no período
    query_payables = """
        SELECT ap.*, s.name AS supplier_name
        FROM accounts_payable ap
        JOIN suppliers s ON ap.supplier_id = s.id
        WHERE ap.due_date BETWEEN %s AND %s
        AND ap.status IN ('pending', 'overdue')
        AND ap.active = TRUE
    """
    params_payables = [start_date, end_date]

    if company_id:
        query_payables += " AND ap.company_id = %s"
        params_payables.append(company_id)

    query_payables += " ORDER BY ap.due_date"

    payables = db.fetch_all(query_payables, tuple(params_payables))
    
    # Buscar contas a receber vencendo no período
    query_receivables = """
        SELECT ar.*, c.name AS customer_name
        FROM accounts_receivable ar
        JOIN customers c ON ar.customer_id = c.id
        WHERE ar.due_date BETWEEN %s AND %s
        AND ar.status IN ('pending', 'overdue')
        AND ar.active = TRUE
    """
    params_receivables = [start_date, end_date]

    if company_id:
        query_receivables += " AND ar.company_id = %s"
        params_receivables.append(company_id)

    query_receivables += " ORDER BY ar.due_date"

    receivables = db.fetch_all(query_receivables, tuple(params_receivables))

    # Buscar empresas para filtro por empresa
    companies = db.fetch_all("""
        SELECT id, nome_fantasia
        FROM empresas
        WHERE ativo = TRUE
        ORDER BY nome_fantasia
    """)
    
    return render_template(
        'cash_flow_dashboard.html',
        cash_flow_items=cash_flow_items,
        bank_accounts=bank_accounts,
        income_total=income_total,
        expense_total=expense_total,
        balance=balance,
        period=period,
        date=base_date.strftime('%Y-%m-%d'),
        title=title,
        prev_date=prev_date,
        next_date=next_date,
        daily_data=daily_data,
        payables=payables,
        receivables=receivables,
        bank_account_id=bank_account_id,
        companies=companies,
        company_id=company_id,
        active_page='cash_flow'
    )

@cash_flow_bp.route('/fluxo-caixa/projecao')
@login_required
def cash_flow_projection():
    """Projeção de fluxo de caixa."""
    db = get_db()
    
    # Obter parâmetros
    months = int(request.args.get('months', '3'))
    bank_account_id = request.args.get('bank_account_id')
    company_id = request.args.get('company_id')
    
    # Definir datas
    today = datetime.datetime.now().date()
    end_date = today + relativedelta(months=months)
    
    # Buscar contas a pagar futuras
    query_payables = """
        SELECT ap.*, s.name AS supplier_name, 'expense' AS flow_type
        FROM accounts_payable ap
        JOIN suppliers s ON ap.supplier_id = s.id
        WHERE ap.due_date BETWEEN %s AND %s
        AND ap.status IN ('pending', 'overdue')
        AND ap.active = TRUE
    """
    params_payables = [today, end_date]
    
    # Adicionar filtro de conta bancária, se fornecido
    if bank_account_id:
        query_payables += " AND ap.bank_account_id = %s"
        params_payables.append(bank_account_id)

    # Adicionar filtro de empresa, se fornecido
    if company_id:
        query_payables += " AND ap.company_id = %s"
        params_payables.append(company_id)
    
    # Buscar contas a receber futuras
    query_receivables = """
        SELECT ar.*, c.name AS customer_name, 'income' AS flow_type
        FROM accounts_receivable ar
        JOIN customers c ON ar.customer_id = c.id
        WHERE ar.due_date BETWEEN %s AND %s
        AND ar.status IN ('pending', 'overdue')
        AND ar.active = TRUE
    """
    params_receivables = [today, end_date]
    
    # Adicionar filtro de conta bancária, se fornecido
    if bank_account_id:
        query_receivables += " AND ar.bank_account_id = %s"
        params_receivables.append(bank_account_id)

    # Adicionar filtro de empresa, se fornecido
    if company_id:
        query_receivables += " AND ar.company_id = %s"
        params_receivables.append(company_id)
    
    # Executar as consultas
    payables = db.fetch_all(query_payables, tuple(params_payables))
    receivables = db.fetch_all(query_receivables, tuple(params_receivables))
    
    # Combinar os resultados
    projection_items = []
    for payable in payables:
        projection_items.append({
            'date': payable['due_date'],
            'description': f"Pagamento: {payable['description']} - {payable['supplier_name']}",
            'amount': payable['total_amount'],
            'type': 'expense'
        })
    
    for receivable in receivables:
        projection_items.append({
            'date': receivable['due_date'],
            'description': f"Recebimento: {receivable['description']} - {receivable['customer_name']}",
            'amount': receivable['total_amount'],
            'type': 'income'
        })
    
    # Ordenar por data
    projection_items.sort(key=lambda x: x['date'])
    
    # Calcular saldo projetado
    current_balance = 0
    
    # Buscar saldo atual
    if bank_account_id:
        balance = db.fetch_one("""
            SELECT 
                SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as balance
            FROM cash_flow
            WHERE bank_account_id = %s
        """, (bank_account_id,))
        
        if balance and balance['balance']:
            current_balance = balance['balance']
    else:
        balance = db.fetch_one("""
            SELECT 
                SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as balance
            FROM cash_flow
        """)
        
        if balance and balance['balance']:
            current_balance = balance['balance']
    
    # Calcular saldo projetado para cada item
    running_balance = current_balance
    for item in projection_items:
        if item['type'] == 'income':
            running_balance += item['amount']
        else:
            running_balance -= item['amount']
        item['balance'] = running_balance
    
    # Buscar contas bancárias para o filtro
    bank_accounts = db.fetch_all("""
        SELECT id, name FROM bank_accounts
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    # Preparar dados para o gráfico
    dates = []
    balances = []
    
    # Adicionar data e saldo atual
    dates.append(today.strftime('%Y-%m-%d'))
    balances.append(current_balance)
    
    # Adicionar projeções
    for item in projection_items:
        dates.append(item['date'].strftime('%Y-%m-%d'))
        balances.append(item['balance'])
    
    return render_template(
        'cash_flow_projection.html',
        projection_items=projection_items,
        bank_accounts=bank_accounts,
        months=months,
        current_balance=current_balance,
        dates=dates,
        balances=balances,
        bank_account_id=bank_account_id,
        active_page='cash_flow_projection'
    )

@cash_flow_bp.route('/fluxo-caixa/relatorio')
@login_required
def cash_flow_report():
    """Relatórios de fluxo de caixa."""
    db = get_db()
    
    # Obter parâmetros
    report_type = request.args.get('type', 'monthly')
    year = int(request.args.get('year', datetime.datetime.now().year))
    bank_account_id = request.args.get('bank_account_id')
    
    # Definir datas
    start_date = datetime.date(year, 1, 1)
    end_date = datetime.date(year, 12, 31)
    
    # Construir a consulta base
    query = """
        SELECT 
            EXTRACT(MONTH FROM date) as month,
            EXTRACT(YEAR FROM date) as year,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expense
        FROM cash_flow
        WHERE date BETWEEN %s AND %s
    """
    params = [start_date, end_date]
    
    # Adicionar filtro de conta bancária, se fornecido
    if bank_account_id:
        query += " AND bank_account_id = %s"
        params.append(bank_account_id)
    
    # Agrupar por período
    if report_type == 'monthly':
        query += " GROUP BY EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date)"
        query += " ORDER BY EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date)"
    elif report_type == 'quarterly':
        query = query.replace("EXTRACT(MONTH FROM date) as month", "CEIL(EXTRACT(MONTH FROM date)/3) as quarter")
        query += " GROUP BY EXTRACT(YEAR FROM date), CEIL(EXTRACT(MONTH FROM date)/3)"
        query += " ORDER BY EXTRACT(YEAR FROM date), CEIL(EXTRACT(MONTH FROM date)/3)"
    else:  # yearly
        query = query.replace("EXTRACT(MONTH FROM date) as month", "1 as dummy")
        query += " GROUP BY EXTRACT(YEAR FROM date)"
        query += " ORDER BY EXTRACT(YEAR FROM date)"
    
    # Executar a consulta
    report_data = db.fetch_all(query, tuple(params))
    
    # Preparar dados para o gráfico
    labels = []
    income_data = []
    expense_data = []
    balance_data = []
    
    if report_type == 'monthly':
        month_names = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        
        for i in range(1, 13):
            # Encontrar o mês nos dados
            month_data = next((item for item in report_data if int(item['month']) == i), None)
            
            labels.append(month_names[i-1])
            
            if month_data:
                income = float(month_data['income'])
                expense = float(month_data['expense'])
                balance = income - expense
                
                income_data.append(income)
                expense_data.append(expense)
                balance_data.append(balance)
            else:
                income_data.append(0)
                expense_data.append(0)
                balance_data.append(0)
    
    elif report_type == 'quarterly':
        quarter_names = ['1º Trimestre', '2º Trimestre', '3º Trimestre', '4º Trimestre']
        
        for i in range(1, 5):
            # Encontrar o trimestre nos dados
            quarter_data = next((item for item in report_data if int(item['quarter']) == i), None)
            
            labels.append(quarter_names[i-1])
            
            if quarter_data:
                income = float(quarter_data['income'])
                expense = float(quarter_data['expense'])
                balance = income - expense
                
                income_data.append(income)
                expense_data.append(expense)
                balance_data.append(balance)
            else:
                income_data.append(0)
                expense_data.append(0)
                balance_data.append(0)
    
    else:  # yearly
        if report_data:
            year_data = report_data[0]
            
            labels.append(str(year))
            income = float(year_data['income'])
            expense = float(year_data['expense'])
            balance = income - expense
            
            income_data.append(income)
            expense_data.append(expense)
            balance_data.append(balance)
        else:
            labels.append(str(year))
            income_data.append(0)
            expense_data.append(0)
            balance_data.append(0)
    
    # Buscar contas bancárias para o filtro
    bank_accounts = db.fetch_all("""
        SELECT id, name FROM bank_accounts
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    # Calcular totais
    total_income = sum(income_data)
    total_expense = sum(expense_data)
    total_balance = total_income - total_expense
    
    return render_template(
        'cash_flow_report.html',
        report_data=report_data,
        bank_accounts=bank_accounts,
        report_type=report_type,
        year=year,
        labels=labels,
        income_data=income_data,
        expense_data=expense_data,
        balance_data=balance_data,
        total_income=total_income,
        total_expense=total_expense,
        total_balance=total_balance,
        bank_account_id=bank_account_id,
        active_page='cash_flow_report'
    )

@cash_flow_bp.route('/fluxo-caixa/simulacao', methods=['GET', 'POST'])
@login_required
def cash_flow_simulation():
    """Simulação de fluxo de caixa."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        simulation_name = request.form.get('simulation_name')
        start_balance = float(request.form.get('start_balance', '0').replace('.', '').replace(',', '.'))
        
        # Processar itens da simulação
        descriptions = request.form.getlist('description[]')
        amounts = request.form.getlist('amount[]')
        types = request.form.getlist('type[]')
        dates = request.form.getlist('date[]')
        
        # Criar lista de itens
        simulation_items = []
        running_balance = start_balance
        
        for i in range(len(descriptions)):
            if descriptions[i] and amounts[i] and dates[i]:
                amount = float(amounts[i].replace('.', '').replace(',', '.'))
                
                if types[i] == 'expense':
                    running_balance -= amount
                else:
                    running_balance += amount
                
                simulation_items.append({
                    'date': datetime.datetime.strptime(dates[i], '%Y-%m-%d').date(),
                    'description': descriptions[i],
                    'amount': amount,
                    'type': types[i],
                    'balance': running_balance
                })
        
        # Ordenar por data
        simulation_items.sort(key=lambda x: x['date'])
        
        # Recalcular saldo
        running_balance = start_balance
        for item in simulation_items:
            if item['type'] == 'expense':
                running_balance -= item['amount']
            else:
                running_balance += item['amount']
            item['balance'] = running_balance
        
        # Preparar dados para o gráfico
        dates = []
        balances = []
        
        # Adicionar saldo inicial
        today = datetime.datetime.now().date()
        dates.append(today.strftime('%Y-%m-%d'))
        balances.append(start_balance)
        
        # Adicionar itens da simulação
        for item in simulation_items:
            dates.append(item['date'].strftime('%Y-%m-%d'))
            balances.append(item['balance'])
        
        return render_template(
            'cash_flow_simulation_result.html',
            simulation_name=simulation_name,
            start_balance=start_balance,
            simulation_items=simulation_items,
            dates=dates,
            balances=balances,
            active_page='cash_flow_simulation'
        )
    
    # Buscar saldo atual
    balance = db.fetch_one("""
        SELECT 
            SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as balance
        FROM cash_flow
    """)
    
    current_balance = balance['balance'] if balance and balance['balance'] else 0
    
    return render_template(
        'cash_flow_simulation.html',
        current_balance=current_balance,
        active_page='cash_flow_simulation'
    )

@cash_flow_bp.route('/api/fluxo-caixa/saldo')
@login_required
def api_cash_flow_balance():
    """API para buscar saldo de uma conta bancária."""
    db = get_db()
    
    bank_account_id = request.args.get('bank_account_id')
    
    if bank_account_id:
        balance = db.fetch_one("""
            SELECT 
                SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as balance
            FROM cash_flow
            WHERE bank_account_id = %s
        """, (bank_account_id,))
        
        if balance and balance['balance']:
            return jsonify({'balance': float(balance['balance'])})
    
    return jsonify({'balance': 0})
