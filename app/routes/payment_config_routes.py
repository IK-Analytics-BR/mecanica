"""
Rotas para configuração de formas de pagamento.
Define regras de negócio: taxas, prazos, parcelamento, etc.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from utils.auth import login_required
from functools import wraps


payment_config_bp = Blueprint('payment_config', __name__)

@payment_config_bp.route('/configuracoes/formas-pagamento', methods=['GET'])
@login_required
def payment_config_list():
    """Lista todas as configurações de formas de pagamento."""
    db = get_db()
    
    configs = db.fetch_all("""
        SELECT 
            pmc.*,
            ba.name as bank_account_name
        FROM payment_methods_config pmc
        LEFT JOIN bank_accounts ba ON pmc.bank_account_id = ba.id
        ORDER BY pmc.name
    """)
    
    return render_template(
        'payment_config_list.html',
        configs=configs,
        active_page='payment_config'
    )

@payment_config_bp.route('/configuracoes/formas-pagamento/novo', methods=['GET', 'POST'])
@login_required
def payment_config_create():
    """Cria uma nova configuração de forma de pagamento."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        financial_behavior = request.form.get('financial_behavior', 'both')
        days_to_receive = int(request.form.get('days_to_receive', 0))
        receive_on_business_days = request.form.get('receive_on_business_days') == 'on'
        operator_fee_percent = float(request.form.get('operator_fee_percent', 0))
        operator_fee_fixed = float(request.form.get('operator_fee_fixed', 0))
        bank_account_id = request.form.get('bank_account_id') or None
        allow_installments = request.form.get('allow_installments') == 'on'
        max_installments = int(request.form.get('max_installments', 1))
        days_between_installments = int(request.form.get('days_between_installments', 30))
        installment_fee_percent = float(request.form.get('installment_fee_percent', 0))
        requires_approval = request.form.get('requires_approval') == 'on'
        credit_analysis = request.form.get('credit_analysis') == 'on'
        generate_boleto = request.form.get('generate_boleto') == 'on'
        notes = request.form.get('notes', '').strip()
        active = request.form.get('active') == 'on'
        
        # Validações
        if not name or not code:
            flash('Nome e Código são obrigatórios.', 'danger')
            return render_template('payment_config_form.html', config=None, active_page='payment_config')
        
        # Verificar se código já existe
        existing = db.fetch_one("SELECT id FROM payment_methods_config WHERE code = %s", (code,))
        if existing:
            flash(f'Código "{code}" já está em uso.', 'danger')
            return render_template('payment_config_form.html', config=None, active_page='payment_config')
        
        # Inserir
        try:
            db.insert("""
                INSERT INTO payment_methods_config 
                (name, code, financial_behavior, days_to_receive, receive_on_business_days,
                 operator_fee_percent, operator_fee_fixed, bank_account_id, 
                 allow_installments, max_installments, days_between_installments, 
                 installment_fee_percent, requires_approval, credit_analysis, 
                 generate_boleto, notes, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                name, code, financial_behavior, days_to_receive, receive_on_business_days,
                operator_fee_percent, operator_fee_fixed, bank_account_id,
                allow_installments, max_installments, days_between_installments,
                installment_fee_percent, requires_approval, credit_analysis,
                generate_boleto, notes, active
            ))
            
            flash(f'Forma de pagamento "{name}" criada com sucesso!', 'success')
            return redirect(url_for('payment_config.payment_config_list'))
            
        except Exception as e:
            flash(f'Erro ao criar configuração: {e}', 'danger')
    
    # GET - Buscar contas bancárias para o formulário
    bank_accounts = db.fetch_all("SELECT id, name FROM bank_accounts WHERE active = TRUE ORDER BY name")
    
    return render_template(
        'payment_config_form.html',
        config=None,
        bank_accounts=bank_accounts,
        active_page='payment_config'
    )

@payment_config_bp.route('/configuracoes/formas-pagamento/<int:config_id>/editar', methods=['GET', 'POST'])
@login_required
def payment_config_edit(config_id):
    """Edita uma configuração de forma de pagamento."""
    db = get_db()
    
    config = db.fetch_one("SELECT * FROM payment_methods_config WHERE id = %s", (config_id,))
    if not config:
        flash('Configuração não encontrada.', 'danger')
        return redirect(url_for('payment_config.payment_config_list'))
    
    if request.method == 'POST':
        # Obter dados do formulário (mesmo código do create)
        name = request.form.get('name', '').strip()
        financial_behavior = request.form.get('financial_behavior', 'both')
        days_to_receive = int(request.form.get('days_to_receive', 0))
        receive_on_business_days = request.form.get('receive_on_business_days') == 'on'
        operator_fee_percent = float(request.form.get('operator_fee_percent', 0))
        operator_fee_fixed = float(request.form.get('operator_fee_fixed', 0))
        bank_account_id = request.form.get('bank_account_id') or None
        allow_installments = request.form.get('allow_installments') == 'on'
        max_installments = int(request.form.get('max_installments', 1))
        days_between_installments = int(request.form.get('days_between_installments', 30))
        installment_fee_percent = float(request.form.get('installment_fee_percent', 0))
        requires_approval = request.form.get('requires_approval') == 'on'
        credit_analysis = request.form.get('credit_analysis') == 'on'
        generate_boleto = request.form.get('generate_boleto') == 'on'
        notes = request.form.get('notes', '').strip()
        active = request.form.get('active') == 'on'
        
        # Validações
        if not name:
            flash('Nome é obrigatório.', 'danger')
            return render_template('payment_config_form.html', config=config, active_page='payment_config')
        
        # Atualizar
        try:
            db.execute("""
                UPDATE payment_methods_config 
                SET name = %s, financial_behavior = %s, days_to_receive = %s, 
                    receive_on_business_days = %s, operator_fee_percent = %s, 
                    operator_fee_fixed = %s, bank_account_id = %s, 
                    allow_installments = %s, max_installments = %s, 
                    days_between_installments = %s, installment_fee_percent = %s,
                    requires_approval = %s, credit_analysis = %s, 
                    generate_boleto = %s, notes = %s, active = %s
                WHERE id = %s
            """, (
                name, financial_behavior, days_to_receive, receive_on_business_days,
                operator_fee_percent, operator_fee_fixed, bank_account_id,
                allow_installments, max_installments, days_between_installments,
                installment_fee_percent, requires_approval, credit_analysis,
                generate_boleto, notes, active, config_id
            ))
            
            flash(f'Configuração atualizada com sucesso!', 'success')
            return redirect(url_for('payment_config.payment_config_list'))
            
        except Exception as e:
            flash(f'Erro ao atualizar: {e}', 'danger')
    
    # GET
    bank_accounts = db.fetch_all("SELECT id, name FROM bank_accounts WHERE active = TRUE ORDER BY name")
    
    return render_template(
        'payment_config_form.html',
        config=config,
        bank_accounts=bank_accounts,
        active_page='payment_config'
    )

@payment_config_bp.route('/configuracoes/formas-pagamento/<int:config_id>/excluir', methods=['POST'])
@login_required
def payment_config_delete(config_id):
    """Exclui (desativa) uma configuração."""
    db = get_db()
    
    try:
        db.execute("UPDATE payment_methods_config SET active = FALSE WHERE id = %s", (config_id,))
        flash('Configuração desativada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao desativar: {e}', 'danger')
    
    return redirect(url_for('payment_config.payment_config_list'))

@payment_config_bp.route('/api/formas-pagamento/<payment_code>', methods=['GET'])
@login_required
def payment_config_api(payment_code):
    """API para obter configuração de uma forma de pagamento."""
    db = get_db()
    
    config = db.fetch_one("""
        SELECT * FROM payment_methods_config 
        WHERE code = %s AND active = TRUE
    """, (payment_code,))
    
    if not config:
        return {'error': 'Configuração não encontrada'}, 404
    
    return {
        'success': True,
        'config': dict(config)
    }
