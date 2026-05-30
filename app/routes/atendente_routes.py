"""
atendente_routes.py — PWA do Atendente de Oficina — IKFlow Mecânica
Focado em: Abertura de OS, cadastro rápido cliente/veículo, envio de orçamento.
Roles: atendente, auxiliar
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from functools import wraps
from datetime import datetime, timedelta, date

from database import get_db
from utils.auth import login_required
from utils.tenant import get_company_id

atendente_bp = Blueprint('atendente', __name__, url_prefix='/atendente')

_ROLES_PERMITIDOS = {'atendente', 'auxiliar', 'admin'}


def atendente_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        role = (session.get('role') or '').lower()
        if role not in _ROLES_PERMITIDOS:
            flash('Acesso restrito ao atendente.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────
# Dashboard principal do atendente
# ─────────────────────────────────────────────────────────────
@atendente_bp.route('/')
@login_required
@atendente_required
def index():
    db = get_db()
    company_id = get_company_id()
    hoje = date.today()

    # OS do dia
    os_hoje = db.fetch_all("""
        SELECT so.id, so.order_number, so.status, so.priority,
               so.customer_complaint,
               c.name as customer_name, c.phone as customer_phone,
               e.plate as plate, e.brand as brand, e.model as model,
               t.name as technician_name
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN technicians t ON so.technician_id = t.id
        WHERE so.company_id = %s AND DATE(so.open_date) = %s
          AND so.active = TRUE
        ORDER BY FIELD(so.status,'in_progress','open','completed'), so.open_date DESC
        LIMIT 30
    """, (company_id, hoje)) or []

    # Contadores
    stats = {
        'abertas': sum(1 for o in os_hoje if o['status'] == 'open'),
        'andamento': sum(1 for o in os_hoje if o['status'] == 'in_progress'),
        'concluidas': sum(1 for o in os_hoje if o['status'] == 'completed'),
        'total': len(os_hoje),
    }

    # OS aguardando orçamento
    aguardando = db.fetch_all("""
        SELECT so.id, so.order_number, c.name as customer_name,
               e.plate as plate, e.brand as brand, e.model as model
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipment e ON so.equipment_id = e.id
        WHERE so.company_id = %s AND so.status_orcamento IN ('rascunho','em_aprovacao')
          AND so.active = TRUE
        ORDER BY so.open_date DESC LIMIT 10
    """, (company_id,)) or []

    return render_template('pwa/atendente/dashboard.html',
                           os_hoje=os_hoje,
                           stats=stats,
                           aguardando=aguardando,
                           data_hoje=hoje.strftime('%d/%m/%Y'))


# ─────────────────────────────────────────────────────────────
# Abrir nova OS
# ─────────────────────────────────────────────────────────────
@atendente_bp.route('/nova-os', methods=['GET', 'POST'])
@login_required
@atendente_required
def nova_os():
    db = get_db()
    company_id = get_company_id()

    if request.method == 'POST':
        customer_id  = request.form.get('customer_id', '').strip()
        equipment_id = request.form.get('equipment_id', '').strip()
        complaint    = request.form.get('customer_complaint', '').strip()
        priority     = request.form.get('priority', 'normal')
        technician_id= request.form.get('technician_id', '') or None

        if not customer_id or not complaint:
            return jsonify({'ok': False, 'erro': 'Cliente e descrição do problema são obrigatórios'}), 400

        # Gerar número de OS
        hoje_str = datetime.now().strftime('%Y%m%d')
        ultimo = db.fetch_one(
            "SELECT order_number FROM service_orders WHERE company_id=%s ORDER BY id DESC LIMIT 1",
            (company_id,)
        )
        seq = 1
        if ultimo and ultimo.get('order_number'):
            try:
                seq = int(ultimo['order_number'].split('-')[-1]) + 1
            except Exception:
                seq = 1
        order_number = f"OS-{hoje_str}-{seq:03d}"

        os_id = db.insert("""
            INSERT INTO service_orders
              (order_number, customer_id, equipment_id, technician_id,
               customer_complaint, priority, status, status_orcamento,
               open_date, company_id, active)
            VALUES (%s,%s,%s,%s,%s,%s,'open','rascunho',NOW(),%s,TRUE)
        """, (order_number,
              customer_id,
              equipment_id or None,
              technician_id,
              complaint, priority,
              company_id))

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'ok': True, 'os_id': os_id, 'order_number': order_number})
        flash(f'OS {order_number} aberta com sucesso!', 'success')
        return redirect(url_for('atendente.os_detalhe', os_id=os_id))

    # GET — formulário
    tecnicos = db.fetch_all(
        "SELECT id, name FROM technicians WHERE company_id=%s AND active=TRUE ORDER BY name",
        (company_id,)
    ) or []

    return render_template('pwa/atendente/nova_os.html', tecnicos=tecnicos)


# ─────────────────────────────────────────────────────────────
# Detalhe / edição da OS pelo atendente
# ─────────────────────────────────────────────────────────────
@atendente_bp.route('/os/<int:os_id>')
@login_required
@atendente_required
def os_detalhe(os_id):
    db = get_db()
    company_id = get_company_id()

    os = db.fetch_one("""
        SELECT so.*,
               c.name as customer_name, c.phone as customer_phone, c.email as customer_email,
               e.plate as plate, e.brand as brand, e.model as model,
               e.year as year, e.color as color, e.chassis as chassis,
               t.name as technician_name
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN technicians t ON so.technician_id = t.id
        WHERE so.id=%s AND so.company_id=%s AND so.active=TRUE
    """, (os_id, company_id))

    if not os:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('atendente.index'))

    itens = db.fetch_all("""
        SELECT soi.*, p.name as product_name, p.code as product_code
        FROM service_order_items soi
        LEFT JOIN products p ON soi.product_id = p.id
        WHERE soi.service_order_id = %s
        ORDER BY soi.item_type, soi.id
    """, (os_id,)) or []

    tecnicos = db.fetch_all(
        "SELECT id, name FROM technicians WHERE company_id=%s AND active=TRUE ORDER BY name",
        (company_id,)
    ) or []

    _STATUS = {
        'open': ('Aberta', 'badge-open'),
        'in_progress': ('Em Andamento', 'badge-andamento'),
        'completed': ('Concluída', 'badge-concluida'),
        'cancelled': ('Cancelada', 'badge-cancelada'),
    }
    os['status_label'], os['status_class'] = _STATUS.get(os['status'], ('Aberta', 'badge-open'))

    return render_template('pwa/atendente/os_detalhe.html',
                           os=os, itens=itens, tecnicos=tecnicos)


# ─────────────────────────────────────────────────────────────
# Enviar orçamento ao cliente
# ─────────────────────────────────────────────────────────────
@atendente_bp.route('/os/<int:os_id>/enviar-orcamento', methods=['POST'])
@login_required
@atendente_required
def enviar_orcamento(os_id):
    db = get_db()
    company_id = get_company_id()
    obs = request.form.get('obs_orcamento', '')

    db.execute("""
        UPDATE service_orders
        SET status_orcamento = 'em_aprovacao',
            obs_orcamento = %s,
            updated_at = NOW()
        WHERE id=%s AND company_id=%s
    """, (obs, os_id, company_id))

    return jsonify({'ok': True, 'msg': 'Orçamento enviado para aprovação!'})


# ─────────────────────────────────────────────────────────────
# API: busca rápida de cliente por nome/CPF
# ─────────────────────────────────────────────────────────────
@atendente_bp.route('/api/buscar-cliente')
@login_required
def api_buscar_cliente():
    db = get_db()
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    rows = db.fetch_all("""
        SELECT id, name, cnpj as cpf_cnpj, phone, email
        FROM customers
        WHERE active=TRUE AND (name LIKE %s OR cnpj LIKE %s)
        ORDER BY name LIMIT 10
    """, (f'%{q}%', f'%{q}%')) or []
    return jsonify([dict(r) for r in rows])


# ─────────────────────────────────────────────────────────────
# API: veículos do cliente
# ─────────────────────────────────────────────────────────────
@atendente_bp.route('/api/veiculos-cliente/<int:customer_id>')
@login_required
def api_veiculos_cliente(customer_id):
    db = get_db()
    rows = db.fetch_all("""
        SELECT id, plate, brand, model, year, color
        FROM equipment
        WHERE customer_id=%s AND active=TRUE
        ORDER BY plate
    """, (customer_id,)) or []
    return jsonify([dict(r) for r in rows])


# ─────────────────────────────────────────────────────────────
# API: cadastro rápido de cliente
# ─────────────────────────────────────────────────────────────
@atendente_bp.route('/api/cadastrar-cliente', methods=['POST'])
@login_required
def api_cadastrar_cliente():
    db = get_db()
    company_id = get_company_id()
    data = request.get_json() or {}
    nome  = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    cpf   = (data.get('cpf_cnpj') or '').strip()
    if not nome:
        return jsonify({'ok': False, 'erro': 'Nome obrigatório'}), 400

    cid = db.insert("""
        INSERT INTO customers (name, cnpj, phone, active, company_id, created_at)
        VALUES (%s,%s,%s,TRUE,%s,NOW())
    """, (nome, cpf, phone, company_id))
    return jsonify({'ok': True, 'id': cid, 'name': nome})


# ─────────────────────────────────────────────────────────────
# API: cadastro rápido de veículo
# ─────────────────────────────────────────────────────────────
@atendente_bp.route('/api/cadastrar-veiculo', methods=['POST'])
@login_required
def api_cadastrar_veiculo():
    db = get_db()
    company_id = get_company_id()
    data = request.get_json() or {}
    customer_id = data.get('customer_id')
    plate = (data.get('plate') or '').strip().upper()
    brand = (data.get('brand') or '').strip()
    model = (data.get('model') or '').strip()
    year  = data.get('year') or None
    color = (data.get('color') or '').strip()

    if not plate:
        return jsonify({'ok': False, 'erro': 'Placa obrigatória'}), 400

    eid = db.insert("""
        INSERT INTO equipment (customer_id, plate, brand, model, year, color, active, company_id, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,TRUE,%s,NOW())
    """, (customer_id, plate, brand, model, year, color, company_id))
    return jsonify({'ok': True, 'id': eid, 'plate': plate, 'label': f'{brand} {model} — {plate}'})


# ─────────────────────────────────────────────────────────────
# Histórico de OS do atendente (todas)
# ─────────────────────────────────────────────────────────────
@atendente_bp.route('/historico')
@login_required
@atendente_required
def historico():
    db = get_db()
    company_id = get_company_id()
    status_f = request.args.get('status', 'all')
    dias_f   = int(request.args.get('dias', 30))

    query = """
        SELECT so.id, so.order_number, so.status, so.open_date, so.priority,
               c.name as customer_name,
               e.plate as plate, e.brand as brand, e.model as model,
               t.name as technician_name,
               COALESCE(so.total_geral, 0) as total
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipment e ON so.equipment_id = e.id
        LEFT JOIN technicians t ON so.technician_id = t.id
        WHERE so.company_id=%s AND so.active=TRUE
          AND so.open_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
    """
    params = [company_id, dias_f]
    if status_f != 'all':
        query += " AND so.status=%s"
        params.append(status_f)
    query += " ORDER BY so.open_date DESC LIMIT 100"

    ordens = db.fetch_all(query, tuple(params)) or []
    for o in ordens:
        _STATUS = {'open': 'Aberta', 'in_progress': 'Em Andamento',
                   'completed': 'Concluída', 'cancelled': 'Cancelada'}
        o['status_label'] = _STATUS.get(o['status'], o['status'])
        if o['open_date']:
            o['data_fmt'] = o['open_date'].strftime('%d/%m/%Y') if hasattr(o['open_date'], 'strftime') else str(o['open_date'])[:10]

    return render_template('pwa/atendente/historico.html',
                           ordens=ordens, status_f=status_f, dias_f=dias_f)
