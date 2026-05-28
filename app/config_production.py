# ========================================
# CONFIGURAÇÃO: AMBIENTE PRODUÇÃO
# Lê credenciais do arquivo .env na raiz do projeto
# ========================================
import os

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'user':     os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'supply_chain_mecanica'),
    'port':     int(os.getenv('DB_PORT', 3306)),
    'autocommit': True,
    'buffered': True,
    'connection_timeout': 10,
    'ssl_disabled': True
}

DEBUG = False
FLASK_ENV = 'production'
SECRET_KEY = os.getenv('SECRET_KEY', 'mecanica-ikflow-secret-2026')
