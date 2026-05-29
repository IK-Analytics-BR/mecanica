from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
from database import Database


# Função para obter conexão com o banco de dados (usa configuração automática)
def get_db():
    return Database()

ncm_bp = Blueprint('ncm', __name__)

# Rota para listar NCMs
@ncm_bp.route('/ncms')
@login_required
def ncms():
    # Buscar NCMs no banco de dados (limitado a 100 para não sobrecarregar)
    db = get_db()
    ncms = db.fetch_all("SELECT * FROM ncm ORDER BY codigo LIMIT 100")
    db.close()
    return render_template('ncm_list.html', ncms=ncms or [])

# Rota para buscar NCMs por código ou descrição (API)
@ncm_bp.route('/api/ncms/search')
@login_required
def search_ncms():
    # Obter parâmetros da busca
    search_term = request.args.get('term', '')
    
    if not search_term or len(search_term) < 3:
        return jsonify({'results': []})
    
    # Buscar NCMs no banco de dados
    db = get_db()
    
    # Buscar por código ou descrição
    query = """
    SELECT id, codigo, descricao 
    FROM ncm 
    WHERE codigo LIKE %s OR descricao LIKE %s
    ORDER BY 
        CASE 
            WHEN codigo = %s THEN 0
            WHEN codigo LIKE %s THEN 1
            WHEN descricao LIKE %s THEN 2
            ELSE 3
        END,
        codigo
    LIMIT 20
    """
    
    params = (
        f"{search_term}%",  # Código começando com o termo
        f"%{search_term}%", # Descrição contendo o termo
        search_term,        # Código exato
        f"{search_term}%",  # Código começando com o termo
        f"%{search_term}%" # Descrição contendo o termo
    )
    
    ncms = db.fetch_all(query, params)
    db.close()
    
    # Formatar resultados para Select2
    results = []
    for ncm in (ncms or []):
        results.append({
            'id': ncm['codigo'],
            'text': f"{ncm['codigo']} - {ncm['descricao']}"
        })
    
    return jsonify({'results': results})

# Rota para obter detalhes de um NCM específico (API)
@ncm_bp.route('/api/ncms/<codigo>')
@login_required
def get_ncm_details(codigo):
    # Buscar NCM no banco de dados
    db = get_db()
    ncm = db.fetch_one("SELECT * FROM ncm WHERE codigo = %s", (codigo,))
    db.close()
    
    if ncm:
        return jsonify({
            'success': True,
            'ncm': {
                'id': ncm['id'],
                'codigo': ncm['codigo'],
                'descricao': ncm['descricao'],
                'data_inicio': ncm['data_inicio'].strftime('%d/%m/%Y') if ncm.get('data_inicio') else '',
                'data_fim': ncm['data_fim'].strftime('%d/%m/%Y') if ncm.get('data_fim') else ''
            }
        })
    else:
        return jsonify({
            'success': False,
            'message': 'NCM não encontrado'
        })
