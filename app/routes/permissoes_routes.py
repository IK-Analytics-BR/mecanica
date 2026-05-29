"""
Rotas para administração de permissões de usuário.
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from functools import wraps
from database import get_db
from utils.auth import login_required
from utils.permissoes_helper import (
    listar_telas_sistema, 
    listar_permissoes_usuario,
    salvar_permissoes_usuario,
    copiar_permissoes,
    dar_acesso_total,
    tem_permissao
)

permissoes_bp = Blueprint('permissoes', __name__, url_prefix='/admin/permissoes')


def admin_required(f):
    """Decorator que exige permissão admin.permissoes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not tem_permissao('admin.permissoes', 'visualizar'):
            flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
            return redirect(url_for('bem_vindo'))
        return f(*args, **kwargs)
    return decorated_function




@permissoes_bp.route('/')
@login_required
@admin_required
def lista():
    """Lista de usuários para configurar permissões."""
    db = get_db()
    
    # Buscar usuários
    usuarios = db.fetch_all("""
        SELECT 
            u.id, u.name, u.username, u.email, u.role, u.status,
            COALESCE(u.is_seller,0) as eh_vendedor,
            COALESCE(u.eh_operador,0) as eh_operador,
            COALESCE(u.eh_lider_equipe,0) as eh_lider_equipe,
            (SELECT COUNT(*) FROM usuario_permissoes WHERE usuario_id = u.id) as total_permissoes
        FROM users u
        WHERE u.status = 'active'
        ORDER BY u.name
    """)
    
    return render_template('admin/permissoes_lista.html', usuarios=usuarios)


@permissoes_bp.route('/usuario/<int:usuario_id>')
@login_required
@admin_required
def editar_usuario(usuario_id):
    """Editar permissões de um usuário específico."""
    db = get_db()
    
    # Buscar usuário
    usuario = db.fetch_one("SELECT id, name, username, email, role FROM users WHERE id = %s", (usuario_id,))
    if not usuario:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('permissoes.lista'))
    
    # Buscar permissões do usuário
    permissoes = listar_permissoes_usuario(usuario_id)
    
    # Agrupar por módulo
    modulos = {}
    for p in permissoes:
        modulo = p['modulo']
        if modulo not in modulos:
            modulos[modulo] = []
        modulos[modulo].append(p)
    
    # Buscar outros usuários para copiar permissões
    outros_usuarios = db.fetch_all("""
        SELECT id, name, username 
        FROM users 
        WHERE id != %s AND status = 'active'
        ORDER BY name
    """, (usuario_id,))
    
    return render_template('admin/permissoes_editar.html', 
                          usuario=usuario, 
                          modulos=modulos,
                          outros_usuarios=outros_usuarios)


@permissoes_bp.route('/usuario/<int:usuario_id>/salvar', methods=['POST'])
@login_required
@admin_required
def salvar_usuario(usuario_id):
    """Salvar permissões do usuário."""
    db = get_db()
    
    # Verificar se usuário existe
    usuario = db.fetch_one("SELECT id, name FROM users WHERE id = %s", (usuario_id,))
    if not usuario:
        return jsonify({'success': False, 'error': 'Usuário não encontrado.'}), 404
    
    try:
        # Coletar permissões do formulário
        permissoes = []
        
        # Buscar todas as telas
        telas = db.fetch_all("SELECT id FROM sistema_telas WHERE ativo = 1")
        
        for tela in telas:
            tela_id = tela['id']
            permissoes.append({
                'tela_id': tela_id,
                'visualizar': request.form.get(f'perm_{tela_id}_visualizar') == '1',
                'criar': request.form.get(f'perm_{tela_id}_criar') == '1',
                'editar': request.form.get(f'perm_{tela_id}_editar') == '1',
                'excluir': request.form.get(f'perm_{tela_id}_excluir') == '1',
            })
        
        # Salvar
        if salvar_permissoes_usuario(usuario_id, permissoes, session.get('user_id')):
            flash(f'Permissões de {usuario["name"]} salvas com sucesso!', 'success')
            return redirect(url_for('permissoes.lista'))
        else:
            flash('Erro ao salvar permissões.', 'danger')
            return redirect(url_for('permissoes.editar_usuario', usuario_id=usuario_id))
            
    except Exception as e:
        flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('permissoes.editar_usuario', usuario_id=usuario_id))


@permissoes_bp.route('/usuario/<int:usuario_id>/copiar', methods=['POST'])
@login_required
@admin_required
def copiar_de_usuario(usuario_id):
    """Copia permissões de outro usuário."""
    origem_id = request.form.get('usuario_origem_id', type=int)
    
    if not origem_id:
        return jsonify({'success': False, 'error': 'Usuário de origem não informado.'}), 400
    
    if copiar_permissoes(origem_id, usuario_id, session.get('user_id')):
        flash('Permissões copiadas com sucesso!', 'success')
    else:
        flash('Erro ao copiar permissões.', 'danger')
    
    return redirect(url_for('permissoes.editar_usuario', usuario_id=usuario_id))


@permissoes_bp.route('/usuario/<int:usuario_id>/acesso-total', methods=['POST'])
@login_required
@admin_required
def acesso_total_usuario(usuario_id):
    """Dá acesso total a um usuário."""
    if dar_acesso_total(usuario_id, session.get('user_id')):
        flash('Acesso total concedido com sucesso!', 'success')
    else:
        flash('Erro ao conceder acesso total.', 'danger')
    
    return redirect(url_for('permissoes.editar_usuario', usuario_id=usuario_id))


@permissoes_bp.route('/usuario/<int:usuario_id>/remover-todas', methods=['POST'])
@login_required
@admin_required
def remover_todas_permissoes(usuario_id):
    """Remove todas as permissões de um usuário."""
    db = get_db()
    
    try:
        db.execute_query("DELETE FROM usuario_permissoes WHERE usuario_id = %s", (usuario_id,))
        flash('Todas as permissões foram removidas.', 'success')
    except Exception as e:
        flash(f'Erro ao remover permissões: {str(e)}', 'danger')
    
    return redirect(url_for('permissoes.editar_usuario', usuario_id=usuario_id))


@permissoes_bp.route('/telas')
@login_required
@admin_required
def listar_telas():
    """Lista todas as telas do sistema."""
    telas = listar_telas_sistema()
    
    # Agrupar por módulo
    modulos = {}
    for t in telas:
        modulo = t['modulo']
        if modulo not in modulos:
            modulos[modulo] = []
        modulos[modulo].append(t)
    
    return render_template('admin/permissoes_telas.html', modulos=modulos)


@permissoes_bp.route('/telas/sincronizar', methods=['POST'])
@login_required
@admin_required
def sincronizar_telas():
    """Sincroniza as telas do sistema (re-executa o INSERT do SQL)."""
    db = get_db()
    
    try:
        # Re-executa o script de inserção de telas
        db.execute("SOURCE app/scripts/069_PERMISSOES_USUARIO.sql")
        flash('Telas sincronizadas com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao sincronizar: {str(e)}', 'warning')
    
    return redirect(url_for('permissoes.listar_telas'))


# API endpoints
@permissoes_bp.route('/api/usuario/<int:usuario_id>/permissoes')
@login_required
@admin_required
def api_permissoes_usuario(usuario_id):
    """API: Retorna permissões de um usuário."""
    permissoes = listar_permissoes_usuario(usuario_id)
    return jsonify({'success': True, 'permissoes': permissoes})


@permissoes_bp.route('/api/usuario/<int:usuario_id>/toggle', methods=['POST'])
@login_required
@admin_required
def api_toggle_permissao(usuario_id):
    """API: Alterna uma permissão específica."""
    db = get_db()
    
    data = request.get_json()
    tela_id = data.get('tela_id')
    campo = data.get('campo')  # visualizar, criar, editar, excluir
    valor = data.get('valor', False)
    
    if not tela_id or not campo:
        return jsonify({'success': False, 'error': 'Parâmetros inválidos.'}), 400
    
    # Mapear campo para coluna
    colunas = {
        'visualizar': 'pode_visualizar',
        'criar': 'pode_criar',
        'editar': 'pode_editar',
        'excluir': 'pode_excluir'
    }
    
    if campo not in colunas:
        return jsonify({'success': False, 'error': 'Campo inválido.'}), 400
    
    coluna = colunas[campo]
    
    try:
        # Verificar se já existe registro
        existente = db.fetch_one("""
            SELECT id FROM usuario_permissoes 
            WHERE usuario_id = %s AND tela_id = %s
        """, (usuario_id, tela_id))
        
        if existente:
            # Atualizar
            db.execute(f"""
                UPDATE usuario_permissoes 
                SET {coluna} = %s 
                WHERE usuario_id = %s AND tela_id = %s
            """, (1 if valor else 0, usuario_id, tela_id))
        else:
            # Inserir novo
            db.insert(f"""
                INSERT INTO usuario_permissoes 
                (usuario_id, tela_id, {coluna}, created_by)
                VALUES (%s, %s, %s, %s)
            """, (usuario_id, tela_id, 1 if valor else 0, session.get('user_id')))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@permissoes_bp.route('/api/usuario/<int:usuario_id>/marcar-modulo', methods=['POST'])
@login_required
@admin_required
def api_marcar_modulo(usuario_id):
    """API: Marca/desmarca todas as permissões de um módulo."""
    db = get_db()
    
    data = request.get_json()
    modulo = data.get('modulo')
    campo = data.get('campo')  # visualizar, criar, editar, excluir, todos
    valor = data.get('valor', False)
    
    if not modulo:
        return jsonify({'success': False, 'error': 'Módulo não informado.'}), 400
    
    try:
        # Buscar telas do módulo
        telas = db.fetch_all("""
            SELECT id FROM sistema_telas 
            WHERE modulo = %s AND ativo = 1
        """, (modulo,))
        
        for tela in telas:
            tela_id = tela['id']
            
            # Verificar se já existe
            existente = db.fetch_one("""
                SELECT id FROM usuario_permissoes 
                WHERE usuario_id = %s AND tela_id = %s
            """, (usuario_id, tela_id))
            
            if campo == 'todos':
                # Marcar todas as permissões
                if existente:
                    db.execute("""
                        UPDATE usuario_permissoes 
                        SET pode_visualizar = %s, pode_criar = %s, pode_editar = %s, pode_excluir = %s
                        WHERE usuario_id = %s AND tela_id = %s
                    """, (1 if valor else 0, 1 if valor else 0, 1 if valor else 0, 1 if valor else 0,
                          usuario_id, tela_id))
                else:
                    db.insert("""
                        INSERT INTO usuario_permissoes 
                        (usuario_id, tela_id, pode_visualizar, pode_criar, pode_editar, pode_excluir, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (usuario_id, tela_id, 
                          1 if valor else 0, 1 if valor else 0, 1 if valor else 0, 1 if valor else 0,
                          session.get('user_id')))
            else:
                # Marcar apenas um campo
                colunas = {
                    'visualizar': 'pode_visualizar',
                    'criar': 'pode_criar',
                    'editar': 'pode_editar',
                    'excluir': 'pode_excluir'
                }
                coluna = colunas.get(campo)
                if coluna:
                    if existente:
                        db.execute(f"""
                            UPDATE usuario_permissoes 
                            SET {coluna} = %s 
                            WHERE usuario_id = %s AND tela_id = %s
                        """, (1 if valor else 0, usuario_id, tela_id))
                    else:
                        db.insert(f"""
                            INSERT INTO usuario_permissoes 
                            (usuario_id, tela_id, {coluna}, created_by)
                            VALUES (%s, %s, %s, %s)
                        """, (usuario_id, tela_id, 1 if valor else 0, session.get('user_id')))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
