"""
Módulo de detecção automática de ambiente
Detecta se está rodando em LOCAL ou PRODUÇÃO (AWS)
"""
import socket
import os
import platform

def detect_environment():
    """
    Detecta automaticamente o ambiente de execução.
    Prioridade: variável FLASK_ENV > config_local.py presente > Linux sem DISPLAY
    """
    # Método 1: Variável de ambiente FLASK_ENV (definida no .env do servidor)
    env = os.getenv('FLASK_ENV', '').lower()
    if env == 'production':
        return 'production'
    if env in ('development', 'local'):
        return 'local'

    # Método 2: Se config_local.py não existe, estamos no servidor
    config_dir = os.path.abspath(os.path.dirname(__file__))
    if not os.path.exists(os.path.join(config_dir, 'config_local.py')):
        return 'production'

    # Método 3: Hostname AWS/EC2
    hostname = socket.gethostname().lower()
    if any(k in hostname for k in ['aws', 'ec2', 'ip-172', 'ip-10']):
        return 'production'

    # Padrão: ambiente local
    return 'local'

def get_config():
    """
    Retorna a configuração correta baseada no ambiente detectado.
    """
    env = detect_environment()

    if env == 'production':
        print("[AUTO-CONFIG] Ambiente detectado: PRODUCAO")
        from config_production import DB_CONFIG, DEBUG, FLASK_ENV, SECRET_KEY
    else:
        print("[AUTO-CONFIG] Ambiente detectado: LOCAL (Desenvolvimento)")
        from config_local import DB_CONFIG, DEBUG, FLASK_ENV, SECRET_KEY
    
    # Criar objeto de configuração
    class Config:
        pass
    
    config = Config()
    config.DB_CONFIG = DB_CONFIG
    config.DEBUG = DEBUG
    config.FLASK_ENV = FLASK_ENV
    config.SECRET_KEY = SECRET_KEY
    config.ENVIRONMENT = env
    
    return config

# Exportar configuração automaticamente
config = get_config()

# Printar informações
print(f"[AUTO-CONFIG] Banco de dados: {config.DB_CONFIG['host']}")
print(f"[AUTO-CONFIG] Debug: {config.DEBUG}")
print("=" * 60)
