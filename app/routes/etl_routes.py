"""
etl_routes.py — ETL / Migração de Legado — IKFlow Mecânica
Permite importar dados históricos via CSV:
  - Clientes (nome, cpf, telefone, email)
  - Veículos/Equipamentos (placa, modelo, marca, ano, cliente)
  - OS históricas (número, cliente, veículo, serviço, valor, data)
"""
import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from database import get_db
from utils.auth import admin_required

etl_bp = Blueprint('etl', __name__)


def _parse_csv(file_storage, encoding='utf-8-sig'):
    """Lê arquivo CSV e retorna lista de dicts."""
    raw = file_storage.read().decode(encoding, errors='replace')
    reader = csv.DictReader(io.StringIO(raw))
    return list(reader), reader.fieldnames or []


# ─────────────────────────────────────────────────────────────
# Painel ETL
# ─────────────────────────────────────────────────────────────
@etl_bp.route('/etl')
@admin_required
def etl_painel():
    db = get_db()
    company_id = session.get('company_id', 1)
    stats = {
        'clientes':  (db.fetch_one("SELECT COUNT(*) as n FROM customers WHERE company_id=%s", (company_id,)) or {}).get('n', 0),
        'veiculos':  (db.fetch_one("SELECT COUNT(*) as n FROM equipment WHERE company_id=%s", (company_id,)) or {}).get('n', 0),
        'ordens':    (db.fetch_one("SELECT COUNT(*) as n FROM service_orders WHERE company_id=%s", (company_id,)) or {}).get('n', 0),
    }
    logs = db.fetch_all("""
        SELECT * FROM etl_log WHERE company_id=%s ORDER BY criado_em DESC LIMIT 20
    """, (company_id,)) or []
    return render_template('etl/etl_painel.html', stats=stats, logs=logs)


def _log_etl(db, company_id, tipo, total, ok, erros, detalhes=''):
    try:
        db.execute("""
            INSERT INTO etl_log (company_id, tipo, total, importados, erros, detalhes)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (company_id, tipo, total, ok, erros, detalhes[:2000]))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# Importar Clientes
# ─────────────────────────────────────────────────────────────
@etl_bp.route('/etl/clientes', methods=['GET', 'POST'])
@admin_required
def etl_clientes():
    if request.method == 'GET':
        return render_template('etl/etl_upload.html',
                               titulo='Importar Clientes',
                               tipo='clientes',
                               colunas=['nome*', 'cpf_cnpj', 'telefone', 'email', 'endereco', 'cidade', 'estado', 'cep'])

    db = get_db()
    company_id = session.get('company_id', 1)
    f = request.files.get('arquivo')
    if not f:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('etl.etl_clientes'))

    rows, _ = _parse_csv(f)
    ok, erros, detalhes = 0, 0, []

    for i, row in enumerate(rows, 1):
        nome = (row.get('nome') or row.get('name') or '').strip()
        if not nome:
            erros += 1
            detalhes.append(f'Linha {i}: nome vazio, ignorado.')
            continue
        try:
            db.execute("""
                INSERT INTO customers
                  (company_id, name, cpf_cnpj, phone, email, address, city, state, zip_code, active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
                ON DUPLICATE KEY UPDATE
                  phone=VALUES(phone), email=VALUES(email), address=VALUES(address)
            """, (
                company_id, nome,
                (row.get('cpf_cnpj') or row.get('cpf') or '').strip(),
                (row.get('telefone') or row.get('phone') or '').strip(),
                (row.get('email') or '').strip(),
                (row.get('endereco') or row.get('address') or '').strip(),
                (row.get('cidade') or row.get('city') or '').strip(),
                (row.get('estado') or row.get('state') or '').strip(),
                (row.get('cep') or row.get('zip_code') or '').strip(),
            ))
            ok += 1
        except Exception as e:
            erros += 1
            detalhes.append(f'Linha {i}: {e}')

    _log_etl(db, company_id, 'clientes', len(rows), ok, erros, '; '.join(detalhes[:20]))
    flash(f'Clientes: {ok} importados, {erros} erros.', 'success' if erros == 0 else 'warning')
    return redirect(url_for('etl.etl_painel'))


# ─────────────────────────────────────────────────────────────
# Importar Veículos
# ─────────────────────────────────────────────────────────────
@etl_bp.route('/etl/veiculos', methods=['GET', 'POST'])
@admin_required
def etl_veiculos():
    if request.method == 'GET':
        return render_template('etl/etl_upload.html',
                               titulo='Importar Veículos',
                               tipo='veiculos',
                               colunas=['placa*', 'modelo', 'marca', 'ano', 'cor', 'km', 'cpf_cnpj_cliente'])

    db = get_db()
    company_id = session.get('company_id', 1)
    f = request.files.get('arquivo')
    if not f:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('etl.etl_veiculos'))

    rows, _ = _parse_csv(f)
    ok, erros, detalhes = 0, 0, []

    for i, row in enumerate(rows, 1):
        placa = (row.get('placa') or row.get('serial_number') or '').strip().upper()
        if not placa:
            erros += 1
            detalhes.append(f'Linha {i}: placa vazia, ignorado.')
            continue
        try:
            # Resolver cliente por CPF/CNPJ se informado
            customer_id = None
            cpf = (row.get('cpf_cnpj_cliente') or '').strip()
            if cpf:
                c = db.fetch_one(
                    "SELECT id FROM customers WHERE cpf_cnpj=%s AND company_id=%s LIMIT 1",
                    (cpf, company_id)
                )
                if c:
                    customer_id = c['id']

            db.execute("""
                INSERT INTO equipment
                  (company_id, customer_id, serial_number, model, brand, year, color, current_km, active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1)
                ON DUPLICATE KEY UPDATE
                  model=VALUES(model), brand=VALUES(brand), year=VALUES(year)
            """, (
                company_id, customer_id, placa,
                (row.get('modelo') or row.get('model') or '').strip(),
                (row.get('marca') or row.get('brand') or '').strip(),
                int(row.get('ano') or row.get('year') or 0) or None,
                (row.get('cor') or row.get('color') or '').strip(),
                int(row.get('km') or row.get('current_km') or 0) or None,
            ))
            ok += 1
        except Exception as e:
            erros += 1
            detalhes.append(f'Linha {i}: {e}')

    _log_etl(db, company_id, 'veiculos', len(rows), ok, erros, '; '.join(detalhes[:20]))
    flash(f'Veículos: {ok} importados, {erros} erros.', 'success' if erros == 0 else 'warning')
    return redirect(url_for('etl.etl_painel'))


# ─────────────────────────────────────────────────────────────
# Importar OS históricas
# ─────────────────────────────────────────────────────────────
@etl_bp.route('/etl/ordens', methods=['GET', 'POST'])
@admin_required
def etl_ordens():
    if request.method == 'GET':
        return render_template('etl/etl_upload.html',
                               titulo='Importar OS Históricas',
                               tipo='ordens',
                               colunas=['numero*', 'placa', 'cpf_cnpj_cliente', 'descricao', 'valor', 'data', 'status'])

    db = get_db()
    company_id = session.get('company_id', 1)
    f = request.files.get('arquivo')
    if not f:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('etl.etl_ordens'))

    rows, _ = _parse_csv(f)
    ok, erros, detalhes = 0, 0, []

    for i, row in enumerate(rows, 1):
        numero = (row.get('numero') or row.get('order_number') or '').strip()
        if not numero:
            erros += 1
            detalhes.append(f'Linha {i}: número OS vazio, ignorado.')
            continue
        try:
            # Resolver cliente
            customer_id = None
            cpf = (row.get('cpf_cnpj_cliente') or '').strip()
            if cpf:
                c = db.fetch_one(
                    "SELECT id FROM customers WHERE cpf_cnpj=%s AND company_id=%s LIMIT 1",
                    (cpf, company_id)
                )
                if c:
                    customer_id = c['id']

            # Resolver veículo
            equipment_id = None
            placa = (row.get('placa') or row.get('serial_number') or '').strip().upper()
            if placa:
                e = db.fetch_one(
                    "SELECT id FROM equipment WHERE serial_number=%s AND company_id=%s LIMIT 1",
                    (placa, company_id)
                )
                if e:
                    equipment_id = e['id']

            # Data
            raw_dt = (row.get('data') or row.get('created_at') or '').strip()
            created_at = None
            for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                try:
                    created_at = datetime.strptime(raw_dt, fmt)
                    break
                except Exception:
                    pass

            status_val = (row.get('status') or 'completed').strip().lower()
            valid_statuses = ('open','in_progress','completed','canceled','waiting_parts')
            if status_val not in valid_statuses:
                status_val = 'completed'

            valor = float((row.get('valor') or row.get('total_geral') or '0').replace(',', '.').strip() or 0)

            db.execute("""
                INSERT INTO service_orders
                  (company_id, customer_id, equipment_id, order_number,
                   description, total_geral, status, status_orcamento, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'aprovado',%s)
                ON DUPLICATE KEY UPDATE
                  total_geral=VALUES(total_geral), status=VALUES(status)
            """, (
                company_id, customer_id, equipment_id, numero,
                (row.get('descricao') or row.get('description') or 'OS importada').strip(),
                valor, status_val,
                created_at or datetime.now(),
            ))
            ok += 1
        except Exception as e:
            erros += 1
            detalhes.append(f'Linha {i}: {e}')

    _log_etl(db, company_id, 'ordens', len(rows), ok, erros, '; '.join(detalhes[:20]))
    flash(f'OS: {ok} importadas, {erros} erros.', 'success' if erros == 0 else 'warning')
    return redirect(url_for('etl.etl_painel'))
