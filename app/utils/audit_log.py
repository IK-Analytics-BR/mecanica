"""
audit_log.py — Log de auditoria de ações críticas — IKFlow Mecânica
Registra criação, edição e exclusão de OS, clientes e veículos.
"""
import json
from datetime import datetime
from flask import session, request
from functools import wraps

from database import get_db


def registrar_audit(tabela: str, registro_id: int, acao: str, dados_antes=None, dados_depois=None):
    """
    Grava uma entrada no audit_log.
    - tabela: 'service_orders' | 'customers' | 'equipment' | 'users' | etc.
    - acao:   'create' | 'update' | 'delete' | 'login' | 'logout'
    """
    try:
        db = get_db()
        usuario = session.get('username', 'sistema')
        company_id = session.get('company_id', 1)
        ip = request.remote_addr if request else None

        db.execute("""
            INSERT INTO audit_log
              (company_id, tabela, registro_id, acao,
               usuario, ip, dados_antes, dados_depois)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            company_id, tabela, registro_id, acao,
            usuario, ip,
            json.dumps(dados_antes, default=str) if dados_antes else None,
            json.dumps(dados_depois, default=str) if dados_depois else None,
        ))
    except Exception as e:
        # Não quebra o fluxo principal se o log falhar
        print(f'[AUDIT] Falha ao registrar log: {e}')


def audit(tabela: str, acao: str):
    """
    Decorator para logar automaticamente POST de criação/edição/exclusão.
    Uso: @audit('service_orders', 'update')
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            result = f(*args, **kwargs)
            registro_id = kwargs.get('order_id') or kwargs.get('cliente_id') \
                       or kwargs.get('vid') or kwargs.get('id') or 0
            if request.method in ('POST', 'DELETE'):
                registrar_audit(tabela, registro_id, acao)
            return result
        return wrapped
    return decorator
