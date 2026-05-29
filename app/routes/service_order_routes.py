"""
Rotas para gerenciamento de ordens de serviço.

Antes da solicitação: caso já tenha na versão atual, avance para a próxima.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
from datetime import datetime

from database import get_db
from utils.auth import login_required
from utils.tenant import get_company_id, inject_company_id
from services.notification_service import NotificationService
try:
    from routes.whatsapp_routes import _disparar_wa_automatico as _wa
except Exception:
    _wa = None

try:
    from routes.agenda_routes import calcular_proximo_preventivo as _preventivo
except Exception:
    _preventivo = None

try:
    from utils.estoque_helper import registrar_movimentacao as _baixar_estoque
except Exception:
    _baixar_estoque = None

try:
    from routes.comissao_routes import registrar_comissao_os as _registrar_comissao
except Exception:
    _registrar_comissao = None

try:
    from routes.garantia_routes import registrar_garantia_os as _registrar_garantia
except Exception:
    _registrar_garantia = None

try:
    from utils.audit_log import registrar_audit as _audit
except Exception:
    _audit = None

# Criar o blueprint
service_order_bp = Blueprint('service_order', __name__)


@service_order_bp.route('/service_orders')
@login_required
def service_order_list():
    """Lista todas as ordens de serviço."""
    db = get_db()
    
    # Buscar as ordens de serviço
    company_id = get_company_id()
    orders = db.fetch_all("""
        SELECT so.*, c.name as customer_name, e.name as equipment_name,
               s.name as supply_name, t.name as technician_name
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN supplies s ON so.supply_id = s.id
        LEFT JOIN technicians t ON so.technician_id = t.id
        WHERE so.active = TRUE AND so.company_id = %s
        ORDER BY so.open_date DESC
    """, (company_id,))
    
    return render_template(
        'service_order_list.html',
        orders=orders,
        active_page='service_orders'
    )

# ──────────────────────────────────────────────────────────────────────────────
# APIs JSON — usadas pelo formulário inteligente de OS (AJAX)
# ──────────────────────────────────────────────────────────────────────────────

@service_order_bp.route('/api/clientes/buscar')
@login_required
def api_buscar_cliente():
    """Busca cliente por CPF/CNPJ ou nome (retorna JSON)."""
    db = get_db()
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    # Busca por CPF/CNPJ (apenas dígitos) ou por nome
    q_digits = ''.join(filter(str.isdigit, q))
    results = []
    if q_digits and len(q_digits) >= 3:
        rows = db.fetch_all(
            "SELECT id, name, cnpj, phone, email FROM customers "
            "WHERE active=TRUE AND REPLACE(REPLACE(REPLACE(cnpj,'.',''),'-',''),'/','') LIKE %s "
            "ORDER BY name LIMIT 10",
            (f'%{q_digits}%',)
        )
        results.extend(rows)
    if len(results) < 10:
        rows2 = db.fetch_all(
            "SELECT id, name, cnpj, phone, email FROM customers "
            "WHERE active=TRUE AND name LIKE %s "
            "ORDER BY name LIMIT %s",
            (f'%{q}%', 10 - len(results))
        )
        # evitar duplicatas
        ids_ja = {r['id'] for r in results}
        results.extend(r for r in rows2 if r['id'] not in ids_ja)
    return jsonify([dict(r) for r in results])


@service_order_bp.route('/api/clientes/cadastrar-rapido', methods=['POST'])
@login_required
def api_cadastrar_cliente_rapido():
    """Cadastra cliente mínimo inline (nome + CPF/CNPJ + telefone)."""
    db = get_db()
    data = request.get_json() or {}
    nome  = (data.get('name') or '').strip()
    cpf   = (data.get('cnpj') or '').strip()
    phone = (data.get('phone') or '').strip()
    if not nome:
        return jsonify({'ok': False, 'erro': 'Nome obrigatório'}), 400
    # Evitar duplicata por CPF
    if cpf:
        cpf_digits = ''.join(filter(str.isdigit, cpf))
        existe = db.fetch_one(
            "SELECT id, name FROM customers WHERE "
            "REPLACE(REPLACE(REPLACE(cnpj,'.',''),'-',''),'/','')=%s AND active=TRUE",
            (cpf_digits,)
        )
        if existe:
            return jsonify({'ok': True, 'id': existe['id'], 'name': existe['name'], 'ja_existia': True})
    cid = db.insert(
        "INSERT INTO customers (name, cnpj, phone, address, number, city, state, cep, active) "
        "VALUES (%s,%s,%s,'Não informado','S/N','Não informada','MS','00000-000',TRUE)",
        (nome, cpf or '00.000.000/0000-00', phone)
    )
    if cid:
        return jsonify({'ok': True, 'id': cid, 'name': nome, 'ja_existia': False})
    return jsonify({'ok': False, 'erro': 'Erro ao salvar'}), 500


@service_order_bp.route('/api/veiculos/por-cliente/<int:customer_id>')
@login_required
def api_veiculos_por_cliente(customer_id):
    """Retorna veículos do cliente (para popular o select de veículo)."""
    db = get_db()
    rows = db.fetch_all(
        "SELECT id, name, serial_number as placa, model, manufacturer "
        "FROM equipment WHERE customer_id=%s AND active=TRUE ORDER BY name",
        (customer_id,)
    )
    return jsonify([dict(r) for r in rows])


@service_order_bp.route('/api/veiculos/buscar-placa')
@login_required
def api_buscar_placa():
    """Busca veículo pela placa (serial_number) — retorna cliente vinculado também."""
    db = get_db()
    placa = request.args.get('placa', '').strip().upper()
    if not placa:
        return jsonify(None)
    row = db.fetch_one(
        "SELECT e.id, e.name, e.serial_number as placa, e.model, e.manufacturer, "
        "       e.customer_id, c.name as customer_name, c.cnpj, c.phone "
        "FROM equipment e "
        "LEFT JOIN customers c ON e.customer_id = c.id "
        "WHERE e.serial_number = %s AND e.active=TRUE LIMIT 1",
        (placa,)
    )
    return jsonify(dict(row) if row else None)


@service_order_bp.route('/api/veiculos/cadastrar-rapido', methods=['POST'])
@login_required
def api_cadastrar_veiculo_rapido():
    """Cadastra veículo mínimo inline (placa + modelo + customer_id)."""
    db = get_db()
    data = request.get_json() or {}
    placa       = (data.get('placa') or '').strip().upper()
    modelo      = (data.get('modelo') or '').strip()
    fabricante  = (data.get('fabricante') or '').strip()
    customer_id = data.get('customer_id')
    ano         = data.get('ano') or None
    if not placa or not customer_id:
        return jsonify({'ok': False, 'erro': 'Placa e cliente são obrigatórios'}), 400
    # Checar se placa já existe
    existe = db.fetch_one(
        "SELECT id, name, customer_id FROM equipment WHERE serial_number=%s AND active=TRUE",
        (placa,)
    )
    if existe:
        return jsonify({'ok': True, 'id': existe['id'], 'name': existe['name'],
                        'placa': placa, 'ja_existia': True,
                        'customer_id': existe['customer_id']})
    nome_veiculo = f'{fabricante} {modelo}'.strip() or placa
    vid = db.insert(
        "INSERT INTO equipment (name, serial_number, model, manufacturer, customer_id, installation_date, active) "
        "VALUES (%s,%s,%s,%s,%s,CURDATE(),TRUE)",
        (nome_veiculo, placa, modelo, fabricante, customer_id)
    )
    if vid:
        return jsonify({'ok': True, 'id': vid, 'name': nome_veiculo, 'placa': placa, 'ja_existia': False})
    return jsonify({'ok': False, 'erro': 'Erro ao salvar'}), 500


# ──────────────────────────────────────────────────────────────────────────────

@service_order_bp.route('/service_orders/add', methods=['GET', 'POST'])
@login_required
def service_order_add():
    """Adiciona uma nova ordem de serviço."""
    db = get_db()
    
    if request.method == 'POST':
        import json
        customer_id = request.form.get('customer_id')
        equipment_id = request.form.get('equipment_id')
        order_type = request.form.get('type', 'corrective')
        technician_id = request.form.get('technician_id') or None
        observations = request.form.get('observations', '')
        diagnostico = request.form.get('diagnostico', '')
        complexidade = request.form.get('complexidade', 'medio')
        horas_estimadas = request.form.get('horas_estimadas') or 0
        valor_hora = request.form.get('valor_hora') or 0
        total_mao_obra = request.form.get('total_mao_obra') or 0
        total_pecas = request.form.get('total_pecas') or 0
        desconto = request.form.get('desconto') or 0
        total_geral = request.form.get('total_geral') or 0
        km_entrada = request.form.get('km_entrada') or None
        status_orcamento = request.form.get('status_orcamento', 'rascunho')
        acao = request.form.get('acao', 'salvar')
        pecas_json = request.form.get('pecas_json', '[]')

        if not customer_id or not equipment_id or not order_type:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return redirect(url_for('service_order.service_order_add'))

        if acao == 'enviar':
            status_orcamento = 'enviado'
        elif acao == 'aprovar':
            status_orcamento = 'aprovado'

        today = datetime.now().strftime('%Y%m%d')
        last_order = db.fetch_one("""
            SELECT order_number FROM service_orders
            WHERE order_number LIKE %s
            ORDER BY id DESC LIMIT 1
        """, (f'OS-{today}-%',))
        if last_order:
            last_number = int(last_order['order_number'].split('-')[-1])
            order_number = f'OS-{today}-{last_number + 1:03d}'
        else:
            order_number = f'OS-{today}-001'

        query = """
            INSERT INTO service_orders (
                order_number, customer_id, equipment_id, type, technician_id,
                observations, diagnostico, complexidade, horas_estimadas, valor_hora,
                total_mao_obra, total_pecas, desconto, total_geral,
                km_entrada, status_orcamento
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        params = (
            order_number, customer_id, equipment_id, order_type, technician_id,
            observations, diagnostico, complexidade, horas_estimadas, valor_hora,
            total_mao_obra, total_pecas, desconto, total_geral,
            km_entrada, status_orcamento
        )
        order_id = db.insert(query, params)

        if order_id:
            # Disparo automático WA: alerta admin se OS urgente
            if order_type in ('urgent', 'urgente') and _wa:
                try:
                    _wa(order_id, 'urgente')
                except Exception as _e:
                    print(f'[WA] Erro trigger urgente: {_e}')
            # Salvar itens de peças
            try:
                itens = json.loads(pecas_json)
                for item in itens:
                    if item.get('descricao') and float(item.get('valor_unitario', 0)) > 0:
                        db.insert("""
                            INSERT INTO service_order_items
                            (service_order_id, supply_id, descricao, quantidade, valor_unitario, valor_total, quantity, unit_cost)
                            VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)
                        """, (
                            order_id,
                            item.get('descricao', ''),
                            float(item.get('quantidade', 1)),
                            float(item.get('valor_unitario', 0)),
                            float(item.get('valor_total', 0)),
                            float(item.get('quantidade', 1)),
                            float(item.get('valor_unitario', 0))
                        ))
            except Exception as e:
                print(f'[OS] Erro ao salvar itens: {e}')

            if _audit:
                _audit('service_orders', order_id, 'create',
                       dados_depois={'order_number': order_number, 'status': 'open'})
            flash(f'OS {order_number} salva com sucesso!', 'success')
            return redirect(url_for('service_order.service_order_view', order_id=order_id))
        else:
            flash('Erro ao cadastrar ordem de serviço.', 'danger')
    
    company_id = get_company_id()
    customers = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE AND company_id = %s
        ORDER BY name
    """, (company_id,))
            
    equipments = db.fetch_all("""
        SELECT id, name, customer_id FROM equipment
        WHERE active = TRUE AND company_id = %s
        ORDER BY name
    """, (company_id,))
    
    supplies = db.fetch_all("""
        SELECT id, name FROM supplies
        WHERE active = TRUE
        ORDER BY name
    """)
    
    maintenance_plans = db.fetch_all("""
        SELECT id, task, customer_id, equipment_id FROM maintenance_plans
        WHERE active = TRUE
        ORDER BY id DESC
    """)
    
    technicians = db.fetch_all("""
        SELECT id, name, specialty FROM technicians
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    return render_template(
        'service_order_form.html',
        customers=customers,
        equipments=equipments,
        supplies=supplies,
        maintenance_plans=maintenance_plans,
        technicians=technicians,
        order=None,
        active_page='service_orders'
    )

@service_order_bp.route('/service_orders/edit/<int:order_id>', methods=['GET', 'POST'])
@login_required
def service_order_edit(order_id):
    """Edita uma ordem de serviço existente."""
    db = get_db()
    
    # Buscar a ordem de serviço
    order = db.fetch_one("""
        SELECT * FROM service_orders
        WHERE id = %s
    """, (order_id,))
    
    if not order:
        flash('Ordem de serviço não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))
    
    # Verificar se a ordem de serviço pode ser editada
    if order['status'] == 'completed' or order['status'] == 'canceled':
        flash('Não é possível editar uma ordem de serviço concluída ou cancelada.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    
    if request.method == 'POST':
        # Obter dados do formulário
        _tech_raw = request.form.get('technician_id', '').strip()
        try:
            technician_id = int(_tech_raw) if _tech_raw else None
        except (ValueError, TypeError):
            technician_id = None
        # Garantir que o técnico existe antes de salvar (evita FK violation)
        if technician_id:
            _tech_exists = db.fetch_one("SELECT id FROM users WHERE id=%s", (technician_id,))
            if not _tech_exists:
                technician_id = None
        status = request.form.get('status')
        observations = request.form.get('observations')
        downtime_minutes = request.form.get('downtime_minutes') or 0
        
        # Validar dados
        if not status:
            flash('Por favor, selecione um status para a ordem de serviço.', 'danger')
            return redirect(url_for('service_order.service_order_edit', order_id=order_id))
        
        try:
            downtime_minutes = int(downtime_minutes)
            if downtime_minutes < 0:
                raise ValueError("Tempo de parada deve ser positivo")
        except ValueError:
            flash('O tempo de parada deve ser um número inteiro positivo.', 'danger')
            return redirect(url_for('service_order.service_order_edit', order_id=order_id))
        
        # Verificar se a ordem está sendo concluída
        completion_date = None
        if status == 'completed' and order['status'] != 'completed':
            completion_date = datetime.now()
            
        # Verificar se um técnico está sendo atribuído
        is_technician_assigned = False
        if technician_id and not order['technician_id']:
            is_technician_assigned = True
        
        # Atualizar ordem de serviço no banco de dados
        query = """
            UPDATE service_orders
            SET technician_id = %s, status = %s, observations = %s,
                downtime_minutes = %s, completion_date = %s
            WHERE id = %s
        """
        params = (
            technician_id, status, observations,
            downtime_minutes, completion_date, order_id
        )
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Ordem de serviço atualizada com sucesso!', 'success')
            
            # Criar alerta se a OS foi concluída
            if status == 'completed' and order['status'] != 'completed':
                NotificationService.create_alert(
                    equipment_id=order['equipment_id'],
                    supply_id=order['supply_id'],
                    alert_type='os_completed',
                    message=f'Ordem de serviço {order["order_number"]} concluída.',
                    priority='medium'
                )
                # Disparo automático WA: OS pronta para retirada
                if _wa:
                    try:
                        _wa(order_id, 'concluido')
                    except Exception as _e:
                        print(f'[WA] Erro trigger concluido: {_e}')
                # Preventivo automático: atualiza next_maintenance do veículo
                if _preventivo:
                    try:
                        _preventivo(order_id)
                    except Exception as _e:
                        print(f'[AGENDA] Erro trigger preventivo: {_e}')

                # Baixa automática de estoque: itens da OS com supply_id ou produto_id
                if _baixar_estoque:
                    try:
                        itens_os = db.fetch_all("""
                            SELECT supply_id, produto_id, quantidade, quantity, descricao
                            FROM service_order_items
                            WHERE service_order_id = %s
                        """, (order_id,))
                        for item in (itens_os or []):
                            pid = item.get('produto_id') or item.get('supply_id')
                            qty = float(item.get('quantidade') or item.get('quantity') or 0)
                            if pid and qty > 0:
                                _baixar_estoque(
                                    produto_id=int(pid),
                                    tipo='saida',
                                    quantidade=qty,
                                    origem_tela='OS',
                                    referencia_tipo='os',
                                    referencia_id=order_id,
                                    referencia_codigo=order.get('order_number', ''),
                                    observacao=f'Baixa automática ao concluir OS {order.get("order_number","")}'
                                )
                    except Exception as _e:
                        print(f'[ESTOQUE] Erro baixa automática OS {order_id}: {_e}')

                # Comissão automática do mecânico
                if _registrar_comissao:
                    try:
                        _registrar_comissao(order_id)
                    except Exception as _e:
                        print(f'[COMISSAO] Erro ao registrar comissão OS {order_id}: {_e}')

                # Garantia automática (90 dias padrão)
                if _registrar_garantia:
                    try:
                        _registrar_garantia(order_id, prazo_dias=90)
                    except Exception as _e:
                        print(f'[GARANTIA] Erro ao registrar garantia OS {order_id}: {_e}')

            # Criar alerta se um técnico foi atribuído
            if is_technician_assigned:
                # Buscar o nome do técnico
                technician = db.fetch_one("SELECT name FROM technicians WHERE id = %s", (technician_id,))
                technician_name = technician['name'] if technician else 'Desconhecido'
                
                NotificationService.create_alert(
                    equipment_id=order['equipment_id'],
                    supply_id=order['supply_id'],
                    alert_type='os_assigned',
                    message=f'Técnico {technician_name} atribuído à ordem de serviço {order["order_number"]}.',
                    priority='medium'
                )
            
            return redirect(url_for('service_order.service_order_view', order_id=order_id))
        else:
            flash('Erro ao atualizar ordem de serviço.', 'danger')
    
    # Buscar técnicos para o formulário
    technicians = db.fetch_all("""
        SELECT id, name, specialty FROM technicians
        WHERE active = TRUE AND status = 'active'
        ORDER BY name
    """)
    
    return render_template(
        'service_order_edit.html',
        order=order,
        technicians=technicians,
        active_page='service_orders'
    )

@service_order_bp.route('/service_orders/view/<int:order_id>')
@login_required
def service_order_view(order_id):
    """Visualiza uma ordem de serviço."""
    db = get_db()
    
    # Buscar a ordem de serviço
    order = db.fetch_one("""
        SELECT so.*, c.name as customer_name, c.phone as customer_phone,
               e.name as equipment_name, e.serial_number as placa,
               e.manufacturer as fabricante, e.model as modelo,
               t.name as technician_name
        FROM service_orders so
        LEFT JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN technicians t ON so.technician_id = t.id
        WHERE so.id = %s
    """, (order_id,))
    
    if not order:
        flash('Ordem de serviço não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))
    
    # Buscar itens da ordem de serviço
    items = db.fetch_all("""
        SELECT i.*, s.name as supply_name
        FROM service_order_items i
        LEFT JOIN supplies s ON i.supply_id = s.id
        WHERE i.service_order_id = %s
    """, (order_id,))

    # Buscar horas trabalhadas (tabela legada)
    labor = []
    try:
        labor = db.fetch_all("""
            SELECT l.*, t.name as technician_name
            FROM service_order_labor l
            LEFT JOIN technicians t ON l.technician_id = t.id
            WHERE l.service_order_id = %s
        """, (order_id,))
    except Exception:
        pass

    # Calcular totais (fallback se campos novos ainda não existem)
    total_items = sum(
        float(i.get('valor_total') or (float(i.get('quantidade') or i.get('quantity') or 1) * float(i.get('valor_unitario') or i.get('unit_cost') or 0)))
        for i in items
    )
    total_labor = sum(float(l.get('hours_worked', 0)) * float(l.get('hourly_rate', 0)) for l in labor)
    total_cost = float(order.get('total_geral') or 0) or (total_items + total_labor)

    return render_template(
        'service_order_view.html',
        order=order,
        items=items,
        labor=labor,
        total_items=total_items,
        total_labor=total_labor,
        total_cost=total_cost,
    )

@service_order_bp.route('/service_orders/add_item/<int:order_id>', methods=['POST'])
@login_required
def service_order_add_item(order_id):
    """Adiciona um item a uma ordem de serviço."""
    db = get_db()
    
    # Verificar se a ordem de serviço existe e pode ser editada
    order = db.fetch_one("""
        SELECT * FROM service_orders
        WHERE id = %s
    """, (order_id,))
    
    if not order:
        flash('Ordem de serviço não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))
    
    if order['status'] == 'completed' or order['status'] == 'canceled':
        flash('Não é possível adicionar itens a uma ordem de serviço concluída ou cancelada.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    
    # Obter dados do formulário
    supply_id = request.form.get('supply_id')
    quantity = request.form.get('quantity')
    unit_cost = request.form.get('unit_cost')
    
    # Validar dados
    if not supply_id or not quantity or not unit_cost:
        flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    
    try:
        quantity = int(quantity)
        unit_cost = float(unit_cost)
        if quantity <= 0 or unit_cost < 0:
            raise ValueError("Valores devem ser positivos")
    except ValueError:
        flash('Quantidade e custo unitário devem ser números positivos.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    
    # Inserir item no banco de dados
    query = """
        INSERT INTO service_order_items
        (service_order_id, supply_id, quantity, unit_cost)
        VALUES (%s, %s, %s, %s)
    """
    params = (order_id, supply_id, quantity, unit_cost)
    
    item_id = db.insert(query, params)
    
    if item_id:
        # Atualizar estoque
        db.update("""
            UPDATE supplies
            SET stock = stock - %s
            WHERE id = %s
        """, (quantity, supply_id))
        
        flash('Item adicionado com sucesso!', 'success')
    else:
        flash('Erro ao adicionar item.', 'danger')
    
    return redirect(url_for('service_order.service_order_view', order_id=order_id))

@service_order_bp.route('/service_orders/add_labor/<int:order_id>', methods=['POST'])
@login_required
def service_order_add_labor(order_id):
    """Adiciona horas trabalhadas a uma ordem de serviço."""
    db = get_db()
    
    # Verificar se a ordem de serviço existe e pode ser editada
    order = db.fetch_one("""
        SELECT * FROM service_orders
        WHERE id = %s
    """, (order_id,))
    
    if not order:
        flash('Ordem de serviço não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))
    
    if order['status'] == 'completed' or order['status'] == 'canceled':
        flash('Não é possível adicionar horas trabalhadas a uma ordem de serviço concluída ou cancelada.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    
    # Obter dados do formulário
    technician_id = request.form.get('technician_id')
    hours_worked = request.form.get('hours_worked')
    hourly_rate = request.form.get('hourly_rate')
    
    # Validar dados
    if not technician_id or not hours_worked or not hourly_rate:
        flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    
    try:
        hours_worked = float(hours_worked)
        hourly_rate = float(hourly_rate)
        if hours_worked <= 0 or hourly_rate < 0:
            raise ValueError("Valores devem ser positivos")
    except ValueError:
        flash('Horas trabalhadas e taxa horária devem ser números positivos.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    
    # Inserir horas trabalhadas no banco de dados
    query = """
        INSERT INTO service_order_labor
        (service_order_id, technician_id, hours_worked, hourly_rate)
        VALUES (%s, %s, %s, %s)
    """
    params = (order_id, technician_id, hours_worked, hourly_rate)
    
    labor_id = db.insert(query, params)
    
    if labor_id:
        flash('Horas trabalhadas adicionadas com sucesso!', 'success')
    else:
        flash('Erro ao adicionar horas trabalhadas.', 'danger')
    
    return redirect(url_for('service_order.service_order_view', order_id=order_id))

@service_order_bp.route('/service_orders/cancel/<int:order_id>', methods=['POST'])
@login_required
def service_order_cancel(order_id):
    """Cancela uma ordem de serviço."""
    db = get_db()
    
    # Verificar se a ordem de serviço existe e pode ser cancelada
    order = db.fetch_one("""
        SELECT * FROM service_orders
        WHERE id = %s
    """, (order_id,))
    
    if not order:
        flash('Ordem de serviço não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))
    
    if order['status'] == 'completed':
        flash('Não é possível cancelar uma ordem de serviço concluída.', 'danger')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    
    if order['status'] == 'canceled':
        flash('Esta ordem de serviço já está cancelada.', 'warning')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    
    # Cancelar a ordem de serviço
    affected_rows = db.update("""
        UPDATE service_orders
        SET status = 'canceled'
        WHERE id = %s
    """, (order_id,))
    
    if affected_rows > 0:
        # Devolver itens ao estoque
        items = db.fetch_all("""
            SELECT supply_id, quantity
            FROM service_order_items
            WHERE service_order_id = %s
        """, (order_id,))
        
        for item in items:
            db.update("""
                UPDATE supplies
                SET stock = stock + %s
                WHERE id = %s
            """, (item['quantity'], item['supply_id']))
        
        if _audit:
            _audit('service_orders', order_id, 'cancel',
                   dados_antes={'status': order.get('status')},
                   dados_depois={'status': 'canceled'})
        flash('Ordem de serviço cancelada com sucesso!', 'success')
    else:
        flash('Erro ao cancelar ordem de serviço.', 'danger')
    
    return redirect(url_for('service_order.service_order_view', order_id=order_id))

# ─────────────────────────────────────────────────────────────
# ITEM 3 — Controle início / fim do serviço pelo mecânico
# ─────────────────────────────────────────────────────────────

@service_order_bp.route('/service_orders/<int:order_id>/iniciar', methods=['POST'])
@login_required
def service_order_iniciar(order_id):
    """Mecânico inicia o serviço — registra data_inicio_servico."""
    db = get_db()
    order = db.fetch_one("SELECT * FROM service_orders WHERE id = %s", (order_id,))
    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))
    if order.get('data_inicio_servico'):
        flash('Serviço já foi iniciado.', 'warning')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))
    db.update("""
        UPDATE service_orders
        SET data_inicio_servico = NOW(), status = 'in_progress'
        WHERE id = %s
    """, (order_id,))
    flash(f'Serviço da OS {order["order_number"]} iniciado! Cronômetro ativo.', 'success')
    return redirect(url_for('service_order.service_order_view', order_id=order_id))


@service_order_bp.route('/service_orders/<int:order_id>/finalizar', methods=['POST'])
@login_required
def service_order_finalizar(order_id):
    """Mecânico finaliza o serviço — registra data_fim_servico e calcula tempo real."""
    db = get_db()
    order = db.fetch_one("SELECT * FROM service_orders WHERE id = %s", (order_id,))
    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))
    if order.get('data_fim_servico'):
        flash('Serviço já foi finalizado.', 'warning')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    db.update("""
        UPDATE service_orders
        SET data_fim_servico = NOW(), status = 'completed', completion_date = NOW()
        WHERE id = %s
    """, (order_id,))

    # Lançar automaticamente em Contas a Receber se orçamento aprovado
    _lancar_contas_receber(db, order)

    flash(f'OS {order["order_number"]} concluída! Financeiro atualizado.', 'success')
    return redirect(url_for('service_order.service_order_view', order_id=order_id))


# ─────────────────────────────────────────────────────────────
# ITEM 5 — Lançamento automático em Contas a Receber
# ─────────────────────────────────────────────────────────────

def _lancar_contas_receber(db, order):
    """Cria lançamento em accounts_receivable quando OS é aprovada/concluída."""
    try:
        order_id = order['id']
        total = float(order.get('total_geral') or 0)
        if total <= 0:
            return

        # Verifica se já existe lançamento para esta OS
        existente = db.fetch_one(
            "SELECT id FROM accounts_receivable WHERE notes LIKE %s AND active = TRUE",
            (f'%OS-{order["order_number"]}%',)
        )
        if existente:
            return

        from datetime import date, timedelta
        vencimento = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')

        db.insert("""
            INSERT INTO accounts_receivable
            (customer_id, total_amount, due_date, status, description, notes,
             payment_method, origin, issue_date, installments)
            VALUES (%s, %s, %s, 'pending', %s, %s, 'pix', 'service', CURDATE(), 1)
        """, (
            order.get('customer_id'),
            total,
            vencimento,
            f'OS {order["order_number"]} — Serviço mecânico',
            f'Lançamento automático — OS-{order["order_number"]} | Total: R$ {total:.2f}'
        ))
    except Exception as e:
        print(f'[OS] Erro ao lançar C/R: {e}')


@service_order_bp.route('/service_orders/<int:order_id>/aprovar', methods=['POST'])
@login_required
def service_order_aprovar(order_id):
    """Marca orçamento como aprovado e lança em C/R."""
    db = get_db()
    order = db.fetch_one("SELECT * FROM service_orders WHERE id = %s", (order_id,))
    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))

    db.update("""
        UPDATE service_orders SET status_orcamento = 'aprovado', status = 'in_progress'
        WHERE id = %s
    """, (order_id,))

    _lancar_contas_receber(db, order)
    flash(f'OS {order["order_number"]} aprovada! Lançada em Contas a Receber.', 'success')
    return redirect(url_for('service_order.service_order_view', order_id=order_id))


# ─────────────────────────────────────────────────────────────
# ITEM 4 — Histórico do veículo (todas OS por equipment_id)
# ─────────────────────────────────────────────────────────────

@service_order_bp.route('/veiculos/<int:equipment_id>/historico')
@login_required
def veiculo_historico(equipment_id):
    """Histórico completo de OS de um veículo."""
    db = get_db()
    veiculo = db.fetch_one("""
        SELECT e.*, c.name as customer_name, c.phone as customer_phone
        FROM equipment e
        LEFT JOIN customers c ON c.id = e.customer_id
        WHERE e.id = %s
    """, (equipment_id,))
    if not veiculo:
        flash('Veículo não encontrado.', 'danger')
        return redirect(url_for('equipamento.equipamentos'))

    historico = db.fetch_all("""
        SELECT so.*,
               t.name as technician_name,
               TIMESTAMPDIFF(MINUTE, so.data_inicio_servico, so.data_fim_servico) as minutos_servico
        FROM service_orders so
        LEFT JOIN technicians t ON t.id = so.technician_id
        WHERE so.equipment_id = %s
        ORDER BY so.open_date DESC
    """, (equipment_id,))

    # Totais do veículo
    total_gasto = sum(float(o.get('total_geral') or 0) for o in historico)
    total_os = len(historico)
    os_concluidas = sum(1 for o in historico if o['status'] == 'completed')

    return render_template('veiculo_historico.html',
        veiculo=veiculo,
        historico=historico,
        total_gasto=total_gasto,
        total_os=total_os,
        os_concluidas=os_concluidas
    )


# ─────────────────────────────────────────────────────────────
# ITEM 2 — Orçamento avulso (sem cliente cadastrado)
# ─────────────────────────────────────────────────────────────

@service_order_bp.route('/service_orders/avulso', methods=['GET', 'POST'])
@login_required
def service_order_avulso():
    """Abre OS/Orçamento avulso para cliente sem cadastro."""
    db = get_db()

    if request.method == 'POST':
        import json
        # Dados do cliente eventual (sem cadastro)
        nome_eventual = request.form.get('nome_eventual', 'Cliente Eventual')
        phone_eventual = request.form.get('phone_eventual', '')

        # Garantir que existe o cliente "eventual" genérico
        cliente_eventual = db.fetch_one(
            "SELECT id FROM customers WHERE cnpj = '00.000.000/0000-00' LIMIT 1"
        )
        if not cliente_eventual:
            customer_id = db.insert("""
                INSERT INTO customers
                    (name, cnpj, phone, address, number, city, state, cep, active)
                VALUES ('Cliente Eventual', '00.000.000/0000-00', '', 'Sem endereco', 'S/N', 'Campo Grande', 'MS', '00000-000', TRUE)
            """, ())
        else:
            customer_id = cliente_eventual['id']

        # Garantir veículo avulso
        placa_eventual = request.form.get('placa_eventual', 'SEM-PLACA')
        veiculo_eventual = db.fetch_one(
            "SELECT id FROM equipment WHERE serial_number = %s LIMIT 1", (placa_eventual,)
        )
        if not veiculo_eventual:
            equipment_id = db.insert("""
                INSERT INTO equipment (name, serial_number, customer_id, installation_date, active)
                VALUES (%s, %s, %s, CURDATE(), TRUE)
            """, (f'{nome_eventual} — {placa_eventual}', placa_eventual, customer_id))
        else:
            equipment_id = veiculo_eventual['id']

        order_type = request.form.get('type', 'corrective')
        observations = request.form.get('observations', '')
        diagnostico = request.form.get('diagnostico', '')
        complexidade = request.form.get('complexidade', 'medio')
        horas_estimadas = request.form.get('horas_estimadas') or 0
        valor_hora = request.form.get('valor_hora') or 120
        total_mao_obra = request.form.get('total_mao_obra') or 0
        total_pecas = request.form.get('total_pecas') or 0
        desconto = request.form.get('desconto') or 0
        total_geral = request.form.get('total_geral') or 0
        km_entrada = request.form.get('km_entrada') or None
        pecas_json = request.form.get('pecas_json', '[]')

        today = datetime.now().strftime('%Y%m%d')
        last_order = db.fetch_one("""
            SELECT order_number FROM service_orders
            WHERE order_number LIKE %s ORDER BY id DESC LIMIT 1
        """, (f'OS-{today}-%',))
        if last_order:
            last_number = int(last_order['order_number'].split('-')[-1])
            order_number = f'OS-{today}-{last_number + 1:03d}'
        else:
            order_number = f'OS-{today}-001'

        # Adicionar nota com nome/phone do cliente eventual nas observações
        obs_final = f'[Cliente: {nome_eventual} | Tel: {phone_eventual}]\n{observations}'

        order_id = db.insert("""
            INSERT INTO service_orders
            (order_number, customer_id, equipment_id, type, observations,
             diagnostico, complexidade, horas_estimadas, valor_hora,
             total_mao_obra, total_pecas, desconto, total_geral,
             km_entrada, status_orcamento)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'rascunho')
        """, (order_number, customer_id, equipment_id, order_type, obs_final,
              diagnostico, complexidade, horas_estimadas, valor_hora,
              total_mao_obra, total_pecas, desconto, total_geral, km_entrada))

        if order_id:
            try:
                itens = json.loads(pecas_json)
                for item in itens:
                    if item.get('descricao') and float(item.get('valor_unitario', 0)) > 0:
                        db.insert("""
                            INSERT INTO service_order_items
                            (service_order_id, supply_id, descricao, quantidade,
                             valor_unitario, valor_total, quantity, unit_cost)
                            VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)
                        """, (order_id, item['descricao'],
                              float(item.get('quantidade', 1)),
                              float(item.get('valor_unitario', 0)),
                              float(item.get('valor_total', 0)),
                              float(item.get('quantidade', 1)),
                              float(item.get('valor_unitario', 0))))
            except Exception as e:
                print(f'[OS Avulsa] Erro itens: {e}')

            flash(f'OS Avulsa {order_number} criada!', 'success')
            return redirect(url_for('service_order.service_order_view', order_id=order_id))
        else:
            flash('Erro ao criar OS avulsa.', 'danger')

    technicians = db.fetch_all(
        "SELECT id, name FROM technicians WHERE active = TRUE ORDER BY name"
    )
    return render_template('service_order_avulso.html', technicians=technicians)


# ─────────────────────────────────────────────────────────────
# ITEM 1 — PDF / Impressão da OS (Prisma de Diagnóstico)
# ─────────────────────────────────────────────────────────────

@service_order_bp.route('/service_orders/<int:order_id>/pdf')
@login_required
def service_order_pdf(order_id):
    """Gera PDF da OS (Prisma de Diagnóstico) — usa WeasyPrint se disponível, senão HTML imprimível."""
    db = get_db()
    order = db.fetch_one("""
        SELECT so.*,
               c.name as customer_name, c.phone as customer_phone,
               c.cnpj as customer_doc,
               e.name as equipment_name, e.serial_number as placa,
               e.manufacturer as fabricante, e.model as modelo,
               t.name as technician_name
        FROM service_orders so
        LEFT JOIN customers c ON c.id = so.customer_id
        LEFT JOIN equipment e ON e.id = so.equipment_id
        LEFT JOIN technicians t ON t.id = so.technician_id
        WHERE so.id = %s
    """, (order_id,))

    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))

    itens = db.fetch_all("""
        SELECT descricao, quantidade, valor_unitario, valor_total
        FROM service_order_items
        WHERE service_order_id = %s
    """, (order_id,))

    # Tenta WeasyPrint para PDF real
    try:
        from weasyprint import HTML
        from flask import make_response
        html_str = render_template('service_order_pdf.html', order=order, itens=itens)
        pdf = HTML(string=html_str).write_pdf()
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=OS-{order["order_number"]}.pdf'
        return response
    except ImportError:
        # Sem WeasyPrint: retorna HTML com CSS @media print
        return render_template('service_order_pdf.html', order=order, itens=itens)


@service_order_bp.route('/service_orders/dashboard')
@login_required
def service_order_dashboard():
    """Dashboard de ordens de serviço."""
    db = get_db()
    
    # Estatísticas de ordens de serviço
    stats = db.fetch_one("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
            SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_count,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
            SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END) as canceled_count
        FROM service_orders
        WHERE active = TRUE
    """)
    
    # Ordens de serviço por tipo
    by_type = db.fetch_all("""
        SELECT type, COUNT(*) as count
        FROM service_orders
        WHERE active = TRUE
        GROUP BY type
    """)
    
    # Ordens de serviço por cliente (top 5)
    by_customer = db.fetch_all("""
        SELECT c.name as customer_name, COUNT(*) as count
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        WHERE so.active = TRUE
        GROUP BY c.name
        ORDER BY count DESC
        LIMIT 5
    """)
    
    # Ordens de serviço por técnico
    by_technician = db.fetch_all("""
        SELECT t.name as technician_name, COUNT(*) as count
        FROM service_orders so
        JOIN technicians t ON so.technician_id = t.id
        WHERE so.active = TRUE
        GROUP BY t.name
        ORDER BY count DESC
    """)
    
    # Ordens de serviço recentes
    recent_orders = db.fetch_all("""
        SELECT so.*, c.name as customer_name, e.name as equipment_name, 
               t.name as technician_name
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN technicians t ON so.technician_id = t.id
        WHERE so.active = TRUE
        ORDER BY so.open_date DESC
        LIMIT 5
    """)
    
    return render_template(
        'service_order_dashboard.html',
        stats=stats,
        by_type=by_type,
        by_customer=by_customer,
        by_technician=by_technician,
        recent_orders=recent_orders,
        active_page='service_orders'
    )
