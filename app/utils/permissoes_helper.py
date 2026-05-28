"""
Helper para controle de permissões de usuário por tela.
"""
from functools import wraps
from flask import session, flash, redirect, url_for, request, jsonify, g
from database import get_db


def carregar_permissoes_usuario(usuario_id: int) -> dict:
    """
    Carrega todas as permissões do usuário do banco de dados.
    Retorna um dicionário com as permissões por código de tela.
    
    Exemplo:
    {
        'vendas.pdv': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False},
        'clientes.lista': {'visualizar': True, 'criar': False, 'editar': False, 'excluir': False},
    }
    """
    db = get_db()
    
    try:
        permissoes = db.fetch_all("""
            SELECT 
                st.codigo,
                st.rota_flask,
                st.url_padrao,
                up.pode_visualizar,
                up.pode_criar,
                up.pode_editar,
                up.pode_excluir
            FROM usuario_permissoes up
            JOIN sistema_telas st ON st.id = up.tela_id
            WHERE up.usuario_id = %s AND st.ativo = 1
        """, (usuario_id,))
        
        resultado = {}
        for p in permissoes:
            resultado[p['codigo']] = {
                'visualizar': bool(p['pode_visualizar']),
                'criar': bool(p['pode_criar']),
                'editar': bool(p['pode_editar']),
                'excluir': bool(p['pode_excluir']),
                'rota_flask': p['rota_flask'],
                'url_padrao': p['url_padrao']
            }
        
        return resultado
    except Exception as e:
        print(f"[PERMISSOES] Erro ao carregar permissões: {e}")
        return {}


def tem_permissao(codigo_tela: str, acao: str = 'visualizar') -> bool:
    """
    Verifica se o usuário atual tem permissão para uma ação em uma tela.
    
    Args:
        codigo_tela: Código da tela (ex: 'vendas.pdv', 'clientes.lista')
        acao: Tipo de ação ('visualizar', 'criar', 'editar', 'excluir')
    
    Returns:
        bool: True se tem permissão, False caso contrário
    """
    # Admin sempre tem acesso total
    if session.get('role') == 'admin':
        return True
    
    # Busca permissões da sessão
    permissoes = session.get('permissoes', {})
    
    # Se não tem permissões carregadas, nega acesso
    if not permissoes:
        return False
    
    # Verifica se tem permissão para a tela/ação específica
    if codigo_tela in permissoes:
        return permissoes[codigo_tela].get(acao, False)
    
    return False


def pode_ver(codigo_tela: str) -> bool:
    """Atalho para verificar permissão de visualização."""
    return tem_permissao(codigo_tela, 'visualizar')


def pode_criar(codigo_tela: str) -> bool:
    """Atalho para verificar permissão de criação."""
    return tem_permissao(codigo_tela, 'criar')


def pode_editar(codigo_tela: str) -> bool:
    """Atalho para verificar permissão de edição."""
    return tem_permissao(codigo_tela, 'editar')


def pode_excluir(codigo_tela: str) -> bool:
    """Atalho para verificar permissão de exclusão."""
    return tem_permissao(codigo_tela, 'excluir')


def requer_permissao(codigo_tela: str, acao: str = 'visualizar'):
    """
    Decorator para proteger rotas com verificação de permissão.
    
    Uso:
        @app.route('/vendas/pdv')
        @login_required
        @requer_permissao('vendas.pdv', 'visualizar')
        def pdv():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not tem_permissao(codigo_tela, acao):
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False, 
                        'error': 'Você não tem permissão para acessar esta funcionalidade.'
                    }), 403
                flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
                return redirect(url_for('bem_vindo'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_menu_permitido() -> dict:
    """
    Retorna a estrutura de menu filtrada pelas permissões do usuário.
    Usado para renderizar o menu lateral.
    """
    # Admin vê tudo
    if session.get('role') == 'admin':
        return {'admin': True, 'modulos': {}}
    
    permissoes = session.get('permissoes', {})
    
    # Agrupa por módulo
    modulos = {}
    for codigo, perm in permissoes.items():
        if perm.get('visualizar'):
            # Extrai o módulo do código (ex: 'vendas.pdv' -> 'vendas')
            partes = codigo.split('.')
            modulo = partes[0] if partes else 'outros'
            
            if modulo not in modulos:
                modulos[modulo] = []
            modulos[modulo].append(codigo)
    
    return {'admin': False, 'modulos': modulos}


def listar_telas_sistema() -> list:
    """
    Lista todas as telas cadastradas no sistema.
    """
    db = get_db()
    
    try:
        telas = db.fetch_all("""
            SELECT 
                id, codigo, nome, descricao, modulo, 
                rota_flask, url_padrao, icone, ordem, ativo
            FROM sistema_telas
            ORDER BY modulo, ordem, nome
        """)
        return telas or []
    except Exception as e:
        print(f"[PERMISSOES] Erro ao listar telas: {e}")
        return []


def listar_permissoes_usuario(usuario_id: int) -> list:
    """
    Lista todas as permissões de um usuário específico.
    """
    db = get_db()
    
    try:
        permissoes = db.fetch_all("""
            SELECT 
                st.id as tela_id,
                st.codigo,
                st.nome,
                st.modulo,
                st.icone,
                COALESCE(up.pode_visualizar, 0) as pode_visualizar,
                COALESCE(up.pode_criar, 0) as pode_criar,
                COALESCE(up.pode_editar, 0) as pode_editar,
                COALESCE(up.pode_excluir, 0) as pode_excluir
            FROM sistema_telas st
            LEFT JOIN usuario_permissoes up ON up.tela_id = st.id AND up.usuario_id = %s
            WHERE st.ativo = 1
            ORDER BY st.modulo, st.ordem, st.nome
        """, (usuario_id,))
        return permissoes or []
    except Exception as e:
        print(f"[PERMISSOES] Erro ao listar permissões do usuário: {e}")
        return []


def salvar_permissoes_usuario(usuario_id: int, permissoes: list, created_by: int = None) -> bool:
    """
    Salva as permissões de um usuário.
    
    Args:
        usuario_id: ID do usuário
        permissoes: Lista de dicts com {tela_id, visualizar, criar, editar, excluir}
        created_by: ID do usuário que está salvando
    
    Returns:
        bool: True se salvou com sucesso
    """
    db = get_db()
    
    try:
        # Remove permissões existentes
        db.execute_query("DELETE FROM usuario_permissoes WHERE usuario_id = %s", (usuario_id,))
        
        # Insere novas permissões
        for perm in permissoes:
            # Só insere se tem pelo menos uma permissão
            if any([perm.get('visualizar'), perm.get('criar'), perm.get('editar'), perm.get('excluir')]):
                db.insert("""
                    INSERT INTO usuario_permissoes 
                    (usuario_id, tela_id, pode_visualizar, pode_criar, pode_editar, pode_excluir, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    usuario_id,
                    perm['tela_id'],
                    1 if perm.get('visualizar') else 0,
                    1 if perm.get('criar') else 0,
                    1 if perm.get('editar') else 0,
                    1 if perm.get('excluir') else 0,
                    created_by
                ))
        
        return True
    except Exception as e:
        print(f"[PERMISSOES] Erro ao salvar permissões: {e}")
        db.rollback()
        return False


def copiar_permissoes(usuario_origem_id: int, usuario_destino_id: int, created_by: int = None) -> bool:
    """
    Copia permissões de um usuário para outro.
    """
    db = get_db()
    
    try:
        # Buscar permissões da origem
        origem = db.fetch_all(
            "SELECT tela_id, pode_visualizar, pode_criar, pode_editar, pode_excluir FROM usuario_permissoes WHERE usuario_id = %s",
            (usuario_origem_id,)
        ) or []
        # Limpar destino
        db.execute_query("DELETE FROM usuario_permissoes WHERE usuario_id = %s", (usuario_destino_id,))
        # Copiar
        for p in origem:
            db.insert("""
                INSERT INTO usuario_permissoes
                (usuario_id, tela_id, pode_visualizar, pode_criar, pode_editar, pode_excluir, created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (usuario_destino_id, p['tela_id'],
                   p['pode_visualizar'], p['pode_criar'], p['pode_editar'], p['pode_excluir'], created_by))
        return True
    except Exception as e:
        print(f"[PERMISSOES] Erro ao copiar permissões: {e}")
        return False


def dar_acesso_total(usuario_id: int, created_by: int = None) -> bool:
    """
    Dá acesso total a todas as telas para um usuário.
    """
    db = get_db()
    
    try:
        telas = db.fetch_all("SELECT id FROM sistema_telas WHERE ativo=1") or []
        db.execute_query("DELETE FROM usuario_permissoes WHERE usuario_id = %s", (usuario_id,))
        for t in telas:
            db.insert("""
                INSERT INTO usuario_permissoes
                (usuario_id, tela_id, pode_visualizar, pode_criar, pode_editar, pode_excluir, created_by)
                VALUES (%s,%s,1,1,1,1,%s)
            """, (usuario_id, t['id'], created_by))
        return True
    except Exception as e:
        print(f"[PERMISSOES] Erro ao dar acesso total: {e}")
        return False


def registrar_funcoes_template(app):
    """
    Registra funções de permissão para uso nos templates Jinja2.
    Chamar esta função no app factory.
    """
    @app.context_processor
    def inject_permissoes():
        return {
            'tem_permissao': tem_permissao,
            'pode_ver': pode_ver,
            'pode_criar': pode_criar,
            'pode_editar': pode_editar,
            'pode_excluir': pode_excluir,
            'get_menu_permitido': get_menu_permitido
        }
