from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db

venda_bp = Blueprint('venda', __name__)

# Decorador simples compatível com o restante do projeto
from flask import session

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@venda_bp.route('/vendas/nova', methods=['GET'])
@login_required
def venda_nova():
    """Tela para registrar uma venda (cliente, forma de pagamento, itens pai/filho)."""
    db = get_db()
    
    # Verificar se usuário tem caixa aberto
    user_id = int(session.get('user_id', 0))
    open_register = db.fetch_one("""
        SELECT id, register_number FROM cash_register
        WHERE user_id = %s AND status = 'open'
        LIMIT 1
    """, (user_id,))
    
    if not open_register:
        flash('[AVISO] Você precisa abrir um caixa antes de realizar vendas!', 'warning')
        return redirect('/caixa/abrir')
    
    customers = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE ORDER BY name")
    # Carregar produtos e mapear sale_price com fallback de colunas comuns
    rows = db.fetch_all("SELECT * FROM products WHERE active = TRUE ORDER BY name")
    # Saldo por produto a partir de stock_movements
    mv_rows = db.fetch_all("SELECT product_id, COALESCE(SUM(quantity),0) AS saldo FROM stock_movements GROUP BY product_id")
    saldo_by_pid = {r['product_id']: float(r['saldo'] or 0) for r in (mv_rows or [])}
    products = []
    for r in rows:
        sp = 0.0
        for key in ('sale_price','price_sale','price','unit_price','valor_venda','preco_venda'):
            if key in r and r[key] is not None:
                try:
                    sp = float(r[key])
                    break
                except Exception:
                    pass
        # garantir chaves esperadas pelo front
        r['sale_price'] = sp
        if 'unit_measure' not in r:
            r['unit_measure'] = r.get('um') or r.get('unit') or ''
        if 'product_type' not in r:
            r['product_type'] = r.get('tipo') or 'standalone'
        # saldo inicial em products (se existir) + movimentos
        opening = 0.0
        for k in ('start_stock','opening_stock','initial_stock','estoque_inicial'):
            if k in r and r[k] is not None:
                try:
                    opening = float(r[k]); break
                except Exception:
                    pass
        saldo = opening + saldo_by_pid.get(r.get('id'), 0.0)
        # reduzir payload para chaves usadas
        products.append({
            'id': r.get('id'),
            'name': r.get('name'),
            'product_type': r.get('product_type'),
            'unit_measure': r.get('unit_measure'),
            'sale_price': r.get('sale_price'),
            'stock': saldo
        })
    # Sellers: apenas usuários marcados como vendedores (is_seller=1) e preferencialmente ativos
    try:
        sellers = db.fetch_all(
            """
            SELECT id,
                   COALESCE(full_name, username) AS name
            FROM users
            WHERE is_seller = 1
              AND (COALESCE(status, '') = 'active' OR COALESCE(active, 1) = 1)
            ORDER BY name
            """
        )
    except Exception:
        # Fallback: buscar todos e filtrar em Python
        rows_u = db.fetch_all("SELECT * FROM users")
        sellers = []
        for u in rows_u:
            try:
                if int(u.get('is_seller', 0)) == 1 and (u.get('status') == 'active' or int(u.get('active', 1)) == 1):
                    sellers.append({
                        'id': u.get('id'),
                        'name': u.get('full_name') or u.get('username')
                    })
            except Exception:
                pass
    # BUSCAR FORMAS DE PAGAMENTO DINAMICAMENTE da tabela payment_methods_config
    try:
        payment_methods = db.fetch_all("""
            SELECT 
                code,
                name as label,
                allow_installments,
                max_installments,
                operator_fee_percent,
                days_to_receive,
                financial_behavior
            FROM payment_methods_config
            WHERE active = TRUE
            ORDER BY name
        """)
        # Converter para lista de dicts se necessário
        payment_methods = [dict(pm) for pm in payment_methods] if payment_methods else []
    except Exception as e:
        print(f"[AVISO] Erro ao buscar formas de pagamento: {e}")
        # Fallback para formas antigas se a tabela não existir ainda
        payment_methods = [
            {'code': 'cash', 'label': 'Dinheiro', 'allow_installments': False, 'max_installments': 1},
            {'code': 'pix', 'label': 'PIX', 'allow_installments': False, 'max_installments': 1},
            {'code': 'debit_card', 'label': 'Débito', 'allow_installments': False, 'max_installments': 1},
            {'code': 'credit_card', 'label': 'Crédito', 'allow_installments': False, 'max_installments': 1},
            {'code': 'boleto', 'label': 'Boleto', 'allow_installments': False, 'max_installments': 1},
        ]
    # Edição de rascunho
    sale = None
    sale_items = []
    sale_id = request.args.get('sale_id')
    if sale_id and str(sale_id).isdigit():
        sale = db.fetch_one(
            "SELECT * FROM sales WHERE id = %s",
            (int(sale_id),)
        )
        if sale:
            sale_items = db.fetch_all(
                "SELECT * FROM sale_items WHERE sale_id = %s ORDER BY id",
                (int(sale_id),)
            )
    return render_template('venda_form.html', customers=customers, products=products,
                           payment_methods=payment_methods, sellers=sellers,
                           sale=sale, sale_items=sale_items)

@venda_bp.route('/vendas/pdv', methods=['GET'])
@login_required
def venda_pdv_moderna():
    """PDV Moderno - Interface estilo YZIDRO sem barras de rolagem."""
    db = get_db()
    
    # Verificar se usuário tem caixa aberto e buscar informações do PDV
    user_id = int(session.get('user_id', 0))
    open_register = db.fetch_one("""
        SELECT 
            cr.id, 
            cr.register_number,
            cr.pdv_id,
            cr.empresa_id,
            ps.pdv_name,
            ps.pdv_number,
            e.nome_fantasia as empresa_nome,
            e.logo_path
        FROM cash_register cr
        LEFT JOIN pdv_settings ps ON cr.pdv_id = ps.id
        LEFT JOIN empresas e ON cr.empresa_id = e.id
        WHERE cr.user_id = %s AND cr.status = 'open'
        LIMIT 1
    """, (user_id,))
    
    if not open_register:
        flash('[AVISO] Você precisa abrir um caixa antes de realizar vendas!', 'warning')
        return redirect('/caixa/abrir')
    
    # Usar informações do caixa/PDV aberto
    company_logo = open_register.get('logo_path')
    company_name = open_register.get('empresa_nome', 'PDV')
    pdv_number = open_register.get('pdv_number', 1)
    pdv_name = open_register.get('pdv_name', 'PDV')
    
    print(f"[PDV] Caixa aberto: {open_register.get('register_number')}")
    print(f"[PDV] PDV: {pdv_name} (#{pdv_number})")
    print(f"[PDV] Empresa: {company_name}")
    print(f"[PDV] Logo: {company_logo}")
    
    # Verificar se arquivo de logo existe
    if company_logo:
        import os
        logo_full_path = os.path.join('app', 'static', company_logo)
        if not os.path.exists(logo_full_path):
            print(f"[PDV] AVISO: Arquivo de logo nao existe: {logo_full_path}")
            company_logo = None
    
    # Usar novo template profissional
    from datetime import datetime
    return render_template('venda_pdv_profissional.html', 
                         company_logo=company_logo,
                         company_name=company_name,
                         pdv_number=pdv_number,
                         pdv_name=pdv_name,
                         cash_register_id=open_register.get('id'),
                         now=datetime.now())

@venda_bp.route('/vendas/nova-prototipo', methods=['GET'])
@login_required
def venda_nova_prototipo():
    """Protótipo de tela de vendas com layout moderno, usando dados reais."""
    db = get_db()
    customers = db.fetch_all("SELECT id, name FROM customers WHERE active = TRUE ORDER BY name")
    # Produtos com sale_price e unit_measure
    rows = db.fetch_all("SELECT * FROM products WHERE active = TRUE ORDER BY name")
    products = []
    for r in rows:
        sp = 0.0
        for key in ('sale_price','price_sale','price','unit_price','valor_venda','preco_venda'):
            if key in r and r[key] is not None:
                try:
                    sp = float(r[key])
                    break
                except Exception:
                    pass
        products.append({
            'id': r.get('id'),
            'name': r.get('name'),
            'unit_measure': r.get('unit_measure') or r.get('um') or r.get('unit') or '',
            'sale_price': sp,
            'stock': r.get('stock') or 0
        })
    # Vendedores marcados como is_seller=1
    try:
        sellers = db.fetch_all(
            """
            SELECT id, COALESCE(full_name, username) AS name
            FROM users
            WHERE is_seller = 1
              AND (COALESCE(status, '') = 'active' OR COALESCE(active, 1) = 1)
            ORDER BY name
            """
        )
    except Exception:
        sellers = []
    return render_template('venda_form_prototipo.html', customers=customers, products=products, sellers=sellers)

@venda_bp.route('/vendas', methods=['POST'])
@login_required
def venda_criar():
    """Processa a venda: grava sales e sale_items, cria vínculo customer_products para itens pai.
    TODO: baixa de estoque e financeiro.
    """
    data = request.get_json(silent=True) or request.form
    customer_id = data.get('customer_id')
    payment_method = data.get('payment_method')
    seller_id = data.get('seller_id')
    sale_date = data.get('sale_date')  # yyyy-mm-dd
    sale_type = data.get('sale_type')
    payment_terms = data.get('payment_terms')
    notes = data.get('notes', '')
    delivery_type = data.get('delivery_type')
    delivery_address = data.get('delivery_address')
    delivery_eta = data.get('delivery_eta')
    freight_total = float(data.get('freight_total', 0) or 0)
    tax_total = float(data.get('tax_total', 0) or 0)
    action = data.get('action') or data.get('status')  # 'draft' or 'confirm'
    sale_id_form = data.get('sale_id')

    # Itens podem vir como JSON (request.json) ou como campos form items[index][product_id|qty|unit_price|discount]
    items = []
    if request.is_json and isinstance(data, dict) and 'items' in data:
        items = data.get('items') or []
    else:
        index = 0
        while True:
            pid = data.get(f'items[{index}][product_id]')
            qty = data.get(f'items[{index}][qty]')
            unit_price = data.get(f'items[{index}][unit_price]')
            discount = data.get(f'items[{index}][discount]')
            if pid is None:
                break
            try:
                pid_int = int(pid)
                qty_f = float(qty or 1)
                up_f = float(unit_price or 0)
                disc_f = float(discount or 0)
                items.append({'product_id': pid_int, 'qty': qty_f, 'unit_price': up_f, 'discount': disc_f})
            except Exception:
                pass
            index += 1

    try:
        customer_id = int(customer_id)
    except Exception:
        flash('Cliente inválido.', 'danger')
        return redirect(url_for('venda.venda_nova'))

    if not items:
        flash('Adicione ao menos um item.', 'warning')
        return redirect(url_for('venda.venda_nova'))

    db = get_db()

    # Calcular totais
    gross_total = 0.0
    discount_total = 0.0
    for it in items:
        line_gross = it['qty'] * it.get('unit_price', 0)
        line_disc = line_gross * (float(it.get('discount', 0)) / 100.0)
        gross_total += line_gross
        discount_total += line_disc
    net_total = gross_total - discount_total + freight_total + tax_total

    # Inserir cabeçalho da venda
    # Determinar status inicial
    # Comportamento padrão: confirmar venda (como antes), a menos que venha explicitamente como rascunho
    action_l = (action or '').lower()
    if action_l in ('draft','rascunho','salvar'):
        status = 'draft'
    else:
        status = 'confirmed'

    # Preparar colunas (sale_date pode ser NULL -> NOW() no SQL)
    if not sale_date:
        sale_date_expr = 'NOW()'
        sale_date_param = None
    else:
        sale_date_expr = '%s'
        sale_date_param = sale_date

    # Inserção ou atualização
    prev_status = None
    if sale_id_form and str(sale_id_form).isdigit():
        sid = int(sale_id_form)
        old = db.fetch_one("SELECT status FROM sales WHERE id = %s", (sid,))
        prev_status = old['status'] if old else None
        update_sql = f"""
            UPDATE sales SET
                customer_id=%s,
                sale_date={sale_date_expr},
                payment_method=%s,
                status=%s,
                gross_total=%s,
                discount_total=%s,
                freight_total=%s,
                tax_total=%s,
                net_total=%s,
                seller_id=%s,
                sale_type=%s,
                payment_terms=%s,
                notes=%s,
                delivery_type=%s,
                delivery_address=%s,
                delivery_eta=%s
            WHERE id=%s
        """
        if sale_date_param is None:
            upd_params = [customer_id, payment_method, status, gross_total, discount_total, freight_total, tax_total, net_total,
                          (int(seller_id) if (seller_id not in (None,'') and str(seller_id).isdigit()) else None),
                          sale_type, payment_terms, notes,
                          delivery_type, delivery_address, delivery_eta or None, sid]
        else:
            upd_params = [customer_id, sale_date_param, payment_method, status, gross_total, discount_total, freight_total, tax_total, net_total,
                          (int(seller_id) if (seller_id not in (None,'') and str(seller_id).isdigit()) else None),
                          sale_type, payment_terms, notes,
                          delivery_type, delivery_address, delivery_eta or None, sid]
        db.update(update_sql, tuple(upd_params))
        db.update("DELETE FROM sale_items WHERE sale_id = %s", (sid,))
        sale_id = sid
    else:
        # Buscar caixa aberto do usuário
        from flask import session
        user_id = int(session.get('user_id', 0))
        cash_register_row = db.fetch_one("""
            SELECT id FROM cash_register
            WHERE user_id = %s AND status = 'open'
            LIMIT 1
        """, (user_id,))
        cash_register_id = cash_register_row['id'] if cash_register_row else None
        
        # Montar SQL dinâmico para usar NOW() quando necessário
        insert_sql = f"""
            INSERT INTO sales (
                customer_id, sale_date, payment_method, status,
                gross_total, discount_total, freight_total, tax_total, net_total,
                seller_id, sale_type, payment_terms, notes,
                delivery_type, delivery_address, delivery_eta, cash_register_id
            ) VALUES (
                %s, {sale_date_expr}, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """

        params = [
            customer_id, *( [sale_date_param] if sale_date_param is not None else [] ), payment_method, status,
            gross_total, discount_total, freight_total, tax_total, net_total,
            (int(seller_id) if (seller_id not in (None,'') and str(seller_id).isdigit()) else None),
            sale_type, payment_terms, notes,
            delivery_type, delivery_address, delivery_eta or None, cash_register_id
        ]

        # Se usamos NOW(), removemos o placeholder extra
        if sale_date_param is None:
            # precisamos ajustar a ordem porque não fornecemos sale_date
            params = [customer_id, payment_method, status,
                      gross_total, discount_total, freight_total, tax_total, net_total,
                      (int(seller_id) if (seller_id not in (None,'') and str(seller_id).isdigit()) else None),
                      sale_type, payment_terms, notes,
                      delivery_type, delivery_address, delivery_eta or None, cash_register_id]

        sale_id = db.insert(insert_sql, tuple(params))

    # Validação de saldo (antes de gravar baixa), apenas se vamos confirmar agora
    if status == 'confirmed':
        # quando atualizando, só validar se estava diferente de confirmado
        if prev_status is None or prev_status != 'confirmed':
            insuficientes = []
            for it in items:
                prod_row = db.fetch_one("SELECT * FROM products WHERE id = %s", (it['product_id'],))
                if not prod_row:
                    continue
                # saldo inicial
                opening = 0.0
                for k in ('start_stock','opening_stock','initial_stock','estoque_inicial'):
                    if k in prod_row and prod_row[k] is not None:
                        try:
                            opening = float(prod_row[k]); break
                        except Exception:
                            pass
                # somatório de movimentos
                mv = db.fetch_one("SELECT COALESCE(SUM(quantity),0) AS saldo FROM stock_movements WHERE product_id = %s", (it['product_id'],))
                disp = opening + float(mv['saldo'] or 0)
                if disp - float(it['qty']) < 0:
                    insuficientes.append(f"{prod_row.get('name')} (disp: {disp}, solicitado: {it['qty']})")
            if insuficientes:
                msgs = '; '.join(insuficientes)
                flash(f'Estoque insuficiente para: {msgs}', 'danger')
                # Volta para tela; se estávamos editando rascunho, manter o ID
                if sale_id_form and str(sale_id_form).isdigit():
                    return redirect(url_for('venda.venda_nova', sale_id=int(sale_id_form)))
                return redirect(url_for('venda.venda_nova'))

    # Inserir itens e processar vínculos de produto pai
    for it in items:
        prod = db.fetch_one("SELECT id, name, product_type FROM products WHERE id = %s", (it['product_id'],))
        if not prod:
            # pular itens inválidos
            continue
        line_gross = (it['qty'] * it.get('unit_price', 0))
        line_disc = line_gross * (float(it.get('discount', 0)) / 100.0)
        total_price = line_gross - line_disc
        db.insert(
            """
            INSERT INTO sale_items (
                sale_id, product_id, product_type, product_name_snapshot,
                unit_measure, quantity, unit_price, discount_percent, total_price
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                sale_id, prod['id'], prod.get('product_type'), prod.get('name'),
                None, it['qty'], it.get('unit_price', 0), float(it.get('discount', 0)), total_price
            )
        )

        # Se item é Pai, criar vínculo em customer_products
        if status == 'confirmed' and prod.get('product_type') == 'parent' and (prev_status is None or prev_status != 'confirmed'):
            # Evitar fuso horário do MySQL: enviar a data local pelo app
            from datetime import date
            installed_at = date.today().isoformat()  # YYYY-MM-DD
            cp_id = db.insert(
                """
                INSERT INTO customer_products (customer_id, product_id, serial_number, installed_at, notes)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (customer_id, prod['id'], '', installed_at, f'Vínculo criado pela venda #{sale_id} (pagamento: {payment_method or "n/d"})')
            )

            # Popular status inicial dos insumos (filhos) deste produto pai no cliente
            # last_replacement_at = data da venda; interval em dias (preferir interval_value/unit; fallback interval_days)
            sale_date = installed_at
            children = db.fetch_all(
                """
                SELECT child_product_id,
                       COALESCE(
                         CASE pc.interval_unit
                           WHEN 'hours' THEN pc.interval_value / 24
                           WHEN 'days' THEN pc.interval_value
                           WHEN 'months' THEN pc.interval_value * 30
                           WHEN 'years' THEN pc.interval_value * 365
                           ELSE NULL
                         END,
                         pc.interval_days
                       ) AS eff_interval_days
                FROM product_children pc
                WHERE pc.parent_product_id = %s
                """,
                (prod['id'],)
            )

            for ch in children:
                interval_days = int(ch['eff_interval_days']) if ch['eff_interval_days'] is not None else None
                # Upsert no status do insumo por cliente
                db.update(
                    """
                    INSERT INTO customer_product_children_status
                        (customer_product_id, child_product_id, last_replacement_at, interval_days, next_due_at, notes)
                    VALUES (%s, %s, %s, %s,
                            CASE WHEN %s IS NOT NULL THEN DATE_ADD(%s, INTERVAL %s DAY) ELSE NULL END,
                            %s)
                    ON DUPLICATE KEY UPDATE
                        last_replacement_at = VALUES(last_replacement_at),
                        interval_days = VALUES(interval_days),
                        next_due_at = VALUES(next_due_at)
                    """,
                    (cp_id, ch['child_product_id'], sale_date, interval_days,
                     interval_days, sale_date, interval_days, f'Inicializado pela venda #{sale_id}')
                )

        # Se filho/standalone: TODO baixar estoque futuramente (apenas em confirmed)
    # Helper para também manter coluna denormalizada em products (se existir)
    def _bump_product_stock(pid: int, delta: float):
        for col in ('quantity','stock','on_hand','saldo','estoque','qty'):
            try:
                db.update(f"UPDATE products SET {col} = {col} + %s WHERE id = %s", (delta, pid))
                return True
            except Exception:
                continue
        return False

    # Helper: refletir no saldo consolidado por local (tabela current_stock)
    def _bump_current_stock(pid: int, loc_id: int, delta: float):
        try:
            db.insert(
                """
                INSERT INTO current_stock (product_id, location_id, quantity)
                VALUES (%s,%s,%s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                """,
                (pid, loc_id, delta)
            )
        except Exception:
            try:
                db.update("UPDATE current_stock SET quantity = quantity + %s WHERE product_id = %s AND location_id = %s",
                          (delta, pid, loc_id))
            except Exception:
                pass

    # Baixa de estoque ao confirmar (apenas na transição para confirmado) + log
    if status == 'confirmed' and (prev_status is None or prev_status != 'confirmed'):
        # metadados padrão para movimentos
        from flask import session
        created_by = None
        try:
            created_by = int(session.get('user_id') or 1)
        except Exception:
            created_by = 1
        default_location = 1
        for it in items:
            try:
                # Log de movimento
                db.insert(
                    """
                    INSERT INTO stock_movements
                        (product_id, quantity, movement_type, reference_id, reference_type, created_at,
                         unit_cost, created_by, location_id, notes)
                    VALUES (%s,%s,%s,%s,%s,NOW(), %s, %s, %s, %s)
                    """,
                    (
                        it['product_id'],
                        -abs(float(it['qty'])),
                        'sale_confirm',
                        sale_id,
                        'sale',
                        float(it.get('unit_price', 0) or 0),
                        created_by,
                        default_location,
                        f'Movimento gerado pela venda #{sale_id}'
                    )
                )
                # Ajuste denormalizado no products, se houver coluna
                _bump_product_stock(int(it['product_id']), -abs(float(it['qty'])))
                # Atualizar saldo consolidado do local
                _bump_current_stock(int(it['product_id']), default_location, -abs(float(it['qty'])))
            except Exception:
                pass

    # CORREÇÃO #2: Criar lançamento em Contas a Receber ao confirmar venda
    print(f"\n[DEBUG] Verificando integração financeira...")
    print(f"[DEBUG] Status da venda: {status}")
    print(f"[DEBUG] Status anterior: {prev_status}")
    print(f"[DEBUG] Condição atendida: {status == 'confirmed' and (prev_status is None or prev_status != 'confirmed')}")
    
    if status == 'confirmed' and (prev_status is None or prev_status != 'confirmed'):
        print(f"[DEBUG] Iniciando criacao de contas a receber e fluxo de caixa...")
        try:
            # Calcular data de vencimento baseado em payment_terms
            from datetime import datetime, timedelta
            sale_date_obj = datetime.strptime(sale_date, '%Y-%m-%d') if sale_date else datetime.now()
            
            # Extrair dias do payment_terms (ex: "30 dias", "À vista", etc)
            days_to_add = 0
            if payment_terms:
                import re
                match = re.search(r'(\d+)', payment_terms)
                if match:
                    days_to_add = int(match.group(1))
            
            due_date = (sale_date_obj + timedelta(days=days_to_add)).strftime('%Y-%m-%d')
            
            # Mapear payment_method para valores aceitos pelo ENUM
            payment_method_map = {
                'money': 'cash',
                'cash': 'cash',
                'dinheiro': 'cash',
                'credit': 'credit_card',
                'credit_card': 'credit_card',
                'credito': 'credit_card',
                'debit': 'debit_card',
                'debit_card': 'debit_card',
                'debito': 'debit_card',
                'pix': 'pix',
                'boleto': 'boleto',
                'transfer': 'transfer',
                'transferencia': 'transfer',
                'check': 'check',
                'cheque': 'check'
            }
            
            # Converter para valor aceito ou usar 'other'
            payment_method_converted = payment_method_map.get(
                (payment_method or '').lower(), 
                'other'
            )
            
            print(f"[DEBUG] Inserindo em accounts_receivable...")
            print(f"[DEBUG] customer_id={customer_id}, sale_id={sale_id}, total={net_total}")
            print(f"[DEBUG] payment_method original='{payment_method}' → convertido='{payment_method_converted}'")
            
            receivable_id = db.insert(
                """
                INSERT INTO accounts_receivable 
                (customer_id, sale_id, description, invoice_number, 
                 installments, issue_date, due_date, total_amount, 
                 payment_method, bank_account_id, status, origin, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    customer_id,
                    sale_id,
                    f'Venda #{sale_id} - {payment_method or "Não especificado"}',  # description (NOT NULL)
                    '',  # invoice_number (pode ser vazio)
                    1,   # installments (padrão 1)
                    sale_date or datetime.now().strftime('%Y-%m-%d'),  # issue_date (NOT NULL)
                    due_date,
                    net_total,
                    payment_method_converted,  # payment_method CONVERTIDO para ENUM válido
                    1,   # bank_account_id (padrão 1 - ajuste conforme necessário)
                    'pending',  # status
                    'sale',  # origin
                    f'Lançamento automático da venda #{sale_id}'  # notes
                )
            )
            
            print(f"[DEBUG] Conta a receber criada! ID: {receivable_id}")
            
            # CORREÇÃO ADICIONAL: Criar entrada em cash_flow (SCHEMA CORRETO)
            try:
                print(f"[DEBUG] Inserindo em cash_flow...")
                print(f"[DEBUG] receivable_id={receivable_id}, amount={net_total}")
                
                db.insert(
                    """
                    INSERT INTO cash_flow
                    (date, type, description, amount, bank_account_id, 
                     reference_id, reference_type, chart_account_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        sale_date or datetime.now().strftime('%Y-%m-%d'),  # date (NOT NULL)
                        'income',  # type = income (entrada)
                        f'Venda #{sale_id} - {payment_method or "Não especificado"}',  # description
                        net_total,  # amount
                        1,  # bank_account_id (padrão 1)
                        receivable_id,  # reference_id (ID da conta a receber)
                        'receivable',  # reference_type
                        None  # chart_account_id (pode ser NULL)
                    )
                )
                
                print(f"[DEBUG] Fluxo de caixa criado!")
            except Exception as cf_error:
                import traceback
                print(f"\n{'='*60}")
                print(f"[ERRO] Falha ao criar fluxo de caixa para venda #{sale_id}")
                print(f"Erro: {cf_error}")
                print(f"Traceback completo:")
                traceback.print_exc()
                print(f"{'='*60}\n")
                
        except Exception as e:
            # Log erro DETALHADO mas não bloqueia venda
            import traceback
            print(f"\n{'='*60}")
            print(f"[ERRO] Falha ao criar contas a receber para venda #{sale_id}")
            print(f"Erro: {e}")
            print(f"Traceback completo:")
            traceback.print_exc()
            print(f"{'='*60}\n")
            flash(f'ATENÇÃO: Venda criada mas houve erro ao gerar financeiro: {e}', 'warning')
    else:
        print(f"[DEBUG] [AVISO] Condição NÃO atendida. Financeiro NÃO será criado.")
        print(f"[DEBUG] Motivo: Status={status}, deve ser 'confirmed' E status anterior deve ser diferente de 'confirmed'")

    flash(f'Venda #{sale_id} registrada.', 'success')
    return redirect(url_for('venda.venda_nova'))

@venda_bp.route('/vendas/<int:sale_id>/cancelar', methods=['POST'])
@login_required
def venda_cancelar(sale_id):
    """Cancela a venda e reverte estoque se previamente confirmada/faturada."""
    db = get_db()
    sale = db.fetch_one("SELECT id, status FROM sales WHERE id = %s", (sale_id,))
    if not sale:
        flash('Venda não encontrada.', 'warning')
        return redirect(url_for('venda.vendas_relacao'))

    if sale['status'] == 'cancelled':
        flash('Venda já está cancelada.', 'info')
        return redirect(url_for('venda.venda_detalhe', sale_id=sale_id))

    # Helpers locais
    def _bump_product_stock_local(pid: int, delta: float):
        for col in ('quantity','stock','on_hand','saldo','estoque','qty'):
            try:
                db.update(f"UPDATE products SET {col} = {col} + %s WHERE id = %s", (delta, pid))
                return True
            except Exception:
                continue
        return False

    def _bump_current_stock_local(pid: int, loc_id: int, delta: float):
        try:
            db.insert(
                """
                INSERT INTO current_stock (product_id, location_id, quantity)
                VALUES (%s,%s,%s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                """,
                (pid, loc_id, delta)
            )
        except Exception:
            try:
                db.update("UPDATE current_stock SET quantity = quantity + %s WHERE product_id = %s AND location_id = %s",
                          (delta, pid, loc_id))
            except Exception:
                pass

    # Reverter estoque somente se já tinha baixado (confirmed/invoiced)
    if sale['status'] in ('confirmed', 'invoiced'):
        itens = db.fetch_all("SELECT product_id, quantity FROM sale_items WHERE sale_id = %s", (sale_id,))
        from flask import session
        try:
            created_by = int(session.get('user_id') or 1)
        except Exception:
            created_by = 1
        default_location = 1
        for it in itens:
            try:
                # Inserir movimento positivo (estorno)
                db.insert(
                    """
                    INSERT INTO stock_movements
                        (product_id, quantity, movement_type, reference_id, reference_type, created_at,
                         unit_cost, created_by, location_id, notes)
                    VALUES (%s,%s,%s,%s,%s,NOW(), %s, %s, %s, %s)
                    """,
                    (
                        it['product_id'],
                        abs(float(it['quantity'])),
                        'sale_cancel',
                        sale_id,
                        'sale',
                        0.0,
                        created_by,
                        default_location,
                        f'Estorno gerado pelo cancelamento da venda #{sale_id}'
                    )
                )
                _bump_product_stock_local(int(it['product_id']), abs(float(it['quantity'])))
                _bump_current_stock_local(int(it['product_id']), default_location, abs(float(it['quantity'])))
            except Exception:
                pass

    db.update("UPDATE sales SET status = 'cancelled' WHERE id = %s", (sale_id,))
    flash(f'Venda #{sale_id} cancelada e estoque revertido (quando aplicável).', 'success')
    return redirect(url_for('venda.venda_detalhe', sale_id=sale_id))

@venda_bp.route('/vendas/<int:sale_id>/excluir', methods=['POST'])
@login_required
def venda_excluir_rascunho(sale_id):
    """Exclui uma venda em rascunho (sem efeitos em estoque)."""
    db = get_db()
    sale = db.fetch_one("SELECT id, status FROM sales WHERE id = %s", (sale_id,))
    if not sale:
        flash('Venda não encontrada.', 'warning')
        return redirect(url_for('venda.vendas_relacao'))
    if sale['status'] != 'draft':
        flash('Apenas rascunhos podem ser excluídos. Use cancelar para demais status.', 'warning')
        return redirect(url_for('venda.venda_detalhe', sale_id=sale_id))
    db.update("DELETE FROM sale_items WHERE sale_id = %s", (sale_id,))
    db.update("DELETE FROM sales WHERE id = %s", (sale_id,))
    flash(f'Rascunho #{sale_id} excluído.', 'success')
    return redirect(url_for('venda.vendas_relacao'))

    # Reverter estoque somente se já tinha baixado (confirmed/invoiced)
    if sale['status'] in ('confirmed', 'invoiced'):
        itens = db.fetch_all("SELECT product_id, quantity FROM sale_items WHERE sale_id = %s", (sale_id,))
        for it in itens:
            try:
                from flask import session
                try:
                    created_by = int(session.get('user_id') or 1)
                except Exception:
                    created_by = 1
                default_location = 1
                db.insert(
                    """
                    INSERT INTO stock_movements
                        (product_id, quantity, movement_type, reference_id, reference_type, created_at,
                         unit_cost, created_by, location_id, notes)
                    VALUES (%s,%s,%s,%s,%s,NOW(), %s, %s, %s, %s)
                    """,
                    (
                        it['product_id'],
                        abs(float(it['quantity'])),
                        'sale_cancel',
                        sale_id,
                        'sale',
                        0.0,
                        created_by,
                        default_location,
                        f'Estorno gerado pelo cancelamento da venda #{sale_id}'
                    )
                )
                # Ajuste denormalizado no products, se houver coluna
                _bump_product_stock(int(it['product_id']), abs(float(it['quantity'])))
                # Atualizar saldo consolidado do local
                _bump_current_stock(int(it['product_id']), default_location, abs(float(it['quantity'])))
            except Exception:
                pass

    db.update("UPDATE sales SET status = 'cancelled' WHERE id = %s", (sale_id,))
    flash(f'Venda #{sale_id} cancelada e estoque revertido (quando aplicável).', 'success')
    return redirect(url_for('venda.venda_detalhe', sale_id=sale_id))

@venda_bp.route('/vendas/relacao', methods=['GET'])
@login_required
def vendas_relacao():
    """Lista de vendas com filtros e paginação."""
    db = get_db()
    q = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or '').strip()
    seller_id = (request.args.get('seller_id') or '').strip()
    date_from = (request.args.get('date_from') or '').strip()
    date_to = (request.args.get('date_to') or '').strip()
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = 20

    where = []
    params = []
    if q:
        where.append("(c.name LIKE %s OR s.id = %s)")
        params.extend([f"%{q}%", int(q) if q.isdigit() else 0])
    if status:
        where.append("s.status = %s")
        params.append(status)
    if seller_id and seller_id.isdigit():
        where.append("s.seller_id = %s")
        params.append(int(seller_id))
    if date_from:
        where.append("DATE(s.sale_date) >= %s")
        params.append(date_from)
    if date_to:
        where.append("DATE(s.sale_date) <= %s")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (page - 1) * per_page

    try:
        rows = db.fetch_all(
            f"""
            SELECT s.id, s.sale_date, s.status,
                   s.net_total, s.gross_total, s.discount_total,
                   COALESCE(s.chave_acesso_nfe, '') AS chave_acesso_nfe,
                   COALESCE(s.numero_nfe, '') AS numero_nfe,
                   COALESCE(s.status_nfe, '') AS status_nfe,
                   COALESCE(s.chave_acesso_nfce, '') AS chave_acesso_nfce,
                   COALESCE(s.numero_nfce, '') AS numero_nfce,
                   COALESCE(s.status_nfce, '') AS status_nfce,
                   c.name AS customer_name,
                   u.username AS seller_name
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN users u ON u.id = s.seller_id
            {where_sql}
            ORDER BY s.id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [per_page + 1, offset])
        )
    except Exception as e:
        print(f"[VENDAS] Erro ao listar vendas: {e}")
        flash(f'Erro ao carregar vendas: {e}', 'danger')
        rows = []

    has_next = len(rows) > per_page
    vendas = rows[:per_page]

    try:
        sellers = db.fetch_all(
            "SELECT id, COALESCE(full_name, username) AS name FROM users WHERE is_seller=1 ORDER BY name"
        )
    except Exception:
        sellers = []

    return render_template('venda_list.html', vendas=vendas, q=q, status=status,
                           seller_id=seller_id, date_from=date_from, date_to=date_to,
                           page=page, has_next=has_next, per_page=per_page, sellers=sellers)

@venda_bp.route('/vendas/<int:sale_id>', methods=['GET'])
@login_required
def venda_detalhe(sale_id):
    """Visualização completa da venda (cabeçalho + itens) com dados completos do cliente."""
    db = get_db()
    sale = db.fetch_one(
        """
        SELECT s.*,
               c.name AS customer_name, c.cnpj, c.ie, c.email, c.phone,
               c.address, c.number, c.complement, c.neighborhood, c.city, c.state, c.cep,
               u.username AS seller_name
        FROM sales s
        JOIN customers c ON c.id = s.customer_id
        LEFT JOIN users u ON u.id = s.seller_id
        WHERE s.id = %s
        """,
        (sale_id,)
    )
    if not sale:
        flash('Venda não encontrada.', 'warning')
        return redirect(url_for('venda.vendas_relacao'))
    itens = db.fetch_all(
        """
        SELECT si.*, p.name AS product_name
        FROM sale_items si
        LEFT JOIN products p ON p.id = si.product_id
        WHERE si.sale_id = %s
        ORDER BY si.id
        """,
        (sale_id,)
    )
    return render_template('venda_detail.html', sale=sale, itens=itens)

@venda_bp.route('/vendas/<int:sale_id>/nfe', methods=['GET'])
@login_required
def venda_nfe_dados(sale_id):
    """Busca os dados da NF-e vinculada à venda e retorna como JSON."""
    db = get_db()
    
    # Buscar chave de acesso da venda
    sale = db.fetch_one("SELECT chave_acesso_nfe FROM sales WHERE id = %s", (sale_id,))
    
    if not sale or not sale.get('chave_acesso_nfe'):
        return jsonify({'error': 'NF-e não vinculada a esta venda'}), 404
    
    chave_acesso = sale['chave_acesso_nfe']
    
    # Buscar dados da NF-e
    nfe = db.fetch_one(
        "SELECT * FROM nfe_staging_notas WHERE chave_acesso = %s",
        (chave_acesso,)
    )
    
    if not nfe:
        return jsonify({'error': 'Dados da NF-e não encontrados'}), 404
    
    # Buscar itens da NF-e
    itens_nfe = db.fetch_all(
        "SELECT * FROM nfe_staging_itens WHERE nfe_staging_nota_id = %s ORDER BY numero_item",
        (nfe['id'],)
    )
    
    # Converter para dicionários serializáveis
    nfe_dict = dict(nfe)
    itens_dict = [dict(item) for item in itens_nfe]
    
    return jsonify({
        'nfe': nfe_dict,
        'itens': itens_dict
    })
