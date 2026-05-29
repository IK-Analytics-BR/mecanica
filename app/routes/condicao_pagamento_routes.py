"""
Rotas para CRUD de Condições de Pagamento
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
try:
    from database import get_db
except ImportError:
    from app.database import get_db

condicao_pagamento_bp = Blueprint('condicoes_pagamento', __name__, url_prefix='/condicoes-pagamento')


# =====================================================
# LISTA DE CONDIÇÕES DE PAGAMENTO
# =====================================================

@condicao_pagamento_bp.route('/')
@condicao_pagamento_bp.route('/lista')
def lista():
    """Lista todas as condições de pagamento"""
    db = get_db()
    
    condicoes = db.fetch_all("""
        SELECT * FROM payment_terms
        ORDER BY name
    """)
    
    return render_template('cadastros/condicao_pagamento_lista.html',
        condicoes=condicoes or []
    )


# =====================================================
# NOVA CONDIÇÃO
# =====================================================

@condicao_pagamento_bp.route('/nova')
def nova():
    """Formulário de nova condição de pagamento"""
    return render_template('cadastros/condicao_pagamento_form.html',
        condicao=None,
        modo='nova'
    )


# =====================================================
# EDITAR CONDIÇÃO
# =====================================================

@condicao_pagamento_bp.route('/<int:id>/editar')
def editar(id):
    """Formulário de edição de condição"""
    db = get_db()
    
    condicao = db.fetch_one("SELECT * FROM payment_terms WHERE id = %s", [id])
    
    if not condicao:
        flash('Condição de pagamento não encontrada.', 'error')
        return redirect(url_for('condicoes_pagamento.lista'))
    
    return render_template('cadastros/condicao_pagamento_form.html',
        condicao=condicao,
        modo='editar'
    )


# =====================================================
# SALVAR CONDIÇÃO
# =====================================================

@condicao_pagamento_bp.route('/salvar', methods=['POST'])
def salvar():
    """Salva condição (nova ou edição)"""
    db = get_db()
    
    try:
        condicao_id = request.form.get('id')
        
        nome = request.form.get('name', '').strip()
        dias = request.form.get('days', '').strip()
        descricao = request.form.get('description', '').strip()
        active = 1 if request.form.get('active') else 0
        
        if not nome:
            flash('Nome é obrigatório.', 'error')
            return redirect(request.referrer)
        
        if condicao_id:
            # Atualizar
            db.execute_query("""
                UPDATE payment_terms SET
                    name = %s, days = %s, description = %s, active = %s
                WHERE id = %s
            """, [nome, dias, descricao, active, condicao_id])
            flash('Condição de pagamento atualizada com sucesso!', 'success')
        else:
            # Inserir
            db.execute_query("""
                INSERT INTO payment_terms (name, days, description, active)
                VALUES (%s, %s, %s, %s)
            """, [nome, dias, descricao, active])
            flash('Condição de pagamento cadastrada com sucesso!', 'success')
        
        return redirect(url_for('condicoes_pagamento.lista'))
        
    except Exception as e:
        flash(f'Erro ao salvar: {str(e)}', 'error')
        return redirect(request.referrer)


# =====================================================
# EXCLUIR CONDIÇÃO
# =====================================================

@condicao_pagamento_bp.route('/<int:id>/excluir', methods=['POST'])
def excluir(id):
    """Exclui condição (soft delete)"""
    db = get_db()
    
    try:
        db.execute_query("UPDATE payment_terms SET active = 0 WHERE id = %s", [id])
        flash('Condição de pagamento desativada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao desativar: {str(e)}', 'error')
    
    return redirect(url_for('condicoes_pagamento.lista'))


# =====================================================
# API - BUSCAR CONDIÇÕES
# =====================================================

@condicao_pagamento_bp.route('/api/buscar')
def api_buscar():
    """API para buscar condições (autocomplete)"""
    termo = request.args.get('q', '')
    
    db = get_db()
    
    if termo:
        condicoes = db.fetch_all("""
            SELECT id, name AS nome, days AS dias, description AS descricao
            FROM payment_terms
            WHERE active = 1 AND name LIKE %s
            ORDER BY name
            LIMIT 20
        """, [f'%{termo}%'])
    else:
        condicoes = db.fetch_all("""
            SELECT id, name AS nome, days AS dias, description AS descricao
            FROM payment_terms
            WHERE active = 1
            ORDER BY name
            LIMIT 50
        """)
    
    return jsonify(condicoes or [])
