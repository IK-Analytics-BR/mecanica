from flask import Blueprint, request, jsonify, session
from functools import wraps
import sys
import os

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required

# Criar um Blueprint para as rotas de API
api_bp = Blueprint('api', __name__)


# Rota para buscar subgrupos por grupo
@api_bp.route('/api/subgroups-by-group/<int:group_id>', methods=['GET'])
def get_subgroups_by_group(group_id):
    # Buscar subgrupos ativos para o grupo especificado
    db = get_db()
    query = "SELECT * FROM product_subgroups WHERE group_id = %s AND active = TRUE"
    subgroups = db.fetch_all(query, (group_id,))
    
    # Retornar os subgrupos como JSON
    return jsonify({
        'success': True,
        'subgroups': subgroups
    })

# Rota para verificar se um documento (CNPJ/CPF) já existe
@api_bp.route('/api/check-document', methods=['POST', 'GET'])
def check_document():
    # Obter dados da requisição
    if request.method == 'POST':
        data = request.json
        if not data:
            return jsonify({'error': 'Dados inválidos'}), 400
        document_type = data.get('document_type', 'cnpj')
        document_value = data.get('document_value', '')
        entity_type = data.get('entity_type', '')
    else:  # GET
        document_type = request.args.get('document_type', 'cnpj')
        document_value = request.args.get('document_value', '')
        entity_type = request.args.get('entity_type', '')
    
    # Verificar se os dados necessários foram fornecidos
    if not document_value or not entity_type:
        return jsonify({'error': 'Dados incompletos'}), 400
    
    # Limpar o documento (remover caracteres especiais)
    clean_document = ''.join(filter(str.isdigit, document_value))
    if not clean_document:
        return jsonify({'error': 'Documento inválido'}), 400
    
    # Determinar a tabela a ser consultada com base no tipo de entidade
    table = 'customers' if entity_type == 'cliente' else 'suppliers'
    
    # Consultar o banco de dados
    db = get_db()
    query = f"SELECT id, name, cnpj, city, state, phone, email FROM {table} WHERE REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '-', ''), '/', '') = %s AND active = TRUE"
    entity = db.fetch_one(query, (clean_document,))
    
    # Retornar resultado
    if entity:
        return jsonify({
            'exists': True,
            'entity_id': entity['id'],
            'entity_name': entity['name'],
            'entity_type': entity_type,
            'entity_cnpj': entity['cnpj'],
            'entity_city': entity['city'],
            'entity_state': entity['state'],
            'entity_phone': entity['phone'],
            'entity_email': entity['email']
        })
    else:
        return jsonify({'exists': False})

# Rota para buscar informações detalhadas do fornecedor
@api_bp.route('/api/suppliers/<int:supplier_id>', methods=['GET'])
def get_supplier_details(supplier_id):
    """Retorna informações detalhadas de um fornecedor."""
    db = get_db()
    
    # Buscar dados do fornecedor
    supplier = db.fetch_one("""
        SELECT id, name, razao_social as legal_name, cnpj as tax_id, contact_name, email, phone, 
               address, city, state, cep as zip_code, 'Brasil' as country, website, notes
        FROM suppliers
        WHERE id = %s
    """, (supplier_id,))
    
    if not supplier:
        return jsonify({'error': 'Fornecedor não encontrado'}), 404
    
    # Retornar dados do fornecedor
    return jsonify(supplier)

# Rota para buscar informações do produto
@api_bp.route('/api/products/<int:product_id>', methods=['GET'])
def get_product_details(product_id):
    """Retorna informações detalhadas de um produto."""
    db = get_db()
    
    # Buscar dados do produto
    product = db.fetch_one("""
        SELECT p.id, p.name, p.description, p.unit_measure, p.cost_price, 
               p.price, p.stock_quantity, p.ncm, p.barcode,
               b.name as brand_name, c.name as category_name
        FROM products p
        LEFT JOIN product_brands b ON p.brand_id = b.id
        LEFT JOIN product_categories c ON p.category_id = c.id
        WHERE p.id = %s
    """, (product_id,))
    
    if not product:
        return jsonify({'error': 'Produto não encontrado'}), 404
    
    # Buscar último preço de compra do produto
    last_purchase = db.fetch_one("""
        SELECT poi.unit_price, po.order_date
        FROM purchase_order_items poi
        JOIN purchase_orders po ON poi.purchase_order_id = po.id
        WHERE poi.product_id = %s
        ORDER BY po.order_date DESC
        LIMIT 1
    """, (product_id,))
    
    if last_purchase:
        product['last_purchase_price'] = float(last_purchase['unit_price'])
        product['last_purchase_date'] = last_purchase['order_date'].strftime('%Y-%m-%d') if last_purchase['order_date'] else None
    else:
        product['last_purchase_price'] = float(product['cost_price']) if product['cost_price'] else 0
        product['last_purchase_date'] = None
    
    # Retornar dados do produto
    return jsonify(product)

# =====================================================
# ROTAS PARA PDV MODERNO
# =====================================================

# Rota para buscar clientes (F2 no PDV)
@api_bp.route('/api/clientes/buscar', methods=['GET'])
@login_required
def buscar_clientes():
    """Busca clientes por CPF/CNPJ ou nome para o PDV."""
    termo = request.args.get('q', '').strip()
    
    if len(termo) < 2:
        return jsonify([])
    
    db = get_db()
    
    # Limpar termo para busca de documento
    termo_limpo = ''.join(filter(str.isdigit, termo))
    
    # Buscar por CPF/CNPJ ou nome
    if termo_limpo and len(termo_limpo) >= 3:
        # Busca por documento
        clientes = db.fetch_all("""
            SELECT 
                id,
                name,
                cpf_cnpj,
                email,
                phone,
                city,
                state
            FROM customers
            WHERE active = TRUE
            AND (
                REPLACE(REPLACE(REPLACE(cpf_cnpj, '.', ''), '-', ''), '/', '') LIKE %s
                OR name LIKE %s
            )
            ORDER BY name
            LIMIT 20
        """, (f'%{termo_limpo}%', f'%{termo}%'))
    else:
        # Busca por nome
        clientes = db.fetch_all("""
            SELECT 
                id,
                name,
                cpf_cnpj,
                email,
                phone,
                city,
                state
            FROM customers
            WHERE active = TRUE
            AND name LIKE %s
            ORDER BY name
            LIMIT 20
        """, (f'%{termo}%',))
    
    return jsonify(clientes or [])

# Rota para buscar produtos (F3 no PDV)
@api_bp.route('/api/produtos/buscar', methods=['GET'])
@login_required
def buscar_produtos():
    """Busca produtos por código, código de barras ou nome para o PDV."""
    termo = request.args.get('q', '').strip()
    
    if len(termo) < 2:
        return jsonify([])
    
    db = get_db()
    
    # Buscar produtos usando apenas colunas básicas (id, name)
    try:
        # Primeiro, buscar usando apenas ID e NAME (sempre existem)
        produtos = db.fetch_all("""
            SELECT 
                id,
                name,
                CAST(id AS CHAR) AS code,
                '' AS barcode,
                0 as sale_price,
                0 as stock,
                'UN' as unit_measure
            FROM products
            WHERE active = TRUE
            AND (
                name LIKE %s
                OR CAST(id AS CHAR) = %s
            )
            ORDER BY name
            LIMIT 20
        """, (f'%{termo}%', termo))
        
        # Tentar adicionar preço se coluna existir
        for produto in produtos or []:
            # Buscar preço de qualquer coluna possível
            try:
                preco_row = db.fetch_one("""
                    SELECT 
                        COALESCE(sale_price, price, unit_price, 0) as preco
                    FROM products
                    WHERE id = %s
                """, (produto['id'],))
                if preco_row:
                    produto['sale_price'] = float(preco_row.get('preco', 0))
            except:
                produto['sale_price'] = 0
                
    except Exception as e:
        print(f"[API] Erro ao buscar produtos: {e}")
        return jsonify([])
    
    # Calcular estoque real via stock_movements
    for produto in produtos or []:
        movimentos = db.fetch_one("""
            SELECT COALESCE(SUM(quantity), 0) as total
            FROM stock_movements
            WHERE product_id = %s
        """, (produto['id'],))
        
        if movimentos:
            produto['stock'] = float(movimentos['total'] or 0)
    
    return jsonify(produtos or [])
