# -*- coding: utf-8 -*-
"""
Rotas para gerenciamento de Listas de Preço
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from database import get_db
from utils.auth import login_required

# Blueprint
lista_preco_bp = Blueprint('lista_preco', __name__)



# =====================================================
# LISTAGEM
# =====================================================
@lista_preco_bp.route('/listas-preco')
@login_required
def lista():
    """Lista todas as listas de preço"""
    db = get_db()
    
    listas = db.fetch_all("""
        SELECT lp.*, 
               (SELECT COUNT(*) FROM lista_preco_itens WHERE lista_preco_id = lp.id) AS qtd_produtos,
               u.name AS criado_por
        FROM listas_preco lp
        LEFT JOIN users u ON lp.created_by = u.id
        ORDER BY lp.prioridade, lp.nome
    """)
    
    return render_template('lista_preco_list.html',
        listas=listas or [],
        active_page='listas_preco'
    )


# =====================================================
# CADASTRAR
# =====================================================
@lista_preco_bp.route('/listas-preco/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar():
    """Cadastra nova lista de preço"""
    db = get_db()
    
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        codigo = request.form.get('codigo', '').strip().upper()
        descricao = request.form.get('descricao', '').strip()
        tipo = request.form.get('tipo', 'fixo')
        percentual_padrao = request.form.get('percentual_padrao', '0') or '0'
        prioridade = request.form.get('prioridade', '0') or '0'
        data_inicio = request.form.get('data_inicio') or None
        data_fim = request.form.get('data_fim') or None
        ativo = 1 if request.form.get('ativo') else 0
        
        # Validações
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return render_template('lista_preco_form.html', lista=None, active_page='listas_preco')
        
        if not codigo:
            codigo = nome.upper().replace(' ', '_')[:20]
        
        # Verificar código duplicado
        existente = db.fetch_one("SELECT id FROM listas_preco WHERE codigo = %s", [codigo])
        if existente:
            flash(f'Código "{codigo}" já está em uso.', 'danger')
            return render_template('lista_preco_form.html', lista=None, active_page='listas_preco')
        
        try:
            db.execute_query("""
                INSERT INTO listas_preco 
                (nome, codigo, descricao, tipo, percentual_padrao, prioridade, data_inicio, data_fim, ativo, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                nome, codigo, descricao, tipo, 
                float(percentual_padrao.replace(',', '.')), 
                int(prioridade),
                data_inicio, data_fim, ativo,
                session.get('user_id')
            ])
            
            flash(f'Lista de Preço "{nome}" criada com sucesso!', 'success')
            nova = db.fetch_one("SELECT id FROM listas_preco WHERE codigo = %s ORDER BY id DESC LIMIT 1", [codigo])
            if nova and nova.get('id'):
                return redirect(url_for('lista_preco.gerenciar_precos', id=nova['id']))
            return redirect(url_for('lista_preco.lista'))
        except Exception as e:
            flash(f'Erro ao criar lista: {str(e)}', 'danger')
    
    return render_template('lista_preco_form.html', lista=None, active_page='listas_preco')


# =====================================================
# EDITAR
# =====================================================
@lista_preco_bp.route('/listas-preco/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Edita lista de preço existente"""
    db = get_db()
    
    lista = db.fetch_one("SELECT * FROM listas_preco WHERE id = %s", [id])
    if not lista:
        flash('Lista não encontrada.', 'danger')
        return redirect(url_for('lista_preco.lista'))
    
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        codigo = request.form.get('codigo', '').strip().upper()
        descricao = request.form.get('descricao', '').strip()
        tipo = request.form.get('tipo', 'fixo')
        percentual_padrao = request.form.get('percentual_padrao', '0') or '0'
        prioridade = request.form.get('prioridade', '0') or '0'
        data_inicio = request.form.get('data_inicio') or None
        data_fim = request.form.get('data_fim') or None
        ativo = 1 if request.form.get('ativo') else 0
        
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return render_template('lista_preco_form.html', lista=lista, active_page='listas_preco')
        
        # Verificar código duplicado (exceto próprio)
        existente = db.fetch_one("SELECT id FROM listas_preco WHERE codigo = %s AND id != %s", [codigo, id])
        if existente:
            flash(f'Código "{codigo}" já está em uso.', 'danger')
            return render_template('lista_preco_form.html', lista=lista, active_page='listas_preco')
        
        try:
            percentual_padrao_val = float(str(percentual_padrao).replace(',', '.'))
            cursor = db.execute_query("""
                UPDATE listas_preco SET
                    nome = %s, codigo = %s, descricao = %s, tipo = %s,
                    percentual_padrao = %s, prioridade = %s,
                    data_inicio = %s, data_fim = %s, ativo = %s
                WHERE id = %s
            """, [
                nome, codigo, descricao, tipo,
                percentual_padrao_val,
                int(prioridade),
                data_inicio, data_fim, ativo, id
            ])

            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass

            try:
                if getattr(db, 'connection', None):
                    db.connection.commit()
            except Exception:
                pass

            lista = db.fetch_one("SELECT * FROM listas_preco WHERE id = %s", [id])

            try:
                updated_percentual = float((lista or {}).get('percentual_padrao') or 0)
                if abs(updated_percentual - float(percentual_padrao_val)) > 0.001:
                    print(
                        f"[LISTA_PRECO] Percentual não refletiu no banco: enviado={percentual_padrao_val} lido={updated_percentual} id={id}"
                    )
            except Exception as _e:
                pass
            
            flash(f'Lista de Preço atualizada com sucesso!', 'success')
            return redirect(url_for('lista_preco.gerenciar_precos', id=id))
        except Exception as e:
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
    
    return render_template('lista_preco_form.html', lista=lista, active_page='listas_preco')


# =====================================================
# GERENCIAR PREÇOS (produtos da lista)
# =====================================================
@lista_preco_bp.route('/listas-preco/<int:id>/precos', methods=['GET', 'POST'])
@login_required
def gerenciar_precos(id):
    """Gerencia os preços dos produtos na lista"""
    db = get_db()
    
    lista = db.fetch_one("SELECT * FROM listas_preco WHERE id = %s", [id])
    if not lista:
        flash('Lista não encontrada.', 'danger')
        return redirect(url_for('lista_preco.lista'))
    
    if request.method == 'POST':
        # Salvar preços em lote
        produtos = request.form.getlist('produto_id[]')
        precos_finais = request.form.getlist('preco_final[]')
        percentuais_lista = request.form.getlist('percentual_lista[]')
        markups_lista = request.form.getlist('markup_percent[]')

        def _parse_float(value, default=None):
            if value is None:
                return default
            s = str(value).strip()
            if not s:
                return default
            try:
                return float(s.replace(',', '.'))
            except (ValueError, TypeError):
                return default
        
        for i, produto_id in enumerate(produtos):
            if not produto_id:
                continue

            preco_final_raw = precos_finais[i] if i < len(precos_finais) else None
            percentual_raw = percentuais_lista[i] if i < len(percentuais_lista) else None
            markup_raw = markups_lista[i] if i < len(markups_lista) else None

            preco_final_val = _parse_float(preco_final_raw, default=None)
            percentual_val = _parse_float(percentual_raw, default=None)
            markup_val = _parse_float(markup_raw, default=None)

            has_any_value = any(v is not None for v in (preco_final_val, percentual_val, markup_val))
            if not has_any_value:
                continue

            produto = db.fetch_one(
                "SELECT price, cost_price FROM products WHERE id = %s",
                [produto_id],
            )
            preco_padrao = float((produto or {}).get('price') or 0)
            preco_custo = float((produto or {}).get('cost_price') or 0)

            # Normalização: alguns cadastros podem estar com custo e venda invertidos
            if preco_padrao > 0 and preco_custo > preco_padrao:
                preco_padrao, preco_custo = preco_custo, preco_padrao

            tipo = (lista.get('tipo') or 'fixo') if lista else 'fixo'

            if preco_final_val is None:
                if markup_val is not None and preco_custo > 0:
                    preco_final_val = max(0.0, preco_custo * (1.0 + (markup_val / 100.0)))
                elif percentual_val is not None:
                    if tipo == 'desconto':
                        preco_final_val = max(0.0, preco_padrao * (1.0 - (percentual_val / 100.0)))
                    elif tipo == 'markup':
                        base = preco_custo if preco_custo > 0 else preco_padrao
                        preco_final_val = max(0.0, base * (1.0 + (percentual_val / 100.0)))
                    else:
                        preco_final_val = max(0.0, preco_padrao * (1.0 + (percentual_val / 100.0)))

            if preco_final_val is None:
                item_existente = db.fetch_one(
                    """
                    SELECT preco
                    FROM lista_preco_itens
                    WHERE lista_preco_id = %s AND produto_id = %s
                    """,
                    [id, produto_id],
                )
                if item_existente and item_existente.get('preco') is not None:
                    preco_final_val = float(item_existente['preco'])
                else:
                    preco_final_val = preco_padrao

            db.execute_query(
                """
                INSERT INTO lista_preco_itens (lista_preco_id, produto_id, preco, preco_minimo, desconto_maximo)
                VALUES (%s, %s, %s, NULL, 0)
                ON DUPLICATE KEY UPDATE
                    preco = VALUES(preco),
                    preco_minimo = NULL,
                    desconto_maximo = 0
                """,
                [id, produto_id, preco_final_val],
            )
        
        flash('Preços atualizados com sucesso!', 'success')
        return redirect(url_for('lista_preco.gerenciar_precos', id=id))
    
    # Buscar produtos com preços da lista
    itens = db.fetch_all("""
        SELECT p.id, p.internal_code, p.name, p.unit_measure AS unit,
               p.cost_price AS preco_custo,
               p.price AS preco_padrao,
               lpi.preco, lpi.preco_minimo, lpi.desconto_maximo
        FROM products p
        LEFT JOIN lista_preco_itens lpi ON p.id = lpi.produto_id AND lpi.lista_preco_id = %s
        WHERE p.active = 1
        ORDER BY p.name
        LIMIT 500
    """, [id])

    tipo = (lista.get('tipo') or 'fixo') if lista else 'fixo'
    percentual_padrao = float(lista.get('percentual_padrao') or 0) if lista else 0.0

    itens_calc = []
    for item in (itens or []):
        preco_padrao = float(item.get('preco_padrao') or 0)
        preco_custo = float(item.get('preco_custo') or 0)

        # Normalização: alguns cadastros podem estar com custo e venda invertidos
        if preco_padrao > 0 and preco_custo > preco_padrao:
            preco_padrao, preco_custo = preco_custo, preco_padrao

        # Aplicar valores normalizados no item (garante exibição/JS corretos)
        item['preco_padrao'] = preco_padrao
        item['preco_custo'] = preco_custo
        preco_lista_db = item.get('preco')
        preco_lista_db = float(preco_lista_db) if preco_lista_db is not None else None
        preco_minimo = item.get('preco_minimo')
        preco_minimo = float(preco_minimo) if preco_minimo is not None else None
        desc_max = item.get('desconto_maximo')
        desc_max = float(desc_max) if desc_max is not None else 0.0

        # Novo comportamento: lpi.preco é o preço final efetivo da lista.
        # Se ainda não existir, usamos o percentual padrão da lista só como base para sugestão.
        percentual_aplicado = 0.0
        preco_lista_efetivo = preco_lista_db

        if preco_lista_efetivo is None:
            if tipo == 'desconto':
                percentual_aplicado = percentual_padrao
                preco_lista_efetivo = max(0.0, preco_padrao * (1.0 - (percentual_padrao / 100.0)))
            elif tipo == 'markup':
                percentual_aplicado = percentual_padrao
                base = preco_custo if preco_custo > 0 else preco_padrao
                preco_lista_efetivo = max(0.0, base * (1.0 + (percentual_padrao / 100.0)))
            else:
                preco_lista_efetivo = preco_padrao
        else:
            # Quando existe preço salvo, deduzir a % aplicada apenas para exibição
            if tipo == 'desconto' and preco_padrao > 0:
                percentual_aplicado = max(0.0, (1.0 - (preco_lista_efetivo / preco_padrao)) * 100.0)
            elif tipo == 'markup':
                base = preco_custo if preco_custo > 0 else preco_padrao
                if base > 0:
                    percentual_aplicado = max(0.0, ((preco_lista_efetivo / base) - 1.0) * 100.0)

        # Na nova tela, "Preço c/ Desc." é o preço final efetivo da lista
        preco_com_desconto = preco_lista_efetivo

        markup_percent = None
        if preco_custo > 0:
            markup_percent = ((preco_lista_efetivo - preco_custo) / preco_custo) * 100.0

        item['preco_custo'] = preco_custo
        item['preco_lista_efetivo'] = preco_lista_efetivo
        item['preco_com_desconto'] = preco_com_desconto
        item['percentual_aplicado'] = percentual_aplicado
        item['markup_percent'] = markup_percent
        itens_calc.append(item)

    itens_calc.sort(key=lambda x: (x['markup_percent'] is None, x['markup_percent'] if x['markup_percent'] is not None else 0))
    
    return render_template('lista_preco_precos.html',
        lista=lista,
        itens=itens_calc or [],
        active_page='listas_preco'
    )


# =====================================================
# EXCLUIR
# =====================================================
@lista_preco_bp.route('/listas-preco/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    """Exclui uma lista de preço"""
    db = get_db()
    
    try:
        db.execute_query("DELETE FROM listas_preco WHERE id = %s", [id])
        flash('Lista de Preço excluída com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir: {str(e)}', 'danger')
    
    return redirect(url_for('lista_preco.lista'))


# =====================================================
# API - Buscar preço do produto por lista
# =====================================================
@lista_preco_bp.route('/api/preco-produto')
@login_required
def api_preco_produto():
    """Retorna o preço de um produto em uma lista específica"""
    produto_id = request.args.get('produto_id')
    lista_id = request.args.get('lista_id')
    
    if not produto_id:
        return jsonify({'error': 'Produto não informado'}), 400
    
    db = get_db()
    
    # Buscar preço padrão do produto
    produto = db.fetch_one("SELECT price, cost_price FROM products WHERE id = %s", [produto_id])
    if not produto:
        return jsonify({'error': 'Produto não encontrado'}), 404
    
    preco_padrao = float(produto['price'] or 0)
    custo = float(produto['cost_price'] or 0)
    
    # Se não informou lista, retorna preço padrão do produto
    if not lista_id:
        return jsonify({'preco': preco_padrao, 'lista': 'padrao', 'preco_original': preco_padrao})
    
    # Buscar dados da lista
    lista = db.fetch_one("""
        SELECT id, nome, tipo, percentual_padrao 
        FROM listas_preco 
        WHERE id = %s AND ativo = TRUE
    """, [lista_id])
    
    if not lista:
        return jsonify({'preco': preco_padrao, 'lista': 'padrao', 'preco_original': preco_padrao})
    
    # Buscar preço específico do produto na lista (se cadastrado)
    item = db.fetch_one("""
        SELECT preco, preco_minimo, desconto_maximo
        FROM lista_preco_itens
        WHERE produto_id = %s AND lista_preco_id = %s AND ativo = TRUE
    """, [produto_id, lista_id])
    
    # Se tem preço específico cadastrado, usa ele
    if item and item['preco']:
        return jsonify({
            'preco': float(item['preco']),
            'preco_minimo': float(item['preco_minimo']) if item['preco_minimo'] else None,
            'desconto_maximo': float(item['desconto_maximo']) if item['desconto_maximo'] else None,
            'lista': lista['nome'],
            'preco_original': preco_padrao
        })
    
    # Calcular preço baseado no tipo da lista e percentual padrão
    percentual = float(lista['percentual_padrao'] or 0)
    tipo = lista['tipo']
    
    if tipo == 'desconto' and percentual > 0:
        # Aplica desconto sobre o preço de venda
        preco_calculado = preco_padrao * (1 - percentual / 100)
    elif tipo == 'markup' and percentual > 0:
        # Aplica markup sobre o custo
        preco_calculado = custo * (1 + percentual / 100)
    else:
        # Tipo fixo ou sem percentual - usa preço padrão
        preco_calculado = preco_padrao
    
    return jsonify({
        'preco': round(preco_calculado, 2),
        'lista': lista['nome'],
        'tipo': tipo,
        'percentual': percentual,
        'preco_original': preco_padrao
    })
