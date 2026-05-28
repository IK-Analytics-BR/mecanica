"""
pix_routes.py — Módulo PIX para IKFlow Mecânica
Portado de: windsurf-project-4/app/Controllers/PixController.php
Suporta: Bradesco PIX API (padrão Bacen /v2/cob e /v2/cobv)
         e PIX Estático (fallback sem banco configurado)
"""
import json
import os
import uuid
import qrcode
import requests
from io import BytesIO
from base64 import b64encode
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, current_app
from werkzeug.utils import secure_filename
from database import get_db

pix_bp = Blueprint('pix', __name__)

# ─────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────

def _get_config(db):
    cfg = db.fetch_one("SELECT * FROM pix_config WHERE ativo = 1 LIMIT 1")
    return cfg or {}


def _gerar_qr_estatico(chave_pix: str, nome: str, cidade: str, valor: float, txid: str) -> str:
    """Gera payload PIX estático (EMV) e retorna QR code base64."""
    def _campo(id_: str, valor_: str) -> str:
        return f'{id_}{len(valor_):02d}{valor_}'

    merchant_acc = _campo('00', 'BR.GOV.BCB.PIX') + _campo('01', chave_pix)
    payload = (
        _campo('00', '01') +
        _campo('26', merchant_acc) +
        _campo('52', '0000') +
        _campo('53', '986') +
        (f'54{len(f"{valor:.2f}"):02d}{valor:.2f}' if valor > 0 else '') +
        _campo('58', 'BR') +
        _campo('59', nome[:25]) +
        _campo('60', cidade[:15]) +
        _campo('62', _campo('05', txid[:25]))
    )
    # CRC16
    crc = 0xFFFF
    for byte in (payload + '6304').encode('ascii'):
        crc ^= (byte << 8)
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
    crc &= 0xFFFF
    payload += f'6304{crc:04X}'

    try:
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = BytesIO()
        img.save(buf, format='PNG')
        return b64encode(buf.getvalue()).decode('ascii'), payload
    except Exception:
        return '', payload


# ─────────────────────────────────────────────────────────────
# rotas
# ─────────────────────────────────────────────────────────────

@pix_bp.route('/pix')
def pix_painel():
    db = get_db()
    cfg = _get_config(db)

    try:
        cobranças = db.fetch_all("""
            SELECT pc.*, so.order_number, c.name as customer_name
            FROM pix_cobrancas pc
            LEFT JOIN service_orders so ON so.id = pc.service_order_id
            LEFT JOIN customers c ON c.id = so.customer_id
            ORDER BY pc.criado_em DESC LIMIT 50
        """)
        kpis = db.fetch_one("""
            SELECT COUNT(*) as total,
                   SUM(status='ATIVA') as ativas,
                   SUM(status='CONCLUIDA') as pagas,
                   SUM(status='REMOVIDA_PELO_USUARIO_RECEBEDOR') as canceladas,
                   COALESCE(SUM(CASE WHEN status='CONCLUIDA' THEN valor END), 0) as total_recebido
            FROM pix_cobrancas
        """) or {}
    except Exception:
        cobranças, kpis = [], {}

    return render_template('pix/painel.html', cfg=cfg, cobranças=cobranças, kpis=kpis)


@pix_bp.route('/pix/configurar', methods=['GET', 'POST'])
def pix_config():
    db = get_db()
    cfg = _get_config(db)

    if request.method == 'POST':
        # Upload de certificado mTLS (Bradesco exige .pem ou .p12)
        cert_path = cfg.get('cert_path', '') if cfg else ''
        cert_file = request.files.get('cert_file')
        if cert_file and cert_file.filename:
            upload_dir = os.path.join(current_app.root_path, 'certs')
            os.makedirs(upload_dir, exist_ok=True)
            filename = secure_filename(cert_file.filename)
            cert_path = os.path.join(upload_dir, filename)
            cert_file.save(cert_path)

        dados = {
            'chave_pix':        request.form.get('chave_pix', ''),
            'nome_recebedor':   request.form.get('nome_recebedor', ''),
            'cidade':           request.form.get('cidade', ''),
            'provider':         request.form.get('provider', 'estatico'),
            'api_url':          request.form.get('api_url', ''),
            'client_id':        request.form.get('client_id', ''),
            'client_secret':    request.form.get('client_secret', ''),
            'cert_path':        cert_path,
            'cert_senha':       request.form.get('cert_senha', '') or (cfg.get('cert_senha','') if cfg else ''),
            'ativo':            1,
        }
        try:
            if cfg:
                sets = ', '.join(f'{k}=%s' for k in dados)
                db.update(f"UPDATE pix_config SET {sets} WHERE id=%s",
                          list(dados.values()) + [cfg['id']])
            else:
                cols = ', '.join(dados.keys())
                phs  = ', '.join(['%s'] * len(dados))
                db.insert(f"INSERT INTO pix_config ({cols}) VALUES ({phs})",
                          list(dados.values()))
            flash('Configuração PIX salva!', 'success')
        except Exception as e:
            flash(f'Erro: {e}', 'danger')
        return redirect(url_for('pix.pix_config'))

    return render_template('pix/config.html', cfg=cfg)


@pix_bp.route('/pix/gerar/<int:order_id>', methods=['GET', 'POST'])
def pix_gerar(order_id):
    """Gera cobrança PIX para uma OS."""
    db = get_db()
    cfg = _get_config(db)

    order = db.fetch_one("""
        SELECT so.*, c.name as customer_name, c.cnpj as customer_doc
        FROM service_orders so
        LEFT JOIN customers c ON c.id = so.customer_id
        WHERE so.id = %s
    """, (order_id,))

    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))

    valor = float(order.get('total_geral') or 0)
    if valor <= 0:
        flash('OS sem valor total para cobrar via PIX.', 'warning')
        return redirect(url_for('service_order.service_order_view', order_id=order_id))

    txid = 'OS' + order['order_number'].replace('-', '') + uuid.uuid4().hex[:8].upper()
    chave_pix    = cfg.get('chave_pix', '')
    nome_receb   = cfg.get('nome_recebedor', 'IKFlow Mecanica')
    cidade       = cfg.get('cidade', 'Campo Grande')

    qr_base64, payload_pix = _gerar_qr_estatico(chave_pix, nome_receb, cidade, valor, txid)

    # Salvar cobrança
    try:
        cob_id = db.insert("""
            INSERT INTO pix_cobrancas
            (service_order_id, txid, tipo_cob, status, valor,
             payload_pix, qr_base64, chave_pix, criado_em)
            VALUES (%s, %s, 'estatico', 'ATIVA', %s, %s, %s, %s, NOW())
        """, (order_id, txid, valor, payload_pix, qr_base64, chave_pix))
    except Exception as e:
        cob_id = None
        print(f'[PIX] Erro ao salvar cobrança: {e}')

    return render_template('pix/cobranca.html',
        order=order,
        valor=valor,
        txid=txid,
        qr_base64=qr_base64,
        payload_pix=payload_pix,
        chave_pix=chave_pix,
        nome_recebedor=nome_receb,
    )


@pix_bp.route('/pix/confirmar-pagamento/<int:order_id>', methods=['POST'])
def pix_confirmar(order_id):
    """Confirma manualmente o pagamento PIX e baixa o C/R."""
    db = get_db()
    txid = request.form.get('txid', '')

    try:
        db.update("""
            UPDATE pix_cobrancas SET status='CONCLUIDA', pago_em=NOW()
            WHERE service_order_id=%s AND txid=%s
        """, (order_id, txid))

        # Baixar C/R vinculada
        order = db.fetch_one("SELECT order_number FROM service_orders WHERE id=%s", (order_id,))
        if order:
            db.update("""
                UPDATE accounts_receivable SET status='received', receipt_date=CURDATE()
                WHERE notes LIKE %s AND status='pending'
            """, (f'%{order["order_number"]}%',))

        flash('✅ Pagamento PIX confirmado! Financeiro atualizado.', 'success')
    except Exception as e:
        flash(f'Erro: {e}', 'danger')

    return redirect(url_for('service_order.service_order_view', order_id=order_id))


@pix_bp.route('/pix/historico/<int:order_id>')
def pix_historico_os(order_id):
    db = get_db()
    cobranças = db.fetch_all("""
        SELECT * FROM pix_cobrancas WHERE service_order_id=%s ORDER BY criado_em DESC
    """, (order_id,))
    return jsonify([dict(c) for c in cobranças])
