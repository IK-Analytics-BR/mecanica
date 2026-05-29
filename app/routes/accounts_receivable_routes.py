"""
Rotas para gerenciamento de contas a receber.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import datetime

from database import get_db
from utils.auth import login_required

# Criar o blueprint
accounts_receivable_bp = Blueprint('accounts_receivable', __name__)


@accounts_receivable_bp.route('/contas-receber')
@login_required
def accounts_receivable_list():
    """Lista todas as contas a receber."""
    db = get_db()
    
    # Filtros
    status = request.args.get('status', 'all')
    period = request.args.get('period', 'all')
    customer_id = request.args.get('customer_id')
    company_id = request.args.get('company_id')
    
    # Construir a consulta base
    query = """
        SELECT 
            ar.*, 
            c.name AS customer_name, 
            ba.name AS bank_account_name,
            e.nome_fantasia AS company_name
        FROM accounts_receivable ar
        LEFT JOIN customers c ON ar.customer_id = c.id
        LEFT JOIN bank_accounts ba ON ar.bank_account_id = ba.id
        LEFT JOIN empresas e ON ar.company_id = e.id
        WHERE ar.active = TRUE
    """
    params = []
    
    # Adicionar filtros
    if status != 'all':
        query += " AND ar.status = %s"
        params.append(status)
    
    if period == 'today':
        query += " AND ar.due_date = CURDATE()"
    elif period == 'week':
        query += " AND ar.due_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)"
    elif period == 'month':
        query += " AND ar.due_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 1 MONTH)"
    elif period == 'overdue':
        query += " AND ar.due_date < CURDATE() AND ar.status = 'pending'"
    
    if customer_id:
        query += " AND ar.customer_id = %s"
        params.append(customer_id)

    if company_id:
        query += " AND ar.company_id = %s"
        params.append(company_id)
    
    # Ordenação: mais recentes / vencimentos mais distantes primeiro
    query += " ORDER BY ar.due_date DESC"
    
    # Executar a consulta
    receivables = db.fetch_all(query, tuple(params))
    
    # Buscar clientes para o filtro
    customers = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    # Buscar contas bancárias para o formulário
    bank_accounts = db.fetch_all("""
        SELECT id, name FROM bank_accounts
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)

    # Buscar empresas para filtro por empresa
    companies = db.fetch_all("""
        SELECT id, nome_fantasia
        FROM empresas
        WHERE ativo = TRUE
        ORDER BY nome_fantasia
    """)
    
    return render_template(
        'accounts_receivable_list.html',
        receivables=receivables,
        customers=customers,
        bank_accounts=bank_accounts,
        status=status,
        period=period,
        customer_id=customer_id,
        companies=companies,
        company_id=company_id,
        active_page='accounts_receivable'
    )

@accounts_receivable_bp.route('/contas-receber/cadastrar', methods=['GET', 'POST'])
@login_required
def accounts_receivable_create():
    """Cadastra uma nova conta a receber."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        customer_id = request.form.get('customer_id')
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
        
        if not customer_id:
            errors.append('Cliente é obrigatório.')
        
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
        
        if not bank_account_id:
            errors.append('Conta bancária é obrigatória.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            # Buscar clientes para o formulário
            customers = db.fetch_all("""
                SELECT id, name FROM customers
                WHERE active = TRUE
                ORDER BY name
            """)
            
            # Buscar contas bancárias para o formulário
            bank_accounts = db.fetch_all("""
                SELECT id, name FROM bank_accounts
                WHERE active = TRUE AND status = 'active'
                ORDER BY name
            """)
            
            # Buscar contas contábeis
            chart_accounts = db.fetch_all("""
                SELECT id, code, name FROM chart_of_accounts
                WHERE is_analytical = TRUE AND active = TRUE
                AND type IN ('revenue', 'asset')
                ORDER BY code
            """)
            
            return render_template(
                'accounts_receivable_form.html',
                receivable=None,
                customers=customers,
                bank_accounts=bank_accounts,
                chart_accounts=chart_accounts,
                active_page='accounts_receivable'
            )
        
        # Inserir conta a receber no banco de dados
        receivable_id = db.insert("""
            INSERT INTO accounts_receivable (
                customer_id, invoice_number, description, total_amount, 
                installments, issue_date, due_date, payment_method, 
                bank_account_id, status, notes, origin
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            customer_id, invoice_number, description, total_amount, 
            installments, issue_date, due_date, payment_method, 
            bank_account_id, 'pending', notes, 'manual'
        ))
        
        if receivable_id:
            flash('Conta a receber cadastrada com sucesso!', 'success')
            
            # Criar parcelas
            if int(installments) > 1:
                # Chamar a procedure para criar parcelas
                db.execute("""
                    CALL create_installments(%s, %s, %s, %s, %s, %s)
                """, ('receivable', receivable_id, int(installments), float(total_amount), due_date, 30))
            else:
                # Criar uma única parcela
                db.insert("""
                    INSERT INTO receivable_installments (
                        receivable_id, installment_number, amount, due_date, status
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (receivable_id, 1, total_amount, due_date, 'pending'))
            
            return redirect(url_for('accounts_receivable.accounts_receivable_view', receivable_id=receivable_id))
        else:
            flash('Erro ao cadastrar conta a receber.', 'danger')
    
    # Buscar clientes para o formulário
    customers = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    # Buscar contas bancárias para o formulário
    bank_accounts = db.fetch_all("""
        SELECT id, name FROM bank_accounts
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    # Buscar contas contábeis
    chart_accounts = db.fetch_all("""
        SELECT id, code, name FROM chart_of_accounts
        WHERE is_analytical = TRUE AND active = TRUE
        AND type IN ('revenue', 'asset')
        ORDER BY code
    """)
    
    return render_template(
        'accounts_receivable_form.html',
        receivable=None,
        customers=customers,
        bank_accounts=bank_accounts,
        chart_accounts=chart_accounts,
        active_page='accounts_receivable'
    )

@accounts_receivable_bp.route('/contas-receber/editar/<int:receivable_id>', methods=['GET', 'POST'])
@login_required
def accounts_receivable_edit(receivable_id):
    """Edita uma conta a receber existente."""
    db = get_db()
    
    # Buscar a conta a receber
    receivable = db.fetch_one("""
        SELECT * FROM accounts_receivable
        WHERE id = %s AND active = TRUE
    """, (receivable_id,))
    
    if not receivable:
        flash('Conta a receber não encontrada.', 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_list'))
    
    # Verificar se a conta pode ser editada
    if receivable['status'] in ['received', 'canceled']:
        flash('Não é possível editar uma conta a receber que já foi recebida ou cancelada.', 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_view', receivable_id=receivable_id))
    
    if request.method == 'POST':
        # Obter dados do formulário
        customer_id = request.form.get('customer_id')
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
        
        if not customer_id:
            errors.append('Cliente é obrigatório.')
        
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
        
        if not bank_account_id:
            errors.append('Conta bancária é obrigatória.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('accounts_receivable.accounts_receivable_edit', receivable_id=receivable_id))
        
        # Atualizar conta a receber no banco de dados
        affected_rows = db.update("""
            UPDATE accounts_receivable
            SET customer_id = %s, invoice_number = %s, description = %s, 
                issue_date = %s, due_date = %s, payment_method = %s, 
                bank_account_id = %s, chart_account_id = %s, notes = %s
            WHERE id = %s
        """, (
            customer_id, invoice_number, description, 
            issue_date, due_date, payment_method, 
            bank_account_id, chart_account_id if chart_account_id else None, notes, receivable_id
        ))
        
        # Atualizar parcelas se houver apenas uma
        installments_count = db.fetch_one("""
            SELECT COUNT(*) as count FROM receivable_installments
            WHERE receivable_id = %s
        """, (receivable_id,))
        
        if installments_count and installments_count['count'] == 1:
            db.update("""
                UPDATE receivable_installments
                SET amount = %s, due_date = %s
                WHERE receivable_id = %s AND installment_number = 1
            """, (total_amount, due_date, receivable_id))
        
        if affected_rows > 0:
            flash('Conta a receber atualizada com sucesso!', 'success')
            return redirect(url_for('accounts_receivable.accounts_receivable_view', receivable_id=receivable_id))
        else:
            flash('Erro ao atualizar conta a receber.', 'danger')
    
    # Buscar clientes para o formulário
    customers = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    # Buscar contas bancárias para o formulário
    bank_accounts = db.fetch_all("""
        SELECT id, name FROM bank_accounts
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    # Buscar contas contábeis
    chart_accounts = db.fetch_all("""
        SELECT id, code, name FROM chart_of_accounts
        WHERE is_analytical = TRUE AND active = TRUE
        AND type IN ('revenue', 'asset')
        ORDER BY code
    """)
    
    return render_template(
        'accounts_receivable_form.html',
        receivable=receivable,
        customers=customers,
        bank_accounts=bank_accounts,
        chart_accounts=chart_accounts,
        active_page='accounts_receivable'
    )

@accounts_receivable_bp.route('/contas-receber/visualizar/<int:receivable_id>')
@login_required
def accounts_receivable_view(receivable_id):
    """Visualiza detalhes de uma conta a receber."""
    db = get_db()
    
    # Buscar a conta a receber
    receivable = db.fetch_one("""
        SELECT ar.*, c.name as customer_name, ba.name as bank_account_name
        FROM accounts_receivable ar
        LEFT JOIN customers c ON ar.customer_id = c.id
        LEFT JOIN bank_accounts ba ON ar.bank_account_id = ba.id
        WHERE ar.id = %s AND ar.active = TRUE
    """, (receivable_id,))
    
    if not receivable:
        flash('Conta a receber não encontrada.', 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_list'))
    
    # Buscar parcelas da conta a receber
    installments = db.fetch_all("""
        SELECT * FROM receivable_installments
        WHERE receivable_id = %s
        ORDER BY installment_number
    """, (receivable_id,))
    
    return render_template(
        'accounts_receivable_view.html',
        receivable=receivable,
        installments=installments,
        active_page='accounts_receivable'
    )

@accounts_receivable_bp.route('/contas-receber/excluir/<int:receivable_id>', methods=['POST'])
@login_required
def accounts_receivable_delete(receivable_id):
    """Exclui uma conta a receber (exclusão lógica)."""
    db = get_db()
    
    # Verificar se a conta a receber existe
    receivable = db.fetch_one("""
        SELECT * FROM accounts_receivable
        WHERE id = %s AND active = TRUE
    """, (receivable_id,))
    
    if not receivable:
        flash('Conta a receber não encontrada.', 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_list'))
    
    # Verificar se a conta pode ser excluída
    if receivable['status'] == 'received':
        flash('Não é possível excluir uma conta a receber que já foi recebida.', 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_view', receivable_id=receivable_id))
    
    # Excluir conta a receber (exclusão lógica)
    affected_rows = db.update("""
        UPDATE accounts_receivable
        SET active = FALSE, status = 'canceled'
        WHERE id = %s
    """, (receivable_id,))
    
    # Cancelar parcelas
    db.update("""
        UPDATE receivable_installments
        SET status = 'canceled'
        WHERE receivable_id = %s
    """, (receivable_id,))
    
    if affected_rows > 0:
        flash('Conta a receber excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir conta a receber.', 'danger')
    
    return redirect(url_for('accounts_receivable.accounts_receivable_list'))

@accounts_receivable_bp.route('/contas-receber/receber-parcela/<int:installment_id>', methods=['POST'])
@login_required
def accounts_receivable_receive_installment(installment_id):
    """Registra o recebimento de uma parcela."""
    db = get_db()
    
    # Buscar a parcela
    installment = db.fetch_one("""
        SELECT ri.*, ar.customer_id, ar.description, ar.bank_account_id, ar.installments
        FROM receivable_installments ri
        JOIN accounts_receivable ar ON ri.receivable_id = ar.id
        WHERE ri.id = %s
    """, (installment_id,))

    # Fallback: algumas telas podem enviar o ID do título (accounts_receivable.id)
    # em vez do ID da parcela (receivable_installments.id).
    if not installment:
        installment = db.fetch_one(
            """
            SELECT ri.*, ar.customer_id, ar.description, ar.bank_account_id, ar.installments
            FROM receivable_installments ri
            JOIN accounts_receivable ar ON ri.receivable_id = ar.id
            WHERE ri.receivable_id = %s
              AND ri.status IN ('pending', 'overdue')
            ORDER BY ri.installment_number ASC, ri.id ASC
            LIMIT 1
            """,
            (installment_id,),
        )
    
    if not installment:
        flash('Parcela não encontrada.', 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_list'))

    installment_pk = int(installment.get('id') or 0)
    if not installment_pk:
        flash('Parcela não encontrada.', 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_list'))
    
    # Verificar se a parcela pode ser recebida
    if installment['status'] != 'pending' and installment['status'] != 'overdue':
        flash('Esta parcela não está pendente de recebimento.', 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_view', receivable_id=installment['receivable_id']))
    
    # Obter dados do formulário
    receipt_date = request.form.get('receipt_date')
    receipt_amount = request.form.get('receipt_amount')
    payment_method = request.form.get('payment_method')
    notes = request.form.get('notes')
    
    # Validar dados
    errors = []
    
    if not receipt_date:
        receipt_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    if not receipt_amount:
        receipt_amount = installment['amount']
    else:
        try:
            from decimal import Decimal
            # Limpar o valor - remover espaços e caracteres especiais
            receipt_amount_clean = receipt_amount.strip()
            
            # Detectar formato e converter corretamente
            if ',' in receipt_amount_clean and '.' in receipt_amount_clean:
                # Formato brasileiro: 1.500,00 ou americano: 1,500.00
                if receipt_amount_clean.rfind(',') > receipt_amount_clean.rfind('.'):
                    # Brasileiro: vírgula depois do ponto = 1.500,00
                    receipt_amount_clean = receipt_amount_clean.replace('.', '').replace(',', '.')
                else:
                    # Americano: ponto depois da vírgula = 1,500.00
                    receipt_amount_clean = receipt_amount_clean.replace(',', '')
            elif ',' in receipt_amount_clean:
                # Apenas vírgula: 350,00 (brasileiro)
                receipt_amount_clean = receipt_amount_clean.replace(',', '.')
            # Se só tem ponto ou nenhum, já está no formato correto
            
            receipt_amount = Decimal(receipt_amount_clean)
        except (ValueError, Exception) as e:
            errors.append(f'Valor de recebimento inválido: {receipt_amount}')
    
    # Se houver erros, exibir mensagens e retornar
    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_view', receivable_id=installment['receivable_id']))
    
    # Registrar o recebimento da parcela
    affected_rows = db.update("""
        UPDATE receivable_installments
        SET status = 'received', receipt_date = %s
        WHERE id = %s
    """, (receipt_date, installment_pk))
    
    if affected_rows > 0:
        # Registrar no fluxo de caixa
        description = f"Recebimento: {installment['description']}"
        if installment['installments'] > 1:
            description += f" - Parcela {installment['installment_number']}/{installment['installments']}"
        
        db.insert("""
            INSERT INTO cash_flow (date, type, description, amount, bank_account_id, reference_id, reference_type)
            VALUES (%s, 'income', %s, %s, %s, %s, 'receivable')
        """, (receipt_date, description, receipt_amount, installment['bank_account_id'], installment['receivable_id']))
        
        flash('Recebimento registrado com sucesso!', 'success')
        
        # Verificar se todas as parcelas foram recebidas
        received_installments = db.fetch_one("""
            SELECT COUNT(*) as count
            FROM receivable_installments
            WHERE receivable_id = %s AND status = 'received'
        """, (installment['receivable_id'],))
        
        if received_installments and received_installments['count'] == installment['installments']:
            # Atualizar o status da conta a receber
            db.update("""
                UPDATE accounts_receivable
                SET status = 'received', receipt_date = %s
                WHERE id = %s
            """, (receipt_date, installment['receivable_id']))
    else:
        flash('Erro ao registrar recebimento.', 'danger')
    
    return redirect(url_for('accounts_receivable.accounts_receivable_view', receivable_id=installment['receivable_id']))

@accounts_receivable_bp.route('/contas-receber/estornar-parcela/<int:installment_id>', methods=['POST'])
@login_required
def accounts_receivable_reverse_installment(installment_id):
    """Estorna o recebimento de uma parcela."""
    db = get_db()
    
    # Buscar a parcela
    installment = db.fetch_one("""
        SELECT ri.*, ar.customer_id, ar.description, ar.bank_account_id, ar.installments
        FROM receivable_installments ri
        JOIN accounts_receivable ar ON ri.receivable_id = ar.id
        WHERE ri.id = %s
    """, (installment_id,))
    
    if not installment:
        flash('Parcela não encontrada.', 'danger')
        return redirect(url_for('accounts_receivable.accounts_receivable_list'))
    
    # Verificar se a parcela pode ser estornada
    if installment['status'] != 'received':
        flash('Esta parcela não está recebida. Não é possível estornar.', 'warning')
        return redirect(url_for('accounts_receivable.accounts_receivable_view', receivable_id=installment['receivable_id']))
    
    # Obter dados do formulário
    reversal_date = request.form.get('reversal_date')
    reversal_reason = request.form.get('reversal_reason', 'Estorno de recebimento')
    
    if not reversal_date:
        reversal_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # Estornar o recebimento da parcela
    affected_rows = db.update("""
        UPDATE receivable_installments
        SET status = 'pending', receipt_date = NULL
        WHERE id = %s
    """, (installment_id,))
    
    if affected_rows > 0:
        # Registrar estorno no fluxo de caixa (movimento inverso = SAÍDA)
        from decimal import Decimal
        description = f"ESTORNO: {installment['description']}"
        if installment['installments'] > 1:
            description += f" - Parcela {installment['installment_number']}/{installment['installments']}"
        if reversal_reason:
            description += f" ({reversal_reason})"
        
        db.insert("""
            INSERT INTO cash_flow (date, type, description, amount, bank_account_id, reference_id, reference_type)
            VALUES (%s, 'expense', %s, %s, %s, %s, 'receivable')
        """, (reversal_date, description, installment['amount'], installment['bank_account_id'], installment['receivable_id']))
        
        flash('Recebimento estornado com sucesso!', 'success')
        
        # Atualizar o status da conta a receber para pending
        db.update("""
            UPDATE accounts_receivable
            SET status = 'pending', receipt_date = NULL
            WHERE id = %s
        """, (installment['receivable_id'],))
    else:
        flash('Erro ao estornar recebimento.', 'danger')
    
    return redirect(url_for('accounts_receivable.accounts_receivable_view', receivable_id=installment['receivable_id']))

@accounts_receivable_bp.route('/api/clientes')
@login_required
def api_customers():
    """API para buscar clientes."""
    db = get_db()
    
    # Buscar clientes
    customers = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return jsonify(customers)
