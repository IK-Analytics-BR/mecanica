from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required
from utils.permissoes_helper import tem_permissao

# Criar um Blueprint para as rotas de fornecedor
fornecedor_bp = Blueprint('fornecedor', __name__)


# Decorators para permissões granulares
def fornecedor_visualizar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('compras.fornecedores', 'visualizar'):
            flash('Você não tem permissão para visualizar fornecedores.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function

def fornecedor_criar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('compras.fornecedores', 'criar'):
            flash('Você não tem permissão para cadastrar fornecedores.', 'danger')
            return redirect(url_for('fornecedor.fornecedores'))
        return f(*args, **kwargs)
    return decorated_function

def fornecedor_editar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('compras.fornecedores', 'editar'):
            flash('Você não tem permissão para editar fornecedores.', 'danger')
            return redirect(url_for('fornecedor.fornecedores'))
        return f(*args, **kwargs)
    return decorated_function

def fornecedor_excluir_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('compras.fornecedores', 'excluir'):
            flash('Você não tem permissão para excluir fornecedores.', 'danger')
            return redirect(url_for('fornecedor.fornecedores'))
        return f(*args, **kwargs)
    return decorated_function

# Rota para listar todos os fornecedores
@fornecedor_bp.route('/fornecedores')
@fornecedor_visualizar_required
def fornecedores():
    # Verificar se há parâmetros de busca
    search_term = request.args.get('search_term', '')
    search_field = request.args.get('search_field', 'all')
    
    # Buscar fornecedores ativos no banco de dados
    db = get_db()
    
    if search_term:
        # Construir a consulta SQL com base no campo de busca
        if search_field == 'name':
            query = "SELECT * FROM suppliers WHERE active = TRUE AND name LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'cnpj':
            query = "SELECT * FROM suppliers WHERE active = TRUE AND cnpj LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'city':
            query = "SELECT * FROM suppliers WHERE active = TRUE AND city LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'state':
            query = "SELECT * FROM suppliers WHERE active = TRUE AND state LIKE %s"
            params = (f'%{search_term}%',)
        else:  # 'all'
            query = """SELECT * FROM suppliers WHERE active = TRUE AND 
                     (name LIKE %s OR cnpj LIKE %s OR 
                      city LIKE %s OR state LIKE %s)"""
            params = (f'%{search_term}%', f'%{search_term}%', 
                      f'%{search_term}%', f'%{search_term}%')
        
        fornecedores = db.fetch_all(query, params)
    else:
        # Buscar todos os fornecedores ativos
        fornecedores = db.fetch_all("SELECT * FROM suppliers WHERE active = TRUE")
    
    return render_template('fornecedor_list.html', fornecedores=fornecedores, search_term=search_term, search_field=search_field)

# Rota para cadastrar um novo fornecedor
@fornecedor_bp.route('/fornecedores/cadastrar', methods=['GET', 'POST'])
@fornecedor_criar_required
def fornecedor_cadastrar():
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        cnpj = request.form.get('cnpj', '')
        ie = request.form.get('ie', '')
        
        # Verificar se já existe fornecedor com o mesmo CNPJ/CPF
        if cnpj and cnpj.strip():
            # Limpar o CNPJ/CPF (remover caracteres especiais)
            cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
            
            # Verificar se já existe um fornecedor com este CNPJ/CPF
            db = get_db()
            query = "SELECT * FROM suppliers WHERE REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '-', ''), '/', '') = %s AND active = TRUE"
            fornecedor_existente = db.fetch_one(query, (cnpj_limpo,))
            
            if fornecedor_existente:
                # Preparar dados para o modal de confirmação
                form_data = {key: request.form.get(key, '') for key in request.form}
                return render_template('fornecedor_form.html', 
                                      fornecedor=None,
                                      show_duplicate_modal=True,
                                      entidade=fornecedor_existente,
                                      tipo_documento='CNPJ/CPF',
                                      editar_url='fornecedor.fornecedor_editar',
                                      visualizar_url='fornecedor.fornecedor_visualizar',
                                      forcar_url='fornecedor.fornecedor_cadastrar_forcar',
                                      form_data=form_data)
        
        # Se não houver duplicidade, continuar com o cadastro
        # Dados de endereço
        cep = request.form.get('cep', '')
        address = request.form.get('address', '')
        number = request.form.get('number', '')
        complement = request.form.get('complement', '')
        neighborhood = request.form.get('neighborhood', '')
        reference = request.form.get('reference', '')
        city = request.form.get('city', '')
        state = request.form.get('state', '')
        
        # Dados de contato
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        contact_name = request.form.get('contact_name', '')
        contact_role = request.form.get('contact_role', '')
        
        # Dados bancários
        bank = request.form.get('bank', '')
        agency = request.form.get('agency', '')
        account = request.form.get('account', '')
        pix_key = request.form.get('pix_key', '')
        
        # Inserir fornecedor no banco de dados
        db = get_db()
        query = """
            INSERT INTO suppliers (name, cnpj, ie, cep, address, number, complement, 
                                 neighborhood, reference, city, state, phone, email, 
                                 contact_name, contact_role, bank, agency, account, pix_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (name, cnpj, ie, cep, address, number, complement, 
                 neighborhood, reference, city, state, phone, email, 
                 contact_name, contact_role, bank, agency, account, pix_key)
        
        fornecedor_id = db.insert(query, params)
        
        if fornecedor_id:
            flash('Fornecedor cadastrado com sucesso!', 'success')
            return redirect(url_for('fornecedor.fornecedores'))
        else:
            flash('Erro ao cadastrar fornecedor.', 'danger')
    
    # Renderizar o formulário de cadastro de fornecedor
    return render_template('fornecedor_form.html', fornecedor=None)

# Rota para forçar o cadastro de um fornecedor mesmo com duplicidade
@fornecedor_bp.route('/fornecedores/cadastrar/forcar', methods=['POST'])
@login_required
def fornecedor_cadastrar_forcar():
    # Verificar se o formulário foi enviado com a flag de forçar criação
    if request.form.get('force_create') == 'true':
        # Obter dados do formulário
        name = request.form.get('name', '')
        cnpj = request.form.get('cnpj', '')
        ie = request.form.get('ie', '')
        
        # Dados de endereço
        cep = request.form.get('cep', '')
        address = request.form.get('address', '')
        number = request.form.get('number', '')
        complement = request.form.get('complement', '')
        neighborhood = request.form.get('neighborhood', '')
        reference = request.form.get('reference', '')
        city = request.form.get('city', '')
        state = request.form.get('state', '')
        
        # Dados de contato
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        contact_name = request.form.get('contact_name', '')
        contact_role = request.form.get('contact_role', '')
        
        # Dados bancários
        bank = request.form.get('bank', '')
        agency = request.form.get('agency', '')
        account = request.form.get('account', '')
        pix_key = request.form.get('pix_key', '')
        
        # Inserir fornecedor no banco de dados, mesmo com duplicidade
        db = get_db()
        query = """
            INSERT INTO suppliers (name, cnpj, ie, cep, address, number, complement, 
                                 neighborhood, reference, city, state, phone, email, 
                                 contact_name, contact_role, bank, agency, account, pix_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (name, cnpj, ie, cep, address, number, complement, 
                 neighborhood, reference, city, state, phone, email, 
                 contact_name, contact_role, bank, agency, account, pix_key)
        
        fornecedor_id = db.insert(query, params)
        
        if fornecedor_id:
            flash('Fornecedor cadastrado com sucesso! (Criação forçada)', 'warning')
            return redirect(url_for('fornecedor.fornecedores'))
        else:
            flash('Erro ao cadastrar fornecedor.', 'danger')
            return redirect(url_for('fornecedor.fornecedor_cadastrar'))
    
    # Se não houver flag de forçar criação, redirecionar para o formulário normal
    flash('Operação inválida.', 'danger')
    return redirect(url_for('fornecedor.fornecedor_cadastrar'))

# Rota para editar um fornecedor existente
@fornecedor_bp.route('/fornecedores/editar/<id>', methods=['GET', 'POST'])
@fornecedor_editar_required
def fornecedor_editar(id):
    # Buscar o fornecedor pelo ID
    db = get_db()
    fornecedor = db.fetch_one("SELECT * FROM suppliers WHERE id = %s", (id,))
    
    if not fornecedor:
        flash('Fornecedor não encontrado.', 'danger')
        return redirect(url_for('fornecedor.fornecedores'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        cnpj = request.form.get('cnpj', '')
        ie = request.form.get('ie', '')
        
        # Dados de endereço
        cep = request.form.get('cep', '')
        address = request.form.get('address', '')
        number = request.form.get('number', '')
        complement = request.form.get('complement', '')
        neighborhood = request.form.get('neighborhood', '')
        reference = request.form.get('reference', '')
        city = request.form.get('city', '')
        state = request.form.get('state', '')
        
        # Dados de contato
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        contact_name = request.form.get('contact_name', '')
        contact_role = request.form.get('contact_role', '')
        
        # Dados bancários
        bank = request.form.get('bank', '')
        agency = request.form.get('agency', '')
        account = request.form.get('account', '')
        pix_key = request.form.get('pix_key', '')
        
        # Atualizar fornecedor no banco de dados
        query = """
            UPDATE suppliers
            SET name = %s, cnpj = %s, ie = %s, cep = %s, address = %s, 
                number = %s, complement = %s, neighborhood = %s, reference = %s, city = %s, state = %s, 
                phone = %s, email = %s, contact_name = %s, contact_role = %s, 
                bank = %s, agency = %s, account = %s, pix_key = %s
            WHERE id = %s
        """
        params = (name, cnpj, ie, cep, address, number, complement, 
                 neighborhood, reference, city, state, phone, email, 
                 contact_name, contact_role, bank, agency, account, pix_key, id)
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Fornecedor atualizado com sucesso!', 'success')
            return redirect(url_for('fornecedor.fornecedores'))
        else:
            flash('Erro ao atualizar fornecedor.', 'danger')
    
    # Renderizar o formulário de edição de fornecedor
    return render_template('fornecedor_form.html', fornecedor=fornecedor)

# Rota para visualizar um fornecedor
@fornecedor_bp.route('/fornecedores/visualizar/<id>')
@login_required
def fornecedor_visualizar(id):
    # Buscar o fornecedor pelo ID
    db = get_db()
    fornecedor = db.fetch_one("SELECT * FROM suppliers WHERE id = %s", (id,))
    
    if not fornecedor:
        flash('Fornecedor não encontrado.', 'danger')
        return redirect(url_for('fornecedor.fornecedores'))
    
    # Buscar produtos deste fornecedor (relacionamento direto pelo campo main_supplier_id)
    produtos = db.fetch_all("""
        SELECT p.*
        FROM products p
        WHERE p.main_supplier_id = %s AND p.active = TRUE
    """, (id,))
    
    # Renderizar a visualização do fornecedor
    return render_template('fornecedor_view.html', fornecedor=fornecedor, produtos=produtos)

# Rota para excluir um fornecedor
@fornecedor_bp.route('/fornecedores/excluir/<id>')
@fornecedor_excluir_required
def fornecedor_excluir(id):
    # Buscar o fornecedor pelo ID
    db = get_db()
    fornecedor = db.fetch_one("SELECT * FROM suppliers WHERE id = %s", (id,))
    
    if fornecedor:
        # Verificar se o fornecedor possui produtos associados (via products.main_supplier_id)
        produtos = db.fetch_all("""
            SELECT COUNT(*) as count
            FROM products
            WHERE main_supplier_id = %s AND active = TRUE
        """, (id,))
        
        if produtos and produtos[0]['count'] > 0:
            flash('Não é possível excluir o fornecedor pois existem produtos associados a ele.', 'danger')
            return redirect(url_for('fornecedor.fornecedores'))
        
        # Marcar o fornecedor como inativo (exclusão lógica)
        affected_rows = db.update("""
            UPDATE suppliers SET active = FALSE WHERE id = %s
        """, (id,))
        
        if affected_rows > 0:
            flash('Fornecedor excluído com sucesso!', 'success')
        else:
            flash('Erro ao excluir fornecedor.', 'danger')
    else:
        flash('Fornecedor não encontrado.', 'danger')
    
    # Redirecionar para a lista de fornecedores
    return redirect(url_for('fornecedor.fornecedores'))
