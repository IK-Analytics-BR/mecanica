from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required
from utils.permissoes_helper import tem_permissao
from utils.tenant import get_company_id, inject_company_id

# Criar um Blueprint para as rotas de cliente
cliente_bp = Blueprint('cliente', __name__)


# Decorators para permissões granulares
def cliente_visualizar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('clientes.lista', 'visualizar'):
            flash('Você não tem permissão para visualizar clientes.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function

def cliente_criar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('clientes.lista', 'criar'):
            flash('Você não tem permissão para cadastrar clientes.', 'danger')
            return redirect(url_for('cliente.clientes'))
        return f(*args, **kwargs)
    return decorated_function

def cliente_editar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('clientes.lista', 'editar'):
            flash('Você não tem permissão para editar clientes.', 'danger')
            return redirect(url_for('cliente.clientes'))
        return f(*args, **kwargs)
    return decorated_function

def cliente_excluir_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('clientes.lista', 'excluir'):
            flash('Você não tem permissão para excluir clientes.', 'danger')
            return redirect(url_for('cliente.clientes'))
        return f(*args, **kwargs)
    return decorated_function

# =============================
# Produtos do Cliente (página dedicada e entrada do menu)
# =============================

@cliente_bp.route('/clientes/produtos', methods=['GET'])
@login_required
def customers_products_entry():
    """Entrada de menu Produtos do Cliente: direciona para lista de clientes para seleção."""
    return redirect(url_for('cliente.clientes'))

@cliente_bp.route('/clientes/<int:customer_id>/produtos-vinculos', methods=['GET'])
@login_required
def customer_products_page(customer_id):
    """Página dedicada para vincular Produtos Pai ao cliente e consultar insumos."""
    db = get_db()
    cliente = db.fetch_one("SELECT id, name FROM customers WHERE id = %s AND active = TRUE", (customer_id,))
    if not cliente:
        flash('Cliente não encontrado.', 'danger')
        return redirect(url_for('cliente.clientes'))

    parent_candidates = db.fetch_all(
        "SELECT id, name FROM products WHERE active = TRUE AND product_type = 'parent' ORDER BY name"
    )

    return render_template('cliente_produtos.html', cliente=cliente, parent_candidates=parent_candidates)

# Rota para listar todos os clientes
@cliente_bp.route('/clientes')
@cliente_visualizar_required
def clientes():
    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    # Verificar se há parâmetros de busca
    search_term = request.args.get('search_term', '')
    search_field = request.args.get('search_field', 'all')
    
    # Buscar clientes ativos no banco de dados
    db = get_db()
    
    # Construir query base e count query
    company_id = get_company_id()
    if search_term:
        # Construir a consulta SQL com base no campo de busca
        if search_field == 'name':
            query = "SELECT * FROM customers WHERE active = TRUE AND company_id = %s AND name LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND company_id = %s AND name LIKE %s"
            params = (company_id, f'%{search_term}%',)
        elif search_field == 'cnpj':
            query = "SELECT * FROM customers WHERE active = TRUE AND company_id = %s AND cnpj LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND company_id = %s AND cnpj LIKE %s"
            params = (company_id, f'%{search_term}%',)
        elif search_field == 'razao_social':
            query = "SELECT * FROM customers WHERE active = TRUE AND razao_social LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND razao_social LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'ie':
            query = "SELECT * FROM customers WHERE active = TRUE AND ie LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND ie LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'cep':
            query = "SELECT * FROM customers WHERE active = TRUE AND cep LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND cep LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'address':
            query = "SELECT * FROM customers WHERE active = TRUE AND address LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND address LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'number':
            query = "SELECT * FROM customers WHERE active = TRUE AND number LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND number LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'complement':
            query = "SELECT * FROM customers WHERE active = TRUE AND complement LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND complement LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'neighborhood':
            query = "SELECT * FROM customers WHERE active = TRUE AND neighborhood LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND neighborhood LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'reference':
            query = "SELECT * FROM customers WHERE active = TRUE AND reference LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND reference LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'city':
            query = "SELECT * FROM customers WHERE active = TRUE AND city LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND city LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'state':
            query = "SELECT * FROM customers WHERE active = TRUE AND state LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND state LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'phone':
            query = "SELECT * FROM customers WHERE active = TRUE AND phone LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND phone LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'email':
            query = "SELECT * FROM customers WHERE active = TRUE AND email LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND email LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'contact_name':
            query = "SELECT * FROM customers WHERE active = TRUE AND contact_name LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND contact_name LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'contact_role':
            query = "SELECT * FROM customers WHERE active = TRUE AND contact_role LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND contact_role LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'id':
            # Busca por ID (tenta exato, mas aceita LIKE se vier texto)
            if search_term.isdigit():
                query = "SELECT * FROM customers WHERE active = TRUE AND id = %s"
                count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND id = %s"
                params = (int(search_term),)
            else:
                query = "SELECT * FROM customers WHERE active = TRUE AND CAST(id AS CHAR) LIKE %s"
                count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND CAST(id AS CHAR) LIKE %s"
                params = (f'%{search_term}%',)
        elif search_field == 'latitude':
            query = "SELECT * FROM customers WHERE active = TRUE AND CAST(latitude AS CHAR) LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND CAST(latitude AS CHAR) LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'longitude':
            query = "SELECT * FROM customers WHERE active = TRUE AND CAST(longitude AS CHAR) LIKE %s"
            count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND CAST(longitude AS CHAR) LIKE %s"
            params = (f'%{search_term}%',)
        elif search_field == 'cnae':
            # Filtro por CNAE (código ou descrição) requer join nas tabelas de vínculo
            query = (
                """
                SELECT DISTINCT c.*
                FROM customers c
                JOIN customer_cnae cc ON cc.customer_id = c.id
                JOIN cnae20 n ON n.subclasse_codigo = cc.subclasse_codigo
                WHERE c.active = TRUE
                  AND (cc.subclasse_codigo LIKE %s OR n.subclasse_descricao LIKE %s)
                """
            )
            count_query = (
                """
                SELECT COUNT(DISTINCT c.id) as total
                FROM customers c
                JOIN customer_cnae cc ON cc.customer_id = c.id
                JOIN cnae20 n ON n.subclasse_codigo = cc.subclasse_codigo
                WHERE c.active = TRUE
                  AND (cc.subclasse_codigo LIKE %s OR n.subclasse_descricao LIKE %s)
                """
            )
            like = f'%{search_term}%'
            params = (like, like)
        else:  # 'all'
            query = (
                """
                SELECT * FROM customers WHERE active = TRUE AND (
                    name LIKE %s OR cnpj LIKE %s OR razao_social LIKE %s OR ie LIKE %s OR
                    cep LIKE %s OR address LIKE %s OR number LIKE %s OR complement LIKE %s OR
                    neighborhood LIKE %s OR reference LIKE %s OR city LIKE %s OR state LIKE %s OR
                    phone LIKE %s OR email LIKE %s OR contact_name LIKE %s OR contact_role LIKE %s
                )
                """
            )
            count_query = (
                """
                SELECT COUNT(*) as total FROM customers WHERE active = TRUE AND (
                    name LIKE %s OR cnpj LIKE %s OR razao_social LIKE %s OR ie LIKE %s OR
                    cep LIKE %s OR address LIKE %s OR number LIKE %s OR complement LIKE %s OR
                    neighborhood LIKE %s OR reference LIKE %s OR city LIKE %s OR state LIKE %s OR
                    phone LIKE %s OR email LIKE %s OR contact_name LIKE %s OR contact_role LIKE %s
                )
                """
            )
            like = f'%{search_term}%'
            params = (like, like, like, like, like, like, like, like, like, like, like, like, like, like, like, like)
    else:
        # Buscar todos os clientes ativos
        query = "SELECT * FROM customers WHERE active = TRUE"
        count_query = "SELECT COUNT(*) as total FROM customers WHERE active = TRUE"
        params = ()
    
    # Contar total de registros
    total_result = db.fetch_one(count_query, params)
    total = total_result['total'] if total_result else 0
    total_pages = (total + per_page - 1) // per_page  # Calcula páginas totais
    
    # Adicionar LIMIT e OFFSET para paginação
    query += " ORDER BY name LIMIT %s OFFSET %s"
    params = params + (per_page, offset)
    
    clientes = db.fetch_all(query, params)

    return render_template('cliente_list.html',
                         clientes=clientes,
                         search_term=search_term,
                         search_field=search_field,
                         page=page,
                         per_page=per_page,
                         total=total,
                         total_pages=total_pages)

@cliente_bp.route('/api/clientes/<int:id>/json', methods=['GET'])
@login_required
def api_cliente_detail(id):
    """Retorna informações resumidas do cliente em JSON para a tela de vendas."""
    db = get_db()
    c = db.fetch_one(
        """
        SELECT id, name, cnpj, ie, email, phone,
               address, number, complement, neighborhood, city, state, cep
        FROM customers WHERE id = %s AND active = TRUE
        """,
        (id,)
    )
    if not c:
        return jsonify({'error': 'Cliente não encontrado'}), 404
    return jsonify(c)

# Rota para cadastrar um novo cliente
@cliente_bp.route('/clientes/cadastrar', methods=['GET', 'POST'])
@cliente_criar_required
def cliente_cadastrar():
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        razao_social = request.form.get('razao_social', '')
        cnpj = request.form.get('cnpj', '')
        ie = request.form.get('ie', '')
        
        # Verificar se já existe cliente com o mesmo CNPJ/CPF
        if cnpj and cnpj.strip():
            # Limpar o CNPJ/CPF (remover caracteres especiais)
            cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
            
            # Verificar se já existe um cliente com este CNPJ/CPF
            db = get_db()
            query = "SELECT * FROM customers WHERE REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '-', ''), '/', '') = %s AND active = TRUE"
            cliente_existente = db.fetch_one(query, (cnpj_limpo,))
            
            if cliente_existente:
                # Preparar dados para o modal de confirmação
                form_data = {key: request.form.get(key, '') for key in request.form}
                return render_template('cliente_form.html', 
                                      cliente=None,
                                      show_duplicate_modal=True,
                                      entidade=cliente_existente,
                                      tipo_documento='CNPJ/CPF',
                                      editar_url='cliente.cliente_editar',
                                      visualizar_url='cliente.cliente_visualizar',
                                      forcar_url='cliente.cliente_cadastrar_forcar',
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
        permitir_whatsapp = 1 if request.form.get('permitir_whatsapp') else 0
        
        # Dados de georreferenciamento
        latitude = request.form.get('latitude', '')
        longitude = request.form.get('longitude', '')
        
        # Converter para float ou None se estiverem vazios
        try:
            if latitude and latitude != 'Buscando...':
                latitude = float(latitude)
            else:
                latitude = None
        except ValueError:
            print(f"Erro ao converter latitude: {latitude}")
            latitude = None
            
        try:
            if longitude and longitude != 'Buscando...':
                longitude = float(longitude)
            else:
                longitude = None
        except ValueError:
            print(f"Erro ao converter longitude: {longitude}")
            longitude = None
        
        # Inserir cliente no banco de dados
        db = get_db()
        query = """
            INSERT INTO customers (name, razao_social, cnpj, ie, cep, address, number, complement, 
                                 neighborhood, reference, city, state, phone, email, 
                                 contact_name, contact_role, latitude, longitude, permitir_whatsapp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (name, razao_social, cnpj, ie, cep, address, number, complement, 
                 neighborhood, reference, city, state, phone, email, 
                 contact_name, contact_role, latitude, longitude, permitir_whatsapp)
        
        cliente_id = db.insert(query, params)
        
        if cliente_id:
            flash('Cliente cadastrado com sucesso! Você pode agora vincular CNAEs.', 'success')
            return redirect(url_for('cliente.cliente_editar', id=cliente_id))
        else:
            flash('Erro ao cadastrar cliente.', 'danger')
    
    # Renderizar o formulário de cadastro de cliente
    return render_template('cliente_form.html', cliente=None)

# Rota para forçar o cadastro de um cliente mesmo com duplicidade
@cliente_bp.route('/clientes/cadastrar/forcar', methods=['POST'])
@cliente_criar_required
def cliente_cadastrar_forcar():
    # Verificar se o formulário foi enviado com a flag de forçar criação
    if request.form.get('force_create') == 'true':
        # Obter dados do formulário
        name = request.form['name']
        razao_social = request.form.get('razao_social', '')
        cnpj = request.form['cnpj']
        ie = request.form.get('ie', '')
        print(f"DEBUG - IE recebido do formulário: {ie}")
        
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
        permitir_whatsapp = 1 if request.form.get('permitir_whatsapp') else 0
        
        # Dados de georreferenciamento
        latitude = request.form.get('latitude', '')
        longitude = request.form.get('longitude', '')
        
        # Converter para float ou None se estiverem vazios
        try:
            if latitude and latitude != 'Buscando...':
                latitude = float(latitude)
            else:
                latitude = None
        except ValueError:
            print(f"Erro ao converter latitude: {latitude}")
            latitude = None
            
        try:
            if longitude and longitude != 'Buscando...':
                longitude = float(longitude)
            else:
                longitude = None
        except ValueError:
            print(f"Erro ao converter longitude: {longitude}")
            longitude = None
        
        # Inserir cliente no banco de dados, mesmo com duplicidade
        db = get_db()
        query = """
            INSERT INTO customers (name, razao_social, cnpj, ie, cep, address, number, complement, 
                                 neighborhood, reference, city, state, phone, email, 
                                 contact_name, contact_role, latitude, longitude, permitir_whatsapp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (name, razao_social, cnpj, ie, cep, address, number, complement, 
                 neighborhood, reference, city, state, phone, email, 
                 contact_name, contact_role, latitude, longitude, permitir_whatsapp)
        
        cliente_id = db.insert(query, params)
        
        if cliente_id:
            flash('Cliente cadastrado com sucesso! (Criação forçada)', 'warning')
            return redirect(url_for('cliente.clientes'))
        else:
            flash('Erro ao cadastrar cliente.', 'danger')
            return redirect(url_for('cliente.cliente_cadastrar'))
    
    # Se não houver flag de forçar criação, redirecionar para o formulário normal
    flash('Operação inválida.', 'danger')
    return redirect(url_for('cliente.cliente_cadastrar'))

# Rota para editar um cliente existente
@cliente_bp.route('/clientes/editar/<id>', methods=['GET', 'POST'])
@cliente_editar_required
def cliente_editar(id):
    # Buscar o cliente pelo ID
    db = get_db()
    cliente = db.fetch_one("SELECT * FROM customers WHERE id = %s", (id,))
    
    if not cliente:
        flash('Cliente não encontrado.', 'danger')
        return redirect(url_for('cliente.clientes'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name', '')
        razao_social = request.form.get('razao_social', '')
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
        permitir_whatsapp = 1 if request.form.get('permitir_whatsapp') else 0
        
        # Dados de georreferenciamento
        latitude = request.form.get('latitude', '')
        longitude = request.form.get('longitude', '')
        
        # Converter para float ou None se estiverem vazios
        try:
            if latitude and latitude != 'Buscando...':
                latitude = float(latitude)
            else:
                latitude = None
        except ValueError:
            print(f"Erro ao converter latitude: {latitude}")
            latitude = None
            
        try:
            if longitude and longitude != 'Buscando...':
                longitude = float(longitude)
            else:
                longitude = None
        except ValueError:
            print(f"Erro ao converter longitude: {longitude}")
            longitude = None
        
        # Atualizar cliente no banco de dados
        query = """
            UPDATE customers
            SET name = %s, razao_social = %s, cnpj = %s, ie = %s, cep = %s, address = %s, 
                number = %s, complement = %s, neighborhood = %s, reference = %s, city = %s, state = %s, 
                phone = %s, email = %s, contact_name = %s, contact_role = %s, latitude = %s, longitude = %s,
                permitir_whatsapp = %s
            WHERE id = %s
        """
        params = (name, razao_social, cnpj, ie, cep, address, number, complement, 
                 neighborhood, reference, city, state, phone, email, 
                 contact_name, contact_role, latitude, longitude, permitir_whatsapp, id)
        
        affected_rows = db.update(query, params)
        
        if affected_rows > 0:
            flash('Cliente atualizado com sucesso!', 'success')
            return redirect(url_for('cliente.clientes'))
        else:
            flash('Erro ao atualizar cliente.', 'danger')
    
    # Renderizar o formulário de edição de cliente
    return render_template('cliente_form.html', cliente=cliente)

# ==========================
# CNAE MANAGEMENT ENDPOINTS
# ==========================

@cliente_bp.route('/api/cnae/search')
@login_required
def cnae_search():
    """Autocomplete de CNAE por código ou descrição."""
    q = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 20))
    if not q or len(q) < 2:
        return jsonify([])
    db = get_db()
    like = f"%{q}%"
    rows = db.fetch_all(
        """
        SELECT subclasse_codigo, subclasse_descricao
        FROM cnae20
        WHERE subclasse_codigo LIKE %s OR subclasse_descricao LIKE %s
        ORDER BY subclasse_codigo
        LIMIT %s
        """,
        (like, like, limit)
    )
    return jsonify(rows)

# =============================
# Produtos do Cliente (Produto Pai instalado) e Status de Insumos
# =============================

@cliente_bp.route('/clientes/<int:customer_id>/produtos', methods=['GET'])
@login_required
def customer_products_list(customer_id):
    """Lista produtos pai instalados no cliente."""
    db = get_db()
    rows = db.fetch_all(
        """
        SELECT cp.id, cp.product_id, p.name AS product_name, p.barcode, p.unit_measure,
               cp.serial_number, cp.installed_at, cp.active, cp.notes
        FROM customer_products cp
        JOIN products p ON p.id = cp.product_id
        WHERE cp.customer_id = %s AND cp.active = 1
        ORDER BY cp.installed_at DESC, p.name
        """,
        (customer_id,)
    )
    return jsonify(rows)


@cliente_bp.route('/clientes/<int:customer_id>/produtos', methods=['POST'])
@login_required
def customer_products_add(customer_id):
    """Adiciona vínculo de produto pai instalado ao cliente."""
    data = request.get_json(silent=True) or request.form
    product_id = data.get('product_id')
    serial_number = data.get('serial_number', '')
    installed_at = data.get('installed_at')  # yyyy-mm-dd
    notes = data.get('notes', '')

    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'product_id inválido'}), 400

    db = get_db()
    # Verificar se produto é do tipo pai
    prod = db.fetch_one("SELECT id, product_type FROM products WHERE id = %s AND active = TRUE", (product_id,))
    if not prod:
        return jsonify({'error': 'Produto não encontrado'}), 404
    if prod.get('product_type') != 'parent':
        return jsonify({'error': 'Somente produtos do tipo pai podem ser vinculados ao cliente'}), 400

    cp_id = db.insert(
        """
        INSERT INTO customer_products (customer_id, product_id, serial_number, installed_at, notes)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (customer_id, product_id, serial_number, installed_at, notes)
    )
    return jsonify({'ok': True, 'id': cp_id}), 201


@cliente_bp.route('/clientes/<int:customer_id>/produtos/<int:cp_id>', methods=['DELETE'])
@login_required
def customer_products_delete(customer_id, cp_id):
    """Desativa vínculo de produto pai do cliente (soft delete)."""
    db = get_db()
    affected = db.update(
        "UPDATE customer_products SET active = 0 WHERE id = %s AND customer_id = %s",
        (cp_id, customer_id)
    )
    if affected > 0:
        return jsonify({'ok': True})
    return jsonify({'error': 'Vínculo não encontrado'}), 404


@cliente_bp.route('/clientes/<int:customer_id>/produtos/<int:cp_id>/insumos', methods=['GET'])
@login_required
def customer_product_children_list(customer_id, cp_id):
    """Lista insumos (filhos) para um produto pai instalado no cliente, com status."""
    db = get_db()
    # Garantir que o vínculo pertence ao cliente
    cp = db.fetch_one("SELECT id, product_id FROM customer_products WHERE id = %s AND customer_id = %s AND active = 1",
                      (cp_id, customer_id))
    if not cp:
        return jsonify({'error': 'Vínculo não encontrado'}), 404

    rows = db.fetch_all(
        """
        SELECT pc.child_product_id,
               p.name AS child_name,
               p.unit_measure,
               pc.quantity,
               pc.interval_days AS default_interval_days,
               cpcs.last_replacement_at,
               COALESCE(cpcs.interval_days, pc.interval_days) AS interval_days,
               cpcs.next_due_at,
               cpcs.notes
        FROM product_children pc
        JOIN products p ON p.id = pc.child_product_id
        LEFT JOIN customer_product_children_status cpcs
               ON cpcs.customer_product_id = %s AND cpcs.child_product_id = pc.child_product_id
        WHERE pc.parent_product_id = %s
        ORDER BY p.name
        """,
        (cp_id, cp['product_id'])
    )
    return jsonify(rows)


@cliente_bp.route('/clientes/<int:customer_id>/produtos/<int:cp_id>/insumos/<int:child_id>/status', methods=['POST'])
@login_required
def customer_product_children_update_status(customer_id, cp_id, child_id):
    """Atualiza status (última troca, intervalo, próxima troca) de um insumo para um produto pai instalado."""
    data = request.get_json(silent=True) or request.form
    last_replacement_at = data.get('last_replacement_at')  # yyyy-mm-dd ou vazio
    interval_days = data.get('interval_days')
    notes = data.get('notes', '')

    try:
        interval_days = int(interval_days) if interval_days not in (None, '') else None
    except (ValueError, TypeError):
        return jsonify({'error': 'interval_days inválido'}), 400

    db = get_db()
    # Validar vínculo pertence ao cliente
    cp = db.fetch_one("SELECT id FROM customer_products WHERE id = %s AND customer_id = %s AND active = 1",
                      (cp_id, customer_id))
    if not cp:
        return jsonify({'error': 'Vínculo não encontrado'}), 404

    # Calcular next_due_at via SQL usando COALESCE(interval)
    # Estratégia: upsert e atualizar next_due_at com base no intervalo efetivo
    # Intervalo efetivo: preferir cpcs.interval_days se fornecido, caso contrário usar pc.interval_days

    # Primeiro, garantir existência ou atualizar linha
    db.update(
        """
        INSERT INTO customer_product_children_status (customer_product_id, child_product_id, last_replacement_at, interval_days, next_due_at, notes)
        VALUES (%s, %s, %s, %s, NULL, %s)
        ON DUPLICATE KEY UPDATE
            last_replacement_at = VALUES(last_replacement_at),
            interval_days = VALUES(interval_days),
            notes = VALUES(notes)
        """,
        (cp_id, child_id, last_replacement_at or None, interval_days, notes)
    )

    # Em seguida, atualizar next_due_at considerando o intervalo efetivo (override cpcs ou default pc)
    db.update(
        """
        UPDATE customer_product_children_status cpcs
        JOIN customer_products cp ON cp.id = cpcs.customer_product_id
        JOIN product_children pc ON pc.parent_product_id = cp.product_id AND pc.child_product_id = cpcs.child_product_id
        SET cpcs.next_due_at = CASE
             WHEN cpcs.last_replacement_at IS NOT NULL
              AND COALESCE(cpcs.interval_days, pc.interval_days) IS NOT NULL
             THEN DATE_ADD(cpcs.last_replacement_at, INTERVAL COALESCE(cpcs.interval_days, pc.interval_days) DAY)
             ELSE NULL
        END
        WHERE cpcs.customer_product_id = %s AND cpcs.child_product_id = %s
        """,
        (cp_id, child_id)
    )

    return jsonify({'ok': True})

@cliente_bp.route('/clientes/<id>/cnaes', methods=['GET'])
@login_required
def customer_cnaes_list(id):
    """Lista CNAEs vinculados ao cliente."""
    db = get_db()
    rows = db.fetch_all(
        """
        SELECT cc.subclasse_codigo, n.subclasse_descricao, cc.is_primary
        FROM customer_cnae cc
        JOIN cnae20 n ON n.subclasse_codigo = cc.subclasse_codigo
        WHERE cc.customer_id = %s
        ORDER BY cc.is_primary DESC, cc.subclasse_codigo
        """,
        (id,)
    )
    return jsonify(rows)

@cliente_bp.route('/clientes/<id>/cnaes', methods=['POST'])
@login_required
def customer_cnaes_add(id):
    """Adiciona ou atualiza vínculo de CNAE para o cliente."""
    data = request.get_json(silent=True) or request.form
    sub = (data.get('subclasse_codigo') or '').strip()
    is_primary = 1 if str(data.get('is_primary', '0')).lower() in ('1', 'true', 'on') else 0
    if not sub:
        return jsonify({'error': 'subclasse_codigo é obrigatório'}), 400
    db = get_db()
    try:
        db.execute("START TRANSACTION")
        if is_primary:
            db.update("UPDATE customer_cnae SET is_primary = 0 WHERE customer_id = %s AND is_primary = 1", (id,))
        # Sintaxe sem VALUES() deprecado: alias na linha inserida
        db.update(
            """
            INSERT INTO customer_cnae (customer_id, subclasse_codigo, is_primary)
            VALUES (%s, %s, %s) AS new
            ON DUPLICATE KEY UPDATE is_primary = new.is_primary
            """,
            (id, sub, is_primary)
        )
        db.execute("COMMIT")
    except Exception as e:
        db.execute("ROLLBACK")
        return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True})

@cliente_bp.route('/clientes/<id>/cnaes/<path:subclasse_codigo>', methods=['PUT'])
@login_required
def customer_cnaes_set_primary(id, subclasse_codigo):
    """Define o CNAE como principal para o cliente (garante unicidade)."""
    db = get_db()
    try:
        db.execute("START TRANSACTION")
        db.update("UPDATE customer_cnae SET is_primary = 0 WHERE customer_id = %s AND is_primary = 1", (id,))
        db.update(
            """
            INSERT INTO customer_cnae (customer_id, subclasse_codigo, is_primary)
            VALUES (%s, %s, 1) AS new
            ON DUPLICATE KEY UPDATE is_primary = new.is_primary
            """,
            (id, subclasse_codigo)
        )
        db.execute("COMMIT")
    except Exception as e:
        db.execute("ROLLBACK")
        return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True})

@cliente_bp.route('/clientes/<id>/cnaes/<path:subclasse_codigo>', methods=['DELETE'])
@login_required
def customer_cnaes_delete(id, subclasse_codigo):
    """Remove o vínculo de CNAE do cliente."""
    db = get_db()
    affected = db.update(
        "DELETE FROM customer_cnae WHERE customer_id = %s AND subclasse_codigo = %s",
        (id, subclasse_codigo)
    )
    return jsonify({'deleted': affected > 0})

# Rota para visualizar um cliente
@cliente_bp.route('/clientes/visualizar/<id>')
@login_required
def cliente_visualizar(id):
    # Buscar o cliente pelo ID
    db = get_db()
    cliente = db.fetch_one("SELECT * FROM customers WHERE id = %s", (id,))
    
    if not cliente:
        flash('Cliente não encontrado.', 'danger')
        return redirect(url_for('cliente.clientes'))
    
    # Buscar equipamentos do cliente
    equipamentos = db.fetch_all("""
        SELECT e.*, c.name as customer_name 
        FROM equipment e
        JOIN customers c ON e.customer_id = c.id
        WHERE e.customer_id = %s AND e.active = TRUE
    """, (id,))
    
    # Renderizar a visualização do cliente
    return render_template('cliente_view.html', cliente=cliente, equipamentos=equipamentos)

# Rota para excluir um cliente
@cliente_bp.route('/clientes/excluir/<id>')
@cliente_excluir_required
def cliente_excluir(id):
    # Buscar o cliente pelo ID
    db = get_db()
    cliente = db.fetch_one("SELECT * FROM customers WHERE id = %s", (id,))
    
    if cliente:
        # Verificar se o cliente possui equipamentos ativos
        equipamentos = db.fetch_all("""
            SELECT COUNT(*) as count FROM equipment 
            WHERE customer_id = %s AND active = TRUE
        """, (id,))
        
        if equipamentos and equipamentos[0]['count'] > 0:
            flash('Não é possível excluir o cliente pois existem equipamentos associados a ele.', 'danger')
            return redirect(url_for('cliente.clientes'))
        
        # Marcar o cliente como inativo (exclusão lógica)
        affected_rows = db.update("""
            UPDATE customers SET active = FALSE WHERE id = %s
        """, (id,))
        
        if affected_rows > 0:
            flash('Cliente excluído com sucesso!', 'success')
        else:
            flash('Erro ao excluir cliente.', 'danger')
    else:
        flash('Cliente não encontrado.', 'danger')
    
    # Redirecionar para a lista de clientes
    return redirect(url_for('cliente.clientes'))
