"""
utils/auth.py — Autenticação centralizada IKFlow Mecânica
Importar em cada route file:
    from utils.auth import login_required
"""
from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(f):
    """Decorator centralizado. Redireciona para login se não autenticado."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator que exige role=admin além de autenticação."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Acesso restrito a administradores.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function
