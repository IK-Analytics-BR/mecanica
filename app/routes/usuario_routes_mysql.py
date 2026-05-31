from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os
import secrets

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db

# Importar utilitários de senha
from utils.password_utils import hash_password, verify_password, validate_password_strength, is_password_hashed
from utils.permissoes_helper import tem_permissao

# Criar um Blueprint para as rotas de usuário
usuario_bp = Blueprint('usuario', __name__)

# Decorators para verificar permissões granulares
def usuario_visualizar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('admin.usuarios', 'visualizar'):
            flash('Você não tem permissão para visualizar usuários.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function

def usuario_criar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('admin.usuarios', 'criar'):
            flash('Você não tem permissão para cadastrar usuários.', 'danger')
            return redirect(url_for('usuario.usuarios'))
        return f(*args, **kwargs)
    return decorated_function

def usuario_editar_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('admin.usuarios', 'editar'):
            flash('Você não tem permissão para editar usuários.', 'danger')
            return redirect(url_for('usuario.usuarios'))
        return f(*args, **kwargs)
    return decorated_function

def usuario_excluir_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if not tem_permissao('admin.usuarios', 'excluir'):
            flash('Você não tem permissão para excluir usuários.', 'danger')
            return redirect(url_for('usuario.usuarios'))
        return f(*args, **kwargs)
    return decorated_function

# Alias para compatibilidade
admin_required = usuario_visualizar_required

# Rota para listar todos os usuários
@usuario_bp.route('/usuarios')
@admin_required
def usuarios():
    # Buscar usuários no banco de dados
    db = get_db()
    usuarios = db.fetch_all(
        """
        SELECT u.*,
               GROUP_CONCAT(COALESCE(e.nome_fantasia, e.razao_social) ORDER BY COALESCE(e.nome_fantasia, e.razao_social) SEPARATOR ', ') AS empresas
        FROM users u
        LEFT JOIN user_empresas ue ON ue.user_id = u.id
        LEFT JOIN empresas e ON e.id = ue.empresa_id AND e.ativo = TRUE
        GROUP BY u.id
        ORDER BY u.name
        """
    )
    return render_template('usuario_list.html', usuarios=usuarios)

# Utilitários de CPF
import re

def _cpf_digits_only(cpf: str) -> str:
    return re.sub(r'[^0-9]', '', cpf or '')

def _is_valid_cpf(cpf: str) -> bool:
    cpf = _cpf_digits_only(cpf)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10) % 11
    d1 = 0 if d1 == 10 else d1
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10) % 11
    d2 = 0 if d2 == 10 else d2
    return int(cpf[9]) == d1 and int(cpf[10]) == d2

def _format_cpf(cpf_digits: str) -> str:
    d = _cpf_digits_only(cpf_digits)
    if len(d) != 11:
        return cpf_digits or ''
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"

# Utilitários genéricos
def _digits_only(s: str) -> str:
    return re.sub(r'[^0-9]', '', s or '')

def _format_phone(phone: str) -> str | None:
    """Formata telefone brasileiro com DDD.
    - 11 dígitos: (XX) XXXXX-XXXX
    - 10 dígitos: (XX) XXXX-XXXX
    Caso não tenha 10/11 dígitos, retorna original ou None se vazio.
    """
    d = _digits_only(phone)
    if not d:
        return None
    if len(d) == 11:
        return f"({d[0:2]}) {d[2:7]}-{d[7:11]}"
    if len(d) == 10:
        return f"({d[0:2]}) {d[2:6]}-{d[6:10]}"
    return phone or None

def _format_cep(cep: str) -> str | None:
    """Formata CEP (8 dígitos) como 00000-000. Caso diferente de 8 dígitos, retorna original/None."""
    d = _digits_only(cep)
    if not d:
        return None
    if len(d) == 8:
        return f"{d[0:5]}-{d[5:8]}"
    return cep or None


def _get_empresas_ativas(db):
    return db.fetch_all(
        """
        SELECT id, COALESCE(nome_fantasia, razao_social) AS nome
        FROM empresas
        WHERE ativo = TRUE
        ORDER BY COALESCE(nome_fantasia, razao_social)
        """
    )


def _get_user_empresa_ids(db, user_id: int) -> list[int]:
    rows = db.fetch_all(
        """
        SELECT empresa_id
        FROM user_empresas
        WHERE user_id = %s
        """,
        (user_id,)
    )
    ids: list[int] = []
    for r in rows or []:
        try:
            ids.append(int(r['empresa_id']))
        except Exception:
            continue
    return ids


def _parse_empresa_ids_from_form(form) -> list[int]:
    raw = form.getlist('empresa_ids[]')
    ids: list[int] = []
    for v in raw or []:
        try:
            if str(v).isdigit():
                ids.append(int(v))
        except Exception:
            continue
    # remover duplicados preservando ordem
    out: list[int] = []
    seen = set()
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _save_user_empresas(db, user_id: int, empresa_ids: list[int]):
    db.execute("DELETE FROM user_empresas WHERE user_id = %s", (user_id,))
    for eid in empresa_ids:
        db.execute(
            "INSERT IGNORE INTO user_empresas (user_id, empresa_id) VALUES (%s, %s)",
            (user_id, eid),
        )

# Checar se o ENUM de role suporta 'manager'
def _role_enum_supports_manager(db) -> bool:
    try:
        row = db.fetch_one(
            """
            SELECT COLUMN_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'role'
            """
        )
        if not row or 'COLUMN_TYPE' not in row:
            # Alguns conectores retornam lowercase
            coltype = (row.get('column_type') if row else '') or ''
        else:
            coltype = row['COLUMN_TYPE'] or ''
        return 'manager' in coltype
    except Exception:
        return False

# Rota para cadastrar um novo usuário
@usuario_bp.route('/usuarios/cadastrar', methods=['GET', 'POST'])
@usuario_criar_required
def usuario_cadastrar():
    if request.method == 'POST':
        print("\n[DEBUG] Processando formulário de cadastro de usuário")
        print(f"[DEBUG] Dados do formulário: {request.form}")
        
        # Obter dados do formulário de forma resiliente
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        email = request.form.get('email', '').strip()
        role = request.form.get('role', '').strip()
        status = request.form.get('status', '').strip() or 'active'

        db = get_db()
        empresas_ativas = _get_empresas_ativas(db)
        empresa_ids = _parse_empresa_ids_from_form(request.form)
        
        # Novos campos
        cpf = request.form.get('cpf', '').strip()
        phone = request.form.get('phone', '').strip()
        commission = request.form.get('commission', '').strip()
        employment_type = request.form.get('employment_type', '').strip()
        cep = request.form.get('cep', '').strip()
        address = request.form.get('address', '').strip()
        number = request.form.get('number', '').strip()
        complement = request.form.get('complement', '').strip()
        neighborhood = request.form.get('neighborhood', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        reference = request.form.get('reference', '').strip()
        notes = request.form.get('notes', '').strip()
        is_seller = 1 if request.form.get('is_seller') in ('1', 'on', 'true', 'True') else 0
        eh_operador = 1 if request.form.get('eh_operador') in ('1', 'on', 'true', 'True') else 0
        eh_lider_equipe = 1 if request.form.get('eh_lider_equipe') in ('1', 'on', 'true', 'True') else 0

        missing = []
        for field, value in [('name', name), ('username', username), ('email', email), ('role', role)]:
            if not value:
                missing.append(field)
        if not password:
            missing.append('password')
        if not confirm_password:
            missing.append('confirm_password')
        if missing:
            print(f"[ERROR] Campos obrigatórios ausentes: {missing}")
            return render_template(
                'usuario_form.html',
                usuario=request.form,
                form_action=url_for('usuario.usuario_cadastrar'),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason=f"Preencha todos os campos obrigatórios: {', '.join(missing)}."
            )
        
        print(f"[DEBUG] Dados extraídos com sucesso: name={name}, username={username}, email={email}, role={role}, status={status}")
        # Validar role permitido e suporte do ENUM
        allowed_roles = {'admin','manager','user','mecanico','atendente','auxiliar'}
        if role not in allowed_roles:
            return render_template(
                'usuario_form.html',
                usuario=request.form,
                form_action=url_for('usuario.usuario_cadastrar'),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason='Função inválida. Valores permitidos: Administrador, Gerente, Usuário, Mecânico, Atendente, Auxiliar.'
            )

        # Usuário não-admin deve ter ao menos 1 empresa
        if role != 'admin' and not empresa_ids:
            return render_template(
                'usuario_form.html',
                usuario=request.form,
                form_action=url_for('usuario.usuario_cadastrar'),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason='Selecione pelo menos 1 empresa para este usuário.'
            )
        if role == 'manager' and not _role_enum_supports_manager(db):
            return render_template(
                'usuario_form.html',
                usuario=request.form,
                form_action=url_for('usuario.usuario_cadastrar'),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason=(
                    "A coluna role não aceita 'manager'. Execute: "
                    "ALTER TABLE users MODIFY role ENUM('admin','manager','user') NOT NULL DEFAULT 'user';"
                )
            )
        
        # Verificar se o nome de usuário já existe
        existing_user = db.fetch_one("SELECT * FROM users WHERE username = %s", (username,))
        if existing_user:
            return render_template(
                'usuario_form.html',
                usuario=request.form,
                form_action=url_for('usuario.usuario_cadastrar'),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason='Nome de usuário já existe. Por favor, escolha outro.'
            )
        
        # Validar CPF (se informado) e verificar duplicidade por dígitos
        cpf_clean = _cpf_digits_only(cpf)
        if cpf_clean:
            if not _is_valid_cpf(cpf_clean):
                return render_template(
                    'usuario_form.html',
                    usuario=request.form,
                    form_action=url_for('usuario.usuario_cadastrar'),
                    empresas=empresas_ativas,
                    selected_empresas=empresa_ids,
                    show_duplicate_modal=True,
                    entidade={'name': name, 'cpf': cpf, 'email': email, 'status': status},
                    error_reason='CPF inválido.',
                    editar_url='usuario.usuario_editar',
                    visualizar_url='usuario.usuario_visualizar'
                )
            try:
                dup = db.fetch_one(
                    """
                    SELECT id, name, cpf, email, status FROM users
                    WHERE REPLACE(REPLACE(REPLACE(IFNULL(cpf,''), '.', ''), '-', ''), ' ', '') = %s
                    """,
                    (cpf_clean,)
                )
                if dup:
                    return render_template(
                        'usuario_form.html',
                        usuario=None,
                        form_action=url_for('usuario.usuario_cadastrar'),
                        empresas=empresas_ativas,
                        selected_empresas=empresa_ids,
                        show_duplicate_modal=True,
                        entidade=dup,
                        error_reason='Já existe um usuário com este CPF.',
                        editar_url='usuario.usuario_editar',
                        visualizar_url='usuario.usuario_visualizar'
                    )
            except Exception as e:
                msg = str(e).lower()
                if 'unknown column' in msg and "cpf'" in msg:
                    return render_template(
                        'usuario_form.html',
                        usuario=request.form,
                        form_action=url_for('usuario.usuario_cadastrar'),
                        show_error_modal=True,
                        error_reason='A coluna CPF não existe na tabela users. Execute as migrações: add_is_seller_to_users.py e extend_users_table.py.'
                    )
        
        # Verificar se as senhas conferem
        if password != confirm_password:
            return render_template(
                'usuario_form.html',
                usuario=request.form,
                form_action=url_for('usuario.usuario_cadastrar'),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason='As senhas não conferem.'
            )
        
        # Validar a força da senha
        is_valid, message = validate_password_strength(password)
        if not is_valid:
            return render_template(
                'usuario_form.html',
                usuario=request.form,
                form_action=url_for('usuario.usuario_cadastrar'),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason=message
            )
        
        # Hash da senha
        hashed_password = hash_password(password)
        
        # Converter comissão para float (aceita vírgula ou ponto)
        commission_value = None
        if commission:
            try:
                commission_value = float(commission.replace(',', '.'))
            except Exception:
                return render_template(
                    'usuario_form.html',
                    usuario=request.form,
                    form_action=url_for('usuario.usuario_cadastrar'),
                    empresas=empresas_ativas,
                    selected_empresas=empresa_ids,
                    show_error_modal=True,
                    error_reason='Comissão inválida. Use apenas números com vírgula ou ponto (ex.: 10,5 ou 10.5).'
                )

        # Inserir usuário no banco de dados
        try:
            print("\n[DEBUG] Preparando para inserir usuário no banco de dados")
            query = """
                INSERT INTO users (
                    name, username, password, email, role, status, is_seller, eh_operador, eh_lider_equipe,
                    cpf, phone, commission, employment_type,
                    cep, address, number, complement, neighborhood, city, state, reference, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                name, username, hashed_password, email, role, status, is_seller, eh_operador, eh_lider_equipe,
                _format_cpf(cpf_clean) if cpf_clean else None,
                _format_phone(phone),
                commission_value,
                employment_type or None,
                _format_cep(cep), address or None, number or None, complement or None,
                neighborhood or None, city or None, state or None, reference or None, notes or None
            )
            print(f"[DEBUG] Query: {query}")
            print(f"[DEBUG] Parâmetros: {params}")
            
            usuario_id = db.insert(query, params)
            print(f"[DEBUG] Resultado da inserção: ID={usuario_id}")
            
            if not usuario_id:
                print("[WARN] ID não retornado pelo INSERT. Verificando por username...")
                check = db.fetch_one("SELECT id FROM users WHERE username = %s", (username,))
                if check and check.get('id'):
                    usuario_id = check['id']
                    print(f"[INFO] Inserção confirmada por username. ID={usuario_id}")
            
            if usuario_id:
                # Salvar vínculo usuário↔empresas
                try:
                    _save_user_empresas(db, int(usuario_id), empresa_ids)
                except Exception as e:
                    print(f"[WARN] Falha ao salvar vínculo user_empresas: {e}")

                print("[DEBUG] Usuário cadastrado com sucesso!")
                flash('Usuário cadastrado com sucesso!', 'success')
                # Renderizar diretamente a lista para evitar problemas de rota/404
                usuarios = db.fetch_all(
                    """
                    SELECT u.*,
                           GROUP_CONCAT(COALESCE(e.nome_fantasia, e.razao_social) ORDER BY COALESCE(e.nome_fantasia, e.razao_social) SEPARATOR ', ') AS empresas
                    FROM users u
                    LEFT JOIN user_empresas ue ON ue.user_id = u.id
                    LEFT JOIN empresas e ON e.id = ue.empresa_id AND e.ativo = TRUE
                    GROUP BY u.id
                    ORDER BY u.name
                    """
                )
                return render_template('usuario_list.html', usuarios=usuarios)
            else:
                print("[ERROR] Falha ao confirmar inserção do usuário.")
                return render_template(
                    'usuario_form.html',
                    usuario=request.form,
                    form_action=url_for('usuario.usuario_cadastrar'),
                    empresas=empresas_ativas,
                    selected_empresas=empresa_ids,
                    show_error_modal=True,
                    error_reason='Falha ao cadastrar usuário (ID não retornado). Verifique as permissões do banco e constraints.'
                )
        except Exception as e:
            print(f"[ERROR] Exceção ao cadastrar usuário: {e}")
            # Tentar identificar duplicidade de CPF ou username via índice/constraint
            msg = str(e)
            if 'cpf' in msg.lower() and ('duplicate' in msg.lower() or 'duplic' in msg.lower()):
                dup = db.fetch_one("SELECT id, name, cpf, email, status FROM users WHERE cpf = %s", (_format_cpf(cpf_clean),)) if cpf_clean else None
                return render_template(
                    'usuario_form.html',
                    usuario=None,
                    form_action=url_for('usuario.usuario_cadastrar'),
                    show_duplicate_modal=True,
                    entidade=dup if dup else {'name': name, 'cpf': _format_cpf(cpf_clean), 'email': email, 'status': status},
                    error_reason='CPF já cadastrado.',
                    editar_url='usuario.usuario_editar',
                    visualizar_url='usuario.usuario_visualizar'
                )
            if 'email' in msg.lower() and ('duplicate' in msg.lower() or 'duplic' in msg.lower()):
                return render_template(
                    'usuario_form.html',
                    usuario=request.form,
                    form_action=url_for('usuario.usuario_cadastrar'),
                    show_error_modal=True,
                    error_reason='Email já cadastrado. Por favor, use outro email.'
                )
            if 'username' in msg.lower() and ('duplicate' in msg.lower() or 'duplic' in msg.lower()):
                return render_template(
                    'usuario_form.html',
                    usuario=request.form,
                    form_action=url_for('usuario.usuario_cadastrar'),
                    show_error_modal=True,
                    error_reason='Nome de usuário já existe. Por favor, escolha outro.'
                )
            return render_template(
                'usuario_form.html',
                usuario=request.form,
                form_action=url_for('usuario.usuario_cadastrar'),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason=f'Erro ao cadastrar usuário: {e}'
            )
    
    # Renderizar o formulário de cadastro de usuário
    db = get_db()
    empresas_ativas = _get_empresas_ativas(db)
    return render_template(
        'usuario_form.html',
        usuario=None,
        form_action=url_for('usuario.usuario_cadastrar'),
        empresas=empresas_ativas,
        selected_empresas=[]
    )

# Rota para editar um usuário existente
@usuario_bp.route('/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@usuario_editar_required
def usuario_editar(id):
    # Buscar o usuário pelo ID
    db = get_db()
    print(f"[USUARIO_EDITAR] Requisição para editar ID={id}")
    usuario = db.fetch_one("SELECT * FROM users WHERE id = %s", (id,))
    print(f"[USUARIO_EDITAR] Usuario encontrado? {bool(usuario)}")
    
    if not usuario:
        flash(f'Usuário não encontrado (ID {id}).', 'danger')
        return redirect(url_for('usuario.usuarios'))
    
    if request.method == 'POST':
        # Obter dados do formulário de forma resiliente
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', '').strip()
        status = request.form.get('status', '').strip() or 'active'

        empresas_ativas = _get_empresas_ativas(db)
        empresa_ids = _parse_empresa_ids_from_form(request.form)
        # Flags e campos de senha (edição)
        change_password_flag = request.form.get('change_password') in ('1', 'on', 'true', 'True')
        delete_password_flag = request.form.get('delete_password') == '1'
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_new_password = request.form.get('confirm_new_password', '')
        is_seller = 1 if request.form.get('is_seller') in ('1', 'on', 'true', 'True') else 0
        eh_operador = 1 if request.form.get('eh_operador') in ('1', 'on', 'true', 'True') else 0
        eh_lider_equipe = 1 if request.form.get('eh_lider_equipe') in ('1', 'on', 'true', 'True') else 0
        # Campos estendidos
        cpf = request.form.get('cpf', '').strip()
        phone = request.form.get('phone', '').strip()
        commission = request.form.get('commission', '').strip()
        employment_type = request.form.get('employment_type', '').strip()
        cep = request.form.get('cep', '').strip()
        address = request.form.get('address', '').strip()
        number = request.form.get('number', '').strip()
        complement = request.form.get('complement', '').strip()
        neighborhood = request.form.get('neighborhood', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        reference = request.form.get('reference', '').strip()
        notes = request.form.get('notes', '').strip()

        missing = []
        for field, value in [('name', name), ('username', username), ('email', email), ('role', role)]:
            if not value:
                missing.append(field)
        if missing:
            print(f"[ERROR] Campos obrigatórios ausentes na edição: {missing}")
            return render_template(
                'usuario_form.html',
                usuario=usuario,
                form_action=url_for('usuario.usuario_editar', id=id),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason=f"Preencha todos os campos obrigatórios: {', '.join(missing)}."
            )

        # Usuário não-admin deve ter ao menos 1 empresa
        if role != 'admin' and not empresa_ids:
            return render_template(
                'usuario_form.html',
                usuario=request.form,
                form_action=url_for('usuario.usuario_editar', id=id),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason='Selecione pelo menos 1 empresa para este usuário.'
            )
        
        # Verificar unicidade do username (exceto o próprio usuário)
        existing_user = db.fetch_one(
            "SELECT id FROM users WHERE username = %s AND id <> %s",
            (username, id)
        )
        if existing_user:
            return render_template(
                'usuario_form.html',
                usuario=usuario,
                form_action=url_for('usuario.usuario_editar', id=id),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason='Nome de usuário já existe. Por favor, escolha outro.'
            )
        
        # Converter comissão para float (aceita vírgula ou ponto)
        commission_value = None
        if commission:
            try:
                commission_value = float(commission.replace(',', '.'))
            except Exception:
                return render_template(
                    'usuario_form.html',
                    usuario=usuario,
                    show_error_modal=True,
                    error_reason='Comissão inválida. Use apenas números com vírgula ou ponto (ex.: 10,5 ou 10.5).'
                )

        # Validar role permitido e suporte do ENUM
        allowed_roles = {'admin','manager','user','mecanico','atendente','auxiliar'}
        if role not in allowed_roles:
            return render_template(
                'usuario_form.html',
                usuario=usuario,
                form_action=url_for('usuario.usuario_editar', id=id),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason='Função inválida. Valores permitidos: Administrador, Gerente, Usuário, Mecânico, Atendente, Auxiliar.'
            )
        if role == 'manager' and not _role_enum_supports_manager(db):
            return render_template(
                'usuario_form.html',
                usuario=usuario,
                form_action=url_for('usuario.usuario_editar', id=id),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason=(
                    "A coluna role não aceita 'manager'. Execute: "
                    "ALTER TABLE users MODIFY role ENUM('admin','manager','user') NOT NULL DEFAULT 'user';"
                )
            )

        # Validar CPF (opcional se em branco)
        cpf_clean = _cpf_digits_only(cpf)
        if cpf_clean:
            if not _is_valid_cpf(cpf_clean):
                flash('CPF inválido.', 'danger')
                return render_template(
                    'usuario_form.html',
                    usuario=usuario,
                    form_action=url_for('usuario.usuario_editar', id=id),
                    empresas=empresas_ativas,
                    selected_empresas=empresa_ids
                )
            try:
                dup = db.fetch_one(
                    """
                    SELECT id FROM users
                    WHERE REPLACE(REPLACE(REPLACE(IFNULL(cpf,''), '.', ''), '-', ''), ' ', '') = %s
                      AND id <> %s
                    """,
                    (cpf_clean, id)
                )
                if dup:
                    entidade = db.fetch_one("SELECT id, name, cpf, email, status FROM users WHERE id = %s", (dup['id'],))
                    return render_template(
                        'usuario_form.html',
                        usuario=request.form,
                        form_action=url_for('usuario.usuario_editar', id=id),
                        empresas=empresas_ativas,
                        selected_empresas=empresa_ids,
                        show_duplicate_modal=True,
                        entidade=entidade,
                        error_reason='Já existe um usuário com este CPF.',
                        editar_url='usuario.usuario_editar',
                        visualizar_url='usuario.usuario_visualizar'
                    )
            except Exception as e:
                msg = str(e).lower()
                if 'unknown column' in msg and "cpf'" in msg:
                    return render_template(
                        'usuario_form.html',
                        usuario=usuario,
                        form_action=url_for('usuario.usuario_editar', id=id),
                        empresas=empresas_ativas,
                        selected_empresas=empresa_ids,
                        show_error_modal=True,
                        error_reason='A coluna CPF não existe na tabela users. Execute as migrações: add_is_seller_to_users.py e extend_users_table.py.'
                    )

        # Preparar nova senha conforme flags
        hashed_password = None
        if delete_password_flag:
            # Excluir senha: definir senha padrão solicitada
            default_plain = '123456'
            hashed_password = hash_password(default_plain)
        elif change_password_flag:
            # Alterar senha: validar campos
            if not current_password or not new_password or not confirm_new_password:
                return render_template(
                    'usuario_form.html',
                    usuario=usuario,
                    form_action=url_for('usuario.usuario_editar', id=id),
                    empresas=empresas_ativas,
                    selected_empresas=empresa_ids,
                    show_error_modal=True,
                    error_reason='Preencha a senha atual, a nova senha e a confirmação para alterar a senha.'
                )
            # Verificar senha atual (compatível com hash ou texto puro)
            stored_pwd = usuario.get('password', '')
            check_ok = False
            try:
                # verify_password deve funcionar para hash; se falhar e senha não parecer hash, comparar texto puro
                check_ok = verify_password(stored_pwd, current_password)
            except Exception:
                check_ok = False
            if not check_ok:
                if not is_password_hashed(stored_pwd):
                    check_ok = (stored_pwd == current_password)
            if not check_ok:
                return render_template(
                    'usuario_form.html',
                    usuario=usuario,
                    form_action=url_for('usuario.usuario_editar', id=id),
                    empresas=empresas_ativas,
                    selected_empresas=empresa_ids,
                    show_error_modal=True,
                    error_reason='Senha atual incorreta.'
                )
            # Confirmar nova senha
            if new_password != confirm_new_password:
                return render_template(
                    'usuario_form.html',
                    usuario=usuario,
                    form_action=url_for('usuario.usuario_editar', id=id),
                    empresas=empresas_ativas,
                    selected_empresas=empresa_ids,
                    show_error_modal=True,
                    error_reason='A nova senha e a confirmação não coincidem.'
                )
            # Validação de força
            is_valid, message = validate_password_strength(new_password)
            if not is_valid:
                return render_template(
                    'usuario_form.html',
                    usuario=usuario,
                    form_action=url_for('usuario.usuario_editar', id=id),
                    empresas=empresas_ativas,
                    selected_empresas=empresa_ids,
                    show_error_modal=True,
                    error_reason=message
                )
            hashed_password = hash_password(new_password)
        
        # Atualizar usuário no banco de dados
        if hashed_password:
            # Atualizar com nova senha
            query = """
                UPDATE users
                SET name = %s, username = %s, email = %s, role = %s, status = %s, is_seller = %s, eh_operador = %s, eh_lider_equipe = %s, password = %s,
                    cpf = %s, phone = %s, commission = %s, employment_type = %s,
                    cep = %s, address = %s, number = %s, complement = %s, neighborhood = %s, city = %s, state = %s, reference = %s, notes = %s
                WHERE id = %s
            """
            params = (
                name, username, email, role, status, is_seller, eh_operador, eh_lider_equipe, hashed_password,
                _format_cpf(cpf_clean) if cpf_clean else None,
                _format_phone(phone),
                commission_value,
                employment_type or None,
                _format_cep(cep), address or None, number or None, complement or None,
                neighborhood or None, city or None, state or None, reference or None, notes or None,
                id
            )
        else:
            # Atualizar sem alterar a senha
            query = """
                UPDATE users
                SET name = %s, username = %s, email = %s, role = %s, status = %s, is_seller = %s, eh_operador = %s, eh_lider_equipe = %s,
                    cpf = %s, phone = %s, commission = %s, employment_type = %s,
                    cep = %s, address = %s, number = %s, complement = %s, neighborhood = %s, city = %s, state = %s, reference = %s, notes = %s
                WHERE id = %s
            """
            params = (
                name, username, email, role, status, is_seller, eh_operador, eh_lider_equipe,
                _format_cpf(cpf_clean) if cpf_clean else None,
                _format_phone(phone),
                commission_value,
                employment_type or None,
                _format_cep(cep), address or None, number or None, complement or None,
                neighborhood or None, city or None, state or None, reference or None, notes or None,
                id
            )
        
        try:
            affected_rows = db.update(query, params)
        except Exception as e:
            return render_template(
                'usuario_form.html',
                usuario=usuario,
                form_action=url_for('usuario.usuario_editar', id=id),
                empresas=empresas_ativas,
                selected_empresas=empresa_ids,
                show_error_modal=True,
                error_reason=f'Erro ao atualizar usuário: {e}'
            )

        # Alguns bancos retornam 0 quando os dados não mudaram. Considerar como sucesso.
        if affected_rows >= 0:
            # Salvar vínculo usuário↔empresas
            try:
                _save_user_empresas(db, int(id), empresa_ids)
            except Exception as e:
                print(f"[WARN] Falha ao salvar vínculo user_empresas: {e}")

            if delete_password_flag:
                flash('Senha redefinida para o padrão 123456.', 'success')
            elif change_password_flag:
                flash('Senha alterada com sucesso!', 'success')
            else:
                flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('usuario.usuarios'))
        
        # fallback improvável
        return render_template(
            'usuario_form.html',
            usuario=usuario,
            form_action=url_for('usuario.usuario_editar', id=id),
            empresas=empresas_ativas,
            selected_empresas=empresa_ids,
            show_error_modal=True,
            error_reason='Erro ao atualizar usuário.'
        )
    
    # Renderizar o formulário de edição de usuário
    empresas_ativas = _get_empresas_ativas(db)
    selected_empresas = _get_user_empresa_ids(db, int(id))
    return render_template(
        'usuario_form.html',
        usuario=usuario,
        form_action=url_for('usuario.usuario_editar', id=id),
        empresas=empresas_ativas,
        selected_empresas=selected_empresas
    )

# Rota para visualizar um usuário
@usuario_bp.route('/usuarios/visualizar/<int:id>')
@admin_required
def usuario_visualizar(id):
    # Buscar o usuário pelo ID
    db = get_db()
    usuario = db.fetch_one("SELECT * FROM users WHERE id = %s", (id,))
    
    if not usuario:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('usuario.usuarios'))
    
    # Renderizar a visualização do usuário
    return render_template('usuario_view.html', usuario=usuario)

# Rota para excluir um usuário
@usuario_bp.route('/usuarios/excluir/<int:id>')
@usuario_excluir_required
def usuario_excluir(id):
    # Buscar o usuário pelo ID
    db = get_db()
    usuario = db.fetch_one("SELECT * FROM users WHERE id = %s", (id,))
    
    if not usuario:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('usuario.usuarios'))
    
    # Não permitir excluir o próprio usuário logado
    if usuario['username'] == session['username']:
        flash('Você não pode excluir seu próprio usuário.', 'danger')
        return redirect(url_for('usuario.usuarios'))
    
    # Excluir o usuário do banco de dados
    affected_rows = db.delete("DELETE FROM users WHERE id = %s", (id,))
    
    if affected_rows > 0:
        flash('Usuário excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir usuário.', 'danger')
    
    # Redirecionar para a lista de usuários
    return redirect(url_for('usuario.usuarios'))
