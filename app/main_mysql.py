from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import sys
from functools import wraps
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
try:
    from flask_wtf.csrf import CSRFProtect, generate_csrf
    _csrf_available = True
except ImportError:
    _csrf_available = False
    generate_csrf = None

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _limiter_available = True
except ImportError:
    _limiter_available = False

# Adicionar o diretório atual ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Importar utilitários de senha
from utils.password_utils import hash_password, verify_password, validate_password_strength

# Importar o módulo de banco de dados
from database import get_db

# Serviço de câmbio
from services.exchange_rate_service import ExchangeRateService

# Importar os blueprints com tolerância (alguns módulos podem não existir ainda)
def _try_import(module_name, attr_name):
    try:
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)
    except Exception as e:
        print(f"[ROUTES] Aviso: não foi possível importar {module_name}.{attr_name}: {e}")
        return None

# Guards de modo — APP_MODE definido no env; default=mecanica
APP_MODE = (os.getenv('APP_MODE') or 'mecanica').strip().lower()
if APP_MODE not in ('global', 'industrial', 'varejo', 'mecanica'):
    APP_MODE = 'mecanica'
_modo_industrial = APP_MODE in ('industrial', 'global')
_modo_comercial  = APP_MODE in ('varejo', 'global')

cliente_bp = _try_import('routes.cliente_routes_mysql', 'cliente_bp')
produto_bp = _try_import('routes.produto_routes_mysql', 'produto_bp')
ncm_bp = _try_import('routes.ncm_routes', 'ncm_bp')
cfop_bp = _try_import('routes.cfop_routes', 'cfop_bp')
insumo_bp = _try_import('routes.insumo_routes_mysql', 'insumo_bp')
equipamento_bp = _try_import('routes.equipamento_routes_mysql', 'equipamento_bp')
fornecedor_bp = _try_import('routes.fornecedor_routes_mysql', 'fornecedor_bp')
unit_measure_bp = _try_import('routes.unit_measure_routes', 'unit_measure_bp')
usuario_bp = _try_import('routes.usuario_routes_mysql', 'usuario_bp')
hour_meter_bp = _try_import('routes.hour_meter_routes', 'hour_meter_bp')
maintenance_plan_bp = _try_import('routes.maintenance_plan_routes', 'maintenance_plan_bp')
service_order_bp = _try_import('routes.service_order_routes', 'service_order_bp')
alert_bp = _try_import('routes.alert_routes', 'alert_bp')
dashboard_bp = _try_import('routes.dashboard_routes', 'dashboard_bp')
integration_bp = _try_import('routes.integration_routes', 'integration_bp')
vendedor_bp = _try_import('routes.vendedor_routes', 'vendedor_bp') if _modo_comercial else None
cash_register_bp = _try_import('routes.cash_register_routes', 'cash_register_bp')
company_bp = _try_import('routes.company_routes', 'company_bp')
segment_bp = _try_import('routes.segment_routes', 'segment_bp') if _modo_comercial else None

# Módulo Financeiro
bank_account_bp = _try_import('routes.bank_account_routes', 'bank_account_bp')
accounts_payable_bp = _try_import('routes.accounts_payable_routes', 'accounts_payable_bp')
accounts_receivable_bp = _try_import('routes.accounts_receivable_routes', 'accounts_receivable_bp')
cash_flow_bp = _try_import('routes.cash_flow_routes', 'cash_flow_bp')
chart_of_accounts_bp = _try_import('routes.chart_of_accounts_routes', 'chart_of_accounts_bp')
payment_config_bp = _try_import('routes.payment_config_routes', 'payment_config_bp')

# Módulo de Compras
purchase_order_bp = _try_import('routes.purchase_order_routes_fixed', 'purchase_order_bp')
purchase_order_new_bp = _try_import('routes.purchase_order_new_routes', 'purchase_order_new_bp')
purchase_order_simple_bp = _try_import('routes.purchase_order_simple_routes', 'purchase_order_simple_bp')
purchase_order_integrated_bp = _try_import('routes.purchase_order_integrated_routes', 'purchase_order_integrated_bp')
invoice_bp = _try_import('routes.invoice_routes', 'invoice_bp')

# Módulo de Estoque
inventory_bp = _try_import('routes.inventory_routes', 'inventory_bp')
kardex_bp = _try_import('routes.kardex_routes', 'kardex_bp')

# Módulo de Relatórios
reports_bp = _try_import('routes.reports_routes', 'reports_bp')

# Módulo de Usuários e Permissões (usuario_bp = principal; users_bp = legado mantido para compatibilidade)
usuario_bp    = _try_import('routes.usuario_routes_mysql', 'usuario_bp')
users_bp      = _try_import('routes.users_routes',         'users_bp')
permissoes_bp = _try_import('routes.permissoes_routes',    'permissoes_bp')

# API para verificação de documentos
api_bp = _try_import('routes.api_routes', 'api_bp')

# Módulo de Técnicos
technician_bp = _try_import('routes.technician_routes', 'technician_bp')

# Agenda de Mecânicos
agenda_bp = _try_import('routes.agenda_routes', 'agenda_bp')

# Módulo de Produtos - Categorias, Marcas, Grupos e Subgrupos
product_category_bp = _try_import('routes.product_category_routes', 'product_category_bp')
product_brand_bp = _try_import('routes.product_brand_routes', 'product_brand_bp')
product_group_bp = _try_import('routes.product_group_routes', 'product_group_bp')
product_subgroup_bp = _try_import('routes.product_subgroup_routes', 'product_subgroup_bp')
product_model_bp = _try_import('routes.product_model_routes', 'product_model_bp')

# Módulo de Importação de Clientes
importar_clientes_bp = _try_import('routes.importar_clientes_routes', 'importar_clientes_bp')

# Módulo de Clientes em Potencial
clientes_potenciais_bp = _try_import('routes.clientes_potenciais_routes', 'clientes_potenciais_bp')
# Rota de vendas e questionario de visita — só para modo comercial/distribuição
rota_vendas_bp         = _try_import('routes.rota_vendas_routes', 'rota_vendas_bp')                   if _modo_comercial else None
questionario_visita_bp = _try_import('routes.questionario_visita_routes', 'questionario_visita_bp')    if _modo_comercial else None

# Módulo de Importação de NF-e
importar_nfe_bp = _try_import('routes.importar_nfe', 'importar_nfe')
importar_nfe_entrada_bp = _try_import('routes.importar_nfe_entrada', 'importar_nfe_entrada')
nfe_upload_bp = _try_import('routes.importar_nfe_upload', 'nfe_upload_bp')

# Módulo de Emissão de NF-e
nfe_emissao_bp = _try_import('routes.nfe_emissao_routes', 'nfe_emissao_bp')

# Módulo de Emissão de NFC-e
nfce_bp = _try_import('routes.nfce_routes', 'nfce_bp')

# Módulo de Empresas
empresa_bp = _try_import('routes.empresa_routes', 'empresa_bp')

# Módulo Jornada / Ponto
jornada_trabalho_bp = _try_import('routes.jornada_trabalho_routes', 'jornada_trabalho_bp')

# Módulos Industriais — só carregados em APP_MODE=industrial ou global
ordem_producao_bp  = _try_import('routes.ordem_producao_routes',  'ordem_producao_bp')  if _modo_industrial else None
producao_pausas_bp = _try_import('routes.producao_pausas_routes', 'producao_pausas_bp') if _modo_industrial else None
config_producao_bp = _try_import('routes.config_producao_routes', 'config_producao_bp') if _modo_industrial else None

# Módulo Comercial - Orçamentos
orcamento_bp = _try_import('routes.orcamento_routes', 'orcamento_bp')
orcamento_dna_bp = _try_import('routes.orcamento_dna_routes', 'orcamento_dna_bp')

# Módulo de Lista de Preços
lista_preco_bp = _try_import('routes.lista_preco_routes', 'lista_preco_bp')

# Módulo PDV Profissional (Balcão) + Histórico de Vendas
pdv_bp       = _try_import('routes.pdv_profissional_routes', 'pdv_bp')
pdv_config_bp = _try_import('routes.pdv_config_routes',     'pdv_config_bp')
venda_bp      = _try_import('routes.venda_routes',          'venda_bp')

# Módulos portados do Holding
whatsapp_bp = _try_import('routes.whatsapp_routes', 'whatsapp_bp')
pix_bp      = _try_import('routes.pix_routes',      'pix_bp')
nfse_bp2    = _try_import('routes.nfse_routes',     'nfse_bp')

# Módulos Semana 5: Comissões + Garantias
comissao_bp = _try_import('routes.comissao_routes', 'comissao_bp')
garantia_bp = _try_import('routes.garantia_routes', 'garantia_bp')

# Módulo Mecânico (App mobile para oficina)
mecanico_bp = _try_import('routes.mecanico_routes', 'mecanico_bp')

# PWA Atendente (App dedicado para atendente/auxiliar)
atendente_bp = _try_import('routes.atendente_routes', 'atendente_bp')

# Módulos Semana 9: Push Notifications + Portal do Cliente
push_bp   = _try_import('routes.push_routes',   'push_bp')
portal_bp = _try_import('routes.portal_routes', 'portal_bp')

# Módulos Semana 10: Boleto Bancário + ETL
boleto_bp = _try_import('routes.boleto_routes', 'boleto_bp')
etl_bp    = _try_import('routes.etl_routes',    'etl_bp')

# Cadastros Auxiliares
transportadora_bp = _try_import('routes.transportadora_routes', 'transportadora_bp')
condicao_pagamento_bp = _try_import('routes.condicao_pagamento_routes', 'condicao_pagamento_bp')
currency_bp = _try_import('routes.currency_routes', 'currency_bp')


# Importar módulos para servir arquivos markdown
from flask import send_from_directory, abort
import markdown
import os.path

# Criar a aplicação Flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chave_secreta_do_sistema')
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600

# Proteção CSRF global (Flask-WTF)
if _csrf_available:
    _csrf = CSRFProtect(app)

# Rate Limiting (Flask-Limiter)
if _limiter_available:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[],
        storage_uri='memory://',
    )
else:
    limiter = None

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'danger'


class User(UserMixin):
    def __init__(self, user_id: int, username: str | None = None, role: str | None = None):
        self.id = str(user_id)
        self.username = username
        self.role = role


def get_user_by_username(username: str):
    db = get_db()
    user = db.fetch_one("SELECT * FROM users WHERE username = %s", (username,))
    return user


def get_user_by_id(user_id: int):
    db = get_db()
    return db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))


@login_manager.user_loader
def load_user(user_id: str):
    try:
        if not str(user_id).isdigit():
            return None
        row = get_user_by_id(int(user_id))
        if not row:
            return None
        return User(int(row.get('id')), row.get('username'), row.get('role'))
    except Exception as e:
        print(f"[AUTH] Erro no user_loader: {e}")
        return None


def _register(bp):
    if not bp:
        return
    try:
        app.register_blueprint(bp)
    except Exception as e:
        print(f"[ROUTES] Aviso: não foi possível registrar blueprint {getattr(bp, 'name', '?')}: {e}")


for _bp in (
    cliente_bp,
    produto_bp,
    ncm_bp,
    cfop_bp,
    segment_bp,
    insumo_bp,
    equipamento_bp,
    fornecedor_bp,
    unit_measure_bp,
    usuario_bp,
    hour_meter_bp,
    maintenance_plan_bp,
    service_order_bp,
    alert_bp,
    dashboard_bp,
    integration_bp,
    vendedor_bp,
    cash_register_bp,
    company_bp,
    bank_account_bp,
    accounts_payable_bp,
    accounts_receivable_bp,
    cash_flow_bp,
    chart_of_accounts_bp,
    payment_config_bp,
    purchase_order_bp,
    purchase_order_new_bp,
    purchase_order_simple_bp,
    purchase_order_integrated_bp,
    invoice_bp,
    inventory_bp,
    kardex_bp,
    reports_bp,
    users_bp,
    permissoes_bp,
    api_bp,
    technician_bp,
    agenda_bp,
    product_category_bp,
    product_brand_bp,
    product_group_bp,
    product_subgroup_bp,
    product_model_bp,
    importar_clientes_bp,
    clientes_potenciais_bp,
    rota_vendas_bp,
    questionario_visita_bp,
    importar_nfe_bp,
    importar_nfe_entrada_bp,
    nfe_upload_bp,
    nfe_emissao_bp,
    nfce_bp,
    empresa_bp,
    jornada_trabalho_bp,
    ordem_producao_bp,
    producao_pausas_bp,
    config_producao_bp,
    orcamento_bp,
    orcamento_dna_bp,
    lista_preco_bp,
    whatsapp_bp,
    pix_bp,
    nfse_bp2,
    comissao_bp,
    garantia_bp,
    mecanico_bp,
    atendente_bp,
    push_bp,
    portal_bp,
    boleto_bp,
    etl_bp,
    transportadora_bp,
    condicao_pagamento_bp,
    currency_bp,
    pdv_bp,
    pdv_config_bp,
    venda_bp,
):
    _register(_bp)

# Adicionar funções ao contexto do Jinja2 (para usar nos templates)
from datetime import datetime, timedelta
from decimal import Decimal

@app.context_processor
def inject_datetime():
    """Disponibiliza funções de data/hora para os templates"""
    def blueprint_exists(blueprint_name):
        """Verifica se um blueprint está registrado"""
        return blueprint_name in app.blueprints

    def _normalize_mode(value: str) -> str:
        try:
            m = (value or '').strip().lower()
        except Exception:
            m = ''
        if m not in ('global', 'industrial', 'varejo', 'mecanica'):
            return 'mecanica'
        return m

    def get_effective_app_mode() -> str:
        """Modo efetivo do sistema no contexto do usuário.
        Prioridade:
        - session['app_mode'] (empresa selecionada)
        - APP_MODE (ambiente)
        """
        sess_mode = session.get('app_mode')
        if sess_mode:
            return _normalize_mode(str(sess_mode))
        return _normalize_mode(APP_MODE)

    def app_mode_allows(mode_name: str):
        m = _normalize_mode(mode_name)
        eff = get_effective_app_mode()
        if eff == 'global':
            return True
        return eff == m
    # Funções de permissão para templates
    def tem_permissao(codigo_tela, acao='visualizar'):
        """Verifica permissão do usuário na tela/ação."""
        if session.get('role') == 'admin':
            return True
        permissoes = session.get('permissoes', {})
        if codigo_tela in permissoes:
            return permissoes[codigo_tela].get(acao, False)
        return False
    
    def pode_ver(codigo_tela):
        return tem_permissao(codigo_tela, 'visualizar')
    
    def pode_criar(codigo_tela):
        return tem_permissao(codigo_tela, 'criar')
    
    def pode_editar(codigo_tela):
        return tem_permissao(codigo_tela, 'editar')
    
    def pode_excluir(codigo_tela):
        return tem_permissao(codigo_tela, 'excluir')

    ctx = {
        'now': datetime.now,
        'datetime': datetime,
        'timedelta': timedelta,
        'Decimal': Decimal,
        'float': float,
        'blueprint_exists': blueprint_exists,
        'app_mode': get_effective_app_mode(),
        'app_mode_allows': app_mode_allows,
        'tem_permissao': tem_permissao,
        'pode_ver': pode_ver,
        'pode_criar': pode_criar,
        'pode_editar': pode_editar,
        'pode_excluir': pode_excluir,
    }
    # Só injeta csrf_token quando Flask-WTF NAO esta disponivel
    # (quando CSRFProtect esta ativo, ele ja registra csrf_token no Jinja2)
    if not _csrf_available:
        ctx['csrf_token'] = lambda: ''
    return ctx

@app.template_filter('basename')
def _filter_basename(path):
    import os as _os
    return _os.path.basename(path or '')


def _normalize_mode_value(value: str) -> str:
    try:
        m = (value or '').strip().lower()
    except Exception:
        m = ''
    if m not in ('global', 'industrial', 'varejo', 'mecanica'):
        return 'mecanica'
    return m

def _get_user_empresas(user_id: int):
    db = get_db()
    try:
        return db.fetch_all(
            """
            SELECT e.id,
                   COALESCE(e.nome_fantasia, e.razao_social) AS nome,
                   e.razao_social,
                   e.nome_fantasia,
                   e.logo_path,
                   COALESCE(e.app_mode, 'global') AS app_mode
            FROM user_empresas ue
            JOIN empresas e ON e.id = ue.empresa_id
            WHERE ue.user_id = %s
              AND e.ativo = TRUE
            ORDER BY COALESCE(e.nome_fantasia, e.razao_social)
            """,
            (user_id,)
        )
    except Exception as e:
        # Alguns bancos não têm a coluna empresas.app_mode
        msg = str(e).lower()
        if 'unknown column' in msg and 'app_mode' in msg:
            return db.fetch_all(
                """
                SELECT e.id,
                       COALESCE(e.nome_fantasia, e.razao_social) AS nome,
                       e.razao_social,
                       e.nome_fantasia,
                       e.logo_path,
                       'global' AS app_mode
                FROM user_empresas ue
                JOIN empresas e ON e.id = ue.empresa_id
                WHERE ue.user_id = %s
                  AND e.ativo = TRUE
                ORDER BY COALESCE(e.nome_fantasia, e.razao_social)
                """,
                (user_id,)
            )
        raise

def _set_empresa_in_session(empresa_row: dict):
    session['empresa_id'] = int(empresa_row['id'])
    session['app_mode'] = _normalize_mode_value(str(empresa_row.get('app_mode') or 'global'))
    # Logo da empresa (se houver)
    lp = (empresa_row.get('logo_path') if isinstance(empresa_row, dict) else None) or None
    session['empresa_logo_path'] = lp


def get_low_stock_supplies():
    """Retorna lista de insumos (supplies) abaixo do estoque mínimo.
    Implementação resiliente: se a estrutura não bater, retorna lista vazia para não quebrar o dashboard.
    """
    try:
        db = get_db()
        return db.fetch_all(
            """
            SELECT id, name, stock, min_stock
            FROM supplies
            WHERE active = TRUE
              AND min_stock IS NOT NULL
              AND min_stock > 0
              AND stock < min_stock
            ORDER BY (min_stock - stock) DESC
            LIMIT 10
            """
        ) or []
    except Exception as e:
        print(f"[DASHBOARD] Aviso: falha ao buscar insumos com estoque baixo: {e}")
        return []


def get_maintenance_equipment():
    """Retorna equipamentos com próxima manutenção programada.
    Implementação resiliente: se a estrutura não bater, retorna lista vazia para não quebrar o dashboard.
    """
    try:
        db = get_db()
        return db.fetch_all(
            """
            SELECT id, name, next_maintenance
            FROM equipment
            WHERE active = TRUE
              AND next_maintenance IS NOT NULL
            ORDER BY next_maintenance ASC
            LIMIT 10
            """
        ) or []
    except Exception as e:
        print(f"[DASHBOARD] Aviso: falha ao buscar equipamentos para manutenção: {e}")
        return []

@app.before_request
def enforce_app_mode_access():
    """Bloqueia rotas conforme modo efetivo (session/app_mode).
    Observação: isso complementa o controle de menus; evita acesso por URL direta.
    """
    try:
        path = (request.path or '')
    except Exception:
        path = ''

    # rotas públicas
    if path.startswith('/static/') or path in ('/login', '/logout'):
        return None

    # rotas do fluxo de seleção de empresa
    if path in ('/selecionar-empresa',):
        return None

    # sem login ainda
    if 'username' not in session:
        return None

    # admin sempre pode acessar qualquer módulo, independente do modo
    if session.get('role') == 'admin':
        return None

    # Se ainda não selecionou empresa, não bloquear (fluxo de login cuidará disso)
    if not session.get('empresa_id'):
        return None

    eff = _normalize_mode_value(str(session.get('app_mode') or APP_MODE or 'global'))
    if eff == 'global':
        return None

    varejo_prefixes = (
        '/vendas',
        '/caixa',
        # '/nfce' removido - Teste NFC-e deve estar acessível em qualquer modo
        '/empresa/configuracoes',
    )
    industria_prefixes = (
        '/industria',
    )

    if eff == 'industrial':
        if path.startswith(varejo_prefixes):
            flash('Acesso não permitido no modo Indústria.', 'danger')
            return redirect(url_for('dashboard'))

    if eff == 'varejo':
        if path.startswith(industria_prefixes):
            flash('Acesso não permitido no modo Varejo.', 'danger')
            return redirect(url_for('dashboard'))

    return None

# Adicionar filtro customizado para converter Decimal para float
@app.template_filter('to_float')
def to_float_filter(value):
    """Converte valor para float (útil para Decimal)"""
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('bem_vindo'))
    return redirect(url_for('login'))

@app.route('/bem-vindo')
@app.route('/dashboard')
@login_required
def bem_vindo():
    """Página inicial após login - Dashboard premium com KPIs."""
    db = get_db()

    rate_date = None
    rate_date_param = request.args.get('fx_date')
    if rate_date_param:
        try:
            rate_date = date.fromisoformat(rate_date_param)
        except ValueError:
            rate_date = None

    if not rate_date:
        try:
            row = db.fetch_one(
                "SELECT MAX(rate_date) AS d FROM exchange_rates",
            )
            if row and row.get('d'):
                rate_date = row['d']
        except Exception as e:
            print(f"[FX] Aviso: falha ao buscar data máxima de câmbio: {e}")

    if not rate_date:
        rate_date = date.today() - timedelta(days=1)

    # Buscar moedas ativas e suas cotações em relação à moeda base
    try:
        base_row = db.fetch_one(
            "SELECT code, name, symbol FROM currencies WHERE code = %s",
            ('BRL',),
        )
    except Exception:
        base_row = None

    base_code = base_row['code'] if base_row else 'BRL'

    try:
        moedas = db.fetch_all(
            """
            SELECT c.code, c.name, c.symbol, c.decimal_places,
                   er.rate
            FROM currencies c
            LEFT JOIN exchange_rates er
              ON er.rate_date = %s
             AND er.base_currency_code = %s
             AND er.target_currency_code = c.code
            WHERE c.active = 1
            ORDER BY c.code
            """,
            (rate_date, base_code),
        ) or []
    except Exception as e:
        print(f"[FX] Aviso: falha ao buscar cotações para bem_vindo: {e}")
        moedas = []

    # Controlar habilitação dos botões de atualização manual
    today = date.today()
    if today.weekday() == 0:
        prev_close_date = today - timedelta(days=3)
    else:
        prev_close_date = today - timedelta(days=1)

    fx_can_update_today = True
    fx_can_update_prev_close = True

    try:
        row_today = db.fetch_one(
            """SELECT COUNT(*) AS cnt
                FROM exchange_rates
               WHERE rate_date = %s
                 AND base_currency_code = %s""",
            (today, base_code),
        )
        if row_today and (row_today.get('cnt') or 0) > 0:
            fx_can_update_today = False
    except Exception as e:
        print(f"[FX] Aviso: falha ao verificar cotações de hoje: {e}")

    try:
        row_prev = db.fetch_one(
            """SELECT COUNT(*) AS cnt
                FROM exchange_rates
               WHERE rate_date = %s
                 AND base_currency_code = %s""",
            (prev_close_date, base_code),
        )
        if row_prev and (row_prev.get('cnt') or 0) > 0:
            fx_can_update_prev_close = False
    except Exception as e:
        print(f"[FX] Aviso: falha ao verificar cotações de fechamento (D-1): {e}")

    # Buscar dados para o Dashboard
    company_id = get_company_id()
    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    inicio_mes = hoje.replace(day=1)
    
    # KPIs
    kpi = {}
    
    # OS Abertas hoje
    row = db.fetch_one("""
        SELECT COUNT(*) as cnt FROM service_orders
        WHERE company_id = %s AND DATE(opened_at) = %s AND status = 'open'
    """, (company_id, hoje))
    kpi['os_abertas'] = row['cnt'] if row else 0
    
    # OS em andamento
    row = db.fetch_one("""
        SELECT COUNT(*) as cnt FROM service_orders
        WHERE company_id = %s AND status = 'in_progress'
    """, (company_id,))
    kpi['os_andamento'] = row['cnt'] if row else 0
    
    # OS concluídas hoje
    row = db.fetch_one("""
        SELECT COUNT(*) as cnt FROM service_orders
        WHERE company_id = %s AND DATE(completed_at) = %s AND status = 'completed'
    """, (company_id, hoje))
    kpi['os_concluidas'] = row['cnt'] if row else 0
    
    # OS urgentes
    row = db.fetch_one("""
        SELECT COUNT(*) as cnt FROM service_orders
        WHERE company_id = %s AND status = 'open' AND priority = 'urgente'
    """, (company_id,))
    kpi['os_urgentes'] = row['cnt'] if row else 0
    
    # Vendas hoje
    row = db.fetch_one("""
        SELECT COALESCE(SUM(total_amount), 0) as total FROM sales
        WHERE company_id = %s AND DATE(sale_date) = %s AND status = 'completed'
    """, (company_id, hoje))
    kpi['vendas_hoje'] = f"{row['total']:.2f}".replace('.', ',') if row else '0,00'
    
    # Clientes novos este mês
    row = db.fetch_one("""
        SELECT COUNT(*) as cnt FROM customers
        WHERE company_id = %s AND DATE(created_at) >= %s
    """, (company_id, inicio_mes))
    kpi['clientes_novos'] = row['cnt'] if row else 0
    
    # OS em andamento (lista)
    os_andamento = db.fetch_all("""
        SELECT so.id, so.order_number, so.total_value, so.started_at, so.priority,
               c.name as customer_name,
               e.name as equipment_name,
               t.name as technician_name
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        LEFT JOIN equipments e ON so.equipment_id = e.id
        LEFT JOIN technicians t ON so.technician_id = t.id
        WHERE so.company_id = %s AND so.status = 'in_progress'
        ORDER BY so.started_at DESC
        LIMIT 5
    """, (company_id,))
    
    # OS recentes (abertas)
    os_recentes = db.fetch_all("""
        SELECT so.id, so.order_number, so.opened_at, so.service_type,
               c.name as customer_name
        FROM service_orders so
        JOIN customers c ON so.customer_id = c.id
        WHERE so.company_id = %s AND so.status = 'open'
        ORDER BY so.opened_at DESC
        LIMIT 5
    """, (company_id,))
    
    # Gráfico de vendas (últimos 7 dias)
    grafico_vendas = []
    max_venda = 1
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        row = db.fetch_one("""
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE company_id = %s AND DATE(sale_date) = %s AND status = 'completed'
        """, (company_id, dia))
        valor = float(row['total']) if row else 0
        grafico_vendas.append({
            'dia': dia.strftime('%d/%m'),
            'valor': f"{valor:.0f}",
            'percentual': 0  # Calculado depois
        })
        if valor > max_venda:
            max_venda = valor
    
    # Calcular percentuais
    for item in grafico_vendas:
        item['percentual'] = min(100, max(15, (float(item['valor']) / max_venda) * 100)) if max_venda > 0 else 15
    
    # Alertas
    alertas = []
    if kpi['os_urgentes'] > 0:
        alertas.append({
            'tipo': 'danger',
            'icone': 'fa-exclamation-triangle',
            'titulo': f'{kpi["os_urgentes"]} OS Urgentes',
            'descricao': 'OS com prioridade urgente aguardando atendimento'
        })
    if kpi['os_andamento'] > 5:
        alertas.append({
            'tipo': 'warning',
            'icone': 'fa-clock',
            'titulo': 'Muitas OS em Andamento',
            'descricao': f'{kpi["os_andamento"]} OS em execução simultânea'
        })
    
    # Tarefas de exemplo (placeholder - idealmente buscar de tabela tasks)
    tarefas = [
        {'id': 1, 'texto': 'Revisar estoque de óleo', 'horario': '09:00', 'priority': 'high', 'completed': False},
        {'id': 2, 'texto': 'Ligar cliente João', 'horario': '10:30', 'priority': 'medium', 'completed': True},
        {'id': 3, 'texto': 'Orçamento da Hilux', 'horario': '14:00', 'priority': 'medium', 'completed': False},
    ]
    
    # Saudação baseada na hora
    hora_atual = datetime.now().hour
    if hora_atual < 12:
        saudacao = 'Bom dia'
    elif hora_atual < 18:
        saudacao = 'Boa tarde'
    else:
        saudacao = 'Boa noite'
    
    # Verificar qual template usar (para permitir fallback)
    try:
        return render_template('dashboard_desktop.html',
                               kpi=kpi,
                               os_andamento=os_andamento or [],
                               os_recentes=os_recentes or [],
                               grafico_vendas=grafico_vendas,
                               alertas=alertas,
                               tarefas=tarefas,
                               saudacao=saudacao,
                               data_atual=hoje.strftime('%A, %d de %B de %Y').capitalize())
    except:
        # Fallback para template antigo se houver erro
        return render_template('bem_vindo.html')


@app.route('/bem-vindo/atualizar-fx', methods=['POST'])
@login_required
def bem_vindo_atualizar_fx():
    """Permite atualizar manualmente as cotações na tela inicial.

    - tipo = 'atual'     -> busca cotação do dia (hoje)
    - tipo = 'encerrada' -> busca cotação de fechamento (D-1, ou sexta se hoje for segunda)
    """
    from datetime import date, timedelta

    tipo = (request.form.get('tipo') or '').strip()
    today = date.today()

    if tipo == 'atual':
        target_date = today
        label = 'atual'
    else:
        # Cotação de fechamento do dia anterior (D-1). Se hoje for segunda,
        # usamos a sexta-feira anterior.
        if today.weekday() == 0:
            target_date = today - timedelta(days=3)
        else:
            target_date = today - timedelta(days=1)
        label = 'encerrada'

    try:
        db = get_db()
        fx_service = ExchangeRateService()
        base_code = fx_service.base_currency.upper()

        # Se já existir qualquer taxa para esta data/base, não chamar API novamente
        row = db.fetch_one(
            """SELECT COUNT(*) AS cnt
                FROM exchange_rates
               WHERE rate_date = %s
                 AND base_currency_code = %s""",
            (target_date, base_code),
        )
        if row and (row.get('cnt') or 0) > 0:
            flash(
                f"Cotações {label} já existentes para a data "
                f"{target_date.strftime('%d/%m/%Y')}.", 'info'
            )
        else:
            result_fx = fx_service.update_daily_rates(rate_date=target_date)
            if result_fx.get('success'):
                msg = (
                    f"Cotações {label} atualizadas para {result_fx.get('count', 0)} "
                    f"moeda(s) na data {target_date.strftime('%d/%m/%Y')}."
                )
                flash(msg, 'success')
            else:
                msg = result_fx.get('message') or 'Falha ao atualizar cotações.'
                flash(msg, 'warning')
            print(f"[FX] Atualização manual de câmbio ({label}) no bem_vindo: {result_fx}")
    except Exception as e:
        print(f"[FX] Erro ao atualizar câmbio manualmente ({tipo}): {e}")
        flash('Erro ao atualizar cotações. Verifique os logs.', 'danger')

    # Redirecionar para a tela bem_vindo já apontando para a data usada
    return redirect(url_for('bem_vindo', fx_date=target_date.isoformat()))


@app.route('/apresentacao-ikflow')
@login_required
def apresentacao_ikflow():
    """Apresentação do IK Flow / IK Analytics (exige login)."""
    try:
        return render_template('apresentacao_ikflow.html')
    except Exception as e:
        print(f"[IKFLOW] Erro ao renderizar apresentacao_ikflow: {e}")
        return render_template('apresentacao_ikflow.html')


@app.route('/apresentacao-ikflow-v2')
@login_required
def apresentacao_ikflow_v2():
    """Nova versão da apresentação IK Flow (exige login)."""
    try:
        return render_template('apresentacao_ikflow_v2.html')
    except Exception as e:
        print(f"[IKFLOW] Erro ao renderizar apresentacao_ikflow_v2: {e}")
        return render_template('apresentacao_ikflow_v2.html')

@app.route('/em-desenvolvimento')
@app.route('/em-desenvolvimento/<path:funcionalidade>')
@login_required
def em_desenvolvimento(funcionalidade=None):
    """Página padrão para funcionalidades em desenvolvimento"""
    _MODULOS = {
        'agenda': {
            'titulo': 'Agenda & Agendamento Inteligente',
            'icone': '📅',
            'descricao': 'Calendário visual por mecânico, agendamento com horário marcado e agendamento preventivo automático com base no histórico do veículo.',
            'prazo': 'Julho / 2026',
            'features': [
                {'icone': '📆', 'titulo': 'Calendário por Mecânico', 'desc': 'Visualização diária e semanal da agenda de cada profissional.'},
                {'icone': '⏰', 'titulo': 'Agendamento com Confirmação', 'desc': 'Cliente agenda horário + serviço. Sistema envia confirmação via WhatsApp.'},
                {'icone': '🔁', 'titulo': 'Preventivo Automático', 'desc': 'Ao concluir OS, calcula e agenda próxima revisão por KM ou prazo automaticamente.'},
                {'icone': '🔔', 'titulo': 'Lembrete de Revisão', 'desc': 'Disparo automático 7 dias antes da revisão programada via WhatsApp.'},
            ]
        },
        'comissoes': {
            'titulo': 'Comissionamento de Mecânicos',
            'icone': '💰',
            'descricao': 'Cálculo automático de comissões por OS concluída, valor de mão de obra ou peças vendidas. Relatório mensal por colaborador.',
            'prazo': 'Agosto / 2026',
            'features': [
                {'icone': '🔧', 'titulo': 'Comissão por OS', 'desc': 'Percentual sobre o valor total ou apenas mão de obra por OS concluída.'},
                {'icone': '🏷️', 'titulo': 'Comissão por Captação', 'desc': 'Percentual para vendedor/indicador que trouxe o cliente.'},
                {'icone': '📊', 'titulo': 'Relatório Mensal', 'desc': 'Extrato individual por colaborador com valores apurados.'},
                {'icone': '📤', 'titulo': 'Exportação para Folha', 'desc': 'Exportação em planilha para integração com sistema de RH.'},
            ]
        },
        'garantia': {
            'titulo': 'Controle de Garantia',
            'icone': '🛡️',
            'descricao': 'Registro de garantia por serviço e peça trocada, com alertas automáticos de vencimento e histórico de acionamentos.',
            'prazo': 'Agosto / 2026',
            'features': [
                {'icone': '📋', 'titulo': 'Garantia por OS', 'desc': 'Prazo de garantia do serviço vinculado à OS concluída.'},
                {'icone': '🔩', 'titulo': 'Garantia por Peça', 'desc': 'Prazo de garantia individual de cada peça trocada com número de série.'},
                {'icone': '🔔', 'titulo': 'Alertas de Vencimento', 'desc': 'Notificação ao cliente e à equipe quando garantia está próxima do fim.'},
                {'icone': '📝', 'titulo': 'Histórico de Acionamentos', 'desc': 'Registro de todas as reclamações e retornos em garantia.'},
            ]
        },
        'venda-balcao': {
            'titulo': 'Venda no Balcão (PDV)',
            'icone': '🛒',
            'descricao': 'Venda direta de peças e serviços no balcão com emissão de cupom, NF-e e integração com estoque em tempo real.',
            'prazo': 'Junho / 2026',
            'features': [
                {'icone': '⚡', 'titulo': 'PDV Rápido', 'desc': 'Interface otimizada para venda ágil com busca por código ou nome da peça.'},
                {'icone': '💳', 'titulo': 'Multi-pagamento', 'desc': 'PIX, cartão, dinheiro, crédito da loja — tudo em uma tela.'},
                {'icone': '🧾', 'titulo': 'Cupom / NF-e / NFC-e', 'desc': 'Emissão fiscal integrada ao momento da venda.'},
                {'icone': '📦', 'titulo': 'Baixa Automática de Estoque', 'desc': 'Cada item vendido deduz automaticamente do estoque.'},
            ]
        },
        'boleto': {
            'titulo': 'Boleto Bancário',
            'icone': '📄',
            'descricao': 'Emissão de boletos pelo Banco do Brasil e Mercado Pago, com envio automático por WhatsApp e baixa automática ao confirmar pagamento.',
            'prazo': 'Setembro / 2026',
            'features': [
                {'icone': '🏦', 'titulo': 'Banco do Brasil', 'desc': 'Integração com API do BB para emissão de boletos registrados.'},
                {'icone': '🛒', 'titulo': 'Mercado Pago', 'desc': 'Boleto + link de pagamento via Mercado Pago.'},
                {'icone': '📲', 'titulo': 'Envio por WhatsApp', 'desc': 'Boleto enviado automaticamente no WhatsApp ao gerar.'},
                {'icone': '✅', 'titulo': 'Baixa Automática', 'desc': 'Confirmação via webhook — Contas a Receber atualizado automaticamente.'},
            ]
        },
        'ponto': {
            'titulo': 'Controle de Ponto e RH',
            'icone': '👷',
            'descricao': 'Registro de ponto ao logar no sistema, controle de jornada, faltas e atrasos com relatório mensal para folha de pagamento.',
            'prazo': 'Agosto / 2026',
            'features': [
                {'icone': '🕐', 'titulo': 'Ponto Digital', 'desc': 'Registro de entrada/saída ao acessar o sistema, com geolocalização por rede.'},
                {'icone': '📅', 'titulo': 'Espelho de Ponto', 'desc': 'Relatório mensal individual com horas trabalhadas, extras, faltas.'},
                {'icone': '⚠️', 'titulo': 'Alertas de Atraso', 'desc': 'Notificação ao gestor em tempo real quando há atraso ou ausência.'},
                {'icone': '📊', 'titulo': 'Relatório para Folha', 'desc': 'Exportação das informações para cálculo de folha de pagamento.'},
            ]
        },
        'app-mecanico': {
            'titulo': 'App Mobile do Mecânico',
            'icone': '📱',
            'descricao': 'Aplicativo para Android e iOS que permite ao mecânico visualizar sua fila de OS, iniciar/finalizar serviços e registrar ponto pelo celular.',
            'prazo': 'Outubro / 2026',
            'features': [
                {'icone': '📋', 'titulo': 'Fila de OS', 'desc': 'Mecânico vê suas OS do dia ordenadas por prioridade.'},
                {'icone': '▶️', 'titulo': 'Iniciar/Finalizar Serviço', 'desc': 'Toque para iniciar e concluir — cronômetro automático.'},
                {'icone': '📸', 'titulo': 'Fotos do Serviço', 'desc': 'Registrar fotos antes e depois do serviço diretamente na OS.'},
                {'icone': '⏱️', 'titulo': 'Ponto pelo App', 'desc': 'Registro de ponto com validação por WiFi da oficina.'},
            ]
        },
        'portal-cliente': {
            'titulo': 'Portal do Cliente',
            'icone': '🌐',
            'descricao': 'Área exclusiva onde o cliente acessa o histórico completo do veículo, acompanha OS em aberto, baixa notas fiscais e aprova orçamentos.',
            'prazo': 'Setembro / 2026',
            'features': [
                {'icone': '🚗', 'titulo': 'Histórico do Veículo', 'desc': 'Todas as OS e serviços realizados, organizados por data.'},
                {'icone': '📊', 'titulo': 'OS em Tempo Real', 'desc': 'Acompanhe o andamento do serviço em tempo real.'},
                {'icone': '✅', 'titulo': 'Aprovar Orçamento Online', 'desc': 'Cliente aprova orçamento com um clique pelo celular.'},
                {'icone': '🧾', 'titulo': 'Download de Notas', 'desc': 'Acesse e baixe NF-e e NFS-e emitidas para cada serviço.'},
            ]
        },
        'relatorios': {
            'titulo': 'Relatórios Gerenciais',
            'icone': '📊',
            'descricao': 'Dashboard executivo com KPIs da oficina: faturamento, produtividade por mecânico, peças mais consumidas, clientes VIP e projeções.',
            'prazo': 'Julho / 2026',
            'features': [
                {'icone': '💵', 'titulo': 'Faturamento por Período', 'desc': 'Receita bruta, serviços x peças, comparativo mensal/anual.'},
                {'icone': '🔧', 'titulo': 'Produtividade por Mecânico', 'desc': 'OS concluídas, tempo médio, comissões geradas.'},
                {'icone': '📦', 'titulo': 'Peças Mais Consumidas', 'desc': 'Ranking de peças por quantidade e valor, auxiliando no estoque mínimo.'},
                {'icone': '⭐', 'titulo': 'Clientes VIP', 'desc': 'Ranking de clientes por faturamento e frequência de visita.'},
            ]
        },
    }
    dados = _MODULOS.get(funcionalidade, {
        'titulo': 'Módulo em Implantação',
        'icone': '⚙️',
        'descricao': 'Esta funcionalidade está sendo desenvolvida especialmente para você. Em breve estará disponível!',
        'prazo': None,
        'features': []
    })
    return render_template('em_desenvolvimento.html', funcionalidade=funcionalidade, **dados)

@app.route('/pwa/inicio')
@login_required
def pwa_inicio():
    """Redireciona para o PWA correto conforme o role do usuário logado."""
    role = (session.get('role') or '').lower()
    if role in ('mecanico', 'mechanic'):
        return redirect(url_for('mecanico.index'))
    if role in ('atendente', 'auxiliar'):
        return redirect(url_for('atendente.index'))
    return redirect(url_for('bem_vindo'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        print(f"\n[AUTH] Tentativa de login: username={username}")
        
        # Verificar se o banco de dados está conectado
        try:
            db = get_db()
            print("[AUTH] Conexão com o banco de dados estabelecida")
        except Exception as e:
            print(f"[AUTH] Erro ao conectar ao banco de dados: {e}")
            flash('Erro ao conectar ao banco de dados. Tente novamente mais tarde.', 'danger')
            return render_template('login.html')
        
        # Buscar usuário pelo nome de usuário
        try:
            user = get_user_by_username(username)
            print(f"[AUTH] Usuário encontrado: {bool(user)}")
        except Exception as e:
            print(f"[AUTH] Erro ao buscar usuário: {e}")
            flash('Erro ao buscar usuário. Tente novamente mais tarde.', 'danger')
            return render_template('login.html')
        
        # Verificar autenticação
        if not user:
            print(f"[AUTH] Usuário não encontrado: {username}")
            flash('Usuário ou senha inválidos. Tente novamente.', 'danger')
            return render_template('login.html')

        is_valid_password = False
        try:
            # Compatibilidade: aceita hash ou senha em texto se ainda não migrado
            is_valid_password = (user.get('password') == password) or verify_password(user.get('password', ''), password)
        except Exception as e:
            print(f"[AUTH] Erro ao validar senha: {e}")

        # Verificar status do usuário (aceita 'status' ou 'active')
        user_status = user.get('status')
        user_active = user.get('active')
        is_user_active = (user_status == 'active') or (user_active == 1) or (user_active == True)
        
        if is_valid_password and is_user_active:
            print(f"[AUTH] Login bem-sucedido para {username}")
            session['username'] = username
            session['role'] = user.get('role')
            session['user_id'] = user.get('id')
            session['eh_vendedor'] = bool(user.get('eh_vendedor') or user.get('is_seller'))
            session['eh_operador'] = bool(user.get('eh_operador'))
            session['eh_lider_equipe'] = bool(user.get('eh_lider_equipe'))

            # Carregar permissões do usuário na sessão
            try:
                from utils.permissoes_helper import carregar_permissoes_usuario
                session['permissoes'] = carregar_permissoes_usuario(int(user.get('id')))
                print(f"[AUTH] Permissoes carregadas: {len(session['permissoes'])} telas")
            except Exception as e:
                print(f"[AUTH] Aviso: falha ao carregar permissoes: {e}")
                session['permissoes'] = {}

            # Evitar que uma sessão residual prenda uma empresa anterior.
            # A empresa só deve ser definida após avaliarmos os vínculos do usuário.
            session.pop('empresa_id', None)
            session.pop('app_mode', None)

            try:
                login_user(User(int(user.get('id')), username, user.get('role')))
            except Exception as e:
                print(f"[AUTH] Aviso: falha ao registrar login_user: {e}")

            # Atualizar cotações uma vez por dia (no primeiro login do dia)
            try:
                today_str = datetime.utcnow().strftime('%Y-%m-%d')
                last_fx_update = session.get('last_fx_update')
                if last_fx_update != today_str:
                    fx_service = ExchangeRateService()
                    from datetime import date, timedelta
                    today = date.today()
                    # weekday(): Monday=0, Sunday=6
                    if today.weekday() == 0:
                        # Segunda-feira -> usar sexta-feira (3 dias antes)
                        target_date = today - timedelta(days=3)
                    else:
                        # Demais dias -> usar ontem
                        target_date = today - timedelta(days=1)
                    result_fx = fx_service.update_daily_rates(rate_date=target_date)
                    print(f"[FX] Atualização diária de câmbio no login: {result_fx}")
                    session['last_fx_update'] = today_str
            except Exception as e:
                print(f"[FX] Aviso: falha ao atualizar câmbio no login: {e}")

            # Buscar empresas vinculadas (para qualquer role).
            # Regra:
            # - Se houver 1 empresa -> entra direto nela
            # - Se houver 2+ -> obrigar seleção (inclusive admin)
            # - Se não houver -> apenas admin entra sem empresa; demais são bloqueados
            try:
                empresas = _get_user_empresas(int(user.get('id')))
            except Exception as e:
                print(f"[AUTH] Erro ao buscar empresas do usuário: {e}")
                empresas = []

            if empresas and len(empresas) == 1:
                _set_empresa_in_session(empresas[0])
                flash('Login realizado com sucesso!', 'success')
                # Redirecionar para PWA conforme role
                _role = (session.get('role') or '').lower()
                if _role in ('mecanico', 'mechanic'):
                    return redirect(url_for('mecanico.index'))
                if _role in ('atendente', 'auxiliar'):
                    return redirect(url_for('atendente.index'))
                return redirect(url_for('bem_vindo'))

            if empresas and len(empresas) > 1:
                flash('Selecione a empresa para acessar.', 'info')
                return redirect(url_for('selecionar_empresa'))

            # Sem empresas vinculadas
            if session.get('role') == 'admin':
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('bem_vindo'))

            session.pop('username', None)
            session.pop('role', None)
            session.pop('user_id', None)
            flash('Usuário sem empresa vinculada. Contate o administrador.', 'danger')
            return redirect(url_for('login'))
        else:
            if user.get('status') != 'active':
                print("[AUTH] Usuário inativo")
            else:
                print(f"[AUTH] Senha inválida para {username}")
            flash('Usuário ou senha inválidos. Tente novamente.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    try:
        logout_user()
    except Exception as e:
        print(f"[AUTH] Aviso: falha ao executar logout_user: {e}")
    session.pop('username', None)
    session.pop('role', None)
    session.pop('user_id', None)
    session.pop('empresa_id', None)
    session.pop('app_mode', None)
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

@app.route('/selecionar-empresa', methods=['GET', 'POST'])
@login_required
def selecionar_empresa():
    # Se já existe empresa selecionada nesta sessão, não permitir troca sem novo login
    if session.get('empresa_id'):
        return redirect(url_for('bem_vindo'))

    user_id = session.get('user_id')
    if not user_id:
        flash('Sessão inválida. Faça login novamente.', 'danger')
        return redirect(url_for('login'))

    empresas = _get_user_empresas(int(user_id))
    if not empresas:
        flash('Usuário sem empresa vinculada. Contate o administrador.', 'danger')
        return redirect(url_for('logout'))

    if request.method == 'POST':
        empresa_id = request.form.get('empresa_id', '').strip()
        if not empresa_id.isdigit():
            flash('Selecione uma empresa válida.', 'danger')
            return render_template('selecionar_empresa_trabalho.html', empresas=empresas)

        empresa_id_int = int(empresa_id)
        empresa_sel = next((e for e in empresas if int(e['id']) == empresa_id_int), None)
        if not empresa_sel:
            flash('Empresa não permitida para este usuário.', 'danger')
            return render_template('selecionar_empresa_trabalho.html', empresas=empresas)

        _set_empresa_in_session(empresa_sel)
        flash('Empresa selecionada com sucesso!', 'success')
        return redirect(url_for('bem_vindo'))

    # Se só tiver 1 empresa, não precisa perguntar
    if len(empresas) == 1:
        _set_empresa_in_session(empresas[0])
        return redirect(url_for('bem_vindo'))

    return render_template('selecionar_empresa_trabalho.html', empresas=empresas)

# Rota do dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    # Contagem de itens
    db = get_db()
    result = db.fetch_one("SELECT COUNT(*) as count FROM customers WHERE active = TRUE")
    customers_count = result['count'] if result else 0
    result = db.fetch_one("SELECT COUNT(*) as count FROM products WHERE active = TRUE")
    products_count = result['count'] if result else 0
    result = db.fetch_one("SELECT COUNT(*) as count FROM supplies WHERE active = TRUE")
    supplies_count = result['count'] if result else 0
    result = db.fetch_one("SELECT COUNT(*) as count FROM suppliers WHERE active = TRUE")
    suppliers_count = result['count'] if result else 0
    
    # Insumos com estoque baixo
    low_stock_supplies = get_low_stock_supplies()
    
    # Equipamentos para manutenção
    maintenance_equipment = get_maintenance_equipment()
    
    return render_template(
        'dashboard.html',
        active_page='dashboard',
        customers_count=customers_count,
        products_count=products_count,
        supplies_count=supplies_count,
        suppliers_count=suppliers_count,
        low_stock_supplies=low_stock_supplies,
        maintenance_equipment=maintenance_equipment
    )

@app.route('/debug')
@login_required
def debug():
    return render_template('debug.html')

@app.route('/docs/<path:filename>')
@login_required
def serve_docs(filename):
    """Serve arquivos de documentação, incluindo o manual do usuário"""
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
    
    # Verificar se o arquivo existe
    file_path = os.path.join(docs_dir, filename)
    if not os.path.isfile(file_path):
        abort(404)
    
    # Se for um arquivo markdown, converter para HTML
    if filename.endswith('.md'):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Converter markdown para HTML
            html_content = markdown.markdown(
                content,
                extensions=['tables', 'fenced_code', 'codehilite', 'toc']
            )
            # Adicionar estilos básicos
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Manual do Usuário</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    body {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
                    h1, h2, h3 {{ color: #0d6efd; margin-top: 30px; }}
                    code {{ background-color: #f8f9fa; padding: 2px 4px; border-radius: 4px; }}
                    pre {{ background-color: #f8f9fa; padding: 15px; border-radius: 8px; overflow-x: auto; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                    th, td {{ padding: 8px; border: 1px solid #dee2e6; }}
                    th {{ background-color: #e9ecef; }}
                    img {{ max-width: 100%; height: auto; }}
                    .container {{ padding: 20px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <a href="/dashboard" class="btn btn-primary mb-4">← Voltar ao Dashboard</a>
                    {html_content}
                </div>
                <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
            </body>
            </html>
            """
            return styled_html
    
    # Para outros tipos de arquivo, servir normalmente
    return send_from_directory(docs_dir, filename)

@app.route('/busca-global')
@login_required
def busca_global():
    """Busca global para o header mobile PWA."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'results': []})

    db = get_db()
    results = []
    like = f'%{q}%'

    try:
        # OS / Ordens de serviço
        rows = db.fetch_all("""
            SELECT so.id, so.order_number, c.name as customer_name,
                   e.serial_number as placa, so.status
            FROM service_orders so
            LEFT JOIN customers c ON c.id = so.customer_id
            LEFT JOIN equipment e ON e.id = so.equipment_id
            WHERE so.order_number LIKE %s OR c.name LIKE %s OR e.serial_number LIKE %s
            LIMIT 5
        """, (like, like, like))
        for r in rows:
            results.append({
                'title': f'OS {r["order_number"]}',
                'subtitle': f'{r.get("customer_name","") or ""} — {r.get("placa","") or ""}',
                'url': f'/service_orders/{r["id"]}',
                'icon': 'fa-clipboard-list',
                'color': '#0b2447',
            })
    except Exception:
        pass

    try:
        # Clientes
        rows = db.fetch_all("""
            SELECT id, name, phone, cpf_cnpj FROM customers
            WHERE name LIKE %s OR cpf_cnpj LIKE %s OR phone LIKE %s
            LIMIT 4
        """, (like, like, like))
        for r in rows:
            results.append({
                'title': r['name'],
                'subtitle': r.get('phone') or r.get('cpf_cnpj') or 'Cliente',
                'url': f'/clientes/{r["id"]}',
                'icon': 'fa-user',
                'color': '#8b7bff',
            })
    except Exception:
        pass

    try:
        # Veículos / Equipamentos
        rows = db.fetch_all("""
            SELECT e.id, e.serial_number as placa, e.name as modelo,
                   c.name as customer_name
            FROM equipment e
            LEFT JOIN customers c ON c.id = e.customer_id
            WHERE e.serial_number LIKE %s OR e.name LIKE %s
            LIMIT 4
        """, (like, like))
        for r in rows:
            results.append({
                'title': r.get('placa') or r.get('modelo') or 'Veículo',
                'subtitle': r.get('customer_name') or 'Veículo',
                'url': f'/veiculos/{r["id"]}/historico',
                'icon': 'fa-car',
                'color': '#08a5b2',
            })
    except Exception:
        pass

    try:
        # Peças / Produtos
        rows = db.fetch_all("""
            SELECT id, name, sku FROM products
            WHERE name LIKE %s OR sku LIKE %s
            LIMIT 3
        """, (like, like))
        for r in rows:
            results.append({
                'title': r['name'],
                'subtitle': f'SKU: {r.get("sku","") or "—"}',
                'url': f'/produtos/{r["id"]}',
                'icon': 'fa-wrench',
                'color': '#ff9f1a',
            })
    except Exception:
        pass

    return jsonify({'results': results[:12]})


# =====================================================
# TEARDOWN: Fechar conexões ao fim de cada request
# =====================================================
@app.teardown_appcontext
def close_db_connection(error):
    """Fecha conexão do banco ao fim de cada request para liberar pool"""
    from database import _thread_local
    if hasattr(_thread_local, 'db'):
        try:
            _thread_local.db.close()
        except:
            pass
        finally:
            delattr(_thread_local, 'db')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
