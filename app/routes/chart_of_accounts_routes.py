"""
Rotas para gerenciamento de Contas Contábeis (Plano de Contas)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from database import get_db
from utils.auth import login_required
from functools import wraps

chart_of_accounts_bp = Blueprint('chart_of_accounts', __name__)


@chart_of_accounts_bp.route('/contas-contabeis')
@login_required
def chart_of_accounts_list():
    """Lista o plano de contas"""
    db = get_db()
    
    # Filtros
    account_type = request.args.get('type', '')
    level = request.args.get('level', '')
    
    # Construir query
    query = """
        SELECT 
            id,
            code,
            name,
            type,
            parent_id,
            level,
            is_analytical,
            description,
            active
        FROM chart_of_accounts
        WHERE 1=1
    """
    
    params = []
    
    if account_type:
        query += " AND type = %s"
        params.append(account_type)
    
    if level:
        query += " AND level = %s"
        params.append(int(level))
    
    # Ordenar por código
    query += " ORDER BY code ASC"
    
    # Executar query
    accounts = db.fetch_all(query, tuple(params) if params else None)
    
    # Contar por tipo
    type_counts = db.fetch_all("""
        SELECT 
            type,
            COUNT(*) as count
        FROM chart_of_accounts
        WHERE active = TRUE
        GROUP BY type
    """)
    
    # Transformar em dicionário
    type_counts_dict = {row['type']: row['count'] for row in type_counts}
    
    return render_template(
        'chart_of_accounts_list.html',
        accounts=accounts,
        type_counts=type_counts_dict,
        account_type=account_type,
        level=level,
        active_page='chart_of_accounts'
    )

@chart_of_accounts_bp.route('/contas-contabeis/visualizar/<int:account_id>')
@login_required
def chart_of_accounts_view(account_id):
    """Visualiza detalhes de uma conta contábil"""
    db = get_db()
    
    # Buscar conta
    account = db.fetch_one("""
        SELECT 
            ca.*,
            parent.code as parent_code,
            parent.name as parent_name
        FROM chart_of_accounts ca
        LEFT JOIN chart_of_accounts parent ON ca.parent_id = parent.id
        WHERE ca.id = %s
    """, (account_id,))
    
    if not account:
        flash('Conta contábil não encontrada.', 'danger')
        return redirect(url_for('chart_of_accounts.chart_of_accounts_list'))
    
    # Buscar contas filhas (sub-contas)
    children = db.fetch_all("""
        SELECT 
            id,
            code,
            name,
            type,
            level,
            is_analytical,
            active
        FROM chart_of_accounts
        WHERE parent_id = %s
        ORDER BY code
    """, (account_id,))
    
    # Buscar movimentações relacionadas (contas a pagar/receber que usam esta conta)
    payables = db.fetch_all("""
        SELECT 
            ap.id,
            ap.description,
            ap.total_amount,
            ap.status,
            s.name as supplier_name
        FROM accounts_payable ap
        JOIN suppliers s ON ap.supplier_id = s.id
        WHERE ap.chart_account_id = %s
        AND ap.active = TRUE
        ORDER BY ap.due_date DESC
        LIMIT 10
    """, (account_id,))
    
    receivables = db.fetch_all("""
        SELECT 
            ar.id,
            ar.description,
            ar.total_amount,
            ar.status,
            c.name as customer_name
        FROM accounts_receivable ar
        JOIN customers c ON ar.customer_id = c.id
        WHERE ar.chart_account_id = %s
        AND ar.active = TRUE
        ORDER BY ar.due_date DESC
        LIMIT 10
    """, (account_id,))
    
    return render_template(
        'chart_of_accounts_view.html',
        account=account,
        children=children,
        payables=payables,
        receivables=receivables,
        active_page='chart_of_accounts'
    )

@chart_of_accounts_bp.route('/contas-contabeis/cadastrar', methods=['GET', 'POST'])
@login_required
def chart_of_accounts_create():
    """Cadastra uma nova conta contábil"""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        code = request.form.get('code')
        name = request.form.get('name')
        account_type = request.form.get('type')
        parent_id = request.form.get('parent_id')
        level = request.form.get('level', '3')
        is_analytical = request.form.get('is_analytical') == 'on'
        description = request.form.get('description')
        
        # Validar
        errors = []
        
        if not code:
            errors.append('Código é obrigatório.')
        
        if not name:
            errors.append('Nome é obrigatório.')
        
        if not account_type:
            errors.append('Tipo é obrigatório.')
        
        # Verificar se código já existe
        existing = db.fetch_one("""
            SELECT id FROM chart_of_accounts WHERE code = %s
        """, (code,))
        
        if existing:
            errors.append(f'Código {code} já existe.')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            # Inserir
            db.insert("""
                INSERT INTO chart_of_accounts (
                    code, name, type, parent_id, level, is_analytical, description, active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            """, (
                code, name, account_type, 
                parent_id if parent_id else None,
                int(level), is_analytical, description
            ))
            
            flash('Conta contábil cadastrada com sucesso!', 'success')
            return redirect(url_for('chart_of_accounts.chart_of_accounts_list'))
    
    # Buscar contas para parent_id
    parent_accounts = db.fetch_all("""
        SELECT id, code, name, CONCAT(code, ' - ', name) as full_name
        FROM chart_of_accounts
        WHERE active = TRUE
        AND is_analytical = FALSE
        ORDER BY code
    """)
    
    return render_template(
        'chart_of_accounts_form.html',
        account=None,
        parent_accounts=parent_accounts,
        active_page='chart_of_accounts'
    )

@chart_of_accounts_bp.route('/contas-contabeis/editar/<int:account_id>', methods=['GET', 'POST'])
@login_required
def chart_of_accounts_edit(account_id):
    """Edita uma conta contábil"""
    db = get_db()
    
    # Buscar conta
    account = db.fetch_one("""
        SELECT * FROM chart_of_accounts WHERE id = %s
    """, (account_id,))
    
    if not account:
        flash('Conta não encontrada.', 'danger')
        return redirect(url_for('chart_of_accounts.chart_of_accounts_list'))
    
    if request.method == 'POST':
        # Obter dados
        name = request.form.get('name')
        description = request.form.get('description')
        is_analytical = request.form.get('is_analytical') == 'on'
        
        # Validar
        if not name:
            flash('Nome é obrigatório.', 'danger')
        else:
            # Atualizar
            db.update("""
                UPDATE chart_of_accounts
                SET name = %s, description = %s, is_analytical = %s
                WHERE id = %s
            """, (name, description, is_analytical, account_id))
            
            flash('Conta atualizada com sucesso!', 'success')
            return redirect(url_for('chart_of_accounts.chart_of_accounts_view', account_id=account_id))
    
    # Buscar contas para parent_id
    parent_accounts = db.fetch_all("""
        SELECT id, code, name, CONCAT(code, ' - ', name) as full_name
        FROM chart_of_accounts
        WHERE active = TRUE
        AND is_analytical = FALSE
        AND id != %s
        ORDER BY code
    """, (account_id,))
    
    return render_template(
        'chart_of_accounts_form.html',
        account=account,
        parent_accounts=parent_accounts,
        active_page='chart_of_accounts'
    )

@chart_of_accounts_bp.route('/contas-contabeis/toggle/<int:account_id>', methods=['POST'])
@login_required
def chart_of_accounts_toggle(account_id):
    """Ativa/Desativa uma conta"""
    db = get_db()
    
    account = db.fetch_one("""
        SELECT active FROM chart_of_accounts WHERE id = %s
    """, (account_id,))
    
    if account:
        new_status = not account['active']
        db.update("""
            UPDATE chart_of_accounts
            SET active = %s
            WHERE id = %s
        """, (new_status, account_id))
        
        status_text = 'ativada' if new_status else 'desativada'
        flash(f'Conta {status_text} com sucesso!', 'success')
    
    return redirect(url_for('chart_of_accounts.chart_of_accounts_list'))

@chart_of_accounts_bp.route('/api/contas-contabeis')
@login_required
def api_chart_of_accounts():
    """API para buscar contas contábeis (para selects)"""
    db = get_db()
    
    account_type = request.args.get('type', '')
    
    query = """
        SELECT 
            id,
            code,
            name,
            CONCAT(code, ' - ', name) as full_name
        FROM chart_of_accounts
        WHERE is_analytical = TRUE
        AND active = TRUE
    """
    
    params = []
    
    if account_type:
        query += " AND type = %s"
        params.append(account_type)
    
    query += " ORDER BY code"
    
    accounts = db.fetch_all(query, tuple(params) if params else None)
    
    return jsonify(accounts)
