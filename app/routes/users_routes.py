"""
Rotas para o módulo de Usuários e Permissões.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import datetime
import hashlib
import secrets
import re

from database import get_db
from utils.auth import login_required, admin_required

# Criar o blueprint
users_bp = Blueprint('users', __name__)

@users_bp.route('/usuarios')
@admin_required
def users_list():
    """Lista todos os usuários."""
    db = get_db()
    
    # Buscar todos os usuários
    users = db.fetch_all("""
        SELECT u.*, GROUP_CONCAT(p.name SEPARATOR ', ') as permissions
        FROM users u
        LEFT JOIN user_permissions up ON u.id = up.user_id
        LEFT JOIN permissions p ON up.permission_id = p.id
        WHERE u.active = TRUE
        GROUP BY u.id
        ORDER BY u.name
    """)
    
    return render_template(
        'users_list.html',
        users=users,
        active_page='users'
    )

@users_bp.route('/usuarios/cadastrar', methods=['GET', 'POST'])
@admin_required
def user_create():
    """Cadastra um novo usuário."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')
        permissions = request.form.getlist('permissions')
        eh_vendedor = 1 if request.form.get('eh_vendedor') else 0
        eh_operador = 1 if request.form.get('eh_operador') else 0
        comissao_padrao = request.form.get('comissao_padrao', '0') or '0'
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome é obrigatório.')
        
        if not username:
            errors.append('Nome de usuário é obrigatório.')
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Nome de usuário deve conter apenas letras, números e underscores.')
        else:
            # Verificar se o nome de usuário já existe
            existing_user = db.fetch_one("SELECT * FROM users WHERE username = %s", (username,))
            if existing_user:
                errors.append('Este nome de usuário já está em uso.')
        
        if not email:
            errors.append('E-mail é obrigatório.')
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('E-mail inválido.')
        else:
            # Verificar se o e-mail já existe
            existing_email = db.fetch_one("SELECT * FROM users WHERE email = %s", (email,))
            if existing_email:
                errors.append('Este e-mail já está em uso.')
        
        if not password:
            errors.append('Senha é obrigatória.')
        elif len(password) < 8:
            errors.append('A senha deve ter pelo menos 8 caracteres.')
        
        if password != confirm_password:
            errors.append('As senhas não conferem.')
        
        if not role:
            errors.append('Perfil é obrigatório.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            # Buscar permissões para o formulário
            all_permissions = db.fetch_all("SELECT * FROM permissions ORDER BY name")
            
            return render_template(
                'user_form.html',
                user=None,
                all_permissions=all_permissions,
                active_page='users'
            )
        
        # Gerar salt e hash da senha
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        
        # Inserir usuário no banco de dados
        user_id = db.insert("""
            INSERT INTO users (name, username, email, password_hash, salt, role, eh_vendedor, eh_operador, comissao_padrao, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            name, username, email, password_hash, salt, role, eh_vendedor, eh_operador, comissao_padrao, session.get('user_id', 1)
        ))
        
        if user_id:
            # Inserir permissões do usuário
            for permission_id in permissions:
                db.insert("""
                    INSERT INTO user_permissions (user_id, permission_id)
                    VALUES (%s, %s)
                """, (user_id, permission_id))
            
            flash('Usuário cadastrado com sucesso!', 'success')
            return redirect(url_for('users.users_list'))
        else:
            flash('Erro ao cadastrar usuário.', 'danger')
    
    # Buscar permissões para o formulário
    all_permissions = db.fetch_all("SELECT * FROM permissions ORDER BY name")
    
    return render_template(
        'user_form.html',
        user=None,
        all_permissions=all_permissions,
        active_page='users'
    )

@users_bp.route('/usuarios/editar/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def user_edit(user_id):
    """Edita um usuário existente."""
    db = get_db()
    
    # Buscar o usuário
    user = db.fetch_one("""
        SELECT * FROM users
        WHERE id = %s AND active = TRUE
    """, (user_id,))
    
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('users.users_list'))
    
    # Buscar permissões do usuário
    user_permissions = db.fetch_all("""
        SELECT permission_id FROM user_permissions
        WHERE user_id = %s
    """, (user_id,))
    
    user_permission_ids = [p['permission_id'] for p in user_permissions]
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        permissions = request.form.getlist('permissions')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        eh_vendedor = 1 if request.form.get('eh_vendedor') else 0
        eh_operador = 1 if request.form.get('eh_operador') else 0
        comissao_padrao = request.form.get('comissao_padrao', '0') or '0'
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome é obrigatório.')
        
        if not email:
            errors.append('E-mail é obrigatório.')
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('E-mail inválido.')
        else:
            # Verificar se o e-mail já existe (exceto para o usuário atual)
            existing_email = db.fetch_one("SELECT * FROM users WHERE email = %s AND id != %s", (email, user_id))
            if existing_email:
                errors.append('Este e-mail já está em uso.')
        
        if not role:
            errors.append('Perfil é obrigatório.')
        
        # Verificar senha apenas se foi fornecida
        if password:
            if len(password) < 8:
                errors.append('A senha deve ter pelo menos 8 caracteres.')
            
            if password != confirm_password:
                errors.append('As senhas não conferem.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            # Buscar permissões para o formulário
            all_permissions = db.fetch_all("SELECT * FROM permissions ORDER BY name")
            
            return render_template(
                'user_form.html',
                user=user,
                user_permission_ids=user_permission_ids,
                all_permissions=all_permissions,
                active_page='users'
            )
        
        # Atualizar usuário no banco de dados
        if password:
            # Gerar novo salt e hash da senha
            salt = secrets.token_hex(16)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            
            affected_rows = db.update("""
                UPDATE users
                SET name = %s, email = %s, password_hash = %s, salt = %s, role = %s, 
                    eh_vendedor = %s, eh_operador = %s, comissao_padrao = %s
                WHERE id = %s
            """, (
                name, email, password_hash, salt, role, eh_vendedor, eh_operador, comissao_padrao, user_id
            ))
        else:
            affected_rows = db.update("""
                UPDATE users
                SET name = %s, email = %s, role = %s, 
                    eh_vendedor = %s, eh_operador = %s, comissao_padrao = %s
                WHERE id = %s
            """, (
                name, email, role, eh_vendedor, eh_operador, comissao_padrao, user_id
            ))
        
        if affected_rows > 0:
            # Remover permissões antigas
            db.delete("""
                DELETE FROM user_permissions
                WHERE user_id = %s
            """, (user_id,))
            
            # Inserir novas permissões
            for permission_id in permissions:
                db.insert("""
                    INSERT INTO user_permissions (user_id, permission_id)
                    VALUES (%s, %s)
                """, (user_id, permission_id))
            
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('users.users_list'))
        else:
            flash('Erro ao atualizar usuário.', 'danger')
    
    # Buscar permissões para o formulário
    all_permissions = db.fetch_all("SELECT * FROM permissions ORDER BY name")
    
    return render_template(
        'user_form.html',
        user=user,
        user_permission_ids=user_permission_ids,
        all_permissions=all_permissions,
        active_page='users'
    )

@users_bp.route('/usuarios/excluir/<int:user_id>', methods=['POST'])
@admin_required
def user_delete(user_id):
    """Exclui um usuário (exclusão lógica)."""
    db = get_db()
    
    # Verificar se o usuário existe
    user = db.fetch_one("""
        SELECT * FROM users
        WHERE id = %s AND active = TRUE
    """, (user_id,))
    
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('users.users_list'))
    
    # Não permitir exclusão do próprio usuário
    if user['id'] == session.get('user_id', 1):  # Usar ID 1 como padrão se não houver user_id na sessão
        flash('Você não pode excluir seu próprio usuário.', 'danger')
        return redirect(url_for('users.users_list'))
    
    # Excluir usuário (exclusão lógica)
    affected_rows = db.update("""
        UPDATE users
        SET active = FALSE
        WHERE id = %s
    """, (user_id,))
    
    if affected_rows > 0:
        flash('Usuário excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir usuário.', 'danger')
    
    return redirect(url_for('users.users_list'))

@users_bp.route('/permissoes')
@admin_required
def permissions_list():
    """Lista todas as permissões."""
    db = get_db()
    
    # Buscar todas as permissões
    permissions = db.fetch_all("""
        SELECT * FROM permissions
        ORDER BY name
    """)
    
    return render_template(
        'permissions_list.html',
        permissions=permissions,
        active_page='permissions'
    )

@users_bp.route('/permissoes/cadastrar', methods=['GET', 'POST'])
@admin_required
def permission_create():
    """Cadastra uma nova permissão."""
    db = get_db()
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        description = request.form.get('description')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome é obrigatório.')
        else:
            # Verificar se a permissão já existe
            existing_permission = db.fetch_one("SELECT * FROM permissions WHERE name = %s", (name,))
            if existing_permission:
                errors.append('Esta permissão já existe.')
        
        if not description:
            errors.append('Descrição é obrigatória.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            return render_template(
                'permission_form.html',
                permission=None,
                active_page='permissions'
            )
        
        # Inserir permissão no banco de dados
        permission_id = db.insert("""
            INSERT INTO permissions (name, description)
            VALUES (%s, %s)
        """, (
            name, description
        ))
        
        if permission_id:
            flash('Permissão cadastrada com sucesso!', 'success')
            return redirect(url_for('users.permissions_list'))
        else:
            flash('Erro ao cadastrar permissão.', 'danger')
    
    return render_template(
        'permission_form.html',
        permission=None,
        active_page='permissions'
    )

@users_bp.route('/permissoes/editar/<int:permission_id>', methods=['GET', 'POST'])
@admin_required
def permission_edit(permission_id):
    """Edita uma permissão existente."""
    db = get_db()
    
    # Buscar a permissão
    permission = db.fetch_one("""
        SELECT * FROM permissions
        WHERE id = %s
    """, (permission_id,))
    
    if not permission:
        flash('Permissão não encontrada.', 'danger')
        return redirect(url_for('users.permissions_list'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        description = request.form.get('description')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome é obrigatório.')
        else:
            # Verificar se a permissão já existe (exceto para a permissão atual)
            existing_permission = db.fetch_one("SELECT * FROM permissions WHERE name = %s AND id != %s", (name, permission_id))
            if existing_permission:
                errors.append('Esta permissão já existe.')
        
        if not description:
            errors.append('Descrição é obrigatória.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            return render_template(
                'permission_form.html',
                permission=permission,
                active_page='permissions'
            )
        
        # Atualizar permissão no banco de dados
        affected_rows = db.update("""
            UPDATE permissions
            SET name = %s, description = %s
            WHERE id = %s
        """, (
            name, description, permission_id
        ))
        
        if affected_rows > 0:
            flash('Permissão atualizada com sucesso!', 'success')
            return redirect(url_for('users.permissions_list'))
        else:
            flash('Erro ao atualizar permissão.', 'danger')
    
    return render_template(
        'permission_form.html',
        permission=permission,
        active_page='permissions'
    )

@users_bp.route('/permissoes/excluir/<int:permission_id>', methods=['POST'])
@admin_required
def permission_delete(permission_id):
    """Exclui uma permissão."""
    db = get_db()
    
    # Verificar se a permissão existe
    permission = db.fetch_one("""
        SELECT * FROM permissions
        WHERE id = %s
    """, (permission_id,))
    
    if not permission:
        flash('Permissão não encontrada.', 'danger')
        return redirect(url_for('users.permissions_list'))
    
    # Verificar se a permissão está em uso
    in_use = db.fetch_one("""
        SELECT COUNT(*) as count FROM user_permissions
        WHERE permission_id = %s
    """, (permission_id,))
    
    if in_use and in_use['count'] > 0:
        flash('Esta permissão está em uso e não pode ser excluída.', 'danger')
        return redirect(url_for('users.permissions_list'))
    
    # Excluir permissão
    affected_rows = db.delete("""
        DELETE FROM permissions
        WHERE id = %s
    """, (permission_id,))
    
    if affected_rows > 0:
        flash('Permissão excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir permissão.', 'danger')
    
    return redirect(url_for('users.permissions_list'))

@users_bp.route('/perfil')
@login_required
def user_profile():
    """Exibe o perfil do usuário logado."""
    db = get_db()
    
    # Buscar o usuário
    user = db.fetch_one("""
        SELECT * FROM users
        WHERE id = %s AND active = TRUE
    """, (session['user_id'],))
    
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Buscar permissões do usuário
    permissions = db.fetch_all("""
        SELECT p.* FROM permissions p
        JOIN user_permissions up ON p.id = up.permission_id
        WHERE up.user_id = %s
        ORDER BY p.name
    """, (session['user_id'],))
    
    return render_template(
        'user_profile.html',
        user=user,
        permissions=permissions,
        active_page='profile'
    )

@users_bp.route('/perfil/editar', methods=['GET', 'POST'])
@login_required
def user_profile_edit():
    """Edita o perfil do usuário logado."""
    db = get_db()
    
    # Buscar o usuário
    user = db.fetch_one("""
        SELECT * FROM users
        WHERE id = %s AND active = TRUE
    """, (session['user_id'],))
    
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Obter dados do formulário
        name = request.form.get('name')
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validar dados
        errors = []
        
        if not name:
            errors.append('Nome é obrigatório.')
        
        if not email:
            errors.append('E-mail é obrigatório.')
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('E-mail inválido.')
        else:
            # Verificar se o e-mail já existe (exceto para o usuário atual)
            existing_email = db.fetch_one("SELECT * FROM users WHERE email = %s AND id != %s", (email, session.get('user_id', 1)))  # Usar ID 1 como padrão se não houver user_id na sessão
            if existing_email:
                errors.append('Este e-mail já está em uso.')
        
        # Verificar senha atual apenas se o usuário deseja alterar a senha
        if new_password:
            if not current_password:
                errors.append('Senha atual é obrigatória para alterar a senha.')
            else:
                # Verificar se a senha atual está correta
                current_hash = hashlib.sha256((current_password + user['salt']).encode()).hexdigest()
                if current_hash != user['password_hash']:
                    errors.append('Senha atual incorreta.')
            
            if len(new_password) < 8:
                errors.append('A nova senha deve ter pelo menos 8 caracteres.')
            
            if new_password != confirm_password:
                errors.append('As senhas não conferem.')
        
        # Se houver erros, exibir mensagens e retornar ao formulário
        if errors:
            for error in errors:
                flash(error, 'danger')
            
            return render_template(
                'user_profile_edit.html',
                user=user,
                active_page='profile'
            )
        
        # Atualizar usuário no banco de dados
        if new_password:
            # Gerar novo salt e hash da senha
            salt = secrets.token_hex(16)
            password_hash = hashlib.sha256((new_password + salt).encode()).hexdigest()
            
            affected_rows = db.update("""
                UPDATE users
                SET name = %s, email = %s, password_hash = %s, salt = %s
                WHERE id = %s
            """, (
                name, email, password_hash, salt, session.get('user_id', 1)  # Usar ID 1 como padrão se não houver user_id na sessão
            ))
        else:
            affected_rows = db.update("""
                UPDATE users
                SET name = %s, email = %s
                WHERE id = %s
            """, (
                name, email, session.get('user_id', 1)  # Usar ID 1 como padrão se não houver user_id na sessão
            ))
        
        if affected_rows > 0:
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('users.user_profile'))
        else:
            flash('Erro ao atualizar perfil.', 'danger')
    
    return render_template(
        'user_profile_edit.html',
        user=user,
        active_page='profile'
    )

@users_bp.route('/perfil/alterar-senha', methods=['POST'])
@login_required
def change_password_modal():
    """Altera a senha do usuário logado a partir do modal no topo."""
    db = get_db()

    user = db.fetch_one(
        """
        SELECT * FROM users
        WHERE id = %s AND active = TRUE
        """,
        (session.get('user_id', 1),)
    )

    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    errors: list[str] = []

    if not current_password or not new_password or not confirm_password:
        errors.append('Preencha a senha atual, a nova senha e a confirmação para alterar a senha.')
    else:
        current_hash = hashlib.sha256((current_password + user['salt']).encode()).hexdigest()
        if current_hash != user['password_hash']:
            errors.append('Senha atual incorreta.')
        if len(new_password) < 8:
            errors.append('A nova senha deve ter pelo menos 8 caracteres.')
        if new_password != confirm_password:
            errors.append('As senhas não conferem.')

    if errors:
        for error in errors:
            flash(error, 'danger')
        referrer = request.referrer or url_for('bem_vindo')
        return redirect(referrer)

    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((new_password + salt).encode()).hexdigest()

    affected_rows = db.update(
        """
        UPDATE users
        SET password_hash = %s, salt = %s
        WHERE id = %s
        """,
        (password_hash, salt, session.get('user_id', 1))
    )

    if affected_rows > 0:
        flash('Senha alterada com sucesso!', 'success')
    else:
        flash('Erro ao alterar senha.', 'danger')

    referrer = request.referrer or url_for('bem_vindo')
    return redirect(referrer)

@users_bp.route('/api/verificar-permissao/<permission_name>')
@login_required
def api_check_permission(permission_name):
    """API para verificar se o usuário tem uma permissão específica."""
    db = get_db()
    
    # Verificar se o usuário tem a permissão
    has_permission = db.fetch_one("""
        SELECT COUNT(*) as count FROM user_permissions up
        JOIN permissions p ON up.permission_id = p.id
        WHERE up.user_id = %s AND p.name = %s
    """, (session.get('user_id', 1), permission_name))  # Usar ID 1 como padrão se não houver user_id na sessão
    
    return jsonify({
        'has_permission': has_permission['count'] > 0
    })
