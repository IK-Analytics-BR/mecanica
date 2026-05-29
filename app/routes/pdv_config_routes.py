"""
PDV Configurações - Routes
Gerenciamento de configurações do PDV
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime
import sys
import os

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db
from utils.auth import login_required

# Criar Blueprint
pdv_config_bp = Blueprint('pdv_config', __name__, url_prefix='/vendas')


# ===== DECORADOR DE AUTENTICAÇÃO =====


# =====================================================
# TELA DE CONFIGURAÇÕES
# =====================================================

@pdv_config_bp.route('/pdv/configuracoes')
@login_required
def configuracoes():
    """
    Tela de listagem de PDVs cadastrados
    """
    db = get_db()
    
    try:
        # Buscar todos os PDVs cadastrados
        pdvs = db.fetch_all("""
            SELECT 
                ps.id,
                ps.pdv_name,
                ps.pdv_number,
                ps.description,
                ps.company_id,
                COALESCE(e.nome_fantasia, e.razao_social, 'Sem empresa') AS empresa_nome,
                ps.active,
                ps.allow_negative_stock,
                ps.ask_quantity,
                ps.show_discount_button,
                ps.created_at,
                ps.updated_at
            FROM pdv_settings ps
            LEFT JOIN empresas e ON e.id = ps.company_id
            ORDER BY ps.company_id, ps.pdv_number
        """)
        
        # Buscar empresas para dropdown (apenas empresas habilitadas para PDV)
        empresas = db.fetch_all("""
            SELECT 
                id, 
                COALESCE(nome_fantasia, razao_social) AS nome,
                cnpj,
                usar_no_pdv
            FROM empresas
            WHERE ativo = 1
            ORDER BY nome
        """)
        
        return render_template('pdv_configuracoes.html', pdvs=pdvs, empresas=empresas)
        
    except Exception as e:
        flash(f'[X] Erro ao carregar PDVs: {str(e)}', 'danger')
        return redirect('/')


@pdv_config_bp.route('/pdv/configuracoes/obter')
@login_required
def obter_configuracoes():
    """
    Retorna configurações de um PDV específico via AJAX
    """
    db = get_db()
    pdv_id = request.args.get('id')
    
    try:
        if not pdv_id:
            return jsonify({
                "success": False,
                "erro": "ID do PDV não fornecido"
            }), 400
        
        config = db.fetch_one("""
            SELECT * FROM pdv_settings
            WHERE id = %s
        """, (pdv_id,))
        
        if not config:
            return jsonify({
                "success": False,
                "erro": "PDV não encontrado"
            }), 404
        
        return jsonify({
            "success": True,
            "config": dict(config)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500


@pdv_config_bp.route('/pdv/configuracoes/salvar', methods=['POST'])
@login_required
def salvar_configuracoes():
    """
    Salva configurações do PDV
    """
    db = get_db()
    user_id = session.get('user_id')
    
    try:
        data = request.form.to_dict()
        
        # Converter checkboxes (ausentes = False)
        bool_fields = [
            'allow_negative_stock', 'check_stock_realtime', 'show_stock_quantity',
            'ask_quantity', 'allow_decimal_quantity', 'allow_price_change',
            'show_discount_button', 'allow_item_discount', 'allow_total_discount',
            'require_manager_approval', 'require_customer', 'allow_customer_registration',
            'require_payment_confirmation', 'allow_multiple_payments', 'print_receipt_auto',
            'show_product_image', 'show_barcode', 'auto_focus_product_field',
            'beep_on_scan', 'enable_f2_customer', 'enable_f4_discount',
            'enable_f5_cancel', 'enable_f6_search', 'enable_f9_finish',
            'require_supervisor_cancel', 'log_all_operations',
            'print_company_logo', 'print_customer_copy'
        ]
        
        for field in bool_fields:
            data[field] = field in data
        
        # Verificar se já existe configuração
        config_exists = db.fetch_one("""
            SELECT id FROM pdv_settings
            WHERE active = TRUE
            LIMIT 1
        """)
        
        if config_exists:
            # Atualizar existente
            db.execute_query("""
                UPDATE pdv_settings SET
                    pdv_name = %s,
                    pdv_number = %s,
                    allow_negative_stock = %s,
                    check_stock_realtime = %s,
                    show_stock_quantity = %s,
                    ask_quantity = %s,
                    default_quantity = %s,
                    allow_decimal_quantity = %s,
                    allow_price_change = %s,
                    show_discount_button = %s,
                    allow_item_discount = %s,
                    allow_total_discount = %s,
                    max_discount_percent = %s,
                    require_manager_approval = %s,
                    require_customer = %s,
                    allow_customer_registration = %s,
                    require_payment_confirmation = %s,
                    allow_multiple_payments = %s,
                    print_receipt_auto = %s,
                    show_product_image = %s,
                    show_barcode = %s,
                    auto_focus_product_field = %s,
                    beep_on_scan = %s,
                    enable_f2_customer = %s,
                    enable_f4_discount = %s,
                    enable_f5_cancel = %s,
                    enable_f6_search = %s,
                    enable_f9_finish = %s,
                    require_supervisor_cancel = %s,
                    log_all_operations = %s,
                    printer_name = %s,
                    paper_width = %s,
                    print_company_logo = %s,
                    print_customer_copy = %s,
                    updated_by = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (
                data.get('pdv_name', 'PDV Principal'),
                data.get('pdv_number', 1),
                data['allow_negative_stock'],
                data['check_stock_realtime'],
                data['show_stock_quantity'],
                data['ask_quantity'],
                data.get('default_quantity', 1.0),
                data['allow_decimal_quantity'],
                data['allow_price_change'],
                data['show_discount_button'],
                data['allow_item_discount'],
                data['allow_total_discount'],
                data.get('max_discount_percent', 10.0),
                data['require_manager_approval'],
                data['require_customer'],
                data['allow_customer_registration'],
                data['require_payment_confirmation'],
                data['allow_multiple_payments'],
                data['print_receipt_auto'],
                data['show_product_image'],
                data['show_barcode'],
                data['auto_focus_product_field'],
                data['beep_on_scan'],
                data['enable_f2_customer'],
                data['enable_f4_discount'],
                data['enable_f5_cancel'],
                data['enable_f6_search'],
                data['enable_f9_finish'],
                data['require_supervisor_cancel'],
                data['log_all_operations'],
                data.get('printer_name'),
                data.get('paper_width', 80),
                data['print_company_logo'],
                data['print_customer_copy'],
                user_id,
                config_exists['id']
            ))
            
            flash('[OK] Configurações atualizadas com sucesso!', 'success')
        else:
            # Inserir nova (não deveria acontecer se script SQL foi executado)
            flash('[OK] Configurações criadas com sucesso!', 'success')
        
        return redirect(url_for('pdv_config.configuracoes'))
        
    except Exception as e:
        flash(f'[X] Erro ao salvar configurações: {str(e)}', 'danger')
        return redirect(url_for('pdv_config.configuracoes'))


@pdv_config_bp.route('/pdv/configuracoes/resetar', methods=['POST'])
@login_required
def resetar_configuracoes():
    """
    Reseta configurações para padrão
    """
    db = get_db()
    user_id = session.get('user_id')
    
    try:
        db.execute_query("""
            UPDATE pdv_settings SET
                allow_negative_stock = FALSE,
                check_stock_realtime = TRUE,
                ask_quantity = TRUE,
                default_quantity = 1.000,
                show_discount_button = TRUE,
                allow_item_discount = TRUE,
                max_discount_percent = 10.00,
                require_manager_approval = FALSE,
                updated_by = %s,
                updated_at = NOW()
            WHERE active = TRUE
        """, (user_id,))
        
        flash('[OK] Configurações resetadas para o padrão!', 'success')
        return redirect(url_for('pdv_config.configuracoes'))
        
    except Exception as e:
        flash(f'[X] Erro ao resetar configurações: {str(e)}', 'danger')
        return redirect(url_for('pdv_config.configuracoes'))


@pdv_config_bp.route('/pdv/editar/<int:pdv_id>')
@login_required
def editar_pdv(pdv_id):
    """
    Tela de edição de um PDV específico
    """
    db = get_db()
    
    try:
        # Buscar PDV específico
        config = db.fetch_one("""
            SELECT * FROM pdv_settings WHERE id = %s
        """, (pdv_id,))
        
        if not config:
            flash('[X] PDV não encontrado!', 'danger')
            return redirect(url_for('pdv_config.configuracoes'))
        
        # Buscar empresas para dropdown (apenas empresas habilitadas para PDV)
        empresas = db.fetch_all("""
            SELECT 
                id, 
                COALESCE(nome_fantasia, razao_social) AS nome,
                cnpj,
                usar_no_pdv
            FROM empresas
            WHERE ativo = 1
            ORDER BY nome
        """)
        
        return render_template('pdv_editar.html', config=config, empresas=empresas)
        
    except Exception as e:
        flash(f'[X] Erro ao carregar PDV: {str(e)}', 'danger')
        return redirect(url_for('pdv_config.configuracoes'))


@pdv_config_bp.route('/pdv/novo')
@login_required
def novo_pdv():
    """
    Tela para criar novo PDV
    """
    db = get_db()
    
    try:
        # Buscar empresas para dropdown
        empresas = db.fetch_all("""
            SELECT 
                id, 
                COALESCE(nome_fantasia, razao_social) AS nome,
                cnpj,
                usar_no_pdv
            FROM empresas
            WHERE ativo = 1
            ORDER BY nome
        """)
        
        # Config vazio para reutilizar template
        config = {}
        
        return render_template('pdv_editar.html', config=config, empresas=empresas, novo=True)
        
    except Exception as e:
        flash(f'[X] Erro ao preparar novo PDV: {str(e)}', 'danger')
        return redirect(url_for('pdv_config.configuracoes'))


@pdv_config_bp.route('/pdv/criar', methods=['POST'])
@login_required
def criar_pdv():
    """
    Cria novo PDV
    """
    db = get_db()
    user_id = session.get('user_id')
    
    try:
        data = request.form.to_dict()
        
        # Converter checkboxes
        bool_fields = [
            'allow_negative_stock', 'check_stock_realtime', 'show_stock_quantity',
            'ask_quantity', 'allow_decimal_quantity', 'allow_price_change',
            'show_discount_button', 'allow_item_discount', 'allow_total_discount',
            'require_manager_approval', 'require_customer', 'allow_customer_registration',
            'require_payment_confirmation', 'allow_multiple_payments', 'print_receipt_auto',
            'show_product_image', 'show_barcode', 'auto_focus_product_field',
            'beep_on_scan', 'enable_f2_customer', 'enable_f4_discount',
            'enable_f5_cancel', 'enable_f6_search', 'enable_f9_finish',
            'require_supervisor_cancel', 'log_all_operations',
            'print_company_logo', 'print_customer_copy', 'active',
            'emitir_nfce', 'imprimir_automatico'  # NFC-e e Impressao
        ]
        
        for field in bool_fields:
            data[field] = field in data
        
        # Inserir novo PDV
        db.execute_query("""
            INSERT INTO pdv_settings (
                pdv_name, pdv_number, description, company_id,
                allow_negative_stock, check_stock_realtime, show_stock_quantity,
                ask_quantity, default_quantity, allow_decimal_quantity,
                allow_price_change, show_discount_button, allow_item_discount,
                allow_total_discount, max_discount_percent, require_manager_approval,
                require_customer, allow_customer_registration,
                require_payment_confirmation, allow_multiple_payments, print_receipt_auto,
                show_product_image, show_barcode, auto_focus_product_field, beep_on_scan,
                enable_f2_customer, enable_f4_discount, enable_f5_cancel,
                enable_f6_search, enable_f9_finish, require_supervisor_cancel,
                log_all_operations, printer_name, paper_width,
                print_company_logo, print_customer_copy, active,
                updated_by
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s
            )
        """, (
            data.get('pdv_name'), data.get('pdv_number'), data.get('description'),
            data.get('company_id') or None,
            data['allow_negative_stock'], data['check_stock_realtime'], data['show_stock_quantity'],
            data['ask_quantity'], data.get('default_quantity', 1.0), data['allow_decimal_quantity'],
            data['allow_price_change'], data['show_discount_button'], data['allow_item_discount'],
            data['allow_total_discount'], data.get('max_discount_percent', 10.0), data['require_manager_approval'],
            data['require_customer'], data['allow_customer_registration'],
            data['require_payment_confirmation'], data['allow_multiple_payments'], data['print_receipt_auto'],
            data['show_product_image'], data['show_barcode'], data['auto_focus_product_field'], data['beep_on_scan'],
            data['enable_f2_customer'], data['enable_f4_discount'], data['enable_f5_cancel'],
            data['enable_f6_search'], data['enable_f9_finish'], data['require_supervisor_cancel'],
            data['log_all_operations'], data.get('printer_name'), data.get('paper_width', 80),
            data['print_company_logo'], data['print_customer_copy'], data['active'],
            user_id
        ))
        
        flash('[OK] PDV criado com sucesso!', 'success')
        return redirect(url_for('pdv_config.configuracoes'))
        
    except Exception as e:
        flash(f'[X] Erro ao criar PDV: {str(e)}', 'danger')
        return redirect(url_for('pdv_config.novo_pdv'))


@pdv_config_bp.route('/pdv/atualizar/<int:pdv_id>', methods=['POST'])
@login_required
def atualizar_pdv(pdv_id):
    """
    Atualiza PDV existente
    """
    db = get_db()
    user_id = session.get('user_id')
    
    try:
        data = request.form.to_dict()
        
        # Converter checkboxes
        bool_fields = [
            'allow_negative_stock', 'check_stock_realtime', 'show_stock_quantity',
            'ask_quantity', 'allow_decimal_quantity', 'allow_price_change',
            'show_discount_button', 'allow_item_discount', 'allow_total_discount',
            'require_manager_approval', 'require_customer', 'allow_customer_registration',
            'require_payment_confirmation', 'allow_multiple_payments', 'print_receipt_auto',
            'show_product_image', 'show_barcode', 'auto_focus_product_field',
            'beep_on_scan', 'enable_f2_customer', 'enable_f4_discount',
            'enable_f5_cancel', 'enable_f6_search', 'enable_f9_finish',
            'require_supervisor_cancel', 'log_all_operations',
            'print_company_logo', 'print_customer_copy', 'active',
            'emitir_nfce', 'imprimir_automatico'  # NFC-e e Impressao
        ]
        
        for field in bool_fields:
            data[field] = field in data
        
        # Atualizar PDV
        db.execute_query("""
            UPDATE pdv_settings SET
                pdv_name = %s,
                pdv_number = %s,
                description = %s,
                company_id = %s,
                allow_negative_stock = %s,
                check_stock_realtime = %s,
                show_stock_quantity = %s,
                ask_quantity = %s,
                default_quantity = %s,
                allow_decimal_quantity = %s,
                allow_price_change = %s,
                show_discount_button = %s,
                allow_item_discount = %s,
                allow_total_discount = %s,
                max_discount_percent = %s,
                require_manager_approval = %s,
                require_customer = %s,
                allow_customer_registration = %s,
                require_payment_confirmation = %s,
                allow_multiple_payments = %s,
                print_receipt_auto = %s,
                show_product_image = %s,
                show_barcode = %s,
                auto_focus_product_field = %s,
                beep_on_scan = %s,
                enable_f2_customer = %s,
                enable_f4_discount = %s,
                enable_f5_cancel = %s,
                enable_f6_search = %s,
                enable_f9_finish = %s,
                require_supervisor_cancel = %s,
                log_all_operations = %s,
                printer_name = %s,
                paper_width = %s,
                print_company_logo = %s,
                print_customer_copy = %s,
                active = %s,
                updated_by = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (
            data.get('pdv_name'), data.get('pdv_number'), data.get('description'),
            data.get('company_id') or None,
            data['allow_negative_stock'], data['check_stock_realtime'], data['show_stock_quantity'],
            data['ask_quantity'], data.get('default_quantity', 1.0), data['allow_decimal_quantity'],
            data['allow_price_change'], data['show_discount_button'], data['allow_item_discount'],
            data['allow_total_discount'], data.get('max_discount_percent', 10.0), data['require_manager_approval'],
            data['require_customer'], data['allow_customer_registration'],
            data['require_payment_confirmation'], data['allow_multiple_payments'], data['print_receipt_auto'],
            data['show_product_image'], data['show_barcode'], data['auto_focus_product_field'], data['beep_on_scan'],
            data['enable_f2_customer'], data['enable_f4_discount'], data['enable_f5_cancel'],
            data['enable_f6_search'], data['enable_f9_finish'], data['require_supervisor_cancel'],
            data['log_all_operations'], data.get('printer_name'), data.get('paper_width', 80),
            data['print_company_logo'], data['print_customer_copy'], data['active'],
            user_id, pdv_id
        ))
        
        flash('[OK] PDV atualizado com sucesso!', 'success')
        return redirect(url_for('pdv_config.configuracoes'))
        
    except Exception as e:
        flash(f'[X] Erro ao atualizar PDV: {str(e)}', 'danger')
        return redirect(url_for('pdv_config.editar_pdv', pdv_id=pdv_id))


@pdv_config_bp.route('/pdv/excluir/<int:pdv_id>', methods=['POST'])
@login_required
def excluir_pdv(pdv_id):
    """
    Exclui (desativa) PDV
    """
    db = get_db()
    
    try:
        db.execute_query("""
            UPDATE pdv_settings 
            SET active = FALSE, updated_at = NOW()
            WHERE id = %s
        """, (pdv_id,))
        
        flash('[OK] PDV desativado com sucesso!', 'success')
        return redirect(url_for('pdv_config.configuracoes'))
        
    except Exception as e:
        flash(f'[X] Erro ao excluir PDV: {str(e)}', 'danger')
        return redirect(url_for('pdv_config.configuracoes'))
