"""
Rotas para o sistema Kardex de Estoque.
Visualização do histórico completo de movimentações.
"""

from flask import Blueprint, render_template, request, jsonify, session
from database import get_db
from utils.auth import login_required

kardex_bp = Blueprint('kardex', __name__, url_prefix='/kardex')




@kardex_bp.route('/')
@login_required
def kardex_index():
    """Página principal do Kardex - lista de produtos com movimentações."""
    db = get_db()
    
    # Filtros
    search = request.args.get('search', '')
    categoria_id = request.args.get('categoria_id', '')
    empresa_id = request.args.get('empresa_id', session.get('empresa_id', ''))
    
    # Buscar empresas para filtro
    empresas = db.fetch_all("""
        SELECT id, COALESCE(nome_fantasia, razao_social) AS nome 
        FROM empresas WHERE ativo = 1 ORDER BY nome
    """) or []
    
    # Buscar produtos com resumo de movimentações (filtrado por empresa)
    query = """
        SELECT 
            p.id,
            p.name AS produto_nome,
            p.internal_code AS codigo,
            p.barcode,
            COALESCE(ee.quantidade, p.stock_quantity, 0) AS estoque_atual,
            c.name AS categoria_nome,
            (SELECT COUNT(*) FROM estoque_movimentacoes em 
             WHERE em.produto_id = p.id AND (em.empresa_id = %s OR %s = '')) AS total_movimentacoes,
            (SELECT MAX(created_at) FROM estoque_movimentacoes em 
             WHERE em.produto_id = p.id AND (em.empresa_id = %s OR %s = '')) AS ultima_movimentacao
        FROM products p
        LEFT JOIN product_categories c ON c.id = p.category_id
        LEFT JOIN estoque_empresa ee ON ee.produto_id = p.id AND ee.empresa_id = %s AND ee.local_id = 1
        WHERE p.active = 1
    """
    params = [empresa_id, empresa_id, empresa_id, empresa_id, empresa_id if empresa_id else 1]
    
    if search:
        query += " AND (p.name LIKE %s OR p.internal_code LIKE %s OR p.barcode LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    if categoria_id:
        query += " AND p.category_id = %s"
        params.append(categoria_id)
    
    query += " ORDER BY p.name LIMIT 100"
    
    produtos = db.fetch_all(query, tuple(params)) or []
    
    # Buscar categorias para filtro
    categorias = db.fetch_all("""
        SELECT id, name FROM product_categories WHERE active = 1 ORDER BY name
    """) or []
    
    return render_template(
        'kardex_index.html',
        produtos=produtos,
        categorias=categorias,
        empresas=empresas,
        search=search,
        categoria_id=categoria_id,
        empresa_id=empresa_id,
        active_page='kardex'
    )


@kardex_bp.route('/produto/<int:produto_id>')
@login_required
def kardex_produto(produto_id):
    """Kardex detalhado de um produto específico."""
    db = get_db()
    
    # Filtros
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    tipo = request.args.get('tipo', '')
    empresa_id = request.args.get('empresa_id', session.get('empresa_id', ''))
    
    # Buscar empresas para filtro
    empresas = db.fetch_all("""
        SELECT id, COALESCE(nome_fantasia, razao_social) AS nome 
        FROM empresas WHERE ativo = 1 ORDER BY nome
    """) or []
    
    # Buscar dados do produto (com estoque da empresa selecionada)
    produto = db.fetch_one("""
        SELECT 
            p.id,
            p.name AS produto_nome,
            p.internal_code AS codigo,
            p.barcode,
            p.unit_measure AS unidade,
            COALESCE(ee.quantidade, p.stock_quantity, 0) AS estoque_atual,
            p.cost_price AS custo,
            p.price AS preco_venda,
            c.name AS categoria_nome
        FROM products p
        LEFT JOIN product_categories c ON c.id = p.category_id
        LEFT JOIN estoque_empresa ee ON ee.produto_id = p.id AND ee.empresa_id = %s AND ee.local_id = 1
        WHERE p.id = %s
    """, (empresa_id if empresa_id else 1, produto_id,))
    
    if not produto:
        return "Produto não encontrado", 404
    
    # Buscar movimentações (filtrado por empresa)
    query = """
        SELECT 
            em.id,
            em.empresa_id,
            e.nome_fantasia AS empresa_nome,
            em.tipo,
            CASE em.tipo
                WHEN 'entrada' THEN 'Entrada'
                WHEN 'saida' THEN 'Saída'
                WHEN 'ajuste_positivo' THEN 'Ajuste (+)'
                WHEN 'ajuste_negativo' THEN 'Ajuste (-)'
                WHEN 'reserva' THEN 'Reserva'
                WHEN 'liberacao_reserva' THEN 'Liberação Reserva'
                WHEN 'baixa_producao' THEN 'Baixa Produção'
                WHEN 'entrada_producao' THEN 'Entrada Produção'
                WHEN 'venda' THEN 'Venda'
                WHEN 'devolucao' THEN 'Devolução'
                WHEN 'transferencia' THEN 'Transferência'
                ELSE em.tipo
            END AS tipo_descricao,
            em.quantidade,
            em.estoque_anterior,
            em.estoque_posterior,
            em.origem_tela,
            em.referencia_tipo,
            em.referencia_id,
            em.referencia_codigo,
            em.custo_unitario,
            em.valor_total,
            em.observacao,
            em.usuario_nome,
            em.created_at
        FROM estoque_movimentacoes em
        LEFT JOIN empresas e ON e.id = em.empresa_id
        WHERE em.produto_id = %s
    """
    params = [produto_id]
    
    if empresa_id:
        query += " AND em.empresa_id = %s"
        params.append(empresa_id)
    
    if data_inicio:
        query += " AND DATE(em.created_at) >= %s"
        params.append(data_inicio)
    
    if data_fim:
        query += " AND DATE(em.created_at) <= %s"
        params.append(data_fim)
    
    if tipo:
        query += " AND em.tipo = %s"
        params.append(tipo)
    
    query += " ORDER BY em.created_at DESC LIMIT 500"
    
    movimentacoes = db.fetch_all(query, tuple(params)) or []
    
    # Calcular totais (filtrado por empresa)
    totais_query = """
        SELECT 
            COALESCE(SUM(CASE WHEN tipo IN ('entrada', 'ajuste_positivo', 'entrada_producao', 'devolucao', 'liberacao_reserva') 
                         THEN quantidade ELSE 0 END), 0) AS total_entradas,
            COALESCE(SUM(CASE WHEN tipo IN ('saida', 'ajuste_negativo', 'baixa_producao', 'venda', 'reserva', 'transferencia') 
                         THEN quantidade ELSE 0 END), 0) AS total_saidas,
            COUNT(*) AS total_movimentacoes
        FROM estoque_movimentacoes
        WHERE produto_id = %s
    """
    totais_params = [produto_id]
    
    if empresa_id:
        totais_query += " AND empresa_id = %s"
        totais_params.append(empresa_id)
    
    totais = db.fetch_one(totais_query, tuple(totais_params))
    
    return render_template(
        'kardex_produto.html',
        produto=produto,
        movimentacoes=movimentacoes,
        totais=totais,
        empresas=empresas,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipo_filtro=tipo,
        empresa_id=empresa_id,
        active_page='kardex'
    )


@kardex_bp.route('/api/movimentacoes/<int:produto_id>')
@login_required
def api_movimentacoes(produto_id):
    """API para buscar movimentações de um produto."""
    db = get_db()
    
    limite = request.args.get('limite', 100, type=int)
    
    movimentacoes = db.fetch_all("""
        SELECT 
            em.id,
            em.tipo,
            em.quantidade,
            em.estoque_anterior,
            em.estoque_posterior,
            em.origem_tela,
            em.referencia_tipo,
            em.referencia_codigo,
            em.observacao,
            em.usuario_nome,
            em.created_at
        FROM estoque_movimentacoes em
        WHERE em.produto_id = %s
        ORDER BY em.created_at DESC
        LIMIT %s
    """, (produto_id, limite)) or []
    
    return jsonify({'success': True, 'movimentacoes': movimentacoes})


@kardex_bp.route('/relatorio')
@login_required
def kardex_relatorio():
    """Relatório geral de movimentações de estoque."""
    db = get_db()
    
    # Filtros
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    tipo = request.args.get('tipo', '')
    origem = request.args.get('origem', '')
    empresa_id = request.args.get('empresa_id', session.get('empresa_id', ''))
    
    # Buscar empresas para filtro
    empresas = db.fetch_all("""
        SELECT id, COALESCE(nome_fantasia, razao_social) AS nome 
        FROM empresas WHERE ativo = 1 ORDER BY nome
    """) or []
    
    # Buscar movimentações (filtrado por empresa)
    query = """
        SELECT 
            em.id,
            em.empresa_id,
            e.nome_fantasia AS empresa_nome,
            p.name AS produto_nome,
            p.internal_code AS produto_codigo,
            em.tipo,
            CASE em.tipo
                WHEN 'entrada' THEN 'Entrada'
                WHEN 'saida' THEN 'Saída'
                WHEN 'ajuste_positivo' THEN 'Ajuste (+)'
                WHEN 'ajuste_negativo' THEN 'Ajuste (-)'
                WHEN 'reserva' THEN 'Reserva'
                WHEN 'liberacao_reserva' THEN 'Liberação Reserva'
                WHEN 'baixa_producao' THEN 'Baixa Produção'
                WHEN 'entrada_producao' THEN 'Entrada Produção'
                WHEN 'venda' THEN 'Venda'
                WHEN 'devolucao' THEN 'Devolução'
                WHEN 'transferencia' THEN 'Transferência'
                ELSE em.tipo
            END AS tipo_descricao,
            em.quantidade,
            em.estoque_anterior,
            em.estoque_posterior,
            em.origem_tela,
            em.referencia_tipo,
            em.referencia_codigo,
            em.observacao,
            em.usuario_nome,
            em.created_at
        FROM estoque_movimentacoes em
        JOIN products p ON p.id = em.produto_id
        LEFT JOIN empresas e ON e.id = em.empresa_id
        WHERE 1=1
    """
    params = []
    
    if empresa_id:
        query += " AND em.empresa_id = %s"
        params.append(empresa_id)
    
    if data_inicio:
        query += " AND DATE(em.created_at) >= %s"
        params.append(data_inicio)
    
    if data_fim:
        query += " AND DATE(em.created_at) <= %s"
        params.append(data_fim)
    
    if tipo:
        query += " AND em.tipo = %s"
        params.append(tipo)
    
    if origem:
        query += " AND em.origem_tela = %s"
        params.append(origem)
    
    query += " ORDER BY em.created_at DESC LIMIT 500"
    
    movimentacoes = db.fetch_all(query, tuple(params)) or []
    
    # Buscar origens distintas para filtro
    origens = db.fetch_all("""
        SELECT DISTINCT origem_tela FROM estoque_movimentacoes 
        WHERE origem_tela IS NOT NULL ORDER BY origem_tela
    """) or []
    
    return render_template(
        'kardex_relatorio.html',
        movimentacoes=movimentacoes,
        origens=origens,
        empresas=empresas,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipo_filtro=tipo,
        origem_filtro=origem,
        empresa_id=empresa_id,
        active_page='kardex'
    )
