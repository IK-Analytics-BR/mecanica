"""
comissao_routes.py — Módulo de Comissões por Mecânico — IKFlow Mecânica
Calcula e registra comissões automaticamente ao concluir OS.
"""
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session

from database import get_db
from utils.auth import login_required, admin_required
from utils.tenant import get_company_id

comissao_bp = Blueprint('comissao', __name__)


# ─────────────────────────────────────────────────────────────
# helper público: calcular e gravar comissão ao concluir OS
# ─────────────────────────────────────────────────────────────

def registrar_comissao_os(order_id: int) -> dict:
    """
    Calcula e insere comissão para o técnico da OS.
    Chamada automaticamente ao setar status=completed.
    Retorna dict com resultado.
    """
    db = get_db()
    company_id = get_company_id()

    order = db.fetch_one("""
        SELECT id, order_number, technician_id,
               COALESCE(total_geral, 0) as valor_os
        FROM service_orders
        WHERE id = %s
    """, (order_id,))

    if not order or not order.get('technician_id'):
        return {'ok': False, 'motivo': 'OS sem técnico atribuído'}

    tecnico_id = order['technician_id']
    valor_os   = float(order['valor_os'])

    # Busca percentual configurado (default 10%)
    cfg = db.fetch_one("""
        SELECT percentual FROM comissao_config
        WHERE company_id = %s AND technician_id = %s AND ativo = 1
    """, (company_id, tecnico_id))
    percentual = float(cfg['percentual']) if cfg else 10.0

    valor_comissao = round(valor_os * percentual / 100, 2)
    periodo_ref    = date.today().replace(day=1)

    # Evita duplicata
    existe = db.fetch_one("""
        SELECT id FROM comissoes
        WHERE service_order_id = %s AND company_id = %s
    """, (order_id, company_id))
    if existe:
        return {'ok': False, 'motivo': 'Comissão já registrada para esta OS'}

    cid = db.insert("""
        INSERT INTO comissoes
          (company_id, technician_id, service_order_id, periodo_ref,
           valor_os, percentual, valor_comissao)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (company_id, tecnico_id, order_id, periodo_ref,
          valor_os, percentual, valor_comissao))

    return {'ok': bool(cid), 'valor_comissao': valor_comissao, 'percentual': percentual}


# ─────────────────────────────────────────────────────────────
# rotas
# ─────────────────────────────────────────────────────────────

@comissao_bp.route('/comissoes')
@login_required
def comissao_lista():
    """Dashboard de comissões com filtro por período e mecânico."""
    db = get_db()
    company_id = get_company_id()

    mes_ref  = request.args.get('mes_ref', date.today().strftime('%Y-%m'))
    tec_id   = request.args.get('technician_id', '')
    status   = request.args.get('status', '')

    periodo_ref = f"{mes_ref}-01"

    query = """
        SELECT co.*, t.name as technician_name,
               so.order_number, so.total_geral
        FROM comissoes co
        JOIN technicians t  ON t.id = co.technician_id
        JOIN service_orders so ON so.id = co.service_order_id
        WHERE co.company_id = %s AND co.periodo_ref = %s
    """
    params = [company_id, periodo_ref]

    if tec_id:
        query += " AND co.technician_id = %s"
        params.append(tec_id)
    if status:
        query += " AND co.status = %s"
        params.append(status)

    query += " ORDER BY t.name, so.order_number"
    comissoes = db.fetch_all(query, tuple(params)) or []

    # KPIs do período
    kpis = db.fetch_one("""
        SELECT
          COUNT(*)                                       AS total_os,
          COALESCE(SUM(valor_os),0)                     AS total_receita,
          COALESCE(SUM(valor_comissao),0)                AS total_comissao,
          COALESCE(SUM(CASE WHEN status='pago' THEN valor_comissao END),0) AS total_pago,
          COALESCE(SUM(CASE WHEN status='pendente' THEN valor_comissao END),0) AS total_pendente
        FROM comissoes
        WHERE company_id = %s AND periodo_ref = %s
    """, (company_id, periodo_ref)) or {}

    technicians = db.fetch_all("""
        SELECT id, name FROM technicians
        WHERE company_id = %s AND status = 'active'
        ORDER BY name
    """, (company_id,)) or []

    return render_template('comissao_lista.html',
        comissoes=comissoes, kpis=kpis,
        technicians=technicians,
        mes_ref=mes_ref, tec_id=tec_id, status=status)


@comissao_bp.route('/comissoes/config', methods=['GET', 'POST'])
@admin_required
def comissao_config():
    """Configura percentual de comissão por técnico."""
    db = get_db()
    company_id = get_company_id()

    if request.method == 'POST':
        tec_id     = request.form.get('technician_id')
        percentual = request.form.get('percentual', '10')
        if not tec_id:
            flash('Selecione um técnico.', 'danger')
        else:
            db.execute("""
                INSERT INTO comissao_config (company_id, technician_id, percentual, ativo)
                VALUES (%s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE percentual = %s, ativo = 1
            """, (company_id, tec_id, percentual, percentual))
            flash('Configuração salva!', 'success')
        return redirect(url_for('comissao.comissao_config'))

    configs = db.fetch_all("""
        SELECT cc.*, t.name as technician_name
        FROM comissao_config cc
        JOIN technicians t ON t.id = cc.technician_id
        WHERE cc.company_id = %s
        ORDER BY t.name
    """, (company_id,)) or []

    technicians = db.fetch_all("""
        SELECT id, name FROM technicians
        WHERE company_id = %s AND status = 'active'
        ORDER BY name
    """, (company_id,)) or []

    return render_template('comissao_config.html',
        configs=configs, technicians=technicians)


@comissao_bp.route('/comissoes/<int:cid>/pagar', methods=['POST'])
@admin_required
def comissao_pagar(cid):
    """Marca uma comissão como paga."""
    db = get_db()
    company_id = get_company_id()
    db.update("""
        UPDATE comissoes SET status='pago', pago_em=NOW()
        WHERE id=%s AND company_id=%s
    """, (cid, company_id))
    flash('Comissão marcada como paga.', 'success')
    return redirect(request.referrer or url_for('comissao.comissao_lista'))
