"""
Rotas para Controle de Caixa (PDV)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from database import get_db
from datetime import datetime
from functools import wraps

cash_register_bp = Blueprint('cash_register', __name__, url_prefix='/caixa')

# Decorator de login customizado (usando session)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# =====================================================
# LISTAGEM DE CAIXAS
# =====================================================

@cash_register_bp.route('/', methods=['GET'])
@login_required
def cash_register_list():
    """Lista todos os caixas (histórico)"""
    db = get_db()
    
    # Filtros
    status_filter = request.args.get('status', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Query base
    query = """
        SELECT 
            cr.*,
            COUNT(s.id) as total_sales,
            CASE 
                WHEN cr.closed_at IS NOT NULL THEN
                    TIMESTAMPDIFF(MINUTE, cr.opened_at, cr.closed_at)
                ELSE
                    TIMESTAMPDIFF(MINUTE, cr.opened_at, NOW())
            END as minutes_open
        FROM cash_register cr
        LEFT JOIN sales s ON s.cash_register_id = cr.id AND s.status = 'confirmed'
        WHERE 1=1
    """
    
    params = []
    
    if status_filter != 'all':
        query += " AND cr.status = %s"
        params.append(status_filter)
    
    if date_from:
        query += " AND DATE(cr.opened_at) >= %s"
        params.append(date_from)
    
    if date_to:
        query += " AND DATE(cr.opened_at) <= %s"
        params.append(date_to)
    
    query += " GROUP BY cr.id ORDER BY cr.opened_at DESC LIMIT 100"
    
    registers = db.fetch_all(query, tuple(params))
    
    return render_template('cash_register_list.html', 
                          registers=registers,
                          status_filter=status_filter,
                          date_from=date_from,
                          date_to=date_to)

# =====================================================
# CAIXA ATUAL (ABERTO)
# =====================================================

@cash_register_bp.route('/atual', methods=['GET'])
@login_required
def cash_register_current():
    """Mostra o caixa aberto do usuário atual"""
    db = get_db()
    user_id = int(session.get('user_id', 0))
    
    # Buscar caixa aberto do usuário (1 por usuário)
    current_register = db.fetch_one("""
        SELECT 
            cr.*,
            ps.pdv_name,
            ps.pdv_number,
            e.nome_fantasia as empresa_nome
        FROM cash_register cr
        LEFT JOIN pdv_settings ps ON cr.pdv_id = ps.id
        LEFT JOIN empresas e ON cr.empresa_id = e.id
        WHERE cr.user_id = %s AND cr.status = 'open'
        ORDER BY cr.opened_at DESC
        LIMIT 1
    """, (user_id,))
    
    if not current_register:
        flash('Você não possui um caixa aberto. Abra um caixa para começar.', 'info')
        return redirect(url_for('cash_register.cash_register_open'))
    
    # Redirecionar para detalhes do caixa
    return redirect(url_for('cash_register.cash_register_detail', register_id=current_register['id']))

# =====================================================
# ABRIR CAIXA
# =====================================================

@cash_register_bp.route('/abrir', methods=['GET', 'POST'])
@login_required
def cash_register_open():
    """Abrir um novo caixa"""
    db = get_db()
    
    if request.method == 'GET':
        user_id = int(session.get('user_id', 0))
        
        # Verificar se usuário já tem caixa aberto
        user_open_register = db.fetch_one("""
            SELECT id FROM cash_register
            WHERE user_id = %s AND status = 'open'
            LIMIT 1
        """, (user_id,))
        
        if user_open_register:
            flash('Você já possui um caixa aberto! Feche o caixa atual antes de abrir outro.', 'warning')
            return redirect(url_for('cash_register.cash_register_current'))
        
        # Buscar PDVs disponíveis (excluindo os que já têm caixa aberto)
        pdvs = db.fetch_all("""
            SELECT 
                ps.id,
                ps.pdv_name,
                ps.pdv_number,
                ps.company_id,
                e.nome_fantasia as empresa_nome,
                CASE 
                    WHEN cr.id IS NOT NULL THEN 1
                    ELSE 0
                END as tem_caixa_aberto,
                cr.id as caixa_id,
                cr.cashier_name as caixa_operador
            FROM pdv_settings ps
            LEFT JOIN empresas e ON ps.company_id = e.id
            LEFT JOIN cash_register cr ON cr.pdv_id = ps.id AND cr.status = 'open'
            WHERE ps.active = 1
            ORDER BY ps.pdv_number
        """)
        
        return render_template('cash_register_open.html', pdvs=pdvs)
    
    # POST: Processar abertura
    user_id = int(session.get('user_id', 0))
    username = session.get('username', 'Operador')
    
    register_number = request.form.get('register_number', 'Caixa 1')
    opening_balance = float(request.form.get('opening_balance', 0))
    opening_notes = request.form.get('opening_notes', '')
    pdv_id = request.form.get('pdv_id')  # Novo campo
    
    # Se PDV não foi informado, usar PDV padrão (ID 1)
    if not pdv_id:
        pdv_id = 1
    else:
        pdv_id = int(pdv_id)
    
    # Buscar empresa do PDV selecionado
    pdv_info = db.fetch_one("SELECT company_id FROM pdv_settings WHERE id = %s", (pdv_id,))
    empresa_id = pdv_info['company_id'] if pdv_info else None
    
    try:
        from datetime import datetime
        # Verificar se já existe caixa aberto para este usuário
        caixa_aberto = db.fetch_one(
            "SELECT id FROM cash_register WHERE user_id = %s AND status = 'open' LIMIT 1",
            (user_id,)
        )
        if caixa_aberto:
            flash('Você já possui um caixa aberto. Feche-o antes de abrir outro.', 'warning')
            return redirect(url_for('cash_register.cash_register_current'))

        # INSERT direto — sem stored procedure
        cash_register_id = db.insert("""
            INSERT INTO cash_register
                (register_number, user_id, pdv_id, empresa_id, cashier_name,
                 opening_balance, opening_notes, opened_at, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 'open', NOW())
        """, (
            register_number,
            user_id,
            pdv_id,
            empresa_id,
            username,
            opening_balance,
            opening_notes,
        ))

        flash(f'Caixa #{cash_register_id} aberto com sucesso! Valor inicial: R$ {opening_balance:.2f}', 'success')
        return redirect(url_for('cash_register.cash_register_current'))

    except Exception as e:
        flash(f'Erro ao abrir caixa: {str(e)}', 'danger')
        return redirect(url_for('cash_register.cash_register_open'))

# =====================================================
# SANGRIA E SUPRIMENTO
# =====================================================

@cash_register_bp.route('/sangria', methods=['POST'])
@login_required
def cash_register_sangria():
    """Registrar sangria (retirada de dinheiro do caixa)"""
    db = get_db()
    user_id = int(session.get('user_id', 0))
    
    try:
        # Buscar caixa aberto
        caixa = db.fetch_one("""
            SELECT id FROM cash_register
            WHERE user_id = %s AND status = 'open'
            LIMIT 1
        """, (user_id,))
        
        if not caixa:
            return jsonify({
                "success": False,
                "erro": "Nenhum caixa aberto encontrado"
            }), 400
        
        # Obter dados
        valor = float(request.json.get('valor', 0))
        motivo = request.json.get('motivo', '').strip()
        
        if valor <= 0:
            return jsonify({
                "success": False,
                "erro": "Valor deve ser maior que zero"
            }), 400
        
        if not motivo:
            return jsonify({
                "success": False,
                "erro": "Motivo é obrigatório"
            }), 400
        
        # Registrar sangria
        # Sempre valor POSITIVO - a query decide se soma ou subtrai pelo type
        db.insert("""
            INSERT INTO cash_flow
            (date, type, description, amount, bank_account_id, created_at)
            VALUES (CURDATE(), 'expense', %s, %s, 1, NOW())
        """, (f'SANGRIA - {motivo}', abs(valor)))
        
        return jsonify({
            "success": True,
            "mensagem": f"Sangria de R$ {valor:.2f} registrada com sucesso!"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500


@cash_register_bp.route('/suprimento', methods=['POST'])
@login_required
def cash_register_suprimento():
    """Registrar suprimento (adição de dinheiro ao caixa)"""
    db = get_db()
    user_id = int(session.get('user_id', 0))
    
    try:
        # Buscar caixa aberto
        caixa = db.fetch_one("""
            SELECT id FROM cash_register
            WHERE user_id = %s AND status = 'open'
            LIMIT 1
        """, (user_id,))
        
        if not caixa:
            return jsonify({
                "success": False,
                "erro": "Nenhum caixa aberto encontrado"
            }), 400
        
        # Obter dados
        valor = float(request.json.get('valor', 0))
        motivo = request.json.get('motivo', '').strip()
        
        if valor <= 0:
            return jsonify({
                "success": False,
                "erro": "Valor deve ser maior que zero"
            }), 400
        
        if not motivo:
            return jsonify({
                "success": False,
                "erro": "Motivo é obrigatório"
            }), 400
        
        # Registrar suprimento
        db.insert("""
            INSERT INTO cash_flow
            (date, type, description, amount, bank_account_id, created_at)
            VALUES (CURDATE(), 'income', %s, %s, 1, NOW())
        """, (f'SUPRIMENTO - {motivo}', abs(valor)))
        
        return jsonify({
            "success": True,
            "mensagem": f"Suprimento de R$ {valor:.2f} registrado com sucesso!"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500


# =====================================================
# FECHAR CAIXA
# =====================================================

@cash_register_bp.route('/fechar/<int:register_id>', methods=['GET', 'POST'])
@login_required
def cash_register_close(register_id):
    """Fechar o caixa"""
    db = get_db()
    
    # Buscar caixa
    register = db.fetch_one("""
        SELECT * FROM cash_register WHERE id = %s
    """, (register_id,))
    
    if not register:
        flash('Caixa não encontrado!', 'danger')
        return redirect(url_for('cash_register.cash_register_list'))
    
    if register['status'] != 'open':
        flash('Este caixa já está fechado!', 'warning')
        return redirect(url_for('cash_register.cash_register_detail', register_id=register_id))
    
    user_id = int(session.get('user_id', 0))
    if register['user_id'] != user_id:
        flash('Você não pode fechar um caixa de outro usuário!', 'danger')
        return redirect(url_for('cash_register.cash_register_list'))
    
    if request.method == 'GET':
        # Calcular valores esperados
        # Incluir 'dinheiro' além de 'cash' e 'money'
        totals = db.fetch_one("""
            SELECT 
                COALESCE(SUM(CASE WHEN s.payment_method IN ('cash', 'money', 'dinheiro') 
                                  OR pmc.code IN ('cash', 'money') 
                                  THEN s.net_total ELSE 0 END), 0) as cash_total,
                COALESCE(SUM(CASE WHEN s.payment_method IN ('credit_card', 'credito', 'debit_card', 'debito')
                                  OR pmc.code IN ('credit_card', 'debit_card') 
                                  THEN s.net_total ELSE 0 END), 0) as card_total,
                COALESCE(SUM(CASE WHEN s.payment_method NOT IN ('cash', 'money', 'dinheiro', 'credit_card', 'credito', 'debit_card', 'debito', 'pix')
                                  AND (pmc.code IS NULL OR pmc.code NOT IN ('cash', 'money', 'credit_card', 'debit_card', 'pix'))
                                  THEN s.net_total ELSE 0 END), 0) as other_total,
                COALESCE(SUM(s.net_total), 0) as grand_total,
                COUNT(s.id) as total_count
            FROM sales s
            LEFT JOIN payment_methods_config pmc ON pmc.code = s.payment_method
            WHERE s.cash_register_id = %s AND s.status = 'confirmed'
        """, (register_id,))
        
        # Buscar sangrias e suprimentos (MESMA LÓGICA do Caixa Atual)
        movimentacoes = db.fetch_one("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'income' AND description LIKE '%SUPRIMENTO%' 
                                  THEN amount ELSE 0 END), 0) as suprimentos,
                COALESCE(SUM(CASE WHEN type = 'expense' AND description LIKE '%SANGRIA%' 
                                  THEN amount ELSE 0 END), 0) as sangrias
            FROM cash_flow
            WHERE DATE(date) = CURDATE()
        """) or {'suprimentos': 0, 'sangrias': 0}
        
        # Calcular total esperado (MESMA FÓRMULA)
        expected_cash = (
            float(register.get('opening_balance', 0)) + 
            float(totals.get('cash_total', 0)) +
            float(movimentacoes.get('suprimentos', 0)) -
            float(movimentacoes.get('sangrias', 0))
        )
        
        print(f"[FECHAR CAIXA] Abertura: {register.get('opening_balance', 0)}")
        print(f"[FECHAR CAIXA] Vendas: {totals.get('cash_total', 0)}")
        print(f"[FECHAR CAIXA] Suprimentos: {movimentacoes.get('suprimentos', 0)}")
        print(f"[FECHAR CAIXA] Sangrias: {movimentacoes.get('sangrias', 0)}")
        print(f"[FECHAR CAIXA] Esperado: {expected_cash}")
        
        return render_template('cash_register_close.html',
                              register=register,
                              totals=totals,
                              expected_cash=expected_cash,
                              movimentacoes=movimentacoes)
    
    # POST: Processar fechamento
    actual_cash  = float(request.form.get('actual_cash', 0))
    actual_card  = float(request.form.get('actual_card', 0))
    actual_other = float(request.form.get('actual_other', 0))
    closing_notes = request.form.get('closing_notes', '')
    actual_total  = actual_cash + actual_card + actual_other

    try:
        # Calcular totais esperados
        totals = db.fetch_one("""
            SELECT
                COALESCE(SUM(CASE WHEN payment_method IN ('cash','money','dinheiro') THEN net_total ELSE 0 END),0) as cash_total,
                COALESCE(SUM(CASE WHEN payment_method IN ('credit_card','credito','debit_card','debito') THEN net_total ELSE 0 END),0) as card_total,
                COALESCE(SUM(CASE WHEN payment_method NOT IN ('cash','money','dinheiro','credit_card','credito','debit_card','debito','pix') THEN net_total ELSE 0 END),0) as other_total,
                COALESCE(SUM(net_total), 0) as grand_total
            FROM sales WHERE cash_register_id = %s AND status = 'confirmed'
        """, (register_id,)) or {}

        expected_cash  = float(register.get('opening_balance', 0)) + float(totals.get('cash_total', 0))
        expected_card  = float(totals.get('card_total', 0))
        expected_other = float(totals.get('other_total', 0))
        expected_total = expected_cash + expected_card + expected_other
        diff_cash  = actual_cash  - expected_cash
        diff_total = actual_total - expected_total

        # UPDATE direto — sem stored procedure
        db.execute_query("""
            UPDATE cash_register SET
                status          = 'closed',
                closed_at       = NOW(),
                actual_cash     = %s,
                actual_card     = %s,
                actual_other    = %s,
                actual_total    = %s,
                expected_cash   = %s,
                expected_card   = %s,
                expected_other  = %s,
                expected_total  = %s,
                difference_cash = %s,
                difference_total= %s,
                closing_notes   = %s,
                updated_at      = NOW()
            WHERE id = %s
        """, (
            actual_cash, actual_card, actual_other, actual_total,
            expected_cash, expected_card, expected_other, expected_total,
            diff_cash, diff_total,
            closing_notes, register_id
        ))

        flash('Caixa fechado com sucesso!', 'success')
        return redirect(url_for('cash_register.cash_register_detail', register_id=register_id))

    except Exception as e:
        flash(f'Erro ao fechar caixa: {str(e)}', 'danger')
        return redirect(url_for('cash_register.cash_register_close', register_id=register_id))

# =====================================================
# DETALHES DO CAIXA (RELATÓRIO)
# =====================================================

@cash_register_bp.route('/detalhes/<int:register_id>', methods=['GET'])
@login_required
def cash_register_detail(register_id):
    """Visualizar detalhes e relatório do caixa"""
    db = get_db()
    
    # Buscar caixa
    register = db.fetch_one("""
        SELECT * FROM cash_register WHERE id = %s
    """, (register_id,))
    
    if not register:
        flash('Caixa não encontrado!', 'danger')
        return redirect(url_for('cash_register.cash_register_list'))
    
    # Buscar vendas
    sales = db.fetch_all("""
        SELECT 
            s.*,
            c.name as customer_name,
            pmc.name as payment_method_name
        FROM sales s
        LEFT JOIN customers c ON c.id = s.customer_id
        LEFT JOIN payment_methods_config pmc ON pmc.code = s.payment_method
        WHERE s.cash_register_id = %s
        ORDER BY s.sale_date, s.id
    """, (register_id,))

    # Resumo financeiro (esperado)
    sales_summary = db.fetch_one(
        """
        SELECT COALESCE(SUM(s.net_total), 0) AS expected_sales
        FROM sales s
        WHERE s.cash_register_id = %s AND s.status = 'confirmed'
        """,
        (register_id,),
    ) or {'expected_sales': 0}

    expected_sales = float(sales_summary.get('expected_sales') or 0)
    opening_balance = float(register.get('opening_balance') or 0)
    expected_total = opening_balance + expected_sales

    # Injetar no dict do register para o template
    register['expected_sales'] = expected_sales
    register['expected_total'] = expected_total
    
    # Totais por forma de pagamento
    payment_totals = db.fetch_all("""
        SELECT 
            COALESCE(pmc.name, NULLIF(s.payment_method, ''), 'Não informado') as payment_name,
            COUNT(s.id) as quantity,
            SUM(s.net_total) as total
        FROM sales s
        LEFT JOIN payment_methods_config pmc ON pmc.code = s.payment_method
        WHERE s.cash_register_id = %s AND s.status = 'confirmed'
        GROUP BY COALESCE(pmc.name, NULLIF(s.payment_method, ''), 'Não informado')
        ORDER BY total DESC
    """, (register_id,))
    
    return render_template('cash_register_detail.html',
                          register=register,
                          sales=sales,
                          payment_totals=payment_totals)

# =====================================================
# API: Status do Caixa
# =====================================================

@cash_register_bp.route('/api/status', methods=['GET'])
@login_required
def api_cash_register_status():
    """API para verificar status do caixa do usuário"""
    db = get_db()
    user_id = int(session.get('user_id', 0))
    
    register = db.fetch_one("""
        SELECT id, register_number, status, opened_at, opening_balance
        FROM cash_register
        WHERE user_id = %s AND status = 'open'
        LIMIT 1
    """, (user_id,))
    
    if register:
        return jsonify({
            'has_open_register': True,
            'register_id': register['id'],
            'register_number': register['register_number'],
            'opened_at': register['opened_at'].strftime('%Y-%m-%d %H:%M:%S'),
            'opening_balance': float(register['opening_balance'])
        })
    else:
        return jsonify({
            'has_open_register': False
        })

# =====================================================
# SANGRIA (RETIRADA DE DINHEIRO)
# =====================================================

@cash_register_bp.route('/sangria/<int:register_id>', methods=['GET', 'POST'])
@login_required
def cash_register_withdrawal(register_id):
    """Registrar sangria (retirada de dinheiro do caixa)"""
    db = get_db()
    register = db.fetch_one("SELECT * FROM cash_register WHERE id = %s", (register_id,))
    if not register or register['status'] != 'open':
        flash('Caixa não encontrado ou já fechado.', 'danger')
        return redirect(url_for('cash_register.cash_register_list'))

    if request.method == 'POST':
        valor = float(request.form.get('valor', 0))
        motivo = request.form.get('motivo', 'Sangria')
        if valor <= 0:
            flash('Informe um valor válido para a sangria.', 'warning')
        else:
            try:
                db.insert("""
                    INSERT INTO cash_flow (type, amount, description, cash_register_id, created_at)
                    VALUES ('expense', %s, %s, %s, NOW())
                """, (valor, f'SANGRIA — {motivo}', register_id))
                flash(f'Sangria de R$ {valor:.2f} registrada com sucesso!', 'success')
                return redirect(url_for('cash_register.cash_register_detail', register_id=register_id))
            except Exception as e:
                flash(f'Erro ao registrar sangria: {str(e)}', 'danger')

    return render_template('cash_register_sangria.html', register=register)

# =====================================================
# SUPRIMENTO (ADIÇÃO DE DINHEIRO)
# =====================================================

@cash_register_bp.route('/suprimento/<int:register_id>', methods=['GET', 'POST'])
@login_required
def cash_register_supply(register_id):
    """Registrar suprimento (adição de dinheiro ao caixa)"""
    db = get_db()
    register = db.fetch_one("SELECT * FROM cash_register WHERE id = %s", (register_id,))
    if not register or register['status'] != 'open':
        flash('Caixa não encontrado ou já fechado.', 'danger')
        return redirect(url_for('cash_register.cash_register_list'))

    if request.method == 'POST':
        valor = float(request.form.get('valor', 0))
        motivo = request.form.get('motivo', 'Suprimento')
        if valor <= 0:
            flash('Informe um valor válido para o suprimento.', 'warning')
        else:
            try:
                db.insert("""
                    INSERT INTO cash_flow (type, amount, description, cash_register_id, created_at)
                    VALUES ('income', %s, %s, %s, NOW())
                """, (valor, f'SUPRIMENTO — {motivo}', register_id))
                flash(f'Suprimento de R$ {valor:.2f} registrado com sucesso!', 'success')
                return redirect(url_for('cash_register.cash_register_detail', register_id=register_id))
            except Exception as e:
                flash(f'Erro ao registrar suprimento: {str(e)}', 'danger')

    return render_template('cash_register_suprimento.html', register=register)


# =====================================================
# IMPRESSÃO DO RELATÓRIO DE CAIXA
# =====================================================

@cash_register_bp.route('/imprimir/<int:register_id>')
@login_required
def imprimir_relatorio_caixa(register_id):
    """
    Gera e retorna PDF do relatório de fechamento de caixa
    Parâmetro opcional: ?formato=80mm|58mm|A4
    """
    from flask import Response
    
    try:
        from app.services.relatorio_caixa_generator import RelatorioCaixaGenerator
        
        db = get_db()
        
        # Formato pode ser passado como parâmetro ou buscar do PDV
        formato = request.args.get('formato')
        
        if not formato:
            # Buscar formato configurado no PDV
            pdv_id = session.get('pdv_id')
            if pdv_id:
                pdv_config = db.fetch_one("""
                    SELECT formato_impressao FROM pdv_settings WHERE id = %s
                """, (pdv_id,))
                formato = pdv_config.get('formato_impressao', '80mm') if pdv_config else '80mm'
            else:
                formato = '80mm'
        
        if formato not in ['80mm', '58mm', 'A4']:
            formato = '80mm'
        
        # Buscar dados do caixa
        register = db.fetch_one("""
            SELECT cr.*, 
                   u.username as operador_nome,
                   ps.pdv_name,
                   e.nome as empresa_nome,
                   e.cnpj as empresa_cnpj
            FROM cash_register cr
            LEFT JOIN users u ON u.id = cr.user_id
            LEFT JOIN pdv_settings ps ON ps.id = cr.pdv_id
            LEFT JOIN empresas e ON e.id = ps.company_id
            WHERE cr.id = %s
        """, (register_id,))
        
        if not register:
            return jsonify({'success': False, 'error': 'Caixa não encontrado'}), 404
        
        # Buscar totais de vendas por forma de pagamento
        totais = db.fetch_one("""
            SELECT 
                COALESCE(SUM(CASE WHEN s.payment_method IN ('cash', 'money', 'dinheiro') THEN s.net_total ELSE 0 END), 0) as dinheiro,
                COALESCE(SUM(CASE WHEN s.payment_method IN ('credit_card', 'credito') THEN s.net_total ELSE 0 END), 0) as credito,
                COALESCE(SUM(CASE WHEN s.payment_method IN ('debit_card', 'debito') THEN s.net_total ELSE 0 END), 0) as debito,
                COALESCE(SUM(CASE WHEN s.payment_method = 'pix' THEN s.net_total ELSE 0 END), 0) as pix,
                COALESCE(SUM(s.net_total), 0) as total,
                COUNT(s.id) as qtd_vendas
            FROM sales s
            WHERE s.cash_register_id = %s AND s.status = 'confirmed'
        """, (register_id,))
        
        # Buscar movimentações
        movimentacoes = db.fetch_one("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'income' AND description LIKE '%SUPRIMENTO%' THEN amount ELSE 0 END), 0) as suprimentos,
                COALESCE(SUM(CASE WHEN type = 'expense' AND description LIKE '%SANGRIA%' THEN amount ELSE 0 END), 0) as sangrias
            FROM cash_flow
            WHERE DATE(date) = DATE(%s)
        """, (register.get('opened_at'),)) or {'suprimentos': 0, 'sangrias': 0}
        
        # Montar dados para o relatório
        saldo_abertura = float(register.get('opening_balance', 0))
        vendas_dinheiro = float(totais.get('dinheiro', 0))
        suprimentos = float(movimentacoes.get('suprimentos', 0))
        sangrias = float(movimentacoes.get('sangrias', 0))
        
        esperado_dinheiro = saldo_abertura + vendas_dinheiro + suprimentos - sangrias
        esperado_cartao = float(totais.get('credito', 0)) + float(totais.get('debito', 0))
        esperado_outros = float(totais.get('pix', 0))
        
        dados_caixa = {
            'empresa_nome': register.get('empresa_nome', 'EMPRESA'),
            'empresa_cnpj': register.get('empresa_cnpj', ''),
            'caixa_numero': register.get('id'),
            'pdv_nome': register.get('pdv_name', '-'),
            'operador': register.get('operador_nome', '-'),
            'data_abertura': register.get('opened_at').strftime('%d/%m/%Y %H:%M') if register.get('opened_at') else '-',
            'data_fechamento': register.get('closed_at').strftime('%d/%m/%Y %H:%M') if register.get('closed_at') else datetime.now().strftime('%d/%m/%Y %H:%M'),
            'total_vendas': float(totais.get('total', 0)),
            'qtd_vendas': totais.get('qtd_vendas', 0),
            'pagamentos': {
                'Dinheiro': vendas_dinheiro,
                'Crédito': float(totais.get('credito', 0)),
                'Débito': float(totais.get('debito', 0)),
                'PIX': float(totais.get('pix', 0))
            },
            'saldo_abertura': saldo_abertura,
            'suprimentos': suprimentos,
            'sangrias': sangrias,
            'esperado_dinheiro': esperado_dinheiro,
            'conferido_dinheiro': float(register.get('actual_cash', 0)),
            'esperado_cartao': esperado_cartao,
            'conferido_cartao': float(register.get('actual_card', 0)),
            'esperado_outros': esperado_outros,
            'conferido_outros': float(register.get('actual_other', 0)),
            'observacoes': register.get('closing_notes', '')
        }
        
        # Gerar PDF
        generator = RelatorioCaixaGenerator()
        pdf_bytes = generator.gerar_pdf(dados_caixa, formato=formato)
        
        # Retornar como PDF
        response = Response(pdf_bytes, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'inline; filename=Relatorio_Caixa_{register_id}.pdf'
        
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
