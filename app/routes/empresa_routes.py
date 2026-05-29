"""
Rotas para o módulo de Cadastro de Empresas.
CRUD completo: Listar, Cadastrar, Editar, Visualizar
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.utils import secure_filename
import re
import os

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required
from utils.permissoes_helper import requer_permissao, tem_permissao

# Configurações de upload
UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads', 'logos')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

# Criar pasta de upload se não existir
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Criar um Blueprint para as rotas de empresa
empresa_bp = Blueprint('empresa', __name__)


_EMPRESA_HAS_APP_MODE = None
_EMPRESA_HAS_MOEDA_FUNCIONAL = None


def _empresa_has_app_mode(db) -> bool:
    global _EMPRESA_HAS_APP_MODE
    # Importante: não cachear indefinidamente o "False".
    # Em desenvolvimento, é comum adicionar a coluna via ALTER TABLE enquanto o servidor está rodando.
    # Se cachearmos False, o app nunca vai perceber a mudança até reiniciar.
    if _EMPRESA_HAS_APP_MODE is True:
        return True
    try:
        row = db.fetch_one(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'empresas'
              AND column_name = 'app_mode'
            """
        )
        _EMPRESA_HAS_APP_MODE = bool(row and int(row.get('cnt') or 0) > 0)
    except Exception:
        _EMPRESA_HAS_APP_MODE = False
    return bool(_EMPRESA_HAS_APP_MODE)


def _get_moedas_funcionais(db):
    try:
        return db.fetch_all(
            "SELECT code, name FROM currencies WHERE active = 1 ORDER BY code"
        ) or []
    except Exception:
        return []


def _get_countries(db):
    """Retorna a lista de países cadastrados na tabela countries.

    Estrutura esperada da tabela countries:
      code, name, tax_id_label, zip_label, default_currency_code
    """
    try:
        return db.fetch_all(
            "SELECT code, name, tax_id_label, zip_label, default_currency_code FROM countries ORDER BY name"
        ) or []
    except Exception:
        return []


# Decorators para verificar permissões granulares
def empresa_visualizar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('admin.empresas', 'visualizar'):
            flash('Você não tem permissão para visualizar empresas.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function

def empresa_criar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('admin.empresas', 'criar'):
            flash('Você não tem permissão para cadastrar empresas.', 'danger')
            return redirect(url_for('empresa.empresas'))
        return f(*args, **kwargs)
    return decorated_function

def empresa_editar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('admin.empresas', 'editar'):
            flash('Você não tem permissão para editar empresas.', 'danger')
            return redirect(url_for('empresa.empresas'))
        return f(*args, **kwargs)
    return decorated_function

def empresa_excluir_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('admin.empresas', 'excluir'):
            flash('Você não tem permissão para excluir empresas.', 'danger')
            return redirect(url_for('empresa.empresas'))
        return f(*args, **kwargs)
    return decorated_function

# Alias para compatibilidade
admin_required = empresa_visualizar_required

# =============================
# LISTAR EMPRESAS
# =============================

@empresa_bp.route('/empresas')
@admin_required
def empresas():
    """Lista todas as empresas cadastradas."""
    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    # Verificar se há parâmetros de busca
    search_term = request.args.get('search_term', '')
    search_field = request.args.get('search_field', 'all')
    
    # Buscar empresas ativas no banco de dados
    db = get_db()

    has_app_mode = _empresa_has_app_mode(db)
    select_app_mode = "COALESCE(app_mode, 'global') AS app_mode" if has_app_mode else "'global' AS app_mode"
    
    # Construir query base e count query
    if search_term:
        # Construir a consulta SQL com base no campo de busca
        if search_field == 'razao_social':
            query = f"SELECT *, {select_app_mode} FROM empresas WHERE ativo = TRUE AND razao_social LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM empresas WHERE ativo = TRUE AND razao_social LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'nome_fantasia':
            query = f"SELECT *, {select_app_mode} FROM empresas WHERE ativo = TRUE AND nome_fantasia LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM empresas WHERE ativo = TRUE AND nome_fantasia LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'cnpj':
            query = f"SELECT *, {select_app_mode} FROM empresas WHERE ativo = TRUE AND cnpj LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM empresas WHERE ativo = TRUE AND cnpj LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'cidade':
            query = f"SELECT *, {select_app_mode} FROM empresas WHERE ativo = TRUE AND cidade LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM empresas WHERE ativo = TRUE AND cidade LIKE %s"
            params = (f'%{search_term}%',)
        else:  # search_field == 'all'
            query = f"""
                SELECT *, {select_app_mode} FROM empresas 
                WHERE ativo = TRUE 
                AND (razao_social LIKE %s OR nome_fantasia LIKE %s OR cnpj LIKE %s OR cidade LIKE %s)
            """
            count_query = """
                SELECT COUNT(*) as total FROM empresas 
                WHERE ativo = TRUE 
                AND (razao_social LIKE %s OR nome_fantasia LIKE %s OR cnpj LIKE %s OR cidade LIKE %s)
            """
            params = (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')
        
        query += " ORDER BY razao_social LIMIT %s OFFSET %s"
        empresas = db.fetch_all(query, params + (per_page, offset))
        total_result = db.fetch_one(count_query, params)
    else:
        # Buscar todas as empresas ativas
        query = f"SELECT *, {select_app_mode} FROM empresas WHERE ativo = TRUE ORDER BY razao_social LIMIT %s OFFSET %s"
        empresas = db.fetch_all(query, (per_page, offset))
        total_result = db.fetch_one("SELECT COUNT(*) as total FROM empresas WHERE ativo = TRUE")
    
    total_empresas = total_result['total'] if total_result else 0
    total_pages = (total_empresas + per_page - 1) // per_page
    
    return render_template(
        'empresa_list.html',
        empresas=empresas,
        page=page,
        total_pages=total_pages,
        search_term=search_term,
        search_field=search_field,
        active_page='empresas'
    )

# =============================
# VISUALIZAR EMPRESA
# =============================

@empresa_bp.route('/empresas/<int:id>')
@admin_required
def empresa_visualizar(id):
    """Visualiza os detalhes de uma empresa."""
    db = get_db()
    has_app_mode = _empresa_has_app_mode(db)
    select_app_mode = "COALESCE(app_mode, 'global') AS app_mode" if has_app_mode else "'global' AS app_mode"
    empresa = db.fetch_one(
        f"SELECT *, {select_app_mode} FROM empresas WHERE id = %s AND ativo = TRUE",
        (id,),
    )
    
    if not empresa:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('empresa.empresas'))
    
    return render_template(
        'empresa_view.html',
        empresa=empresa,
        active_page='empresas'
    )

# =============================
# CADASTRAR EMPRESA
# =============================

@empresa_bp.route('/empresas/cadastrar', methods=['GET', 'POST'])
@empresa_criar_required
def empresa_cadastrar():
    """Cadastra uma nova empresa."""
    if request.method == 'POST':
        # Obter dados do formulário
        razao_social = request.form.get('razao_social', '').strip()
        nome_fantasia = request.form.get('nome_fantasia', '').strip()
        cnpj = request.form.get('cnpj', '').strip()
        inscricao_estadual = request.form.get('inscricao_estadual', '').strip()
        inscricao_municipal = request.form.get('inscricao_municipal', '').strip()
        
        telefone = request.form.get('telefone', '').strip()
        celular = request.form.get('celular', '').strip()
        email = request.form.get('email', '').strip()
        website = request.form.get('website', '').strip()
        
        cep = request.form.get('cep', '').strip()
        logradouro = request.form.get('logradouro', '').strip()
        numero = request.form.get('numero', '').strip()
        complemento = request.form.get('complemento', '').strip()
        bairro = request.form.get('bairro', '').strip()
        cidade = request.form.get('cidade', '').strip()
        estado = request.form.get('estado', '').strip()
        pais = request.form.get('pais', 'Brasil').strip()
        
        regime_tributario = request.form.get('regime_tributario', '')
        cnae_principal = request.form.get('cnae_principal', '').strip()
        natureza_juridica = request.form.get('natureza_juridica', '').strip()
        modelo_nfe = request.form.get('modelo_nfe', 'antigo')  # Padrão: antigo
        ambiente_nfe = request.form.get('ambiente_nfe', '2')  # Padrão: 2 (homologação)
        
        # Campos NFC-e (CSC separado por ambiente)
        ambiente_nfce = request.form.get('ambiente_nfce', '2')  # Padrão: 2 (homologação)
        csc_nfce_homologacao = request.form.get('csc_nfce_homologacao', '').strip()
        id_csc_nfce_homologacao = request.form.get('id_csc_nfce_homologacao', '').strip()
        csc_nfce_producao = request.form.get('csc_nfce_producao', '').strip()
        id_csc_nfce_producao = request.form.get('id_csc_nfce_producao', '').strip()
        
        # CORREÇÃO #1: Usar bank_account_id ao invés de campos duplicados
        bank_account_id = request.form.get('bank_account_id', '')
        if bank_account_id and bank_account_id.isdigit():
            bank_account_id = int(bank_account_id)
        else:
            bank_account_id = None
        
        # Campos legados (serão removidos após migração)
        banco = request.form.get('banco', '').strip()
        agencia = request.form.get('agencia', '').strip()
        conta = request.form.get('conta', '').strip()
        tipo_conta = request.form.get('tipo_conta', '')
        
        capital_social = request.form.get('capital_social', '').strip()
        data_abertura = request.form.get('data_abertura', '').strip()
        responsavel_legal = request.form.get('responsavel_legal', '').strip()
        cpf_responsavel = request.form.get('cpf_responsavel', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        moeda_funcional = (request.form.get('moeda_funcional', 'BRL') or 'BRL').strip().upper()[:3]
        
        # Validações básicas
        db = get_db()

        if not razao_social:
            flash('Razão Social é obrigatória.', 'danger')
            moedas = _get_moedas_funcionais(db)
            countries = _get_countries(db)
            return render_template('empresa_form.html', empresa=None, active_page='empresas', moedas=moedas, countries=countries)
        
        if not nome_fantasia:
            flash('Nome Fantasia é obrigatório.', 'danger')
            moedas = _get_moedas_funcionais(db)
            countries = _get_countries(db)
            return render_template('empresa_form.html', empresa=None, active_page='empresas', moedas=moedas, countries=countries)
        
        if not cnpj:
            flash('CNPJ é obrigatório.', 'danger')
            moedas = _get_moedas_funcionais(db)
            countries = _get_countries(db)
            return render_template('empresa_form.html', empresa=None, active_page='empresas', moedas=moedas, countries=countries)
        
        # Verificar se CNPJ já existe
        db = get_db()
        empresa_existente = db.fetch_one(
            "SELECT * FROM empresas WHERE cnpj = %s AND ativo = TRUE", 
            (cnpj,)
        )
        
        if empresa_existente:
            flash(f'CNPJ {cnpj} já está cadastrado para a empresa {empresa_existente["razao_social"]}.', 'danger')
            moedas = _get_moedas_funcionais(db)
            countries = _get_countries(db)
            return render_template('empresa_form.html', empresa=None, active_page='empresas', moedas=moedas, countries=countries)
        
        # Processar upload de logo
        logo_path = None
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                from datetime import datetime
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(filename)
                filename = f"empresa_{timestamp}{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                logo_path = f"uploads/logos/{filename}"
        
        # Processar checkbox "Usar no PDV" (multiloja)
        usar_no_pdv = 1 if request.form.get('usar_no_pdv') else 0

        app_mode = (request.form.get('app_mode', 'global') or 'global').strip().lower()
        if app_mode not in ('global', 'industrial', 'varejo'):
            app_mode = 'global'
        
        # REMOVIDO: Restrição de apenas uma empresa no PDV
        # Agora permite múltiplas empresas com usar_no_pdv = 1
        
        # Por padrão, novas empresas são cadastradas como ativas
        # (o soft delete é feito marcando ativo = FALSE em empresa_excluir)
        ativo = True

        # Converter capital_social para decimal
        try:
            capital_social_decimal = float(capital_social.replace(',', '.')) if capital_social else None
        except ValueError:
            capital_social_decimal = None
        
        has_app_mode = _empresa_has_app_mode(db)

        if has_app_mode:
            query = """
                INSERT INTO empresas (
                    razao_social, nome_fantasia, cnpj, inscricao_estadual, inscricao_municipal,
                    telefone, celular, email, website, logo_path, usar_no_pdv, app_mode,
                    cep, logradouro, numero, complemento, bairro, cidade, estado, pais, moeda_funcional,
                    regime_tributario, cnae_principal, natureza_juridica, modelo_nfe, ambiente_nfe,
                    ambiente_nfce, csc_nfce_homologacao, id_csc_nfce_homologacao, csc_nfce_producao, id_csc_nfce_producao,
                    bank_account_id,
                    banco, agencia, conta, tipo_conta,
                    capital_social, data_abertura, responsavel_legal, cpf_responsavel, observacoes,
                    ativo, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, NOW()
                )
            """
        else:
            query = """
                INSERT INTO empresas (
                    razao_social, nome_fantasia, cnpj, inscricao_estadual, inscricao_municipal,
                    telefone, celular, email, website, logo_path, usar_no_pdv,
                    cep, logradouro, numero, complemento, bairro, cidade, estado, pais, moeda_funcional,
                    regime_tributario, cnae_principal, natureza_juridica, modelo_nfe, ambiente_nfe,
                    ambiente_nfce, csc_nfce_homologacao, id_csc_nfce_homologacao, csc_nfce_producao, id_csc_nfce_producao,
                    bank_account_id,
                    banco, agencia, conta, tipo_conta,
                    capital_social, data_abertura, responsavel_legal, cpf_responsavel, observacoes,
                    ativo, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, NOW()
                )
            """

        if has_app_mode:
            params = (
                razao_social, nome_fantasia, cnpj, inscricao_estadual or None, inscricao_municipal or None,
                telefone or None, celular or None, email or None, website or None, logo_path, usar_no_pdv, app_mode,
                cep or None, logradouro or None, numero or None, complemento or None, bairro or None,
                cidade or None, estado or None, pais, moeda_funcional,
                regime_tributario or None, cnae_principal or None, natureza_juridica or None, modelo_nfe, ambiente_nfe,
                ambiente_nfce, csc_nfce_homologacao or None, id_csc_nfce_homologacao or None, csc_nfce_producao or None, id_csc_nfce_producao or None,
                bank_account_id,
                banco or None, agencia or None, conta or None, tipo_conta or None,
                capital_social_decimal, data_abertura or None, responsavel_legal or None,
                cpf_responsavel or None, observacoes or None,
                ativo,
            )
        else:
            params = (
                razao_social, nome_fantasia, cnpj, inscricao_estadual or None, inscricao_municipal or None,
                telefone or None, celular or None, email or None, website or None, logo_path, usar_no_pdv,
                cep or None, logradouro or None, numero or None, complemento or None, bairro or None,
                cidade or None, estado or None, pais, moeda_funcional,
                regime_tributario or None, cnae_principal or None, natureza_juridica or None, modelo_nfe, ambiente_nfe,
                ambiente_nfce, csc_nfce_homologacao or None, id_csc_nfce_homologacao or None, csc_nfce_producao or None, id_csc_nfce_producao or None,
                bank_account_id,
                banco or None, agencia or None, conta or None, tipo_conta or None,
                capital_social_decimal, data_abertura or None, responsavel_legal or None,
                cpf_responsavel or None, observacoes or None,
                ativo,
            )
        
        db.execute(query, params)
        flash(f'Empresa {nome_fantasia} cadastrada com sucesso!', 'success')
        return redirect(url_for('empresa.empresas'))
    
    db = get_db()
    moedas = _get_moedas_funcionais(db)
    countries = _get_countries(db)
    return render_template('empresa_form.html', empresa=None, active_page='empresas', moedas=moedas, countries=countries)

# =============================
# EDITAR EMPRESA
# =============================

@empresa_bp.route('/empresas/<int:id>/editar', methods=['GET', 'POST'])
@empresa_editar_required
def empresa_editar(id):
    """Edita uma empresa existente."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        razao_social = request.form.get('razao_social', '').strip()
        nome_fantasia = request.form.get('nome_fantasia', '').strip()
        cnpj = request.form.get('cnpj', '').strip()
        inscricao_estadual = request.form.get('inscricao_estadual', '').strip()
        inscricao_municipal = request.form.get('inscricao_municipal', '').strip()
        
        telefone = request.form.get('telefone', '').strip()
        celular = request.form.get('celular', '').strip()
        email = request.form.get('email', '').strip()
        website = request.form.get('website', '').strip()
        
        cep = request.form.get('cep', '').strip()
        logradouro = request.form.get('logradouro', '').strip()
        numero = request.form.get('numero', '').strip()
        complemento = request.form.get('complemento', '').strip()
        bairro = request.form.get('bairro', '').strip()
        cidade = request.form.get('cidade', '').strip()
        estado = request.form.get('estado', '').strip()
        pais = request.form.get('pais', 'Brasil').strip()
        
        regime_tributario = request.form.get('regime_tributario', '')
        cnae_principal = request.form.get('cnae_principal', '').strip()
        natureza_juridica = request.form.get('natureza_juridica', '').strip()
        modelo_nfe = request.form.get('modelo_nfe', 'antigo')  # Padrão: antigo
        ambiente_nfe = request.form.get('ambiente_nfe', '2')  # Padrão: 2 (homologação)
        
        # Campos NFC-e (CSC separado por ambiente)
        ambiente_nfce = request.form.get('ambiente_nfce', '2')  # Padrão: 2 (homologação)
        csc_nfce_homologacao = request.form.get('csc_nfce_homologacao', '').strip()
        id_csc_nfce_homologacao = request.form.get('id_csc_nfce_homologacao', '').strip()
        csc_nfce_producao = request.form.get('csc_nfce_producao', '').strip()
        id_csc_nfce_producao = request.form.get('id_csc_nfce_producao', '').strip()
        
        banco = request.form.get('banco', '').strip()
        agencia = request.form.get('agencia', '').strip()
        conta = request.form.get('conta', '').strip()
        tipo_conta = request.form.get('tipo_conta', '')
        
        capital_social = request.form.get('capital_social', '').strip()
        data_abertura = request.form.get('data_abertura', '').strip()
        responsavel_legal = request.form.get('responsavel_legal', '').strip()
        cpf_responsavel = request.form.get('cpf_responsavel', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        
        # Validações básicas
        if not razao_social:
            flash('Razão Social é obrigatória.', 'danger')
            empresa = db.fetch_one("SELECT * FROM empresas WHERE id = %s", (id,))
            moedas = _get_moedas_funcionais(db)
            countries = _get_countries(db)
            return render_template('empresa_form.html', empresa=empresa, active_page='empresas', moedas=moedas, countries=countries)
        
        if not nome_fantasia:
            flash('Nome Fantasia é obrigatório.', 'danger')
            empresa = db.fetch_one("SELECT * FROM empresas WHERE id = %s", (id,))
            moedas = _get_moedas_funcionais(db)
            countries = _get_countries(db)
            return render_template('empresa_form.html', empresa=empresa, active_page='empresas', moedas=moedas, countries=countries)
        
        if not cnpj:
            flash('CNPJ é obrigatório.', 'danger')
            empresa = db.fetch_one("SELECT * FROM empresas WHERE id = %s", (id,))
            moedas = _get_moedas_funcionais(db)
            countries = _get_countries(db)
            return render_template('empresa_form.html', empresa=empresa, active_page='empresas', moedas=moedas, countries=countries)
        
        # Verificar se CNPJ já existe em outra empresa
        empresa_existente = db.fetch_one(
            "SELECT * FROM empresas WHERE cnpj = %s AND id != %s AND ativo = TRUE", 
            (cnpj, id)
        )
        
        if empresa_existente:
            flash(f'CNPJ {cnpj} já está cadastrado para outra empresa.', 'danger')
            empresa = db.fetch_one("SELECT * FROM empresas WHERE id = %s", (id,))
            moedas = _get_moedas_funcionais(db)
            countries = _get_countries(db)
            return render_template('empresa_form.html', empresa=empresa, active_page='empresas', moedas=moedas, countries=countries)
        
        # Buscar empresa atual para verificar logo existente
        empresa_atual = db.fetch_one("SELECT logo_path FROM empresas WHERE id = %s", (id,))
        logo_path = empresa_atual['logo_path'] if empresa_atual else None
        
        # Processar remoção de logo
        if request.form.get('remover_logo'):
            if logo_path:
                try:
                    filepath = os.path.join('app', 'static', logo_path)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as e:
                    print(f"Erro ao remover arquivo: {e}")
            logo_path = None
        
        # Processar upload de nova logo
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Remover logo antiga se existir
                if logo_path:
                    try:
                        filepath = os.path.join('app', 'static', logo_path)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    except Exception as e:
                        print(f"Erro ao remover arquivo antigo: {e}")
                
                # Salvar nova logo
                from datetime import datetime
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(filename)
                filename = f"empresa_{timestamp}{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                logo_path = f"uploads/logos/{filename}"
        
        # Processar checkbox "Usar no PDV" (multiloja)
        usar_no_pdv = 1 if request.form.get('usar_no_pdv') else 0

        # Perfil da empresa (modo)
        app_mode = (request.form.get('app_mode', 'global') or 'global').strip().lower()
        if app_mode not in ('global', 'industrial', 'varejo'):
            app_mode = 'global'
        
        # REMOVIDO: Restrição de apenas uma empresa no PDV
        # Agora permite múltiplas empresas com usar_no_pdv = 1
        
        # Converter capital_social para decimal
        try:
            capital_social_decimal = float(capital_social.replace(',', '.')) if capital_social else None
        except ValueError:
            capital_social_decimal = None
        
        has_app_mode = _empresa_has_app_mode(db)

        moeda_funcional = (request.form.get('moeda_funcional', 'BRL') or 'BRL').strip().upper()[:3]

        if has_app_mode:
            query = """
                UPDATE empresas SET
                    razao_social = %s, nome_fantasia = %s, cnpj = %s, 
                    inscricao_estadual = %s, inscricao_municipal = %s,
                    telefone = %s, celular = %s, email = %s, website = %s, logo_path = %s, usar_no_pdv = %s, app_mode = %s,
                    cep = %s, logradouro = %s, numero = %s, complemento = %s, 
                    bairro = %s, cidade = %s, estado = %s, pais = %s, moeda_funcional = %s,
                    regime_tributario = %s, cnae_principal = %s, natureza_juridica = %s, modelo_nfe = %s, ambiente_nfe = %s,
                    ambiente_nfce = %s, csc_nfce_homologacao = %s, id_csc_nfce_homologacao = %s,
                    csc_nfce_producao = %s, id_csc_nfce_producao = %s,
                    banco = %s, agencia = %s, conta = %s, tipo_conta = %s,
                    capital_social = %s, data_abertura = %s, 
                    responsavel_legal = %s, cpf_responsavel = %s, observacoes = %s
                WHERE id = %s
            """

            params = (
                razao_social, nome_fantasia, cnpj, inscricao_estadual or None, inscricao_municipal or None,
                telefone or None, celular or None, email or None, website or None, logo_path, usar_no_pdv, app_mode,
                cep or None, logradouro or None, numero or None, complemento or None, bairro or None,
                cidade or None, estado or None, pais, moeda_funcional,
                regime_tributario or None, cnae_principal or None, natureza_juridica or None, modelo_nfe, ambiente_nfe,
                ambiente_nfce, csc_nfce_homologacao or None, id_csc_nfce_homologacao or None,
                csc_nfce_producao or None, id_csc_nfce_producao or None,
                banco or None, agencia or None, conta or None, tipo_conta or None,
                capital_social_decimal, data_abertura or None,
                responsavel_legal or None, cpf_responsavel or None, observacoes or None,
                id,
            )
        else:
            query = """
                UPDATE empresas SET
                    razao_social = %s, nome_fantasia = %s, cnpj = %s, 
                    inscricao_estadual = %s, inscricao_municipal = %s,
                    telefone = %s, celular = %s, email = %s, website = %s, logo_path = %s, usar_no_pdv = %s,
                    cep = %s, logradouro = %s, numero = %s, complemento = %s, 
                    bairro = %s, cidade = %s, estado = %s, pais = %s, moeda_funcional = %s,
                    regime_tributario = %s, cnae_principal = %s, natureza_juridica = %s, modelo_nfe = %s, ambiente_nfe = %s,
                    ambiente_nfce = %s, csc_nfce_homologacao = %s, id_csc_nfce_homologacao = %s,
                    csc_nfce_producao = %s, id_csc_nfce_producao = %s,
                    banco = %s, agencia = %s, conta = %s, tipo_conta = %s,
                    capital_social = %s, data_abertura = %s, 
                    responsavel_legal = %s, cpf_responsavel = %s, observacoes = %s
                WHERE id = %s
            """

            params = (
                razao_social, nome_fantasia, cnpj, inscricao_estadual or None, inscricao_municipal or None,
                telefone or None, celular or None, email or None, website or None, logo_path, usar_no_pdv,
                cep or None, logradouro or None, numero or None, complemento or None, bairro or None,
                cidade or None, estado or None, pais, moeda_funcional,
                regime_tributario or None, cnae_principal or None, natureza_juridica or None, modelo_nfe, ambiente_nfe,
                ambiente_nfce, csc_nfce_homologacao or None, id_csc_nfce_homologacao or None,
                csc_nfce_producao or None, id_csc_nfce_producao or None,
                banco or None, agencia or None, conta or None, tipo_conta or None,
                capital_social_decimal, data_abertura or None,
                responsavel_legal or None, cpf_responsavel or None, observacoes or None,
                id,
            )

        db.execute(query, params)
        flash(f'Empresa {nome_fantasia} atualizada com sucesso!', 'success')
        return redirect(url_for('empresa.empresa_visualizar', id=id))

    # GET - mostrar formulário preenchido
    empresa = db.fetch_one("SELECT * FROM empresas WHERE id = %s AND ativo = TRUE", (id,))
    moedas = _get_moedas_funcionais(db)
    countries = _get_countries(db)

    if not empresa:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('empresa.empresas'))

    # Garantir campo app_mode no template mesmo quando coluna não existir no banco
    if not _empresa_has_app_mode(db):
        try:
            empresa['app_mode'] = 'global'
        except Exception:
            pass

    return render_template('empresa_form.html', empresa=empresa, active_page='empresas', moedas=moedas, countries=countries)

# =============================
# EXCLUIR EMPRESA (Soft Delete)
# =============================

@empresa_bp.route('/empresas/<int:id>/excluir', methods=['POST'])
@empresa_excluir_required
def empresa_excluir(id):
    """Exclui (desativa) uma empresa."""
    db = get_db()
    
    empresa = db.fetch_one("SELECT * FROM empresas WHERE id = %s", (id,))
    
    if not empresa:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('empresa.empresas'))
    
    # Soft delete - apenas marca como inativo
    db.execute("UPDATE empresas SET ativo = FALSE WHERE id = %s", (id,))
    flash(f'Empresa {empresa["nome_fantasia"]} excluída com sucesso!', 'success')
    
    return redirect(url_for('empresa.empresas'))
