"""
PDV Profissional - Routes
Backend para o PDV moderno e responsivo
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from functools import wraps
from datetime import datetime
import sys
import os

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db

# Helper Kardex
try:
    from utils.estoque_helper import registrar_movimentacao
except ImportError:
    registrar_movimentacao = None

# Criar Blueprint
pdv_bp = Blueprint('pdv_prof', __name__, url_prefix='/vendas')


# ===== DECORADOR DE AUTENTICAÇÃO =====
def login_required(f):
    """Requer login para acessar"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or 'user_id' not in session:
            flash('[AVISO] Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# =====================================================
# FASE 1: INICIALIZAÇÃO
# =====================================================

@pdv_bp.route('/pdv')
@login_required
def pdv_tela():
    """
    Tela principal do PDV Profissional
    
    Verifica:
    1. Se usuário tem caixa aberto
    2. Redireciona para abertura se necessário
    3. Carrega template do PDV
    """
    user_id = session.get('user_id')
    db = get_db()
    
    # Verificar se tem caixa aberto
    try:
        caixa = db.fetch_one("""
            SELECT 
                id,
                register_number,
                opening_balance,
                opened_at,
                status
            FROM cash_register
            WHERE user_id = %s 
              AND status = 'open'
            ORDER BY opened_at DESC
            LIMIT 1
        """, (user_id,))
        
        if not caixa:
            flash('[AVISO] Você precisa abrir um caixa antes de usar o PDV!', 'warning')
            return redirect('/caixa/abrir')
        
        # SEMPRE LIMPAR COMPLETAMENTE ao abrir PDV
        # Remove qualquer dado antigo
        if 'carrinho_pdv' in session:
            carrinho_antigo = session['carrinho_pdv']
            print(f"[PDV] [AVISO] Carrinho antigo encontrado com {len(carrinho_antigo.get('itens', []))} itens")
            del session['carrinho_pdv']
        
        # Cria carrinho novo e vazio
        session['carrinho_pdv'] = {
            "cliente_id": None,
            "cliente_nome": "**CLIENTE A VISTA**",
            "cliente_cpf": "000.000.000-00",
            "itens": [],
            "subtotal": 0.0,
            "desconto_total": 0.0,
            "total": 0.0
        }
        session.modified = True
        session.permanent = False  # Garantir que sessão seja salva
        
        print(f"[PDV] [OK] Carrinho COMPLETAMENTE LIMPO para usuário {user_id}")
        print(f"[PDV] [OK] Carrinho atual tem {len(session['carrinho_pdv']['itens'])} itens")
        
        return render_template('venda_pdv_profissional.html', caixa=caixa)
        
    except Exception as e:
        flash(f'[X] Erro ao verificar caixa: {str(e)}', 'danger')
        return redirect('/')


@pdv_bp.route('/pdv/dados-iniciais')
@login_required
def carregar_dados_iniciais():
    """
    Carrega dados iniciais para o PDV via AJAX
    
    Retorna:
    - Dados do operador (nome, caixa, horário abertura)
    - Dados da empresa (nome, logo)
    - Cliente padrão (A VISTA)
    """
    user_id = session.get('user_id')
    db = get_db()
    
    try:
        # ===== 1. OPERADOR + CAIXA =====
        operador = db.fetch_one("""
            SELECT 
                u.id,
                COALESCE(u.name, u.username) AS nome,
                cr.id AS caixa,
                cr.register_number AS caixa_numero,
                DATE_FORMAT(cr.opened_at, '%H:%i') AS abertura,
                cr.opening_balance AS saldo_abertura
            FROM users u
            INNER JOIN cash_register cr 
                ON cr.user_id = u.id 
                AND cr.status = 'open'
            WHERE u.id = %s
            ORDER BY cr.opened_at DESC
            LIMIT 1
        """, (user_id,))
        
        if not operador:
            return jsonify({
                "success": False,
                "erro": "Nenhum caixa aberto encontrado"
            }), 404
        
        # ===== 2. EMPRESA (LOGO) =====
        try:
            empresa = db.fetch_one("""
                SELECT 
                    id,
                    COALESCE(nome_fantasia, razao_social) AS nome,
                    logo_path AS logo
                FROM empresas 
                WHERE ativo = 1
                LIMIT 1
            """)

            # Se não houver nenhuma empresa cadastrada/ativa, usar defaults
            if not empresa:
                empresa = {
                    "id": None,
                    "nome": "IK Flow",
                    "logo": None
                }
        except Exception:
            # Fallback se tabela não existir
            empresa = {
                "id": None,
                "nome": "IK Flow",
                "logo": None
            }
        
        # ===== 3. CLIENTE DO CARRINHO (NÃO PREENCHER AUTOMATICAMENTE) =====
        # Usar o que está no carrinho, NÃO buscar do banco
        carrinho = session.get('carrinho_pdv', {})
        
        # Se carrinho não tem cliente, manter vazio (None)
        cliente_atual = {
            "id": carrinho.get('cliente_id'),
            "nome": carrinho.get('cliente_nome', '**CLIENTE A VISTA**'),
            "cpf_cnpj": carrinho.get('cliente_cpf', '000.000.000-00')
        }
        
        print(f"[PDV DADOS] Cliente no carrinho: {cliente_atual['nome']}")
        
        # ===== 4. CONFIGURAÇÕES DO PDV =====
        # Busca pelo pdv_id vinculado ao caixa aberto; fallback para active=TRUE
        try:
            config_pdv = db.fetch_one("""
                SELECT 
                    p.id,
                    p.pdv_name,
                    p.allow_negative_stock,
                    p.check_stock_realtime,
                    p.show_stock_quantity,
                    p.ask_quantity,
                    p.default_quantity,
                    p.allow_decimal_quantity,
                    p.allow_price_change,
                    p.show_discount_button,
                    p.allow_item_discount,
                    p.allow_total_discount,
                    p.max_discount_percent,
                    p.require_manager_approval,
                    p.require_customer,
                    p.auto_focus_product_field,
                    p.beep_on_scan,
                    p.enable_f2_customer,
                    p.enable_f4_discount,
                    p.enable_f5_cancel,
                    p.enable_f6_search,
                    p.enable_f9_finish
                FROM pdv_settings p
                INNER JOIN cash_register cr
                    ON cr.pdv_id = p.id
                    AND cr.user_id = %s
                    AND cr.status = 'open'
                ORDER BY cr.opened_at DESC
                LIMIT 1
            """, (user_id,))

            # Fallback: se caixa não tiver pdv_id vinculado, pega o ativo
            if not config_pdv:
                config_pdv = db.fetch_one("""
                    SELECT id, pdv_name, allow_negative_stock, check_stock_realtime,
                           show_stock_quantity, ask_quantity, default_quantity,
                           allow_decimal_quantity, allow_price_change, show_discount_button,
                           allow_item_discount, allow_total_discount, max_discount_percent,
                           require_manager_approval, require_customer, auto_focus_product_field,
                           beep_on_scan, enable_f2_customer, enable_f4_discount,
                           enable_f5_cancel, enable_f6_search, enable_f9_finish
                    FROM pdv_settings
                    WHERE active = TRUE
                    ORDER BY id DESC
                    LIMIT 1
                """)
            
            if config_pdv:
                print(f"[PDV CONFIG] Configurações carregadas: ID={config_pdv.get('id')}, ask_quantity={config_pdv.get('ask_quantity')}, allow_negative_stock={config_pdv.get('allow_negative_stock')}")
            else:
                print("[PDV CONFIG] Nenhuma configuração encontrada, usando padrão")
                # Configuração padrão se não existir
                config_pdv = {
                    "allow_negative_stock": False,
                    "ask_quantity": True,
                    "default_quantity": 1.0,
                    "show_discount_button": True,
                    "allow_item_discount": True,
                    "max_discount_percent": 10.0,
                    "enable_f2_customer": True,
                    "enable_f4_discount": True,
                    "enable_f9_finish": True
                }
        except Exception as e:
            print(f"[PDV CONFIG] Erro ao carregar configurações: {str(e)}")
            # Fallback se tabela não existir ainda
            config_pdv = {
                "allow_negative_stock": False,
                "ask_quantity": True,
                "default_quantity": 1.0,
                "show_discount_button": True,
                "allow_item_discount": True,
                "max_discount_percent": 10.0,
                "enable_f2_customer": True,
                "enable_f4_discount": True,
                "enable_f9_finish": True
            }
        
        # ===== RETORNAR DADOS =====
        return jsonify({
            "success": True,
            "operador": {
                "id": operador['id'],
                "nome": operador['nome'],
                "caixa": operador['caixa'],
                "abertura": operador['abertura'],
                "saldo_abertura": float(operador.get('saldo_abertura', 0))
            },
            "empresa": {
                "id": empresa.get('id'),
                "nome": empresa.get('nome', 'IK Flow'),
                "logo": empresa.get('logo')
            },
            "cliente_padrao": {
                "id": cliente_atual.get('id'),
                "nome": cliente_atual.get('nome', '**CLIENTE A VISTA**'),
                "cpf_cnpj": cliente_atual.get('cpf_cnpj', '000.000.000-00')
            },
            "config": {
                "allow_negative_stock": bool(config_pdv.get('allow_negative_stock', False)),
                "ask_quantity": bool(config_pdv.get('ask_quantity', True)),
                "default_quantity": float(config_pdv.get('default_quantity', 1.0)),
                "show_discount_button": bool(config_pdv.get('show_discount_button', True)),
                "allow_item_discount": bool(config_pdv.get('allow_item_discount', True)),
                "max_discount_percent": float(config_pdv.get('max_discount_percent', 10.0)),
                "enable_f2_customer": bool(config_pdv.get('enable_f2_customer', True)),
                "enable_f4_discount": bool(config_pdv.get('enable_f4_discount', True)),
                "enable_f5_cancel": bool(config_pdv.get('enable_f5_cancel', True)),
                "enable_f6_search": bool(config_pdv.get('enable_f6_search', True)),
                "enable_f9_finish": bool(config_pdv.get('enable_f9_finish', True)),
                "auto_focus_product_field": bool(config_pdv.get('auto_focus_product_field', True)),
                "beep_on_scan": bool(config_pdv.get('beep_on_scan', False))
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": f"Erro ao carregar dados: {str(e)}"
        }), 500


@pdv_bp.route('/pdv/limpar-carrinho', methods=['POST', 'GET'])
@login_required
def limpar_carrinho():
    """
    Limpa o carrinho do PDV
    """
    try:
        user_id = session.get('user_id')
        print(f"\n{'='*60}")
        print(f"[PDV LIMPAR] 🧹 INICIANDO LIMPEZA DO CARRINHO - User: {user_id}")
        print(f"{'='*60}")
        
        itens_antes = 0
        if 'carrinho_pdv' in session:
            itens_antes = len(session['carrinho_pdv'].get('itens', []))
            print(f"[PDV LIMPAR] [AVISO] Carrinho encontrado com {itens_antes} itens:")
            
            if itens_antes > 0:
                for idx, item in enumerate(session['carrinho_pdv'].get('itens', [])):
                    print(f"[PDV LIMPAR]   {idx+1}. {item.get('nome')} - Qtd: {item.get('quantidade')}")
            
            print(f"[PDV LIMPAR] 🗑️ DELETANDO session['carrinho_pdv']...")
            del session['carrinho_pdv']
            print(f"[PDV LIMPAR] [OK] session['carrinho_pdv'] DELETADO!")
        else:
            print(f"[PDV LIMPAR] ℹ️ Nenhum carrinho encontrado na sessão")
        
        # Criar carrinho vazio
        print(f"[PDV LIMPAR] [NOTA] CRIANDO carrinho vazio...")
        session['carrinho_pdv'] = {
            "cliente_id": None,
            "cliente_nome": "**CLIENTE A VISTA**",
            "cliente_cpf": "000.000.000-00",
            "itens": [],
            "subtotal": 0.0,
            "desconto_total": 0.0,
            "total": 0.0
        }
        session.modified = True
        session.permanent = False
        
        print(f"[PDV LIMPAR] [OK] Carrinho RECRIADO com {len(session['carrinho_pdv']['itens'])} itens")
        print(f"[PDV LIMPAR] [OK] LIMPEZA CONCLUÍDA - {itens_antes} itens removidos")
        print(f"{'='*60}\n")
        
        return jsonify({
            "success": True,
            "mensagem": "Carrinho limpo com sucesso!",
            "itens_removidos": itens_antes
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500


@pdv_bp.route('/pdv/status-caixa')
@login_required
def status_caixa():
    """
    Verifica status do caixa atual
    Usado para polling/verificação contínua
    """
    user_id = session.get('user_id')
    db = get_db()
    
    try:
        caixa = db.fetch_one("""
            SELECT 
                id,
                register_number,
                status,
                opened_at,
                opening_balance
            FROM cash_register
            WHERE user_id = %s 
              AND status = 'open'
            LIMIT 1
        """, (user_id,))
        
        if not caixa:
            return jsonify({
                "success": False,
                "caixa_aberto": False,
                "mensagem": "Nenhum caixa aberto"
            })
        
        return jsonify({
            "success": True,
            "caixa_aberto": True,
            "caixa": {
                "id": caixa['id'],
                "numero": caixa['register_number'],
                "status": caixa['status'],
                "abertura": caixa['opened_at'].strftime('%H:%M') if caixa['opened_at'] else None,
                "saldo_abertura": float(caixa.get('opening_balance', 0))
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500


@pdv_bp.route('/pdv/carrinho-atual')
@login_required
def carrinho_atual():
    """
    Retorna o estado atual do carrinho
    """
    try:
        carrinho = session.get('carrinho_pdv', {
            "cliente_id": None,
            "cliente_nome": "**CLIENTE A VISTA**",
            "itens": [],
            "subtotal": 0.0,
            "desconto_total": 0.0,
            "total": 0.0
        })
        
        print(f"[PDV CARRINHO-ATUAL] [PACOTE] Retornando carrinho com {len(carrinho.get('itens', []))} itens")
        if carrinho.get('itens'):
            for idx, item in enumerate(carrinho['itens']):
                print(f"[PDV CARRINHO-ATUAL]   - Item {idx+1}: {item.get('nome')}")
        
        return jsonify({
            "success": True,
            "carrinho": carrinho
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500


@pdv_bp.route('/pdv/configuracoes-api')
@login_required
def obter_configuracoes_api():
    """
    API: Retorna configurações do PDV para controlar botões e atalhos
    """
    pdv_id = session.get('pdv_id', 1)
    db = get_db()
    
    try:
        config = db.fetch_one("""
            SELECT 
                require_customer,
                show_discount_button,
                enable_f2_customer,
                enable_f4_discount,
                enable_f5_cancel,
                enable_f6_search,
                enable_f9_finalize
            FROM pdv_settings
            WHERE id = %s
        """, (pdv_id,))
        
        if not config:
            # Configurações padrão se não existir
            config = {
                'require_customer': True,
                'show_discount_button': True,
                'enable_f2_customer': True,
                'enable_f4_discount': True,
                'enable_f5_cancel': True,
                'enable_f6_search': True,
                'enable_f9_finalize': True
            }
        
        return jsonify({
            "success": True,
            "config": {
                "require_customer": bool(config.get('require_customer', True)),
                "show_discount_button": bool(config.get('show_discount_button', True)),
                "enable_f2_customer": bool(config.get('enable_f2_customer', True)),
                "enable_f4_discount": bool(config.get('enable_f4_discount', True)),
                "enable_f5_cancel": bool(config.get('enable_f5_cancel', True)),
                "enable_f6_search": bool(config.get('enable_f6_search', True)),
                "enable_f9_finalize": bool(config.get('enable_f9_finalize', True))
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500


# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def inicializar_carrinho():
    """
    Inicializa estrutura do carrinho na sessão
    """
    if 'carrinho_pdv' not in session:
        session['carrinho_pdv'] = {
            "cliente_id": None,
            "cliente_nome": "**CLIENTE A VISTA**",
            "cliente_cpf": "000.000.000-00",
            "itens": [],
            "subtotal": 0.0,
            "desconto_total": 0.0,
            "total": 0.0
        }
        session.modified = True


def recalcular_totais(carrinho):
    """
    Recalcula todos os totais do carrinho
    
    Args:
        carrinho (dict): Dicionário do carrinho
        
    Returns:
        dict: Carrinho com totais atualizados
    """
    # Calcular subtotal dos itens
    carrinho['subtotal'] = sum(
        float(item.get('subtotal', 0)) 
        for item in carrinho.get('itens', [])
    )
    
    # Calcular total (subtotal - desconto)
    carrinho['total'] = carrinho['subtotal'] - float(carrinho.get('desconto_total', 0))
    
    # Garantir que total não seja negativo
    if carrinho['total'] < 0:
        carrinho['total'] = 0.0
    
    return carrinho


# =====================================================
# FASE 2: BUSCA DE PRODUTOS
# =====================================================

@pdv_bp.route('/pdv/buscar-produto', methods=['POST'])
@login_required
def buscar_produto():
    """
    Busca produto por código interno, código de barras ou descrição
    
    Retorna:
    - Produto encontrado (se único)
    - Lista de produtos (se múltiplos)
    - Erro 404 (se não encontrado)
    """
    try:
        print("[PDV BUSCA] Iniciando busca de produto...")
        data = request.get_json()
        print(f"[PDV BUSCA] Dados recebidos: {data}")
        
        termo_busca = data.get('termo', '').strip()
        print(f"[PDV BUSCA] Termo de busca: '{termo_busca}'")
        
        if not termo_busca:
            print("[PDV BUSCA] [X] Termo de busca vazio")
            return jsonify({
                "success": False,
                "erro": "Termo de busca vazio"
            }), 400
        
        db = get_db()
        print("[PDV BUSCA] Conexão com banco OK")
        
        # ===== BUSCA EXATA POR CÓDIGO OU BARCODE =====
        produto_exato = db.fetch_one("""
            SELECT 
                id,
                internal_code AS codigo,
                barcode AS codigo_barras,
                name AS nome,
                COALESCE(price, 0) AS preco,
                COALESCE(unit_measure, 'UN') AS unidade,
                COALESCE(stock_quantity, 0) AS estoque,
                active
            FROM products
            WHERE active = TRUE
              AND (
                  internal_code = %s 
                  OR barcode = %s
              )
            LIMIT 1
        """, (termo_busca, termo_busca))
        
        # Se encontrou produto exato, retornar direto
        if produto_exato:
            print(f"[PDV BUSCA] [OK] Produto encontrado: {produto_exato['nome']}")
            return jsonify({
                "success": True,
                "tipo": "unico",
                "produto": {
                    "id": produto_exato['id'],
                    "codigo": produto_exato['codigo'],
                    "codigo_barras": produto_exato['codigo_barras'],
                    "nome": produto_exato['nome'],
                    "preco": float(produto_exato['preco']),
                    "unidade": produto_exato['unidade'],
                    "estoque": float(produto_exato['estoque'])
                }
            })
        
        print("[PDV BUSCA] Produto não encontrado por código, buscando por nome...")
        
        # ===== BUSCA POR DESCRIÇÃO (PARCIAL) =====
        produtos = db.fetch_all("""
            SELECT 
                id,
                internal_code AS codigo,
                barcode AS codigo_barras,
                name AS nome,
                COALESCE(price, 0) AS preco,
                COALESCE(unit_measure, 'UN') AS unidade,
                COALESCE(stock_quantity, 0) AS estoque,
                active
            FROM products
            WHERE active = TRUE
              AND UPPER(name) LIKE CONCAT('%%', UPPER(%s), '%%')
            ORDER BY name
            LIMIT 20
        """, (termo_busca,))
        
        if not produtos:
            return jsonify({
                "success": False,
                "erro": "Produto não encontrado"
            }), 404
        
        # Se encontrou apenas 1 produto, retornar como único
        if len(produtos) == 1:
            p = produtos[0]
            return jsonify({
                "success": True,
                "tipo": "unico",
                "produto": {
                    "id": p['id'],
                    "codigo": p['codigo'],
                    "codigo_barras": p['codigo_barras'],
                    "nome": p['nome'],
                    "preco": float(p['preco']),
                    "unidade": p['unidade'],
                    "estoque": float(p['estoque'])
                }
            })
        
        # Se encontrou múltiplos, retornar lista
        return jsonify({
            "success": True,
            "tipo": "multiplos",
            "produtos": [
                {
                    "id": p['id'],
                    "codigo": p['codigo'],
                    "codigo_barras": p['codigo_barras'],
                    "nome": p['nome'],
                    "preco": float(p['preco']),
                    "unidade": p['unidade'],
                    "estoque": float(p['estoque'])
                }
                for p in produtos
            ],
            "total": len(produtos)
        })
        
    except Exception as e:
        import traceback
        print(f"[PDV BUSCA] [X] ERRO: {str(e)}")
        print(f"[PDV BUSCA] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "erro": f"Erro ao buscar produto: {str(e)}"
        }), 500


@pdv_bp.route('/pdv/buscar-produtos-modal', methods=['POST'])
@login_required
def buscar_produtos_modal():
    """
    Busca múltiplos produtos por código, código de barras ou nome
    Usado no modal de seleção de produtos (F6)
    
    Recebe:
    - termo: string de busca
    
    Retorna:
    - Lista de produtos encontrados
    """
    try:
        data = request.get_json()
        termo = data.get('termo', '').strip()
        
        if not termo:
            return jsonify({
                "success": False,
                "erro": "Digite algo para buscar"
            }), 400
        
        if len(termo) < 3:
            return jsonify({
                "success": False,
                "erro": "Digite pelo menos 3 caracteres"
            }), 400
        
        db = get_db()
        
        # Buscar produtos por código, código de barras ou nome
        produtos = db.fetch_all("""
            SELECT 
                id,
                internal_code AS codigo,
                barcode AS codigo_barras,
                name AS nome,
                COALESCE(price, 0) AS preco,
                COALESCE(unit_measure, 'UN') AS unidade,
                COALESCE(stock_quantity, 0) AS estoque,
                active
            FROM products
            WHERE active = TRUE
              AND (
                  internal_code LIKE %s
                  OR barcode LIKE %s
                  OR UPPER(name) LIKE UPPER(%s)
              )
            ORDER BY name
            LIMIT 50
        """, (f'%{termo}%', f'%{termo}%', f'%{termo}%'))
        
        if not produtos or len(produtos) == 0:
            return jsonify({
                "success": False,
                "erro": "Nenhum produto encontrado"
            }), 404
        
        # Converter para lista de dicionários
        produtos_list = []
        for produto in produtos:
            produtos_list.append({
                "id": produto['id'],
                "codigo": produto.get('codigo', 'N/A'),
                "codigo_barras": produto.get('codigo_barras', 'N/A'),
                "nome": produto['nome'],
                "preco": float(produto.get('preco', 0)),
                "unidade": produto.get('unidade', 'UN'),
                "estoque": float(produto.get('estoque', 0))
            })
        
        return jsonify({
            "success": True,
            "total": len(produtos_list),
            "produtos": produtos_list
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": f"Erro ao buscar produtos: {str(e)}"
        }), 500


# =====================================================
# FASE 2.5: BUSCA DE CLIENTES
# =====================================================

@pdv_bp.route('/pdv/buscar-clientes', methods=['POST'])
@login_required
def buscar_clientes():
    """
    Busca clientes por nome ou CPF/CNPJ
    
    Recebe:
    - termo: string de busca
    
    Retorna:
    - Lista de clientes encontrados
    """
    try:
        data = request.get_json()
        termo = data.get('termo', '').strip()
        
        if not termo:
            return jsonify({
                "success": False,
                "erro": "Digite algo para buscar"
            }), 400
        
        db = get_db()
        
        # Buscar clientes por nome ou CNPJ/Telefone
        clientes = db.fetch_all("""
            SELECT 
                id,
                name AS nome,
                cnpj AS cpf_cnpj,
                phone AS telefone,
                email,
                city AS cidade,
                active AS ativo
            FROM customers
            WHERE active = TRUE
              AND (
                  UPPER(name) LIKE UPPER(%s)
                  OR cnpj LIKE %s
                  OR phone LIKE %s
              )
            ORDER BY name
            LIMIT 50
        """, (f'%{termo}%', f'%{termo}%', f'%{termo}%'))
        
        if not clientes or len(clientes) == 0:
            return jsonify({
                "success": False,
                "erro": "Nenhum cliente encontrado"
            }), 404
        
        # Converter para lista de dicionários
        clientes_list = []
        for cliente in clientes:
            clientes_list.append({
                "id": cliente['id'],
                "nome": cliente['nome'],
                "cpf_cnpj": cliente.get('cpf_cnpj', 'N/A'),
                "telefone": cliente.get('telefone', ''),
                "email": cliente.get('email', ''),
                "cidade": cliente.get('cidade', '')
            })
        
        return jsonify({
            "success": True,
            "total": len(clientes_list),
            "clientes": clientes_list
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": f"Erro ao buscar clientes: {str(e)}"
        }), 500


@pdv_bp.route('/pdv/selecionar-cliente', methods=['POST'])
@login_required
def selecionar_cliente():
    """
    Seleciona um cliente para a venda atual
    
    Recebe:
    - cliente_id: ID do cliente
    
    Retorna:
    - Dados do cliente selecionado
    """
    try:
        data = request.get_json()
        cliente_id = data.get('cliente_id')
        
        if not cliente_id:
            return jsonify({
                "success": False,
                "erro": "ID do cliente não informado"
            }), 400
        
        db = get_db()
        
        # Buscar dados completos do cliente
        cliente = db.fetch_one("""
            SELECT 
                id,
                name AS nome,
                cnpj AS cpf_cnpj,
                phone AS telefone,
                email,
                city AS cidade
            FROM customers
            WHERE id = %s AND active = TRUE
        """, (cliente_id,))
        
        if not cliente:
            return jsonify({
                "success": False,
                "erro": "Cliente não encontrado"
            }), 404
        
        # Atualizar carrinho na sessão
        carrinho = session.get('carrinho_pdv', {})
        carrinho['cliente_id'] = cliente['id']
        carrinho['cliente_nome'] = cliente['nome']
        carrinho['cliente_cpf'] = cliente.get('cpf_cnpj', 'N/A')
        
        session['carrinho_pdv'] = carrinho
        session.modified = True
        
        print(f"[PDV] Cliente selecionado: {cliente['nome']} (ID: {cliente['id']})")
        
        return jsonify({
            "success": True,
            "cliente": {
                "id": cliente['id'],
                "nome": cliente['nome'],
                "cpf_cnpj": cliente.get('cpf_cnpj', 'N/A'),
                "telefone": cliente.get('telefone', ''),
                "email": cliente.get('email', ''),
                "cidade": cliente.get('cidade', '')
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": f"Erro ao selecionar cliente: {str(e)}"
        }), 500


# =====================================================
# FASE 3: GERENCIAMENTO DO CARRINHO
# =====================================================

@pdv_bp.route('/pdv/adicionar-item', methods=['POST'])
@login_required
def adicionar_item():
    """
    Adiciona ou atualiza item no carrinho
    
    Recebe:
    - produto_id
    - quantidade
    - force_new (opcional): força criar novo item ao invés de somar
    
    Retorna:
    - Carrinho atualizado
    """
    try:
        data = request.get_json()
        produto_id = data.get('produto_id')
        quantidade = float(data.get('quantidade', 1))
        force_new = data.get('force_new', False)  # Novo parâmetro
        
        if not produto_id:
            return jsonify({
                "success": False,
                "erro": "ID do produto não informado"
            }), 400
        
        if quantidade <= 0:
            return jsonify({
                "success": False,
                "erro": "Quantidade deve ser maior que zero"
            }), 400
        
        db = get_db()
        
        # Buscar configurações do PDV
        config_pdv = db.fetch_one("""
            SELECT allow_negative_stock
            FROM pdv_settings
            WHERE active = TRUE
            ORDER BY id DESC
            LIMIT 1
        """)
        
        allow_negative_stock = config_pdv.get('allow_negative_stock', False) if config_pdv else False
        
        # Buscar dados do produto
        produto = db.fetch_one("""
            SELECT 
                id,
                internal_code AS codigo,
                barcode AS codigo_barras,
                name AS nome,
                COALESCE(price, 0) AS preco,
                COALESCE(unit_measure, 'UN') AS unidade,
                COALESCE(stock_quantity, 0) AS estoque
            FROM products
            WHERE id = %s AND active = TRUE
        """, (produto_id,))
        
        if not produto:
            return jsonify({
                "success": False,
                "erro": "Produto não encontrado"
            }), 404
        
        # Verificar estoque (apenas se configurado para não permitir estoque negativo)
        if not allow_negative_stock and quantidade > produto['estoque']:
            return jsonify({
                "success": False,
                "erro": f"Estoque insuficiente! Disponível: {produto['estoque']}"
            }), 400
        
        # Obter carrinho da sessão
        carrinho = session.get('carrinho_pdv', {
            "cliente_id": None,
            "cliente_nome": "**CLIENTE A VISTA**",
            "itens": [],
            "subtotal": 0.0,
            "desconto_total": 0.0,
            "total": 0.0
        })
        
        print(f"[PDV ADICIONAR] [PACOTE] Carrinho atual tem {len(carrinho.get('itens', []))} itens ANTES de adicionar")
        if carrinho.get('itens'):
            for idx, item in enumerate(carrinho['itens']):
                print(f"[PDV ADICIONAR]   - Item {idx+1}: {item.get('nome')} (Qtd: {item.get('quantidade')})")
        
        # Garantir que carrinho tem estrutura correta
        if 'itens' not in carrinho:
            carrinho['itens'] = []
        if 'subtotal' not in carrinho:
            carrinho['subtotal'] = 0.0
        if 'desconto_total' not in carrinho:
            carrinho['desconto_total'] = 0.0
        if 'total' not in carrinho:
            carrinho['total'] = 0.0
        
        # Verificar se produto já está no carrinho
        item_existente = None
        for item in carrinho.get('itens', []):
            if item.get('produto_id') == produto_id:
                item_existente = item
                break
        
        preco_unitario = float(produto['preco'])
        
        if item_existente and not force_new:
            print(f"[PDV ADICIONAR] [AVISO] PRODUTO JÁ EXISTE NO CARRINHO!")
            print(f"[PDV ADICIONAR]   - Quantidade atual: {item_existente['quantidade']}")
            print(f"[PDV ADICIONAR]   - Quantidade a adicionar: {quantidade}")
            print(f"[PDV ADICIONAR]   - Nova quantidade: {item_existente['quantidade'] + quantidade}")
            # Atualizar quantidade
            item_existente['quantidade'] += quantidade
            item_existente['subtotal'] = item_existente['quantidade'] * preco_unitario
        else:
            if force_new and item_existente:
                print(f"[PDV ADICIONAR] 🔄 FORCE_NEW ativado - Substituindo item existente")
                carrinho['itens'].remove(item_existente)
            # Adicionar novo item
            novo_item = {
                "produto_id": produto['id'],
                "codigo": produto['codigo'],
                "codigo_barras": produto['codigo_barras'],
                "nome": produto['nome'],
                "quantidade": quantidade,
                "preco_unitario": preco_unitario,
                "unidade": produto['unidade'],
                "desconto": 0.0,
                "subtotal": quantidade * preco_unitario
            }
            carrinho['itens'].append(novo_item)
        
        # Recalcular totais
        carrinho = recalcular_totais(carrinho)
        
        # Salvar no session
        session['carrinho_pdv'] = carrinho
        session.modified = True
        
        print(f"[PDV] Item adicionado: {produto['nome']} (Qtd: {quantidade})")
        print(f"[PDV] Total de itens no carrinho: {len(carrinho['itens'])}")
        print(f"[PDV] Subtotal: R$ {carrinho['total']:.2f}")
        
        return jsonify({
            "success": True,
            "mensagem": "Item adicionado com sucesso",
            "carrinho": carrinho
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": f"Erro ao adicionar item: {str(e)}"
        }), 500


@pdv_bp.route('/pdv/aplicar-desconto-item', methods=['POST'])
@login_required
def aplicar_desconto_item():
    """
    Aplica desconto em um item específico do carrinho
    
    Recebe:
    - produto_id
    - tipo: 'percentual' ou 'valor'
    - valor: percentual (0-100) ou valor em R$
    
    Retorna:
    - Carrinho atualizado
    - Desconto aplicado
    """
    try:
        data = request.get_json()
        produto_id = data.get('produto_id')
        tipo = data.get('tipo', 'percentual')  # 'percentual' ou 'valor'
        valor = float(data.get('valor', 0))
        
        print(f"\n{'='*60}")
        print(f"[PDV DESCONTO] [DINHEIRO] Aplicando desconto - Produto: {produto_id}")
        print(f"[PDV DESCONTO] Tipo: {tipo}, Valor: {valor}")
        print(f"{'='*60}")
        
        if not produto_id:
            return jsonify({
                "success": False,
                "erro": "ID do produto não informado"
            }), 400
        
        if valor < 0:
            return jsonify({
                "success": False,
                "erro": "Valor do desconto não pode ser negativo"
            }), 400
        
        # Obter carrinho da sessão
        carrinho = session.get('carrinho_pdv', {
            "cliente_id": None,
            "cliente_nome": "**CLIENTE A VISTA**",
            "itens": [],
            "subtotal": 0.0,
            "desconto_total": 0.0,
            "total": 0.0
        })
        
        # Buscar item no carrinho
        item_encontrado = None
        for item in carrinho.get('itens', []):
            if item.get('produto_id') == produto_id:
                item_encontrado = item
                break
        
        if not item_encontrado:
            return jsonify({
                "success": False,
                "erro": "Item não encontrado no carrinho"
            }), 404
        
        # Calcular desconto
        subtotal_item = float(item_encontrado['subtotal'])
        desconto_calculado = 0
        
        if tipo == 'percentual':
            if valor > 100:
                return jsonify({
                    "success": False,
                    "erro": "Percentual não pode ser maior que 100%"
                }), 400
            desconto_calculado = (subtotal_item * valor) / 100
        else:  # valor
            if valor > subtotal_item:
                return jsonify({
                    "success": False,
                    "erro": f"Desconto não pode ser maior que o subtotal do item (R$ {subtotal_item:.2f})"
                }), 400
            desconto_calculado = valor
        
        print(f"[PDV DESCONTO] Subtotal do item: R$ {subtotal_item:.2f}")
        print(f"[PDV DESCONTO] Desconto calculado: R$ {desconto_calculado:.2f}")
        
        # Aplicar desconto no item
        item_encontrado['desconto'] = desconto_calculado
        
        # Recalcular totais do carrinho
        total_desconto_carrinho = sum(
            float(item.get('desconto', 0)) 
            for item in carrinho.get('itens', [])
        )
        
        subtotal_carrinho = sum(
            float(item.get('subtotal', 0)) 
            for item in carrinho.get('itens', [])
        )
        
        total_carrinho = subtotal_carrinho - total_desconto_carrinho
        
        carrinho['subtotal'] = subtotal_carrinho
        carrinho['desconto_total'] = total_desconto_carrinho
        carrinho['total'] = max(0, total_carrinho)
        
        print(f"[PDV DESCONTO] Subtotal carrinho: R$ {subtotal_carrinho:.2f}")
        print(f"[PDV DESCONTO] Desconto total carrinho: R$ {total_desconto_carrinho:.2f}")
        print(f"[PDV DESCONTO] Total carrinho: R$ {total_carrinho:.2f}")
        
        # Salvar carrinho atualizado
        session['carrinho_pdv'] = carrinho
        session.modified = True
        
        print(f"[PDV DESCONTO] [OK] Desconto aplicado com sucesso!")
        print(f"{'='*60}\n")
        
        return jsonify({
            "success": True,
            "mensagem": "Desconto aplicado com sucesso!",
            "desconto_aplicado": desconto_calculado,
            "carrinho": carrinho
        })
        
    except Exception as e:
        print(f"[PDV DESCONTO] [X] Erro ao aplicar desconto: {str(e)}")
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500


@pdv_bp.route('/pdv/cancelar-itens', methods=['POST'])
@login_required
def cancelar_itens():
    """
    Cancela múltiplos itens do carrinho
    
    Recebe:
    - produtos_ids: lista de IDs de produtos a cancelar
    
    Retorna:
    - Carrinho atualizado
    """
    try:
        data = request.get_json()
        produtos_ids = data.get('produtos_ids', [])
        
        print(f"\n{'='*60}")
        print(f"[PDV CANCELAR] 🗑️ Cancelando {len(produtos_ids)} item(ns)")
        print(f"[PDV CANCELAR] IDs: {produtos_ids}")
        print(f"{'='*60}")
        
        if not produtos_ids or len(produtos_ids) == 0:
            return jsonify({
                "success": False,
                "erro": "Nenhum item selecionado para cancelar"
            }), 400
        
        # Obter carrinho da sessão
        carrinho = session.get('carrinho_pdv', {
            "cliente_id": None,
            "cliente_nome": "**CLIENTE A VISTA**",
            "itens": [],
            "subtotal": 0.0,
            "desconto_total": 0.0,
            "total": 0.0
        })
        
        itens_antes = len(carrinho.get('itens', []))
        print(f"[PDV CANCELAR] Carrinho tinha {itens_antes} itens")
        
        # Filtrar itens (remover os selecionados)
        itens_removidos = []
        itens_restantes = []
        
        for item in carrinho.get('itens', []):
            if item.get('produto_id') in produtos_ids:
                itens_removidos.append(item)
                print(f"[PDV CANCELAR]   [X] Removendo: {item.get('nome')} (R$ {item.get('subtotal', 0):.2f})")
            else:
                itens_restantes.append(item)
        
        carrinho['itens'] = itens_restantes
        
        # Recalcular totais
        subtotal = sum(float(item.get('subtotal', 0)) for item in itens_restantes)
        desconto_total = sum(float(item.get('desconto', 0)) for item in itens_restantes)
        total = max(0, subtotal - desconto_total)
        
        carrinho['subtotal'] = subtotal
        carrinho['desconto_total'] = desconto_total
        carrinho['total'] = total
        
        # Salvar carrinho atualizado
        session['carrinho_pdv'] = carrinho
        session.modified = True
        
        print(f"[PDV CANCELAR] [OK] {len(itens_removidos)} item(ns) removido(s)")
        print(f"[PDV CANCELAR] Carrinho agora tem {len(itens_restantes)} itens")
        print(f"[PDV CANCELAR] Novo total: R$ {total:.2f}")
        print(f"{'='*60}\n")
        
        return jsonify({
            "success": True,
            "mensagem": f"{len(itens_removidos)} item(ns) cancelado(s) com sucesso!",
            "itens_removidos": len(itens_removidos),
            "carrinho": carrinho
        })
        
    except Exception as e:
        print(f"[PDV CANCELAR] [X] Erro ao cancelar itens: {str(e)}")
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500


@pdv_bp.route('/pdv/remover-item', methods=['POST'])
@login_required
def remover_item():
    """
    Remove item do carrinho (individual - usado pela lixeira na grade)
    """
    try:
        data = request.get_json()
        produto_id = data.get('produto_id')
        
        if not produto_id:
            return jsonify({
                "success": False,
                "erro": "ID do produto não informado"
            }), 400
        
        # Obter carrinho
        carrinho = session.get('carrinho_pdv', {"itens": []})
        
        # Remover item
        carrinho['itens'] = [
            item for item in carrinho['itens'] 
            if item['produto_id'] != produto_id
        ]
        
        # Recalcular totais
        carrinho = recalcular_totais(carrinho)
        
        # Salvar
        session['carrinho_pdv'] = carrinho
        session.modified = True
        
        return jsonify({
            "success": True,
            "mensagem": "Item removido com sucesso",
            "carrinho": carrinho
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": f"Erro ao remover item: {str(e)}"
        }), 500


@pdv_bp.route('/pdv/atualizar-quantidade', methods=['POST'])
@login_required
def atualizar_quantidade():
    """
    Atualiza quantidade de um item
    """
    try:
        data = request.get_json()
        produto_id = data.get('produto_id')
        nova_quantidade = float(data.get('quantidade', 1))
        
        if not produto_id:
            return jsonify({
                "success": False,
                "erro": "ID do produto não informado"
            }), 400
        
        if nova_quantidade <= 0:
            return jsonify({
                "success": False,
                "erro": "Quantidade deve ser maior que zero"
            }), 400
        
        # Obter carrinho
        carrinho = session.get('carrinho_pdv', {"itens": []})
        
        # Encontrar e atualizar item
        item_encontrado = False
        for item in carrinho['itens']:
            if item['produto_id'] == produto_id:
                item['quantidade'] = nova_quantidade
                item['subtotal'] = nova_quantidade * item['preco_unitario']
                item_encontrado = True
                break
        
        if not item_encontrado:
            return jsonify({
                "success": False,
                "erro": "Item não encontrado no carrinho"
            }), 404
        
        # Recalcular totais
        carrinho = recalcular_totais(carrinho)
        
        # Salvar
        session['carrinho_pdv'] = carrinho
        session.modified = True
        
        return jsonify({
            "success": True,
            "mensagem": "Quantidade atualizada",
            "carrinho": carrinho
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": f"Erro ao atualizar quantidade: {str(e)}"
        }), 500


# =====================================================
# FASE 5: FINALIZAÇÃO DE VENDA (F9)
# =====================================================

@pdv_bp.route('/pdv/testar-insert-venda', methods=['GET'])
@login_required
def testar_insert_venda():
    """Endpoint de teste para descobrir qual campo está causando problema"""
    try:
        db = get_db()
        user_id = session.get('user_id')
        company_id = session.get('company_id', 1)
        
        # Teste 1: INSERT mínimo absoluto
        print("[TESTE] Tentando INSERT mínimo...")
        try:
            test_id = db.execute("""
                INSERT INTO sales (
                    sale_date,
                    created_at
                ) VALUES (NOW(), NOW())
            """)
            print(f"[TESTE] [OK] INSERT mínimo OK - ID: {test_id}")
            db.execute("DELETE FROM sales WHERE id = %s", (test_id,))
        except Exception as e:
            print(f"[TESTE] [X] INSERT mínimo FALHOU: {str(e)}")
            return jsonify({"success": False, "erro": f"INSERT mínimo falhou: {str(e)}"})
        
        # Teste 2: Com customer_id
        print("[TESTE] Tentando com customer_id...")
        try:
            test_id = db.execute("""
                INSERT INTO sales (
                    customer_id,
                    sale_date,
                    created_at
                ) VALUES (1, NOW(), NOW())
            """)
            print(f"[TESTE] [OK] Com customer_id OK - ID: {test_id}")
            db.execute("DELETE FROM sales WHERE id = %s", (test_id,))
        except Exception as e:
            print(f"[TESTE] [X] Com customer_id FALHOU: {str(e)}")
            return jsonify({"success": False, "erro": f"customer_id falhou: {str(e)}"})
        
        # Teste 3: Com empresa_id
        print("[TESTE] Tentando com empresa_id...")
        try:
            test_id = db.execute("""
                INSERT INTO sales (
                    customer_id,
                    empresa_id,
                    sale_date,
                    created_at
                ) VALUES (1, %s, NOW(), NOW())
            """, (company_id,))
            print(f"[TESTE] [OK] Com empresa_id OK - ID: {test_id}")
            db.execute("DELETE FROM sales WHERE id = %s", (test_id,))
        except Exception as e:
            print(f"[TESTE] [X] Com empresa_id FALHOU: {str(e)}")
            return jsonify({"success": False, "erro": f"empresa_id falhou: {str(e)}"})
        
        # Teste 4: Com seller_id
        print("[TESTE] Tentando com seller_id...")
        try:
            test_id = db.execute("""
                INSERT INTO sales (
                    customer_id,
                    empresa_id,
                    seller_id,
                    sale_date,
                    created_at
                ) VALUES (1, %s, %s, NOW(), NOW())
            """, (company_id, user_id))
            print(f"[TESTE] [OK] Com seller_id OK - ID: {test_id}")
            db.execute("DELETE FROM sales WHERE id = %s", (test_id,))
        except Exception as e:
            print(f"[TESTE] [X] Com seller_id FALHOU: {str(e)}")
            return jsonify({"success": False, "erro": f"seller_id falhou: {str(e)}"})
        
        return jsonify({
            "success": True,
            "mensagem": "Todos os testes passaram!",
            "user_id": user_id,
            "company_id": company_id
        })
        
    except Exception as e:
        return jsonify({"success": False, "erro": str(e)})


@pdv_bp.route('/pdv/obter-carrinho', methods=['GET'])
@login_required
def obter_carrinho():
    """Retorna o carrinho atual da sessão"""
    try:
        carrinho = session.get('carrinho_pdv', {
            "cliente_id": None,
            "cliente_nome": "**CLIENTE A VISTA**",
            "itens": [],
            "subtotal": 0.0,
            "desconto_total": 0.0,
            "total": 0.0
        })
        
        return jsonify({
            "success": True,
            "carrinho": carrinho
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": f"Erro ao obter carrinho: {str(e)}"
        }), 500


@pdv_bp.route('/pdv/finalizar-venda', methods=['POST'])
@login_required
def finalizar_venda():
    """
    Finaliza a venda com múltiplos métodos de pagamento
    
    Recebe:
    - pagamentos: array de objetos {forma: string, valor: float}
    - troco: float (calculado no frontend)
    
    Exemplo:
    {
        "pagamentos": [
            {"forma": "dinheiro", "valor": 50.00},
            {"forma": "credito", "valor": 50.00}
        ],
        "troco": 0.00
    }
    
    Retorna:
    - sale_id: ID da venda criada
    - numero_venda: Número sequencial da venda
    """
    try:
        data = request.get_json()
        pagamentos = data.get('pagamentos', [])
        troco = float(data.get('troco', 0))
        
        if not pagamentos or len(pagamentos) == 0:
            return jsonify({
                "success": False,
                "erro": "Nenhuma forma de pagamento informada"
            }), 400
        
        # Obter carrinho da sessão
        carrinho = session.get('carrinho_pdv', {})
        
        if not carrinho or not carrinho.get('itens') or len(carrinho.get('itens', [])) == 0:
            return jsonify({
                "success": False,
                "erro": "Carrinho vazio. Adicione produtos antes de finalizar."
            }), 400
        
        # Validações
        db = get_db()
        
        # Verificar se cliente é obrigatório — sempre lê do PDV ativo
        pdv_config = db.fetch_one("""
            SELECT require_customer, show_discount_button 
            FROM pdv_settings 
            WHERE active = TRUE
            ORDER BY id DESC
            LIMIT 1
        """)
        require_customer = bool(pdv_config.get('require_customer', True)) if pdv_config else True

        cliente_id = carrinho.get('cliente_id')

        # Se cliente não foi informado
        if not cliente_id:
            if require_customer:
                return jsonify({
                    "success": False,
                    "erro": "Cliente não selecionado. Configure o PDV para permitir vendas sem cliente."
                }), 400
            else:
                # Buscar ou criar CONSUMIDOR FINAL automaticamente
                consumidor_final = db.fetch_one("""
                    SELECT id FROM customers 
                    WHERE name = 'CONSUMIDOR FINAL' OR cnpj = '00000000000'
                    LIMIT 1
                """)
                if consumidor_final:
                    cliente_id = consumidor_final['id']
                else:
                    db.execute_query("""
                        INSERT INTO customers
                            (name, cnpj, address, city, state, active)
                        VALUES
                            ('CONSUMIDOR FINAL', '00000000000', '', '', '', TRUE)
                    """)
                    consumidor_final = db.fetch_one("SELECT id FROM customers WHERE cnpj = '00000000000' LIMIT 1")
                    cliente_id = consumidor_final['id']
                print(f"[PDV FINALIZAÇÃO] Venda sem cliente — CONSUMIDOR FINAL (ID: {cliente_id})")
        
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                "success": False,
                "erro": "Usuário não autenticado"
            }), 401
        
        # Inicializar com valores padrão
        pdv_id = 1
        company_id = 1

        # Obter empresa do CAIXA ABERTO (empresa vinculada ao caixa)
        caixa_info = db.fetch_one("""
            SELECT empresa_id, pdv_id 
            FROM cash_register 
            WHERE user_id = %s AND status = 'open'
            ORDER BY opened_at DESC
            LIMIT 1
        """, (user_id,))
        
        if caixa_info and caixa_info.get('empresa_id'):
            company_id = caixa_info['empresa_id']
            pdv_id = caixa_info.get('pdv_id') or pdv_id
            print(f"[PDV FINALIZAÇÃO] [OK] Empresa do caixa: {company_id} | PDV: {pdv_id}")
        else:
            # Fallback: buscar empresa do PDV padrão
            try:
                pdv_padrao = db.fetch_one("SELECT id, company_id FROM pdv_settings ORDER BY id LIMIT 1")
                company_id = (pdv_padrao.get('company_id') or 1) if pdv_padrao else 1
                pdv_id = pdv_padrao['id'] if pdv_padrao else 1
            except Exception:
                company_id = 1
                pdv_id = 1
            print(f"[PDV FINALIZAÇÃO] [AVISO] Caixa sem empresa, usando PDV padrão: {company_id} | PDV: {pdv_id}")
        
        # Calcular totais
        subtotal = float(carrinho.get('subtotal', 0))
        desconto_total = float(carrinho.get('desconto_total', 0))
        total = float(carrinho.get('total', 0))
        
        # Validar total dos pagamentos
        total_pagamentos = sum(float(p.get('valor', 0)) for p in pagamentos)
        
        print(f"\n{'='*60}")
        print(f"[PDV FINALIZAÇÃO] [DINHEIRO] Iniciando venda com MÚLTIPLOS PAGAMENTOS")
        print(f"[PDV FINALIZAÇÃO] Total da venda: R$ {total:.2f}")
        print(f"[PDV FINALIZAÇÃO] Total dos pagamentos: R$ {total_pagamentos:.2f}")
        print(f"[PDV FINALIZAÇÃO] Troco: R$ {troco:.2f}")
        print(f"[PDV FINALIZAÇÃO] Formas de pagamento: {len(pagamentos)}")
        for i, p in enumerate(pagamentos, 1):
            print(f"[PDV FINALIZAÇÃO]   {i}. {p['forma']}: R$ {p['valor']:.2f}")
        print(f"[PDV FINALIZAÇÃO] Cliente ID: {cliente_id}, Empresa ID: {company_id}, User ID: {user_id}")
        print(f"[PDV FINALIZAÇÃO] Caixa ID na sessão: {session.get('caixa_id')}")
        print(f"{'='*60}\n")
        
        # 1. GRAVAR VENDA (sales)
        # VERSÃO ULTRA SIMPLIFICADA - Apenas campos essenciais que SEMPRE funcionam
        print(f"[PDV FINALIZAÇÃO] Usando INSERT ultra simplificado...")
        
        # Usar o mesmo método do venda_routes.py
        # Buscar caixa aberto do usuário
        caixa_id = session.get('caixa_id')
        if not caixa_id:
            # Tentar buscar caixa aberto
            caixa_row = db.fetch_one("""
                SELECT id FROM cash_register 
                WHERE user_id = %s AND status = 'open' 
                ORDER BY opened_at DESC 
                LIMIT 1
            """, (user_id,))
            caixa_id = caixa_row['id'] if caixa_row else None
            print(f"[PDV FINALIZAÇÃO] Caixa buscado do banco: {caixa_id}")
        
        # Mapear forma de pagamento para ENUM válido: money|pix|debit|credit|boleto
        _map_pagamento = {
            'dinheiro': 'money', 'money': 'money', 'especie': 'money',
            'pix': 'pix',
            'debito': 'debit', 'debit': 'debit', 'cartao_debito': 'debit',
            'credito': 'credit', 'credit': 'credit', 'cartao_credito': 'credit',
            'boleto': 'boleto',
        }
        if len(pagamentos) > 1:
            forma_pagamento_principal = 'money'  # múltiplos: usa money como principal
        else:
            raw = (pagamentos[0].get('forma') or 'money').lower()
            forma_pagamento_principal = _map_pagamento.get(raw, 'money')
        
        sale_id = db.insert("""
            INSERT INTO sales (
                customer_id,
                sale_date,
                payment_method,
                status,
                gross_total,
                discount_total,
                net_total,
                seller_id,
                cash_register_id
            ) VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s)
        """, (
            cliente_id,
            forma_pagamento_principal,
            'confirmed',
            subtotal,
            desconto_total,
            total,
            user_id,
            caixa_id
        ))
        
        print(f"[PDV FINALIZAÇÃO] [OK] Venda criada - ID: {sale_id} | Empresa: {company_id}")
        
        # 2. GRAVAR ITENS (sale_items) E ATUALIZAR ESTOQUE
        for item in carrinho.get('itens', []):
            produto_id = item.get('produto_id')
            quantidade = float(item.get('quantidade', 0))
            preco_unitario = float(item.get('preco_unitario', 0))
            desconto_item = float(item.get('desconto', 0))
            subtotal_item = float(item.get('subtotal', 0))
            
            # Gravar item da venda - Usar mesmo método do venda_routes.py
            # Calcular desconto percentual
            desconto_percentual = 0
            if preco_unitario > 0 and desconto_item > 0:
                desconto_percentual = (desconto_item / (preco_unitario * quantidade)) * 100
            
            # Buscar informações do produto
            prod = db.fetch_one("SELECT id, name, product_type FROM products WHERE id = %s", (produto_id,))
            
            db.insert("""
                INSERT INTO sale_items (
                    sale_id,
                    product_id,
                    product_type,
                    product_name_snapshot,
                    quantity,
                    unit_price,
                    discount_percent,
                    total_price
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                sale_id,
                produto_id,
                prod.get('product_type') if prod else None,
                prod.get('name') if prod else 'Produto',
                quantidade,
                preco_unitario,
                desconto_percentual,
                subtotal_item
            ))
            
            # Atualizar estoque usando Kardex
            print(f"[PDV FINALIZAÇÃO] Item adicionado - Produto ID: {produto_id}, Qtd: {quantidade}")
            
            if registrar_movimentacao:
                # Usar helper Kardex para registrar movimentação completa
                resultado = registrar_movimentacao(
                    produto_id=produto_id,
                    tipo='venda',
                    quantidade=quantidade,
                    origem_tela='PDV',
                    referencia_tipo='venda',
                    referencia_id=sale_id,
                    referencia_codigo=f'PDV-{sale_id}',
                    observacao=f'Venda PDV #{sale_id}',
                    custo_unitario=preco_unitario
                )
                if resultado.get('success'):
                    print(f"[PDV FINALIZAÇÃO] [KARDEX] Estoque: {resultado.get('estoque_anterior')} -> {resultado.get('estoque_posterior')}")
                else:
                    print(f"[PDV FINALIZAÇÃO] [KARDEX] Erro: {resultado.get('error')}")
            else:
                # Fallback: atualização direta
                db.execute("""
                    UPDATE products 
                    SET stock_quantity = stock_quantity - %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (quantidade, produto_id))
                
                # Atualizar current_stock
                try:
                    db.insert("""
                        INSERT INTO current_stock (product_id, location_id, quantity)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """, (produto_id, 1, -abs(quantidade)))
                except Exception as e:
                    print(f"[PDV FINALIZAÇÃO] [AVISO] Erro current_stock: {str(e)}")
        
        # 3. CRIAR CONTAS A RECEBER E FLUXO DE CAIXA PARA CADA PAGAMENTO
        print(f"[PDV FINALIZAÇÃO] Criando integração financeira com {len(pagamentos)} pagamento(s)...")
        try:
            from datetime import datetime, timedelta
            
            sale_date_obj = datetime.now()
            due_date = sale_date_obj.strftime('%Y-%m-%d')
            
            # Mapear forma de pagamento para ENUM
            payment_method_map = {
                'dinheiro': 'cash',
                'debito': 'debit_card',
                'credito': 'credit_card',
                'pix': 'pix',
                'boleto': 'boleto',
                'misto': 'other'
            }
            
            # Criar um lançamento financeiro para cada forma de pagamento
            for idx, pagamento in enumerate(pagamentos, 1):
                forma = pagamento['forma']
                valor = float(pagamento['valor'])
                
                payment_method_converted = payment_method_map.get(forma.lower(), 'other')
                
                # Criar conta a receber individual
                receivable_id = db.insert("""
                    INSERT INTO accounts_receivable 
                    (customer_id, sale_id, description, invoice_number, 
                     installments, issue_date, due_date, total_amount, 
                     payment_method, bank_account_id, status, origin, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    cliente_id,
                    sale_id,
                    f'Venda PDV #{sale_id} - {forma.upper()} ({idx}/{len(pagamentos)})',
                    '',  # invoice_number
                    1,   # installments
                    sale_date_obj.strftime('%Y-%m-%d'),
                    due_date,
                    valor,
                    payment_method_converted,
                    1,  # bank_account_id padrão
                    'pending',
                    'sale',
                    f'Pagamento {idx} de {len(pagamentos)} da venda PDV #{sale_id}'
                ))
                print(f"[PDV FINALIZAÇÃO] [OK] Conta a receber {idx}/{len(pagamentos)} criada - {forma}: R$ {valor:.2f}")
                
                # Criar fluxo de caixa individual
                db.insert("""
                    INSERT INTO cash_flow
                    (date, type, description, amount, bank_account_id, 
                     reference_id, reference_type, chart_account_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    sale_date_obj.strftime('%Y-%m-%d'),
                    'income',
                    f'Venda PDV #{sale_id} - {forma.upper()} ({idx}/{len(pagamentos)})',
                    valor,
                    1,  # bank_account_id padrão
                    receivable_id,
                    'receivable',
                    None
                ))
                print(f"[PDV FINALIZAÇÃO] [OK] Fluxo de caixa {idx}/{len(pagamentos)} registrado")
            
        except Exception as e:
            print(f"[PDV FINALIZAÇÃO] [AVISO] Erro na integração financeira: {str(e)}")
            # Não bloqueia a venda
        
        # 4. GERAR LANÇAMENTOS FINANCEIROS (financial_transactions) - MANTER COMPATIBILIDADE
        try:
            for idx, pagamento in enumerate(pagamentos, 1):
                forma = pagamento['forma']
                valor = float(pagamento['valor'])
                
                descricao = f"Venda PDV #{sale_id} - {forma.upper()}"
                if len(pagamentos) > 1:
                    descricao += f" ({idx}/{len(pagamentos)})"
                
                db.execute("""
                    INSERT INTO financial_transactions (
                        company_id,
                        transaction_type,
                        category,
                        amount,
                        description,
                        transaction_date,
                        payment_method,
                        status,
                        created_at
                    ) VALUES (%s, 'receita', 'venda', %s, %s, NOW(), %s, 'completed', NOW())
                """, (
                    company_id,
                    valor,
                    descricao,
                    forma
                ))
                print(f"[PDV FINALIZAÇÃO] Lançamento financeiro {idx}/{len(pagamentos)} criado - {forma}: R$ {valor:.2f}")
        except Exception as e:
            # Se coluna company_id não existe ou tabela não existe, apenas logar
            if 'company_id' in str(e) or 'financial_transactions' in str(e):
                print(f"[PDV FINALIZAÇÃO] [AVISO] Lançamentos financeiros não criados (tabela ou coluna não existe)")
            else:
                print(f"[PDV FINALIZAÇÃO] [AVISO] Erro ao criar lançamentos financeiros: {str(e)}")
        
        # 5. EMITIR NFC-e (se configurado no PDV e empresa tiver CSC)
        nfce_resultado = None
        formato_impressao = '80mm'  # Padrão
        imprimir_automatico = True
        try:
            print(f"[PDV NFC-e] Verificando configuracoes do PDV ID={pdv_id}...")
            
            # Verificar configurações de NFC-e e impressão do PDV
            pdv_nfce_config = db.fetch_one("""
                SELECT emitir_nfce, imprimir_automatico, formato_impressao, impressora_padrao 
                FROM pdv_settings WHERE id = %s
            """, (pdv_id,))
            
            print(f"[PDV NFC-e] Config encontrada: {pdv_nfce_config}")
            
            emitir_nfce_habilitado = pdv_nfce_config.get('emitir_nfce', 0) if pdv_nfce_config else 0
            formato_impressao = pdv_nfce_config.get('formato_impressao', '80mm') if pdv_nfce_config else '80mm'
            imprimir_automatico = pdv_nfce_config.get('imprimir_automatico', True) if pdv_nfce_config else True
            
            print(f"[PDV NFC-e] emitir_nfce={emitir_nfce_habilitado} | formato={formato_impressao} | imprimir_auto={imprimir_automatico}")
            
            if not emitir_nfce_habilitado:
                print(f"[PDV FINALIZACAO] NFC-e DESABILITADA nas configuracoes do PDV")
            else:
                # Verificar se empresa tem CSC configurado para NFC-e (por ambiente)
                empresa_nfce = db.fetch_one("""
                    SELECT ambiente_nfce, 
                           csc_nfce_homologacao, csc_nfce_producao,
                           csc_nfce
                    FROM empresas WHERE id = %s
                """, (company_id,))
                
                if empresa_nfce:
                    ambiente = empresa_nfce.get('ambiente_nfce', 2)
                    # Verificar CSC do ambiente correto
                    if ambiente == 1:
                        csc = empresa_nfce.get('csc_nfce_producao') or empresa_nfce.get('csc_nfce')
                        ambiente_str = 'PRODUCAO'
                    else:
                        csc = empresa_nfce.get('csc_nfce_homologacao') or empresa_nfce.get('csc_nfce')
                        ambiente_str = 'HOMOLOGACAO'
                    
                    if csc:
                        print(f"[PDV FINALIZACAO] Emitindo NFC-e em {ambiente_str}...")
                        from app.services.nfce_service import NFCeService
                        
                        nfce_service = NFCeService(company_id)
                        nfce_resultado = nfce_service.emitir(sale_id)
                        
                        if nfce_resultado.get('sucesso'):
                            print(f"[PDV FINALIZACAO] NFC-e emitida! Numero: {nfce_resultado.get('numero_nfce')}")
                        else:
                            print(f"[PDV FINALIZACAO] NFC-e nao emitida: {nfce_resultado.get('erro')}")
                    else:
                        print(f"[PDV FINALIZACAO] NFC-e nao configurada (CSC {ambiente_str} vazio)")
                else:
                    print(f"[PDV FINALIZACAO] NFC-e nao configurada para esta empresa")
        except Exception as e:
            import traceback
            print(f"[PDV FINALIZACAO] Erro ao emitir NFC-e: {str(e)}")
            traceback.print_exc()
        
        # 6. LIMPAR CARRINHO DA SESSÃO
        session['carrinho_pdv'] = {
            "cliente_id": None,
            "cliente_nome": "**CLIENTE A VISTA**",
            "cliente_cpf": "000.000.000-00",
            "itens": [],
            "subtotal": 0.0,
            "desconto_total": 0.0,
            "total": 0.0
        }
        session.modified = True
        
        print(f"[PDV FINALIZAÇÃO] [OK] Venda finalizada com sucesso! ID: {sale_id}")
        print(f"[PDV FINALIZAÇÃO] Troco devolvido: R$ {troco:.2f}")
        print(f"{'='*60}\n")
        
        # Preparar resposta
        resposta = {
            "success": True,
            "mensagem": "Venda finalizada com sucesso!",
            "sale_id": sale_id,
            "numero_venda": sale_id,
            "total": total,
            "troco": troco,
            "pagamentos": pagamentos,
            "forma_pagamento_principal": forma_pagamento_principal
        }
        
        # Adicionar dados da NFC-e se emitida
        if nfce_resultado and nfce_resultado.get('sucesso'):
            resposta['nfce'] = {
                'numero': nfce_resultado.get('numero_nfce'),
                'chave': nfce_resultado.get('chave_acesso'),
                'protocolo': nfce_resultado.get('protocolo'),
                'url_impressao': f'/nfce/imprimir/{sale_id}?formato={formato_impressao}',
                'imprimir_automatico': imprimir_automatico,
                'formato': formato_impressao
            }
        
        return jsonify(resposta)
        
    except Exception as e:
        print(f"[PDV FINALIZAÇÃO] [X] Erro: {str(e)}")
        return jsonify({
            "success": False,
            "erro": f"Erro ao finalizar venda: {str(e)}"
        }), 500
