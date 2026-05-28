"""
Rotas para CRUD de Transportadoras
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import get_db

transportadora_bp = Blueprint('transportadoras', __name__, url_prefix='/transportadoras')


# =====================================================
# LISTA DE TRANSPORTADORAS
# =====================================================

@transportadora_bp.route('/')
@transportadora_bp.route('/lista')
def lista():
    """Lista todas as transportadoras"""
    db = get_db()
    
    busca = request.args.get('busca', '')
    status = request.args.get('status', 'ativas')
    
    query = """
        SELECT * FROM transportadoras
        WHERE 1=1
    """
    params = []
    
    if status == 'ativas':
        query += " AND active = 1"
    elif status == 'inativas':
        query += " AND active = 0"
    
    if busca:
        query += " AND (nome LIKE %s OR cnpj LIKE %s OR cidade LIKE %s)"
        params.extend([f'%{busca}%', f'%{busca}%', f'%{busca}%'])
    
    query += " ORDER BY nome"
    
    transportadoras = db.fetch_all(query, params)
    
    return render_template('cadastros/transportadora_lista.html',
        transportadoras=transportadoras or [],
        busca=busca,
        status=status
    )


# =====================================================
# NOVA TRANSPORTADORA
# =====================================================

@transportadora_bp.route('/nova')
def nova():
    """Formulário de nova transportadora"""
    return render_template('cadastros/transportadora_form.html',
        transportadora=None,
        modo='nova'
    )


# =====================================================
# EDITAR TRANSPORTADORA
# =====================================================

@transportadora_bp.route('/<int:id>/editar')
def editar(id):
    """Formulário de edição de transportadora"""
    db = get_db()
    
    transportadora = db.fetch_one("SELECT * FROM transportadoras WHERE id = %s", [id])
    
    if not transportadora:
        flash('Transportadora não encontrada.', 'error')
        return redirect(url_for('transportadoras.lista'))
    
    return render_template('cadastros/transportadora_form.html',
        transportadora=transportadora,
        modo='editar'
    )


# =====================================================
# SALVAR TRANSPORTADORA
# =====================================================

@transportadora_bp.route('/salvar', methods=['POST'])
def salvar():
    """Salva transportadora (nova ou edição)"""
    db = get_db()
    
    try:
        transportadora_id = request.form.get('id')
        
        dados = {
            'codigo': request.form.get('codigo', '').strip(),
            'nome': request.form.get('nome', '').strip(),
            'razao_social': request.form.get('razao_social', '').strip(),
            'cnpj': request.form.get('cnpj', '').strip(),
            'cpf': request.form.get('cpf', '').strip(),
            'inscricao_estadual': request.form.get('inscricao_estadual', '').strip(),
            'endereco': request.form.get('endereco', '').strip(),
            'numero': request.form.get('numero', '').strip(),
            'complemento': request.form.get('complemento', '').strip(),
            'bairro': request.form.get('bairro', '').strip(),
            'cidade': request.form.get('cidade', '').strip(),
            'estado': request.form.get('estado', '').strip().upper(),
            'cep': request.form.get('cep', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'celular': request.form.get('celular', '').strip(),
            'email': request.form.get('email', '').strip(),
            'contato': request.form.get('contato', '').strip(),
            'observacoes': request.form.get('observacoes', '').strip(),
            'active': 1 if request.form.get('active') else 0
        }
        
        if not dados['nome']:
            flash('Nome é obrigatório.', 'error')
            return redirect(request.referrer)
        
        if transportadora_id:
            # Atualizar
            db.execute_query("""
                UPDATE transportadoras SET
                    codigo = %s, nome = %s, razao_social = %s, cnpj = %s, cpf = %s,
                    inscricao_estadual = %s, endereco = %s, numero = %s, complemento = %s,
                    bairro = %s, cidade = %s, estado = %s, cep = %s, telefone = %s,
                    celular = %s, email = %s, contato = %s, observacoes = %s, active = %s
                WHERE id = %s
            """, [
                dados['codigo'], dados['nome'], dados['razao_social'], dados['cnpj'], dados['cpf'],
                dados['inscricao_estadual'], dados['endereco'], dados['numero'], dados['complemento'],
                dados['bairro'], dados['cidade'], dados['estado'], dados['cep'], dados['telefone'],
                dados['celular'], dados['email'], dados['contato'], dados['observacoes'], dados['active'],
                transportadora_id
            ])
            flash('Transportadora atualizada com sucesso!', 'success')
        else:
            # Inserir
            db.execute_query("""
                INSERT INTO transportadoras (
                    codigo, nome, razao_social, cnpj, cpf, inscricao_estadual,
                    endereco, numero, complemento, bairro, cidade, estado, cep,
                    telefone, celular, email, contato, observacoes, active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                dados['codigo'], dados['nome'], dados['razao_social'], dados['cnpj'], dados['cpf'],
                dados['inscricao_estadual'], dados['endereco'], dados['numero'], dados['complemento'],
                dados['bairro'], dados['cidade'], dados['estado'], dados['cep'], dados['telefone'],
                dados['celular'], dados['email'], dados['contato'], dados['observacoes'], dados['active']
            ])
            flash('Transportadora cadastrada com sucesso!', 'success')
        
        return redirect(url_for('transportadoras.lista'))
        
    except Exception as e:
        flash(f'Erro ao salvar transportadora: {str(e)}', 'error')
        return redirect(request.referrer)


# =====================================================
# EXCLUIR TRANSPORTADORA
# =====================================================

@transportadora_bp.route('/<int:id>/excluir', methods=['POST'])
def excluir(id):
    """Exclui transportadora (soft delete)"""
    db = get_db()
    
    try:
        db.execute_query("UPDATE transportadoras SET active = 0 WHERE id = %s", [id])
        flash('Transportadora desativada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao desativar transportadora: {str(e)}', 'error')
    
    return redirect(url_for('transportadoras.lista'))


# =====================================================
# API - BUSCAR TRANSPORTADORAS
# =====================================================

@transportadora_bp.route('/api/buscar')
def api_buscar():
    """API para buscar transportadoras (autocomplete)"""
    termo = request.args.get('q', '')
    
    if len(termo) < 2:
        return jsonify([])
    
    db = get_db()
    
    transportadoras = db.fetch_all("""
        SELECT id, nome, cnpj AS documento, cidade, estado
        FROM transportadoras
        WHERE active = 1
        AND (nome LIKE %s OR cnpj LIKE %s OR cpf LIKE %s)
        ORDER BY nome
        LIMIT 20
    """, [f'%{termo}%', f'%{termo}%', f'%{termo}%'])
    
    return jsonify(transportadoras or [])


@transportadora_bp.route('/api/<int:id>')
def api_obter(id):
    """API para obter dados completos de uma transportadora"""
    db = get_db()
    
    transportadora = db.fetch_one("""
        SELECT id, nome, razao_social, cnpj, cpf, inscricao_estadual,
               cep, endereco, numero, complemento, bairro, cidade, estado,
               telefone, email
        FROM transportadoras
        WHERE id = %s
    """, [id])
    
    if not transportadora:
        return jsonify({'error': 'Transportadora não encontrada'}), 404
    
    return jsonify(transportadora)
