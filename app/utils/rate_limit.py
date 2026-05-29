"""
rate_limit.py — Wrapper de rate limiting para IKFlow Mecânica.
Usa Flask-Limiter se disponível; caso contrário implementa controle
simples em memória sem dependência externa.
"""
import time
from collections import defaultdict
from functools import wraps
from flask import request, jsonify, abort


# ─── Controle em memória (fallback) ──────────────────────────
_mem_store: dict[str, list[float]] = defaultdict(list)


def _check_rate(key: str, limit: int, window_secs: int) -> bool:
    """True se dentro do limite, False se excedeu."""
    now = time.time()
    timestamps = _mem_store[key]
    # Remove entradas fora da janela
    _mem_store[key] = [t for t in timestamps if now - t < window_secs]
    if len(_mem_store[key]) >= limit:
        return False
    _mem_store[key].append(now)
    return True


def wa_rate_limit(limit: int = 10, window_secs: int = 60):
    """
    Decorator de rate limit para rotas WA.
    Padrão: 10 envios/min por IP.
    Retorna 429 JSON se exceder.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            key = f"wa:{request.remote_addr}:{f.__name__}"
            if not _check_rate(key, limit, window_secs):
                return jsonify({
                    'ok': False,
                    'error': f'Rate limit excedido: máximo {limit} envios por {window_secs}s.'
                }), 429
            return f(*args, **kwargs)
        return wrapped
    return decorator
