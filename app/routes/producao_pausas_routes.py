"""
Blueprint para Gestão de Pausas de Produção
Módulo Indústria
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from database import get_db
from utils.auth import login_required

producao_pausas_bp = Blueprint('producao_pausas', __name__, url_prefix='/industria/producao-pausas')




# =====================================================
# CRUD DE MOTIVOS DE PAUSA
# =====================================================

@producao_pausas_bp.route('/motivos')
@login_required
def listar_motivos():
    """Lista todos os motivos de pausa"""
    db = get_db()
    
    motivos = db.fetch_all("""
        SELECT m.*, 
               (SELECT COUNT(*) FROM producao_pausas p WHERE p.motivo_id = m.id) AS total_uso
        FROM producao_pausas_motivos m
        ORDER BY m.tipo, m.nome
    """) or []
    
    return render_template('industria/producao_pausas_motivos.html', motivos=motivos)


@producao_pausas_bp.route('/motivos/novo', methods=['GET', 'POST'])
@login_required
def novo_motivo():
    """Criar novo motivo de pausa"""
    db = get_db()
    
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        tipo = request.form.get('tipo', 'improdutivo')
        icone = request.form.get('icone', 'bi-pause-circle')
        cor_hex = request.form.get('cor_hex', '#6c757d')
        
        if not nome:
            flash('Nome é obrigatório!', 'danger')
            return render_template('industria/producao_pausas_motivos_form.html', motivo=None)
        
        try:
            db.insert("""
                INSERT INTO producao_pausas_motivos (nome, descricao, tipo, icone, cor_hex)
                VALUES (%s, %s, %s, %s, %s)
            """, (nome, descricao, tipo, icone, cor_hex))
            
            flash('Motivo criado com sucesso!', 'success')
            return redirect(url_for('producao_pausas.listar_motivos'))
        except Exception as e:
            flash(f'Erro ao criar motivo: {str(e)}', 'danger')
    
    return render_template('industria/producao_pausas_motivos_form.html', motivo=None)


@producao_pausas_bp.route('/motivos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_motivo(id):
    """Editar motivo de pausa"""
    db = get_db()
    
    motivo = db.fetch_one("SELECT * FROM producao_pausas_motivos WHERE id = %s", (id,))
    if not motivo:
        flash('Motivo não encontrado!', 'danger')
        return redirect(url_for('producao_pausas.listar_motivos'))
    
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        tipo = request.form.get('tipo', 'improdutivo')
        icone = request.form.get('icone', 'bi-pause-circle')
        cor_hex = request.form.get('cor_hex', '#6c757d')
        ativo = 1 if request.form.get('ativo') else 0
        
        if not nome:
            flash('Nome é obrigatório!', 'danger')
            return render_template('industria/producao_pausas_motivos_form.html', motivo=motivo)
        
        try:
            db.update("""
                UPDATE producao_pausas_motivos 
                SET nome = %s, descricao = %s, tipo = %s, icone = %s, cor_hex = %s, ativo = %s
                WHERE id = %s
            """, (nome, descricao, tipo, icone, cor_hex, ativo, id))
            
            flash('Motivo atualizado com sucesso!', 'success')
            return redirect(url_for('producao_pausas.listar_motivos'))
        except Exception as e:
            flash(f'Erro ao atualizar motivo: {str(e)}', 'danger')
    
    return render_template('industria/producao_pausas_motivos_form.html', motivo=motivo)


@producao_pausas_bp.route('/motivos/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_motivo(id):
    """Excluir motivo de pausa"""
    db = get_db()
    
    try:
        # Verificar se está em uso
        em_uso = db.fetch_one("""
            SELECT COUNT(*) as c FROM producao_pausas WHERE motivo_id = %s
        """, (id,))
        
        if em_uso and em_uso['c'] > 0:
            flash('Este motivo está em uso e não pode ser excluído. Desative-o se necessário.', 'warning')
        else:
            db.execute("DELETE FROM producao_pausas_motivos WHERE id = %s", (id,))
            flash('Motivo excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir motivo: {str(e)}', 'danger')
    
    return redirect(url_for('producao_pausas.listar_motivos'))


# =====================================================
# API PARA OPERADOR (Pausar/Retomar)
# =====================================================

@producao_pausas_bp.route('/api/motivos-ativos')
@login_required
def api_motivos_ativos():
    """Retorna motivos ativos para seleção"""
    db = get_db()
    
    motivos = db.fetch_all("""
        SELECT id, nome, tipo, icone, cor_hex
        FROM producao_pausas_motivos
        WHERE ativo = 1
        ORDER BY tipo DESC, nome
    """) or []
    
    return jsonify(motivos)


@producao_pausas_bp.route('/api/pausar', methods=['POST'])
@login_required
def api_pausar():
    """Inicia uma pausa no lote"""
    db = get_db()
    user_id = session.get('user_id')
    
    data = request.get_json() or request.form
    lote_id = data.get('lote_id')
    motivo_id = data.get('motivo_id')
    observacao = data.get('observacao', '')
    
    if not lote_id or not motivo_id:
        return jsonify({'success': False, 'error': 'Lote e motivo são obrigatórios'}), 400
    
    try:
        # Buscar lote
        lote = db.fetch_one("""
            SELECT l.*, op.id AS op_id FROM op_lotes l
            INNER JOIN ordens_producao op ON op.id = l.ordem_producao_id
            WHERE l.id = %s
        """, (lote_id,))
        
        if not lote:
            return jsonify({'success': False, 'error': 'Lote não encontrado'}), 404
        
        # Verificar se já está pausado
        pausa_ativa = db.fetch_one("""
            SELECT id FROM producao_pausas 
            WHERE lote_id = %s AND fim IS NULL
        """, (lote_id,))
        
        if pausa_ativa:
            return jsonify({'success': False, 'error': 'Este lote já está pausado'}), 400
        
        # Criar pausa
        pausa_id = db.insert("""
            INSERT INTO producao_pausas 
            (lote_id, ordem_producao_id, operador_id, motivo_id, etapa_id, inicio, observacao)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
        """, (lote_id, lote['ordem_producao_id'], user_id, motivo_id, 
              lote.get('etapa_atual_id'), observacao))
        
        # Buscar info do motivo para retornar
        motivo = db.fetch_one("SELECT nome, tipo FROM producao_pausas_motivos WHERE id = %s", (motivo_id,))
        
        return jsonify({
            'success': True, 
            'message': f'Lote pausado - {motivo["nome"]}',
            'pausa_id': pausa_id,
            'tipo': motivo['tipo']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@producao_pausas_bp.route('/api/retomar', methods=['POST'])
@login_required
def api_retomar():
    """Retoma o lote (encerra a pausa)"""
    db = get_db()
    user_id = session.get('user_id')
    
    data = request.get_json() or request.form
    lote_id = data.get('lote_id')
    
    if not lote_id:
        return jsonify({'success': False, 'error': 'Lote é obrigatório'}), 400
    
    try:
        # Buscar pausa ativa
        pausa = db.fetch_one("""
            SELECT p.*, m.nome AS motivo_nome, m.tipo
            FROM producao_pausas p
            INNER JOIN producao_pausas_motivos m ON m.id = p.motivo_id
            WHERE p.lote_id = %s AND p.fim IS NULL
        """, (lote_id,))
        
        if not pausa:
            return jsonify({'success': False, 'error': 'Nenhuma pausa ativa para este lote'}), 400
        
        # Calcular duração e encerrar
        db.update("""
            UPDATE producao_pausas 
            SET fim = NOW(),
                duracao_minutos = TIMESTAMPDIFF(MINUTE, inicio, NOW())
            WHERE id = %s
        """, (pausa['id'],))
        
        # Buscar duração atualizada
        pausa_atualizada = db.fetch_one("SELECT duracao_minutos FROM producao_pausas WHERE id = %s", (pausa['id'],))
        
        return jsonify({
            'success': True, 
            'message': f'Produção retomada após {pausa_atualizada["duracao_minutos"]} minutos',
            'duracao_minutos': pausa_atualizada['duracao_minutos'],
            'motivo': pausa['motivo_nome'],
            'tipo': pausa['tipo']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@producao_pausas_bp.route('/api/pausar-ou-trocar', methods=['POST'])
@login_required
def api_pausar_ou_trocar():
    """
    Pausa o lote OU troca o motivo se já estiver pausado.
    Usado pelo "Pausar Todos" para garantir que todos fiquem com o mesmo motivo.
    """
    db = get_db()
    user_id = session.get('user_id')
    
    data = request.get_json() or request.form
    lote_id = data.get('lote_id')
    motivo_id = data.get('motivo_id')
    observacao = data.get('observacao', '')
    
    if not lote_id or not motivo_id:
        return jsonify({'success': False, 'error': 'Lote e motivo são obrigatórios'}), 400
    
    try:
        # Buscar lote
        lote = db.fetch_one("""
            SELECT l.*, op.id AS op_id FROM op_lotes l
            INNER JOIN ordens_producao op ON op.id = l.ordem_producao_id
            WHERE l.id = %s
        """, (lote_id,))
        
        if not lote:
            return jsonify({'success': False, 'error': 'Lote não encontrado'}), 404
        
        # Verificar se já está pausado
        pausa_ativa = db.fetch_one("""
            SELECT id, motivo_id FROM producao_pausas 
            WHERE lote_id = %s AND fim IS NULL
        """, (lote_id,))
        
        if pausa_ativa:
            # Já pausado - verificar se é o mesmo motivo
            if str(pausa_ativa['motivo_id']) == str(motivo_id):
                # Mesmo motivo, não precisa fazer nada
                motivo = db.fetch_one("SELECT nome, tipo FROM producao_pausas_motivos WHERE id = %s", (motivo_id,))
                return jsonify({
                    'success': True, 
                    'message': f'Lote já pausado - {motivo["nome"]}',
                    'acao': 'mantido',
                    'tipo': motivo['tipo']
                })
            
            # Motivo diferente - encerrar pausa atual e criar nova
            db.update("""
                UPDATE producao_pausas 
                SET fim = NOW(),
                    duracao_minutos = TIMESTAMPDIFF(MINUTE, inicio, NOW()),
                    observacao = CONCAT(COALESCE(observacao, ''), ' [Trocado para outro motivo]')
                WHERE id = %s
            """, (pausa_ativa['id'],))
            
            # Criar nova pausa com novo motivo
            pausa_id = db.insert("""
                INSERT INTO producao_pausas 
                (lote_id, ordem_producao_id, operador_id, motivo_id, etapa_id, inicio, observacao)
                VALUES (%s, %s, %s, %s, %s, NOW(), %s)
            """, (lote_id, lote['ordem_producao_id'], user_id, motivo_id, 
                  lote.get('etapa_atual_id'), observacao))
            
            motivo = db.fetch_one("SELECT nome, tipo FROM producao_pausas_motivos WHERE id = %s", (motivo_id,))
            return jsonify({
                'success': True, 
                'message': f'Motivo alterado para {motivo["nome"]}',
                'pausa_id': pausa_id,
                'acao': 'trocado',
                'tipo': motivo['tipo']
            })
        
        # Não pausado - criar nova pausa
        pausa_id = db.insert("""
            INSERT INTO producao_pausas 
            (lote_id, ordem_producao_id, operador_id, motivo_id, etapa_id, inicio, observacao)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
        """, (lote_id, lote['ordem_producao_id'], user_id, motivo_id, 
              lote.get('etapa_atual_id'), observacao))
        
        motivo = db.fetch_one("SELECT nome, tipo FROM producao_pausas_motivos WHERE id = %s", (motivo_id,))
        return jsonify({
            'success': True, 
            'message': f'Lote pausado - {motivo["nome"]}',
            'pausa_id': pausa_id,
            'acao': 'pausado',
            'tipo': motivo['tipo']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@producao_pausas_bp.route('/api/status/<int:lote_id>')
@login_required
def api_status_pausa(lote_id):
    """Verifica se o lote está pausado"""
    db = get_db()
    
    pausa = db.fetch_one("""
        SELECT p.*, m.nome AS motivo_nome, m.tipo, m.icone, m.cor_hex
        FROM producao_pausas p
        INNER JOIN producao_pausas_motivos m ON m.id = p.motivo_id
        WHERE p.lote_id = %s AND p.fim IS NULL
    """, (lote_id,))
    
    if pausa:
        return jsonify({
            'pausado': True,
            'pausa_id': pausa['id'],
            'motivo': pausa['motivo_nome'],
            'tipo': pausa['tipo'],
            'icone': pausa['icone'],
            'cor': pausa['cor_hex'],
            'inicio': pausa['inicio'].isoformat() if pausa['inicio'] else None
        })
    
    return jsonify({'pausado': False})
