from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from functools import wraps
from werkzeug.utils import secure_filename
import mysql.connector
import sys
import os
import uuid

# Adicionar o diretório pai ao path para importar db_config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Extensões permitidas para upload de imagem
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_photo(photo):
    """Salva a foto do produto e retorna a URL relativa."""
    if photo and allowed_file(photo.filename):
        # Gerar nome único para o arquivo
        ext = photo.filename.rsplit('.', 1)[1].lower()
        filename = f"produto_{uuid.uuid4().hex}.{ext}"
        
        # Definir pasta de upload
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'produtos')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Salvar arquivo
        filepath = os.path.join(upload_folder, filename)
        photo.save(filepath)
        
        # Retornar URL relativa
        return f"/static/uploads/produtos/{filename}"
    return None
from db_config import get_db_connection
from utils.permissoes_helper import tem_permissao


# Decorators para permissões granulares
def produto_visualizar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('produtos.lista', 'visualizar'):
            flash('Você não tem permissão para visualizar produtos.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function

def produto_criar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('produtos.lista', 'criar'):
            flash('Você não tem permissão para cadastrar produtos.', 'danger')
            return redirect(url_for('produto.produtos'))
        return f(*args, **kwargs)
    return decorated_function

def produto_editar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('produtos.lista', 'editar'):
            flash('Você não tem permissão para editar produtos.', 'danger')
            return redirect(url_for('produto.produtos'))
        return f(*args, **kwargs)
    return decorated_function

def produto_excluir_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('produtos.lista', 'excluir'):
            flash('Você não tem permissão para excluir produtos.', 'danger')
            return redirect(url_for('produto.produtos'))
        return f(*args, **kwargs)
    return decorated_function

# Função para obter conexão direta com o banco de dados
# AGORA LÊ DO ARQUIVO .env AUTOMATICAMENTE!
def get_direct_db():
    return get_db_connection()

# Função para converter valores de formulário em número decimal, aceitando vírgula
def safe_decimal(value, default=0.0):
    """Converte strings de formulário para float.

    - Trata None e string vazia como default (0.0, por padrão).
    - Aceita vírgula como separador decimal ("17,45" -> 17.45).
    - Mantém compatibilidade caso value já venha numérico.
    """
    if value is None:
        return default
    # Se já for número, tenta converter direto
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    # Normalizar strings
    try:
        s = str(value).strip()
        if s == '':
            return default
        # Trocar vírgula por ponto para suportar formato brasileiro
        s = s.replace(',', '.')
        return float(s)
    except (ValueError, TypeError):
        return default

produto_bp = Blueprint('produto', __name__)

# Rota para listar produtos
@produto_bp.route('/produtos')
@produto_visualizar_required
def produtos():
    """Lista produtos com busca avançada opcional via query string."""
    search_term = request.args.get('search_term', '').strip()
    search_field = request.args.get('search_field', 'all')

    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)

    if search_term:
        like = f"%{search_term}%"
        query = None
        params = None

        # Campos textuais
        if search_field == 'name':
            query = "SELECT * FROM products WHERE active = TRUE AND name LIKE %s"
            params = (like,)
        elif search_field == 'category_any':
            # Categoria por ID ou Nome (ou texto livre em p.category)
            query = (
                """
                SELECT DISTINCT p.*
                FROM products p
                LEFT JOIN product_categories pc ON pc.id = p.category_id
                WHERE p.active = TRUE AND (
                    pc.name LIKE %s OR CAST(p.category_id AS CHAR) LIKE %s OR p.category LIKE %s
                )
                """
            )
            params = (like, like, like)
        elif search_field == 'description':
            query = "SELECT * FROM products WHERE active = TRUE AND description LIKE %s"
            params = (like,)
        elif search_field == 'barcode':
            query = "SELECT * FROM products WHERE active = TRUE AND barcode LIKE %s"
            params = (like,)
        elif search_field == 'unit_measure':
            query = "SELECT * FROM products WHERE active = TRUE AND unit_measure LIKE %s"
            params = (like,)
        elif search_field == 'supplier_code':
            query = "SELECT * FROM products WHERE active = TRUE AND supplier_code LIKE %s"
            params = (like,)
        elif search_field == 'location':
            query = "SELECT * FROM products WHERE active = TRUE AND location LIKE %s"
            params = (like,)
        elif search_field == 'lot_number':
            query = "SELECT * FROM products WHERE active = TRUE AND lot_number LIKE %s"
            params = (like,)
        elif search_field == 'notes':
            query = "SELECT * FROM products WHERE active = TRUE AND notes LIKE %s"
            params = (like,)
        elif search_field == 'category':
            query = "SELECT * FROM products WHERE active = TRUE AND category LIKE %s"
            params = (like,)
        elif search_field == 'category_name':
            query = (
                """
                SELECT DISTINCT p.*
                FROM products p
                LEFT JOIN product_categories pc ON pc.id = p.category_id
                WHERE p.active = TRUE AND pc.name LIKE %s
                """
            )
            params = (like,)
        elif search_field == 'brand_name':
            query = (
                """
                SELECT DISTINCT p.*
                FROM products p
                LEFT JOIN product_brands pb ON pb.id = p.brand_id
                WHERE p.active = TRUE AND pb.name LIKE %s
                """
            )
            params = (like,)
        elif search_field == 'group_name':
            query = (
                """
                SELECT DISTINCT p.*
                FROM products p
                LEFT JOIN product_groups pg ON pg.id = p.group_id
                WHERE p.active = TRUE AND pg.name LIKE %s
                """
            )
            params = (like,)
        elif search_field == 'subgroup_name':
            query = (
                """
                SELECT DISTINCT p.*
                FROM products p
                LEFT JOIN product_subgroups psg ON psg.id = p.subgroup_id
                WHERE p.active = TRUE AND psg.name LIKE %s
                """
            )
            params = (like,)
        elif search_field == 'ncm':
            query = "SELECT * FROM products WHERE active = TRUE AND ncm LIKE %s"
            params = (like,)
        elif search_field == 'cest':
            query = "SELECT * FROM products WHERE active = TRUE AND cest LIKE %s"
            params = (like,)
        elif search_field == 'cfop_in':
            query = "SELECT * FROM products WHERE active = TRUE AND cfop_in LIKE %s"
            params = (like,)
        elif search_field == 'cfop_out':
            query = "SELECT * FROM products WHERE active = TRUE AND cfop_out LIKE %s"
            params = (like,)
        elif search_field == 'cst_csosn':
            query = "SELECT * FROM products WHERE active = TRUE AND cst_csosn LIKE %s"
            params = (like,)
        elif search_field == 'origin':
            query = "SELECT * FROM products WHERE active = TRUE AND CAST(origin AS CHAR) LIKE %s"
            params = (like,)

        # IDs e chaves estrangeiras
        elif search_field == 'id':
            if search_term.isdigit():
                query = "SELECT * FROM products WHERE active = TRUE AND id = %s"
                params = (int(search_term),)
            else:
                query = "SELECT * FROM products WHERE active = TRUE AND CAST(id AS CHAR) LIKE %s"
                params = (like,)
        elif search_field == 'category_id':
            query = "SELECT * FROM products WHERE active = TRUE AND CAST(category_id AS CHAR) LIKE %s"
            params = (like,)
        elif search_field == 'brand_id':
            query = "SELECT * FROM products WHERE active = TRUE AND CAST(brand_id AS CHAR) LIKE %s"
            params = (like,)
        elif search_field == 'group_id':
            query = "SELECT * FROM products WHERE active = TRUE AND CAST(group_id AS CHAR) LIKE %s"
            params = (like,)
        elif search_field == 'subgroup_id':
            query = "SELECT * FROM products WHERE active = TRUE AND CAST(subgroup_id AS CHAR) LIKE %s"
            params = (like,)
        elif search_field == 'main_supplier_id':
            query = "SELECT * FROM products WHERE active = TRUE AND CAST(main_supplier_id AS CHAR) LIKE %s"
            params = (like,)

        # Númericos/decimais
        elif search_field in (
            'icms_rate','pis_rate','cofins_rate','ipi_rate','last_purchase_price','avg_delivery_time',
            'cost_price','margin','price','max_discount','stock_quantity','min_stock','max_stock',
            'net_weight','gross_weight','length_cm','width_cm','height_cm','volume_m3','latitude','longitude'
        ):
            query = f"SELECT * FROM products WHERE active = TRUE AND CAST({search_field} AS CHAR) LIKE %s"
            params = (like,)
        elif search_field == 'expiry_date':
            query = "SELECT * FROM products WHERE active = TRUE AND CAST(expiry_date AS CHAR) LIKE %s"
            params = (like,)

        # Booleans
        elif search_field in ('active','lot_control','serial_control','imported'):
            # aceita 1/0, true/false
            val = search_term.lower()
            if val in ('1','true','sim','yes'): val = 1
            elif val in ('0','false','nao','não','no'): val = 0
            else:
                # fallback like em CHAR
                query = f"SELECT * FROM products WHERE active = TRUE AND CAST({search_field} AS CHAR) LIKE %s"
                params = (like,)
            if query is None:
                query = f"SELECT * FROM products WHERE active = TRUE AND {search_field} = %s"
                params = (val,)

        # All (campos principais)
        else:
            # Busca ampla, incluindo nomes descritivos das tabelas relacionadas
            query = (
                """
                SELECT DISTINCT p.*
                FROM products p
                LEFT JOIN product_categories pc ON pc.id = p.category_id
                LEFT JOIN product_brands pb ON pb.id = p.brand_id
                LEFT JOIN product_groups pg ON pg.id = p.group_id
                LEFT JOIN product_subgroups psg ON psg.id = p.subgroup_id
                WHERE p.active = TRUE AND (
                    p.name LIKE %s OR p.description LIKE %s OR p.barcode LIKE %s OR p.unit_measure LIKE %s OR
                    p.ncm LIKE %s OR p.cest LIKE %s OR p.cfop_in LIKE %s OR p.cfop_out LIKE %s OR p.cst_csosn LIKE %s OR p.category LIKE %s OR
                    p.supplier_code LIKE %s OR p.location LIKE %s OR p.lot_number LIKE %s OR p.notes LIKE %s OR
                    pc.name LIKE %s OR pb.name LIKE %s OR pg.name LIKE %s OR psg.name LIKE %s
                )
                """
            )
            params = (
                like, like, like, like, like, like, like, like, like, like,
                like, like, like, like,
                like, like, like, like
            )

        cursor.execute(query, params)
        produtos = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM products WHERE active = TRUE")
        produtos = cursor.fetchall()

    # Enriquecer produtos com informações de categoria (nome e categoria_fiscal)
    try:
        if produtos:
            cursor.execute("SELECT id, name, categoria_fiscal FROM product_categories WHERE active = TRUE")
            categorias_all = cursor.fetchall() or []
            categorias_map = {c.get('id'): c for c in categorias_all}

            for p in produtos:
                cid = p.get('category_id') if isinstance(p, dict) else None
                cat = categorias_map.get(cid) if cid is not None else None
                if cat:
                    # Campos adicionais usados no template
                    p['categoria_nome'] = cat.get('name')
                    p['categoria_fiscal'] = cat.get('categoria_fiscal')
    except Exception as e:
        # Em caso de qualquer erro, seguimos sem quebrar a listagem
        print(f"[PRODUTOS] Aviso ao enriquecer categorias: {e}")

    cursor.close()
    conn.close()
    return render_template('produto_list.html', produtos=produtos, search_term=search_term, search_field=search_field)

# Rota para cadastrar um novo produto
@produto_bp.route('/produtos/cadastrar', methods=['GET', 'POST'])
@produto_criar_required
def produto_cadastrar():
    # Buscar categorias, marcas, grupos e unidades de medida para o formulário
    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)
    modelos = []  # garante variável definida
    
    # Buscar categorias
    cursor.execute("SELECT * FROM product_categories WHERE active = TRUE ORDER BY name")
    categorias = cursor.fetchall()
    
    # Buscar marcas
    cursor.execute("SELECT * FROM product_brands WHERE active = TRUE ORDER BY name")
    marcas = cursor.fetchall()
    
    # Buscar grupos
    cursor.execute("SELECT * FROM product_groups WHERE active = TRUE ORDER BY name")
    grupos = cursor.fetchall()
    
    # Buscar fornecedores
    cursor.execute("SELECT * FROM suppliers WHERE active = TRUE ORDER BY name")
    fornecedores = cursor.fetchall()
    
    # Buscar unidades de medida
    cursor.execute("SELECT * FROM unit_measures WHERE active = TRUE ORDER BY code")
    unit_measures = cursor.fetchall()
    
    # Carregar modelos para o formulário de edição
    cursor.execute("SELECT * FROM product_models WHERE active = TRUE ORDER BY name")
    modelos = cursor.fetchall()
    try:
        print(f"[DEBUG] modelos carregados (editar): {len(modelos)}")
    except Exception:
        pass
    
    # Carregar modelos para o formulário de edição
    cursor.execute("SELECT * FROM product_models WHERE active = TRUE ORDER BY name")
    modelos = cursor.fetchall()
    
    # Carregar modelos (uma vez)
    cursor.execute("SELECT * FROM product_models WHERE active = TRUE ORDER BY name")
    modelos = cursor.fetchall()
    try:
        print(f"[DEBUG] modelos carregados (cadastrar): {len(modelos)}")
    except Exception:
        pass
    
    # Subgrupos serão carregados via AJAX
    subgrupos = []
    
    if request.method == 'POST':
        try:
            # 1. Dados Básicos
            name = request.form.get('name', '')
            description = request.form.get('description', '')
            barcode = request.form.get('barcode', '')
            unit_measure = request.form.get('unit_measure', '')
            category_id = request.form.get('category_id') or None
            brand_id = request.form.get('brand_id') or None
            model_id = request.form.get('model_id')
            model_id = int(model_id) if model_id and str(model_id).strip() != '' else None
            group_id = request.form.get('group_id') or None
            subgroup_id = request.form.get('subgroup_id') or None
            
            # 2. Dados Fiscais
            ncm = request.form.get('ncm', '')
            cest = request.form.get('cest', '')
            cfop_in = request.form.get('cfop_in', '')
            cfop_out = request.form.get('cfop_out', '')
            cst_csosn = request.form.get('cst_csosn', '')
            origin = request.form.get('origin') or None
            
            # Converter campos decimais vazios para zero
            icms_rate = safe_decimal(request.form.get('icms_rate'))
            pis_rate = safe_decimal(request.form.get('pis_rate'))
            cofins_rate = safe_decimal(request.form.get('cofins_rate'))
            ipi_rate = safe_decimal(request.form.get('ipi_rate'))
            
            tax_benefits = request.form.get('tax_benefits', '')
            
            # 3. Dados de Compras
            main_supplier_id = request.form.get('main_supplier_id') or None
            supplier_code = request.form.get('supplier_code', '')
            last_purchase_price = safe_decimal(request.form.get('last_purchase_price'))
            # Prazo médio de entrega (dias) – pode vir vazio
            avg_delivery_time = request.form.get('avg_delivery_time') or None
            # Novos campos de unidade de compra e custos adicionais (frete, ICMS, outros)
            purchase_unit = request.form.get('purchase_unit', '')
            purchase_factor = safe_decimal(request.form.get('purchase_factor'))
            purchase_freight_value = safe_decimal(request.form.get('purchase_freight_value'))
            purchase_icms_value = safe_decimal(request.form.get('purchase_icms_value'))
            purchase_other_costs_value = safe_decimal(request.form.get('purchase_other_costs_value'))

            # 4. Dados de Preço (movidos para Identificação Básica)
            # Nesta implementação, cost_price representa o custo da unidade de compra (ex.: PCT, CX, FARDO)
            cost_price_form = safe_decimal(request.form.get('cost_price'))
            cost_price = cost_price_form

            # Se o usuário não informou explicitamente o preço de custo, mas informou componentes de compra,
            # somamos os componentes para definir o custo da unidade de compra.
            lp = last_purchase_price or 0
            pfv = purchase_freight_value or 0
            piv = purchase_icms_value or 0
            po = purchase_other_costs_value or 0
            if (cost_price is None or cost_price == 0) and any(v > 0 for v in (lp, pfv, piv, po)):
                cost_price = lp + pfv + piv + po

            # Custo convertido por unidade base (ex.: R$/KG) vai em purchase_total_cost.
            # Preferimos o valor enviado pelo formulário (calculado no JS) e, se não existir,
            # calculamos a partir de cost_price e purchase_factor.
            purchase_total_cost = safe_decimal(request.form.get('purchase_total_cost'), default=None)
            if (purchase_total_cost is None or purchase_total_cost <= 0) and cost_price and purchase_factor and purchase_factor > 0:
                try:
                    purchase_total_cost = cost_price / purchase_factor
                except Exception:
                    purchase_total_cost = None
            margin = safe_decimal(request.form.get('margin'))
            price = safe_decimal(request.form.get('price'))
            max_discount = safe_decimal(request.form.get('max_discount'))
            
            # 5. Estoque e Logística
            stock_quantity = safe_decimal(request.form.get('stock_quantity'))
            min_stock = safe_decimal(request.form.get('min_stock'))
            max_stock = safe_decimal(request.form.get('max_stock'))
            location = request.form.get('location', '')
            lot_number = request.form.get('lot_number', '')
            expiry_date = request.form.get('expiry_date') or None
            net_weight = safe_decimal(request.form.get('net_weight'))
            gross_weight = safe_decimal(request.form.get('gross_weight'))
            length_cm = safe_decimal(request.form.get('length_cm'))
            width_cm = safe_decimal(request.form.get('width_cm'))
            height_cm = safe_decimal(request.form.get('height_cm'))
            volume_m3 = safe_decimal(request.form.get('volume_m3'))
            
            # 6. Integrações / Outras Informações
            active = 'active' in request.form
            lot_control = 'lot_control' in request.form
            serial_control = 'serial_control' in request.form
            imported = 'imported' in request.form
            notes = request.form.get('notes', '')
            # Tipo de Produto (standalone | parent | child)
            product_type = request.form.get('product_type', 'standalone')
            
            # Upload de foto
            photo_url = ''
            if 'photo_upload' in request.files and request.files['photo_upload'].filename:
                photo = request.files['photo_upload']
                new_photo_url = save_photo(photo)
                if new_photo_url:
                    photo_url = new_photo_url
            
            # Definir valor da coluna legacy `category` (string) com base na categoria selecionada
            category = "outro"
            if category_id:
                try:
                    for cat in categorias:
                        if str(cat.get('id')) == str(category_id):
                            category = cat.get('name') or "outro"
                            break
                except Exception:
                    # Em caso de qualquer problema, mantém "outro" para não quebrar o insert
                    pass
            
            # Validar dados obrigatórios
            if not name or price <= 0:
                flash('Nome e Preço de Venda são campos obrigatórios.', 'danger')
                cursor.close()
                conn.close()
                return render_template('produto_form_abas.html', produto=None, categorias=categorias, 
                                    marcas=marcas, grupos=grupos, subgrupos=subgrupos,
                                    fornecedores=fornecedores, unit_measures=unit_measures,
                                    modelos=modelos,
                                    ncm_description='',
                                    cfop_in_description='',
                                    cfop_out_description='')
            
            # Inserir produto no banco de dados usando conexão direta
            insert_cursor = conn.cursor()
            
            # Montar colunas/params dinamicamente para evitar desalinhamentos
            cols = [
                'name','description','barcode','unit_measure',
                'category_id','brand_id','model_id','group_id','subgroup_id',
                'ncm','cest','cfop_in','cfop_out','cst_csosn','origin',
                'icms_rate','pis_rate','cofins_rate','ipi_rate','tax_benefits',
                'main_supplier_id','supplier_code','last_purchase_price','avg_delivery_time',
                'purchase_unit','purchase_factor','purchase_freight_value','purchase_icms_value','purchase_other_costs_value','purchase_total_cost',
                'cost_price','margin','price','max_discount',
                'stock_quantity','min_stock','max_stock','location','lot_number',
                'net_weight','gross_weight','length_cm','width_cm','height_cm','volume_m3',
                'active','lot_control','serial_control','imported','notes','photo_url','category','product_type'
            ]
            placeholders = ', '.join(['%s'] * len(cols))
            query = f"INSERT INTO products ({', '.join(cols)}) VALUES ({placeholders})"
            params = (
                name, description, barcode, unit_measure,
                category_id, brand_id, model_id, group_id, subgroup_id,
                ncm, cest, cfop_in, cfop_out, cst_csosn, origin,
                icms_rate, pis_rate, cofins_rate, ipi_rate, tax_benefits,
                main_supplier_id, supplier_code, last_purchase_price, avg_delivery_time,
                purchase_unit, purchase_factor, purchase_freight_value, purchase_icms_value, purchase_other_costs_value, purchase_total_cost,
                cost_price, margin, price, max_discount,
                stock_quantity, min_stock, max_stock, location, lot_number,
                net_weight, gross_weight, length_cm, width_cm, height_cm, volume_m3,
                active, lot_control, serial_control, imported, notes, photo_url, category, product_type
            )
            
            print("Tentando inserir produto com os seguintes parâmetros:")
            print(f"Nome: {name}")
            print(f"Preço: {price}")
            print(f"Categoria: {category}")
            print(f"ICMS: {icms_rate}")
            print(f"PIS: {pis_rate}")
            print(f"COFINS: {cofins_rate}")
            print(f"IPI: {ipi_rate}")
            try:
                print(f"DEBUG cols: {len(cols)} | placeholders: {len(cols)} | params: {len(params)}")
            except Exception:
                pass
            
            insert_cursor.execute(query, params)
            conn.commit()
            
            produto_id = insert_cursor.lastrowid
            insert_cursor.close()

            # Recalcular custos em cascata após criação de produto
            try:
                sp_cursor = conn.cursor()
                sp_cursor.execute("CALL sp_recalcular_custos_fichas()")
                conn.commit()
                sp_cursor.close()
            except Exception as sp_err:
                # Não impede o cadastro do produto; apenas registra no log
                print(f"[PRODUTO] Aviso: erro ao executar sp_recalcular_custos_fichas() apos cadastro: {sp_err}")
            
            if produto_id:
                flash(f'Produto cadastrado com sucesso! ID: {produto_id}', 'success')
                cursor.close()
                conn.close()
                return redirect(url_for('produto.produtos'))
            else:
                flash('Erro ao cadastrar produto: Nenhum ID retornado.', 'danger')
                
        except Exception as e:
            conn.rollback()
            print(f"ERRO AO CADASTRAR PRODUTO: {str(e)}")
            flash(f'Erro ao cadastrar produto: {str(e)}', 'danger')
        finally:
            if 'insert_cursor' in locals() and insert_cursor:
                insert_cursor.close()
    
    # Fechar conexão
    cursor.close()
    conn.close()
    
    # Renderizar o formulário de cadastro
    return render_template('produto_form_abas.html', produto=None, categorias=categorias, 
                           marcas=marcas, grupos=grupos, subgrupos=subgrupos,
                           fornecedores=fornecedores, unit_measures=unit_measures,
                           modelos=modelos,
                           ncm_description='',
                           cfop_in_description='',
                           cfop_out_description='')

# Rota para editar um produto existente
@produto_bp.route('/produtos/editar/<id>', methods=['GET', 'POST'])
@produto_editar_required
def produto_editar(id):
    # Buscar o produto pelo ID
    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)
    modelos = []  # garante variável definida
    
    cursor.execute("SELECT * FROM products WHERE id = %s", (id,))
    produto = cursor.fetchone()
    
    if not produto:
        flash('Produto não encontrado.', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('produto.produtos'))
    
    # Buscar categorias, marcas, grupos e unidades de medida para o formulário
    cursor.execute("SELECT * FROM product_categories WHERE active = TRUE ORDER BY name")
    categorias = cursor.fetchall()
    
    cursor.execute("SELECT * FROM product_brands WHERE active = TRUE ORDER BY name")
    marcas = cursor.fetchall()
    
    cursor.execute("SELECT * FROM product_groups WHERE active = TRUE ORDER BY name")
    grupos = cursor.fetchall()
    
    cursor.execute("SELECT * FROM suppliers WHERE active = TRUE ORDER BY name")
    fornecedores = cursor.fetchall()
    
    cursor.execute("SELECT * FROM unit_measures WHERE active = TRUE ORDER BY code")
    unit_measures = cursor.fetchall()
    
    # Carregar modelos para o formulário de edição
    cursor.execute("SELECT * FROM product_models WHERE active = TRUE ORDER BY name")
    modelos = cursor.fetchall()
    try:
        print(f"[DEBUG] modelos carregados (editar): {len(modelos)}")
    except Exception:
        pass
    
    # Buscar descrições de NCM e CFOPs para exibir no formulário de edição
    ncm_description = ''
    cfop_in_description = ''
    cfop_out_description = ''
    
    if produto.get('ncm'):
        cursor.execute("SELECT descricao FROM ncm WHERE codigo = %s LIMIT 1", (produto['ncm'],))
        row = cursor.fetchone()
        if row:
            ncm_description = row['descricao']

    
    if produto.get('cfop_in'):
        cursor.execute("SELECT descricao FROM cfop WHERE codigo = %s LIMIT 1", (produto['cfop_in'],))
        row = cursor.fetchone()
        if row:
            cfop_in_description = row['descricao']
    
    if produto.get('cfop_out'):
        cursor.execute("SELECT descricao FROM cfop WHERE codigo = %s LIMIT 1", (produto['cfop_out'],))
        row = cursor.fetchone()
        if row:
            cfop_out_description = row['descricao']
    
    # Se o produto tem um grupo, buscar os subgrupos desse grupo
    subgrupos = []
    if produto['group_id']:
        cursor.execute("SELECT * FROM product_subgroups WHERE group_id = %s AND active = TRUE ORDER BY name", (produto['group_id'],))
        subgrupos = cursor.fetchall()

    # Candidatos a filhos (insumos): produtos do tipo 'child'
    cursor.execute("SELECT id, name, unit_measure FROM products WHERE active = TRUE AND product_type = 'child' ORDER BY name")
    child_candidates = cursor.fetchall()
    
    # Carregar dados para aba Especificações Técnicas
    especificacao = None
    tipos_correia = []
    materiais_correia = []
    perfis_correia = []
    try:
        cursor.execute("SELECT * FROM produto_especificacoes_tecnicas WHERE produto_id = %s", (id,))
        especificacao = cursor.fetchone()
        cursor.execute("SELECT * FROM tipos_correia WHERE ativo = 1 ORDER BY nome")
        tipos_correia = cursor.fetchall()
        cursor.execute("SELECT * FROM materiais_correia WHERE ativo = 1 ORDER BY nome")
        materiais_correia = cursor.fetchall()
        cursor.execute("SELECT * FROM perfis_correia WHERE ativo = 1 ORDER BY codigo")
        perfis_correia = cursor.fetchall()
    except Exception as e:
        print(f"[PRODUTO] Aviso: Tabelas de especificações não encontradas: {e}")
    
    if request.method == 'POST':
        try:
            # 1. Dados Básicos
            name = request.form.get('name', '')
            description = request.form.get('description', '')
            barcode = request.form.get('barcode', '')
            unit_measure = request.form.get('unit_measure', '')
            category_id = request.form.get('category_id') or None
            brand_id = request.form.get('brand_id') or None
            model_id = request.form.get('model_id') or None
            group_id = request.form.get('group_id') or None
            subgroup_id = request.form.get('subgroup_id') or None
            
            # 2. Dados Fiscais
            ncm = request.form.get('ncm', '')
            cest = request.form.get('cest', '')
            cfop_in = request.form.get('cfop_in', '')
            cfop_out = request.form.get('cfop_out', '')
            cst_csosn = request.form.get('cst_csosn', '')
            origin = request.form.get('origin') or None
            
            # Converter campos decimais vazios para zero
            icms_rate = safe_decimal(request.form.get('icms_rate'))
            pis_rate = safe_decimal(request.form.get('pis_rate'))
            cofins_rate = safe_decimal(request.form.get('cofins_rate'))
            ipi_rate = safe_decimal(request.form.get('ipi_rate'))
            
            tax_benefits = request.form.get('tax_benefits', '')
            
            # 3. Dados de Compras
            main_supplier_id = request.form.get('main_supplier_id') or None
            supplier_code = request.form.get('supplier_code', '')
            last_purchase_price = safe_decimal(request.form.get('last_purchase_price'))
            avg_delivery_time = request.form.get('avg_delivery_time') or None
            purchase_unit = request.form.get('purchase_unit', '')
            purchase_factor = safe_decimal(request.form.get('purchase_factor'))
            purchase_freight_value = safe_decimal(request.form.get('purchase_freight_value'))
            purchase_icms_value = safe_decimal(request.form.get('purchase_icms_value'))
            purchase_other_costs_value = safe_decimal(request.form.get('purchase_other_costs_value'))

            # 4. Dados de Preço (movidos para Identificação Básica)
            # Aqui também consideramos cost_price como custo da unidade de compra (PCT/CX/FARDO...)
            cost_price_form = safe_decimal(request.form.get('cost_price'))
            cost_price = cost_price_form

            lp = last_purchase_price or 0
            pfv = purchase_freight_value or 0
            piv = purchase_icms_value or 0
            po = purchase_other_costs_value or 0
            if (cost_price is None or cost_price == 0) and any(v > 0 for v in (lp, pfv, piv, po)):
                cost_price = lp + pfv + piv + po

            # Custo convertido por unidade base (ex.: R$/KG) armazenado em purchase_total_cost
            purchase_total_cost = safe_decimal(request.form.get('purchase_total_cost'), default=None)
            if (purchase_total_cost is None or purchase_total_cost <= 0) and cost_price and purchase_factor and purchase_factor > 0:
                try:
                    purchase_total_cost = cost_price / purchase_factor
                except Exception:
                    purchase_total_cost = None
            margin = safe_decimal(request.form.get('margin'))
            price = safe_decimal(request.form.get('price'))
            max_discount = safe_decimal(request.form.get('max_discount'))
            
            # 5. Estoque e Logística
            stock_quantity = safe_decimal(request.form.get('stock_quantity'))
            min_stock = safe_decimal(request.form.get('min_stock'))
            max_stock = safe_decimal(request.form.get('max_stock'))
            location = request.form.get('location', '')
            lot_number = request.form.get('lot_number', '')
            expiry_date = request.form.get('expiry_date') or None
            net_weight = safe_decimal(request.form.get('net_weight'))
            gross_weight = safe_decimal(request.form.get('gross_weight'))
            length_cm = safe_decimal(request.form.get('length_cm'))
            width_cm = safe_decimal(request.form.get('width_cm'))
            height_cm = safe_decimal(request.form.get('height_cm'))
            volume_m3 = safe_decimal(request.form.get('volume_m3'))
            
            # 6. Integrações / Outras Informações
            active = 'active' in request.form
            lot_control = 'lot_control' in request.form
            serial_control = 'serial_control' in request.form
            imported = 'imported' in request.form
            notes = request.form.get('notes', '')
            # Tipo de Produto (standalone | parent | child)
            product_type = request.form.get('product_type', produto.get('product_type', 'standalone'))

            # Definir valor da coluna legacy `category` (string) com base na categoria selecionada
            # Mantemos este campo apenas por compatibilidade com telas/rotinas antigas
            category = produto.get('category', 'outro') or 'outro'
            if category_id:
                try:
                    for cat in categorias:
                        if str(cat.get('id')) == str(category_id):
                            category = cat.get('name') or 'outro'
                            break
                except Exception:
                    # Se algo der errado na resolução do nome, mantém valor anterior
                    pass
            
            # Upload de foto - manter a existente se não enviar nova
            photo_url = produto.get('photo_url', '') or ''
            if 'photo_upload' in request.files and request.files['photo_upload'].filename:
                photo = request.files['photo_upload']
                new_photo_url = save_photo(photo)
                if new_photo_url:
                    photo_url = new_photo_url
            
            # Garantir um valor padrão para a coluna legacy `category` se nada foi resolvido
            category = category or "outro"
            
            # Validar dados obrigatórios
            if not name or price <= 0:
                flash('Nome e Preço de Venda são campos obrigatórios.', 'danger')
                cursor.close()
                conn.close()
                return render_template('produto_form_abas.html', produto=produto, categorias=categorias, 
                                    marcas=marcas, grupos=grupos, subgrupos=subgrupos,
                                    fornecedores=fornecedores, unit_measures=unit_measures,
                                    modelos=modelos,
                                    child_candidates=child_candidates,
                                    ncm_description=ncm_description,
                                    cfop_in_description=cfop_in_description,
                                    cfop_out_description=cfop_out_description)
            
            # Atualizar produto no banco de dados usando conexão direta
            update_cursor = conn.cursor()
            
            # Construir a query de atualização
            query = """
                UPDATE products SET 
                    name = %s, description = %s, barcode = %s, unit_measure = %s, 
                    category_id = %s, brand_id = %s, model_id = %s, group_id = %s, subgroup_id = %s,
                    ncm = %s, cest = %s, cfop_in = %s, cfop_out = %s, cst_csosn = %s, origin = %s, 
                    icms_rate = %s, pis_rate = %s, cofins_rate = %s, ipi_rate = %s, tax_benefits = %s,
                    main_supplier_id = %s, supplier_code = %s, last_purchase_price = %s, avg_delivery_time = %s,
                    purchase_unit = %s, purchase_factor = %s, purchase_freight_value = %s, purchase_icms_value = %s, purchase_other_costs_value = %s, purchase_total_cost = %s,
                    cost_price = %s, margin = %s, price = %s, max_discount = %s,
                    stock_quantity = %s, min_stock = %s, max_stock = %s, location = %s, lot_number = %s,
                    net_weight = %s, gross_weight = %s, length_cm = %s, width_cm = %s, height_cm = %s, volume_m3 = %s,
                    active = %s, lot_control = %s, serial_control = %s, imported = %s, notes = %s, photo_url = %s, category = %s,
                    product_type = %s
                WHERE id = %s
            """
            
            params = (
                name, description, barcode, unit_measure, 
                category_id, brand_id, model_id, group_id, subgroup_id,
                ncm, cest, cfop_in, cfop_out, cst_csosn, origin, 
                icms_rate, pis_rate, cofins_rate, ipi_rate, tax_benefits,
                main_supplier_id, supplier_code, last_purchase_price, avg_delivery_time,
                purchase_unit, purchase_factor, purchase_freight_value, purchase_icms_value, purchase_other_costs_value, purchase_total_cost,
                cost_price, margin, price, max_discount,
                stock_quantity, min_stock, max_stock, location, lot_number,
                net_weight, gross_weight, length_cm, width_cm, height_cm, volume_m3,
                active, lot_control, serial_control, imported, notes, photo_url, category,
                product_type,
                id
            )
            
            update_cursor.execute(query, params)
            conn.commit()
            update_cursor.close()

            # Recalcular custos em cascata após atualização de produto
            try:
                sp_cursor = conn.cursor()
                sp_cursor.execute("CALL sp_recalcular_custos_fichas()")
                conn.commit()
                sp_cursor.close()
            except Exception as sp_err:
                print(f"[PRODUTO] Aviso: erro ao executar sp_recalcular_custos_fichas() apos edicao: {sp_err}")
            
            # MySQL retorna 0 em rowcount se os dados não mudaram, mas o UPDATE foi bem-sucedido
            # Portanto, não verificamos affected_rows - se chegou aqui sem exceção, deu certo
            if True:
                # Salvar especificações técnicas (se preenchidas)
                try:
                    spec_tipo_id = request.form.get('spec_tipo_correia_id') or None
                    spec_material_id = request.form.get('spec_material_base_id') or None
                    spec_perfil_id = request.form.get('spec_perfil_id') or None
                    spec_largura = request.form.get('spec_largura_mm') or None
                    spec_comprimento = request.form.get('spec_comprimento_mm') or None
                    spec_espessura = request.form.get('spec_espessura_mm') or None
                    spec_cor = request.form.get('spec_cor') or None
                    spec_dureza = request.form.get('spec_dureza_shore') or None
                    spec_lonas = request.form.get('spec_numero_lonas') or None
                    spec_tipo_lona = request.form.get('spec_tipo_lona') or None
                    spec_emenda = request.form.get('spec_tipo_emenda') or None
                    spec_borda = request.form.get('spec_acabamento_borda') or None
                    spec_temp_min = request.form.get('spec_temperatura_min') or None
                    spec_temp_max = request.form.get('spec_temperatura_max') or None
                    spec_aplicacao = request.form.get('spec_aplicacao') or None
                    spec_ambiente = request.form.get('spec_ambiente') or None
                    spec_obs = request.form.get('spec_observacoes_tecnicas') or None
                    
                    # Verificar se tem algum campo preenchido
                    has_specs = any([spec_tipo_id, spec_material_id, spec_largura, spec_comprimento])
                    
                    if has_specs:
                        spec_cursor = conn.cursor()
                        # Verificar se já existe
                        spec_cursor.execute("SELECT id FROM produto_especificacoes_tecnicas WHERE produto_id = %s", (id,))
                        exists = spec_cursor.fetchone()
                        
                        if exists:
                            # UPDATE
                            spec_cursor.execute("""
                                UPDATE produto_especificacoes_tecnicas SET
                                    tipo_correia_id = %s, material_base_id = %s, perfil_id = %s,
                                    largura_mm = %s, comprimento_mm = %s, espessura_mm = %s,
                                    cor = %s, dureza_shore = %s, numero_lonas = %s,
                                    tipo_lona = %s, tipo_emenda = %s, acabamento_borda = %s,
                                    temperatura_min = %s, temperatura_max = %s,
                                    aplicacao = %s, ambiente = %s, observacoes_tecnicas = %s
                                WHERE produto_id = %s
                            """, (spec_tipo_id, spec_material_id, spec_perfil_id,
                                  spec_largura, spec_comprimento, spec_espessura,
                                  spec_cor, spec_dureza, spec_lonas,
                                  spec_tipo_lona, spec_emenda, spec_borda,
                                  spec_temp_min, spec_temp_max,
                                  spec_aplicacao, spec_ambiente, spec_obs, id))
                        else:
                            # INSERT
                            spec_cursor.execute("""
                                INSERT INTO produto_especificacoes_tecnicas (
                                    produto_id, tipo_correia_id, material_base_id, perfil_id,
                                    largura_mm, comprimento_mm, espessura_mm,
                                    cor, dureza_shore, numero_lonas,
                                    tipo_lona, tipo_emenda, acabamento_borda,
                                    temperatura_min, temperatura_max,
                                    aplicacao, ambiente, observacoes_tecnicas
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (id, spec_tipo_id, spec_material_id, spec_perfil_id,
                                  spec_largura, spec_comprimento, spec_espessura,
                                  spec_cor, spec_dureza, spec_lonas,
                                  spec_tipo_lona, spec_emenda, spec_borda,
                                  spec_temp_min, spec_temp_max,
                                  spec_aplicacao, spec_ambiente, spec_obs))
                            # Atualizar flag no produto
                            spec_cursor.execute("UPDATE products SET tipo_produto_industrial = 'correia', tem_especificacao_tecnica = 1 WHERE id = %s", (id,))
                        
                        conn.commit()
                        spec_cursor.close()
                except Exception as spec_error:
                    print(f"[PRODUTO] Aviso: Erro ao salvar especificações: {spec_error}")
                
                flash('Produto atualizado com sucesso!', 'success')
                cursor.close()
                conn.close()
                return redirect(url_for('produto.produtos'))
                
        except Exception as e:
            conn.rollback()
            print(f"ERRO AO ATUALIZAR PRODUTO: {str(e)}")
            flash(f'Erro ao atualizar produto: {str(e)}', 'danger')
        finally:
            if 'update_cursor' in locals() and update_cursor:
                update_cursor.close()
    
    # Fechar conexão
    cursor.close()
    conn.close()
    
    # Renderizar o formulário de edição
    return render_template('produto_form_abas.html', produto=produto, categorias=categorias,
                           marcas=marcas, grupos=grupos, subgrupos=subgrupos,
                           fornecedores=fornecedores, unit_measures=unit_measures,
                           modelos=modelos,
                           child_candidates=child_candidates,
                           ncm_description=ncm_description,
                           cfop_in_description=cfop_in_description,
                           cfop_out_description=cfop_out_description,
                           especificacao=especificacao,
                           tipos_correia=tipos_correia,
                           materiais_correia=materiais_correia,
                           perfis_correia=perfis_correia)

# Rota para visualizar um produto
@produto_bp.route('/produtos/visualizar/<id>')
@login_required
def produto_visualizar(id):
    # Buscar o produto pelo ID
    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM products WHERE id = %s", (id,))
    produto = cursor.fetchone()
    
    if not produto:
        cursor.close()
        conn.close()
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('produto.produtos'))
    
    # Buscar dados relacionados
    categoria = None
    marca = None
    modelo = None
    grupo = None
    subgrupo = None
    fornecedor = None
    especificacao = None
    tipo_correia = None
    material_correia = None
    ficha_tecnica = None
    ficha_tecnica_itens = []
    
    try:
        # Categoria
        if produto.get('category_id'):
            cursor.execute("SELECT * FROM product_categories WHERE id = %s", (produto['category_id'],))
            categoria = cursor.fetchone()
        
        # Marca
        if produto.get('brand_id'):
            cursor.execute("SELECT * FROM product_brands WHERE id = %s", (produto['brand_id'],))
            marca = cursor.fetchone()
        
        # Modelo
        if produto.get('model_id'):
            cursor.execute("SELECT * FROM product_models WHERE id = %s", (produto['model_id'],))
            modelo = cursor.fetchone()
        
        # Grupo
        if produto.get('group_id'):
            cursor.execute("SELECT * FROM product_groups WHERE id = %s", (produto['group_id'],))
            grupo = cursor.fetchone()
        
        # Subgrupo
        if produto.get('subgroup_id'):
            cursor.execute("SELECT * FROM product_subgroups WHERE id = %s", (produto['subgroup_id'],))
            subgrupo = cursor.fetchone()
        
        # Fornecedor
        if produto.get('main_supplier_id'):
            cursor.execute("SELECT * FROM suppliers WHERE id = %s", (produto['main_supplier_id'],))
            fornecedor = cursor.fetchone()
        
        # Especificações Técnicas
        try:
            cursor.execute("SELECT * FROM produto_especificacoes_tecnicas WHERE produto_id = %s", (id,))
            especificacao = cursor.fetchone()
            
            if especificacao:
                if especificacao.get('tipo_correia_id'):
                    cursor.execute("SELECT * FROM tipos_correia WHERE id = %s", (especificacao['tipo_correia_id'],))
                    tipo_correia = cursor.fetchone()
                if especificacao.get('material_base_id'):
                    cursor.execute("SELECT * FROM materiais_correia WHERE id = %s", (especificacao['material_base_id'],))
                    material_correia = cursor.fetchone()
        except Exception as e:
            print(f"[PRODUTO] Aviso: Tabelas de especificações não encontradas: {e}")
        
        # Ficha Técnica de Produção
        try:
            cursor.execute("SELECT * FROM produto_templates_producao WHERE produto_id = %s AND ativo = 1 ORDER BY id DESC LIMIT 1", (id,))
            ficha_tecnica = cursor.fetchone()
            
            if ficha_tecnica:
                cursor.execute("""
                    SELECT pti.*, p.name as produto_nome 
                    FROM produto_template_itens pti
                    LEFT JOIN products p ON pti.produto_id = p.id
                    WHERE pti.template_id = %s
                    ORDER BY pti.tipo_item, pti.id
                """, (ficha_tecnica['id'],))
                ficha_tecnica_itens = cursor.fetchall()
        except Exception as e:
            print(f"[PRODUTO] Aviso: Tabelas de ficha técnica não encontradas: {e}")
    
    except Exception as e:
        print(f"[PRODUTO] Erro ao buscar dados relacionados: {e}")
    
    cursor.close()
    conn.close()
    
    return render_template('produto_view_completo.html', 
                           produto=produto,
                           categoria=categoria,
                           marca=marca,
                           modelo=modelo,
                           grupo=grupo,
                           subgrupo=subgrupo,
                           fornecedor=fornecedor,
                           especificacao=especificacao,
                           tipo_correia=tipo_correia,
                           material_correia=material_correia,
                           ficha_tecnica=ficha_tecnica,
                           ficha_tecnica_itens=ficha_tecnica_itens)

# Rota para excluir um produto
@produto_bp.route('/produtos/excluir/<id>')
@produto_excluir_required
def produto_excluir(id):
    # Buscar o produto pelo ID
    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM products WHERE id = %s", (id,))
    produto = cursor.fetchone()
    
    if not produto:
        flash('Produto não encontrado.', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('produto.produtos'))
    
    # Excluir o produto (soft delete)
    update_cursor = conn.cursor()
    update_cursor.execute("UPDATE products SET active = FALSE WHERE id = %s", (id,))
    conn.commit()
    
    affected_rows = update_cursor.rowcount
    update_cursor.close()
    cursor.close()
    conn.close()
    
    if affected_rows > 0:
        flash('Produto excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir produto.', 'danger')
    
    return redirect(url_for('produto.produtos'))


@produto_bp.route('/produtos/pacotes')
@produto_visualizar_required
def produto_pacotes_lista():
    """Lista os pacotes comerciais cadastrados para os produtos.

    Permite filtrar por produto e por termo de busca (nome do produto ou descrição do pacote).
    """
    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)

    search_term = (request.args.get('search_term') or '').strip()
    produto_id = (request.args.get('produto_id') or '').strip()

    base_query = """
        SELECT
            pp.id,
            pp.produto_id,
            pp.descricao,
            pp.unidade_comercial,
            pp.unidades_por_pacote,
            pp.peso_pacote_kg,
            pp.preco_pacote,
            pp.preco_unidade,
            pp.ativo,
            pp.padrao_planejamento,
            p.name AS produto_nome,
            p.internal_code AS produto_codigo,
            p.unit_measure AS produto_unidade,
            COALESCE(
                NULLIF(p.cost_price, 0),
                NULLIF(p.purchase_total_cost, 0),
                NULLIF(p.last_purchase_price, 0)
            ) AS produto_custo_unitario
        FROM produto_pacotes pp
        INNER JOIN products p ON p.id = pp.produto_id
    """

    where_clauses = []
    params = []

    if produto_id and produto_id.isdigit():
        where_clauses.append("pp.produto_id = %s")
        params.append(int(produto_id))

    if search_term:
        like = f"%{search_term}%"
        where_clauses.append("(p.name LIKE %s OR pp.descricao LIKE %s)")
        params.extend([like, like])

    if where_clauses:
        base_query += " WHERE " + " AND ".join(where_clauses)

    base_query += " ORDER BY p.name, pp.descricao"

    cursor.execute(base_query, params)
    pacotes = cursor.fetchall() or []

    cursor.close()
    conn.close()

    return render_template(
        'produto_pacotes_lista.html',
        pacotes=pacotes,
        search_term=search_term,
        produto_id=produto_id,
    )


@produto_bp.route('/produtos/pacotes/<int:id>/editar', methods=['GET', 'POST'])
@produto_editar_required
def produto_pacotes_editar(id):
    """Edita um pacote comercial de produto (descricao, quantidade, preços, flags)."""
    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            pp.*,
            p.name AS produto_nome,
            p.internal_code AS produto_codigo,
            p.unit_measure AS produto_unidade,
            COALESCE(
                NULLIF(p.cost_price, 0),
                NULLIF(p.purchase_total_cost, 0),
                NULLIF(p.last_purchase_price, 0)
            ) AS produto_custo_unitario
        FROM produto_pacotes pp
        INNER JOIN products p ON p.id = pp.produto_id
        WHERE pp.id = %s
        """,
        (id,),
    )
    pacote = cursor.fetchone()

    if not pacote:
        cursor.close()
        conn.close()
        flash('Pacote de produto não encontrado.', 'danger')
        return redirect(url_for('produto.produto_pacotes_lista'))

    if request.method == 'POST':
        produto_id_raw = (request.form.get('produto_id') or '').strip()
        if not produto_id_raw or not produto_id_raw.isdigit():
            flash('Produto selecionado é inválido.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('produto.produto_pacotes_editar', id=id))

        novo_produto_id = int(produto_id_raw)

        # Opcional: validar se o produto existe e está ativo
        cursor.execute(
            "SELECT id FROM products WHERE id = %s AND active = TRUE",
            (novo_produto_id,),
        )
        if cursor.fetchone() is None:
            flash('Produto selecionado não foi encontrado ou está inativo.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('produto.produto_pacotes_editar', id=id))

        descricao = (request.form.get('descricao') or '').strip()
        unidade_comercial = (request.form.get('unidade_comercial') or '').strip()
        unidades_por_pacote = safe_decimal(
            request.form.get('unidades_por_pacote'),
            default=pacote.get('unidades_por_pacote') or 1.0,
        )
        peso_pacote_kg = safe_decimal(request.form.get('peso_pacote_kg'), default=None)
        preco_pacote = safe_decimal(request.form.get('preco_pacote'), default=None)
        preco_unidade = safe_decimal(request.form.get('preco_unidade'), default=None)
        ativo = 1 if request.form.get('ativo') in ('on', '1', 'true') else 0
        padrao_planejamento = 1 if request.form.get('padrao_planejamento') in ('on', '1', 'true') else 0

        if not descricao:
            flash('Descrição do pacote é obrigatória.', 'danger')
            cursor.close()
            conn.close()
            return render_template('produto_pacotes_form.html', pacote=pacote, is_new=False)

        update_cursor = conn.cursor()
        try:
            # Garantir apenas um pacote padrão por produto
            if padrao_planejamento:
                update_cursor.execute(
                    "UPDATE produto_pacotes SET padrao_planejamento = 0 WHERE produto_id = %s",
                    (novo_produto_id,),
                )

            update_cursor.execute(
                """
                UPDATE produto_pacotes
                SET produto_id = %s,
                    descricao = %s,
                    unidade_comercial = %s,
                    unidades_por_pacote = %s,
                    peso_pacote_kg = %s,
                    preco_pacote = %s,
                    preco_unidade = %s,
                    ativo = %s,
                    padrao_planejamento = %s
                WHERE id = %s
                """,
                (
                    novo_produto_id,
                    descricao,
                    unidade_comercial,
                    unidades_por_pacote,
                    peso_pacote_kg,
                    preco_pacote,
                    preco_unidade,
                    ativo,
                    padrao_planejamento,
                    id,
                ),
            )
            conn.commit()
            flash('Pacote de produto atualizado com sucesso!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Erro ao atualizar pacote de produto: {str(e)}', 'danger')
        finally:
            update_cursor.close()
            cursor.close()
            conn.close()

        return redirect(url_for('produto.produto_pacotes_lista'))

    cursor.close()
    conn.close()
    return render_template('produto_pacotes_form.html', pacote=pacote)


@produto_bp.route('/produtos/pacotes/novo', methods=['GET', 'POST'])
@produto_editar_required
def produto_pacotes_novo():
    """Cadastra um novo pacote comercial de produto.

    Usa o mesmo formulário de edição, mas em modo de criação. O custo unitário é
    sempre obtido do cadastro do produto (products.cost_price), e os custos/margens
    são calculados na visualização.
    """
    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        produto_id_raw = (request.form.get('produto_id') or '').strip()

        if not produto_id_raw or not produto_id_raw.isdigit():
            flash('ID do produto é obrigatório e deve ser numérico.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('produto.produto_pacotes_novo'))

        produto_id = int(produto_id_raw)

        cursor.execute(
            """
            SELECT 
                id, 
                name, 
                internal_code, 
                unit_measure,
                COALESCE(
                    NULLIF(cost_price, 0),
                    NULLIF(purchase_total_cost, 0),
                    NULLIF(last_purchase_price, 0)
                ) AS cost_price
            FROM products
            WHERE id = %s AND active = TRUE
            """,
            (produto_id,),
        )
        produto = cursor.fetchone()

        if not produto:
            flash('Produto informado não foi encontrado ou está inativo.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('produto.produto_pacotes_novo'))

        descricao = (request.form.get('descricao') or '').strip()
        unidade_comercial = (request.form.get('unidade_comercial') or '').strip()
        unidades_por_pacote = safe_decimal(
            request.form.get('unidades_por_pacote'),
            default=1.0,
        )
        peso_pacote_kg = safe_decimal(request.form.get('peso_pacote_kg'), default=None)
        preco_pacote = safe_decimal(request.form.get('preco_pacote'), default=None)
        preco_unidade = safe_decimal(request.form.get('preco_unidade'), default=None)
        ativo = 1 if request.form.get('ativo') in ('on', '1', 'true') else 0
        padrao_planejamento = 1 if request.form.get('padrao_planejamento') in ('on', '1', 'true') else 0

        if not descricao:
            flash('Descrição do pacote é obrigatória.', 'danger')
            pacote = {
                'id': None,
                'produto_id': produto['id'],
                'produto_nome': produto['name'],
                'produto_codigo': produto.get('internal_code'),
                'produto_unidade': produto.get('unit_measure'),
                'descricao': descricao,
                'unidade_comercial': unidade_comercial,
                'unidades_por_pacote': unidades_por_pacote,
                'peso_pacote_kg': peso_pacote_kg,
                'preco_pacote': preco_pacote,
                'preco_unidade': preco_unidade,
                'ativo': ativo,
                'padrao_planejamento': padrao_planejamento,
                'produto_custo_unitario': produto.get('cost_price'),
            }
            cursor.close()
            conn.close()
            return render_template('produto_pacotes_form.html', pacote=pacote, is_new=True)

        insert_cursor = conn.cursor()
        try:
            # Garantir apenas um pacote padrão por produto
            if padrao_planejamento:
                insert_cursor.execute(
                    "UPDATE produto_pacotes SET padrao_planejamento = 0 WHERE produto_id = %s",
                    (produto_id,),
                )

            insert_cursor.execute(
                """
                INSERT INTO produto_pacotes (
                    produto_id,
                    descricao,
                    unidade_comercial,
                    unidades_por_pacote,
                    peso_pacote_kg,
                    preco_pacote,
                    preco_unidade,
                    ativo,
                    padrao_planejamento
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    produto_id,
                    descricao,
                    unidade_comercial,
                    unidades_por_pacote,
                    peso_pacote_kg,
                    preco_pacote,
                    preco_unidade,
                    ativo,
                    padrao_planejamento,
                ),
            )
            conn.commit()
            flash('Pacote de produto cadastrado com sucesso!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Erro ao cadastrar pacote de produto: {str(e)}', 'danger')
        finally:
            insert_cursor.close()
            cursor.close()
            conn.close()

        return redirect(url_for('produto.produto_pacotes_lista', produto_id=produto_id))

    # GET
    produto = None
    produto_id_param = (request.args.get('produto_id') or '').strip()
    if produto_id_param and produto_id_param.isdigit():
        cursor.execute(
            """
            SELECT 
                id, 
                name, 
                internal_code, 
                unit_measure,
                COALESCE(
                    NULLIF(cost_price, 0),
                    NULLIF(purchase_total_cost, 0),
                    NULLIF(last_purchase_price, 0)
                ) AS cost_price
            FROM products
            WHERE id = %s AND active = TRUE
            """,
            (int(produto_id_param),),
        )
        produto = cursor.fetchone()

    # Valores padrão ou vindos da querystring (usado ao duplicar pacote)
    descricao_qs = (request.args.get('descricao') or '').strip()
    unidade_com_qs = (request.args.get('unidade_comercial') or '').strip()
    unidades_qs = safe_decimal(request.args.get('unidades_por_pacote'), default=1.0)
    peso_qs = safe_decimal(request.args.get('peso_pacote_kg'), default=None)
    preco_pacote_qs = safe_decimal(request.args.get('preco_pacote'), default=None)
    preco_unidade_qs = safe_decimal(request.args.get('preco_unidade'), default=None)

    cursor.close()
    conn.close()

    pacote = {
        'id': None,
        'produto_id': produto.get('id') if produto else None,
        'produto_nome': produto.get('name') if produto else '',
        'produto_codigo': produto.get('internal_code') if produto else '',
        'produto_unidade': produto.get('unit_measure') if produto else '',
        'descricao': descricao_qs or '',
        'unidade_comercial': unidade_com_qs or '',
        'unidades_por_pacote': unidades_qs,
        'peso_pacote_kg': peso_qs,
        'preco_pacote': preco_pacote_qs,
        'preco_unidade': preco_unidade_qs,
        'ativo': 1,
        'padrao_planejamento': 0,
        'produto_custo_unitario': produto.get('cost_price') if produto else None,
    }

    return render_template('produto_pacotes_form.html', pacote=pacote, is_new=True)

# Rota para buscar subgrupos de um grupo via AJAX
@produto_bp.route('/api/subgroups-by-group/<group_id>')
@login_required
def subgroups_by_group(group_id):
    from flask import jsonify
    
    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM product_subgroups WHERE group_id = %s AND active = TRUE ORDER BY name", (group_id,))
    subgrupos = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'subgroups': subgrupos})

# =============================
# Gestão de Filhos (Insumos) do Produto Pai
# =============================

@produto_bp.route('/produtos/<int:parent_id>/filhos', methods=['GET'])
@login_required
def produto_filhos_list(parent_id):
    """Lista os filhos (insumos) de um produto pai."""
    from flask import jsonify
    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verifica se o produto existe e é pai
        cursor.execute("SELECT id, name, product_type FROM products WHERE id = %s AND active = TRUE", (parent_id,))
        parent = cursor.fetchone()
        if not parent:
            return jsonify({'error': 'Produto não encontrado'}), 404
        if parent.get('product_type') != 'parent':
            return jsonify({'error': 'Produto não é do tipo pai'}), 400

        cursor.execute(
            """
            SELECT pc.id, pc.child_product_id, pc.quantity,
                   pc.interval_value, pc.interval_unit, pc.interval_days, pc.notes,
                   p.name AS child_name, p.unit_measure, p.barcode
            FROM product_children pc
            JOIN products p ON p.id = pc.child_product_id
            WHERE pc.parent_product_id = %s
            ORDER BY p.name
            """,
            (parent_id,)
        )
        rows = cursor.fetchall()
        return jsonify({'parent': parent, 'children': rows})
    finally:
        cursor.close()
        conn.close()


@produto_bp.route('/insumos', methods=['GET'])
@login_required
def insumos_page():
    """Página dedicada para gerenciar vínculos Pai ↔ Filho (insumos)."""
    from flask import request
    parent_id = request.args.get('parent_id')

    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name FROM products WHERE active = TRUE AND product_type = 'parent' ORDER BY name")
        parent_candidates = cursor.fetchall()
        cursor.execute("SELECT id, name, unit_measure FROM products WHERE active = TRUE AND product_type = 'child' ORDER BY name")
        child_candidates = cursor.fetchall()
        selected_parent = None
        if parent_id:
            cursor.execute("SELECT id, name FROM products WHERE id = %s AND active = TRUE AND product_type = 'parent'", (parent_id,))
            selected_parent = cursor.fetchone()
        # Contagem de filhos por pai
        cursor.execute(
            "SELECT parent_product_id, COUNT(*) AS cnt FROM product_children GROUP BY parent_product_id"
        )
        counts = cursor.fetchall()
        counts_map = {row['parent_product_id']: row['cnt'] for row in counts}
    finally:
        cursor.close()
        conn.close()

    return render_template('insumos.html', parents=parent_candidates, child_candidates=child_candidates, selected_parent=selected_parent, counts=counts_map)

@produto_bp.route('/produtos/<int:parent_id>/filhos', methods=['POST'])
@login_required
def produto_filhos_add(parent_id):
    """Adiciona um filho (insumo) a um produto pai."""
    from flask import jsonify
    data = request.get_json(silent=True) or request.form
    child_product_id = data.get('child_product_id')
    quantity = data.get('quantity', 1)
    interval_value = data.get('interval_value') or data.get('interval_days')
    interval_unit = (data.get('interval_unit') or 'days').lower()
    notes = data.get('notes', '')

    # Validações básicas
    try:
        child_product_id = int(child_product_id)
        quantity = float(quantity) if quantity != '' else 1.0
        interval_value = int(interval_value) if (interval_value not in (None, '')) else None
        if interval_unit not in ('hours','days','months','years'):
            interval_unit = 'days'
    except (ValueError, TypeError):
        return jsonify({'error': 'Parâmetros inválidos'}), 400

    if child_product_id == parent_id:
        return jsonify({'error': 'Produto filho não pode ser o mesmo que o pai'}), 400

    conn = get_direct_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # Verificar tipos de produto
        cursor.execute("SELECT id, product_type FROM products WHERE id = %s AND active = TRUE", (parent_id,))
        parent = cursor.fetchone()
        if not parent:
            return jsonify({'error': 'Produto pai não encontrado'}), 404
        if parent['product_type'] != 'parent':
            return jsonify({'error': 'Produto não é do tipo pai'}), 400

        cursor.execute("SELECT id, product_type FROM products WHERE id = %s AND active = TRUE", (child_product_id,))
        child = cursor.fetchone()
        if not child:
            return jsonify({'error': 'Produto filho não encontrado'}), 404
        if child['product_type'] == 'parent':
            # Permitimos tecnicamente, mas muitas empresas proíbem pai como filho.
            # Aqui vamos bloquear para simplicidade.
            return jsonify({'error': 'Produto filho não pode ser do tipo pai'}), 400

        # Inserir relação (evitar duplicidade pela UNIQUE)
        insert_cur = conn.cursor()
        insert_cur.execute(
            """
            INSERT INTO product_children (parent_product_id, child_product_id, quantity, interval_value, interval_unit, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (parent_id, child_product_id, quantity, interval_value, interval_unit, notes)
        )
        conn.commit()
        new_id = insert_cur.lastrowid
        insert_cur.close()
        return jsonify({'ok': True, 'id': new_id}), 201
    except mysql.connector.IntegrityError as e:
        conn.rollback()
        return jsonify({'error': 'Relação já existente ou violação de integridade', 'detail': str(e)}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@produto_bp.route('/produtos/<int:parent_id>/filhos/<int:child_id>', methods=['DELETE'])
@login_required
def produto_filhos_delete(parent_id, child_id):
    """Remove um vínculo de filho de um produto pai."""
    from flask import jsonify
    conn = get_direct_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM product_children WHERE parent_product_id = %s AND child_product_id = %s",
            (parent_id, child_id)
        )
        conn.commit()
        if cursor.rowcount > 0:
            return jsonify({'ok': True})
        return jsonify({'error': 'Vínculo não encontrado'}), 404
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
