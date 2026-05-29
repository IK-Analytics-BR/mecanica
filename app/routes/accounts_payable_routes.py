"""
Rotas para gerenciamento de contas a pagar.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import datetime

from database import get_db
from utils.auth import login_required

# Criar o blueprint
accounts_payable_bp = Blueprint('accounts_payable', __name__)


@accounts_payable_bp.route('/contas-pagar')
@login_required
def accounts_payable_list():
    """Lista todas as contas a pagar."""
    db = get_db()
    
    # Filtros
    status = request.args.get('status', 'all')
    period = request.args.get('period', 'all')
    supplier_id = request.args.get('supplier_id')
    
    # Construir a consulta base
    query = """
        SELECT ap.*, s.name as supplier_name
        FROM accounts_payable ap
        LEFT JOIN suppliers s ON ap.supplier_id = s.id
        WHERE ap.active = TRUE
    """
    params = []
    
    # Adicionar filtros
    if status != 'all':
        query += " AND ap.status = %s"
        params.append(status)
    
    if period == 'today':
        query += " AND ap.due_date = CURDATE()"
    elif period == 'week':
        query += " AND ap.due_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)"
    elif period == 'month':
        query += " AND ap.due_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 1 MONTH)"
    elif period == 'overdue':
        query += " AND ap.due_date < CURDATE() AND ap.status = 'pending'"
    
    if supplier_id:
        query += " AND ap.supplier_id = %s"
        params.append(supplier_id)
    
    # Ordenação
    query += " ORDER BY ap.due_date ASC"
    
    # Executar a consulta
    payables = db.fetch_all(query, tuple(params))
    
    # Buscar fornecedores para o filtro
    suppliers = db.fetch_all("""
        SELECT id, name FROM suppliers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    try:
        bank_accounts = db.fetch_all("""
            SELECT id, name FROM bank_accounts
            WHERE active = TRUE AND status = 'active'
            ORDER BY name
        """)
    except Exception:
        bank_accounts = []
    
    return render_template(
        'accounts_payable_list.html',
        payables=payables,
        suppliers=suppliers,
        bank_accounts=bank_accounts,
        status=status,
        period=period,
        supplier_id=supplier_id,
        active_page='accounts_payable'
    )

@accounts_payable_bp.route('/contas-pagar/cadastrar', methods=['GET', 'POST'])
@login_required
def accounts_payable_create():
    """Cadastra uma nova conta a pagar."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        supplier_id = request.form.get('supplier_id')
        invoice_number = request.form.get('invoice_number')
        description = request.form.get('description')
        total_amount = request.form.get('total_amount')
        installments = request.form.get('installments', '1')
        issue_date = request.form.get('issue_date')
        due_date = request.form.get('due_date')
        payment_method = request.form.get('payment_method')
        bank_account_id = request.form.get('bank_account_id')
        notes = request.form.get('notes')
        
        # Validar dados
        errors = []
        
        if not supplier_id:
            errors.append('Fornecedor é obrigatório.')
        
        if not description:
            errors.append('Descrição é obrigatória.')
        
        if not total_amount:
            errors.append('Valor total é obrigatório.')
        else:
            try:
                from decimal import Decimal
                total_amount = Decimal(total_amount.replace('.', '').replace(',', '.'))
            except (ValueError, Exception):
                errors.append('Valor total inválido.')
        
        if not issue_date:
            errors.append('Data de emissão é obrigatória.')
        
        if not due_date:
            errors.append('Data de vencimento é obrigatória.')
        
        if not payment_method:
            errors.append('Forma de pagamento é obrigatória.')
        
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
            
            try:
                bank_accounts = db.fetch_all("""
                    SELECT id, name FROM bank_accounts
                    WHERE active = TRUE AND status = 'active'
                    ORDER BY name
                """)
            except Exception:
                bank_accounts = []
            
            # Buscar contas contábeis
            chart_accounts = db.fetch_all("""
                SELECT id, code, name FROM chart_of_accounts
                WHERE is_analytical = TRUE AND active = TRUE
                AND type IN ('expense', 'liability')
                ORDER BY code
            """)
            
            return render_template(
                'accounts_payable_form.html',
                payable=None,
                suppliers=suppliers,
                bank_accounts=bank_accounts,
                chart_accounts=chart_accounts,
                active_page='accounts_payable'
            )
        
        # Inserir conta a pagar no banco de dados
        payable_id = db.insert("""
            INSERT INTO accounts_payable (
                supplier_id, document_number, description, amount,
                issue_date, due_date, status, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            supplier_id, invoice_number, description, total_amount,
            issue_date, due_date, 'pending', notes
        ))
        
        if payable_id:
            flash('Conta a pagar cadastrada com sucesso!', 'success')
            
            # Criar parcelas
            if int(installments) > 1:
                # Chamar a procedure para criar parcelas
                db.execute("""
                    CALL create_installments(%s, %s, %s, %s, %s, %s)
                """, ('payable', payable_id, int(installments), float(total_amount), due_date, 30))
            else:
                # Criar uma única parcela
                db.insert("""
                    INSERT INTO payable_installments (
                        payable_id, installment_number, amount, due_date, status
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (payable_id, 1, total_amount, due_date, 'pending'))
            
            return redirect(url_for('accounts_payable.accounts_payable_view', payable_id=payable_id))
        else:
            flash('Erro ao cadastrar conta a pagar.', 'danger')
    
    # Buscar fornecedores para o formulário
    suppliers = db.fetch_all("""
        SELECT id, name FROM suppliers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    try:
        bank_accounts = db.fetch_all("""
            SELECT id, name FROM bank_accounts
            WHERE active = TRUE AND status = 'active'
            ORDER BY name
        """)
    except Exception:
        bank_accounts = []
    
    try:
        chart_accounts = db.fetch_all("""
            SELECT id, code, name FROM chart_of_accounts
            WHERE is_analytical = TRUE AND active = TRUE
            AND type IN ('expense', 'liability')
            ORDER BY code
        """)
    except Exception:
        chart_accounts = []
    
    return render_template(
        'accounts_payable_form.html',
        payable=None,
        suppliers=suppliers,
        bank_accounts=bank_accounts,
        chart_accounts=chart_accounts,
        active_page='accounts_payable'
    )

@accounts_payable_bp.route('/contas-pagar/editar/<int:payable_id>', methods=['GET', 'POST'])
@login_required
def accounts_payable_edit(payable_id):
    """Edita uma conta a pagar existente."""
    db = get_db()
    
    # Buscar a conta a pagar
    payable = db.fetch_one("""
        SELECT * FROM accounts_payable
        WHERE id = %s AND active = TRUE
    """, (payable_id,))
    
    if not payable:
        flash('Conta a pagar não encontrada.', 'danger')
        return redirect(url_for('accounts_payable.accounts_payable_list'))
    
    # Verificar se a conta pode ser editada
    if payable['status'] in ['paid', 'canceled']:
        flash('Não é possível editar uma conta a pagar que já foi paga ou cancelada.', 'danger')
        return redirect(url_for('accounts_payable.accounts_payable_view', payable_id=payable_id))
    
    if request.method == 'POST':
        # Obter dados do formulário
        supplier_id = request.form.get('supplier_id')
        invoice_number = request.form.get('invoice_number')
        description = request.form.get('description')
        total_amount = request.form.get('total_amount')
        issue_date = request.form.get('issue_date')
        due_date = request.form.get('due_date')
        payment_method = request.form.get('payment_method')
        bank_account_id = request.form.get('bank_account_id')
        chart_account_id = request.form.get('chart_account_id')
        notes = request.form.get('notes')
        
        # Validar dados
        errors = []
        
        if not supplier_id:
            errors.append('Fornecedor é obrigatório.')
        
        if not description:
            errors.append('Descrição é obrigatória.')
        
        if not total_amount:
            errors.append('Valor total é obrigatório.')
        else:
            try:
                from decimal import Decimal
                total_amount = Decimal(total_amount.replace('.', '').replace(',', '.'))
            except (ValueError, Exception):
                errors.append('Valor total inválido.')
        
        if not issue_date:
            errors.append('Data de emissão é obrigatória.')
        
        if not due_date:
            errors.append('Data de vencimento é obrigatória.')
        
        if not payment_method:
            errors.append('Forma de pagamento é obrigatória.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('accounts_payable.accounts_payable_edit', payable_id=payable_id))
        
        # Atualizar conta a pagar no banco de dados
        affected_rows = db.update("""
            UPDATE accounts_payable
            SET supplier_id = %s, document_number = %s, description = %s,
                issue_date = %s, due_date = %s, notes = %s
            WHERE id = %s
        """, (
            supplier_id, invoice_number, description,
            issue_date, due_date, notes, payable_id
        ))
        
        # Atualizar parcelas se houver apenas uma
        installments_count = db.fetch_one("""
            SELECT COUNT(*) as count FROM payable_installments
            WHERE payable_id = %s
        """, (payable_id,))
        
        if installments_count and installments_count['count'] == 1:
            db.update("""
                UPDATE payable_installments
                SET amount = %s, due_date = %s
                WHERE payable_id = %s AND installment_number = 1
            """, (total_amount, due_date, payable_id))
        
        if affected_rows > 0:
            flash('Conta a pagar atualizada com sucesso!', 'success')
            return redirect(url_for('accounts_payable.accounts_payable_view', payable_id=payable_id))
        else:
            flash('Erro ao atualizar conta a pagar.', 'danger')
    
    # Buscar fornecedores para o formulário
    suppliers = db.fetch_all("""
        SELECT id, name FROM suppliers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    try:
        bank_accounts = db.fetch_all("""
            SELECT id, name FROM bank_accounts
            WHERE active = TRUE AND status = 'active'
            ORDER BY name
        """)
    except Exception:
        bank_accounts = []
    
    try:
        chart_accounts = db.fetch_all("""
            SELECT id, code, name FROM chart_of_accounts
            WHERE is_analytical = TRUE AND active = TRUE
            AND type IN ('expense', 'liability')
            ORDER BY code
        """)
    except Exception:
        chart_accounts = []
    
    return render_template(
        'accounts_payable_form.html',
        payable=payable,
        suppliers=suppliers,
        bank_accounts=bank_accounts,
        chart_accounts=chart_accounts,
        active_page='accounts_payable'
    )

@accounts_payable_bp.route('/contas-pagar/visualizar/<int:payable_id>')
@login_required
def accounts_payable_view(payable_id):
    """Visualiza detalhes de uma conta a pagar."""
    db = get_db()
    
    # Buscar a conta a pagar
    payable = db.fetch_one("""
        SELECT ap.*, s.name as supplier_name
        FROM accounts_payable ap
        LEFT JOIN suppliers s ON ap.supplier_id = s.id
        WHERE ap.id = %s AND ap.active = TRUE
    """, (payable_id,))
    
    if not payable:
        flash('Conta a pagar não encontrada.', 'danger')
        return redirect(url_for('accounts_payable.accounts_payable_list'))
    
    # Buscar parcelas da conta a pagar
    installments = db.fetch_all("""
        SELECT * FROM payable_installments
        WHERE payable_id = %s
        ORDER BY installment_number
    """, (payable_id,))
    
    return render_template(
        'accounts_payable_view.html',
        payable=payable,
        installments=installments,
        active_page='accounts_payable'
    )

@accounts_payable_bp.route('/contas-pagar/excluir/<int:payable_id>', methods=['POST'])
@login_required
def accounts_payable_delete(payable_id):
    """Exclui uma conta a pagar (exclusão lógica)."""
    db = get_db()
    
    # Verificar se a conta a pagar existe
    payable = db.fetch_one("""
        SELECT * FROM accounts_payable
        WHERE id = %s AND active = TRUE
    """, (payable_id,))
    
    if not payable:
        flash('Conta a pagar não encontrada.', 'danger')
        return redirect(url_for('accounts_payable.accounts_payable_list'))
    
    # Verificar se a conta pode ser excluída
    if payable['status'] == 'paid':
        flash('Não é possível excluir uma conta a pagar que já foi paga.', 'danger')
        return redirect(url_for('accounts_payable.accounts_payable_view', payable_id=payable_id))
    
    # Excluir conta a pagar (exclusão lógica)
    affected_rows = db.update("""
        UPDATE accounts_payable
        SET active = FALSE, status = 'canceled'
        WHERE id = %s
    """, (payable_id,))
    
    # Cancelar parcelas
    db.update("""
        UPDATE payable_installments
        SET status = 'canceled'
        WHERE payable_id = %s
    """, (payable_id,))
    
    if affected_rows > 0:
        flash('Conta a pagar excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir conta a pagar.', 'danger')
    
    return redirect(url_for('accounts_payable.accounts_payable_list'))

@accounts_payable_bp.route('/contas-pagar/pagar-parcela/<int:installment_id>', methods=['POST'])
@login_required
def accounts_payable_pay_installment(installment_id):
    """Registra o pagamento de uma parcela."""
    db = get_db()
    
    # Buscar a parcela
    installment = db.fetch_one("""
        SELECT pi.*, ap.supplier_id, ap.description, ap.installments
        FROM payable_installments pi
        JOIN accounts_payable ap ON pi.payable_id = ap.id
        WHERE pi.id = %s
    """, (installment_id,))
    
    if not installment:
        flash('Parcela não encontrada.', 'danger')
        return redirect(url_for('accounts_payable.accounts_payable_list'))
    
    # Verificar se a parcela pode ser paga
    if installment['status'] != 'pending' and installment['status'] != 'overdue':
        flash('Esta parcela não está pendente de pagamento.', 'danger')
        return redirect(url_for('accounts_payable.accounts_payable_view', payable_id=installment['payable_id']))
    
    # Obter dados do formulário
    payment_date = request.form.get('payment_date')
    payment_amount = request.form.get('payment_amount')
    payment_method = request.form.get('payment_method')
    notes = request.form.get('notes')
    
    # Validar dados
    errors = []
    
    if not payment_date:
        payment_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    if not payment_amount:
        payment_amount = installment['amount']
    else:
        try:
            from decimal import Decimal
            # Limpar o valor - remover espaços e caracteres especiais
            payment_amount_clean = payment_amount.strip()
            
            # Detectar formato e converter corretamente
            if ',' in payment_amount_clean and '.' in payment_amount_clean:
                # Formato brasileiro: 1.500,00 ou americano: 1,500.00
                if payment_amount_clean.rfind(',') > payment_amount_clean.rfind('.'):
                    # Brasileiro: vírgula depois do ponto = 1.500,00
                    payment_amount_clean = payment_amount_clean.replace('.', '').replace(',', '.')
                else:
                    # Americano: ponto depois da vírgula = 1,500.00
                    payment_amount_clean = payment_amount_clean.replace(',', '')
            elif ',' in payment_amount_clean:
                # Apenas vírgula: 350,00 (brasileiro)
                payment_amount_clean = payment_amount_clean.replace(',', '.')
            # Se só tem ponto ou nenhum, já está no formato correto
            
            payment_amount = Decimal(payment_amount_clean)
        except (ValueError, Exception) as e:
            errors.append(f'Valor de pagamento inválido: {payment_amount}')
    
    # Se houver erros, exibir mensagens e retornar
    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('accounts_payable.accounts_payable_view', payable_id=installment['payable_id']))
    
    # Registrar o pagamento da parcela
    affected_rows = db.update("""
        UPDATE payable_installments
        SET status = 'paid', payment_date = %s
        WHERE id = %s
    """, (payment_date, installment_id))
    
    if affected_rows > 0:
        # Registrar no fluxo de caixa
        description = f"Pagamento: {installment['description']}"
        if installment['installments'] > 1:
            description += f" - Parcela {installment['installment_number']}/{installment['installments']}"
        
        try:
            db.insert("""
                INSERT INTO cash_flow (date, type, description, amount, reference_id, reference_type)
                VALUES (%s, 'expense', %s, %s, %s, 'payable')
            """, (payment_date, description, payment_amount, installment['payable_id']))
        except Exception:
            pass
        
        flash('Pagamento registrado com sucesso!', 'success')
        
        # Verificar se todas as parcelas foram pagas
        paid_installments = db.fetch_one("""
            SELECT COUNT(*) as count
            FROM payable_installments
            WHERE payable_id = %s AND status = 'paid'
        """, (installment['payable_id'],))
        
        if paid_installments and paid_installments['count'] == installment['installments']:
            # Atualizar o status da conta a pagar
            db.update("""
                UPDATE accounts_payable
                SET status = 'paid', payment_date = %s
                WHERE id = %s
            """, (payment_date, installment['payable_id']))
    else:
        flash('Erro ao registrar pagamento.', 'danger')
    
    return redirect(url_for('accounts_payable.accounts_payable_view', payable_id=installment['payable_id']))

@accounts_payable_bp.route('/contas-pagar/estornar-parcela/<int:installment_id>', methods=['POST'])
@login_required
def accounts_payable_reverse_installment(installment_id):
    """Estorna o pagamento de uma parcela."""
    db = get_db()
    
    # Buscar a parcela
    installment = db.fetch_one("""
        SELECT pi.*, ap.supplier_id, ap.description, ap.installments
        FROM payable_installments pi
        JOIN accounts_payable ap ON pi.payable_id = ap.id
        WHERE pi.id = %s
    """, (installment_id,))
    
    if not installment:
        flash('Parcela não encontrada.', 'danger')
        return redirect(url_for('accounts_payable.accounts_payable_list'))
    
    # Verificar se a parcela pode ser estornada
    if installment['status'] != 'paid':
        flash('Esta parcela não está paga. Não é possível estornar.', 'warning')
        return redirect(url_for('accounts_payable.accounts_payable_view', payable_id=installment['payable_id']))
    
    # Obter dados do formulário
    reversal_date = request.form.get('reversal_date')
    reversal_reason = request.form.get('reversal_reason', 'Estorno de pagamento')
    
    if not reversal_date:
        reversal_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # Estornar o pagamento da parcela
    affected_rows = db.update("""
        UPDATE payable_installments
        SET status = 'pending', payment_date = NULL
        WHERE id = %s
    """, (installment_id,))
    
    if affected_rows > 0:
        # Registrar estorno no fluxo de caixa (movimento inverso = ENTRADA)
        from decimal import Decimal
        description = f"ESTORNO: {installment['description']}"
        if installment['installments'] > 1:
            description += f" - Parcela {installment['installment_number']}/{installment['installments']}"
        if reversal_reason:
            description += f" ({reversal_reason})"
        
        try:
            db.insert("""
                INSERT INTO cash_flow (date, type, description, amount, reference_id, reference_type)
                VALUES (%s, 'income', %s, %s, %s, 'payable')
            """, (reversal_date, description, installment['amount'], installment['payable_id']))
        except Exception:
            pass
        
        flash('Pagamento estornado com sucesso!', 'success')
        
        # Atualizar o status da conta a pagar para pending
        db.update("""
            UPDATE accounts_payable
            SET status = 'pending', payment_date = NULL
            WHERE id = %s
        """, (installment['payable_id'],))
    else:
        flash('Erro ao estornar pagamento.', 'danger')
    
    return redirect(url_for('accounts_payable.accounts_payable_view', payable_id=installment['payable_id']))

@accounts_payable_bp.route('/api/fornecedores')
@login_required
def api_suppliers():
    """API para buscar fornecedores."""
    db = get_db()
    
    # Buscar fornecedores
    suppliers = db.fetch_all("""
        SELECT id, name FROM suppliers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return jsonify(suppliers)
