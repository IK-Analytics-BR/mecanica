"""Rotas para cadastro e gestão de Moedas (currencies)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from functools import wraps

from database import get_db


currency_bp = Blueprint('currency', __name__, url_prefix='/moedas')


def admin_required(f):
    """Permite acesso apenas para usuários administradores."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Apenas administradores podem gerenciar moedas.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return wrapper


@currency_bp.route('/')
@currency_bp.route('/lista')
@login_required
@admin_required
def lista():
    """Lista todas as moedas cadastradas."""
    db = get_db()
    moedas = db.fetch_all(
        """
        SELECT code, name, symbol, decimal_places, active
        FROM currencies
        ORDER BY code
        """
    )
    return render_template('cadastros/moedas_lista.html', moedas=moedas or [])


@currency_bp.route('/nova')
@login_required
@admin_required
def nova():
    """Formulário de nova moeda."""
    return render_template('cadastros/moedas_form.html', moeda=None, modo='nova')


@currency_bp.route('/<string:code>/editar')
@login_required
@admin_required
def editar(code: str):
    """Formulário de edição de moeda."""
    db = get_db()
    moeda = db.fetch_one(
        "SELECT code, name, symbol, decimal_places, active FROM currencies WHERE code = %s",
        (code.upper(),),
    )
    if not moeda:
        flash('Moeda não encontrada.', 'error')
        return redirect(url_for('currency.lista'))

    return render_template('cadastros/moedas_form.html', moeda=moeda, modo='editar')


@currency_bp.route('/salvar', methods=['POST'])
@login_required
@admin_required
def salvar():
    """Salva moeda (inclusão ou atualização)."""
    db = get_db()

    code = (request.form.get('code') or '').strip().upper()
    name = (request.form.get('name') or '').strip()
    symbol = (request.form.get('symbol') or '').strip() or None
    decimal_places_raw = (request.form.get('decimal_places') or '').strip()
    active = 1 if request.form.get('active') else 0

    if not code:
        flash('Código da moeda é obrigatório.', 'error')
        return redirect(request.referrer or url_for('currency.lista'))

    if not name:
        flash('Nome da moeda é obrigatório.', 'error')
        return redirect(request.referrer or url_for('currency.lista'))

    try:
        decimal_places = int(decimal_places_raw) if decimal_places_raw != '' else 2
    except ValueError:
        decimal_places = 2

    # Limitar a faixa de casas decimais
    if decimal_places < 0:
        decimal_places = 0
    if decimal_places > 8:
        decimal_places = 8

    try:
        # UPSERT simples: insere ou atualiza se já existir
        db.execute_query(
            """
            INSERT INTO currencies (code, name, symbol, decimal_places, active)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                symbol = VALUES(symbol),
                decimal_places = VALUES(decimal_places),
                active = VALUES(active)
            """,
            (code, name, symbol, decimal_places, active),
        )
        flash('Moeda salva com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao salvar moeda: {e}', 'error')

    return redirect(url_for('currency.lista'))


@currency_bp.route('/<string:code>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir(code: str):
    """Desativa (inativa) uma moeda. Não remove fisicamente devido a vínculos de câmbio."""
    db = get_db()
    try:
        db.execute_query(
            "UPDATE currencies SET active = 0 WHERE code = %s",
            (code.upper(),),
        )
        flash('Moeda desativada com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao desativar moeda: {e}', 'error')

    return redirect(url_for('currency.lista'))
