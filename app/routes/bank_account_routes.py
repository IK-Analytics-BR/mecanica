"""
Rotas para gerenciamento de contas bancárias.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import datetime

from database import get_db
from utils.auth import login_required

# Criar o blueprint
bank_account_bp = Blueprint('bank_account', __name__)


@bank_account_bp.route('/contas-bancarias')
@login_required
def bank_accounts_list():
    """Lista todas as contas bancárias."""
    db = get_db()
    
    # Buscar todas as contas bancárias ativas
    accounts = db.fetch_all("""
        SELECT * FROM bank_accounts
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'bank_account_list.html',
        accounts=accounts,
        active_page='bank_accounts'
    )

@bank_account_bp.route('/contas-bancarias/cadastrar', methods=['GET', 'POST'])
@login_required
def bank_account_create():
    """Cadastra uma nova conta bancária."""
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        agency = request.form.get('agency')
        account_number = request.form.get('account_number')
        pix_key = request.form.get('pix_key')
        cost_center = request.form.get('cost_center')
        status = request.form.get('status')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome da conta é obrigatório.')
        
        if not cost_center:
            errors.append('Centro de custo é obrigatório.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('bank_account.bank_account_create'))
        
        # Inserir conta bancária no banco de dados
        db = get_db()
        account_id = db.insert("""
            INSERT INTO bank_accounts (name, agency, account_number, pix_key, cost_center, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, agency, account_number, pix_key, cost_center, status))
        
        if account_id:
            flash('Conta bancária cadastrada com sucesso!', 'success')
            return redirect(url_for('bank_account.bank_accounts_list'))
        else:
            flash('Erro ao cadastrar conta bancária.', 'danger')
    
    return render_template(
        'bank_account_form.html',
        account=None,
        active_page='bank_accounts'
    )

@bank_account_bp.route('/contas-bancarias/editar/<int:account_id>', methods=['GET', 'POST'])
@login_required
def bank_account_edit(account_id):
    """Edita uma conta bancária existente."""
    db = get_db()
    
    # Buscar a conta bancária
    account = db.fetch_one("""
        SELECT * FROM bank_accounts
        WHERE id = %s AND active = TRUE
    """, (account_id,))
    
    if not account:
        flash('Conta bancária não encontrada.', 'danger')
        return redirect(url_for('bank_account.bank_accounts_list'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        agency = request.form.get('agency')
        account_number = request.form.get('account_number')
        pix_key = request.form.get('pix_key')
        cost_center = request.form.get('cost_center')
        status = request.form.get('status')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome da conta é obrigatório.')
        
        if not cost_center:
            errors.append('Centro de custo é obrigatório.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('bank_account.bank_account_edit', account_id=account_id))
        
        # Atualizar conta bancária no banco de dados
        affected_rows = db.update("""
            UPDATE bank_accounts
            SET name = %s, agency = %s, account_number = %s, pix_key = %s, cost_center = %s, status = %s
            WHERE id = %s
        """, (name, agency, account_number, pix_key, cost_center, status, account_id))
        
        if affected_rows > 0:
            flash('Conta bancária atualizada com sucesso!', 'success')
            return redirect(url_for('bank_account.bank_accounts_list'))
        else:
            flash('Erro ao atualizar conta bancária.', 'danger')
    
    return render_template(
        'bank_account_form.html',
        account=account,
        active_page='bank_accounts'
    )

@bank_account_bp.route('/contas-bancarias/visualizar/<int:account_id>')
@login_required
def bank_account_view(account_id):
    """Visualiza detalhes de uma conta bancária."""
    db = get_db()
    
    # Buscar a conta bancária
    account = db.fetch_one("""
        SELECT * FROM bank_accounts
        WHERE id = %s AND active = TRUE
    """, (account_id,))
    
    if not account:
        flash('Conta bancária não encontrada.', 'danger')
        return redirect(url_for('bank_account.bank_accounts_list'))
    
    # Buscar movimentações financeiras da conta
    cash_flow = db.fetch_all("""
        SELECT * FROM cash_flow
        WHERE bank_account_id = %s
        ORDER BY date DESC
        LIMIT 10
    """, (account_id,))
    
    # Calcular saldo atual
    balance = db.fetch_one("""
        SELECT 
            SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as balance
        FROM cash_flow
        WHERE bank_account_id = %s
    """, (account_id,))
    
    return render_template(
        'bank_account_view.html',
        account=account,
        cash_flow=cash_flow,
        balance=balance['balance'] if balance and balance['balance'] else 0,
        active_page='bank_accounts'
    )

@bank_account_bp.route('/contas-bancarias/excluir/<int:account_id>', methods=['POST'])
@login_required
def bank_account_delete(account_id):
    """Exclui uma conta bancária (exclusão lógica)."""
    db = get_db()
    
    # Verificar se a conta bancária existe
    account = db.fetch_one("""
        SELECT * FROM bank_accounts
        WHERE id = %s AND active = TRUE
    """, (account_id,))
    
    if not account:
        flash('Conta bancária não encontrada.', 'danger')
        return redirect(url_for('bank_account.bank_accounts_list'))
    
    # Verificar se a conta tem movimentações financeiras
    cash_flow = db.fetch_one("""
        SELECT COUNT(*) as count FROM cash_flow
        WHERE bank_account_id = %s
    """, (account_id,))
    
    if cash_flow and cash_flow['count'] > 0:
        flash('Não é possível excluir uma conta bancária com movimentações financeiras.', 'danger')
        return redirect(url_for('bank_account.bank_account_view', account_id=account_id))
    
    # Excluir conta bancária (exclusão lógica)
    affected_rows = db.update("""
        UPDATE bank_accounts
        SET active = FALSE
        WHERE id = %s
    """, (account_id,))
    
    if affected_rows > 0:
        flash('Conta bancária excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir conta bancária.', 'danger')
    
    return redirect(url_for('bank_account.bank_accounts_list'))
