"""
utils/tenant.py — Isolamento multi-empresa (multi-tenant) IKFlow Mecânica

Uso nos route files:
    from utils.tenant import get_company_id, company_filter

    company_id = get_company_id()
    rows = db.fetch_all("SELECT * FROM customers WHERE company_id = %s", (company_id,))

    # Ou com helper de filtro:
    where, params = company_filter()
    rows = db.fetch_all(f"SELECT * FROM customers WHERE {where}", params)
"""
from flask import session


def get_company_id() -> int:
    """Retorna o company_id ativo da sessão. Fallback = 1 (empresa padrão)."""
    try:
        cid = session.get('company_id')
        if cid and str(cid).isdigit() and int(cid) > 0:
            return int(cid)
    except Exception:
        pass
    return 1


def company_filter(alias: str = '') -> tuple:
    """
    Retorna (cláusula WHERE, params) para filtrar por company_id.

    Args:
        alias: prefixo de tabela, ex: 'so' → 'so.company_id = %s'

    Returns:
        ('company_id = %s', (1,))  ou  ('so.company_id = %s', (1,))
    """
    prefix = f'{alias}.' if alias else ''
    return f'{prefix}company_id = %s', (get_company_id(),)


def inject_company_id(data: dict) -> dict:
    """Injeta company_id num dict de dados antes de INSERT/UPDATE."""
    data['company_id'] = get_company_id()
    return data
