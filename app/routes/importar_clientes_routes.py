from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
from utils.auth import login_required


# Decorator para verificar se o usuário é admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

importar_clientes_bp = Blueprint('importar_clientes', __name__)

@importar_clientes_bp.route('/admin/importar-clientes', methods=['GET'])
@login_required
@admin_required
def importar_clientes_form():
    """Exibe o formulário de importação de clientes"""
    return render_template('importar_clientes.html')

@importar_clientes_bp.route('/admin/importar-clientes/buscar-cnae', methods=['POST'])
@login_required
@admin_required
def buscar_cnae():
    """Busca CNAEs na tabela cnae20 por código ou descrição"""
    from app.database import Database
    
    data = request.get_json()
    search_term = data.get('search_term', '').strip()
    
    if not search_term:
        return jsonify({
            'success': False,
            'message': 'Termo de busca não informado'
        })
    
    try:
        # Conectar ao banco
        db = Database()
        
        # Buscar em todas as colunas relevantes
        like_term = f"%{search_term}%"
        query = """
            SELECT 
                cnae_id,
                secao_codigo,
                secao_descricao,
                divisao_codigo,
                divisao_descricao,
                grupo_codigo,
                grupo_descricao,
                classe_codigo,
                classe_descricao,
                subclasse_codigo,
                subclasse_codigo_num,
                SUBSTRING(subclasse_descricao, 1, 1024) AS subclasse_descricao,
                cnae7p
            FROM cnae20
            WHERE 
                secao_codigo LIKE %s OR
                secao_descricao LIKE %s OR
                divisao_codigo LIKE %s OR
                divisao_descricao LIKE %s OR
                grupo_codigo LIKE %s OR
                grupo_descricao LIKE %s OR
                classe_codigo LIKE %s OR
                classe_descricao LIKE %s OR
                subclasse_codigo LIKE %s OR
                subclasse_codigo_num LIKE %s OR
                subclasse_descricao LIKE %s OR
                cnae7p LIKE %s
            ORDER BY subclasse_codigo
            LIMIT 100
        """
        
        # Executar query com o termo de busca em todas as colunas
        params = tuple([like_term] * 12)
        results = db.fetch_all(query, params)
        db.close()
        
        return jsonify({
            'success': True,
            'results': results or [],
            'total': len(results or [])
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar CNAEs: {str(e)}'
        })

@importar_clientes_bp.route('/admin/importar-clientes/processar', methods=['POST'])
@login_required
@admin_required
def processar_importacao():
    """Inicia a importação de clientes da Receita Federal em background"""
    import threading
    import sys
    import os
    
    data = request.get_json()
    ufs = data.get('ufs', [])  # Lista de UFs
    cnae_codigos = data.get('cnae_codigos', [])  # Lista de códigos CNAE
    limpar_tabela = data.get('limpar_tabela', False)  # Padrão: não limpar
    
    if not ufs or len(ufs) == 0 or not cnae_codigos or len(cnae_codigos) == 0:
        return jsonify({
            'success': False,
            'message': 'Pelo menos uma UF e um CNAE são obrigatórios'
        })
    
    # Adicionar diretório scripts ao path
    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts')
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    
    # Importar e executar em thread separada
    from scripts.importar_receita_federal_v2 import process_and_insert
    
    def run_import():
        try:
            # Remover caracteres não numéricos de cada CNAE
            cnaes_limpos = [''.join(filter(str.isdigit, cnae)) for cnae in cnae_codigos]
            
            # [OK] DEBUG: Mostrar CNAEs originais vs limpos
            print(f"\n[ROTA] CNAEs recebidos da interface:")
            for i, (original, limpo) in enumerate(zip(cnae_codigos, cnaes_limpos)):
                print(f"  [{i+1}] '{original}' → '{limpo}'")
            print(f"\n[ROTA] UFs: {ufs}")
            print(f"[ROTA] Limpar tabela: {limpar_tabela}\n")
            
            process_and_insert(cnaes=cnaes_limpos, ufs=ufs, table_name="empresas_filtradas", limpar=limpar_tabela)
        except Exception as e:
            print(f"Erro na importação: {e}")
    
    # Iniciar thread
    thread = threading.Thread(target=run_import, daemon=True)
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Importação iniciada com sucesso',
        'ufs': ufs,
        'cnae_codigos': cnae_codigos
    })

@importar_clientes_bp.route('/admin/importar-clientes/status', methods=['GET'])
@login_required
@admin_required
def obter_status():
    """Retorna o status atual da importação"""
    import os
    import json
    
    status_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'importacao_status.json')
    
    if not os.path.exists(status_file):
        return jsonify({
            'status': 'aguardando',
            'etapa': 'Nenhuma importação em andamento',
            'arquivos_total': 0,
            'arquivo_atual': 0,
            'registros_lidos': 0,
            'registros_inseridos': 0,
            'percentual': 0
        })
    
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status = json.load(f)
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'erro': str(e)
        })

@importar_clientes_bp.route('/admin/importar-clientes/geocodificar', methods=['POST'])
@login_required
@admin_required
def iniciar_geocodificacao():
    """Inicia a geocodificação das empresas importadas"""
    import threading
    
    # Importar e executar em thread separada
    from scripts.geocodificar_empresas import geocodificar_empresas_existentes
    
    def run_geocoding():
        try:
            geocodificar_empresas_existentes(table_name="empresas_filtradas", batch_size=100)
        except Exception as e:
            print(f"Erro na geocodificação: {e}")
    
    # Iniciar thread
    thread = threading.Thread(target=run_geocoding, daemon=True)
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Geocodificação iniciada com sucesso'
    })

@importar_clientes_bp.route('/admin/importar-clientes/geocodificacao-status', methods=['GET'])
@login_required
@admin_required
def obter_status_geocodificacao():
    """Retorna o status atual da geocodificação"""
    import os
    import json
    
    status_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'geocodificacao_status.json')
    
    if not os.path.exists(status_file):
        return jsonify({
            'status': 'aguardando',
            'etapa': 'Nenhuma geocodificação em andamento',
            'total_registros': 0,
            'registros_processados': 0,
            'registros_geocodificados': 0,
            'registros_falha': 0,
            'percentual': 0
        })
    
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status = json.load(f)
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'erro': str(e)
        })

@importar_clientes_bp.route('/admin/importar-clientes/resetar-contador', methods=['POST'])
@login_required
@admin_required
def resetar_contador():
    """Reseta o contador de requisições (início de novo mês)"""
    import os
    import json
    
    try:
        contador_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'geocodificacao_contador.json')
        
        # Resetar contador
        with open(contador_file, 'w') as f:
            json.dump({
                'requisicoes_feitas': 0,
                'ultima_atualizacao': datetime.now().isoformat(),
                'resetado_em': datetime.now().isoformat()
            }, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Contador resetado com sucesso! Novo mês iniciado.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': str(e)
        })

@importar_clientes_bp.route('/admin/importar-clientes/importar-sistema', methods=['POST'])
@login_required
@admin_required
def importar_para_sistema():
    """Importa empresas_filtradas para clientes do sistema"""
    import threading
    import sys
    import os
    
    # Adicionar diretório de scripts ao path
    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts')
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    
    from importar_para_sistema import importar_empresas_para_sistema
    
    try:
        data = request.get_json() or {}
        modo = data.get('modo', 'substituir')  # 'substituir' ou 'mesclar'
        apenas_ativas = data.get('apenas_ativas', True)
        
        # Executar em background
        thread = threading.Thread(
            target=importar_empresas_para_sistema,
            args=(modo, apenas_ativas)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Importação iniciada em modo: {modo}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': str(e)
        })

@importar_clientes_bp.route('/admin/importar-clientes/importacao-status', methods=['GET'])
@login_required
@admin_required
def obter_status_importacao():
    """Retorna o status atual da importação para o sistema"""
    import os
    import json
    
    status_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'importacao_sistema_status.json')
    
    if not os.path.exists(status_file):
        return jsonify({
            'status': 'aguardando',
            'etapa': 'Nenhuma importação em andamento',
            'total_registros': 0,
            'registros_processados': 0,
            'registros_importados': 0,
            'registros_duplicados': 0,
            'registros_erro': 0,
            'percentual': 0
        })
    
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status = json.load(f)
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'erro': str(e)
        })

@importar_clientes_bp.route('/admin/importar-clientes/verificar-pendentes', methods=['GET'])
@login_required
@admin_required
def verificar_pendentes():
    """Verifica quantos registros existem sem geocodificação"""
    from app.database import Database
    
    try:
        db = Database()
        
        # Contar total de registros
        result = db.fetch_one("SELECT COUNT(*) as total FROM empresas_filtradas")
        total = result['total'] if result else 0
        
        # Contar registros sem geocodificação
        result = db.fetch_one("""
            SELECT COUNT(*) as pendentes
            FROM empresas_filtradas 
            WHERE LATITUDE IS NULL OR LONGITUDE IS NULL
        """)
        pendentes = result['pendentes'] if result else 0
        
        db.close()
        
        # Contar registros já geocodificados
        geocodificados = total - pendentes
        
        return jsonify({
            'success': True,
            'total': total,
            'pendentes': pendentes,
            'geocodificados': geocodificados,
            'percentual_completo': int((geocodificados / total * 100) if total > 0 else 0)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': str(e),
            'total': 0,
            'pendentes': 0,
            'geocodificados': 0
        })
