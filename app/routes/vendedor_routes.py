"""
Rotas para gerenciamento de vendedores.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import re

from database import get_db
from utils.auth import login_required

# Criar o blueprint
vendedor_bp = Blueprint('vendedor', __name__)


@vendedor_bp.route('/vendedores')
@login_required
def vendedores():
    """Lista todos os vendedores."""
    db = get_db()
    
    # Buscar todos os vendedores ativos
    vendedores = db.fetch_all("""
        SELECT * FROM sellers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'vendedor_list.html',
        vendedores=vendedores,
        active_page='vendedores'
    )

def _cpf_digits_only(cpf: str) -> str:
    return re.sub(r'[^0-9]', '', cpf or '')


def _is_valid_cpf(cpf: str) -> bool:
    """Valida CPF com base nos dígitos verificadores.
    Regras:
    - 11 dígitos numéricos
    - Não pode ser sequência repetida (ex.: 000... 111...)
    - Dígitos verificadores conforme algoritmo oficial
    """
    cpf = _cpf_digits_only(cpf)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False

    # Calcula primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10) % 11
    d1 = 0 if d1 == 10 else d1

    # Calcula segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10) % 11
    d2 = 0 if d2 == 10 else d2

    return int(cpf[9]) == d1 and int(cpf[10]) == d2


def _format_cpf(cpf_digits: str) -> str:
    """Formata CPF (11 dígitos) como 000.000.000-00."""
    d = _cpf_digits_only(cpf_digits)
    if len(d) != 11:
        return cpf_digits or ''
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


# Garante índice único em sellers.cpf na primeira execução
_unique_cpf_checked = False

def _ensure_unique_cpf_index():
    global _unique_cpf_checked
    if _unique_cpf_checked:
        return
    try:
        db = get_db()
        exists = db.fetch_one(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'sellers'
              AND index_name = 'idx_sellers_cpf'
            """
        )
        if not exists or int(exists.get('cnt', 0)) == 0:
            print("[DB] Criando índice único idx_sellers_cpf em sellers(cpf)...")
            db.execute("ALTER TABLE sellers ADD UNIQUE INDEX idx_sellers_cpf (cpf)")
        _unique_cpf_checked = True
    except Exception as e:
        # Não falhar a requisição por causa do índice; validaremos no app de qualquer forma
        print(f"[DB] Aviso: não foi possível garantir índice único do CPF: {e}")


@vendedor_bp.route('/vendedores/cadastrar', methods=['GET', 'POST'])
@login_required
def vendedor_cadastrar():
    """Cadastra um novo vendedor."""
    if request.method == 'POST':
        _ensure_unique_cpf_index()
        # Obter dados do formulário
        name = request.form.get('name')
        cpf = request.form.get('cpf')
        region = request.form.get('region')
        phone = request.form.get('phone')
        email = request.form.get('email')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome é obrigatório.')
        
        if not cpf:
            errors.append('CPF é obrigatório.')
        else:
            cpf_clean = _cpf_digits_only(cpf)
            if not _is_valid_cpf(cpf_clean):
                errors.append('CPF inválido.')
        
        if not region:
            errors.append('Região de atuação é obrigatória.')
        
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errors.append('E-mail inválido.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template(
                'vendedor_form.html',
                vendedor=request.form,
                active_page='vendedores'
            )
        
        # Inserir vendedor no banco de dados
        db = get_db()
        
        # Verificar se o CPF já está cadastrado (comparando por dígitos para cobrir registros antigos)
        existing_vendedor = db.fetch_one(
            """
            SELECT id, name, cpf, phone, email FROM sellers
            WHERE REPLACE(REPLACE(REPLACE(cpf, '.', ''), '-', ''), ' ', '') = %s AND active = TRUE
            """,
            (cpf_clean,)
        )
        
        if existing_vendedor:
            # Montar modal semelhante ao de clientes
            form_data = {key: request.form.get(key, '') for key in request.form}
            return render_template(
                'vendedor_form.html',
                vendedor=None,
                show_duplicate_modal=True,
                entidade=existing_vendedor,
                editar_url='vendedor.vendedor_editar',
                visualizar_url='vendedor.vendedor_view',
                form_data=form_data,
                active_page='vendedores'
            )
        
        # Inserir vendedor
        try:
            vendedor_id = db.insert(
                """
                INSERT INTO sellers (name, cpf, region, phone, email)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (name, _format_cpf(cpf_clean), region, phone, email),
            )
        except Exception as e:
            msg = str(e)
            if 'Duplicate' in msg or 'duplicat' in msg.lower():
                # Buscar entidade para exibir no modal
                entidade = db.fetch_one(
                    "SELECT id, name, cpf, phone, email FROM sellers WHERE REPLACE(REPLACE(REPLACE(cpf, '.', ''), '-', ''), ' ', '') = %s AND active = TRUE",
                    (cpf_clean,)
                )
                form_data = {key: request.form.get(key, '') for key in request.form}
                return render_template(
                    'vendedor_form.html',
                    vendedor=None,
                    show_duplicate_modal=True,
                    entidade=entidade,
                    editar_url='vendedor.vendedor_editar',
                    visualizar_url='vendedor.vendedor_view',
                    form_data=form_data,
                    active_page='vendedores'
                )
            raise
        
        if vendedor_id:
            flash('Vendedor cadastrado com sucesso!', 'success')
            
            # Processar clientes vinculados
            clientes_ids = request.form.getlist('clientes')
            if clientes_ids:
                for cliente_id in clientes_ids:
                    db.insert("""
                        INSERT INTO seller_customer (seller_id, customer_id)
                        VALUES (%s, %s)
                    """, (vendedor_id, cliente_id))
            
            return redirect(url_for('vendedor.vendedor_view', vendedor_id=vendedor_id))
        else:
            flash('Erro ao cadastrar vendedor.', 'danger')
    
    # Buscar clientes para o formulário
    db = get_db()
    clientes = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    return render_template(
        'vendedor_form.html',
        vendedor=None,
        clientes=clientes,
        active_page='vendedores'
    )

@vendedor_bp.route('/vendedores/editar/<int:vendedor_id>', methods=['GET', 'POST'])
@login_required
def vendedor_editar(vendedor_id):
    """Edita um vendedor existente."""
    _ensure_unique_cpf_index()
    db = get_db()
    
    # Buscar o vendedor
    vendedor = db.fetch_one("""
        SELECT * FROM sellers
        WHERE id = %s AND active = TRUE
    """, (vendedor_id,))
    
    if not vendedor:
        flash('Vendedor não encontrado.', 'danger')
        return redirect(url_for('vendedor.vendedores'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        cpf = request.form.get('cpf')
        region = request.form.get('region')
        phone = request.form.get('phone')
        email = request.form.get('email')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome é obrigatório.')
        
        if not cpf:
            errors.append('CPF é obrigatório.')
        else:
            # Remover caracteres não numéricos
            cpf_clean = re.sub(r'[^0-9]', '', cpf)
            if len(cpf_clean) != 11:
                errors.append('CPF deve ter 11 dígitos.')
        
        if not region:
            errors.append('Região de atuação é obrigatória.')
        
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errors.append('E-mail inválido.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template(
                'vendedor_form.html',
                vendedor=request.form,
                vendedor_id=vendedor_id,
                active_page='vendedores'
            )
        
        # Verificar se o CPF já está cadastrado para outro vendedor
        existing_vendedor = db.fetch_one(
            """
            SELECT id FROM sellers
            WHERE REPLACE(REPLACE(REPLACE(cpf, '.', ''), '-', ''), ' ', '') = %s AND id != %s AND active = TRUE
            """,
            (cpf_clean, vendedor_id),
        )
        
        if existing_vendedor:
            # Mostrar modal apontando para o cadastro que conflita
            entidade = db.fetch_one("SELECT id, name, cpf, phone, email FROM sellers WHERE id = %s", (existing_vendedor['id'],))
            form_data = {key: request.form.get(key, '') for key in request.form}
            return render_template(
                'vendedor_form.html',
                vendedor=request.form,
                vendedor_id=vendedor_id,
                show_duplicate_modal=True,
                entidade=entidade,
                editar_url='vendedor.vendedor_editar',
                visualizar_url='vendedor.vendedor_view',
                form_data=form_data,
                active_page='vendedores'
            )
        
        # Atualizar vendedor
        try:
            affected_rows = db.update(
                """
                UPDATE sellers
                SET name = %s, cpf = %s, region = %s, phone = %s, email = %s
                WHERE id = %s
                """,
                (name, _format_cpf(cpf_clean), region, phone, email, vendedor_id),
            )
        except Exception as e:
            msg = str(e)
            if 'Duplicate' in msg or 'duplicat' in msg.lower():
                entidade = db.fetch_one(
                    "SELECT id, name, cpf, phone, email FROM sellers WHERE REPLACE(REPLACE(REPLACE(cpf, '.', ''), '-', ''), ' ', '') = %s AND id != %s AND active = TRUE",
                    (cpf_clean, vendedor_id)
                )
                form_data = {key: request.form.get(key, '') for key in request.form}
                return render_template(
                    'vendedor_form.html',
                    vendedor=request.form,
                    vendedor_id=vendedor_id,
                    show_duplicate_modal=True,
                    entidade=entidade,
                    editar_url='vendedor.vendedor_editar',
                    visualizar_url='vendedor.vendedor_view',
                    form_data=form_data,
                    active_page='vendedores'
                )
            raise
        
        # Mesmo que nenhum campo "cabeçalho" mude (affected_rows == 0), ainda assim devemos atualizar vínculos
        flash('Vendedor atualizado com sucesso!', 'success')

        # Atualizar clientes vinculados
        # Primeiro, remover todos os vínculos existentes
        db.execute("""
            DELETE FROM seller_customer
            WHERE seller_id = %s
        """, (vendedor_id,))
        
        # Depois, adicionar os novos vínculos (se houver)
        clientes_ids = request.form.getlist('clientes')
        if clientes_ids:
            for cliente_id in clientes_ids:
                db.insert("""
                    INSERT INTO seller_customer (seller_id, customer_id)
                    VALUES (%s, %s)
                """, (vendedor_id, cliente_id))
        
        return redirect(url_for('vendedor.vendedor_view', vendedor_id=vendedor_id))
    
    # Buscar clientes para o formulário
    clientes = db.fetch_all("""
        SELECT id, name FROM customers
        WHERE active = TRUE
        ORDER BY name
    """)
    
    # Buscar clientes vinculados ao vendedor
    clientes_vinculados = db.fetch_all("""
        SELECT customer_id FROM seller_customer
        WHERE seller_id = %s
    """, (vendedor_id,))
    
    clientes_ids = [cliente['customer_id'] for cliente in clientes_vinculados]
    
    return render_template(
        'vendedor_form.html',
        vendedor=vendedor,
        vendedor_id=vendedor_id,
        clientes=clientes,
        clientes_ids=clientes_ids,
        active_page='vendedores'
    )

@vendedor_bp.route('/vendedores/visualizar/<int:vendedor_id>')
@login_required
def vendedor_view(vendedor_id):
    """Visualiza detalhes de um vendedor."""
    db = get_db()
    
    # Buscar o vendedor
    vendedor = db.fetch_one("""
        SELECT * FROM sellers
        WHERE id = %s AND active = TRUE
    """, (vendedor_id,))
    
    if not vendedor:
        flash('Vendedor não encontrado.', 'danger')
        return redirect(url_for('vendedor.vendedores'))
    
    # Buscar clientes vinculados ao vendedor
    clientes = db.fetch_all("""
        SELECT c.* FROM customers c
        JOIN seller_customer sc ON c.id = sc.customer_id
        WHERE sc.seller_id = %s AND c.active = TRUE
        ORDER BY c.name
    """, (vendedor_id,))
    
    # Buscar rotas do vendedor
    rotas = db.fetch_all("""
        SELECT * FROM sales_routes
        WHERE seller_id = %s AND active = TRUE
        ORDER BY name
    """, (vendedor_id,))
    
    # Buscar romaneios do vendedor
    romaneios = db.fetch_all("""
        SELECT * FROM sales_manifests
        WHERE seller_id = %s AND active = TRUE
        ORDER BY date DESC
        LIMIT 10
    """, (vendedor_id,))
    
    return render_template(
        'vendedor_view.html',
        vendedor=vendedor,
        clientes=clientes,
        rotas=rotas,
        romaneios=romaneios,
        active_page='vendedores'
    )

@vendedor_bp.route('/vendedores/excluir/<int:vendedor_id>', methods=['POST'])
@login_required
def vendedor_excluir(vendedor_id):
    """Exclui um vendedor (exclusão lógica)."""
    db = get_db()
    
    # Verificar se o vendedor existe
    vendedor = db.fetch_one("""
        SELECT * FROM sellers
        WHERE id = %s AND active = TRUE
    """, (vendedor_id,))
    
    if not vendedor:
        flash('Vendedor não encontrado.', 'danger')
        return redirect(url_for('vendedor.vendedores'))
    
    # Verificar se o vendedor possui rotas ativas
    rotas = db.fetch_one("""
        SELECT COUNT(*) as count FROM sales_routes
        WHERE seller_id = %s AND active = TRUE
    """, (vendedor_id,))
    
    if rotas and rotas['count'] > 0:
        flash('Não é possível excluir o vendedor pois ele possui rotas ativas.', 'danger')
        return redirect(url_for('vendedor.vendedor_view', vendedor_id=vendedor_id))
    
    # Verificar se o vendedor possui romaneios ativos
    romaneios = db.fetch_one("""
        SELECT COUNT(*) as count FROM sales_manifests
        WHERE seller_id = %s AND active = TRUE AND status != 'completed' AND status != 'canceled'
    """, (vendedor_id,))
    
    if romaneios and romaneios['count'] > 0:
        flash('Não é possível excluir o vendedor pois ele possui romaneios ativos.', 'danger')
        return redirect(url_for('vendedor.vendedor_view', vendedor_id=vendedor_id))
    
    # Excluir vendedor (exclusão lógica)
    affected_rows = db.update("""
        UPDATE sellers
        SET active = FALSE, status = 'inactive'
        WHERE id = %s
    """, (vendedor_id,))
    
    if affected_rows > 0:
        flash('Vendedor excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir vendedor.', 'danger')
    
    return redirect(url_for('vendedor.vendedores'))
