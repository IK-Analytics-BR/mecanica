from flask import Blueprint, render_template, request, jsonify
from utils.auth import login_required
from database import get_db

cfop_bp = Blueprint('cfop', __name__)

# Rota para listar CFOPs
@cfop_bp.route('/cfops')
@login_required
def cfops():
    # Buscar CFOPs no banco de dados (limitado a 100 para não sobrecarregar)
    db = get_db()
    cfops = db.fetch_all("SELECT * FROM cfop ORDER BY codigo LIMIT 100")
    return render_template('cfop_list.html', cfops=cfops or [])

# Rota para buscar CFOPs por código ou descrição (API)
@cfop_bp.route('/api/cfops/search')
@login_required
def search_cfops():
    # Obter parâmetros da busca
    search_term = request.args.get('term', '')
    
    if not search_term or len(search_term) < 2:
        return jsonify({'results': []})
    
    # Buscar CFOPs no banco de dados
    db = get_db()
    
    # Buscar por código ou descrição
    query = """
    SELECT id, codigo, descricao 
    FROM cfop 
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
    
    cfops = db.fetch_all(query, params)

    # Formatar resultados para Select2
    results = []
    for cfop in (cfops or []):
        results.append({
            'id': cfop['codigo'],
            'text': f"{cfop['codigo']} - {cfop['descricao']}"
        })
    
    return jsonify({'results': results})

# Rota para obter detalhes de um CFOP específico (API)
@cfop_bp.route('/api/cfops/<codigo>')
@login_required
def get_cfop_details(codigo):
    # Buscar CFOP no banco de dados
    db = get_db()
    cfop = db.fetch_one("SELECT * FROM cfop WHERE codigo = %s", (codigo,))

    if cfop:
        return jsonify({
            'success': True,
            'cfop': {
                'id': cfop['id'],
                'codigo': cfop['codigo'],
                'descricao': cfop['descricao']
            }
        })
    else:
        return jsonify({
            'success': False,
            'message': 'CFOP não encontrado'
        })
