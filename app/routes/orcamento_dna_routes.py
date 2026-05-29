"""
API para Busca de Estoque com DNA Similar e Geração de OP no Orçamento
"""

from flask import Blueprint, request, jsonify, session
from decimal import Decimal
from datetime import datetime, timedelta

try:
    from database import get_db
    from utils.auth import login_required
except ImportError:
    from app.database import get_db
    from functools import wraps
    
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return jsonify({'error': 'Não autorizado'}), 401
            return f(*args, **kwargs)
        return decorated_function

orcamento_dna_bp = Blueprint('orcamento_dna', __name__, url_prefix='/api/orcamento')


@orcamento_dna_bp.route('/buscar-estoque-dna/<int:produto_id>', methods=['GET'])
@login_required
def buscar_estoque_dna(produto_id):
    """
    Busca produtos no estoque com DNA similar ao produto solicitado.
    Retorna opções de alocação de estoque existente.
    """
    db = get_db()
    
    quantidade = request.args.get('quantidade', 1, type=float)
    largura = request.args.get('largura', 0, type=float)
    comprimento = request.args.get('comprimento', 0, type=float)
    
    # Buscar especificação do produto solicitado
    especificacao = db.fetch_one("""
        SELECT 
            pet.*,
            tc.codigo AS tipo_codigo,
            tc.nome AS tipo_nome,
            mc.codigo AS material_codigo,
            mc.nome AS material_nome
        FROM produto_especificacoes_tecnicas pet
        LEFT JOIN tipos_correia tc ON tc.id = pet.tipo_correia_id
        LEFT JOIN materiais_correia mc ON mc.id = pet.material_base_id
        WHERE pet.produto_id = %s
    """, (produto_id,))
    
    if not especificacao:
        return jsonify({
            'success': False,
            'message': 'Produto não possui especificações técnicas (DNA)',
            'estoque_similar': [],
            'pode_produzir': True
        })
    
    # Usar dimensões do parâmetro ou da especificação
    largura_busca = largura if largura > 0 else (especificacao.get('largura_mm') or 0)
    comprimento_busca = comprimento if comprimento > 0 else (especificacao.get('comprimento_mm') or 0)
    
    # Buscar produtos com DNA similar no estoque (usa products.stock_quantity como fonte única)
    estoque_similar = db.fetch_all("""
        SELECT 
            p.id AS produto_id,
            p.name AS produto_nome,
            p.internal_code AS produto_codigo,
            p.price AS preco_unitario,
            pet.codigo_dna,
            pet.largura_mm,
            pet.comprimento_mm,
            pet.espessura_mm,
            COALESCE(p.stock_quantity, 0) AS estoque_total,
            COALESCE(
                (SELECT SUM(er.quantidade) 
                 FROM estoque_reservas er 
                 WHERE er.produto_id = p.id AND er.status IN ('ativo', 'confirmado')), 
                0
            ) AS estoque_reservado,
            COALESCE(p.stock_quantity, 0) - COALESCE(
                (SELECT SUM(er.quantidade) 
                 FROM estoque_reservas er 
                 WHERE er.produto_id = p.id AND er.status IN ('ativo', 'confirmado')), 
                0
            ) AS estoque_disponivel,
            tc.nome AS tipo_nome,
            mc.nome AS material_nome
        FROM products p
        INNER JOIN produto_especificacoes_tecnicas pet ON pet.produto_id = p.id
        LEFT JOIN tipos_correia tc ON tc.id = pet.tipo_correia_id
        LEFT JOIN materiais_correia mc ON mc.id = pet.material_base_id
        WHERE p.active = 1
          AND p.id != %s
          AND COALESCE(p.stock_quantity, 0) > 0
          AND pet.codigo_dna IS NOT NULL
          AND (
              -- Match por tipo e material (mesmo DNA base)
              (pet.tipo_correia_id = %s AND pet.material_base_id = %s)
              OR
              -- Match exato de DNA
              pet.codigo_dna = %s
          )
        ORDER BY 
            -- Prioridade 1: DNA exato
            CASE WHEN pet.codigo_dna = %s THEN 0 ELSE 1 END,
            -- Prioridade 2: Dimensões compatíveis (podem derivar)
            CASE WHEN pet.largura_mm >= %s AND pet.comprimento_mm >= %s THEN 0 ELSE 1 END,
            -- Prioridade 3: Proximidade de dimensões
            ABS(COALESCE(pet.largura_mm, 0) - %s) + ABS(COALESCE(pet.comprimento_mm, 0) - %s),
            -- Prioridade 4: Maior estoque disponível
            COALESCE(p.stock_quantity, 0) DESC
        LIMIT 10
    """, (
        produto_id,
        especificacao.get('tipo_correia_id'),
        especificacao.get('material_base_id'),
        especificacao.get('codigo_dna'),
        especificacao.get('codigo_dna'),
        largura_busca, comprimento_busca,
        largura_busca, comprimento_busca
    ))
    
    # Processar resultados
    resultado = []
    quantidade_restante = quantidade
    
    for item in (estoque_similar or []):
        estoque_disp = float(item['estoque_disponivel'] or 0)
        if estoque_disp <= 0:
            continue
            
        # Determinar tipo de match
        is_dna_exato = item['codigo_dna'] == especificacao.get('codigo_dna')
        largura_ok = (item['largura_mm'] or 0) >= largura_busca
        comprimento_ok = (item['comprimento_mm'] or 0) >= comprimento_busca
        
        if is_dna_exato and largura_ok and comprimento_ok:
            tipo_match = 'EXATO'
        elif largura_ok and comprimento_ok:
            tipo_match = 'DERIVAVEL'
        else:
            tipo_match = 'PARCIAL'
        
        # Quantidade que pode ser alocada deste item
        qtd_alocar = min(estoque_disp, quantidade_restante)
        
        resultado.append({
            'produto_id': item['produto_id'],
            'produto_nome': item['produto_nome'],
            'produto_codigo': item['produto_codigo'],
            'preco_unitario': float(item['preco_unitario'] or 0),
            'codigo_dna': item['codigo_dna'],
            'largura_mm': float(item['largura_mm'] or 0),
            'comprimento_mm': float(item['comprimento_mm'] or 0),
            'espessura_mm': float(item['espessura_mm'] or 0),
            'estoque_disponivel': estoque_disp,
            'tipo_match': tipo_match,
            'tipo_nome': item['tipo_nome'],
            'material_nome': item['material_nome'],
            'quantidade_sugerida': qtd_alocar,
            'pode_atender_total': estoque_disp >= quantidade
        })
        
        if tipo_match in ['EXATO', 'DERIVAVEL']:
            quantidade_restante -= qtd_alocar
            if quantidade_restante <= 0:
                break
    
    return jsonify({
        'success': True,
        'produto_solicitado': {
            'id': produto_id,
            'codigo_dna': especificacao.get('codigo_dna'),
            'largura_mm': float(especificacao.get('largura_mm') or 0),
            'comprimento_mm': float(especificacao.get('comprimento_mm') or 0),
            'tipo_nome': especificacao.get('tipo_nome'),
            'material_nome': especificacao.get('material_nome')
        },
        'quantidade_solicitada': quantidade,
        'estoque_similar': resultado,
        'quantidade_disponivel_total': sum(r['quantidade_sugerida'] for r in resultado if r['tipo_match'] in ['EXATO', 'DERIVAVEL']),
        'quantidade_a_produzir': max(0, quantidade - sum(r['quantidade_sugerida'] for r in resultado if r['tipo_match'] in ['EXATO', 'DERIVAVEL'])),
        'pode_atender_do_estoque': any(r['pode_atender_total'] and r['tipo_match'] in ['EXATO', 'DERIVAVEL'] for r in resultado)
    })


@orcamento_dna_bp.route('/reservar-estoque', methods=['POST'])
@login_required
def reservar_estoque():
    """
    Reserva estoque para um item do orçamento.
    Cria soft-lock no estoque para evitar venda duplicada.
    """
    db = get_db()
    data = request.json
    
    orcamento_id = data.get('orcamento_id')
    orcamento_item_id = data.get('orcamento_item_id')
    produto_estoque_id = data.get('produto_estoque_id')
    quantidade = data.get('quantidade', 0)
    
    if not all([orcamento_id, produto_estoque_id, quantidade]):
        return jsonify({'success': False, 'message': 'Dados incompletos'}), 400
    
    try:
        # Verificar estoque disponível (usa products.stock_quantity como fonte única)
        estoque = db.fetch_one("""
            SELECT 
                COALESCE(p.stock_quantity, 0) - COALESCE(
                    (SELECT SUM(er.quantidade) FROM estoque_reservas er 
                     WHERE er.produto_id = p.id AND er.status IN ('ativo', 'confirmado')), 0
                ) AS disponivel
            FROM products p
            WHERE p.id = %s
        """, (produto_estoque_id,))
        
        if not estoque or estoque['disponivel'] < quantidade:
            return jsonify({
                'success': False, 
                'message': f'Estoque insuficiente. Disponível: {estoque["disponivel"] if estoque else 0}'
            }), 400
        
        # Criar reserva (expira em 7 dias se orçamento não for aprovado)
        data_expiracao = datetime.now() + timedelta(days=7)
        
        db.insert("""
            INSERT INTO estoque_reservas (
                produto_id, quantidade, tipo_origem, origem_id, 
                status, data_expiracao, created_by, observacao
            ) VALUES (%s, %s, 'orcamento', %s, 'ativo', %s, %s, %s)
        """, (
            produto_estoque_id,
            quantidade,
            orcamento_id,
            data_expiracao,
            session.get('user_id'),
            f'Reserva automática para orçamento #{orcamento_id}'
        ))
        
        # Registrar alocação
        if orcamento_item_id:
            # Buscar DNAs para registro
            dna_info = db.fetch_one("""
                SELECT 
                    pet_orig.codigo_dna AS dna_origem,
                    pet_est.codigo_dna AS dna_estoque
                FROM orcamento_itens oi
                LEFT JOIN produto_especificacoes_tecnicas pet_orig ON pet_orig.produto_id = oi.produto_id
                LEFT JOIN produto_especificacoes_tecnicas pet_est ON pet_est.produto_id = %s
                WHERE oi.id = %s
            """, (produto_estoque_id, orcamento_item_id))
            
            db.insert("""
                INSERT INTO orcamento_item_alocacao (
                    orcamento_id, orcamento_item_id, tipo_alocacao,
                    produto_estoque_id, quantidade_estoque,
                    codigo_dna_origem, codigo_dna_estoque, tipo_match,
                    status, created_by
                ) VALUES (%s, %s, 'estoque', %s, %s, %s, %s, %s, 'reservado', %s)
            """, (
                orcamento_id,
                orcamento_item_id,
                produto_estoque_id,
                quantidade,
                dna_info.get('dna_origem') if dna_info else None,
                dna_info.get('dna_estoque') if dna_info else None,
                'exato' if dna_info and dna_info.get('dna_origem') == dna_info.get('dna_estoque') else 'derivavel',
                session.get('user_id')
            ))
            
            # Atualizar item do orçamento
            db.execute_query("""
                UPDATE orcamento_itens 
                SET qtd_estoque_alocada = COALESCE(qtd_estoque_alocada, 0) + %s,
                    status_alocacao = CASE 
                        WHEN COALESCE(qtd_estoque_alocada, 0) + %s >= quantidade THEN 'alocado'
                        ELSE 'parcial'
                    END
                WHERE id = %s
            """, (quantidade, quantidade, orcamento_item_id))
        
        return jsonify({
            'success': True,
            'message': f'Reserva de {quantidade} unidades criada com sucesso',
            'data_expiracao': data_expiracao.isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@orcamento_dna_bp.route('/gerar-op', methods=['POST'])
@login_required
def gerar_op_orcamento():
    """
    Gera Ordem de Produção para quantidade que não pode ser atendida pelo estoque.
    """
    db = get_db()
    data = request.json
    
    orcamento_id = data.get('orcamento_id')
    orcamento_item_id = data.get('orcamento_item_id')
    produto_id = data.get('produto_id')
    quantidade = data.get('quantidade', 0)
    cliente_id = data.get('cliente_id')
    empresa_id = data.get('empresa_id')
    data_prevista = data.get('data_prevista')
    etapa_inicial_id = data.get('etapa_inicial_id')
    
    if not all([orcamento_id, produto_id, quantidade]):
        return jsonify({'success': False, 'message': 'Dados incompletos'}), 400
    
    try:
        # Buscar dados do produto
        produto = db.fetch_one("SELECT * FROM products WHERE id = %s", (produto_id,))
        if not produto:
            return jsonify({'success': False, 'message': 'Produto não encontrado'}), 404
        
        # Buscar ficha técnica do produto (template de produção)
        ficha_tecnica = db.fetch_one("""
            SELECT * FROM produto_templates_producao 
            WHERE produto_id = %s AND ativo = 1 
            ORDER BY id DESC LIMIT 1
        """, (produto_id,))
        
        # Gerar número da OP
        ultimo_numero = db.fetch_one("""
            SELECT MAX(CAST(SUBSTRING(numero_op, 4) AS UNSIGNED)) AS ultimo
            FROM ordens_producao
            WHERE numero_op LIKE 'OP-%'
        """)
        proximo_numero = (ultimo_numero['ultimo'] or 0) + 1 if ultimo_numero else 1
        numero_op = f"OP-{proximo_numero:06d}"
        
        # Data prevista padrão: 7 dias
        if not data_prevista:
            data_prevista = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Criar OP
        op_id = db.insert("""
            INSERT INTO ordens_producao (
                numero_op, produto_id, quantidade, cliente_id, empresa_id,
                data_solicitacao, data_prevista, status, prioridade,
                orcamento_id, template_id, etapa_atual_id,
                observacoes, created_by
            ) VALUES (
                %s, %s, %s, %s, %s,
                NOW(), %s, 'pendente', 'normal',
                %s, %s, %s,
                %s, %s
            )
        """, (
            numero_op,
            produto_id,
            quantidade,
            cliente_id,
            empresa_id,
            data_prevista,
            orcamento_id,
            ficha_tecnica['id'] if ficha_tecnica else None,
            etapa_inicial_id,
            f'OP gerada automaticamente do orçamento #{orcamento_id}',
            session.get('user_id')
        ))
        
        # Copiar itens da ficha técnica para a OP
        if ficha_tecnica:
            itens_template = db.fetch_all("""
                SELECT * FROM produto_template_itens 
                WHERE template_id = %s
            """, (ficha_tecnica['id'],))
            
            for item in (itens_template or []):
                # Ajustar quantidade proporcionalmente
                qtd_item = float(item['quantidade'] or 0) * quantidade
                
                db.insert("""
                    INSERT INTO ordem_producao_itens (
                        ordem_producao_id, tipo_item, produto_id, descricao,
                        quantidade, unidade_medida, custo_unitario, custo_total,
                        veio_template
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
                """, (
                    op_id,
                    item['tipo_item'],
                    item.get('produto_id'),
                    item.get('descricao'),
                    qtd_item,
                    item.get('unidade_medida'),
                    item.get('custo_unitario'),
                    qtd_item * float(item.get('custo_unitario') or 0),
                ))
        
        # Registrar alocação
        if orcamento_item_id:
            # Buscar DNA
            dna_info = db.fetch_one("""
                SELECT codigo_dna FROM produto_especificacoes_tecnicas WHERE produto_id = %s
            """, (produto_id,))
            
            db.insert("""
                INSERT INTO orcamento_item_alocacao (
                    orcamento_id, orcamento_item_id, tipo_alocacao,
                    ordem_producao_id, quantidade_producao,
                    codigo_dna_origem, status, created_by
                ) VALUES (%s, %s, 'producao', %s, %s, %s, 'pendente', %s)
            """, (
                orcamento_id,
                orcamento_item_id,
                op_id,
                quantidade,
                dna_info.get('codigo_dna') if dna_info else None,
                session.get('user_id')
            ))
            
            # Atualizar item do orçamento
            db.execute_query("""
                UPDATE orcamento_itens 
                SET qtd_a_produzir = COALESCE(qtd_a_produzir, 0) + %s,
                    status_alocacao = 'op_gerada'
                WHERE id = %s
            """, (quantidade, orcamento_item_id))
        
        return jsonify({
            'success': True,
            'message': f'Ordem de Produção {numero_op} criada com sucesso',
            'op_id': op_id,
            'numero_op': numero_op
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@orcamento_dna_bp.route('/verificar-alocacao/<int:orcamento_id>', methods=['GET'])
@login_required
def verificar_alocacao(orcamento_id):
    """
    Verifica o status de alocação de todos os itens de um orçamento.
    """
    db = get_db()
    
    # Buscar itens do orçamento com status de alocação
    itens = db.fetch_all("""
        SELECT 
            oi.id,
            oi.produto_id,
            p.name AS produto_nome,
            p.internal_code AS produto_codigo,
            oi.quantidade,
            COALESCE(oi.qtd_estoque_alocada, 0) AS qtd_estoque,
            COALESCE(oi.qtd_a_produzir, 0) AS qtd_producao,
            oi.status_alocacao,
            pet.codigo_dna
        FROM orcamento_itens oi
        LEFT JOIN products p ON p.id = oi.produto_id
        LEFT JOIN produto_especificacoes_tecnicas pet ON pet.produto_id = oi.produto_id
        WHERE oi.orcamento_id = %s
        ORDER BY oi.sequencia
    """, (orcamento_id,))
    
    # Buscar detalhes das alocações
    alocacoes = db.fetch_all("""
        SELECT 
            oia.*,
            p.name AS produto_estoque_nome,
            op.numero_op
        FROM orcamento_item_alocacao oia
        LEFT JOIN products p ON p.id = oia.produto_estoque_id
        LEFT JOIN ordens_producao op ON op.id = oia.ordem_producao_id
        WHERE oia.orcamento_id = %s
        ORDER BY oia.id
    """, (orcamento_id,))
    
    return jsonify({
        'success': True,
        'itens': itens or [],
        'alocacoes': alocacoes or [],
        'resumo': {
            'total_itens': len(itens or []),
            'itens_alocados': sum(1 for i in (itens or []) if i['status_alocacao'] == 'alocado'),
            'itens_parciais': sum(1 for i in (itens or []) if i['status_alocacao'] == 'parcial'),
            'itens_op_gerada': sum(1 for i in (itens or []) if i['status_alocacao'] == 'op_gerada'),
            'itens_pendentes': sum(1 for i in (itens or []) if i['status_alocacao'] == 'pendente')
        }
    })


@orcamento_dna_bp.route('/cancelar-reserva/<int:reserva_id>', methods=['POST'])
@login_required
def cancelar_reserva(reserva_id):
    """Cancela uma reserva de estoque."""
    db = get_db()
    
    try:
        db.execute_query("""
            UPDATE estoque_reservas 
            SET status = 'cancelado', updated_at = NOW()
            WHERE id = %s
        """, (reserva_id,))
        
        return jsonify({'success': True, 'message': 'Reserva cancelada'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@orcamento_dna_bp.route('/calcular-previsao-producao/<int:produto_id>', methods=['GET'])
@login_required
def calcular_previsao_producao(produto_id):
    """
    Calcula a previsão de produção para um produto usando DADOS EXISTENTES:
    1. Tempo de produção da ficha técnica (produto_templates_producao)
    2. Tempo por etapa HISTÓRICO (op_lotes_etapas_log)
    3. Fila de produção atual/gargalos (op_lotes)
    4. Jornada de trabalho (jornadas_trabalho + jornada_horarios)
    
    NÃO cria tabelas novas - usa estrutura existente do chão de fábrica!
    """
    db = get_db()
    
    quantidade = request.args.get('quantidade', 1, type=float)
    empresa_id = request.args.get('empresa_id', 1, type=int)
    
    resultado = {
        'success': True,
        'produto_id': produto_id,
        'quantidade': quantidade,
        'ficha_tecnica': None,
        'tempos_etapas': [],
        'gargalos': [],
        'tempo_total_minutos': 0,
        'tempo_fila_minutos': 0,
        'dias_uteis_necessarios': 0,
        'previsao_inicio': None,
        'previsao_conclusao': None
    }
    
    try:
        # 1. Buscar ficha técnica do produto
        ficha = db.fetch_one("""
            SELECT 
                t.id,
                t.nome_template,
                t.tempo_producao_horas,
                t.custo_total_base,
                t.versao,
                p.name as produto_nome,
                p.internal_code as produto_codigo
            FROM produto_templates_producao t
            INNER JOIN products p ON t.produto_id = p.id
            WHERE t.produto_id = %s AND t.ativo = 1
            ORDER BY t.versao DESC
            LIMIT 1
        """, (produto_id,))
        
        if ficha:
            resultado['ficha_tecnica'] = {
                'id': ficha['id'],
                'nome': ficha['nome_template'],
                'tempo_producao_horas': float(ficha['tempo_producao_horas'] or 0),
                'custo_total': float(ficha['custo_total_base'] or 0),
                'versao': ficha['versao'],
                'produto_nome': ficha['produto_nome'],
                'produto_codigo': ficha['produto_codigo']
            }
        
        # 2. Buscar tempos HISTÓRICOS por etapa (usando op_lotes_etapas_log existente)
        # Esta query é a MESMA usada na ficha técnica (ficha_tecnica_routes.py linha 169)
        tempos_etapas = db.fetch_all("""
            SELECT 
                e.id as etapa_id,
                e.nome as etapa_nome,
                e.ordem,
                COUNT(DISTINCT log.id) as qtd_amostras,
                COALESCE(
                    ROUND(AVG(
                        TIMESTAMPDIFF(MINUTE, log.created_at, 
                            COALESCE(
                                (SELECT MIN(log2.created_at) 
                                 FROM op_lotes_etapas_log log2 
                                 WHERE log2.lote_id = log.lote_id 
                                   AND log2.created_at > log.created_at),
                                l.data_fim_operador
                            )
                        )
                    ), 0),
                    30
                ) as tempo_medio_minutos,
                ROUND(MIN(
                    TIMESTAMPDIFF(MINUTE, log.created_at, 
                        COALESCE(
                            (SELECT MIN(log2.created_at) 
                             FROM op_lotes_etapas_log log2 
                             WHERE log2.lote_id = log.lote_id 
                               AND log2.created_at > log.created_at),
                            l.data_fim_operador
                        )
                    )
                ), 0) as tempo_min_minutos,
                ROUND(MAX(
                    TIMESTAMPDIFF(MINUTE, log.created_at, 
                        COALESCE(
                            (SELECT MIN(log2.created_at) 
                             FROM op_lotes_etapas_log log2 
                             WHERE log2.lote_id = log.lote_id 
                               AND log2.created_at > log.created_at),
                            l.data_fim_operador
                        )
                    )
                ), 0) as tempo_max_minutos
            FROM producao_etapas e
            LEFT JOIN op_lotes_etapas_log log ON log.etapa_nova_id = e.id
            LEFT JOIN op_lotes l ON log.lote_id = l.id
            LEFT JOIN ordens_producao op ON l.ordem_producao_id = op.id 
                AND op.produto_id = %s 
                AND op.status = 'concluida'
                AND op.data_conclusao >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            WHERE e.ativo = 1
            GROUP BY e.id, e.nome, e.ordem
            ORDER BY e.ordem
        """, (produto_id,))
        
        tempo_producao_total = 0
        etapas_list = []
        
        for etapa in (tempos_etapas or []):
            tempo_medio = float(etapa['tempo_medio_minutos'] or 30)
            qtd_amostras = int(etapa['qtd_amostras'] or 0)
            
            # Se não há histórico, usar tempo padrão de 30 min
            if qtd_amostras == 0 or tempo_medio <= 0:
                tempo_medio = 30
            
            tempo_etapa = tempo_medio * quantidade
            tempo_producao_total += tempo_etapa
            
            etapas_list.append({
                'etapa_id': etapa['etapa_id'],
                'etapa_nome': etapa['etapa_nome'],
                'ordem': etapa['ordem'],
                'tempo_unitario_minutos': tempo_medio,
                'tempo_total_minutos': tempo_etapa,
                'fonte_tempo': 'historico' if qtd_amostras > 0 else 'padrao',
                'historico': {
                    'tempo_medio': tempo_medio,
                    'tempo_min': float(etapa['tempo_min_minutos'] or 0),
                    'tempo_max': float(etapa['tempo_max_minutos'] or 0),
                    'amostras': qtd_amostras
                }
            })
        
        resultado['tempos_etapas'] = etapas_list
        resultado['tempo_total_minutos'] = tempo_producao_total
        
        # 3. Buscar gargalos (usando op_lotes existente)
        gargalos = db.fetch_all("""
            SELECT 
                e.id AS etapa_id,
                e.nome AS etapa_nome,
                e.ordem,
                COUNT(CASE WHEN l.status_operador = 'em_espera' THEN 1 END) AS qtd_aguardando,
                COUNT(CASE WHEN l.status_operador = 'em_producao' THEN 1 END) AS qtd_em_producao,
                COUNT(l.id) AS qtd_total,
                10 AS capacidade_diaria,
                CASE 
                    WHEN COUNT(CASE WHEN l.status_operador = 'em_espera' THEN 1 END) > 30 THEN 'critico'
                    WHEN COUNT(CASE WHEN l.status_operador = 'em_espera' THEN 1 END) > 10 THEN 'atencao'
                    ELSE 'normal'
                END AS status_gargalo
            FROM producao_etapas e
            LEFT JOIN op_lotes l ON l.etapa_atual_id = e.id AND l.status NOT IN ('concluido', 'cancelado')
            WHERE e.ativo = 1
            GROUP BY e.id, e.nome, e.ordem
            ORDER BY e.ordem
        """)
        
        tempo_fila_total = 0
        gargalos_list = []
        
        for g in (gargalos or []):
            qtd_aguardando = int(g['qtd_aguardando'] or 0)
            capacidade = int(g['capacidade_diaria'] or 10)
            
            dias_espera = qtd_aguardando / capacidade if capacidade > 0 else 0
            minutos_espera = dias_espera * 480
            tempo_fila_total += minutos_espera
            
            gargalos_list.append({
                'etapa_id': g['etapa_id'],
                'etapa_nome': g['etapa_nome'],
                'ordem': g['ordem'],
                'qtd_aguardando': qtd_aguardando,
                'qtd_em_producao': int(g['qtd_em_producao'] or 0),
                'capacidade_diaria': capacidade,
                'status': g['status_gargalo'],
                'dias_espera_estimado': round(dias_espera, 1),
                'minutos_espera': round(minutos_espera)
            })
        
        resultado['gargalos'] = gargalos_list
        resultado['tempo_fila_minutos'] = tempo_fila_total
        
        # 4. Calcular previsão
        tempo_total = tempo_producao_total + tempo_fila_total
        
        # Buscar minutos úteis por dia (jornada existente)
        minutos_por_dia = db.fetch_one("""
            SELECT COALESCE(SUM(
                TIMESTAMPDIFF(MINUTE, jh.hora_inicio, jh.hora_fim)
            ), 480) as minutos_dia
            FROM jornadas_trabalho jt
            JOIN jornada_horarios jh ON jt.id = jh.jornada_id
            WHERE jt.empresa_id = %s AND jt.ativo = 1 AND jh.dia_semana = 'Segunda'
        """, (empresa_id,))
        
        minutos_uteis_dia = int(minutos_por_dia['minutos_dia']) if minutos_por_dia else 480
        
        dias_uteis = tempo_total / minutos_uteis_dia if minutos_uteis_dia > 0 else tempo_total / 480
        resultado['dias_uteis_necessarios'] = round(dias_uteis, 1)
        
        # Calcular data prevista (pulando finais de semana)
        data_inicio = datetime.now()
        data_prevista = data_inicio
        dias_contados = 0
        max_iteracoes = 365
        
        while dias_contados < dias_uteis and max_iteracoes > 0:
            data_prevista += timedelta(days=1)
            max_iteracoes -= 1
            
            if data_prevista.weekday() < 5:  # Segunda a Sexta
                dias_contados += 1
        
        resultado['previsao_inicio'] = data_inicio.strftime('%Y-%m-%d')
        resultado['previsao_conclusao'] = data_prevista.strftime('%Y-%m-%d')
        
        # Resumo legível
        horas_producao = tempo_producao_total / 60
        horas_fila = tempo_fila_total / 60
        horas_total = tempo_total / 60
        
        resultado['resumo'] = {
            'tempo_producao': f"{int(horas_producao)}h {int(tempo_producao_total % 60)}min",
            'tempo_fila': f"{int(horas_fila)}h {int(tempo_fila_total % 60)}min",
            'tempo_total': f"{int(horas_total)}h {int(tempo_total % 60)}min",
            'dias_uteis': f"{resultado['dias_uteis_necessarios']} dias",
            'previsao': data_prevista.strftime('%d/%m/%Y')
        }
        
        return jsonify(resultado)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e),
            'produto_id': produto_id
        }), 500


@orcamento_dna_bp.route('/aprovar-orcamento/<int:orcamento_id>', methods=['POST'])
@login_required
def aprovar_orcamento_com_dna(orcamento_id):
    """
    Aprova orçamento e processa alocações de DNA/estoque.
    Este é o momento em que:
    1. Reservas de estoque são confirmadas
    2. OPs são geradas para quantidades faltantes
    3. Status do orçamento é atualizado
    """
    db = get_db()
    data = request.json or {}
    
    try:
        # Buscar orçamento
        orcamento = db.fetch_one("""
            SELECT o.*, c.name as cliente_nome
            FROM orcamentos o
            LEFT JOIN customers c ON c.id = o.cliente_id
            WHERE o.id = %s
        """, (orcamento_id,))
        
        if not orcamento:
            return jsonify({'success': False, 'message': 'Orçamento não encontrado'}), 404
        
        # Buscar itens do orçamento
        itens = db.fetch_all("""
            SELECT 
                oi.*,
                p.name as produto_nome,
                pet.codigo_dna,
                pet.tipo_correia_id,
                pet.material_base_id,
                pet.largura_mm,
                pet.comprimento_mm
            FROM orcamento_itens oi
            LEFT JOIN products p ON p.id = oi.produto_id
            LEFT JOIN produto_especificacoes_tecnicas pet ON pet.produto_id = oi.produto_id
            WHERE oi.orcamento_id = %s
        """, (orcamento_id,))
        
        resultados = {
            'reservas_confirmadas': 0,
            'ops_geradas': [],
            'erros': []
        }
        
        for item in (itens or []):
            produto_id = item['produto_id']
            quantidade = float(item['quantidade'] or 0)
            
            # Verificar se produto tem DNA
            if not item.get('codigo_dna'):
                continue
            
            # Buscar estoque com DNA similar (usa products.stock_quantity como fonte única)
            estoque_similar = db.fetch_all("""
                SELECT 
                    p.id AS produto_id,
                    p.name AS produto_nome,
                    COALESCE(p.stock_quantity, 0) - COALESCE(
                        (SELECT SUM(er.quantidade) FROM estoque_reservas er 
                         WHERE er.produto_id = p.id AND er.status IN ('ativo', 'confirmado')), 0
                    ) AS estoque_disponivel,
                    pet.codigo_dna
                FROM products p
                INNER JOIN produto_especificacoes_tecnicas pet ON pet.produto_id = p.id
                WHERE p.active = 1
                  AND pet.tipo_correia_id = %s
                  AND pet.material_base_id = %s
                  AND COALESCE(p.stock_quantity, 0) > 0
                ORDER BY 
                    CASE WHEN pet.codigo_dna = %s THEN 0 ELSE 1 END,
                    COALESCE(p.stock_quantity, 0) DESC
                LIMIT 5
            """, (
                item['tipo_correia_id'],
                item['material_base_id'],
                item['codigo_dna']
            ))
            
            quantidade_alocada = 0
            
            # Tentar alocar do estoque
            for estoque in (estoque_similar or []):
                if quantidade_alocada >= quantidade:
                    break
                    
                estoque_disp = float(estoque['estoque_disponivel'] or 0)
                if estoque_disp <= 0:
                    continue
                
                qtd_alocar = min(estoque_disp, quantidade - quantidade_alocada)
                
                # Criar reserva confirmada
                db.insert("""
                    INSERT INTO estoque_reservas (
                        produto_id, quantidade, tipo_origem, origem_id,
                        status, created_by, observacao
                    ) VALUES (%s, %s, 'orcamento', %s, 'confirmado', %s, %s)
                """, (
                    estoque['produto_id'],
                    qtd_alocar,
                    orcamento_id,
                    session.get('user_id'),
                    f'Alocação confirmada para orçamento #{orcamento_id} - Produto: {item["produto_nome"]}'
                ))
                
                # Registrar alocação
                db.insert("""
                    INSERT INTO orcamento_item_alocacao (
                        orcamento_id, orcamento_item_id, tipo_alocacao,
                        produto_estoque_id, quantidade_estoque,
                        codigo_dna_origem, codigo_dna_estoque, 
                        tipo_match, status, created_by
                    ) VALUES (%s, %s, 'estoque', %s, %s, %s, %s, %s, 'reservado', %s)
                """, (
                    orcamento_id,
                    item['id'],
                    estoque['produto_id'],
                    qtd_alocar,
                    item['codigo_dna'],
                    estoque['codigo_dna'],
                    'exato' if estoque['codigo_dna'] == item['codigo_dna'] else 'derivavel',
                    session.get('user_id')
                ))
                
                quantidade_alocada += qtd_alocar
                resultados['reservas_confirmadas'] += 1
            
            # Gerar OP para quantidade faltante
            quantidade_faltante = quantidade - quantidade_alocada
            
            if quantidade_faltante > 0:
                # Gerar número da OP
                ultimo_numero = db.fetch_one("""
                    SELECT MAX(CAST(SUBSTRING(numero_op, 4) AS UNSIGNED)) AS ultimo
                    FROM ordens_producao WHERE numero_op LIKE 'OP-%'
                """)
                proximo_numero = (ultimo_numero['ultimo'] or 0) + 1 if ultimo_numero else 1
                numero_op = f"OP-{proximo_numero:06d}"
                
                # Buscar previsão de produção
                previsao = calcular_previsao_interna(db, produto_id, quantidade_faltante, orcamento.get('empresa_id', 1))
                
                # Criar OP
                op_id = db.insert("""
                    INSERT INTO ordens_producao (
                        numero_op, produto_id, quantidade, cliente_id, empresa_id,
                        data_solicitacao, data_prevista, status, prioridade,
                        orcamento_id, observacoes, created_by
                    ) VALUES (%s, %s, %s, %s, %s, NOW(), %s, 'pendente', 'normal', %s, %s, %s)
                """, (
                    numero_op,
                    produto_id,
                    quantidade_faltante,
                    orcamento.get('cliente_id'),
                    orcamento.get('empresa_id'),
                    previsao['previsao_conclusao'],
                    orcamento_id,
                    f'OP gerada automaticamente na aprovação do orçamento #{orcamento_id}',
                    session.get('user_id')
                ))
                
                # Registrar alocação de produção
                db.insert("""
                    INSERT INTO orcamento_item_alocacao (
                        orcamento_id, orcamento_item_id, tipo_alocacao,
                        ordem_producao_id, quantidade_producao,
                        codigo_dna_origem, status, created_by
                    ) VALUES (%s, %s, 'producao', %s, %s, %s, 'pendente', %s)
                """, (
                    orcamento_id,
                    item['id'],
                    op_id,
                    quantidade_faltante,
                    item['codigo_dna'],
                    session.get('user_id')
                ))
                
                resultados['ops_geradas'].append({
                    'op_id': op_id,
                    'numero_op': numero_op,
                    'produto': item['produto_nome'],
                    'quantidade': quantidade_faltante,
                    'previsao': previsao['previsao_conclusao']
                })
            
            # Atualizar item do orçamento
            db.execute_query("""
                UPDATE orcamento_itens 
                SET qtd_estoque_alocada = %s,
                    qtd_a_produzir = %s,
                    status_alocacao = %s
                WHERE id = %s
            """, (
                quantidade_alocada,
                quantidade_faltante,
                'alocado' if quantidade_faltante == 0 else 'op_gerada',
                item['id']
            ))
        
        # Atualizar status do orçamento para aprovado
        db.execute_query("""
            UPDATE orcamentos 
            SET status = 'aprovado', 
                data_aprovacao = NOW(),
                aprovado_por = %s
            WHERE id = %s
        """, (session.get('user_id'), orcamento_id))
        
        return jsonify({
            'success': True,
            'message': f'Orçamento aprovado com sucesso!',
            'resultados': resultados
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@orcamento_dna_bp.route('/verificar-estoque-produzido/<int:produto_id>', methods=['GET'])
@login_required
def verificar_estoque_produzido(produto_id):
    """
    Verifica estoque produzido com DNA similar ao produto.
    APENAS INFORMACIONAL - não reserva nem altera estoque.
    Para uso do vendedor mostrar ao cliente.
    
    Retorna:
    - Produto solicitado
    - Produtos com DNA similar em estoque
    - Quantidades disponíveis
    """
    db = get_db()
    
    quantidade_desejada = request.args.get('quantidade', 1, type=float)
    
    resultado = {
        'success': True,
        'produto_id': produto_id,
        'quantidade_desejada': quantidade_desejada,
        'produto_solicitado': None,
        'estoque_similar': [],
        'resumo': {
            'total_disponivel': 0,
            'atende_pedido': False,
            'qtd_faltante': quantidade_desejada
        }
    }
    
    try:
        # 1. Buscar dados do produto solicitado (usa products.stock_quantity como fonte única)
        produto = db.fetch_one("""
            SELECT 
                p.id,
                p.name,
                p.internal_code,
                COALESCE(p.stock_quantity, 0) AS estoque_proprio,
                pet.codigo_dna,
                pet.tipo_correia_id,
                tc.nome AS tipo_correia_nome,
                pet.material_base_id,
                mc.nome AS material_base_nome,
                pet.largura_mm,
                pet.comprimento_mm,
                pet.espessura_mm
            FROM products p
            LEFT JOIN produto_especificacoes_tecnicas pet ON pet.produto_id = p.id
            LEFT JOIN tipos_correia tc ON tc.id = pet.tipo_correia_id
            LEFT JOIN materiais_correia mc ON mc.id = pet.material_base_id
            WHERE p.id = %s
        """, (produto_id,))
        
        if not produto:
            return jsonify({'success': False, 'message': 'Produto não encontrado'}), 404
        
        resultado['produto_solicitado'] = {
            'id': produto['id'],
            'nome': produto['name'],
            'codigo': produto['internal_code'],
            'estoque_proprio': float(produto['estoque_proprio'] or 0),
            'codigo_dna': produto['codigo_dna'],
            'tipo_correia': produto['tipo_correia_nome'],
            'material': produto['material_base_nome'],
            'largura_mm': float(produto['largura_mm'] or 0),
            'comprimento_mm': float(produto['comprimento_mm'] or 0),
            'espessura_mm': float(produto['espessura_mm'] or 0)
        }
        
        # Se não tem DNA, retornar apenas estoque próprio
        if not produto['codigo_dna']:
            estoque_proprio = float(produto['estoque_proprio'] or 0)
            resultado['resumo'] = {
                'total_disponivel': estoque_proprio,
                'atende_pedido': estoque_proprio >= quantidade_desejada,
                'qtd_faltante': max(0, quantidade_desejada - estoque_proprio)
            }
            resultado['mensagem'] = 'Produto sem especificação técnica (DNA). Mostrando apenas estoque próprio.'
            return jsonify(resultado)
        
        # 2. Buscar produtos com DNA similar em estoque
        # Critérios flexíveis:
        # - Mesmo tipo E material = EXATO
        # - Dimensões maiores ou iguais = DERIVÁVEL (pode cortar para obter)
        # - Mesmo tipo OU material = SIMILAR
        
        largura_ref = produto['largura_mm'] or 0
        comprimento_ref = produto['comprimento_mm'] or 0
        tipo_ref = produto['tipo_correia_id']
        material_ref = produto['material_base_id']
        dna_ref = produto['codigo_dna'] or ''
        
        estoque_similar = db.fetch_all("""
            SELECT 
                p.id AS produto_id,
                p.name AS produto_nome,
                p.internal_code AS codigo_interno,
                COALESCE(p.stock_quantity, 0) AS estoque_disponivel,
                pet.codigo_dna,
                pet.tipo_correia_id,
                pet.material_base_id,
                pet.largura_mm,
                pet.comprimento_mm,
                pet.espessura_mm,
                -- Tipo de match baseado em critérios
                CASE 
                    WHEN pet.codigo_dna = %s AND %s != '' THEN 'EXATO'
                    WHEN pet.tipo_correia_id = %s AND pet.material_base_id = %s 
                         AND COALESCE(pet.largura_mm,0) = %s AND COALESCE(pet.comprimento_mm,0) = %s THEN 'DIMENSAO_EXATA'
                    WHEN pet.tipo_correia_id = %s AND pet.material_base_id = %s 
                         AND COALESCE(pet.largura_mm,9999) >= %s AND COALESCE(pet.comprimento_mm,9999) >= %s THEN 'DERIVAVEL'
                    WHEN pet.tipo_correia_id = %s OR pet.material_base_id = %s THEN 'SIMILAR'
                    ELSE 'PARCIAL'
                END AS tipo_match,
                -- Score de similaridade (maior = melhor match)
                (
                    CASE WHEN pet.tipo_correia_id = %s THEN 40 ELSE 0 END +
                    CASE WHEN pet.material_base_id = %s THEN 30 ELSE 0 END +
                    CASE WHEN COALESCE(pet.largura_mm,0) >= %s AND %s > 0 THEN 15 ELSE 0 END +
                    CASE WHEN COALESCE(pet.comprimento_mm,0) >= %s AND %s > 0 THEN 15 ELSE 0 END
                ) AS score_similaridade
            FROM products p
            INNER JOIN produto_especificacoes_tecnicas pet ON pet.produto_id = p.id
            WHERE p.id != %s
              AND COALESCE(p.stock_quantity, 0) > 0
              AND (
                  -- Mesmo tipo ou material
                  pet.tipo_correia_id = %s 
                  OR pet.material_base_id = %s
                  -- OU dimensões maiores (pode derivar)
                  OR (COALESCE(pet.largura_mm,0) >= %s AND %s > 0)
                  OR (COALESCE(pet.comprimento_mm,0) >= %s AND %s > 0)
              )
            ORDER BY 
                score_similaridade DESC,
                COALESCE(p.stock_quantity, 0) DESC
            LIMIT 20
        """, (
            dna_ref, dna_ref,
            tipo_ref, material_ref, largura_ref, comprimento_ref,
            tipo_ref, material_ref, largura_ref, comprimento_ref,
            tipo_ref, material_ref,
            tipo_ref, material_ref,
            largura_ref, largura_ref,
            comprimento_ref, comprimento_ref,
            produto_id,
            tipo_ref, material_ref,
            largura_ref, largura_ref,
            comprimento_ref, comprimento_ref
        ))
        
        # 3. Montar lista de estoque similar
        total_disponivel = float(produto['estoque_proprio'] or 0)
        estoque_list = []
        
        # Incluir o próprio produto se tiver estoque
        if float(produto['estoque_proprio'] or 0) > 0:
            estoque_list.append({
                'produto_id': produto['id'],
                'produto_nome': produto['name'],
                'codigo_interno': produto['internal_code'],
                'estoque_disponivel': float(produto['estoque_proprio'] or 0),
                'codigo_dna': produto['codigo_dna'],
                'tipo_match': 'PROPRIO',
                'score': 100,
                'largura_mm': float(produto['largura_mm'] or 0),
                'comprimento_mm': float(produto['comprimento_mm'] or 0)
            })
        
        for item in (estoque_similar or []):
            estoque_disp = float(item['estoque_disponivel'] or 0)
            total_disponivel += estoque_disp
            
            estoque_list.append({
                'produto_id': item['produto_id'],
                'produto_nome': item['produto_nome'],
                'codigo_interno': item['codigo_interno'],
                'estoque_disponivel': estoque_disp,
                'codigo_dna': item['codigo_dna'],
                'tipo_match': item['tipo_match'],
                'score': int(item['score_similaridade'] or 0),
                'largura_mm': float(item['largura_mm'] or 0),
                'comprimento_mm': float(item['comprimento_mm'] or 0)
            })
        
        resultado['estoque_similar'] = estoque_list
        resultado['resumo'] = {
            'total_disponivel': total_disponivel,
            'atende_pedido': total_disponivel >= quantidade_desejada,
            'qtd_faltante': max(0, quantidade_desejada - total_disponivel),
            'qtd_produtos_similares': len(estoque_list)
        }
        
        # Mensagem informativa
        if resultado['resumo']['atende_pedido']:
            resultado['mensagem'] = f"✅ Pedido pode ser atendido! {total_disponivel:.0f} unidades disponíveis."
        else:
            resultado['mensagem'] = f"⚠️ Estoque insuficiente. Disponível: {total_disponivel:.0f}, Faltam: {resultado['resumo']['qtd_faltante']:.0f}"
        
        return jsonify(resultado)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e),
            'produto_id': produto_id
        }), 500


def calcular_previsao_interna(db, produto_id, quantidade, empresa_id):
    """Função interna para calcular previsão de produção."""
    
    # Buscar tempo de produção
    tempos = db.fetch_all("""
        SELECT COALESCE(pte.tempo_padrao_minutos, pte.tempo_medio_historico, 30) as tempo
        FROM producao_etapas e
        LEFT JOIN produtos_tempo_etapa pte ON pte.produto_id = %s AND pte.etapa_id = e.id
        WHERE e.ativo = 1
    """, (produto_id,))
    
    tempo_producao = sum(float(t['tempo'] or 30) for t in (tempos or [])) * quantidade
    
    # Buscar tempo de fila
    fila = db.fetch_one("""
        SELECT COALESCE(SUM(
            CASE WHEN l.status_operador = 'em_espera' THEN 1 ELSE 0 END
        ) / NULLIF(COALESCE(cap.capacidade_diaria_lotes, 10), 0) * 480, 0) as tempo_fila
        FROM producao_etapas e
        LEFT JOIN op_lotes l ON l.etapa_atual_id = e.id AND l.status NOT IN ('concluido', 'cancelado')
        LEFT JOIN config_capacidade_etapa cap ON cap.etapa_id = e.id
        WHERE e.ativo = 1
    """)
    
    tempo_fila = float(fila['tempo_fila'] or 0) if fila else 0
    tempo_total = tempo_producao + tempo_fila
    
    # Calcular dias úteis
    minutos_por_dia = 480
    dias_uteis = tempo_total / minutos_por_dia
    
    # Calcular data prevista
    data_prevista = datetime.now()
    dias_contados = 0
    
    while dias_contados < dias_uteis:
        data_prevista += timedelta(days=1)
        if data_prevista.weekday() < 5:
            dias_contados += 1
    
    return {
        'tempo_producao_minutos': tempo_producao,
        'tempo_fila_minutos': tempo_fila,
        'tempo_total_minutos': tempo_total,
        'dias_uteis': dias_uteis,
        'previsao_conclusao': data_prevista.strftime('%Y-%m-%d')
    }
